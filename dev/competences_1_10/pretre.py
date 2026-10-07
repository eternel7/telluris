"""Prêtre ✝ — guérisseur indispensable, la lumière qui relève (magie Sainte)."""
from competences_1_10 import A

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Lumière sainte", "✨", "frappe", "lumiere", "Un rai de lumière qui brûle l'impur."),
	A(1, "Prière de soin", "🙏", "soin", "soin_sacre", "Une prière murmurée, et la plaie se referme."),
	A(1, "Bénédiction", "🕊️", "buff_allie", "aura_sacree", "Il bénit un compagnon, qui se sent plus fort.", stats=("Vol", "R")),
	A(1, "Réprimande", "☝️", "entrave", "lumiere", "Un mot sévère qui fait plier l'ennemi.", malus=("Vol",)),
	# ── Niveau 2 ──
	A(2, "Grâce", "💫", "regen_allie", "soin_sacre", "Une grâce qui soigne lentement mais sûrement."),
	A(2, "Clarté", "💡", "pm_allie", "meditation", "Il éclaire l'esprit d'un compagnon et lui rend son énergie."),
	A(2, "Feu sacré", "🔥", "poison", "lumiere", "Une flamme sacrée qui brûle longtemps."),
	A(2, "Sanctuaire", "⛪", "posture", "bouclier", "Il se recueille, et une lumière le protège.", stats=("R", "Vol")),
	# ── Niveau 3 ──
	A(3, "Cercle de guérison", "⭕", "soin_zone", "soin_vague", "Un cercle de lumière soigne tous ceux qui s'y tiennent."),
	# ── Niveau 4 ──
	A(4, "Éclat divin", "🌟", "frappe", "lumiere", "Un éclat de pure divinité."),
	A(4, "Protection divine", "🛡️", "buff_allie", "bouclier", "Un bouclier de lumière sur un compagnon.", stats=("R",)),
	A(4, "Purification", "💧", "siphon", "lumiere", "Il purifie la magie impie de la cible."),
	A(4, "Lumière de l'aube", "🌅", "zone_cercle", "lumiere_zone", "Une lumière aveuglante sur le groupe ennemi."),
	# ── Niveau 5 ──
	A(5, "Guérison majeure", "❤️‍🩹", "soin", "soin_sacre", "Une prière puissante qui referme les blessures graves."),
	A(5, "Chaînes de lumière", "⛓️", "entrave", "lumiere", "Des chaînes de lumière entravent l'ennemi.", malus=("Ag", "F")),
	A(5, "Hymne", "🎶", "cri", "chant", "Un hymne qui fortifie tous ceux qui l'entendent.", stats=("Vol", "R")),
	A(5, "Saut de foi", "🕊️", "saut", "aura_sacree", "Il s'en remet à la foi, et elle le porte."),
	# ── Niveau 6 ──
	A(6, "Colonne de lumière", "☀️", "frappe", "lumiere_zone", "Une colonne de lumière s'abat sur la cible."),
	A(6, "Source de grâce", "⛲", "regen_allie", "source", "Une source de grâce qui coule sans fin."),
	# ── Niveau 7 ──
	A(7, "Exorcisme", "📿", "poison_pm", "lumiere", "Il chasse les esprits impurs, et la magie avec eux."),
	A(7, "Prière de masse", "🙏", "soin_zone", "soin_vague", "Toute l'assemblée est soignée d'une seule prière."),
	A(7, "Châtiment divin", "⚡", "zone_cercle", "lumiere_zone", "Le ciel frappe le groupe ennemi.", rayon=2),
	A(7, "Rempart de la foi", "🛡️", "posture", "aura_sacree", "Sa foi devient un rempart impénétrable.", stats=("R", "Vol")),
	# ── Niveau 8 ──
	A(8, "Jugement céleste", "⚖️", "frappe", "lumiere", "Le ciel juge, et le ciel frappe."),
	A(8, "Grâce de l'esprit", "💫", "pm_allie", "soin_sacre", "Il restaure l'énergie d'un compagnon par la prière."),
	A(8, "Silence sacré", "🤫", "entrave", "lumiere", "Un silence qui coupe l'ennemi de ses forces.", malus=("Vol", "Int")),
	A(8, "Bénédiction de masse", "🕊️", "cri", "aura_sacree", "Il bénit tout le groupe.", stats=("Vol", "F"), rayon=2),
	# ── Niveau 9 ──
	A(9, "Lumière purificatrice", "☀️", "rituel", "lumiere_zone", "Une prière longue, et une lumière qui purifie tout."),
	A(9, "Résurgence", "❤️", "soin", "soin_vague", "Une guérison presque miraculeuse."),
	A(9, "Anathème", "🚫", "siphon", "lumiere_zone", "Il frappe la cible d'anathème et la coupe de sa magie."),
	A(9, "Vœu de lumière", "🌟", "buff_allie", "aura_sacree", "Un vœu qui rend un compagnon presque invincible.", stats=("R", "Vol")),
	# ── Niveau 10 ──
	A(10, "Apothéose", "👼", "soin_zone", "aura_sacree", "Une lumière divine qui relève tous les blessés."),
	A(10, "Courroux du ciel", "⚡", "zone_cercle", "lumiere_zone", "La colère du ciel s'abat sur l'ennemi.", rayon=2),
]
