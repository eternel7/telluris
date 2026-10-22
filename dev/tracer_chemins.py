"""Aperçu de JOUABILITÉ d'une cité : entrées, portes de rempart et chemins entre elles.

POURQUOI : une grille se juge à ce qu'on peut y faire. On trace, avec le tracé des voies de
l'éditeur (`dev/tracer_chemins.js` → `templates/scripts/voies.js`, jusqu'à 8 variantes par
paire), les chemins :
- DEHORS : entre chaque paire de points d'arrivée (connexions venues d'un autre lieu) et de
  cases extérieures de porte de rempart ;
- DEDANS : d'une case intérieure de porte de rempart à une autre — il doit TOUJOURS exister
  un passage d'une porte à l'autre.
Une paire injoignable est signalée. Règle de pas : exploration (case === 1), celle des flèches.

Usage : python dev/tracer_chemins.py jsons/<fichier>_a_importer.json lieu:<cite> [--max 8]
Sortie : jsons/<slug>_chemins_apercu.png
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from utils.lieux import VALID_MOVES  # noqa: E402

COULEURS = [(230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200), (245, 130, 48),
	(145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60), (250, 190, 212),
	(0, 128, 128), (170, 110, 40)]


def points(docs, cite):
	"""(arrivées, portes) : arrivées = nœuds posés sur la cité par une connexion venue d'un
	autre lieu (hors portes) ; portes = {nom: (case dehors, case dedans)}."""
	lieux = {d["_id"]: d for d in docs if d.get("type") == "lieu"}
	arrivees, portes = [], {}
	for d in docs:
		if d.get("type") != "connection":
			continue
		ici = [n for n in d["nodes"] if n["lieu"] == cite]
		autres = [n for n in d["nodes"] if n["lieu"] != cite]
		if not ici or not autres:
			continue
		autre = lieux.get(autres[0]["lieu"], {})
		if autre.get("categorie") == "Porte de rempart":
			nom = autre["label"].rsplit(" — ", 1)[0]
			cote = 0 if autre["_id"].endswith("_exterieur") else 1
			portes.setdefault(nom, [None, None])[cote] = tuple(ici[0]["pos"])
		else:
			arrivees.append((ici[0].get("label") or autres[0]["lieu"], tuple(ici[0]["pos"])))
	return arrivees, portes


def tracer(doc, paires, maxi):
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
		json.dump({"cells": doc["cells"], "nav": doc.get("nav") or {},
			"dims": doc["dimensions"], "regle": "exploration", "max": maxi,
			"paires": [{"nom": n, "a": list(a), "b": list(b)} for n, a, b in paires]}, f)
	try:
		sortie = subprocess.run(["node", os.path.join(os.path.dirname(__file__), "tracer_chemins.js"),
			f.name], capture_output=True, text=True, check=True).stdout
	finally:
		os.unlink(f.name)
	return json.loads(sortie)["paires"]


def main() -> int:
	args = [a for a in sys.argv[1:] if not a.startswith("--")]
	maxi = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 8
	if len(args) < 2:
		print(__doc__)
		return 2
	docs = json.load(open(args[0], encoding="utf-8"))
	cite = args[1]
	doc = next(d for d in docs if d["_id"] == cite)
	arrivees, portes = points(docs, cite)
	dehors = arrivees + [(f"{n} (dehors)", c[0]) for n, c in portes.items()]
	dedans = [(f"{n} (dedans)", c[1]) for n, c in portes.items()]
	paires = []
	for groupe in (dehors, dedans):
		for i in range(len(groupe)):
			for j in range(i + 1, len(groupe)):
				paires.append((f"{groupe[i][0]} → {groupe[j][0]}", groupe[i][1], groupe[j][1]))
	resultats = tracer(doc, paires, maxi)
	for r in resultats:
		print(f"{'✗' if not r['chemins'] else '✓'} {r['nom']} : {len(r['chemins'])} chemin(s)"
			+ (f", le plus court {len(r['chemins'][0])} cases" if r["chemins"] else " — INJOIGNABLE"))

	from PIL import Image, ImageDraw
	chemin_img = ggi.trouver_image(doc["image"])
	im = Image.open(chemin_img).convert("RGB")
	cw, ch = im.width / doc["dimensions"]["x"], im.height / doc["dimensions"]["y"]
	dr = ImageDraw.Draw(im, "RGBA")
	for y, ligne in enumerate(doc["cells"]):
		for x, v in enumerate(ligne):
			boite = [x * cw, y * ch, (x + 1) * cw, (y + 1) * ch]
			if v == 0:
				dr.rectangle(boite, fill=(0, 0, 0, 110))
			elif v == 5:
				dr.rectangle(boite, fill=(0, 70, 255, 110))
	for cle, masque in (doc.get("nav") or {}).items():
		x, y = map(int, cle.split(","))
		for bit, dx, dy, _op in VALID_MOVES:
			if masque & bit:
				cx, cy = (x + 0.5) * cw, (y + 0.5) * ch
				dr.line([cx, cy, cx + dx * cw * 0.5, cy + dy * ch * 0.5], fill=(255, 0, 0, 255), width=3)
	for k, r in enumerate(resultats):
		couleur = COULEURS[k % len(COULEURS)]
		for n, c in enumerate(r["chemins"]):
			pts = [((x + 0.5) * cw + (k % 3 - 1) * 2, (y + 0.5) * ch + (n % 3 - 1) * 2) for x, y in c]
			dr.line(pts, fill=couleur + (230 if n == 0 else 120,), width=3 if n == 0 else 1)
	for nom, (x, y) in dehors + dedans:
		cx, cy = (x + 0.5) * cw, (y + 0.5) * ch
		porte = "dedans" in nom or "dehors" in nom
		dr.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(255, 140, 0, 255) if porte else (255, 255, 255, 255),
			outline=(0, 0, 0, 255), width=2)
	sortie = os.path.join(ggi.DOSSIER_JSONS, f"{cite.split(':', 1)[1]}_chemins_apercu.png")
	im.save(sortie)
	print(f"✎ {os.path.relpath(sortie, ggi.RACINE)}")
	return 0 if all(r["chemins"] for r in resultats) else 1


if __name__ == "__main__":
	sys.exit(main())
