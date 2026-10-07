"""Démoniste 😈 — invocateur infernal ; chaque pacte consume une part de son âme (Démonologie)."""
from competences_1_10 import A

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Trait infernal", "🔥", "frappe", "projectile_infernal", "Un trait de flamme infernale."),
	A(1, "Malédiction", "😈", "entrave", "demon_buff", "Une malédiction qui affaiblit la cible.", malus=("Vol",)),
	A(1, "Pacte mineur", "📜", "sang", "rage", "Il paie de son sang un sort plus puissant."),
	A(1, "Peau de démon", "👹", "buff_soi", "demon_buff", "Sa peau se couvre d'écailles infernales.", stats=("R", "Int")),
	# ── Niveau 2 ──
	A(2, "Flammes de l'abîme", "🔥", "poison", "feu", "Des flammes qui brûlent l'âme autant que le corps."),
	A(2, "Siphon infernal", "🌀", "siphon", "drain", "Il aspire la magie de la cible au profit de ses maîtres."),
	A(2, "Faille", "🕳️", "saut", "portail_infernal", "Une faille s'ouvre, il y entre, et ressort ailleurs."),
	A(2, "Sang pour le démon", "🩸", "drain", "drain", "Il offre le sang de la cible à son démon, qui lui en rend une part."),
	# ── Niveau 3 ──
	A(3, "Pluie de soufre", "🌋", "zone_cercle", "soufre", "Une pluie de soufre ardent sur les ennemis."),
	A(3, "Regard du démon", "👁️", "entrave", "demon_buff", "Le regard du démon paralyse la cible.", malus=("Ag", "Vol")),
	# ── Niveau 4 ──
	A(4, "Lance de l'enfer", "🔱", "frappe", "projectile_infernal", "Une lance de feu infernal."),
	A(4, "Corruption de l'âme", "🖤", "poison_pm", "demon_buff", "Une corruption qui ronge la volonté de la cible."),
	A(4, "Bouclier infernal", "🛡️", "posture", "demon_buff", "Un bouclier de flammes noires l'entoure.", stats=("R", "Vol")),
	A(4, "Don du démon", "🎁", "pm_allie", "demon_buff", "Il partage avec un compagnon l'énergie de son pacte."),
	# ── Niveau 5 ──
	A(5, "Explosion infernale", "💥", "zone_cercle", "explosion_feu", "Une explosion de feu noir.", rayon=2),
	A(5, "Chaînes de l'enfer", "⛓️", "entrave", "demon_buff", "Des chaînes infernales enserrent la cible.", malus=("Ag", "F")),
	A(5, "Pacte de puissance", "📜", "sang", "rage", "Il sacrifie sa chair pour une puissance infernale."),
	A(5, "Fièvre infernale", "🤒", "poison", "soufre", "Une fièvre qui brûle de l'intérieur."),
	# ── Niveau 6 ──
	A(6, "Souffle de l'abîme", "🌋", "zone_cone", "impact_brulure/cone_souffle_feu", "Un souffle de flammes infernales."),
	A(6, "Rapt d'âme", "👻", "drain", "drain", "Il arrache un fragment d'âme à la cible."),
	# ── Niveau 7 ──
	A(7, "Feu de l'âme", "🔥", "frappe", "projectile_infernal", "Un feu qui brûle l'âme de la cible."),
	A(7, "Peur infernale", "😱", "entrave", "demon_buff", "Une terreur venue des enfers.", malus=("Vol", "Ag")),
	A(7, "Siphon de l'abîme", "🕳️", "siphon", "drain", "L'abîme aspire la magie de la cible."),
	A(7, "Forme démoniaque", "👹", "posture", "demon_buff", "Il prend un instant la forme de son démon.", stats=("F", "R")),
	# ── Niveau 8 ──
	A(8, "Tempête de feu noir", "🔥", "zone_carre", "feu", "Un tourbillon de feu noir autour de lui.", rayon=2),
	A(8, "Pacte de sang majeur", "🩸", "sang", "rage", "Un pacte majeur, payé au prix fort."),
	A(8, "Malédiction de l'abîme", "📜", "poison_pm", "demon_buff", "Une malédiction qui coupe la cible de toute magie."),
	A(8, "Porte de l'enfer", "🚪", "saut", "portail_infernal", "Il ouvre une porte vers l'enfer, et en ressort ailleurs."),
	# ── Niveau 9 ──
	A(9, "Rituel infernal", "⛧", "rituel", "portail_infernal", "Un rituel long qui ouvre une brèche sur l'enfer."),
	A(9, "Flamme du seigneur démon", "🔥", "frappe", "projectile_infernal", "La flamme d'un seigneur démon."),
	A(9, "Peste infernale", "☠️", "poison", "soufre", "Une peste venue des enfers."),
	A(9, "Banquet de l'abîme", "🍷", "drain", "drain", "L'abîme se nourrit de la cible, et lui en rend une part."),
	# ── Niveau 10 ──
	A(10, "Apocalypse", "🌋", "zone_cercle", "meteore", "Le ciel s'ouvre et le feu infernal tombe.", rayon=2),
	A(10, "Âme damnée", "💀", "entrave", "demon_buff", "Il marque l'âme de la cible pour l'enfer.", malus=("Vol", "F", "R")),
]
