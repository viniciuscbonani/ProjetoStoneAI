"""Servidor MCP do agente (FastMCP): uma ferramenta por modo, todas chamando executar().

Qualquer cliente MCP (Claude Desktop, Claude Code, Cursor...) passa a ter as ferramentas analisar, recomendar,
gerar_criativo, gerar_imagens (capa e cenas de um criativo já gerado) e avaliar. A resposta é a Saida do agente em JSON, com achados, Reels de referência e o run_id do log.

Uso (transporte stdio, o padrão dos clientes MCP):
    .venv/bin/python -m agente.servidor_mcp
Exemplo de configuração no cliente:
    {"mcpServers": {"impulso-stone": {"command": "/caminho/.venv/bin/python",
                                      "args": ["-m", "agente.servidor_mcp"], "cwd": "/caminho/ProjetoStoneAI"}}}
"""

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from . import executar, imagens, registro

mcp = FastMCP(
    "impulso-stone",
    instructions="Agente de conteúdo da @impulsostone: analisa o que engaja em Reels para micro e pequenos "
                 "empreendedores, recomenda e gera criativos, sempre citando Reels reais da base.",
)

Setor = Annotated[Literal["alimentacao", "beleza", "varejo", "servicos"] | None,
                  Field(description="setor do empreendedor; vazio = todos")]
Faixas = Annotated[list[Literal["micro", "medio", "grande"]] | None,
                   Field(description="tamanho do perfil: micro (até 10 mil), medio (10 a 100 mil), grande")]


def _rodar(mode: str, query: str, segment: str | None, faixa: list[str] | None) -> dict:
    entrada = {"mode": mode, "query": query, "segment": segment, "filters": {"faixa": faixa} if faixa else None}
    return executar(entrada).model_dump(mode="json")


@mcp.tool
def analisar(query: Annotated[str, Field(description="pergunta sobre os Reels de alto engajamento")],
             segment: Setor = None, faixa: Faixas = None) -> dict:
    """Responde a uma pergunta sobre o que aparece nos Reels de alto engajamento para MPEs, comparando com
    Reels comuns, com os números da base e Reels reais de exemplo."""
    return _rodar("analisar", query, segment, faixa)


@mcp.tool
def recomendar(query: Annotated[str, Field(description="público ou objetivo das recomendações")],
               segment: Setor = None, faixa: Faixas = None) -> dict:
    """Recomenda como a @impulsostone deveria fazer Reels para um público ou objetivo, com o que fazer e o que
    evitar segundo a base, e Reels e perfis de referência."""
    return _rodar("recomendar", query, segment, faixa)


@mcp.tool
def gerar_criativo(query: Annotated[str, Field(description="que Reels são necessários: público, objetivo ou tema")],
                   segment: Setor = None, faixa: Faixas = None) -> dict:
    """Gera 3 criativos de Reels para a @impulsostone (gancho, roteiro em cenas, legenda, CTA e prompts de
    imagem), cada um com os achados e os Reels reais que o inspiraram. Leva de 1 a 2 minutos. Não gera imagens:
    para isso, passe o run_id da resposta e o número do criativo para gerar_imagens."""
    return _rodar("gerar_criativo", query, segment, faixa)


@mcp.tool
def gerar_imagens(run_id: Annotated[str, Field(description="run_id devolvido pelo gerar_criativo")],
                  criativo: Annotated[int, Field(ge=1, le=3, description="qual dos 3 criativos (1 a 3)")],
                  refazer: Annotated[bool, Field(description="gerar de novo imagens que já existem")] = False) -> dict:
    """Gera as imagens de um criativo do gerar_criativo: a capa 9:16 e uma imagem por cena, sempre com a mesma
    personagem (Cloudflare Workers AI). Cada imagem passa por um revisor com visão e, reprovada, ganha uma segunda
    versão. Devolve o caminho local de cada arquivo e a revisão (aprovada, nota de 0 a 10, problemas). Leva de 1 a
    2 minutos por criativo; imagens já geradas são reaproveitadas, salvo com refazer."""
    linha = registro.execucao(run_id)
    criativos = ((linha or {}).get("saida") or {}).get("creatives") or []
    if not criativos:
        raise ToolError(f"nenhum criativo encontrado para o run_id {run_id}")
    if criativo > len(criativos):
        raise ToolError(f"a execução tem {len(criativos)} criativos")
    dados_criativo = criativos[criativo - 1]
    feitas = imagens.revisoes(run_id)
    resultado, erros = [], []
    for indice in range(len(dados_criativo["roteiro"]) + 1):
        nome = "capa" if indice == 0 else f"cena {indice} ({dados_criativo['roteiro'][indice - 1]['tempo']})"
        destino = imagens.arquivo(run_id, criativo, indice)
        try:
            if destino.exists() and not refazer:
                revisao = feitas.get(destino.name)
            else:
                destino, revisao = imagens.gerar_do_criativo(run_id, criativo, indice, dados_criativo)
        except imagens.SemCredenciais as e:
            raise ToolError(f"geração de imagem indisponível: {e}")
        except Exception as e:  # Cloudflare fora do ar ou sem cota: sem capa, as cenas perdem a referência
            erros.append(f"{nome}: {e}")
            if indice == 0:
                break
            continue
        resultado.append({"imagem": nome, "arquivo": str(destino),
                          "aprovada": revisao["aprovada"] if revisao else None,
                          "nota": revisao["nota"] if revisao else None,
                          "problemas": revisao["problemas"] if revisao else []})
    return {"run_id": run_id, "criativo": criativo, "titulo": dados_criativo["titulo"],
            "pasta": str(imagens.PASTA / run_id), "imagens": resultado, "erros": erros}


@mcp.tool
def avaliar(roteiro: Annotated[str | None, Field(description="roteiro em texto, se ainda não houver vídeo")] = None,
            video_path: Annotated[str | None, Field(description="caminho local de um vídeo (mp4/mov)")] = None,
            segment: Setor = None) -> dict:
    """Avalia um vídeo (caminho local) ou um roteiro em texto da @impulsostone contra os padrões dos Reels de
    alto engajamento: pontos fortes, pontos a melhorar e o que não precisa mudar, com Reels de exemplo. Não
    prevê engajamento. Um vídeo leva de 1 a 3 minutos (transcrição local)."""
    entrada = {"mode": "avaliar", "query": "Avaliar pelo MCP", "segment": segment,
               "roteiro": roteiro, "video_path": video_path}
    return executar(entrada).model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
