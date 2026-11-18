import { useLocalStorage } from "@mantine/hooks";
import { createContext, useContext, useEffect, useState, useSyncExternalStore } from "react";

import { api } from "./api";
import type { Achado, Execucao, ExecucaoResumo, FrequenciaStone, FrequenciasStone } from "./tipos";

// Qualquer componente abre um Reel num glance com abrirReel(shortCode, elemento clicado); o glance cresce a partir
// desse elemento.
export const ReelContexto = createContext<(shortCode: string, origem?: Element | null) => void>(() => {});
export const useAbrirReel = () => useContext(ReelContexto);

// Qualquer componente abre o banco de ganchos num glance com abrirGanchos(tipo, elemento clicado); o glance cresce a
// partir desse elemento.
export const GanchosContexto = createContext<(tipo: string, origem?: Element | null) => void>(() => {});
export const useAbrirGanchos = () => useContext(GanchosContexto);

// Execuções recentes da barra lateral; as telas pedem para recarregar quando terminam uma execução.
export const RecentesContexto = createContext<{ recentes: ExecucaoResumo[] | null; atualizar: () => void }>({
  recentes: null,
  atualizar: () => {},
});
export const useRecentes = () => useContext(RecentesContexto);

// Execuções já carregadas: a tela que acabou de rodar guarda a sua aqui antes de navegar para /<tela>/<run_id>.
const cache = new Map<string, Execucao>();
export const guardarExecucao = (e: Execucao) => cache.set(e.run_id, e);

export function useExecucao(runId: string | undefined) {
  const [execucao, setExecucao] = useState<Execucao | null>(runId ? cache.get(runId) ?? null : null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setErro(null);
    if (!runId) return setExecucao(null);
    const guardada = cache.get(runId);
    if (guardada) return setExecucao(guardada);
    setExecucao(null);
    let ativo = true;
    api.execucao(runId)
      .then((e) => { cache.set(runId, e); if (ativo) setExecucao(e); })
      .catch((e) => ativo && setErro(e.message));
    return () => { ativo = false; };
  }, [runId]);

  return { execucao, erro };
}

// Segundos desde `inicio` (para mostrar há quanto tempo o agente está trabalhando, mesmo depois de trocar de tela).
export function useCronometro(inicio: number) {
  const calc = () => Math.max(0, Math.round((Date.now() - inicio) / 1000));
  const [s, setS] = useState(calc);
  useEffect(() => {
    setS(calc());
    const t = setInterval(() => setS(calc()), 1000);
    return () => clearInterval(t);
  }, [inicio]); // eslint-disable-line react-hooks/exhaustive-deps
  return s;
}

// Execuções em andamento, uma por tela. Ficam fora dos componentes para continuar quando a pessoa troca de tela:
// ao voltar, a tela mostra o progresso; ao terminar, o resultado só abre sozinho se ela ainda estiver na tela.
export type TelaExecucao = "perguntar" | "criar" | "avaliar";
export interface Tarefa {
  titulo: string;
  inicio: number;
  rodando: boolean;
  etapa?: string | null;
  fonte?: "video" | "roteiro";
  erro?: string;
}

let tarefas: Partial<Record<TelaExecucao, Tarefa>> = {};
const ouvintes = new Set<() => void>();

function mudar(tela: TelaExecucao, t: Tarefa | null) {
  tarefas = { ...tarefas };
  if (t) tarefas[tela] = t;
  else delete tarefas[tela];
  ouvintes.forEach((f) => f());
}

export function useTarefas() {
  return useSyncExternalStore((f) => { ouvintes.add(f); return () => { ouvintes.delete(f); }; }, () => tarefas);
}
export const useTarefa = (tela: TelaExecucao) => useTarefas()[tela];
export const limparTarefa = (tela: TelaExecucao) => mudar(tela, null);

export async function rodar(tela: TelaExecucao, inicial: Omit<Tarefa, "inicio" | "rodando">,
  executar: (avisar: (etapa: string) => void) => Promise<Execucao>, abrir: (rota: string) => void, aoTerminar: () => void) {
  const base: Tarefa = { ...inicial, inicio: Date.now(), rodando: true };
  mudar(tela, base);
  try {
    const e = await executar((etapa) => mudar(tela, { ...(tarefas[tela] ?? base), etapa }));
    cache.set(e.run_id, e);
    mudar(tela, null);
    if (window.location.pathname.startsWith(`/${tela}`)) abrir(`/${tela}/${e.run_id}`);
  } catch (err) {
    mudar(tela, { ...base, rodando: false, erro: (err as Error).message });
  } finally {
    aoTerminar();
  }
}

// Título da aba do navegador.
export function useTitulo(titulo: string | null | undefined) {
  useEffect(() => {
    document.title = titulo ? `${titulo} · Impulso Stone` : "Agente Impulso Stone";
  }, [titulo]);
}

// Comparação com a @impulsostone: um interruptor só para o app todo (lembrado no navegador). Ligado, as barras e os
// números top x controle ganham a frequência nos Reels da Stone. As frequências vêm uma vez, na primeira vez que liga.
let frequenciasStone: Promise<FrequenciasStone> | null = null;

export function useComparacaoStone() {
  const [ativo, setAtivo] = useLocalStorage({ key: "comparar-stone", defaultValue: false });
  const [dados, setDados] = useState<FrequenciasStone | null>(null);
  useEffect(() => {
    if (ativo) (frequenciasStone ??= api.frequenciasStone()).then(setDados).catch(() => { frequenciasStone = null; });
  }, [ativo]);
  const stone = ativo ? dados : null;
  const de = (a: Pick<Achado, "campo" | "valor">): FrequenciaStone | null => stone?.valores[`${a.campo}=${a.valor}`] ?? null;
  return { ativo, setAtivo, stone, de };
}
