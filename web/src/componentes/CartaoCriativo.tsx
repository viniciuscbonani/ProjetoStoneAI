import { ActionIcon, Badge, Button, Card, CopyButton, Divider, Group, Stack, Table, Text, Title, Tooltip } from "@mantine/core";

import { useAbrirReel } from "../App";
import type { Criativo } from "../tipos";

function Copiar({ valor, rotulo = "Copiar" }: { valor: string; rotulo?: string }) {
  return (
    <CopyButton value={valor} timeout={1500}>
      {({ copied, copy }) => (
        <Button size="compact-xs" variant={copied ? "filled" : "light"} color={copied ? "stone" : "gray"} onClick={copy}>
          {copied ? "Copiado" : rotulo}
        </Button>
      )}
    </CopyButton>
  );
}

// O criativo inteiro em texto, para colar num documento ou mandar para a equipe.
function emTexto(c: Criativo) {
  return [
    c.titulo, `${c.formato} · ${c.duracao_alvo}`, "", `GANCHO: ${c.gancho}`, "", "ROTEIRO:",
    ...c.roteiro.map((s) => `${s.tempo}: ${s.descricao}${s.texto_na_tela ? ` [na tela: ${s.texto_na_tela}]` : ""}`),
    "", `LEGENDA: ${c.legenda}`, "", `CTA: ${c.cta}`, "",
    `Inspirado em: ${c.inspirado_em.map((s) => `https://www.instagram.com/reel/${s}/`).join(" ")}`,
    `Achados usados: ${c.achados_usados.join("; ")}`,
  ].join("\n");
}

export default function CartaoCriativo({ c, n }: { c: Criativo; n: number }) {
  const abrirReel = useAbrirReel();
  return (
    <Card withBorder padding="lg">
      <Group justify="space-between" align="flex-start" mb="xs">
        <div>
          <Text size="xs" c="dimmed">Criativo {n}</Text>
          <Title order={4}>{c.titulo}</Title>
          <Group gap={6} mt={4}>
            <Badge variant="light" color="gray">{c.formato}</Badge>
            <Badge variant="light" color="gray">{c.duracao_alvo}</Badge>
          </Group>
        </div>
        <Copiar valor={emTexto(c)} rotulo="Copiar criativo" />
      </Group>

      <Card bg="stone.0" padding="sm" mb="sm">
        <Text size="xs" c="stone.9" fw={600}>Gancho (0–3 s)</Text>
        <Text fw={600}>{c.gancho}</Text>
      </Card>

      <Text size="sm" fw={600} mb={4}>Roteiro</Text>
      <Table verticalSpacing={6} withRowBorders>
        <Table.Tbody>
          {c.roteiro.map((cena) => (
            <Table.Tr key={cena.tempo + cena.descricao}>
              <Table.Td w={80} style={{ verticalAlign: "top" }}><Text size="xs" c="dimmed">{cena.tempo}</Text></Table.Td>
              <Table.Td>
                <Text size="sm">{cena.descricao}</Text>
                {cena.texto_na_tela && <Text size="xs" c="dimmed">Na tela: “{cena.texto_na_tela}”</Text>}
              </Table.Td>
              <Table.Td w={40} style={{ verticalAlign: "top" }}>
                {cena.prompt_imagem && (
                  <CopyButton value={cena.prompt_imagem} timeout={1500}>
                    {({ copied, copy }) => (
                      <Tooltip label={copied ? "Prompt copiado" : "Copiar prompt de imagem da cena"}>
                        <ActionIcon variant="subtle" color={copied ? "stone" : "gray"} onClick={copy} aria-label="Copiar prompt de imagem da cena">
                          {copied ? "✓" : "🖼"}
                        </ActionIcon>
                      </Tooltip>
                    )}
                  </CopyButton>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Group justify="space-between" mt="sm" mb={4}>
        <Text size="sm" fw={600}>Legenda</Text>
        <Copiar valor={c.legenda} />
      </Group>
      <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{c.legenda}</Text>

      <Text size="sm" fw={600} mt="sm">Chamada para ação</Text>
      <Text size="sm">{c.cta}</Text>

      {c.prompt_capa && (
        <>
          <Group justify="space-between" mt="sm" mb={4}>
            <Text size="sm" fw={600}>Prompt da capa (9:16)</Text>
            <Copiar valor={c.prompt_capa} rotulo="Copiar prompt" />
          </Group>
          <Text size="xs" c="dimmed" ff="monospace">{c.prompt_capa}</Text>
          <Text size="xs" c="dimmed" mt={2}>Em inglês, para colar num gerador de imagem. Os prompts de cada cena estão no ícone 🖼 do roteiro.</Text>
        </>
      )}

      <Divider my="sm" />
      <Stack gap={6}>
        <Group gap={6}>
          <Text size="xs" c="dimmed">Inspirado em:</Text>
          {c.inspirado_em.map((s) => (
            <Button key={s} size="compact-xs" variant="outline" color="stone" onClick={() => abrirReel(s)}>{s}</Button>
          ))}
        </Group>
        <Group gap={6}>
          <Text size="xs" c="dimmed">Apoiado em:</Text>
          {c.achados_usados.map((a) => <Badge key={a} size="sm" variant="light" color="stone">{a}</Badge>)}
        </Group>
      </Stack>
    </Card>
  );
}
