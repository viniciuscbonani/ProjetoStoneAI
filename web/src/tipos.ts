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
  visual?: string;
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
  personagem?: string;
  prompt_capa: string;
  prompt_copiar?: string;
  inspirado_em: string[];
  achados_usados: string[];
}

export interface RevisaoImagem {
  aprovada: boolean;
  nota: number;
  problemas: string[];
  tentativas: number;
}

export interface ImagemGerada {
  url: string;
  revisao: RevisaoImagem | null;
}

export interface Ponto {
  texto: string;
  achado: string;
  robustez: Robustez;
  referencias: string[];
}

export interface Avaliacao {
  fonte: "video" | "roteiro";
  leitura: Record<string, string | number | boolean>;
  pontos_fortes: Ponto[];
  pontos_a_melhorar: Ponto[];
  sem_efeito: Ponto[];
}

export interface EstadoAvaliacao {
  id: string;
  pronto: boolean;
  etapa: string;
  erro: string | null;
  fonte: "video" | "roteiro";
  saida: Saida | null;
}

export interface Saida {
  run_id: string;
  mode: Modo;
  findings: Achado[];
  reference_posts: ReferencePost[];
  creatives: Criativo[];
  avaliacao?: Avaliacao | null;
  profiles: Perfil[];
  confidence_flag: Confianca;
  explanation: string;
  warnings: string[];
}

export interface Panorama {
  totais: { reels: number; top: number; perfis: number };
  recorte: boolean;
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
  transcricao: string;
}

// Busca nos Reels (GET /busca e /busca/opcoes), usada pela página Ganchos.
export interface ReelBusca extends ReferencePost {
  grupo: "top" | "controle";
  oculta_parcial: boolean;
  trecho: string | null;
  fala_final: string;
}

export interface ResultadoBusca {
  total: number;
  n_top: number;
  termos: string[];
  itens: ReelBusca[];
}

export interface FiltroBusca {
  campo: string;
  rotulo: string;
  valores: { valor: string; rotulo: string; n: number; n_top: number }[];
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

// Uma linha do log do agente (GET /execucoes/{run_id}).
export interface Execucao {
  run_id: string;
  quando: string;
  duracao_s: number;
  entrada: Entrada & { roteiro?: string | null; video_path?: string | null };
  erro: string | null;
  saida: Saida | null;
}

// Diagnóstico da @impulsostone (GET /diagnostico/frequencias e /diagnostico).
export interface FrequenciaStone { k: number; freq: number; ic_min: number; ic_max: number }

export interface FrequenciasStone {
  perfil: string;
  n: number;
  valores: Record<string, FrequenciaStone>;
}

export interface PontoDiagnostico {
  tipo: "lacuna" | "excesso" | "em_linha";
  nivel: "claro" | "provavel" | "";
  achado: Achado & { depende_de_poucos?: boolean };
  stone: FrequenciaStone;
  reels_stone: ReferencePost[];
  reels_top: ReferencePost[];
}

export interface Diagnostico {
  perfil: string;
  n: number;
  periodo: [string, string] | null;
  posicao: { taxa_mediana: number; perfis_micro: number; abaixo: number; mediana_micro: number };
  pontos: PontoDiagnostico[];
  nao_alavanca: { achado: Achado; stone: FrequenciaStone }[];
  retrato: { campo: string; rotulo: string; valores: { valor: string; rotulo: string; freq: number; freq_top: number | null }[] }[];
  reels: ReferencePost[];
}
