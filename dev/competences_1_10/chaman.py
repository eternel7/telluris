"""Chaman 🐺 — esprits totems : ours, loup, sanglier, chat sauvage, faucon (magie de la Nature)."""
from competences_1_10 import A

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
	A(4, "Foudre des ancêtres", "⚡", "frappe", "foudre", "Les ancêtres frappent du haut des nuages."),
	A(4, "Fièvre des marais", "🤒", "poison_pm", "poison", "Un esprit de fièvre ronge la volonté de la cible."),
	A(4, "Hurlement de la meute", "🐺", "zone_cercle", "appel_sauvage", "Un hurlement qui fait trembler tout un groupe d'ennemis."),
	A(4, "Veille de l'esprit", "👁️", "posture", "totem", "Un esprit veille sur lui et détourne les coups.", stats=("Vol", "R")),
	# ── Niveau 5 ──
	A(5, "Crocs de l'esprit", "🦷", "drain", "griffe", "L'esprit-loup mord et lui rend la vie volée.", **CC),
	A(5, "Masque des morts", "👺", "entrave", "spectre", "Il revêt le masque des morts, et l'ennemi recule.", malus=("Vol", "F")),
	A(5, "Esprit guérisseur", "💚", "regen_allie", "soin_nature", "Un esprit bienveillant veille sur un compagnon."),
	A(5, "Transe", "🌀", "pm_allie", "totem", "Une transe qui ouvre à un compagnon la source des esprits."),
	# ── Niveau 6 ──
	A(6, "Griffes de l'ours-esprit", "🐻", "zone_cone", "impact_plaie/cone_griffe", "Une patte immense d'esprit lacère devant lui."),
	A(6, "Ailes du faucon", "🦅", "saut", "vent", "Les ailes de l'esprit l'emportent."),
	# ── Niveau 7 ──
	A(7, "Fléau des esprits", "💀", "poison", "spectre", "Les esprits hantent la cible et la consument."),
	A(7, "Totem de guerre", "🗿", "cri", "totem", "Il plante un totem, et la troupe se bat comme une meute.", stats=("F", "Ag"), rayon=2),
	A(7, "Esprit du sanglier", "🐗", "frappe", "griffe", "La fureur du sanglier dans un seul coup.", **CC),
	A(7, "Chaînes spirituelles", "⛓️", "entrave", "spectre", "Des chaînes d'esprit lient la cible.", malus=("Ag", "Vol")),
	# ── Niveau 8 ──
	A(8, "Orage ancestral", "⛈️", "zone_cercle", "foudre", "Les ancêtres déchaînent l'orage sur les ennemis.", rayon=2),
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
	A(10, "Colère des ancêtres", "⚡", "zone_carre", "foudre", "Les ancêtres frappent tout autour de lui.", rayon=2),
]
