import { Anchor, Box, Group, Loader, Stack, Text, Title, UnstyledButton } from "@mantine/core";
import {
  IconArrowRight, IconBolt, IconBuildingStore, IconChartDots3, IconClock, IconSparkles, IconToolsKitchen2, IconUserCircle,
  IconUsers, IconWand, type Icon,
} from "@tabler/icons-react";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router";

import { api } from "../api";
import { AchadosDaResposta } from "../componentes/Achados";
import { FaixaReels } from "../componentes/CartaoReel";
import { numerarCitacoes, TextoComCitacoes } from "../componentes/Citacoes";
import { Avisos, Compositor, Erro, Escolha, Inicio, MetaExecucao, Secao, Sugestoes, Tela, Trabalhando } from "../componentes/Comum";
import { limparTarefa, rodar, useExecucao, useRecentes, useTarefa, useTitulo } from "../contexto";
import { FAIXAS, SEGMENTOS } from "../formato";
import type { Entrada, Execucao } from "../tipos";

type ModoPergunta = "analisar" | "recomendar";
interface Rascunho { mode: ModoPergunta; query: string; segment: string; faixas: string[] }

const SUGESTOES: (Rascunho & { curto: string; icone: Icon })[] = [
  { icone: IconClock, curto: "Que duração aparece mais no top", mode: "analisar", query: "Que duração de Reels mais aparece entre os de alto engajamento?", segment: "", faixas: [] },
  { icone: IconBolt, curto: "Que tipo de gancho aparece mais", mode: "analisar", query: "Que tipo de gancho aparece mais nos Reels de alto engajamento?", segment: "", faixas: [] },
  { icone: IconUserCircle, curto: "Mostrar o rosto faz diferença?", mode: "analisar", query: "Os vídeos de maior engajamento mostram o rosto?", segment: "", faixas: [] },
  { icone: IconToolsKitchen2, curto: "Recomendações para alimentação", mode: "recomendar", query: "Como a @impulsostone deveria fazer Reels para empreendedoras de alimentação?", segment: "alimentacao", faixas: [] },
];

const MODOS = [
  { value: "analisar", label: "Analisar", descricao: "O que aparece nos Reels de alto engajamento" },
  { value: "recomendar", label: "Recomendar", descricao: "O que fazer e o que evitar" },
];

const PLACEHOLDER: Record<ModoPergunta, string> = {
  analisar: "Pergunte sobre os Reels de alto engajamento…",
  recomendar: "Para que público ou objetivo você quer recomendações?",
};

function CaixaPergunta({ r, setR, enviar, ocupado, autoFocus }: {
  r: Rascunho; setR: (r: Rascunho) => void; enviar: () => void; ocupado: boolean; autoFocus?: boolean;
}) {
  return (
    <Compositor
      valor={r.query}
      onChange={(query) => setR({ ...r, query })}
      onEnviar={enviar}
      placeholder={PLACEHOLDER[r.mode]}
      pronto={r.query.trim().length >= 3}
      ocupado={ocupado}
      autoFocus={autoFocus}
      opcoes={(
        <>
          <Escolha opcoes={MODOS} valor={r.mode} onChange={(v) => setR({ ...r, mode: v as ModoPergunta })} />
          <Escolha icone={IconBuildingStore} opcoes={SEGMENTOS} valor={r.segment} onChange={(v) => setR({ ...r, segment: v as string })} />
          <Escolha icone={IconUsers} opcoes={FAIXAS} valor={r.faixas} multiplo vazio="Todos os tamanhos"
            onChange={(v) => setR({ ...r, faixas: v as string[] })} />
        </>
      )}
    />
  );
}

// Próximo passo depois da resposta: uma linha de texto com seta, sem caixa.
function Passo({ icone: Icone, children, onClick }: { icone: typeof IconSparkles; children: string; onClick: () => void }) {
  return (
    <UnstyledButton onClick={onClick} className="pilula">
      <Group gap={8} wrap="nowrap">
        <Icone size={15} stroke={1.7} />
        {children}
        <IconArrowRight size={14} />
      </Group>
    </UnstyledButton>
  );
}

function Resposta({ e, novaPergunta, caixa }: { e: Execucao; novaPergunta: (r: Rascunho) => void; caixa: ReactNode }) {
  const navigate = useNavigate();
  const s = e.saida!;
  const numeros = numerarCitacoes(s.reference_posts, s.explanation);
  const segment = e.entrada.segment ?? "";

  return (
    <Tela largura={860}>
      <Stack gap={48}>
        <div>
          <Title order={1} fz={{ base: 22, sm: 27 }} fw={600} lh={1.3} mb="sm">{e.entrada.query}</Title>
          <MetaExecucao e={e} />
        </div>

        {s.reference_posts.length > 0 && (
          <Secao titulo="Reels em que a resposta se apoia">
            <FaixaReels refs={s.reference_posts} numeros={numeros} />
          </Secao>
        )}

        <div>
          <TextoComCitacoes texto={s.explanation} refs={s.reference_posts} numeros={numeros} size="16px" />
          <Box mt="md"><Avisos avisos={s.warnings} /></Box>
          <Group gap={8} mt="xl">
            <Passo icone={IconSparkles} onClick={() => navigate("/criar", { state: { query: e.entrada.query, segment } })}>
              Criar Reels a partir disto
            </Passo>
            {e.entrada.mode === "analisar" && (
              <Passo icone={IconWand}
                onClick={() => novaPergunta({ mode: "recomendar", query: e.entrada.query, segment, faixas: e.entrada.filters?.faixa ?? [] })}>
                Transformar em recomendações
              </Passo>
            )}
            <Passo icone={IconChartDots3} onClick={() => navigate("/panorama")}>Ver todas as características</Passo>
          </Group>
        </div>

        <AchadosDaResposta achados={s.findings} />

        {s.profiles.length > 0 && (
          <Secao titulo="Perfis para acompanhar">
            <Stack gap={10}>
              {s.profiles.map((p) => (
                <Group key={p.perfil} gap="sm">
                  <Anchor href={`https://www.instagram.com/${p.perfil}/`} target="_blank" fw={500} size="sm">@{p.perfil}</Anchor>
                  <Text size="sm" c="dimmed">
                    {p.n_top} de {p.n_amostra} Reels no top · {p.tema_predominante.replaceAll("_", " ")} · {p.formato_predominante.replaceAll("_", " ")}
                  </Text>
                </Group>
              ))}
            </Stack>
          </Secao>
        )}

        <div>
          <Text size="sm" c="dimmed" mb="sm">Fazer outra pergunta</Text>
          {caixa}
        </div>
      </Stack>
    </Tela>
  );
}

const VAZIO: Rascunho = { mode: "analisar", query: "", segment: "", faixas: [] };

export default function Perguntar() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { atualizar } = useRecentes();
  const { execucao, erro: erroCarga } = useExecucao(runId);
  const tarefa = useTarefa("perguntar");
  const [r, setR] = useState<Rascunho>(VAZIO);
  useTitulo(tarefa?.rodando ? tarefa.titulo : runId ? execucao?.entrada.query : "Perguntar");

  // Ao abrir um resultado, o campo de "outra pergunta" começa vazio e um erro anterior some.
  useEffect(() => {
    setR((x) => ({ ...x, query: "" }));
    if (runId) limparTarefa("perguntar");
  }, [runId]);

  function enviar(pedido: Rascunho = r) {
    const entrada: Entrada = {
      mode: pedido.mode, query: pedido.query.trim(), segment: pedido.segment || null,
      filters: pedido.faixas.length ? { faixa: pedido.faixas } : null,
    };
    setR(pedido);
    rodar("perguntar", { titulo: entrada.query }, async () => {
      const inicio = Date.now();
      const saida = await api.consultar(entrada);
      return { run_id: saida.run_id, quando: new Date().toISOString(), duracao_s: (Date.now() - inicio) / 1000, entrada, erro: null, saida };
    }, navigate, atualizar);
  }

  const caixa = <CaixaPergunta r={r} setR={setR} enviar={() => enviar()} ocupado={Boolean(tarefa?.rodando)} />;

  if (tarefa?.rodando) {
    return (
      <Tela largura={720}>
        <Title order={1} fz={{ base: 22, sm: 27 }} fw={600} lh={1.3} mb={40}>{tarefa.titulo}</Title>
        <Trabalhando
          etapas={["Escolhendo as consultas à base", "Consultando os achados e os Reels de referência", "Escrevendo a resposta", "Revisando as citações"]}
          limites={[3, 8, 16]}
          inicio={tarefa.inicio}
          previsao="5 a 30 s"
        />
      </Tela>
    );
  }

  if (!runId || tarefa?.erro) {
    return (
      <Inicio titulo="O que engaja nos Reels de pequenos negócios?"
        abaixo={<Sugestoes itens={SUGESTOES} rotulo={(s) => s.curto} icone={(s) => s.icone} onEscolher={(s) => enviar(s)} />}>
        {tarefa?.erro && <Box mb="md"><Erro>{tarefa.erro}</Erro></Box>}
        <CaixaPergunta r={r} setR={setR} enviar={() => enviar()} ocupado={false} autoFocus />
      </Inicio>
    );
  }
  if (erroCarga) return <Tela><Erro titulo="Não foi possível abrir esta execução">{erroCarga}</Erro></Tela>;
  if (!execucao) return <Tela><Loader size="sm" /></Tela>;
  if (!execucao.saida) return <Tela><Erro titulo="Esta execução não terminou">{execucao.erro}</Erro></Tela>;

  return <Resposta e={execucao} novaPergunta={(p) => enviar(p)} caixa={caixa} />;
}
