import {
  Box, Button, Drawer, Group, Loader, Paper, ScrollArea, SimpleGrid, Spoiler, Stack, Text,
} from "@mantine/core";
import { IconBrandInstagram } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { api, urlQuadro } from "../api";
import { compacto, inteiro, pct, rotuloValor } from "../formato";
import type { ReelDetalhe } from "../tipos";

const CATEGORIAS: [string, string][] = [
  ["formato_video", "Formato"], ["duracao_faixa", "Duração"], ["tipo_hook", "Gancho"], ["hook_visual", "Gancho visual"],
  ["tema_principal", "Tema"], ["pilar_impulso", "Pilar"], ["segmento_publico", "Segmento"], ["tem_rosto", "Rosto em cena"],
  ["tem_cta", "CTA"], ["tipo_cta", "Tipo de CTA"], ["abordagem", "Abordagem"], ["tom", "Tom"],
];
const NOMES_QUADROS: Record<string, string> = {
  gancho_0s: "0 s", gancho_1s: "1 s", gancho_2s: "2 s", gancho_3s: "3 s", meio_40: "40%", meio_60: "60%", final_2s: "fim −2 s", final_0s: "fim",
};

function Metrica({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <Paper p="sm" bg="var(--suave)" withBorder={false}>
      <Text size="xs" c="dimmed">{rotulo}</Text>
      <Text fw={600}>{valor}</Text>
    </Paper>
  );
}

export default function ReelDrawer({ shortCode, onClose }: { shortCode: string | null; onClose: () => void }) {
  const [reel, setReel] = useState<ReelDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setReel(null);
    setErro(null);
    if (shortCode) api.reel(shortCode).then(setReel).catch((e) => setErro(e.message));
  }, [shortCode]);

  return (
    <Drawer
      opened={!!shortCode}
      onClose={onClose}
      position="right"
      size={520}
      title={reel ? (
        <div>
          <Text fw={600}>@{reel.perfil}</Text>
          <Text size="xs" c="dimmed">{reel.faixa} · {compacto(reel.seguidores)} seguidores · {reel.publicado_em}</Text>
        </div>
      ) : shortCode}
    >
      {!reel && !erro && <Loader size="sm" />}
      {erro && <Text c="red">{erro}</Text>}
      {reel && (
        <Stack gap="lg">
          <div>
            <Text size="sm" c="dimmed" mb={4}>
              {reel.grupo === "top" ? "Top 10% de engajamento" : "Grupo de controle"} · {Math.round(reel.duracao_s)} s · gancho
            </Text>
            <Text fz={18} fw={500} lh={1.4}>“{reel.hook_texto}”</Text>
          </div>

          <div>
            <Text size="sm" fw={600} mb={8}>Quadros do vídeo</Text>
            <ScrollArea type="auto" offsetScrollbars scrollbarSize={6}>
              <Group gap={8} wrap="nowrap" pb={4}>
                {reel.quadros.map((q) => (
                  <Box key={q} w={104} style={{ flexShrink: 0 }}>
                    <div className="quadro" style={{ borderRadius: "var(--mantine-radius-sm)" }}>
                      <img src={urlQuadro(reel.shortCode, q)} alt={`Quadro em ${NOMES_QUADROS[q]}`} loading="lazy" />
                    </div>
                    <Text size="xs" c="dimmed" ta="center" mt={2}>{NOMES_QUADROS[q]}</Text>
                  </Box>
                ))}
              </Group>
            </ScrollArea>
          </div>

          <SimpleGrid cols={2} spacing="xs">
            <Metrica rotulo="Taxa de engajamento" valor={pct(reel.taxa_engajamento, 1)} />
            <Metrica rotulo="Visualizações" valor={inteiro(reel.visualizacoes)} />
            <Metrica rotulo="Curtidas" valor={inteiro(reel.curtidas)} />
            <Metrica rotulo="Comentários" valor={inteiro(reel.comentarios)} />
          </SimpleGrid>

          <div>
            <Text size="sm" fw={600} mb={8}>Como o Reel foi anotado</Text>
            <Paper className="lista" style={{ overflow: "hidden" }}>
              {CATEGORIAS.map(([campo, nome]) => (
                <Group key={campo} justify="space-between" px="sm" py={7} wrap="nowrap">
                  <Text size="sm" c="dimmed">{nome}</Text>
                  <Text size="sm" fw={500} ta="right">{rotuloValor(reel[campo])}</Text>
                </Group>
              ))}
            </Paper>
          </div>

          {reel.elementos_top5.length > 0 && (
            <div>
              <Text size="sm" fw={600} mb={6}>Elementos de destaque</Text>
              <Text size="sm" c="dimmed">{reel.elementos_top5.join(" · ")}</Text>
            </div>
          )}

          <div>
            <Text size="sm" fw={600} mb={4}>Legenda</Text>
            <Spoiler maxHeight={96} showLabel="Ver mais" hideLabel="Ver menos">
              <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>{reel.legenda || "(sem legenda)"}</Text>
            </Spoiler>
          </div>

          <Button component="a" href={reel.url} target="_blank" variant="default" leftSection={<IconBrandInstagram size={17} />}>
            Abrir no Instagram
          </Button>
        </Stack>
      )}
    </Drawer>
  );
}
