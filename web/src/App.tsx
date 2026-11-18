import { useWindowEvent } from "@mantine/hooks";
import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router";

import { api } from "./api";
import Glance from "./componentes/Glance";
import Layout from "./componentes/Layout";
import ReelGlance from "./componentes/ReelGlance";
import { GanchosContexto, RecentesContexto, ReelContexto } from "./contexto";
import Avaliar from "./telas/Avaliar";
import { PainelGanchos, rotuloGancho, TODOS } from "./telas/Ganchos";
import Criar from "./telas/Criar";
import Diagnostico from "./telas/Diagnostico";
import Panorama from "./telas/Panorama";
import Perguntar from "./telas/Perguntar";
import type { ExecucaoResumo } from "./tipos";

export default function App() {
  const [reel, setReel] = useState<{ shortCode: string; origem: DOMRect | null } | null>(null);
  const abrirReel = useCallback((shortCode: string, origem?: Element | null) => {
    setReel({ shortCode, origem: origem?.getBoundingClientRect() ?? null });
  }, []);
  const [recentes, setRecentes] = useState<ExecucaoResumo[] | null>(null);
  const [ganchos, setGanchos] = useState<{ tipo: string; origem: DOMRect | null } | null>(null);
  const abrirGanchos = useCallback((tipo: string, origem?: Element | null) => {
    setGanchos({ tipo, origem: origem?.getBoundingClientRect() ?? null });
  }, []);
  const atualizar = useCallback(() => { api.execucoes().then(setRecentes).catch(() => setRecentes([])); }, []);
  useEffect(atualizar, [atualizar]);
  // Ao voltar para a aba do navegador, os Recentes se atualizam (uma execução pode ter terminado em outra aba).
  useWindowEvent("focus", atualizar);

  return (
    <ReelContexto.Provider value={abrirReel}>
      <GanchosContexto.Provider value={abrirGanchos}>
        <RecentesContexto.Provider value={{ recentes, atualizar }}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/perguntar" replace />} />
              <Route path="perguntar/:runId?" element={<Perguntar />} />
              <Route path="criar/:runId?" element={<Criar />} />
              <Route path="avaliar/:runId?" element={<Avaliar />} />
              <Route path="panorama" element={<Panorama />} />
              <Route path="diagnostico" element={<Diagnostico />} />
              <Route path="*" element={<Navigate to="/perguntar" replace />} />
            </Route>
          </Routes>
          {ganchos && (
            <Glance origem={ganchos.origem} onFechar={() => setGanchos(null)}
              rotulo={ganchos.tipo === TODOS ? "Todos os ganchos" : `Ganchos de ${rotuloGancho(ganchos.tipo)}`}>
              <PainelGanchos tipo={ganchos.tipo} onTipo={(tipo) => setGanchos({ ...ganchos, tipo })} aoCriar={() => setGanchos(null)} />
            </Glance>
          )}
          {reel && (
            <Glance key={reel.shortCode} origem={reel.origem} onFechar={() => setReel(null)} rotulo={`Reel ${reel.shortCode}`} largura={920}>
              <ReelGlance shortCode={reel.shortCode} fechar={() => setReel(null)} />
            </Glance>
          )}
        </RecentesContexto.Provider>
      </GanchosContexto.Provider>
    </ReelContexto.Provider>
  );
}
