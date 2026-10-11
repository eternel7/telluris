"""La France et ses voisins : UN fichier à importer pour la plaine européenne, Bruges,
Aix-la-Chapelle, l'Espagne, l'Italie, Rome, la Pannonie, la Roumanie, Bucarest et leurs connexions.

Assemble `gen_france_espagne_italie.construire`, `gen_plaine_europeenne.construire` et
`gen_pannonie.construire` (le détail des règles y est). Règle commune : le territoire du voisin que montre une carte est
mis à 0, la connexion se pose SUR la frontière ; on ne change de carte que par elle.

ÉMIS = ce qui DIFFÈRE DU DUMP (`_rev` ignoré) : un lieu absent est créé avec sa grille
proposée, un lieu présent est relu et ne reçoit que la frontière / le parent ; une connexion
identique en base n'est pas réémise. Rejeu sur un dump à jour ⇒ AUCUN fichier.
⚠️ Import = PUT COMPLET (CLAUDE.md §11) : `lieu:france` et `lieu:italie` (peintes à la main),
`lieu:espagne`, `lieu:roumanie`, `lieu:rome` et `lieu:bucarest` partent ENTIERS depuis le dump —
dump frais exigé.

Usage :
  python dev/gen_voisins_france.py [--dump jsons/telluris-dump-….json] [--sans-apercu]

Sortie : jsons/voisins_france_a_importer.json (+ jsons/<slug>_grille_apercu.png par lieu émis)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_france_espagne_italie as sud  # noqa: E402
from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_pannonie as pannonie  # noqa: E402
from dev import gen_plaine_europeenne as plaine  # noqa: E402
from dev.gen_villes_images import _taille_image  # noqa: E402
from utils import grille_image  # noqa: E402

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "voisins_france_a_importer.json")


def a_emettre(docs, sortants):
	"""(émis, refus) : les docs qui diffèrent du dump ; un `_id` produit deux fois ⇒ refus."""
	par_id = {d.get("_id"): plaine.sans_rev(d) for d in docs}
	vus, emis, refus = set(), [], []
	for doc in sortants:
		if doc["_id"] in vus:
			refus.append(f"{doc['_id']} : produit deux fois")
			continue
		vus.add(doc["_id"])
		if par_id.get(doc["_id"]) != doc:
			emis.append(doc)
	return emis, refus


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

	def proposer(doc, profil=""):
		dim = doc["dimensions"]
		return ggi.proposer_pour_image(ggi.trouver_image(doc["image"]), dim["x"], dim["y"], doc,
			options={"--nav-vide"}, profil=profil)

	def eau(doc):
		dim = doc["dimensions"]
		couleurs, _, _ = ggi.echantillonner(ggi.trouver_image(doc["image"]), dim["x"], dim["y"])
		return grille_image.masque_eau(couleurs, dim["x"], dim["y"], grille_image.regles_de("pays"))

	lieux_sud, liens_sud, refus, avert = sud.construire(docs, lambda d: proposer(d, "pays"))
	france = next((d for d in lieux_sud if d["_id"] == plaine.FRANCE), None)
	lieux_pl, liens_pl, refus_pl, propositions, avert_pl = ([], [], [], {}, []) if refus else \
		plaine.construire(docs, _taille_image, proposer, france)
	refus += refus_pl
	italie = next((d for d in lieux_sud if d["_id"] == pannonie.ITALIE), None)
	lieux_pa, liens_pa, refus_pa, prop_pa, avert_pa = ([], [], [], {}, []) if refus else \
		pannonie.construire(docs, _taille_image, proposer, eau, italie)
	refus += refus_pa
	propositions.update(prop_pa)
	for a in avert + avert_pl + avert_pa:
		print(f"⚠ {a}")
	emis, r = a_emettre(docs, lieux_sud + lieux_pl + lieux_pa + liens_sud + liens_pl + liens_pa)
	refus += r
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not emis:
		print("Tout est déjà en base : rien à écrire.")
		return 0

	for doc in emis:
		if doc.get("type") == "connection":
			a, b = doc["nodes"]
			print(f"  🔗 {doc['_id']} : {a['lieu']} {a['pos']} ↔ {b['lieu']} {b['pos']}")
			continue
		neuf = doc["_id"] in propositions
		print(f"  {'✚' if neuf else '✎'} {doc['_id']} — {doc.get('label')}"
			f"{' · parent ' + doc['lieu_parent'] if doc.get('lieu_parent') else ''}")
		chemin = ggi.trouver_image(doc["image"])
		if neuf:
			ggi.imprimer_resume(chemin, propositions[doc["_id"]])
		if "--sans-apercu" not in args and doc.get("cells"):
			slug = doc["_id"].split(":", 1)[1]
			apercu = os.path.join(ggi.DOSSIER_JSONS, f"{slug}_grille_apercu.png")
			rapport = propositions[doc["_id"]]["rapport"] if neuf else None
			ggi.ecrire_apercu(chemin, doc["cells"], apercu, doc.get("nav"), rapport)
			print(f"    aperçu : {os.path.relpath(apercu, RACINE)}")

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	n_liens = sum(1 for d in emis if d.get("type") == "connection")
	print(f"\n✎ {os.path.relpath(SORTIE, RACINE)} — {len(emis) - n_liens} lieu(x), {n_liens} connexion(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
