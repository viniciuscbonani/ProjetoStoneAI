# Conteúdo de alto engajamento para MPEs × @impulsostone

TAPI Stone × Inteli Academy. O projeto mapeia o que os Reels de maior engajamento entre micro e pequenos
empreendedores (MPEs) têm em comum e transforma isso em conteúdo para a **@impulsostone**, o programa social da Stone.

## Problema e recorte

A Stone quer usar o Instagram da @impulsostone para captar empreendedores para o programa. Hoje, as decisões de
conteúdo se apoiam em referências pontuais. Pergunta norteadora: **quais características de conteúdo, formato e perfil
de criador estão presentes nos Reels de maior engajamento voltados a MPEs, e como transformar isso em criativos para a
Stone?**

Recorte adotado:

- **Plataforma e formato:** só Reels do Instagram. Carrossel e YouTube Shorts ficaram fora.
- **Fontes:** criadores que falam com MPEs, em temas como finanças, precificação, vendas, marketing, gestão,
  alimentação e beleza.
- **Abordagem:** descritiva e sem modelo preditivo. Além do retrato do top pedido no núcleo do TAPI, comparamos o top
  com Reels comuns (extensão 4.2), para separar o que é sucesso do que é só costume do nicho.
- **Lead:** como dados de conversão não são públicos, o lead é medido de forma indireta, pela presença de CTA e pelos
  comentários com intenção de contato.
- **Fora do escopo (4.3):** edição de vídeo e design final. Os criativos são roteiros e capas preliminares.

Entregas:

- **[Playbook de conteúdo](docs/playbook.md):** traz o retrato do Reel do top com recortes por tema e formato; o que
  fazer, o que evitar e o que não faz diferença; o diagnóstico da @impulsostone; os perfis em destaque; o banco de
  ganchos; e 6 criativos prontos para gravar. O documento é montado por script (`scripts/gerar_playbook.py`) a partir
  da base, para que todo número e todo exemplo venha dos dados. Os criativos e as capas são produzidos pelo agente
  (modo `gerar_criativo` e geração de imagens).
- **Agente de conteúdo:** recebe um pedido e devolve uma análise, recomendações, criativos ou a avaliação de um vídeo,
  sempre citando Reels reais da base. Funciona de três jeitos: como função Python, como **servidor MCP** (para usar no
  Claude, no Cursor e em outros clientes) e por uma API com front web.
- **Base e análise:** 7.554 Reels coletados, uma amostra de 944 anotados (top × controle) e o cálculo de lift com
  intervalo de confiança.

## Base de dados

- **Origem:** Reels públicos do Instagram, coletados na Apify com o ator `esdrasdw/instagram-content-scraper`, a rota
  definida no case. Os perfis vieram de hashtags de MPE e de indicações do material da Stone: foram 126 candidatos,
  verificados um a um pelos critérios do case (público MPE, atividade nos últimos 12 meses e diversidade de tamanho de
  conta), dos quais 92 ficaram aptos. Lista em `data/perfis_candidatos.csv`.
- **Período:** Reels publicados de 14/11/2025 a 14/11/2026, até 100 por perfil, coletados em 14/11/2026. Os seguidores
  são de 11/11/2026.
- **Volume:**
  - 7.561 Reels coletados; 7.554 depois de tirar os repetidos.
  - 4.719 Reels de 83 perfis entram no ranking: 712 de perfis micro, 1.962 de médios e 2.045 de grandes.
  - Ficaram fora do ranking:
    - 1.012 colaborações com terceiros;
    - 918 Reels com menos de 14 dias (métricas ainda crescendo);
    - 676 com curtidas ocultas (de perfis inteiros ou de Reels isolados);
    - 182 com menos de 300 visualizações;
    - 47 de perfis de referência.
- **Custo:** cerca de US$ 3,60 na Apify. Cada execução, com parâmetros e custo, está em `data/raw/coletas.csv`.
- **Licença e uso:** são dados públicos de terceiros, usados só para análise acadêmica neste TAPI. Vídeos, quadros,
  comentários e respostas brutas da Apify ficam fora do Git, e o repositório guarda só métricas, legendas e as
  anotações. O código não tem licença de código aberto definida.
- **Limitações de representatividade:**
  - A amostra de perfis foi escolhida a dedo (descoberta por hashtags), não sorteada do universo de MPEs.
  - Só entra o que é público: compartilhamentos e salvamentos não entram.
  - Os seguidores são de uma data só, mesmo para os Reels mais antigos.
  - Os 6 criadores com mais Reels no top somam 37% dele.

## Arquitetura

O fluxo tem quatro partes:

1. **Coleta (Apify):** os Reels entram na base limpa (`base.csv`).
2. **Amostra e leitura:** a amostra top × controle (`amostra.csv`) passa pela leitura da mídia (quadros e
   transcrição) e pela anotação com o Gemini (`anotacoes.jsonl`).
3. **Análise:** com a anotação, calculam-se o lift e os achados finais.
4. **Base do agente:** tudo é reunido em `agente.db`, que o agente consulta.

O agente pode ser usado como função Python, como servidor MCP ou pela API FastAPI, que o front web usa. As telas de
Panorama, banco de ganchos e diagnóstico leem a base direto, sem LLM.

O agente é um grafo em LangGraph (`agente/grafo.py`):

- **analisar, recomendar e gerar_criativo:** o orquestrador (flash-lite) chama as ferramentas de consulta
  (`consultar_caracteristicas`, `buscar_referencias` e `perfis_em_destaque`). Depois, o redator ou o gerador (flash)
  escreve o texto, e um revisor confere as citações e o tom da persona. Se o revisor reprovar, o texto é refeito uma
  vez.
- **avaliar:** segue um caminho fixo, sem orquestrador: ler o vídeo, comparar por código com os achados, escrever a
  avaliação e revisar.

Achados e Reels de referência são montados a partir do resultado das ferramentas, nunca do texto do LLM: o modelo
orquestra e redige, mas os números vêm da base. Detalhes de implementação estão no [AGENTS.md](AGENTS.md).

## Como rodar

Requisitos: Python 3.12 e Node 20 ou mais recente (só para o front).

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # preencha GEMINI_API_KEY (e as chaves da Cloudflare, se for gerar imagens)
.venv/bin/python scripts/indexar_base.py   # cria data/processed/agente.db
```

A base do agente (`data/processed/agente.db`, 1,3 MB) fica fora do Git. O `indexar_base.py` precisa dos CSV e JSONL do
repositório e também de `data/midia/` (duração e cortes de cada Reel), que não é versionada. Sem essa pasta, copie o
`agente.db` de quem já tem a base.

O Gemini roda no plano grátis. A cota diária é contada **por modelo**: o `gemini-3.5-flash-lite` aguenta cerca de 500
chamadas por dia, e o `gemini-3.5-flash` só 20. Cada execução do agente faz de 3 a 6 chamadas. Quando a cota do flash
acaba, a redação passa sozinha para o flash-lite. O ffmpeg vem do pacote `imageio-ffmpeg`, então não é preciso
instalar nada no sistema.

### Agente como função Python

```python
from agente import executar
saida = executar({"mode": "analisar", "query": "Que duração de Reels mais aparece no top?"})
print(saida.explanation)
```

Modos: `analisar`, `recomendar`, `gerar_criativo` e `avaliar` (vídeo ou roteiro). A saída é validada com Pydantic e
traz `findings`, `reference_posts`, `creatives`, `confidence_flag`, `explanation` e o `run_id` do log
(`data/logs/agente.jsonl`).

### Servidor MCP (local, no Claude)

O servidor (`agente/servidor_mcp.py`, feito com FastMCP) roda na própria máquina via stdio e expõe 5 ferramentas:

- `analisar`
- `recomendar`
- `gerar_criativo`
- `gerar_imagens`: recebe o `run_id` de um `gerar_criativo` e o número do criativo (1 a 3). Gera a capa 9:16 e uma
  imagem por cena, passa cada uma pelo revisor de imagem e devolve o caminho local e a nota de cada arquivo.
- `avaliar`

As chamadas externas são as do Gemini e, só no `gerar_imagens`, as da Cloudflare. Nos exemplos abaixo, troque
`/caminho/ProjetoStoneAI` pelo caminho absoluto do repositório.

**Claude Code** (terminal ou app):

```bash
claude mcp add impulso-stone --env PYTHONPATH=/caminho/ProjetoStoneAI -- /caminho/ProjetoStoneAI/.venv/bin/python -m agente.servidor_mcp
```

Para conferir, rode `claude mcp list`. Depois é só pedir em linguagem natural, por exemplo: "use o impulso-stone para
gerar criativos sobre precificação para salões de beleza".

**Claude Desktop:** adicione ao `claude_desktop_config.json` (Linux: `~/.config/Claude/`; macOS:
`~/Library/Application Support/Claude/`; Windows: `%APPDATA%\Claude\`) e reinicie o app:

```json
{
  "mcpServers": {
    "impulso-stone": {
      "command": "/caminho/ProjetoStoneAI/.venv/bin/python",
      "args": ["-m", "agente.servidor_mcp"],
      "env": {"PYTHONPATH": "/caminho/ProjetoStoneAI"}
    }
  }
}
```

O `PYTHONPATH` deixa o servidor funcionar seja qual for a pasta de onde o cliente o inicia. As chaves vêm do `.env` do
repositório, então não é preciso repeti-las na configuração. Tempos de resposta: `analisar` e `recomendar` levam de
30 a 60 s, `gerar_criativo` de 1 a 2 min, `gerar_imagens` de 1 a 2 min por criativo e `avaliar` de 30 s (roteiro)
a 3 min (vídeo, com transcrição local).

### API e front

```bash
.venv/bin/uvicorn agente.api:app --port 8000
cd web && npm install && npm run dev   # http://localhost:5173 (o Vite repassa /api para a porta 8000)
```

Telas do front:

- **Perguntar:** analisar e recomendar.
- **Criar:** 3 criativos com storyboard 9:16, imagens geradas na Cloudflare e download em .zip.
- **Avaliar:** recebe um vídeo ou um roteiro.
- **Panorama:** top × controle por característica, com filtros de setor e tamanho.
- **Diagnóstico:** a @impulsostone comparada ao top.
- **Banco de ganchos:** as frases de abertura reais do top.

Os quadros dos Reels (`data/midia/`) não vão para o Git. Sem eles, o front mostra os cartões sem imagem.

## Modelos e configurações

| Uso | Modelo | Onde se configura |
|---|---|---|
| Anotação dos Reels (rubrica v2) e orquestrador do agente | `gemini-3.5-flash-lite` (plano grátis, ~500 chamadas/dia) | `AGENTE_MODELO` |
| Redação, geração de criativos e avaliação | `gemini-3.5-flash` (20 chamadas/dia), que passa para o flash-lite quando a cota acaba ou o modelo está sobrecarregado | `AGENTE_MODELO_REDATOR` |
| Revisor de imagem | `gemini-3.5-flash-lite` com visão | — |
| Transcrição | faster-whisper, rodando local | — |
| Imagens dos criativos | `flux-2-klein-4b` no Cloudflare Workers AI (864×1536, 9:16) | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |

Toda chamada ao Gemini tem limite de 90 s. Os erros 429 e 503 são tratados com espera e nova tentativa.

## Metodologia: como os dados foram feitos

Os scripts ficam em `scripts/` e rodam nesta ordem:

1. `coleta_esdrasdw.py`: coleta dos Reels na Apify (cada execução fica registrada em `data/raw/coletas.csv`).
2. `curtidas_ocultas.py` e `confirmar_ocultas.py`: triagem dos perfis que ocultam as curtidas.
3. `preparar_base.py --min-views 300`: limpeza da base, taxa de engajamento e entrada no ranking.
4. `sortear_amostra.py`: top 10% e controle estratificado por faixa de tamanho.
5. `processar_midia.py` e `transcrever_paralelo.sh 7 2`: 8 quadros por Reel e transcrição com faster-whisper.
6. `coleta_comentarios.py`: comentários com intenção de contato.
7. `anotar_gemini.py`: aplica a rubrica v2 (`agente/rubrica.py`) a cada Reel da amostra.
8. `gerar_validacao.py` e `concordancia.py`: validação manual de 50 Reels às cegas e concordância entre modelos.
9. `lift.py`: lift top × controle com IC95 por bootstrap de perfil e teste de sensibilidade.
10. `achados_finais.py`: classifica os achados e refaz o cálculo sem os 6 maiores criadores.
11. `ler_impulsostone.py`: lê os 56 Reels da @impulsostone com a mesma rubrica.
12. `indexar_base.py`: monta a base do agente.
13. `criativos_playbook.py` e `gerar_playbook.py`: geram o playbook. **Não edite o `docs/playbook.md` à mão**; altere o
    script e rode de novo.

| Arquivo | Conteúdo |
|---|---|
| `data/processed/base.csv` | 7.554 Reels com métricas, perfil, faixa e nicho |
| `data/processed/amostra.csv` | 944 Reels: top (472) e controle (472) |
| `data/processed/anotacoes.jsonl` | Anotação de cada Reel da amostra (usar `versao_rubrica == "v2"`) |
| `data/processed/lift.csv` | Top × controle por característica, com IC95 e robustez |
| `data/processed/achados_finais.csv` | Lista oficial de achados |
| `data/processed/perfis_destaque.csv` | 15 criadores com mais Reels no top |
| `data/processed/impulsostone.jsonl` | Leitura dos 56 Reels da @impulsostone |

Vídeos, quadros, comentários de terceiros e respostas brutas da Apify ficam fora do Git (ver `.gitignore`).

## Resultados: principais achados

Métrica: **taxa de engajamento = (curtidas + comentários) ÷ seguidores**. Os 472 Reels de maior taxa (os 10% de cima)
foram comparados a 472 Reels sorteados do restante, na mesma proporção de perfis micro, médios e grandes.

| Achado | Top | Controle | Confiança |
|---|---|---|---|
| Vídeos de **mais de 90 s** | 32% | 16% | Diferença clara (2,0× mais comum no top) |
| Vídeos de **30 a 60 s** | 21% | 31% | Diferença clara (1,5× menos comum no top) |
| Gancho de **curiosidade** | 36% | 28% | Indício |
| Gancho de **polêmica** | 5% | 2% | Indício (raro) |
| Formato **explicativo** | 20% | 9% | Indício; depende de poucos criadores |
| **Data comemorativa** | 4% | 10% | Indício (menos comum no top); depende de poucos criadores |

Rosto, dor real, frase motivacional, CTA, prova social e histórias reais **não diferenciam** o top: aparecem na mesma
proporção nos Reels comuns. Os comentários com intenção de contato também ficam iguais (4,8% × 4,6%).

Os 6 criadores com mais Reels no top somam 37% dele, por isso cada achado foi recalculado sem eles. Na @impulsostone
(56 Reels analisados), as maiores lacunas em relação ao top são as **durações acima de 90 s** (5% × 32%) e o **gancho
de curiosidade** (7% × 36%). A lista completa está em `data/processed/achados_finais.csv` e no playbook.

## Limites

- A análise é **correlacional**: mostra o que aparece mais no top, não o que causa engajamento.
- A anotação é feita por modelo. Os campos de gancho e abordagem têm concordância moderada, e o campo
  `criador_e_empreendedor_real` não é usado.
- Os perfis que ocultam as curtidas de forma sistemática ficaram fora do ranking. Quatro perfis em destaque ocultam
  parte delas, e a taxa desses perfis pode estar distorcida; no playbook, eles não aparecem como exemplo.
- O objetivo da @impulsostone é a inscrição (lead), mas a base mede engajamento orgânico. Por isso todo criativo
  termina com uma chamada clara.

## Registro das análises

- **Coletas:** cada execução na Apify, com parâmetros, volume e custo, está em `data/raw/coletas.csv`.
- **Anotação e validação:** `data/processed/anotacoes.jsonl` (com a versão da rubrica) e
  `data/processed/concordancia_*.csv`.
- **Análise:** `data/processed/lift.csv` e `data/processed/achados_finais.csv`, gerados pelos scripts da seção de metodologia.
- **Agente:** cada execução fica em `data/logs/agente.jsonl`, com a entrada, as ferramentas chamadas, a decisão do
  revisor e a saída. As imagens ficam em `data/logs/imagens.jsonl`.

## Possibilidades de evolução

- **Medir o efeito na @impulsostone:** gravar Reels seguindo o playbook e comparar a taxa de engajamento e os cliques
  (CTR) com os anteriores. Com dados do próprio perfil, dá para medir a conversão real, e não só o engajamento.
- **Ampliar a base:**
  - incluir carrossel e YouTube Shorts;
  - coletar de novo para ter seguidores na data de cada Reel;
  - sortear perfis de um universo maior, para reduzir o viés de seleção.
- **Dados do Instagram Insights:** compartilhamentos, salvamentos e retenção, que não são públicos mas pesam no
  algoritmo.
- **Análises que ficaram de fora:**
  - horário e frequência de publicação, com um calendário editorial;
  - dúvidas e objeções recorrentes nos comentários;
  - o teste de quando os perfis ocultam as curtidas (antes ou depois de ver o resultado).
- **Playbook para o lojista:** uma versão educativa voltada ao próprio empreendedor (extensão 4.2).
- **Agente:**
  - busca semântica (RAG) nas transcrições;
  - avaliação de rascunhos direto no fluxo de produção da equipe;
  - roteiros por setor (alimentação, beleza, varejo e serviços) com mais exemplos.
