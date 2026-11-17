import {
  ActionIcon, AppShell, Burger, Group, Loader, ScrollArea, Stack, Text, Tooltip, UnstyledButton,
  useComputedColorScheme, useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure, useLocalStorage, useMediaQuery } from "@mantine/hooks";
import {
  IconChartDots3, IconClipboardCheck, IconLayoutSidebarLeftCollapse, IconLayoutSidebarLeftExpand, IconMessageCircleSearch,
  IconMoon, IconSparkles, IconSun, type Icon,
} from "@tabler/icons-react";
import { useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router";

import { useRecentes, useTarefas, type TelaExecucao } from "../contexto";
import { rotaDoModo } from "../formato";
import type { ExecucaoResumo } from "../tipos";

const TELAS: { rota: string; rotulo: string; icone: Icon; tela?: TelaExecucao }[] = [
  { rota: "/perguntar", rotulo: "Perguntar", icone: IconMessageCircleSearch, tela: "perguntar" },
  { rota: "/criar", rotulo: "Criar", icone: IconSparkles, tela: "criar" },
  { rota: "/avaliar", rotulo: "Avaliar", icone: IconClipboardCheck, tela: "avaliar" },
  { rota: "/panorama", rotulo: "Panorama", icone: IconChartDots3 },
];

// Logo da Stone (wordmark de stone.com.br). Com a barra recolhida, fica só o símbolo (o "o" do wordmark), que vira o
// botão de expandir quando o mouse passa por cima, como no ChatGPT.
function Logo({ altura = 22 }: { altura?: number }) {
  return (
    <Link to="/perguntar" aria-label="Stone, início" style={{ display: "flex" }}>
      <img src="/stone-logo.svg" alt="Stone" style={{ height: altura, width: "auto" }} />
    </Link>
  );
}

function LogoRecolhido({ expandir }: { expandir: () => void }) {
  return (
    <Tooltip label="Expandir barra" position="right">
      <UnstyledButton className="logo-recolhido" onClick={expandir} aria-label="Expandir barra">
        <img className="logo-simbolo" src="/stone-simbolo.svg" alt="Stone" />
        <IconLayoutSidebarLeftExpand className="logo-expandir" size={20} stroke={1.6} />
      </UnstyledButton>
    </Tooltip>
  );
}

// Recentes agrupados por dia, como no ChatGPT; só o título, sem ícone. Execuções com erro não aparecem.
function agrupar(lista: ExecucaoResumo[]) {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const dia = 24 * 3600 * 1000;
  const grupos: [string, ExecucaoResumo[]][] = [["Hoje", []], ["Ontem", []], ["Últimos 7 dias", []], ["Antes", []]];
  for (const e of lista) {
    const t = new Date(e.quando).getTime();
    const i = t >= hoje.getTime() ? 0 : t >= hoje.getTime() - dia ? 1 : t >= hoje.getTime() - 7 * dia ? 2 : 3;
    grupos[i][1].push(e);
  }
  return grupos.filter(([, itens]) => itens.length);
}

function Recentes() {
  const { recentes } = useRecentes();
  const tarefas = useTarefas();
  const { pathname } = useLocation();
  const rodando = (Object.entries(tarefas) as [TelaExecucao, NonNullable<(typeof tarefas)[TelaExecucao]>][])
    .filter(([, t]) => t.rodando);
  const validos = (recentes ?? []).filter((e) => !e.erro).slice(0, 30);

  return (
    <Stack gap="lg">
      {rodando.length > 0 && (
        <div>
          <Text size="xs" c="dimmed" px={10} mb={4}>Em andamento</Text>
          {rodando.map(([tela, t]) => (
            <Link key={tela} to={`/${tela}`} className="nav nav-recente" title={t.titulo}>
              <Loader size={12} style={{ flexShrink: 0 }} />
              <span>{t.titulo}</span>
            </Link>
          ))}
        </div>
      )}
      {recentes && !validos.length && !rodando.length && <Text size="sm" c="dimmed" px={10}>As execuções aparecem aqui.</Text>}
      {agrupar(validos).map(([nome, itens]) => (
        <div key={nome}>
          <Text size="xs" c="dimmed" px={10} mb={4}>{nome}</Text>
          {itens.map((e) => {
            const rota = `${rotaDoModo(e.mode)}/${e.run_id}`;
            return (
              <Link key={e.run_id} to={rota} className="nav nav-recente" data-ativo={pathname === rota || undefined} title={e.query}>
                <span>{e.query}</span>
              </Link>
            );
          })}
        </div>
      ))}
    </Stack>
  );
}

function TrocarTema() {
  const { setColorScheme } = useMantineColorScheme();
  const atual = useComputedColorScheme("light");
  return (
    <Tooltip label={atual === "light" ? "Tema escuro" : "Tema claro"}>
      <ActionIcon variant="subtle" color="gray" onClick={() => setColorScheme(atual === "light" ? "dark" : "light")}
        aria-label="Trocar tema">
        {atual === "light" ? <IconMoon size={16} /> : <IconSun size={16} />}
      </ActionIcon>
    </Tooltip>
  );
}

export default function Layout() {
  const [aberta, { toggle, close }] = useDisclosure();
  const [recolhida, setRecolhida] = useLocalStorage({ key: "barra-recolhida", defaultValue: false });
  const celular = useMediaQuery("(max-width: 48em)");
  const recolher = recolhida && !celular;
  const tarefas = useTarefas();
  const { pathname } = useLocation();
  useEffect(close, [pathname, close]);

  return (
    <AppShell
      header={{ height: { base: 52, sm: 0 } }}
      navbar={{ width: recolher ? 64 : 248, breakpoint: "sm", collapsed: { mobile: !aberta } }}
      styles={{
        main: { background: "var(--fundo)" },
        navbar: { background: "var(--lateral)", borderColor: "var(--linha)" },
        header: { background: "var(--lateral)", borderColor: "var(--linha)" },
      }}
      layout="alt"
    >
      <AppShell.Header hiddenFrom="sm" px="md">
        <Group h="100%" justify="space-between" wrap="nowrap">
          <Group gap="md" wrap="nowrap">
            <Burger opened={aberta} onClick={toggle} size="sm" aria-label="Menu" />
            <Logo altura={18} />
          </Group>
          <TrocarTema />
        </Group>
      </AppShell.Header>

      <AppShell.Navbar>
        <AppShell.Section px={recolher ? 0 : 18} pt={16} pb={20} visibleFrom="sm">
          {recolher ? (
            <Group justify="center"><LogoRecolhido expandir={() => setRecolhida(false)} /></Group>
          ) : (
            <Group justify="space-between" wrap="nowrap" h={34}>
              <Logo />
              <Tooltip label="Recolher barra">
                <ActionIcon variant="subtle" color="gray" onClick={() => setRecolhida(true)} aria-label="Recolher barra">
                  <IconLayoutSidebarLeftCollapse size={18} stroke={1.6} />
                </ActionIcon>
              </Tooltip>
            </Group>
          )}
        </AppShell.Section>
        <AppShell.Section px={8} pt={{ base: 12, sm: 0 }}>
          <Stack gap={2}>
            {TELAS.map((t) => {
              const rodando = t.tela && tarefas[t.tela]?.rodando;
              return (
                <Tooltip key={t.rota} label={rodando ? `${t.rotulo} · em andamento` : t.rotulo} position="right" disabled={!recolher}>
                  <Link to={t.rota} className="nav" data-ativo={pathname.startsWith(t.rota) || undefined}
                    data-recolhido={recolher || undefined} aria-label={t.rotulo}>
                    {rodando && recolher ? <Loader size={16} /> : <t.icone size={18} stroke={1.6} />}
                    {!recolher && <span style={{ flex: 1 }}>{t.rotulo}</span>}
                    {rodando && !recolher && <Loader size={12} />}
                  </Link>
                </Tooltip>
              );
            })}
          </Stack>
        </AppShell.Section>
        {recolher ? <AppShell.Section grow /> : (
          <AppShell.Section grow component={ScrollArea} px={8} pt={32} pb="md" scrollbarSize={6}>
            <Text size="xs" fw={600} c="dimmed" px={10} mb="sm">Recentes</Text>
            <Recentes />
          </AppShell.Section>
        )}
        <AppShell.Section px={recolher ? 0 : 18} py="md">
          {recolher ? <Group justify="center"><TrocarTema /></Group> : (
            <Group justify="space-between" wrap="nowrap">
              <Text size="xs" c="dimmed">944 Reels de MPEs · top 10% × controle</Text>
              <TrocarTema />
            </Group>
          )}
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
