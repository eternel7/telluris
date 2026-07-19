# tests/test_cible_allie_exploration.py
#
# Ciblage allié HORS combat : `_cible_alliee` (qui reçoit l'effet) et `_save_cast` (qui
# persiste jusqu'à trois docs). Le reste de la chaîne — empiler_effet_sort, clamp aux max,
# débit des PM — est déjà couvert par les tests purs des sorts et des consommables.
#
# ⚠️ Le piège central de cette feature est l'IDENTITÉ des dicts : lanceur, cible et
# principal peuvent désigner le même document. Deux dicts d'un même doc = deux `save_doc`
# sur le même `_rev`, donc une écriture perdue en silence.

import pytest

from fastapi import HTTPException

from routers import user as user_mod


# ── Fixtures ─────────────────────────────────────────────────────────────────────

def _doc(_id, nom):
	return {"_id": _id, "nom": nom, "currentPV": 20, "currentPM": 10, "effets_actifs": []}


@pytest.fixture
def groupe(monkeypatch):
	"""Principal + un compagnon + une monture, tous rendus par porteurs_effectifs."""
	principal = _doc("character:moi", "Frida")
	compagnon = _doc("aventurier:borin", "Borin")
	monture = _doc("monture:mule", "Mule")
	# ⚠️ porteurs_effectifs RELIT la base : on rend des COPIES, comme le vrai helper, pour
	# que le test attrape un éventuel retour de dict dupliqué.
	monkeypatch.setattr(user_mod.recrutement, "porteurs_effectifs",
						lambda principal_doc, get_doc: [dict(compagnon), dict(monture)])
	return principal, compagnon, monture


# ── Résolution de la cible ───────────────────────────────────────────────────────

def test_le_principal_est_une_cible_valide(groupe):
	principal, _c, _m = groupe
	cible = user_mod._cible_alliee(principal, principal, {"cible_id": "character:moi"})
	assert cible is principal        # le dict déjà en main, pas une relecture


def test_un_compagnon_est_une_cible_valide(groupe):
	principal, compagnon, _m = groupe
	cible = user_mod._cible_alliee(principal, principal, {"cible_id": compagnon["_id"]})
	assert cible["_id"] == "aventurier:borin"


def test_une_monture_est_une_cible_valide(groupe):
	principal, _c, monture = groupe
	cible = user_mod._cible_alliee(principal, principal, {"cible_id": monture["_id"]})
	assert cible["_id"] == "monture:mule"


def test_le_lanceur_est_resolu_AVANT_la_relecture(groupe):
	# ⚠️ Régression majeure : un compagnon qui se vise lui-même. Si la résolution passait
	# par porteurs_effectifs, on obtiendrait un SECOND dict du même doc — _save_cast
	# écrirait deux fois sur le même `_rev` et l'un des deux serait perdu.
	principal, compagnon, _m = groupe
	cible = user_mod._cible_alliee(principal, compagnon, {"cible_id": compagnon["_id"]})
	assert cible is compagnon


def test_une_cible_hors_du_groupe_est_refusee(groupe):
	principal, _c, _m = groupe
	with pytest.raises(HTTPException) as exc:
		user_mod._cible_alliee(principal, principal, {"cible_id": "aventurier:inconnu"})
	assert exc.value.status_code == 403


def test_une_cible_absente_est_refusee(groupe):
	principal, _c, _m = groupe
	with pytest.raises(HTTPException) as exc:
		user_mod._cible_alliee(principal, principal, {})
	assert exc.value.status_code == 422


# ── Persistance ──────────────────────────────────────────────────────────────────

def _capturer_saves(monkeypatch, echecs=()):
	"""Remplace save_doc et enregistre les ids sauvés, dans l'ordre."""
	vus = []

	def fake_save(doc):
		vus.append(doc["_id"])
		return None if doc["_id"] in echecs else doc

	monkeypatch.setattr(user_mod, "save_doc", fake_save)
	return vus


def test_un_seul_save_quand_tout_est_le_meme_doc(monkeypatch, groupe):
	# Cas nominal, de loin le plus fréquent : le joueur se lance un sort à lui-même.
	principal, _c, _m = groupe
	vus = _capturer_saves(monkeypatch)
	user_mod._save_cast(principal, principal, principal)
	assert vus == ["character:moi"]


def test_deux_saves_quand_la_cible_differe(monkeypatch, groupe):
	principal, compagnon, _m = groupe
	vus = _capturer_saves(monkeypatch)
	user_mod._save_cast(principal, compagnon, principal)
	assert vus == ["character:moi", "aventurier:borin"]


def test_trois_saves_quand_lanceur_cible_et_principal_different(monkeypatch, groupe):
	# Un compagnon soigne une monture : trois documents distincts.
	principal, compagnon, monture = groupe
	vus = _capturer_saves(monkeypatch)
	user_mod._save_cast(compagnon, monture, principal)
	assert vus == ["aventurier:borin", "monture:mule", "character:moi"]


def test_le_lanceur_est_autoritatif(monkeypatch, groupe):
	# C'est lui qui a payé les PM : son échec de sauvegarde doit remonter en 409.
	principal, compagnon, _m = groupe
	_capturer_saves(monkeypatch, echecs=("character:moi",))
	with pytest.raises(HTTPException) as exc:
		user_mod._save_cast(principal, compagnon, principal)
	assert exc.value.status_code == 409


def test_un_echec_sur_la_cible_n_annule_pas_le_lancement(monkeypatch, groupe):
	# Best-effort assumé, faute d'écriture multi-documents atomique en CouchDB : mieux
	# vaut un soin perdu qu'une exception après que les PM sont partis.
	principal, compagnon, _m = groupe
	vus = _capturer_saves(monkeypatch, echecs=("aventurier:borin",))
	user_mod._save_cast(principal, compagnon, principal)
	assert vus == ["character:moi", "aventurier:borin"]
