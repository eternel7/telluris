"""Endpoints 🔎 (`routers/renseignement.py`) sur une base en mémoire, avec le VRAI doc
`rules:renseignement` du générateur — ce que la logique pure ne voit pas : enchaînement des
gardes, débit, délai, carnet, note, PV de l'acteur. Gabarit de `tests/test_auberge_endpoints.py`."""

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_renseignement  # noqa: E402
from models import character_stats  # noqa: E402
from utils import focalisation  # noqa: E402

LIEUX = [
	{"_id": "lieu:france", "type": "lieu", "label": "France", "categorie": "pays",
	 "rencontres": [{"espece": "espece:loup", "zones": ["zone:foret"]}],
	 "ressources": [{"ressource": "item:Herbe", "zones": ["zone:foret"]}]},
	{"_id": "lieu:cite", "type": "lieu", "label": "Lutèce", "categorie": "ville", "lieu_parent": "lieu:france"},
	{"_id": "lieu:auberge", "type": "lieu", "label": "Au Lion d'or", "categorie": "auberge", "lieu_parent": "lieu:cite"},
	{"_id": "lieu:scripto", "type": "lieu", "label": "Le Scriptorium", "categorie": "scriptorium",
	 "lieu_parent": "lieu:cite"},
]
LIENS = [
	{"_id": "link:1", "type": "connection", "nodes": [{"lieu": "lieu:auberge", "pos": [1, 1]}, {"lieu": "lieu:cite", "pos": [2, 2]}]},
	{"_id": "link:2", "type": "connection", "nodes": [{"lieu": "lieu:cite", "pos": [3, 3]}, {"lieu": "lieu:france", "pos": [4, 4]}]},
	{"_id": "link:3", "type": "connection", "nodes": [{"lieu": "lieu:scripto", "pos": [1, 1]}, {"lieu": "lieu:cite", "pos": [5, 5]}]},
]
AUTRES = [
	{"_id": "espece:loup", "type": "espece", "nom": "Loup", "tags": ["animal", "predateur"]},
	{"_id": "zone:foret", "type": "zone_influence", "nom": "Forêt profonde", "terrain_tags": ["foret"]},
	{"_id": "item:Herbe", "type": "item", "nom": "Herbe", "sous_categorie": "herbe", "poids": 0.1},
]
CARACTS = {"V": 5, "F": 30, "R": 20, "Ag": 20, "Vol": 20, "Int": 40, "Cha": 30, "Ch": 20}


def _perso(voc, lieu="lieu:auberge", **champs):
	base = {"_id": "character:u_1", "type": "character", "voc": voc, "prenom": "Bran", "lieu": lieu,
			"inventaire": [], "slots": {}, "groupe": [], "montures": [],
			"caracteristiques_current": dict(CARACTS), "currentPV": 20, "currentPM": 10,
			"or": 0, "argent": 1, "cuivre": 0}
	base.update(champs)
	return base


class De:
	def __init__(self, jets):
		self.jets = list(jets)

	def randint(self, a, b):
		return self.jets.pop(0) if self.jets else a

	def random(self):
		return 0.0

	def choice(self, seq):
		return list(seq)[0]

	def choices(self, seq, weights=None, k=1):
		return [list(seq)[0]]


@pytest.fixture
def monde(monkeypatch):
	from routers import renseignement as rr
	from utils import characters, marche
	docs = {d["_id"]: d for d in LIEUX + LIENS + AUTRES + gen_renseignement.docs()}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def find_docs_fn(selector, fields=None):
		return [d for d in list(docs.values()) if all(d.get(k) == v for k, v in (selector or {}).items())]

	from utils import recrutement
	for mod in (rr, characters, marche, recrutement):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
	monkeypatch.setattr(rr, "_rang", lambda eid: "E" if eid == "espece:loup" else None)
	focalisation.reset_graphe_cache()
	yield {"docs": docs, "rr": rr}
	focalisation.reset_graphe_cache()


def _appel(monde, character, fn, *args, jets=()):
	rr = monde["rr"]
	monde["docs"][character["_id"]] = character
	origine, origine_rand = rr.get_selected_character, rr._hasard
	try:
		rr.get_selected_character = lambda _u: character
		rr._hasard = lambda: De(jets)
		resultat = fn(None, *args)
		return asyncio.run(resultat) if asyncio.iscoroutine(resultat) else resultat
	finally:
		rr.get_selected_character = origine
		rr._hasard = origine_rand


def test_offre_du_guerrier_en_taverne(monde):
	data = _appel(monde, _perso("guerrier"), monde["rr"].offre)
	assert [m["id"] for m in data["methodes"]] == ["veterans"]
	assert monde["rr"].disponible(_perso("guerrier"))
	assert not monde["rr"].disponible(_perso("lettre"))     # aucune méthode, pas d'informateur


def test_belle_reussite_du_guerrier_bestiaire_carnet_xp_cout_et_delai(monde):
	rr, c = monde["rr"], _perso("guerrier")
	data = _appel(monde, c, rr.chercher, {"methode": "veterans", "mode": "libre", "cible": "espece:loup"}, jets=[1])
	r = data["resultat"]
	assert r["niveau"] == "exact" and "Forêt profonde" in r["texte"] and "rang E" in r["texte"]
	assert r["xp"] == character_stats.RENS_XP_BELLE
	m = next(x for x in gen_renseignement.METHODES if x["id"] == "veterans")
	assert r["cout"] == round(m["cout"] * character_stats.RENS_COUT_MULT["exact"])
	assert c["bestiaire"]["espece:loup"]["lieux"][0]["oui_dire"] is True
	assert c["journal"][-1]["texte"] == r["texte"]
	assert data["fiche"]["id"] == c["_id"]
	with pytest.raises(HTTPException) as e:
		_appel(monde, c, rr.chercher, {"methode": "veterans", "mode": "libre", "cible": "espece:loup"})
	assert e.value.status_code == 409


def test_le_guerrier_ne_cherche_pas_de_ressource(monde):
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso("guerrier"), monde["rr"].chercher,
			   {"methode": "veterans", "mode": "libre", "cible": "item:Herbe"})
	assert e.value.status_code == 422


def test_le_lettre_ecrit_une_note_et_la_lire_l_apprend(monde):
	rr, c = monde["rr"], _perso("lettre", lieu="lieu:scripto")
	data = _appel(monde, c, rr.chercher, {"methode": "registres", "mode": "libre", "cible": "espece:loup"}, jets=[50])
	assert data["resultat"]["niveau"] == "region" and data["resultat"]["note"]
	ref = c["inventaire"][-1]
	assert ref["item"] == "item:note_renseignement" and "France" in ref["piste"]["texte"]
	autre = _perso("guerrier", inventaire=[ref])
	autre["_id"] = "character:u_2"
	lu = _appel(monde, autre, rr.lire, {"index": 0})
	assert lu["appris"] and autre["bestiaire"]["espece:loup"]["lieux"][0]["id"] == "lieu:france"


def test_le_bras_de_fer_coute_des_pv_jamais_sous_un(monde):
	rr, c = monde["rr"], _perso("barbare", currentPV=2)
	monkey = rr._rang
	rr._rang = lambda eid: "C"
	try:
		data = _appel(monde, c, rr.chercher, {"methode": "bras_de_fer", "mode": "libre", "cible": "espece:loup"},
					  jets=[99, 100, 6])
	finally:
		rr._rang = monkey
	assert data["resultat"]["pv_perdus"] >= 1 and c["currentPV"] == 1


def test_echec_rumeur_sans_bestiaire(monde):
	rr, c = monde["rr"], _perso("guerrier")
	data = _appel(monde, c, rr.chercher, {"methode": "veterans", "mode": "libre", "cible": "espece:loup"},
				  jets=[100, 100])
	assert data["resultat"]["niveau"] == "rumeur"
	assert "bestiaire" not in c and len(c["journal"]) == 1


def test_bourse_trop_legere(monde):
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso("guerrier", argent=0), monde["rr"].chercher,
			   {"methode": "veterans", "mode": "libre", "cible": "espece:loup"})
	assert e.value.status_code == 409


def test_catalogue_filtre_par_methode(monde):
	rr = monde["rr"]
	c = _perso("lettre", lieu="lieu:scripto")
	data = _appel(monde, c, rr.catalogue, "registres", "her")
	assert [s["id"] for s in data["suggestions"]] == ["item:Herbe"]
	c = _perso("guerrier")
	assert _appel(monde, c, rr.catalogue, "veterans", "her")["suggestions"] == []


# ── Salle commune de guilde ──────────────────────────────────────────────────────

GUILDE = [
	{"_id": "lieu:reception", "type": "lieu", "label": "La Halle - réception", "categorie": "guilde_aventurier",
	 "lieu_parent": "lieu:cite"},
	{"_id": "lieu:comptoir", "type": "lieu", "label": "La Halle - comptoir", "categorie": "guilde_aventurier_comptoir",
	 "lieu_parent": "lieu:cite"},
	{"_id": "link:4", "type": "connection", "nodes": [{"lieu": "lieu:reception", "pos": [1, 1]}, {"lieu": "lieu:cite", "pos": [6, 6]}]},
	{"_id": "link:5", "type": "connection", "nodes": [{"lieu": "lieu:comptoir", "pos": [1, 1]}, {"lieu": "lieu:cite", "pos": [7, 7]}]},
	{"_id": "pnj:cynan", "type": "pnj", "nom": "Cynan", "services": {"renseignement": {"noeuds": {"ouvre": "x"}}}},
	{"_id": "aventurier:r1", "type": "aventurier", "statut": "offert", "giver": "lieu:reception", "prenom": "Ysolde",
	 "voc": "guerrier", "xp_total": 0, "caracteristiques_current": dict(CARACTS)},
	{"_id": "espece:dragon", "type": "espece", "nom": "Dragon", "tags": ["monstre"]},
]


@pytest.fixture
def guilde(monde):
	for d in GUILDE:
		monde["docs"][d["_id"]] = d
	france = monde["docs"]["lieu:france"]
	france["rencontres"] = france["rencontres"] + [{"espece": "espece:dragon", "zones": ["zone:foret"]}]
	monde["rr"]._rang = lambda eid: {"espece:loup": "F", "espece:dragon": "B"}.get(eid)
	return monde


def test_les_recrues_renseignent_a_la_reception_et_le_bouton_s_affiche(guilde):
	rr, c = guilde["rr"], _perso("lettre", lieu="lieu:reception")
	data = _appel(guilde, c, rr.offre)
	recrue = next(m for m in data["methodes"] if m["interlocuteur"] == "recrue")
	assert recrue["cle"] == "recrues|aventurier:r1" and "Ysolde" in recrue["nom"]
	dangers = {s["id"]: s for s in recrue["cibles"]["dangers"]}
	assert dangers["espece:loup"]["bloque"] is None
	assert "dépasse" in dangers["espece:dragon"]["bloque"]        # recrue de rang F, dragon de rang B
	assert rr.disponible(c)


def test_une_recrue_qui_a_affronte_donne_le_lieu_exact_contre_un_pourboire(guilde):
	rr, c = guilde["rr"], _perso("lettre", lieu="lieu:reception")
	data = _appel(guilde, c, rr.chercher, {"methode": "recrues", "interlocuteur": "aventurier:r1",
										   "mode": "dangers", "cible": "espece:loup"})
	r = data["resultat"]
	assert r["niveau"] == "exact" and "affronté" in r["texte"]       # seule espèce à sa mesure : affrontée
	assert r["cout"] == rr.rens.cout_recrue("exact", 0) and r["affinite"] == character_stats.RENS_RECRUE_AFFINITE
	assert c["affinites"]["aventurier:r1"] > 0
	assert c["bestiaire"]["espece:loup"]["lieux"][0]["oui_dire"]


def test_sujet_bloque_rien_paye_aucun_delai(guilde):
	rr, c = guilde["rr"], _perso("lettre", lieu="lieu:reception")
	avant = rr.money_to_cuivre(c)
	with pytest.raises(HTTPException) as e:
		_appel(guilde, c, rr.chercher, {"methode": "recrues", "interlocuteur": "aventurier:r1",
										"mode": "dangers", "cible": "espece:dragon"})
	assert e.value.status_code == 403
	assert rr.money_to_cuivre(c) == avant and not c.get("renseignements_at")


def test_le_receptionniste_au_comptoir_via_son_dialogue(guilde):
	rr = guilde["rr"]
	c = _perso("lettre", lieu="lieu:comptoir", pnj_present={"lieu": "lieu:comptoir", "characters": ["pnj:cynan"]},
			   rangs_guilde={"lieu:cite": "C"})
	assert not rr.disponible(c)                                   # pas de bouton : on passe par Cynan
	data = _appel(guilde, c, rr.offre)
	m = data["methodes"][0]
	assert m["cle"] == "receptionniste|pnj:cynan" and m["cout_max"] == 0
	assert all(s["bloque"] is None for s in m["cibles"]["dangers"])   # rang C ≥ B − 1
	data = _appel(guilde, c, rr.chercher, {"methode": "receptionniste", "interlocuteur": "pnj:cynan",
										   "mode": "dangers", "cible": "espece:dragon"}, jets=[1])
	assert data["resultat"]["niveau"] == "exact" and data["resultat"]["cout"] == 0
	assert data["resultat"]["xp"] == character_stats.RENS_XP_BELLE
	with pytest.raises(HTTPException) as e:                        # délai PAR interlocuteur
		_appel(guilde, c, rr.chercher, {"methode": "receptionniste", "interlocuteur": "pnj:cynan",
										"mode": "dangers", "cible": "espece:loup"})
	assert e.value.status_code == 409


def test_rang_du_joueur_trop_bas_pour_le_receptionniste(guilde):
	rr = guilde["rr"]
	c = _perso("lettre", lieu="lieu:comptoir", pnj_present={"lieu": "lieu:comptoir", "characters": ["pnj:cynan"]})
	m = _appel(guilde, c, rr.offre)["methodes"][0]
	assert "Pas pour votre rang" in {s["id"]: s for s in m["cibles"]["dangers"]}["espece:dragon"]["bloque"]


def test_quete_de_visite_donne_le_lieu_au_carnet(guilde):
	rr = guilde["rr"]
	q = {"id": "q1", "titre": "Visiter la France", "objectif": {"type": "visite", "cible": "lieu:france", "quantite": 1}}
	c = _perso("lettre", lieu="lieu:comptoir", pnj_present={"lieu": "lieu:comptoir", "characters": ["pnj:cynan"]},
			   quetes_actives=[q])
	data = _appel(guilde, c, rr.chercher, {"methode": "receptionniste", "interlocuteur": "pnj:cynan",
										   "mode": "quete", "quete_id": "q1"}, jets=[50])
	assert "« France »" in data["resultat"]["texte"] and "bestiaire" not in c
