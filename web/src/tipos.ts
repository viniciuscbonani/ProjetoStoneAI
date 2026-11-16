// Tipos espelhados de agente/contrato.py e das rotas de agente/api.py.

export type Modo = "analisar" | "recomendar" | "gerar_criativo" | "avaliar";
export type Robustez = "robusto" | "fragil" | "sem_diferenca" | "insuficiente";
export type Confianca = "robusto" | "fragil" | "insuficiente";

export interface Entrada {
  mode: Modo;
  query: string;
  segment?: string | null;
  filters?: { faixa?: string[] | null } | null;
}

export interface Achado {
  campo: string;
  valor: string;
  descricao: string;
  freq_top: number;
  freq_controle: number;
  dif_pp: number;
  lift: number | null;
  ic95_min: number | null;
  ic95_max: number | null;
  n_top: number;
  n_controle: number;
  robustez: Robustez;
  recorte: string | null;
}

export interface ReferencePost {
  shortCode: string;
  url: string;
  perfil: string;
  faixa: string;
  seguidores: number;
  curtidas: number;
  comentarios: number;
  visualizacoes: number;
  taxa_engajamento: number;
  duracao_s: number;
  publicado_em: string;
  hook_texto: string;
  categorias: Record<string, string | boolean | number>;
  motivo: string;
}

export interface Perfil {
  perfil: string;
  faixa: string;
  seguidores: number;
  nicho: string;
  n_top: number;
  n_amostra: number;
  tema_predominante: string;
  formato_predominante: string;
  taxa_mediana: number;
}

export interface Cena {
  tempo: string;
  descricao: string;
  texto_na_tela: string;
  prompt_imagem: string;
}

export interface Criativo {
  titulo: string;
  formato: string;
  duracao_alvo: string;
  gancho: string;
  roteiro: Cena[];
  legenda: string;
  cta: string;
  prompt_capa: string;
  inspirado_em: string[];
  achados_usados: string[];
}

export interface Saida {
  run_id: string;
  mode: Modo;
  findings: Achado[];
  reference_posts: ReferencePost[];
  creatives: Criativo[];
  profiles: Perfil[];
  confidence_flag: Confianca;
  explanation: string;
  warnings: string[];
}

export interface Panorama {
  totais: { reels: number; top: number; perfis: number };
  achados: Achado[];
  perfis: Perfil[];
}

export interface ReelDetalhe extends Record<string, unknown> {
  shortCode: string;
  url: string;
  perfil: string;
  faixa: string;
  grupo: string;
  seguidores: number;
  curtidas: number;
  comentarios: number;
  visualizacoes: number;
  taxa_engajamento: number;
  duracao_s: number;
  publicado_em: string;
  hook_texto: string;
  legenda: string;
  elementos_top5: string[];
  quadros: string[];
}

export interface ExecucaoResumo {
  run_id: string;
  quando: string;
  mode: Modo;
  query: string;
  segment: string | null;
  duracao_s: number;
  erro: string | null;
  confidence_flag: Confianca | null;
}
