import { useWindowEvent } from "@mantine/hooks";
import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router";

import { api } from "./api";
import Layout from "./componentes/Layout";
import ReelDrawer from "./componentes/ReelDrawer";
import { RecentesContexto, ReelContexto } from "./contexto";
import Avaliar from "./telas/Avaliar";
import Criar from "./telas/Criar";
import Panorama from "./telas/Panorama";
import Perguntar from "./telas/Perguntar";
import type { ExecucaoResumo } from "./tipos";

export default function App() {
  const [reel, setReel] = useState<string | null>(null);
  const [recentes, setRecentes] = useState<ExecucaoResumo[] | null>(null);
  const atualizar = useCallback(() => { api.execucoes().then(setRecentes).catch(() => setRecentes([])); }, []);
  useEffect(atualizar, [atualizar]);
  // Ao voltar para a aba do navegador, os Recentes se atualizam (uma execução pode ter terminado em outra aba).
  useWindowEvent("focus", atualizar);

  return (
    <ReelContexto.Provider value={setReel}>
      <RecentesContexto.Provider value={{ recentes, atualizar }}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/perguntar" replace />} />
            <Route path="perguntar/:runId?" element={<Perguntar />} />
            <Route path="criar/:runId?" element={<Criar />} />
            <Route path="avaliar/:runId?" element={<Avaliar />} />
            <Route path="panorama" element={<Panorama />} />
            <Route path="*" element={<Navigate to="/perguntar" replace />} />
          </Route>
        </Routes>
        <ReelDrawer shortCode={reel} onClose={() => setReel(null)} />
      </RecentesContexto.Provider>
    </ReelContexto.Provider>
  );
}
