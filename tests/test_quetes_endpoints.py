"""Endpoints du tableau de quêtes (`routers/quetes.py`) — coût et cycle de vie des docs.

Deux choses s'y jouent, que rien d'autre ne couvre :

1. **Le doc `quete:*` d'une offre GÉNÉRÉE meurt à l'acceptation** — le personnage en garde
   un snapshot, plus personne ne le relit. Le laisser en base faisait grossir sans borne ce
   que `offres_du_giver` rapatrie à chaque ouverture du tableau. ⚠️ Une quête AUTHORÉE, elle,
   n'est jamais supprimée.
2. **`_board_payload` ne détaille chaque quête qu'UNE fois** : `actives` est un filtre de
   `fiche_actives`, pas une seconde passe de `quete_detail` (qui relit, par quête de chasse,
   le doc `lieu:*` complet — le plus gros du jeu).

Base en mémoire, comme `tests/test_apprendre_sort.py`.
"""

import asyncio

import pytest

from utils import quetes


GUILDE = {"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier",
          "lieu_parent": "lieu:ville"}
AUTRE_GUILDE = {"_id": "lieu:guilde2", "type": "lieu", "categorie": "guilde_aventurier",
                "lieu_parent": "lieu:ville"}
VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "rencontres": []}
LOUP = {"_id": "espece:loup", "type": "espece", "nom": "Loup"}
# Un lieu de chasse AVEC grille : c'est ce doc que `quete_detail` relit par quête de chasse.
FORET = {
	"_id": "lieu:foret", "type": "lieu", "categorie": "map", "label": "Forêt",
	"dimensions": {"x": 20, "y": 20},
}


def _offre(oid, source="genere", statut="offerte", giver="lieu:guilde"):
	return {
		"_id": oid, "type": "quete", "source": source, "statut": statut, "giver": giver,
		"titre": oid, "rang": "F", "description": "",
		"objectif": {"type": "kill", "cible": "espece:loup", "quantite": 3},
		"recompenses": {"xp": 10, "cuivre": 30},
		# Sans horodatage, `offre_perimee` la déclare périmée d'office (repli documenté).
		"genere_at": 1_000, "expire_at": 4_000_000_000,
	}


def _chasse_active(qid, lieu="lieu:foret", giver="lieu:guilde"):
	"""Snapshot d'une quête de chasse active — le type qui fait relire un doc `lieu:*`."""
	return {
		"id": qid, "titre": qid, "giver": giver, "rang": "F", "description": "",
		"objectif": {"type": "chasse", "cible": "espece:loup", "lieu": lieu,
					 "profil": "profil:x", "quantite": 1},
		"progress": 0, "recompenses": {"xp": 50, "cuivre": 100},
	}


def _perso(**champs):
	base = {
		"_id": "character:u_1", "type": "character", "lieu": "lieu:guilde",
		"inventaire": [], "quetes_actives": [], "quetes_terminees": [],
		"or": 0, "argent": 0, "cuivre": 0, "groupe": [],
	}
	base.update(champs)
	return base


@pytest.fixture
def monde(monkeypatch):
	"""`routers/quetes` et `utils/quetes` câblés sur une base en mémoire.
	Renvoie {docs, supprimes, lectures} — `lectures` compte les `get_doc` par id."""
	from routers import quetes as rq

	docs = {d["_id"]: d for d in (GUILDE, AUTRE_GUILDE, VILLE, LOUP, FORET)}
	supprimes, lectures = [], {}

	def get_doc_fn(doc_id):
		lectures[doc_id] = lectures.get(doc_id, 0) + 1
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def delete_doc_fn(doc):
		docs.pop(doc.get("_id"), None)
		supprimes.append(doc)
		return None

	def find_docs_fn(selector, fields=None):
		return [d for d in docs.values()
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	for mod in (rq, quetes):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
		monkeypatch.setattr(mod, "delete_doc", delete_doc_fn, raising=False)
	return {"docs": docs, "supprimes": supprimes, "lectures": lectures, "rq": rq}


def _accepter(monde, character, quete_id):
	rq = monde["rq"]
	monde["docs"][character["_id"]] = character
	rq_get_selected = rq.get_selected_character
	try:
		rq.get_selected_character = lambda _u: character
		return asyncio.run(rq.quetes_accepter(None, {"quete_id": quete_id}))
	finally:
		rq.get_selected_character = rq_get_selected


# ── Cycle de vie du doc d'offre ──────────────────────────────────────────────────

def test_accepter_supprime_le_doc_dune_offre_generee(monde):
	"""Le personnage en garde un snapshot : le doc n'est plus lu par personne, et 112 docs
	morts pour 6 vivants était ce qui ralentissait le tableau avec le temps."""
	monde["docs"]["quete:g1"] = _offre("quete:g1")
	char = _perso()

	_accepter(monde, char, "quete:g1")

	assert [d["_id"] for d in monde["supprimes"]] == ["quete:g1"]
	assert "quete:g1" not in monde["docs"]
	assert [q["id"] for q in char["quetes_actives"]] == ["quete:g1"]   # le snapshot, lui, est là


def test_accepter_une_quete_authoree_ne_supprime_rien(monde):
	"""Une mission ÉCRITE doit pouvoir être remise au tableau à la main."""
	monde["docs"]["quete:borin"] = _offre("quete:borin", source="authoree")
	char = _perso()

	_accepter(monde, char, "quete:borin")

	assert monde["supprimes"] == []
	assert monde["docs"]["quete:borin"]["statut"] == "acceptee"
	assert monde["docs"]["quete:borin"]["accepte_par"] == char["_id"]


def test_accepter_deux_fois_est_refuse(monde):
	"""La garde qui compte reste `quete_active` (409), pas le statut du doc supprimé."""
	monde["docs"]["quete:g1"] = _offre("quete:g1")
	char = _perso()
	_accepter(monde, char, "quete:g1")

	from fastapi import HTTPException
	with pytest.raises(HTTPException) as exc:
		_accepter(monde, char, "quete:g1")
	assert exc.value.status_code == 404      # le doc a disparu ; la quête reste dans le perso


# ── Payload du tableau ───────────────────────────────────────────────────────────

def test_board_payload_ne_detaille_chaque_quete_quune_fois(monde):
	"""`actives` est un FILTRE de `fiche_actives` — deux quêtes de chasse dans le même lieu
	ne doivent relire le doc `lieu:*` (le plus gros du jeu) qu'UNE seule fois."""
	rq = monde["rq"]
	char = _perso(quetes_actives=[
		_chasse_active("q1"), _chasse_active("q2"),
		_chasse_active("q3", giver="lieu:guilde2"),   # quête d'une AUTRE guilde
	])

	payload = rq._board_payload(char, GUILDE)

	assert [d["id"] for d in payload["fiche_actives"]] == ["q1", "q2", "q3"]
	assert [d["id"] for d in payload["actives"]] == ["q1", "q2"]   # filtré sur le donneur
	assert all(d in payload["fiche_actives"] for d in payload["actives"])
	assert monde["lectures"]["lieu:foret"] == 1   # ⚠️ mémoïsé : 3 chasses, 1 lecture


def test_board_payload_ne_genere_rien_sans_completer(monde):
	"""terminer / déposer / abandonner ne libèrent aucune place : ils listent, c'est tout."""
	rq = monde["rq"]
	monde["docs"]["quete:g1"] = _offre("quete:g1")
	avant = set(monde["docs"])

	payload = rq._board_payload(_perso(), GUILDE)

	assert [o["id"] for o in payload["offres"]] == ["quete:g1"]
	assert set(monde["docs"]) == avant            # aucun doc `quete:*` créé
