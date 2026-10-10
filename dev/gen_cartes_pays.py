"""Un doc `lieu:*` de PAYS pour chaque carte de `maps/` qu'aucun lieu n'utilise, avec sa grille
proposée au profil `pays` (`utils/grille_image.proposer_pays`).

POURQUOI : une carte déposée dans `templates/resources/maps/` n'existe en jeu que quand un doc
`lieu:*` la cite par son champ `image`. Ce générateur crée ce doc — minimal, sur le modèle de
`lieu:france` — et lui pose la PREMIÈRE PASSE de murs : `cells` toutes à 1 (seuls les nav
bloquent), la côte seule murée (les fleuves ne bloquent rien).
Rien d'autre (ni zones d'influence, ni rencontres, ni ressources) : c'est du contenu à authorer.

LISTE BLANCHE (`CARTES`) : `maps/` mêle des cartes de pays, des vues de globe
(`world_globe*`), un hameau et des fortifications — ces derniers ne sont pas des pays.
`france.png` y est : déjà citée par `lieu:france`, elle est ignorée (sa grille est peinte à la
main et sert de référence au profil), mais un dump sans elle la recréerait.

REJOUABLE : une carte déjà citée par un lieu du dump est ignorée ; une fois le fichier importé
et le dump régénéré, le rejeu n'a plus rien à créer et N'ÉCRIT AUCUN FICHIER.

DIMENSIONS : des cases CARRÉES de la taille de celles des pays déjà en base — côté relu sur
le dump (`gen_villes_images.cote_case`, catégorie `pays`), jamais en dur.

Usage :
  python dev/gen_cartes_pays.py [--dump jsons/telluris-dump-….json] [--sans-apercu]
  (sans --dump : le dump le plus récent de jsons/)

Sortie : jsons/cartes_pays_a_importer.json (+ jsons/<slug>_grille_apercu.png par carte)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_villes_images import _taille_image, cote_case, images_citees, poser_grille  # noqa: E402

RACINE = ggi.RACINE
DOSSIER_CARTES = os.path.join(ggi.RESSOURCES, "maps")
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "cartes_pays_a_importer.json")
CATEGORIE = "pays"
PROFIL = "pays"

# Nom de fichier → (libellé, sous_categorie). Seules ces cartes deviennent des lieux.
CARTES = {
	"afrique_du_nord.png": ("Afrique du Nord", "region"),
	"angleterre.png": ("Angleterre", "pays"),
	"australie.png": ("Australie", "pays"),
	"egypte.png": ("Égypte", "pays"),
	"espagne.png": ("Espagne", "pays"),
	"europe.png": ("Europe", "continent"),
	"france.png": ("France", "pays"),
	"islande.png": ("Islande", "pays"),
	"italie.png": ("Italie", "pays"),
	"pannonie.jpg": ("Pannonie", "region"),
	"plaine_europeenne.jpg": ("Plaine européenne", "region"),
	"roumanie.png": ("Roumanie", "pays"),
	"world.png": ("Monde", "monde"),
}


def cartes_a_creer(noms_images, docs, taille_fn):
	"""(docs à créer SANS grille, refus). Un `_id` déjà pris par autre chose ⇒ refus du lot.

	`taille_fn(nom) -> (largeur, hauteur) | None` : injecté (Pillow côté CLI, table en test)."""
	ids = {d.get("_id") for d in docs}
	deja = images_citees(docs)
	cote = cote_case(docs, taille_fn, CATEGORIE)
	a_creer, refus = [], []
	for nom in sorted(noms_images):
		if nom not in CARTES or nom in deja:
			continue
		label, sous_categorie = CARTES[nom]
		taille = taille_fn(nom)
		if not taille:
			refus.append(f"{nom} : image illisible")
			continue
		_id = f"lieu:{os.path.splitext(nom)[0]}"
		if _id in ids:
			refus.append(f"{nom} : {_id} déjà pris (par une autre image)")
			continue
		a_creer.append({
			"_id": _id,
			"type": "lieu",
			"label": label,
			"image": nom,
			"categorie": CATEGORIE,
			"sous_categorie": sous_categorie,
			"dimensions": {"x": max(1, round(taille[0] / cote)), "y": max(1, round(taille[1] / cote))},
			"tags": [],
		})
	return a_creer, refus


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

	tailles = {}

	def taille_fn(nom):
		if nom not in tailles:
			tailles[nom] = _taille_image(nom)
		return tailles[nom]

	a_creer, refus = cartes_a_creer(sorted(os.listdir(DOSSIER_CARTES)), docs, taille_fn)
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not a_creer:
		print("Toutes les cartes de pays de maps/ ont déjà leur lieu : rien à créer.")
		return 0
	print(f"{len(a_creer)} carte(s) de pays sans lieu · cases de "
		f"{cote_case(docs, taille_fn, CATEGORIE)} px\n")

	sortants = []
	for doc in a_creer:
		chemin = ggi.trouver_image(doc["image"])
		dim = doc["dimensions"]
		proposition = ggi.proposer_pour_image(chemin, dim["x"], dim["y"], doc, profil=PROFIL)
		print(f"{doc['_id']} — {doc['label']} ({doc['sous_categorie']})")
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
