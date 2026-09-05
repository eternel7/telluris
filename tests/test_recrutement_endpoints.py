"""Endpoints du recrutement (`routers/recrutement.py`) — le CONTRAT D'UNE MISSION.

Ce que le module pur ne peut pas couvrir, et qui est exactement ce qui se casse en
silence : la SÉQUENCE des gardes de l'embauche payante (contrôle AVANT la dépense, bourse
intacte sur refus), le 403 hors guilde, et le cycle complet de la reprise.

Base en mémoire, patron de `tests/test_quetes_endpoints.py` : `get_doc`/`save_doc`/
`find_docs` patchés sur le router ET sur les utils qu'il traverse, `get_selected_character`
stubbé, endpoints `async` appelés par `asyncio.run`.
"""

import asyncio

import pytest
from fastapi import HTTPException

from models import character_stats
from utils import recrutement
from utils import characters as characters_util
from utils import combat as combat_util
from utils import montures as montures_util
from utils import escorte as escorte_util
from utils.characters import money_to_cuivre


GUILDE = {"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier",
		  "sous_categorie": "guilde_aventurier", "lieu_parent": "lieu:ville",
		  "tags": ["recrutement"]}
# Lieu qui RECRUTE sans être une guilde (tag seul) : c'est lui qui doit refuser le contrat
# d'une mission — le tableau y est bien affiché, mais ce contrat-là se signe à la guilde.
CASERNE = {"_id": "lieu:caserne", "type": "lieu", "categorie": "caserne",
		   "lieu_parent": "lieu:ville", "tags": ["recrutement"]}
VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "sous_categorie": "ville"}
RACES = {
	"_id": "rules:races", "type": "rules",
	"value": [{
		"id": "humain", "label": "Humain",
		"stats": {"V": 5, "F": 20, "R": 20, "Ag": 20, "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20},
		"stats_max": {"V": 8, "F": 50, "R": 50, "Ag": 60, "Vol": 70, "Int": 70, "Cha": 80, "Ch": 60},
	}],
}
VOCATIONS = {
	"_id": "rules:vocations", "type": "rules",
	"value": [{"id": "guerrier", "label": "Guerrier", "equipement_de_base": []}],
}


def _perso(**champs):
	base = {
		"_id": "character:u_1", "type": "character", "user_id": "user:u",
		"prenom": "Test", "nom": "Héros", "lieu": "lieu:guilde",
		"inventaire": [], "slots": {}, "groupe": [], "montures": [], "proteges": [],
		"affinites": {}, "compagnons_connus": {}, "quetes_actives": [],
		"caracteristiques_current": {"V": 5, "F": 20, "R": 20, "Ag": 20,
									 "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20},
		"or": 0, "argent": 0, "cuivre": 1000,
	}
	base.update(champs)
	return base


def _recrue(rid="aventurier:guilde_abc", statut="offert", **champs):
	base = {
		"_id": rid, "type": "aventurier", "statut": statut, "giver": "lieu:guilde",
		"prenom": "Aldric", "nom": "Ferrant", "sex": "M", "race": "humain",
		"voc": "guerrier", "image": "", "rang": "F", "specialite": "Éclaireur",
		"caracteristiques_current": {"V": 5, "F": 20, "R": 20, "Ag": 20,
									 "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20},
		"currentPV": 80, "currentPM": 120, "inventaire": [], "slots": {},
		"vocations_niveaux": {"guerrier": 0}, "xp_total": 0, "attribute_points": 0,
		"exigences": {"part_butin_pct": 20, "clauses": []},
		"or": 0, "argent": 0, "cuivre": 0,
		"genere_at": 1000, "expire_at": 4_000_000_000,
	}
	base.update(champs)
	return base


@pytest.fixture
def monde(monkeypatch):
	from routers import recrutement as rr

	docs = {d["_id"]: d for d in (GUILDE, CASERNE, VILLE, RACES, VOCATIONS)}
	saves = []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		saves.append(doc["_id"])
		return doc

	def delete_doc_fn(doc):
		docs.pop(doc.get("_id"), None)
		return None

	def find_docs_fn(selector, fields=None):
		return [d for d in docs.values()
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	for mod in (rr, recrutement, characters_util, combat_util, montures_util, escorte_util):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
		monkeypatch.setattr(mod, "delete_doc", delete_doc_fn, raising=False)
	monkeypatch.setattr(recrutement, "now_epoch", lambda: 1000)
	# La carte d'aventurier a son propre test (module pur) : elle n'a rien à voir avec le
	# mode de contrat, et l'exiger ici n'éprouverait qu'un garde déjà couvert.
	monkeypatch.setattr(character_stats, "RECRUTEMENT_CARTE_REQUISE", False)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_GROUPE_TAILLE_MAX", 2)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_COUT_CUIVRE", 300)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_COUT_PAR_NIVEAU", 200)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_PART_FACTEUR", 0.5)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_PART_MIN", 0)
	return {"docs": docs, "saves": saves, "rr": rr}


def _appel(monde, character, coro_fn, body):
	"""Exécute un endpoint avec `character` comme personnage sélectionné."""
	rr = monde["rr"]
	monde["docs"][character["_id"]] = character
	origine = rr.get_selected_character
	try:
		rr.get_selected_character = lambda _u: character
		return asyncio.run(coro_fn(None, body))
	finally:
		rr.get_selected_character = origine


def _embaucher(monde, character, av_id, mode=None):
	body = {"aventurier_id": av_id}
	if mode:
		body["mode"] = mode
	return _appel(monde, character, monde["rr"].recrutement_embaucher, body)


def _reprendre(monde, character, av_id):
	return _appel(monde, character, monde["rr"].recrutement_reprendre,
				  {"aventurier_id": av_id})


# ── Embauche pour une mission ────────────────────────────────────────────────────

def test_embauche_de_mission_debite_et_estampille(monde):
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a")
	c = _perso(cuivre=1000)

	payload = _embaucher(monde, c, "aventurier:a", "mission")

	av = monde["docs"]["aventurier:a"]
	assert av["contrat"]["mode"] == "mission" and av["contrat"]["cout_cuivre"] == 300
	assert av["contrat"]["giver"] == "lieu:guilde"
	# ⚠️ La bourse est NORMALISÉE par `cuivre_to_purse` (700 cu = 7 argent) : on la relit
	# en cuivre, jamais champ à champ.
	assert money_to_cuivre(monde["docs"]["character:u_1"]) == 700
	assert payload["embauche"] == {"nom": "Aldric Ferrant", "mission": True, "cout": 300}
	# La part réduite voyage par `exigences_effectives.mode` — source unique du client.
	vue = next(g for g in payload["groupe"] if g["id"] == "aventurier:a")
	assert vue["exigences_effectives"] == {"part_butin_pct": 10, "mode": "mission", "clauses": []}


def test_embauche_ordinaire_inchangee_a_la_lettre(monde):
	"""`mode` absent ⇒ comportement d'avant : gratuit, aucun bloc `contrat`."""
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a")
	c = _perso(cuivre=1000)

	payload = _embaucher(monde, c, "aventurier:a")

	assert "contrat" not in monde["docs"]["aventurier:a"]
	assert money_to_cuivre(monde["docs"]["character:u_1"]) == 1000
	assert payload["embauche"]["mission"] is False


def test_embauche_de_mission_refusee_hors_guilde(monde):
	"""Le tableau s'affiche (tag `recrutement`), mais ce contrat-là se signe à la guilde."""
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a", giver="lieu:caserne")
	c = _perso(cuivre=1000, lieu="lieu:caserne")

	with pytest.raises(HTTPException) as exc:
		_embaucher(monde, c, "aventurier:a", "mission")

	assert exc.value.status_code == 403
	assert money_to_cuivre(monde["docs"]["character:u_1"]) == 1000   # rien débité


def test_embauche_de_mission_409_sans_fonds_et_bourse_intacte(monde):
	"""⚠️ Tout ou rien : un refus de paiement ne laisse ni bourse entamée, ni doc sauvé."""
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a")
	c = _perso(cuivre=100)

	with pytest.raises(HTTPException) as exc:
		_embaucher(monde, c, "aventurier:a", "mission")

	assert exc.value.status_code == 409 and "Fonds" in exc.value.detail
	assert money_to_cuivre(c) == 100 and c["groupe"] == []
	assert monde["docs"]["aventurier:a"]["statut"] == "offert"


def test_embauche_de_mission_groupe_complet_refuse_AVANT_le_debit(monde, monkeypatch):
	"""L'ordre des gardes est la seule chose que ce test protège : contrôle métier PUIS
	dépense. Inversés, un groupe complet coûterait le prix du contrat pour rien."""
	monkeypatch.setattr(character_stats, "RECRUTEMENT_GROUPE_TAILLE_MAX", 0)
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a")
	c = _perso(cuivre=1000)

	with pytest.raises(HTTPException) as exc:
		_embaucher(monde, c, "aventurier:a", "mission")

	assert exc.value.status_code == 409 and "complet" in exc.value.detail
	assert money_to_cuivre(c) == 1000


def test_le_tableau_offre_les_termes_dans_une_guilde_seulement(monde):
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a")
	c = _perso()

	payload = _appel(monde, c, monde["rr"].recrutement_board, None) \
		if False else asyncio.run(_board(monde, c))

	assert payload["lieu_de_guilde"] is True
	offerte = next(r for r in payload["recrues"] if r["id"] == "aventurier:a")
	assert offerte["mission"] == {"cout_cuivre": 300, "part_butin_pct": 10}


def test_le_tableau_d_un_lieu_non_guilde_n_offre_aucun_contrat_de_mission(monde):
	monde["docs"]["aventurier:b"] = _recrue("aventurier:b", giver="lieu:caserne")
	c = _perso(lieu="lieu:caserne")

	payload = asyncio.run(_board(monde, c))

	assert payload["lieu_de_guilde"] is False
	assert all("mission" not in r for r in payload["recrues"])


async def _board(monde, character):
	rr = monde["rr"]
	monde["docs"][character["_id"]] = character
	origine = rr.get_selected_character
	try:
		rr.get_selected_character = lambda _u: character
		return await rr.recrutement_board(None)
	finally:
		rr.get_selected_character = origine


# ── Reprise ──────────────────────────────────────────────────────────────────────

def _echu(monde, c, av_id="aventurier:a"):
	"""Un compagnon dont le contrat d'une mission vient d'échoir à la guilde."""
	monde["docs"][av_id] = _recrue(av_id)
	_embaucher(monde, c, av_id, "mission")
	av = monde["docs"][av_id]
	recrutement.cloturer_contrats_mission(c, GUILDE, compagnons=[av])
	return av


def test_reprendre_debite_et_rattache(monde):
	c = _perso(cuivre=1000)
	av = _echu(monde, c)
	assert c["groupe"] == [] and av["statut"] == "parti"

	payload = _reprendre(monde, c, av["_id"])

	assert monde["docs"][av["_id"]]["statut"] == "embauche"
	assert c["groupe"] == [av["_id"]]
	assert money_to_cuivre(c) == 400               # 1000 − 300 (embauche) − 300 (reprise)
	assert payload["reprise"] == {"nom": "Aldric Ferrant", "cout": 300}
	assert "echu_at" not in monde["docs"][av["_id"]]["contrat"]


def test_reprendre_refuse_hors_guilde(monde):
	c = _perso(cuivre=1000)
	av = _echu(monde, c)
	c["lieu"] = "lieu:caserne"

	with pytest.raises(HTTPException) as exc:
		_reprendre(monde, c, av["_id"])

	assert exc.value.status_code == 403
	assert money_to_cuivre(c) == 700 and c["groupe"] == []   # rien débité, rien rattaché


def test_reprendre_refuse_un_contrat_ordinaire(monde):
	c = _perso(cuivre=1000)
	monde["docs"]["aventurier:o"] = _recrue("aventurier:o")
	_embaucher(monde, c, "aventurier:o")
	av = monde["docs"]["aventurier:o"]
	recrutement.congedier(c, av, GUILDE)

	with pytest.raises(HTTPException) as exc:
		_reprendre(monde, c, "aventurier:o")

	assert exc.value.status_code == 409 and "mission" in exc.value.detail


def test_reprendre_409_sans_fonds_et_bourse_intacte(monde):
	c = _perso(cuivre=350)
	av = _echu(monde, c)                # coûte 300 : il reste 50

	with pytest.raises(HTTPException) as exc:
		_reprendre(monde, c, av["_id"])

	assert exc.value.status_code == 409 and "Fonds" in exc.value.detail
	assert money_to_cuivre(c) == 50 and c["groupe"] == []
	assert monde["docs"][av["_id"]]["statut"] == "parti"


def test_reprendre_404_sur_un_doc_inconnu(monde):
	c = _perso()
	with pytest.raises(HTTPException) as exc:
		_reprendre(monde, c, "aventurier:fantome")
	assert exc.value.status_code == 404


# ── Rupture ──────────────────────────────────────────────────────────────────────

def test_congedier_a_la_guilde_est_sans_frais_et_le_dit(monde):
	c = _perso(cuivre=1000)
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a")
	_embaucher(monde, c, "aventurier:a", "mission")
	c["affinites"]["aventurier:a"] = 55

	payload = _appel(monde, c, monde["rr"].recrutement_congedier,
					 {"aventurier_id": "aventurier:a"})

	assert payload["congedie"] == {"nom": "Aldric Ferrant", "sans_frais": True}
	assert c["affinites"]["aventurier:a"] == 55


def test_congedier_ailleurs_coute_et_ne_le_pretend_pas(monde):
	c = _perso(cuivre=1000)
	monde["docs"]["aventurier:a"] = _recrue("aventurier:a")
	_embaucher(monde, c, "aventurier:a", "mission")
	c["affinites"]["aventurier:a"] = 55
	c["lieu"] = "lieu:caserne"

	payload = _appel(monde, c, monde["rr"].recrutement_congedier,
					 {"aventurier_id": "aventurier:a"})

	assert payload["congedie"]["sans_frais"] is False
	assert c["affinites"]["aventurier:a"] == 55 + character_stats.AFFINITE_DELTA_CONGEDIE
