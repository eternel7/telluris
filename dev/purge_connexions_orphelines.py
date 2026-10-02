"""Nettoyeur des connexions ORPHELINES : docs `type: connection` dont au moins un nœud ne
mène à aucun lieu existant (lieu supprimé, `_id` mal saisi, nœud sans `lieu`).

Une telle connexion n'a plus de sens : un de ses bouts ne se charge pas. La règle vit dans
`utils/connexions_orphelines.py`, partagée avec la colonne `node_inexistant` de
`/admin/table`.

⚠️ Fail-closed : si l'existence des lieux ne peut pas être lue, le script s'arrête sans
rien supprimer — un ensemble vide ferait de TOUTES les connexions des orphelines.

À lancer DANS LE CONTENEUR (CouchDB n'est pas joignable depuis le poste de dev), ou depuis
/admin/dev-tools :

	docker compose exec web python dev/purge_connexions_orphelines.py            # aperçu seul
	docker compose exec web python dev/purge_connexions_orphelines.py --appliquer
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.config import find_docs, delete_doc  # noqa: E402
from utils import connexions_orphelines as co  # noqa: E402


# Le terminal Windows n'est pas toujours en UTF-8 (même repli que dev/lint_dialogues.py).
def ecrire(ligne: str) -> None:
	try:
		print(ligne)
	except UnicodeEncodeError:
		print(ligne.encode("ascii", "replace").decode("ascii"))


def main() -> int:
	appliquer = "--appliquer" in sys.argv
	connexions = find_docs({"type": "connection"})
	if connexions is None:
		ecrire("CouchDB injoignable (find_docs a échoué). À lancer dans le conteneur.")
		return 1
	cites = co.lieux_cites(connexions)
	trouves = find_docs({"_id": {"$in": cites}}, fields=["_id"]) if cites else []
	if trouves is None:
		ecrire("Existence des lieux illisible (find_docs a échoué) : rien n'est supprimé.")
		return 1
	existants = {d["_id"] for d in trouves if d.get("_id")}

	liste = co.orphelines(connexions, existants)
	ecrire(f"{len(connexions)} connexion(s) lue(s), {len(cites)} lieu(x) cité(s), "
		f"{len(cites) - len(existants)} introuvable(s).")
	if not liste:
		ecrire("Rien à nettoyer : aucune connexion orpheline.")
		return 0

	ecrire(f"\n{len(liste)} connexion(s) orpheline(s) :")
	for c, manquants in liste:
		trous = ", ".join(f"nœud {i} → {lieu or '(sans lieu)'}" for i, lieu in manquants)
		ecrire(f"   {c.get('_id')}  [{trous}]")

	if not appliquer:
		ecrire("\nAperçu seulement — relancez avec --appliquer pour supprimer.")
		return 0

	# `delete_doc` renvoie None en succès COMME en échec (cf. db/config) : on ne peut compter
	# que les tentatives. Une suppression ratée réapparaîtra au prochain aperçu.
	for c, _ in liste:
		delete_doc(c)
	ecrire(f"\n{len(liste)} document(s) supprimé(s).")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
