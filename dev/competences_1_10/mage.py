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
	L(3, "Entrave arcanique", "🔗", "arcane", "Des anneaux de force enserrent l'esprit de la cible : ses sorts lui coûtent davantage d'effort.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 15, "effets": {"buffs": {"Int": "-5-{Int/8}", "Vol": -5}, "duree": 3}},
	  remplace="missile_guide"),
	A(3, "Champ de force", "🛡️", "posture", "bouclier", "Un champ de force qu'il tient à bout de volonté.", stats=("R", "Int")),
	# ── Niveau 4 ──
	A(4, "Lame de mana", "🔪", "frappe", "enchantement", "Une lame faite de mana pur, qui ignore le métal.", **CC),
	L(4, "Onde de gravité", "🌑", "arcane", "Le sol pèse soudain plus lourd sous les pieds des ennemis rassemblés.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 18, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Ag": "-4-{Int/10}", "F": -4}, "duree": 3}},
	  remplace="explosion_arcanique"),
	A(4, "Ralentissement", "🐌", "entrave", "illusion", "Le temps s'épaissit autour de la cible.", malus=("Ag",)),
	A(4, "Rune de vigueur", "ᚢ", "buff_soi", "enchantement", "Une rune tracée sur sa poitrine qui le rend plus fort.", stats=("F", "R")),
	# ── Niveau 5 ──
	L(5, "Accélération", "⏩", "enchantement", "Il trace une rune de vitesse sur un compagnon, dont les gestes se font plus vifs.",
	  {"cible": "allie", "portee": 4, "cout_pm": 21, "effets": {"buffs": {"Ag": "6+{Int/7}"}, "duree": 4}},
	  remplace="eclair_de_bataille"),
	A(5, "Brûlure de mana", "🔥", "poison_pm", "arcane", "Le mana adverse se met à brûler son porteur."),
	A(5, "Bouclier partagé", "🛡️", "buff_allie", "bouclier", "Il projette un bouclier sur un compagnon.", stats=("R",)),
	A(5, "Saut de force", "🌀", "saut", "saut", "Une impulsion de force qui le projette en avant."),
	# ── Niveau 6 ──
	L(6, "Dôme de déviation", "🫧", "bouclier", "Un dôme qui fait dévier les coups portés à ceux qui se tiennent près de lui.",
	  {"cible": "soi", "portee": 1, "cout_pm": 25, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1}, "effets": {"esquive": "5+{Int/8}", "duree": 4}},
	  remplace="tourbillon_arcanique"),
	A(6, "Absorption", "🌀", "drain", "drain", "Il absorbe l'énergie vitale de la cible."),
	# ── Niveau 7 ──
	L(7, "Translation arcanique", "🔄", "saut", "Il échange sa place avec celle d'un compagnon en difficulté.",
	  {"cible": "allie", "portee": 6, "cout_pm": 29, "effets": {"echange": 1}},
	  remplace="lance_arcanique"),
	A(7, "Cage de force", "🔲", "entrave", "bouclier", "Des murs invisibles enferment l'ennemi.", malus=("Ag", "F")),
	L(7, "Onde de stupeur", "😵", "impact_etincelles/cone_decharge", "Une décharge sans flamme qui fige les premiers rangs une poignée d'instants.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 29, "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "decalage": 1, "longueur": 3, "angle": 90}, "effets": {"buffs": {"Ag": "-5-{Int/10}", "Int": -5, "V": -1}, "duree": 2}},
	  remplace="decharge"),
	A(7, "Égide de bataille", "🛡️", "cri", "bouclier", "Un dôme protecteur s'étend autour du groupe.", stats=("R", "Int")),
	# ── Niveau 8 ──
	A(8, "Frappe runique", "ᚦ", "frappe", "enchantement", "Le bâton gravé de runes frappe comme un marteau.", **CC),
	A(8, "Vide arcanique", "🕳️", "siphon", "arcane", "Il crée un vide qui aspire toute la magie de la cible."),
	L(8, "Pesanteur", "⚓", "meteore", "Toute une zone s'alourdit : les ennemis s'y traînent comme dans la vase.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 33, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "effets": {"buffs": {"Ag": "-5-{Int/12}", "F": -5, "V": -1}, "duree": 2}},
	  remplace="bombardement"),
	A(8, "Recharge", "🔋", "pm_allie", "enchantement", "Il transfère une part de son mana à un compagnon."),
	# ── Niveau 9 ──
	L(9, "Surcharge arcanique", "💥", "arcane", "Il force le mana au-delà de ce que son corps supporte. On le voit venir, et c'est terrible.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 45, "incantation": "5-{Int/30}", "effets": {"degats": "6D10+{Int/5}", "cout_pv": 10}},
	  remplace="rayon_desintegrant"),
	L(9, "Bulle temporelle", "⏳", "enchantement", "Il plie le temps autour d'un compagnon, qui agit plus vite que le monde.",
	  {"cible": "allie", "portee": 4, "cout_pm": 48, "incantation": 2, "effets": {"buffs": {"Ag": "5+{Int/10}", "V": 1}, "duree": 2}},
	  remplace="tempete_arcanique"),
	A(9, "Armure runique", "🛡️", "posture", "enchantement", "Des runes recouvrent son armure et brillent tant qu'il les nourrit.", stats=("R", "Int")),
	A(9, "Sceau de silence", "🤐", "poison_pm", "arcane", "Un sceau qui empêche la cible de puiser dans sa magie."),
	# ── Niveau 10 ──
	L(10, "Silence de masse", "🤐", "arcane", "Une onde qui étouffe le mana de tous les ennemis alentour.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 40, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "effets": {"buffs": {"Int": "-6-{Int/10}", "Vol": -6}, "duree": 5}},
	  remplace="nova_arcanique"),
	A(10, "Lame du mage-guerrier", "⚔️", "sang", "enchantement", "Il nourrit sa lame de sa propre vie.", **CC),
]
