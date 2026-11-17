import {
  Box, Button, Grid, Group, Loader, Paper, SegmentedControl, Stack, Text, Textarea, TextInput, Title, UnstyledButton,
} from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconBuildingStore, IconFileText, IconMovie, IconUpload, IconX } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { api } from "../api";
import { MiniReel } from "../componentes/CartaoReel";
import { numerarCitacoes, TextoComCitacoes } from "../componentes/Citacoes";
import { Avisos, Erro, Escolha, Inicio, MetaExecucao, Tela, Trabalhando } from "../componentes/Comum";
import { SeloRobustez } from "../componentes/Selos";
import { limparTarefa, rodar, useExecucao, useRecentes, useTarefa, useTitulo } from "../contexto";
import { rotuloValor, SEGMENTOS } from "../formato";
import type { Avaliacao, Execucao, Ponto, ReferencePost } from "../tipos";

const ROTEIRO_EXEMPLO = `Cena 1 (dona da loja de roupas falando para a câmera): "Sabe por que sua loja vende muito em dezembro e mesmo assim falta dinheiro em janeiro?"
Cena 2: ela mostra o caderno de vendas e explica que o dinheiro do Natal entra, mas os boletos dos fornecedores vencem depois.
Cena 3: dica prática: separar toda semana uma parte do que entra para pagar os fornecedores de janeiro.
Cena 4: "Quer aprender a organizar o caixa da sua loja? O Impulso Stone tem curso gratuito. Link na bio."`;

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Etapas da API (agente/api.py, PROXIMA_ETAPA), na ordem em que aparecem.
const ETAPAS: [string, string][] = [
  ["Na fila", "Enviando"],
  ["Lendo", "Lendo o material"],
  ["Comparando", "Comparando com os achados da base"],
  ["Escrevendo", "Escrevendo os pontos fortes e a melhorar"],
  ["Revisando", "Revisando"],
];
const indiceEtapa = (etapa: string | null) =>
  etapa?.startsWith("Finalizando") ? ETAPAS.length - 1 : Math.max(0, ETAPAS.findIndex(([p]) => etapa?.startsWith(p)));

function Formulario({ enviar, erro }: { enviar: (dados: FormData, fonte: "video" | "roteiro") => void; erro?: string }) {
  const [material, setMaterial] = useState<"video" | "roteiro">("video");
  const [video, setVideo] = useState<File | null>(null);
  const [roteiro, setRoteiro] = useState("");
  const [contexto, setContexto] = useState("");
  const [segmento, setSegmento] = useState("");
  const pronto = material === "video" ? Boolean(video) : roteiro.trim().length > 20;

  function avaliar() {
    const dados = new FormData();
    // Sem contexto, o nome do arquivo identifica a avaliação nos Recentes.
    dados.append("query", contexto.trim() || (material === "video" && video ? `Avaliar ${video.name}` : "Avaliar meu roteiro"));
    if (segmento) dados.append("segment", segmento);
    if (material === "video" && video) dados.append("arquivo", video);
    else dados.append("roteiro", roteiro);
    enviar(dados, material);
  }

  return (
    <Inicio titulo="Avalie um Reel antes de publicar"
      abaixo={(
        <Stack gap={2} mt="md" px={6}>
          <Text size="sm" c="dimmed" px={12} py={6}>
            {material === "video"
              ? "MP4 ou MOV, até 300 MB. A leitura do vídeo leva de 1 a 3 minutos."
              : "Sem vídeo, a duração é estimada pelo texto e o visual não entra na avaliação."}
          </Text>
          {material === "roteiro" && (
            <UnstyledButton className="sugestao" onClick={() => { setRoteiro(ROTEIRO_EXEMPLO); setSegmento("varejo"); }}>
              <IconFileText size={18} stroke={1.5} />
              Usar um roteiro de exemplo
            </UnstyledButton>
          )}
        </Stack>
      )}>
      {erro && <Box mb="md"><Erro titulo="Não foi possível avaliar">{erro}</Erro></Box>}
      <Paper radius={24} p="sm" className="compositor">
        <SegmentedControl size="xs" radius="xl" mb="sm" value={material} onChange={(v) => setMaterial(v as "video" | "roteiro")}
          data={[{ value: "video", label: "Vídeo" }, { value: "roteiro", label: "Roteiro" }]} />
        {material === "video" ? (
          <Dropzone onDrop={(f) => setVideo(f[0] ?? null)} accept={["video/*"]} maxSize={300 * 1024 * 1024} multiple={false}
            radius="lg" p="lg" bg="transparent">
            <Group justify="center" gap="sm" style={{ pointerEvents: "none" }} py="md">
              <Dropzone.Reject><IconX size={22} color="var(--mantine-color-red-6)" /></Dropzone.Reject>
              <Dropzone.Idle>{video ? <IconMovie size={22} stroke={1.5} /> : <IconUpload size={22} stroke={1.5} />}</Dropzone.Idle>
              <Dropzone.Accept><IconUpload size={22} stroke={1.5} /></Dropzone.Accept>
              {video ? (
                <Text size="sm">{video.name} <Text span c="dimmed" size="sm">· {(video.size / 1024 / 1024).toFixed(1)} MB · trocar</Text></Text>
              ) : (
                <Text size="sm" c="dimmed">Arraste o vídeo aqui ou clique para escolher</Text>
              )}
            </Group>
          </Dropzone>
        ) : (
          <Textarea variant="unstyled" autosize minRows={5} maxRows={14} value={roteiro} autoFocus
            onChange={(e) => setRoteiro(e.currentTarget.value)} placeholder="Cole o roteiro, cena por cena…"
            styles={{ input: { fontSize: 15, lineHeight: 1.55, paddingInline: 8, border: 0 } }} />
        )}
        <TextInput variant="unstyled" mt={4} placeholder="Contexto (opcional): ex.: Reels para atrair lojistas de roupa"
          value={contexto} onChange={(e) => setContexto(e.currentTarget.value)} styles={{ input: { paddingInline: 8 } }} />
        <Group justify="space-between" mt={4} wrap="nowrap">
          <Escolha icone={IconBuildingStore} opcoes={SEGMENTOS} valor={segmento} onChange={(v) => setSegmento(v as string)} />
          <Button radius="xl" size="sm" onClick={() => pronto && avaliar()} variant={pronto ? "filled" : "default"}>Avaliar</Button>
        </Group>
      </Paper>
    </Inicio>
  );
}

function Secao({ titulo, pontos, vazio, refs, numeros }: {
  titulo: string; pontos: Ponto[]; vazio: string; refs: ReferencePost[]; numeros: Map<string, number>;
}) {
  return (
    <div>
      <Group gap={8} mb="sm">
        <Text fw={600}>{titulo}</Text>
        <Text size="sm" c="dimmed">{pontos.length}</Text>
      </Group>
      <Paper className="lista" style={{ overflow: "hidden" }}>
        {pontos.length === 0 && <Text size="sm" c="dimmed" p="md">{vazio}</Text>}
        {pontos.map((p) => (
          <Group key={p.achado} p="md" gap="md" wrap="nowrap" align="flex-start">
            <Box style={{ flex: 1, minWidth: 0 }}>
              <TextoComCitacoes texto={p.texto} refs={refs} numeros={numeros} />
              <Box mt={6}><SeloRobustez robustez={p.robustez} /></Box>
            </Box>
            <Group gap={6} wrap="nowrap" visibleFrom="xs">
              {p.referencias.slice(0, 2).map((c) => <MiniReel key={c} codigo={c} refs={refs} largura={46} />)}
            </Group>
          </Group>
        ))}
      </Paper>
    </div>
  );
}

// O que o agente leu do vídeo (ou do roteiro), na ordem em que importa para a avaliação.
const LEITURA: [string, string][] = [
  ["duracao_s", "Duração"], ["formato_video", "Formato"], ["tipo_hook", "Tipo de gancho"], ["hook_texto", "Gancho"],
  ["tema_principal", "Tema"], ["pilar_impulso", "Pilar"], ["tem_rosto", "Rosto em cena"], ["texto_na_tela", "Texto na tela"],
  ["tipo_cta", "CTA"], ["abordagem", "Abordagem"], ["ritmo_cortes", "Ritmo de cortes"],
];

function Leitura({ a }: { a: Avaliacao }) {
  const l = a.leitura;
  return (
    <Paper p="lg">
      <Text fw={600} mb="md">Como o agente leu {a.fonte === "video" ? "o vídeo" : "o roteiro"}</Text>
      <Stack gap={8}>
        {LEITURA.filter(([k]) => l[k] !== undefined && l[k] !== "").map(([k, nome]) => (
          <Group key={k} justify="space-between" align="flex-start" wrap="nowrap" gap="md">
            <Text size="sm" c="dimmed" style={{ flexShrink: 0 }}>{nome}</Text>
            <Text size="sm" ta="right" fw={500}>
              {k === "duracao_s" ? `${Math.round(Number(l[k]))} s${l.duracao_estimada ? " (estimada)" : ""}`
                : k === "hook_texto" ? `“${l[k]}”` : rotuloValor(l[k])}
            </Text>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}

function Resultado({ e }: { e: Execucao }) {
  const navigate = useNavigate();
  const s = e.saida!;
  const a = s.avaliacao!;
  const pontos = [...a.pontos_fortes, ...a.pontos_a_melhorar, ...a.sem_efeito];
  const numeros = numerarCitacoes(s.reference_posts, s.explanation, ...pontos.map((p) => p.texto));

  return (
    <Tela>
      <Grid gap="xl">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Stack gap="xl">
            <div>
              <Title order={1} fz={{ base: 22, sm: 27 }} fw={600} lh={1.3} mb="sm">
                Avaliação {a.fonte === "video" ? "do vídeo" : "do roteiro"}
              </Title>
              <MetaExecucao e={e} />
            </div>
            <div>
              <TextoComCitacoes texto={s.explanation} refs={s.reference_posts} numeros={numeros} size="15px" />
              <Box mt="sm"><Avisos avisos={s.warnings} /></Box>
            </div>
            <Secao titulo="Pontos fortes" pontos={a.pontos_fortes} refs={s.reference_posts}
              numeros={numeros} vazio="Nenhuma característica que aparece mais no top." />
            <Secao titulo="A melhorar" pontos={a.pontos_a_melhorar} refs={s.reference_posts}
              numeros={numeros} vazio="Nada a mudar segundo os achados da base." />
            {a.sem_efeito.length > 0 && (
              <Secao titulo="Não precisa mudar" pontos={a.sem_efeito} refs={s.reference_posts}
                numeros={numeros} vazio="" />
            )}
            <Text size="xs" c="dimmed">Comparação com os padrões dos Reels de alto engajamento da base, não previsão de resultado.</Text>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap="md" style={{ position: "sticky", top: 24 }}>
            <Leitura a={a} />
            <Button variant="default" leftSection={<IconUpload size={16} />} onClick={() => navigate("/avaliar")}>
              Avaliar outro material
            </Button>
          </Stack>
        </Grid.Col>
      </Grid>
    </Tela>
  );
}

export default function Avaliar() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { atualizar } = useRecentes();
  const { execucao, erro: erroCarga } = useExecucao(runId);
  const tarefa = useTarefa("avaliar");
  useTitulo(tarefa?.rodando ? tarefa.titulo : runId ? "Avaliação" : "Avaliar");

  useEffect(() => {
    if (runId) limparTarefa("avaliar");
  }, [runId]);

  // A avaliação roda em segundo plano na API (a leitura do vídeo leva minutos): envia e consulta o progresso. O laço
  // fica fora da tela (rodar), então continua se a pessoa for para outra tela.
  function enviar(dados: FormData, fonte: "video" | "roteiro") {
    const entrada = { mode: "avaliar" as const, query: String(dados.get("query")), segment: (dados.get("segment") as string) || null };
    rodar("avaliar", { titulo: entrada.query, fonte }, async (avisar) => {
      const inicio = Date.now();
      const { id } = await api.avaliar(dados);
      for (;;) {
        const estado = await api.estadoAvaliacao(id);
        avisar(estado.etapa);
        if (estado.pronto) {
          if (estado.erro) throw new Error(estado.erro);
          const saida = estado.saida!;
          return { run_id: saida.run_id, quando: new Date().toISOString(), duracao_s: (Date.now() - inicio) / 1000, entrada, erro: null, saida };
        }
        await espera(2000);
      }
    }, navigate, atualizar);
  }

  if (tarefa?.rodando) {
    const video = tarefa.fonte === "video";
    const etapas = ETAPAS.map(([, nome], i) => (i === 1 ? (video ? "Lendo o vídeo: quadros, transcrição e rubrica" : "Lendo o roteiro") : nome));
    return (
      <Tela largura={720}>
        <Title order={1} fz={{ base: 22, sm: 27 }} fw={600} lh={1.3} mb={40}>{tarefa.titulo}</Title>
        <Trabalhando etapas={etapas} atual={indiceEtapa(tarefa.etapa ?? null)} inicio={tarefa.inicio}
          previsao={video ? "1 a 3 min" : "cerca de 30 s"} />
      </Tela>
    );
  }
  if (!runId) return <Formulario enviar={enviar} erro={tarefa?.erro} />;
  if (erroCarga) return <Tela><Erro titulo="Não foi possível abrir esta execução">{erroCarga}</Erro></Tela>;
  if (!execucao) return <Tela><Loader size="sm" /></Tela>;
  if (!execucao.saida?.avaliacao) return <Tela><Erro titulo="Esta execução não terminou">{execucao.erro}</Erro></Tela>;
  return <Resultado e={execucao} />;
}
