"""Démoniste 😈 — invocateur infernal ; chaque pacte consume une part de son âme (Démonologie)."""
from competences_1_10 import A, L

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
	L(3, "Brume sulfureuse", "🌫️", "soufre", "Une brume jaune qui amollit les chairs de ceux qu'elle enveloppe.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 15, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"R": "-3-{Vol/10}", "Vol": -3}, "duree": 3}},
	  remplace="pluie_de_soufre"),
	A(3, "Regard du démon", "👁️", "entrave", "demon_buff", "Le regard du démon paralyse la cible.", malus=("Ag", "Vol")),
	# ── Niveau 4 ──
	L(4, "Transfusion impie", "🩸", "drain", "Il verse son propre sang dans les plaies d'un compagnon.",
	  {"cible": "allie", "portee": 4, "cout_pm": 18, "effets": {"pv": "14+{Vol/3}", "cout_pv": 7}},
	  remplace="lance_de_l_enfer"),
	A(4, "Corruption de l'âme", "🖤", "poison_pm", "demon_buff", "Une corruption qui ronge la volonté de la cible."),
	A(4, "Bouclier infernal", "🛡️", "posture", "demon_buff", "Un bouclier de flammes noires l'entoure.", stats=("R", "Vol")),
	A(4, "Don du démon", "🎁", "pm_allie", "demon_buff", "Il partage avec un compagnon l'énergie de son pacte."),
	# ── Niveau 5 ──
	L(5, "Cercle de terreur", "😱", "portail_infernal", "Un cercle de flammes noires où l'on ne voit plus que ses propres cauchemars.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 21, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Vol": "-4-{Vol/10}", "Ag": -4}, "duree": 4}},
	  remplace="explosion_infernale"),
	A(5, "Chaînes de l'enfer", "⛓️", "entrave", "demon_buff", "Des chaînes infernales enserrent la cible.", malus=("Ag", "F")),
	A(5, "Pacte de puissance", "📜", "sang", "rage", "Il sacrifie sa chair pour une puissance infernale."),
	A(5, "Fièvre infernale", "🤒", "poison", "soufre", "Une fièvre qui brûle de l'intérieur."),
	# ── Niveau 6 ──
	A(6, "Souffle de l'abîme", "🌋", "zone_cone", "impact_brulure/cone_souffle_feu", "Un souffle de flammes infernales."),
	L(6, "Soif du pacte", "😈", "drain", "Il paie le démon de son sang pour boire celui d'un autre.",
	  {"cible": "ennemi", "jet": "magique", "portee": 4, "cout_pm": 25, "effets": {"degats": "3D8+{Int/10}", "cout_pv": 8, "drain_pv": 50, "drain_max": "{Vol/3}"}},
	  remplace="rapt_d_ame"),
	L(6, "Ombre du familier", "👹", "demon_buff", "Son familier se glisse dans l'ombre d'un compagnon et détourne les coups qui le visent.",
	  {"cible": "allie", "portee": 4, "cout_pm": 25, "effets": {"buffs": {"Ag": "4+{Vol/12}"}, "esquive": "5+{Vol/8}", "duree": 4}},
	  remplace="griffe_du_familier"),
	# ── Niveau 7 ──
	L(7, "Marque de damnation", "⛧", "marque", "Une marque qui ronge la résistance de la cible : chaque coup la trouve plus tendre.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 29, "effets": {"buffs": {"R": "-8-{Vol/7}", "Vol": -8}, "duree": 4}},
	  remplace="feu_de_l_ame"),
	A(7, "Peur infernale", "😱", "entrave", "demon_buff", "Une terreur venue des enfers.", malus=("Vol", "Ag")),
	A(7, "Siphon de l'abîme", "🕳️", "siphon", "drain", "L'abîme aspire la magie de la cible."),
	A(7, "Forme démoniaque", "👹", "posture", "demon_buff", "Il prend un instant la forme de son démon.", stats=("F", "R")),
	# ── Niveau 8 ──
	A(8, "Tempête de feu noir", "🔥", "zone_carre", "feu", "Un tourbillon de feu noir autour de lui.", rayon=2),
	L(8, "Pacte de sang partagé", "🩸", "demon_buff", "Il paie de sa vie la fureur de tous ceux qui l'entourent.",
	  {"cible": "soi", "portee": 1, "cout_pm": 33, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1}, "effets": {"buffs": {"Int": "7+{Vol/8}", "F": 7}, "cout_pv": 12, "duree": 4}},
	  remplace="pacte_de_sang_majeur"),
	A(8, "Malédiction de l'abîme", "📜", "poison_pm", "demon_buff", "Une malédiction qui coupe la cible de toute magie."),
	A(8, "Porte de l'enfer", "🚪", "saut", "portail_infernal", "Il ouvre une porte vers l'enfer, et en ressort ailleurs."),
	# ── Niveau 9 ──
	A(9, "Rituel infernal", "⛧", "rituel", "portail_infernal", "Un rituel long qui ouvre une brèche sur l'enfer."),
	A(9, "Flamme du seigneur démon", "🔥", "frappe", "projectile_infernal", "La flamme d'un seigneur démon."),
	A(9, "Peste infernale", "☠️", "poison", "soufre", "Une peste venue des enfers."),
	A(9, "Banquet de l'abîme", "🍷", "drain", "drain", "L'abîme se nourrit de la cible, et lui en rend une part."),
	# ── Niveau 10 ──
	L(10, "Ténèbres de l'abîme", "🕳️", "portail_infernal", "L'abîme s'ouvre sous les ennemis : la terreur les cloue sur place.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 40, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "effets": {"buffs": {"Vol": "-5-{Vol/12}", "Ag": -5, "V": -1}, "duree": 3}},
	  remplace="apocalypse"),
	A(10, "Âme damnée", "💀", "entrave", "demon_buff", "Il marque l'âme de la cible pour l'enfer.", malus=("Vol", "F", "R")),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(10, "Invocation majeure", "🔯", "portail_infernal", "Il n'appelle plus une créature : il lui prête sa peau pour la durée du contrat.",
	  {"cible": "soi", "portee": 1, "cout_pm": 40, "effets": {"buffs": {"F": 14, "Int": 14, "R": 8}, "regen_pv": 2, "regen_pm": 2, "duree": 5, "cout_pv": 15}},
	  remplace="invocation_majeure"),
]
