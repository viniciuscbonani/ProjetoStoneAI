import { Box, Button, CloseButton, Group, Loader, Stack, Text, TextInput, Title, Tooltip, UnstyledButton } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconArrowsSort, IconSearch, IconSparkles } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { api } from "../api";
import { ListaValores } from "../componentes/Achados";
import { Erro, Escolha } from "../componentes/Comum";
import { SeloRobustez } from "../componentes/Selos";
import { useAbrirReel } from "../contexto";
import { inteiro, pct } from "../formato";
import type { Achado, ReelBusca, ResultadoBusca } from "../tipos";

// O que cada tipo de gancho faz.
export const TIPOS_GANCHO: { valor: string; rotulo: string; ajuda: string }[] = [
  { valor: "curiosidade", rotulo: "Curiosidade", ajuda: "abre uma lacuna que só o vídeo fecha" },
  { valor: "promessa", rotulo: "Promessa", ajuda: "diz logo o que a pessoa vai ganhar assistindo" },
  { valor: "dor", rotulo: "Dor", ajuda: "nomeia um problema de quem assiste" },
  { valor: "pergunta", rotulo: "Pergunta", ajuda: "faz uma pergunta direta a quem assiste" },
  { valor: "numero", rotulo: "Número", ajuda: "abre com um número, um valor ou uma lista" },
  { valor: "polemica", rotulo: "Polêmica", ajuda: "contraria o que todo mundo diz" },
  { valor: "nenhum", rotulo: "Sem gancho claro", ajuda: "começa sem nada que prenda nos primeiros segundos" },
];
const GRUPOS = [
  { value: "top", label: "Só o top 10%" },
  { value: "todos", label: "Top e amostra comum", descricao: "a amostra comum é um sorteio do que os perfis publicam" },
];
const ORDENS = [
  { value: "taxa", label: "Maior engajamento" },
  { value: "visualizacoes", label: "Mais visualizações" },
  { value: "recentes", label: "Mais recentes" },
];
const POR_PAGINA = 40;

// "todos": busca em todos os tipos de uma vez.
export const TODOS = "todos";
const infoTipo = (tipo: string) => TIPOS_GANCHO.find((t) => t.valor === tipo) ?? TIPOS_GANCHO[0];
export const rotuloGancho = (tipo: string) => infoTipo(tipo).rotulo.toLowerCase();

// Os achados de tipo de gancho (top x controle) não mudam durante a sessão: uma busca só, compartilhada.
let achadosGancho: Promise<Achado[]> | null = null;
const carregarAchados = () =>
  (achadosGancho ??= api.panorama("", []).then((p) => p.achados.filter((a) => a.campo === "tipo_hook")));

// Mesma normalização da API (agente/busca.py): sem acento e em minúsculas, letra a letra (por ponto de código, para
// que um emoji conte como uma letra), para achar o termo buscado no texto original e marcá-lo.
const letra = (c: string) => {
  const b = c.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  return b.length === 1 && b.trim() ? b : " ";
};
const normalizar = (texto: string) => [...texto].map(letra).join("");

function Marcado({ texto, termos }: { texto: string; termos: string[] }) {
  const letras = [...texto];
  const norm = letras.map(letra).join("");
  if (!termos.length) return <>{texto}</>;
  const marcas = new Array(letras.length).fill(false);
  for (const t of termos) {
    for (let i = norm.indexOf(t); i >= 0; i = norm.indexOf(t, i + t.length)) marcas.fill(true, i, i + t.length);
  }
  const partes: { s: string; m: boolean }[] = [];
  letras.forEach((c, i) => {
    const ultima = partes[partes.length - 1];
    if (ultima && ultima.m === marcas[i]) ultima.s += c;
    else partes.push({ s: c, m: marcas[i] });
  });
  return <>{partes.map((p, i) => (p.m ? <mark key={i} className="marca">{p.s}</mark> : <span key={i}>{p.s}</span>))}</>;
}

function Linha({ r, termos, comTipo }: { r: ReelBusca; termos: string[]; comTipo: boolean }) {
  const abrirReel = useAbrirReel();
  // O trecho da fala ou da legenda só aparece quando a palavra buscada não está na própria frase.
  const naFrase = termos.length > 0 && termos.every((t) => normalizar(r.hook_texto).includes(t));
  return (
    <UnstyledButton onClick={(e) => abrirReel(r.shortCode, e.currentTarget)} className="linha-gancho">
      <Text fz={17} fw={500} lh={1.4}>“<Marcado texto={r.hook_texto} termos={termos} />”</Text>
      <Text size="xs" c="dimmed" mt={6}>
        {comTipo && `gancho ${rotuloGancho(String(r.categorias.tipo_hook))} · `}@{r.perfil} · {r.faixa} · {Math.round(r.duracao_s)} s · {String(r.categorias.formato_video).replaceAll("_", " ")} ·{" "}
        <Tooltip label={r.oculta_parcial ? "Perfil que oculta parte das curtidas: a taxa pode estar distorcida" : "(curtidas + comentários) ÷ seguidores"}>
          <span style={{ cursor: "help" }}>{pct(r.taxa_engajamento, 1)} de engajamento{r.oculta_parcial ? "*" : ""}</span>
        </Tooltip>
        {r.grupo === "controle" && " · amostra comum"}
      </Text>
      {r.trecho && !naFrase && (
        <Text size="sm" c="dimmed" mt={6} lineClamp={2}><Marcado texto={r.trecho} termos={termos} /></Text>
      )}
    </UnstyledButton>
  );
}

// Banco de ganchos: os tipos ordenados pelo quanto aparecem no top (fixos ao rolar) e as frases reais do tipo escolhido,
// ou de todos. Aberto num glance do Perguntar, do Panorama e do Reel.
export function PainelGanchos({ tipo, onTipo, aoCriar }: { tipo: string; onTipo: (t: string) => void; aoCriar?: () => void }) {
  const navigate = useNavigate();
  const [achados, setAchados] = useState<Achado[] | null>(null);
  const [res, setRes] = useState<ResultadoBusca | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [mais, setMais] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [q] = useDebouncedValue(texto.trim(), 300);
  const [grupo, setGrupo] = useState("top");
  const [ordem, setOrdem] = useState("taxa");
  const todos = tipo === TODOS;
  const info = infoTipo(tipo);

  useEffect(() => { carregarAchados().then(setAchados).catch((e) => setErro(e.message)); }, []);

  const consulta = new URLSearchParams({ ordem, limite: String(POR_PAGINA) });
  if (!todos) consulta.set("f", `tipo_hook:${info.valor}`);
  if (q) consulta.set("q", q);
  if (grupo === "top") consulta.set("grupo", "top");
  const chave = consulta.toString();

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    api.busca(consulta)
      .then((r) => { if (ativo) { setRes(r); setErro(null); } })
      .catch((e) => ativo && setErro(e.message))
      .finally(() => ativo && setCarregando(false));
    return () => { ativo = false; };
  }, [chave]); // eslint-disable-line react-hooks/exhaustive-deps

  function carregarMais() {
    if (!res) return;
    setMais(true);
    api.busca(consulta, res.itens.length)
      .then((r) => setRes({ ...res, itens: [...res.itens, ...r.itens] }))
      .catch((e) => setErro(e.message))
      .finally(() => setMais(false));
  }

  const achado = todos ? undefined : achados?.find((a) => a.valor === info.valor);
  const totalTop = achados?.reduce((n, a) => n + a.n_top, 0);

  return (
    <Box px={{ base: "md", sm: 40 }} pt={{ base: 56, sm: 40 }} pb={56}>
      <Text size="sm" c="dimmed" mb={6}>Banco de ganchos</Text>
      <Title order={1} fz={{ base: 24, sm: 28 }} fw={600} lh={1.25}>Como os Reels do top abrem</Title>
      <Text c="dimmed" mt={6} maw={640}>
        A frase dos primeiros segundos dos 472 Reels do top 10%, por tipo de gancho. Clique numa frase para ver o Reel.
      </Text>

      <Box mt={36} style={{ display: "flex", gap: 40, alignItems: "flex-start", flexWrap: "wrap" }}>
        <Box w={{ base: "100%", sm: 250 }} className="coluna-fixa">
          <Text size="sm" fw={600} mb="xs" px={12}>Tipos de gancho</Text>
          {!achados && !erro && <Loader size="sm" ml={12} />}
          {achados && (
            <ListaValores achados={achados} rotulo={(a) => infoTipo(a.valor).rotulo} contagem={(a) => `${a.n_top} frases`}
              ativo={todos ? null : info.valor} onEscolher={onTipo}
              antes={(
                <UnstyledButton className="item-valor" data-ativo={todos || undefined} onClick={() => onTipo(TODOS)}>
                  <Group justify="space-between" wrap="nowrap" gap="xs">
                    <Text size="sm" fw={todos ? 600 : 500}>Todos os ganchos</Text>
                    <Text size="xs" c="dimmed">{totalTop} frases</Text>
                  </Group>
                </UnstyledButton>
              )} />
          )}
        </Box>

        <Box style={{ flex: 1, minWidth: 280 }}>
          <Group justify="space-between" align="center" gap="md" mih={36}>
            <Text fz={22} fw={600} lh={1.3}>{todos ? "Todos os ganchos" : info.rotulo}</Text>
            {!todos && info.valor !== "nenhum" && (
              <Button variant="default" leftSection={<IconSparkles size={16} />} onClick={() => {
                aoCriar?.();
                navigate("/criar", { state: { query: `Reels para a @impulsostone com gancho de ${info.rotulo.toLowerCase()}` } });
              }}>
                Criar Reels com esse gancho
              </Button>
            )}
          </Group>
          <Text c="dimmed" mt={4}>
            {todos ? "As frases de abertura de todos os tipos. Busque uma palavra para achar ganchos sobre um assunto." : `O gancho ${info.ajuda}.`}
          </Text>
          {achado && (
            <Group gap="sm" mt={6}>
              <Text size="sm">{pct(achado.freq_top)} do top × {pct(achado.freq_controle)} do controle</Text>
              <SeloRobustez robustez={achado.robustez} />
            </Group>
          )}

          <TextInput mt="lg" radius="md" placeholder="Buscar uma palavra na frase, na fala ou na legenda: preço, cliente…" value={texto}
            onChange={(e) => setTexto(e.currentTarget.value)} leftSection={<IconSearch size={17} stroke={1.7} />}
            rightSection={texto ? <CloseButton size="sm" onClick={() => setTexto("")} aria-label="Limpar busca" /> : null} />

          <Group justify="space-between" gap="sm" mt="sm" pb="sm" style={{ borderBottom: "1px solid var(--linha)" }}>
            <Group gap="xs">
              {res && <Text size="sm" c="dimmed">{inteiro(res.total)} frases</Text>}
              {carregando && <Loader size={14} />}
            </Group>
            <Group gap={4}>
              <Escolha opcoes={GRUPOS} valor={grupo} onChange={(v) => setGrupo(v as string)} />
              <Escolha icone={IconArrowsSort} opcoes={ORDENS} valor={ordem} onChange={(v) => setOrdem(v as string)} />
            </Group>
          </Group>

          {erro && <Box my="xl"><Erro titulo="Não foi possível buscar">{erro}</Erro></Box>}

          {res && (
            <Box style={{ opacity: carregando ? 0.5 : 1, transition: "opacity 0.2s" }}>
              {res.itens.length === 0 && <Text c="dimmed" py="xl">Nenhuma frase com essa palavra. Tente outra.</Text>}
              {res.itens.map((r) => <Linha key={r.shortCode} r={r} termos={res.termos} comTipo={todos} />)}
              {res.itens.length < res.total && (
                <Button variant="default" mt="lg" onClick={carregarMais} loading={mais}>Ver mais ({inteiro(res.total - res.itens.length)})</Button>
              )}
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
}
