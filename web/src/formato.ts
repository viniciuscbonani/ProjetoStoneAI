import type { Confianca, Robustez } from "./tipos";

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

export const rotuloValor = (v: unknown) =>
  v === true ? "sim" : v === false ? "não" : String(v).replaceAll("_", " ");
