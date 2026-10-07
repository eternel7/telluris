"""Duelliste 🤺 — précision, vitesse et panache plutôt que robustesse."""
from competences_1_10 import A, P

ENTREES = [
	# ── Niveau 1 ──
	P(1, "Poignet souple", "🤌", "p_carac", "La lame tourne dans sa main comme une plume.", stats=("Ag",)),
	P(1, "Élégance", "🎩", "p_carac", "Même dans la boue, il garde l'allure d'un salon.", stats=("Cha",)),
	A(1, "Coup droit", "🗡️", "frappe", "lame", "La première leçon de toute salle d'armes, exécutée à la perfection."),
	A(1, "Battement", "🤺", "entrave", "lame", "Un coup sec sur la lame adverse, qui ouvre la garde.", malus=("Ag",)),
	A(1, "En garde", "⚜️", "esquive_soi", "garde", "Il prend la garde, et l'on comprend qu'il ne sera pas facile à toucher."),
	A(1, "Marche-fente", "🦶", "saut", "saut", "Un pas glissé, puis la détente : il est déjà au contact."),
	A(1, "Riposte", "↩️", "frappe", "lame", "Il pare et rend la politesse dans le même mouvement."),
	# ── Niveau 2 ──
	P(2, "Œil de l'escrimeur", "👁️", "p_esquive", "Il lit l'épaule avant que la lame ne parte."),
	P(2, "Port de tête", "👑", "p_carac", "Son assurance déroute ceux qui le croisent.", stats=("Vol",)),
	A(2, "Flèche", "➡️", "saut", "saut", "Une course en extension, la pointe en avant."),
	A(2, "Coup de manchette", "✂️", "entrave", "saignee", "La lame effleure le poignet, et l'arme pèse soudain plus lourd.", malus=("F",)),
	A(2, "Taille en tierce", "⚔️", "frappe", "lame", "Un coup haut, porté avec la grâce d'une révérence."),
	A(2, "Estafilade", "🩸", "poison", "saignee", "Une entaille fine, qui saigne plus qu'on ne le croit."),
	A(2, "Défi d'honneur", "🧤", "buff_soi", "aura_bataille", "Il jette le gant, et son sang s'échauffe.", stats=("Ag", "Cha")),
	# ── Niveau 3 ──
	P(3, "Grâce naturelle", "🦢", "p_carac", "Chacun de ses gestes semble avoir été répété mille fois.", stats=("Ag",)),
	A(3, "Double attaque", "⚔️", "frappe", "lame", "Deux coups si proches qu'on n'en voit qu'un."),
	A(3, "Désarmement", "🫳", "entrave", "garde", "D'une torsion du poignet, l'arme adverse lui échappe presque.", malus=("F", "Ag")),
	A(3, "Danse des lames", "💃", "zone_rect", "balayage", "Un enchaînement léger qui touche trois adversaires."),
	A(3, "Garde de soie", "🧵", "posture", "garde", "Une garde si souple qu'elle ne laisse aucune prise.", stats=("Ag",)),
	# ── Niveau 4 ──
	P(4, "Jambes de danseur", "🩰", "p_esquive", "Il ne se trouve jamais là où tombe le coup."),
	P(4, "Coup d'œil", "🎯", "p_carac", "Il voit l'ouverture avant qu'elle n'existe.", stats=("Int",)),
	A(4, "Coup de Jarnac", "🦵", "entrave", "saignee", "Un coup bas, légal mais déloyal, au défaut du genou.", malus=("Ag",)),
	A(4, "Fente basse", "🗡️", "frappe", "lame", "Il plonge sous la garde et pique au flanc."),
	A(4, "Volte", "🌀", "zone_carre", "balayage", "Une pirouette et sa lame fait le tour de ses adversaires."),
	A(4, "Bravade", "😏", "buff_soi", "aura_bataille", "Un sourire insolent : il se sait meilleur.", stats=("Cha", "Ag")),
	A(4, "Saut de côté", "↗️", "saut", "saut", "Il s'efface d'un bond et réapparaît dans le dos de l'adversaire."),
	# ── Niveau 5 ──
	P(5, "Main du prévôt", "✋", "p_carac", "La main de celui qui enseigne : jamais crispée, jamais lâche.", stats=("Ag",)),
	P(5, "Prestance", "🎭", "p_carac", "Il se bat comme on joue sur scène, et le public le sent.", stats=("Cha",)),
	A(5, "Coup de pointe", "📍", "frappe", "lame", "La pointe trouve le cœur de la cible comme une aiguille son chas."),
	A(5, "Liement", "🔗", "entrave", "garde", "Il enroule sa lame autour de l'autre et l'emporte.", malus=("Ag", "F")),
	A(5, "Saignées multiples", "🩸", "poison", "saignee", "Dix petites coupures, et aucune ne se ferme."),
	A(5, "Salut du maître", "🤺", "buff_allie", "aura_bataille", "Il salue un compagnon, et celui-ci se tient soudain mieux.", stats=("Ag", "Vol")),
	A(5, "Moulinet du bretteur", "⚔️", "zone_rect", "balayage", "Un moulinet de poignet, rapide et tranchant."),
	# ── Niveau 6 ──
	P(6, "Réflexes de chat", "🐈", "p_esquive", "Il esquive comme un chat retombe sur ses pattes."),
	A(6, "Coup de maître", "🏅", "frappe", "lame", "Un coup qu'on ne voit qu'une fois par vie."),
	A(6, "Feinte double", "🎭", "entrave", "double", "Il menace à gauche, puis à droite, et l'adversaire ne sait plus où se garder.", malus=("Int", "Ag")),
	A(6, "Éventail d'acier", "🪭", "zone_cone", "impact_eclat_dore/cone_tueur_demon", "La lame se déploie en éventail devant lui."),
	A(6, "Pas de l'ombre", "👣", "saut", "furtif", "Il glisse d'une ombre à l'autre."),
	# ── Niveau 7 ──
	P(7, "Lame vivante", "🗡️", "p_carac", "L'épée n'est plus un outil : elle est le prolongement de son bras.", stats=("Ag",)),
	P(7, "Panache", "🪶", "p_carac", "Il ne recule jamais sans un mot d'esprit.", stats=("Vol",)),
	A(7, "Botte secrète", "🤫", "frappe", "saignee", "Un coup transmis de maître à élève, jamais écrit."),
	A(7, "Coup du papillon", "🦋", "zone_carre", "balayage", "Une volte légère, et partout autour la lame a mordu."),
	A(7, "Prise de fer", "🔗", "entrave", "garde", "Sa lame cloue celle de l'autre et la paralyse.", malus=("F", "Ag")),
	A(7, "Assaut de grâce", "💫", "buff_soi", "aura_bataille", "Une série parfaite, enchaînée sans un faux pas.", stats=("Ag", "F")),
	A(7, "Coup de pied de salle", "🦶", "frappe", "poing", "Un coup de botte, que les règles tolèrent à peine."),
	# ── Niveau 8 ──
	P(8, "Instinct du duel", "⚖️", "p_esquive", "Face à un seul adversaire, il est presque intouchable."),
	P(8, "Œil de faucon", "🦅", "p_carac", "Pas un mouvement adverse ne lui échappe.", stats=("Int",)),
	A(8, "Pointe au cœur", "❤️", "frappe", "lame", "La pointe entre entre deux côtes."),
	A(8, "Tourbillon du bretteur", "🌀", "zone_carre", "balayage", "Une danse circulaire où chaque pas porte un coup.", rayon=2),
	A(8, "Saignée d'artère", "🩸", "poison", "saignee", "Une coupure précise, là où le sang court le plus vite."),
	A(8, "Inspiration du maître d'armes", "📖", "buff_allie", "chant", "Un conseil glissé à l'oreille d'un compagnon, qui change tout.", stats=("Ag", "F")),
	A(8, "Pas du vent", "🌬️", "saut", "vent", "Il franchit la distance comme une bourrasque."),
	# ── Niveau 9 ──
	P(9, "Perfection du geste", "✨", "p_carac", "Pas un muscle ne se contracte en vain.", stats=("Ag",)),
	P(9, "Aura de champion", "🏆", "p_carac", "On sait, en le voyant entrer, qui gagnera le duel.", stats=("Cha",)),
	A(9, "Coup du roi", "👑", "frappe", "lame", "Le coup réservé aux adversaires dignes de lui."),
	A(9, "Main paralysée", "🫳", "entrave", "saignee", "Une entaille aux tendons : la main ne serre plus.", malus=("F", "Ag")),
	A(9, "Vent de lames", "🌪️", "zone_cone", "impact_eclat_dore/cone_tueur_demon", "Une série de coups si rapide qu'elle semble faire du vent."),
	A(9, "Garde absolue", "🛡️", "posture", "garde", "Aucune lame ne passe : il les détourne toutes.", stats=("Ag", "R")),
	A(9, "Sang du duel", "🩸", "drain", "saignee", "Chaque touche lui rend de la vigueur."),
	# ── Niveau 10 ──
	P(10, "Légende de l'escrime", "📜", "p_esquive", "Les traités d'escrime citeront son nom."),
	A(10, "Coup parfait", "💎", "frappe", "lame", "Le coup que tout bretteur cherche, et que lui seul a trouvé."),
	A(10, "Ballet mortel", "💃", "zone_carre", "balayage", "Une danse dont aucun partenaire ne se relève.", rayon=2),
	A(10, "Envol du bretteur", "🦅", "saut", "saut", "Il bondit par-dessus la mêlée et retombe la pointe en avant."),
	A(10, "Maître du terrain", "♟️", "cri", "aura_bataille", "Il dirige le combat comme une leçon, et chacun y trouve sa place.", stats=("Ag", "Vol"), rayon=2),
]
