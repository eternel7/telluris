"""Profils de BORD d'une image de carte : ce que lit `grille_image.epaisseur_cadre` pour mettre à 0
le cadre décoratif d'une carte de pays (enluminure, parchemin déchiqueté).

Pour chaque côté (`grille_image.COTES_CADRE`) et chaque ligne de pixels parallèle à ce côté, depuis
le bord : la densité MOYENNE de contours (`FIND_EDGES`, 0-255) et la PART de pixels blancs (0-1).
Un trait droit de cadre court sur toute la longueur du côté : il ressort de la moyenne, quand un
trait de la carte, lui, s'y dilue.

Partagé par `GET /api/lieu/{id}/grille_proposee` (`utils/lieux.py`) et `dev/gen_grille_image.py`
(donc `gen_cartes_pays.py`) : les deux chemins lisent EXACTEMENT les mêmes profils.

⚠️ Pillow importé DANS la fonction : il n'est pas dans les dépendances de collecte locale des
tests (CLAUDE.md § Running tests) — même remède que `utils/lieux.grille_proposee`.
"""

import math

# Part de la longueur du côté écartée à chaque bout : les coins mêlent les deux cadres qui s'y
# croisent (et le monde y peint des écoinçons), ils brouilleraient le trait.
COINS_EXCLUS = 0.12
# Pixel « blanc » : canal le plus sombre au-dessus de 200, écart entre canaux sous 40 — le papier
# blanc déchiqueté de France ; le parchemin crème (≈ 200/180/140) n'y entre pas.
BLANC_MIN = 200
BLANC_ECART_MAX = 40


def profils_bords(img, cols: int, rows: int, cases_max: int) -> dict:
	"""`{cote: {"contours": [...], "blanc": [...], "px_case": float}}` d'une image PIL, pour une
	grille de `cols`×`rows`. Profondeur lue : `cases_max + 1` cases (au plus la moitié de
	l'image) — au-delà, `epaisseur_cadre` ne regarde pas."""
	from PIL import Image, ImageChops, ImageFilter
	rgb = img.convert("RGB")
	w, h = rgb.size
	contours = rgb.convert("L").filter(ImageFilter.FIND_EDGES)
	r, g, b = rgb.split()
	sombre = ImageChops.darker(ImageChops.darker(r, g), b)
	clair = ImageChops.lighter(ImageChops.lighter(r, g), b)
	blanc = ImageChops.multiply(
		sombre.point(lambda v: 255 if v > BLANC_MIN else 0),
		ImageChops.subtract(clair, sombre).point(lambda v: 255 if v < BLANC_ECART_MAX else 0))

	sortie = {}
	for cote in ("haut", "bas", "gauche", "droite"):
		horizontal = cote in ("haut", "bas")
		longueur, epaisseur = (w, h) if horizontal else (h, w)
		px_case = epaisseur / float(rows if horizontal else cols)
		p = max(1, min(int(math.ceil((cases_max + 1) * px_case)), epaisseur // 2))
		a, z = int(longueur * COINS_EXCLUS), int(longueur * (1 - COINS_EXCLUS))
		boite = {"haut": (a, 0, z, p), "bas": (a, h - p, z, h),
			"gauche": (0, a, p, z), "droite": (w - p, a, w, z)}[cote]
		# BOX = moyenne d'AIRE : une ligne de pixels réduite à un seul pixel donne sa moyenne.
		taille = (1, p) if horizontal else (p, 1)
		profils = []
		for source, echelle in ((contours, 1.0), (blanc, 255.0)):
			valeurs = _a_plat(source.crop(boite).resize(taille, Image.BOX))
			if cote in ("bas", "droite"):
				valeurs.reverse()   # toujours depuis le bord
			profils.append([v / echelle for v in valeurs])
		sortie[cote] = {"contours": profils[0], "blanc": profils[1], "px_case": px_case}
	return sortie


def _a_plat(img) -> list:
	"""Les pixels, à plat (même repli Pillow 12 que `utils/lieux._pixels_a_plat`)."""
	if hasattr(img, "get_flattened_data"):
		return list(img.get_flattened_data())
	return list(img.getdata())
