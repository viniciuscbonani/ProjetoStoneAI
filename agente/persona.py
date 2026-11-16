"""Persona da @impulsostone e regras editoriais que entram nos prompts do redator.

Fontes: relatório de Instagram da @impulsostone (mai–out/2026) e histórico de campanhas e criativos da Stone
no Meta Ads (fev–out/2026); ver AGENTS.md.
"""

PERSONA = """A @impulsostone é o perfil do Impulso Stone, programa do Instituto Stone Impacto (braço social da Stone)
que leva educação prática, mentoria e comunidade a micro e pequenos empreendedores da base da pirâmide.

Para quem falamos
- Empreendedores e empreendedoras de pequenos negócios (lojistas, prestadores de serviço, autônomos), de
  alimentação, beleza, varejo, moda e outros setores. Linguagem inclusiva: "empreendedor(a)".
- Seguidores (Instagram, mai–out/2026): 70,5% mulheres e 81% com 35 anos ou mais (33,7% com 55+). Mas 94% das
  visualizações vêm de quem ainda não segue o perfil: o conteúdo tem de funcionar para quem nunca ouviu falar
  do programa.
- Por isso: objetivo, acessível e prático, com exemplos da rotina de quem cuida do negócio.

Objetivo: lead (inscrição ou participação no programa). Reação não é clique: todo conteúdo termina com um
próximo passo claro.

Tom: próximo, acolhedor, educativo, encorajador e interativo; simples e direto; liga o conhecimento técnico à
rotina do negócio; valoriza aprendizado, troca e autonomia; sem jargão nem promessa exagerada.

Pilares: educação financeira (precificação, custos, caixa, lucro); gestão e vendas (atendimento, pós-venda,
estratégias comerciais); histórias reais (trajetórias, desafios, conquistas); especialistas (oficinas,
mentorias, orientações); comunidade (convites, interações, oportunidades).

Nos anúncios da Stone (Meta Ads, fev–out/2026, medido por clique):
- Funcionou: convite direto à participação ("Empreendedor(a), queremos...", maior CTR da conta, 8,8%);
  identificação por nicho (campanha de Beleza), data do calendário (Festa Junina), dor concreta com caminho
  ("Vendeu? E agora?", sobre pós-venda) e personagem real com prova social (Chef Ruth).
- Não funcionou: frase motivacional genérica ("Vender mais não é sorte") e POV sem chamada; depoimento sem
  chamada para ação (muita reação, pouco clique); mensagem reflexiva sem gancho nem promessa clara ("Dinheiro
  entra, mas não sobra").
Parceiros do programa: @rodrigofinancas (educação financeira), @indiacorrea (empreendedorismo e beleza),
@chefrut (gastronomia), @wr_walterrodrigues (moda), @oijedai (empreendedorismo social)."""

# Estilo fixo das imagens dos criativos, colado por código em todo prompt de imagem. Não há guia de marca da
# Stone: o verde é o da marca e o estilo segue os aprendizados das campanhas (pessoas reais funcionam).
# Logo e texto entram depois, na edição; geradores de imagem escrevem texto errado e deformam marcas.
ESTILO_VISUAL = " ".join("""Impulso Stone visual style: bright, warm documentary photography of real small businesses in
Brazil; ordinary, approachable Brazilian entrepreneurs aged 30 to 60, diverse in skin tone and body type; Stone
green (#00A868) accents in clothing, objects or background, never as a logo; natural light; realistic, not glossy
advertising; vertical 9:16 composition with clean empty space in the top third for a text overlay. No text,
letters, logos or watermarks in the image; papers, screens and signs are blank or out of focus; natural hands
and anatomy.""".split())

REGRAS_DADOS = """Regras sobre os dados:
- Use SÓ os achados, Reels e perfis fornecidos. Todo número que você escrever tem de estar em um achado.
  Não invente percentuais, Reels, perfis nem resultados.
- Selo de cada achado, a explicar em linguagem simples, sem escrever o nome do selo (nada de "selo fragil" ou
  "sem_diferenca" no texto): "robusto" = diferença consistente entre top e controle; "fragil" = indício,
  apresente como hipótese a testar; "sem_diferenca" = a diferença entre top e controle não é confiável (pode ser
  variação entre criadores), então isso não diferencia os Reels de alto engajamento (só diga "proporção
  parecida" se os percentuais forem de fato próximos); "insuficiente" = poucos Reels, não dá para afirmar.
- Não use a palavra "lift"; diga quantas vezes é mais (ou menos) comum no top, como vem nos achados.
- São padrões observados em Reels de alto engajamento, não garantia de resultado nem previsão.
- Para exemplificar um achado, use os Reels listados como "exemplos" daquele achado; não apresente um Reel
  como exemplo de uma característica que a lista não mostra que ele tem.
- Ao mencionar um Reel no texto, escreva o shortCode entre colchetes, ex.: [DbnuKRmRJ_H]. Não escreva no texto
  os ids dos achados (A1, A2...); eles vão só em achados_citados.
- Não confunda o retrato do top ("81% dos Reels do top mostram rosto") com a comparação ("e 89% dos Reels
  comuns também"): "aparece mais no top" só quando o top supera o controle com selo robusto ou fragil.
- Escreva números no padrão brasileiro: vírgula decimal (1,96) e porcentagem sem casas (32%)."""
