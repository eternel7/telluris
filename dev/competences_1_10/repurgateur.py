"""Répurgateur 🔱 — chasseur de créatures maudites, combat le mal par le mal (Démonologie)."""
from competences_1_10 import A, L

MAG = {"jet": "magique", "portee": 5}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Lame d'argent", "🗡️", "frappe", "lame", "L'argent mord la chair maudite."),
	A(1, "Sel et cendre", "🧂", "entrave", "poudre", "Une poignée de sel béni jetée au visage du monstre.", malus=("Vol",)),
	A(1, "Œil du chasseur de sorcières", "👁️", "buff_soi", "marque", "Il voit ce que la créature voudrait cacher.", stats=("Vol", "Int")),
	A(1, "Signe noir", "🔱", "siphon", "demon_buff", "Un signe tracé dans l'air, qui aspire la magie de la cible.", **MAG),
	# ── Niveau 2 ──
	A(2, "Coup de pieu", "🪵", "frappe", "saignee", "Le pieu cherche le cœur, comme il se doit."),
	A(2, "Eau lustrale", "💧", "poison", "eau", "Une fiole d'eau bénite qui ronge la créature.", jet="cd", portee=4),
	A(2, "Sang contre sang", "🩸", "sang", "rage", "Il paie de son sang le droit de frapper le maudit."),
	A(2, "Pas du traqueur", "👣", "saut", "furtif", "Il surgit derrière la proie qu'il pistait."),
	# ── Niveau 3 ──
	L(3, "Huile consacrée", "🫗", "lame_sacree", "Il oint l'arme d'un compagnon d'une huile qui mord la chair maudite.",
	  {"cible": "allie", "portee": 4, "cout_pm": 15, "effets": {"buffs": {"F": "5+{Vol/8}", "Vol": 5}, "duree": 3}},
	  remplace="flamme_noire"),
	A(3, "Chaînes d'argent", "⛓️", "entrave", "marque", "Des chaînes d'argent qui brûlent la peau des maudits.", malus=("Ag", "F")),
	# ── Niveau 4 ──
	A(4, "Croix renversée", "✝️", "frappe", "lame_sacree", "Un coup porté avec la garde en croix."),
	L(4, "Cercle de sel", "🧂", "aura_sacree", "Un cercle de sel où ses compagnons tiennent mieux face aux puissances impies.",
	  {"cible": "allie", "portee": 4, "cout_pm": 18, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Vol": "5+{Vol/8}", "R": 5}, "duree": 3}},
	  remplace="soufre"),
	L(4, "Rite d'expulsion", "✝️", "lumiere", "Une formule d'expulsion qui arrache à la cible la force qui l'anime.",
	  {"cible": "ennemi", "jet": "magique", "portee": 3, "cout_pm": 18, "effets": {"degats": "1D8", "degats_pm": "2D6+{Vol/10}"}},
	  remplace="exorcisme_mineur"),
	A(4, "Garde du chasseur", "🛡️", "posture", "demon_buff", "Une garde forgée face aux griffes et aux crocs.", stats=("Vol", "R")),
	# ── Niveau 5 ──
	A(5, "Marque d'argent", "🎯", "poison_pm", "marque", "Une marque qui empêche le maudit de puiser dans ses forces."),
	A(5, "Carreau béni", "🏹", "frappe", "tir", "Un carreau d'arbalète trempé dans l'eau bénite.", jet="cd", portee=8),
	A(5, "Pacte inversé", "😈", "buff_soi", "demon_buff", "Il emprunte au démon sa force pour mieux le tuer.", stats=("F", "Vol")),
	A(5, "Fouet de flammes", "🔥", "zone_rect", "feu", "Une lanière de feu qui claque devant lui."),
	# ── Niveau 6 ──
	L(6, "Fer et sel", "🧂", "lame_sacree", "Une lame frottée de sel, un mot appris dans les vieux traités : la créature faiblit et son pouvoir fuit.",
	  {"cible": "ennemi", "jet": "cc", "portee": 1, "cout_pm": 25, "effets": {"degats": "1D6", "buffs": {"Vol": "-3-{Int/8}"}, "regen_pm": "-2-{Int/25}", "duree": 3}},
	  remplace="coup_du_tueur_de_monstres"),
	A(6, "Haleine de l'abîme", "🌋", "zone_cone", "impact_brulure/cone_souffle_feu", "Il souffle le feu de l'abîme sur les créatures."),
	# ── Niveau 7 ──
	A(7, "Brise-sortilège", "🚫", "siphon", "arcane", "Il brise la magie du sorcier comme on brise un os."),
	A(7, "Lame sanctifiée", "⚔️", "frappe", "lame_sacree", "Une lame consacrée qui ne connaît qu'une cible."),
	A(7, "Malédiction de l'inquisiteur", "📜", "poison", "poison", "Une malédiction qui ronge le maudit de l'intérieur.", **MAG),
	A(7, "Bond de la chasse", "🦇", "saut", "saut", "Il bondit sur la créature avant qu'elle ne s'envole."),
	# ── Niveau 8 ──
	L(8, "Sceau du proscrit", "⛔", "marque", "Il trace l'interdit : là, nulle magie ne se puise sans douleur.",
	  {"cible": "ennemi", "jet": "magique", "portee": 5, "cout_pm": 33, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Vol": "-6-{Int/8}", "Int": -6}, "duree": 4}},
	  remplace="feu_de_l_enfer_retourne"),
	A(8, "Pieu au cœur", "❤️", "drain", "saignee", "Le pieu s'enfonce, et la vie volée de la créature passe en lui."),
	A(8, "Sceau d'entrave", "🔱", "entrave", "demon_buff", "Un sceau démoniaque qui lie le monstre à la terre.", malus=("Ag", "Vol"), **MAG),
	A(8, "Endurance du traqueur", "🩸", "posture", "rage", "Des nuits de traque ont fait de lui un homme qu'on ne fatigue pas.", stats=("R", "Vol")),
	# ── Niveau 9 ──
	L(9, "Purge par le sang", "🩸", "drain", "Il brûle son propre sang pour arracher au maudit ce qui lui reste de pouvoir.",
	  {"cible": "ennemi", "jet": "magique", "portee": 3, "cout_pm": 37, "effets": {"degats": "4D10+{Vol/8}", "cout_pv": 10, "drain_pm": 30}},
	  remplace="execution_du_maudit"),
	A(9, "Purification par le feu", "🔥", "poison", "feu", "Le bûcher, sans le bûcher.", **MAG),
	A(9, "Tourbillon d'argent", "🌀", "zone_carre", "balayage", "Ses lames d'argent tournent autour de lui."),
	L(9, "Veillée du chasseur", "🕯️", "meditation", "Une longue prière sur un compagnon blessé, qui se relève plus ferme.",
	  {"cible": "allie", "portee": 4, "cout_pm": 48, "incantation": 2, "effets": {"buffs": {"Vol": "9+{Vol/7}"}, "regen_pv": "2+{Vol/20}", "duree": 5}},
	  remplace="rituel_d_exorcisme"),
	# ── Niveau 10 ──
	L(10, "Mise au ban", "🔨", "marque", "Il prononce le ban : la créature maudite chancelle et sa volonté se délite.",
	  {"cible": "ennemi", "jet": "magique", "portee": 5, "cout_pm": 40, "effets": {"buffs": {"Vol": "-10-{Int/7}", "Int": -10, "V": -1}, "duree": 3}},
	  remplace="fleau_des_demons"),
	A(10, "Pacte rompu", "💔", "siphon", "demon_buff", "Il rompt le pacte qui nourrit le maudit."),
]
