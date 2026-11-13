"""Endpoints de la voie de colonisation (`routers/colonisation.py`).

Ce que la logique pure ne voit pas :
1. **Fonder crée DEUX docs** — l'implantation et sa connexion depuis la case du pays — et
   débite la charte ; l'implantation part en base SANS grille (lien pur au modèle).
2. **Les rôles gardent les routes** : le visiteur lit et donne, le fondateur décide.
3. **Changer de palier** déplace le nœud de la connexion et le personnage sur la première
   entrée du nouveau modèle.

Base en mémoire qui applique le VRAI point unique de `db/config.py` (`suivre_modele` à la
lecture, `sans_modele` à l'écriture). Règles et modèles bâtis par le générateur."""

import asyncio
import copy
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_colonisation as gen  # noqa: E402

from db import config as db_config  # noqa: E402
from utils import characters as characters_util  # noqa: E402
from utils import colonisation as col  # noqa: E402
from utils import marche  # noqa: E402
from utils import proprietes  # noqa: E402
from utils.characters import money_to_cuivre  # noqa: E402

W, H = 30, 20
PAYS = {"_id": "lieu:pays", "type": "lieu", "categorie": "pays", "label": "Pays", "tags": [],
		"dimensions": {"x": W, "y": H}, "cells": [[1] * W for _ in range(H)],
		"zone_influences": [{"x": 20, "y": 10, "w": 8, "h": 8, "rot": 0, "forme": "rectangle", "zone": "zone:foret"}],
		"rencontres": [{"espece": "espece:loup", "zones": ["zone:foret"]}]}
ZONE = {"_id": "zone:foret", "type": "zone_influence", "terrain_tags": ["foret"], "modificateurs": {"danger": 1}}
CITE = {"_id": "lieu:cite", "type": "lieu", "categorie": "ville", "label": "Cité"}
LIEN_CITE = {"_id": "link:cite", "type": "connection",
			 "nodes": [{"lieu": "lieu:pays", "pos": [5, 5]}, {"lieu": "lieu:cite", "pos": [0, 0]}]}
PAIN = {"_id": "item:pain", "type": "item", "nom": "Pain", "categorie": "consommable",
		"sous_categorie": "boulangerie", "slots": [], "poids": 2.0, "rarete": "commun"}
EPEE_SAC = {"_id": "item:epee", "type": "item", "nom": "Épée", "categorie": "arme", "sous_categorie": "",
		"slots": ["main_droite"], "tags": ["cac"], "poids": 2.0, "rarete": "commun"}
METIERS = {"_id": "rules:proprietes", "type": "rules", "value": {"types": [], "amenagements": [], "metiers": [
	{"id": "garde", "label": "Garde", "cout_embauche_cuivre": 800},
	{"id": "medecin", "label": "Médecin", "cout_embauche_cuivre": 2000},
	{"id": "intendant", "label": "Intendant", "cout_embauche_cuivre": 1500},
	{"id": "marchand", "label": "Marchand", "cout_embauche_cuivre": 1200}]}}
# Combat de la colonisation : l'équipement standard du garde et l'espèce de la menace (dump).
EPEE = {"_id": "item:Epee_courte", "type": "item", "nom": "Épée courte", "categorie": "arme", "sous_categorie": "",
		"slots": ["main_droite", "main_gauche"], "bonus_cc": 1, "bonus_degats": 2, "bonus_degats_dice": 4,
		"poids": 1.5, "tags": ["cac", "tranchant"], "portee": 1, "rarete": "commun"}
GAMBISON = {"_id": "item:Armure_matelassee", "type": "item", "nom": "Armure matelassée", "categorie": "armure",
			"sous_categorie": "", "slots": ["torse"], "poids": [3, 5], "tags": [], "bonus_pa": 5, "bonus": {"Ag": -2},
			"rarete": "commun"}
LOUP = {"_id": "espece:loup", "type": "espece", "nom": "Loup", "genre": "m", "image": "loup_transparent.png",
		"base_attributes": {k: {"min": a, "max": b} for k, (a, b) in {"V": (4, 6), "F": (20, 35), "R": (20, 35),
							"Ag": (35, 60), "Vol": (15, 30), "Int": (10, 20), "Cha": (0, 0), "Ch": (5, 15)}.items()},
		"tags": ["animal", "predateur"], "proprietes": {}}
NOVICE = {"_id": "profil:novice", "type": "profil", "niveau": 1, "nom": "Novice",
		  "attributs_modifier": {k: {"min": 0, "max": 5} for k in ("F", "R", "Ag", "Vol", "Int", "Cha", "Ch")},
		  "bonus_skills": []}
CARACTS = {"V": 5, "F": 40, "R": 40, "Ag": 40, "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40}


def _perso(ident="a", **champs):
	base = {"_id": f"character:{ident}", "type": "character", "lieu": "lieu:pays",
			"position": {"x": 20, "y": 10}, "prenom": "Greta" if ident == "a" else "Milo", "nom": "",
			"cite": "lieu:cite", "inventaire": [], "slots": {}, "groupe": [], "montures": [],
			"caracteristiques_current": dict(CARACTS), "currentPV": 1, "currentPM": 0,
			"rangs_guilde": {"lieu:cite": "C"}, "or": 100, "argent": 0, "cuivre": 0,
			col.CHAMP_CHARTE: {"cite": "lieu:cite", "label": "Cité"}}
	base.update(champs)
	return base


@pytest.fixture
def monde(monkeypatch):
	from routers import colonisation as rc
	from routers import user as ru

	docs = {d["_id"]: copy.deepcopy(d) for d in [*gen.generer({}), PAYS, ZONE, CITE, LIEN_CITE, PAIN, EPEE_SAC, METIERS, EPEE,
												 GAMBISON, LOUP, NOVICE]}

	def brut(doc_id):
		return copy.deepcopy(docs.get(doc_id))

	def get_doc_fn(doc_id):
		return db_config.suivre_modele(brut(doc_id), brut)

	def save_doc_fn(doc):
		docs[doc["_id"]] = copy.deepcopy(db_config.sans_modele(doc))
		return doc

	def _correspond(d, selecteur):
		for k, v in (selecteur or {}).items():
			if isinstance(v, dict) and "$elemMatch" in v:
				if v["$elemMatch"].get("$eq") not in (d.get(k) or []):
					return False
			elif d.get(k) != v:
				return False
		return True

	def find_docs_fn(selecteur, fields=None):
		return [copy.deepcopy(d) for d in docs.values() if _correspond(d, selecteur)]

	from utils import combat as combat_util
	for mod in (rc, ru, characters_util, proprietes, marche, combat_util):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
	monkeypatch.setattr(rc, "connexions_du_lieu", lambda lieu_id: [
		copy.deepcopy(d) for d in docs.values() if d.get("type") == "connection"
		and any(n.get("lieu") == lieu_id for n in d.get("nodes") or [])])
	monkeypatch.setattr(rc, "get_lieu_links", lambda _u: ["liens"])
	yield {"docs": docs, "rc": rc, "get": get_doc_fn}


def _appel(monde, character, coro_fn, *args):
	rc = monde["rc"]
	monde["docs"][character["_id"]] = character
	origine = rc.get_selected_character
	try:
		rc.get_selected_character = lambda _u: character
		return asyncio.run(coro_fn(*args))
	finally:
		rc.get_selected_character = origine


def _refus(monde, character, coro_fn, *args) -> int:
	with pytest.raises(HTTPException) as e:
		_appel(monde, character, coro_fn, *args)
	return e.value.status_code


def _fonder(monde, char, nom="Val-Clair"):
	rc = monde["rc"]
	site = _appel(monde, char, rc.site, None)
	rep = _appel(monde, char, rc.fonder, None, {"modele": site["modeles"][0]["id"], "nom": nom})
	imp_id = rep["fondee"]["id"]
	lien = monde["docs"][monde["docs"][imp_id]["lien"]]
	entree = lien["nodes"][1]["pos"]
	char["lieu"], char["position"] = imp_id, {"x": entree[0], "y": entree[1]}
	return imp_id


def _reg(monde):
	return col.regles(monde["get"])


# ── Fonder ───────────────────────────────────────────────────────────────────────────

def test_site_lit_la_fiche_propose_les_modeles_et_nomme_la_cite_de_la_charte(monde):
	rc = monde["rc"]
	char = _perso()
	rep = _appel(monde, char, rc.site, None)
	assert rep["peut_fonder"] and rep["refus"] == ""
	assert rep["charte"]["cite"] == "lieu:cite"
	assert rep["cites"] == [{"id": "lieu:cite", "label": "Cité"}]
	assert set(rep["site"]) == set(_reg(monde)["axes_site"])
	assert [m["generique"] for m in rep["modeles"]] == [True] and rep["modeles"][0]["route"]
	# hors d'un pays : 403 ; rang insuffisant : la fiche se lit, la charte se refuse
	assert _refus(monde, _perso(lieu="lieu:cite"), rc.site, None) == 403
	assert not _appel(monde, _perso(rangs_guilde={"lieu:cite": "D"}), rc.site, None)["peut_fonder"]


def test_la_charte_s_achete_au_bureau_du_maitre_de_la_cite(monde):
	rc = monde["rc"]
	monde["docs"]["lieu:bureau"] = {"_id": "lieu:bureau", "type": "lieu", "categorie": col.CATEGORIE_BUREAU,
									"lieu_parent": "lieu:cite", "pnj": [{"nom": "Gautier"}]}
	char = _perso(lieu="lieu:bureau")
	char.pop(col.CHAMP_CHARTE)
	avant = money_to_cuivre(char)
	rep = _appel(monde, char, rc.charte, None)
	assert rep["peut_acheter"] and rep["cite"] == "Cité" and rep["maitre"] == "Gautier"
	rep = _appel(monde, char, rc.charte_acheter, None)
	assert rep["achetee"] and rep["charte"]["cite"] == "lieu:cite"
	assert money_to_cuivre(char) == avant - _reg(monde)["reglages"]["charte_cuivre"]
	assert _refus(monde, char, rc.charte_acheter, None) == 409                 # une à la fois
	assert _refus(monde, _perso(), rc.charte, None) == 403                     # hors d'un bureau
	pauvre = _perso(lieu="lieu:bureau", **{"or": 0})
	pauvre.pop(col.CHAMP_CHARTE)
	assert _refus(monde, pauvre, rc.charte_acheter, None) == 409


def test_fonder_cree_le_lieu_et_sa_connexion_remet_la_charte_sans_recopier_la_grille(monde):
	rc = monde["rc"]
	char = _perso()
	avant = money_to_cuivre(char)
	imp_id = _fonder(monde, char)
	stocke = monde["docs"][imp_id]
	assert not set(db_config.CHAMPS_MODELE) & set(stocke)                    # lien PUR en base
	assert stocke["label"] == "Val-Clair" and stocke["fondateur"] == char["_id"]
	assert stocke["menace"]["espece"] == "espece:loup"
	assert money_to_cuivre(char) == avant and col.CHAMP_CHARTE not in char     # payée au bureau, remise ici
	assert char["implantations"] == [imp_id]
	lien = monde["docs"][stocke["lien"]]
	assert lien["nodes"][0] == {"lieu": "lieu:pays", "pos": [20, 10]} and lien["metadata"]["type"] == col.CATEGORIE
	lu = monde["get"](imp_id)
	assert lu["cells"] and lien["nodes"][1]["pos"] == col.entrees_de(lu)[0]  # la grille se lit sur le modèle
	# une seule par pays et par personnage
	dehors = _perso(implantations=[imp_id], position={"x": 10, "y": 15})
	assert not _appel(monde, dehors, rc.site, None)["peut_fonder"]
	assert _refus(monde, dehors, rc.fonder, None, {"modele": stocke["modele"]}) == 403


def test_fonder_refuse_un_modele_non_propose_et_sans_charte(monde):
	rc = monde["rc"]
	assert _refus(monde, _perso(), rc.fonder, None, {"modele": "lieu:modele_colonie_ville"}) == 409
	sans = _perso()
	sans.pop(col.CHAMP_CHARTE)
	site = _appel(monde, sans, rc.site, None)
	assert not site["peut_fonder"] and "Cité" in site["refus"]
	assert _refus(monde, sans, rc.fonder, None, {"modele": site["modeles"][0]["id"]}) == 403
	assert not [d for d in monde["docs"] if d.startswith("implantation:")]


# ── Rôles ────────────────────────────────────────────────────────────────────────────

def test_le_visiteur_lit_en_mots_donne_et_ne_decide_de_rien(monde):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	visiteur = _perso("v", lieu=imp_id, position=dict(fondateur["position"]),
					  inventaire=["item:pain", "item:epee"])
	rep = _appel(monde, visiteur, rc.ici, None)
	assert rep["role"] == col.VISITEUR and "stocks" not in rep and set(rep["securite"]) == {"mot"}
	assert [d["nom"] for d in rep["dons_possibles"]] == ["Pain"]             # l'épée ne nourrit personne
	for route, corps in ((rc.construire, {"type": "habitation"}), (rc.feu, {"reglage": "reduit"}),
						 (rc.chantier_ouvrir, {"genre": "statut"}), (rc.poser, {"batiment": "b_x"})):
		assert _refus(monde, visiteur, route, None, corps) == 403
	assert _refus(monde, visiteur, rc.embauche, None) == 403
	assert _refus(monde, visiteur, rc.donner, None, {"index": 1, "item_id": "item:epee"}) == 409
	avant = monde["docs"][imp_id]["stocks"]["nourriture"]
	rep = _appel(monde, visiteur, rc.donner, None, {"index": 0, "item_id": "item:pain"})
	assert rep["role"] == col.SOUTIEN and visiteur["inventaire"] == ["item:epee"]
	assert monde["docs"][imp_id]["stocks"]["nourriture"] == avant + rep["don"]["unites"]
	assert "inventaire_payload" in rep
	# le don est au carnet du fondateur
	carnet = _appel(monde, fondateur, rc.ici, None)["journal"]
	assert any("Milo donne Pain" in j["texte"] for j in carnet)


def test_association_demande_reponse_et_financement_d_un_chantier(monde):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	associe = _perso("b", lieu=imp_id, position=dict(fondateur["position"]))
	_appel(monde, associe, rc.association_demander, None, {"texte": "Je paie ma part."})
	assert associe["demande_association"] == imp_id
	assert _refus(monde, associe, rc.association_repondre, None, {"id": associe["_id"], "accepter": True}) == 403
	rep = _appel(monde, fondateur, rc.association_repondre, None, {"id": associe["_id"], "accepter": True})
	assert [a["id"] for a in rep["associes"]] == [associe["_id"]]
	rep = _appel(monde, associe, rc.ici, None)                              # son passage pose l'association
	assert rep["role"] == col.ASSOCIE and associe["association"] == imp_id and "stocks" in rep
	# le fondateur ouvre un chantier de fortification, l'associé en verse une part
	reg = _reg(monde)
	f = col.fortification_requise(reg, "hameau")
	monde["docs"][imp_id]["stocks"].update({"bois": f["bois"], "materiaux": f["materiaux"]})
	assert _refus(monde, associe, rc.chantier_ouvrir, None, {"genre": "fortification", "objet": f["id"]}) == 403
	_appel(monde, fondateur, rc.chantier_ouvrir, None, {"genre": "fortification", "objet": f["id"]})
	avant = money_to_cuivre(associe)
	rep = _appel(monde, associe, rc.chantier_financer, None, {"montant": 10 ** 9})
	assert rep["verse"] == f["prix_cuivre"] and rep["acheve"] and money_to_cuivre(associe) == avant - f["prix_cuivre"]
	assert monde["docs"][imp_id]["fortifications"] == [f["id"]]
	assert monde["docs"][imp_id]["associes"][0]["apports"] == {"cuivre": f["prix_cuivre"]}
	# exclusion : au passage suivant, l'association tombe
	_appel(monde, fondateur, rc.association_exclure, None, {"id": associe["_id"]})
	assert _appel(monde, associe, rc.ici, None)["role"] == col.VISITEUR and "association" not in associe


# ── Bâtir, engager, grandir ──────────────────────────────────────────────────────────

def test_construire_poser_engager_puis_changer_de_palier(monde):
	rc = monde["rc"]
	reg = _reg(monde)
	fondateur = _perso(**{"or": 1000})
	imp_id = _fonder(monde, fondateur)
	monde["docs"][imp_id]["stocks"].update({"bois": 500, "materiaux": 500})
	bdef = col.batiment_def(reg, "poste_de_garde")
	avant = money_to_cuivre(fondateur)
	rep = _appel(monde, fondateur, rc.construire, None, {"type": "poste_de_garde"})
	bid = rep["construit"]
	assert money_to_cuivre(fondateur) == avant - bdef["prix_cuivre"] and rep["reperes"] == []
	assert _refus(monde, fondateur, rc.poser, None, {"batiment": bid}) == 409      # debout sur l'entrée
	fondateur["position"] = {"x": 3, "y": 3}
	rep = _appel(monde, fondateur, rc.poser, None, {"batiment": bid})
	assert [(r["x"], r["y"]) for r in rep["reperes"]] == [(3, 3)]
	# le tableau d'embauche offre un candidat par poste ; engager crée l'employé
	tableau = _appel(monde, fondateur, rc.embauche, None)
	assert len(tableau["candidats"]) == len(bdef["postes"])
	garde = next(c for c in tableau["candidats"] if c["metier_label"] == "Garde")
	rep = _appel(monde, fondateur, rc.engager, None, {"candidat_id": garde["id"]})
	assert rep["engage"] and len(rep["employes"]) == 1
	employe_id = monde["docs"][imp_id]["employes"][0]
	assert monde["docs"][employe_id]["propriete"] == imp_id and monde["docs"][employe_id]["poste"] == bid

	# seuils du Hameau atteints (posés à la main), chantier de statut, choix du modèle
	suivant = col.palier_suivant(reg, "campement")
	stocke = monde["docs"][imp_id]
	stocke["population"] = suivant["population_min"]
	stocke["fortifications"] = [col.fortification_requise(reg, suivant["id"])["id"]]
	for n in range(suivant["postes_min"]):
		e = {"_id": f"employe:garde_x{n}", "type": "employe", "metier": "garde", "poste": bid,
			 "statut": "employe", "propriete": imp_id, "prenom": "G", "nom": str(n)}
		monde["docs"][e["_id"]] = e
		stocke["employes"].append(e["_id"])
	assert _refus(monde, fondateur, rc.palier, None, {"modele": "lieu:modele_colonie_hameau"}) == 409
	_appel(monde, fondateur, rc.chantier_ouvrir, None, {"genre": "statut"})
	rep = _appel(monde, fondateur, rc.chantier_financer, None, {"montant": suivant["prix_statut_cuivre"]})
	assert not rep["acheve"] and [m["id"] for m in rep["modeles"]] == ["lieu:modele_colonie_hameau"]
	rep = _appel(monde, fondateur, rc.palier, None, {"modele": "lieu:modele_colonie_hameau"})
	assert rep == {"palier": suivant["label"], "recharger": True}
	stocke = monde["docs"][imp_id]
	assert stocke["palier"] == suivant["id"] and stocke["modele"] == "lieu:modele_colonie_hameau"
	assert not set(db_config.CHAMPS_MODELE) & set(stocke)
	nouveau = monde["docs"]["lieu:modele_colonie_hameau"]
	entree = col.entrees_de(nouveau)[0]
	assert monde["docs"][stocke["lien"]]["nodes"][1]["pos"] == entree          # on arrive par la première entrée
	assert fondateur["position"] == {"x": entree[0], "y": entree[1]}
	assert col.batiment(stocke, bid)["pos"] is not None
	assert monde["get"](imp_id)["dimensions"] == nouveau["dimensions"]          # nouvelle image, nouvelle grille


def test_hors_d_une_implantation_les_routes_du_lieu_refusent(monde):
	rc = monde["rc"]
	assert _refus(monde, _perso(), rc.ici, None) == 403
	assert _refus(monde, _perso(), rc.donner, None, {"index": 0}) == 403


def test_un_sous_lieu_se_construit_se_pose_et_ouvre_avec_son_tenancier(monde):
	rc = monde["rc"]
	reg = _reg(monde)
	monde["docs"]["pnj:marchand_boulangerie"] = {"_id": "pnj:marchand_boulangerie", "type": "pnj", "nom": "Aubry"}
	fondateur = _perso(**{"or": 1000})
	imp_id = _fonder(monde, fondateur)
	monde["docs"][imp_id].update(palier="bourgade", stocks={"nourriture": 50, "bois": 500, "materiaux": 500, "medicaments": 0})
	ici = _appel(monde, fondateur, rc.ici, None)
	boutique = next(c for c in ici["catalogue"] if c["id"] == "boutique")
	assert boutique["categories"] == [{"id": "boulangerie", "label": "Boulangerie"}]
	assert _refus(monde, fondateur, rc.construire, None, {"type": "boutique"}) == 409          # métier à choisir
	assert _refus(monde, fondateur, rc.construire, None, {"type": "boutique", "categorie": "armurerie"}) == 409
	bid = _appel(monde, fondateur, rc.construire, None, {"type": "boutique", "categorie": "boulangerie"})["construit"]
	fondateur["position"] = {"x": 4, "y": 4}
	rep = _appel(monde, fondateur, rc.poser, None, {"batiment": bid})
	b = col.batiment(monde["docs"][imp_id], bid)
	lieu, lien = monde["docs"][b["lieu"]], monde["docs"][b["lien"]]
	assert lieu["categorie"] == "boulangerie" and lieu["lieu_parent"] == imp_id and lieu["image"].startswith("boulangerie_europe")
	assert lien["nodes"][0] == {"lieu": imp_id, "pos": [4, 4]} and "links" in rep
	assert lieu["pnj"] == [] and not col.sous_lieu_ouvert(lieu, monde["get"])[0]
	# déplacer : la porte suit, aucun second lieu
	fondateur["position"] = {"x": 6, "y": 5}
	_appel(monde, fondateur, rc.poser, None, {"batiment": bid})
	assert monde["docs"][b["lien"]]["nodes"][0]["pos"] == [6, 5]
	assert len([d for d in monde["docs"] if d.startswith(col.PREFIXE_SOUS_LIEU)]) == 1
	# engager le marchand : le sous-lieu ouvre sous son nom
	tableau = _appel(monde, fondateur, rc.embauche, None)
	cand = next(c for c in tableau["candidats"] if c["poste_nom"] == "Boutique")
	_appel(monde, fondateur, rc.engager, None, {"candidat_id": cand["id"]})
	lieu = monde["docs"][b["lieu"]]
	assert lieu["pnj"][0]["character"] == "pnj:marchand_boulangerie" and lieu["pnj"][0]["nom"].startswith(cand["prenom"])
	assert col.sous_lieu_ouvert(lieu, monde["get"]) == (True, "")
	visiteur = _perso("v", lieu=imp_id, position={"x": 1, "y": 1})
	assert any(s["ouvert"] for s in _appel(monde, visiteur, rc.ici, None)["sous_lieux"])
	# renvoyé : fermé de nouveau
	employe_id = next(e for e in monde["docs"][imp_id]["employes"])
	_appel(monde, fondateur, rc.renvoyer, None, {"employe_id": employe_id})
	assert monde["docs"][b["lieu"]]["pnj"] == []


def test_la_caisse_se_releve_et_la_vente_se_regle_par_pnj(monde):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	monde["docs"][imp_id]["caisse_cuivre"] = 120
	avant = money_to_cuivre(fondateur)
	assert _appel(monde, fondateur, rc.caisse_relever, None)["releve"] == 120
	assert money_to_cuivre(fondateur) == avant + 120 and monde["docs"][imp_id]["caisse_cuivre"] == 0
	assert _refus(monde, fondateur, rc.caisse_relever, None) == 409
	monde["docs"][imp_id]["batiments"] = [{"id": "b_f", "type": "ferme", "pos": [2, 2]}]
	e = {"_id": "employe:agri", "type": "employe", "metier": "agriculteur", "poste": "b_f", "statut": "employe",
		 "propriete": imp_id, "prenom": "A", "nom": "B"}
	monde["docs"][e["_id"]] = e
	monde["docs"][imp_id]["employes"] = [e["_id"]]
	rep = _appel(monde, fondateur, rc.employe_vente, None, {"employe_id": "employe:agri", "vente": False})
	assert monde["docs"]["employe:agri"]["vente_cite"] is False
	ferme = next(b for b in rep["batiments"] if b["id"] == "b_f")
	assert ferme["postes"][0]["tenus"][0]["vend"] is False
	visiteur = _perso("v", lieu=imp_id, position={"x": 1, "y": 1})
	assert _refus(monde, visiteur, rc.caisse_relever, None) == 403
	assert _refus(monde, visiteur, rc.employe_vente, None, {"employe_id": "employe:agri", "vente": True}) == 403


def test_l_attaque_se_joue_aux_cotes_des_gardes_et_son_issue_revient_au_lieu(monde):
	from utils import combat as combat_util
	rc = monde["rc"]
	fondateur = _perso(user_id="user:a")
	imp_id = _fonder(monde, fondateur)
	imp = monde["docs"][imp_id]
	assert _refus(monde, fondateur, rc.defendre, None) == 409                       # rien à repousser
	imp["batiments"] = [{"id": "b_g", "type": "poste_de_garde", "pos": [2, 2]}]
	garde = {"_id": "employe:g", "type": "employe", "metier": "garde", "poste": "b_g", "statut": "employe",
			 "propriete": imp_id, "prenom": "Aldo", "nom": "Brun", "race": "nain"}
	monde["docs"][garde["_id"]] = garde
	imp["employes"] = [garde["_id"]]
	imp["attaque_en_cours"] = {"at": 1, "espece": "espece:loup"}
	visiteur = _perso("v", lieu=imp_id, position=dict(fondateur["position"]))
	assert _refus(monde, visiteur, rc.defendre, None) == 403
	rep = _appel(monde, fondateur, rc.defendre, None)
	combat = monde["docs"][rep["combat_id"]]
	assert combat["colonie"] == {"implantation": imp_id, "genre": col.DEFENSE}
	assert combat["battle_map_id"] == imp_id and combat["map_route"]
	[g] = [j for j in combat["joueurs"] if j.get("est_garde")]
	assert g["character_id"] == garde["_id"] and g["se_defend"] and not g.get("jouable", True)
	reg = _reg(monde)
	assert len(combat["monstres"]) == col.nb_adversaires(imp, reg, col.DEFENSE)
	# victoire, garde tombé : le lieu le sait, une seule fois
	combat["status"] = "victoire"
	g["currentPV"] = 0
	combat_util._finalize_colonie(combat, "victoire")
	combat_util._finalize_colonie(combat, "victoire")
	imp = monde["docs"][imp_id]
	assert "attaque_en_cours" not in imp and imp["employes"] == []
	assert [a for a in imp["attaques"] if a["repoussee"]] == [imp["attaques"][-1]]
	assert monde["docs"]["employe:g"]["statut"] == col.EMPLOYE_MORT


def test_la_taniere_localisee_se_vide_en_combat(monde):
	from utils import combat as combat_util
	rc = monde["rc"]
	monde["docs"]["lieu:carte_foret"] = {"_id": "lieu:carte_foret", "type": "lieu", "categorie": "battle_map",
										 "image": "foret0001.png", "tags": ["foret"], "dimensions": {"x": 10, "y": 8},
										 "cells": [[1] * 10 for _ in range(8)]}
	fondateur = _perso(user_id="user:a")
	imp_id = _fonder(monde, fondateur)
	assert _refus(monde, fondateur, rc.taniere, None) == 409
	monde["docs"][imp_id]["menace"]["etape"] = 4
	rep = _appel(monde, fondateur, rc.taniere, None)
	combat = monde["docs"][rep["combat_id"]]
	assert combat["colonie"]["genre"] == col.TANIERE and combat["battle_map_id"] == "lieu:carte_foret"
	assert not [j for j in combat["joueurs"] if j.get("est_garde")]
	combat_util._finalize_colonie(combat, "victoire")
	assert monde["docs"][imp_id]["menace"]["etape"] == 0
