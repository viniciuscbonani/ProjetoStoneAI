"""Contrato do agente (seção 7 do documento do projeto): entrada e saída validadas com Pydantic.

Os nomes dos campos de primeiro nível seguem o documento (mode, query, segment, filters → findings,
reference_posts, creatives, confidence_flag, explanation). O modo "avaliar" e os campos avaliacao,
profiles e warnings são acréscimos do projeto.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Modo = Literal["analisar", "recomendar", "gerar_criativo", "avaliar"]
Segmento = Literal["alimentacao", "beleza", "varejo", "servicos"]
Faixa = Literal["micro", "medio", "grande"]
# robusto: diferença consistente; fragil: diferença que não se mantém no teste de sensibilidade;
# sem_diferenca: top e controle não se distinguem (IC95 do lift contém o 1); insuficiente: menos de 20 Reels no top.
Robustez = Literal["robusto", "fragil", "sem_diferenca", "insuficiente"]
Confianca = Literal["robusto", "fragil", "insuficiente"]


class Filtros(BaseModel):
    plataforma: Literal["instagram"] = "instagram"
    faixa: list[Faixa] | None = Field(None, description="tamanho do perfil: micro (até 10 mil), medio, grande")
    periodo_inicio: date | None = None
    periodo_fim: date | None = None


class Entrada(BaseModel):
    mode: Modo
    query: str = Field(min_length=3)
    segment: Segmento | None = Field(None, description="setor do empreendedor")
    filters: Filtros | None = None
    video_path: str | None = Field(None, description="vídeo a avaliar (modo avaliar)")
    roteiro: str | None = Field(None, description="roteiro em texto a avaliar, sem vídeo (modo avaliar)")


class Achado(BaseModel):
    campo: str
    valor: str
    descricao: str = Field(description="o achado em linguagem simples")
    freq_top: float
    freq_controle: float
    dif_pp: float
    lift: float | None
    ic95_min: float | None = None
    ic95_max: float | None = None
    n_top: int
    n_controle: int
    robustez: Robustez
    recorte: str | None = Field(None, description="ex.: segmento=alimentacao; vazio = amostra inteira")


class ReferencePost(BaseModel):
    shortCode: str
    url: str
    perfil: str
    faixa: Faixa
    seguidores: int
    curtidas: int
    comentarios: int
    visualizacoes: int
    taxa_engajamento: float = Field(description="(curtidas + comentários) ÷ seguidores; 0,05 = 5%")
    duracao_s: float
    publicado_em: str
    hook_texto: str
    categorias: dict[str, str | bool | int]
    motivo: str = Field(description="por que este Reel foi escolhido como referência")


class Perfil(BaseModel):
    perfil: str
    faixa: Faixa
    seguidores: int
    nicho: str
    n_top: int
    n_amostra: int
    tema_predominante: str
    formato_predominante: str
    taxa_mediana: float


class Cena(BaseModel):
    tempo: str = Field(description="ex.: 0–3 s")
    descricao: str = Field(description="o que se fala e o que aparece na cena")
    texto_na_tela: str = Field("", description="texto sobreposto ao vídeo, se houver")
    prompt_imagem: str = Field("", description="prompt (em inglês) para gerar uma imagem de referência da cena")


class Criativo(BaseModel):
    titulo: str
    formato: str
    duracao_alvo: str
    gancho: str = Field(description="o que se diz ou mostra nos primeiros 3 segundos")
    roteiro: list[Cena]
    legenda: str
    cta: str
    prompt_capa: str = Field("", description="prompt (em inglês) da capa vertical 9:16 do Reel")
    inspirado_em: list[str] = Field(description="shortCodes dos Reels de referência")
    achados_usados: list[str] = Field(description="achados aplicados, em linguagem simples")


class Ponto(BaseModel):
    texto: str
    achado: str = Field(description="campo=valor em que o ponto se apoia")
    robustez: Robustez
    referencias: list[str] = Field(default_factory=list, description="shortCodes")


class Avaliacao(BaseModel):
    leitura: dict[str, str | bool | int | float] = Field(description="como o agente leu o vídeo ou roteiro")
    pontos_fortes: list[Ponto]
    pontos_a_melhorar: list[Ponto]


class Saida(BaseModel):
    run_id: str
    mode: Modo
    findings: list[Achado]
    reference_posts: list[ReferencePost]
    creatives: list[Criativo] = Field(default_factory=list)
    avaliacao: Avaliacao | None = None
    profiles: list[Perfil] = Field(default_factory=list)
    confidence_flag: Confianca
    explanation: str
    warnings: list[str] = Field(default_factory=list)
