"""Carte d'aventurier PERDUE : le réceptionniste se moque et refait la carte au même rang.

1. **`pnj.don_a_remplacer`** : don `unique` localisé, carte absente du sac, personnage déjà
   inscrit DANS CETTE cité — et rien d'autre.
2. **Le contenu** (`dev/gen_carte_perdue.py`, rejoué contre le dernier dump) : chaque
   réceptionniste propose « j'ai perdu ma carte » au seul inscrit sans carte, jamais en même
   temps que l'inscription ; Borin, qui inscrit par sa première mission, n'ouvre le don qu'à
   l'inscrit — la condition, revalidée au serveur, est le verrou.
3. Le linter connaît le flag et le nœud.
"""

import glob
import json
import os

import pytest
from fastapi import HTTPException

from dev import gen_carte_perdue as g
from utils import lint_dialogues, pnj

CITE = "lieu:lutecia"
DON = {"item": "item:carte_aventurier", "unique": True, "lieu_parent": "auto"}


def _inscrit(cites):
	return lambda character, cite: cite in cites


# ── Le prédicat pur ──────────────────────────────────────────────────────────────

def test_carte_perdue_par_un_inscrit_est_a_remplacer():
	assert pnj.don_a_remplacer({}, DON, CITE, False, _inscrit({CITE})) is True


def test_carte_au_sac_ou_inconnu_au_registre_rien_a_remplacer():
	assert pnj.don_a_remplacer({}, DON, CITE, True, _inscrit({CITE})) is False
	# Inscrit AILLEURS : c'est une inscription, pas un remplacement.
	assert pnj.don_a_remplacer({}, DON, CITE, False, _inscrit({"lieu:auxerre"})) is False


def test_seul_un_don_unique_et_localise_se_remplace():
	assert pnj.don_a_remplacer({}, {**DON, "unique": False}, CITE, False, _inscrit({CITE})) is False
	assert pnj.don_a_remplacer({}, DON, None, False, _inscrit({None})) is False
	assert pnj.don_a_remplacer({}, {"unique": True}, CITE, False, _inscrit({CITE})) is False


def test_le_linter_connait_le_flag_et_le_noeud():
	assert "don_a_remplacer" in lint_dialogues.FLAGS_CONNUS
	assert "remplacement" in lint_dialogues.DON_REMPLACEMENT


# ── Le contenu, rejoué contre le dernier dump ────────────────────────────────────

def _dump():
	dumps = sorted(glob.glob(os.path.join(g.RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		pytest.skip("aucun dump")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}


def _docs_generes():
	docs = _dump()
	return {pid: g.appliquer(json.loads(json.dumps(docs[pid]))) for pid in g.receptionnistes(docs)}


def _visibles(doc, flags):
	ctx = {"flags": flags, "prenom": "Greta", "placeholders": {}}
	return {c["id"] for c in pnj._choix_visibles(doc, doc["dialogue"]["noeud_depart"], ctx)}


def test_chaque_receptionniste_a_sa_moquerie():
	generes = _docs_generes()
	assert set(generes) == set(g.MOQUERIES)
	for pid, doc in generes.items():
		assert doc["services"]["don"]["noeuds"]["remplacement"] == g.NOEUD, pid
		assert "{rang}" in doc["dialogue"]["noeuds"][g.NOEUD]["texte"], pid


def test_perdue_le_remplacement_jamais_l_inscription():
	for pid, doc in _docs_generes().items():
		perdue = _visibles(doc, {"don_recu": False, "don_a_remplacer": True})
		assert g.CHOIX_ID in perdue and "inscription" not in perdue, pid
		au_sac = _visibles(doc, {"don_recu": True, "don_a_remplacer": False})
		assert g.CHOIX_ID not in au_sac and "inscription" not in au_sac, pid


def test_le_non_inscrit_s_inscrit_et_borin_reste_la_premiere_mission():
	for pid, doc in _docs_generes().items():
		vus = _visibles(doc, {"don_recu": False, "don_a_remplacer": False})
		assert g.CHOIX_ID not in vus, pid
		if pid == g.BORIN:
			# Aucune inscription par le don : la carte d'Auxerre se gagne en mission.
			assert "rang_guilde" not in doc["services"]["don"]
		else:
			assert "inscription" in vus, pid


def test_le_contenu_passe_le_linter():
	rapport = lint_dialogues.analyser(list(_docs_generes().values()))
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


def test_regeneration_idempotente():
	for pid, doc in _docs_generes().items():
		assert g.appliquer(json.loads(json.dumps(doc))) == doc, pid


# ── Router : flag du contexte et remise ──────────────────────────────────────────

def _router(monkeypatch, character):
	import asyncio
	import routers.pnj as rp
	pnj_doc = {"_id": "pnj:x", "services": {"don": {
		**DON, "quantite": 1, "rang_guilde": "F",
		"noeuds": {"fait": "faite", "remplacement": "refaite", "trop_charge": "t", "sans_fonds": "s"}}},
		"dialogue": {"noeud_depart": "a", "noeuds": {
			"a": {"texte": "?", "choix": [
				{"id": "inscription", "label": "i", "condition": {"don_recu": False, "don_a_remplacer": False},
				 "action": {"service": "don"}},
				{"id": "perdue", "label": "p", "condition": {"don_a_remplacer": True},
				 "action": {"service": "don"}}]},
			"faite": {"texte": "Bienvenue.", "choix": []},
			"refaite": {"texte": "Perdue ! Rang {rang}.", "choix": []}}}}
	lieu = {"_id": "lieu:guilde", "lieu_parent": CITE}
	carte = {"_id": "item:carte_aventurier", "nom": "Carte d'aventurier", "poids": 0.05}
	monkeypatch.setattr(rp, "get_doc", lambda i: carte if i == carte["_id"] else None)
	monkeypatch.setattr(rp, "find_docs", lambda *a, **k: [])
	monkeypatch.setattr(rp, "save_doc", lambda d: d)
	monkeypatch.setattr(rp, "get_selected_character", lambda u: character)
	monkeypatch.setattr(rp, "_pnj_du_lieu", lambda c, pid: ({}, pnj_doc, lieu))
	monkeypatch.setattr(rp.transport, "traiter_expirations", lambda *a, **k: [])
	monkeypatch.setattr(rp, "_inventory_payload", lambda c: {})
	monkeypatch.setattr(rp, "carried_weight", lambda c: 0)
	monkeypatch.setattr(rp, "charge_max_of", lambda c: 100)
	monkeypatch.setattr(rp, "tirer_poids", lambda d: 0.05)
	return lambda choix_id: asyncio.run(rp.pnj_dialogue_choix({"_id": "user:u"}, {"noeud": "a", "choix_id": choix_id}))


def test_router_carte_perdue_refaite_au_meme_rang(monkeypatch):
	character = {"_id": "character:u_1", "rangs_guilde": {CITE: "C"}, "inventaire": []}
	choisir = _router(monkeypatch, character)
	with pytest.raises(HTTPException):
		choisir("inscription")          # un inscrit ne se RÉ-inscrit pas
	r = choisir("perdue")
	assert r["don"]["remplacement"] is True
	assert "Rang C" in r["noeud"]["texte"]
	assert character["rangs_guilde"] == {CITE: "C"}
	assert character["inventaire"][-1]["lieu_parent"] == CITE
	with pytest.raises(HTTPException):
		choisir("perdue")               # la carte est revenue au sac


def test_router_premiere_inscription_inchangee(monkeypatch):
	character = {"_id": "character:u_1", "inventaire": []}
	choisir = _router(monkeypatch, character)
	with pytest.raises(HTTPException):
		choisir("perdue")
	r = choisir("inscription")
	assert r["don"]["remplacement"] is False and r["noeud"]["texte"] == "Bienvenue."
	assert character["rangs_guilde"] == {CITE: "F"}
