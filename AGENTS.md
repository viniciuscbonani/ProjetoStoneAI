# AGENTS.md

Guia para agentes de código que trabalham neste repositório.

## Projeto
TAPI Stone × Inteli Academy: mapear o conteúdo de alto engajamento para micro e pequenos
empreendedores (MPEs) no Instagram e transformar isso em criativos para o **@impulsostone**, o
programa social da Stone. Entrega presencial em **25/11/2026**. As tarefas estão em issues de
`viniciuscbonani/ProjetoStoneAI`, com milestones por dia.

Documentos de referência (fora do repo, em `~/Downloads`): `Proposta de TAPI_Stone_Inteli_Academy (1)-1.pdf`
(o documento do projeto; seções 4.1, 6 e 7 definem escopo, métrica e agente), `Aula1_Case_Stone.html`,
`relatorio_impulso_stone_instagram.pdf` e `Impulso Stone · Histórico de Campanhas e Criativos.pptx.pdf`.

## Regras de trabalho
- Planejar e propor antes de implementar; o Vinícius aprova a abordagem.
- Commits agrupados por assunto, em português, **sem linha de coautoria**. Trabalhar numa branch e só
  juntar na `main` quando pedido.
- Não criar arquivos `.md` avulsos; contexto para agentes vai neste arquivo.
- Segredos só no `.env` (`GEMINI_API_KEY`, `APIFY_TOKEN`); nunca no código, no chat ou no Git.
- Dados brutos, mídia e comentários de terceiros ficam fora do Git (ver `.gitignore`).

## Ambiente
- Python 3.12 em `.venv` (`.venv/bin/python`); dependências em `requirements.txt`.
- Gemini no plano grátis, cota diária **por modelo**: `gemini-3.5-flash-lite` ~500/dia;
  `gemini-3.5-flash` só **20/dia**. A anotação usa o flash-lite. O agente faz 3 a 5 chamadas por execução:
  orquestrador no flash-lite (`AGENTE_MODELO`) e redação no flash (`AGENTE_MODELO_REDATOR`), que volta sozinha
  para o flash-lite quando a cota do flash acaba. A cota zera ~05h (horário de Brasília).
- ffmpeg vem do pacote `imageio-ffmpeg` (`imageio_ffmpeg.get_ffmpeg_exe()`); não há ffmpeg no sistema.
- Processos longos: rodar desacoplados (`setsid nohup ... &`), porque a sessão pode encerrar.

## Pipeline (scripts em `scripts/`, na ordem)
`coleta_esdrasdw.py` → `curtidas_ocultas.py` / `confirmar_ocultas.py` → `preparar_base.py --min-views 300`
→ `sortear_amostra.py` → `processar_midia.py` → `transcrever_paralelo.sh 7 2` → `coleta_comentarios.py`
→ `anotar_gemini.py` (rubrica em `rubrica.py`) → `lift.py` → `gerar_validacao.py` / `concordancia.py`
→ `indexar_base.py` (gera `data/processed/agente.db`, a base do agente; rodar de novo se a anotação ou o lift mudarem).
Toda execução na Apify fica registrada em `data/raw/coletas.csv`.

## Dados
| Arquivo | Conteúdo |
|---|---|
| `data/processed/base.csv` | 7.561 Reels; `no_ranking=True` em 4.719. Colunas: shortCode, url, perfil, publicado_em, curtidas, comentarios, visualizacoes, duracao_s, seguidores, faixa (micro/medio/grande), tipo, nicho, taxa_engajamento, taxa_visualizacoes, taxa_comentarios, motivo_fora, legenda |
| `data/processed/amostra.csv` | 944 Reels: `grupo` = top (472, 10% de maior taxa) ou controle (472, sorteado e estratificado por faixa) |
| `data/processed/anotacoes.jsonl` | Anotação do Gemini por Reel da amostra; usar só `versao_rubrica == "v2"`. Campos na classe `Anotacao` de `scripts/rubrica.py` |
| `data/processed/lift.csv` | Top × controle por campo/valor: freq_top, freq_controle, dif_pp, lift, ic95_min/max, confidence_flag, robusto_sensibilidade |
| `data/processed/concordancia_*.csv` | Concordância da anotação (validação cruzada entre modelos) |
| `data/midia/{shortCode}/` | 8 quadros, `transcricao.json`, `meta.json` (fora do Git) |
| `data/interim/comentarios.csv` | Comentários com intenção de contato por Reel (fora do Git) |

Métrica principal: **taxa de engajamento = (curtidas + comentários) ÷ seguidores**.

## Estado da análise (provisório; fechamento na #17)
- Reels com **mais de 90 s**: 32% no top × 16% no controle (lift 1,96; robusto). **30–60 s** aparecem menos (21% × 31%).
- Formato **explicativo** (20% × 9%) e gancho de **curiosidade** (36% × 28%): diferenças frágeis.
- Sem diferença clara: convite à participação, dor real, motivacional genérica, CTA, prova social e
  comentários com intenção de contato (4,8% × 4,6%).
- Confiabilidade dos campos: bons — tem_rosto, tem_cta, tipo_cta, tema_principal, fala_de_negocio,
  formato_video; moderados — abordagem, tipo_hook; **fraco — criador_e_empreendedor_real (não usar)**.

## Persona da @impulsostone (criativos)
Texto completo em `agente/persona.py` (fontes: relatório de Instagram e histórico de campanhas do Meta Ads).
- Fala com **empreendedores e empreendedoras de pequenos negócios** em geral ("empreendedor(a)"), não com
  um gênero. Os 70,5% de mulheres e os 81% com 35+ anos (33,7% com 55+) são dos **seguidores**; 94% das
  visualizações vêm de não seguidores, então o criativo tem de funcionar para quem não conhece o programa.
- Objetivo: **lead** (inscrição/participação). Os aprendizados dos anúncios são medidos por **clique (CTR)**:
  "reação não é clique", então todo criativo termina com um próximo passo claro.
- Tom próximo, acolhedor, educativo, encorajador e interativo; simples e direto; sem jargão nem promessa
  exagerada. Pilares: educação financeira, gestão e vendas, histórias reais, especialistas, comunidade.
- Funcionou: convite à participação (CTR 8,8%), nicho (Beleza), data do calendário, dor concreta com caminho,
  personagem real com prova social. Não funcionou: motivacional genérica, POV sem chamada, **depoimento sem
  CTA** (pessoa real sozinha não basta) e mensagem reflexiva sem promessa clara.

## Agente (issue #14)
Exigências do documento do projeto:
- Orquestração em **LangGraph**, com ferramentas de consulta à base, busca de Reels de referência e
  geração de criativos; disponível como **função Python** e **servidor MCP** (FastMCP).
- **Registro das execuções** em JSONL e **rastreabilidade**: toda recomendação cita os Reels reais em
  que se apoia; o LLM orquestra e redige, mas os dados vêm da base.
- Contrato validado com **Pydantic** — entrada: `mode` (analisar | recomendar | gerar_criativo),
  `query`, `segment` (opcional), `filters` (opcional); saída: `findings`, `reference_posts` (link,
  métrica, categorias), `creatives` (gancho, roteiro, legenda, CTA, cada um com os Reels que o
  inspiraram), `confidence_flag`, `explanation`.
- Pronto quando: os 3 modos respondem com achados provisórios, saída validada, referências com link e
  log gravado.

Implementação (pacote `agente/`, branch `agente`): um agente que recebe o modo. Grafo em `grafo.py`:
orquestrador (Gemini com ferramentas) ⇄ ferramentas → coletar → redator → revisor (refaz 1×) → montar_saida.
- `ferramentas.py`: `consultar_caracteristicas`, `buscar_referencias`, `perfis_em_destaque`; cada `@tool`
  devolve texto para o LLM e os dados à parte (`content_and_artifact`). `findings`, `reference_posts` e
  `profiles` são montados desses dados, nunca do texto do LLM; o revisor rejeita citação que não veio deles.
- Selo de cada achado: **robusto** (IC95 do lift exclui o 1 e passa no teste de sensibilidade; 2 achados),
  **fragil** (exclui o 1, mas não passa; 5), **sem_diferenca** (IC95 contém o 1: top e controle não se
  distinguem; 67) e **insuficiente** (menos de 20 Reels no top; 18). No front: "Diferença clara", "Indício",
  "Sem diferença" e "Poucos dados"; o lift aparece como "2× mais comum no top".
- `confidence_flag` (robusto | fragil | insuficiente; no front, confiança alta/média/baixa): o achado mais
  fraco entre os principais; um "sem diferença" conta como alta quando o IC95 fica entre 0,67 e 1,5.
- Modo analisar responde primeiro à pergunta feita (o valor mais comum no top) e depois se isso diferencia
  o top; os exemplos são dos valores perguntados (com e sem rosto, por exemplo). O recomendar usa só o que
  aparece mais no top (para fazer) e menos (para evitar), sem os "sem diferença".
- Modos prontos: analisar, recomendar. Faltam gerar_criativo e servidor MCP (#14), API FastAPI (#28) e
  front React + Mantine (#29).
- Modo **avaliar** (#27, acréscimo do projeto ao documento): a pessoa envia o próprio vídeo, ou só o roteiro
  em texto, e recebe pontos fortes e pontos a melhorar. Fluxo: `ler_video` (quadros, cortes, transcrição
  local e rubrica v2) → comparação por código com os achados → redator, cada ponto com achado, robustez e
  Reels de referência. Sem nota de engajamento (modelo preditivo está fora do escopo); fala-se em aderência
  aos padrões observados. Desenhado no FigJam (seção Agente).
- API e front básico (para testar): `.venv/bin/uvicorn agente.api:app --port 8000` e, em `web/`,
  `npm install && npm run dev` (http://localhost:5173; o Vite repassa `/api` para a porta 8000). Front em
  React + Vite + Mantine 9: telas Perguntar, Panorama e Histórico, e gaveta com os quadros de cada Reel.
- Uso: `from agente import executar; executar({"mode": "analisar", "query": "..."})`. Log em
  `data/logs/agente.jsonl`.
