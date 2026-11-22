"""Récits historiques retranscrits dans l'histoire tellurienne (Auteur, 22/11/2026).

Des livres écrits par des figures historiques de la Terre, ramenés au monde de Telluris
(portails, mana, cristaux, monstres, cités), chacun écrit À LA MANIÈRE de son auteur —
pastiche cryptique plutôt que résumé : le titre et l'auteur disent le sujet, le texte le
voile. Deux lots :
- `OUVRAGES` : vingt-quatre livres seuls ;
- `CONTROVERSES` : des paires d'auteurs aux théories opposées sur ce que l'histoire de
  Telluris laisse ambigu (la Vague, l'origine des monstres, le portail devenu donjon, Arthur,
  la lycanthropie, le sang premier, le vrykolakas, Méduse). Aucune ne tranche.

Lecture seule, aucun bonus : la description EST le livre. Tag `ouvrage_historique` = un
« récit », plafonné en rayon (`utils/recits.py`, `RECITS_PLAFOND`). Recette
`lieu_categorie: "scriptorium"`, reprise par `grand_scriptorium`, `bibliotheque` et
`grande_bibliotheque` (`LIEU_CATEGORIES_FUSION`), au prix des grimoires : 3 papier + 2 encre +
1 pigment. Sous-catégorie `ouvrage` : ni grimoire (n'enseigne rien), ni livre de contenu du
scriptorium (non scellé en vitrine).

Écrit aussi les tenanciers génériques `pnj:marchand_bibliotheque` et
`pnj:marchand_grande_bibliotheque`, CLONÉS de `pnj:marchand_grand_scriptorium` relu au dump
(même machinerie de dialogue et de services), nom / race / portrait / accueil propres.

Sortie : jsons/ouvrages_historiques_a_importer.json — le DELTA contre le dump le plus récent
(un doc identique en base n'est pas réémis). Refuse un `_id` déjà pris par un doc étranger.
"""
import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "ouvrages_historiques_a_importer.json")
sys.path.insert(0, RACINE)

from dev.gen_marchands import METIERS  # noqa: E402

TAG = "ouvrage_historique"

# Matières : la signature des grimoires (dev/gen_grimoires_sans_plume.py).
MATIERES = [
	{"item": "item:Papier", "quantite": 3},
	{"item": "item:Encre", "quantite": 2},
	{"item": "item:pigment", "quantite": 1},
]

# (slug, nom, icône, texte à la manière de l'auteur)
OUVRAGES = [
	# ── Origines et histoire du monde ────────────────────────────────────────
	("celui_qui_a_vu_l_abime", "« Celui qui a vu l'abîme » — Sîn-lēqi-unninni", "📜",
	 "Celui qui a vu l'abîme, je veux le faire connaître au pays ; celui qui a su toutes choses, qu'on se souvienne de lui. Il a vu le secret, il a découvert le caché, il a rapporté un récit d'avant le Déluge. "
	 "Monte sur la muraille d'Uruk et promène-toi : éprouve la brique, regarde les fondations. Ce qui rôdait dehors n'a pas franchi ce que sa main a levé. "
	 "Il chercha la vie qui ne finit pas, et trouva Utnapishtim, le lointain, qui avait traversé les eaux. « Ce qui vint sur nous, je l'appelle eau, dit le vieil homme, car je n'ai pas d'autre mot. »"),
	("enquetes_herodote", "« Enquêtes » — Hérodote d'Halicarnasse", "📕",
	 "Hérodote d'Halicarnasse présente ici les résultats de son enquête, afin que le temps n'abolisse pas les travaux des hommes, ni les murailles qu'ils ont dressées contre ce qui rôde. "
	 "Les prêtres de Babylone m'ont dit que les bêtes couraient les routes avant qu'aucune porte ne fût ouverte ; les Égyptiens disent la même chose, mais plus tôt. "
	 "Pour moi, je dois rapporter ce que l'on dit, mais je ne suis nullement tenu de le croire ; et que cette parole vaille pour tout mon récit."),
	("vie_de_charles", "« Vie de Charles » — Éginhard", "📕",
	 "Je n'ai pas cru devoir taire la vie d'un tel homme, moi qui lui dois tout, de peur qu'un plus ignorant que moi ne l'écrive plus mal. "
	 "Il était d'une taille élevée sans excès, la voix claire, et il ne franchissait jamais une porte qu'il n'eût d'abord vu franchir par d'autres, revenus. Un siècle après la grande couleur des portes, il fit d'Aix le nœud de ses chemins. "
	 "De ce qu'il fit entendre aux Architectes dans ses bains, je ne dirai rien : je ne l'ai pas compris."),
	("muqaddima", "« Muqaddima » — Ibn Khaldoun", "📕",
	 "Sache que la cité est naturelle à l'homme, car seul il ne survit pas une nuit hors des murs. "
	 "Sache encore que les murs ne tiennent que par la solidarité de ceux qui les ont levés ; à la troisième génération, on entretient la porte sans savoir pourquoi, et à la quatrième on cesse de payer les cristaux. "
	 "Les cités ne se combattent pas : elles s'usent. Et celui qui croit voir tomber une ville sous un coup ne voit que la dernière pierre d'une chute commencée chez ses arrière-grands-pères."),
	# ── Portails, mana et cristaux ───────────────────────────────────────────
	("abrege_du_calcul_des_seuils", "« Abrégé du calcul des seuils » — al-Khwārizmī", "📘",
	 "Lorsque tu veux connaître le lieu où mène une porte, prends le nombre des tours de la corde, et retranches-en ce qui revient ; ce qui reste, compare-le à la mesure du cercle. "
	 "J'ai composé ce bref ouvrage sur ce qui est facile et ce qui est noble dans le calcul des seuils, afin que l'on ne soit plus contraint de se fier à la mémoire des anciens. "
	 "Si le résultat ne mène nulle part, ce n'est pas le calcul qui ment, c'est que l'on a mal compté les tours. Ou bien la porte n'est pas de leur main."),
	("traite_d_optique", "« Traité d'optique » — Ibn al-Haytham", "📘",
	 "Celui qui étudie les livres des savants, s'il cherche la vérité, doit se faire l'ennemi de tout ce qu'il lit, et se suspecter lui-même tandis qu'il l'examine. "
	 "La lumière va en ligne droite ; nous l'avons éprouvé par le trou de la chambre obscure. La couleur d'une porte n'est donc pas un caprice : quelque chose, au jour de la grande Vague, s'est placé entre l'œil et le seuil. "
	 "Et si la lumière va droit sans jamais dévier, un trait assez pur la suivrait, et rien sur sa ligne ne lui résisterait."),
	("des_mineraux", "« Des minéraux » — Albert le Grand", "📘",
	 "Nous disons donc, après avoir éprouvé la chose nous-même et non sur la foi d'autrui, qu'il est deux pierres de mana dont la vertu s'oppose : la violette, qui pousse, et la jaune, qui retient. "
	 "Les unes se tirent des mines qui dorment derrière les portes changées ; les autres du ventre des bêtes, ce qui fait dire aux simples que la bête a mangé la pierre, et aux philosophes que la pierre a fait la bête. "
	 "De ces deux opinions, nous ne déciderons pas ici ; il suffit que l'on ne confonde jamais la violette et la jaune."),
	("lettre_sur_l_aimant", "« Lettre sur l'aimant » — Pierre de Maricourt", "📜",
	 "Très cher ami, à ta demande je t'écris en peu de mots la nature occulte de la pierre d'aimant, qui est connue de peu et que l'expérience seule enseigne. "
	 "Sache que l'aiguille frottée, posée sur l'eau dans un vase de bois, cherche le pôle ; mais qu'aux abords de certains lieux elle tremble, tourne et ne sait plus où se fixer. "
	 "Là où elle s'affole, creuse, ou attends : une porte y dort, ou va s'y éveiller. Je ne t'en dirai pas davantage, car je n'en sais pas davantage."),
	# ── Bêtes, plantes et corps ──────────────────────────────────────────────
	("histoire_naturelle", "« Histoire naturelle » — Pline l'Ancien", "📗",
	 "J'ai rassemblé vingt mille faits dignes d'attention, tirés de cent auteurs ; j'en ai ajouté beaucoup que les anciens ignoraient. "
	 "On rapporte qu'au-delà des murs vivent des bêtes dont le ventre porte une pierre de couleur ; on rapporte aussi qu'elles naissent de la pierre. Je l'écris comme on me l'a dit. "
	 "Rien n'est plus sûr que l'incertain, et rien n'est plus misérable ni plus orgueilleux que l'homme qui se croit à l'abri derrière son rempart."),
	("physica", "« Physica » — Hildegarde de Bingen", "📗",
	 "L'herbe qui croît au pied des remparts est tempérée ; celle qui croît au bord d'une porte est chaude et sèche, car elle a bu le souffle de l'autre côté. "
	 "Que celui dont le mana s'épuise prenne de la sauge qui n'a pas vu de seuil, qu'il la cuise dans le vin, et il retrouvera sa verdeur. "
	 "Mais qu'il se garde de la même sauge cueillie près d'une porte changée : elle guérit le jour et ronge la nuit. Ainsi l'ai-je vu, et non par les yeux du corps."),
	("canon_de_la_medecine", "« Canon de la médecine » — Ibn Sīnā (Avicenne)", "📗",
	 "La médecine est l'art par lequel on connaît les états du corps, afin de conserver la santé quand elle est là et de la rendre quand elle s'en va. "
	 "Du venin des grands serpents, il faut savoir qu'il est de deux sortes : celui qui court au cœur et celui qui court au mana ; le premier se lie, le second ne se lie pas. "
	 "Le paladin referme la plaie ; il ne chasse pas le venin. Que le malade ne s'en remette pas à la seule prière : il en mourrait guéri."),
	("otia_imperialia", "« Otia imperialia » — Gervais de Tilbury", "📗",
	 "Pour le délassement de votre altesse, j'ai recueilli les merveilles que j'ai vues de mes yeux ou apprises de témoins sûrs, laissant au lecteur prudent le soin de trier. "
	 "Nous avons vu en notre temps des hommes changés en loups à la lune nouvelle, et qui couraient le garou par trois paroisses avant l'aube ; quand on les appelait par leur nom, ils redevenaient hommes, et pleuraient. "
	 "De la bête qui dévasta le Gévaudan, les uns disent loup, les autres non. Je n'étais pas là."),
	# ── Voyages et géographie ────────────────────────────────────────────────
	("devisement_du_monde", "« Le Devisement du monde » — Marco Polo", "📙",
	 "Seigneurs, empereurs et rois, ducs et marquis, comtes, chevaliers et bourgeois, et toutes gens qui voulez savoir les diverses générations des hommes et les diversités des cités du monde, prenez ce livre et le faites lire. "
	 "Et sachez qu'au-delà de la dernière auberge-relais il y a une porte que les gens du lieu ne nomment pas, et qu'ils ne passent qu'avec un cristal dans la bouche. "
	 "Je n'ai pas écrit la moitié de ce que j'ai vu ; car qui l'aurait cru ?"),
	("rihla", "« Rihla » — Ibn Baṭṭūta", "📙",
	 "Je partis seul, sans compagnon dont je pusse goûter la société, ni caravane à laquelle me joindre, poussé par un désir longtemps caché dans mon cœur de voir les cités illustres. "
	 "J'appris à juger une ville à la hauteur de ses murs, et ses habitants à la façon dont ils ouvrent la porte au voyageur après le coucher du soleil. "
	 "Dans un monastère-relais, un vieillard me dit : « Tu verras trois mers et tu n'en traverseras aucune. » Il se trompait d'une."),
	("geographie_ptolemee", "« Géographie » — Claude Ptolémée", "📙",
	 "La géographie est l'imitation, par le dessin, de toute la partie connue de la terre et de ce qui s'y rattache. "
	 "Nous avons placé les cités selon leurs distances, mesurées par les routes et non par les portes, car une porte ne dit pas où elle est, seulement où elle mène. "
	 "Au-delà de la limite tracée, nous laissons la carte blanche : non qu'il n'y ait rien, mais nul n'en est revenu avec une mesure."),
	("machines_de_rempart", "« Des machines de rempart » — Archimède de Syracuse", "📘",
	 "Certains pensent, roi Hiéron, que la mer ne se peut repousser, et que ce qui en sort est en nombre infini. Je vais te montrer qu'il n'en est rien. "
	 "Que l'on dresse sur le mur une griffe de fer au bout d'un levier, et le plus grand des serpents sera soulevé hors de l'eau par la seule force d'un enfant ; que l'on dispose les boucliers polis selon la courbe que je décris, et la pieuvre brûlera avant d'atteindre le quai. "
	 "Donne-moi un point d'appui sur le rempart, et je repousserai la mer."),
	# ── Savoirs et pensée ────────────────────────────────────────────────────
	("la_caverne", "« La Caverne » — Platon", "📜",
	 "— Représente-toi des hommes dans une demeure souterraine, enchaînés depuis l'enfance, qui ne voient que des ombres sur la paroi. — Je me les représente, dit Glaucon. "
	 "— Si l'un d'eux était délivré et contraint de regarder la lumière, puis redescendait, ne dirait-on pas qu'il est revenu les yeux gâtés ? Et s'il voulait délier les autres, ne le tueraient-ils pas, s'ils le pouvaient ? "
	 "— Assurément. — Il ne pourrait donc leur parler qu'en ombres, lui aussi ; et ce serait encore trop."),
	("critias", "« Critias » — Platon", "📜",
	 "Écoute donc, Socrate, une histoire fort étrange et pourtant vraie de tout point. Au-delà des colonnes, il y avait une île, et le dieu de la mer en traça lui-même les anneaux, de terre et d'eau, si bien que nul n'y pouvait venir que par la mer. "
	 "Le mur extérieur était tout entier revêtu d'orichalque, qui jetait des feux comme du feu. Et quand vint le voyageur qui ouvrait les portes, ils le renvoyèrent. "
	 "On dit qu'elle a sombré. On le dit aussi d'une autre. Les marins rient, et je ne sais lesquels ont raison."),
	("commentaire_averroes", "« Commentaire » — Ibn Rushd (Averroès)", "📕",
	 "Le Philosophe dit que tout ce qui se meut est mû par autre chose. Nous disons, en commentant : il en va ainsi du mana, qui ne coule pas sans pente. "
	 "Ceux qui veulent que la magie soit sans règle ne font que donner un nom à leur ignorance. Ce que l'on n'a pas encore mesuré n'est pas pour autant sans mesure. "
	 "Et si l'on nous objecte les portes qui changent de couleur sans raison, nous répondrons : sans raison connue de toi."),
	("gloses_bernard_de_chartres", "« Gloses » — Bernard de Chartres", "📕",
	 "Nous sommes des nains assis sur des épaules de géants : nous voyons plus loin qu'eux, non par l'acuité de notre vue, mais parce qu'ils nous portent. "
	 "Glose : le premier sut faire la porte ; le second sut l'entretenir ; le troisième sut qu'il fallait l'entretenir ; le quatrième se souvint qu'il y avait une porte. "
	 "Glose sur la glose : le cinquième, c'est toi, qui lis ceci, et qui crois être le premier."),
	# ── Légendes et cités ────────────────────────────────────────────────────
	("histoire_des_rois_de_bretagne", "« Histoire des rois de Bretagne » — Geoffroy de Monmouth", "📙",
	 "En ce temps-là, quand les portes de l'île eurent changé de couleur, Arthur, jeune encore, prit la couronne et bâtit Camelot au carrefour de ce qui débordait. "
	 "Douze fois les collines se vidèrent, et douze fois il les fit rentrer ; et ce n'étaient pas des hommes qui en sortaient, c'est pourquoi l'on se souvient de ceux qui les arrêtèrent. "
	 "Et Merlin prophétisa : « Le dragon blanc dormira sous la pierre, le rouge sous l'eau, et le roi ni sous l'une ni sous l'autre. » Après Camlann, on le porta dans l'île d'Avalon pour y guérir. On attend encore."),
	("edda", "« Edda » — Snorri Sturluson", "📙",
	 "Gangleri demanda : « Où est le lieu principal, le sanctuaire ? » Hár répondit : « C'est au frêne. Ses branches s'étendent sur tous les mondes, et chaque porte qu'il ouvre est une demeure dont on ne revient pas les mains vides, ni toujours. » "
	 "Gangleri demanda : « Et qui garde les hommes du Nord ? » « Ceux qui portent la peau du loup et chassent pour les deux cités, et qui ne la brûlent jamais. » "
	 "Puis Gangleri entendit un grand bruit, et il se trouva seul dans une plaine, sans halle ni frêne."),
	("lais_marie_de_france", "« Lais » — Marie de France", "📙",
	 "Puisque de lais faire je m'entremets, / Je ne veux oublier Bisclavret ; / Bisclavret a nom en bretonne langue, / Garou l'appellent les Normands. "
	 "Trois jours la semaine il s'en allait, / Nul ne savait où il passait ; / Ses vêtements sous la pierre creuse, / Sans eux jamais homme ne redevenait. "
	 "D'autres lais disent la colline ouverte, / La dame qui passe et ne revient, / Le chevalier qui la suit de nuit : / Ce que j'ai ouï, je le retiens."),
	("cite_des_dames", "« La Cité des dames » — Christine de Pizan", "📕",
	 "Comme j'étais un jour assise en mon étude, environnée de maints volumes de diverses matières, trois dames m'apparurent et me dirent : « Prends la truelle de ton entendement, et creuse : les fondations sont prêtes. » "
	 "La première pierre, je la posai au nom de celle qui garda seule la porte d'une cité pendant que les hommes dormaient ; la deuxième au nom de celle qui leva le premier mur ; la troisième, je la laisse vide. "
	 "Que celle qui la mérite vienne la prendre."),
]

# Paires d'auteurs aux théories opposées : (sujet, [(slug, nom, icône, texte), …])
CONTROVERSES = [
	("La nature de la Vague", [
		("incoherence_des_architectes", "« L'Incohérence des Architectes » — al-Ghazālī", "📕",
		 "Les Architectes prétendent que la porte a changé de couleur parce qu'elle était mal entretenue, comme le coton brûle parce que le feu le touche. Nous disons : le coton brûle quand le feu le touche, non parce qu'il le touche. "
		 "Rien n'obligeait la porte. Ce qui l'a changée l'a voulu, au moment où il l'a voulu, et l'aurait pu ne pas le vouloir. "
		 "Qu'on cesse donc de chercher la cause de la Vague dans la pierre et le cristal : on ne trouvera que l'habitude d'avoir vu deux choses ensemble."),
		("incoherence_de_l_incoherence", "« L'Incohérence de l'incohérence » — Ibn Rushd (Averroès)", "📕",
		 "Nier les causes, c'est nier la raison, et nier la raison, c'est rendre la science des portes impossible. Celui qui dit que le feu ne brûle pas le coton n'a jamais tenu le coton. "
		 "La Vague a une cause, comme toute chose qui arrive ; que nous l'ignorions ne prouve rien contre elle, et beaucoup contre nous. "
		 "Notre adversaire a dit l'incohérence des Architectes ; nous dirons l'incohérence de son livre, et nous attendrons qu'on trouve ce qu'il a défendu de chercher."),
	]),
	("L'origine des monstres", [
		("de_la_nature_empedocle", "« De la nature » — Empédocle d'Agrigente", "📜",
		 "Sur la terre poussaient maintes têtes sans cou, des bras erraient nus, privés d'épaules, des yeux vaguaient seuls, cherchant un front. "
		 "Quand l'Amour du mana les joignit au hasard, il en naquit des bêtes à double face et des bœufs à tête d'homme ; ce qui put vivre vécut, et rôde encore hors des murs. "
		 "Ne cherche pas qui les a voulus : personne. La Haine défait ce que l'Amour assemble, et ce qui reste, nous l'appelons monstre."),
		("generation_des_monstres", "« De la génération des monstres » — Aristote", "📕",
		 "Le monstre appartient aux choses contraires à la nature, non à la nature tout entière, mais à celle qui se produit le plus souvent. "
		 "Ceux qui disent, comme Empédocle, que les bêtes du dehors sont des membres joints au hasard se trompent : le hasard ne fait pas d'espèce qui se reproduit, et ces bêtes en font. "
		 "Le monstre est une nature qui visait juste et a manqué sa cible ; reste à savoir ce qui a fait trembler la main."),
	]),
	("Ce qui change un portail en donjon", [
		("sic_et_non_des_seuils", "« Sic et non des seuils » — Pierre Abélard", "📕",
		 "Les uns disent que la porte devient demeure parce qu'on l'a mal bâtie ; les autres, parce qu'on l'a trop bien bâtie. Les uns, qu'elle s'ouvre sur ce qui était déjà là ; les autres, qu'elle le crée en s'ouvrant. "
		 "J'ai rangé ici ces sentences contraires sans les accorder, afin que le lecteur s'exerce. "
		 "Car c'est en doutant que nous venons à la recherche, et en cherchant que nous trouvons la vérité. Celui qui ne doute pas d'une porte y entrera sans en sortir."),
		("lettre_contre_les_sondeurs", "« Lettre contre les sondeurs de seuils » — Bernard de Clairvaux", "📜",
		 "Il y a un homme qui scrute ce qui ne se scrute pas, qui dispute des portes comme d'une syllabe, et qui prétend tout comprendre par la raison. Qu'il descende donc dans le seuil qu'il dispute. "
		 "Ce qui change une porte en demeure n'est pas fait pour être compris, mais pour être gardé ; on le sait en veillant, non en lisant. "
		 "Crois-en celui qui l'a éprouvé : tu trouveras plus dans les forêts que dans les livres, et plus au pied de la muraille que dans les deux."),
	]),
	("Arthur, Merlin et Avalon", [
		("histoire_des_choses_anglaises", "« Histoire des choses de l'île » — Guillaume de Newburgh", "📕",
		 "Un certain écrivain, de nos jours, a tissé sur Arthur des fables risibles, et les a revêtues du nom honorable d'histoire. "
		 "Qu'Arthur ait bâti Camelot et repoussé ce qui débordait des collines, je l'accorde : les pierres le disent. Mais qu'il dorme dans une île, guéri par des dames, et doive revenir, c'est ce que les vieilles femmes racontent aux enfants. "
		 "Quant à Merlin, il a prophétisé tant de choses qu'il était forcé d'en voir arriver quelques-unes."),
	]),
	("La lycanthropie", [
		("demonomanie_des_lycanthropes", "« De la démonomanie des lycanthropes » — Jean Bodin", "📕",
		 "Ayant siégé aux procès, j'ai vu des accusés confesser sans torture qu'ils s'étaient frottés d'un onguent et avaient couru sous peau de loup. "
		 "La chose est volontaire : on ne devient pas loup par mélancolie, on le devient par art, et l'art s'apprend, se transmet et se paie. "
		 "Ceux qui veulent n'y voir qu'une maladie ôtent au juge son office et au loup sa faute."),
		("des_prestiges", "« Des prestiges » — Johann Weyer", "📗",
		 "J'ai visité, comme médecin, ceux que l'on dit loups ; j'ai trouvé des hommes pâles, aux yeux creux, aux jambes écorchées par les ronces, et qui hurlaient la nuit dans les cimetières. "
		 "Les Grecs nommaient ce mal lycanthropie ; c'est une humeur noire, ou un esprit de bête qui prend l'homme quand l'homme faiblit, et non un métier qu'on choisit. "
		 "Qu'on les soigne, et qu'on cesse de les brûler : la bête qu'on brûle ne meurt pas avec eux."),
	]),
	("Le sang premier", [
		("traite_sur_les_revenants", "« Traité sur les revenants » — Dom Augustin Calmet", "📕",
		 "Je me suis proposé de rassembler ce que l'on rapporte des revenants de sang, sans rien décider témérairement. "
		 "Toutefois, quand je mets côte à côte les morts de Serbie, ceux de Novgorod et ceux des cours du Sud, je ne puis m'empêcher de voir une même soif, et de penser qu'elle coula d'une seule source, il y a fort longtemps. "
		 "Qu'on me montre cette source, et je me tairai ; qu'on me prouve qu'il n'y en a pas, et je me tairai aussi."),
		("rapport_sur_les_pretendus_vampires", "« Rapport sur les prétendus vampires » — Gerard van Swieten", "📗",
		 "Envoyé par la souveraine pour examiner les cadavres que l'on disait gonflés de sang, j'ai trouvé une terre froide et argileuse qui garde les corps, et des villageois qui gardent leurs peurs. "
		 "Que certains morts se relèvent, je ne le nie pas, l'ayant vu. Mais rien ne m'autorise à dire que tous boivent au même sang : chaque lignée a sa faiblesse, son soleil et sa tombe, comme on le voit aux arbres de forêts différentes. "
		 "Le sang premier est une idée commode. Je n'en ai trouvé nulle part la preuve."),
	]),
	("Le vrykolakas", [
		("opinions_de_quelques_grecs", "« Des opinions de quelques Grecs » — Leo Allatius", "📕",
		 "Le vrykolakas est le corps d'un homme de mauvaise vie que la terre refuse ; il frappe aux portes la nuit, appelle par leur nom ceux de la maison, et qui répond meurt le lendemain. "
		 "Les anciens de l'île disent qu'il fut loup avant d'être mort, et que le loup, ne pouvant mourir tout à fait, est revenu sous la forme de ceux qui boivent le sang. Son nom même dit le poil de loup. "
		 "Je ne l'invente pas ; je l'ai entendu de témoins qui ne se connaissaient pas."),
		("relation_d_un_voyage_tournefort", "« Relation d'un voyage » — Joseph Pitton de Tournefort", "📙",
		 "Nous fûmes témoins, dans cette île, d'une scène bien singulière : un paysan mort, que l'on disait revenu, fut déterré, et l'on brûla son cœur sur le rivage dans une fumée si épaisse que personne ne vit rien. "
		 "Chacun jura ensuite avoir senti le loup ; aucun ne l'avait vu. La peur gagnait de maison en maison plus vite que le mort n'aurait marché. "
		 "Je ne dis pas qu'il n'y a pas de vrykolakas ; je dis qu'à Mykonos, cet hiver-là, il n'y avait que des vivants."),
	]),
	("Méduse et les attaques contre Atlantis", [
		("theogonie_hesiode", "« Théogonie » — Hésiode", "📜",
		 "Céto donna au vieux de la mer les Grées aux belles joues, et les Gorgones qui habitent au-delà de l'illustre Océan, aux confins de la nuit : Sthéno, Euryale, et Méduse au sort lamentable, car elle était mortelle et ses sœurs ne l'étaient pas. "
		 "Celui qui trancha sa tête crut finir une histoire ; il en commença une autre. Les sœurs ne meurent pas, et la mère n'oublie pas. "
		 "Demande aux murs de l'île d'orichalque pourquoi la mer les frappe : ils te répondront dans la langue des Gorgones."),
		("metamorphoses_ovide", "« Métamorphoses » — Ovide", "📜",
		 "Je chante les corps changés en formes nouvelles. Méduse fut d'une beauté illustre, et nombreux ceux qui la désirèrent ; mais un dieu la vit dans un temple, et une déesse, offensée, changea ses cheveux en serpents. "
		 "Elle ne naquit donc pas monstre : on la fit telle, et ce n'est pas la mer qui pleure sa tête. "
		 "Quant aux vagues qui frappent les murs d'orichalque, elles frappaient avant elle, et frapperont après moi. Tout change ; rien ne périt."),
	]),
]


def tous_les_ouvrages() -> list:
	out = list(OUVRAGES)
	for _sujet, livres in CONTROVERSES:
		out.extend(livres)
	return out


def _dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("aucun dump trouvé dans jsons/")
	return dumps[-1]


def docs_ouvrages() -> list:
	docs = []
	for slug, nom, icone, texte in tous_les_ouvrages():
		obj = f"ouvrage_{slug}"
		docs.append({
			"_id": f"item:{obj}", "type": "item", "nom": nom, "icon": icone,
			"description": texte, "rarete": "peu_commun",
			"categorie": "livre", "sous_categorie": "ouvrage",
			"slots": [], "tags": [TAG], "poids": 0.6,
		})
		docs.append({
			"_id": f"recette:{obj}", "type": "recette", "lieu_categorie": "scriptorium",
			"objet_final": obj, "quantite_produite": 1, "matieres_premieres": MATIERES,
		})
	return docs


# Tenanciers des bibliothèques : (catégorie, race, portrait). Nom et ambiance : METIERS.
TENANCIERS = [
	("bibliotheque", "nain", "personnel_lettre_f_nain01.jpg"),
	("grande_bibliotheque", "elfe", "personnel_lettre_m_elfe01.jpg"),
]
MODELE_TENANCIER = "pnj:marchand_grand_scriptorium"


def docs_tenanciers(base: dict) -> list:
	modele = base.get(MODELE_TENANCIER)
	if not modele:
		sys.exit(f"{MODELE_TENANCIER} absent du dump : impossible de cloner le tenancier")
	docs = []
	for cat, race, portrait in TENANCIERS:
		nom, _metier, ambiance = METIERS[cat]
		doc = copy.deepcopy(modele)
		doc.pop("_rev", None)
		doc.update({"_id": f"pnj:marchand_{cat}", "nom": nom, "race": race, "portrait": portrait})
		doc["dialogue"]["noeuds"]["accueil"]["texte"] = f"{ambiance} « Bien le bonjour, {{prenom}}. Que puis-je pour vous ? »"
		docs.append(doc)
	return docs


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


def main() -> None:
	dump = _dernier_dump()
	with open(dump, encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f)["docs"]}
	manquants = [m["item"] for m in MATIERES if m["item"] not in base]
	if manquants:
		sys.exit(f"matières absentes du dump : {manquants}")
	docs = docs_ouvrages() + docs_tenanciers(base)
	ids = [d["_id"] for d in docs]
	assert len(ids) == len(set(ids)), "doublon d'_id dans la sortie"
	# Un `_id` déjà en base doit être l'un des nôtres (récit tagué, recette d'ouvrage, tenancier
	# de bibliothèque) : sinon on écraserait un doc étranger (import = PUT complet).
	etrangers = []
	for d in docs:
		b = base.get(d["_id"])
		if not b:
			continue
		nous = (TAG in (b.get("tags") or []) or str(b.get("objet_final", "")).startswith("ouvrage_")
				or d["_id"] in {f"pnj:marchand_{c}" for c, _r, _p in TENANCIERS})
		if not nous:
			etrangers.append(d["_id"])
	if etrangers:
		sys.exit(f"collision d'_id avec {os.path.basename(dump)} : {etrangers}")
	delta = [d for d in docs if d["_id"] not in base or _sans_rev(base[d["_id"]]) != d]
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(delta, f, ensure_ascii=False, indent=1)
		f.write("\n")
	n = len(tous_les_ouvrages())
	print(f"{len(delta)} docs (delta sur {len(docs)} : {n} récits + recettes, {len(TENANCIERS)} tenanciers) "
		  f"-> {SORTIE} (contrôlé contre {os.path.basename(dump)})")


if __name__ == "__main__":
	main()
