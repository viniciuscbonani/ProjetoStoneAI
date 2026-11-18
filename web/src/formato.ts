import type { Confianca, Modo, Robustez } from "./tipos";

const br = (n: number, casas = 0) => n.toLocaleString("pt-BR", { maximumFractionDigits: casas, minimumFractionDigits: casas });

export const pct = (x: number, casas = 0) => `${br(x * 100, casas)}%`;
export const num = (x: number | null | undefined, casas = 2) => (x == null ? "–" : br(x, casas));
export const inteiro = (x: number) => x.toLocaleString("pt-BR");
export const compacto = (x: number) => new Intl.NumberFormat("pt-BR", { notation: "compact" }).format(x);

export const ROBUSTEZ: Record<Robustez, { rotulo: string; cor: string; ajuda: string }> = {
  robusto: { rotulo: "Diferença clara", cor: "stone", ajuda: "diferença consistente entre top e controle" },
  fragil: { rotulo: "Indício", cor: "yellow", ajuda: "diferença que ainda não se sustenta em todos os testes; hipótese a testar" },
  sem_diferenca: { rotulo: "Sem diferença", cor: "gray", ajuda: "a diferença entre top e controle não é confiável (pode ser variação entre criadores): não diferencia os Reels de alto engajamento" },
  insuficiente: { rotulo: "Poucos dados", cor: "orange", ajuda: "menos de 20 Reels no top; não dá para afirmar" },
};

export const CONFIANCA: Record<Confianca, { rotulo: string; cor: string; ajuda: string }> = {
  robusto: { rotulo: "Alta", cor: "stone", ajuda: "a conclusão se apoia em dados consistentes" },
  fragil: { rotulo: "Média", cor: "yellow", ajuda: "a conclusão se apoia em indícios; trate como hipótese" },
  insuficiente: { rotulo: "Baixa", cor: "orange", ajuda: "a conclusão se apoia em poucos Reels" },
};

// O lift em linguagem simples, como no agente (dados.vezes).
export const vezes = (lift: number | null, robustez: Robustez) => {
  if (robustez === "sem_diferenca") return "diferença não confiável entre top e controle";
  if (lift == null) return "só aparece no top";
  if (lift >= 1) return `${num(lift, 1)}× mais comum no top`;
  return lift > 0 ? `${num(1 / lift, 1)}× menos comum no top` : "não aparece no top";
};

export const SEGMENTOS = [
  { value: "", label: "Todos os setores" },
  { value: "alimentacao", label: "Alimentação" },
  { value: "beleza", label: "Beleza" },
  { value: "varejo", label: "Varejo" },
  { value: "servicos", label: "Serviços" },
];

export const FAIXAS = [
  { value: "micro", label: "Micro (até 10 mil)" },
  { value: "medio", label: "Médio (10 a 100 mil)" },
  { value: "grande", label: "Grande (100 mil+)" },
];

// Rótulos com acento dos valores da rubrica (os mesmos de dados.VALORES na API).
const VALORES: Record<string, string> = {
  ate_15s: "até 15 s", "15_30s": "15 a 30 s", "30_60s": "30 a 60 s", "60_90s": "60 a 90 s", mais_90s: "mais de 90 s",
  link_na_bio: "link na bio", dm: "mensagem direta (DM)", numero: "número", polemica: "polêmica", dor_real: "dor real",
  motivacional_generica: "motivacional genérica", humoristico: "humorístico", tecnico: "técnico",
  alimentacao: "alimentação", servicos: "serviços", ferramentas_maquininha: "ferramentas e maquininha",
  financas: "finanças", gestao: "gestão", historia_de_empreendedor: "história de empreendedor",
  gestao_e_vendas: "gestão e vendas", educacao_financeira: "educação financeira", historias_reais: "histórias reais",
  medio: "médio", rapido: "rápido", media: "média",
};

export const rotuloValor = (v: unknown) =>
  v === true ? "sim" : v === false ? "não" : VALORES[String(v)] ?? String(v).replaceAll("_", " ");

export const rotuloSegmento = (s: string | null | undefined) => SEGMENTOS.find((x) => x.value === (s ?? ""))?.label ?? s ?? "";

export const ROTULO_MODO: Record<Modo, string> = {
  analisar: "Analisar", recomendar: "Recomendar", gerar_criativo: "Criar", avaliar: "Avaliar",
};

// Cada modo tem a sua tela; o resultado de uma execução abre em /<tela>/<run_id>.
export const rotaDoModo = (modo: Modo) =>
  ({ analisar: "/perguntar", recomendar: "/perguntar", gerar_criativo: "/criar", avaliar: "/avaliar" })[modo];

// "quando" vem do log do agente (ISO, horário local).
export function tempoRelativo(iso: string) {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  if (min < 24 * 60) return `há ${Math.round(min / 60)} h`;
  return new Date(iso).toLocaleDateString("pt-BR", { day: "numeric", month: "short" });
}

export const nomeAchado = (descricao: string) => descricao.split(" — ")[0];

// Recorte de um achado ("segmento=beleza", "faixa=micro") em texto.
export const rotuloRecorte = (recorte: string) =>
  recorte.replace(/segmento=(\w+)/, (_, s) => `setor ${rotuloSegmento(s).toLowerCase()}`).replace(/faixa=(\w+)/, "perfis $1");
