import { Box, Button, Collapse, Group, Stack, Text, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChevronDown } from "@tabler/icons-react";

import { nomeAchado, num, pct, rotuloRecorte, vezes } from "../formato";
import type { Achado } from "../tipos";
import { SeloRobustez } from "./Selos";

// Gráfico de halteres com eixo fixo de 0 a 100% (o mesmo em todas as listas, para comparar de olho): ponto cinza =
// controle, ponto verde = top. O intervalo de confiança fica no tooltip; na tela, o selo diz o quanto confiar.
const x = (f: number) => `${Math.min(100, Math.max(0, f * 100))}%`;

function Trilho({ a }: { a: Achado }) {
  const [ini, fim] = [Math.min(a.freq_top, a.freq_controle), Math.max(a.freq_top, a.freq_controle)];
  const destaque = a.robustez === "robusto" || a.robustez === "fragil";
  const cor = destaque ? "var(--mantine-color-stone-6)" : "var(--mantine-color-gray-5)";
  return (
    <Tooltip label={`Top ${pct(a.freq_top)} × controle ${pct(a.freq_controle)}. Lift ${num(a.lift)}, intervalo de 95% de ${num(a.ic95_min)} a ${num(a.ic95_max)}.`}>
      <div className="trilho">
        <div className="trilho-ligacao" style={{ left: x(ini), width: `calc(${x(fim)} - ${x(ini)})`, background: cor }} />
        <div className="trilho-ponto" style={{ left: x(a.freq_controle), background: "var(--mantine-color-gray-5)" }} />
        <div className="trilho-ponto" style={{ left: x(a.freq_top), background: cor }} />
      </div>
    </Tooltip>
  );
}

// Cabeçalho do eixo: 0%, 25%, 50%, 75% e 100% alinhados com as linhas de grade dos trilhos.
export function Eixo() {
  return (
    <div className="achado-grade achado-eixo">
      <span />
      <div className="eixo-marcas">
        {[0, 25, 50, 75, 100].map((v) => <span key={v} style={{ left: `${v}%` }}>{v}%</span>)}
      </div>
      <Text size="xs" c="dimmed" ta="right">top × controle</Text>
      <span className="achado-col-selo" />
    </div>
  );
}

function LinhaAchado({ a }: { a: Achado }) {
  return (
    <div className="achado-grade achado-linha">
      <div style={{ minWidth: 0 }}>
        <Text size="sm" fw={500}>{nomeAchado(a.descricao)}</Text>
        <Text size="xs" c="dimmed">{a.n_top} Reels no top{a.recorte ? ` · ${rotuloRecorte(a.recorte)}` : ""}</Text>
        <Box className="achado-selo-abaixo" mt={2}><SeloRobustez robustez={a.robustez} /></Box>
      </div>
      <div className="achado-col-trilho"><Trilho a={a} /></div>
      <div style={{ textAlign: "right" }}>
        <Text size="sm" style={{ fontVariantNumeric: "tabular-nums" }}>
          <Text span inherit fw={600}>{pct(a.freq_top)}</Text> <Text span inherit c="dimmed">× {pct(a.freq_controle)}</Text>
        </Text>
        <Text size="xs" c="dimmed">{a.robustez === "sem_diferenca" ? "sem diferença" : vezes(a.lift, a.robustez).replace(" no top", "")}</Text>
      </div>
      <div className="achado-col-selo"><SeloRobustez robustez={a.robustez} /></div>
    </div>
  );
}

// Linhas de achados com o eixo em cima. `compacto` (painéis estreitos): sem a coluna do selo, que vai para baixo do nome.
export function ListaAchados({ achados, eixo = true, compacto = false }: { achados: Achado[]; eixo?: boolean; compacto?: boolean }) {
  return (
    <div className={compacto ? "achados-compactos" : undefined}>
      {eixo && <Eixo />}
      {achados.map((a) => <LinhaAchado key={a.campo + a.valor + (a.recorte ?? "")} a={a} />)}
    </div>
  );
}

export function Legenda() {
  return (
    <Group gap="md">
      <Group gap={6}><Box w={10} h={10} bg="stone.6" style={{ borderRadius: 5 }} /><Text size="xs" c="dimmed">Top 10%</Text></Group>
      <Group gap={6}><Box w={10} h={10} bg="gray.5" style={{ borderRadius: 5 }} /><Text size="xs" c="dimmed">Controle sorteado</Text></Group>
    </Group>
  );
}

export function Grupo({ titulo, ajuda, achados }: { titulo: string; ajuda?: string; achados: Achado[] }) {
  return (
    <div>
      <Group gap={8} mb={4}>
        <Text fw={500} size="sm">{titulo}</Text>
        {ajuda && <Text size="sm" c="dimmed">{ajuda}</Text>}
      </Group>
      <ListaAchados achados={achados} />
    </div>
  );
}

// Achados de uma resposta: o que aparece mais e menos no top e, recolhido, o que não diferencia.
export function AchadosDaResposta({ achados }: { achados: Achado[] }) {
  const [verSem, { toggle }] = useDisclosure(false);
  const comDiferenca = achados.filter((a) => a.robustez !== "sem_diferenca");
  const mais = comDiferenca.filter((a) => a.dif_pp > 0);
  const menos = comDiferenca.filter((a) => a.dif_pp <= 0);
  const sem = achados.filter((a) => a.robustez === "sem_diferenca");
  if (!achados.length) return null;

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Text fw={600}>Achados da base</Text>
        <Legenda />
      </Group>
      {mais.length > 0 && <Grupo titulo="Aparecem mais no top" ajuda="o que fazer" achados={mais} />}
      {menos.length > 0 && <Grupo titulo="Aparecem menos no top" ajuda="o que evitar" achados={menos} />}
      {sem.length > 0 && (
        <div>
          <Button variant="subtle" color="gray" size="compact-sm" onClick={toggle}
            rightSection={<IconChevronDown size={14} style={{ transform: verSem ? "rotate(180deg)" : undefined }} />}>
            {sem.length} {sem.length === 1 ? "característica" : "características"} sem diferença entre top e controle
          </Button>
          <Collapse expanded={verSem}>
            <Box mt="xs"><ListaAchados achados={sem} /></Box>
          </Collapse>
        </div>
      )}
    </Stack>
  );
}
