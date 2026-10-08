"""Chaman 🐺 — esprits totems : ours, loup, sanglier, chat sauvage, faucon (magie de la Nature)."""
from competences_1_10 import A, L

CC = {"jet": "cc", "portee": 1}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Griffe du loup", "🐺", "frappe", "griffe", "Ses ongles s'allongent en griffes le temps d'un coup.", **CC),
	A(1, "Cri de l'esprit", "👻", "entrave", "totem", "Un cri qui appelle un esprit hostile sur la cible.", malus=("Vol",)),
	A(1, "Force de l'ours", "🐻", "buff_soi", "totem", "L'esprit de l'ours lui prête sa force.", stats=("F", "R")),
	A(1, "Bénédiction ancestrale", "🪶", "soin", "soin_nature", "Les ancêtres posent la main sur la plaie."),
	# ── Niveau 2 ──
	A(2, "Morsure du serpent", "🐍", "poison", "poison", "Un esprit-serpent mord la cible."),
	A(2, "Œil du faucon", "🦅", "buff_allie", "totem", "L'esprit du faucon aiguise le regard d'un compagnon.", stats=("Ag", "Int")),
	A(2, "Bond du chat sauvage", "🐈", "saut", "totem", "Il bondit avec la souplesse du chat."),
	A(2, "Esprit voleur", "👤", "siphon", "spectre", "Un esprit vole l'énergie de la cible."),
	# ── Niveau 3 ──
	A(3, "Ruée du sanglier-esprit", "🐗", "entrave", "griffe", "Il fonce comme le sanglier et renverse l'ennemi.", malus=("Ag",), **CC),
	A(3, "Tambour des esprits", "🥁", "cri", "totem", "Le tambour bat, et les esprits fortifient le groupe.", stats=("Vol", "F")),
	# ── Niveau 4 ──
	L(4, "Esprit du faucon", "🦅", "totem", "L'esprit du faucon se pose sur l'épaule d'un compagnon et guide son regard.",
	  {"cible": "allie", "portee": 4, "cout_pm": 18, "effets": {"buffs": {"Ag": "6+{Cha/7}", "Ch": 6}, "duree": 3}},
	  remplace="foudre_des_ancetres"),
	A(4, "Fièvre des marais", "🤒", "poison_pm", "poison", "Un esprit de fièvre ronge la volonté de la cible."),
	L(4, "Hurlement d'effroi", "🐺", "appel_sauvage", "Un hurlement qui glace le sang de tout un groupe d'ennemis.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 18, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Vol": "-4-{Vol/10}", "F": -4}, "duree": 3}},
	  remplace="hurlement_de_la_meute"),
	L(4, "Transe des ancêtres", "🥁", "totem", "Il chante et les ancêtres répondent, prêtant leur force à son bras.",
	  {"cible": "soi", "portee": 1, "cout_pm": 18, "effets": {"buffs": {"F": "3+{Cha/8}", "Vol": "2+{Cha/12}"}, "duree": 3}},
	  remplace="veille_de_l_esprit"),
	# ── Niveau 5 ──
	A(5, "Crocs de l'esprit", "🦷", "drain", "griffe", "L'esprit-loup mord et lui rend la vie volée.", **CC),
	A(5, "Masque des morts", "👺", "entrave", "spectre", "Il revêt le masque des morts, et l'ennemi recule.", malus=("Vol", "F")),
	A(5, "Esprit guérisseur", "💚", "regen_allie", "soin_nature", "Un esprit bienveillant veille sur un compagnon."),
	A(5, "Transe", "🌀", "pm_allie", "totem", "Une transe qui ouvre à un compagnon la source des esprits."),
	# ── Niveau 6 ──
	A(6, "Griffes de l'ours-esprit", "🐻", "zone_cone", "impact_plaie/cone_griffe", "Une patte immense d'esprit lacère devant lui."),
	L(6, "Fardeau des esprits", "👻", "lien", "Il lie un compagnon aux esprits : ils absorbent une part des coups, le chaman porte le reste.",
	  {"cible": "allie", "portee": 3, "cout_pm": 20, "maintien": 3, "effets": {"lien_vie": {"part": "25+{Cha/4}", "reduction": 30}}},
	  remplace="ailes_du_faucon"),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(6, "Homme bête", "🐺", "totem", "L'esprit n'est plus un compagnon qu'il invoque : il vit à l'intérieur, et sort quand on l'y oblige.",
	  {"cible": "soi", "portee": 1, "cout_pm": 25, "effets": {"buffs": {"F": 12, "R": 8, "Ag": 6, "Int": -6}, "regen_pv": 1, "duree": 5, "saut": 3}},
	  remplace="homme_bete"),
	# ── Niveau 7 ──
	A(7, "Fléau des esprits", "💀", "poison", "spectre", "Les esprits hantent la cible et la consument."),
	A(7, "Totem de guerre", "🗿", "cri", "totem", "Il plante un totem, et la troupe se bat comme une meute.", stats=("F", "Ag"), rayon=2),
	A(7, "Esprit du sanglier", "🐗", "frappe", "griffe", "La fureur du sanglier dans un seul coup.", **CC),
	A(7, "Chaînes spirituelles", "⛓️", "entrave", "spectre", "Des chaînes d'esprit lient la cible.", malus=("Ag", "Vol")),
	# ── Niveau 8 ──
	L(8, "Pluie des ancêtres", "🌧️", "soin_nature", "Une pluie tiède tombe sur ses compagnons et referme lentement leurs plaies.",
	  {"cible": "allie", "portee": 4, "cout_pm": 33, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"regen_pv": "2+{Cha/30}", "duree": 4}},
	  remplace="orage_ancestral"),
	A(8, "Danse de l'esprit", "💃", "soin_zone", "totem", "Une danse qui soigne tous ceux qui l'entourent."),
	A(8, "Peau de l'ours", "🐻", "posture", "totem", "Il revêt la peau de l'ours-esprit.", stats=("R", "F")),
	A(8, "Vol d'âme", "👻", "siphon", "spectre", "Il arrache un morceau d'âme à la cible."),
	# ── Niveau 9 ──
	A(9, "Fureur totémique", "🗿", "frappe", "totem", "Tous les esprits frappent en même temps."),
	A(9, "Rituel du grand esprit", "🔥", "rituel", "totem", "Un long chant qui appelle le grand esprit."),
	A(9, "Bond du loup-garou", "🐺", "saut", "griffe", "Un bond surhumain, porté par l'esprit du loup."),
	A(9, "Chant des morts", "💀", "poison_pm", "spectre", "Les morts chantent dans la tête de la cible."),
	# ── Niveau 10 ──
	A(10, "Avatar totémique", "🐻", "posture", "totem", "Il devient l'esprit lui-même.", stats=("F", "R")),
	L(10, "Marche des ancêtres", "🥁", "totem", "Les ancêtres marchent avec la troupe : chacun frappe et tient comme dix.",
	  {"cible": "soi", "portee": 1, "cout_pm": 40, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 2}, "effets": {"buffs": {"F": "7+{Cha/10}", "R": 7}, "duree": 5}},
	  remplace="colere_des_ancetres"),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(10, "Esprit Antique", "🦣", "totem", "Le mammouth, le tigre à dents de sabre, le grand saurien. Un seul, une seule fois, et il faut ensuite s'en remettre.",
	  {"cible": "soi", "portee": 1, "cout_pm": 40, "effets": {"buffs": {"F": 16, "R": 10, "Ag": 6, "V": 1}, "regen_pv": 2, "duree": 5}},
	  remplace="esprit_antique"),
]
