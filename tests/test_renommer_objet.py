"""POST /api/renommer_objet et /api/equip par exemplaire — le nom propre vit sur la RÉFÉRENCE.

Verrouille ce qui rendrait le renommage faux sans bruit : un nom posé sur le doc item (donc
chez tous les joueurs), un nom perdu en route (équiper/déséquiper/poser), la mauvaise épée
équipée quand deux exemplaires identiques ne diffèrent que par leur nom, et l'écriture du
doc du principal quand c'est un compagnon qui renomme.
"""

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers import user as user_router
from utils import characters

ITEMS = {
	"item:epee": {"_id": "item:epee", "type": "item", "nom": "Épée", "categorie": "arme",
				  "slots": ["main_droite"], "poids": 3},
	"item:pain": {"_id": "item:pain", "type": "item", "nom": "Pain", "slots": [], "poids": 0.5},
}


def _perso(_id="character:u_1", inventaire=None, slots=None):
	return {"_id": _id, "inventaire": list(inventaire or []),
			"slots": dict(slots or {}), "caracteristiques_current": {"F": 50}}


@pytest.fixture
def db(monkeypatch):
	ecrits = []
	monkeypatch.setattr(user_router, "get_doc", ITEMS.get)
	monkeypatch.setattr(characters, "get_doc", ITEMS.get)
	monkeypatch.setattr(user_router, "save_doc", lambda doc: ecrits.append(doc["_id"]) or doc)
	# Le payload complet (charge, canalisation…) est couvert ailleurs : ici, la ref seule compte.
	monkeypatch.setattr(user_router, "_inventory_payload", lambda c, p=None: {"ok": True})
	monkeypatch.setattr(user_router, "sync_equipment_bonus", lambda c: c.setdefault("equipment_bonus", {}))
	monkeypatch.setattr(user_router, "_derived_from_character",
						lambda c, eq: type("D", (), {"model_dump": lambda self: {}})())
	monkeypatch.setattr(user_router.consommables, "caracts_detail", lambda c: {})
	return ecrits


def _appel(monkeypatch, porteur, principal, fn, body):
	monkeypatch.setattr(user_router, "_acteur", lambda _u, _b: (porteur, principal))
	return asyncio.run(fn(None, body))


def test_renommer_au_sac_puis_le_nom_suit_equiper_desequiper_poser(db, monkeypatch):
	perso = _perso(inventaire=["item:epee"])
	_appel(monkeypatch, perso, perso, user_router.renommer_objet,
		   {"index": 0, "item_id": "item:epee", "nom": "Crocdeloup"})
	ref = perso["inventaire"][0]
	assert ref == {"item": "item:epee", "poids": 3.0, "nom_perso": "Crocdeloup"}
	assert "nom_perso" not in ITEMS["item:epee"]                  # jamais sur le doc partagé

	_appel(monkeypatch, perso, perso, user_router.equip_item,
		   {"item_id": "item:epee", "slot": "main_droite", "index": 0})
	assert perso["slots"]["main_droite"]["nom_perso"] == "Crocdeloup"
	_appel(monkeypatch, perso, perso, user_router.unequip_item, {"slot": "main_droite"})
	assert perso["inventaire"][0]["nom_perso"] == "Crocdeloup"
	_appel(monkeypatch, perso, perso, user_router.drop_item, {"index": 0, "item_id": "item:epee"})
	assert perso["objets_au_sol"][0]["nom_perso"] == "Crocdeloup"


def test_equiper_par_index_prend_le_bon_exemplaire(db, monkeypatch):
	anonyme = {"item": "item:epee", "poids": 3.0}
	baptisee = {"item": "item:epee", "poids": 3.0, "nom_perso": "Crocdeloup"}
	perso = _perso(inventaire=[anonyme, baptisee])
	_appel(monkeypatch, perso, perso, user_router.equip_item,
		   {"item_id": "item:epee", "slot": "main_droite", "index": 1})
	assert perso["slots"]["main_droite"] is baptisee
	assert perso["inventaire"] == [anonyme]


def test_renommer_un_objet_porte_et_retirer_le_nom(db, monkeypatch):
	perso = _perso(slots={"main_droite": "item:epee"})
	_appel(monkeypatch, perso, perso, user_router.renommer_objet,
		   {"slot": "main_droite", "item_id": "item:epee", "nom": "L'Aube"})
	assert perso["slots"]["main_droite"]["nom_perso"] == "L’Aube"
	_appel(monkeypatch, perso, perso, user_router.renommer_objet,
		   {"slot": "main_droite", "item_id": "item:epee", "nom": ""})
	assert "nom_perso" not in perso["slots"]["main_droite"]


def test_objet_non_equipable_et_nom_vide_de_sens_refuses(db, monkeypatch):
	perso = _perso(inventaire=["item:pain", "item:epee"])
	with pytest.raises(HTTPException) as err:
		_appel(monkeypatch, perso, perso, user_router.renommer_objet,
			   {"index": 0, "item_id": "item:pain", "nom": "Miche"})
	assert err.value.status_code == 422
	with pytest.raises(HTTPException) as err:
		_appel(monkeypatch, perso, perso, user_router.renommer_objet,
			   {"index": 1, "item_id": "item:epee", "nom": "<>;"})
	assert err.value.status_code == 422
	assert perso["inventaire"] == ["item:pain", "item:epee"]       # rien n'a bougé
	assert db == []


def test_compagnon_renomme_son_equipement_seul_son_doc_est_ecrit(db, monkeypatch):
	principal = _perso(inventaire=["item:epee"])
	compagnon = _perso(_id="aventurier:bran", slots={"main_droite": "item:epee"})
	_appel(monkeypatch, compagnon, principal, user_router.renommer_objet,
		   {"slot": "main_droite", "item_id": "item:epee", "nom": "Fidèle"})
	assert compagnon["slots"]["main_droite"]["nom_perso"] == "Fidèle"
	assert principal["inventaire"] == ["item:epee"]
	assert db == ["aventurier:bran"]
