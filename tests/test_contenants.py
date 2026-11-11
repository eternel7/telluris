"""Contenants (`utils/contenants.py`, `routers/contenants.py`) — docs/conception_contenants.md.

Ce que ces tests verrouillent :
1. Le contenu vit sur la RÉFÉRENCE : il suit le contenant (transfert de groupe, coffre) et
   ne pèse rien pour le porteur — physiquement comme magiquement (Auteur, 02/11).
2. Capacité, aucun contenant dans un autre, sortir borné par la charge du porteur.
3. Marée en temps réel (Sac de Manannán) : dépôt toujours, reprise seulement en fenêtre.
4. Gardes : vente et don à un atelier refusés plein, limite de vol au poids RÉEL, combat.
5. Vente en boutique et remises de quête (collecte, transport, apport) : le contenant est un
   PORTEUR de plus, comme un compagnon (Auteur, 07/11) ; marée basse = contenu hors d'atteinte.
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


def test_poser_au_sol_sans_controle_de_charge(db, monkeypatch):
	"""Ce que le porteur ne peut pas sortir dans son sac, il peut le poser par terre : le sol
	est celui du PRINCIPAL, la charge n'est pas vérifiée."""
	pleine = {"item": "item:urne", "poids": 8, "contenu": ["item:pierre"] * 4}
	perso = _perso([pleine, "item:pierre", "item:pierre", "item:pierre"], objets_au_sol=["item:pomme"])
	r = _appel(monkeypatch, perso, rc.contenant_poser,
			   {"index_contenant": 0, "item_id_contenant": "item:urne", "index_contenu": 0, "item_id": "item:pierre"})
	assert r["pose"] == "Pierre" and len(pleine["contenu"]) == 3
	assert perso["objets_au_sol"] == ["item:pomme", "item:pierre"]
	assert characters.carried_weight(perso) == 20


def test_un_compagnon_pose_sur_le_sol_du_principal(db, monkeypatch):
	principal = _perso([])
	compagnon = _perso([{"item": "item:besace", "contenu": ["item:pomme"]}], _id="aventurier:x")
	_appel(monkeypatch, compagnon, rc.contenant_poser,
		   {"index_contenant": 0, "item_id_contenant": "item:besace", "index_contenu": 0}, principal=principal)
	assert principal["objets_au_sol"] == ["item:pomme"] and "objets_au_sol" not in compagnon
	assert "contenu" not in compagnon["inventaire"][0]   # contenant vidé : clé retirée


def test_poser_refuse_a_maree_basse(db, maree, monkeypatch):
	monkeypatch.setattr(rc.time, "time", lambda: 500)
	perso = _perso([{"item": "item:sac_maree", "poids": 0.5, "contenu": ["item:pierre"]}])
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, perso, rc.contenant_poser,
			   {"index_contenant": 0, "item_id_contenant": "item:sac_maree", "index_contenu": 0})
	assert e.value.status_code == 409 and not perso.get("objets_au_sol")


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


# ── Contenants comme porteurs : vente en boutique et remises de quête (Auteur, 07/11) ─

from utils import chasse
from utils import quetes
from utils import transport


def _besace(*contenu):
	return {"item": "item:besace", "poids": 0.5, "contenu": list(contenu)}


def test_avec_contenants_reels_en_tete_puis_contenants_ouverts(db, maree):
	ouvert = _besace("item:pomme")
	perso = _perso(["item:pierre", ouvert, {"item": "item:besace", "poids": 0.5}])
	compagnon = {"_id": "aventurier:b", "inventaire": [{"item": "item:sac_maree", "poids": 0.5,
														 "contenu": ["item:pierre"]}]}
	# Mer basse (t = 500) : le Sac de Manannán ne s'ouvre pas ; la besace VIDE n'est pas un sac.
	sacs = contenants.avec_contenants([perso, compagnon], db["docs"].get, 500)
	assert sacs[:2] == [perso, compagnon] and len(sacs) == 3
	assert sacs[2]["inventaire"] == ["item:pomme"]
	assert sacs[2][contenants.CLE_VIRTUEL]["porteur"] is perso and sacs[2][contenants.CLE_VIRTUEL]["index"] == 1
	# Mer haute (t = 0) : il devient un porteur de plus.
	assert len(contenants.avec_contenants([perso, compagnon], db["docs"].get, 0)) == 4


def test_depot_de_collecte_puise_dans_les_contenants(db):
	perso = _perso(["item:pierre", _besace("item:pierre", "item:pomme")])
	compagnon = {"_id": "aventurier:b", "inventaire": [_besace("item:pierre")]}
	q = {"objectif": {"type": "collect", "cible": "item:pierre", "quantite": 3}, "progress": 0}
	sacs = contenants.avec_contenants([perso, compagnon], db["docs"].get, 0)
	n, touches = quetes.deposer_collect(perso, q, sacs[1:])
	contenants.reporter(sacs)
	assert n == 3 and q["progress"] == 3
	# Le sac porté se vide d'abord ; la besace du principal garde la pomme ; celle du
	# compagnon, vidée, perd sa clé `contenu`.
	assert perso["inventaire"] == [_besace("item:pomme")]
	assert compagnon["inventaire"] == [{"item": "item:besace", "poids": 0.5}]
	# À persister : le compagnon (son contenant a bougé), jamais le principal ni un sac virtuel.
	assert contenants.porteurs_reels(touches, exclure=perso) == [compagnon]


def test_livraison_de_transport_depuis_un_contenant(db):
	perso = _perso([_besace("item:pomme", "item:pierre")])
	q = {"cargaison": [{"item": "item:pierre", "poids": 4.0}], "objectif": {"quantite": 1}}
	assert transport.cargaison_manquante(perso, q) == {"item:pierre": 1}
	sacs = contenants.avec_contenants([perso], db["docs"].get, 0)
	touches = []
	assert transport.livrer_transport(perso, q, sacs[1:], touches)
	contenants.reporter(sacs)
	assert perso["inventaire"] == [_besace("item:pomme")]
	assert contenants.porteurs_reels(touches, exclure=perso) == []


def test_epreuve_d_apport_depuis_un_contenant(db):
	perso = _perso([_besace("item:pierre")])
	spec = {"items": ["item:pierre"]}
	sacs = contenants.avec_contenants([perso], db["docs"].get, 0)
	i = chasse.sac_avec_apport(sacs, spec)
	assert i == 1 and chasse.retirer_objet_apport(sacs[i], spec) == "item:pierre"
	contenants.reporter(sacs)
	assert perso["inventaire"] == [{"item": "item:besace", "poids": 0.5}]


def test_sac_vise_refus(db, maree):
	perso = _perso(["item:pierre", {"item": "item:sac_maree", "poids": 0.5, "contenu": ["item:pomme"]}])
	assert contenants.sac_vise(perso, None, None, db["docs"].get, 0)[0] is perso["inventaire"]
	assert contenants.sac_vise(perso, 0, "item:pierre", db["docs"].get, 0)[2][0] == 422
	assert contenants.sac_vise(perso, 1, "item:sac_maree", db["docs"].get, 500)[2][0] == 409
	refs, ref_c, refus = contenants.sac_vise(perso, 1, "item:sac_maree", db["docs"].get, 0)
	assert refus is None and refs == ["item:pomme"] and ref_c is perso["inventaire"][1]


@pytest.fixture
def boutique(db, monkeypatch):
	"""Une échoppe qui achète tout à 10 cu ; écritures neutralisées."""
	monkeypatch.setattr(ru, "get_doc", db["docs"].get)
	monkeypatch.setattr(ru, "_current_lieu_doc", lambda p: {"_id": "lieu:echoppe"})
	monkeypatch.setattr(ru.proprietes, "vend_au_proprietaire", lambda *a: False)
	monkeypatch.setattr(ru, "get_relation", lambda *a: {})
	monkeypatch.setattr(ru, "relation_value", lambda r: 50)
	monkeypatch.setattr(ru, "lieu_buys", lambda lieu, item: True)
	monkeypatch.setattr(ru, "_prix_vente_joueur", lambda *a: (10, 5, 15))
	monkeypatch.setattr(ru, "now_epoch", lambda: 0)
	for nom in ("convertir_apres_achat", "save_doc", "persister_flux", "_save_acteur", "_appliquer_fidelite"):
		monkeypatch.setattr(ru, nom, lambda *a, **k: None)
	monkeypatch.setattr(ru, "flux_cite", lambda *a: None)
	monkeypatch.setattr(ru, "resolve_stock_vente", lambda *a: [])
	monkeypatch.setattr(ru, "_inventory_payload", lambda c, p=None: {})
	monkeypatch.setattr(ru, "_fiche_payload", lambda c: None)
	monkeypatch.setattr(ru.recrutement, "porteurs_effectifs", lambda *a: [])


def test_vendables_listent_le_contenu_des_contenants(boutique, maree, monkeypatch):
	perso = _perso(["item:pierre", _besace("item:pomme"),
					{"item": "item:sac_maree", "poids": 0.5, "contenu": ["item:pierre"]}])
	monkeypatch.setattr(ru, "now_epoch", lambda: 500)   # mer basse : le Sac de Manannán semble vide
	v = ru._marchand_vendables(perso, {"_id": "lieu:echoppe"})
	dedans = [e for e in v if e["contenant"]]
	assert [e["item_id"] for e in dedans] == ["item:pomme"]
	assert dedans[0]["index"] == 0 and dedans[0]["contenant"] == {
		"index": 1, "item_id": "item:besace", "nom": "Besace profonde"}
	# Les objets du sac restent listés sans bloc `contenant` (les contenants eux-mêmes aussi).
	assert sorted(e["item_id"] for e in v if not e["contenant"]) == ["item:besace", "item:pierre", "item:sac_maree"]


def test_vendre_un_objet_range_dans_un_contenant(boutique, monkeypatch):
	perso = _perso([_besace("item:pomme")])
	monkeypatch.setattr(ru, "_acteur", lambda _u, _b: (perso, perso))
	out = asyncio.run(ru.sell_item({"_id": "user:a"}, {
		"index": 0, "item_id": "item:pomme", "index_contenant": 0, "item_id_contenant": "item:besace"}))
	assert out["vendu"]["nom"] == "Pomme"
	# Vidé par la vente : la besace perd sa clé `contenu`, et se vend désormais elle-même.
	assert perso["inventaire"] == [{"item": "item:besace", "poids": 0.5}]
	with pytest.raises(HTTPException) as e:
		asyncio.run(ru.sell_item({"_id": "user:a"}, {
			"index": 0, "item_id": "item:pomme", "index_contenant": 0, "item_id_contenant": "item:besace"}))
	assert e.value.status_code == 422


def test_l_artisan_puise_dans_les_contenants_sans_confondre_deux_contenants(db, monkeypatch):
	"""Commande chez un artisan : les matières rangées se fournissent comme celles d'un sac de
	compagnon. Deux contenants ont chacun leur `_id` virtuel : la même position dans deux
	contenus ne se « retient » pas une seule fois pour les deux."""
	from routers import commande as rcmd
	from utils import commande as cmd_util
	perso = _perso([_besace("item:pierre"), _besace("item:pierre", "item:pomme")])
	sacs = contenants.avec_contenants([perso], db["docs"].get, 0)
	assert [s["_id"] for s in sacs[1:]] == ["character:a#0", "character:a#1"]
	trouves, manquants = cmd_util.emplacements_fournis([("item:pierre", 2)], sacs, db["docs"].get)
	assert not manquants and len(trouves) == 2
	cmd_util.retirer_fournitures(trouves)
	sauves = []
	monkeypatch.setattr(rcmd, "save_doc", lambda d: sauves.append(d) or d)
	rcmd._save_porteurs(perso, list({id(t["porteur"]): t["porteur"] for t in trouves}.values()))
	# Réécrit sur les références AVANT l'unique save du principal ; aucun sac virtuel sauvé.
	assert sauves == [perso]
	assert perso["inventaire"] == [{"item": "item:besace", "poids": 0.5}, _besace("item:pomme")]
