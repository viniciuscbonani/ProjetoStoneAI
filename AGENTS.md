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
- Gemini no plano grátis: ~500 requisições/dia **por modelo**. A anotação usa `gemini-3.5-flash-lite`;
  para outras tarefas, prefira outro modelo (ex.: `gemini-3.5-flash`) para não disputar a cota.
- ffmpeg vem do pacote `imageio-ffmpeg` (`imageio_ffmpeg.get_ffmpeg_exe()`); não há ffmpeg no sistema.
- Processos longos: rodar desacoplados (`setsid nohup ... &`), porque a sessão pode encerrar.

## Pipeline (scripts em `scripts/`, na ordem)
`coleta_esdrasdw.py` → `curtidas_ocultas.py` / `confirmar_ocultas.py` → `preparar_base.py --min-views 300`
→ `sortear_amostra.py` → `processar_midia.py` → `transcrever_paralelo.sh 7 2` → `coleta_comentarios.py`
→ `anotar_gemini.py` (rubrica em `rubrica.py`) → `lift.py` → `gerar_validacao.py` / `concordancia.py`.
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
Público 70,5% feminino, 47,5% entre 35 e 54 anos. Objetivo: **lead** (inscrição no programa). Tom
próximo, acolhedor, educativo e interativo, linguagem simples, sem jargão nem promessa exagerada.
Pilares: educação financeira, gestão e vendas, histórias reais, especialistas, comunidade. Nos
anúncios da Stone funcionaram convite à participação, dor real, datas comemorativas e pessoas reais;
não funcionaram frase motivacional genérica, POV sem chamada e mensagem sem gancho.

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
