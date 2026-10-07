# tests/test_fiche_resync.py
#
# Bloc `fiche` des réponses d'action (utils/fiche.fiche_resync, Convention §10). Bug d'origine :
# un grimoire acheté (ou une quête rendue) laissait « 📖 Apprendre », l'XP et les points figés
# jusqu'au prochain /play — `buy_item` ne renvoyait que l'inventaire.
#
# Pur : `get_doc`/`find_docs` en mémoire, `resolve_item_ref` (lu par utils.fiche) rebranché.

import pytest

from models.character_stats import compute_character_level
from utils import fiche as fiche_util


_RULES_VOCS = {"_id": "rules:vocations", "type": "rules", "value": [
	{"id": "moine", "magie": "Sainte"},
]}

_SOIN_MINEUR = {
	"_id": "sort:soin_mineur", "type": "sort", "nom": "Soin mineur", "icon": "✝️",
	"vocation": "pretre", "magie": "Sainte", "niveau": 0, "cout_pm": 8,
	"cible": "soi", "portee": 0, "effets": {"pv": 12},
}

_GRIMOIRE = {
	"_id": "item:grimoire_soin_mineur", "type": "item", "nom": "Grimoire : Soin mineur",
	"categorie": "livre", "sous_categorie": "grimoire", "poids": 1.0,
	"sorts": ["sort:soin_mineur"],
}

_DOCS = {d["_id"]: d for d in (_RULES_VOCS, _SOIN_MINEUR, _GRIMOIRE)}


def _get_doc(doc_id):
	return _DOCS.get(doc_id)


def _find_docs(sel):
	return [d for d in _DOCS.values() if all(d.get(k) == v for k, v in (sel or {}).items())]


def _resolve(ref):
	return _DOCS.get(ref if isinstance(ref, str) else (ref or {}).get("item"))


@pytest.fixture(autouse=True)
def _base(monkeypatch):
	monkeypatch.setattr(fiche_util, "resolve_item_ref", _resolve)
	import utils.characters as characters
	monkeypatch.setattr(characters, "resolve_item_ref", _resolve)


def _perso(**overrides):
	doc = {
		"_id": "character:u_1", "type": "character", "prenom": "Aliénor",
		"voc": "moine", "vocations_niveaux": {"moine": 1},
		"attribute_points": 2, "xp_total": 0, "sorts_connus": [],
		"caracteristiques_current": {"V": 10, "F": 10, "R": 10, "Ag": 10,
		                             "Vol": 10, "Int": 10, "Cha": 10, "Ch": 10},
		"inventaire": [], "slots": {},
	}
	doc.update(overrides)
	return doc


def _soin(f):
	return next(s for s in f["sorts_apprenables"] if s["id"] == "sort:soin_mineur")


def test_grimoire_acquis_ouvre_l_apprentissage():
	sans = fiche_util.fiche_resync(_perso(), _get_doc, _find_docs, race={})
	avec = fiche_util.fiche_resync(
		_perso(inventaire=[{"item": "item:grimoire_soin_mineur", "poids": 1.0}]),
		_get_doc, _find_docs, race={})
	assert _soin(sans)["grimoire_ok"] is False
	assert _soin(avec)["grimoire_ok"] is True


def test_identite_suit_xp_et_points():
	xp = 5000
	f = fiche_util.fiche_resync(_perso(xp_total=xp, attribute_points=7), _get_doc, _find_docs, race={})
	assert f["id"] == "character:u_1"
	assert f["xp_total"] == xp
	assert f["niveau"] == compute_character_level(xp)
	assert f["attribute_points"] == 7
	assert f["voc_niveau"] == 1
	# Mêmes clés que `bloc_fiche` : le client les affecte sans savoir d'où vient le bloc.
	bloc = fiche_util.bloc_fiche(_perso(), _get_doc, _find_docs, race={})
	assert set(bloc) <= set(f)


def test_monture_sans_fiche(monkeypatch):
	from routers import user as user_router
	assert user_router._fiche_payload({"_id": "monture:x"}) is None
