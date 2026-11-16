import type { Robustez } from "./tipos";

const br = (n: number, casas = 0) => n.toLocaleString("pt-BR", { maximumFractionDigits: casas, minimumFractionDigits: casas });

export const pct = (x: number, casas = 0) => `${br(x * 100, casas)}%`;
export const num = (x: number | null | undefined, casas = 2) => (x == null ? "–" : br(x, casas));
export const inteiro = (x: number) => x.toLocaleString("pt-BR");
export const compacto = (x: number) => new Intl.NumberFormat("pt-BR", { notation: "compact" }).format(x);

export const ROBUSTEZ: Record<Robustez, { rotulo: string; cor: string; ajuda: string }> = {
  robusto: { rotulo: "Robusto", cor: "stone", ajuda: "diferença consistente entre top e controle" },
  fragil: { rotulo: "Frágil", cor: "yellow", ajuda: "indício; tratar como hipótese a testar" },
  insuficiente: { rotulo: "Insuficiente", cor: "gray", ajuda: "poucos Reels; não dá para afirmar" },
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
