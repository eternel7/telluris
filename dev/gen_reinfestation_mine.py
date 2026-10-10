"""Ré-infestation de la mine aux cristaux d'Auxerre : la salle n'est libérée que jusqu'à la
PROCHAINE commission acceptée (`donjon.donjon_reinfeste`), et le templier qui la garde le dit.

    python dev/gen_reinfestation_mine.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/reinfestation_mine_a_importer.json   (carte d'import de /admin)

Deux docs, RELUS dans le dump (PUT complet : on n'y injecte que ce qui change) :
  · `lieu:la_mine_aux_cristaux` ← `reinfestation: true` ;
  · `pnj:templier_armand_de_vaucremont_01` ← le choix « mineurs » réservé à la PREMIÈRE
    infestation (`acces_reinfeste: false`), un choix jumeau et son nœud `mineurs_remontes`
    (« ça remonte ») quand une nouvelle commission reprend la salle ; et le refus « Pourquoi
    cette arche est-elle fermée ? » dédoublé de même (`acces_refus_libre`, mine libérée).

Idempotent : un doc déjà à jour n'est pas réécrit ; si les deux le sont, aucun fichier.
⚠️ `dev/gen_acces_donjon.py` (figé sur un dump de juillet) ne connaît pas ces ajouts : le
rejouer les déferait — relancer celui-ci après lui.
"""

import argparse
import copy
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_recettes_orphelins import dernier_dump  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "reinfestation_mine_a_importer.json")
MINE_ID = "lieu:la_mine_aux_cristaux"
ARMAND_ID = "pnj:templier_armand_de_vaucremont_01"

LABEL_MINEURS = "« Et ces mineurs qui attendent ? »"
CHOIX_REMONTES = {
	"id": "mineurs_remontes",
	"label": LABEL_MINEURS,
	"condition": {"acces_reinfeste": True},
	"next": "mineurs_remontes",
}
NOEUD_REMONTES = {
	"texte": "Les lampes sont de nouveau éteintes. Les mineurs piétinent au fond de la nef, "
			 "certains encore gris de la poussière des galeries. {pnj} tourne le registre vers "
			 "vous : les deux colonnes ont la même longueur. « Vingt-deux descendus, vingt-deux "
			 "remontés — mais pas au pas. Ils ont entendu gratter dans les galeries basses et "
			 "ils ont tout laissé là-dessous, les pics avec. » Il referme le registre du plat de "
			 "la main. « Ça remonte. Les uns disent que le portail recrache ce qu'on y tue, les "
			 "autres qu'il en vient d'ailleurs. Moi, je compte. Le chantier attend de nouveau des "
			 "aventuriers. »",
	"choix": [{"id": "revenir", "label": "Revenir.", "next": "accueil"}],
}


# « Pourquoi cette arche est-elle fermée ? » : la réponse d'origine (« ne rouvriront qu'une fois
# l'éradication confirmée ») ne vaut que si la mine est MENACÉE ; mine libérée, son jumeau.
LABEL_POURQUOI = "« Pourquoi cette arche est-elle fermée ? »"
CHOIX_POURQUOI_LIBRE = {
	"id": "pourquoi_libre",
	"label": LABEL_POURQUOI,
	"condition": {"acces_refuse": True, "acces_libere": True},
	"next": "acces_refus_libre",
}
NOEUD_REFUS_LIBRE = {
	"texte": "« Fermée ? Pas pour tout le monde. » {pnj} désigne du menton la file des mineurs "
			 "qui passe sous l'arche, lampes allumées. « Les galeries sont rendues à ceux qui les "
			 "creusent. Ceux-là ont leur jeton de compagnie, et je les compte à l'aller comme au "
			 "retour. Un aventurier qui descend sans mandat, c'est une ligne de plus dans la "
			 "colonne de gauche et rien de sûr dans celle de droite. » Il trempe sa plume. « Si "
			 "la Guilde vous renvoie là-dessous, {prenom}, c'est que ça remonte. Ce jour-là, je "
			 "vous ouvrirai. »",
	"choix": [{"id": "revenir", "label": "Revenir.", "next": "accueil"}],
}


def maj_mine(doc: dict) -> dict:
	out = copy.deepcopy(doc)
	out["reinfestation"] = True
	return out


def maj_armand(doc: dict) -> dict:
	"""Le choix « mineurs » d'origine ne vaut plus qu'à la première infestation ; son jumeau
	`mineurs_remontes` est inséré juste après lui. Sans toucher au reste de l'arbre."""
	out = copy.deepcopy(doc)
	noeuds = out["dialogue"]["noeuds"]
	accueil = noeuds["accueil"]["choix"]
	idx = next(i for i, c in enumerate(accueil) if c.get("id") == "mineurs")
	accueil[idx]["condition"] = {"acces_menace": True, "acces_reinfeste": False}
	if not any(c.get("id") == CHOIX_REMONTES["id"] for c in accueil):
		accueil.insert(idx + 1, copy.deepcopy(CHOIX_REMONTES))
	noeuds.setdefault("mineurs_remontes", copy.deepcopy(NOEUD_REMONTES))
	idx = next(i for i, c in enumerate(accueil) if c.get("id") == "pourquoi")
	accueil[idx]["condition"] = {"acces_refuse": True, "acces_libere": False}
	if not any(c.get("id") == CHOIX_POURQUOI_LIBRE["id"] for c in accueil):
		accueil.insert(idx + 1, copy.deepcopy(CHOIX_POURQUOI_LIBRE))
	noeuds.setdefault("acces_refus_libre", copy.deepcopy(NOEUD_REFUS_LIBRE))
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
	for doc_id, maj in ((MINE_ID, maj_mine), (ARMAND_ID, maj_armand)):
		existant = index.get(doc_id)
		if existant is None:
			erreurs.append("%s : absent du dump" % doc_id)
			continue
		try:
			neuf = maj(existant)
		except (KeyError, StopIteration) as e:
			erreurs.append("%s : structure inattendue (%s)" % (doc_id, e))
			continue
		if neuf != existant:
			neuf.pop("_rev", None)   # réattaché depuis la base par l'import
			lot.append(neuf)
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
