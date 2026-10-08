"""Prêtre ✝ — guérisseur indispensable, la lumière qui relève (magie Sainte)."""
from competences_1_10 import A, L

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Lumière sainte", "✨", "frappe", "lumiere", "Un rai de lumière qui brûle l'impur."),
	A(1, "Prière de soin", "🙏", "soin", "soin_sacre", "Une prière murmurée, et la plaie se referme."),
	A(1, "Bénédiction", "🕊️", "buff_allie", "aura_sacree", "Il bénit un compagnon, qui se sent plus fort.", stats=("Vol", "R")),
	A(1, "Réprimande", "☝️", "entrave", "lumiere", "Un mot sévère qui fait plier l'ennemi.", malus=("Vol",)),
	# ── Niveau 2 ──
	L(2, "Oraison du chevet", "🙏", "soin_sacre", "La prière du chevet des mourants, qui en ramène plus d'un.",
	  {"cible": "allie", "portee": 4, "cout_pm": 12, "effets": {"soin": "1D8+{Vol/8}"}},
	  remplace="grace"),
	A(2, "Clarté", "💡", "pm_allie", "meditation", "Il éclaire l'esprit d'un compagnon et lui rend son énergie."),
	A(2, "Feu sacré", "🔥", "poison", "lumiere", "Une flamme sacrée qui brûle longtemps."),
	A(2, "Sanctuaire", "⛪", "posture", "bouclier", "Il se recueille, et une lumière le protège.", stats=("R", "Vol")),
	# ── Niveau 3 ──
	A(3, "Cercle de guérison", "⭕", "soin_zone", "soin_vague", "Un cercle de lumière soigne tous ceux qui s'y tiennent."),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(3, "Main du guérisseur", "🙏", "soin_sacre", "Il améliore n'importe quel soin, qu'il soit naturel ou magique. Souvent d'assez peu, toujours d'assez.",
	  {"cible": "allie", "portee": 2, "cout_pm": 15, "effets": {"pv": 16, "regen_pv": 2, "duree": 3}},
	  remplace="main_du_guerisseur"),
	# passive rééquilibrée entre vocations (médiane de son palier)
	L(3, "Clerc", "📖", None, "Des années à lire et à recopier des piles de livres. Le savoir des grimoires lui vient plus vite qu'aux autres.",
	  {"effets": {"buffs": {"Int": 4}}},
	  remplace="clerc", mode="passive"),
	# ── Niveau 4 ──
	L(4, "Voile sacré", "⛪", "soin_sacre", "Une lueur enveloppe un compagnon : les coups glissent sur lui.",
	  {"cible": "allie", "portee": 4, "cout_pm": 18, "effets": {"esquive": "4+{Vol/8}", "duree": 3}},
	  remplace="eclat_divin"),
	A(4, "Protection divine", "🛡️", "buff_allie", "bouclier", "Un bouclier de lumière sur un compagnon.", stats=("R",)),
	A(4, "Purification", "💧", "siphon", "lumiere", "Il purifie la magie impie de la cible."),
	L(4, "Aube éblouissante", "🌅", "eblouissant", "Une lumière d'aube aveuglante qui fait chanceler les ennemis rassemblés.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 18, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Ag": "-4-{Vol/10}", "F": -4}, "duree": 3}},
	  remplace="lumiere_de_l_aube"),
	# ── Niveau 5 ──
	A(5, "Guérison majeure", "❤️‍🩹", "soin", "soin_sacre", "Une prière puissante qui referme les blessures graves."),
	A(5, "Chaînes de lumière", "⛓️", "entrave", "lumiere", "Des chaînes de lumière entravent l'ennemi.", malus=("Ag", "F")),
	A(5, "Hymne", "🎶", "cri", "chant", "Un hymne qui fortifie tous ceux qui l'entendent.", stats=("Vol", "R")),
	A(5, "Saut de foi", "🕊️", "saut", "aura_sacree", "Il s'en remet à la foi, et elle le porte."),
	# ── Niveau 6 ──
	L(6, "Contrition", "🙏", "lumiere", "La lumière fait ployer la cible sous le poids de ses fautes.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 25, "effets": {"buffs": {"F": "-7-{Vol/7}", "Int": -7}, "duree": 4}},
	  remplace="colonne_de_lumiere"),
	L(6, "Martyre", "🕯️", "soin_vague", "Il donne sa propre vie pour en sauver une autre.",
	  {"cible": "allie", "portee": 1, "cout_pm": 10, "effets": {"pv": "10+{Vol/4}", "cout_pv": 12}},
	  remplace="source_de_grace"),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(6, "Bénédiction du Prophète", "🕊️", "soin_sacre", "Son aura de bienfaisance irradie ceux qui le suivent, qu'ils l'aient demandé ou non.",
	  {"cible": "allie", "portee": 4, "cout_pm": 25, "effets": {"pv": 18, "buffs": {"R": 6, "Vol": 3}, "regen_pv": 1, "duree": 4}},
	  remplace="benediction_du_prophete"),
	# ── Niveau 7 ──
	A(7, "Exorcisme", "📿", "poison_pm", "lumiere", "Il chasse les esprits impurs, et la magie avec eux."),
	A(7, "Prière de masse", "🙏", "soin_zone", "soin_vague", "Toute l'assemblée est soignée d'une seule prière."),
	L(7, "Halo de protection", "😇", "lumiere_zone", "Un halo descend sur ses compagnons et détourne les coups qui leur sont portés.",
	  {"cible": "allie", "portee": 4, "cout_pm": 29, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"esquive": "4+{Vol/12}", "duree": 4}},
	  remplace="chatiment_divin"),
	A(7, "Rempart de la foi", "🛡️", "posture", "aura_sacree", "Sa foi devient un rempart impénétrable.", stats=("R", "Vol")),
	# ── Niveau 8 ──
	L(8, "Verdict céleste", "⚖️", "descente_celeste", "Le ciel juge la cible : elle plie le genou sous le verdict.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 33, "effets": {"buffs": {"F": "-9-{Vol/7}", "Int": -9, "V": -1}, "duree": 2}},
	  remplace="jugement_celeste"),
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
	L(10, "Interdit céleste", "🌩️", "lumiere_zone", "Le ciel interdit toute une zone aux impies, qui s'y traînent sans force.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 40, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "effets": {"buffs": {"F": "-5-{Vol/12}", "Int": -5, "V": -1}, "duree": 3}},
	  remplace="courroux_du_ciel"),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(10, "Oracle", "👁️‍🗨️", "aura_sacree", "Ses prédictions sont complexes à décrypter et s'avèrent souvent exactes. Celui qu'il désigne ne peut plus vraiment échouer.",
	  {"cible": "allie", "portee": 6, "cout_pm": 40, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"pv": 22, "pm": 5, "buffs": {"Ch": 5, "Vol": 3}, "duree": 3}},
	  remplace="oracle"),
	# passive rééquilibrée entre vocations (médiane de son palier)
	L(10, "Thaumaturge", "✨", None, "Le nombre de gens morts sous ses mains se compte sur les doigts d'une seule. Il les connaît tous par leur nom.",
	  {"effets": {"buffs": {"Vol": 6, "Int": 4}, "regen_pv": 4}},
	  remplace="thaumaturge", mode="passive"),
]
