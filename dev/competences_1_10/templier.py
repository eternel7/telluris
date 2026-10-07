"""Templier ⚜️ — défenseur de la cité, épée de l'institution (magie de Bataille)."""
from competences_1_10 import A

MAG = {"jet": "magique", "portee": 5}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Coup réglementaire", "⚔️", "frappe", "lame", "Un coup tel qu'on l'enseigne à l'ordre : propre et efficace."),
	A(1, "Ordre de halte", "✋", "entrave", "garde", "Un commandement sec qui fige l'adversaire.", malus=("Ag",)),
	A(1, "Garde de l'ordre", "🛡️", "esquive_soi", "garde", "La garde réglementaire, haute et serrée.", stats=("R",)),
	A(1, "Discipline du rang", "📏", "buff_soi", "aura_bataille", "Il rectifie sa posture et respire au rythme de l'ordre.", stats=("R", "Vol")),
	# ── Niveau 2 ──
	A(2, "Frappe du gardien", "🗡️", "frappe", "lame", "Le coup du gardien de porte : économe et sûr."),
	A(2, "Bouclier repoussant", "🛡️", "entrave", "coup_lourd", "Un coup de bouclier qui fait reculer l'ennemi.", malus=("F", "Ag")),
	A(2, "Rune de résistance", "ᚱ", "buff_allie", "enchantement", "Il trace une rune sur l'armure d'un compagnon.", stats=("R",)),
	A(2, "Pas de la patrouille", "🚶", "saut", "saut", "Il couvre la distance au pas de charge réglementaire."),
	# ── Niveau 3 ──
	A(3, "Ligne de l'ordre", "🧱", "zone_rect", "lame", "Une taille horizontale qui frappe le premier rang adverse."),
	A(3, "Annulation", "🚫", "siphon", "arcane", "Une formule de l'ordre qui dissipe la magie adverse.", **MAG),
	# ── Niveau 4 ──
	A(4, "Lame enflammée", "🔥", "frappe", "feu", "Une formule de bataille, et l'épée s'embrase."),
	A(4, "Sceau de garde", "🔰", "posture", "bouclier", "Un sceau runique qui renforce la garde tant qu'il le tient.", stats=("R", "Vol")),
	A(4, "Chaînes de l'ordre", "⛓️", "entrave", "arcane", "Des chaînes d'énergie entravent le malfaiteur.", malus=("Ag", "F"), **MAG),
	A(4, "Ordre de bataille", "📯", "cri", "aura_bataille", "Il donne l'ordre, et la ligne se reforme.", stats=("R", "F")),
	# ── Niveau 5 ──
	A(5, "Coup de l'inquisition", "🔨", "frappe", "lame_sacree", "Un coup qui porte la sentence de l'ordre."),
	A(5, "Mur de l'ordre", "🏰", "buff_allie", "bouclier", "Il étend sa garde sur un compagnon.", stats=("R", "Vol")),
	A(5, "Fer rouge", "🔥", "poison", "feu", "Une lame chauffée à blanc qui marque l'ennemi."),
	A(5, "Explosion runique", "💥", "zone_cercle", "explosion_feu", "Une rune gravée explose au milieu des ennemis.", **MAG),
	# ── Niveau 6 ──
	A(6, "Taille du gardien des temples", "⚔️", "frappe", "lame", "Un coup appris dans le cloître, pour défendre l'autel."),
	A(6, "Égide runique", "🛡️", "posture", "enchantement", "Des runes s'allument sur son armure et la rendent impénétrable.", stats=("R",)),
	# ── Niveau 7 ──
	A(7, "Lame de foudre", "⚡", "frappe", "foudre", "L'épée crépite d'éclairs au moment du coup."),
	A(7, "Interdit", "🚷", "entrave", "arcane", "Une parole de l'ordre interdit à l'ennemi de bouger.", malus=("Ag", "Int"), **MAG),
	A(7, "Rotation du templier", "🌀", "zone_carre", "balayage", "Il pivote, épée et bouclier, et frappe tout autour."),
	A(7, "Restauration de l'ordre", "🩹", "soin", "soin_sacre", "Une prière de l'ordre qui remet un frère sur pied."),
	# ── Niveau 8 ──
	A(8, "Jugement de l'ordre", "⚖️", "frappe", "lame_sacree", "La sentence tombe sans appel."),
	A(8, "Feu de l'autel", "🔥", "zone_cone", "impact_brulure/cone_souffle_feu", "Un souffle de flammes sacrées s'échappe de sa lame."),
	A(8, "Bastion", "🏯", "cri", "bouclier", "Il fait de ses compagnons un bastion.", stats=("R", "Vol"), rayon=2),
	A(8, "Dissipation", "✨", "siphon", "arcane", "Il défait la magie de l'ennemi fil à fil.", **MAG),
	# ── Niveau 9 ──
	A(9, "Épée de l'institution", "🗡️", "frappe", "lame", "Le coup qui fait respecter la loi."),
	A(9, "Tempête runique", "🌩️", "zone_cercle", "foudre", "Les runes s'embrasent et la foudre tombe sur les ennemis.", rayon=2, **MAG),
	A(9, "Garde inflexible", "🛡️", "posture", "garde", "Il ne bouge plus d'un pouce, quoi qu'il arrive.", stats=("R", "F")),
	A(9, "Saut du gardien", "🦅", "saut", "saut", "Il bondit pour couvrir le point faible de la ligne."),
	# ── Niveau 10 ──
	A(10, "Sentence capitale", "⚔️", "frappe", "lame_sacree", "L'ordre a jugé ; l'épée exécute."),
	A(10, "Rempart de la cité", "🏰", "cri", "aura_bataille", "Tant qu'il est debout, la cité ne tombera pas.", stats=("R", "Vol"), rayon=2),
]
