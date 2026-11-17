import { Text, Tooltip } from "@mantine/core";

import { CONFIANCA, ROBUSTEZ } from "../formato";
import type { Confianca, Robustez } from "../tipos";

// Selos em texto, sem pílula colorida: só "Diferença clara" leva o verde; o resto é texto comum ou apagado.
const COR: Record<Robustez, string | undefined> = {
  robusto: "var(--verde-texto)", fragil: undefined, sem_diferenca: "dimmed", insuficiente: "dimmed",
};

export function SeloRobustez({ robustez, size = "xs" }: { robustez: Robustez; size?: string }) {
  const r = ROBUSTEZ[robustez];
  return (
    <Tooltip label={r.ajuda}>
      <Text span size={size} fw={500} c={COR[robustez]} style={{ whiteSpace: "nowrap", cursor: "help" }}>{r.rotulo}</Text>
    </Tooltip>
  );
}

export function SeloConfianca({ confianca }: { confianca: Confianca }) {
  const c = CONFIANCA[confianca];
  return (
    <Tooltip label={c.ajuda}>
      <Text span inherit style={{ cursor: "help", textDecoration: "underline dotted", textUnderlineOffset: 3 }}>
        confiança {c.rotulo.toLowerCase()}
      </Text>
    </Tooltip>
  );
}
