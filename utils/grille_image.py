"""Proposer une grille de terrain (`cells`) ET ses murs de navigation (`nav`) à partir de
l'image d'une carte — logique PURE.

Peindre à la main la grille d'une cité, c'est 4 128 cases (88×48). Ce module propose une
PREMIÈRE PASSE que l'auteur retouche ensuite au pinceau dans l'éditeur de carte. Ce n'est pas
un oracle : une case de 16 px d'une carte de cité contient souvent un toit ET une ruelle, et
la classification rend ce qui domine.

Quatre étages, dans cet ordre :
  1. **classer** chaque case d'après sa couleur moyenne et sa densité de traits, selon un
     PROFIL (`PROFILS_GRILLE` : ville, forêt, catacombes) ;
  2. **lisser** (`lisser_majorite`) ;
  3. **rues** (`tracer_rues`, villes) : rouvrir les rues plus fines qu'une case, lues sur
     des sous-cases de 4 px (`fins`) ;
  4. **topologie** (`proposer`) : fermer l'ENCEINTE d'une ville (par `nav`, ou par le
     terrain si les murs nav ne sont pas proposés), interdire les diagonales qui passent
     au-dessus de l'angle d'une maison (`fermer_coins`), puis RELIER les zones praticables
     disjointes d'un même côté du rempart (`relier_zones` : pont, ruelle, sentier, couloir).

⚠️ **AUCUN import de Pillow ici.** `tests/` importe `utils/*` → `routers/*`, et Pillow n'est
pas dans les dépendances de collecte locale (cf. CLAUDE.md § Running tests) : un import en
tête de module ferait échouer la COLLECTE de toute la suite de tests purs. Ce module reçoit
donc des ÉCHANTILLONS déjà réduits (une couleur moyenne et une densité de contours par case) ;
`dev/gen_grille_image.py`, `dev/calibrer_grille_image.py` et l'endpoint `grille_proposee` sont
les seuls à ouvrir un fichier image.

⚠️ **RIEN N'EST SEUILLÉ EN ABSOLU** — tout se décide par rapport à l'image elle-même. L'eau
d'Auxerre est franchement bleue (99, 156, 180), celle de Lutèce un turquoise désaturé
(146, 169, 151) : une palette de couleurs absolues calée sur l'une classe l'eau de l'autre en
terre ferme. Chaque indice est donc ramené à l'image (écart à la médiane, divisé par l'écart
interquartile — `calibrer`) et la coupure est choisie par Otsu sur l'image.

Vocabulaire produit : **0 / 1 / 3 / 5** (`templates/admin_map_editor.html:1258` — 0
inaccessible, 1 libre, 3 falaise, 5 terrain très difficile). 3 n'est produit que par les
profils qui le déclarent (roche en forêt, cristaux de la mine).

**`nav` est produit (sauf `murs_nav=False`), mais jamais retiré.** Le `nav` existant du doc
est une ENTRÉE : ses bits sont conservés, on n'en ajoute que. Un mur nav peint à la main est
une intention d'auteur.

**Calibration** : `dev/calibrer_grille_image.py`, sur les onze lieux peints à la main (trois
villes, quatre forêts, quatre souterrains), score = F1 moyen PAR VALEUR (jamais le taux
global, cf. `concordance`), validé en laissant un lieu de côté. Les chiffres cités dans
`PROFILS_GRILLE` en sortent. ⚠️ La grille peinte de Lutèce suit mal sa propre image (un liseré
de cases sur les bords, des diagonales éparses en travers de la ville) : elle compte à égalité
avec Auxerre à la demande de l'auteur, mais son score mesure autant la grille que l'outil.
"""

# ── Valeurs de terrain (`templates/admin_map_editor.html:1258`) ──────────────────────────
TERRAIN_INACCESSIBLE = 0
TERRAIN_LIBRE = 1
TERRAIN_FALAISE = 3
TERRAIN_EAU = 5

# Indices d'une case, dans cet ordre partout (poids des profils, normalisation).
INDICES = ("luminance", "contours", "froideur", "rougeur", "verdeur", "saturation")

# ── LES PROFILS — tout se règle ici ──────────────────────────────────────────────────────
# `obstacle` et `roche` sont des SCORES LINÉAIRES sur les indices normalisés de l'image :
# poids positif = « plus la case a de cet indice, plus elle bloque ». La coupure est l'Otsu
# de ce score sur la terre ferme, décalée de `decalage` (en unités de score).
PROFILS_GRILLE = {
	"ville": {
		"libelle": "Ville",
		# ── Eau ──────────────────────────────────────────────────────────────────────
		# `froideur` = (g + b) / 2 - r, en ÉCART à la médiane de l'image. Sur un parchemin
		# sépia, seule l'eau passe franchement au-dessus : +96 à Auxerre, +41 à Lutèce.
		"eau": True,
		"eau_ecart_froideur": 27.5,
		# ⚠️ Garde-fou ABSOLU en plus de l'écart : sur une carte SANS eau, la médiane est
		# celle de la terre ferme et les cases les plus froides du bruit franchiraient le
		# seuil relatif à elles seules.
		"eau_froideur_minimale": -25,
		"valeur_froide": TERRAIN_EAU,
		# ── Bâti ─────────────────────────────────────────────────────────────────────
		# Toits : très dessinés, rouges (terracotta) ou froids (ardoise), surtout PAS verts —
		# c'est la verdeur qui sépare le mieux la ville de sa campagne. Calibré sur Auxerre,
		# Lutèce et Reims : F1 par valeur 0,79 / 0,71 / 0,78 (ancienne règle « contours ET
		# rougeur » : 0,78 / 0,63 / 0,65) ; en laissant chaque ville de côté : 0,72 / 0,66 /
		# 0,65. ⚠️ Le poids des contours est FIXÉ à +1, pas optimisé : libre, la descente le
		# rend négatif pour +0,005 de score et perd en validation croisée — un toit se
		# reconnaît à ses traits, c'est l'invariant de `tests/test_grille_image.py`.
		# La luminance positive est mesurée, pas intuitive : à verdeur égale, les champs
		# des trois cartes sont plus sombres que les toits.
		"obstacle": {"luminance": 1.25, "contours": 1.0, "froideur": 1.25, "rougeur": 2.5,
			"verdeur": -4.5, "saturation": -1.0},
		"obstacle_decalage": 1.125,
		"roche": None,
		"otsu_bacs": 64,
		# ── Topologie ────────────────────────────────────────────────────────────────
		"enceinte": True,
		"coins": True,
		"passages": True,
		"passage_longueur_max": 12,
		"poche_min": 3,
		# Zone qu'aucun passage de `passage_longueur_max` cases ne rejoint : effacée si elle
		# tient en autant de cases (une cour), signalée au-delà. Sur Auxerre, les 9 zones
		# isolées font 3 à 11 cases, toutes des cours de pâtés de maisons.
		"poche_isolee_max": 12,
		# Surcoût de creuser une case selon sa valeur (en plus de 1 par case) : on
		# préfère percer une rangée de toits peu marqués (une rue que la grille a
		# manquée) plutôt que jeter un pont où l'image n'en montre pas.
		"cout_creuser": {TERRAIN_INACCESSIBLE: 2.0, TERRAIN_EAU: 3.0, TERRAIN_FALAISE: 6.0},
		# Surcoût par écart interquartile de MARGE (à quel point la case est franchement
		# classée) : un pont de pierre sur l'eau est « peu froid », une rue est « peu dense ».
		"cout_marge": 2.0,
		# Enceinte : fermeture morphologique du bâti (rayon, cases) puis trous comblés ;
		# retenue si elle couvre au moins `enceinte_part_min` de la carte.
		"enceinte_rayon": 2,
		"enceinte_part_min": 0.10,
		# Cadre de parchemin (`masque_cadre`) : anneau extérieur bâti à 80 % au moins, sur
		# 3 cases de profondeur au plus. Reims : anneau entièrement bâti ; Auxerre et
		# Lutèce : anneau surtout libre, aucun cadre.
		"cadre_part": 0.8,
		"cadre_profondeur": 3,
		# ── Rues (`tracer_rues`) ─────────────────────────────────────────────────────
		# Une rue fait 6 à 10 px, la case 16 : la couleur MOYENNE la noie dans les toits.
		# Elle reparaît à l'échelle de la sous-case (4 px) : sous les cases que l'auteur a
		# peintes 1 dans la ville, la sous-case la plus claire vaut 182 de luminance à
		# Auxerre contre 150 sous ses cases 0 (184 / 170 à Lutèce) — le pavé est clair et
		# terne, le toit sombre et vif. Score = clarté de la `rang`-ième sous-case la plus
		# claire − `poids_saturation` × sa vivacité, ramenés à l'image ; coupure Otsu +
		# `decalage`. Un groupe de cases claires n'est ouvert que s'il touche une case libre
		# ou fait au moins `longueur_min` cases (une cour éclairée isolée n'est pas une rue),
		# et pas s'il longe le bord (`bord_max` : le cadre clair du parchemin de Reims).
		# Mesuré (classification seule, F1 par valeur) : Auxerre 0,79 → 0,79, Lutèce
		# 0,71 → 0,79, Reims 0,78 → 0,80 ; plateau large autour de ces valeurs.
		# ⚠️ Écartés après mesure : l'ébarbage des impasses (retire plus de vraies rues que
		# de bruit) et l'exigence de maisons de part et d'autre (aucun gain).
		# Hors les murs (villages, faubourgs) : normalisation et coupure à part dès que le
		# dehors compte `cases_min` cases bâties, sinon celles de l'ensemble (Lutèce : 6
		# cases bâties dehors). Mesuré : à part ou commun, le score est le même à 0,001
		# près (Reims 22/25 rues justes hors les murs contre 20/23 en commun ; Auxerre, peu
		# de villages, 3/25) — ce qui a ouvert les villages de Reims, c'est le CADRE
		# (`masque_cadre`) qui en faisait des cases intra-muros. Le réglage à part reste
		# pour les cartes où le dehors est vaste et autrement éclairé.
		"rues": {"rang": 1, "poids_saturation": 1.0, "decalage": 0.75, "longueur_min": 3,
			"bord_max": 0.2, "cases_min": 30, "decalage_dehors": 0.75},
	},
	"foret": {
		"libelle": "Forêt",
		"eau": True,
		"eau_ecart_froideur": 40,
		"eau_froideur_minimale": -25,
		"valeur_froide": TERRAIN_EAU,
		# Obstacles (souches, fourrés, troncs) : ombres denses. Les grilles peintes en
		# forêt en posent peu : F1 moyen 0,39 (ancienne règle : 0,22). ⚠️ Pas le réglage
		# « optimisé » (0,48) : il tombe à 0,29 en laissant chaque forêt de côté, celui-ci
		# tient 0,33 — quatre cartes ne suffisent pas à apprendre davantage.
		"obstacle": {"luminance": -1.0, "contours": -0.25, "froideur": 0.0, "rougeur": 0.0,
			"verdeur": 0.0, "saturation": 0.0},
		"obstacle_decalage": 0.5,
		# Roche (falaise, 3) : froide, dessinée, peu verte, peu saturée. Rappel 0,50 et
		# précision 0,78 sur `chemin2`, la seule forêt à falaise nette.
		"roche": {"luminance": 0.0, "contours": 0.5, "froideur": 1.5, "rougeur": 0.0,
			"verdeur": -0.5, "saturation": -1.0},
		"roche_decalage": 0.625,
		"otsu_bacs": 64,
		"rues": None,
		"enceinte": False,
		"coins": True,
		"passages": True,
		"passage_longueur_max": 6,
		"poche_min": 2,
		"poche_isolee_max": 6,
		"cout_creuser": {TERRAIN_INACCESSIBLE: 1.0, TERRAIN_EAU: 3.0, TERRAIN_FALAISE: 6.0},
		"cout_marge": 2.0,
	},
	"catacombes": {
		"libelle": "Catacombes / souterrain",
		# Pas d'eau à traverser : ce qui est « froid » sous terre, ce sont les cristaux de
		# la mine et les flaques — posés en 3 (rappel 0,57, précision 0,76 sur la mine).
		"eau": True,
		"eau_ecart_froideur": 10,
		"eau_froideur_minimale": -25,
		"valeur_froide": TERRAIN_FALAISE,
		# Paroi : SOMBRE (le vide noir et la roche) contre un sol éclairé. F1 0,81 / 0,81 /
		# 0,76 sur les trois catacombes (ancienne règle : 0,34 / 0,36 / 0,29) ; la mine,
		# éclairée autrement, reste à 0,46 (0,11 avant) — son sol passe pour de la paroi,
		# ses zones restent SIGNALÉES.
		"obstacle": {"luminance": -1.5, "contours": 0.0, "froideur": 1.0, "rougeur": 0.0,
			"verdeur": 0.0, "saturation": 0.0},
		"obstacle_decalage": 0.5,
		"roche": None,
		"otsu_bacs": 64,
		# Sous terre, le couloir EST le sol clair : la classification le voit déjà.
		"rues": None,
		"enceinte": False,
		"coins": True,
		"passages": True,
		# Court : on rouvre un couloir que la grille a manqué, on ne perce pas de tunnel.
		"passage_longueur_max": 3,
		"poche_min": 3,
		"poche_isolee_max": 6,
		"cout_creuser": {TERRAIN_INACCESSIBLE: 1.0, TERRAIN_EAU: 3.0, TERRAIN_FALAISE: 4.0},
		"cout_marge": 2.0,
	},
}
PROFIL_DEFAUT = "ville"
# Compatibilité : l'ancien nom désignait le seul réglage, celui des villes.
REGLES_GRILLE = PROFILS_GRILLE[PROFIL_DEFAUT]

# Tags qui désignent un profil (`profil_de`) — premier trouvé gagne, dans cet ordre.
TAGS_PROFIL = (
	("catacombes", ("catacombe", "sous-terrain", "mine", "grotte_profonde")),
	("foret", ("foret", "bois", "clairiere", "clariere")),
)


def profil_de(doc) -> str:
	"""Profil de réglage d'un lieu, lu sur ses tags (souterrain d'abord, forêt ensuite).

	⚠️ Souterrain AVANT forêt : `lieu:grotte_en_foret` porte `foret` ET `grotte` ; une grotte
	peinte en sous-bois reste une forêt tant qu'elle ne porte pas un tag de souterrain.
	Sans tag reconnu — une ville, un pays — c'est le profil `ville`."""
	tags = {str(t).lower() for t in ((doc or {}).get("tags") or [])}
	for profil, cles in TAGS_PROFIL:
		if tags & set(cles):
			return profil
	return PROFIL_DEFAUT


def regles_de(profil=None, regles=None) -> dict:
	"""Le jeu de règles d'un profil (inconnu ⇒ ville) ; `regles` explicite prime."""
	if regles:
		return regles
	return PROFILS_GRILLE.get(profil or PROFIL_DEFAUT, PROFILS_GRILLE[PROFIL_DEFAUT])


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


def verdeur(rgb) -> float:
	"""Combien le vert domine les deux autres canaux (feuillage, prairie)."""
	r, g, b = _rgb(rgb)
	return g - (r + b) / 2.0


def luminance(rgb) -> float:
	"""Luminance perçue (Rec. 601)."""
	r, g, b = _rgb(rgb)
	return 0.299 * r + 0.587 * g + 0.114 * b


def saturation(rgb) -> float:
	"""Vivacité HSV × 100 : la pierre est terne, le feuillage vif. Recopiée de `colorsys`
	(une ligne) pour garder ce module sans import."""
	r, g, b = _rgb(rgb)
	haut = max(r, g, b)
	return (haut - min(r, g, b)) / haut * 100.0 if haut > 0 else 0.0


def indices(rgb, contour) -> list:
	"""Les six indices d'une case, dans l'ordre de `INDICES`."""
	return [luminance(rgb), float(contour or 0), froideur(rgb), rougeur(rgb), verdeur(rgb),
		saturation(rgb)]


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

	POURQUOI Otsu et pas un seuil réglé à la main : la coupure entre « bloque » et « ne bloque
	pas » n'est pas la même d'une carte à l'autre, et un écart à la médiane choisi une fois
	pour toutes se trompe dès que la proportion de ville change. Otsu la relit sur CHAQUE
	image.

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


def _quartiles(valeurs):
	ordonnees = sorted(valeurs)
	if not ordonnees:
		return 0.0, 1.0
	n = len(ordonnees)
	ecart = ordonnees[3 * n // 4] - ordonnees[n // 4]
	# Plancher d'UN niveau de gris : en dessous, l'écart est du bruit d'arrondi, et diviser
	# par lui ferait d'un demi-niveau de luminance un écart énorme. Ne mord sur aucune des
	# dix cartes de calibration (plus petit écart mesuré : 1,0, la verdeur de la mine).
	return ordonnees[n // 2], max(ecart, 1.0)


def _score(poids, z) -> float:
	return sum(poids.get(nom, 0.0) * v for nom, v in zip(INDICES, z))


def calibrer(couleurs, contours, regles=None, profil=None) -> dict:
	"""Repère de l'image : normalisation des indices et coupures dont dépend la classification.

	⚠️ **L'eau est écartée AVANT de calibrer le reste**, et l'ordre n'est pas commutatif : une
	rivière est lisse et froide, elle tirerait la médiane, les quartiles et la coupure d'Otsu.
	On normalise et on coupe sur la seule terre ferme.

	Normalisation ROBUSTE (médiane, écart interquartile) : quelques cases extrêmes — une
	cathédrale, un brasero — ne déplacent rien. Un écart nul vaut 1 (image unie).
	"""
	regles = regles_de(profil, regles)
	vecteurs = [indices(c, contours[i] if i < len(contours) else 0)
		for i, c in enumerate(couleurs)]
	seuil_eau = None
	if regles.get("eau", True):
		seuil_eau = mediane([v[2] for v in vecteurs]) + regles["eau_ecart_froideur"]
		seuil_eau = max(seuil_eau, regles["eau_froideur_minimale"])
	terre = [v for v in vecteurs if seuil_eau is None or v[2] < seuil_eau]
	norme = [_quartiles([v[t] for v in terre]) for t in range(len(INDICES))]

	def normaliser(v):
		return [(v[t] - norme[t][0]) / norme[t][1] for t in range(len(INDICES))]

	bacs = regles.get("otsu_bacs", 64)
	z_terre = [normaliser(v) for v in terre]
	scores = [_score(regles["obstacle"], z) for z in z_terre]
	repere = {
		"seuil_eau": seuil_eau,
		"valeur_froide": regles.get("valeur_froide", TERRAIN_EAU),
		"norme": norme,
		"obstacle": regles["obstacle"],
		"seuil_obstacle": seuil_otsu(scores, bacs) + regles.get("obstacle_decalage", 0.0),
		"echelle_obstacle": _quartiles(scores)[1],
		"roche": regles.get("roche"),
		"seuil_roche": None,
	}
	if regles.get("roche"):
		roches = [_score(regles["roche"], z) for z in z_terre]
		repere["seuil_roche"] = seuil_otsu(roches, bacs) + regles.get("roche_decalage", 0.0)
		repere["echelle_roche"] = _quartiles(roches)[1]
	# Écart interquartile de la froideur : l'unité de « marge » d'une case d'eau.
	repere["echelle_eau"] = norme[2][1]
	return repere


# ── Classification ───────────────────────────────────────────────────────────────────────
def classer_case_marge(rgb, contour, repere):
	"""(valeur, marge) d'UNE case. La marge dit à quel point la case est FRANCHEMENT de sa
	classe, en écarts interquartiles au-delà de sa coupure (0 pour une case libre) : c'est
	elle qui rend « peu froide » une arche de pont posée sur l'eau, et « peu dense » une rue
	que la grille a noyée dans les toits (`relier_zones`).

	⚠️ La valeur froide passe en premier : une berge ou un pont très dessiné reste de l'eau.
	"""
	v = indices(rgb, contour)
	if repere["seuil_eau"] is not None and v[2] >= repere["seuil_eau"]:
		return repere["valeur_froide"], (v[2] - repere["seuil_eau"]) / repere["echelle_eau"]
	norme = repere["norme"]
	z = [(v[t] - norme[t][0]) / norme[t][1] for t in range(len(INDICES))]
	s = _score(repere["obstacle"], z)
	if s >= repere["seuil_obstacle"]:
		return TERRAIN_INACCESSIBLE, (s - repere["seuil_obstacle"]) / (repere["echelle_obstacle"] or 1.0)
	if repere.get("roche") and repere.get("seuil_roche") is not None:
		s3 = _score(repere["roche"], z)
		if s3 >= repere["seuil_roche"]:
			return TERRAIN_FALAISE, (s3 - repere["seuil_roche"]) / (repere.get("echelle_roche") or 1.0)
	return TERRAIN_LIBRE, 0.0


def classer_case(rgb, contour, repere) -> int:
	"""Valeur de terrain d'UNE case, d'après sa couleur moyenne et sa densité de contours."""
	return classer_case_marge(rgb, contour, repere)[0]


def analyser(couleurs, contours, cols, rows, regles=None, profil=None) -> dict:
	"""`{cells, marges}` : la grille classée (NON lissée) et la marge de chaque case, [y][x]."""
	repere = calibrer(couleurs, contours, regles, profil)
	cells, marges = [], []
	for y in range(int(rows)):
		ligne, ligne_m = [], []
		for x in range(int(cols)):
			i = y * int(cols) + x
			if i < len(couleurs) and i < len(contours):
				v, m = classer_case_marge(couleurs[i], contours[i], repere)
			else:
				v, m = TERRAIN_LIBRE, 0.0
			ligne.append(v)
			ligne_m.append(m)
		cells.append(ligne)
		marges.append(ligne_m)
	return {"cells": cells, "marges": marges}


def grille_depuis_echantillons(couleurs, contours, cols, rows, regles=None, profil=None) -> list:
	"""Matrice `cells` indexée **[y][x]**, de `rows` lignes de `cols` colonnes exactement.

	⚠️ L'ordre `[y][x]` et le fait que TOUTES les lignes portent exactement `cols` entrées ne
	sont pas cosmétiques : `utils.lieux.dimensions_coherentes` refuse en 422 une matrice qui
	contredit ses `dimensions`, sur n'importe laquelle de ses lignes. Un échantillon manquant
	donne donc une case libre plutôt que de décaler toute la suite de la grille.
	"""
	return analyser(couleurs, contours, cols, rows, regles, profil)["cells"]


# ── Nettoyage ────────────────────────────────────────────────────────────────────────────
VOISINS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
ORTHOGONAUX = [(0, -1), (1, 0), (0, 1), (-1, 0)]


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


# ── Rues ─────────────────────────────────────────────────────────────────────────────────
# Sous-cases par côté de case pour les échantillons FINS (`fins`) : 4 → 4 px sur une case de
# 16. ⚠️ Le module ne réduit rien lui-même : l'appelant (endpoint, CLI) réduit l'image à
# `cols·k × rows·k` en `Image.BOX`, couleur seule.
SOUS_CASES = 4


def tracer_rues(cells, fins, k, regles, masque=None):
	"""Ouvre (passe à 1) les cases bâties que traverse une rue trop fine pour la case.

	`fins` : couleurs à plat, ligne par ligne, d'une image réduite à `cols·k × rows·k`.
	Post-traitement : à appeler APRÈS `lisser_majorite` (qui refermerait une rue d'une case)
	et avant la topologie (les passages raccordent ensuite ce qui reste). Ne mute pas `cells`.
	Rend `(cells, ouvertes)`, `ouvertes` = [[x, y], …] dans l'ordre de lecture.

	`masque` (enceinte, `detecter_enceinte`) : normalisation et coupure calculées À PART dedans
	et dehors — les villages et faubourgs (rues de terre, toits épars) n'ont pas la lumière de
	la cité, qui sinon dicterait seule le seuil. Un côté de moins de `cases_min` cases bâties
	emprunte le réglage de l'ensemble : Otsu sur six cases ne veut rien dire. Le dehors a son
	décalage (`decalage_dehors`). Le cadre de la carte (`masque_cadre`) n'est jamais une rue.
	"""
	sortie = [list(ligne) for ligne in cells]
	reglage = (regles or {}).get("rues")
	H = len(sortie)
	W = len(sortie[0]) if H else 0
	k = int(k or 0)
	if not reglage or not H or not W or k < 1 or len(fins or []) < W * k * H * k:
		return sortie, []
	largeur = W * k
	rang = max(1, min(int(reglage.get("rang", 1)), k * k))
	cadre = masque_cadre(sortie, regles)
	bati = [(x, y) for y in range(H) for x in range(W)
		if sortie[y][x] == TERRAIN_INACCESSIBLE and not (cadre and cadre[y][x])]
	if not bati:
		return sortie, []
	clarte, vivacite = {}, {}
	for x, y in bati:
		sous = sorted(((luminance(fins[(y * k + j) * largeur + x * k + i]),
			saturation(fins[(y * k + j) * largeur + x * k + i]))
			for j in range(k) for i in range(k)), reverse=True)
		clarte[(x, y)], vivacite[(x, y)] = sous[rang - 1]
	poids = float(reglage.get("poids_saturation", 0.0))
	bacs = regles.get("otsu_bacs", 64)

	def reglage_de(cases, decalage):
		"""(score par case, coupure), ramenés aux cases bâties données : rien d'absolu."""
		m_l, e_l = _quartiles([clarte[c] for c in cases])
		m_s, e_s = _quartiles([vivacite[c] for c in cases])
		score = {c: (clarte[c] - m_l) / e_l - poids * (vivacite[c] - m_s) / e_s for c in cases}
		return score, seuil_otsu(list(score.values()), bacs) + decalage

	decalage = float(reglage.get("decalage", 0.0))
	commun, coupure_commune = reglage_de(bati, decalage)
	candidates = set()
	if masque:
		cases_min = int(reglage.get("cases_min", 0))
		for dedans, dec in ((True, decalage), (False, float(reglage.get("decalage_dehors", decalage)))):
			cote = [c for c in bati if bool(masque[c[1]][c[0]]) == dedans]
			if len(cote) >= cases_min:
				score, coupure = reglage_de(cote, dec)
			else:
				score, coupure = commun, coupure_commune - decalage + dec
			candidates |= {c for c in cote if score[c] >= coupure}
	else:
		candidates = {c for c in bati if commun[c] >= coupure_commune}

	def libre(x, y):
		return _dans(sortie, x, y) and sortie[y][x] == TERRAIN_LIBRE

	def au_bord(x, y):
		return x in (0, W - 1) or y in (0, H - 1)

	bord_max = float(reglage.get("bord_max", 1.0))
	longueur_min = int(reglage.get("longueur_min", 1))
	ouvertes, vues = [], set()
	for depart in sorted(candidates, key=lambda c: (c[1], c[0])):
		if depart in vues:
			continue
		pile, groupe = [depart], []
		vues.add(depart)
		while pile:
			cx, cy = pile.pop()
			groupe.append((cx, cy))
			for dx, dy in VOISINS:
				voisine = (cx + dx, cy + dy)
				if voisine in candidates and voisine not in vues:
					vues.add(voisine)
					pile.append(voisine)
		# Le CADRE d'une carte sur parchemin (Reims) est une bande claire le long du bord :
		# un groupe dont plus de `bord_max` des cases touchent le bord n'est pas une rue.
		if sum(1 for c in groupe if au_bord(*c)) > bord_max * len(groupe):
			continue
		touche = any(libre(x + dx, y + dy) for x, y in groupe for dx, dy in VOISINS)
		if touche or len(groupe) >= longueur_min:
			ouvertes.extend(groupe)
	for x, y in ouvertes:
		sortie[y][x] = TERRAIN_LIBRE
	return sortie, [[x, y] for x, y in sorted(ouvertes, key=lambda c: (c[1], c[0]))]


# ── nav ──────────────────────────────────────────────────────────────────────────────────
# [bit, dx, dy, bit opposé] — ⚠️ RECOPIE de `utils.lieux.VALID_MOVES` (miroir client :
# `templates/scripts/nav.js`). Importer `utils.lieux` tirerait FastAPI et CouchDB dans un
# module qui n'a aucune dépendance ; la recopie est verrouillée par
# `tests/test_grille_image.py::test_la_recopie_de_valid_moves_suit_utils_lieux`.
VALID_MOVES = [
	[1,   0, -1, 16],
	[2,   1, -1, 32],
	[4,   1,  0, 64],
	[8,   1,  1, 128],
	[16,  0,  1, 1],
	[32, -1,  1, 2],
	[64, -1,  0, 4],
	[128, -1, -1, 8],
]
_BIT = {(dx, dy): (bit, op) for bit, dx, dy, op in VALID_MOVES}


def nav_autorise(nav, x, y, dx, dy) -> bool:
	"""La direction (dx, dy) depuis (x, y) est-elle permise par `nav` ? Vérification
	BIDIRECTIONNELLE, comme `getFinalMask` : la source ne l'interdit pas ET la cible
	n'interdit pas l'entrée."""
	if not nav:
		return True
	bit, op = _BIT[(dx, dy)]
	if int(nav.get(f"{x},{y}", 0) or 0) & bit:
		return False
	return not (int(nav.get(f"{x + dx},{y + dy}", 0) or 0) & op)


def interdire(nav, x, y, dx, dy) -> int:
	"""Interdit le pas (dx, dy) depuis (x, y) — bit posé DES DEUX CÔTÉS, pour que l'éditeur
	montre le mur sur les deux cases. Mute `nav` ; rend le nombre de bits ajoutés."""
	bit, op = _BIT[(dx, dy)]
	ajoutes = 0
	for cle, b in ((f"{x},{y}", bit), (f"{x + dx},{y + dy}", op)):
		avant = int(nav.get(cle, 0) or 0)
		if not avant & b:
			nav[cle] = avant | b
			ajoutes += 1
	return ajoutes


def _dans(cells, x, y) -> bool:
	return 0 <= y < len(cells) and 0 <= x < len(cells[y])


def pas_praticable(cells, nav, x, y, dx, dy) -> bool:
	"""Pas à pied (règle d'EXPLORATION, miroir de `pasAutoriseLocal`) : cible `== 1` et
	`nav` le permet. La source n'est pas testée — c'est la règle du jeu."""
	nx, ny = x + dx, y + dy
	return _dans(cells, nx, ny) and cells[ny][nx] == TERRAIN_LIBRE and nav_autorise(nav, x, y, dx, dy)


# ── Coins ────────────────────────────────────────────────────────────────────────────────
# Un obstacle PLEIN : on ne le frôle pas en diagonale. L'eau n'en est pas un — on longe une
# berge en biais — sauf quand les DEUX orthogonales sont infranchissables.
OBSTACLES_PLEINS = (TERRAIN_INACCESSIBLE, TERRAIN_FALAISE)


def _coin_ferme(cells, x, y, dx, dy) -> bool:
	a = cells[y][x + dx] if _dans(cells, x + dx, y) else TERRAIN_INACCESSIBLE
	b = cells[y + dy][x] if _dans(cells, x, y + dy) else TERRAIN_INACCESSIBLE
	if a in OBSTACLES_PLEINS or b in OBSTACLES_PLEINS:
		return True
	return a != TERRAIN_LIBRE and b != TERRAIN_LIBRE


def fermer_coins(cells, nav, zone=None) -> int:
	"""Interdit dans `nav` tout pas DIAGONAL entre deux cases libres qui passerait au-dessus
	de l'angle d'une maison, d'un mur ou d'un rocher (une orthogonale intermédiaire pleine),
	ou entre deux cases d'eau. Sans ce mur, le jeton traverse le coin d'un toit.

	`zone` (ensemble de (x, y)) restreint la passe aux cases listées. Mute `nav` ; rend le
	nombre de bits ajoutés. Ne pose que des bits DIAGONAUX."""
	ajoutes = 0
	cases = sorted(zone) if zone is not None else [
		(x, y) for y in range(len(cells)) for x in range(len(cells[y]))]
	for x, y in cases:
		if not _dans(cells, x, y) or cells[y][x] != TERRAIN_LIBRE:
			continue
		for dx, dy in ((1, -1), (1, 1), (-1, 1), (-1, -1)):
			nx, ny = x + dx, y + dy
			if not _dans(cells, nx, ny) or cells[ny][nx] != TERRAIN_LIBRE:
				continue
			if _coin_ferme(cells, x, y, dx, dy) and nav_autorise(nav, x, y, dx, dy):
				ajoutes += interdire(nav, x, y, dx, dy)
	return ajoutes


# ── Enceinte ─────────────────────────────────────────────────────────────────────────────
def _dilater(masque, rayon):
	H = len(masque)
	W = len(masque[0]) if H else 0
	sortie = [[False] * W for _ in range(H)]
	for y in range(H):
		for x in range(W):
			if masque[y][x]:
				for yy in range(max(0, y - rayon), min(H, y + rayon + 1)):
					ligne = sortie[yy]
					for xx in range(max(0, x - rayon), min(W, x + rayon + 1)):
						ligne[xx] = True
	return sortie


def _eroder(masque, rayon):
	inverse = [[not v for v in ligne] for ligne in masque]
	return [[not v for v in ligne] for ligne in _dilater(inverse, rayon)]


def masque_cadre(cells, regles) -> list:
	"""Masque [y][x] du CADRE dessiné autour d'une carte sur parchemin (liste vide sinon).

	Cadre présumé si au moins `cadre_part` des cases de l'anneau extérieur sont bâties ; il
	comprend alors les cases bâties atteintes depuis l'anneau, de proche en proche, à moins
	de `cadre_profondeur` cases du bord (Reims : trois rangées en haut, une ailleurs). Une
	ville qui touche le bord (Lutèce) laisse l'anneau surtout libre : pas de cadre."""
	H = len(cells)
	W = len(cells[0]) if H else 0
	if H < 3 or W < 3:
		return []
	anneau = [(x, y) for y in range(H) for x in range(W) if x in (0, W - 1) or y in (0, H - 1)]
	baties = [c for c in anneau if cells[c[1]][c[0]] == TERRAIN_INACCESSIBLE]
	if len(baties) < float(regles.get("cadre_part", 0.8)) * len(anneau):
		return []
	profondeur = int(regles.get("cadre_profondeur", 3))
	masque = [[False] * W for _ in range(H)]
	pile = list(baties)
	for x, y in pile:
		masque[y][x] = True
	while pile:
		x, y = pile.pop()
		for dx, dy in VOISINS:
			nx, ny = x + dx, y + dy
			if (0 <= nx < W and 0 <= ny < H and not masque[ny][nx]
					and cells[ny][nx] == TERRAIN_INACCESSIBLE
					and min(nx, ny, W - 1 - nx, H - 1 - ny) < profondeur):
				masque[ny][nx] = True
				pile.append((nx, ny))
	return masque


def detecter_enceinte(cells, regles) -> list:
	"""Masque [y][x] de l'ENCEINTE d'une ville (liste vide si aucune n'est retenue).

	⚠️ **Géométrique, pas colorimétrique.** À 16 px la case, un rempart est plus fin qu'une
	case : mesuré sur Auxerre, les cases « pierre » (denses, ternes, pas rouges) sont semées
	partout et ne dessinent pas le mur. Ce qui dessine l'enceinte, c'est la MASSE BÂTIE :
	fermeture morphologique du bâti (`enceinte_rayon`), trous comblés — les rues, les places et
	la rivière intra-muros en font partie —, plus grande composante. Sur Lutèce, les murs `nav`
	peints à la main longent ce contour. Retenue seulement si elle couvre au moins
	`enceinte_part_min` de la carte : un hameau n'a pas d'enceinte.
	"""
	H = len(cells)
	W = len(cells[0]) if H else 0
	if not H or not W:
		return []
	rayon = int(regles.get("enceinte_rayon", 2))
	# ⚠️ Le CADRE d'une carte sur parchemin compte comme DEHORS : sur Reims, soudé à la ville,
	# il faisait de la carte ENTIÈRE une enceinte (4 320 cases sur 4 320).
	cadre = masque_cadre(cells, regles)
	bati = [[v == TERRAIN_INACCESSIBLE and not (cadre and cadre[y][x])
		for x, v in enumerate(ligne)] for y, ligne in enumerate(cells)]
	ferme = _eroder(_dilater(bati, rayon), rayon)
	if cadre:
		for y in range(H):
			for x in range(W):
				if cadre[y][x]:
					ferme[y][x] = False
	# Trous comblés : ce que le bord n'atteint pas sans traverser la masse.
	dehors = [[False] * W for _ in range(H)]
	pile = [(x, y) for y in range(H) for x in range(W)
		if ((x in (0, W - 1) or y in (0, H - 1)) or (cadre and cadre[y][x])) and not ferme[y][x]]
	for x, y in pile:
		dehors[y][x] = True
	while pile:
		x, y = pile.pop()
		for dx, dy in ORTHOGONAUX:
			nx, ny = x + dx, y + dy
			if 0 <= nx < W and 0 <= ny < H and not dehors[ny][nx] and not ferme[ny][nx]:
				dehors[ny][nx] = True
				pile.append((nx, ny))
	plein = [[not dehors[y][x] for x in range(W)] for y in range(H)]
	# Plus grande composante (4-connexité : un pont diagonal de deux cases ne soude rien).
	vus = [[False] * W for _ in range(H)]
	meilleure = []
	for y in range(H):
		for x in range(W):
			if not plein[y][x] or vus[y][x]:
				continue
			pile, membres = [(x, y)], []
			vus[y][x] = True
			while pile:
				cx, cy = pile.pop()
				membres.append((cx, cy))
				for dx, dy in ORTHOGONAUX:
					nx, ny = cx + dx, cy + dy
					if 0 <= nx < W and 0 <= ny < H and plein[ny][nx] and not vus[ny][nx]:
						vus[ny][nx] = True
						pile.append((nx, ny))
			if len(membres) > len(meilleure):
				meilleure = membres
	if len(meilleure) < regles.get("enceinte_part_min", 0.10) * W * H:
		return []
	masque = [[False] * W for _ in range(H)]
	for x, y in meilleure:
		masque[y][x] = True
	return masque


def fermer_enceinte(cells, nav, masque) -> list:
	"""Mur `nav` entre l'enceinte et le dehors : tout pas qui changerait de côté, entre deux
	cases foulables EN COMBAT (`>= 1` hors falaise — l'eau aussi, un nageur ne doit pas
	contourner le rempart). Le rempart n'est PAS peint en 0 : la case de porte dessinée reste
	praticable, l'auteur y posera sa porte de rempart (deux lieux et un passage).

	Mute `nav` ; rend la liste des cases du pourtour intérieur touchées, [[x, y], …]."""
	touchees = set()
	if not masque:
		return []

	def foulable(x, y):
		return _dans(cells, x, y) and cells[y][x] >= 1 and cells[y][x] != TERRAIN_FALAISE

	for y in range(len(cells)):
		for x in range(len(cells[y])):
			if not masque[y][x] or not foulable(x, y):
				continue
			for dx, dy in VOISINS:
				nx, ny = x + dx, y + dy
				if _dans(cells, nx, ny) and not masque[ny][nx] and foulable(nx, ny):
					if interdire(nav, x, y, dx, dy):
						touchees.add((x, y))
	return [[x, y] for x, y in sorted(touchees, key=lambda c: (c[1], c[0]))]


def fermer_enceinte_terrain(cells, masque) -> list:
	"""L'enceinte fermée SANS `nav` (murs nav non proposés) : les cases libres du dedans qui
	touchent (8-voisinage) une case libre du dehors passent à 0 — la porte dessinée se ferme,
	l'auteur la rouvre au pinceau en posant sa porte de rempart. Ne touche qu'au DEDANS : le
	dehors garde ses chemins jusqu'au pied du mur.

	Mute `cells` ; rend les cases fermées, [[x, y], …]."""
	fermees = []
	if not masque:
		return fermees
	for y in range(len(cells)):
		for x in range(len(cells[y])):
			if not masque[y][x] or cells[y][x] != TERRAIN_LIBRE:
				continue
			for dx, dy in VOISINS:
				nx, ny = x + dx, y + dy
				if (_dans(cells, nx, ny) and not masque[ny][nx]
						and cells[ny][nx] == TERRAIN_LIBRE):
					fermees.append([x, y])
					break
	for x, y in fermees:
		cells[y][x] = TERRAIN_INACCESSIBLE
	return fermees


def cotes_de(masque) -> list:
	"""`cotes[y][x]` : 0 dans l'enceinte, puis 1, 2… pour chaque morceau du DEHORS
	(8-connexité, celle de la marche).

	⚠️ Une ville qui touche le bord de la carte coupe le dehors en morceaux — Lutèce sépare
	sa rive nord de sa rive sud-ouest. Chacun est un côté à part : en jeu, on passe de l'un à
	l'autre par les portes de la ville ; creuser un chemin qui la contourne serait faux, et
	exiger qu'ils soient reliés serait impossible."""
	H = len(masque)
	W = len(masque[0]) if H else 0
	cotes = [[0 if masque[y][x] else -1 for x in range(W)] for y in range(H)]
	n = 0
	for y in range(H):
		for x in range(W):
			if cotes[y][x] != -1:
				continue
			n += 1
			cotes[y][x] = n
			pile = [(x, y)]
			while pile:
				cx, cy = pile.pop()
				for dx, dy in VOISINS:
					nx, ny = cx + dx, cy + dy
					if 0 <= nx < W and 0 <= ny < H and cotes[ny][nx] == -1:
						cotes[ny][nx] = n
						pile.append((nx, ny))
	return cotes


# ── Zones et passages ────────────────────────────────────────────────────────────────────
def zones(cells, nav):
	"""Composantes sous la règle de marche (`pas_praticable`). `(zone, tailles)` : `zone[y][x]`
	= numéro de zone (-1 hors case libre), numérotées dans l'ordre de découverte."""
	H = len(cells)
	zone = [[-1] * len(ligne) for ligne in cells]
	tailles = []
	for y in range(H):
		for x in range(len(cells[y])):
			if cells[y][x] != TERRAIN_LIBRE or zone[y][x] != -1:
				continue
			n = len(tailles)
			zone[y][x] = n
			pile, compte = [(x, y)], 0
			while pile:
				cx, cy = pile.pop()
				compte += 1
				for dx, dy in VOISINS:
					if pas_praticable(cells, nav, cx, cy, dx, dy) and zone[cy + dy][cx + dx] == -1:
						zone[cy + dy][cx + dx] = n
						pile.append((cx + dx, cy + dy))
			tailles.append(compte)
	return zone, tailles


def _tas_pousser(tas, element):
	tas.append(element)
	k = len(tas) - 1
	while k > 0:
		p = (k - 1) >> 1
		if tas[p] <= tas[k]:
			break
		tas[p], tas[k] = tas[k], tas[p]
		k = p


def _tas_tirer(tas):
	dernier = tas.pop()
	if not tas:
		return dernier
	tete, tas[0] = tas[0], dernier
	k, n = 0, len(tas)
	while True:
		g, d, m = 2 * k + 1, 2 * k + 2, k
		if g < n and tas[g] < tas[m]:
			m = g
		if d < n and tas[d] < tas[m]:
			m = d
		if m == k:
			return tete
		tas[m], tas[k] = tas[k], tas[m]
		k = m


def relier_zones(cells, nav, marges=None, cotes=None, regles=None, profil=None, murs_nav=True):
	"""Relie les zones praticables disjointes d'un même CÔTÉ en creusant des passages.

	`cotes[y][x]` = côté de la case (`cotes_de` ; None = un seul côté). Pour
	chaque côté, on part de sa plus grande zone et on répète : Dijkstra multi-source, PAS
	ORTHOGONAUX seulement, jusqu'à la première case d'une autre zone ; le chemin est creusé
	(cases passées à 1), la zone rejointe fusionne, on recommence. Coût d'entrer dans une case
	à creuser = 1 + `cout_creuser[valeur]` + `cout_marge` × marge : le passage prend la case
	d'eau la moins froide (le pont dessiné), la rangée de toits la moins marquée (la rue).

	⚠️ Pourquoi orthogonal : un escalier diagonal passerait au-dessus des angles que
	`fermer_coins` vient de fermer ; et un passage d'une case de large tient en jeu.
	⚠️ Interdits : changer de côté (le rempart reste fermé), un pas que `nav` refuse (un mur
	peint à la main est une intention), la case hors carte.

	Poches de moins de `poche_min` cases : passées à 0 avant tout (bruit — on n'invente pas de
	ruelle vers une cour de deux cases). Passage plus long que `passage_longueur_max` : la zone
	est laissée telle quelle et SIGNALÉE.

	`murs_nav=False` : aucun bit n'est posé (ni coins, ni rescellement). Le rempart tient
	alors par le TERRAIN (`fermer_enceinte_terrain`) : une case à creuser qui toucherait une
	case libre de l'autre côté est refusée, elle rouvrirait la brèche.

	Ne mute pas `cells` ni `nav` : rend `(cells, nav, rapport)`. Déterministe.
	"""
	regles = regles_de(profil, regles)
	cells = [list(ligne) for ligne in cells]
	nav = dict(nav or {})
	H = len(cells)
	W = len(cells[0]) if H else 0
	rapport = {"passages": [], "zones_isolees": [], "poches_effacees": 0, "nav_ajoutes": 0}
	if not H or not W:
		return cells, nav, rapport
	cote = (lambda x, y: cotes[y][x]) if cotes else (lambda x, y: 0)
	marge = (lambda x, y: marges[y][x]) if marges else (lambda x, y: 0.0)
	cout_creuser = regles.get("cout_creuser", {})
	cout_marge = float(regles.get("cout_marge", 0.0))
	longueur_max = int(regles.get("passage_longueur_max", 12))
	isolee_max = int(regles.get("poche_isolee_max", 0))

	# Poches.
	zone, tailles = zones(cells, nav)
	poche_min = int(regles.get("poche_min", 0))
	if poche_min > 1:
		for y in range(H):
			for x in range(W):
				if zone[y][x] != -1 and tailles[zone[y][x]] < poche_min:
					cells[y][x] = TERRAIN_INACCESSIBLE
					rapport["poches_effacees"] += 1
		zone, tailles = zones(cells, nav)

	# Zones par côté.
	cote_zone = {}
	for y in range(H):
		for x in range(W):
			if zone[y][x] != -1:
				cote_zone.setdefault(zone[y][x], cote(x, y))
	par_cote = {}
	for z, c in sorted(cote_zone.items()):
		par_cote.setdefault(c, []).append(z)

	for c in sorted(par_cote):
		ids = par_cote[c]
		if len(ids) < 2:
			continue
		principale = max(ids, key=lambda z: (tailles[z], -z))
		relie = {principale}
		exclues = set()
		while len(relie) + len(exclues) < len(ids):
			chemin, cible = _plus_proche(cells, nav, zone, relie, exclues, c, cote,
				marge, cout_creuser, cout_marge, garde_terrain=bool(cotes) and not murs_nav)
			if chemin is None:
				# Plus rien d'atteignable de ce côté : les autres restent isolées.
				for z in ids:
					if z not in relie and z not in exclues:
						exclues.add(z)
						_isoler(cells, zone, z, tailles, isolee_max, rapport)
				break
			a_creuser = [(x, y) for x, y in chemin if cells[y][x] != TERRAIN_LIBRE]
			if len(a_creuser) > longueur_max:
				exclues.add(cible)
				_isoler(cells, zone, cible, tailles, isolee_max, rapport)
				continue
			traverse = sorted({cells[y][x] for x, y in a_creuser})
			for x, y in a_creuser:
				cells[y][x] = TERRAIN_LIBRE
			if cotes and murs_nav:
				# ⚠️ Le rempart n'a été scellé qu'entre cases foulables : une case creusée
				# contre le mur ouvrirait une brèche vers l'autre côté.
				rapport["nav_ajoutes"] += _sceller(cells, nav, cotes, a_creuser)
			autour ={(x + dx, y + dy) for x, y in a_creuser for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
			if murs_nav:
				rapport["nav_ajoutes"] += fermer_coins(cells, nav, autour)
			relie.add(cible)
			# Les cases creusées rejoignent la zone principale.
			for x, y in a_creuser:
				zone[y][x] = principale
			rapport["passages"].append({
				"cases": [[x, y] for x, y in a_creuser],
				"traverse": ["eau" if v == TERRAIN_EAU else ("falaise" if v == TERRAIN_FALAISE
					else "bati") for v in traverse],
				"longueur": len(a_creuser),
			})
	# ⚠️ Relu sur l'état FINAL : une zone écartée (passage trop long) a pu être rejointe
	# ensuite par le passage creusé vers une autre, qui la frôle.
	zone, tailles = zones(cells, nav)
	principales = {}
	for y in range(H):
		for x in range(W):
			z = zone[y][x]
			if z != -1:
				c = cote(x, y)
				if c not in principales or (tailles[z], -z) > (tailles[principales[c]], -principales[c]):
					principales[c] = z
	vues = set(principales.values())
	rapport["zones_isolees"] = []
	for y in range(H):
		for x in range(W):
			z = zone[y][x]
			if z != -1 and z not in vues:
				vues.add(z)
				rapport["zones_isolees"].append({"case": [x, y], "taille": tailles[z]})
	return cells, nav, rapport


def _sceller(cells, nav, cotes, cases) -> int:
	"""Mur `nav` entre chaque case de `cases` et ses voisines foulables de l'AUTRE côté."""
	ajoutes = 0
	for x, y in cases:
		for dx, dy in VOISINS:
			nx, ny = x + dx, y + dy
			if (_dans(cells, nx, ny) and cotes[ny][nx] != cotes[y][x]
					and cells[ny][nx] >= 1 and cells[ny][nx] != TERRAIN_FALAISE):
				ajoutes += interdire(nav, x, y, dx, dy)
	return ajoutes


def _isoler(cells, zone, z, tailles, isolee_max, rapport):
	"""Zone qu'aucun passage raisonnable ne rejoint : effacée (0) si elle tient en
	`poche_isolee_max` cases — une cour, un bout de berge, inatteignable en jeu donc trompeur
	sur la carte —, sinon laissée et SIGNALÉE à l'auteur."""
	if tailles[z] <= isolee_max:
		for y, ligne in enumerate(zone):
			for x, v in enumerate(ligne):
				if v == z:
					cells[y][x] = TERRAIN_INACCESSIBLE
					zone[y][x] = -1
		rapport["poches_effacees"] += tailles[z]


def _plus_proche(cells, nav, zone, relie, exclues, c, cote, marge, cout_creuser, cout_marge,
		garde_terrain=False):
	"""Dijkstra multi-source depuis les zones RELIÉES du côté `c` jusqu'à la première case
	d'une zone ni reliée ni exclue. `(chemin [(x, y)…] sans la source, zone atteinte)` ou
	`(None, None)`. Départage des ex æquo par index de case : déterministe.
	`garde_terrain` : refuse de creuser une case voisine d'une case libre d'un autre côté."""
	H, W = len(cells), len(cells[0])

	def contre_le_mur(x, y):
		return any(0 <= x + dx < W and 0 <= y + dy < H and cells[y + dy][x + dx] == TERRAIN_LIBRE
			and cote(x + dx, y + dy) != c for dx, dy in VOISINS)

	dist = {}
	parent = {}
	tas = []
	for y in range(H):
		for x in range(W):
			if zone[y][x] in relie and cote(x, y) == c:
				dist[(x, y)] = 0.0
				_tas_pousser(tas, (0.0, y * W + x))
	fermees = set()
	while tas:
		d, i = _tas_tirer(tas)
		x, y = i % W, i // W
		if (x, y) in fermees:
			continue
		fermees.add((x, y))
		z = zone[y][x]
		if z != -1 and z not in relie and z not in exclues:
			chemin = []
			p = (x, y)
			while p in parent:
				chemin.append(p)
				p = parent[p]
			chemin.reverse()
			return chemin[:-1], z
		for dx, dy in ORTHOGONAUX:
			nx, ny = x + dx, y + dy
			if not (0 <= nx < W and 0 <= ny < H) or (nx, ny) in fermees:
				continue
			if cote(nx, ny) != c or not nav_autorise(nav, x, y, dx, dy):
				continue
			v = cells[ny][nx]
			nz = zone[ny][nx]
			if v == TERRAIN_LIBRE:
				if nz in exclues:
					continue
				pas = 0.0 if nz in relie else 1.0
			else:
				if garde_terrain and contre_le_mur(nx, ny):
					continue
				pas = 1.0 + float(cout_creuser.get(v, 2.0)) + cout_marge * max(0.0, marge(nx, ny))
			nd = d + pas
			if nd < dist.get((nx, ny), float("inf")):
				dist[(nx, ny)] = nd
				parent[(nx, ny)] = (x, y)
				_tas_pousser(tas, (nd, ny * W + nx))
	return None, None


# ── Point d'entrée ───────────────────────────────────────────────────────────────────────
def proposer(couleurs, contours, cols, rows, nav=None, profil=None, regles=None,
		passages=True, enceinte=None, fins=None, k=SOUS_CASES, rues=True,
		murs_nav=True) -> dict:
	"""La proposition complète : `{cells, nav, profil, rapport}`.

	classer → lisser → rues → enceinte (ville) → coins → passages. ⚠️ Le lissage vient AVANT
	les rues et la topologie : il refermerait une rue ou un pont d'une case.
	`passages=False` : ni enceinte, ni coins, ni passages (`nav` rendu tel quel).
	`enceinte` : None = ce que dit le profil ; True/False force.
	`fins` (échantillons à `k×k` sous-cases par case) + `rues` : tracé des rues (`tracer_rues`),
	seulement si le profil en déclare ; sans `fins`, rien à tracer.
	`murs_nav=False` : AUCUN bit ajouté, `nav` rendu tel quel ; l'enceinte est alors fermée
	par le terrain (`fermer_enceinte_terrain`), la porte dessinée passe à 0.
	"""
	regles = regles_de(profil, regles)
	nom = profil if profil in PROFILS_GRILLE else PROFIL_DEFAUT
	analyse = analyser(couleurs, contours, cols, rows, regles)
	cells = lisser_majorite(analyse["cells"])
	nav_sortie = dict(nav or {})
	rapport = {"passages": [], "zones_isolees": [], "poches_effacees": 0, "nav_ajoutes": 0,
		"enceinte": False, "rempart": [], "coins": 0, "rues": [], "rues_dehors": 0,
		"murs_nav": bool(murs_nav)}
	# L'enceinte est cherchée AVANT les rues : elles se règlent à part dedans et dehors. Les
	# rues ne déplacent pas la masse bâtie (une fermeture de rayon 2 les comble).
	masque = []
	if regles.get("enceinte") if enceinte is None else enceinte:
		masque = detecter_enceinte(cells, regles)
	if rues and fins:
		cells, rapport["rues"] = tracer_rues(cells, fins, k, regles, masque)
		rapport["rues_dehors"] = sum(1 for x, y in rapport["rues"] if not (masque and masque[y][x]))
	if not passages:
		rapport["zones"] = len(zones(cells, nav_sortie)[1])
		return {"cells": cells, "nav": nav_sortie, "profil": nom, "rapport": rapport}

	avant = _bits(nav_sortie)
	coins = murs_nav and regles.get("coins", True)
	if masque:
		rapport["enceinte"] = True
		rapport["rempart"] = (fermer_enceinte(cells, nav_sortie, masque) if murs_nav
			else fermer_enceinte_terrain(cells, masque))
	if coins:
		rapport["coins"] = fermer_coins(cells, nav_sortie)
	if regles.get("passages", True):
		cotes = cotes_de(masque) if masque else None
		cells, nav_sortie, relie = relier_zones(cells, nav_sortie, analyse["marges"], cotes, regles,
			murs_nav=murs_nav)
		for cle in ("passages", "zones_isolees", "poches_effacees"):
			rapport[cle] = relie[cle]
		if coins:
			# Une poche effacée a pu laisser un angle neuf : repasse complète, idempotente.
			rapport["coins"] += fermer_coins(cells, nav_sortie)
	rapport["nav_ajoutes"] = _bits(nav_sortie) - avant
	rapport["zones"] = len(zones(cells, nav_sortie)[1])
	return {"cells": cells, "nav": nav_sortie, "profil": nom, "rapport": rapport}


def _bits(nav) -> int:
	return sum(bin(int(v or 0)).count("1") for v in (nav or {}).values())


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
	travaille, et la précision qui dit ce qu'il en coûte à l'auteur en retouches. `f1_moyen`
	résume les deux : c'est le score de la calibration.

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
		rappel = (n_juste / n_attendu) if n_attendu else 0.0
		precision = (n_juste / n_obtenu) if n_obtenu else 0.0
		par_valeur[v] = {
			"attendu": n_attendu,
			"obtenu": n_obtenu,
			"rappel": rappel,
			"precision": precision,
			"f1": (2 * rappel * precision / (rappel + precision)) if rappel + precision else 0.0,
		}
	return {
		"total": total,
		"justes": justes_total,
		"global": (justes_total / total) if total else 0.0,
		"f1_moyen": (sum(m["f1"] for m in par_valeur.values()) / len(par_valeur)) if par_valeur else 0.0,
		"par_valeur": par_valeur,
		"ecarts": ecarts,
	}


def concordance_nav(proposee, reference, tolerance: int = 1) -> dict:
	"""Les murs `nav` peints à la main sont-ils retrouvés ? Rappel = part des cases de
	`reference` portant un mur qui ont, à `tolerance` cases près (Chebyshev), une case murée
	dans `proposee`. Un mur tracé à une case près suffit à l'auteur ; un bit exact près, non —
	les deux grilles ne coupent pas le même trait au même endroit."""
	def cases(nav):
		sortie = set()
		for cle, v in (nav or {}).items():
			if int(v or 0):
				try:
					x, y = (int(p) for p in str(cle).split(","))
				except ValueError:
					continue
				sortie.add((x, y))
		return sortie
	ref, prop = cases(reference), cases(proposee)
	retrouves = sum(1 for x, y in ref if any((x + dx, y + dy) in prop
		for dx in range(-tolerance, tolerance + 1) for dy in range(-tolerance, tolerance + 1)))
	return {"peintes": len(ref), "proposees": len(prop), "retrouvees": retrouves,
		"rappel": (retrouves / len(ref)) if ref else 0.0}
