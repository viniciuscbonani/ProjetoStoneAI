import { Alert, Badge, Button, Card, Loader, Stack, Table, Text } from "@mantine/core";
import { useEffect, useState } from "react";

import { api } from "../api";
import Resultado, { SeloRobustez } from "../componentes/Resultado";
import type { ExecucaoResumo, Modo, Saida } from "../tipos";

const ROTULO_MODO: Record<Modo, string> = {
  analisar: "Analisar", recomendar: "Recomendar", gerar_criativo: "Gerar criativo", avaliar: "Avaliar",
};

export default function Historico({ ativo }: { ativo: boolean }) {
  const [lista, setLista] = useState<ExecucaoResumo[] | null>(null);
  const [aberta, setAberta] = useState<Saida | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (ativo) api.execucoes().then(setLista).catch((e) => setErro(e.message));
  }, [ativo]);

  async function abrir(runId: string) {
    const l = await api.execucao(runId);
    if (l.saida) setAberta(l.saida);
  }

  if (erro) return <Alert color="red">{erro}</Alert>;
  if (!lista) return <Loader size="sm" />;
  if (aberta) {
    return (
      <Stack>
        <Button variant="subtle" w="fit-content" onClick={() => setAberta(null)}>← Voltar ao histórico</Button>
        <Resultado saida={aberta} />
      </Stack>
    );
  }

  return (
    <Card withBorder>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr><Table.Th>Quando</Table.Th><Table.Th>Modo</Table.Th><Table.Th>Pergunta</Table.Th><Table.Th>Confiança</Table.Th><Table.Th>Tempo</Table.Th></Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lista.map((e) => (
            <Table.Tr key={e.run_id} style={{ cursor: e.erro ? "default" : "pointer" }} onClick={() => !e.erro && abrir(e.run_id)}>
              <Table.Td><Text size="xs">{e.quando.replace("T", " ").slice(0, 16)}</Text></Table.Td>
              <Table.Td><Text size="sm">{ROTULO_MODO[e.mode]}</Text></Table.Td>
              <Table.Td><Text size="sm" lineClamp={1}>{e.query}</Text>{e.segment && <Text size="xs" c="dimmed">{e.segment}</Text>}</Table.Td>
              <Table.Td>{e.erro ? <Badge color="red" variant="light">erro</Badge> : e.confidence_flag && <SeloRobustez robustez={e.confidence_flag} />}</Table.Td>
              <Table.Td><Text size="xs">{Math.round(e.duracao_s)} s</Text></Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Card>
  );
}
