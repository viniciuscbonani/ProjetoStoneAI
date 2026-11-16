import { Anchor, Badge, Card, Group, Image, Text } from "@mantine/core";

import { useAbrirReel } from "../App";
import { urlQuadro } from "../api";
import { compacto, pct, rotuloValor } from "../formato";
import type { ReferencePost } from "../tipos";

export default function CartaoReel({ r }: { r: ReferencePost }) {
  const abrirReel = useAbrirReel();
  return (
    <Card withBorder padding="sm" style={{ cursor: "pointer" }} onClick={() => abrirReel(r.shortCode)}>
      <Card.Section>
        <Image src={urlQuadro(r.shortCode)} h={220} fit="cover" alt={`Primeiro quadro do Reel de @${r.perfil}`} />
      </Card.Section>
      <Group justify="space-between" mt="xs" wrap="nowrap">
        <Text fw={600} size="sm" truncate>@{r.perfil}</Text>
        <Badge size="sm" variant="light" color="stone">{pct(r.taxa_engajamento, 1)}</Badge>
      </Group>
      <Text size="xs" c="dimmed">
        {r.faixa} · {compacto(r.seguidores)} seguidores · {Math.round(r.duracao_s)} s · {compacto(r.visualizacoes)} views
      </Text>
      <Text size="sm" mt={6} lineClamp={2}>“{r.hook_texto}”</Text>
      <Group gap={4} mt={6}>
        <Badge size="xs" variant="outline" color="gray">{rotuloValor(r.categorias.formato_video)}</Badge>
        <Badge size="xs" variant="outline" color="gray">gancho {rotuloValor(r.categorias.tipo_hook)}</Badge>
      </Group>
      <Anchor href={r.url} target="_blank" size="xs" mt={6} onClick={(e) => e.stopPropagation()}>
        Ver no Instagram
      </Anchor>
    </Card>
  );
}
