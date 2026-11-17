import {
  ActionIcon, Alert, Badge, Box, Button, Code, Collapse, CopyButton, Group, Loader, Paper, ScrollArea, SimpleGrid,
  Stack, Text, Title, Tooltip,
} from "@mantine/core";
import { IconCheck, IconCopy, IconDownload, IconPhoto, IconPhotoAi } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { api, urlZipCriativo } from "../api";
import type { Criativo as TCriativo, ImagemGerada, ReferencePost } from "../tipos";
import { MiniReel } from "./CartaoReel";

export function Copiar({ valor, rotulo = "Copiar", variante = "default" }: { valor: string; rotulo?: string; variante?: string }) {
  return (
    <CopyButton value={valor} timeout={1500}>
      {({ copied, copy }) => (
        <Button size="xs" variant={copied ? "light" : variante} color={copied ? "stone" : undefined} onClick={copy}
          leftSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />}>
          {copied ? "Copiado" : rotulo}
        </Button>
      )}
    </CopyButton>
  );
}

// O criativo inteiro em texto, para colar num documento ou mandar para a equipe.
function emTexto(c: TCriativo) {
  return [
    c.titulo, `${c.formato} · ${c.duracao_alvo}`, "", `GANCHO: ${c.gancho}`, "", "ROTEIRO:",
    ...c.roteiro.map((s) => `${s.tempo}: ${s.descricao}${s.texto_na_tela ? ` [na tela: ${s.texto_na_tela}]` : ""}`),
    "", `LEGENDA: ${c.legenda}`, "", `CTA: ${c.cta}`, "",
    `Inspirado em: ${c.inspirado_em.map((s) => `https://www.instagram.com/reel/${s}/`).join(" ")}`,
    `Achados usados: ${c.achados_usados.join("; ")}`,
  ].join("\n");
}

// Selo da revisão de uma imagem gerada: nota do revisor e, se reprovada nas duas versões, os problemas.
function SeloRevisao({ img }: { img?: ImagemGerada }) {
  const r = img?.revisao;
  if (!r) return null;
  const ajuda = r.aprovada
    ? `Aprovada pelo revisor${r.tentativas > 1 ? ` na ${r.tentativas}ª tentativa` : ""}`
    : `Melhor de ${r.tentativas} tentativas, ainda com problemas: ${r.problemas.join("; ")}`;
  return (
    <Tooltip label={ajuda}>
      <Badge size="sm" variant="filled" color={r.aprovada ? "dark" : "orange"} tt="none"
        style={{ position: "absolute", top: 6, right: 6, cursor: "help" }}>
        {r.aprovada ? `nota ${r.nota}` : `revisar · ${r.nota}`}
      </Badge>
    </Tooltip>
  );
}

// Uma cena do storyboard: quadro 9:16 (imagem gerada ou espaço reservado) com o texto na tela por cima.
function Cena({ rotulo, tempo, descricao, texto, img, url, gerando, nomeArquivo }: {
  rotulo: string; tempo?: string; descricao: string; texto?: string; img?: ImagemGerada; url?: string;
  gerando: boolean; nomeArquivo: string;
}) {
  return (
    <Box w={176} style={{ flexShrink: 0 }}>
      <div className="quadro">
        {url ? <img src={url} alt={rotulo} /> : (
          <Stack h="100%" align="center" justify="center" gap={4} c="dimmed">
            {gerando ? <Loader size="sm" /> : <IconPhoto size={28} stroke={1.3} />}
            <Text size="xs">{gerando ? "gerando…" : rotulo}</Text>
          </Stack>
        )}
        {texto && <div className="quadro-texto">{texto}</div>}
        <Badge className="quadro-canto" size="sm" color="dark" variant="filled" tt="none">{rotulo}</Badge>
        <SeloRevisao img={img} />
        {url && (
          <ActionIcon component="a" href={url} download={nomeArquivo} size="sm" variant="white" color="dark"
            style={{ position: "absolute", bottom: 6, right: 6 }} aria-label={`Baixar ${rotulo}`}>
            <IconDownload size={14} />
          </ActionIcon>
        )}
      </div>
      {tempo && <Text size="xs" fw={600} c="dimmed" mt={8}>{tempo}</Text>}
      <Text size="sm" mt={tempo ? 2 : 8}>{descricao}</Text>
    </Box>
  );
}

// Índice 0 = capa; 1..n = cenas. Os nomes batem com os arquivos da API (criativo1_capa, criativo1_cena2...).
const chave = (n: number, indice: number) => `criativo${n}_${indice === 0 ? "capa" : `cena${indice}`}`;

export default function Criativo({ c, n, runId, refs }: { c: TCriativo; n: number; runId: string; refs: ReferencePost[] }) {
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
      // Em ordem: cada cena usa um recorte do rosto da capa como referência, então a capa vem primeiro.
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
    <Stack gap={40}>
      <Group justify="space-between" align="flex-start" gap="md">
        <div style={{ flex: 1, minWidth: 240 }}>
          <Title order={2} fz={22} fw={600} lh={1.3}>{c.titulo}</Title>
          <Text size="sm" c="dimmed" mt={6}>
            {c.formato.replaceAll("_", " ")} · {c.duracao_alvo} · {c.roteiro.length} cenas
          </Text>
        </div>
        <Group gap="xs">
          <Copiar valor={emTexto(c)} rotulo="Copiar criativo" />
          <Tooltip label={geradas
            ? `Texto do criativo, prompt das imagens e as ${geradas} imagens geradas`
            : "Texto do criativo e prompt das imagens (gere as imagens para incluí-las)"}>
            <Button size="xs" variant="default" component="a" href={urlZipCriativo(runId, n)} download
              leftSection={<IconDownload size={14} />}>
              Baixar .zip
            </Button>
          </Tooltip>
          {temPrompts && (
            <Button size="xs" leftSection={<IconPhotoAi size={15} />} onClick={gerarImagens} loading={gerando !== null}>
              {geradas === total ? "Gerar imagens de novo" : `Gerar ${total} imagens`}
            </Button>
          )}
        </Group>
      </Group>

      <div>
        <Text size="sm" c="dimmed" mb={6}>Gancho, nos primeiros 3 segundos</Text>
        <Text fz={{ base: 20, sm: 24 }} fw={500} lh={1.35} maw={820} style={{ letterSpacing: "-0.01em" }}>“{c.gancho}”</Text>
      </div>

      <div>
        <Group justify="space-between" mb="md">
          <Text fw={600}>Roteiro em cenas</Text>
          {gerando !== null && (
            <Text size="xs" c="dimmed">Gerando e revisando {gerando === 0 ? "a capa" : `a cena ${gerando} de ${total - 1}`}…</Text>
          )}
        </Group>
        <ScrollArea type="auto" offsetScrollbars scrollbarSize={8}>
          <Group gap="lg" wrap="nowrap" align="flex-start" pb="xs">
            <Cena rotulo="Capa" descricao="Capa do Reel no feed (9:16)." img={imagens[chave(n, 0)]} url={url(0)}
              gerando={gerando === 0} nomeArquivo={`${chave(n, 0)}.jpg`} />
            {c.roteiro.map((cena, i) => (
              <Cena key={cena.tempo + i} rotulo={`Cena ${i + 1}`} tempo={cena.tempo} descricao={cena.descricao}
                texto={cena.texto_na_tela} img={imagens[chave(n, i + 1)]} url={url(i + 1)} gerando={gerando === i + 1}
                nomeArquivo={`${chave(n, i + 1)}.jpg`} />
            ))}
          </Group>
        </ScrollArea>
        {erro && <Alert color="red" variant="light" mt="xs" p="xs"><Text size="sm">{erro}</Text></Alert>}
      </div>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing={48} verticalSpacing={32}>
        <div>
          <Group justify="space-between" mb="sm">
            <Text fw={600}>Legenda</Text>
            <Copiar valor={c.legenda} rotulo="Copiar" variante="subtle" />
          </Group>
          <Text size="sm" lh={1.65} style={{ whiteSpace: "pre-wrap" }}>{c.legenda}</Text>
        </div>
        <Stack gap={32}>
          <div>
            <Text fw={600} mb="sm">Chamada para ação</Text>
            <Text size="sm" lh={1.65}>{c.cta}</Text>
          </div>
          <div>
            <Text fw={600} mb="sm">Inspirado em</Text>
            <Group gap="sm">
              {c.inspirado_em.map((s) => <MiniReel key={s} codigo={s} refs={refs} largura={56} />)}
            </Group>
          </div>
          <div>
            <Text fw={600} mb="sm">Apoiado nos achados</Text>
            <Stack gap={6}>
              {c.achados_usados.map((a) => (
                <Text key={a} size="sm">{a}</Text>
              ))}
            </Stack>
          </div>
        </Stack>
      </SimpleGrid>

      {temPrompts && c.prompt_copiar && (
        <Paper p="lg" bg="var(--suave)" radius="md">
          <Group justify="space-between" gap="xs">
            <div style={{ flex: 1, minWidth: 220 }}>
              <Text fw={600} size="sm">Prefere gerar as imagens no Gemini ou no ChatGPT?</Text>
              <Text size="xs" c="dimmed">
                Copie um prompt único com a capa e as {c.roteiro.length} cenas. Aqui, as imagens saem do Cloudflare e um
                revisor confere cada uma (a mesma pessoa da capa, sem texto inventado).
              </Text>
            </div>
            <Group gap="xs">
              <Button size="xs" variant="subtle" color="gray" onClick={() => setVerPrompt((v) => !v)}>
                {verPrompt ? "Esconder" : "Ver prompt"}
              </Button>
              <Copiar valor={c.prompt_copiar} rotulo="Copiar prompt" />
            </Group>
          </Group>
          <Collapse expanded={verPrompt}>
            <Code block mt="sm" style={{ whiteSpace: "pre-wrap" }}>{c.prompt_copiar}</Code>
          </Collapse>
        </Paper>
      )}
    </Stack>
  );
}
