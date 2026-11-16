import { Alert, Anchor, Card, Group, Loader, SegmentedControl, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { CartaoAchado } from "../componentes/Resultado";
import { inteiro } from "../formato";
import type { Panorama as TPanorama } from "../tipos";

const ORDEM = { robusto: 0, fragil: 1, insuficiente: 2 };

export default function Panorama() {
  const [dados, setDados] = useState<TPanorama | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [filtro, setFiltro] = useState("relevantes");

  useEffect(() => { api.panorama().then(setDados).catch((e) => setErro(e.message)); }, []);

  const achados = useMemo(() => {
    if (!dados) return [];
    return dados.achados
      .filter((a) => a.dif_pp !== 0 && (filtro === "todos" || (a.robustez !== "insuficiente" && Math.abs(a.dif_pp) >= 3)))
      .sort((a, b) => ORDEM[a.robustez] - ORDEM[b.robustez] || Math.abs(b.dif_pp) - Math.abs(a.dif_pp));
  }, [dados, filtro]);

  if (erro) return <Alert color="red" title="Não foi possível carregar o panorama">{erro}</Alert>;
  if (!dados) return <Loader size="sm" />;

  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <Card withBorder><Text size="xs" c="dimmed">Reels analisados</Text><Title order={2}>{inteiro(dados.totais.reels)}</Title></Card>
        <Card withBorder><Text size="xs" c="dimmed">No top 10% de engajamento</Text><Title order={2}>{inteiro(dados.totais.top)}</Title></Card>
        <Card withBorder><Text size="xs" c="dimmed">Perfis</Text><Title order={2}>{inteiro(dados.totais.perfis)}</Title></Card>
      </SimpleGrid>

      <div>
        <Group justify="space-between" mb="xs">
          <div>
            <Title order={4}>O que diferencia o top do controle</Title>
            <Text size="sm" c="dimmed">Frequência de cada característica nos Reels de alto engajamento × controle sorteado.</Text>
          </div>
          <SegmentedControl value={filtro} onChange={setFiltro}
            data={[{ value: "relevantes", label: "Diferenças relevantes" }, { value: "todos", label: "Todas" }]} />
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
          {achados.map((a) => <CartaoAchado key={a.campo + a.valor} a={a} />)}
        </SimpleGrid>
      </div>

      <Card withBorder>
        <Title order={4} mb="xs">Perfis em destaque</Title>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr><Table.Th>Perfil</Table.Th><Table.Th>Faixa</Table.Th><Table.Th>Reels no top</Table.Th><Table.Th>Tema</Table.Th><Table.Th>Formato</Table.Th></Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {dados.perfis.map((p) => (
              <Table.Tr key={p.perfil}>
                <Table.Td><Anchor href={`https://www.instagram.com/${p.perfil}/`} target="_blank">@{p.perfil}</Anchor></Table.Td>
                <Table.Td>{p.faixa}</Table.Td>
                <Table.Td>{p.n_top} de {p.n_amostra}</Table.Td>
                <Table.Td>{p.tema_predominante.replaceAll("_", " ")}</Table.Td>
                <Table.Td>{p.formato_predominante.replaceAll("_", " ")}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
    </Stack>
  );
}
