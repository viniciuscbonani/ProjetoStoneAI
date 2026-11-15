"""Rubrica de anotação dos Reels: esquema de saída do Gemini e prompt.

Baseada na rubrica do documento do projeto (seção 6.2), com os acréscimos da revisão de 14/11:
hipóteses da Stone (convite à participação, dor real x motivacional, data comemorativa), pilares
editoriais do @impulsostone, POV como formato e pessoa em cena. Duração, ritmo de cortes e
tamanho da legenda são calculados por código e não fazem parte deste esquema.
"""

from typing import Literal

from pydantic import BaseModel, Field

# v2 (piloto de 14/11): "explicativo" separado de tutorial; pilar/tema "outro" para conteúdo que não
# fala de negócio; convite à participação separado de CTA de comentar; "comenta X que eu mando" = comentar.
VERSAO = "v2"


class Anotacao(BaseModel):
    # Formato
    formato_video: Literal["talking_head", "tutorial", "explicativo", "bastidores", "antes_depois",
                           "humor_esquete", "depoimento", "lista_dicas", "trend", "pov", "vlog_lifestyle", "outro"]
    fala_de_negocio: bool = Field(description="o conteúdo é sobre empreender, vender, gerir ou o próprio negócio")
    # Gancho (primeiros 3 segundos)
    hook_texto: str = Field(description="o gancho em até 15 palavras, falado ou escrito na tela")
    tipo_hook: Literal["pergunta", "promessa", "dor", "numero", "polemica", "curiosidade", "nenhum"]
    hook_visual: Literal["rosto", "texto_na_tela", "produto_resultado", "acao", "nenhum"]
    forca_hook_0a10: int
    # Tema
    tema_principal: Literal["vendas", "financas", "marketing", "atendimento", "gestao", "motivacao",
                            "ferramentas_maquininha", "historia_de_empreendedor", "outro"]
    pilar_impulso: Literal["educacao_financeira", "gestao_e_vendas", "historias_reais", "especialistas",
                           "comunidade", "outro"]
    segmento_publico: Literal["alimentacao", "beleza", "varejo", "servicos", "geral"]
    # Pessoas
    tem_rosto: bool
    pessoa_em_cena: Literal["mulher", "homem", "ambos", "ninguem"]
    criador_e_empreendedor_real: bool
    prova_social: bool
    # Texto e linguagem
    texto_na_tela: bool
    tom: Literal["informal", "tecnico", "inspiracional", "humoristico"]
    usa_linguagem_regional: bool
    clareza_mensagem_0a10: int
    # Conversão
    tem_cta: bool
    tipo_cta: Literal["comentar", "salvar", "compartilhar", "link_na_bio", "dm", "seguir", "outro", "nenhum"]
    oferta_ou_beneficio_explicito: bool
    # Hipóteses da Stone
    convite_participacao: bool
    abordagem: Literal["dor_real", "motivacional_generica", "ambos", "nenhum"]
    data_comemorativa: str = Field(description="nome da data (ex.: festa junina, dia das mães) ou 'nenhuma'")
    # Síntese
    elementos_top5: list[str] = Field(description="até 5 elementos, em poucas palavras cada")


PROMPT = """Você é um analista de conteúdo para micro e pequenos empreendedores (MPEs) no Instagram.
Analise UM Reel a partir da legenda, da transcrição do áudio e de quadros extraídos em instantes
conhecidos (gancho = primeiros 3 segundos; meio; final). Responda somente com o JSON pedido.

Definições:
- formato_video: talking_head = pessoa falando para a câmera, opinião ou conselho; tutorial = passo a
  passo prático que ensina a FAZER algo (receita, técnica, configuração); explicativo = explica um
  conceito ou fenômeno (por que algo acontece), com narração ou texto, sem passo a passo; bastidores =
  rotina/produção do negócio; antes_depois; humor_esquete; depoimento = cliente ou terceiro relata
  experiência; lista_dicas = "3 dicas", "5 erros"; trend = áudio ou formato viral; pov = "POV: ...";
  vlog_lifestyle = dia a dia, família, momentos pessoais.
- fala_de_negocio: false para conteúdo pessoal, de humor ou lifestyle que não trata de empreender.
  Nesse caso use tema_principal = outro e pilar_impulso = outro.
- tipo_hook: como os primeiros 3 segundos prendem a atenção. dor = nomeia um problema real do
  empreendedor ("seu dinheiro some no fim do mês"); promessa = resultado ("venda mais com..."); numero =
  começa com número/lista; nenhum = não há gancho claro.
- hook_visual: o que domina o primeiro quadro.
- forca_hook_0a10: quão forte o gancho é para um MPE parar de rolar o feed.
- pilar_impulso: educacao_financeira (precificação, custos, caixa, lucro); gestao_e_vendas
  (atendimento, pós-venda, estratégias comerciais); historias_reais (trajetórias, desafios,
  conquistas); especialistas (oficinas, mentorias, orientação de especialista); comunidade
  (convites, interação, oportunidades).
- segmento_publico: para qual tipo de negócio o conteúdo fala; geral = qualquer empreendedor.
- criador_e_empreendedor_real: quem fala tem um negócio próprio real (não é só influenciador/marca).
- prova_social: mostra resultado, depoimento, número de clientes ou faturamento.
- tem_cta / tipo_cta: chamada explícita para uma ação (falada, na tela ou na legenda). "Comenta X que
  eu te mando o link" conta como comentar, não como dm.
- convite_participacao: convida o empreendedor a PARTICIPAR de algo — programa, evento, comunidade,
  pesquisa, desafio (ex.: "Empreendedor(a), queremos te ouvir", "inscreva-se"). Pedir para comentar,
  curtir ou seguir NÃO é convite à participação; isso é CTA.
- abordagem: dor_real = problema concreto e específico; motivacional_generica = frase de efeito sem
  orientação prática ("vender mais não é sorte"); ambos; nenhum.
- usa_linguagem_regional: gírias ou expressões claramente regionais.
- Se não houver transcrição (Reel sem fala), baseie-se nos quadros e na legenda.
"""
