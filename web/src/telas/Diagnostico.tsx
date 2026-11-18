import { Anchor, Box, Button, Group, Loader, Paper, SimpleGrid, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconSparkles } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { api } from "../api";
import { corTop } from "../componentes/Achados";
import CartaoReel, { FaixaReels } from "../componentes/CartaoReel";
import { Erro, Secao, Tela, TituloTela } from "../componentes/Comum";
import Glance from "../componentes/Glance";
import { SeloRobustez } from "../componentes/Selos";
import { useTitulo } from "../contexto";
import { nomeAchado, pct } from "../formato";
import type { Achado, Diagnostico as TDiagnostico, FrequenciaStone } from "../tipos";

// Um item do diagnóstico: o achado da base, a frequência na @impulsostone e a situação dela.
type Situacao = "mudar" | "observar" | "em_linha" | "nao_alavanca";
interface Item {
  achado: Achado & { depende_de_poucos?: boolean };
  stone: FrequenciaStone;
  situacao: Situacao;
  lacuna: boolean;
  reels_stone: TDiagnostico["reels"];
  reels_top: TDiagnostico["reels"];
}

const SITUACAO: Record<Situacao, { titulo: string; ajuda: string }> = {
  mudar: { titulo: "O que mudar", ajuda: "Onde a @impulsostone fica longe do top com segurança, mesmo com poucos Reels." },
  observar: { titulo: "Para observar", ajuda: "A @impulsostone está do lado do controle, mas com poucos Reels não dá para afirmar." },
  em_linha: { titulo: "Já em linha com o top", ajuda: "Diferenciam o top, e a @impulsostone já está do lado dele." },
  nao_alavanca: { titulo: "Não é alavanca", ajuda: "Hipóteses da Stone que não diferenciam o top nos Reels orgânicos: podem seguir como estão." },
};

const maiuscula = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
const data = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR", { day: "numeric", month: "short" });
const simNao = (a: Achado) => a.valor === "True" || a.valor === "False";
// Em campos sim/não, o nome do item é o próprio campo ("Data comemorativa"); nos outros, o valor ("Mais de 90 s") com o
// campo acima, como rótulo.
const campoDe = (a: Achado) => (simNao(a) ? "" : maiuscula(nomeAchado(a.descricao).split(": ")[0]));
const valorDe = (a: Achado) => (simNao(a)
  ? `${nomeAchado(a.descricao).split(": ")[0]}${a.valor === "False" ? " (não)" : ""}`
  : nomeAchado(a.descricao).split(": ").slice(1).join(": "));

// O que a característica quer dizer, como verbo: "duram mais de 90 s", "abrem com gancho de curiosidade". Assim os números
// viram frase: "5% dos Reels da @impulsostone duram mais de 90 s".
const VERBOS: Record<string, (v: string) => string> = {
  duracao_faixa: (v) => `duram ${v}`,
  tipo_hook: (v) => `abrem com gancho de ${v}`,
  formato_video: (v) => `são no formato ${v}`,
  abordagem: (v) => `têm abordagem de ${v}`,
  tema_principal: (v) => `têm o tema ${v}`,
  tipo_cta: (v) => `têm CTA de ${v}`,
  tem_rosto: () => "mostram rosto em cena",
  tem_cta: () => "têm chamada para ação (CTA)",
  prova_social: () => "têm prova social",
  fala_de_negocio: () => "falam do negócio",
  tem_data_comemorativa: () => "falam de data comemorativa",
};
function oQue(campo: string, valor: string, rotulo: string): string {
  const nome = nomeAchado(rotulo).split(": ");
  const v = nome.length > 1 ? nome.slice(1).join(": ") : nome[0];
  const verbo = VERBOS[campo];
  if (valor === "True" || valor === "False") {
    const f = verbo ? verbo("") : `têm ${nome[0]}`;
    return valor === "False" ? `não ${f}` : f;
  }
  return verbo ? verbo(v) : `têm ${nome[0]}: ${v}`;
}
const oQueAchado = (a: Achado) => oQue(a.campo, a.valor, a.descricao.split(" — ")[0]);

function itens(d: TDiagnostico): Item[] {
  return [
    ...d.pontos.map((p) => ({
      achado: p.achado, stone: p.stone, reels_stone: p.reels_stone, reels_top: p.reels_top, lacuna: p.tipo === "lacuna",
      situacao: (p.tipo === "em_linha" ? "em_linha" : p.nivel === "claro" ? "mudar" : "observar") as Situacao,
    })),
    ...d.nao_alavanca.map((x) => ({ achado: x.achado, stone: x.stone, reels_stone: [], reels_top: [], lacuna: false, situacao: "nao_alavanca" as Situacao })),
  ];
}

const chave = (it: Item) => `${it.achado.campo}=${it.achado.valor}`;

function useCriar() {
  const navigate = useNavigate();
  return (a: Achado) => navigate("/criar", { state: { query: `Reels para a @impulsostone com ${nomeAchado(a.descricao)}` } });
}

// O veredito diz a comparação inteira, em duas linhas ("6× menos" / "que o top"); embaixo, de onde vêm os números.
function veredito(it: Item): { linhas: [string, string]; numeros: string[] } {
  const s = it.stone.freq, t = it.achado.freq_top;
  const numeros = [`${pct(s)} dos Reels da @impulsostone`, `${pct(t)} dos Reels do top`];
  if (it.stone.k === 0) return { linhas: ["Nenhum Reel", "da @impulsostone"], numeros: numeros.slice(1) };
  const r = t > s ? t / s : s / t;
  if (r >= 1.95) return { linhas: [`${Math.round(r)}× ${t > s ? "menos" : "mais"}`, "que o top"], numeros };
  const p = Math.abs(Math.round(t * 100) - Math.round(s * 100)); // dos números mostrados, para a conta bater
  if (p === 0) return { linhas: ["Igual", "ao top"], numeros };
  return { linhas: [`${p} ${p === 1 ? "ponto" : "pontos"}`, `${t > s ? "abaixo" : "acima"} do top`], numeros };
}

// Um ponto de "O que mudar" numa linha larga: à esquerda a característica no alto e o veredito no meio da altura,
// com o atalho e o selo no pé; à direita, Reels do top que fazem isso.
function LinhaPonto({ it, abrir }: { it: Item; abrir: (el: HTMLElement) => void }) {
  const criar = useCriar();
  const v = veredito(it);
  return (
    <Paper p="lg" className="clicavel" onClick={(e) => abrir(e.currentTarget)} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && abrir(e.currentTarget)}
      style={{ display: "flex", gap: 32, flexWrap: "wrap", alignItems: "stretch" }}>
      <Stack gap="lg" w={{ base: "100%", sm: 240 }} style={{ flexShrink: 0 }}>
        <div>
          <Text size="xs" c="dimmed">{campoDe(it.achado)}</Text>
          <Text fz={20} fw={600} lh={1.3}>{maiuscula(valorDe(it.achado))}</Text>
        </div>
        <Stack justify="center" style={{ flex: 1 }}>
          <div>
            <Text fz={30} fw={600} lh={1.1} c="var(--barra-stone)" style={{ letterSpacing: "-0.02em" }}>
              {v.linhas[0]}<br />{v.linhas[1]}
            </Text>
            {v.numeros.map((n, i) => <Text key={n} size="sm" c="dimmed" mt={i ? 0 : 10}>{n}</Text>)}
          </div>
        </Stack>
        <Group gap="md">
          <Anchor component="button" size="sm" c="var(--verde-texto)" onClick={(e) => { e.stopPropagation(); criar(it.achado); }}>
            Criar Reels com isso
          </Anchor>
          <SeloRobustez robustez={it.achado.robustez} />
        </Group>
      </Stack>
      <SimpleGrid cols={4} spacing="sm" style={{ flex: 1, minWidth: 280 }} onClick={(e) => e.stopPropagation()}>
        {it.reels_top.slice(0, 4).map((r) => <CartaoReel key={r.shortCode} r={r} largura="100%" />)}
      </SimpleGrid>
    </Paper>
  );
}

// Peça de "Todas as características": a característica (com o campo embaixo) e um veredito curto em destaque, na cor da
// situação (laranja quando pode ser problema, verde quando já está como o top, cinza quando não muda o engajamento), com
// os números embaixo.
const COR: Record<Situacao, string> = {
  mudar: "var(--barra-stone)", observar: "var(--barra-stone)", em_linha: "var(--verde-texto)", nao_alavanca: "var(--mantine-color-dimmed)",
};

// O veredito curto de cada situação: o que a @impulsostone faz em relação ao top.
function resumo(it: Item): string {
  if (it.situacao === "em_linha") return "Igual ao top";
  if (it.situacao === "nao_alavanca") return "Não faz diferença";
  return it.lacuna ? "Usa pouco" : "Usa demais";
}

function PecaVeredito({ it, abrir }: { it: Item; abrir: (el: HTMLElement) => void }) {
  const numeros = [`${pct(it.stone.freq)} dos Reels da @impulsostone`, `${pct(it.achado.freq_top)} dos Reels do top`];
  return (
    <UnstyledButton onClick={(e) => abrir(e.currentTarget)} className="clicavel peca"
      style={{ padding: "16px 18px", display: "flex", flexDirection: "column" }}>
      <Text fw={600} truncate>{maiuscula(valorDe(it.achado))}</Text>
      {campoDe(it.achado) && <Text size="xs" c="dimmed" truncate>{campoDe(it.achado)}</Text>}
      {/* No pé da peça, para o veredito ficar na mesma altura em toda a linha, com ou sem o campo embaixo do título. */}
      <div style={{ marginTop: "auto", paddingTop: 16 }}>
        <Text fz={22} fw={600} lh={1.2} c={COR[it.situacao]} style={{ letterSpacing: "-0.01em" }}>{resumo(it)}</Text>
        {numeros.map((n, i) => <Text key={n} size="xs" c="dimmed" mt={i ? 0 : 6}>{n}</Text>)}
      </div>
    </UnstyledButton>
  );
}

// Detalhe num glance: os números com rótulo, os Reels da Stone e do top, o que é mais comum na Stone e o atalho.
function Detalhe({ it, d, fechar }: { it: Item; d: TDiagnostico; fechar: () => void }) {
  const navigate = useNavigate();
  const a = it.achado;
  const retrato = d.retrato.find((c) => c.campo === a.campo);
  const linhas: [string, number, string][] = [
    ["Reels da @impulsostone", it.stone.freq, "var(--barra-stone)"], ["Reels do top 10%", a.freq_top, corTop(a)], ["Reels do controle", a.freq_controle, "var(--barra-controle)"],
  ];
  return (
    <Box px={{ base: "md", sm: 40 }} pt={{ base: 56, sm: 40 }} pb={48}>
      <Group justify="space-between" align="flex-start" gap="md" wrap="nowrap">
        <div>
          <Text size="sm" c="dimmed">{[SITUACAO[it.situacao].titulo, campoDe(a)].filter(Boolean).join(" · ")}</Text>
          <Text fz={26} fw={600} lh={1.25} mt={2}>{maiuscula(valorDe(a))}</Text>
          <Text c="dimmed" mt={6} maw={600}>
            {it.stone.k} de {d.n} Reels da @impulsostone {oQueAchado(a)} ({pct(it.stone.freq)}). Com tão poucos Reels, o valor real pode
            estar entre {pct(it.stone.ic_min)} e {pct(it.stone.ic_max)}.
            {a.depende_de_poucos && " O achado depende de poucos criadores: trate como algo a testar."}
          </Text>
        </div>
        {it.lacuna && it.situacao !== "em_linha" && (
          <Button variant="default" leftSection={<IconSparkles size={16} />} style={{ flexShrink: 0 }}
            onClick={() => { fechar(); navigate("/criar", { state: { query: `Reels para a @impulsostone com ${nomeAchado(a.descricao)}` } }); }}>
            Criar Reels com isso
          </Button>
        )}
      </Group>

      <Box mt={32} style={{ display: "flex", gap: 40, alignItems: "flex-start", flexWrap: "wrap" }}>
        <Stack w={{ base: "100%", sm: 280 }} gap="lg" style={{ flexShrink: 0 }}>
          <Stack gap={10}>
            <Text size="sm" fw={600}>% dos Reels que {oQueAchado(a)}</Text>
            {linhas.map(([nome, f, cor]) => (
              <div key={nome}>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">{nome}</Text>
                  <Text size="sm" fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>{pct(f)}</Text>
                </Group>
                <div className="peca-barra" style={{ height: 6, borderRadius: 3 }}><span style={{ width: `${f * 100}%`, background: cor }} /></div>
              </div>
            ))}
            <SeloRobustez robustez={a.robustez} />
          </Stack>
          {retrato && (
            <div>
              <Text size="sm" fw={600} mb={6}>Na @impulsostone, {retrato.rotulo} mais comum</Text>
              {retrato.valores.map((v) => (
                <Group key={v.valor} justify="space-between" py={3} wrap="nowrap">
                  <Text size="sm">{v.rotulo}</Text>
                  <Text size="sm" style={{ fontVariantNumeric: "tabular-nums" }}>
                    <Text span inherit fw={600}>{pct(v.freq)}</Text>
                    {v.freq_top != null && <Text span inherit c="dimmed"> · top {pct(v.freq_top)}</Text>}
                  </Text>
                </Group>
              ))}
            </div>
          )}
        </Stack>

        <Stack style={{ flex: 1, minWidth: 280 }} gap="xl">
          {it.reels_top.length > 0 && (
            <div>
              <Text fw={600} mb="sm">Como o top faz</Text>
              <SimpleGrid cols={3} spacing="md">{it.reels_top.map((r) => <CartaoReel key={r.shortCode} r={r} largura="100%" />)}</SimpleGrid>
            </div>
          )}
          {it.reels_stone.length > 0 && (
            <div>
              <Text fw={600} mb="sm">{it.lacuna ? "Os da @impulsostone que já fazem isso" : "Os da @impulsostone com isso"}</Text>
              <SimpleGrid cols={3} spacing="md">{it.reels_stone.map((r) => <CartaoReel key={r.shortCode} r={r} largura="100%" />)}</SimpleGrid>
            </div>
          )}
        </Stack>
      </Box>
    </Box>
  );
}

export default function Diagnostico() {
  useTitulo("Diagnóstico");
  const [d, setD] = useState<TDiagnostico | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aberto, setAberto] = useState<{ it: Item; origem: DOMRect } | null>(null);
  useEffect(() => { api.diagnostico().then(setD).catch((e) => setErro(e.message)); }, []);

  if (erro) return <Tela><Erro titulo="Não foi possível carregar o diagnóstico">{erro}</Erro></Tela>;
  if (!d) return <Tela><Loader size="sm" /></Tela>;

  const todos = itens(d);
  const abrir = (it: Item) => (el: HTMLElement) => setAberto({ it, origem: el.getBoundingClientRect() });
  const pos = d.posicao;
  const meio = pos.abaixo / pos.perfis_micro;
  const mudar = todos.filter((it) => it.situacao === "mudar");
  const grupos = (["observar", "em_linha", "nao_alavanca"] as Situacao[]).map((s) => [s, todos.filter((it) => it.situacao === s)] as const);

  return (
    <Tela>
      <TituloTela
        titulo="Diagnóstico da @impulsostone"
        subtitulo={`${d.n} Reels${d.periodo ? ` de ${data(d.periodo[0])} a ${data(d.periodo[1])}` : ""} comparados ao top 10% · taxa mediana de ${pct(pos.taxa_mediana, 1)}, ${meio >= 0.67 ? "acima da maioria" : meio <= 0.33 ? "abaixo da maioria" : "no meio"} dos perfis micro`}
      />

      <Stack gap={64}>
        <section>
          <Text fw={600} mb="md">O que mudar</Text>
          {!mudar.length && <Text c="dimmed">Nenhuma característica separa a @impulsostone do top com segurança.</Text>}
          <Stack gap="md">{mudar.map((it) => <LinhaPonto key={chave(it)} it={it} abrir={abrir(it)} />)}</Stack>
        </section>

        <Secao titulo="Todas as características">
          <Stack gap={40}>
            {grupos.filter(([, lista]) => lista.length).map(([s, lista]) => (
              <div key={s}>
                <Text size="sm" fw={600}>{SITUACAO[s].titulo}</Text>
                <Text size="sm" c="dimmed" mb="sm">{SITUACAO[s].ajuda}</Text>
                <SimpleGrid cols={{ base: 1, xs: 2, md: 3, lg: 4 }} spacing="sm">
                  {lista.map((it) => <PecaVeredito key={chave(it)} it={it} abrir={abrir(it)} />)}
                </SimpleGrid>
              </div>
            ))}
          </Stack>
        </Secao>

        <Secao titulo={`Os ${d.n} Reels da @impulsostone`}>
          <FaixaReels refs={d.reels} />
        </Secao>
      </Stack>

      {aberto && (
        <Glance origem={aberto.origem} onFechar={() => setAberto(null)} rotulo={maiuscula(valorDe(aberto.it.achado))} largura={1040}>
          <Detalhe it={aberto.it} d={d} fechar={() => setAberto(null)} />
        </Glance>
      )}
    </Tela>
  );
}
