import { Alert, Anchor, Badge, Button, Card, Code, Collapse, CopyButton, Divider, Group, Image, Progress, Stack, Table, Text, Title, Tooltip } from "@mantine/core";
import { useEffect, useState } from "react";

import { useAbrirReel } from "../App";
import { api } from "../api";
import type { Criativo, ImagemGerada } from "../tipos";

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

// Selo da revisão de uma imagem gerada: nota do revisor e, se reprovada nas 3 tentativas, os problemas.
function SeloRevisao({ img }: { img?: ImagemGerada }) {
  const r = img?.revisao;
  if (!img) return null;
  if (!r) return <Text size="10px" c="dimmed" ta="center">sem revisão</Text>;
  const rotulo = `${r.aprovada ? "✓" : "⚠"} ${r.nota}/10`;
  const ajuda = r.aprovada
    ? `Aprovada pelo revisor${r.tentativas > 1 ? ` na ${r.tentativas}ª tentativa` : ""}`
    : `Melhor de ${r.tentativas} tentativas, ainda com problemas: ${r.problemas.join("; ")}`;
  return (
    <Tooltip label={ajuda} multiline w={260}>
      <Text size="10px" ta="center" c={r.aprovada ? "stone.8" : "orange.8"} fw={600}>{rotulo}</Text>
    </Tooltip>
  );
}

// Índice 0 = capa; 1..n = cenas. Os nomes batem com os arquivos da API (criativo1_capa, criativo1_cena2...).
const chave = (n: number, indice: number) => `criativo${n}_${indice === 0 ? "capa" : `cena${indice}`}`;

export default function CartaoCriativo({ c, n, runId }: { c: Criativo; n: number; runId: string }) {
  const abrirReel = useAbrirReel();
  const [verPrompt, setVerPrompt] = useState(false);
  const [imagens, setImagens] = useState<Record<string, ImagemGerada>>({});
  const [gerando, setGerando] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const total = c.roteiro.length + 1;
  const temPrompts = Boolean(c.prompt_capa && c.roteiro.every((s) => s.prompt_imagem));

  // Imagens já geradas antes (ao reabrir pelo histórico).
  useEffect(() => { api.imagens(runId).then(setImagens).catch(() => {}); }, [runId]);

  async function gerarImagens() {
    setErro(null);
    try {
      // Em ordem: cada cena usa a capa e a cena anterior como referência, então precisa delas prontas.
      for (let i = 0; i < total; i++) {
        setGerando(i);
        const r = await api.gerarImagem(runId, n, i);
        setImagens((atual) => ({ ...atual, [chave(n, i)]: { url: `${r.url}?v=${Date.now()}`, revisao: r.revisao } }));
      }
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setGerando(null);
    }
  }

  const url = (indice: number) => {
    const u = imagens[chave(n, indice)]?.url;
    return u ? `/api${u}` : undefined;
  };
  const geradas = Array.from({ length: total }, (_, i) => url(i)).filter(Boolean).length;

  return (
    <Card withBorder padding="lg">
      <Group justify="space-between" align="flex-start" mb="xs" wrap="nowrap">
        <div>
          <Text size="xs" c="dimmed">Criativo {n}</Text>
          <Title order={4}>{c.titulo}</Title>
          <Group gap={6} mt={4}>
            <Badge variant="light" color="gray">{c.formato}</Badge>
            <Badge variant="light" color="gray">{c.duracao_alvo}</Badge>
          </Group>
        </div>
        <Group gap="sm" align="flex-start" wrap="nowrap">
          {url(0) && (
            <Stack gap={2}>
              <Anchor href={url(0)} target="_blank">
                <Image src={url(0)} w={72} h={128} radius="sm" alt={`Capa do criativo ${n}`} />
              </Anchor>
              <SeloRevisao img={imagens[chave(n, 0)]} />
            </Stack>
          )}
          <Copiar valor={emTexto(c)} rotulo="Copiar criativo" />
        </Group>
      </Group>

      <Card bg="stone.0" padding="sm" mb="sm">
        <Text size="xs" c="stone.9" fw={600}>Gancho (0–3 s)</Text>
        <Text fw={600}>{c.gancho}</Text>
      </Card>

      <Text size="sm" fw={600} mb={4}>Roteiro</Text>
      <Table verticalSpacing={6} withRowBorders>
        <Table.Tbody>
          {c.roteiro.map((cena, i) => (
            <Table.Tr key={cena.tempo + cena.descricao}>
              <Table.Td w={80} style={{ verticalAlign: "top" }}><Text size="xs" c="dimmed">{cena.tempo}</Text></Table.Td>
              <Table.Td>
                <Text size="sm">{cena.descricao}</Text>
                {cena.texto_na_tela && <Text size="xs" c="dimmed">Na tela: “{cena.texto_na_tela}”</Text>}
              </Table.Td>
              {geradas > 0 && (
                <Table.Td w={64} style={{ verticalAlign: "top" }}>
                  {url(i + 1) && (
                    <Stack gap={2}>
                      <Anchor href={url(i + 1)} target="_blank">
                        <Image src={url(i + 1)} w={54} h={96} radius="sm" alt={`Cena ${cena.tempo}`} />
                      </Anchor>
                      <SeloRevisao img={imagens[chave(n, i + 1)]} />
                    </Stack>
                  )}
                </Table.Td>
              )}
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

      {temPrompts && (
        <Card withBorder mt="md" padding="sm" bg="gray.0">
          <Text size="sm" fw={600}>Imagens do criativo</Text>
          {c.personagem && <Text size="xs" c="dimmed">Personagem: {c.personagem}</Text>}
          <Group mt="xs" gap="xs">
            {c.prompt_copiar && <Copiar valor={c.prompt_copiar} rotulo="Copiar prompt (todas as imagens)" />}
            {c.prompt_copiar && (
              <Button size="compact-xs" variant="subtle" color="gray" onClick={() => setVerPrompt((v) => !v)}>
                {verPrompt ? "Esconder prompt" : "Ver prompt"}
              </Button>
            )}
            <Button size="compact-xs" onClick={gerarImagens} loading={gerando !== null}>
              {geradas === total ? "Gerar de novo" : `Gerar ${total} imagens`}
            </Button>
          </Group>
          <Text size="xs" c="dimmed" mt={4}>
            Copiar: cole no Gemini ou no ChatGPT. Gerar: capa e cenas em 9:16 pelo Cloudflare; cada cena usa o rosto da capa
            como base, para manter a mesma pessoa; um revisor confere cada imagem e, se reprovar, gera de novo (até 3 vezes).
          </Text>
          <Collapse expanded={verPrompt}>
            <Code block mt="xs" style={{ whiteSpace: "pre-wrap" }}>{c.prompt_copiar}</Code>
          </Collapse>
          {gerando !== null && (
            <Stack gap={4} mt="xs">
              <Text size="xs">Gerando e revisando {gerando === 0 ? "a capa" : `a cena ${gerando} de ${total - 1}`}…</Text>
              <Progress value={(gerando / total) * 100} size="sm" />
            </Stack>
          )}
          {erro && <Alert color="red" mt="xs" p="xs"><Text size="sm">{erro}</Text></Alert>}
          {geradas > 0 && gerando === null && (
            <Group gap={6} mt="xs">
              {Array.from({ length: total }, (_, i) => url(i) && (
                <Anchor key={i} href={url(i)} download={`${chave(n, i)}.jpg`} size="xs">
                  {i === 0 ? "baixar capa" : `cena ${i}`}
                </Anchor>
              ))}
            </Group>
          )}
        </Card>
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
