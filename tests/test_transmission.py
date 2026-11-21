"""Transmettre un objet (`utils/transmission.py`, `POST /api/transmettre`).

Un geste pour tout ce que le groupe a en main : sac d'un porteur, contenant porté, sol du lieu.
Ce que ces tests verrouillent :
1. Chaque paire source → cible (sac, contenant, sol) passe l'objet, une seule fois.
2. Refus (charge, place, contenant dans un contenant, marée basse, même tas) ⇒ RIEN n'a bougé.
3. Le contenant visé dans le MÊME sac que l'objet : sa position glisse, l'objet y arrive quand même.
4. Endpoint : un même porteur résolu en UN dict, cible sauvée d'abord, porteur hors groupe = 403.
"""

import pytest
from fastapi import HTTPException

from models import character_stats
from routers import contenants as rcontenants
from routers import transmission as rt
from routers import user as ru
from utils import characters
from utils import transmission as tr

from tests.test_combat_groupe import character, aventurier

BESACE = {"_id": "item:besace", "type": "item", "nom": "Besace profonde", "icon": "👜", "slots": [],
		  "poids": 0.5, "contenant": {"capacite_kg": 10}}
SAC_MAREE = dict(BESACE, _id="item:sac_maree", nom="Sac de Manannán",
				 contenant={"capacite_kg": 500, "maree": True})
PIERRE = {"_id": "item:pierre", "type": "item", "nom": "Pierre", "slots": [], "poids": 4.0}
ENCLUME = {"_id": "item:enclume", "type": "item", "nom": "Enclume", "slots": [], "poids": 200.0}
ITEMS = {d["_id"]: d for d in (BESACE, SAC_MAREE, PIERRE, ENCLUME)}


@pytest.fixture
def docs(monkeypatch):
	base = dict(ITEMS)
	monkeypatch.setattr(characters, "get_doc", base.get, raising=False)
	return base


@pytest.fixture
def maree_basse(monkeypatch):
	"""Période 1 000 s, fenêtre 200 s, pleine mer à t = 0 ; t = 500 → mer basse."""
	monkeypatch.setattr(character_stats, "MAREE_PERIODE_S", 1000)
	monkeypatch.setattr(character_stats, "MAREE_FENETRE_S", 200)
	monkeypatch.setattr(character_stats, "MAREE_REFERENCE_EPOCH", 0)


def _t(source, cible, au_sol, idx, item_id, docs, now=0):
	return tr.transmettre(source, cible, au_sol, idx, item_id, docs.get, now)


# ── Pur : chaque paire passe l'objet ─────────────────────────────────────────────

def test_sac_vers_sac_sol_et_retour(docs):
	moi, ami, sol = character(inventaire=["item:pierre"]), aventurier(), []
	ok, _c, _r, ref = _t(tr.emplacement_sac(moi), tr.emplacement_sac(ami), sol, 0, "item:pierre", docs)
	assert ok and ref == "item:pierre" and moi["inventaire"] == [] and ami["inventaire"] == ["item:pierre"]
	assert _t(tr.emplacement_sac(ami), tr.emplacement_sol(), sol, 0, "item:pierre", docs)[0]
	assert ami["inventaire"] == [] and sol == ["item:pierre"]
	assert _t(tr.emplacement_sol(), tr.emplacement_sac(moi), sol, 0, "item:pierre", docs)[0]
	assert sol == [] and moi["inventaire"] == ["item:pierre"]


def test_sac_vers_contenant_d_un_autre_puis_vers_le_sol(docs):
	moi = character(inventaire=["item:pierre"])
	ami = aventurier(inventaire=[{"item": "item:besace"}])
	sol = []
	ctn = tr.emplacement_contenant(ami, 0, "item:besace")
	assert _t(tr.emplacement_sac(moi), ctn, sol, 0, "item:pierre", docs)[0]
	assert moi["inventaire"] == [] and ami["inventaire"][0]["contenu"] == ["item:pierre"]
	assert _t(ctn, tr.emplacement_sol(), sol, 0, "item:pierre", docs)[0]
	assert sol == ["item:pierre"] and "contenu" not in ami["inventaire"][0], "contenant vidé : clé retirée"


def test_contenant_vers_contenant_et_vers_sac(docs):
	moi = character(inventaire=[{"item": "item:besace", "contenu": ["item:pierre"]}])
	ane = {"_id": "monture:ane", "nom": "Grison", "inventaire": [{"item": "item:besace"}]}
	a = tr.emplacement_contenant(moi, 0, "item:besace")
	b = tr.emplacement_contenant(ane, 0, "item:besace")
	assert _t(a, b, [], 0, "item:pierre", docs)[0]
	assert "contenu" not in moi["inventaire"][0] and ane["inventaire"][0]["contenu"] == ["item:pierre"]
	assert _t(b, tr.emplacement_sac(moi), [], 0, "item:pierre", docs)[0]
	assert moi["inventaire"][1] == "item:pierre"


def test_contenant_du_meme_sac_place_avant_l_objet_qui_part(docs):
	"""L'objet quitte le sac AVANT le contenant visé : la position du contenant glisse."""
	moi = character(inventaire=["item:pierre", {"item": "item:besace"}])
	assert _t(tr.emplacement_sac(moi), tr.emplacement_contenant(moi, 1, "item:besace"), [], 0, "item:pierre", docs)[0]
	assert moi["inventaire"] == [{"item": "item:besace", "contenu": ["item:pierre"]}]


def test_sol_vers_contenant(docs):
	moi, sol = character(inventaire=[{"item": "item:besace"}]), ["item:pierre"]
	assert _t(tr.emplacement_sol(), tr.emplacement_contenant(moi, 0, "item:besace"), sol, 0, "item:pierre", docs)[0]
	assert sol == [] and moi["inventaire"][0]["contenu"] == ["item:pierre"]


# ── Pur : refus ⇒ rien ne bouge ──────────────────────────────────────────────────

def test_refus_charge_ne_touche_pas_la_source(docs):
	moi, ami, sol = character(), aventurier(), ["item:enclume"]
	ok, code, raison, _ = _t(tr.emplacement_sol(), tr.emplacement_sac(ami), sol, 0, "item:enclume", docs)
	assert not ok and code == 409 and "Aldric" in raison
	assert sol == ["item:enclume"] and ami["inventaire"] == []


def test_refus_contenant_plein_ou_emboite(docs):
	moi = character(inventaire=[{"item": "item:besace"}, {"item": "item:besace"}, "item:enclume"])
	ctn = tr.emplacement_contenant(moi, 0, "item:besace")
	ok, code, raison, _ = _t(tr.emplacement_sac(moi), ctn, [], 2, "item:enclume", docs)
	assert not ok and code == 409 and "plein" in raison
	ok, code, raison, _ = _t(tr.emplacement_sac(moi), ctn, [], 1, "item:besace", docs)
	assert not ok and code == 409 and "autre" in raison
	ok, _c, raison, _ = _t(tr.emplacement_sac(moi), ctn, [], 0, "item:besace", docs)
	assert not ok and "lui-même" in raison
	assert len(moi["inventaire"]) == 3 and all("contenu" not in r for r in moi["inventaire"][:2])


def test_maree_basse_on_depose_on_ne_reprend_pas(docs, maree_basse):
	moi = character(inventaire=[{"item": "item:sac_maree"}, "item:pierre"])
	ctn = tr.emplacement_contenant(moi, 0, "item:sac_maree")
	assert _t(tr.emplacement_sac(moi), ctn, [], 1, "item:pierre", docs, now=500)[0]
	ok, code, raison, _ = _t(ctn, tr.emplacement_sol(), [], 0, "item:pierre", docs, now=500)
	assert not ok and code == 409 and "mer" in raison
	assert moi["inventaire"][0]["contenu"] == ["item:pierre"]


def test_meme_emplacement_et_objet_absent(docs):
	moi = character(inventaire=["item:pierre", {"item": "item:besace"}])
	ok, code, _r, _ = _t(tr.emplacement_sac(moi), tr.emplacement_sac(moi), [], 0, "item:pierre", docs)
	assert not ok and code == 422
	ctn = tr.emplacement_contenant(moi, 1, "item:besace")
	assert _t(ctn, ctn, [], 0, "item:pierre", docs)[1] == 422
	assert _t(tr.emplacement_sol(), tr.emplacement_sol(), ["item:pierre"], 0, "item:pierre", docs)[1] == 422
	ok, code, _r, _ = _t(tr.emplacement_sol(), tr.emplacement_sac(moi), [], 0, "item:pierre", docs)
	assert not ok and code == 422
	ok, code, _r, _ = _t(tr.emplacement_sac(moi), tr.emplacement_contenant(moi, 0, "item:pierre"), [], 0, "item:pierre", docs)
	assert not ok and code == 404
	assert moi["inventaire"] == ["item:pierre", {"item": "item:besace"}]


# ── Endpoint ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def endpoint(docs, monkeypatch):
	etat = {"saves": []}

	def appeler(acteur, principal, compagnons, body):
		monkeypatch.setattr(rt, "_acteur", lambda _u, _b: (acteur, principal))
		monkeypatch.setattr(ru.recrutement, "porteurs_effectifs",
							lambda c, g: [dict(x) for x in compagnons])   # relu : un dict NEUF à chaque appel
		monkeypatch.setattr(rt, "get_doc", docs.get)
		monkeypatch.setattr(rt, "save_doc", lambda d: etat["saves"].append(d) or d)
		monkeypatch.setattr(rt, "_inventory_payload", lambda a, p: {"inventaire": list(a.get("inventaire", []))})
		monkeypatch.setattr(rt, "_fiche_payload", lambda d: {"id": d["_id"]})
		monkeypatch.setattr(rt, "_refuser_en_combat", lambda u, p: None)
		return rt.transmettre({"_id": "user:u"}, body)
	etat["appeler"] = appeler
	return etat


def test_endpoint_compagnon_vers_contenant_du_meme_compagnon_un_seul_dict(endpoint):
	moi = character()
	ami = aventurier(inventaire=["item:pierre", {"item": "item:besace"}])
	r = endpoint["appeler"](moi, moi, [ami], {
		"source": {"porteur_id": ami["_id"]},
		"cible": {"porteur_id": ami["_id"], "contenant_index": 1, "contenant_item_id": "item:besace"},
		"index": 0, "item_id": "item:pierre"})
	assert len(endpoint["saves"]) == 1, "même porteur des deux côtés : un seul doc, un seul save"
	assert endpoint["saves"][0]["inventaire"] == [{"item": "item:besace", "contenu": ["item:pierre"]}]
	assert r["transmis"]["nom"] == "Pierre" and r["fiches"] == [{"id": ami["_id"]}]


def test_endpoint_vers_le_sol_cible_d_abord_et_reponse_de_l_acteur(endpoint):
	moi = character(objets_au_sol=[])
	ami = aventurier(inventaire=["item:pierre"])
	r = endpoint["appeler"](ami, moi, [ami], {
		"compagnon_id": ami["_id"], "source": {"porteur_id": ami["_id"]}, "cible": {"sol": True},
		"index": 0, "item_id": "item:pierre"})
	assert endpoint["saves"][0] is moi and moi["objets_au_sol"] == ["item:pierre"]
	assert endpoint["saves"][1] is ami and r["inventaire"] == []


def test_endpoint_refus_porteur_hors_groupe_et_refus_de_regle(endpoint):
	moi = character(inventaire=["item:enclume"])
	with pytest.raises(HTTPException) as e:
		endpoint["appeler"](moi, moi, [], {"source": {"porteur_id": moi["_id"]},
										   "cible": {"porteur_id": "aventurier:inconnu"}, "index": 0})
	assert e.value.status_code == 403
	ami = aventurier()
	with pytest.raises(HTTPException) as e:
		endpoint["appeler"](moi, moi, [ami], {"source": {"porteur_id": moi["_id"]},
											  "cible": {"porteur_id": ami["_id"]}, "index": 0, "item_id": "item:enclume"})
	assert e.value.status_code == 409 and endpoint["saves"] == []
	with pytest.raises(HTTPException) as e:
		endpoint["appeler"](moi, moi, [], {"source": "sac", "cible": {"sol": True}})
	assert e.value.status_code == 422


def test_routeur_branche_dans_l_app():
	assert any(getattr(r, "path", "") == "/transmettre" for r in rt.transmission_router.routes)
	assert rcontenants._refuser_en_combat is not None
