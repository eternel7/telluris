# tests/test_apport.py
# Quête d'APPORT confiée par un PNJ (utils/apport.py, service `apport`) : offre écrite,
# acceptation → quête `collect` ordinaire, remise partielle puis complète, réception par un
# AUTRE PNJ du même lieu, linter. Contenu : les feuilles d'argentine d'Élise.

import json
import os

from utils import apport, lint_dialogues, quetes

COQ = "lieu:le_coq_de_lutece"
QID = "quete:plantes_d_elise"
ITEM = "item:Feuilles_d_argentine"
CONTENU = os.path.join(os.path.dirname(__file__), "..", "jsons", "pnj_elise_herboriste_a_importer.json")


def _donneur(**offre):
	base = {"id": QID, "titre": "Trois plantes", "item": ITEM, "quantite": 3,
			"recompenses": {"xp": 40}}
	base.update(offre)
	return {"_id": "pnj:elise", "services": {"apport": {"offre": base}}}


def _receveur():
	return {"_id": "pnj:aubergiste", "services": {"apport": {"quete": QID}}}


def _feuilles(n):
	return [{"item": ITEM, "poids": 0.1} for _ in range(n)]


# ── Offre ────────────────────────────────────────────────────────────────────

def test_offre_illisible_ignoree():
	assert apport.offre_spec(_donneur(id="plantes")) is None
	assert apport.offre_spec(_donneur(item="argentine")) is None
	assert apport.offre_spec(_donneur(quantite=0)) is None
	assert apport.offre_spec(_donneur(quantite=True)) is None
	assert apport.offre_spec({"services": {}}) is None


def test_le_receveur_ne_offre_rien_mais_connait_la_quete():
	assert apport.offre_spec(_receveur()) is None
	assert apport.quete_id_de(_receveur()) == QID
	assert apport.quete_id_de(_donneur()) == QID


# ── Cycle de vie ─────────────────────────────────────────────────────────────

def test_accepter_pose_une_quete_collect_ordinaire():
	c = {}
	assert apport.etat(c, _donneur(), COQ)["apport_offert"]
	q = apport.accepter(c, _donneur(), COQ)
	assert q["id"] == QID and q["giver"] == COQ
	assert q["objectif"] == {"type": "collect", "cible": ITEM, "quantite": 3}
	assert c["quetes_actives"] == [q]
	e = apport.etat(c, _donneur(), COQ)
	assert not e["apport_offert"] and e["apport_en_cours"] and not e["apport_possible"]
	assert apport.accepter(c, _donneur(), COQ) is None, "pas deux fois la même quête"


def test_remise_partielle_puis_complete():
	c = {"inventaire": _feuilles(2)}
	apport.accepter(c, _donneur(), COQ)
	assert apport.etat(c, _donneur(), COQ)["apport_possible"]
	q, n, complete = apport.remettre(c, _donneur(), COQ)
	assert (n, complete) == (2, False) and c["inventaire"] == []
	assert apport.reste_a_remettre(q) == 1
	assert not apport.etat(c, _donneur(), COQ)["apport_possible"], "plus rien en poche"
	c["inventaire"] = _feuilles(2)
	q, n, complete = apport.remettre(c, _donneur(), COQ)
	assert (n, complete) == (1, True)
	assert len(c["inventaire"]) == 1, "on ne prend pas plus que le reste à faire"
	apport.archiver(c, q, now=123)
	assert c["quetes_actives"] == []
	assert c["quetes_terminees"][-1]["giver"] == COQ
	assert quetes.quete_reussie(c, QID)
	e = apport.etat(c, _donneur(), COQ)
	assert e["apport_accompli"] and not e["apport_offert"], "offre unique : pas reproposée"


def test_offre_non_unique_reproposee():
	c = {"quetes_terminees": [{"id": QID}]}
	assert apport.etat(c, _donneur(unique=False), COQ)["apport_offert"]
	assert not apport.etat(c, _donneur(), COQ)["apport_offert"]


def test_un_echec_rouvre_l_offre():
	c = {"quetes_terminees": [{"id": QID, "echec": True}]}
	assert apport.etat(c, _donneur(), COQ)["apport_offert"]


def test_un_autre_pnj_du_meme_lieu_recoit_la_remise():
	c = {"inventaire": _feuilles(3)}
	apport.accepter(c, _donneur(), COQ)
	assert apport.etat(c, _receveur(), COQ)["apport_possible"]
	assert not apport.etat(c, _receveur(), COQ)["apport_offert"]
	q, n, complete = apport.remettre(c, _receveur(), COQ)
	assert (n, complete) == (3, True)


def test_la_remise_exige_le_lieu_du_donneur():
	c = {"inventaire": _feuilles(3)}
	apport.accepter(c, _donneur(), COQ)
	assert not apport.etat(c, _receveur(), "lieu:ailleurs")["apport_possible"]
	assert apport.remettre(c, _receveur(), "lieu:ailleurs") == (None, 0, False)
	assert len(c["inventaire"]) == 3


def test_placeholders_depuis_l_offre_puis_le_snapshot():
	nom = lambda iid: "Feuilles d'argentine"
	c = {"inventaire": _feuilles(1)}
	assert apport.placeholders(c, _donneur(), COQ, nom)["reste"] == 3
	apport.accepter(c, _donneur(), COQ)
	apport.remettre(c, _donneur(), COQ)
	p = apport.placeholders(c, _receveur(), COQ, nom)
	assert p == {"objet": "Feuilles d'argentine", "quantite": 3, "reste": 2, "xp": 40, "prime": 0}


# ── Linter ───────────────────────────────────────────────────────────────────

def _doc_lint(services, choix):
	return {"_id": "pnj:x", "type": "pnj", "services": services,
			"dialogue": {"noeud_depart": "a", "noeuds": {
				"a": {"texte": "…", "choix": choix},
				"ok": {"texte": "…", "choix": [{"id": "fin", "next": "fin", "label": "."}]},
			}}}


def test_linter_offre_illisible_et_remise_non_conditionnee():
	doc = _doc_lint({"apport": {"offre": {"id": "x"}, "noeuds": {"remis": "ok", "partiel": "ok", "accepte": "ok"}}},
					[{"id": "r", "label": ".", "action": {"service": "apport", "op": "remettre"}}])
	messages = [t["message"] for t in lint_dialogues.analyser([doc])["trouvailles"]]
	assert any("services.apport.offre" in m for m in messages)
	assert any("apport/remettre" in m and "apport_possible" in m for m in messages)


def test_linter_receveur_sans_quete():
	doc = _doc_lint({"apport": {"noeuds": {"remis": "ok", "partiel": "ok"}}},
					[{"id": "f", "label": ".", "next": "ok"}])
	assert lint_dialogues.analyser([doc])["erreurs"] >= 1


# ── Contenu ──────────────────────────────────────────────────────────────────

def test_contenu_elise_et_aubergiste_partagent_la_quete():
	with open(CONTENU, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)}
	spec = apport.offre_spec(docs["pnj:elise_herboriste"])
	assert spec and spec["item"] in docs, "l'item demandé est livré avec l'import"
	assert apport.quete_id_de(docs["pnj:aubergiste_du_coq_de_lutece"]) == spec["id"]
	rapport = lint_dialogues.analyser(list(docs.values()))
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


# ── Routeur : accepter → remise partielle → remise complète ─────────────────

def test_router_cycle_complet(monkeypatch):
	from routers import pnj as rp
	sauves = []
	monkeypatch.setattr(rp, "get_doc", lambda _id: {"nom": "Feuilles d'argentine"} if _id == ITEM else None)
	monkeypatch.setattr(rp, "save_doc", lambda d: sauves.append(d) or d)
	monkeypatch.setattr(rp, "_inventory_payload", lambda c: {"n": len(c.get("inventaire", []))})
	monkeypatch.setattr(rp, "_vitals_payload", lambda c: {})
	monkeypatch.setattr(rp.quetes, "fiche_details", lambda c, *a, **k: ([], []))
	monkeypatch.setattr(rp.quetes, "recompenser_donneur", lambda *a, **k: None)
	monkeypatch.setattr(rp.recrutement, "groupe_effectif", lambda c, g: [])
	elise = {**_donneur(), "services": {"apport": {**_donneur()["services"]["apport"],
				"noeuds": {"accepte": "a", "partiel": "p", "remis": "r"}}}}
	lieu = {"_id": COQ}
	c = {"inventaire": _feuilles(1), "xp_total": 0, "cuivre": 0}

	rep = {}
	assert rp._resoudre_apport(c, elise, lieu, "accepter", rep)[0] == "a"
	assert rep["apport"] == {"accepte": "Trois plantes"}

	rep = {}
	suivant, dits = rp._resoudre_apport(c, elise, lieu, "remettre", rep)
	assert suivant == "p" and dits["reste"] == 2 and rep["apport"]["depose"] == 1

	c["inventaire"] = _feuilles(2)
	rep = {}
	suivant, dits = rp._resoudre_apport(c, elise, lieu, "remettre", rep)
	assert suivant == "r" and rep["apport"]["remis"] and rep["apport"]["xp"] == 40
	assert quetes.quete_reussie(c, QID) and c["quetes_actives"] == []

	import pytest
	from fastapi import HTTPException
	with pytest.raises(HTTPException):
		rp._resoudre_apport(c, elise, lieu, "remettre", {})
