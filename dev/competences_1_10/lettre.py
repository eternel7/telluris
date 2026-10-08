"""Lettré 📜 — érudit universel, alchimiste, ingénieur et enchanteur (magie Illusoire)."""
from competences_1_10 import A, L

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Fiole corrosive", "🧪", "frappe", "alchimie", "Une fiole d'acide jetée avec précision."),
	A(1, "Citation savante", "📖", "entrave", "arcane", "Une citation si brillante qu'elle laisse l'ennemi interdit.", malus=("Int",)),
	A(1, "Tonique", "🍵", "soin", "alchimie", "Une infusion de sa composition qui remet d'aplomb."),
	A(1, "Étude de l'adversaire", "🔍", "buff_soi", "meditation", "Il observe, note, et comprend comment frapper.", stats=("Int", "Ag")),
	# ── Niveau 2 ──
	A(2, "Poudre détonante", "💥", "zone_cercle", "explosion_feu", "Un petit sachet de poudre qui fait grand bruit."),
	A(2, "Somnifère", "😴", "entrave", "alchimie", "Une fiole qui alourdit les paupières.", malus=("Ag", "Vol")),
	A(2, "Élixir de clarté", "💧", "pm_allie", "alchimie", "Un élixir qui clarifie l'esprit et rend du mana."),
	A(2, "Mécanisme à ressort", "⚙️", "saut", "saut", "Une semelle à ressort de son invention."),
	# ── Niveau 3 ──
	L(3, "Point faible noté", "📝", "marque", "Il a lu sur cette créature. Il sait où elle cède.",
	  {"cible": "ennemi", "jet": "magique", "portee": 5, "cout_pm": 15, "effets": {"buffs": {"R": "-3-{Int/8}"}, "duree": "2+{Int/40}"}},
	  remplace="fleche_alchimique"),
	A(3, "Glyphe protecteur", "🔰", "buff_allie", "enchantement", "Il trace un glyphe sur l'armure d'un compagnon.", stats=("R", "Vol")),
	# ── Niveau 4 ──
	A(4, "Éclat de savoir", "💡", "frappe", "eblouissant", "La connaissance brute, projetée comme une lame."),
	A(4, "Dissolvant", "🫗", "siphon", "alchimie", "Une fiole qui dissout la magie de la cible."),
	A(4, "Bombe de fumée", "💨", "esquive_soi", "poudre", "Un nuage dense qui couvre sa retraite."),
	A(4, "Onguent", "🧴", "regen_allie", "alchimie", "Un onguent à base de miel et d'herbes rares."),
	# ── Niveau 5 ──
	A(5, "Feu liquide", "🔥", "zone_rect", "feu", "Une fiole de feu liquide qui se répand devant lui."),
	A(5, "Paradoxe", "♾️", "entrave", "illusion", "Une énigme insoluble qui paralyse l'esprit de la cible.", malus=("Int", "Ag")),
	A(5, "Transmutation", "⚗️", "drain", "alchimie", "Il transmute la vitalité de la cible en la sienne."),
	A(5, "Mémoire du palais", "🏛️", "posture", "meditation", "Il se retire dans son palais mental, où rien ne l'atteint.", stats=("Int", "Vol")),
	# ── Niveau 6 ──
	L(6, "Lecture à voix haute", "📖", "enchantement", "Il lit à voix haute un vieux texte, et ses compagnons y puisent des forces nouvelles.",
	  {"cible": "allie", "portee": 4, "cout_pm": 25, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"pm": "3+{Int/10}"}},
	  remplace="grenade_alchimique"),
	A(6, "Panacée", "💊", "soin_zone", "alchimie", "Une brume curative qui soigne tout un groupe."),
	# ── Niveau 7 ──
	A(7, "Verbe de pouvoir", "🗣️", "frappe", "arcane", "Un mot ancien qui frappe comme un coup de masse."),
	A(7, "Gaz innervant", "☁️", "poison_pm", "poison", "Une vapeur qui ronge la volonté."),
	A(7, "Enchantement d'arme", "✨", "buff_allie", "enchantement", "Il enchante l'arme d'un compagnon pour la durée du combat.", stats=("F", "Ag")),
	A(7, "Automate de saut", "🤖", "saut", "saut", "Un harnais mécanique le projette au loin."),
	# ── Niveau 8 ──
	A(8, "Acide royal", "🧪", "poison", "alchimie", "L'acide qui dissout l'or — et le reste."),
	A(8, "Démonstration", "📐", "entrave", "arcane", "Une démonstration si implacable que l'ennemi en perd ses moyens.", malus=("Int", "Vol")),
	A(8, "Explosion en chaîne", "💥", "zone_cone", "impact_brulure/cone_souffle_feu", "Une série de fioles explosent en éventail."),
	A(8, "Grande encyclopédie", "📚", "cri", "meditation", "Il partage ce qu'il sait, et le groupe combat plus intelligemment.", stats=("Int", "Vol")),
	# ── Niveau 9 ──
	A(9, "Pierre philosophale", "💎", "rituel", "alchimie", "Un processus long qui libère une énergie terrible."),
	A(9, "Éclair de génie", "⚡", "frappe", "foudre", "Une idée si brillante qu'elle foudroie."),
	A(9, "Élixir de vie", "❤️", "soin", "soin_sacre", "L'élixir que cherchent tous les alchimistes."),
	A(9, "Rune de silence", "🤐", "siphon", "enchantement", "Une rune qui coupe la cible de toute magie."),
	# ── Niveau 10 ──
	A(10, "Œuvre au noir", "⚫", "zone_cercle", "ombre", "Le premier stade du Grand Œuvre, libéré sur l'ennemi.", rayon=2),
	A(10, "Savoir universel", "🌐", "posture", "enchantement", "Il embrasse toutes les connaissances, et rien ne le surprend plus.", stats=("Int", "Vol")),
]
