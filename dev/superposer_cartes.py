"""Superpose deux cartes de pays voisines pour VALIDER leur frontière : zones et passages.

Calage (repères, similitude sans rotation) : `dev/calage_cartes.py`, une paire par frontière ;
la carte POSÉE, la plus détaillée, est rétrécie sur la carte de FOND.

Sortie par paire : `dev/cartes/superposition_<paire>.jpg` — les deux cartes en fondu à
`--alpha` sur leur recouvrement, et par-dessus, lus dans le DUMP le plus récent
(`jsons/telluris-dump-*.json`) :
  · les cases à 0 de chaque grille (profil `pays` : ce sont les frontières, la mer est fermée
    par `nav`) — bleu pour le fond, rouge pour la carte posée ;
  · en VIOLET les cases du fond DOUBLEMENT praticables : dans la zone de terre du fond ET,
    projetées, dans celle de la carte posée — le même terrain franchissable sur les deux ;
  · les passages de la paire : bout du fond en bleu, bout posé en rouge, un trait épais reliant
    les deux bouts d'une même connexion.

Rapport : par paire, l'écart des deux bouts de chaque passage, en cases du fond (0 = ils se
font face), et le compte de cases doublement praticables.

	python dev/superposer_cartes.py [paire …] [--alpha 0.5] [--sans-frontieres]
		[--import jsons/<lot>_a_importer.json]

`--import` : le lot appliqué par-dessus le dump (PUT complet, `_deleted` supprime) — l'aperçu
de ce que la base sera une fois le lot importé.
"""

import argparse
import glob
import json
import os
import statistics
import sys

from PIL import Image, ImageDraw

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from dev.calage_cartes import PAIRES, ajuster  # noqa: E402
from utils import grille_image  # noqa: E402

CARTES = os.path.join(RACINE, "templates", "resources", "maps")
SORTIES = os.path.join(RACINE, "dev", "cartes")

BLEU = (40, 110, 255)
ROUGE = (230, 30, 30)
VIOLET = (170, 0, 220)
TRAIT = (255, 215, 0)

# Une case de TERRE par carte (celle des générateurs : `ANCRE_*`) : sa zone est celle où l'on
# marche — sur une carte de pays, la mer est une zone à part.
ANCRES = {
	"lieu:france": (45, 25),
	"lieu:plaine_europeenne": (41, 29),
	"lieu:espagne": (40, 24),
	"lieu:italie": (47, 25),
	"lieu:pannonie": (50, 25),
	"lieu:roumanie": (35, 17),
	"lieu:egypte": (40, 30),
	"lieu:afrique_du_nord": (40, 30),
}

def image_de(doc):
	return Image.open(os.path.join(CARTES, doc["image"])).convert("RGBA")


def superposer(paire, docs, alpha=0.5):
	"""(toile, info) : `info[lieu]` = (échelle, origine px sur la toile, taille de l'image)."""
	cfg = PAIRES[paire]
	s, tx, ty = ajuster(cfg["reperes"])
	fond, pose = image_de(docs[cfg["fond"]]), image_de(docs[cfg["pose"]])
	taille_pose = pose.size
	pose = pose.resize((round(pose.width * s), round(pose.height * s)), Image.LANCZOS)
	tx, ty = round(tx), round(ty)
	x0, y0 = min(0, tx), min(0, ty)
	w = max(fond.width, tx + pose.width) - x0
	h = max(fond.height, ty + pose.height) - y0
	toile = Image.new("RGBA", (w, h), (0, 0, 0, 255))
	# Fond opaque dessous : hors du recouvrement il garde ses couleurs, dedans le fondu.
	toile.alpha_composite(fond, (-x0, -y0))
	toile.alpha_composite(pose, (tx - x0, ty - y0))
	fond.putalpha(round(255 * alpha))
	toile.alpha_composite(fond, (-x0, -y0))
	return toile, {cfg["fond"]: (1.0, (-x0, -y0), fond.size),
				   cfg["pose"]: (s, (tx - x0, ty - y0), taille_pose)}


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


def vers_toile(lieu, info):
	"""Case (x, y) de la grille de `lieu` → (rect px de la case, centre px) sur la toile."""
	k, (ox, oy), (lw, lh) = info[lieu["_id"]]
	cells = lieu["cells"]
	cw, ch = lw / len(cells[0]) * k, lh / len(cells) * k

	def f(x, y):
		rect = (ox + x * cw, oy + y * ch, ox + (x + 1) * cw, oy + (y + 1) * ch)
		return rect, ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
	return f


def depuis_toile(lieu, info):
	"""Point px de la toile → case (x, y) de la grille de `lieu` (peut tomber hors grille)."""
	k, (ox, oy), (lw, lh) = info[lieu["_id"]]
	cells = lieu["cells"]
	cw, ch = lw / len(cells[0]) * k, lh / len(cells) * k
	return lambda px, py: (int((px - ox) // cw), int((py - oy) // ch))


def zone(doc):
	"""Cases de la zone de terre de `doc` (celle de son ancre)."""
	z, _tailles = grille_image.zones(doc["cells"], doc.get("nav") or {})
	ax, ay = ANCRES[doc["_id"]]
	n = z[ay][ax]
	return {(x, y) for y, ligne in enumerate(z) for x, v in enumerate(ligne) if v == n and n != -1}


def valider(paire, toile, info, docs):
	"""Dessine zones à 0, cases doublement praticables et passages ; rend le rapport."""
	cfg = PAIRES[paire]
	fond_id, pose_id = cfg["fond"], cfg["pose"]
	fond, pose = docs[fond_id], docs[pose_id]
	proj = {i: vers_toile(docs[i], info) for i in (fond_id, pose_id)}
	calque = Image.new("RGBA", toile.size, (0, 0, 0, 0))
	d = ImageDraw.Draw(calque)
	for lieu_id, couleur in ((fond_id, BLEU), (pose_id, ROUGE)):
		for y, rang in enumerate(docs[lieu_id]["cells"]):
			for x, v in enumerate(rang):
				if v == 0:
					d.rectangle(proj[lieu_id](x, y)[0], fill=couleur + (90,), outline=couleur + (150,))
	z_fond, z_pose = zone(fond), zone(pose)
	vers_pose = depuis_toile(pose, info)
	doubles = [c for c in z_fond if vers_pose(*proj[fond_id](*c)[1]) in z_pose]
	for c in doubles:
		d.rectangle(proj[fond_id](*c)[0], fill=VIOLET + (130,), outline=VIOLET + (220,))
	toile.alpha_composite(calque)

	liens = [c for c in docs.values() if c.get("type") == "connection"
		and sorted(n["lieu"] for n in c.get("nodes", [])) == sorted((fond_id, pose_id))]
	cote = info[fond_id][2][0] / len(fond["cells"][0])
	d = ImageDraw.Draw(toile)
	bouts, ecarts = [], []
	for c in sorted(liens, key=lambda c: c["_id"]):
		pos = {n["lieu"]: proj[n["lieu"]](*n["pos"])[1] for n in c["nodes"]}
		a, b = pos[fond_id], pos[pose_id]
		ecarts.append((((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 / cote, c["_id"]))
		d.line([a, b], fill=(0, 0, 0, 255), width=7)
		d.line([a, b], fill=TRAIT + (255,), width=4)
		bouts += [(a, BLEU), (b, ROUGE)]
	for (cx, cy), couleur in bouts:
		d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=couleur + (255,), outline=(0, 0, 0, 255), width=2)
	return {"liens": len(liens), "ecarts": ecarts, "doubles": len(doubles)}


def main() -> int:
	ap = argparse.ArgumentParser()
	ap.add_argument("paires", nargs="*")
	ap.add_argument("--alpha", type=float, default=0.5)
	ap.add_argument("--sans-frontieres", action="store_true")
	ap.add_argument("--import", dest="lot")
	args = ap.parse_args()
	paires = args.paires or list(PAIRES)
	inconnues = [p for p in paires if p not in PAIRES]
	if inconnues:
		print(f"✗ paire(s) inconnue(s) : {', '.join(inconnues)} — connues : {', '.join(PAIRES)}")
		return 2
	docs, dump = charger_dump(args.lot)
	print(dump)
	os.makedirs(SORTIES, exist_ok=True)
	for paire in paires:
		cfg = PAIRES[paire]
		toile, info = superposer(paire, docs, args.alpha)
		ligne = f"{paire} : {cfg['pose']} ×{info[cfg['pose']][0]:.3f} sur {cfg['fond']}"
		if not args.sans_frontieres:
			r = valider(paire, toile, info, docs)
			e = [v for v, _ in r["ecarts"]]
			if e:
				pire = max(r["ecarts"])
				ligne += (f" — {r['liens']} passages, écart médian {statistics.median(e):.1f} "
						  f"case(s), max {pire[0]:.1f} ({pire[1]}) ; {r['doubles']} case(s) "
						  f"doublement praticables")
			else:
				ligne += f" — aucun passage ; {r['doubles']} case(s) doublement praticables"
		sortie = os.path.join(SORTIES, f"superposition_{paire}.jpg")
		toile.convert("RGB").save(sortie, quality=88)
		print(f"{ligne}\n  ✎ {os.path.relpath(sortie, RACINE)} {toile.size}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
