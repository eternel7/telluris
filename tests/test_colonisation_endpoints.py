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
	from utils import recrutement as recrutement_util
	for mod in (rc, ru, characters_util, proprietes, marche, combat_util, recrutement_util):
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


def test_on_donne_depuis_tout_le_groupe_compagnons_montures_et_contenants(monde):
	"""Le don puise dans les sacs du GROUPE : compagnon, monture, contenant ouvert (sac virtuel
	du principal comme d'un porteur). Le sac d'autrui n'est pas adressable."""
	rc = monde["rc"]
	monde["docs"]["item:besace"] = {"_id": "item:besace", "type": "item", "nom": "Besace profonde",
									"categorie": "outil", "sous_categorie": "contenant", "slots": [], "poids": 0.5,
									"tags": ["contenant", "non_personnalisable"], "contenant": {"capacite_kg": 10}}
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	av = {"_id": "aventurier:1", "type": "aventurier", "statut": "embauche", "embauche_par": "character:v",
		  "prenom": "Bo", "nom": "", "caracteristiques_current": dict(CARACTS),
		  "inventaire": ["item:pain", {"item": "item:besace", "contenu": ["item:pain"]}]}
	mule = {"_id": "monture:1", "type": "monture", "statut": "acquise", "acquise_par": "character:v",
			"nom": "Mule", "inventaire": ["item:pain"]}
	etranger = {"_id": "aventurier:2", "type": "aventurier", "statut": "embauche", "embauche_par": "character:x",
				"prenom": "Nul", "nom": "", "inventaire": ["item:pain"]}
	for d in (av, mule, etranger):
		monde["docs"][d["_id"]] = d
	visiteur = _perso("v", lieu=imp_id, position=dict(fondateur["position"]), groupe=[av["_id"], etranger["_id"]],
					  montures=[mule["_id"]], inventaire=[{"item": "item:besace", "contenu": ["item:pain"]}])
	dons = _appel(monde, visiteur, rc.ici, None)["dons_possibles"]
	assert [(d["sac"], d["porteur"]) for d in dons] == [
		("aventurier:1", "Bo"), ("monture:1", "Mule"),
		("character:v#0", "Besace profonde"), ("aventurier:1#1", "Besace profonde")]
	assert _refus(monde, visiteur, rc.donner, None, {"sac": "aventurier:2", "index": 0, "item_id": "item:pain"}) == 404
	for sac, idx in (("aventurier:1#1", 0), ("character:v#0", 0), ("aventurier:1", 0), ("monture:1", 0)):
		rep = _appel(monde, visiteur, rc.donner, None, {"sac": sac, "index": idx, "item_id": "item:pain"})
		assert rep["don"]["nom"] == "Pain"
		# le sac du PORTEUR réel revient à part (sac virtuel → son porteur), jamais celui du principal
		porteur = sac.split("#")[0]
		if porteur == visiteur["_id"]:
			assert "compagnon_id" not in rep and "compagnon" not in rep
		else:
			assert rep["compagnon_id"] == porteur
			assert [o["_id"] for o in rep["compagnon"]["inventaire"]] == [
				_id for r in monde["docs"][porteur]["inventaire"] for _id in [r["item"] if isinstance(r, dict) else r]]
	assert monde["docs"]["aventurier:1"]["inventaire"] == [{"item": "item:besace"}]   # pain donné, besace vidée
	assert monde["docs"]["monture:1"]["inventaire"] == []
	assert visiteur["inventaire"] == [{"item": "item:besace"}]
	assert monde["docs"]["aventurier:2"]["inventaire"] == ["item:pain"]
	assert rep["dons_possibles"] == [] and rep["role"] == col.SOUTIEN


def test_tout_donner_verse_chaque_exemplaire_du_meme_sac(monde):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	visiteur = _perso("v", lieu=imp_id, position=dict(fondateur["position"]),
					  inventaire=["item:pain", "item:epee", "item:pain", "item:pain"])
	avant = monde["docs"][imp_id]["stocks"]["nourriture"]
	rep = _appel(monde, visiteur, rc.donner, None, {"index": 0, "item_id": "item:pain", "tout": True})
	assert rep["don"]["nombre"] == 3 and visiteur["inventaire"] == ["item:epee"]
	assert monde["docs"][imp_id]["stocks"]["nourriture"] == round(avant + rep["don"]["unites"], 1)
	# sans `tout`, un seul exemplaire
	visiteur["inventaire"] = ["item:pain", "item:pain"]
	assert _appel(monde, visiteur, rc.donner, None, {"index": 1, "item_id": "item:pain"})["don"]["nombre"] == 1
	assert visiteur["inventaire"] == ["item:pain"]


def test_le_mini_plan_vient_du_lieu_modele_et_reste_aux_gerants(monde, monkeypatch):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	monkeypatch.setattr(rc.os.path, "exists", lambda chemin: True)
	modele = monde["get"](monde["docs"][imp_id]["modele"])
	plan = _appel(monde, fondateur, rc.ici, None)["plan"]
	assert plan["dimensions"] == {"x": modele["dimensions"]["x"], "y": modele["dimensions"]["y"]}
	assert plan["entrees"] == modele["entrees"] and plan["image"].endswith("/" + modele["image"])
	visiteur = _perso("v", lieu=imp_id, position=dict(fondateur["position"]))
	assert "plan" not in _appel(monde, visiteur, rc.ici, None)
	monkeypatch.setattr(rc.os.path, "exists", lambda chemin: False)
	assert _appel(monde, fondateur, rc.ici, None)["plan"] is None, "image absente du disque : pas de plan"


def test_le_fondateur_choisit_l_icone_de_la_carte_le_visiteur_non(monde, monkeypatch):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	palier = monde["docs"][imp_id]["palier"]
	monkeypatch.setattr(rc, "fichiers_towns", lambda: [f"{palier}_icon.webp", f"{palier}_icon_feu.webp"])
	rep = _appel(monde, fondateur, rc.ici, None)
	assert rep["icone_carte"]["courante"] is None and len(rep["icone_carte"]["choix"]) == 2
	rep = _appel(monde, fondateur, rc.icone, None, {"fichier": f"{palier}_icon_feu.webp"})
	assert rep["icone_carte"]["courante"] == f"{palier}_icon_feu.webp"
	assert monde["docs"][imp_id]["icone_carte"] == f"{palier}_icon_feu.webp"
	assert _refus(monde, fondateur, rc.icone, None, {"fichier": "autre_icon.webp"}) == 409
	visiteur = _perso("v", lieu=imp_id, position=dict(fondateur["position"]))
	assert "icone_carte" not in _appel(monde, visiteur, rc.ici, None)
	assert _refus(monde, visiteur, rc.icone, None, {"fichier": None}) == 403


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


def test_sortie_batiments_et_portes_suivent_le_modele_retouche(monde):
	"""Le modèle est retouché APRÈS la fondation (entrées 🚪, grille) : au passage suivant, la
	sortie va sur la nouvelle première entrée, un bâtiment sur une entrée ou une case murée
	est déplacé, la porte de son sous-lieu le suit (cas de Sens, hameau du 21/11)."""
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	reg = _reg(monde)
	modele_id = monde["docs"][imp_id]["modele"]
	modele = monde["docs"][modele_id]
	w, h = modele["dimensions"]["x"], modele["dimensions"]["y"]
	nouvelles = [[w // 2, 0], [w // 2, h - 1]]
	stocke = monde["docs"][imp_id]
	stocke["batiments"] = [
		{"id": "b_e", "type": "entrepot", "pos": list(nouvelles[1])},                       # sur une future entrée
		{"id": "b_h", "type": "habitation", "pos": [3, 3], "lien": "link:colonie_t"},         # sur une future case murée
		{"id": "b_g", "type": "poste_de_garde", "pos": [5, 5]}]                               # intacte
	monde["docs"]["link:colonie_t"] = {"_id": "link:colonie_t", "type": "connection",
									   "nodes": [{"lieu": imp_id, "pos": [3, 3]}, {"lieu": "lieu:colonie_t", "pos": [0, 0]}]}
	ancienne = monde["docs"][stocke["lien"]]["nodes"][1]["pos"]
	assert ancienne != nouvelles[0]
	# retouche du modèle dans l'éditeur
	modele["entrees"] = nouvelles
	modele["cells"] = [list(r) for r in modele["cells"]]
	modele["cells"][3][3] = 0
	rc.suivre_modele_ici(monde["get"](imp_id), reg)
	assert monde["docs"][stocke["lien"]]["nodes"][1]["pos"] == nouvelles[0]
	apres = {b["id"]: b["pos"] for b in monde["docs"][imp_id]["batiments"]}
	assert apres["b_g"] == [5, 5]
	assert apres["b_e"] not in nouvelles and apres["b_h"] != [3, 3]
	imp = monde["get"](imp_id)
	assert all(col.case_marchable(imp, *p) for p in apres.values())
	assert len({tuple(p) for p in apres.values()}) == 3
	assert monde["docs"]["link:colonie_t"]["nodes"][0]["pos"] == apres["b_h"], "la porte suit son bâtiment"
	assert not set(db_config.CHAMPS_MODELE) & set(monde["docs"][imp_id]), "lien pur : rien du modèle en base"
	# idempotent : un second passage ne change plus rien
	avant = copy.deepcopy(monde["docs"])
	rc.suivre_modele_ici(monde["get"](imp_id), reg)
	assert monde["docs"] == avant
	# arrivée par la sortie : la première entrée actuelle, même si le nœud n'avait pas suivi
	monde["docs"][stocke["lien"]]["nodes"][1]["pos"] = ancienne
	assert col.arrivee_implantation(monde["get"](imp_id), stocke["lien"], {"x": 1, "y": 1}) == {"x": nouvelles[0][0], "y": 0}
	assert col.arrivee_implantation(monde["get"](imp_id), "link:colonie_t", {"x": 3, "y": 4}) == {"x": 3, "y": 4}


def test_hors_d_une_implantation_les_routes_du_lieu_refusent(monde):
	rc = monde["rc"]
	assert _refus(monde, _perso(), rc.ici, None) == 403
	assert _refus(monde, _perso(), rc.donner, None, {"index": 0}) == 403


def test_une_boutique_s_achete_se_pose_et_ouvre_comme_en_ville(monde):
	rc = monde["rc"]
	reg = _reg(monde)
	monde["docs"]["pnj:marchand_boulangerie"] = {"_id": "pnj:marchand_boulangerie", "type": "pnj",
												 "nom": "Maître Fromond", "portrait": "humain_m_guerrier01.jpg"}
	fondateur = _perso(**{"or": 1000})
	imp_id = _fonder(monde, fondateur)
	monde["docs"][imp_id].update(palier="bourgade", stocks={"nourriture": 50, "bois": 0, "materiaux": 0, "medicaments": 0})
	ici = _appel(monde, fondateur, rc.ici, None)
	[ligne] = [c for c in ici["catalogue"] if c["id"] == "boutique"]
	assert ligne["categorie"] == "boulangerie" and ligne["label"] == "Boulangerie" and not ligne["refus"]
	assert _refus(monde, fondateur, rc.construire, None, {"type": "boutique"}) == 409          # quel métier ?
	assert _refus(monde, fondateur, rc.construire, None, {"type": "boutique", "categorie": "armurerie"}) == 409
	avant = money_to_cuivre(fondateur)
	bid = _appel(monde, fondateur, rc.construire, None, {"type": "boutique", "categorie": "boulangerie"})["construit"]
	assert money_to_cuivre(fondateur) == avant - ligne["prix"]                                 # sans bois ni matériaux
	fondateur["position"] = {"x": 4, "y": 4}
	rep = _appel(monde, fondateur, rc.poser, None, {"batiment": bid})
	b = col.batiment(monde["docs"][imp_id], bid)
	lieu, lien = monde["docs"][b["lieu"]], monde["docs"][b["lien"]]
	assert lieu["categorie"] == "boulangerie" and lieu["lieu_parent"] == imp_id and lieu["image"].startswith("boulangerie_europe")
	assert lien["nodes"][0] == {"lieu": imp_id, "pos": [4, 4]} and "links" in rep
	assert lieu["pnj"] == [{"character": "pnj:marchand_boulangerie", "nom": "Maître Fromond",
							"portrait": "humain_m_guerrier01.jpg"}]
	assert col.sous_lieu_ouvert(lieu, monde["get"]) == (True, "")
	# déplacer : la porte suit, aucun second lieu
	fondateur["position"] = {"x": 6, "y": 5}
	_appel(monde, fondateur, rc.poser, None, {"batiment": bid})
	assert monde["docs"][b["lien"]]["nodes"][0]["pos"] == [6, 5]
	assert len([d for d in monde["docs"] if d.startswith(col.PREFIXE_SOUS_LIEU)]) == 1
	visiteur = _perso("v", lieu=imp_id, position={"x": 1, "y": 1})
	assert any(x["ouvert"] for x in _appel(monde, visiteur, rc.ici, None)["sous_lieux"])
	assert not _appel(monde, fondateur, rc.embauche, None)["candidats"]                       # rien à engager


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


def test_la_consigne_d_achat_fait_partir_le_charretier_vers_la_cite(monde):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	visiteur = _perso("v", lieu=imp_id, position={"x": 1, "y": 1})
	assert "approvisionnement" not in _appel(monde, visiteur, rc.ici, None)
	assert _refus(monde, visiteur, rc.consigne, None, {"stock": "nourriture", "acheter": True, "plafond_jour": 10}) == 403
	assert _refus(monde, fondateur, rc.consigne, None, {"stock": "or", "acheter": True, "plafond_jour": 10}) == 400
	rep = _appel(monde, fondateur, rc.consigne, None, {"stock": "nourriture", "acheter": True, "plafond_jour": 100000})
	assert next(c for c in rep["approvisionnement"]["consignes"] if c["stock"] == "nourriture")["acheter"] is True
	imp = monde["docs"][imp_id]
	imp["batiments"] = [{"id": "b_e", "type": "entrepot", "pos": [2, 2]}, {"id": "b_c", "type": "comptoir", "pos": [3, 3]}]
	for metier, poste in (("intendant", "b_e"), ("charretier", "b_c")):
		e = {"_id": f"employe:{metier}", "type": "employe", "metier": metier, "poste": poste, "statut": "employe",
			 "propriete": imp_id, "prenom": "A", "nom": metier}
		monde["docs"][e["_id"]] = e
	imp["employes"] = ["employe:intendant", "employe:charretier"]
	imp["stocks"]["nourriture"] = 0
	imp["caisse_cuivre"] = 100000
	imp["rattrape_at"] -= 2 * _reg(monde)["temps"]["passe_s"]
	rep = _appel(monde, fondateur, rc.ici, None)
	[l] = rep["approvisionnement"]["livraisons"]
	assert l["cite"] == "Cité" and l["stock"] == "nourriture" and l["unites"] >= 1
	assert monde["docs"][imp_id]["caisse_cuivre"] < 100000 and rep["approvisionnement"]["charretier"]


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


def test_la_guilde_se_fonde_se_rejoint_et_envoie_ses_groupes_en_mission(monde):
	import time
	rc = monde["rc"]
	reg = _reg(monde)
	fondateur = _perso(**{"or": 10 ** 6})
	imp_id = _fonder(monde, fondateur)
	monde["docs"][imp_id]["palier"] = "village"
	rep = _appel(monde, fondateur, rc.chantier_ouvrir, None, {"genre": "guilde", "nom": "Les Loups"})
	assert rep["chantier"]["genre"] == col.CHANTIER_GUILDE
	rep = _appel(monde, fondateur, rc.chantier_financer, None, {"montant": rep["chantier"]["cout"]})
	assert rep["acheve"] and rep["guilde"]["nom"] == "Les Loups" and rep["guilde"]["titre"] == col.MAITRE
	# la maison se pose comme un sous-lieu, ouverte sans tenancier, tableau de recrues
	imp = monde["docs"][imp_id]
	maison = next(b for b in imp["batiments"] if b["type"] == "maison_guilde")
	fondateur["position"] = {"x": 4, "y": 4}
	_appel(monde, fondateur, rc.poser, None, {"batiment": maison["id"]})
	lieu = monde["docs"][col.batiment(monde["docs"][imp_id], maison["id"])["lieu"]]
	assert lieu["categorie"] == "guilde_colonie" and lieu["tags"] == ["recrutement"]
	assert col.sous_lieu_ouvert(lieu, monde["get"]) == (True, "")
	# un visiteur la rejoint depuis la maison de guilde
	visiteur = _perso("v", lieu=lieu["_id"], position={"x": 0, "y": 0})
	assert _appel(monde, visiteur, rc.guilde, None)["guilde"]["titre"] is None
	assert _appel(monde, visiteur, rc.guilde_rejoindre, None)["guilde"]["titre"] == col.MEMBRE
	# le maître envoie un compagnon en mission, puis l'accueille
	av = {"_id": "aventurier:1", "type": "aventurier", "statut": "embauche", "embauche_par": fondateur["_id"],
		  "prenom": "Bo", "nom": "", "xp_total": 0, "caracteristiques_current": dict(CARACTS), "currentPV": 10}
	monde["docs"][av["_id"]] = av
	fondateur["groupe"] = [av["_id"]]
	mission = col.missions_ouvertes(monde["docs"][imp_id], reg)[0]
	rep = _appel(monde, fondateur, rc.guilde_envoyer, None, {"mission": mission["id"], "compagnons": [av["_id"]]})
	assert fondateur["groupe"] == [] and monde["docs"][av["_id"]]["en_mission"]["expedition"] == rep["envoyee"]
	assert _refus(monde, fondateur, rc.guilde_accueillir, None, {"expedition": rep["envoyee"]}) == 409   # pas revenu
	exp = col.guilde_de(monde["docs"][imp_id])["expeditions"][0]
	exp["retour"], exp["chance"] = int(time.time()) - 1, 1.0
	avant = money_to_cuivre(fondateur)
	rep = _appel(monde, fondateur, rc.guilde_accueillir, None, {"expedition": exp["id"]})
	assert rep["issue"]["reussie"] and money_to_cuivre(fondateur) == avant + rep["issue"]["gain"]
	assert fondateur["groupe"] == [av["_id"]] and "en_mission" not in monde["docs"][av["_id"]]
	assert monde["docs"][imp_id]["caisse_cuivre"] == rep["issue"]["commission"]


def test_le_materiel_commun_s_ouvre_a_la_demeure_des_aventuriers(monde):
	rc = monde["rc"]
	reg = _reg(monde)
	fondateur = _perso(inventaire=["item:pain"])
	imp_id = _fonder(monde, fondateur)
	imp = monde["docs"][imp_id]
	imp["guilde"] = {"echelon": col.echelons(reg)[0]["id"], "nom": "G", "membres": {
		fondateur["_id"]: {"nom": "Greta", "titre": col.MAITRE}}, "coffre": [], "expeditions": []}
	assert _refus(monde, fondateur, rc.guilde_coffre_deposer, None, {"index": 0, "item_id": "item:pain"}) == 403
	imp["guilde"]["echelon"] = next(e["id"] for e in col.echelons(reg) if "coffre" in e["fonctions"])
	rep = _appel(monde, fondateur, rc.guilde_coffre_deposer, None, {"index": 0, "item_id": "item:pain"})
	assert fondateur["inventaire"] == [] and [o["nom"] for o in rep["guilde"]["coffre"]] == ["Pain"]
	membre = _perso("m", lieu=imp_id, position={"x": 1, "y": 1})
	imp["guilde"]["membres"][membre["_id"]] = {"nom": "Milo", "titre": col.MEMBRE}
	assert _refus(monde, membre, rc.guilde_coffre_retirer, None, {"index": 0}) == 403
	_appel(monde, fondateur, rc.guilde_coffre_retirer, None, {"index": 0})
	assert fondateur["inventaire"] == ["item:pain"]


def test_entrepot_commun_et_petit_coffre_par_les_routes(monde):
	rc = monde["rc"]
	fondateur = _perso(inventaire=["item:pain"])
	imp_id = _fonder(monde, fondateur)
	imp = monde["docs"][imp_id]
	imp["batiments"] = [{"id": "b_e", "type": "entrepot", "pos": [1, 1]}, {"id": "b_h", "type": "habitation", "pos": [2, 2]}]
	imp["associes"] = [{"id": "character:b", "nom": "Milo", "apports": {}}]
	associe = _perso("b", lieu=imp_id, position={"x": 3, "y": 3}, inventaire=["item:pain", "item:pain"], association=imp_id)
	_appel(monde, associe, rc.rangements_deposer, None, {"cible": "entrepot", "index": 0, "item_id": "item:pain"})
	assert monde["docs"][imp_id]["entrepot"] == ["item:pain"]
	assert _refus(monde, associe, rc.rangements_retirer, None, {"cible": "entrepot", "index": 0}) == 403
	_appel(monde, fondateur, rc.rangements_autoriser, None, {"id": "character:b", "retrait": True})
	_appel(monde, associe, rc.rangements_retirer, None, {"cible": "entrepot", "index": 0})
	assert associe["inventaire"] == ["item:pain", "item:pain"]
	rep = _appel(monde, associe, rc.rangements_deposer, None, {"cible": "coffre", "index": 0, "item_id": "item:pain"})
	assert monde["docs"][imp_id]["coffres"]["character:b"] == ["item:pain"]
	assert [o["_id"] for o in rep["rangements"]["coffre"]["inventaire"]] == ["item:pain"]
	assert rep["colonie"] and set(rep["rangements"]) == {"entrepot", "coffre"} and rep["associes"] is None
	assert set(_appel(monde, fondateur, rc.rangements, None)["rangements"]) == {"entrepot"}
	assert _refus(monde, fondateur, rc.rangements_deposer, None, {"cible": "coffre", "index": 0, "item_id": "item:pain"}) == 403
	visiteur = _perso("v", lieu=imp_id, position={"x": 1, "y": 1}, inventaire=["item:pain"])
	assert _refus(monde, visiteur, rc.rangements_deposer, None, {"cible": "entrepot", "index": 0, "item_id": "item:pain"}) == 403
	# journal des mouvements de l'entrepôt : au fondateur seul, sans le petit coffre
	mvts = _appel(monde, fondateur, rc.rangements, None)["mouvements"]
	assert [m["texte"] for m in mvts] == ["Milo prend Pain à l'entrepôt.", "Milo dépose Pain à l'entrepôt."]
	assert rep["mouvements"] is None
	# objets que les réserves acceptent (flèche « réserves ») : le pain, pas l'épée
	associe["inventaire"] = ["item:pain", "item:epee"]
	assert _appel(monde, associe, rc.rangements, None)["reserves"] == {"item:pain": _reg(monde)["stocks_labels"]["nourriture"]}


def test_les_rangements_servent_tous_les_sacs_du_groupe(monde):
	"""Même panneau que le coffre d'une propriété : on dépose depuis le sac d'un compagnon,
	d'une monture ou d'un contenant, on y reprend ; le sac d'autrui n'est pas adressable."""
	rc = monde["rc"]
	monde["docs"]["item:besace"] = {"_id": "item:besace", "type": "item", "nom": "Besace profonde",
									"categorie": "outil", "sous_categorie": "contenant", "slots": [], "poids": 0.5,
									"tags": ["contenant", "non_personnalisable"], "contenant": {"capacite_kg": 10}}
	fondateur = _perso(inventaire=[{"item": "item:besace", "contenu": ["item:pain"]}])
	imp_id = _fonder(monde, fondateur)
	monde["docs"][imp_id]["batiments"] = [{"id": "b_e", "type": "entrepot", "pos": [1, 1]}]
	av = {"_id": "aventurier:1", "type": "aventurier", "statut": "embauche", "embauche_par": fondateur["_id"],
		  "prenom": "Bo", "nom": "", "caracteristiques_current": dict(CARACTS), "inventaire": ["item:pain"]}
	mule = {"_id": "monture:1", "type": "monture", "statut": "acquise", "acquise_par": fondateur["_id"],
			"nom": "Mule", "inventaire": ["item:pain"]}
	etranger = {"_id": "aventurier:2", "type": "aventurier", "statut": "embauche", "embauche_par": "character:x",
				"prenom": "Nul", "nom": "", "inventaire": ["item:pain"]}
	for d in (av, mule, etranger):
		monde["docs"][d["_id"]] = d
	fondateur["groupe"], fondateur["montures"] = [av["_id"], etranger["_id"]], [mule["_id"]]
	rep = _appel(monde, fondateur, rc.rangements, None)
	assert [p["id"] for p in rep["porteurs"]] == ["aventurier:1", "monture:1"]
	assert [c["cle"] for c in rep["sacs_contenants"]] == [f"{fondateur['_id']}#0"]
	base = {"cible": "entrepot", "index": 0, "item_id": "item:pain"}
	assert _refus(monde, fondateur, rc.rangements_deposer, None, dict(base, compagnon_id="aventurier:2")) == 403
	_appel(monde, fondateur, rc.rangements_deposer, None, dict(base, compagnon_id="aventurier:1"))
	_appel(monde, fondateur, rc.rangements_deposer, None, dict(base, compagnon_id="monture:1"))
	rep = _appel(monde, fondateur, rc.rangements_deposer, None,
				 dict(base, index_contenant=0, item_id_contenant="item:besace"))
	assert monde["docs"][imp_id]["entrepot"] == ["item:pain"] * 3
	docs = monde["docs"]
	assert docs["aventurier:1"]["inventaire"] == [] and docs["monture:1"]["inventaire"] == []
	assert fondateur["inventaire"] == [{"item": "item:besace"}]
	assert [o["idx"] for o in rep["rangements"]["entrepot"]["inventaire"]] == [0, 1, 2]
	# on reprend vers le compagnon, puis dans la besace (rangé sans peser)
	_appel(monde, fondateur, rc.rangements_retirer, None, {"cible": "entrepot", "index": 0, "item_id": "item:pain", "compagnon_id": "aventurier:1"})
	_appel(monde, fondateur, rc.rangements_retirer, None, {"cible": "entrepot", "index": 0, "item_id": "item:pain",
														   "index_contenant": 0, "item_id_contenant": "item:besace"})
	assert docs["aventurier:1"]["inventaire"] == ["item:pain"] and fondateur["inventaire"] == [{"item": "item:besace", "contenu": ["item:pain"]}]
	assert monde["docs"][imp_id]["entrepot"] == ["item:pain"]


def test_les_colons_se_trouvent_a_l_auberge_d_une_cite(monde):
	rc = monde["rc"]
	fondateur = _perso()
	imp_id = _fonder(monde, fondateur)
	monde["docs"]["lieu:auberge"] = {"_id": "lieu:auberge", "type": "lieu", "categorie": "auberge", "lieu_parent": "lieu:cite"}
	fondateur.update(lieu="lieu:auberge", position={"x": 0, "y": 0})
	rep = _appel(monde, fondateur, rc.colons, None)
	[offre] = rep["offres"]
	assert offre["id"] == imp_id and offre["nombre"] > 0 and not offre["refus"]
	rep = _appel(monde, fondateur, rc.colons_recruter, None, {"implantation": imp_id})
	assert rep["recrutes"] == offre["nombre"] and fondateur["colons"]["implantation"] == imp_id
	assert _refus(monde, fondateur, rc.colons_recruter, None, {"implantation": imp_id}) == 409
	assert _refus(monde, _perso(lieu=imp_id), rc.colons, None) == 403            # pas dans une auberge de cité
