import { Anchor, Box, Group, HoverCard, Stack, Text, Typography } from "@mantine/core";
import Markdown from "react-markdown";

import { useAbrirReel } from "../contexto";
import { pct } from "../formato";
import type { ReferencePost } from "../tipos";
import { Capa } from "./CartaoReel";

const CODIGO = /\[([A-Za-z0-9_-]{9,})\]/g;

// Número de cada Reel citado: primeiro os de referência (na ordem dos cartões), depois os que só aparecem no texto.
export function numerarCitacoes(refs: ReferencePost[], ...textos: string[]) {
  const ordem = refs.map((r) => r.shortCode);
  for (const t of textos) for (const [, c] of t.matchAll(CODIGO)) if (!ordem.includes(c)) ordem.push(c);
  return new Map(ordem.map((c, i) => [c, i + 1]));
}

export function Citacao({ codigo, numero, refs }: { codigo: string; numero?: number; refs: ReferencePost[] }) {
  const abrirReel = useAbrirReel();
  const r = refs.find((x) => x.shortCode === codigo);
  return (
    <HoverCard width={280} shadow="md" openDelay={150} position="top">
      <HoverCard.Target>
        <button type="button" className="citacao" onClick={() => abrirReel(codigo)} aria-label={`Reel ${codigo}`}>
          {numero ?? "↗"}
        </button>
      </HoverCard.Target>
      <HoverCard.Dropdown p="xs">
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <Box w={64} className="quadro" style={{ borderRadius: "var(--mantine-radius-sm)" }}><Capa codigo={codigo} /></Box>
          <Stack gap={2}>
            <Text size="sm" fw={600}>{r ? `@${r.perfil}` : codigo}</Text>
            {r && <Text size="xs" c="dimmed">{pct(r.taxa_engajamento, 1)} de engajamento · {Math.round(r.duracao_s)} s</Text>}
            {r?.hook_texto && <Text size="xs" lineClamp={3}>“{r.hook_texto}”</Text>}
            <Text size="xs" c="stone.7" mt={2}>Clique para ver os quadros</Text>
          </Stack>
        </Group>
      </HoverCard.Dropdown>
    </HoverCard>
  );
}

// Texto do agente em markdown, com cada [shortCode] virando uma citação numerada.
export function TextoComCitacoes({ texto, refs, numeros, size = "sm" }: {
  texto: string; refs: ReferencePost[]; numeros?: Map<string, number>; size?: string;
}) {
  const nums = numeros ?? numerarCitacoes(refs, texto);
  return (
    <Typography fz={size} style={{ lineHeight: 1.65 }}>
      <Markdown
        components={{
          a: ({ href, children }) =>
            href?.startsWith("#reel-") ? (
              <Citacao codigo={href.slice(6)} numero={nums.get(href.slice(6))} refs={refs} />
            ) : (
              <Anchor href={href} target="_blank">{children}</Anchor>
            ),
        }}
      >
        {texto.replace(CODIGO, "[$1](#reel-$1)")}
      </Markdown>
    </Typography>
  );
}
