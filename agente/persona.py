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

REGRAS_DADOS = """Regras sobre os dados:
- Use SÓ os achados, Reels e perfis fornecidos. Todo número que você escrever tem de estar em um achado.
  Não invente percentuais, Reels, perfis nem resultados.
- Selo de cada achado, a explicar em linguagem simples: "robusto" = diferença consistente entre top e controle;
  "fragil" = indício, apresente como hipótese a testar; "sem_diferenca" = top e controle têm proporção parecida,
  então isso não diferencia os Reels de alto engajamento; "insuficiente" = poucos Reels, não dá para afirmar.
- Não use a palavra "lift"; diga quantas vezes é mais (ou menos) comum no top, como vem nos achados.
- São padrões observados em Reels de alto engajamento, não garantia de resultado nem previsão.
- Para exemplificar um achado, use os Reels listados como "exemplos" daquele achado; não apresente um Reel
  como exemplo de uma característica que a lista não mostra que ele tem.
- Ao mencionar um Reel no texto, escreva o shortCode entre colchetes, ex.: [DbnuKRmRJ_H]. Não escreva no texto
  os ids dos achados (A1, A2...); eles vão só em achados_citados.
- Não confunda o retrato do top ("81% dos Reels do top mostram rosto") com a comparação ("e 89% dos Reels
  comuns também"): "aparece mais no top" só quando o top supera o controle com selo robusto ou fragil.
- Escreva números no padrão brasileiro: vírgula decimal (1,96) e porcentagem sem casas (32%)."""
