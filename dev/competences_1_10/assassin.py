"""Assassin 🗡 — l'ombre, le poison, la lame qui ne frappe qu'une fois."""
from competences_1_10 import A, P

OMBRE = ("sous-terrain", "catacombe", "donjon", "grotte", "couvert", "humide", "mine")

ENTREES = [
	# ── Niveau 1 ──
	P(1, "Pas feutrés", "🐾", "p_furtif", "Dans le noir, il n'est qu'un souffle de plus.", terrains=OMBRE),
	P(1, "Main froide", "🧊", "p_carac", "Une main qui ne tremble pas, même au moment de tuer.", stats=("Ag",)),
	A(1, "Coup de dague", "🗡️", "frappe", "lame", "Rapide, discret, précis."),
	A(1, "Lame enduite", "🧪", "poison", "poison", "Une goutte de venin sur le fil, et la plaie brûle."),
	A(1, "Entaille au tendon", "🦵", "entrave", "saignee", "Un coup bas qui coupe la fuite.", malus=("Ag",)),
	A(1, "Glissade", "👣", "saut", "furtif", "Il glisse d'une ombre à l'autre."),
	A(1, "Sang-froid du tueur", "❄️", "buff_soi", "furtif", "Le cœur ralentit, le regard se fixe.", stats=("Ag", "Vol")),
	# ── Niveau 2 ──
	P(2, "Silhouette effacée", "🌫️", "p_esquive", "On le regarde sans le voir."),
	A(2, "Coup dans le dos", "🔪", "frappe", "saignee", "La lame entre là où la victime ne regardait pas."),
	A(2, "Fiole de belladone", "🫙", "poison_pm", "poison", "Une poudre qui embrume l'esprit et vide les forces."),
	A(2, "Garrot", "🪢", "entrave", "saignee", "Une cordelette autour de la gorge, juste le temps d'affaiblir.", malus=("F", "Vol")),
	A(2, "Double lame", "⚔️", "zone_rect", "lame", "Ses deux lames frappent en même temps, à gauche et à droite."),
	A(2, "Pas dans l'ombre", "🌑", "esquive_soi", "furtif", "Il recule dans une ombre et disparaît un instant."),
	# ── Niveau 3 ──
	P(3, "Patience de l'araignée", "🕷️", "p_carac", "Il peut attendre des heures pour un seul geste.", stats=("Vol",)),
	A(3, "Perce-cœur", "❤️", "frappe", "lame", "La lame cherche le cœur entre deux côtes."),
	A(3, "Venin d'aspic", "🐍", "poison", "poison", "Un venin lent, qui ne pardonne pas."),
	A(3, "Saut de l'ombre", "🌑", "saut", "furtif", "Il disparaît ici pour réapparaître derrière sa cible."),
	A(3, "Poudre de pavot", "💨", "entrave", "poudre", "Un nuage de poudre qui engourdit les membres.", malus=("Ag", "Int")),
	# ── Niveau 4 ──
	P(4, "Réflexes de vipère", "🐍", "p_esquive", "Il esquive comme frappe le serpent : avant qu'on ne bouge."),
	A(4, "Lame de miséricorde", "🗡️", "frappe", "saignee", "La dague fine qu'on glisse dans la visière."),
	A(4, "Toxine paralysante", "🧪", "entrave", "poison", "La victime sent ses jambes se dérober.", malus=("Ag", "F")),
	A(4, "Fleur de lames", "🌸", "zone_carre", "lame", "Il tourne, et ses deux lames ouvrent une fleur sanglante."),
	A(4, "Sang du contrat", "🩸", "sang", "saignee", "Il s'ouvre la main pour sceller la mort de la cible."),
	A(4, "Voile de fumée", "🌫️", "esquive_soi", "poudre", "Une fiole brisée au sol, et il n'est plus là."),
	# ── Niveau 5 ──
	P(5, "Œil de nuit", "🌙", "p_carac", "Il voit dans le noir comme d'autres en plein jour.", stats=("Int",)),
	A(5, "Égorgement", "🔪", "frappe", "saignee", "Un geste, et la gorge s'ouvre."),
	A(5, "Ciguë", "☠️", "poison", "poison", "Le poison des philosophes, pour ceux qui parlent trop."),
	A(5, "Essence de mandragore", "🌿", "poison_pm", "poison", "Une essence qui ronge la volonté."),
	A(5, "Saut du chat", "🐈", "saut", "saut", "D'un toit à l'autre, d'une ombre à l'autre."),
	A(5, "Concentration mortelle", "🎯", "posture", "marque", "Plus rien n'existe que la cible.", stats=("Ag", "F")),
	# ── Niveau 6 ──
	A(6, "Lame dans les reins", "🗡️", "frappe", "lame", "Un coup sous la cuirasse, là où elle ne protège pas."),
	A(6, "Nuage toxique", "☁️", "zone_cercle", "poison", "Une fiole lancée, et le poison se répand sur le groupe."),
	A(6, "Voler le souffle", "😮‍💨", "siphon", "ombre", "Un coup au plexus, et la victime ne peut plus rien."),
	A(6, "Marque de mort", "💀", "entrave", "marque", "La cible sait qu'elle est condamnée, et ses forces la quittent.", malus=("Vol", "Ag")),
	# ── Niveau 7 ──
	P(7, "Ombre parmi les ombres", "🌑", "p_furtif", "Dans les souterrains, il est l'obscurité même.", terrains=OMBRE),
	A(7, "Assassinat", "💀", "frappe", "saignee", "Un seul coup, celui pour lequel on l'a payé."),
	A(7, "Venin du scorpion noir", "🦂", "poison", "poison", "Le poison le plus cher du marché noir."),
	A(7, "Danse des dagues", "🗡️", "zone_carre", "lame", "Les dagues volent autour de lui comme des guêpes.", rayon=2),
	A(7, "Pas de l'assassin", "👣", "saut", "furtif", "Il franchit la salle sans un bruit."),
	A(7, "Saignée silencieuse", "🩸", "drain", "drain", "Il boit la vie de sa victime avec sa lame."),
	# ── Niveau 8 ──
	P(8, "Insaisissable", "💨", "p_esquive", "On le frappe, et ce n'est déjà plus lui."),
	A(8, "Coup du cobra", "🐍", "frappe", "lame", "Une détente fulgurante, sans prévenir."),
	A(8, "Poudre de sommeil", "😴", "entrave", "poudre", "Un nuage qui alourdit les paupières et les bras.", malus=("Ag", "Vol")),
	A(8, "Venin de l'âme", "🖤", "poison_pm", "poison", "Un poison qui n'attaque pas le corps, mais l'esprit."),
	A(8, "Éventail de dagues", "🪭", "zone_cone", "impact_plaie/cone_griffe", "Une poignée de couteaux lancés en éventail."),
	A(8, "Oubli de la douleur", "💉", "sang", "rage", "Une drogue qui fait oublier ses blessures le temps d'un coup."),
	# ── Niveau 9 ──
	P(9, "Cœur de glace", "🧊", "p_carac", "Plus aucune émotion ne passe : il est la lame.", stats=("Vol",)),
	P(9, "Main de la mort", "☠️", "p_carac", "Chaque geste est économe, et chaque geste tue.", stats=("Ag",)),
	A(9, "Exécution silencieuse", "🤫", "frappe", "saignee", "La victime meurt sans avoir crié."),
	A(9, "Peste noire", "☠️", "poison", "poison", "Une contagion distillée dans une fiole."),
	A(9, "Ombre mortelle", "🌑", "saut", "furtif", "Il surgit de l'ombre la plus lointaine."),
	A(9, "Brume empoisonnée", "🌫️", "zone_cercle", "poison", "Une brume verte qui s'étend et ronge les poumons.", rayon=2),
	A(9, "Pacte de l'ombre", "🌑", "posture", "ombre", "Il appelle l'obscurité à lui et s'y installe.", stats=("Ag", "Vol")),
	# ── Niveau 10 ──
	P(10, "Maître de la guilde noire", "🖤", "p_esquive", "Son nom ne se prononce qu'à voix basse."),
	A(10, "Mort certaine", "⚰️", "frappe", "saignee", "Il n'a jamais raté un contrat."),
	A(10, "Fiole du maître empoisonneur", "⚗️", "poison", "poison", "Son chef-d'œuvre : un poison sans antidote."),
	A(10, "Fléau silencieux", "🗡️", "zone_carre", "lame", "Il traverse le groupe ennemi, et derrière lui chacun saigne.", rayon=2),
	A(10, "Disparition", "💨", "esquive_soi", "furtif", "Il n'était jamais là."),
]
