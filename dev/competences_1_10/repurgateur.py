"""Répurgateur 🔱 — chasseur de créatures maudites, combat le mal par le mal (Démonologie)."""
from competences_1_10 import A

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
	A(3, "Flamme noire", "🔥", "frappe", "projectile_infernal", "Une flamme infernale retournée contre ses semblables.", **MAG),
	A(3, "Chaînes d'argent", "⛓️", "entrave", "marque", "Des chaînes d'argent qui brûlent la peau des maudits.", malus=("Ag", "F")),
	# ── Niveau 4 ──
	A(4, "Croix renversée", "✝️", "frappe", "lame_sacree", "Un coup porté avec la garde en croix."),
	A(4, "Soufre", "💨", "zone_cercle", "soufre", "Une bouffée de soufre qui suffoque tout le nid.", **MAG),
	A(4, "Exorcisme mineur", "📿", "siphon", "lumiere", "Une prière qui arrache au maudit une part de sa force.", **MAG),
	A(4, "Garde du chasseur", "🛡️", "posture", "demon_buff", "Une garde forgée face aux griffes et aux crocs.", stats=("Vol", "R")),
	# ── Niveau 5 ──
	A(5, "Marque d'argent", "🎯", "poison_pm", "marque", "Une marque qui empêche le maudit de puiser dans ses forces."),
	A(5, "Carreau béni", "🏹", "frappe", "tir", "Un carreau d'arbalète trempé dans l'eau bénite.", jet="cd", portee=8),
	A(5, "Pacte inversé", "😈", "buff_soi", "demon_buff", "Il emprunte au démon sa force pour mieux le tuer.", stats=("F", "Vol")),
	A(5, "Fouet de flammes", "🔥", "zone_rect", "feu", "Une lanière de feu qui claque devant lui."),
	# ── Niveau 6 ──
	A(6, "Coup du tueur de monstres", "💀", "frappe", "saignee", "Le coup qu'on garde pour la créature qui a tué le village."),
	A(6, "Haleine de l'abîme", "🌋", "zone_cone", "impact_brulure/cone_souffle_feu", "Il souffle le feu de l'abîme sur les créatures."),
	# ── Niveau 7 ──
	A(7, "Brise-sortilège", "🚫", "siphon", "arcane", "Il brise la magie du sorcier comme on brise un os."),
	A(7, "Lame sanctifiée", "⚔️", "frappe", "lame_sacree", "Une lame consacrée qui ne connaît qu'une cible."),
	A(7, "Malédiction de l'inquisiteur", "📜", "poison", "poison", "Une malédiction qui ronge le maudit de l'intérieur.", **MAG),
	A(7, "Bond de la chasse", "🦇", "saut", "saut", "Il bondit sur la créature avant qu'elle ne s'envole."),
	# ── Niveau 8 ──
	A(8, "Feu de l'enfer retourné", "🔥", "zone_cercle", "explosion_feu", "Il retourne le feu des démons contre leur nid.", rayon=2, **MAG),
	A(8, "Pieu au cœur", "❤️", "drain", "saignee", "Le pieu s'enfonce, et la vie volée de la créature passe en lui."),
	A(8, "Sceau d'entrave", "🔱", "entrave", "demon_buff", "Un sceau démoniaque qui lie le monstre à la terre.", malus=("Ag", "Vol"), **MAG),
	A(8, "Endurance du traqueur", "🩸", "posture", "rage", "Des nuits de traque ont fait de lui un homme qu'on ne fatigue pas.", stats=("R", "Vol")),
	# ── Niveau 9 ──
	A(9, "Exécution du maudit", "⚔️", "frappe", "lame_sacree", "La sentence de l'inquisition, portée à la lame."),
	A(9, "Purification par le feu", "🔥", "poison", "feu", "Le bûcher, sans le bûcher.", **MAG),
	A(9, "Tourbillon d'argent", "🌀", "zone_carre", "balayage", "Ses lames d'argent tournent autour de lui."),
	A(9, "Rituel d'exorcisme", "📿", "rituel", "lumiere_zone", "Un rituel long, qui arrache le démon de sa chair.", **MAG),
	# ── Niveau 10 ──
	A(10, "Fléau des démons", "😈", "frappe", "projectile_infernal", "La flamme qui a chassé les démons de trois provinces.", **MAG),
	A(10, "Pacte rompu", "💔", "siphon", "demon_buff", "Il rompt le pacte qui nourrit le maudit."),
]
