"""Moine 🥋 — le corps comme arme, l'esprit comme bouclier (magie Sainte : aucune passive neuve)."""
from competences_1_10 import A

MAG = {"jet": "magique", "portee": 4}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Paume tranchante", "🤚", "frappe", "poing", "Le tranchant de la main, durci par mille planches brisées."),
	A(1, "Balayage de jambe", "🦵", "entrave", "poing", "Il fauche les appuis de l'adversaire d'un seul mouvement.", malus=("Ag",)),
	A(1, "Respiration du lotus", "🪷", "buff_soi", "meditation", "Un souffle profond, et le corps se fait léger.", stats=("Vol", "Ag")),
	# ── Niveau 2 ──
	A(2, "Coup du dragon", "🐉", "frappe", "poing", "Un poing qui part des talons et finit dans la poitrine adverse."),
	A(2, "Toucher des méridiens", "☯️", "siphon", "meditation", "Deux doigts sur un point vital, et l'énergie de l'autre se dissipe."),
	A(2, "Bond de la grue", "🕊️", "saut", "vent", "Il s'élève comme la grue et retombe où il le veut."),
	A(2, "Main apaisante", "🤲", "soin", "soin_sacre", "Une paume posée sur la blessure, et la douleur reflue.", portee=1),
	# ── Niveau 3 ──
	A(3, "Roue du vent", "🌀", "zone_carre", "poing", "Il tourne sur lui-même, pieds et poings en éventail."),
	A(3, "Souffle intérieur", "🌬️", "pm_allie", "meditation", "Il partage le calme de son souffle avec un compagnon."),
	# ── Niveau 4 ──
	A(4, "Poing de pierre", "🪨", "frappe", "roc", "Sa main frappe comme la roche tombe."),
	A(4, "Frappe du tigre", "🐯", "entrave", "griffe", "Les doigts en griffes, il déchire la garde.", malus=("Ag", "F")),
	A(4, "Posture de la montagne", "⛰️", "posture", "meditation", "Il s'enracine : rien ne le déplacera.", stats=("R", "Vol")),
	A(4, "Esprit clair", "💭", "buff_allie", "meditation", "Un mot calme, et un compagnon retrouve sa lucidité.", stats=("Vol", "Int")),
	# ── Niveau 5 ──
	A(5, "Paume de lumière", "☀️", "frappe", "lumiere", "Une paume chargée d'énergie pure.", **MAG),
	A(5, "Coup du serpent", "🐍", "poison_pm", "poing", "Deux doigts au creux de l'épaule, et l'énergie fuit."),
	A(5, "Pas de la brise", "🍃", "esquive_soi", "vent", "Il devient insaisissable comme une brise."),
	A(5, "Chant du monastère", "🔔", "cri", "chant", "Un mantra grave que reprennent ceux qui l'entourent.", stats=("Vol", "R")),
	# ── Niveau 6 ──
	A(6, "Mille poings", "👊", "zone_rect", "poing", "Une rafale de coups si rapide qu'on n'en compte que le bruit."),
	A(6, "Sceau d'harmonie", "☯️", "regen_allie", "soin_sacre", "Il rétablit l'équilibre dans le corps d'un compagnon."),
	# ── Niveau 7 ──
	A(7, "Frappe de l'âme", "👻", "drain", "meditation", "Le coup traverse la chair et touche l'esprit.", **MAG),
	A(7, "Pied du phénix", "🔥", "frappe", "feu", "Un coup de pied qui laisse une traînée brûlante."),
	A(7, "Corps de bronze", "🛡️", "posture", "bouclier", "Il durcit sa peau par la seule volonté.", stats=("R",)),
	A(7, "Saut du singe", "🐒", "saut", "saut", "Un bond acrobatique par-dessus la mêlée."),
	# ── Niveau 8 ──
	A(8, "Onde de choc", "💥", "zone_carre", "poing", "Il frappe le sol, et l'onde renverse tout autour de lui.", rayon=2),
	A(8, "Point de pression", "📍", "entrave", "poing", "Un doigt sur un nerf, et le bras de l'ennemi ne répond plus.", malus=("F", "Ag")),
	A(8, "Vide intérieur", "🕳️", "siphon", "arcane", "Il fait le vide en lui — et chez l'autre.", **MAG),
	A(8, "Souffle de vie", "💨", "soin_zone", "soin_vague", "Un souffle qui ranime ceux qui l'entourent."),
	# ── Niveau 9 ──
	A(9, "Poing du ciel", "☁️", "frappe", "lumiere", "Un poing qui tombe comme la foudre du ciel."),
	A(9, "Danse des mille mains", "🙏", "zone_cone", "impact_etincelles/cone_decharge", "Une rafale de paumes qui s'ouvre devant lui en éventail."),
	A(9, "Paix du sage", "🕊️", "cri", "meditation", "Une sérénité qui gagne tout le groupe.", stats=("Vol", "R"), rayon=2),
	A(9, "Brise-esprit", "🧠", "poison_pm", "arcane", "Un coup au front qui trouble les pensées.", **MAG),
	# ── Niveau 10 ──
	A(10, "Paume du néant", "🌑", "frappe", "arcane", "Une paume qui efface ce qu'elle touche."),
	A(10, "Ascension", "🌤️", "saut", "aura_sacree", "Il s'élève et retombe comme une feuille portée par le vent."),
]
