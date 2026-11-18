import {
  ActionIcon, Alert, Box, Button, Group, Loader, Menu, Paper, Stack, Switch, Text, Textarea, Title, UnstyledButton,
} from "@mantine/core";
import { IconAlertTriangle, IconArrowUp, IconCheck, IconChevronDown, type Icon } from "@tabler/icons-react";
import type { ReactNode } from "react";

import { useComparacaoStone, useCronometro } from "../contexto";
import { FAIXAS, rotuloSegmento, ROTULO_MODO, tempoRelativo } from "../formato";
import type { Execucao } from "../tipos";
import { SeloConfianca } from "./Selos";

export function Tela({ children, largura = 1120 }: { children: ReactNode; largura?: number }) {
  return (
    <Box maw={largura} mx="auto" px={{ base: "md", sm: 40 }} pt={{ base: "lg", sm: 48 }} pb={80}>
      {children}
    </Box>
  );
}

export function TituloTela({ titulo, subtitulo, direita }: { titulo: ReactNode; subtitulo?: ReactNode; direita?: ReactNode }) {
  return (
    <Group justify="space-between" align="flex-end" mb={40} gap="md">
      <div style={{ minWidth: 0, flex: 1 }}>
        <Title order={1} fz={{ base: 24, sm: 28 }} fw={600} lh={1.25}>{titulo}</Title>
        {subtitulo && <Text c="dimmed" mt={6}>{subtitulo}</Text>}
      </div>
      {direita}
    </Group>
  );
}

// Título de seção: texto, sem caixa em volta (o espaço é que separa as seções).
export function Secao({ titulo, direita, children }: { titulo: ReactNode; direita?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <Group justify="space-between" mb="md" gap="sm">
        <Text fw={600} size="md">{titulo}</Text>
        {direita}
      </Group>
      {children}
    </section>
  );
}

// Tela inicial (Perguntar, Criar, Avaliar): título e compositor no meio da tela, como no ChatGPT. O que vem
// `abaixo` (sugestões) fica pendurado sob o compositor sem tirá-lo do centro.
export function Inicio({ titulo, children, abaixo }: { titulo: string; children: ReactNode; abaixo?: ReactNode }) {
  return (
    <Box className="inicio" px={{ base: "md", sm: 40 }}>
      <Box w="100%" maw={760} pos="relative">
        <Title order={1} ta="center" fz={{ base: 24, sm: 30 }} fw={500} lh={1.25} mb={{ base: 24, sm: 32 }}
          style={{ letterSpacing: "-0.01em" }}>
          {titulo}
        </Title>
        {children}
        {abaixo && <Box className="inicio-abaixo">{abaixo}</Box>}
      </Box>
    </Box>
  );
}

// Caixa de texto no estilo dos chats: campo sem borda, opções discretas embaixo e o botão de enviar.
export function Compositor({ valor, onChange, onEnviar, placeholder, opcoes, botao, pronto, ocupado, autoFocus, linhas = 2 }: {
  valor: string; onChange: (v: string) => void; onEnviar: () => void; placeholder: string; opcoes?: ReactNode;
  botao?: string; pronto: boolean; ocupado?: boolean; autoFocus?: boolean; linhas?: number;
}) {
  const enviar = () => pronto && !ocupado && onEnviar();
  return (
    <Paper radius={24} p="sm" pt={10} className="compositor">
      <Textarea
        variant="unstyled"
        autosize
        minRows={linhas}
        maxRows={10}
        autoFocus={autoFocus}
        placeholder={placeholder}
        value={valor}
        onChange={(e) => onChange(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            enviar();
          }
        }}
        styles={{ input: { fontSize: 15, lineHeight: 1.55, paddingInline: 8, border: 0, outline: "none", boxShadow: "none" } }}
      />
      <Group justify="space-between" gap="xs" mt={4} wrap="nowrap">
        <Group gap={2} wrap="wrap" style={{ flex: 1, minWidth: 0 }}>{opcoes}</Group>
        {botao ? (
          <Button radius="xl" size="sm" onClick={enviar} loading={ocupado} variant={pronto ? "filled" : "default"}
            style={{ flexShrink: 0 }}>
            {botao}
          </Button>
        ) : (
          <ActionIcon size={36} radius="xl" onClick={enviar} loading={ocupado} aria-label="Enviar"
            variant={pronto ? "filled" : "default"} style={{ flexShrink: 0 }}>
            <IconArrowUp size={18} />
          </ActionIcon>
        )}
      </Group>
    </Paper>
  );
}

interface Opcao { value: string; label: string; descricao?: string }

// Escolha discreta no compositor: um botão de texto que abre um menu (em vez de um select com caixa).
// Com `prefixo`, o botão diz de que é a escolha também depois de marcada ("Gancho: pergunta").
export function Escolha({ icone: Icone, opcoes, valor, onChange, vazio, prefixo, multiplo = false }: {
  icone?: Icon; opcoes: Opcao[]; valor: string | string[]; onChange: (v: string | string[]) => void; vazio?: string;
  prefixo?: string; multiplo?: boolean;
}) {
  const marcados = Array.isArray(valor) ? valor : [valor];
  const curto = (l: string) => l.split(" (")[0];
  const escolhidos = opcoes.filter((o) => o.value && marcados.includes(o.value)).map((o) => curto(o.label)).join(", ");
  const rotulo = escolhidos
    ? (prefixo ? `${prefixo}: ${escolhidos}` : escolhidos)
    : vazio ?? curto(opcoes.find((o) => o.value === "")?.label ?? "");

  function escolher(v: string) {
    if (!multiplo) return onChange(v);
    onChange(marcados.includes(v) ? marcados.filter((x) => x !== v) : [...marcados.filter(Boolean), v]);
  }

  return (
    <Menu position="bottom-start" closeOnItemClick={!multiplo} shadow="md" width={240}>
      <Menu.Target>
        <Button variant="subtle" color="gray" size="compact-sm" radius="xl" fw={500} px={10} maw="100%"
          styles={{ label: { overflow: "hidden", textOverflow: "ellipsis" } }}
          leftSection={Icone && <Icone size={15} stroke={1.7} />} rightSection={<IconChevronDown size={13} />}
          c="var(--mantine-color-dimmed)">
          {rotulo}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {opcoes.map((o) => (
          <Menu.Item key={o.value} onClick={() => escolher(o.value)}
            rightSection={marcados.includes(o.value) ? <IconCheck size={15} color="var(--verde-icone)" /> : null}>
            <Text size="sm">{o.label}</Text>
            {o.descricao && <Text size="xs" c="dimmed">{o.descricao}</Text>}
          </Menu.Item>
        ))}
        {multiplo && marcados.filter(Boolean).length > 0 && (
          <>
            <Menu.Divider />
            <Menu.Item onClick={() => onChange([])}><Text size="sm" c="dimmed">Limpar</Text></Menu.Item>
          </>
        )}
      </Menu.Dropdown>
    </Menu>
  );
}

// Sugestões sob o compositor: linhas com ícone e texto curto, sem borda (o clique usa o pedido completo).
export function Sugestoes<T>({ itens, rotulo, icone, onEscolher }: {
  itens: T[]; rotulo: (i: T) => string; icone: (i: T) => Icon; onEscolher: (i: T) => void;
}) {
  return (
    <Stack gap={2} mt="md" px={6}>
      {itens.map((i) => {
        const Icone = icone(i);
        return (
          <UnstyledButton key={rotulo(i)} className="sugestao" onClick={() => onEscolher(i)}>
            <Icone size={18} stroke={1.5} />
            {rotulo(i)}
          </UnstyledButton>
        );
      })}
    </Stack>
  );
}

// Linha de contexto de uma execução: modo, setor, tamanhos, quando e quanto tempo levou, e a confiança.
export function MetaExecucao({ e }: { e: Execucao }) {
  const faixas = (e.entrada.filters?.faixa ?? []).map((f) => FAIXAS.find((x) => x.value === f)?.label.split(" (")[0] ?? f);
  const partes = [
    ROTULO_MODO[e.entrada.mode], e.entrada.segment ? rotuloSegmento(e.entrada.segment) : null, ...faixas,
    `${tempoRelativo(e.quando)} · ${Math.round(e.duracao_s)} s`,
  ].filter(Boolean);
  return (
    <Text size="sm" c="dimmed">
      {partes.join(" · ")}
      {e.saida && <> · <SeloConfianca confianca={e.saida.confidence_flag} /></>}
    </Text>
  );
}

// O agente trabalhando: etapas e o tempo que já passou. A API não manda o progresso das consultas, então, sem
// `atual`, as etapas avançam pelo tempo médio de cada uma (`limites`, em segundos).
export function Trabalhando({ etapas, previsao, inicio, atual, limites = [] }: {
  etapas: string[]; previsao: string; inicio: number; atual?: number; limites?: number[];
}) {
  const s = useCronometro(inicio);
  atual ??= Math.min(limites.filter((l) => s >= l).length, etapas.length - 1);
  return (
    <Box>
      <Group justify="space-between" mb="lg">
        <Text fw={500}>{etapas[Math.min(atual, etapas.length - 1)]}…</Text>
        <Text size="sm" c="dimmed">{s} s de {previsao}</Text>
      </Group>
      <Stack gap={12} pl={4}>
        {etapas.map((nome, i) => (
          <Group key={nome} gap="sm">
            <Box w={18} style={{ display: "flex", justifyContent: "center" }}>
              {i < atual ? <IconCheck size={16} color="var(--verde-icone)" />
                : i === atual ? <Loader size={12} /> : <Box w={5} h={5} bg="var(--linha)" style={{ borderRadius: 3 }} />}
            </Box>
            <Text size="sm" c={i === atual ? undefined : "dimmed"}>{nome}</Text>
          </Group>
        ))}
      </Stack>
    </Box>
  );
}

export function Erro({ titulo = "Não foi possível responder", children }: { titulo?: string; children: ReactNode }) {
  return (
    <Alert color="red" variant="light" title={titulo} icon={<IconAlertTriangle size={18} />}>{children}</Alert>
  );
}

export function Avisos({ avisos }: { avisos: string[] }) {
  if (!avisos.length) return null;
  return (
    <Stack gap={6}>
      {avisos.map((w) => (
        <Group key={w} gap={8} wrap="nowrap" align="flex-start">
          <IconAlertTriangle size={16} color="var(--mantine-color-yellow-7)" style={{ flexShrink: 0, marginTop: 2 }} />
          <Text size="sm" c="dimmed">{w[0].toUpperCase() + w.slice(1)}.</Text>
        </Group>
      ))}
    </Stack>
  );
}

// Interruptor da comparação com a @impulsostone (vale para o app todo). `curto` para colunas estreitas.
export function ComparadorStone({ curto = false }: { curto?: boolean }) {
  const { ativo, setAtivo } = useComparacaoStone();
  return (
    <Switch size="xs" checked={ativo} onChange={(e) => setAtivo(e.currentTarget.checked)} color="orange"
      label={<Text size="xs" c="dimmed" span>{curto ? "Comparar com a Stone" : "Comparar com a @impulsostone"}</Text>} />
  );
}
