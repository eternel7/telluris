"""Superpose `plaine_europeenne.jpg` et `france.png` : le nord de la France coïncide.

Les deux cartes sont orientées nord en haut : la transformation est une SIMILITUDE SANS
ROTATION (échelle + translation) de la plaine vers la France, ajustée aux moindres carrés sur
des repères lus à la main sur les deux images (px de l'image d'origine, 1408×768).

Sortie : la plaine à l'échelle et la France, en fondu à `--alpha` sur leur recouvrement (0.5
par défaut : les deux tracés se lisent ; 1 : la France recouvre la plaine).

	python dev/superposer_cartes.py [--alpha 0.5] [--sortie chemin.jpg]
"""

import argparse
import os

from PIL import Image

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARTES = os.path.join(RACINE, "templates", "resources", "maps")

# Repères : nom → (point sur la plaine, point sur la France).
REPERES = {
	"embouchure de la Seine": ((148, 597), (560, 160)),
	"Lutecia": ((258, 705), (715, 212)),
	"pas de Calais": ((215, 550), (660, 20)),
	"forêt d'Ardenne": ((500, 620), (950, 190)),
}


def ajuster(reperes):
	"""(s, tx, ty) minimisant Σ |s·p + t − f|² — similitude sans rotation."""
	ps = [p for p, _ in reperes.values()]
	fs = [f for _, f in reperes.values()]
	n = len(ps)
	pcx, pcy = sum(p[0] for p in ps) / n, sum(p[1] for p in ps) / n
	fcx, fcy = sum(f[0] for f in fs) / n, sum(f[1] for f in fs) / n
	num = sum((p[0] - pcx) * (f[0] - fcx) + (p[1] - pcy) * (f[1] - fcy) for p, f in zip(ps, fs))
	den = sum((p[0] - pcx) ** 2 + (p[1] - pcy) ** 2 for p in ps)
	s = num / den
	return s, fcx - s * pcx, fcy - s * pcy


def superposer(alpha=0.5):
	s, tx, ty = ajuster(REPERES)
	plaine = Image.open(os.path.join(CARTES, "plaine_europeenne.jpg")).convert("RGBA")
	france = Image.open(os.path.join(CARTES, "france.png")).convert("RGBA")
	plaine = plaine.resize((round(plaine.width * s), round(plaine.height * s)), Image.LANCZOS)
	tx, ty = round(tx), round(ty)
	x0, y0 = min(0, tx), min(0, ty)
	w = max(france.width, tx + plaine.width) - x0
	h = max(france.height, ty + plaine.height) - y0
	toile = Image.new("RGBA", (w, h), (0, 0, 0, 255))
	# France opaque dessous : hors du recouvrement elle garde ses couleurs, dedans le fondu.
	toile.alpha_composite(france, (-x0, -y0))
	toile.alpha_composite(plaine, (tx - x0, ty - y0))
	france.putalpha(round(255 * alpha))
	toile.alpha_composite(france, (-x0, -y0))
	return toile, {"echelle": s, "plaine": (tx - x0, ty - y0), "france": (-x0, -y0)}


if __name__ == "__main__":
	ap = argparse.ArgumentParser()
	ap.add_argument("--alpha", type=float, default=0.5)
	ap.add_argument("--sortie", default=os.path.join(RACINE, "dev", "cartes", "superposition_plaine_france.jpg"))
	args = ap.parse_args()
	toile, info = superposer(args.alpha)
	os.makedirs(os.path.dirname(args.sortie), exist_ok=True)
	toile.convert("RGB").save(args.sortie, quality=90)
	print(f"{args.sortie} {toile.size} échelle plaine ×{info['echelle']:.3f}, "
	      f"plaine en {info['plaine']}, France en {info['france']}")
