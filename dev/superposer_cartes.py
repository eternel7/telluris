"""Superpose `plaine_europeenne.jpg` et `france.png` : le nord de la France coïncide.

Les deux cartes sont orientées nord en haut : la transformation est une SIMILITUDE SANS
ROTATION (échelle + translation) de la plaine vers la France, ajustée aux moindres carrés sur
des repères lus à la main sur les deux images (px de l'image d'origine, 1408×768).

Sortie : la plaine à l'échelle et la France, en fondu à `--alpha` sur leur recouvrement (0.5
par défaut : les deux tracés se lisent ; 1 : la France recouvre la plaine).

Par-dessus, lus dans le DUMP le plus récent (`jsons/telluris-dump-*.json`) :
  · les cases à 0 de chaque grille (profil `pays` : ce sont les frontières, la mer est
    fermée par `nav`) — bleu pour la France, rouge pour la plaine ;
  · les passages France ↔ plaine : le bout France en bleu, le bout plaine en rouge, un trait
    épais reliant les deux bouts d'une même connexion.

	python dev/superposer_cartes.py [--alpha 0.5] [--sortie chemin.jpg] [--sans-frontieres]
		[--import jsons/<lot>_a_importer.json]

`--import` : le lot appliqué par-dessus le dump (PUT complet, `_deleted` supprime) — l'aperçu
de ce que la base sera une fois le lot importé.
"""

import argparse
import glob
import json
import os

from PIL import Image, ImageDraw

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARTES = os.path.join(RACINE, "templates", "resources", "maps")
FRANCE = "lieu:france"
PLAINE = "lieu:plaine_europeenne"

BLEU = (40, 110, 255)
ROUGE = (230, 30, 30)
TRAIT = (255, 215, 0)

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


def charger_dump(lot=None):
	"""{_id: doc} du dump committé le plus récent, `lot` (fichier à importer) appliqué dessus."""
	chemin = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))[-1]
	with open(chemin, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	nom = os.path.basename(chemin)
	if lot:
		with open(lot, encoding="utf-8") as f:
			for d in json.load(f):
				if d.get("_deleted"):
					docs.pop(d["_id"], None)
				else:
					docs[d["_id"]] = d
		nom += " + " + os.path.basename(lot)
	return docs, nom


def vers_toile(lieu, info, taille_image):
	"""Case (x, y) de la grille de `lieu` → (rect px de la case, centre px) sur la toile."""
	cells = lieu["cells"]
	cw, ch = taille_image[0] / len(cells[0]), taille_image[1] / len(cells)
	k = info["echelle"] if lieu["_id"] == PLAINE else 1.0
	ox, oy = info["plaine"] if lieu["_id"] == PLAINE else info["france"]

	def f(x, y):
		rect = (ox + x * cw * k, oy + y * ch * k, ox + (x + 1) * cw * k, oy + (y + 1) * ch * k)
		return rect, ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
	return f


def dessiner_frontieres(toile, info, docs):
	"""Cases à 0 des deux grilles, puis passages France ↔ plaine reliés deux à deux."""
	tailles = {i: Image.open(os.path.join(CARTES, docs[i]["image"])).size for i in (FRANCE, PLAINE)}
	proj = {i: vers_toile(docs[i], info, tailles[i]) for i in (FRANCE, PLAINE)}
	calque = Image.new("RGBA", toile.size, (0, 0, 0, 0))
	d = ImageDraw.Draw(calque)
	for lieu_id, couleur in ((FRANCE, BLEU), (PLAINE, ROUGE)):
		for y, rang in enumerate(docs[lieu_id]["cells"]):
			for x, v in enumerate(rang):
				if v == 0:
					d.rectangle(proj[lieu_id](x, y)[0], fill=couleur + (90,), outline=couleur + (150,))
	toile.alpha_composite(calque)

	liens = [c for c in docs.values() if c.get("type") == "connection"
		and sorted(n["lieu"] for n in c.get("nodes", [])) == sorted((FRANCE, PLAINE))]
	d = ImageDraw.Draw(toile)
	bouts = []
	for c in liens:
		pos = {n["lieu"]: proj[n["lieu"]](*n["pos"])[1] for n in c["nodes"]}
		d.line([pos[FRANCE], pos[PLAINE]], fill=(0, 0, 0, 255), width=7)
		d.line([pos[FRANCE], pos[PLAINE]], fill=TRAIT + (255,), width=4)
		bouts += [(pos[FRANCE], BLEU), (pos[PLAINE], ROUGE)]
	for (cx, cy), couleur in bouts:
		d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=couleur + (255,), outline=(0, 0, 0, 255), width=2)
	return len(liens)


if __name__ == "__main__":
	ap = argparse.ArgumentParser()
	ap.add_argument("--alpha", type=float, default=0.5)
	ap.add_argument("--sortie", default=os.path.join(RACINE, "dev", "cartes", "superposition_plaine_france.jpg"))
	ap.add_argument("--sans-frontieres", action="store_true")
	ap.add_argument("--import", dest="lot")
	args = ap.parse_args()
	toile, info = superposer(args.alpha)
	if not args.sans_frontieres:
		docs, dump = charger_dump(args.lot)
		n = dessiner_frontieres(toile, info, docs)
		print(f"{dump} : {n} connexions France ↔ plaine")
	os.makedirs(os.path.dirname(args.sortie), exist_ok=True)
	toile.convert("RGB").save(args.sortie, quality=90)
	print(f"{args.sortie} {toile.size} échelle plaine ×{info['echelle']:.3f}, "
	      f"plaine en {info['plaine']}, France en {info['france']}")
