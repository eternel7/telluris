"""Purge ONE-SHOT des docs `quete:*` GÉNÉRÉS déjà acceptés — du poids mort en base.

Quand le joueur accepte une quête, son personnage en garde un SNAPSHOT complet
(`quetes.snapshot_quete`) : le doc `quete:*` n'est plus relu par personne (`accepte_par`
était écrit sans jamais être lu, et le seul lecteur — `routers/quetes.quetes_accepter` —
exige `statut == "offerte"`). Ces docs s'accumulaient donc à raison d'un par acceptation,
et `quetes.offres_du_giver` les rapatriait TOUS à chaque ouverture du tableau : 112 docs
morts pour 6 vivants sur la base de référence. C'est ce qui rendait le tableau de plus en
plus lent avec le temps.

`routers/quetes.quetes_accepter` supprime désormais le doc à l'acceptation : ce script ne
sert qu'à solder l'arriéré, UNE FOIS.

⚠️ Seules les quêtes `source == "genere"` sont supprimées. Une quête AUTHORÉE est une
mission ÉCRITE : même acceptée, elle doit rester en base pour pouvoir être remise au
tableau à la main.

À lancer DANS LE CONTENEUR (CouchDB n'est pas joignable depuis le poste de dev) :

	docker compose exec web python dev/purge_quetes_acceptees.py            # aperçu seul
	docker compose exec web python dev/purge_quetes_acceptees.py --appliquer
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.config import find_docs, delete_doc  # noqa: E402


# Le terminal Windows n'est pas toujours en UTF-8 (même repli que dev/lint_dialogues.py).
def ecrire(ligne: str) -> None:
	try:
		print(ligne)
	except UnicodeEncodeError:
		print(ligne.encode("ascii", "replace").decode("ascii"))


def main() -> int:
	appliquer = "--appliquer" in sys.argv
	docs = find_docs({"type": "quete", "statut": "acceptee", "source": "genere"})
	if docs is None:
		ecrire("CouchDB injoignable (find_docs a échoué). À lancer dans le conteneur.")
		return 1
	if not docs:
		ecrire("Rien à purger : aucune quête générée acceptée en base.")
		return 0

	par_giver: dict[str, int] = {}
	for d in docs:
		cle = d.get("giver") or "(sans donneur)"
		par_giver[cle] = par_giver.get(cle, 0) + 1
	ecrire(f"{len(docs)} quête(s) générée(s) acceptée(s) à supprimer :")
	for giver, n in sorted(par_giver.items(), key=lambda kv: -kv[1]):
		ecrire(f"   {n:5d}  {giver}")

	if not appliquer:
		ecrire("\nAperçu seulement — relancez avec --appliquer pour supprimer.")
		return 0

	# `delete_doc` renvoie None en succès COMME en échec (cf. db/config) : on ne peut pas
	# compter les échecs, seulement les tentatives. Une suppression ratée sera simplement
	# retentée au prochain passage du script.
	for d in docs:
		delete_doc(d)
	ecrire(f"\n{len(docs)} document(s) supprimé(s).")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
