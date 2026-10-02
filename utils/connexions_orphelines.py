"""Connexions orphelines (pur) : un doc `type: connection` dont au moins un nœud ne mène à
aucun lieu existant.

Source unique de la règle, partagée par le nettoyeur `dev/purge_connexions_orphelines.py`
et la colonne calculée `node_inexistant` de `/admin/table` (type `connection`).

Un nœud est INEXISTANT quand il n'est pas un objet, qu'il ne porte pas de `lieu`, ou que
son `lieu` n'est l'`_id` d'aucun doc en base. ⚠️ L'ensemble des `_id` existants est
INJECTÉ : l'appelant le lit (Mango `$in` sur `lieux_cites`), ce module ne touche pas la
base. Un appelant qui n'a pas pu le lire ne doit RIEN conclure — un ensemble vide ferait
de toutes les connexions des orphelines.
"""


def _lieu(noeud):
	"""`lieu` d'un nœud, ou None s'il n'en porte pas (nœud mal formé compris)."""
	if not isinstance(noeud, dict):
		return None
	lieu = noeud.get("lieu")
	return lieu if isinstance(lieu, str) and lieu else None


def lieux_cites(connexions) -> list:
	"""Les `_id` de lieux cités par les nœuds, sans doublon, triés (requête déterministe)."""
	return sorted({lieu for c in (connexions or []) for lieu in
		(_lieu(n) for n in ((c or {}).get("nodes") or [])) if lieu})


def noeuds_inexistants(connexion, existants) -> list:
	"""Les nœuds de `connexion` qui ne mènent nulle part, sous la forme `(index, lieu)` —
	`lieu` vaut None pour un nœud sans lieu. Liste vide = connexion saine."""
	manquants = []
	for i, noeud in enumerate((connexion or {}).get("nodes") or []):
		lieu = _lieu(noeud)
		if lieu is None or lieu not in existants:
			manquants.append((i, lieu))
	return manquants


def orphelines(connexions, existants) -> list:
	"""`[(connexion, noeuds_inexistants)]` des seules connexions orphelines, dans l'ordre reçu."""
	sortie = []
	for c in connexions or []:
		manquants = noeuds_inexistants(c, existants)
		if manquants:
			sortie.append((c, manquants))
	return sortie
