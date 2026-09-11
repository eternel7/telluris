"""Proposer une grille de terrain (`cells`) à partir de l'image d'une carte — logique PURE.

Peindre à la main la grille d'une cité, c'est 4 128 cases (88×48). Deux lieux seulement
l'ont reçue — `lieu:auxerre` et `lieu:lutecia` — tandis que `lieu:france` et `lieu:rhemi`
sont restés des matrices de `1` uniformes. Ce module propose une PREMIÈRE PASSE que l'auteur
retouche ensuite au pinceau dans l'éditeur de carte. Ce n'est pas un oracle : une case de
16 px d'une carte de cité contient souvent un toit ET une ruelle, et la classification rend
ce qui domine.

⚠️ **AUCUN import de Pillow ici.** `tests/` importe `utils/*` → `routers/*`, et Pillow n'est
pas dans les dépendances de collecte locale (cf. CLAUDE.md § Running tests) : un import en
tête de module ferait échouer la COLLECTE de toute la suite de tests purs. Même raison, même
précaution que `routers/animations._dimensions`. Ce module reçoit donc des ÉCHANTILLONS déjà
réduits (une couleur moyenne et une densité de contours par case) ; `dev/gen_grille_image.py`
et l'endpoint `grille_proposee` sont les seuls à ouvrir un fichier image.

⚠️ **RIEN N'EST SEUILLÉ EN ABSOLU** — tout se décide par rapport à l'image elle-même. C'est
la leçon des deux seules grilles peintes à la main, mesurées case à case : leur étalonnage
colorimétrique n'est pas le même. L'eau d'Auxerre est franchement bleue (99, 156, 180),
celle de Lutèce un turquoise désaturé (146, 169, 151) — une palette de couleurs absolues
calée sur l'une classe l'eau de l'autre en terre ferme. Ce qui survit au changement de
carte, c'est l'ÉCART à la dominante : ces cartes sont des parchemins sépia où le rouge
l'emporte partout SAUF sur l'eau. `calibrer()` mesure ce repère sur chaque image, et les
règles ne parlent plus que d'écarts à lui.

Vocabulaire produit : **0 / 1 / 5**, celui des deux cartes de cité déjà peintes
(`templates/admin_map_editor.html:1258` — 0 inaccessible, 1 libre, 5 terrain très difficile).

⚠️ **`nav` n'est jamais produit.** C'est un dict creux `{"x,y": bitmask}` dont l'absence vaut
« aucune interdiction » (`templates/scripts/nav.js:47`) : le terrain suffit. Inventer des
arêtes de navigation serait du contenu faux que personne n'a demandé.

⚠️ **`lieu:auxerre` est la SEULE référence de réglage**, et il ne faut pas en chercher une
seconde à la légère. Concordance mesurée : 76 % au global, rappel 0,76 sur le bâti, 0,89 sur
l'eau. `lieu:lutecia` tombe à 48 %, mais ce chiffre ne mesure PAS l'outil : sa grille peinte
ne suit pas sa propre image (un liseré de cases sur les bords, des diagonales éparses en
travers de la ville), ce que les deux aperçus superposés montrent d'un coup d'œil. C'est
d'ailleurs ce qui explique que, sous ses cases `0` et sous ses cases `1`, l'image donne les
mêmes chiffres (contours 78 contre 80, rougeur 26 contre 23) : deux tirages de la même
population. Régler les seuils pour remonter ce score reviendrait à apprendre à se tromper.
"""

# ── LES RÈGLES — tout se règle ici ───────────────────────────────────────────────────────
REGLES_GRILLE = {
	# ── Eau ──────────────────────────────────────────────────────────────────────────
	# `froideur` = (g + b) / 2 - r, en ÉCART à la médiane de l'image. Sur un parchemin sépia,
	# seule l'eau passe franchement au-dessus : +96 au-dessus de la médiane à Auxerre, +41 à
	# Lutèce. Le seuil est pris bas dans cette fourchette pour attraper les deux.
	"eau_ecart_froideur": 30,
	# ⚠️ Garde-fou ABSOLU en plus de l'écart, et il n'est pas décoratif : sur une carte SANS
	# eau, la médiane est celle de la terre ferme et les cases les plus froides du bruit
	# franchiraient le seuil relatif à elles seules. Une carte sans rivière doit rendre zéro
	# case d'eau, pas un delta de bruit promu en fleuve.
	"eau_froideur_minimale": -25,

	# ── Bâti ─────────────────────────────────────────────────────────────────────────
	# Aucun seuil à régler : la coupure est choisie par Otsu sur l'image elle-même (cf.
	# `seuil_otsu`). Un pâté de maisons se reconnaît à DEUX traits simultanés — beaucoup de
	# traits (toits, murs, ombres) ET une teinte qui tire vers le rouge (terracotta) plutôt
	# que vers le vert (feuillage).
	# ⚠️ Le ET n'est pas un OU. Mesuré sur Auxerre : en OU, la forêt dense de la campagne
	# passe pour du bâti et la précision tombe de 0,55 à 0,39. La forêt a autant de traits
	# qu'une ville ; c'est sa COULEUR qui la trahit.
	"otsu_bacs": 64,
}

# Valeurs de terrain produites (`templates/admin_map_editor.html:1258`).
TERRAIN_INACCESSIBLE = 0
TERRAIN_LIBRE = 1
TERRAIN_EAU = 5


# ── Indices chromatiques ─────────────────────────────────────────────────────────────────
def _rgb(rgb):
	"""(r, g, b) en flottants. Tolère un RGBA : l'alpha ne dit rien du terrain."""
	if not rgb:
		return (0.0, 0.0, 0.0)
	valeurs = [float(v) for v in list(rgb)[:3]]
	while len(valeurs) < 3:
		valeurs.append(0.0)
	return tuple(valeurs)


def rougeur(rgb) -> float:
	"""Combien la case tire vers le rouge plutôt que vers le vert (toits contre feuillage)."""
	r, g, _ = _rgb(rgb)
	return r - g


def froideur(rgb) -> float:
	"""Combien la case échappe à la dominante rouge du parchemin — l'indice de l'eau."""
	r, g, b = _rgb(rgb)
	return (g + b) / 2.0 - r


def mediane(valeurs) -> float:
	"""Médiane d'une liste, 0.0 si elle est vide.

	⚠️ Recopiée plutôt qu'importée de `statistics` : quatre lignes, et ce module n'a AUCUNE
	dépendance — c'est ce qui le rend testable là où Pillow n'est pas installé."""
	ordonnees = sorted(float(v) for v in valeurs)
	n = len(ordonnees)
	if not n:
		return 0.0
	if n % 2:
		return ordonnees[n // 2]
	return (ordonnees[n // 2 - 1] + ordonnees[n // 2]) / 2.0


def seuil_otsu(valeurs, bacs: int = 64) -> float:
	"""Coupure d'Otsu : celle qui maximise la variance INTER-classes de l'histogramme.

	POURQUOI Otsu et pas un seuil réglé à la main : la coupure entre « beaucoup de traits »
	et « peu de traits » n'est pas la même d'une carte à l'autre, et un écart à la médiane
	choisi une fois pour toutes se trompe dès que la proportion de ville change. Otsu la
	relit sur CHAQUE image, sans paramètre à régler. Rendement mesuré sur Auxerre : 71 % de
	concordance avec un écart fixe, 76 % avec Otsu.

	Rend le minimum de la série si elle est vide ou constante — aucune coupure n'a de sens.
	"""
	series = [float(v) for v in valeurs]
	if not series:
		return 0.0
	bas, haut = min(series), max(series)
	if haut <= bas:
		return bas
	bacs = max(2, int(bacs))
	histo = [0] * bacs
	for v in series:
		histo[int((v - bas) / (haut - bas) * (bacs - 1))] += 1
	total = len(series)
	somme = sum(i * n for i, n in enumerate(histo))
	poids_bas, somme_bas, meilleure, coupure = 0, 0.0, -1.0, 0
	for i, n in enumerate(histo):
		poids_bas += n
		if poids_bas == 0 or poids_bas == total:
			continue
		somme_bas += i * n
		moyenne_bas = somme_bas / poids_bas
		moyenne_haut = (somme - somme_bas) / (total - poids_bas)
		variance = poids_bas * (total - poids_bas) * (moyenne_bas - moyenne_haut) ** 2
		if variance > meilleure:
			meilleure, coupure = variance, i
	return bas + (coupure + 0.5) * (haut - bas) / (bacs - 1)


def calibrer(couleurs, contours, regles=None) -> dict:
	"""Repère de l'image : les trois coupures dont dépend toute la classification.

	⚠️ **L'eau est écartée AVANT de calibrer le bâti**, et l'ordre n'est pas commutatif : une
	rivière est lisse et verte-bleue, elle tirerait les deux coupures d'Otsu vers le bas et
	ferait passer de la campagne pour du bâti. On calibre le bâti sur la seule terre ferme.
	"""
	regles = regles or REGLES_GRILLE
	seuil_eau = mediane([froideur(c) for c in couleurs]) + regles["eau_ecart_froideur"]
	seuil_eau = max(seuil_eau, regles["eau_froideur_minimale"])
	terre = [i for i, c in enumerate(couleurs) if froideur(c) < seuil_eau]
	bacs = regles.get("otsu_bacs", 64)
	return {
		"seuil_eau": seuil_eau,
		"seuil_contours": seuil_otsu(
			[float(contours[i]) for i in terre if i < len(contours)], bacs),
		"seuil_rougeur": seuil_otsu([rougeur(couleurs[i]) for i in terre], bacs),
	}


# ── Classification ───────────────────────────────────────────────────────────────────────
def classer_case(rgb, contour, repere) -> int:
	"""Valeur de terrain d'UNE case, d'après sa couleur moyenne et sa densité de contours.

	⚠️ L'eau passe en premier : une berge ou un pont très dessiné doit rester de l'eau.
	"""
	if froideur(rgb) >= repere["seuil_eau"]:
		return TERRAIN_EAU
	dense = float(contour) >= repere["seuil_contours"]
	rouge = rougeur(rgb) >= repere["seuil_rougeur"]
	return TERRAIN_INACCESSIBLE if (dense and rouge) else TERRAIN_LIBRE


def grille_depuis_echantillons(couleurs, contours, cols, rows, regles=None) -> list:
	"""Matrice `cells` indexée **[y][x]**, de `rows` lignes de `cols` colonnes exactement.

	⚠️ L'ordre `[y][x]` et le fait que TOUTES les lignes portent exactement `cols` entrées ne
	sont pas cosmétiques : `utils.lieux.dimensions_coherentes` refuse en 422 une matrice qui
	contredit ses `dimensions`, sur n'importe laquelle de ses lignes. Un échantillon manquant
	donne donc une case libre plutôt que de décaler toute la suite de la grille.
	"""
	repere = calibrer(couleurs, contours, regles)
	cells = []
	for y in range(int(rows)):
		ligne = []
		for x in range(int(cols)):
			i = y * int(cols) + x
			if i < len(couleurs) and i < len(contours):
				ligne.append(classer_case(couleurs[i], contours[i], repere))
			else:
				ligne.append(TERRAIN_LIBRE)
		cells.append(ligne)
	return cells


# ── Nettoyage ────────────────────────────────────────────────────────────────────────────
VOISINS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def lisser_majorite(cells, passes: int = 1, seuil: int = 5) -> list:
	"""Absorbe les cases isolées : une case dont `seuil` des 8 voisines partagent une AUTRE
	valeur prend cette valeur.

	⚠️ `seuil = 5`, et surtout pas moins. À 4, un couloir de deux cases de large se referme :
	chaque case d'un tel couloir a exactement 4 voisines hors couloir sur ses flancs. Une
	ruelle murée par le lissage est une régression parfaitement silencieuse — elle ne se voit
	qu'en jeu, en butant dessus. C'est ce que verrouille `tests/test_grille_image.py`.

	Ne mute pas la source, et chaque passe lit la grille PRÉCÉDENTE : écrire sur place ferait
	influer une case déjà réécrite sur ses voisines dans la même passe.
	"""
	courante = [list(ligne) for ligne in cells]
	for _ in range(max(0, int(passes))):
		suivante = [list(ligne) for ligne in courante]
		for y, ligne in enumerate(courante):
			for x, valeur in enumerate(ligne):
				comptes = {}
				for dx, dy in VOISINS:
					vx, vy = x + dx, y + dy
					if 0 <= vy < len(courante) and 0 <= vx < len(courante[vy]):
						v = courante[vy][vx]
						comptes[v] = comptes.get(v, 0) + 1
				for v, n in sorted(comptes.items(), key=lambda kv: -kv[1]):
					if v != valeur and n >= seuil:
						suivante[y][x] = v
						break
		courante = suivante
	return courante


def garder_composante_principale(cells) -> list:
	"""Passe à 0 les régions praticables (`>= 1`) qui ne touchent pas la plus grande.

	Une poche de terrain libre enclavée dans le bâti est le plus souvent une cour intérieure
	que l'image ne sait pas distinguer d'une place : inatteignable en jeu, donc trompeuse sur
	la carte. ⚠️ **Destructif par nature** — jamais appelé par défaut, uniquement sur demande
	explicite (`--connexite`) : sur une carte à deux rives, il effacerait la seconde.

	Connexité à 8, la même que celle des déplacements (`nav.VALID_MOVES`).
	"""
	sortie = [list(ligne) for ligne in cells]
	if not cells or not any(cells):
		return sortie
	vus = set()
	composantes = []
	for y, ligne in enumerate(cells):
		for x, valeur in enumerate(ligne):
			if valeur < 1 or (x, y) in vus:
				continue
			pile, membres = [(x, y)], []
			vus.add((x, y))
			while pile:
				cx, cy = pile.pop()
				membres.append((cx, cy))
				for dx, dy in VOISINS:
					vx, vy = cx + dx, cy + dy
					if (0 <= vy < len(cells) and 0 <= vx < len(cells[vy])
							and cells[vy][vx] >= 1 and (vx, vy) not in vus):
						vus.add((vx, vy))
						pile.append((vx, vy))
			composantes.append(membres)
	if not composantes:
		return sortie
	principale = max(range(len(composantes)), key=lambda i: len(composantes[i]))
	for i, membres in enumerate(composantes):
		if i != principale:
			for cx, cy in membres:
				sortie[cy][cx] = TERRAIN_INACCESSIBLE
	return sortie


# ── Notation contre une grille peinte à la main ──────────────────────────────────────────
def comptes(cells) -> dict:
	"""{valeur de terrain: nombre de cases}."""
	sortie = {}
	for ligne in cells:
		for v in ligne:
			sortie[v] = sortie.get(v, 0) + 1
	return sortie


def concordance(proposee, reference) -> dict:
	"""Compare une grille proposée à une grille peinte à la main.

	⚠️ **Le rappel PAR VALEUR est l'indicateur, jamais le taux global seul.** Auxerre est à
	65 % de cases `1` : un classifieur qui répondrait « libre » partout afficherait 65 % de
	réussite et ne servirait à rien. C'est le rappel sur `0` et sur `5` qui dit si l'outil
	travaille, et la précision qui dit ce qu'il en coûte à l'auteur en retouches.

	Toute case absente de l'une des deux grilles est ignorée plutôt que comptée fausse.
	"""
	attendus, obtenus, justes = {}, {}, {}
	total, justes_total, ecarts = 0, 0, []
	for y, ligne in enumerate(reference):
		for x, attendu in enumerate(ligne):
			if y >= len(proposee) or x >= len(proposee[y]):
				continue
			obtenu = proposee[y][x]
			total += 1
			attendus[attendu] = attendus.get(attendu, 0) + 1
			obtenus[obtenu] = obtenus.get(obtenu, 0) + 1
			if obtenu == attendu:
				justes[attendu] = justes.get(attendu, 0) + 1
				justes_total += 1
			else:
				ecarts.append([x, y, attendu, obtenu])
	par_valeur = {}
	for v in sorted(set(attendus) | set(obtenus)):
		n_attendu, n_obtenu = attendus.get(v, 0), obtenus.get(v, 0)
		n_juste = justes.get(v, 0)
		par_valeur[v] = {
			"attendu": n_attendu,
			"obtenu": n_obtenu,
			"rappel": (n_juste / n_attendu) if n_attendu else 0.0,
			"precision": (n_juste / n_obtenu) if n_obtenu else 0.0,
		}
	return {
		"total": total,
		"justes": justes_total,
		"global": (justes_total / total) if total else 0.0,
		"par_valeur": par_valeur,
		"ecarts": ecarts,
	}
