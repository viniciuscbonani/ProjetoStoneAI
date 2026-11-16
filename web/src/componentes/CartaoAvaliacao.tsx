import { Anchor, Badge, Card, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import Markdown from "react-markdown";

import { useAbrirReel } from "../App";
import { rotuloValor } from "../formato";
import type { Avaliacao, Ponto } from "../tipos";
import { SeloRobustez } from "./Resultado";

// O que o agente leu do vídeo (ou do roteiro), na ordem em que importa para a avaliação.
const LEITURA: [string, string][] = [
  ["duracao_s", "Duração"], ["formato_video", "Formato"], ["tipo_hook", "Tipo de gancho"], ["hook_texto", "Gancho"],
  ["tema_principal", "Tema"], ["pilar_impulso", "Pilar"], ["tem_rosto", "Rosto em cena"], ["texto_na_tela", "Texto na tela"],
  ["tipo_cta", "CTA"], ["abordagem", "Abordagem"], ["ritmo_cortes", "Ritmo de cortes"],
];

const comLinks = (texto: string) => texto.replace(/\[([A-Za-z0-9_-]{9,})\]/g, "[$1](#reel-$1)");

function TextoComLinks({ texto }: { texto: string }) {
  const abrirReel = useAbrirReel();
  return (
    <Markdown components={{
      p: ({ children }) => <Text size="sm">{children}</Text>,
      a: ({ href, children }) => href?.startsWith("#reel-")
        ? <Anchor component="button" size="sm" fw={600} onClick={() => abrirReel(href.slice(6))}>{children}</Anchor>
        : <Anchor href={href} target="_blank">{children}</Anchor>,
    }}>{comLinks(texto)}</Markdown>
  );
}

function Pontos({ titulo, cor, pontos, vazio }: { titulo: string; cor: string; pontos: Ponto[]; vazio: string }) {
  return (
    <Card withBorder padding="md" style={{ borderTop: `3px solid var(--mantine-color-${cor}-6)` }}>
      <Title order={5} mb="xs">{titulo}</Title>
      {pontos.length === 0 && <Text size="sm" c="dimmed">{vazio}</Text>}
      <Stack gap="sm">
        {pontos.map((p) => (
          <div key={p.achado}>
            <TextoComLinks texto={p.texto} />
            <Group gap={6} mt={4}>
              <SeloRobustez robustez={p.robustez} />
            </Group>
          </div>
        ))}
      </Stack>
    </Card>
  );
}

export default function CartaoAvaliacao({ a }: { a: Avaliacao }) {
  const l = a.leitura;
  return (
    <Stack gap="md">
      <Card withBorder padding="md">
        <Group justify="space-between" mb="xs">
          <Title order={5}>Como o agente leu {a.fonte === "video" ? "o vídeo" : "o roteiro"}</Title>
          <Badge variant="light" color="gray">{a.fonte === "video" ? "vídeo" : "roteiro"}</Badge>
        </Group>
        <Group gap={6}>
          {LEITURA.filter(([k]) => l[k] !== undefined && l[k] !== "").map(([k, nome]) => (
            <Badge key={k} variant="outline" color="gray" tt="none" size="lg" fw={500}>
              {nome}: {k === "duracao_s" ? `${Math.round(Number(l[k]))} s${l.duracao_estimada ? " (estimada)" : ""}`
                : k === "hook_texto" ? `“${l[k]}”` : rotuloValor(l[k])}
            </Badge>
          ))}
        </Group>
      </Card>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Pontos titulo="Pontos fortes" cor="stone" pontos={a.pontos_fortes} vazio="Nenhuma característica que aparece mais no top." />
        <Pontos titulo="Pontos a melhorar" cor="orange" pontos={a.pontos_a_melhorar} vazio="Nada a mudar segundo os achados da base." />
      </SimpleGrid>
      {a.sem_efeito.length > 0 && (
        <Pontos titulo="Não precisa se preocupar" cor="gray" pontos={a.sem_efeito} vazio="" />
      )}
      <Text size="xs" c="dimmed">
        Comparação com os padrões dos Reels de alto engajamento da base, não previsão de resultado.
      </Text>
    </Stack>
  );
}
