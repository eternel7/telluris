"""Trésor du dernier étage des catacombes de Lutecia (`lieu:catacombes0003`) : le coffre de
l'ossuaire, au fond de l'alcôve sud-ouest, et le cristal de mana jaune qu'on y trouve —
« cristaux jaunes trouvés au fond des catacombes » (Auteur, 11/10).

    python dev/gen_tresor_catacombes.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/tresor_catacombes_a_importer.json   (carte d'import de /admin)

Deux docs :
  · `donjon:catacombes_de_lutecia`, RELU dans le dump (PUT complet) : seul le bloc `tresor`
    de l'entrée `lieu:catacombes0003` est posé (utils/tresor.py) ;
  · `item:cristal_de_mana_jaune`, neuf (refus si l'id existe déjà sous une autre forme).

Idempotent : un doc déjà à jour n'est pas réécrit ; si les deux le sont, aucun fichier.
"""

import argparse
import copy
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_recettes_orphelins import dernier_dump  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "tresor_catacombes_a_importer.json")
DONJON_ID = "donjon:catacombes_de_lutecia"
ETAGE_ID = "lieu:catacombes0003"
CRISTAL_ID = "item:cristal_de_mana_jaune"

CRISTAL = {
	"_id": CRISTAL_ID,
	"type": "item",
	"nom": "Cristal de mana jaune",
	"icon": "💛",
	"description": "Éclat de mana couleur de miel, tiède au creux de la main. Les Architectes "
				   "disent qu'il tient un seuil ouvert quand le portail voudrait se refermer ; "
				   "aucun n'explique pourquoi on le trouve au fond des catacombes, et pas "
				   "ailleurs.",
	"categorie": "composant",
	"sous_categorie": "cristal",
	"rarete": "tres_rare",
	"slots": [],
	"poids": 0.1,
}

# Case (5, 35) : l'alcôve au bout de la galerie sud-ouest, la plus éloignée de l'arrivée
# (33, 3). Grade de l'étage : 3-4 (`niveau_*` de la salle) — piège de danger 2, renforts
# moins nombreux que la garnison (5).
TRESOR = {
	"nom": "Coffre de l'ossuaire",
	"icon": "🧰",
	"pos": [5, 35],
	"garanti": [{"item": CRISTAL_ID, "quantite": 1}],
	"bourse": [40, 120],
	"tirage": {"nb": 2, "table": [
		{"item": "item:gemmes", "poids": 3},
		{"item": "item:anneau", "poids": 3},
		{"item": "item:bague", "poids": 2},
		{"item": "item:Cristal_canalisation", "poids": 2},
	]},
	"piege": {"chance": 40, "danger": 2, "effets": ["degats", "alarme"], "alarme": 3},
}


def maj_donjon(doc: dict) -> dict:
	out = copy.deepcopy(doc)
	entree = next(e for e in out["battle_maps"] if e.get("lieu") == ETAGE_ID)
	entree["tresor"] = copy.deepcopy(TRESOR)
	return out


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser()
	ap.add_argument("--dump", default=None)
	args = ap.parse_args()
	chemin = args.dump or dernier_dump()
	print("source : %s" % os.path.relpath(chemin, RACINE))
	index = {d["_id"]: d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			 if isinstance(d, dict) and d.get("_id")}

	erreurs, lot = [], []
	for item in (t["item"] for t in TRESOR["tirage"]["table"]):
		if item not in index:
			erreurs.append("%s : absent du dump" % item)
	donjon = index.get(DONJON_ID)
	if donjon is None:
		erreurs.append("%s : absent du dump" % DONJON_ID)
	else:
		try:
			neuf = maj_donjon(donjon)
		except (KeyError, StopIteration) as e:
			erreurs.append("%s : structure inattendue (%s)" % (DONJON_ID, e))
		else:
			if neuf != donjon:
				neuf.pop("_rev", None)   # réattaché depuis la base par l'import
				lot.append(neuf)
	existant = index.get(CRISTAL_ID)
	if existant is None:
		lot.append(copy.deepcopy(CRISTAL))
	elif {k: v for k, v in existant.items() if k != "_rev"} != CRISTAL:
		erreurs.append("%s : déjà en base sous une autre forme — collision d'_id" % CRISTAL_ID)
	if erreurs:
		print("\n".join("ERREUR " + e for e in erreurs))
		sys.exit(1)
	if not lot:
		print("base à jour : aucun fichier écrit")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(lot, f, ensure_ascii=False, indent=2)
	print("%d doc(s) → %s" % (len(lot), os.path.relpath(SORTIE, RACINE)))


if __name__ == "__main__":
	main()
