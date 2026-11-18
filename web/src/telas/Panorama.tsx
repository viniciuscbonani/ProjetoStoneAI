import { Anchor, Box, Button, Group, Loader, Paper, SegmentedControl, SimpleGrid, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconBuildingStore, IconQuote, IconUsers } from "@tabler/icons-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { api } from "../api";
import { corTop, Grupo, Legenda, LegendaBarras, ListaValores } from "../componentes/Achados";
import CartaoReel, { MiniReel } from "../componentes/CartaoReel";
import { Erro, Escolha, Secao, Tela, TituloTela } from "../componentes/Comum";
import Glance from "../componentes/Glance";
import { SeloRobustez } from "../componentes/Selos";
import { useAbrirGanchos, useTitulo } from "../contexto";
import { compacto, FAIXAS, inteiro, nomeAchado, num, pct, SEGMENTOS, vezes } from "../formato";
import type { Achado, Panorama as TPanorama, ReferencePost } from "../tipos";
import { TODOS } from "./Ganchos";

const ORDEM = { robusto: 0, fragil: 1, sem_diferenca: 2, insuficiente: 3 };
// Em campos sim/não, o "não" é o espelho do "sim" (data comemorativa: não 96% × 91% repete o "sim" 4% × 10%):
// destaques e cartões mostram só o "sim"; o "não" fica no detalhe e na lista.
const relevante = (a: Achado) => (a.robustez === "robusto" || a.robustez === "fragil") && a.valor !== "False";
const porForca = (a: Achado, b: Achado) => ORDEM[a.robustez] - ORDEM[b.robustez] || Math.abs(b.dif_pp) - Math.abs(a.dif_pp);

// "formato do vídeo: explicativo — 20% no top × 9% no controle" → "Formato do vídeo" e "explicativo"
const nomeCampo = (a: Achado) => a.descricao.split(":")[0];
const rotuloCampo = (a: Achado) => nomeCampo(a)[0].toUpperCase() + nomeCampo(a).slice(1);
const rotuloValor = (a: Achado) => nomeAchado(a.descricao).split(": ").slice(1).join(": ");
const maiuscula = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
const multiplicador = (a: Achado) => (a.lift == null ? "só no top" : `${num(a.lift >= 1 ? a.lift : 1 / a.lift, 1)}×`);

function useExemplos(a: Achado | null, segmento: string, faixas: string[], n: number) {
  const [refs, setRefs] = useState<ReferencePost[] | null>(null);
  const chave = a ? `${a.campo}=${a.valor}|${segmento}|${faixas.join("+")}|${n}` : "";
  useEffect(() => {
    setRefs(null);
    if (!a) return;
    let ativo = true;
    api.exemplos(a.campo, a.valor, segmento, faixas, n).then((r) => ativo && setRefs(r)).catch(() => ativo && setRefs([]));
    return () => { ativo = false; };
  }, [chave]); // eslint-disable-line react-hooks/exhaustive-deps
  return refs;
}

// Cartão de destaque: o multiplicador grande, o que é, os números e (no que fazer) Reels do top que têm a característica.
function Destaque({ a, evitar, segmento, faixas, abrir }: {
  a: Achado; evitar: boolean; segmento: string; faixas: string[]; abrir: (el: HTMLElement) => void;
}) {
  const refs = useExemplos(evitar ? null : a, segmento, faixas, 3);
  return (
    <Paper p="lg" className="clicavel" onClick={(e) => abrir(e.currentTarget)} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && abrir(e.currentTarget)} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <Text size="xs" c="dimmed">{evitar ? "Evitar" : rotuloCampo(a)}</Text>
      <Text fz={34} fw={600} lh={1.1} c={a.robustez === "robusto" && !evitar ? "var(--verde-texto)" : undefined}
        style={{ letterSpacing: "-0.02em" }}>
        {multiplicador(a)}
      </Text>
      <Text fw={500}>{evitar ? `${rotuloCampo(a)}: ${rotuloValor(a)}` : rotuloValor(a)}</Text>
      <Text size="sm" c="dimmed">
        {evitar ? "menos comum no top · " : ""}{pct(a.freq_top)} do top × {pct(a.freq_controle)} do controle
      </Text>
      <Box mt="sm" mih={evitar ? 0 : 76} onClick={(e) => e.stopPropagation()}>
        {!evitar && (refs ? (
          <Group gap={6}>{refs.map((r) => <MiniReel key={r.shortCode} codigo={r.shortCode} refs={refs} largura={42} />)}</Group>
        ) : <Loader size={14} />)}
      </Box>
      <Box mt="auto" pt="xs"><SeloRobustez robustez={a.robustez} /></Box>
    </Paper>
  );
}

// Peça da grade: uma característica, o valor que mais se destaca nela e duas barras (top e controle).
function Peca({ itens, abrir }: { itens: Achado[]; abrir: (el: HTMLElement) => void }) {
  const fortes = itens.filter(relevante).sort(porForca);
  const a = fortes[0] ?? [...itens].sort((x, y) => y.freq_top - x.freq_top)[0];
  const destaca = fortes.length > 0;
  return (
    <UnstyledButton onClick={(e) => abrir(e.currentTarget)} className="clicavel peca">
      <Text size="xs" c="dimmed" truncate>{rotuloCampo(a)}</Text>
      <Text size="sm" fw={500} truncate mt={2}>{destaca ? rotuloValor(a) : "Sem diferença clara"}</Text>
      <Text size="xs" c={destaca && a.robustez === "robusto" && a.dif_pp > 0 ? "var(--verde-texto)" : "dimmed"} mb={8}>
        {destaca ? vezes(a.lift, a.robustez).replace(" no top", "") : `mais comum: ${rotuloValor(a)}`}
      </Text>
      <div className="peca-barra"><span style={{ width: `${a.freq_top * 100}%`, background: corTop(a) }} /></div>
      <div className="peca-barra"><span style={{ width: `${a.freq_controle * 100}%`, background: "var(--barra-controle)" }} /></div>
    </UnstyledButton>
  );
}

// Detalhe de uma característica (num glance): todos os valores e os Reels do top com o valor escolhido. Ao lado do
// título, só a `acao` (em tipo de gancho, "Ver todos os ganchos"), que recebe o valor escolhido na lista.
function Detalhe({ itens, inicial, segmento, faixas, acao }: {
  itens: Achado[]; inicial: string | null; segmento: string; faixas: string[]; acao?: (valor: string | null) => ReactNode;
}) {
  const ordenados = [...itens].sort((x, y) => y.freq_top - x.freq_top);
  const padrao = inicial ?? (itens.filter(relevante).sort(porForca)[0] ?? ordenados[0])?.valor ?? null;
  const [valor, setValor] = useState(padrao);
  useEffect(() => setValor(padrao), [padrao]);
  const escolhido = itens.find((a) => a.valor === valor) ?? null;
  const refs = useExemplos(escolhido, segmento, faixas, 6);
  if (!itens.length) return null;

  return (
    <>
      <Group justify="space-between" align="flex-start" gap="md" wrap="nowrap">
        <div>
          <Text size="sm" c="dimmed">Característica</Text>
          <Text fz={26} fw={600} lh={1.25} mt={2}>{rotuloCampo(itens[0])}</Text>
          <Text c="dimmed" mt={6}>Quanto cada valor aparece no top e no controle. Clique num valor para ver os Reels.</Text>
        </div>
        {acao?.(valor)}
      </Group>

      <Box mt={32} style={{ display: "flex", gap: 40, alignItems: "flex-start", flexWrap: "wrap" }}>
        <Box w={{ base: "100%", sm: 300 }} className="coluna-fixa">
          <ListaValores achados={itens} rotulo={(a) => maiuscula(rotuloValor(a))} contagem={(a) => `${a.n_top} Reels no top`}
            ativo={valor} onEscolher={setValor} />
        </Box>

        <Box style={{ flex: 1, minWidth: 280 }}>
          {escolhido && (
            <>
              <Text fz={20} fw={600} lh={1.3}>{maiuscula(rotuloValor(escolhido))} no top</Text>
              <Text size="sm" c="dimmed" mt={4} mb="md">
                {escolhido.n_top ? "Reels do top com esse valor, do maior engajamento (no máximo 2 por perfil)." : "Nenhum Reel do top tem esse valor."}
              </Text>
            </>
          )}
          {!refs && <Loader size="sm" />}
          {refs?.length === 0 && escolhido?.n_top !== 0 && <Text size="sm" c="dimmed">Nenhum Reel do top com esse valor.</Text>}
          {refs && refs.length > 0 && (
            <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="md">{refs.map((r) => <CartaoReel key={r.shortCode} r={r} largura="100%" />)}</SimpleGrid>
          )}
        </Box>
      </Box>
    </>
  );
}

function Perfis({ perfis }: { perfis: TPanorama["perfis"] }) {
  const [todos, setTodos] = useState(false);
  const lista = todos ? perfis : perfis.slice(0, 8);
  if (!perfis.length) return <Text size="sm" c="dimmed">Nenhum perfil com Reels no top neste recorte.</Text>;
  return (
    <div>
      {lista.map((p) => (
        <Group key={p.perfil} gap="md" wrap="nowrap" py={10} style={{ borderBottom: "1px solid var(--linha)" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Anchor href={`https://www.instagram.com/${p.perfil}/`} target="_blank" size="sm" fw={500} c="inherit">@{p.perfil}</Anchor>
            <Text size="xs" c="dimmed" truncate>
              {p.faixa} · {compacto(p.seguidores)} seguidores · {p.tema_predominante.replaceAll("_", " ")} · {p.formato_predominante.replaceAll("_", " ")}
            </Text>
          </div>
          <Text size="sm" ta="right" style={{ flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
            {p.n_top} de {p.n_amostra} <Text span size="xs" c="dimmed">no top</Text>
          </Text>
          <Text size="sm" c="dimmed" ta="right" w={64} visibleFrom="xs" style={{ flexShrink: 0 }}>{pct(p.taxa_mediana, 1)}</Text>
        </Group>
      ))}
      {perfis.length > 8 && (
        <Button variant="subtle" color="gray" size="compact-sm" mt="sm" onClick={() => setTodos((t) => !t)}>
          {todos ? "Mostrar menos" : `Ver os ${perfis.length}`}
        </Button>
      )}
    </div>
  );
}

function Rotulo({ children }: { children: ReactNode }) {
  return <Text size="sm" c="dimmed" mb="md">{children}</Text>;
}

export default function Panorama() {
  const [segmento, setSegmento] = useState("");
  const [faixas, setFaixas] = useState<string[]>([]);
  const [dados, setDados] = useState<TPanorama | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [vista, setVista] = useState("cartoes");
  const [aberto, setAberto] = useState<{ campo: string; valor: string | null; origem: DOMRect | null } | null>(null);
  useTitulo("Panorama");
  const abrirGanchos = useAbrirGanchos();

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    api.panorama(segmento, faixas)
      .then((d) => { if (ativo) { setDados(d); setErro(null); } })
      .catch((e) => ativo && setErro(e.message))
      .finally(() => ativo && setCarregando(false));
    return () => { ativo = false; };
  }, [segmento, faixas]);

  const achados = useMemo(() => dados?.achados ?? [], [dados]);
  // Características (campos) com os seus valores; as que diferenciam o top vêm primeiro.
  const campos = useMemo(() => {
    const grupos = new Map<string, Achado[]>();
    for (const a of achados) grupos.set(a.campo, [...(grupos.get(a.campo) ?? []), a]);
    const forca = (itens: Achado[]) => Math.min(...itens.filter(relevante).map((a) => ORDEM[a.robustez]), 9);
    return [...grupos.entries()].sort(([, a], [, b]) => forca(a) - forca(b));
  }, [achados]);

  const fortes = achados.filter(relevante).sort(porForca);
  const destaques = [...fortes.filter((a) => a.dif_pp > 0).slice(0, 3), ...fortes.filter((a) => a.dif_pp < 0).slice(0, 1)];
  const semEfeito = [...new Set(achados.filter((a) => a.robustez === "sem_diferenca" && a.valor === "True").map(nomeCampo))];
  const itensAbertos = aberto ? campos.find(([c]) => c === aberto.campo)?.[1] ?? [] : [];
  const abrir = (a: Achado, el?: Element | null) =>
    setAberto({ campo: a.campo, valor: a.valor, origem: el?.getBoundingClientRect() ?? null });

  return (
    <Tela>
      <TituloTela
        titulo="Panorama"
        subtitulo="O que diferencia os 10% de Reels com maior engajamento de um controle sorteado do mesmo tamanho."
      />

      <Group gap="xs" mb={40} pb="md" style={{ borderBottom: "1px solid var(--linha)" }}>
        <Escolha icone={IconBuildingStore} opcoes={SEGMENTOS} valor={segmento} onChange={(v) => setSegmento(v as string)} />
        <Escolha icone={IconUsers} opcoes={FAIXAS} valor={faixas} multiplo vazio="Todos os tamanhos"
          onChange={(v) => setFaixas(v as string[])} />
        {dados && (
          <Text size="sm" c="dimmed" ml="xs">
            {inteiro(dados.totais.reels)} Reels · {inteiro(dados.totais.top)} no top · {inteiro(dados.totais.perfis)} perfis
          </Text>
        )}
        {carregando && <Loader size={14} ml="xs" />}
      </Group>

      {erro && <Box mb="xl"><Erro titulo="Não foi possível carregar o panorama">{erro}</Erro></Box>}
      {!dados && !erro && <Loader size="sm" />}

      {dados && (
        <Stack gap={64} style={{ opacity: carregando ? 0.5 : 1, transition: "opacity 0.2s" }}>
          <section>
            <Text fw={600} mb={4}>Destaques</Text>
            <Rotulo>
              O que mais separa o top do controle{dados.recorte ? " neste recorte" : ""}. Clique para ver os valores e os Reels.
              {dados.recorte && ` Num recorte, o mais forte possível é “Indício”${dados.totais.top < 60 ? `, e com ${dados.totais.top} Reels no top, leia como pistas` : ""}.`}
            </Rotulo>
            {destaques.length ? (
              <SimpleGrid cols={{ base: 1, sm: 2, lg: Math.min(destaques.length, 4) }} spacing="md">
                {destaques.map((a) => (
                  <Destaque key={a.campo + a.valor} a={a} evitar={a.dif_pp < 0} segmento={segmento} faixas={faixas} abrir={(el) => abrir(a, el)} />
                ))}
              </SimpleGrid>
            ) : (
              <Text c="dimmed">Neste recorte, nenhuma característica separa o top do controle com segurança.</Text>
            )}
          </section>

          <Secao
            titulo="Explorar por característica"
            direita={(
              <SegmentedControl size="xs" value={vista} onChange={setVista}
                data={[{ value: "cartoes", label: "Cartões" }, { value: "lista", label: "Lista" }]} />
            )}
          >
            {vista === "cartoes" ? (
              <>
                <Box mb="md"><LegendaBarras verde /></Box>
                <SimpleGrid cols={{ base: 2, sm: 3, lg: 4 }} spacing="sm">
                  {campos.map(([campo, itens]) => (
                    <Peca key={campo} itens={itens} abrir={(el) => setAberto({ campo, valor: null, origem: el.getBoundingClientRect() })} />
                  ))}
                </SimpleGrid>
              </>
            ) : (
              <Stack gap={40}>
                <Legenda />
                {campos.map(([campo, itens]) => (
                  <Grupo key={campo} titulo={rotuloCampo(itens[0])} achados={[...itens].sort((x, y) => y.freq_top - x.freq_top)} />
                ))}
              </Stack>
            )}
            {semEfeito.length > 0 && (
              <Text size="sm" c="dimmed" mt="lg" maw={760}>Não diferenciam o top do controle: {semEfeito.join(", ")}.</Text>
            )}
          </Secao>

          <Secao titulo="Perfis em destaque">
            <Rotulo>Criadores com mais Reels no top{dados.recorte ? " neste recorte" : ""}. À direita, a taxa mediana de engajamento.</Rotulo>
            <Perfis perfis={dados.perfis} />
          </Secao>
        </Stack>
      )}

      {aberto && itensAbertos.length > 0 && (
        <Glance origem={aberto.origem} onFechar={() => setAberto(null)} rotulo={rotuloCampo(itensAbertos[0])} largura={1040}>
          <Box px={{ base: "md", sm: 40 }} pt={{ base: 56, sm: 40 }} pb={48}>
            <Detalhe itens={itensAbertos} inicial={aberto.valor} segmento={segmento} faixas={faixas}
              acao={aberto.campo === "tipo_hook" ? (valor) => (
                <Button leftSection={<IconQuote size={16} />} variant="default" style={{ flexShrink: 0 }}
                  onClick={(e) => { abrirGanchos(valor ?? TODOS, e.currentTarget); setAberto(null); }}>
                  Ver todos os ganchos
                </Button>
              ) : undefined} />
          </Box>
        </Glance>
      )}
    </Tela>
  );
}
