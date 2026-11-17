import type {
  Entrada, EstadoAvaliacao, Execucao, ExecucaoResumo, ImagemGerada, Panorama, ReelDetalhe, ReferencePost, Saida,
} from "./tipos";

const SEM_API = "A API não respondeu. Ela está rodando? Em outro terminal: .venv/bin/uvicorn agente.api:app --port 8000";

async function chamar<T>(caminho: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`/api${caminho}`, init);
  } catch {
    throw new Error(SEM_API);
  }
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => null);
    // Sem corpo JSON e com 5xx: é o proxy do Vite avisando que a API está fora do ar.
    if (!corpo && resp.status >= 500) throw new Error(SEM_API);
    throw new Error(typeof corpo?.detail === "string" ? corpo.detail : `erro ${resp.status}`);
  }
  return resp.json();
}

export const api = {
  consultar: (entrada: Entrada) =>
    chamar<Saida>("/consultas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entrada),
    }),
  panorama: (segmento: string, faixas: string[]) => {
    const q = new URLSearchParams();
    if (segmento) q.set("segmento", segmento);
    faixas.forEach((f) => q.append("faixa", f));
    return chamar<Panorama>(`/panorama${q.size ? `?${q}` : ""}`);
  },
  exemplos: (campo: string, valor: string, segmento: string, faixas: string[], n = 6) => {
    const q = new URLSearchParams({ campo, valor, n: String(n) });
    if (segmento) q.set("segmento", segmento);
    faixas.forEach((f) => q.append("faixa", f));
    return chamar<ReferencePost[]>(`/panorama/exemplos?${q}`);
  },
  reel: (shortCode: string) => chamar<ReelDetalhe>(`/reels/${shortCode}`),
  execucoes: () => chamar<ExecucaoResumo[]>("/execucoes"),
  execucao: (runId: string) => chamar<Execucao>(`/execucoes/${runId}`),
  gerarImagem: (runId: string, criativo: number, indice: number) =>
    chamar<ImagemGerada & { indice: number }>("/imagens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId, criativo, indice }),
    }),
  avaliar: (dados: FormData) => chamar<{ id: string }>("/avaliacoes", { method: "POST", body: dados }),
  estadoAvaliacao: (id: string) => chamar<EstadoAvaliacao>(`/avaliacoes/${id}`),
  imagens: (runId: string) => chamar<Record<string, ImagemGerada>>(`/imagens/${runId}`),
};

// O criativo n de uma execução em .zip (texto, prompt e imagens já geradas).
export const urlZipCriativo = (runId: string, n: number) => `/api/execucoes/${runId}/criativos/${n}.zip`;

export const urlQuadro = (shortCode: string, nome = "gancho_0s") => `/api/reels/${shortCode}/quadros/${nome}`;
