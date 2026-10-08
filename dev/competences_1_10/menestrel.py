"""Ménestrel 🎶 — chanteur, espion, négociateur ; sa musique ouvre des portes (magie Illusoire)."""
from competences_1_10 import A, L

CC = {"jet": "cc", "portee": 1}

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Note discordante", "🎵", "entrave", "chant", "Une note fausse qui fait grincer les dents.", malus=("Vol",)),
	A(1, "Coup de luth", "🪕", "frappe", "poing", "Le luth sert aussi à ça.", **CC),
	A(1, "Chanson à boire", "🍺", "buff_allie", "chant", "Un refrain joyeux qui redonne courage.", stats=("Vol", "Cha")),
	# ── Niveau 2 ──
	A(2, "Berceuse", "😴", "entrave", "chant", "Une mélodie douce qui alourdit les paupières.", malus=("Ag", "Vol")),
	A(2, "Mélodie apaisante", "🎶", "regen_allie", "chant", "Une mélodie qui apaise les blessures."),
	A(2, "Satire", "😂", "poison_pm", "chant", "Une chanson moqueuse qui sape le moral."),
	L(2, "Couplet entraînant", "🎵", "chant", "Un air qui fait bouger les pieds de toute la troupe, et qui dure tant qu'on le fredonne.",
	  {"cible": "allie", "portee": 4, "cout_pm": 12, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Ag": "2+{Cha/10}"}, "duree": "1+{Cha/30}"}},
	  remplace="pas_de_danse"),
	# ── Niveau 3 ──
	A(3, "Cri strident", "📢", "zone_cercle", "chant", "Un cri si aigu qu'il blesse les oreilles."),
	A(3, "Air de bravoure", "🎺", "cri", "chant", "Un air héroïque qui galvanise ses alliés.", stats=("F", "Vol")),
	# ── Niveau 4 ──
	A(4, "Accord dissonant", "🎸", "frappe", "chant", "Un accord qui fait vibrer les os."),
	L(4, "Refrain tenu", "🎶", "chant", "Tant qu'il tient la note, ceux qui l'entourent tiennent bon.",
	  {"cible": "soi", "portee": 1, "cout_pm": 10, "maintien": 3, "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1}, "effets": {"buffs": {"Vol": "2+{Cha/10}"}}},
	  remplace="ballade_du_heros"),
	A(4, "Charme du barde", "💕", "entrave", "illusion", "Un sourire et un vers, et l'ennemi baisse sa garde.", malus=("Int", "Vol")),
	A(4, "Chant de repos", "😌", "pm_allie", "chant", "Un chant qui rend le souffle et l'énergie."),
	# ── Niveau 5 ──
	A(5, "Lame du conteur", "🗡️", "frappe", "lame", "Une dague sortie au milieu d'une histoire.", **CC),
	A(5, "Requiem", "⚰️", "poison", "chant", "Un chant funèbre qui ronge la cible."),
	L(5, "Tournée générale", "🍺", "chant", "Une chanson de taverne qui panse les plaies du groupe ; le ménestrel se nourrit des applaudissements.",
	  {"cible": "allie", "portee": 4, "cout_pm": 21, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"soin": "1D6+{Cha/10}", "partage_soin": 20}},
	  remplace="chur"),
	A(5, "Pirouette", "🤸", "saut", "saut", "Une pirouette acrobatique qui le met hors de portée."),
	# ── Niveau 6 ──
	A(6, "Tonnerre de tambour", "🥁", "zone_cone", "impact_etincelles/cone_folie", "Un roulement de tambour qui déferle devant lui."),
	A(6, "Sérénade", "🌹", "soin", "chant", "Une sérénade qui soigne le cœur et le corps."),
	# ── Niveau 7 ──
	A(7, "Chanson de geste", "📯", "cri", "chant", "La chanson des grandes batailles, que tous reprennent.", stats=("F", "R"), rayon=2),
	L(7, "Fausse note", "🎻", "impact_etincelles/cone_folie", "Une dissonance qui fait grincer les esprits et s'enfuir le mana.",
	  {"cible": "ennemi", "jet": "magique", "portee": 1, "cout_pm": 29, "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "longueur": 4, "angle": 90, "decalage": 1}, "effets": {"degats_pm": "1D6+{Cha/12}", "buffs": {"Int": "-2-{Cha/10}"}, "duree": 2}},
	  remplace="voix_d_or"),
	A(7, "Danse macabre", "💀", "entrave", "spectre", "Une danse qui fait trembler les morts et les vivants.", malus=("Vol", "Ag")),
	A(7, "Ritournelle", "🔁", "posture", "chant", "Une ritournelle qu'il ne cesse de fredonner, et qui le protège.", stats=("Cha", "Ag")),
	# ── Niveau 8 ──
	A(8, "Crescendo", "📈", "frappe", "chant", "La musique monte, monte, et frappe."),
	A(8, "Opéra", "🎭", "zone_cercle", "illusion_zone", "Une scène entière qui s'abat sur l'ennemi.", rayon=2),
	A(8, "Hymne de victoire", "🏆", "buff_allie", "chant", "Un hymne qui annonce la victoire.", stats=("Vol", "F")),
	A(8, "Complainte", "😢", "poison_pm", "chant", "Une complainte si triste qu'elle désespère."),
	# ── Niveau 9 ──
	A(9, "Symphonie", "🎼", "rituel", "chant", "Une symphonie longue à jouer, terrible à entendre."),
	A(9, "Voix de sirène", "🧜", "entrave", "illusion", "Une voix qui envoûte et paralyse.", malus=("Vol", "Int")),
	A(9, "Chant de vie", "💚", "soin_zone", "soin_vague", "Un chant qui soigne tout un groupe."),
	A(9, "Pas du saltimbanque", "🎪", "saut", "saut", "Un saut acrobatique digne des foires."),
	# ── Niveau 10 ──
	A(10, "Cantate des héros", "🎶", "cri", "chant", "La cantate que chantent les héros avant de mourir — ou de vaincre.", stats=("F", "Vol"), rayon=2),
	A(10, "Dernière note", "🎵", "frappe", "chant", "La note finale, qui laisse le silence derrière elle."),
]
