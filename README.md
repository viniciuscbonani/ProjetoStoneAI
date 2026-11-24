# Conteúdo de alto engajamento para MPEs × @impulsostone

TAPI Stone × Inteli Academy. O projeto mapeia o que os Reels de maior engajamento entre micro e pequenos
empreendedores (MPEs) têm em comum e transforma isso em conteúdo para a **@impulsostone**, o programa social da Stone.

Entregas:

- **[Playbook de conteúdo](docs/playbook.md):** o que fazer, o que evitar e o que não faz diferença. Também traz o
  diagnóstico da @impulsostone, perfis de referência, um banco de ganchos e 6 criativos prontos para gravar.
- **Agente de conteúdo:** recebe um pedido e devolve uma análise, recomendações, criativos ou a avaliação de um vídeo,
  sempre citando Reels reais da base. Funciona de três jeitos: como função Python, como **servidor MCP** (para usar no
  Claude, no Cursor e em outros clientes) e por uma API com front web.
- **Base e análise:** 7.554 Reels coletados, uma amostra de 944 anotados (top × controle) e o cálculo de lift com
  intervalo de confiança.

## Principais achados

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

O servidor (`agente/servidor_mcp.py`, feito com FastMCP) roda na própria máquina via stdio e expõe 4 ferramentas:
`analisar`, `recomendar`, `gerar_criativo` e `avaliar`. As únicas chamadas externas são as do Gemini. Nos exemplos
abaixo, troque `/caminho/ProjetoStoneAI` pelo caminho absoluto do repositório.

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
30 a 60 s, `gerar_criativo` de 1 a 2 min e `avaliar` de 30 s (roteiro) a 3 min (vídeo, com transcrição local).

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

## Como os dados foram feitos

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

## Estrutura do agente

O agente é um grafo em LangGraph (`agente/grafo.py`):

- **analisar, recomendar e gerar_criativo:** o orquestrador (flash-lite) chama as ferramentas de consulta
  (`consultar_caracteristicas`, `buscar_referencias` e `perfis_em_destaque`). Depois, o redator ou o gerador (flash)
  escreve o texto, e um revisor confere as citações e o tom da persona. Se o revisor reprovar, o texto é refeito uma
  vez.
- **avaliar:** segue um caminho fixo, sem orquestrador: ler o vídeo, comparar por código com os achados, escrever a
  avaliação e revisar.

Achados e Reels de referência são montados a partir do resultado das ferramentas, nunca do texto do LLM: o modelo
orquestra e redige, mas os números vêm da base. Detalhes de implementação estão no [AGENTS.md](AGENTS.md).

## Limites

- A análise é **correlacional**: mostra o que aparece mais no top, não o que causa engajamento.
- A anotação é feita por modelo. Os campos de gancho e abordagem têm concordância moderada, e o campo
  `criador_e_empreendedor_real` não é usado.
- Os perfis que ocultam as curtidas de forma sistemática ficaram fora do ranking. Quatro perfis em destaque ocultam
  parte delas, e a taxa desses perfis pode estar distorcida; no playbook, eles não aparecem como exemplo.
- O objetivo da @impulsostone é a inscrição (lead), mas a base mede engajamento orgânico. Por isso todo criativo
  termina com uma chamada clara.
