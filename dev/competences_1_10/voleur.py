"""Voleur 🔑 — doigts légers, coups bas, fuite élégante ; pièges déjà livrés (dev/gen_pieges.py)."""
from competences_1_10 import A, P

OMBRE = ("sous-terrain", "catacombe", "donjon", "grotte", "couvert", "humide", "mine")

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Coup bas", "🦵", "entrave", "coup_lourd", "Un coup de genou là où ça fait mal.", malus=("Ag",)),
	A(1, "Lame de poche", "🔪", "frappe", "lame", "Un canif sorti de nulle part."),
	A(1, "Sable aux yeux", "🏖️", "entrave", "poudre", "Une poignée de sable, et l'ennemi frappe au hasard.", malus=("Ag", "Int")),
	A(1, "Filer à l'anglaise", "💨", "saut", "furtif", "Il est là, puis il n'y est plus."),
	A(1, "Chance du gredin", "🍀", "buff_soi", "furtif", "Tout lui réussit aujourd'hui, et il le sait.", stats=("Ch", "Ag")),
	# ── Niveau 2 ──
	P(2, "Doigts de fée", "🪄", "p_carac", "Il dénoue une bourse sans que le nœud ne s'en aperçoive.", stats=("Ag",)),
	A(2, "Croc-en-jambe", "🦶", "entrave", "coup_lourd", "Un pied qui traîne, et le colosse s'étale.", malus=("Ag",)),
	A(2, "Surin", "🗡️", "frappe", "saignee", "Un coup vicieux, porté de près."),
	A(2, "Esquive du coupe-bourse", "🤸", "esquive_soi", "furtif", "Il roule sous la table et ressort de l'autre côté."),
	A(2, "Bourse lestée", "💰", "frappe", "poing", "Une bourse pleine de plomb, au bout d'une lanière."),
	A(2, "Couteaux de lancer", "🔪", "zone_rect", "lame", "Trois couteaux, trois cibles.", jet="cd", portee=4),
	# ── Niveau 3 ──
	A(3, "Coup du pavé", "🧱", "frappe", "coup_lourd", "Ce qui traîne dans la rue fait une très bonne arme."),
	A(3, "Poivre des quais", "🌶️", "entrave", "poudre", "Une poignée de poivre noir qui fait pleurer les plus durs.", malus=("Ag", "Vol")),
	A(3, "Pickpocket de combat", "🫳", "siphon", "furtif", "Il vole jusqu'au souffle de son adversaire."),
	A(3, "Saut de toit", "🏚️", "saut", "saut", "Il connaît chaque toit de la ville par cœur."),
	# ── Niveau 4 ──
	P(4, "Pas de souris", "🐭", "p_furtif", "Dans les caves et les égouts, il est chez lui.", terrains=OMBRE),
	A(4, "Lame cachée", "🗡️", "frappe", "lame", "La lame sort de la manche au dernier moment."),
	A(4, "Cordelette", "🪢", "entrave", "saignee", "Une cordelette qui entrave les chevilles.", malus=("Ag",)),
	A(4, "Bombe fumigène", "💨", "zone_cercle", "poudre", "Un éclat de verre, un nuage âcre, et la confusion."),
	A(4, "Sale coup", "😈", "sang", "saignee", "Il se blesse en frappant, mais le coup en vaut la peine."),
	A(4, "Gouaille", "😏", "buff_soi", "chant", "Un bon mot lancé au bon moment : il reprend confiance.", stats=("Cha", "Ch")),
	# ── Niveau 5 ──
	P(5, "Chance insolente", "🎲", "p_carac", "Les dés tombent toujours du bon côté pour lui.", stats=("Ch",)),
	A(5, "Coup du lapin", "🐇", "frappe", "coup_lourd", "Un coup sec à la nuque."),
	A(5, "Vol à l'arraché", "🫳", "siphon", "furtif", "Il arrache à sa victime ce qui lui restait de forces."),
	A(5, "Pluie de clous", "📌", "zone_cercle", "lame", "Il jette une poignée de clous rouillés sous les pieds ennemis."),
	A(5, "Roulade", "🤸", "saut", "saut", "Une roulade sous les jambes de l'ennemi."),
	A(5, "Fiel de crapaud", "🐸", "poison", "poison", "Une lame trempée dans un fiel que vend l'apothicaire véreux."),
	# ── Niveau 6 ──
	A(6, "Coup de surin", "🔪", "frappe", "saignee", "Un coup vif dans le flanc, sans prévenir."),
	A(6, "Cendre au visage", "🌫️", "entrave", "poudre", "Une poignée de cendre chaude, en plein visage.", malus=("Ag", "Int")),
	A(6, "Tourbillon de coutelas", "🌀", "zone_carre", "lame", "Il fait tournoyer ses lames dans la ruelle étroite."),
	A(6, "Bouclier de fortune", "🪑", "posture", "garde", "Un tabouret, une planche, un couvercle : tout lui sert de bouclier.", stats=("Ag", "R")),
	# ── Niveau 7 ──
	P(7, "Feinte de rue", "🎭", "p_esquive", "Il a appris l'escrime dans les ruelles, et ça se voit."),
	A(7, "Coup de crosse", "🔨", "entrave", "coup_lourd", "Un coup derrière l'oreille, qui fait voir trente-six chandelles.", malus=("Int", "Ag")),
	A(7, "Lame du coupe-jarret", "🗡️", "frappe", "saignee", "La lame qui fait la réputation du quartier."),
	A(7, "Grimpe éclair", "🧗", "saut", "saut", "Une gouttière, un balcon, et il est hors d'atteinte."),
	A(7, "Mauvaise fiole", "🧪", "poison_pm", "poison", "Une fiole volée chez un alchimiste, qui ronge l'esprit."),
	A(7, "Réseau d'informateurs", "🕸️", "buff_allie", "chant", "Il souffle à un compagnon ce qu'il a appris sur l'ennemi.", stats=("Int", "Ag")),
	# ── Niveau 8 ──
	P(8, "Roi des ruelles", "👑", "p_carac", "Dans la ville basse, chaque pavé lui obéit.", stats=("Ag",)),
	A(8, "Coup du maître voleur", "🔑", "frappe", "lame", "Un coup si propre qu'on croirait un tour de passe-passe."),
	A(8, "Feu grégeois de poche", "🔥", "zone_cercle", "feu", "Une petite fiole qui fait un très grand feu.", jet="cd", portee=4),
	A(8, "Détrousser l'âme", "👻", "siphon", "ombre", "Il vole même ce qui ne se voit pas."),
	A(8, "Chausse-trappe lancée", "📌", "entrave", "lame", "Des pointes semées sous les pas, qui font boiter.", malus=("Ag",)),
	A(8, "Disparition dans la foule", "👥", "esquive_soi", "double", "Il se fond dans la mêlée comme dans une foule de marché."),
	# ── Niveau 9 ──
	P(9, "Ange gardien des voleurs", "😇", "p_carac", "Il devrait être mort cent fois.", stats=("Ch",)),
	P(9, "Toujours une issue", "🚪", "p_esquive", "Il trouve toujours une sortie, même là où il n'y en a pas."),
	A(9, "Coup du prince des voleurs", "🤴", "frappe", "saignee", "Le coup qui a fait de lui une légende des bas-fonds."),
	A(9, "Nuage de poivre", "🌶️", "zone_cercle", "poudre", "Une grosse bourse de poivre éventrée au milieu des ennemis.", rayon=2),
	A(9, "Lame dans la manche", "🗡️", "drain", "saignee", "Chaque coup volé lui rend des forces."),
	A(9, "Fuite par les toits", "🏚️", "saut", "saut", "Plus personne ne le rattrape quand il prend les toits."),
	A(9, "Bagout", "🗣️", "cri", "chant", "Il harangue ses compagnons comme une foule de marché.", stats=("Cha", "Ag"), rayon=2),
	# ── Niveau 10 ──
	P(10, "Main invisible", "🫥", "p_carac", "On dit qu'il a volé la couronne sur la tête du roi.", stats=("Ag",)),
	A(10, "Le grand coup", "💎", "frappe", "lame", "Le casse de sa vie, mais avec une lame."),
	A(10, "Tempête de couteaux", "🌪️", "zone_carre", "lame", "Une volée de couteaux autour de lui.", rayon=2),
	A(10, "Voleur d'ombres", "🌑", "siphon", "ombre", "Il vole jusqu'à l'énergie qui fait vivre les mages."),
	A(10, "Prestidigitation", "🎩", "esquive_soi", "double", "Un tour de passe-passe, et il est derrière vous."),
]
