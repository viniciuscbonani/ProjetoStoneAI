import { AppShell, Badge, Container, Group, Tabs, Text, Title } from "@mantine/core";
import { createContext, useContext, useState } from "react";

import Historico from "./telas/Historico";
import Panorama from "./telas/Panorama";
import Perguntar from "./telas/Perguntar";
import ReelDrawer from "./componentes/ReelDrawer";

// Qualquer componente abre a gaveta de um Reel com abrirReel(shortCode).
const ReelContexto = createContext<(shortCode: string) => void>(() => {});
export const useAbrirReel = () => useContext(ReelContexto);

export default function App() {
  const [reel, setReel] = useState<string | null>(null);
  const [aba, setAba] = useState<string | null>("perguntar");

  return (
    <ReelContexto.Provider value={setReel}>
      <AppShell header={{ height: 64 }} padding="md">
        <AppShell.Header>
          <Container size="lg" h="100%">
            <Group h="100%" justify="space-between">
              <Group gap="sm">
                <Title order={3} c="stone.7">Impulso Stone</Title>
                <Text c="dimmed" size="sm">Agente de conteúdo para MPEs</Text>
              </Group>
              <Badge variant="light" color="gray">944 Reels analisados · top 10% × controle</Badge>
            </Group>
          </Container>
        </AppShell.Header>
        <AppShell.Main bg="gray.0">
          <Container size="lg" py="md">
            <Tabs value={aba} onChange={setAba} keepMounted>
              <Tabs.List mb="lg">
                <Tabs.Tab value="perguntar">Perguntar</Tabs.Tab>
                <Tabs.Tab value="panorama">Panorama</Tabs.Tab>
                <Tabs.Tab value="historico">Histórico</Tabs.Tab>
              </Tabs.List>
              <Tabs.Panel value="perguntar"><Perguntar /></Tabs.Panel>
              <Tabs.Panel value="panorama"><Panorama /></Tabs.Panel>
              <Tabs.Panel value="historico"><Historico ativo={aba === "historico"} /></Tabs.Panel>
            </Tabs>
          </Container>
        </AppShell.Main>
      </AppShell>
      <ReelDrawer shortCode={reel} onClose={() => setReel(null)} />
    </ReelContexto.Provider>
  );
}
