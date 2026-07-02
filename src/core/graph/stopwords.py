"""Stopwords PT/EN para o extrator de conceitos (Fase 2).

Listas compactas embutidas (sem dependência externa). Comparações são feitas
sobre termos normalizados (casefold + sem acentos) — por isso as palavras aqui
estão sem acento.
"""

STOPWORDS_PT = frozenset("""
a as o os um uma uns umas ao aos aa aas da das do dos na nas no nos num numa
nuns numas pela pelas pelo pelos dum duma
de em por para com sem sob sobre entre ate apos desde contra perante trás tras
e ou mas nem que se ja tambem porem todavia contudo entretanto portanto pois
porque quando enquanto embora caso onde como quanto quanta quantos quantas
qual quais quem cujo cuja cujos cujas
eu tu ele ela nos vos eles elas voce voces
me te lhe lhes mim ti si nosso nossa nossos nossas meu minha meus minhas
teu tua teus tuas seu sua seus suas dele dela deles delas
este esta estes estas esse essa esses essas aquele aquela aqueles aquelas
isto isso aquilo mesmo mesma mesmos mesmas outro outra outros outras
tal tais tanto tanta tantos tantas todo toda todos todas algum alguma alguns
algumas nenhum nenhuma cada qualquer quaisquer varios varias muito muita
muitos muitas pouco pouca poucos poucas mais menos bem mal so apenas ainda
ser estar ter haver fazer ir vir poder dever querer dizer ver dar saber ficar
e sao era eram foi foram sera serao seria seriam sendo sido
esta estao estava estavam esteve estiveram estara sendo
tem tinha tinham teve tiveram tera terao tendo tido ha havia
faz fazia fez feito vai vao foi ia iam indo ido vem vinha veio vindo
pode podia pode puderam podera podendo podido deve devia devem devendo devido
quer queria quis querem querendo diz dizia disse dizem dizendo dito
ve via viu veem vendo visto da dava deu dao dando dado sabe sabia soube sabem
fica ficava ficou ficam ficando ficado
nao sim la ali aqui ai acola agora antes depois sempre nunca jamais logo cedo
tarde hoje ontem amanha entao assim talvez quase apos
seja sejam fosse fossem for forem sera tambem etc
""".split())

STOPWORDS_EN = frozenset("""
a an the and or but nor so yet for of in on at by to from with without under
over between among through during before after above below up down out off
again further then once here there when where why how what which who whom
whose that this these those it its it's is are was were be been being am
have has had having do does did doing will would shall should may might must
can could ought i you he she we they me him her us them my your his their our
mine yours hers ours theirs myself yourself himself herself itself ourselves
themselves each every either neither some any no not only own same other
another such as if than too very just about against because until while all
both few more most much many little less least own s t don now
get gets got getting go goes went going gone make makes made making come
comes came coming take takes took taking see sees saw seen seeing know knows
knew known knowing think thinks thought thinking say says said saying
also however therefore thus hence moreover furthermore meanwhile instead
etc eg ie via per
""".split())

STOPWORDS = STOPWORDS_PT | STOPWORDS_EN
