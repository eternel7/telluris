"""Grimoires manquants (pur) : un grimoire UNIQUE + sa recette de scriptorium par sort.

Un sort ne s'apprend qu'avec un grimoire porté qui le cite (`sorts.grimoire_pour`), et un
grimoire n'arrive en rayon que si une recette le fait fabriquer — les scriptoriums tirent
leur production parmi les recettes de leur catégorie, aucun grimoire n'est approvisionné.

⚠️ **COUVERT = par un grimoire UNIQUE** (`sorts == [sort_id]`). Un sort que seul un grimoire
multiple cite reçoit quand même le sien : le multiple reste en base, intact, mais il ne
dispense pas du grimoire unitaire.

Partagé par `dev/gen_grimoires.py`, `dev/gen_sorts_invocation.py` et l'alerte de `/admin`
(`GET /admin/grimoires/manquants`) : la règle de couverture n'existe qu'ici.
Aucune DB : on reçoit les docs (dump ou projection `find_docs`), on rend des docs à importer.
"""

import json
from collections import Counter


def est_grimoire(doc) -> bool:
	return isinstance(doc, dict) and doc.get("type", "item") == "item" \
		and doc.get("sous_categorie") == "grimoire"


def rarete_grimoire(niveau: int) -> str:
	"""Paliers de rareté selon le niveau du sort enseigné (niveau 0 = celle des grimoires
	historiques, peu communs)."""
	if niveau <= 3:
		return "peu_commun"
	if niveau <= 6:
		return "rare"
	if niveau <= 9:
		return "tres_rare"
	return "legendaire"


def valeur_grimoire(niveau: int) -> list:
	"""Fourchette de prix (min, max) : 5-15 argent au niveau 0, 10n-30n argent au niveau n."""
	if niveau <= 0:
		return [{"ag": 5}, {"ag": 15}]
	return [{"ag": 10 * niveau}, {"ag": 30 * niveau}]


def matieres_grimoire(base: dict) -> list:
	"""Matières de la recette de grimoire la plus répandue en base — relues, jamais retapées.
	`ValueError` s'il n'y en a aucune : pas de modèle à reprendre."""
	signatures = Counter(
		json.dumps(d.get("matieres_premieres"), sort_keys=True, ensure_ascii=False)
		for d in base.values()
		if d.get("type") == "recette" and str(d.get("objet_final") or "").startswith("grimoire_")
		and d.get("matieres_premieres")
	)
	if not signatures:
		raise ValueError("aucune recette de grimoire en base — pas de modèle à reprendre")
	return json.loads(signatures.most_common(1)[0][0])


def grimoire_doc(sort: dict) -> dict:
	slug = sort["_id"][len("sort:"):]
	niveau = int(sort.get("niveau") or 0)
	nom = sort.get("nom") or slug
	# Un sort appartient à son ÉCOLE, jamais à une vocation. Sans `magie`, la phrase ne
	# nomme simplement aucune école.
	ecole = str(sort.get("magie") or "").strip()
	return {
		"_id": "item:grimoire_" + slug,
		"type": "item",
		"nom": "Grimoire : " + nom,
		"icon": "📖",
		"description": "Un grimoire relié qui enseigne le sort « %s »%s. Il n'est pas consumé par l'étude."
					   % (nom, ", de l'école " + ecole if ecole else ""),
		"rarete": rarete_grimoire(niveau),
		"categorie": "livre",
		"sous_categorie": "grimoire",
		"slots": [],
		"tags": ["grimoire"],
		"poids": 1,
		"sorts": [sort["_id"]],
		"valeur": valeur_grimoire(niveau),
	}


def recette_doc(sort: dict, matieres: list) -> dict:
	slug = sort["_id"][len("sort:"):]
	return {
		"_id": "recette:grimoire_" + slug,
		"type": "recette",
		"lieu_categorie": "scriptorium",
		"objet_final": "grimoire_" + slug,
		"quantite_produite": 1,
		"matieres_premieres": [dict(m) for m in matieres],
	}


def _couverts(grimoires) -> set:
	"""Sorts enseignés par un grimoire UNIQUE (`sorts` d'exactement un id)."""
	return {
		g["sorts"][0] for g in grimoires
		if est_grimoire(g) and isinstance(g.get("sorts"), list) and len(g["sorts"]) == 1
	}


def sorts_couverts_unitairement(base: dict) -> set:
	return _couverts(base.values())


def _cle_tri(sort: dict):
	return (str(sort.get("magie") or ""), int(sort.get("niveau") or 0), sort["_id"])


def sorts_sans_grimoire_unique(sorts, grimoires) -> list:
	"""Sorts sans grimoire unique, triés école → niveau → id. Accepte des docs projetés."""
	couverts = _couverts(grimoires)
	return sorted(
		(s for s in sorts if s.get("_id") and s["_id"] not in couverts),
		key=_cle_tri,
	)


def grimoires_sans_recette(base: dict) -> list:
	"""Grimoires en base qu'aucune recette ne produit — ils n'arrivent jamais en rayon."""
	produits = {str(d.get("objet_final") or "") for d in base.values() if d.get("type") == "recette"}
	return sorted(
		d["_id"] for d in base.values()
		if d.get("type") == "item" and est_grimoire(d) and d["_id"][len("item:"):] not in produits
	)


def grimoires_manquants(base: dict, sorts_en_plus=()) -> tuple:
	"""`(docs, lignes, erreurs)` : grimoires + recettes à importer pour chaque sort (en base
	ou `sorts_en_plus`, pas encore importés) sans grimoire UNIQUE.

	IDEMPOTENT : une recette qui produit déjà le grimoire n'est pas réémise. Un `_id` pris par
	AUTRE CHOSE est une erreur — l'import (PUT complet) l'écraserait ; l'appelant n'écrit rien."""
	sorts = [d for d in base.values() if d.get("type") == "sort"] + list(sorts_en_plus)
	manquants = sorts_sans_grimoire_unique(sorts, base.values())
	docs, lignes, erreurs = [], [], []
	if not manquants:
		return docs, lignes, erreurs
	try:
		matieres = matieres_grimoire(base)
	except ValueError as err:
		return docs, lignes, [str(err)]
	for sort in manquants:
		grimoire = grimoire_doc(sort)
		recette = recette_doc(sort, matieres)
		existant = base.get(grimoire["_id"])
		if existant is not None:
			# Il existe mais n'est pas le grimoire unique de ce sort (sinon il serait couvert).
			if sort["_id"] in (existant.get("sorts") or []):
				erreurs.append("%s existe déjà et enseigne %s parmi d'autres sorts — l'écraser les perdrait"
							   % (grimoire["_id"], sort["_id"]))
			else:
				erreurs.append("%s existe déjà et n'enseigne pas %s" % (grimoire["_id"], sort["_id"]))
			continue
		docs.append(grimoire)
		etat_recette = "neuve"
		existante = base.get(recette["_id"])
		if existante is not None:
			if existante.get("objet_final") == recette["objet_final"]:
				etat_recette = "déjà en base"
			else:
				erreurs.append("%s existe déjà et ne produit pas %s" % (recette["_id"], grimoire["_id"]))
				continue
		else:
			docs.append(recette)
		lignes.append("%-44s niv %2d  %-10s %s-%s ag  recette %s" % (
			grimoire["_id"], int(sort.get("niveau") or 0), grimoire["rarete"],
			grimoire["valeur"][0]["ag"], grimoire["valeur"][1]["ag"], etat_recette))
	return docs, lignes, erreurs
