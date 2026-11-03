"""POST /api/renommer_personnage — prénom et nom du personnage SÉLECTIONNÉ.

Même règle qu'à la création (`IDENTITE_MAX`, `auberge.nettoyer_ligne`) : borné sans échapper
(Convention §9), vide refusé (422), rien d'écrit en cas de refus.
"""

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers import user as user_router


@pytest.fixture
def perso(monkeypatch):
	doc = {"_id": "character:u_1", "prenom": "Aldric", "nom": "Valmont"}
	ecrits = []
	monkeypatch.setattr(user_router, "get_selected_character", lambda _u: doc)
	monkeypatch.setattr(user_router, "save_doc", lambda d: ecrits.append(dict(d)) or d)
	doc["_ecrits"] = ecrits
	return doc


def _appel(body):
	return asyncio.run(user_router.renommer_personnage(None, body))


def test_renomme_et_nettoie(perso):
	rep = _appel({"prenom": "  Élise\t", "nom": "de  Bruges "})
	assert rep == {"prenom": "Élise", "nom": "de Bruges"}
	assert (perso["prenom"], perso["nom"]) == ("Élise", "de Bruges")
	assert len(perso["_ecrits"]) == 1


def test_borne_a_identite_max(perso):
	rep = _appel({"prenom": "A" * 100, "nom": "B"})
	assert rep["prenom"] == "A" * user_router.IDENTITE_MAX


def test_n_echappe_pas_le_html(perso):
	# On BORNE au serveur, on ÉCHAPPE au rendu : échapper ici doublerait l'échappement.
	assert _appel({"prenom": "<b>&'", "nom": "X"})["prenom"] == "<b>&'"


@pytest.mark.parametrize("body", [{"prenom": "", "nom": "X"}, {"prenom": "X", "nom": "  "},
								  {"prenom": "X"}, {}])
def test_vide_refuse_sans_ecrire(perso, body):
	with pytest.raises(HTTPException) as e:
		_appel(body)
	assert e.value.status_code == 422
	assert (perso["prenom"], perso["nom"]) == ("Aldric", "Valmont")
	assert perso["_ecrits"] == []


def test_sans_personnage_404(monkeypatch):
	monkeypatch.setattr(user_router, "get_selected_character", lambda _u: None)
	with pytest.raises(HTTPException) as e:
		_appel({"prenom": "A", "nom": "B"})
	assert e.value.status_code == 404
