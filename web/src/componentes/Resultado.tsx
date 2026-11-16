import { Alert, Anchor, Badge, Card, Group, Progress, SimpleGrid, Stack, Text, Title, Tooltip, Typography } from "@mantine/core";
import Markdown from "react-markdown";

import { useAbrirReel } from "../App";
import { num, pct, ROBUSTEZ } from "../formato";
import type { Achado, Saida } from "../tipos";
import CartaoReel from "./CartaoReel";

export function SeloRobustez({ robustez }: { robustez: Achado["robustez"] }) {
  const r = ROBUSTEZ[robustez];
  return (
    <Tooltip label={r.ajuda}>
      <Badge color={r.cor} variant="light" style={{ flexShrink: 0, overflow: "visible" }}>{r.rotulo}</Badge>
    </Tooltip>
  );
}

export function CartaoAchado({ a }: { a: Achado }) {
  const nome = a.descricao.split(" — ")[0];
  return (
    <Card withBorder padding="sm">
      <Group justify="space-between" mb={6} wrap="nowrap">
        <Text fw={600} size="sm">{nome}</Text>
        <SeloRobustez robustez={a.robustez} />
      </Group>
      <Stack gap={4}>
        <Group gap="xs" wrap="nowrap">
          <Text size="xs" w={56}>Top</Text>
          <Progress value={a.freq_top * 100} color="stone" style={{ flex: 1 }} />
          <Text size="xs" w={36} ta="right">{pct(a.freq_top)}</Text>
        </Group>
        <Group gap="xs" wrap="nowrap">
          <Text size="xs" w={56}>Controle</Text>
          <Progress value={a.freq_controle * 100} color="gray.5" style={{ flex: 1 }} />
          <Text size="xs" w={36} ta="right">{pct(a.freq_controle)}</Text>
        </Group>
      </Stack>
      <Text size="xs" c="dimmed" mt={6}>
        lift {num(a.lift)} (IC95 {num(a.ic95_min)}–{num(a.ic95_max)}) · {a.n_top} Reels no top · base: {a.recorte ?? "amostra inteira"}
      </Text>
    </Card>
  );
}

// [DbnuKRmRJ_H] no texto vira link que abre a gaveta do Reel.
const comLinks = (texto: string) => texto.replace(/\[([A-Za-z0-9_-]{9,})\]/g, "[$1](#reel-$1)");

export default function Resultado({ saida }: { saida: Saida }) {
  const abrirReel = useAbrirReel();
  const mais = saida.findings.filter((a) => a.dif_pp > 0);
  const menos = saida.findings.filter((a) => a.dif_pp < 0);

  return (
    <Stack gap="lg">
      <Card withBorder padding="lg">
        <Group justify="space-between" mb="sm">
          <Title order={4}>Resposta</Title>
          <Group gap="xs">
            <Text size="xs" c="dimmed">Confiança</Text>
            <SeloRobustez robustez={saida.confidence_flag} />
          </Group>
        </Group>
        <Typography>
          <Markdown
            components={{
              a: ({ href, children }) =>
                href?.startsWith("#reel-") ? (
                  <Anchor component="button" onClick={() => abrirReel(href.slice(6))} fw={600}>{children}</Anchor>
                ) : (
                  <Anchor href={href} target="_blank">{children}</Anchor>
                ),
            }}
          >
            {comLinks(saida.explanation)}
          </Markdown>
        </Typography>
        {saida.warnings.map((w) => (
          <Alert key={w} color="yellow" variant="light" mt="sm" p="xs"><Text size="sm">{w}</Text></Alert>
        ))}
        <Text size="xs" c="dimmed" mt="sm">Execução {saida.run_id} · padrões observados, não garantia de resultado</Text>
      </Card>

      {mais.length > 0 && (
        <div>
          <Title order={5} mb="xs">Aparecem mais no top</Title>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>{mais.map((a) => <CartaoAchado key={a.campo + a.valor + a.recorte} a={a} />)}</SimpleGrid>
        </div>
      )}
      {menos.length > 0 && (
        <div>
          <Title order={5} mb="xs">Aparecem menos no top</Title>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>{menos.map((a) => <CartaoAchado key={a.campo + a.valor + a.recorte} a={a} />)}</SimpleGrid>
        </div>
      )}

      {saida.reference_posts.length > 0 && (
        <div>
          <Title order={5} mb="xs">Reels de referência</Title>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
            {saida.reference_posts.map((r) => <CartaoReel key={r.shortCode} r={r} />)}
          </SimpleGrid>
        </div>
      )}

      {saida.profiles.length > 0 && (
        <div>
          <Title order={5} mb="xs">Perfis em destaque</Title>
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
            {saida.profiles.map((p) => (
              <Card key={p.perfil} withBorder padding="sm">
                <Anchor href={`https://www.instagram.com/${p.perfil}/`} target="_blank" fw={600}>@{p.perfil}</Anchor>
                <Text size="xs" c="dimmed">{p.faixa} · {p.seguidores.toLocaleString("pt-BR")} seguidores</Text>
                <Text size="sm" mt={4}>{p.n_top} de {p.n_amostra} Reels no top</Text>
                <Text size="xs" c="dimmed">tema {p.tema_predominante.replaceAll("_", " ")} · formato {p.formato_predominante.replaceAll("_", " ")}</Text>
              </Card>
            ))}
          </SimpleGrid>
        </div>
      )}
    </Stack>
  );
}
