import "@mantine/core/styles.css";
import "@mantine/dropzone/styles.css";
import "./estilos.css";

import { createTheme, MantineProvider, type CSSVariablesResolver, type MantineColorsTuple } from "@mantine/core";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import App from "./App";

// Cores do design system Odin de stone.com.br. Verde da marca (escala "stone-green", a mesma do logo): o tom 6 é
// #00DB00, com texto escuro por cima (autoContrast), como nos botões do site; texto verde usa o tom 8 (#005700).
const stone: MantineColorsTuple = [
  "#e6fde2", "#c9f8c4", "#b2f1ac", "#9ae694", "#7cd676", "#43c33c", "#00db00", "#00c700", "#005700", "#003800",
];
// Cinzas "sage" do site (puxados para o verde) no lugar dos cinzas azulados do Mantine.
const gray: MantineColorsTuple = [
  "#f6f8f7", "#eef1f0", "#e7e9e9", "#d7dad9", "#cacecc", "#b8bcba", "#7c8381", "#4c5250", "#343b38", "#1b221f",
];
// Escuro com o mesmo matiz (o 0 é o texto no tema escuro).
const dark: MantineColorsTuple = [
  "#d7dad9", "#b8bcba", "#868d8b", "#5f6664", "#3c4340", "#2c322f", "#212724", "#191e1c", "#131715", "#0d100f",
];

// Variantes "light" e "outline" com texto #005700 sobre o verde translúcido do site, e não verde-neon sobre branco.
const resolverVariaveis: CSSVariablesResolver = () => ({
  variables: {},
  light: {
    "--mantine-color-stone-text": "#005700",
    "--mantine-color-stone-light": "rgba(27, 235, 0, 0.12)",
    "--mantine-color-stone-light-hover": "rgba(27, 235, 0, 0.2)",
    "--mantine-color-stone-light-color": "#005700",
    "--mantine-color-stone-outline": "#005700",
    "--mantine-color-stone-outline-hover": "rgba(27, 235, 0, 0.12)",
  },
  dark: {
    "--mantine-color-stone-text": "#7cd676",
    "--mantine-color-stone-light": "rgba(0, 219, 0, 0.14)",
    "--mantine-color-stone-light-hover": "rgba(0, 219, 0, 0.22)",
    "--mantine-color-stone-light-color": "#7cd676",
  },
});

const tema = createTheme({
  primaryColor: "stone",
  primaryShade: { light: 6, dark: 6 },
  autoContrast: true,
  colors: { stone, gray, dark },
  black: "#1b221f",
  fontFamily: "Geist, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  defaultRadius: "md",
  headings: { fontWeight: "600" },
  components: {
    // Sem borda por padrão: o espaço agrupa; borda só onde precisa de um limite firme (campos, listas).
    Paper: { defaultProps: { radius: "lg" } },
    Card: { defaultProps: { radius: "lg" } },
    Button: { defaultProps: { radius: "md" } },
    Badge: { defaultProps: { radius: "sm" } },
    Tooltip: { defaultProps: { multiline: true, maw: 300, withArrow: true } },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MantineProvider theme={tema} cssVariablesResolver={resolverVariaveis} defaultColorScheme="light">
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </MantineProvider>
  </StrictMode>,
);
