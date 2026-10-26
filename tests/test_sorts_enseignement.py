# tests/test_sorts_enseignement.py
#
# Sorts ENSEIGNÉS par un maître (`enseignement: true`) et sorts qui en AMÉLIORENT un autre
# (`ameliore: "sort:…"`) — Lance de lumière, forme supérieure du Rayon de lumière.
#   • ni liste « 📖 Apprendre », ni grimoire (`utils/grimoires.py`) ;
#   • règles partagées endpoint / service PNJ : `verifier_apprentissage` ;
#   • l'amélioration REMPLACE le sort simple au même rang (connus, épinglés, barre).
# Champs absents ⇒ comportement d'avant (aucune migration). Logique pure.

from utils import grimoires
from utils.sorts import (
	appliquer_apprentissage, cout_apprentissage, etat_enseignement, normaliser_sort,
	sorts_apprenables, verifier_apprentissage,
)


_RULES_VOCS = {"_id": "rules:vocations", "type": "rules", "value": [
	{"id": "paladin", "magie": "Sainte"},
	{"id": "pretre", "magie": "Sainte"},
	{"id": "guerrier", "magie": ""},
]}

RAYON = {"_id": "sort:rayon_de_lumiere", "type": "sort", "nom": "Rayon de lumière",
		 "magie": "Sainte", "niveau": 10, "cout_pm": 55, "cible": "ennemi",
		 "effets": {"degats": "25+3D8"}}
LANCE = {"_id": "sort:lance_de_lumiere", "type": "sort", "nom": "Lance de lumière",
		 "magie": "Sainte", "niveau": 10, "cout_pm": 80, "cible": "ennemi",
		 "effets": {"degats": "50+5D10"}, "enseignement": True,
		 "ameliore": "sort:rayon_de_lumiere"}


def _perso(voc="paladin", niveau=10, points=100, **overrides):
	char = {"_id": "character:test", "voc": voc, "vocations_niveaux": {voc: niveau},
			"sorts_connus": [], "inventaire": [], "slots": {}, "attribute_points": points}
	char.update(overrides)
	return char


def _find(docs):
	return lambda sel: [d for d in docs if d.get("type") == sel.get("type")]


def test_champs_absents_neutres():
	s = normaliser_sort(RAYON)
	assert s["enseignement"] is False and s["ameliore"] is None


def test_un_sort_enseigne_n_est_pas_dans_la_liste_apprendre():
	ids = {s["id"] for s in sorts_apprenables(_perso(), _find([RAYON, LANCE]),
											  lambda ref: None, _RULES_VOCS)}
	assert ids == {"sort:rayon_de_lumiere"}


def test_un_sort_enseigne_n_a_pas_de_grimoire():
	manquants = grimoires.sorts_sans_grimoire_unique([RAYON, LANCE], [])
	assert [s["_id"] for s in manquants] == ["sort:rayon_de_lumiere"]


def test_la_forme_superieure_exige_la_forme_simple():
	lance = normaliser_sort(LANCE)
	code, msg = verifier_apprentissage(_perso(), lance, _RULES_VOCS)
	assert code == 422 and "forme simple" in msg
	assert verifier_apprentissage(_perso(sorts_connus=[RAYON["_id"]]), lance, _RULES_VOCS) is None


def test_toute_l_ecole_sainte_peut_recevoir_l_enseignement():
	lance = normaliser_sort(LANCE)
	assert verifier_apprentissage(_perso("pretre", sorts_connus=[RAYON["_id"]]), lance, _RULES_VOCS) is None
	assert verifier_apprentissage(_perso("guerrier", sorts_connus=[RAYON["_id"]]), lance,
								  _RULES_VOCS)[0] == 422


def test_niveau_et_points_insuffisants():
	lance = normaliser_sort(LANCE)
	assert verifier_apprentissage(_perso(niveau=9, sorts_connus=[RAYON["_id"]]), lance, _RULES_VOCS)
	pauvre = _perso(points=cout_apprentissage(lance) - 1, sorts_connus=[RAYON["_id"]])
	assert "Points insuffisants" in verifier_apprentissage(pauvre, lance, _RULES_VOCS)[1]


def test_l_amelioration_remplace_au_meme_rang():
	lance = normaliser_sort(LANCE)
	char = _perso(sorts_connus=["sort:soin", RAYON["_id"], "sort:benediction"],
				  sorts_epingles=[RAYON["_id"]],
				  slots_actions=[{"type": "attaque", "ref": "cac"},
								 {"type": "sort", "ref": RAYON["_id"]}, None])
	avant = char["attribute_points"]
	appliquer_apprentissage(char, lance)
	assert char["sorts_connus"] == ["sort:soin", LANCE["_id"], "sort:benediction"]
	assert char["sorts_epingles"] == [LANCE["_id"]]
	assert char["slots_actions"][1] == {"type": "sort", "ref": LANCE["_id"]}
	assert char["attribute_points"] == avant - cout_apprentissage(lance)


def test_un_sort_ordinaire_s_ajoute_a_la_fin():
	char = _perso(sorts_connus=["sort:soin"])
	appliquer_apprentissage(char, normaliser_sort(RAYON))
	assert char["sorts_connus"] == ["sort:soin", RAYON["_id"]]
	assert "sorts_epingles" not in char           # clé absente : on ne la crée pas


def test_drapeaux_du_service_enseignement():
	lance = normaliser_sort(LANCE)
	f = etat_enseignement(_perso(), lance, _RULES_VOCS)
	assert f["enseignement_prerequis_manquant"] and not f["enseignement_possible"]
	f = etat_enseignement(_perso(sorts_connus=[RAYON["_id"]]), lance, _RULES_VOCS)
	assert f["enseignement_possible"] and not f["enseignement_connu"]
	f = etat_enseignement(_perso(sorts_connus=[LANCE["_id"]]), lance, _RULES_VOCS)
	assert f["enseignement_connu"] and not f["enseignement_possible"]
	assert etat_enseignement(_perso("guerrier"), lance, _RULES_VOCS)["enseignement_niveau_insuffisant"]
	assert not any(etat_enseignement(_perso(), None, _RULES_VOCS).values())


# ── Router : service PNJ `enseignement` (routers/pnj._resoudre_enseignement) ──────────

def _maitre():
	return {"_id": "pnj:maitre", "type": "pnj", "services": {"enseignement": {
		"sort": LANCE["_id"], "noeuds": {"appris": "appris", "refus": "refus"}}}}


def _router(monkeypatch, sauves):
	from routers import pnj as rp
	docs = {LANCE["_id"]: LANCE, RAYON["_id"]: RAYON, "rules:vocations": _RULES_VOCS}
	monkeypatch.setattr(rp, "get_doc", lambda _id: docs.get(_id))
	monkeypatch.setattr(rp, "save_doc", lambda d: sauves.append(d) or d)
	monkeypatch.setattr(rp.fiche_util, "fiche_resync", lambda c, *a, **k: {"id": c["_id"]})
	return rp


def test_router_le_maitre_transmet_la_lance_a_la_place_du_rayon(monkeypatch):
	sauves = []
	rp = _router(monkeypatch, sauves)
	char = _perso(sorts_connus=[RAYON["_id"]])
	rep = {}
	assert rp._resoudre_enseignement(char, _maitre(), "apprendre", rep) == "appris"
	assert char["sorts_connus"] == [LANCE["_id"]] and sauves == [char]
	assert rep["enseignement"]["appris"]["nom"] == "Lance de lumière"
	assert rep["fiche"] == {"id": char["_id"]}           # resync de la fiche (§10)


def test_router_refus_parle_sans_rien_sauver(monkeypatch):
	sauves = []
	rp = _router(monkeypatch, sauves)
	char = _perso()                                     # le Rayon n'est pas connu
	rep = {}
	assert rp._resoudre_enseignement(char, _maitre(), "apprendre", rep) == "refus"
	assert "forme simple" in rep["enseignement"]["refus"]
	assert sauves == [] and char["sorts_connus"] == []


def test_l_endpoint_refuse_un_sort_enseigne(monkeypatch):
	"""`/api/apprendre_sort` : 403 AVANT tout contrôle (même grimoire en main)."""
	import asyncio
	import pytest
	from fastapi import HTTPException
	from routers import user as ru
	char = _perso(sorts_connus=[RAYON["_id"]])
	monkeypatch.setattr(ru, "_acteur", lambda u, b: (char, char))
	monkeypatch.setattr(ru, "get_doc", lambda _id: {LANCE["_id"]: LANCE}.get(_id))
	with pytest.raises(HTTPException) as exc:
		asyncio.run(ru.apprendre_sort({"id": "u"}, {"sort_id": LANCE["_id"]}))
	assert exc.value.status_code == 403
