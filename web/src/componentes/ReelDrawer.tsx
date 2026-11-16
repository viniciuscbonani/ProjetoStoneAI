import { Anchor, Badge, Drawer, Group, Image, Loader, SimpleGrid, Stack, Table, Text } from "@mantine/core";
import { useEffect, useState } from "react";

import { api, urlQuadro } from "../api";
import { inteiro, pct, rotuloValor } from "../formato";
import type { ReelDetalhe } from "../tipos";

const CATEGORIAS: [string, string][] = [
  ["formato_video", "Formato"], ["duracao_faixa", "Duração"], ["tipo_hook", "Gancho"], ["hook_visual", "Gancho visual"],
  ["tema_principal", "Tema"], ["pilar_impulso", "Pilar"], ["segmento_publico", "Segmento"], ["tem_rosto", "Rosto em cena"],
  ["tem_cta", "CTA"], ["tipo_cta", "Tipo de CTA"], ["abordagem", "Abordagem"], ["tom", "Tom"],
];
const NOMES_QUADROS: Record<string, string> = {
  gancho_0s: "0 s", gancho_1s: "1 s", gancho_2s: "2 s", gancho_3s: "3 s", meio_40: "40%", meio_60: "60%", final_2s: "fim −2 s", final_0s: "fim",
};

export default function ReelDrawer({ shortCode, onClose }: { shortCode: string | null; onClose: () => void }) {
  const [reel, setReel] = useState<ReelDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setReel(null);
    setErro(null);
    if (shortCode) api.reel(shortCode).then(setReel).catch((e) => setErro(e.message));
  }, [shortCode]);

  return (
    <Drawer opened={!!shortCode} onClose={onClose} position="right" size="lg" title={reel ? `@${reel.perfil}` : shortCode}>
      {!reel && !erro && <Loader size="sm" />}
      {erro && <Text c="red">{erro}</Text>}
      {reel && (
        <Stack>
          <Group gap="xs">
            <Badge color={reel.grupo === "top" ? "stone" : "gray"}>{reel.grupo === "top" ? "Top 10%" : "Controle"}</Badge>
            <Badge variant="light" color="gray">{reel.faixa}</Badge>
            <Anchor href={reel.url} target="_blank" size="sm">Abrir no Instagram</Anchor>
          </Group>
          <Text fw={600}>“{reel.hook_texto}”</Text>
          <SimpleGrid cols={4} spacing={6}>
            {reel.quadros.map((q) => (
              <div key={q}>
                <Image src={urlQuadro(reel.shortCode, q)} radius="sm" alt={`Quadro em ${NOMES_QUADROS[q]}`} />
                <Text size="xs" c="dimmed" ta="center">{NOMES_QUADROS[q]}</Text>
              </div>
            ))}
          </SimpleGrid>
          <Table withRowBorders={false} verticalSpacing={2}>
            <Table.Tbody>
              <Table.Tr><Table.Td c="dimmed">Taxa de engajamento</Table.Td><Table.Td>{pct(reel.taxa_engajamento, 1)}</Table.Td></Table.Tr>
              <Table.Tr><Table.Td c="dimmed">Curtidas · comentários</Table.Td><Table.Td>{inteiro(reel.curtidas)} · {inteiro(reel.comentarios)}</Table.Td></Table.Tr>
              <Table.Tr><Table.Td c="dimmed">Visualizações</Table.Td><Table.Td>{inteiro(reel.visualizacoes)}</Table.Td></Table.Tr>
              <Table.Tr><Table.Td c="dimmed">Seguidores</Table.Td><Table.Td>{inteiro(reel.seguidores)}</Table.Td></Table.Tr>
              <Table.Tr><Table.Td c="dimmed">Duração · publicado em</Table.Td><Table.Td>{Math.round(reel.duracao_s)} s · {reel.publicado_em}</Table.Td></Table.Tr>
              {CATEGORIAS.map(([campo, nome]) => (
                <Table.Tr key={campo}><Table.Td c="dimmed">{nome}</Table.Td><Table.Td>{rotuloValor(reel[campo])}</Table.Td></Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <div>
            <Text size="sm" fw={600}>Elementos de destaque</Text>
            <Group gap={4} mt={4}>{reel.elementos_top5.map((e) => <Badge key={e} variant="outline" color="gray">{e}</Badge>)}</Group>
          </div>
          <div>
            <Text size="sm" fw={600}>Legenda</Text>
            <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>{reel.legenda || "(sem legenda)"}</Text>
          </div>
        </Stack>
      )}
    </Drawer>
  );
}
