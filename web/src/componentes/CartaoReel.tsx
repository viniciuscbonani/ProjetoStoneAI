import { Badge, Box, Group, ScrollArea, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { useEffect, useState } from "react";

import { urlQuadro } from "../api";
import { useAbrirReel } from "../contexto";
import { compacto, pct, rotuloValor } from "../formato";
import type { ReferencePost } from "../tipos";

// Ordem dos quadros salvos de cada Reel (processar_midia.py): o primeiro é a capa.
const QUADROS = ["gancho_0s", "gancho_1s", "gancho_2s", "gancho_3s", "meio_40", "meio_60", "final_2s", "final_0s"];

// Capa do Reel: se o primeiro quadro faltar, tenta os seguintes; sem nenhum, fica só o fundo cinza do .quadro.
export function Capa({ codigo, alt = "" }: { codigo: string; alt?: string }) {
  const [i, setI] = useState(0);
  useEffect(() => setI(0), [codigo]);
  if (i >= QUADROS.length) return null;
  return <img src={urlQuadro(codigo, QUADROS[i])} alt={alt} loading="lazy" onError={() => setI(i + 1)} />;
}

// Capa 9:16 do Reel com o número da citação, o perfil e a taxa de engajamento.
export default function CartaoReel({ r, numero, largura = 150 }: { r: ReferencePost; numero?: number; largura?: number }) {
  const abrirReel = useAbrirReel();
  return (
    <UnstyledButton onClick={() => abrirReel(r.shortCode)} w={largura} style={{ flexShrink: 0 }}>
      <div className="quadro clicavel">
        <Capa codigo={r.shortCode} alt={`Primeiro quadro do Reel de @${r.perfil}`} />
        {numero && <Badge className="quadro-canto" size="sm" circle color="dark" variant="filled">{numero}</Badge>}
        <div className="quadro-rodape">
          <Text size="xs" fw={600} truncate>@{r.perfil}</Text>
          <Text size="10px" opacity={0.85}>{compacto(r.seguidores)} seguidores · {Math.round(r.duracao_s)} s</Text>
        </div>
      </div>
      <Group gap={6} mt={8} wrap="nowrap">
        <Tooltip label="Taxa de engajamento: (curtidas + comentários) ÷ seguidores">
          <Text size="xs" fw={600} style={{ cursor: "help" }}>{pct(r.taxa_engajamento, 1)}</Text>
        </Tooltip>
        <Text size="xs" c="dimmed" truncate>{rotuloValor(r.categorias.formato_video)}</Text>
      </Group>
      <Text size="xs" mt={4} lineClamp={2} c="dimmed">“{r.hook_texto}”</Text>
    </UnstyledButton>
  );
}

// Fileira horizontal de Reels de referência (as "fontes" da resposta).
export function FaixaReels({ refs, numeros }: { refs: ReferencePost[]; numeros?: Map<string, number> }) {
  return (
    <ScrollArea type="hover" offsetScrollbars scrollbarSize={6}>
      <Group gap="md" wrap="nowrap" align="flex-start" pb={4}>
        {refs.map((r) => <CartaoReel key={r.shortCode} r={r} numero={numeros?.get(r.shortCode)} />)}
      </Group>
    </ScrollArea>
  );
}

// Miniatura de um Reel citado só pelo código (inspirações de criativo, exemplos de um ponto da avaliação).
export function MiniReel({ codigo, largura = 52, refs = [] }: { codigo: string; largura?: number; refs?: ReferencePost[] }) {
  const abrirReel = useAbrirReel();
  const r = refs.find((x) => x.shortCode === codigo);
  return (
    <Tooltip label={r ? `@${r.perfil} · ${pct(r.taxa_engajamento, 1)} de engajamento` : `Reel ${codigo}`}>
      <UnstyledButton onClick={() => abrirReel(codigo)} aria-label={`Abrir o Reel ${codigo}`}>
        <Box w={largura} className="quadro clicavel" style={{ borderRadius: "var(--mantine-radius-sm)" }}>
          <Capa codigo={codigo} />
        </Box>
      </UnstyledButton>
    </Tooltip>
  );
}
