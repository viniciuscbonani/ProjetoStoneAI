import { Anchor, Box, Button, Group, Loader, Paper, SimpleGrid, Spoiler, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconBrandInstagram } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { api, urlQuadro } from "../api";
import { useAbrirGanchos } from "../contexto";
import { compacto, inteiro, pct, rotuloValor } from "../formato";
import { rotuloGancho } from "../telas/Ganchos";
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

// Conteúdo do glance de um Reel: à esquerda o quadro grande e os 8 quadros para trocar; à direita o gancho, as
// métricas, a anotação, a fala e a legenda.
export default function ReelGlance({ shortCode, fechar }: { shortCode: string; fechar: () => void }) {
  const [reel, setReel] = useState<ReelDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [quadro, setQuadro] = useState<string | null>(null);
  const abrirGanchos = useAbrirGanchos();

  useEffect(() => {
    setReel(null);
    setErro(null);
    api.reel(shortCode).then((r) => { setReel(r); setQuadro(r.quadros[0] ?? null); }).catch((e) => setErro(e.message));
  }, [shortCode]);

  if (erro) return <Box p={40}><Text c="red">{erro}</Text></Box>;
  if (!reel) return <Box p={40}><Loader size="sm" /></Box>;

  return (
    <Box px={{ base: "md", sm: 40 }} pt={{ base: 56, sm: 40 }} pb={48}
      style={{ display: "flex", gap: 40, alignItems: "flex-start", flexWrap: "wrap" }}>
      <Box w={{ base: "100%", xs: 280 }} style={{ position: "sticky", top: 0, flexShrink: 0 }}>
        <Box className="quadro" maw={280} mx="auto">
          {quadro && <img src={urlQuadro(reel.shortCode, quadro)} alt={`Quadro em ${NOMES_QUADROS[quadro]}`} />}
        </Box>
        <SimpleGrid cols={4} spacing={6} mt="sm" maw={280} mx="auto">
          {reel.quadros.map((q) => (
            <UnstyledButton key={q} onClick={() => setQuadro(q)} aria-label={`Ver o quadro em ${NOMES_QUADROS[q]}`}>
              <div className="quadro" style={{ borderRadius: "var(--mantine-radius-sm)", outline: q === quadro ? "2px solid var(--mantine-color-text)" : "none", outlineOffset: 1 }}>
                <img src={urlQuadro(reel.shortCode, q)} alt="" loading="lazy" />
              </div>
              <Text size="10px" c="dimmed" ta="center" mt={2}>{NOMES_QUADROS[q]}</Text>
            </UnstyledButton>
          ))}
        </SimpleGrid>
      </Box>

      <Stack gap="lg" style={{ flex: 1, minWidth: 260 }}>
        <div>
          <Text fw={600} size="lg">@{reel.perfil}</Text>
          <Text size="sm" c="dimmed">{reel.faixa} · {compacto(reel.seguidores)} seguidores · {reel.publicado_em}</Text>
        </div>

        <div>
          <Text size="sm" c="dimmed" mb={4}>
            {reel.grupo === "top" ? "Top 10% de engajamento" : reel.grupo === "impulsostone" ? "Reel da @impulsostone" : "Amostra comum"} · {Math.round(reel.duracao_s)} s · gancho
          </Text>
          <Text fz={22} fw={500} lh={1.35}>“{reel.hook_texto}”</Text>
          {reel.tipo_hook !== "nenhum" && (
            <Anchor component="button" size="sm" mt={6} c="var(--verde-texto)"
              onClick={(e) => { abrirGanchos(String(reel.tipo_hook), e.currentTarget); fechar(); }}>
              Outros ganchos de {rotuloGancho(String(reel.tipo_hook))} do top
            </Anchor>
          )}
        </div>

        <SimpleGrid cols={2} spacing="xs">
          <Metrica rotulo="Taxa de engajamento" valor={pct(reel.taxa_engajamento, 1)} />
          <Metrica rotulo="Visualizações" valor={inteiro(reel.visualizacoes)} />
          <Metrica rotulo="Curtidas" valor={inteiro(reel.curtidas)} />
          <Metrica rotulo="Comentários" valor={inteiro(reel.comentarios)} />
        </SimpleGrid>

        {reel.transcricao && (
          <div>
            <Text size="sm" fw={600} mb={4}>Fala do vídeo</Text>
            <Spoiler maxHeight={96} showLabel="Ver mais" hideLabel="Ver menos">
              <Text size="sm" c="dimmed">{reel.transcricao}</Text>
            </Spoiler>
          </div>
        )}

        <div>
          <Text size="sm" fw={600} mb={4}>Legenda</Text>
          <Spoiler maxHeight={96} showLabel="Ver mais" hideLabel="Ver menos">
            <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>{reel.legenda || "(sem legenda)"}</Text>
          </Spoiler>
        </div>

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

        <Button component="a" href={reel.url} target="_blank" variant="default" leftSection={<IconBrandInstagram size={17} />}
          style={{ alignSelf: "flex-start" }}>
          Abrir no Instagram
        </Button>
      </Stack>
    </Box>
  );
}
