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
- Não criar arquivos `.md` avulsos; contexto para agentes vai neste arquivo. Exceção: o playbook (`docs/playbook.md`).
- Segredos só no `.env` (`GEMINI_API_KEY`, `APIFY_TOKEN`); nunca no código, no chat ou no Git.
- Dados brutos, mídia e comentários de terceiros ficam fora do Git (ver `.gitignore`).

## Ambiente
- Python 3.12 em `.venv` (`.venv/bin/python`); dependências em `requirements.txt`.
- Gemini no plano grátis, cota diária **por modelo**: `gemini-3.5-flash-lite` ~500/dia;
  `gemini-3.5-flash` só **20/dia**. A anotação usa o flash-lite. O agente faz 3 a 5 chamadas por execução:
  orquestrador no flash-lite (`AGENTE_MODELO`) e redação no flash (`AGENTE_MODELO_REDATOR`), que volta sozinha
  para o flash-lite quando a cota do flash acaba. A cota zera ~05h (horário de Brasília).
- Toda chamada ao Gemini tem tempo limite de 90 s (`dados.TEMPO_LIMITE_S`): com o Google sobrecarregado, uma
  chamada sem limite ficou presa para sempre (17/11). Estourado, o redator segue com o flash-lite; a leitura do
  vídeo e o revisor de imagem esperam e tentam de novo; nos outros nós, a execução termina com erro.
- ffmpeg vem do pacote `imageio-ffmpeg` (`imageio_ffmpeg.get_ffmpeg_exe()`); não há ffmpeg no sistema.
- Processos longos: rodar desacoplados (`setsid nohup ... &`), porque a sessão pode encerrar.

## Pipeline (scripts em `scripts/`, na ordem)
`coleta_esdrasdw.py` → `curtidas_ocultas.py` / `confirmar_ocultas.py` → `preparar_base.py --min-views 300`
→ `sortear_amostra.py` → `processar_midia.py` → `transcrever_paralelo.sh 7 2` → `coleta_comentarios.py`
→ `anotar_gemini.py` (rubrica em `agente/rubrica.py`) → `lift.py` → `gerar_validacao.py` / `concordancia.py`
→ `indexar_base.py` (gera `data/processed/agente.db`, a base do agente; rodar de novo se a anotação ou o lift mudarem).
Toda execução na Apify fica registrada em `data/raw/coletas.csv`.
`ler_impulsostone.py` lê os 56 Reels da @impulsostone (fora do top e do controle) do mesmo jeito: links novos (uma
execução do esdrasdw só com o perfil), quadros em `data/midia/`, transcrição e rubrica em
`data/processed/impulsostone.jsonl`; base do diagnóstico do perfil. O `indexar_base.py` grava esses Reels na tabela
`impulsostone` do agente.db (mesmas colunas de `reels`, grupo = "impulsostone"; `dados.reels_stone()`).

## Dados
| Arquivo | Conteúdo |
|---|---|
| `data/processed/base.csv` | 7.554 Reels (7.561 coletados, menos 7 repetidos); `no_ranking=True` em 4.719. Colunas: shortCode, url, perfil, publicado_em, curtidas, comentarios, visualizacoes, duracao_s, seguidores, faixa (micro/medio/grande), tipo, nicho, taxa_engajamento, taxa_visualizacoes, taxa_comentarios, motivo_fora, legenda |
| `data/processed/amostra.csv` | 944 Reels: `grupo` = top (472, 10% de maior taxa) ou controle (472, sorteado e estratificado por faixa) |
| `data/processed/anotacoes.jsonl` | Anotação do Gemini por Reel da amostra; usar só `versao_rubrica == "v2"`. Campos na classe `Anotacao` de `agente/rubrica.py` |
| `data/processed/lift.csv` | Top × controle por campo/valor: freq_top, freq_controle, dif_pp, lift, ic95_min/max, confidence_flag, robusto_sensibilidade |
| `data/processed/concordancia_*.csv` | Concordância da anotação (validação cruzada entre modelos) |
| `data/midia/{shortCode}/` | 8 quadros, `transcricao.json`, `meta.json` (fora do Git) |
| `data/interim/comentarios.csv` | Comentários com intenção de contato por Reel (fora do Git) |

Métrica principal: **taxa de engajamento = (curtidas + comentários) ÷ seguidores**.

## Achados finais (#17, fechados em 16/11)
Lista oficial para playbook, README e slides: `data/processed/achados_finais.csv` e
`data/processed/perfis_destaque.csv`, gerados por `scripts/achados_finais.py` (rodar de novo se o lift mudar).
Teste extra de concentração: os 6 criadores com mais Reels no top somam 37% do top; cada achado foi
recalculado sem eles (coluna `mantem_sem_6_maiores`).
- **Diferença clara** (mantém sem os 6): **mais de 90 s** (32% × 16%, 2× mais comum no top) e **30–60 s**
  aparecendo menos (21% × 31%).
- **Indícios**: gancho de **curiosidade** (36% × 28%) e de **polêmica** (5% × 2%, raro) mantêm sem os 6;
  formato **explicativo** (20% × 9%) e **data comemorativa** aparecendo menos (4% × 10%, ao contrário dos
  anúncios da Stone) **dependem dos maiores criadores** e somem sem eles.
- **Hipóteses da Stone sem diferença** nos Reels orgânicos (e seguem assim sem os 6): pessoas reais/rosto,
  dor real, frase motivacional genérica, CTA, prova social, histórias reais e comentários com intenção de
  contato (4,8% × 4,6%: engajar mais não traz mais pedidos de contato). Convite à participação: só 3% dos
  Reels, poucos dados.
- **Perfis em destaque**: 15 criadores com mais Reels no top; 4 com ocultação parcial de curtidas
  (@fabio.morassi, @larice_, @caitomaiaoficial, @karolinebragaf), cuja taxa pode estar distorcida.
- Confiabilidade dos campos: bons — tem_rosto, tem_cta, tipo_cta, tema_principal, fala_de_negocio,
  formato_video; moderados — abordagem, tipo_hook; **fraco — criador_e_empreendedor_real (não usar)**.

## Playbook (#19 e #20)
`docs/playbook.md`, o manual de conteúdo para a equipe da @impulsostone, é **gerado** por `scripts/gerar_playbook.py`
(não editar à mão; o texto fixo, como o "Como aplicar" de cada achado, fica no script). Números, Reels de exemplo
(um por criador, sem repetir Reel nem gancho), ganchos, diagnóstico e perfis vêm da base; rodar de novo se o lift, os
achados finais ou o diagnóstico mudarem. Os criativos vêm de `scripts/criativos_playbook.py`: 3 briefings no modo
gerar_criativo (educação financeira geral, beleza e alimentação; ~1 min e ~5 chamadas cada), salvos em
`data/processed/playbook_criativos.json`; o playbook usa os 2 primeiros de cada (6). O script pula briefings já feitos:
para refazer, apagar o JSON. Seções: resumo, método, retrato do top (valor mais comum de cada campo e recortes por tema e formato, com um Reel de exemplo por linha, pedido pelas seções 4.1 e 6.1 do TAPI), o que fazer, o que evitar, o que não faz diferença, diagnóstico da
@impulsostone, perfis, banco de ganchos, criativos e limites. Sem vídeos (edição está fora do escopo, seção 4.3 do
documento): só links para os Reels. Filtros do script (23/11): exemplos e ganchos sem os perfis com ocultação parcial
de curtidas, exemplos de explicativo com 45 s ou mais, `GANCHOS_FORA` (ganchos fora do tema, revisão manual),
hashtags com gênero trocadas por neutras e, nos criativos, só os achados que o roteiro cumpre (formato e duração),
com o aviso de "depende de poucos criadores". Capas dos 6 criativos: geradas à parte com `agente.imagens` em
`data/imagens/{run_id}/` (conferidas a olho; as duas de alimentação foram refeitas sem "bold text on screen" e sem
"empty space in the top third", que viravam texto embaralhado e faixa chapada) e copiadas reduzidas pelo script
para `docs/imagens/` (essas vão para o Git).

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
orquestrador (Gemini com ferramentas) ⇄ ferramentas → coletar → redator (analisar, recomendar) ou gerador
(gerar_criativo) → revisor (refaz 1×) → montar_saida.
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
- Modos prontos: analisar, recomendar e **gerar_criativo**. O gerador (flash) escreve 3 criativos com gancho,
  roteiro em cenas (texto na tela e prompt de imagem por cena), legenda, CTA, prompt da capa 9:16, Reels de
  inspiração e achados usados (só selo robusto ou fragil que aparecem mais no top). O revisor confere por
  código e depois o tom pela persona (flash-lite). ~45 s e 4 a 6 chamadas por execução.
- Imagens do criativo, em dois modos. O gerador descreve a **personagem** (uma vez) e o **visual** de cada
  cena; o código monta os prompts com o estilo fixo `ESTILO_VISUAL` (`persona.py`: verde Stone #00A868 em
  detalhes, foto documental, 30–60 anos, terço de cima livre, sem texto nem logo; não há guia de marca).
  - **Copiar**: um prompt único com capa e cenas, para colar no Gemini ou no ChatGPT.
  - **Gerar** (`agente/imagens.py`, rotas `/imagens`): Cloudflare Workers AI, `flux-2-klein-4b`, 864×1536 (9:16),
    sob demanda e em ordem; a capa sai sem referência e cada cena usa **só um recorte do rosto e do tronco da
    capa** como referência. Com a capa inteira ou a cena anterior como referência, o modelo copiava pose e
    fundo e as cenas saíam iguais (testado em 16/11). ~5–10 s e ~140 neurons por imagem; o plano grátis
    (10.000 neurons/dia) dá ~10 criativos completos. Credenciais `CLOUDFLARE_ACCOUNT_ID` e
    `CLOUDFLARE_API_TOKEN` no `.env`; imagens em `data/imagens/` e log em `data/logs/imagens.jsonl`.
  - **Revisor de imagem** (Gemini flash-lite com visão): reprova anatomia estranha, texto inventado em
    destaque, objetos deformados, cena errada e, nas cenas, pessoa diferente da capa (a capa vai como
    "IMAGEM 2", só para conferir a pessoa). Reprovada, gera **uma** segunda versão com outra seed e os
    problemas no prompt, e guarda a de maior nota; no front, cada imagem tem o selo ✓/⚠ com a nota. Mais
    tentativas não compensam (16/11): as boas passam de primeira, e ações difíceis para o modelo (ex.: secar
    o cabelo de uma cliente) falharam nas 3 tentativas do teste; o valor do revisor é marcar o que ficou ruim.
  - Pesquisa (16/11): a cota grátis de imagem do Gemini é zero; o Groq não gera imagem; o `flux-1-schnell`
    (mais barato) não aceita 9:16 nem referência.
- Servidor MCP: `agente/servidor_mcp.py` com o pacote `fastmcp` (o SDK `mcp` 2.x renomeou o FastMCP para
  MCPServer); ferramentas analisar, recomendar, gerar_criativo, **gerar_imagens** e avaliar. Rodar com
  `.venv/bin/python -m agente.servidor_mcp`. O gerar_criativo só devolve prompts; `gerar_imagens(run_id, criativo)`
  (24/11) gera capa e cenas de um criativo com `imagens.gerar_do_criativo` (o criativo vem do log, via
  `registro.execucao`), reaproveita as que já existem (salvo `refazer`) e devolve o caminho e a revisão de cada uma;
  ~1–2 min e ~840 neurons por criativo. No teste, 3 de 6 imagens aprovadas (as reprovadas: pessoa diferente, ação
  errada e mãos), como no front.
- O revisor por código reprova capa ou visual de cena que peça texto escrito na imagem (`pede_texto_na_imagem` em
  `nos.py`: frase entre aspas, "with the text", "text overlay"...), o que contradiz o "No text" do `ESTILO_VISUAL`;
  aparecia em 5 de 119 descrições do log (24/11). O gerador também é instruído a não pedir texto na imagem.
- Modo **avaliar** (#27, acréscimo do projeto ao documento; `agente/avaliacao.py`): a pessoa envia o próprio
  vídeo, ou só o roteiro em texto, e recebe pontos fortes, pontos a melhorar e o que não precisa mudar. Caminho
  fixo, sem orquestrador: ler → comparar → avaliador → revisor → saída.
  - **ler** usa `agente/midia.py`, a mesma leitura dos Reels da amostra (quadros e cortes com ffmpeg, transcrição
    com faster-whisper local, rubrica v2 no flash-lite). `processar_midia.py`, `transcrever.py` e
    `anotar_gemini.py` usam essas mesmas funções. Roteiro: só a rubrica, duração estimada (2,5 palavras/s) e
    campos visuais fora da comparação.
  - **comparar** (código): o que o vídeo tem e aparece mais no top (robusto/frágil) é forte; o que aparece menos,
    ou a falta da melhor alternativa do mesmo campo, é a melhorar; "sem diferença" vai para "não precisa mudar".
    Cada ponto leva 2 Reels de exemplo. O LLM só redige o texto de cada ponto. Sem nota nem previsão.
  - Tempo: 40 s a 3 min por vídeo (transcrição e esperas quando o Gemini responde 503); roteiro, ~30 s.
  - API: `POST /avaliacoes` (vídeo ou roteiro, em segundo plano) e `GET /avaliacoes/{id}` (etapa atual). Vídeos
    em `data/uploads/` (fora do Git). Testado com vídeos reconstruídos de Reels da base (quadros + áudio): a
    leitura bate com a anotação original em 9 de 10 campos.
  - A redação (flash) volta para o flash-lite também quando o flash está sobrecarregado (503), não só sem cota.
- Achados que dependem de poucos criadores (`dados.depende_de_poucos()`, de `achados_finais.csv`: explicativo e
  data comemorativa) chegam ao redator, ao gerador e ao avaliador com esse aviso.
- API e front básico (para testar): `.venv/bin/uvicorn agente.api:app --port 8000` e, em `web/`,
  `npm install && npm run dev` (http://localhost:5173; o Vite repassa `/api` para a porta 8000). Front em
  React + Vite + Mantine 9 + React Router, redesenhado em 17/11 com referências de ChatGPT/Gemini (barra lateral
  com Recentes, tela inicial com sugestões), Perplexity (Reels-fonte no alto e citações numeradas com prévia),
  NotebookLM (detalhe do Reel sem sair da tela) e Jasper/Canva (briefing fixo e variações lado a lado).
  - Telas, cada uma com URL própria e resultado em `/<tela>/<run_id>`: **Perguntar** (analisar e recomendar),
    **Criar** (briefing + 3 criativos com storyboard de cenas 9:16), **Avaliar** (vídeo ou roteiro, progresso por
    etapa) e **Panorama** (top × controle em halteres: ponto verde = top, cinza = controle).
  - A API não manda o progresso das consultas: as etapas de Perguntar e Criar avançam pelo tempo médio
    (`Trabalhando` em `componentes/Comum.tsx`); só Avaliar tem a etapa real.
  - Tema claro e escuro; cores de superfície em `src/estilos.css` (variáveis `--fundo`, `--linha`, `--verde-suave`).
  - Cores do design system Odin de stone.com.br (`src/main.tsx`): verde da marca #00DB00 (tom 6, também no logo) com
    texto escuro por cima; texto verde #005700; fundo verde translúcido do site nas variantes "light"; cinzas "sage"
    (puxados para o verde, texto #1B221F) no lugar dos cinzas azulados do Mantine, e o escuro com o mesmo matiz.
  - Estilo limpo (pedido do Vinícius, 17/11): navegação apagada como no Linear (item ativo só com fundo cinza),
    espaço em vez de bordas (`Paper` sem borda por padrão; borda só em campos e listas), telas iniciais
    centralizadas na vertical como no ChatGPT (`Inicio` e `Compositor`), opções discretas (`Escolha`) e sugestões
    em linhas com ícone (`componentes/Comum.tsx`). Fonte Geist.
  - Logo: wordmark da Stone em `web/public/stone-logo.svg` (de stone.com.br) e o símbolo (o "o" do wordmark) em
    `stone-simbolo.svg`, também favicon. Barra lateral recolhível (lembrada no navegador): recolhida, mostra só o
    símbolo, que vira o botão de expandir ao passar o mouse.
  - Execuções em andamento ficam fora das telas (`rodar` e `useTarefa` em `contexto.tsx`): seguem ao trocar de tela,
    aparecem em "Em andamento" nos Recentes, e o resultado só abre sozinho se a pessoa continuar na tela.
  - Capa de Reel (`Capa` em `CartaoReel.tsx`): se um quadro faltar, tenta o próximo da lista.
  - Panorama: filtros de setor e tamanho (`GET /panorama?segmento=&faixa=`, sem LLM, recalcula o lift no recorte
    como `consultar_caracteristicas`; ~1 s, com cache). Em formato de dashboard: Destaques (até 3 do que fazer e 1 do
    que evitar, com o multiplicador grande e Reels de exemplo), grade "Explorar por característica" (uma peça por
    campo, com barras top e controle; ou "Lista", com os halteres de `componentes/Achados.tsx`) e painel de detalhe
    ao clicar (todos os valores, Reels do top de cada valor via `GET /panorama/exemplos` e "Criar Reels com isso",
    que abre Criar preenchido). Em campos sim/não, destaques e peças mostram só o "sim".
  - **Banco de ganchos** (`PainelGanchos` em `telas/Ganchos.tsx`): à esquerda, fixa ao rolar, "Todos os ganchos" e os 7
    tipos do mais ao menos usado no top, com barras top × controle e selo; à direita, as frases reais do tipo escolhido
    (ou de todos, com o tipo em cada linha), com busca por palavra (frase, fala e legenda, sem acento), opção de incluir
    a amostra comum e "Criar Reels com esse gancho". Abre só num **glance** (`componentes/Glance.tsx`, como o do Zen
    Browser: janela por cima da tela, que cresce a partir do botão clicado e volta para ele ao fechar; Esc ou clique
    fora fecham; sem botão de página inteira, pedido de 17/11) a partir de `abrirGanchos(tipo, elemento)`
    (`contexto.tsx`). Entradas: no Perguntar, quando os achados da resposta incluem `tipo_hook`; no detalhe de "Tipo de
    gancho" do Panorama ("Ver todos os ganchos", no alto, à direita do título); e no Reel ("Outros ganchos de...").
    Busca em `agente/busca.py` (`GET /busca` e `/busca/opcoes`, sem LLM; filtros f=campo:valor). Uma aba
    "Biblioteca" de Reels com filtros foi testada e descartada (17/11): repetia o Panorama e o Perguntar.
  - **Glance no lugar de gavetas laterais** (pedido do Vinícius, 17/11): o Reel (`componentes/ReelGlance.tsx`, aberto
    por `abrirReel(shortCode, elemento)` de qualquer cartão, miniatura ou citação: quadro grande e os 8 quadros, gancho,
    métricas, fala, legenda e anotação) e o detalhe de uma característica no Panorama abrem em glance. Glances se
    empilham (um Reel aberto de dentro do banco de ganchos fica por cima); Esc fecha só o de cima.
  - **Diagnóstico** (aba própria, `telas/Diagnostico.tsx`; `agente/diagnostico.py`, `GET /diagnostico`, sem LLM): os 56
    Reels da @impulsostone (22/04 a 13/11) comparados ao top e ao controle, com IC de 95% de Wilson (n pequeno). Cada
    achado com diferença clara ou indício vira lacuna (aparece mais no top e a Stone fica abaixo do ponto médio entre
    top e controle), excesso (o espelho) ou em linha; "claro" quando o IC inteiro fica longe do top e o achado não
    depende de poucos criadores, senão "provável" (seção "Para observar"). Resultado (17/11): lacunas claras em mais de
    90 s (Stone 5% × top 32%) e gancho de curiosidade (7% × 36%); para observar: polêmica, 30–60 s e data comemorativa;
    em linha: explicativo. As hipóteses da Stone sem diferença (rosto, CTA, dor real...) vão para "Não é alavanca".
    Tela no padrão do Panorama (escolhida em 18/11 entre 5 versões de teste): linha de contexto (56 Reels, período, taxa
    mediana de 0,8%, no meio dos 15 perfis micro, por perfil); "O que mudar" em linhas largas, cada uma com a
    característica e um **veredito** ("6× menos / que o top", e embaixo "5% dos Reels da @impulsostone · 32% dos Reels do
    top"), "Criar Reels com isso" e o selo no pé, e 4 Reels do top à direita; grade "Todas as características" agrupada
    por situação (título e uma frase de ajuda por grupo), com um veredito curto em texto no lugar de barras (as barras de
    valores pequenos ficavam ilegíveis, 18/11): a característica no alto, o campo embaixo dela e, no pé da peça, "Usa
    pouco" ou "Usa demais" em laranja (Para observar), "Igual ao top" em verde (Já em linha) ou "Não faz diferença" em
    cinza (Não é alavanca), com os dois números; detalhe em glance (frase "3 de 56 Reels da @impulsostone duram mais de 90 s", intervalo, valores mais
    comuns na Stone para o campo, Reels do top e da Stone); no fim, os 56 Reels numa faixa. Todo número diz de onde vem
    ("dos Reels da @impulsostone", "dos Reels do top"), sem repetir a mesma informação em dois lugares (pedido de 18/11);
    as frases por campo ficam em `VERBOS` (`Diagnostico.tsx`).
  - **Comparar com a @impulsostone**: interruptor único para o app todo (`ComparadorStone`, `useComparacaoStone` em
    `contexto.tsx`, lembrado no navegador; `GET /diagnostico/frequencias`). Ligado, as barras ganham uma terceira em
    laranja (`--barra-stone`), os halteres um losango e os números "Stone x%": Panorama (destaques, grade e detalhe),
    banco de ganchos e achados do Perguntar.
  - Criar: "Baixar .zip" por criativo (`GET /execucoes/{run_id}/criativos/{n}.zip`): `criativo.txt`,
    `prompt-imagens.txt` e as imagens já geradas (capa.jpg, cena1.jpg...).
  - Evitar sinais de "interface feita por IA": barra grossa colorida ao lado de cartões, selos em pílulas coloridas
    (os selos são texto; verde só em "Diferença clara"), avatares de iniciais, ✓/⚠ e emoji como ícone, fileira de
    cartões de métrica, grade de três passos com números em círculos, cartões dentro de cartões.
- Uso: `from agente import executar; executar({"mode": "analisar", "query": "..."})`. Log em
  `data/logs/agente.jsonl`.
