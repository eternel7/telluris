"""Paladin 🛡 — protecteur au-delà des remparts, arme qui brûle de lumière (magie Sainte)."""
from competences_1_10 import A, L

MAG = {"jet": "magique", "portee": 5}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Coup béni", "✨", "frappe", "lame_sacree", "La masse s'abat, nimbée d'une lueur dorée."),
	A(1, "Bouclier de la foi", "🛡️", "esquive_soi", "bouclier", "Sa foi dresse devant lui un bouclier que l'on ne voit pas.", stats=("Vol",)),
	A(1, "Châtiment léger", "⚖️", "entrave", "lumiere", "Un éclat de lumière qui fait baisser les yeux du mécréant.", malus=("Vol",), **MAG),
	# ── Niveau 2 ──
	A(2, "Frappe du juste", "⚔️", "frappe", "lame_sacree", "Un coup porté sans haine, mais sans pitié."),
	A(2, "Prière de guérison", "🙏", "soin", "soin_sacre", "Une prière courte, et une plaie se referme."),
	A(2, "Bénédiction de l'acier", "🗡️", "buff_allie", "aura_sacree", "Il bénit l'arme d'un compagnon, qui frappe plus juste.", stats=("F", "Vol")),
	A(2, "Bond du croisé", "🦅", "saut", "saut", "Il s'élance au secours d'un frère d'armes."),
	# ── Niveau 3 ──
	A(3, "Lumière aveuglante", "☀️", "zone_cercle", "lumiere_zone", "Un éclat sacré qui brûle les yeux des impurs.", **MAG),
	L(3, "Mains secourables", "🙌", "soin_sacre", "Il referme la plaie d'un compagnon, et un peu de cette grâce lui revient.",
	  {"cible": "allie", "portee": 1, "cout_pm": 15, "effets": {"soin": "1D8+{Vol/10}", "partage_soin": 30}},
	  remplace="serment_de_protection"),
	# ── Niveau 4 ──
	L(4, "Châtiment juste", "⚖️", "lumiere", "Ce n'est pas son bras qui frappe, c'est sa foi.",
	  {"cible": "ennemi", "jet": "cc", "portee": 1, "cout_pm": 18, "effets": {"degats": "2D8+{Vol/8}"}},
	  remplace="masse_de_lumiere"),
	A(4, "Soins du champ de bataille", "⛑️", "regen_allie", "soin_sacre", "Il impose les mains et laisse la grâce agir."),
	L(4, "Jugement", "⚖️", "lame_sacree", "Il désigne le coupable du plat de sa lame : désormais, c'est à lui que l'impie doit répondre.",
	  {"cible": "ennemi", "jet": "cc", "portee": 1, "cout_pm": 18, "effets": {"degats": "1D8+{Vol/15}", "buffs": {"F": -9}, "provocation": 1, "duree": 3}},
	  remplace="jugement"),
	A(4, "Aura de courage", "🦁", "cri", "aura_sacree", "Autour de lui, plus personne ne recule.", stats=("Vol", "R")),
	# ── Niveau 5 ──
	A(5, "Brûlure sacrée", "🔥", "poison", "lumiere", "Une lumière qui continue de brûler longtemps après le coup.", **MAG),
	A(5, "Charge sainte", "🐎", "saut", "aura_sacree", "Il franchit la mêlée, porté par sa foi."),
	A(5, "Égide", "🛡️", "buff_allie", "bouclier", "Il étend sa protection sur un compagnon menacé.", stats=("R",)),
	A(5, "Frappe du croisé", "✝️", "frappe", "lame_sacree", "Un coup qui porte la croix gravée dans le métal."),
	# ── Niveau 6 ──
	L(6, "Serment de garde", "🤝", "lien", "Il jure de garder un compagnon : sa foi amortit les coups, son corps prend le reste.",
	  {"cible": "allie", "portee": 4, "cout_pm": 20, "maintien": "6-{Vol/30}", "effets": {"lien_vie": {"part": "40+{Vol/4}", "reduction": 20}}},
	  remplace="marteau_de_justice"),
	A(6, "Mains de lumière", "🙌", "soin_zone", "soin_vague", "La lumière jaillit de ses mains et soigne ceux qui l'entourent."),
	# ── Niveau 7 ──
	A(7, "Lame de l'aube", "🌅", "frappe", "lumiere", "Une lame qui brille comme le soleil levant."),
	A(7, "Bannissement", "🚫", "siphon", "lumiere_zone", "Il chasse la magie impie hors du corps ennemi.", **MAG),
	A(7, "Rempart sacré", "🏰", "posture", "aura_sacree", "Une muraille de foi se dresse autour de lui.", stats=("R", "Vol")),
	A(7, "Grâce restauratrice", "💫", "soin", "soin_sacre", "Une grâce qui relève les plus touchés."),
	# ── Niveau 8 ──
	A(8, "Colère divine", "⚡", "zone_cercle", "lumiere_zone", "La lumière tombe du ciel sur les ennemis rassemblés.", rayon=2, **MAG),
	A(8, "Purge", "🔥", "poison", "lumiere", "Une flamme sacrée qui ronge l'impur.", **MAG),
	A(8, "Vœu du protecteur", "🤝", "buff_allie", "lien", "Il jure de protéger un compagnon, et celui-ci se sent invincible.", stats=("R", "Vol")),
	A(8, "Bond de l'ange", "👼", "saut", "descente_celeste", "Il descend sur le champ de bataille comme un ange."),
	# ── Niveau 9 ──
	A(9, "Épée de la foi", "🗡️", "frappe", "lame_sacree", "Le coup d'un homme qui ne doute plus."),
	A(9, "Vague sainte", "🌊", "zone_cone", "impact_eclat_dore/cone_tueur_demon", "Une vague de lumière tranchante qui s'ouvre devant lui."),
	A(9, "Croisade", "✝️", "cri", "aura_bataille", "Il lève sa masse, et la troupe entière marche avec lui.", stats=("F", "Vol"), rayon=2),
	A(9, "Pénitence", "⛓️", "entrave", "lumiere", "Le mécréant ploie sous le poids de ses péchés.", malus=("F", "Ag"), **MAG),
	# ── Niveau 10 ──
	A(10, "Jugement dernier", "⚖️", "frappe", "lumiere", "Le coup qui pèse l'âme avant de la frapper."),
	A(10, "Miracle", "🌟", "soin_zone", "aura_sacree", "Un miracle, et ceux qui tombaient se relèvent."),
]
