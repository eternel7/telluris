"""Élémentaliste 🔥 — feu, glace, foudre, roc, eau et vent (magie Élémentaire)."""
from competences_1_10 import A, L

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Étincelle", "✨", "frappe", "feu", "Une étincelle claque au bout des doigts et mord la cible."),
	A(1, "Gel des membres", "🥶", "entrave", "givre", "Le froid saisit les articulations de l'ennemi.", malus=("Ag",)),
	A(1, "Peau de granit", "🪨", "buff_soi", "roc", "Sa peau prend le grain du granit.", stats=("R",)),
	A(1, "Brise", "🌬️", "saut", "vent", "Le vent le soulève et le dépose plus loin."),
	# ── Niveau 2 ──
	L(2, "Rafale tranchante", "🌪️", "vent", "Une lame d'air qui balaie tout ce qui se tient devant lui.",
	  {"cible": "ennemi", "jet": "magique", "portee": 1, "cout_pm": 12, "zone": {"forme": "rectangle", "origine": "lanceur", "orientation": "cible", "longueur": 1, "largeur": 3, "decalage": 1}, "effets": {"degats": "1D{Int/6}"}},
	  remplace="trait_de_glace"),
	A(2, "Arc électrique", "⚡", "siphon", "foudre", "Un arc qui court sur la cible et grille ses réserves."),
	A(2, "Brûlure", "🔥", "poison", "feu", "Une flamme qui s'accroche et ne s'éteint pas."),
	A(2, "Pluie douce", "🌧️", "regen_allie", "source", "Une ondée qui lave et apaise les plaies d'un compagnon."),
	# ── Niveau 3 ──
	A(3, "Gerbe de flammes", "🔥", "zone_cercle", "explosion_feu", "Le feu éclate au milieu des ennemis."),
	A(3, "Bourrasque", "🌪️", "entrave", "vent", "Une rafale qui fait chanceler les plus solides.", malus=("Ag", "F")),
	# ── Niveau 4 ──
	A(4, "Lance de foudre", "⚡", "frappe", "foudre", "La foudre se fait lance et transperce."),
	A(4, "Torrent", "🌊", "zone_rect", "eau", "Un jet d'eau furieux qui balaie le premier rang."),
	A(4, "Givre rampant", "❄️", "poison", "givre", "Le gel gagne la chair, lentement, inexorablement."),
	A(4, "Armure de glace", "🧊", "posture", "givre", "Une carapace de glace se forme et se reforme autour de lui.", stats=("R",)),
	# ── Niveau 5 ──
	A(5, "Projection de roc", "🪨", "frappe", "roc", "Un bloc arraché au sol vole vers la cible."),
	A(5, "Langue de feu", "🔥", "zone_cone", "impact_brulure/cone_souffle_feu", "Les flammes jaillissent de ses mains en éventail."),
	L(5, "Peau de basalte", "🪨", "roc", "Sa peau se couvre de pierre noire, et la garde tant qu'il la tient en pensée.",
	  {"cible": "soi", "portee": 1, "cout_pm": 12, "maintien": 2, "effets": {"buffs": {"R": "3+{Int/8}"}, "esquive": 3}},
	  remplace="echo_du_tonnerre"),
	A(5, "Souffle des éléments", "🌀", "buff_allie", "nature_buff", "Il prête à un compagnon la force des éléments.", stats=("R", "F")),
	# ── Niveau 6 ──
	A(6, "Tempête de grêle", "🌨️", "zone_cercle", "givre", "La grêle s'abat sur une large zone.", rayon=2),
	A(6, "Forme de vapeur", "♨️", "esquive_soi", "eau", "Son corps se fait brume, et les coups le traversent."),
	# ── Niveau 7 ──
	L(7, "Ligne de braise", "🔥", "explosion_feu", "Une ligne de braises jetée en travers du passage. Qui la franchit s'y brûle — ami ou ennemi.",
	  {"cible": "ennemi", "jet": "magique", "portee": 4, "cout_pm": 22, "maintien": 3, "zone": {"forme": "rectangle", "origine": "cible", "orientation": "cible", "longueur": 1, "largeur": 3}, "effets": {"degats": "2D6+{Int/12}"}},
	  remplace="colonne_de_feu", zone_persistante=True),
	A(7, "Éclair en chaîne", "⚡", "zone_cone", "impact_etincelles/cone_decharge", "La foudre bondit de cible en cible devant lui."),
	A(7, "Sables mouvants", "🏜️", "entrave", "roc", "Le sol se dérobe sous l'ennemi.", malus=("Ag",)),
	A(7, "Source de mana", "💧", "pm_allie", "source", "Il fait jaillir pour un compagnon une source d'énergie pure."),
	# ── Niveau 8 ──
	A(8, "Javelot de glace", "🧊", "frappe", "givre", "Un javelot de glace pure, lourd comme la mort."),
	A(8, "Siphon des éléments", "🌀", "drain", "vent", "Il aspire la vie de la cible avec le vent."),
	A(8, "Tremblement", "🌋", "zone_carre", "roc", "La terre tremble autour de lui et renverse les ennemis.", rayon=2),
	A(8, "Rituel de la tempête", "⛈️", "rituel", "foudre", "Il invoque l'orage, et l'orage met du temps à venir."),
	# ── Niveau 9 ──
	A(9, "Brasier", "🔥", "poison", "feu", "Un feu qui dévore longtemps."),
	A(9, "Raz-de-marée", "🌊", "zone_rect", "eau", "Une vague qui emporte le premier rang ennemi."),
	A(9, "Cyclone", "🌪️", "saut", "vent", "Le vent l'emporte et le dépose où il veut."),
	A(9, "Bouclier des quatre vents", "🛡️", "cri", "bouclier", "Les vents tournent autour du groupe et détournent les coups.", stats=("R", "Ag"), rayon=2),
	# ── Niveau 10 ──
	L(10, "Égide élémentaire", "🔰", "bouclier", "Feu, glace, foudre et roc tournent autour de ses compagnons et les protègent.",
	  {"cible": "allie", "portee": 4, "cout_pm": 40, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"buffs": {"R": "7+{Vol/10}"}, "esquive": "4+{Vol/12}", "duree": 5}},
	  remplace="fureur_elementaire"),
	A(10, "Zéro absolu", "❄️", "entrave", "givre", "Le froid absolu fige la cible dans la glace.", malus=("Ag", "F")),
	# signature recalibrée (~1,15 × l'archétype généré du niveau)
	L(10, "Courroux des éléments", "🌋", "meteore", "Il n'appelle plus le feu : il le laisse arriver, et s'écarte de son chemin.",
	  {"cible": "ennemi", "jet": "magique", "portee": 12, "cout_pm": 40, "incantation": 4, "zone": {"forme": "cercle", "origine": "cible", "rayon": 2}, "effets": {"degats": "3D10+8", "buffs": {"R": -8}, "duree": 3}},
	  remplace="courroux_des_elements"),
]
