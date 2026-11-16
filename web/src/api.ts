import type { Entrada, ExecucaoResumo, Panorama, ReelDetalhe, Saida } from "./tipos";

async function chamar<T>(caminho: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${caminho}`, init);
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    const detalhe = typeof corpo.detail === "string" ? corpo.detail : `erro ${resp.status}`;
    throw new Error(detalhe);
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
  panorama: () => chamar<Panorama>("/panorama"),
  reel: (shortCode: string) => chamar<ReelDetalhe>(`/reels/${shortCode}`),
  execucoes: () => chamar<ExecucaoResumo[]>("/execucoes"),
  execucao: (runId: string) => chamar<{ saida: Saida | null; erro: string | null }>(`/execucoes/${runId}`),
  gerarImagem: (runId: string, criativo: number, indice: number) =>
    chamar<{ indice: number; url: string }>("/imagens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId, criativo, indice }),
    }),
  imagens: (runId: string) => chamar<Record<string, string>>(`/imagens/${runId}`),
};

export const urlQuadro = (shortCode: string, nome = "gancho_0s") => `/api/reels/${shortCode}/quadros/${nome}`;
