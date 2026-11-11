# tests/test_vocation_niveau.py
#
# Plafond du niveau de vocation : `POST /api/spend_xp_vocation` (routers/user.py).
#
# Bug d'origine : la fiche de /play masquait le bouton « Monter » à 5 (`_vocNiveau < 5` codé
# en dur dans `_refreshStatBoxes`), vestige de l'ancien maximum, alors que le serveur montait
# sans aucune limite. Le plafond est désormais la variable de monde `VOC_NIVEAU_MAX` (10),
# appliquée par le serveur et relue par le client.
#
# Base en mémoire (même câblage que tests/test_apprendre_sort.py) ; `_fiche_payload` est
# remplacé par une sentinelle : on vérifie que le bloc part, pas son contenu.

import asyncio

import pytest
from fastapi import HTTPException

from models import character_stats


def _perso(niveau, points):
	return {
		"_id": "aventurier:alienor", "type": "aventurier", "prenom": "Aliénor",
		"voc": "moine", "vocations_niveaux": {"moine": niveau},
		"attribute_points": points,
	}


@pytest.fixture
def monter(monkeypatch):
	"""`appeler(character)` exécute `spend_xp_vocation` sur ce porteur et rend sa réponse."""
	from routers import user as user_router

	docs = {}
	monkeypatch.setattr(user_router, "save_doc", lambda doc: docs.__setitem__(doc["_id"], doc) or doc)
	monkeypatch.setattr(user_router, "_fiche_payload", lambda character: {"id": character["_id"]})

	def appeler(character):
		monkeypatch.setattr(user_router, "_acteur", lambda _u, _b: (character, character))
		return asyncio.run(user_router.spend_xp_vocation(object(), {}))

	return appeler


def _cout(niveau):
	return (niveau + 1) * character_stats.XP_VOC_COEFF


def test_monte_jusquau_plafond(monter):
	n = character_stats.VOC_NIVEAU_MAX - 1
	perso = _perso(n, _cout(n))
	rep = monter(perso)
	assert rep["voc_niveau"] == character_stats.VOC_NIVEAU_MAX
	assert rep["voc_niveau_max"] == character_stats.VOC_NIVEAU_MAX
	assert rep["attribute_points"] == 0
	assert perso["vocations_niveaux"]["moine"] == character_stats.VOC_NIVEAU_MAX
	# Le nouveau niveau débloque des capacités : la fiche se resynchronise (§10).
	assert rep["fiche"] == {"id": perso["_id"]}


def test_au_plafond_refuse_sans_rien_depenser(monter):
	n = character_stats.VOC_NIVEAU_MAX
	perso = _perso(n, 10_000)
	with pytest.raises(HTTPException) as exc:
		monter(perso)
	assert exc.value.status_code == 422
	assert perso["attribute_points"] == 10_000
	assert perso["vocations_niveaux"]["moine"] == n


def test_plafond_lu_dans_la_variable_de_monde(monter, monkeypatch):
	# L'ancien maximum codé en dur (5) ne bloque plus ; le plafond suit la variable de monde.
	monkeypatch.setattr(character_stats, "VOC_NIVEAU_MAX", 6)
	assert monter(_perso(5, _cout(5)))["voc_niveau"] == 6
	with pytest.raises(HTTPException):
		monter(_perso(6, 10_000))


def test_cout_suivant_suit_le_coefficient(monter, monkeypatch):
	# `xp_cout_next` portait un 5 en dur au lieu de XP_VOC_COEFF.
	monkeypatch.setattr(character_stats, "XP_VOC_COEFF", 7)
	rep = monter(_perso(2, 3 * 7))
	assert rep["xp_cout_next"] == 4 * 7
