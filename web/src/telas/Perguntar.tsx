import { Alert, Button, Card, FileInput, Group, Loader, MultiSelect, SegmentedControl, Select, Stack, Text, Textarea } from "@mantine/core";
import { useState } from "react";

import { api } from "../api";
import Resultado from "../componentes/Resultado";
import { FAIXAS, SEGMENTOS } from "../formato";
import type { Modo, Saida } from "../tipos";

const EXEMPLOS: { mode: Modo; query: string; segment?: string }[] = [
  { mode: "analisar", query: "Que duração de Reels mais aparece entre os de alto engajamento?" },
  { mode: "recomendar", query: "Como a @impulsostone deveria fazer Reels para empreendedoras de alimentação?", segment: "alimentacao" },
  { mode: "analisar", query: "Que tipo de gancho aparece mais nos Reels de alto engajamento?" },
  { mode: "gerar_criativo", query: "Preciso de um Reels para atrair donos e donas de salão de beleza para o programa", segment: "beleza" },
];

const ROTEIRO_EXEMPLO = `Cena 1 (dona da loja de roupas falando para a câmera): "Sabe por que sua loja vende muito em dezembro e mesmo assim falta dinheiro em janeiro?"
Cena 2: ela mostra o caderno de vendas e explica que o dinheiro do Natal entra, mas os boletos dos fornecedores vencem depois.
Cena 3: dica prática: separar toda semana uma parte do que entra para pagar os fornecedores de janeiro.
Cena 4: "Quer aprender a organizar o caixa da sua loja? O Impulso Stone tem curso gratuito. Link na bio."`;

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Perguntar() {
  const [modo, setModo] = useState<Modo>("analisar");
  const [query, setQuery] = useState("");
  const [segmento, setSegmento] = useState("");
  const [faixas, setFaixas] = useState<string[]>([]);
  const [material, setMaterial] = useState<"video" | "roteiro">("video");
  const [video, setVideo] = useState<File | null>(null);
  const [roteiro, setRoteiro] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [etapa, setEtapa] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [saida, setSaida] = useState<Saida | null>(null);
  const avaliando = modo === "avaliar";

  // Avaliar roda em segundo plano na API (a leitura do vídeo leva minutos): envia e consulta o progresso.
  async function avaliar() {
    const dados = new FormData();
    dados.append("query", query.trim() || "Avaliar meu vídeo");
    if (segmento) dados.append("segment", segmento);
    if (material === "video" && video) dados.append("arquivo", video);
    else dados.append("roteiro", roteiro);
    const { id } = await api.avaliar(dados);
    for (;;) {
      const estado = await api.estadoAvaliacao(id);
      setEtapa(estado.etapa);
      if (estado.pronto) {
        if (estado.erro) throw new Error(estado.erro);
        return estado.saida!;
      }
      await espera(2000);
    }
  }

  async function enviar() {
    setCarregando(true);
    setErro(null);
    setEtapa(null);
    setSaida(null);
    try {
      setSaida(avaliando ? await avaliar() : await api.consultar({
        mode: modo, query, segment: segmento || null, filters: faixas.length ? { faixa: faixas } : null,
      }));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(false);
    }
  }

  const pronto = avaliando ? (material === "video" ? Boolean(video) : roteiro.trim().length > 20) : query.trim().length >= 3;

  return (
    <Stack gap="lg">
      <Card withBorder padding="lg">
        <Stack>
          <SegmentedControl
            value={modo}
            onChange={(v) => setModo(v as Modo)}
            data={[
              { value: "analisar", label: "Analisar" },
              { value: "recomendar", label: "Recomendar" },
              { value: "gerar_criativo", label: "Gerar criativo" },
              { value: "avaliar", label: "Avaliar vídeo" },
            ]}
          />
          {avaliando ? (
            <>
              <SegmentedControl size="xs" w="fit-content" value={material} onChange={(v) => setMaterial(v as "video" | "roteiro")}
                data={[{ value: "video", label: "Enviar vídeo" }, { value: "roteiro", label: "Colar roteiro" }]} />
              {material === "video" ? (
                <FileInput label="Vídeo do Reel" description="MP4 ou MOV, até 300 MB. A leitura leva de 1 a 3 minutos."
                  placeholder="Escolher arquivo" accept="video/*" value={video} onChange={setVideo} clearable />
              ) : (
                <Textarea label="Roteiro" description="Ainda não gravou? Cole o roteiro: a duração é estimada pelo texto e o visual não é avaliado."
                  autosize minRows={5} value={roteiro} onChange={(e) => setRoteiro(e.currentTarget.value)}
                  placeholder={ROTEIRO_EXEMPLO} />
              )}
              <Textarea label="Contexto (opcional)" placeholder="Ex.: Reels para atrair lojistas de roupa para o programa"
                autosize minRows={1} value={query} onChange={(e) => setQuery(e.currentTarget.value)} />
              <Group grow align="flex-start">
                <Select label="Setor (para os Reels de exemplo)" data={SEGMENTOS} value={segmento} onChange={(v) => setSegmento(v ?? "")} allowDeselect={false} />
              </Group>
              <Group justify="space-between">
                {material === "roteiro" ? (
                  <Button size="compact-xs" variant="subtle" color="gray" onClick={() => { setRoteiro(ROTEIRO_EXEMPLO); setSegmento("varejo"); }}>
                    Usar roteiro de exemplo
                  </Button>
                ) : <span />}
                <Button onClick={enviar} loading={carregando} disabled={!pronto}>Avaliar</Button>
              </Group>
            </>
          ) : (
            <>
              <Textarea
                label={{ analisar: "O que você quer saber sobre os Reels de alto engajamento?",
                         recomendar: "Para que público ou objetivo você quer recomendações?",
                         gerar_criativo: "Que Reels você precisa? Diga o público, o objetivo ou o tema.",
                         avaliar: "" }[modo]}
                placeholder="Ex.: que formato de vídeo aparece mais entre os Reels de alto engajamento?"
                autosize minRows={2} value={query} onChange={(e) => setQuery(e.currentTarget.value)}
              />
              <Group grow align="flex-start">
                <Select label="Setor do empreendedor" data={SEGMENTOS} value={segmento} onChange={(v) => setSegmento(v ?? "")} allowDeselect={false} />
                <MultiSelect label="Tamanho do perfil" placeholder="Todos" data={FAIXAS} value={faixas} onChange={setFaixas} clearable />
              </Group>
              <Group justify="space-between">
                <Group gap="xs">
                  <Text size="xs" c="dimmed">Exemplos:</Text>
                  {EXEMPLOS.map((ex) => (
                    <Button key={ex.query} size="compact-xs" variant="subtle" color="gray"
                      onClick={() => { setModo(ex.mode); setQuery(ex.query); setSegmento(ex.segment ?? ""); setFaixas([]); }}>
                      {ex.query.length > 48 ? `${ex.query.slice(0, 48)}…` : ex.query}
                    </Button>
                  ))}
                </Group>
                <Button onClick={enviar} loading={carregando} disabled={!pronto}>
                  {{ analisar: "Analisar", recomendar: "Recomendar", gerar_criativo: "Gerar 3 criativos", avaliar: "Avaliar" }[modo]}
                </Button>
              </Group>
            </>
          )}
        </Stack>
      </Card>

      {carregando && (
        <Group justify="center" py="xl">
          <Loader size="sm" />
          <Text c="dimmed" size="sm">
            {avaliando
              ? `${etapa ?? "Enviando"}…`
              : modo === "gerar_criativo"
                ? "Consultando a base, escrevendo os 3 criativos e revisando o tom (1 a 2 min)…"
                : "Consultando a base e escrevendo a resposta (5 a 30 s)…"}
          </Text>
        </Group>
      )}
      {erro && <Alert color="red" title="Não foi possível responder">{erro}</Alert>}
      {saida && !carregando && <Resultado saida={saida} />}
    </Stack>
  );
}
