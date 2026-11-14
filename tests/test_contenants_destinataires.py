"""Contenants comme DESTINATAIRES (`utils/contenants.py` § Contenants comme destinataires).

Un contenant porté par le principal, un compagnon ou une monture reçoit comme un porteur de
plus : butin de combat (`/collect`, butin d'étage), objet du sol (🤝 → `pickup_item`), transfert
du panneau 👥 (`/groupe/transferer`). Ce que ces tests verrouillent :
1. L'objet rangé ne pèse rien pour le porteur ; seule la capacité du contenant borne.
2. Aucun contenant dans un autre ; refus ⇒ la source (sol, sac, butin) n'est pas amputée.
3. Marée basse : on dépose, on ne reprend pas ; la place est masquée (`libre` None).
4. Butin d'étage : en attente sur le snapshot (`butin_contenants`), rangé à la finalisation.
"""


import pytest
from fastapi import HTTPException

from models import character_stats
from routers import combat as rcombat
from routers import recrutement as rrec
from routers import user as ru
from utils import characters
from utils import combat as combat_util
from utils import contenants

from tests.test_combat_groupe import character, joueur_snap, monstre_snap, combat_doc

BESACE = {"_id": "item:besace", "type": "item", "nom": "Besace profonde", "icon": "👜", "slots": [],
		  "poids": 0.5, "contenant": {"capacite_kg": 10}}
SAC_MAREE = dict(BESACE, _id="item:sac_maree", nom="Sac de Manannán",
				 contenant={"capacite_kg": 500, "maree": True})
PIERRE = {"_id": "item:pierre", "type": "item", "nom": "Pierre", "slots": [], "poids": 4.0}
POMME = {"_id": "item:pomme", "type": "item", "nom": "Pomme", "slots": [], "poids": 0.2}
ITEMS = {d["_id"]: d for d in (BESACE, SAC_MAREE, PIERRE, POMME)}


@pytest.fixture
def docs(monkeypatch):
	base = dict(ITEMS)
	for mod in (characters, combat_util, ru, rrec, rcombat):
		monkeypatch.setattr(mod, "get_doc", base.get, raising=False)
	return base


@pytest.fixture
def maree_basse(monkeypatch):
	"""Période 1 000 s, fenêtre 200 s, pleine mer à t = 0 ; `time.time()` → 500 (mer basse)."""
	monkeypatch.setattr(character_stats, "MAREE_PERIODE_S", 1000)
	monkeypatch.setattr(character_stats, "MAREE_FENETRE_S", 200)
	monkeypatch.setattr(character_stats, "MAREE_REFERENCE_EPOCH", 0)
	monkeypatch.setattr("time.time", lambda: 500)


# ── Pur ──────────────────────────────────────────────────────────────────────────

def test_destinations_dans_l_ordre_des_porteurs(docs):
	principal = character(inventaire=["item:pierre", {"item": "item:besace", "contenu": ["item:pierre"]}])
	ane = {"_id": "monture:ane", "nom": "Grison", "inventaire": [{"item": "item:besace", "nom_perso": "Fonte"}]}
	out = contenants.destinations([principal, ane], docs.get, 0)
	assert [c["cle"] for c in out] == ["character:u_1#1", "monture:ane#0"]
	assert out[0]["charge_kg"] == 4.0 and out[0]["libre"] == 6.0 and out[0]["porteur_nom"] == "Test Héros"
	assert out[1]["nom"] == "Fonte" and out[1]["libre"] == 10


def test_destinations_en_attente_et_maree_masquee(docs, maree_basse):
	p = character(inventaire=[{"item": "item:besace"}, {"item": "item:sac_maree"}])
	besace, sac = contenants.destinations([p], docs.get, 500, en_attente={"character:u_1#0": 3})
	assert besace["libre"] == 7.0
	assert sac["accessible"] is False and sac["libre"] is None and sac["charge_kg"] is None


def test_deposer_refuse_plein_emboitement_et_lui_meme(docs):
	p = character(inventaire=[{"item": "item:besace"}, {"item": "item:besace"}])
	ok, raison, _ = contenants.deposer(p, 0, "item:besace", p["inventaire"][1], docs.get)
	assert not ok and "autre" in raison
	ok, _r, ref_c = contenants.deposer(p, 0, "item:besace", {"item": "item:pierre", "poids": 4}, docs.get)
	assert ok and p["inventaire"][0] is ref_c and ref_c["contenu"] == [{"item": "item:pierre", "poids": 4}]
	contenants.deposer(p, 0, "item:besace", {"item": "item:pierre", "poids": 4}, docs.get)
	ok, raison, _ = contenants.deposer(p, 0, "item:besace", {"item": "item:pierre", "poids": 4}, docs.get)
	assert not ok and "plein" in raison
	assert not contenants.deposer(p, 0, "item:besace", p["inventaire"][0], docs.get)[0]
	assert not contenants.deposer(p, 5, "item:inconnu", "item:pomme", docs.get)[0]


def test_peut_recevoir_cumule_les_lignes(docs):
	ref_c = {"item": "item:besace", "contenu": [{"item": "item:pierre", "poids": 4}]}
	deux = [{"item": "item:pierre", "poids": 3}] * 2
	assert contenants.peut_recevoir(ref_c, BESACE, deux, docs.get)[0]
	assert not contenants.peut_recevoir(ref_c, BESACE, deux, docs.get, deja_kg=1)[0]
	assert not contenants.peut_recevoir(ref_c, BESACE, [{"item": "item:besace"}], docs.get)[0]


def test_retirer_refuse_a_maree_basse(docs, maree_basse):
	p = character(inventaire=[{"item": "item:sac_maree", "contenu": ["item:pomme"]}])
	ok, raison, _ = contenants.retirer(p, 0, "item:sac_maree", 0, "item:pomme", docs.get, 500)
	assert not ok and "mer" in raison
	ok, _r, ref = contenants.retirer(p, 0, "item:sac_maree", 0, "item:pomme", docs.get, 0)
	assert ok and ref == "item:pomme" and "contenu" not in p["inventaire"][0]


# ── Sol → contenant (`pickup_item`) ─────────────────────────────────────────────

def _pickup(monkeypatch, acteur, principal, body, compagnons=()):
	monkeypatch.setattr(ru, "_acteur", lambda _u, _b: (acteur, principal))
	monkeypatch.setattr(ru, "_save_acteur", lambda porteur, p: None)
	monkeypatch.setattr(ru.recrutement, "porteurs_effectifs", lambda c, g: list(compagnons))
	return ru.pickup_item({"_id": "user:u"}, body)


def test_ramasser_dans_le_contenant_d_un_compagnon(docs, monkeypatch):
	av = {"_id": "aventurier:ami", "prenom": "Ami", "nom": "", "inventaire": [{"item": "item:besace"}]}
	p = character(objets_au_sol=[{"item": "item:pierre", "poids": 4}])
	out = _pickup(monkeypatch, p, p, {"index": 0, "item_id": "item:pierre", "destinataire_id": av["_id"],
									  "contenant_index": 0, "contenant_item_id": "item:besace"}, [av])
	assert p["objets_au_sol"] == [] and av["inventaire"][0]["contenu"] == [{"item": "item:pierre", "poids": 4}]
	assert out["destinataire"]["id"] == av["_id"] and out["pris"]["nom"] == "Pierre"
	# Rangé = sans poids pour le compagnon.
	assert characters.carried_weight(av) == 0.5


def test_ramasser_dans_son_propre_contenant_refus_garde_le_sol(docs, monkeypatch):
	p = character(inventaire=[{"item": "item:besace", "contenu": [{"item": "item:pierre", "poids": 8}]}],
				  objets_au_sol=[{"item": "item:pierre", "poids": 4}])
	with pytest.raises(HTTPException) as e:
		_pickup(monkeypatch, p, p, {"index": 0, "item_id": "item:pierre",
									"contenant_index": 0, "contenant_item_id": "item:besace"})
	assert e.value.status_code == 409 and len(p["objets_au_sol"]) == 1


def test_ramasser_pour_un_contenant_hors_du_groupe_est_refuse(docs, monkeypatch):
	p = character(objets_au_sol=["item:pomme"])
	with pytest.raises(HTTPException) as e:
		_pickup(monkeypatch, p, p, {"index": 0, "item_id": "item:pomme", "destinataire_id": "aventurier:x",
									"contenant_index": 0, "contenant_item_id": "item:besace"})
	assert e.value.status_code == 403


# ── Panneau 👥 (`/groupe/transferer`) ────────────────────────────────────────────

def _transferer(monkeypatch, p, body, porteurs=()):
	monkeypatch.setattr(rrec, "get_selected_character", lambda u: p)
	monkeypatch.setattr(rrec, "_porteurs_du_groupe", lambda c: list(porteurs))
	monkeypatch.setattr(rrec, "save_doc", lambda d: d)
	monkeypatch.setattr(rrec, "_inventory_payload", lambda c, s=None: {"inventaire": list(c.get("inventaire") or [])})
	monkeypatch.setattr(rrec, "_fiche_payload", lambda c: None)
	return rrec.groupe_transferer({"_id": "user:u"}, body)


def test_transferer_vers_son_propre_contenant_recalcule_la_cle(docs, monkeypatch):
	p = character(inventaire=["item:pomme", {"item": "item:besace"}])
	out = _transferer(monkeypatch, p, {"compagnon_id": p["_id"], "contenant_index": 1,
									   "contenant_item_id": "item:besace", "sens": "vers_compagnon",
									   "index": 0, "item_id": "item:pomme"})
	assert p["inventaire"] == [{"item": "item:besace", "contenu": ["item:pomme"]}]
	assert out["contenant_cle"] == "character:u_1#0"
	assert [c["cle"] for c in out["contenants"]] == ["character:u_1#0"]


def test_transferer_du_contenant_d_une_monture_vers_le_principal(docs, monkeypatch):
	ane = {"_id": "monture:ane", "nom": "Grison",
		   "inventaire": [{"item": "item:besace", "contenu": [{"item": "item:pierre", "poids": 4}]}]}
	p = character()
	_transferer(monkeypatch, p, {"compagnon_id": ane["_id"], "contenant_index": 0,
								 "contenant_item_id": "item:besace", "sens": "vers_principal",
								 "index": 0, "item_id": "item:pierre"}, [ane])
	assert p["inventaire"] == [{"item": "item:pierre", "poids": 4}]
	assert ane["inventaire"] == [{"item": "item:besace"}]


def test_transferer_un_contenant_dans_un_contenant_est_refuse(docs, monkeypatch):
	ane = {"_id": "monture:ane", "nom": "Grison", "inventaire": [{"item": "item:besace"}]}
	p = character(inventaire=["item:besace"])
	with pytest.raises(HTTPException) as e:
		_transferer(monkeypatch, p, {"compagnon_id": ane["_id"], "contenant_index": 0,
									 "contenant_item_id": "item:besace", "sens": "vers_compagnon",
									 "index": 0, "item_id": "item:besace"}, [ane])
	assert e.value.status_code == 409 and p["inventaire"] == ["item:besace"]


# ── Butin de combat ──────────────────────────────────────────────────────────────

def _victoire(docs, perso, poids=4):
	docs[perso["_id"]] = perso
	doc = combat_doc([joueur_snap("joueur_0", perso["_id"], charge=0, charge_max=150)],
					 [monstre_snap("monstre_0", vivant=False), monstre_snap("monstre_1", vivant=False)],
					 status="victoire")
	doc["_id"] = "combat:1"
	doc["user_id"] = "user:u"
	doc["character_id"] = perso["_id"]
	doc["butin_disponible"] = [
		{"monstre_id": m, "item_id": "item:pierre", "nom": "Pierre", "poids": poids} for m in ("monstre_0", "monstre_1")]
	docs["combat:1"] = doc
	return doc


def _collect(monkeypatch, docs, attributions):
	monkeypatch.setattr(rcombat, "save_doc", lambda d: d)
	monkeypatch.setattr(rcombat, "verser_butin_au_sol", lambda c, cd, deja=None: [])
	body = rcombat.CollectLootRequest(attributions=[rcombat.LootAttribution(**a) for a in attributions])
	return rcombat.collect_loot("combat:1", body, {"_id": "user:u"})


def test_collect_range_dans_un_contenant(docs, monkeypatch):
	perso = character(inventaire=[{"item": "item:besace"}])
	_victoire(docs, perso)
	a = {"monstre_id": "monstre_0", "beneficiaire_id": perso["_id"],
		 "contenant_index": 0, "contenant_item_id": "item:besace"}
	out = _collect(monkeypatch, docs, [a, dict(a, monstre_id="monstre_1")])
	assert out["collected"] == ["Pierre", "Pierre"]
	assert perso["inventaire"] == [{"item": "item:besace", "contenu": [{"item": "item:pierre", "poids": 4}] * 2}]


def test_collect_refuse_un_contenant_trop_plein_sans_rien_encaisser(docs, monkeypatch):
	perso = character(inventaire=[{"item": "item:besace"}])
	_victoire(docs, perso, poids=6)
	a = {"monstre_id": "monstre_0", "beneficiaire_id": perso["_id"],
		 "contenant_index": 0, "contenant_item_id": "item:besace"}
	with pytest.raises(HTTPException) as e:
		_collect(monkeypatch, docs, [a, dict(a, monstre_id="monstre_1")])
	assert e.value.status_code == 422 and perso["inventaire"] == [{"item": "item:besace"}]


def test_vue_client_liste_les_contenants_a_la_victoire_seulement(docs):
	perso = character(inventaire=[{"item": "item:besace"}])
	doc = _victoire(docs, perso)
	assert [c["cle"] for c in combat_util.contenants_butin(doc)] == ["character:u_1#0"]
	assert combat_util.contenants_butin(doc)[0]["character_id"] == perso["_id"]
	doc["status"] = "active"
	assert combat_util.contenants_butin(doc) == []


def test_butin_d_etage_en_attente_puis_range_a_la_finalisation(docs, monkeypatch):
	perso = character(inventaire=[{"item": "item:besace"}])
	docs[perso["_id"]] = perso
	snap = joueur_snap("joueur_0", perso["_id"], charge=0, charge_max=150)
	doc = combat_doc([snap], [monstre_snap("monstre_0", vivant=False)])
	doc["etages"] = {"etage": "lieu:e1"}
	monkeypatch.setattr(combat_util, "_ensure_loot_item", lambda *a: PIERRE)
	dispo = [{"monstre_id": "monstre_0", "item_id": "item:pierre", "nom": "Pierre", "poids": 7}]
	a = {"monstre_id": "monstre_0", "beneficiaire_id": perso["_id"],
		 "contenant_index": 0, "contenant_item_id": "item:besace"}
	assert combat_util._repartir_butin_d_etage(doc, dispo, [a]) is None
	assert snap["charge"] == 0 and snap["butin_contenants"][0]["refs"] == [{"item": "item:pierre", "poids": 7}]
	# La place promise compte : une seconde ligne de 7 kg ne tient plus.
	assert "plein" in combat_util._repartir_butin_d_etage(doc, dispo, [a])
	monkeypatch.setattr(combat_util, "save_doc", lambda d: d)
	combat_util._finalize_membre(doc, snap, perso, "fuite")
	assert perso["inventaire"][0]["contenu"] == [{"item": "item:pierre", "poids": 7}]


def test_contenant_introuvable_a_la_finalisation_le_butin_va_au_sac(docs):
	doc_perso = character(inventaire=[])
	snap = {"butin_contenants": [{"index": 0, "item_id": "item:besace", "refs": ["item:pomme"]}]}
	assert combat_util.verser_butin_contenants(snap, doc_perso) == []
	assert doc_perso["inventaire"] == ["item:pomme"]


def _descente(docs, monkeypatch, inventaire):
	perso = character(inventaire=inventaire)
	docs[perso["_id"]] = perso
	snap = joueur_snap("joueur_0", perso["_id"], charge=0, charge_max=150)
	doc = combat_doc([snap], [monstre_snap("monstre_0", vivant=False)])
	doc["etages"] = {"etage": "lieu:e1"}
	monkeypatch.setattr(combat_util, "_ensure_loot_item", lambda *a: PIERRE)
	monkeypatch.setattr(combat_util, "save_doc", lambda d: d)
	dispo = [{"monstre_id": "monstre_0", "item_id": "item:pierre", "nom": "Pierre", "poids": 7}]
	return perso, snap, doc, dispo


def _vers(perso, index):
	return {"monstre_id": "monstre_0", "beneficiaire_id": perso["_id"],
			"contenant_index": index, "contenant_item_id": "item:besace"}


def test_objet_retire_entre_deux_etages_la_place_promise_compte_encore(docs, monkeypatch):
	"""Havresac de Zora Scarmouche (dump du 14/11) : un piège posé AVANT le contenant décalait
	sa position ; la place promise à l'étage précédent n'était plus comptée."""
	perso, snap, doc, dispo = _descente(docs, monkeypatch, ["item:pomme", {"item": "item:besace"}])
	assert combat_util._repartir_butin_d_etage(doc, dispo, [_vers(perso, 1)]) is None
	perso["inventaire"].pop(0)   # piège posé / remède bu : sauvé aussitôt en combat
	assert combat_util.contenants_butin(dict(doc, status="victoire"))[0]["libre"] == 3.0
	assert "plein" in combat_util._repartir_butin_d_etage(doc, dispo, [_vers(perso, 0)])
	combat_util._finalize_membre(doc, snap, perso, "victoire")
	assert perso["inventaire"][0]["contenu"] == [{"item": "item:pierre", "poids": 7}]


def test_deux_contenants_identiques_le_rang_garde_le_bon(docs, monkeypatch):
	perso, snap, doc, dispo = _descente(
		docs, monkeypatch, [{"item": "item:besace"}, "item:pomme", {"item": "item:besace"}])
	assert combat_util._repartir_butin_d_etage(doc, dispo, [_vers(perso, 2)]) is None
	perso["inventaire"].pop(1)
	combat_util._finalize_membre(doc, snap, perso, "victoire")
	assert "contenu" not in perso["inventaire"][0]
	assert perso["inventaire"][1]["contenu"] == [{"item": "item:pierre", "poids": 7}]


def test_finalisation_l_excedent_d_un_contenant_tombe_au_sol(docs, monkeypatch):
	perso = character(inventaire=[{"item": "item:besace", "contenu": [{"item": "item:pierre", "poids": 8}]}])
	snap = {"butin_contenants": [{"index": 0, "item_id": "item:besace", "rang": 0,
								  "refs": [{"item": "item:pomme", "poids": 1}, {"item": "item:pierre", "poids": 4}]}]}
	monkeypatch.setattr(combat_util, "save_doc", lambda d: d)
	combat_util._finalize_membre({"_id": "combat:x", "joueurs": [snap]}, snap, perso, "fuite")
	assert perso["inventaire"][0]["contenu"][-1] == {"item": "item:pomme", "poids": 1}
	assert perso["objets_au_sol"] == [{"item": "item:pierre", "poids": 4}]
	# Compagnon : son excédent tombe au sol du PRINCIPAL.
	comp = dict(character(inventaire=[{"item": "item:besace", "contenu": [{"item": "item:pierre", "poids": 10}]}]),
				_id="aventurier:a")
	principal = character(inventaire=[])
	combat_util._finalize_membre({"_id": "combat:x", "joueurs": [snap]}, snap, comp, "fuite", principal=principal)
	assert len(principal["objets_au_sol"]) == 2 and "objets_au_sol" not in comp
