#!/usr/bin/env python
# dev/detourer_image.py
# Détoure une illustration de monstre générée sur fond UNI (docs/prompts_images.md § 3 :
# magenta, vert vif ou bleu vif) → PNG transparent recadré au contenu.
#
# Méthode (Pillow + stdlib seuls, comme l'image Docker) :
#   1. couleur du fond = médiane des pixels du cadre ;
#   2. remplissage DEPUIS LES BORDS sur les pixels proches de cette couleur : seul le fond
#      relié au cadre disparaît, une touche de la même teinte DANS la créature reste ;
#   3. poches ENCLAVÉES (entre des cous, sous une aile) : composantes de pixels TRÈS proches
#      du fond, d'au moins POCHE_MIN pixels, plus leur halo doux ;
#   4. alpha en rampe entre `dur` et `doux` (bord adouci), teinte du fond retirée des pixels
#      semi-transparents (sinon liseré magenta/bleu), recadrage au contenu.
#
# ⚠️ Échoue sans le dire sur une image avec DÉCOR (rocher, sol, grotte collés à la créature) :
# le fond n'est plus uni, la médiane du cadre est fausse. Regarder le résultat sur fond sombre
# ET clair ; si le décor reste, régénérer l'image (prompt : « aucun rocher, aucun sol… »).
#
# Usage :
#   python dev/detourer_image.py source.jpg <slug_espece>      # → templates/resources/monsters/<slug>_transparent.png
#   python dev/detourer_image.py source.jpg <slug>_transparent01.png  # variante tirée au sort en combat (utils/images_monstres.py)
#   python dev/detourer_image.py source.jpg chemin/sortie.png [--dur 60] [--doux 110]

import argparse
import os
import statistics
import sys
from collections import deque

from PIL import Image, ImageFilter

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONSTRES = os.path.join(RACINE, "templates", "resources", "monsters")

POCHE_MIN = 25      # pixels : en dessous, un reflet de la créature, pas une poche de fond
HALO = 6            # pixels de halo doux autour d'une poche
VOISINS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _pixels(img) -> list:
	"""Pixels à plat : `get_flattened_data` (Pillow ≥ 12), `getdata` avant."""
	lire = getattr(img, "get_flattened_data", None) or img.getdata
	return list(lire())


def _remplir(depart, accepte, w, h, marque):
	"""BFS 4-connexe depuis `depart` sur les indices où `accepte(i)` ; marque et renvoie la liste."""
	q, vus = deque(), []
	for i in depart:
		if not marque[i] and accepte(i):
			marque[i] = 1
			q.append(i)
	while q:
		i = q.popleft()
		vus.append(i)
		y, x = divmod(i, w)
		for dy, dx in VOISINS:
			ny, nx = y + dy, x + dx
			if 0 <= ny < h and 0 <= nx < w:
				j = ny * w + nx
				if not marque[j] and accepte(j):
					marque[j] = 1
					q.append(j)
	return vus


def detourer(source: str, sortie: str, dur: float = 60.0, doux: float = 110.0) -> tuple:
	img = Image.open(source).convert("RGB")
	w, h = img.size
	px = _pixels(img)

	cadre = [y * w + x for y in range(h) for x in (0, w - 1)] + \
			[y * w + x for x in range(w) for y in (0, h - 1)]
	fond = tuple(statistics.median(px[i][c] for i in cadre) for c in range(3))
	dist = [((r - fond[0]) ** 2 + (g - fond[1]) ** 2 + (b - fond[2]) ** 2) ** 0.5 for (r, g, b) in px]

	# 2. Fond relié au cadre.
	fondu = bytearray(w * h)
	_remplir(cadre, lambda i: dist[i] < doux, w, h, fondu)

	# 3. Poches enclavées, puis leur halo.
	poche = dur * 0.8
	vu = bytearray(fondu)
	grandes = bytearray(w * h)
	for i in range(w * h):
		if not vu[i] and dist[i] < poche:
			comp = _remplir([i], lambda j: dist[j] < poche, w, h, vu)
			if len(comp) >= POCHE_MIN:
				for j in comp:
					grandes[j] = 255
		vu[i] = 1
	if any(grandes):
		masque = Image.frombytes("L", (w, h), bytes(grandes)).filter(ImageFilter.MaxFilter(2 * HALO + 1))
		for i, v in enumerate(_pixels(masque)):
			if grandes[i] or (v and dist[i] < doux):
				fondu[i] = 1

	# 4. Alpha adouci et teinte du fond retirée.
	sortie_px = []
	for i, (r, g, b) in enumerate(px):
		if not fondu[i]:
			sortie_px.append((r, g, b, 255))
			continue
		a = min(1.0, max(0.0, (dist[i] - dur) / (doux - dur)))
		if a <= 0.01:
			sortie_px.append((0, 0, 0, 0))
			continue
		rgb = tuple(min(255, max(0, round((v - f * (1 - a)) / a))) for v, f in zip((r, g, b), fond))
		sortie_px.append(rgb + (round(a * 255),))

	out = Image.new("RGBA", (w, h))
	out.putdata(sortie_px)
	bbox = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
	out = out.crop(bbox)
	out.save(sortie, optimize=True)
	part_fond = sum(fondu) / (w * h)
	return fond, out.size, part_fond


def main() -> None:
	p = argparse.ArgumentParser(description="Détoure une illustration de monstre sur fond uni.")
	p.add_argument("source", help="image générée (jpg/png)")
	p.add_argument("cible", help="slug d'espèce (→ templates/resources/monsters/<slug>_transparent.png), nom .png seul "
					"(même dossier) ou chemin .png de sortie")
	p.add_argument("--dur", type=float, default=60.0, help="distance au fond sous laquelle un pixel est effacé")
	p.add_argument("--doux", type=float, default=110.0, help="distance au-delà de laquelle un pixel reste opaque")
	args = p.parse_args()
	if args.doux <= args.dur:
		sys.exit("ERREUR : --doux doit dépasser --dur")
	sortie = args.cible if args.cible.lower().endswith(".png") else f"{args.cible}_transparent.png"
	if not os.path.dirname(sortie):
		sortie = os.path.join(MONSTRES, sortie)  # nom seul (variante `…_transparent01.png`) : dossier des monstres
	fond, taille, part = detourer(args.source, sortie, args.dur, args.doux)
	print(f"{os.path.relpath(sortie, RACINE)} : fond {tuple(round(c) for c in fond)}, "
		  f"{taille[0]}x{taille[1]}, {part:.0%} de fond retiré")


if __name__ == "__main__":
	main()
