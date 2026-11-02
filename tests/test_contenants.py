"""Contenants (`utils/contenants.py`, `routers/contenants.py`) — docs/conception_contenants.md.

Ce que ces tests verrouillent :
1. Le contenu vit sur la RÉFÉRENCE : il suit le contenant (transfert de groupe, coffre) et
   ne pèse rien pour le porteur — physiquement comme magiquement (Auteur, 02/11).
2. Capacité, aucun contenant dans un autre, sortir borné par la charge du porteur.
3. Marée en temps réel (Sac de Manannán) : dépôt toujours, reprise seulement en fenêtre.
4. Gardes : vente et don à un atelier refusés plein, limite de vol au poids RÉEL, combat.
"""

import asyncio

import pytest
from fastapi import HTTPException

from models import character_stats
from routers import contenants as rc
from routers import user as ru
from utils import characters
from utils import contenants
from utils import proprietes
from utils import recrutement

BESACE = {"_id": "item:besace", "type": "item", "nom": "Besace profonde", "categorie": "outil",
		  "sous_categorie": "contenant", "slots": [], "poids": 0.5,
		  "tags": ["contenant", "non_personnalisable"], "contenant": {"capacite_kg": 10}}
SAC_MAREE = dict(BESACE, _id="item:sac_maree", nom="Sac de Manannán",
				 contenant={"capacite_kg": 500, "maree": True})
URNE = dict(BESACE, _id="item:urne", nom="Urne intérieure", poids=8, contenant={"capacite_kg": 300})
PIERRE = {"_id": "item:pierre", "type": "item", "nom": "Pierre", "categorie": "composant",
		  "slots": [], "poids": 4.0}
POMME = {"_id": "item:pomme", "type": "item", "nom": "Pomme", "categorie": "consommable",
		 "slots": [], "poids": 0.2}
ITEMS = {d["_id"]: d for d in (BESACE, SAC_MAREE, URNE, PIERRE, POMME)}
# F = 4 → charge max 20 kg (F × 5) : assez pour vérifier le refus de « sortir ».
CARACTS = {"V": 5, "F": 4, "R": 5, "Ag": 5, "Vol": 5, "Int": 5, "Cha": 5, "Ch": 5}


def _perso(inventaire, **champs):
	base = {"_id": "character:a", "type": "character", "inventaire": list(inventaire), "slots": {},
			"caracteristiques_current": dict(CARACTS)}
	base.update(champs)
	return base


@pytest.fixture
def maree(monkeypatch):
	"""Période 1 000 s, fenêtre 200 s, pleine mer à t = 0 (mod 1 000)."""
	monkeypatch.setattr(character_stats, "MAREE_PERIODE_S", 1000)
	monkeypatch.setattr(character_stats, "MAREE_FENETRE_S", 200)
	monkeypatch.setattr(character_stats, "MAREE_REFERENCE_EPOCH", 0)


@pytest.fixture
def db(monkeypatch):
	docs = dict(ITEMS)
	combats = []
	for mod in (characters, rc):
		monkeypatch.setattr(mod, "get_doc", docs.get, raising=False)
	monkeypatch.setattr(rc, "find_docs", lambda sel, fields=None: [
		c for c in combats if all(c.get(k) == v for k, v in sel.items())])
	monkeypatch.setattr(rc, "_save_acteur", lambda porteur, principal: None)
	monkeypatch.setattr(rc, "_inventory_payload", lambda c, p=None: {"inventaire": list(c.get("inventaire") or [])})
	monkeypatch.setattr(rc, "_fiche_payload", lambda c: None)
	return {"docs": docs, "combats": combats}


def _appel(monkeypatch, porteur, fn, body, principal=None):
	principal = principal or porteur
	monkeypatch.setattr(rc, "_acteur", lambda _u, _b: (porteur, principal))
	return asyncio.run(fn({"_id": "user:a"}, body))


# ── Pur ──────────────────────────────────────────────────────────────────────────

def test_est_contenant_et_capacite():
	assert contenants.est_contenant(BESACE) and contenants.capacite(BESACE) == 10
	assert not contenants.est_contenant(PIERRE)
	assert not contenants.est_contenant({"contenant": {"capacite_kg": 0}})


def test_le_contenu_ne_pese_rien_pour_le_porteur(db):
	plein = {"item": "item:besace", "poids": 0.5, "contenu": ["item:pierre", "item:pierre"]}
	perso = _perso([plein])
	assert characters.carried_weight(perso) == 0.5
	assert contenants.poids_contenu(plein) == 8.0
	assert contenants.poids_total(plein) == 8.5


def test_peut_ranger_capacite_emboitement_et_lui_meme(db):
	vide = {"item": "item:besace", "poids": 0.5}
	assert contenants.peut_ranger(vide, BESACE, "item:pierre", PIERRE)[0]
	presque = {"item": "item:besace", "contenu": ["item:pierre", "item:pierre"]}
	ok, raison = contenants.peut_ranger(presque, BESACE, "item:pierre", PIERRE)
	assert not ok and "plein" in raison
	ok, raison = contenants.peut_ranger(vide, BESACE, "item:urne", URNE)
	assert not ok and "autre" in raison
	assert not contenants.peut_ranger(vide, BESACE, vide, BESACE)[0]
	assert not contenants.peut_ranger(vide, PIERRE, "item:pomme", POMME)[0]


def test_ranger_fige_une_reference_chaine_et_sortir_retire_la_cle(db):
	perso = _perso(["item:besace", "item:pomme"])
	contenants.ranger(perso, 0, 1)
	assert perso["inventaire"] == [{"item": "item:besace", "poids": 0.5, "contenu": ["item:pomme"]}]
	contenants.sortir(perso, 0, 0)
	assert perso["inventaire"] == [{"item": "item:besace", "poids": 0.5}, "item:pomme"]


def test_maree_fenetre_centree_sur_la_pleine_mer(maree):
	assert contenants.maree_haute(0) and contenants.maree_haute(100) and contenants.maree_haute(900)
	assert not contenants.maree_haute(101) and not contenants.maree_haute(899)
	assert contenants.maree_haute(1000 * 7 + 50)          # même moment à chaque période
	assert contenants.prochaine_maree(500) == 900
	assert contenants.prochaine_maree(50) == 900           # fenêtre en cours → la SUIVANTE
	assert contenants.prochaine_maree(950) == 1900
	assert contenants.fin_maree(50) == 100 and contenants.fin_maree(950) == 1100
	assert contenants.fin_maree(500) is None


def test_resume_masque_le_contenu_hors_maree(db, maree):
	ref = {"item": "item:sac_maree", "poids": 0.5, "contenu": ["item:pierre"]}
	bas = contenants.resume(ref, SAC_MAREE, 500)
	assert bas["accessible"] is False and bas["nb"] == 0 and bas["charge_kg"] == 0
	haut = contenants.resume(ref, SAC_MAREE, 1000)
	assert haut["accessible"] and haut["nb"] == 1 and haut["charge_kg"] == 4.0
	assert contenants.vue(ref, SAC_MAREE, 500, characters.resolve_item_ref)["contenu"] == []
	assert contenants.resume("item:pierre", PIERRE, 0) is None


def test_resolve_item_ref_pose_le_resume(db):
	doc = characters.resolve_item_ref({"item": "item:besace", "poids": 0.5, "contenu": ["item:pomme"]})
	assert doc["contenant"]["capacite_kg"] == 10 and doc["contenant"]["nb"] == 1
	assert ITEMS["item:besace"]["contenant"] == {"capacite_kg": 10}   # doc générique intact


def test_le_contenu_suit_le_contenant_entre_porteurs_et_au_coffre(db):
	plein = {"item": "item:besace", "poids": 0.5, "contenu": ["item:pierre"]}
	perso, compagnon = _perso([plein]), _perso([], _id="aventurier:b")
	ok, _, _ = recrutement.transferer_ref(perso, compagnon, 0, "item:besace")
	assert ok and compagnon["inventaire"][0]["contenu"] == ["item:pierre"]
	prop = {"coffre": []}
	proprietes.deposer(compagnon, prop, 0)
	assert prop["coffre"][0]["contenu"] == ["item:pierre"]
	# Le coffre ne compte que le contenant (Auteur, 02/11) ; la limite de vol, le poids réel.
	assert proprietes.poids_coffre(prop) == 0.5
	assert proprietes.poids_coffre_reel(prop) == 4.5


def test_limite_de_vol_au_poids_reel(db):
	plein = {"item": "item:besace", "poids": 0.5, "contenu": ["item:pierre", "item:pierre"]}
	prop = {"coffre": [plein, "item:pierre", "item:pierre"]}   # réel : 8,5 + 8 = 16,5 kg
	limite = {"fraction": 0.5, "delai_s": 3600}               # plafond : 8,25 kg
	ok, _ = proprietes.vol_coffre_autorise(prop, limite, plein, now=10)
	assert not ok                                              # 8,5 kg > 8,25 : refusé
	assert proprietes.vol_coffre_autorise(prop, limite, "item:pierre", now=10)[0]


def test_donner_a_un_atelier_refuse_plein():
	atelier = {"_id": "employe:x", "type": proprietes.TYPE_EMPLOYE, "categorie": "negociant",
			   "statut": proprietes.EMPLOYE_ACTIF}
	ok, raison = proprietes.donner(atelier, BESACE, ref={"item": "item:besace", "contenu": ["item:pomme"]})
	assert not ok and raison == contenants.REFUS_PLEIN


# ── Endpoints ────────────────────────────────────────────────────────────────────

def test_ranger_puis_sortir(db, monkeypatch):
	perso = _perso(["item:pomme", "item:besace", "item:pierre"])
	r = _appel(monkeypatch, perso, rc.contenant_ranger,
			   {"index_contenant": 1, "item_id_contenant": "item:besace", "index": 0, "item_id": "item:pomme"})
	# La pomme était AVANT le contenant : son index a glissé, la réponse le dit.
	assert r["contenant"]["index"] == 0 and r["contenant"]["nb"] == 1
	assert [c["_id"] for c in r["contenant"]["contenu"]] == ["item:pomme"]
	r = _appel(monkeypatch, perso, rc.contenant_sortir,
			   {"index_contenant": 0, "item_id_contenant": "item:besace", "index_contenu": 0, "item_id": "item:pomme"})
	assert r["sorti"] == "Pomme" and "item:pomme" in perso["inventaire"]


def test_ranger_refuse_plein_et_emboitement(db, monkeypatch):
	perso = _perso([{"item": "item:besace", "poids": 0.5, "contenu": ["item:pierre", "item:pierre"]},
					"item:pierre", "item:urne"])
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, perso, rc.contenant_ranger,
			   {"index_contenant": 0, "item_id_contenant": "item:besace", "index": 1, "item_id": "item:pierre"})
	assert e.value.status_code == 409
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, perso, rc.contenant_ranger,
			   {"index_contenant": 0, "item_id_contenant": "item:besace", "index": 2, "item_id": "item:urne"})
	assert e.value.status_code == 409


def test_sortir_refuse_si_le_porteur_ne_peut_pas_porter(db, monkeypatch):
	pleine = {"item": "item:urne", "poids": 8, "contenu": ["item:pierre"] * 4}
	perso = _perso([pleine, "item:pierre", "item:pierre", "item:pierre"])   # 8 + 12 = 20 kg sur 20
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, perso, rc.contenant_sortir,
			   {"index_contenant": 0, "item_id_contenant": "item:urne", "index_contenu": 0, "item_id": "item:pierre"})
	assert e.value.status_code == 409 and len(pleine["contenu"]) == 4


def test_maree_basse_on_depose_mais_on_ne_reprend_pas(db, maree, monkeypatch):
	monkeypatch.setattr(rc.time, "time", lambda: 500)
	perso = _perso([{"item": "item:sac_maree", "poids": 0.5, "contenu": ["item:pierre"]}, "item:pomme"])
	r = _appel(monkeypatch, perso, rc.contenant_ranger,
			   {"index_contenant": 0, "item_id_contenant": "item:sac_maree", "index": 1, "item_id": "item:pomme"})
	assert r["contenant"]["contenu"] == [] and r["contenant"]["prochaine_maree_at"] == 900
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, perso, rc.contenant_sortir,
			   {"index_contenant": 0, "item_id_contenant": "item:sac_maree", "index_contenu": 0})
	assert e.value.status_code == 409
	monkeypatch.setattr(rc.time, "time", lambda: 1000)
	r = _appel(monkeypatch, perso, rc.contenant_sortir,
			   {"index_contenant": 0, "item_id_contenant": "item:sac_maree", "index_contenu": 1, "item_id": "item:pomme"})
	assert r["sorti"] == "Pomme"


def test_refus_en_combat(db, monkeypatch):
	db["combats"].append({"type": "combat", "user_id": "user:a", "character_id": "character:a", "status": "active"})
	perso = _perso(["item:besace", "item:pomme"])
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, perso, rc.contenant_ranger,
			   {"index_contenant": 0, "item_id_contenant": "item:besace", "index": 1, "item_id": "item:pomme"})
	assert e.value.status_code == 409


def test_compagnon_range_dans_son_propre_sac(db, monkeypatch):
	principal = _perso([])
	compagnon = _perso(["item:besace", "item:pomme"], _id="aventurier:b")
	_appel(monkeypatch, compagnon, rc.contenant_ranger,
		   {"index_contenant": 0, "item_id_contenant": "item:besace", "index": 1, "item_id": "item:pomme",
			"compagnon_id": "aventurier:b"}, principal=principal)
	assert compagnon["inventaire"][0]["contenu"] == ["item:pomme"] and principal["inventaire"] == []


def test_vendre_un_contenant_plein_refuse(db, monkeypatch):
	perso = _perso([{"item": "item:besace", "poids": 0.5, "contenu": ["item:pomme"]}])
	monkeypatch.setattr(ru, "_acteur", lambda _u, _b: (perso, perso))
	monkeypatch.setattr(ru, "_current_lieu_doc", lambda p: {"_id": "lieu:echoppe"})
	monkeypatch.setattr(ru.proprietes, "vend_au_proprietaire", lambda *a: False)
	monkeypatch.setattr(ru, "get_relation", lambda *a: {})
	monkeypatch.setattr(ru, "relation_value", lambda r: 50)
	with pytest.raises(HTTPException) as e:
		asyncio.run(ru.sell_item({"_id": "user:a"}, {"index": 0, "item_id": "item:besace"}))
	assert e.value.status_code == 409 and e.value.detail == contenants.REFUS_PLEIN
