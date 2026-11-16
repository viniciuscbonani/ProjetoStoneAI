import "@mantine/core/styles.css";

import { createTheme, MantineProvider, type MantineColorsTuple } from "@mantine/core";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

// Verde Stone (#00A868) no tom 7, com a escala clara e escura em volta.
const stone: MantineColorsTuple = [
  "#e3fbf0", "#cdf3e1", "#9ce6c2", "#67d8a1", "#3ccd85", "#21c673", "#0bb868", "#00a868", "#00915a", "#007a4b",
];

const tema = createTheme({
  primaryColor: "stone",
  primaryShade: 7,
  colors: { stone },
  fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  defaultRadius: "md",
  headings: { fontWeight: "700" },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MantineProvider theme={tema} defaultColorScheme="light">
      <App />
    </MantineProvider>
  </StrictMode>,
);
