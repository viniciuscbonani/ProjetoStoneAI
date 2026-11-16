import { Alert, Button, Card, Group, Loader, MultiSelect, SegmentedControl, Select, Stack, Text, Textarea } from "@mantine/core";
import { useState } from "react";

import { api } from "../api";
import Resultado from "../componentes/Resultado";
import { FAIXAS, SEGMENTOS } from "../formato";
import type { Modo, Saida } from "../tipos";

const EXEMPLOS: { mode: Modo; query: string; segment?: string }[] = [
  { mode: "analisar", query: "Que duração de Reels mais aparece entre os de alto engajamento?" },
  { mode: "recomendar", query: "Como a @impulsostone deveria fazer Reels para empreendedoras de alimentação?", segment: "alimentacao" },
  { mode: "analisar", query: "Que tipo de gancho aparece mais nos Reels de alto engajamento?" },
];

export default function Perguntar() {
  const [modo, setModo] = useState<Modo>("analisar");
  const [query, setQuery] = useState("");
  const [segmento, setSegmento] = useState("");
  const [faixas, setFaixas] = useState<string[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [saida, setSaida] = useState<Saida | null>(null);

  async function enviar() {
    setCarregando(true);
    setErro(null);
    try {
      setSaida(await api.consultar({
        mode: modo, query, segment: segmento || null, filters: faixas.length ? { faixa: faixas } : null,
      }));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(false);
    }
  }

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
              { value: "gerar_criativo", label: "Gerar criativo (em breve)", disabled: true },
              { value: "avaliar", label: "Avaliar vídeo (em breve)", disabled: true },
            ]}
          />
          <Textarea
            label={modo === "analisar" ? "O que você quer saber sobre os Reels de alto engajamento?" : "Para que público ou objetivo você quer recomendações?"}
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
            <Button onClick={enviar} loading={carregando} disabled={query.trim().length < 3}>
              {modo === "analisar" ? "Analisar" : "Recomendar"}
            </Button>
          </Group>
        </Stack>
      </Card>

      {carregando && (
        <Group justify="center" py="xl">
          <Loader size="sm" />
          <Text c="dimmed" size="sm">Consultando a base e escrevendo a resposta (5 a 30 s)…</Text>
        </Group>
      )}
      {erro && <Alert color="red" title="Não foi possível responder">{erro}</Alert>}
      {saida && !carregando && <Resultado saida={saida} />}
    </Stack>
  );
}
