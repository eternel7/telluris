"""Magicien de combat 🌀 — la magie au service de la guerre : armes enchantées, boucliers arcaniques."""
from competences_1_10 import A, L

CC = {"jet": "cc", "portee": 1}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Projectile arcanique", "🔮", "frappe", "arcane", "Une sphère d'énergie violette qui file vers la cible."),
	A(1, "Lame chargée", "⚔️", "frappe", "enchantement", "Le bâton s'illumine au moment du coup.", **CC),
	A(1, "Bouclier réflexe", "🛡️", "esquive_soi", "bouclier", "Un bouclier qui se dresse avant même qu'il ne le décide.", stats=("Int",)),
	A(1, "Pas éclair", "⚡", "saut", "saut", "Un pas, un éclair, il est ailleurs."),
	# ── Niveau 2 ──
	A(2, "Rayon de force", "💫", "entrave", "arcane", "Un rayon qui pèse sur les membres de l'ennemi.", malus=("F", "Ag")),
	A(2, "Arme enchantée", "🗡️", "buff_allie", "enchantement", "Il grave une rune sur l'arme d'un compagnon.", stats=("F",)),
	A(2, "Brèche de mana", "🕳️", "siphon", "arcane", "Il ouvre une brèche dans la réserve de mana adverse."),
	A(2, "Onde de choc arcanique", "💥", "zone_rect", "arcane", "Une onde violette qui repousse le premier rang."),
	# ── Niveau 3 ──
	L(3, "Projectile savant", "🔮", "arcane", "Plus le mage est savant, plus le trait est lourd et plus il porte loin.",
	  {"cible": "ennemi", "jet": "magique", "portee": "4+{Int/15}", "cout_pm": 15, "effets": {"degats": "2D{Int/8}"}},
	  remplace="missile_guide"),
	A(3, "Champ de force", "🛡️", "posture", "bouclier", "Un champ de force qu'il tient à bout de volonté.", stats=("R", "Int")),
	# ── Niveau 4 ──
	A(4, "Lame de mana", "🔪", "frappe", "enchantement", "Une lame faite de mana pur, qui ignore le métal.", **CC),
	A(4, "Explosion arcanique", "💥", "zone_cercle", "arcane", "Une sphère d'énergie éclate au milieu des ennemis."),
	A(4, "Ralentissement", "🐌", "entrave", "illusion", "Le temps s'épaissit autour de la cible.", malus=("Ag",)),
	A(4, "Rune de vigueur", "ᚢ", "buff_soi", "enchantement", "Une rune tracée sur sa poitrine qui le rend plus fort.", stats=("F", "R")),
	# ── Niveau 5 ──
	A(5, "Éclair de bataille", "⚡", "frappe", "foudre", "La foudre des champs de bataille, maîtrisée."),
	A(5, "Brûlure de mana", "🔥", "poison_pm", "arcane", "Le mana adverse se met à brûler son porteur."),
	A(5, "Bouclier partagé", "🛡️", "buff_allie", "bouclier", "Il projette un bouclier sur un compagnon.", stats=("R",)),
	A(5, "Saut de force", "🌀", "saut", "saut", "Une impulsion de force qui le projette en avant."),
	# ── Niveau 6 ──
	A(6, "Tourbillon arcanique", "🌀", "zone_carre", "arcane", "L'énergie tourbillonne autour de lui et frappe tout ce qu'elle touche."),
	A(6, "Absorption", "🌀", "drain", "drain", "Il absorbe l'énergie vitale de la cible."),
	# ── Niveau 7 ──
	A(7, "Lance arcanique", "🔱", "frappe", "arcane", "Une lance de pure énergie qui transperce tout."),
	A(7, "Cage de force", "🔲", "entrave", "bouclier", "Des murs invisibles enferment l'ennemi.", malus=("Ag", "F")),
	A(7, "Décharge", "⚡", "zone_cone", "impact_etincelles/cone_decharge", "Une décharge en éventail qui grille les premiers rangs."),
	A(7, "Égide de bataille", "🛡️", "cri", "bouclier", "Un dôme protecteur s'étend autour du groupe.", stats=("R", "Int")),
	# ── Niveau 8 ──
	A(8, "Frappe runique", "ᚦ", "frappe", "enchantement", "Le bâton gravé de runes frappe comme un marteau.", **CC),
	A(8, "Vide arcanique", "🕳️", "siphon", "arcane", "Il crée un vide qui aspire toute la magie de la cible."),
	A(8, "Bombardement", "☄️", "zone_cercle", "meteore", "Une pluie de projectiles s'abat sur la zone.", rayon=2),
	A(8, "Recharge", "🔋", "pm_allie", "enchantement", "Il transfère une part de son mana à un compagnon."),
	# ── Niveau 9 ──
	L(9, "Surcharge arcanique", "💥", "arcane", "Il force le mana au-delà de ce que son corps supporte. On le voit venir, et c'est terrible.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 45, "incantation": 3, "effets": {"degats": "6D10+{Int/5}", "cout_pv": 10}},
	  remplace="rayon_desintegrant"),
	A(9, "Tempête arcanique", "⛈️", "rituel", "arcane", "Il rassemble l'énergie pendant de longs instants avant de la libérer."),
	A(9, "Armure runique", "🛡️", "posture", "enchantement", "Des runes recouvrent son armure et brillent tant qu'il les nourrit.", stats=("R", "Int")),
	A(9, "Sceau de silence", "🤐", "poison_pm", "arcane", "Un sceau qui empêche la cible de puiser dans sa magie."),
	# ── Niveau 10 ──
	A(10, "Nova arcanique", "💥", "zone_carre", "arcane", "Une explosion d'énergie pure tout autour de lui.", rayon=2),
	A(10, "Lame du mage-guerrier", "⚔️", "sang", "enchantement", "Il nourrit sa lame de sa propre vie.", **CC),
]
