"""Illusionniste 🎭 — manipulateur de perceptions (magie Illusoire)."""
from competences_1_10 import A, L

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Mirage", "🌫️", "entrave", "illusion", "Une image trouble qui égare le regard de l'ennemi.", malus=("Ag",)),
	A(1, "Lueur aveuglante", "💡", "frappe", "eblouissant", "Un éclat qui brûle les yeux autant que la chair."),
	A(1, "Image miroir", "🪞", "esquive_soi", "double", "Un reflet de lui-même attire les coups."),
	A(1, "Pas fantôme", "👻", "saut", "spectre", "Il disparaît ici et réapparaît là-bas."),
	# ── Niveau 2 ──
	L(2, "Reflet trompeur", "🪞", "double", "Un reflet de lui-même prend les coups à sa place, et tient d'autant mieux qu'il est convaincant.",
	  {"cible": "soi", "portee": 1, "cout_pm": 12, "effets": {"esquive": "2+{Cha/8}", "duree": "1+{Int/25}"}},
	  remplace="murmure_trompeur"),
	A(2, "Couleurs dansantes", "🌈", "zone_cercle", "illusion_zone", "Un tourbillon de couleurs qui étourdit le groupe ennemi."),
	A(2, "Charme", "💕", "buff_allie", "chant", "Il donne à un compagnon une aura de séduction troublante.", stats=("Cha", "Vol")),
	A(2, "Peur fantasmée", "😱", "entrave", "spectre", "L'ennemi voit sa pire peur se dresser devant lui.", malus=("Vol", "F")),
	# ── Niveau 3 ──
	A(3, "Lame illusoire", "🗡️", "frappe", "illusion", "Une lame qui n'existe pas, mais qui blesse."),
	A(3, "Voile", "🫥", "posture", "furtif", "Il s'enveloppe d'un voile qui trouble sa silhouette.", stats=("Ag", "Int")),
	# ── Niveau 4 ──
	A(4, "Cauchemar éveillé", "😨", "poison", "spectre", "Des visions horribles qui rongent l'esprit et le corps."),
	A(4, "Confusion", "🌀", "entrave", "illusion", "L'ennemi ne sait plus où est la gauche ni la droite.", malus=("Int", "Ag")),
	A(4, "Prisme", "🔷", "frappe", "eblouissant", "La lumière se brise en mille éclats tranchants."),
	A(4, "Rêve apaisant", "😌", "regen_allie", "meditation", "Un rêve doux qui soigne les blessures d'un compagnon."),
	# ── Niveau 5 ──
	A(5, "Ombres hurlantes", "👥", "zone_cercle", "illusion_zone", "Des ombres surgissent et assaillent le groupe ennemi.", rayon=2),
	A(5, "Vol de pensée", "🧠", "siphon", "illusion", "Il dérobe les pensées de la cible, et sa magie avec."),
	A(5, "Doubles multiples", "👯", "esquive_soi", "double", "Trois, quatre, cinq de lui : lequel est le vrai ?"),
	L(5, "Permutation", "🔀", "saut", "Un compagnon disparaît dans un clin d'œil et réapparaît plus loin. Personne n'a rien vu.",
	  {"cible": "allie", "portee": 6, "cout_pm": 21, "effets": {"saut": 4}},
	  remplace="inspiration_trompeuse"),
	# ── Niveau 6 ──
	A(6, "Éventail de folie", "🌀", "zone_cone", "impact_etincelles/cone_folie", "Une vague de démence qui déferle devant lui."),
	A(6, "Pas entre les reflets", "🪞", "saut", "double", "Il passe d'un reflet à un autre."),
	# ── Niveau 7 ──
	A(7, "Lame de cauchemar", "🗡️", "frappe", "spectre", "Une lame forgée dans les cauchemars de la cible."),
	L(7, "Terreur nocturne", "😱", "spectre", "Une vision de ce que la cible redoute le plus : la volonté se brise, le mana fuit.",
	  {"cible": "ennemi", "jet": "magique", "portee": 5, "cout_pm": 29, "effets": {"buffs": {"Vol": "-3-{Cha/8}"}, "regen_pm": -3, "duree": 3}},
	  remplace="paralysie_hypnotique"),
	A(7, "Dévoreur de rêves", "🌙", "drain", "spectre", "Il se nourrit des rêves de la cible."),
	A(7, "Spectacle", "🎪", "cri", "illusion_zone", "Une illusion grandiose qui galvanise ses alliés.", stats=("Cha", "Vol")),
	# ── Niveau 8 ──
	A(8, "Démence", "🤪", "poison_pm", "illusion", "La raison de la cible se délite peu à peu."),
	A(8, "Kaléidoscope", "🔮", "zone_cercle", "eblouissant", "Un éclatement de lumière qui aveugle tout un groupe.", rayon=2),
	A(8, "Masque de terreur", "🎭", "entrave", "spectre", "Il revêt un masque qui terrifie quiconque le regarde.", malus=("Vol", "F")),
	A(8, "Mirage de refuge", "🏝️", "posture", "illusion", "Il se dissimule dans un refuge qui n'existe pas.", stats=("Ag", "R")),
	# ── Niveau 9 ──
	A(9, "Illusion mortelle", "💀", "frappe", "spectre", "La cible croit mourir — et son corps la croit."),
	A(9, "Folie collective", "🌀", "zone_cone", "impact_etincelles/cone_folie", "Le groupe ennemi perd toute raison."),
	A(9, "Rêve partagé", "💭", "pm_allie", "meditation", "Il partage un rêve qui restaure l'énergie d'un compagnon."),
	A(9, "Grand théâtre", "🎭", "rituel", "illusion_zone", "Une illusion longue à monter, terrible à vivre."),
	# ── Niveau 10 ──
	A(10, "Réalité brisée", "💔", "entrave", "illusion", "La cible ne sait plus ce qui est réel.", malus=("Int", "Vol", "Ag")),
	A(10, "Fantasmagorie", "🎆", "zone_cercle", "illusion_zone", "Le monde entier semble se retourner contre l'ennemi.", rayon=2),
]
