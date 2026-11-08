"""Service PNJ `vente` (prix fixe, plusieurs articles) et l'Architecte de la Cour des Arches
qui vend les trois copies de contenants (`dev/gen_architecte_contenants.py`).

Décisions de l'Auteur : copies vendues à PRIX FIXE par un PNJ Architecte de l'institut, sans
stock, sans fabrication, sans condition de rang (02/11) ; à la Cour des Arches, avec Aélis (08/11).
"""

import glob
import json
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_architecte_contenants as gen
from utils import lint_dialogues, pnj

BESACE = {"_id": "item:besace_profonde", "type": "item", "nom": "Besace profonde", "icon": "👜",
		  "poids": 0.5, "contenant": {"capacite_kg": 100}, "valeur": [{"cu": 10000}, {"cu": 10000}]}
URNE = {"_id": "item:urne_interieure", "type": "item", "nom": "Urne intérieure", "icon": "🏺",
		"poids": 8, "contenant": {"capacite_kg": 300}, "valeur": [{"cu": 40000}, {"cu": 40000}]}
COFFRE = {"_id": "item:coffre_de_retrait", "type": "item", "nom": "Coffre de retrait", "icon": "🗃️",
		  "poids": 20, "contenant": {"capacite_kg": 1000}, "valeur": [{"cu": 150000}, {"cu": 150000}]}
ITEMS = {d["_id"]: d for d in (BESACE, URNE, COFFRE)}
VENDEUR = gen.doc_pnj([BESACE, URNE, COFFRE])


def _dump() -> dict:
	dumps = sorted(glob.glob(os.path.join(gen.RACINE, "jsons", "telluris-dump-*.json")))
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}


# ── utils/pnj.article_en_vente ─────────────────────────────────────────────────

def test_article_en_vente_lit_le_prix_fixe_de_l_article():
	for d in (BESACE, URNE, COFFRE):
		assert pnj.article_en_vente(VENDEUR, d["_id"]) == {"item": d["_id"], "cout_cuivre": d["valeur"][0]["cu"]}


def test_article_absent_ou_illisible_n_est_pas_vendu():
	assert pnj.article_en_vente(VENDEUR, "item:sac_de_rhiannon") is None
	assert pnj.article_en_vente(VENDEUR, None) is None
	assert pnj.article_en_vente({}, BESACE["_id"]) is None
	for cout in (None, "beaucoup", -1):
		doc = {"services": {"vente": {"articles": [{"item": BESACE["_id"], "cout_cuivre": cout}]}}}
		assert pnj.article_en_vente(doc, BESACE["_id"]) is None, cout   # jamais gratuit par défaut


# ── Router : routers/pnj._resoudre_vente ──────────────────────────────────────

def _router(monkeypatch, sauves, charge=0.0, charge_max=100.0):
	from routers import pnj as rp
	monkeypatch.setattr(rp, "get_doc", lambda _id: ITEMS.get(_id))
	monkeypatch.setattr(rp, "save_doc", lambda d: sauves.append(d) or d)
	monkeypatch.setattr(rp, "carried_weight", lambda c: charge)
	monkeypatch.setattr(rp, "charge_max_of", lambda c: charge_max)
	monkeypatch.setattr(rp, "_inventory_payload", lambda c: {"n": len(c.get("inventaire", []))})
	return rp


def _achat(rp, character, item_id):
	contexte, reponse = {"placeholders": {}}, {}
	suivant = rp._resoudre_vente(character, VENDEUR, {"service": "vente", "op": "acheter", "item": item_id},
								 contexte, reponse)
	return suivant, contexte["placeholders"], reponse


def test_achat_debite_le_prix_et_remet_l_objet(monkeypatch):
	sauves = []
	rp = _router(monkeypatch, sauves)
	char = {"_id": "character:x", "or": 2, "argent": 0, "cuivre": 0, "inventaire": []}
	suivant, dits, reponse = _achat(rp, char, BESACE["_id"])
	assert suivant == "vendu"
	assert char["inventaire"] == [{"item": BESACE["_id"], "poids": BESACE["poids"]}]
	assert reponse["purse"] == {"or": 1, "argent": 0, "cuivre": 0}
	assert reponse["vente"]["item"] == BESACE["_id"] and reponse["inventaire_payload"] == {"n": 1}
	assert dits == {"objet": "Besace profonde", "prix": "1 or"}
	assert sauves == [char]


def test_bourse_trop_legere_ne_touche_a_rien(monkeypatch):
	sauves = []
	rp = _router(monkeypatch, sauves)
	char = {"_id": "character:x", "or": 3, "argent": 99, "cuivre": 99, "inventaire": []}
	suivant, dits, reponse = _achat(rp, char, URNE["_id"])
	assert suivant == "sans_fonds" and dits["prix"] == "4 or"
	assert (char["or"], char["argent"], char["cuivre"], char["inventaire"]) == (3, 99, 99, [])
	assert "vente" not in reponse and sauves == []


def test_sac_trop_lourd_ne_debite_rien(monkeypatch):
	sauves = []
	rp = _router(monkeypatch, sauves, charge=90.0, charge_max=100.0)
	char = {"_id": "character:x", "or": 20, "inventaire": []}
	suivant, _, reponse = _achat(rp, char, COFFRE["_id"])    # 20 kg de trop
	assert suivant == "trop_charge"
	assert char["or"] == 20 and char["inventaire"] == [] and sauves == []


def test_objet_non_vendu_ou_op_inconnue_refuse_en_422(monkeypatch):
	rp = _router(monkeypatch, [])
	char = {"_id": "character:x", "or": 99, "inventaire": []}
	for action in ({"service": "vente", "op": "acheter", "item": "item:sac_de_rhiannon"},
				   {"service": "vente", "op": "voler", "item": BESACE["_id"]}):
		with pytest.raises(HTTPException) as e:
			rp._resoudre_vente(char, VENDEUR, action, {"placeholders": {}}, {})
		assert e.value.status_code == 422
	assert char["inventaire"] == [] and char["or"] == 99


# ── Linter ────────────────────────────────────────────────────────────────────

def test_le_linter_accepte_l_architecte():
	res = lint_dialogues.analyser([VENDEUR])
	assert (res["erreurs"], res["avertissements"]) == (0, 0), res["trouvailles"]


def test_le_linter_refuse_un_achat_hors_catalogue_et_un_article_illisible():
	doc = json.loads(json.dumps(VENDEUR))
	doc["dialogue"]["noeuds"]["catalogue"]["choix"][0]["action"]["item"] = "item:sac_de_rhiannon"
	doc["services"]["vente"]["articles"].append({"item": "item:x", "cout_cuivre": "cher"})
	messages = [t["message"] for t in lint_dialogues.analyser([doc])["trouvailles"] if t["niveau"] == "erreur"]
	assert any("sac_de_rhiannon" in m for m in messages)
	assert any("article illisible" in m for m in messages)


# ── Contenu, contre le dernier dump ───────────────────────────────────────────

def test_le_contenu_vend_les_trois_copies_au_prix_du_dump():
	dump = _dump()
	pnj_doc, lieu = gen.generer(dump)
	assert [a["item"] for a in pnj_doc["services"]["vente"]["articles"]] == list(gen.COPIES)
	for a in pnj_doc["services"]["vente"]["articles"]:
		valeur = dump[a["item"]]["valeur"]
		assert a["cout_cuivre"] == valeur[0]["cu"] == valeur[1]["cu"]
	# Un choix d'achat par copie, chacun lisible par le moteur.
	achats = [c["action"]["item"] for c in pnj_doc["dialogue"]["noeuds"]["catalogue"]["choix"] if c.get("action")]
	assert achats == list(gen.COPIES)


def test_l_architecte_rejoint_aelis_a_la_cour_sans_rien_lui_retirer():
	dump = _dump()
	_, lieu = gen.generer(dump)
	avant = dump[gen.LIEU_ID]
	assert lieu["_id"] == gen.LIEU_ID and "_rev" not in lieu
	assert lieu["pnj"][:-1] == avant["pnj"]                 # Aélis et ses conditions intactes
	assert lieu["pnj"][-1]["character"] == gen.PNJ_ID and lieu["pnj"][-1]["probabilite"] == 1
	assert {k: v for k, v in lieu.items() if k != "pnj"} == {k: v for k, v in avant.items()
															 if k not in ("pnj", "_rev")}
	# Idempotent : rejoué sur son propre résultat, rien ne bouge.
	assert gen.lieu_avec_architecte(lieu) == lieu


def test_le_portrait_existe():
	assert os.path.isfile(os.path.join(gen.RACINE, "templates", "resources", "pnj", gen.PORTRAIT))

