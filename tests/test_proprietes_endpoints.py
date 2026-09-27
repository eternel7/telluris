"""Endpoints des propriétés (`routers/proprietes.py`) et leurs points d'intégration.

Ce que la logique pure ne voit pas :
1. **L'achat crée DEUX docs** — la propriété et sa connexion depuis la case d'achat — et
   n'est offert que sur une zone habitable du bon type.
2. **Céder supprime la porte et reconduit dehors** : on ne reste pas dans un lieu sans porte.
3. **Le vol** passe par `retirer` ; un gardien au poste le bloque.
4. **La nuit chez soi est gratuite** et emprunte le flux de l'auberge (`_acces_nuit`).
5. **Louer deux fois la même chambre la prolonge** au lieu d'en créer une seconde.

Base en mémoire, gabarit de `tests/test_auberge_endpoints.py`.
"""

import asyncio
import json
import os

import pytest

from fastapi import HTTPException

from utils import characters as characters_util
from utils import proprietes


with open(os.path.join(os.path.dirname(__file__), "..", "jsons", "proprietes_a_importer.json"),
		  encoding="utf-8") as _f:
	CATALOGUE_DOCS = json.load(_f)["docs"]

VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "label": "Ville",
		 "zone_influences": [{"x": 5, "y": 5, "w": 4, "h": 4, "rot": 0, "forme": "rectangle",
							  "zone": "zone:habitable_maison"}]}
AUBERGE = {"_id": "lieu:auberge", "type": "lieu", "categorie": "auberge", "label": "Auberge",
		   "lieu_parent": "lieu:ville"}
CARACTS = {"V": 5, "F": 40, "R": 40, "Ag": 40, "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40}


def _perso(**champs):
	base = {
		"_id": "character:a", "type": "character", "lieu": "lieu:ville",
		"position": {"x": 5, "y": 5}, "prenom": "Greta", "nom": "Hazgard", "cite": "lieu:ville",
		"inventaire": [], "slots": {}, "groupe": [], "montures": [],
		"caracteristiques_current": dict(CARACTS), "currentPV": 1, "currentPM": 0,
		"or": 100, "argent": 0, "cuivre": 0,
	}
	base.update(champs)
	return base


@pytest.fixture
def monde(monkeypatch):
	from routers import proprietes as rp
	from routers import auberge as ra
	from utils import auberge

	docs = {d["_id"]: json.loads(json.dumps(d)) for d in [*CATALOGUE_DOCS, VILLE, AUBERGE]}
	supprimes = []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def delete_doc_fn(doc):
		docs.pop(doc.get("_id"), None)
		supprimes.append(doc.get("_id"))
		return doc

	def find_docs_fn(selector, fields=None):
		return [d for d in list(docs.values())
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	for mod in (rp, ra, auberge, characters_util, proprietes):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
		monkeypatch.setattr(mod, "delete_doc", delete_doc_fn, raising=False)
	return {"docs": docs, "supprimes": supprimes, "rp": rp, "ra": ra}


def _appel(monde, character, coro_fn, *args, module="rp"):
	mod = monde[module]
	monde["docs"][character["_id"]] = character
	origine = mod.get_selected_character
	try:
		mod.get_selected_character = lambda _u: character
		return asyncio.run(coro_fn(*args))
	finally:
		mod.get_selected_character = origine


def _cat(monde):
	return proprietes.catalogue(monde["docs"].get)


def _acheter_maison(monde, char):
	return _appel(monde, char, monde["rp"].acheter, None, {"type": "maison"})


# ── Achat ─────────────────────────────────────────────────────────────────────────

def test_offre_dans_la_zone(monde):
	data = _appel(monde, _perso(), monde["rp"].offre, None)
	assert [t["id"] for t in data["types"]] == ["maison"]
	assert data["location"] is None


def test_offre_refusee_hors_zone(monde):
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso(position={"x": 40, "y": 40}), monde["rp"].offre, None)
	assert e.value.status_code == 403


def test_achat_cree_propriete_et_connexion(monde):
	char = _perso()
	avant = characters_util.money_to_cuivre(char)
	data = _acheter_maison(monde, char)
	prop = monde["docs"][data["achetee"]["id"]]
	lien = monde["docs"][prop["lien"]]
	assert prop["type_propriete"] == "maison" and prop["statut"] == proprietes.POSSEDEE
	assert lien["nodes"][0] == {"lieu": "lieu:ville", "pos": [5, 5]}
	prix = proprietes.type_def(_cat(monde), "maison")["prix_cuivre"]
	assert characters_util.money_to_cuivre(char) == avant - prix
	assert char["proprietes"] == [prop["_id"]]


def test_achat_d_un_autre_type_refuse(monde):
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso(), monde["rp"].acheter, None, {"type": "demeure"})
	assert e.value.status_code == 403


def test_achat_sans_fonds_ne_cree_rien(monde):
	char = _perso(**{"or": 0})
	n = len(monde["docs"])
	with pytest.raises(HTTPException) as e:
		_acheter_maison(monde, char)
	assert e.value.status_code == 409
	assert len(monde["docs"]) == n + 1       # seul le personnage a été posé par `_appel`


# ── Dans la propriété ─────────────────────────────────────────────────────────────

def _entrer(monde, char):
	pid = _acheter_maison(monde, char)["achetee"]["id"]
	char["lieu"] = pid
	char["position"] = {"x": 0, "y": 0}
	return monde["docs"][pid]


def test_installer_debite_et_resynchronise(monde):
	char = _perso()
	prop = _entrer(monde, char)
	data = _appel(monde, char, monde["rp"].installer, None, {"amenagement": "cave"})
	assert "cave" in prop["amenagements"]
	assert [a["id"] for a in data["installes"]] == ["cave"]
	assert "cave" not in [a["id"] for a in data["disponibles"]]
	with pytest.raises(HTTPException):
		_appel(monde, char, monde["rp"].installer, None, {"amenagement": "ecurie_limitee"})


def test_vol_puis_gardien(monde):
	proprio = _perso()
	prop = _entrer(monde, proprio)
	prop["coffre"] = [{"item": "item:a", "poids": 1}, {"item": "item:b", "poids": 1}]
	voleur = _perso(_id="character:b", lieu=prop["_id"])
	data = _appel(monde, voleur, monde["rp"].retirer, None, {"idx": 0, "item_id": "item:a"})
	assert data["vol"] is True and voleur["inventaire"] == [{"item": "item:a", "poids": 1}]

	_appel(monde, proprio, monde["rp"].installer, None, {"amenagement": "loge_gardien"})
	_appel(monde, proprio, monde["rp"].engager, None,
		   {"metier": "gardien", "amenagement": "loge_gardien"})
	with pytest.raises(HTTPException) as e:
		_appel(monde, voleur, monde["rp"].retirer, None, {"idx": 0, "item_id": "item:b"})
	assert e.value.status_code == 403
	vue = _appel(monde, voleur, monde["rp"].ici, None)
	assert vue["role"] == "visiteur" and vue["gardien"] is True and vue["coffre"] == []


def test_visiteur_ne_gere_pas(monde):
	prop = _entrer(monde, _perso())
	voleur = _perso(_id="character:b", lieu=prop["_id"])
	with pytest.raises(HTTPException) as e:
		_appel(monde, voleur, monde["rp"].installer, None, {"amenagement": "cave"})
	assert e.value.status_code == 403


def test_vendre_supprime_la_porte_et_reconduit_dehors(monde):
	char = _perso()
	prop = _entrer(monde, char)
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "cave"})
	avant = characters_util.money_to_cuivre(char)
	data = _appel(monde, char, monde["rp"].vendre, None)
	tdef = proprietes.type_def(_cat(monde), "maison")
	assert data["gain"] == proprietes.prix_revente(tdef)
	assert characters_util.money_to_cuivre(char) == avant + data["gain"]
	assert prop["lien"] in monde["supprimes"]
	assert prop["amenagements"] == ["cave"] and prop["statut"] == proprietes.VENDUE
	assert char["lieu"] == "lieu:ville" and char["position"] == {"x": 5, "y": 5}
	assert char["proprietes"] == []


def test_deposer_renvoie_le_sac(monde):
	char = _perso(inventaire=[{"item": "item:a", "poids": 2}])
	prop = _entrer(monde, char)
	data = _appel(monde, char, monde["rp"].deposer, None, {"idx": 0, "item_id": "item:a"})
	assert prop["coffre"] == [{"item": "item:a", "poids": 2}]
	assert "inventaire_payload" in data and data["capacites"]["stockage_utilise"] == 2


# ── Location ──────────────────────────────────────────────────────────────────────

def test_louer_puis_prolonger_la_meme_chambre(monde):
	char = _perso(lieu="lieu:auberge", position={"x": 0, "y": 0})
	d1 = _appel(monde, char, monde["rp"].louer, None)
	d2 = _appel(monde, char, monde["rp"].louer, None)
	assert d1["louee"]["id"] == d2["louee"]["id"]
	duree = proprietes.location_de(proprietes.type_def(_cat(monde), "chambre"))["duree_s"]
	assert d2["louee"]["expire_at"] - d1["louee"]["expire_at"] == duree
	chambres = [d for d in monde["docs"].values() if d.get("type") == "propriete"]
	assert len(chambres) == 1 and chambres[0]["mode"] == proprietes.MODE_LOCATION


def test_chambre_louee_refuse_un_intrus(monde):
	char = _perso(lieu="lieu:auberge", position={"x": 0, "y": 0})
	pid = _appel(monde, char, monde["rp"].louer, None)["louee"]["id"]
	intrus = _perso(_id="character:b", lieu=pid)
	with pytest.raises(HTTPException) as e:
		_appel(monde, intrus, monde["rp"].ici, None)
	assert e.value.status_code == 403


# ── La nuit chez soi ──────────────────────────────────────────────────────────────

def test_nuit_gratuite_chez_soi(monde):
	char = _perso()
	_entrer(monde, char)
	avant = characters_util.money_to_cuivre(char)
	data = _appel(monde, char, monde["ra"].passer_la_nuit, None, module="ra")
	assert data["cout"] == 0 and characters_util.money_to_cuivre(char) == avant


def test_nuit_refusee_chez_autrui(monde):
	prop = _entrer(monde, _perso())
	intrus = _perso(_id="character:b", lieu=prop["_id"])
	with pytest.raises(HTTPException) as e:
		_appel(monde, intrus, monde["ra"].passer_la_nuit, None, module="ra")
	assert e.value.status_code == 403
