import { Box, Button, Group, Loader, Stack, Tabs, Text, Title } from "@mantine/core";
import { IconBuildingStore, IconCash, IconPlus, IconScissors, IconShoppingBag, type Icon } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";

import { api } from "../api";
import { FaixaReels } from "../componentes/CartaoReel";
import { numerarCitacoes, TextoComCitacoes } from "../componentes/Citacoes";
import { Avisos, Compositor, Erro, Escolha, Inicio, MetaExecucao, Secao, Sugestoes, Tela, Trabalhando } from "../componentes/Comum";
import Criativo from "../componentes/Criativo";
import { limparTarefa, rodar, useExecucao, useRecentes, useTarefa, useTitulo } from "../contexto";
import { SEGMENTOS } from "../formato";
import type { Entrada, Execucao } from "../tipos";

const EXEMPLOS: { curto: string; query: string; segment: string; icone: Icon }[] = [
  { icone: IconScissors, curto: "Atrair donos de salão de beleza para o programa", query: "Preciso de um Reels para atrair donos e donas de salão de beleza para o programa", segment: "beleza" },
  { icone: IconCash, curto: "Organizar o caixa de um pequeno restaurante", query: "Reels sobre organizar o caixa para quem tem um pequeno restaurante ou lanchonete", segment: "alimentacao" },
  { icone: IconShoppingBag, curto: "Convidar lojistas para os cursos gratuitos", query: "Reels convidando lojistas a participar dos cursos gratuitos do Impulso Stone", segment: "varejo" },
];

function Resultado({ e, novo }: { e: Execucao; novo: () => void }) {
  const s = e.saida!;
  const [ativo, setAtivo] = useState("0");
  useEffect(() => setAtivo("0"), [s.run_id]);
  const numeros = numerarCitacoes(s.reference_posts, s.explanation);

  return (
    <Tela>
      <Stack gap={40}>
        <Group justify="space-between" align="flex-start" gap="md">
          <div style={{ flex: 1, minWidth: 260 }}>
            <Title order={1} fz={{ base: 22, sm: 27 }} fw={600} lh={1.3} mb="sm">{e.entrada.query}</Title>
            <MetaExecucao e={e} />
          </div>
          <Button variant="default" leftSection={<IconPlus size={16} />} onClick={novo}>Novo briefing</Button>
        </Group>

        <Tabs value={ativo} onChange={(v) => setAtivo(v ?? "0")} keepMounted={false}>
          <Tabs.List mb={32}>
            {s.creatives.map((c, i) => (
              <Tabs.Tab key={c.titulo} value={String(i)} py="sm">
                <Text size="xs" c="dimmed">Criativo {i + 1}</Text>
                <Text size="sm" fw={500} maw={240} truncate>{c.titulo}</Text>
              </Tabs.Tab>
            ))}
          </Tabs.List>
          {s.creatives.map((c, i) => (
            <Tabs.Panel key={c.titulo} value={String(i)}>
              <Criativo c={c} n={i + 1} runId={s.run_id} refs={s.reference_posts} />
            </Tabs.Panel>
          ))}
        </Tabs>

        <Secao titulo="Por que estes criativos">
          <Box maw={760}>
            <TextoComCitacoes texto={s.explanation} refs={s.reference_posts} numeros={numeros} size="15px" />
            <Box mt="md"><Avisos avisos={s.warnings} /></Box>
          </Box>
          {s.reference_posts.length > 0 && <Box mt="xl"><FaixaReels refs={s.reference_posts} numeros={numeros} /></Box>}
        </Secao>
      </Stack>
    </Tela>
  );
}

export default function Criar() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { query?: string; segment?: string } | null };
  const { atualizar } = useRecentes();
  const { execucao, erro: erroCarga } = useExecucao(runId);
  const tarefa = useTarefa("criar");
  // Depois de um erro, o pedido volta para o campo (mesmo se a pessoa saiu e voltou para a tela).
  const [query, setQuery] = useState(state?.query ?? (tarefa?.erro ? tarefa.titulo : ""));
  const [segment, setSegment] = useState(state?.segment ?? "");
  useTitulo(tarefa?.rodando ? tarefa.titulo : runId ? execucao?.entrada.query : "Criar");

  useEffect(() => {
    if (runId) limparTarefa("criar");
  }, [runId]);

  function gerar() {
    const entrada: Entrada = { mode: "gerar_criativo", query: query.trim(), segment: segment || null, filters: null };
    rodar("criar", { titulo: entrada.query }, async () => {
      const inicio = Date.now();
      const saida = await api.consultar(entrada);
      setQuery("");
      return { run_id: saida.run_id, quando: new Date().toISOString(), duracao_s: (Date.now() - inicio) / 1000, entrada, erro: null, saida };
    }, navigate, atualizar);
  }

  if (tarefa?.rodando) {
    return (
      <Tela largura={720}>
        <Title order={1} fz={{ base: 22, sm: 27 }} fw={600} lh={1.3} mb={40}>{tarefa.titulo}</Title>
        <Trabalhando
          etapas={["Consultando os achados e os Reels de referência", "Escrevendo os 3 criativos", "Conferindo as citações",
            "Revisando o tom pela persona da @impulsostone"]}
          limites={[8, 40, 60]}
          inicio={tarefa.inicio}
          previsao="1 a 2 min"
        />
      </Tela>
    );
  }

  if (!runId || tarefa?.erro) {
    return (
      <Inicio titulo="Que Reels você precisa?"
        abaixo={<Sugestoes itens={EXEMPLOS} rotulo={(x) => x.curto} icone={(x) => x.icone}
          onEscolher={(x) => { setQuery(x.query); setSegment(x.segment); }} />}>
        {tarefa?.erro && <Box mb="md"><Erro titulo="Não foi possível gerar os criativos">{tarefa.erro}</Erro></Box>}
        <Compositor
          valor={query}
          onChange={setQuery}
          onEnviar={gerar}
          placeholder="Diga o público, o objetivo ou o tema. O agente escreve 3 criativos em 1 a 2 minutos."
          pronto={query.trim().length >= 3}
          botao="Gerar 3 criativos"
          linhas={3}
          autoFocus
          opcoes={<Escolha icone={IconBuildingStore} opcoes={SEGMENTOS} valor={segment} onChange={(v) => setSegment(v as string)} />}
        />
      </Inicio>
    );
  }
  if (erroCarga) return <Tela><Erro titulo="Não foi possível abrir esta execução">{erroCarga}</Erro></Tela>;
  if (!execucao) return <Tela><Loader size="sm" /></Tela>;
  if (!execucao.saida) return <Tela><Erro titulo="Esta execução não terminou">{execucao.erro}</Erro></Tela>;
  return <Resultado e={execucao} novo={() => navigate("/criar")} />;
}
