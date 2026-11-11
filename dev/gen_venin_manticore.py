"""Venin de manticore (demande du 11/11) : un seul fichier pour les DEUX docs qui changent.

    python dev/gen_venin_manticore.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/venin_manticore_a_importer.json   (carte d'import de /admin)

  · `item:manticore_queue` : bloc `fabrication` et `rarete` relus dans la table de
    dev/gen_fabrication_matieres.py (palier 4 par dérogation, poison 5 × 5) ;
  · `item:Fouet_dard_de_manticore` : pièce reconstruite par dev/gen_trophees.py (socle Fouet +
    apport, palier de la ligne, `valeur` de la variante sur mesure — calculée avec la queue À
    JOUR, dont la rareté entre dans le prix).

Pourquoi un script : gen_trophees refuse un `_id` déjà pris par un doc différent (il ne crée que
des pièces neuves), et le fichier de gen_fabrication_matieres porterait un autre lot. Les deux
docs partent DU DUMP (PUT complet, CLAUDE.md §11) : seules les clés recalculées changent.
Base à jour ⇒ aucun fichier. Garde-fous de gen_trophees (budget du palier, effets bien dirigés)
rejoués ; rien n'est écrit en cas d'erreur.
"""

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_recettes_orphelins import brancher_moteur, dernier_dump  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "venin_manticore_a_importer.json")
QUEUE = "item:manticore_queue"
FOUET = "Fouet_dard_de_manticore"


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


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
	docs = [d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")]
	index = {d["_id"]: d for d in docs}

	marche = brancher_moteur(docs)
	import gen_fabrication_matieres as gfm
	import gen_trophees as gt
	from utils import commande, fabrication

	erreurs = gfm.erreurs_de_budget({QUEUE: gfm.MATIERES[QUEUE]})
	erreurs += gfm.effets_mal_diriges({QUEUE: gfm.MATIERES[QUEUE]})

	# ── La queue, d'abord : le prix du Fouet-dard en dépend ──
	queue = gfm.a_ecrire_depuis(gfm.MATIERES[QUEUE], index[QUEUE])
	queue_jeu = queue or _sans_rev(index[QUEUE])
	docs[docs.index(index[QUEUE])] = queue_jeu
	marche.reset_prix_cache()

	# ── Le Fouet-dard, reconstruit comme gen_trophees le ferait ──
	p = gt.PIECES[FOUET]
	socle = index[p["socle"]]
	palier = gt.palier_piece(FOUET, index.get(queue_jeu["source_espece"]))
	piece = gt.item_doc(FOUET, socle, gfm.PALIERS[palier]["rarete"])
	erreurs += gt.erreurs_de_budget(FOUET, socle, piece, palier)
	matieres = [(queue_jeu, 1)] + [(index[marche.matiere_item_id(c)], q) for c, q in p["intrants"]]
	piece["valeur"] = gt.valeur_piece(marche, commande, fabrication, socle, matieres,
									  gfm.PALIERS[palier]["valeur"])
	existant = index["item:" + FOUET]
	fouet = dict(_sans_rev(existant), **piece)
	# Clés du socle retirées de l'apport (ex. le débuff R −3) : la pièce reconstruite fait foi.
	for cle in set(existant) - set(piece) - {"_rev"}:
		if cle in gt.CHAMPS_PROPRES or cle in socle or cle == "effets":
			fouet.pop(cle, None)
	fouet = None if fouet == _sans_rev(existant) else fouet

	if erreurs:
		print("\n%d ERREUR(S) — rien n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("  ✗ " + e)
		sys.exit(1)

	lot = [d for d in (queue, fouet) if d]
	for d in lot:
		print("  %-32s rarete %-10s effets/fabrication %s" % (
			d["_id"], d.get("rarete"),
			json.dumps(d.get("effets") or d.get("fabrication"), ensure_ascii=False)))
	if fouet:
		print("  valeur du Fouet-dard : %s (avant %s)" % (fouet["valeur"], existant.get("valeur")))
	if not lot:
		print("Base à jour — aucun fichier écrit.")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(lot, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print("→ %s (%d doc(s))" % (os.path.relpath(SORTIE, RACINE), len(lot)))


if __name__ == "__main__":
	main()
