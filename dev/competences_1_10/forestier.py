"""Forestier 🏹 — l'arc, la piste et les bois ; les pièges sont déjà livrés (dev/gen_pieges.py)."""
from competences_1_10 import A, P, L

BOIS = ("foret", "bois", "clariere", "couvert", "chemin")
CC = {"jet": "cc", "portee": 1}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Flèche rapide", "🏹", "frappe", "tir", "Encoche, vise, lâche : un seul souffle."),
	A(1, "Tir aux jambes", "🦵", "entrave", "tir", "Une flèche basse qui ralentit la course de la proie.", malus=("Ag",)),
	A(1, "Coup de couteau", "🔪", "frappe", "saignee", "Le couteau de chasse, quand la bête est trop près pour l'arc.", **CC),
	A(1, "Bond du lièvre", "🐇", "saut", "saut", "Il s'éloigne d'un bond pour retrouver la bonne distance."),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(1, "Baume de campagne", "🌿", "soin_nature", "Deux feuilles mâchées, un linge serré, et on repart. Le forestier ne guérit pas : il rafistole assez pour tenir jusqu'au camp.",
	  {"cible": "allie", "portee": 2, "cout_pm": 8, "effets": {"pv": 8, "regen_pv": 2, "duree": 3}},
	  remplace="baume_de_campagne"),
	# ── Niveau 2 ──
	P(2, "Pas de velours", "🍂", "p_furtif", "Il marche sur les feuilles mortes sans en froisser une.", terrains=BOIS),
	L(2, "Tir à longue portée", "🏹", "tir", "Une flèche qui file plus loin que l'œil ne suit — pour qui a la main assez sûre.",
	  {"cible": "ennemi", "jet": "cd", "portee": "6+{Ag/10}", "cout_pm": 12, "effets": {"degats": "1D8+3"}},
	  remplace="double_fleche"),
	A(2, "Flèche barbelée", "🩸", "poison", "tir", "La pointe accroche les chairs, et la plaie saigne."),
	A(2, "Patience du chasseur", "🧘", "buff_soi", "nature_buff", "Il retient son souffle ; le monde ralentit autour de sa cible.", stats=("Ag",)),
	A(2, "Herbes de guérison", "🌿", "soin", "soin_nature", "Une poignée de plantes mâchées, appliquée sur la plaie."),
	A(2, "Volée", "🌧️", "zone_cercle", "tir", "Une pluie de flèches sur une petite clairière."),
	# ── Niveau 3 ──
	A(3, "Flèche perforante", "🎯", "frappe", "tir", "Une pointe lourde qui traverse le cuir et l'os."),
	A(3, "Cri du faucon", "🦅", "entrave", "vent", "Un sifflement aigu qui affole la proie.", malus=("Vol", "Ag")),
	A(3, "Marque du gibier", "🎯", "siphon", "marque", "Il repère le point faible de la bête et l'épuise."),
	A(3, "Pas de côté du rôdeur", "🍃", "esquive_soi", "furtif", "Il se fond dans un fourré, et la riposte frappe le vide."),
	# ── Niveau 4 ──
	P(4, "Œil perçant", "👁️", "p_carac", "Il distingue un écureuil à cent pas dans le feuillage.", stats=("Ag",)),
	A(4, "Tir à l'œil", "👁️", "frappe", "tir", "Une flèche qui cherche le seul point que l'armure ne couvre pas."),
	A(4, "Flèche de chasse", "🏹", "entrave", "tir", "Une flèche à large fer, qui handicape plus qu'elle ne tue.", malus=("Ag", "F")),
	A(4, "Lame et pointe", "🔪", "zone_rect", "balayage", "Couteau dans une main, flèche dans l'autre : il taille large.", **CC),
	A(4, "Remède du bois", "🌱", "regen_allie", "soin_nature", "Un baume d'écorce qui referme lentement les plaies."),
	A(4, "Saut de branche", "🌳", "saut", "saut", "Il grimpe et retombe plus loin, hors d'atteinte."),
	# ── Niveau 5 ──
	P(5, "Endurance du pisteur", "🥾", "p_regen", "Des jours sur la piste, sans repos, et toujours debout."),
	A(5, "Flèche venimeuse", "🐍", "poison", "poison", "La pointe trempée dans la sève des marais."),
	A(5, "Pluie de flèches", "🌧️", "zone_cercle", "tir", "Le ciel s'assombrit au-dessus des ennemis.", rayon=2),
	A(5, "Flèche longue", "🏹", "frappe", "tir", "Un tir à la limite de la portée, qui touche quand même.", portee=10),
	L(5, "Se fondre dans les fourrés", "🌿", "furtif", "Un pas de côté entre deux branches, et il n'est plus là.",
	  {"cible": "soi", "portee": 1, "cout_pm": 21, "effets": {"furtivite": "4+{Ag/10}"}},
	  remplace="affut"),
	A(5, "Appel du loup", "🐺", "cri", "appel_sauvage", "Un hurlement qui rend la meute — et ses compagnons — plus mordants.", stats=("Ag", "F")),
	# ── Niveau 6 ──
	L(6, "Cataplasme de sente", "🌱", "soin_nature", "Quelques feuilles mâchées, un linge serré : ce que la forêt sait guérir, il le sait aussi.",
	  {"cible": "allie", "portee": 1, "cout_pm": 25, "effets": {"soin": "1D6+{Int/10}", "regen_pv": 2, "duree": 3}},
	  remplace="fleche_du_pistard"),
	A(6, "Clouer au sol", "📌", "entrave", "tir", "La flèche traverse le pied et s'enfonce dans la terre.", malus=("Ag",)),
	A(6, "Flèche épuisante", "😮‍💨", "siphon", "tir", "Une pointe qui vide la bête de ses forces."),
	A(6, "Ombre des feuilles", "🍃", "esquive_soi", "furtif", "Il disparaît dans le feuillage le temps d'un souffle."),
	# ── Niveau 7 ──
	P(7, "Peau de chasseur", "🦌", "p_carac", "Les ronces, le froid, la pluie : il les ignore.", stats=("R",)),
	A(7, "Tir mortel", "💀", "frappe", "tir", "Une flèche qu'on n'entend qu'une fois."),
	A(7, "Volée en éventail", "🪭", "zone_cone", "impact_etincelles/cone_decharge", "Trois flèches à la fois, ouvertes en éventail."),
	A(7, "Saignée de cerf", "🩸", "poison", "saignee", "Il vise l'artère comme on achève un grand cerf."),
	A(7, "Bond de la panthère", "🐆", "saut", "saut", "Un saut silencieux vers la position idéale."),
	A(7, "Pharmacopée sylvestre", "🌿", "soin", "soin_nature", "Il sait quelle herbe pousse au pied de quel arbre."),
	# ── Niveau 8 ──
	P(8, "Fantôme des bois", "👻", "p_furtif", "Même les oiseaux ne le remarquent pas.", terrains=BOIS),
	A(8, "Tir transperçant", "🎯", "frappe", "tir", "La flèche traverse le premier et cherche le second."),
	A(8, "Grêle de flèches", "🌧️", "zone_cercle", "tir", "Un orage de traits sur une large zone.", rayon=2),
	A(8, "Flèche aveuglante", "😵", "entrave", "eblouissant", "Une pointe enduite de résine qui brûle les yeux.", malus=("Ag", "Int")),
	A(8, "Esprit de la forêt", "🌳", "buff_allie", "nature_buff", "Il murmure aux arbres, et un compagnon en reçoit la force.", stats=("R", "Ag")),
	A(8, "Couteau du dépeceur", "🔪", "drain", "saignee", "Le geste sûr de celui qui a dépecé mille bêtes.", **CC),
	# ── Niveau 9 ──
	P(9, "Maîtrise de l'arc", "🏹", "p_carac", "L'arc est devenu une partie de son corps.", stats=("Ag",)),
	L(9, "Sens aiguisés", "👃", None, "Il lit la forêt comme un livre : qui en sait le plus voit venir les coups de plus loin.",
	  {"effets": {"esquive": "{Int/7}"}},
	  remplace="sens_aiguises", mode="passive"),
	A(9, "Flèche du roi des bois", "👑", "frappe", "tir", "La flèche que l'on garde pour le monstre de la forêt."),
	A(9, "Tir de suppression", "🌧️", "zone_cone", "impact_etincelles/cone_decharge", "Un barrage de flèches qui force l'ennemi à se terrer."),
	A(9, "Venin du marais", "🐸", "poison", "poison", "Un poison noir qui ronge jusqu'à l'os."),
	A(9, "Vigilance du guetteur", "👁️", "posture", "nature_buff", "Il garde l'œil sur tout le champ de bataille.", stats=("Ag", "Int")),
	A(9, "Bond de l'élan", "🦌", "saut", "saut", "Un saut puissant qui l'emporte loin de la mêlée."),
	# ── Niveau 10 ──
	P(10, "Seigneur des bois", "🦌", "p_carac", "La forêt le reconnaît comme l'un des siens.", stats=("Ag",)),
	A(10, "Flèche de légende", "🌠", "frappe", "tir", "La flèche dont parlent les chansons de chasse."),
	A(10, "Ciel de flèches", "🌧️", "zone_cercle", "tir", "Il assombrit le ciel, et la pluie qui tombe est d'acier.", rayon=2),
	A(10, "Appel de la grande chasse", "📯", "cri", "appel_sauvage", "Le cor sonne, et tout le groupe se met en chasse.", stats=("Ag", "F"), rayon=2),
	A(10, "Proie épuisée", "😮‍💨", "siphon", "marque", "Il traque sa cible jusqu'à ce qu'elle n'ait plus rien."),
]
