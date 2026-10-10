"""Un doc `lieu:*` de ville pour chaque carte de `towns/` qu'aucun lieu n'utilise, avec sa
grille proposée par `gen_grille_image.py`.

POURQUOI : une carte de cité déposée dans `templates/resources/towns/` n'existe en jeu que
quand un doc `lieu:*` la cite par son champ `image`. Ce générateur crée ce doc — minimal, sur
le modèle de `lieu:rhemi` — et lui pose la PREMIÈRE PASSE de grille (`cells`, `nav`,
`dimensions`) que l'auteur retouche ensuite dans l'éditeur. Rien d'autre (ni intro, ni zones
d'influence, ni rencontres) : c'est du contenu à authorer.

REJOUABLE : une carte déjà citée par un lieu du dump est ignorée ; une fois le fichier importé
et le dump régénéré, le rejeu n'a plus rien à créer et N'ÉCRIT AUCUN FICHIER (le 📥 Importer
de `/admin/dev-tools` refuse alors l'ancien, cf. `dev_tools.sortie_fraiche`).

DIMENSIONS : des cases CARRÉES de la taille de celles des villes déjà en base — côté relu sur
le dump (médiane de √(px_x · px_y) des villes ayant image et dimensions), jamais en dur.

Usage :
  python dev/gen_villes_images.py [--dump jsons/telluris-dump-….json] [--sans-apercu]
  (sans --dump : le dump le plus récent de jsons/)

Sortie : jsons/villes_images_a_importer.json (+ jsons/<slug>_grille_apercu.png par ville)
"""

import json
import os
import statistics
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402

RACINE = ggi.RACINE
DOSSIER_VILLES = os.path.join(ggi.RESSOURCES, "towns")
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "villes_images_a_importer.json")

# Suffixe du nom de fichier → `sous_categorie`. ⚠️ `_start_city` AVANT `_city`, qu'il contient.
SUFFIXES = (("_start_city", "ville"), ("_capital", "capitale"), ("_city", "ville"))
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

# Libellés qui ne se déduisent pas du nom de fichier (exonyme, accent) ; sinon slug capitalisé.
LIBELLES = {
	"aix_la_chapelle": "Aix-la-Chapelle",
	"cairo": "Le Caire",
	"london": "Londres",
	"lutecia_capital": "Lutecia",
	"orleans": "Orléans",
	"pekin": "Pékin",
	"reykjavik": "Reykjavík",
}

# Cités rattachées à `lieu:france` — le seul pays en base ; les autres restent sans parent.
PAYS_FRANCE = "lieu:france"
VILLES_FRANCE = {"auxerre", "chartres", "lutecia", "lutecia_capital", "lyon", "orleans",
	"paris", "reims"}

# Repli si aucune ville de la base n'a image + dimensions : le côté des cases d'Auxerre et de
# Lutèce (1376 et 1408 px ÷ 86 et 88 cases, 768 px ÷ 48).
COTE_CASE_DEFAUT = 16


def sans_accents(texte: str) -> str:
	return "".join(c for c in unicodedata.normalize("NFKD", texte)
		if not unicodedata.combining(c))


def decouper_nom(nom: str):
	"""(base, sous_categorie) d'un fichier de carte de ville, ou None si ce n'en est pas un."""
	racine, ext = os.path.splitext(nom)
	if ext.lower() not in EXTENSIONS:
		return None
	for suffixe, sous_categorie in SUFFIXES:
		if racine.endswith(suffixe) and len(racine) > len(suffixe):
			return racine[: -len(suffixe)], sous_categorie
	return None


def slug_de(texte: str) -> str:
	return sans_accents(texte).lower().replace("-", "_").replace(" ", "_")


def images_citees(docs) -> set:
	return {d.get("image") for d in docs
		if str(d.get("_id", "")).startswith("lieu:") and d.get("image")}


def cote_case(docs, taille_fn, categorie: str = "ville") -> int:
	"""Côté en pixels des cases des lieux de `categorie` déjà en base (médiane, arrondie) —
	les villes ici, les pays pour `gen_cartes_pays.py`."""
	cotes = []
	for d in docs:
		if not str(d.get("_id", "")).startswith("lieu:") or d.get("categorie") != categorie:
			continue
		dim = d.get("dimensions") or {}
		taille = taille_fn(d.get("image")) if d.get("image") else None
		if not taille or not dim.get("x") or not dim.get("y"):
			continue
		cotes.append(((taille[0] / dim["x"]) * (taille[1] / dim["y"])) ** 0.5)
	return round(statistics.median(cotes)) if cotes else COTE_CASE_DEFAUT


def villes_a_creer(noms_images, docs, taille_fn):
	"""(docs à créer SANS grille, refus). Un `_id` déjà pris par autre chose ⇒ refus du lot.

	`taille_fn(nom) -> (largeur, hauteur) | None` : injecté (Pillow côté CLI, table en test).
	Chaque doc porte `dimensions` ; la grille est posée ensuite par `poser_grille`."""
	ids = {d.get("_id") for d in docs}
	deja = images_citees(docs)
	cote = cote_case(docs, taille_fn)
	a_creer, refus, pris = [], [], set()
	for nom in sorted(noms_images):
		decoupe = decouper_nom(nom)
		if not decoupe or nom in deja:
			continue
		base, sous_categorie = decoupe
		taille = taille_fn(nom)
		if not taille:
			refus.append(f"{nom} : image illisible")
			continue
		# `lutecia` est déjà la capitale (sur paris_capital.png) : on retombe sur le nom
		# complet, pour un lieu distinct plutôt qu'un écrasement.
		slug = next((s for s in (slug_de(base), slug_de(os.path.splitext(nom)[0]))
			if f"lieu:{s}" not in ids and s not in pris), None)
		if slug is None:
			refus.append(f"{nom} : lieu:{slug_de(base)} et lieu:{slug_de(os.path.splitext(nom)[0])}"
				" déjà pris")
			continue
		pris.add(slug)
		doc = {
			"_id": f"lieu:{slug}",
			"type": "lieu",
			"label": LIBELLES.get(slug, slug.replace("_", " ").title()),
			"image": nom,
			"categorie": "ville",
			"sous_categorie": sous_categorie,
			"dimensions": {"x": max(1, round(taille[0] / cote)), "y": max(1, round(taille[1] / cote))},
			"tags": [],
		}
		if slug in VILLES_FRANCE and PAYS_FRANCE in ids:
			doc["lieu_parent"] = PAYS_FRANCE
		a_creer.append(doc)
	return a_creer, refus


def poser_grille(doc: dict, proposition: dict) -> dict:
	"""Le doc avec `cells` et `nav` de la proposition, dans l'ordre de clés de `lieu:rhemi`."""
	sortant = {}
	for cle, valeur in doc.items():
		sortant[cle] = valeur
		if cle == "dimensions":
			sortant["cells"] = proposition["cells"]
			sortant["nav"] = proposition["nav"]
	return sortant


def _taille_image(nom: str):
	from PIL import Image
	chemin = ggi.trouver_image(nom)
	if not chemin:
		return None
	try:
		with Image.open(chemin) as img:
			return img.size
	except OSError:
		return None


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = None
	if "--dump" in args:
		i = args.index("--dump")
		if i + 1 >= len(args):
			print("✗ --dump attend un chemin.")
			return 2
		chemin_dump = args[i + 1]
	docs = ggi.charger_dump(chemin_dump)
	if not docs:
		print("✗ aucun dump : passer --dump ou exporter un telluris-dump-*.json dans jsons/.")
		return 1

	noms = sorted(os.listdir(DOSSIER_VILLES))
	tailles = {}

	def taille_fn(nom):
		if nom not in tailles:
			tailles[nom] = _taille_image(nom)
		return tailles[nom]

	a_creer, refus = villes_a_creer(noms, docs, taille_fn)
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not a_creer:
		print("Toutes les cartes de ville de towns/ ont déjà leur lieu : rien à créer.")
		return 0
	print(f"{len(a_creer)} carte(s) de ville sans lieu · cases de "
		f"{cote_case(docs, taille_fn)} px\n")

	sortants = []
	for doc in a_creer:
		chemin = ggi.trouver_image(doc["image"])
		dim = doc["dimensions"]
		proposition = ggi.proposer_pour_image(chemin, dim["x"], dim["y"], doc)
		print(f"{doc['_id']} — {doc['label']} ({doc['sous_categorie']}"
			f"{', ' + doc['lieu_parent'] if doc.get('lieu_parent') else ''})")
		ggi.imprimer_resume(chemin, proposition)
		if "--sans-apercu" not in args:
			slug = doc["_id"].split(":", 1)[1]
			apercu = os.path.join(ggi.DOSSIER_JSONS, f"{slug}_grille_apercu.png")
			ggi.ecrire_apercu(chemin, proposition["cells"], apercu, proposition["nav"],
				proposition["rapport"])
			print(f"  ✎ {os.path.relpath(apercu, RACINE)}")
		print()
		sortants.append(poser_grille(doc, proposition))

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortants, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"✎ {os.path.relpath(SORTIE, RACINE)} — {len(sortants)} lieu(x) à importer")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
