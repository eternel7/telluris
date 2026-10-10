"""Harnachement des montures — emplacements propres, capacité d'emport, garde d'équipement.

Verrouille ce qui casserait sans bruit : une selle sur un homme ou une cuirasse sur un cheval,
un bât qui gonfle la charge depuis le sac (et non le dos), une bête surchargée parce qu'on lui
a ôté son bât, et un harnachement qui disparaîtrait avec la monture relâchée ou morte.
Cf. utils/montures.py § Harnachement, contenu dev/gen_bourrellerie.py.
"""

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_bourrellerie as gen
from models import character_stats
from routers import user as user_router
from utils import characters, montures

ESPECE = {"_id": "espece:mulet", "type": "espece", "proprietes": {"charge_mult": 1.0}}
DOCS = {
	ESPECE["_id"]: ESPECE,
	"item:bat": {"_id": "item:bat", "type": "item", "nom": "Bât", "slots": ["monture_dos"],
				 "poids": 6, "monture": {"charge_pct": 50}},   # valeurs rondes de test, pas le contenu
	"item:selle": {"_id": "item:selle", "type": "item", "nom": "Selle", "slots": ["monture_dos"],
				   "poids": 4, "monture": {"charge_pct": 10}},
	"item:bride": {"_id": "item:bride", "type": "item", "nom": "Bride", "slots": ["monture_tete"],
				   "poids": 1, "monture": {"charge_pct": 5}},
	"item:barde": {"_id": "item:barde", "type": "item", "nom": "Barde", "slots": ["monture_poitrail"],
				   "poids": 8, "bonus_pa": 6, "restriction": {"F": 35}},
	"item:cuirasse": {"_id": "item:cuirasse", "type": "item", "nom": "Cuirasse", "slots": ["torse"],
					  "poids": 5, "bonus_pa": 8},
	"item:enclume": {"_id": "item:enclume", "type": "item", "nom": "Enclume", "slots": [], "poids": 90},
	# Bloc `monture` mal saisi : ne doit jamais AMPUTER la bête.
	"item:licol_casse": {"_id": "item:licol_casse", "type": "item", "slots": ["monture_tete"],
						 "poids": 1, "monture": {"charge_pct": -80}},
}


def _monture(f=20, inventaire=None, slots=None):
	"""F=20, charge_mult 1 → 100 kg à nu."""
	return {"_id": "monture:mulet_1", "type": "monture", "espece": ESPECE["_id"], "nom": "Mulet",
			"caracteristiques_current": {"F": f}, "inventaire": list(inventaire or []),
			"slots": dict(slots or {})}


def _perso(inventaire=None):
	return {"_id": "character:u_1", "type": "character", "inventaire": list(inventaire or []),
			"slots": {}, "caracteristiques_current": {"F": 50}}


@pytest.fixture
def db(monkeypatch):
	ecrits = []
	for mod in (montures, characters, user_router):
		monkeypatch.setattr(mod, "get_doc", DOCS.get)
	monkeypatch.setattr(character_stats, "MONTURE_CHARGE_MULT_DEFAUT", 1.0)
	monkeypatch.setattr(user_router, "save_doc", lambda doc: ecrits.append(doc["_id"]) or doc)
	monkeypatch.setattr(user_router, "sync_equipment_bonus", lambda c: c.setdefault("equipment_bonus", {}))
	monkeypatch.setattr(user_router, "_derived_from_character",
						lambda c, eq: type("D", (), {"model_dump": lambda self: {}})())
	monkeypatch.setattr(user_router.consommables, "caracts_detail", lambda c: {})
	return ecrits


def _appel(monkeypatch, porteur, fn, body):
	monkeypatch.setattr(user_router, "_acteur", lambda _u, _b: (porteur, porteur))
	return asyncio.run(fn(None, body))


# ── Logique pure ─────────────────────────────────────────────────────────────────

def test_slots_admis_selon_le_porteur():
	m, p = _monture(), _perso()
	for slot in montures.SLOTS_MONTURE:
		assert montures.slot_admis(m, slot) and not montures.slot_admis(p, slot)
	assert montures.slot_admis(p, "torse") and not montures.slot_admis(m, "torse")


def test_le_harnachement_porte_augmente_la_charge(db):
	m = _monture(slots={"monture_dos": "item:bat", "monture_tete": "item:bride"})
	assert montures.bonus_charge_pct(m) == 55
	assert montures.charge_max_monture(m) == 155
	assert montures.charge_max_porteur(m) == 155


def test_le_harnachement_au_sac_ne_compte_pas(db):
	"""Seul ce qui est SUR la bête compte : un bât rangé dans son sac ne porte rien."""
	m = _monture(inventaire=["item:bat"])
	assert montures.charge_max_monture(m) == 100


def test_un_bloc_negatif_n_ampute_pas_la_bete(db):
	m = _monture(slots={"monture_tete": "item:licol_casse"})
	assert montures.charge_max_monture(m) == 100


def test_harnachement_tient(db):
	m = _monture(inventaire=["item:enclume"], slots={"monture_dos": "item:bat"})   # 96 / 150
	assert montures.harnachement_tient(m)
	m["inventaire"].append("item:enclume")                                        # 186 / 150
	assert not montures.harnachement_tient(m)


def test_relacher_refuse_une_bete_harnachee(db):
	p = _perso()
	m = _monture(slots={"monture_dos": "item:selle"})
	m.update(statut="acquise", acquise_par=p["_id"])
	p["montures"] = [m["_id"]]
	ok, raison = montures.relacher(p, m)
	assert ok is False and "harnachement" in raison
	assert p["montures"] == [m["_id"]]


def test_tuer_rend_aussi_le_harnachement(db):
	p = _perso()
	m = _monture(inventaire=["item:enclume"], slots={"monture_dos": "item:selle", "monture_tete": None})
	p["montures"] = [m["_id"]]
	cargaison = montures.tuer(p, m)
	assert cargaison == ["item:enclume", "item:selle"]
	assert m["slots"] == {"monture_dos": None, "monture_tete": None}


# ── Endpoints /equip, /unequip ───────────────────────────────────────────────────

def test_harnacher_puis_oter_une_monture(db, monkeypatch):
	m = _monture(inventaire=["item:bat"])
	rep = _appel(monkeypatch, m, user_router.equip_item, {"item_id": "item:bat", "slot": "monture_dos"})
	assert m["slots"]["monture_dos"] == "item:bat" and m["inventaire"] == []
	assert rep["charge_max"] == 150 and rep["charge"] == 6
	rep = _appel(monkeypatch, m, user_router.unequip_item, {"slot": "monture_dos"})
	assert m["inventaire"] == ["item:bat"] and rep["charge_max"] == 100


def test_pas_de_selle_sur_un_homme_ni_de_cuirasse_sur_un_cheval(db, monkeypatch):
	p = _perso(inventaire=["item:selle"])
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, p, user_router.equip_item, {"item_id": "item:selle", "slot": "monture_dos"})
	assert e.value.status_code == 422 and p["inventaire"] == ["item:selle"]
	m = _monture(inventaire=["item:cuirasse"])
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, m, user_router.equip_item, {"item_id": "item:cuirasse", "slot": "torse"})
	assert e.value.status_code == 422 and m["inventaire"] == ["item:cuirasse"]


def test_oter_le_bat_d_une_bete_trop_chargee_est_refuse(db, monkeypatch):
	"""Ôter le bât ne change pas le poids porté mais réduit la capacité : 409, rien d'écrit."""
	m = _monture(inventaire=["item:enclume"] + ["item:cuirasse"] * 3 + ["item:selle"],
				 slots={"monture_dos": "item:bat"})                                # 115 / 150
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, m, user_router.unequip_item, {"slot": "monture_dos"})
	assert e.value.status_code == 409 and db == []
	# Remplacer le bât par la selle : même verdict (115 kg pour 110).
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, m, user_router.equip_item, {"item_id": "item:selle", "slot": "monture_dos"})
	assert e.value.status_code == 409 and db == []


def test_la_restriction_se_lit_sur_la_bete(db, monkeypatch):
	m = _monture(f=20, inventaire=["item:barde"])
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, m, user_router.equip_item, {"item_id": "item:barde", "slot": "monture_poitrail"})
	assert e.value.status_code == 422
	m = _monture(f=40, inventaire=["item:barde"])
	_appel(monkeypatch, m, user_router.equip_item, {"item_id": "item:barde", "slot": "monture_poitrail"})
	assert m["slots"]["monture_poitrail"] == "item:barde"


# ── Contenu (dev/gen_bourrellerie.py) ────────────────────────────────────────────

def test_generateur_miroir_des_slots_de_monture():
	assert gen.SLOTS_MONTURE == set(montures.SLOTS_MONTURE)
	assert gen.SLOTS_PERSONNAGE | gen.SLOTS_MONTURE == user_router._VALID_SLOTS


def test_items_du_lot_bien_formes():
	lot = [gen.item_doc(s) for s in gen.ITEMS]
	assert gen.controler_items(lot) == []
	for doc in lot:
		monture = set(doc["slots"]) & gen.SLOTS_MONTURE
		assert ("harnachement" in doc["tags"]) == bool(monture), doc["_id"]


def test_controle_des_items_refuse_les_melanges():
	erreurs = gen.controler_items([
		{"_id": "item:a", "slots": ["torse", "monture_dos"]},
		{"_id": "item:b", "slots": ["torse"], "monture": {"charge_pct": 10}},
		{"_id": "item:c", "slots": ["selle"]},
	])
	assert len(erreurs) == 3


def test_chaque_item_a_sa_recette_et_les_ids_sont_uniques():
	assert set(gen.ITEMS) <= set(gen.RECETTES)
	ids = [gen.recette_doc(s)["_id"] for s in gen.RECETTES]
	assert len(ids) == len(set(ids))


def test_villes_par_categorie_remonte_jusqu_a_la_cite():
	docs = [
		{"_id": "lieu:france", "categorie": "pays"},
		{"_id": "lieu:auxerre", "categorie": "ville", "lieu_parent": "lieu:france"},
		{"_id": "lieu:quartier", "categorie": "quartier", "lieu_parent": "lieu:auxerre"},
		{"_id": "lieu:bourrelier", "categorie": "bourrellerie", "lieu_parent": "lieu:quartier"},
	]
	villes = gen.villes_par_categorie(docs)
	assert villes["bourrellerie"] == {"lieu:auxerre"}
	assert "pays" not in villes   # aucune cité au-dessus : ignoré
