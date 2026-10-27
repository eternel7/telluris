"""Sur-mesure avec la pièce de base APPORTÉE (`body.base`) : le client confie sa pièce au
lieu d'en faire fabriquer une neuve.

Contrats tenus ici :
- la pièce tient lieu de toute la recette — un trophée n'est pas redemandé — et elle est
  remise en entier sur le prix (restent façon, complexité, matières sur mesure) ;
- elle est retirée du sac au paiement, et son NOM PROPRE passe à la pièce livrée ;
- seul l'objet de base EXACT est admis, à la position désignée — jamais une autre pièce ;
- jamais de mise en attente avec une pièce confiée (sa position aura bougé à la relance) ;
- hors du sur-mesure, apporter sa pièce n'a pas de sens : 422.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from routers import commande as rc  # noqa: E402
from utils import characters, commande as commande_util, marche  # noqa: E402


MAISON = "grand_arsenal"   # une des `LIEU_CATEGORIES_FUSION` : elle fabrique sur mesure
TETE = "item:tete_de_test"

# La pièce exige un TROPHÉE : c'est le cas où apporter sa pièce change tout.
RECETTE = {
	"_id": "recette:apportee_casque", "type": "recette", "lieu_categorie": MAISON,
	"objet_final": "Casque_de_test", "quantite_produite": 1,
	"matieres_premieres": [{"item": TETE, "quantite": 1, "trophee": True},
						   {"item": "item:fer", "quantite": 2}],
}

_DB = {
	"item:Casque_de_test": {"_id": "item:Casque_de_test", "nom": "Casque cornu", "icon": "🐂",
							"categorie": "armure", "sous_categorie": "", "slots": ["tete"],
							"poids": 3.0, "bonus_pa": 2},
	TETE: {"_id": TETE, "nom": "Tête de test", "categorie": "composant",
		   "sous_categorie": "carcasse", "slots": [], "poids": 16.0},
	"item:fer": {"_id": "item:fer", "nom": "Lingot de fer", "categorie": "metal",
				 "sous_categorie": "fer", "slots": [], "poids": 3.0},
	"item:gemme": {"_id": "item:gemme", "nom": "Gemme", "categorie": "composant",
				   "sous_categorie": "gemme", "slots": [], "poids": 0.1,
				   "tags": ["fabrication_armure"],
				   "fabrication": {"nom": "serti", "modificateurs": {"bonus_pv": 2}}},
}

LIEU = {"_id": "lieu:arsenal_de_test", "categorie": MAISON, "label": "L'Arsenal"}
_MONDE = dict(_DB, **{LIEU["_id"]: LIEU})
_ECRITS = {}


def _get(doc_id):
	return _ECRITS.get(doc_id) or _MONDE.get(doc_id)


def _save(doc):
	if doc.get("_id", "").startswith(("item:", "recette:")):
		_ECRITS[doc["_id"]] = doc
	return doc


@pytest.fixture
def atelier(monkeypatch):
	"""Même bordure que `test_commande_payload` : recette semée, base stubbée."""
	marche.reset_prix_cache()
	_ECRITS.clear()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE])
	monkeypatch.setattr(marche, "_matieres_fab_memo", ["item:gemme"])
	monkeypatch.setattr(rc, "get_doc", _get)
	monkeypatch.setattr(characters, "get_doc", _get)
	monkeypatch.setattr(marche, "get_doc", _get)
	monkeypatch.setattr(rc, "_inventory_payload", lambda c: {"inventaire": []})
	monkeypatch.setattr(rc, "_marchand_vendables", lambda *a, **k: [])
	monkeypatch.setattr(rc, "resolve_stock_vente", lambda *a, **k: [])
	monkeypatch.setattr(rc.recrutement, "porteurs_effectifs", lambda *a, **k: [])
	monkeypatch.setattr(rc, "find_docs", lambda *a, **k: [])
	monkeypatch.setattr(rc, "get_relation", lambda *a, **k: {"value": 50})
	monkeypatch.setattr(rc, "save_doc", _save)
	yield
	marche.reset_prix_cache()


def _joueur(*refs):
	return {"_id": "character:j", "lieu": LIEU["_id"], "or": 50, "commandes": [],
			"inventaire": list(refs)}


def _appel(monkeypatch, fn, character, body):
	monkeypatch.setattr(rc, "get_selected_character", lambda u: character)
	rep = fn({"_id": "user:j"}, body)
	return asyncio.run(rep) if asyncio.iscoroutine(rep) else rep


CASQUE_NOMME = {"item": "item:Casque_de_test", "poids": 3.0, "nom_perso": "Brise-Crâne"}
GEMME = {"item": "item:gemme", "poids": 0.1}
SUR_MESURE = {"item_id": "item:Casque_de_test", "matieres": [{"item": "item:gemme", "quantite": 1}]}


# ── Pur ─────────────────────────────────────────────────────────────────────────

def test_seul_l_objet_de_base_exact_est_un_exemplaire():
	porteur = _joueur("item:fer", CASQUE_NOMME, {"item": "item:Casque_de_test_ab12cd34"})
	assert commande_util.exemplaires_base([porteur], "item:Casque_de_test") == [
		{"porteur": "character:j", "index": 1, "nom_perso": "Brise-Crâne"}]


def test_une_position_qui_a_bouge_ne_designe_rien():
	porteur = _joueur("item:fer", CASQUE_NOMME)
	assert commande_util.exemplaire_base([porteur], "item:Casque_de_test",
										 {"porteur": "character:j", "index": 0}) is None
	assert commande_util.exemplaire_base([porteur], "item:Casque_de_test",
										 {"porteur": "character:j", "index": 9}) is None
	assert commande_util.exemplaire_base([porteur], "item:Casque_de_test",
										 {"porteur": "autre", "index": 1}) is None
	assert commande_util.exemplaire_base([porteur], "item:Casque_de_test",
										 {"porteur": "character:j", "index": "x"}) is None
	e = commande_util.exemplaire_base([porteur], "item:Casque_de_test",
									  {"porteur": "character:j", "index": 1})
	assert e["index"] == 1 and e["nom_perso"] == "Brise-Crâne" and e["porteur"] is porteur


def test_le_nom_propre_passe_a_la_piece_livree():
	cmd = commande_util.nouvelle_commande(LIEU, "item:X", {"total": 1}, now=1, nom_perso="Brise-Crâne")
	assert commande_util.ref_livree(cmd)["nom_perso"] == "Brise-Crâne"
	sans = commande_util.nouvelle_commande(LIEU, "item:X", {"total": 1}, now=1)
	assert "nom_perso" not in sans and "nom_perso" not in commande_util.ref_livree(sans)


# ── Endpoints ───────────────────────────────────────────────────────────────────

def test_sans_sa_piece_le_trophee_reste_exige(atelier, monkeypatch):
	rep = _appel(monkeypatch, rc.devis_commande, _joueur(GEMME), SUR_MESURE)
	assert TETE in [m["cle"] for m in rep["manquantes"]]
	assert rep["base_apportee"] is False


def test_la_piece_apportee_remplace_la_recette_et_se_remet_en_entier(atelier, monkeypatch):
	joueur = _joueur(CASQUE_NOMME, GEMME)
	body = dict(SUR_MESURE, base={"porteur": "character:j", "index": 0})
	rep = _appel(monkeypatch, rc.devis_commande, joueur, body)
	assert rep["manquantes"] == [] and rep["base_apportee"] is True
	d = rep["devis"]
	assert d["credit_matieres"] == d["prix_base"]                # la pièce entière est remise
	assert d["total"] == max(1, d["cout_fabrication"] + d["cout_matieres"] + d["supplement_complexite"])
	assert joueur["inventaire"] == [CASQUE_NOMME, GEMME]         # le devis n'écrit rien


def test_passer_prend_la_piece_et_garde_son_nom(atelier, monkeypatch):
	joueur = _joueur(CASQUE_NOMME, GEMME, "item:fer")
	_appel(monkeypatch, rc.passer_commande, joueur,
		   dict(SUR_MESURE, base={"porteur": "character:j", "index": 0}))
	assert joueur["inventaire"] == ["item:fer"]                  # pièce ET gemme prises, pas le fer
	cmd = joueur["commandes"][0]
	assert cmd["statut"] == commande_util.ETAT_PAYEE
	assert cmd["base_item"] == "item:Casque_de_test" and cmd["item"] != "item:Casque_de_test"
	ref = commande_util.ref_livree(cmd)
	assert ref["item"] == cmd["item"] and ref["nom_perso"] == "Brise-Crâne"


def test_une_matiere_manquante_refuse_au_lieu_de_mettre_en_attente(atelier, monkeypatch):
	joueur = _joueur(CASQUE_NOMME)                               # pas de gemme, ni en rayon
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, rc.passer_commande, joueur,
			   dict(SUR_MESURE, base={"porteur": "character:j", "index": 0}))
	assert e.value.status_code == 422 and "Gemme" in e.value.detail
	assert joueur["inventaire"] == [CASQUE_NOMME] and joueur["commandes"] == []


def test_apporter_sa_piece_hors_sur_mesure_est_refuse(atelier, monkeypatch):
	joueur = _joueur(CASQUE_NOMME)
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, rc.passer_commande, joueur,
			   {"item_id": "item:Casque_de_test", "base": {"porteur": "character:j", "index": 0}})
	assert e.value.status_code == 422
	assert joueur["inventaire"] == [CASQUE_NOMME]


def test_une_autre_piece_a_la_position_est_refusee(atelier, monkeypatch):
	joueur = _joueur(GEMME, CASQUE_NOMME)
	with pytest.raises(HTTPException) as e:
		_appel(monkeypatch, rc.passer_commande, joueur,
			   dict(SUR_MESURE, base={"porteur": "character:j", "index": 0}))
	assert e.value.status_code == 422
	assert joueur["inventaire"] == [GEMME, CASQUE_NOMME]


def test_la_liste_des_matieres_offre_les_exemplaires(atelier, monkeypatch):
	joueur = _joueur(CASQUE_NOMME, "item:Casque_de_test")
	rep = _appel(monkeypatch, rc.matieres_sur_mesure, joueur, "item:Casque_de_test")
	assert rep["exemplaires"] == [
		{"porteur": "character:j", "index": 0, "nom": "Brise-Crâne", "chez": ""},
		{"porteur": "character:j", "index": 1, "nom": "Casque cornu", "chez": ""}]
