"""Nécromancien 💀 — maître de la mort ; sa voie ultime mène vers la Liche (Nécromancie)."""
from competences_1_10 import A, L

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Toucher glacé", "🥶", "frappe", "ombre", "Un toucher qui glace la chair jusqu'à l'os."),
	A(1, "Malaise", "🤢", "entrave", "poison", "Une nausée soudaine qui affaiblit la cible.", malus=("R",)),
	A(1, "Sangsue", "🩸", "drain", "drain", "Il boit un peu de la vie de la cible."),
	A(1, "Linceul", "⚰️", "buff_soi", "tombeau", "Il s'enveloppe d'un linceul qui le protège.", stats=("R", "Vol")),
	# ── Niveau 2 ──
	A(2, "Trait d'os", "🦴", "frappe", "roc", "Un éclat d'os projeté comme une flèche."),
	A(2, "Peste", "☠️", "poison", "poison", "Une maladie qui ronge la cible."),
	A(2, "Murmure des morts", "👻", "poison_pm", "spectre", "Les morts murmurent à l'oreille de la cible et l'épuisent."),
	A(2, "Pas de la tombe", "🪦", "saut", "spectre", "Il disparaît dans le sol et ressort plus loin."),
	# ── Niveau 3 ──
	A(3, "Nuage pestilentiel", "☁️", "zone_cercle", "poison", "Un nuage de pestilence qui empoisonne le groupe."),
	L(3, "Toucher de la tombe", "🦴", "drain", "Un toucher glacé qui arrache la vie et la rend à celui qui la prend.",
	  {"cible": "ennemi", "jet": "magique", "portee": 1, "cout_pm": 15, "effets": {"degats": "2D6+{Int/12}", "drain_pv": "20+{Vol/4}"}},
	  remplace="faiblesse"),
	# ── Niveau 4 ──
	A(4, "Lance d'ombre", "🌑", "frappe", "ombre", "Une lance d'ombre pure qui transperce."),
	A(4, "Vampirisme", "🧛", "drain", "drain", "Il se nourrit du sang de la cible."),
	A(4, "Siphon d'âme", "👻", "siphon", "spectre", "Il aspire l'énergie magique de la cible."),
	A(4, "Carapace d'os", "🦴", "posture", "tombeau", "Des os se soudent autour de lui en armure.", stats=("R",)),
	# ── Niveau 5 ──
	A(5, "Main du tombeau", "🖐️", "entrave", "tombeau", "Une main sort de terre et agrippe la cible.", malus=("Ag",)),
	L(5, "Miasme", "☠️", "poison", "Un cadavre se répand en miasme : les chairs vivantes alentour s'affaiblissent.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 21, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"R": "-4-{Vol/10}", "F": -4}, "duree": 4}},
	  remplace="explosion_de_cadavre"),
	L(5, "Armure d'ossements", "🦴", "tombeau", "Des os poussent sous la peau d'un compagnon et le cuirassent.",
	  {"cible": "allie", "portee": 4, "cout_pm": 21, "effets": {"buffs": {"R": "6+{Int/7}"}, "duree": 4}},
	  remplace="pacte_de_sang_noir"),
	A(5, "Énergie sombre", "⚫", "pm_allie", "ombre", "Il transfère de l'énergie sombre à un compagnon."),
	# ── Niveau 6 ──
	A(6, "Souffle de la tombe", "🌫️", "zone_cone", "impact_etincelles/cone_folie", "Un souffle froid venu d'outre-tombe."),
	L(6, "Pacte de chair", "🩸", "ombre", "Il se taille un peu de chair et en fait du mana.",
	  {"cible": "soi", "portee": 1, "cout_pm": 0, "effets": {"pm": "8+{Int/5}", "cout_pv": "15-{R/10}"}},
	  remplace="corruption"),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(6, "Drain vital", "🩸", "drain", "Il prend ce qui tient la cible debout. Ce qu'il en fait ensuite ne regarde personne.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 25, "effets": {"degats": "3D8+6", "buffs": {"F": -5}, "duree": 3, "drain_pv": 35}},
	  remplace="drain_vital"),
	# ── Niveau 7 ──
	A(7, "Doigt de mort", "☝️", "frappe", "ombre", "Il pointe le doigt, et la mort suit."),
	A(7, "Moisson d'âmes", "🌾", "drain", "drain", "Il moissonne la vie de la cible."),
	A(7, "Terreur", "😱", "entrave", "spectre", "Une terreur glaciale paralyse l'ennemi.", malus=("Vol", "Ag")),
	A(7, "Marche des ombres", "🌑", "saut", "ombre", "Il passe d'une ombre à l'autre."),
	# ── Niveau 8 ──
	A(8, "Fléau", "☠️", "zone_cercle", "poison", "Un fléau qui s'abat sur tout un groupe.", rayon=2),
	L(8, "Sangsue d'âme", "🌑", "spectre", "Il boit le mana de sa victime à travers ses blessures.",
	  {"cible": "ennemi", "jet": "magique", "portee": 4, "cout_pm": 25, "effets": {"degats": "2D8+{Int/10}", "drain_pm": 40, "drain_max": 20}},
	  remplace="vol_de_mana"),
	A(8, "Peau de cadavre", "🧟", "posture", "tombeau", "Sa peau devient froide et insensible.", stats=("R", "Vol")),
	A(8, "Malédiction de la liche", "📜", "poison_pm", "ombre", "Une malédiction qui empêche toute magie."),
	# ── Niveau 9 ──
	A(9, "Ténèbres dévorantes", "🌑", "frappe", "ombre", "Les ténèbres dévorent la cible."),
	L(9, "Sursis", "⌛", "levee_morts", "La mort elle-même accorde un sursis à un compagnon : ses plaies cessent de compter.",
	  {"cible": "allie", "portee": 4, "cout_pm": 48, "incantation": 2, "effets": {"buffs": {"R": "7+{Int/10}"}, "regen_pv": "2+{Int/20}", "duree": 5}},
	  remplace="rituel_de_mort"),
	L(9, "Linceul de spectres", "👻", "spectre", "Des spectres enveloppent les ennemis et glacent leurs membres.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 37, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"Ag": "-6-{Vol/10}", "F": -6, "V": -1}, "duree": 3}},
	  remplace="nuee_de_spectres"),
	A(9, "Banquet du vampire", "🧛", "sang", "drain", "Il paie de son sang un coup qui lui en rendra davantage."),
	# ── Niveau 10 ──
	L(10, "Mot d'effroi", "💀", "spectre", "Un mot qui n'aurait jamais dû être dit : la cible se fige d'horreur.",
	  {"cible": "ennemi", "jet": "magique", "portee": 6, "cout_pm": 40, "effets": {"buffs": {"Vol": "-10-{Vol/7}", "R": -10, "V": -2}, "duree": 2}},
	  remplace="mot_de_mort"),
	A(10, "Hiver éternel", "❄️", "entrave", "givre", "Le froid de la tombe fige la cible.", malus=("Ag", "F", "R")),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(10, "Étreinte du tombeau", "⚱️", "tombeau", "Le sol se souvient de tous ceux qu'il a reçus, et tend les mains vers celui qui marche dessus.",
	  {"cible": "ennemi", "jet": "magique", "portee": 8, "cout_pm": 40, "incantation": 3, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "effets": {"degats": "3D10+8", "buffs": {"R": -4, "V": -1}, "duree": 3, "drain_pv": 25, "drain_max": 12}},
	  remplace="etreinte_du_tombeau"),
]
