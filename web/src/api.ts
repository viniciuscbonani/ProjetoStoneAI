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
};

export const urlQuadro = (shortCode: string, nome = "gancho_0s") => `/api/reels/${shortCode}/quadros/${nome}`;
