"""Relit la grille d'une cité DESSINÉE À L'ENCRE par ses traits noirs (`utils/grille_traits`).

POURQUOI : la proposition de `gen_grille_image.py` classe chaque case par sa couleur ; sur une
carte à l'encre, elle fait traverser des maisons et bloque des rues. Ici une rue est ce qui
reste clair et beige entre les traits, et un trait noir est une limite (mur `nav`).

Sans spec, toute la carte est relue. Avec `--spec` (JSON, facultatif) :
  {"enceinte": [[x, y], …],        polygone en cases sur la crête du mur : son anneau devient
                                   le rempart (rien ne le franchit) et seul l'intérieur est
                                   relu — le dehors garde la grille du doc ;
   "passages": [[[x, y], …], …]}   suites de cases voisines ouvertes à la main (arche, porte
                                   que la lecture manque).

N'ÉCRIT PAS EN BASE : relit le doc dans le DUMP (CLAUDE.md §11) et n'y change que `cells` et
`nav`. ⚠️ Première passe : les zones isolées sont listées, à relier dans l'éditeur (ou par
`passages`). Les portes de rempart, elles, se posent dans l'éditeur (🏰).

Usage :
  python dev/gen_grille_traits.py lieu:calais [--dump jsons/telluris-dump-….json]
                                  [--spec spec.json] [--sans-apercu]

Sorties (nom FIXE, celui que relit le 📥 Importer de /admin/lieux) :
  jsons/grille_traits_a_importer.json (le doc complet) + jsons/grille_traits_apercu.png
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from utils import grille_image, grille_traits  # noqa: E402

RACINE = ggi.RACINE


def masque_image(chemin):
	"""(masque de rue, largeur, hauteur) de l'image (Pillow)."""
	from PIL import Image
	with Image.open(chemin) as img:
		img = img.convert("RGB")
		largeur, hauteur = img.size
		octets = img.tobytes()
	libre = [grille_traits.pixel_de_rue(octets[i], octets[i + 1], octets[i + 2])
			 for i in range(0, len(octets), 3)]
	return grille_traits.masque_rues(libre, largeur, hauteur), largeur, hauteur


def relire(doc, masque, spec=None):
	"""(doc relu, rapport) — `masque` = (masque de rue, largeur, hauteur). Pur."""
	spec = spec or {}
	cells = [list(ligne) for ligne in doc["cells"]]
	nav = dict(doc.get("nav") or {})
	cols, rows = len(cells[0]), len(cells)
	rue, largeur, hauteur = masque
	anneau = set()
	if spec.get("enceinte"):
		anneau, cases = grille_traits.anneau_et_interieur(spec["enceinte"], cols, rows)
	else:
		cases = {(x, y) for y in range(rows) for x in range(cols)}
	murs = grille_traits.grille_traits(cells, nav, rue, largeur, hauteur, cases)
	fermees = grille_traits.fermer_anneau(cells, nav, anneau)
	grille_traits.ouvrir_passages(cells, nav, spec.get("passages") or [])
	zone, tailles = grille_image.zones(cells, nav)
	par_zone = {}
	for y, ligne in enumerate(zone):
		for x, z in enumerate(ligne):
			if z != -1 and (x, y) in cases:
				par_zone.setdefault(z, []).append((x, y))
	sortant = dict(doc, cells=cells, nav=nav)
	sortant.pop("_rev", None)
	zones_relues = sorted(par_zone.values(), key=len, reverse=True)
	return sortant, {"murs_nav": murs, "anneau": fermees, "zones": zones_relues}


def main() -> int:
	args = sys.argv[1:]
	options = {a for a in args if a.startswith("--") and a not in ("--dump", "--spec")}

	def valeur(nom):
		if nom in args and args.index(nom) + 1 < len(args):
			return args[args.index(nom) + 1]
		return None

	cibles = [a for a in args if a.startswith("lieu:")]
	if not cibles:
		print(__doc__)
		return 2
	docs = ggi.charger_dump(valeur("--dump"))
	doc = next((d for d in docs if d.get("_id") == cibles[0]), None)
	if not doc or not doc.get("cells") or not doc.get("image"):
		print(f"✗ {cibles[0]} : absent du dump, sans grille ou sans image.")
		return 1
	chemin = ggi.trouver_image(doc["image"])
	if not chemin:
		print(f"✗ image introuvable : {doc['image']}")
		return 1
	spec = {}
	if valeur("--spec"):
		with open(valeur("--spec"), encoding="utf-8") as f:
			spec = json.load(f)
	sortant, rapport = relire(doc, masque_image(chemin), spec)
	zones = rapport["zones"]
	print(f"{doc['_id']} — {rapport['murs_nav']} mur(s) nav posé(s) sur les traits · "
		  f"{rapport['anneau']} case(s) d'anneau fermée(s)")
	print(f"  réseau principal : {len(zones[0]) if zones else 0} cases · "
		  f"{len(zones) - 1 if zones else 0} zone(s) isolée(s)")
	for z in zones[1:16]:
		print(f"    {len(z):4} case(s) autour de {list(min(z))}")
	sortie = os.path.join(ggi.DOSSIER_JSONS, "grille_traits_a_importer.json")
	with open(sortie, "w", encoding="utf-8") as f:
		json.dump([sortant], f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"  ✎ {os.path.relpath(sortie, RACINE)}")
	if "--sans-apercu" not in options:
		apercu = os.path.join(ggi.DOSSIER_JSONS, "grille_traits_apercu.png")
		ggi.ecrire_apercu(chemin, sortant["cells"], apercu, sortant["nav"])
		print(f"  ✎ {os.path.relpath(apercu, RACINE)}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
