# tests/test_vocations.py
#
# Changement de vocation (utils/vocations.py + POST /api/changer_vocation, /api/vocation/options).
# Règles de l'Auteur (11/11/2026) : prix d'une voie NOUVELLE = round(BASE × FACTEUR^(n + k)),
# retour vers une voie CONNUE = min(RETOUR, prix neuf), retour libre hors graphe, rien ne se
# perd, on repart au niveau 0, la spécialité d'un compagnon recruté suit, pas son portrait.
# Les nombres se RELISENT depuis character_stats (§14), sauf les cas chiffrés de l'Auteur.

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

from models import character_stats  # noqa: E402
from utils import vocations  # noqa: E402

RULES_VOCS = {"_id": "rules:vocations", "type": "rules", "value": [
	{"id": "guerrier", "label": "Guerrier", "icon": "⚔️", "magie": "", "blurb": "Pilier."},
	{"id": "barbare", "label": "Barbare", "icon": "🪓", "magie": "", "blurb": "Rage."},
	{"id": "templier", "label": "Templier", "icon": "⚜️", "magie": "Bataille", "blurb": "Gardien."},
	{"id": "paladin", "label": "Paladin", "icon": "🛡", "magie": "Sainte", "blurb": "Routes."},
	{"id": "druide", "label": "Druide", "icon": "🌳", "magie": "Nature", "blurb": "Cycles."},
]}
TRANSITIONS = {"_id": vocations.TRANSITIONS_DOC_ID, "type": "rules", "value": {
	"guerrier": ["paladin", "templier"],
	"barbare": ["druide"],            # sens unique : druide ne mène pas au barbare
	"druide": ["guerrier"],
	"templier": ["guerrier"],
	"paladin": ["guerrier"],
}}


def _perso(voc="guerrier", niveaux=None, points=1000, **extra):
	doc = {"_id": "character:u_1", "type": "character", "voc": voc,
		   "vocations_niveaux": niveaux if niveaux is not None else {voc: 0},
		   "attribute_points": points, "sorts_connus": ["sort:a"],
		   "competences_connues": ["competence:x"], "magies_apprises": {"Noire": 1}}
	doc.update(extra)
	return doc


@pytest.fixture
def prix_auteur(monkeypatch):
	"""Les valeurs de l'Auteur (11/11) — constantes voulues pour les cas chiffrés."""
	monkeypatch.setattr(character_stats, "VOC_CHANGEMENT_BASE", 5)
	monkeypatch.setattr(character_stats, "VOC_CHANGEMENT_FACTEUR", 1.5)
	monkeypatch.setattr(character_stats, "VOC_RETOUR_COUT", 10)


# ── Prix ──────────────────────────────────────────────────────────────────────

def test_prix_nouvelle_suit_niveau_quitte(prix_auteur):
	attendus = {0: 5, 1: 8, 2: 11, 3: 17, 4: 25, 5: 38, 10: 288}
	for n, prix in attendus.items():
		assert vocations.cout_nouvelle(_perso(niveaux={"guerrier": n})) == prix, n


def test_prix_compte_les_vocations_deja_pratiquees(prix_auteur):
	# k = 1 (le barbare déjà pratiqué) : même tarif qu'un niveau de plus.
	p = _perso(niveaux={"guerrier": 4, "barbare": 0})
	assert vocations.nb_autres_pratiquees(p) == 1
	assert vocations.cout_nouvelle(p) == vocations.cout_nouvelle(_perso(niveaux={"guerrier": 5}))


def test_prix_retour_jamais_plus_cher_qu_un_depart_neuf(prix_auteur):
	assert vocations.cout_retour(_perso(niveaux={"guerrier": 4, "barbare": 2})) == 10
	# Niveau 0 sans autre vocation : un départ neuf coûte 5, le retour aussi.
	assert vocations.cout_retour(_perso(niveaux={"guerrier": 0})) == 5


def test_prix_suit_les_variables_de_monde(monkeypatch):
	monkeypatch.setattr(character_stats, "VOC_CHANGEMENT_BASE", 3)
	monkeypatch.setattr(character_stats, "VOC_CHANGEMENT_FACTEUR", 2.0)
	monkeypatch.setattr(character_stats, "VOC_RETOUR_COUT", 1)
	p = _perso(niveaux={"guerrier": 2, "barbare": 0})
	assert vocations.cout_nouvelle(p) == 3 * 2 ** 3
	assert vocations.cout_retour(p) == 1


# ── Options ───────────────────────────────────────────────────────────────────

def test_options_connues_d_abord_puis_nouvelles_du_graphe(prix_auteur):
	p = _perso(niveaux={"guerrier": 4, "barbare": 2})
	opts = vocations.options(p, RULES_VOCS, TRANSITIONS)
	assert [o["id"] for o in opts] == ["barbare", "templier", "paladin"]
	barbare = opts[0]
	assert barbare["connue"] and barbare["niveau"] == 2 and barbare["cout"] == vocations.cout_retour(p)
	assert all(not o["connue"] and o["cout"] == vocations.cout_nouvelle(p) for o in opts[1:])


def test_retour_libre_hors_graphe(prix_auteur):
	# Druide ne mène pas au barbare, mais un ancien barbare peut y revenir.
	p = _perso(voc="druide", niveaux={"barbare": 3, "druide": 0})
	ids = [o["id"] for o in vocations.options(p, RULES_VOCS, TRANSITIONS)]
	assert "barbare" in ids and "guerrier" in ids
	assert vocations.refus(p, "barbare", RULES_VOCS, TRANSITIONS) is None


def test_sans_doc_de_transitions_seuls_les_retours(prix_auteur):
	p = _perso(niveaux={"guerrier": 1, "barbare": 0})
	assert [o["id"] for o in vocations.options(p, RULES_VOCS, None)] == ["barbare"]


# ── Refus ─────────────────────────────────────────────────────────────────────

def test_refus(prix_auteur):
	p = _perso(niveaux={"guerrier": 4}, points=24)
	assert vocations.refus(p, "guerrier", RULES_VOCS, TRANSITIONS)[0] == 422      # déjà la sienne
	assert vocations.refus(p, "druide", RULES_VOCS, TRANSITIONS)[0] == 422        # hors graphe
	assert "Points insuffisants" in vocations.refus(p, "templier", RULES_VOCS, TRANSITIONS)[1]
	p["attribute_points"] = 25
	assert vocations.refus(p, "templier", RULES_VOCS, TRANSITIONS) is None


# ── Application ───────────────────────────────────────────────────────────────

def test_appliquer_ne_perd_rien_et_repart_aspirant(prix_auteur):
	p = _perso(niveaux={"guerrier": 4}, points=30)
	recap = vocations.appliquer_changement(p, "templier", RULES_VOCS, TRANSITIONS)
	assert recap == {"de": "guerrier", "vers": "templier", "retour": False, "cout": 25, "niveau": 0}
	assert p["voc"] == "templier" and p["attribute_points"] == 5
	assert p["vocations_niveaux"] == {"guerrier": 4, "templier": 0}
	assert p["sorts_connus"] == ["sort:a"] and p["competences_connues"] == ["competence:x"]
	assert p["magies_apprises"] == {"Noire": 1}


def test_retour_reprend_le_niveau_acquis(prix_auteur):
	p = _perso(voc="templier", niveaux={"guerrier": 4, "templier": 1}, points=30)
	attendu = vocations.cout_retour(p)          # min(10, 5 × 1,5²) = 10
	recap = vocations.appliquer_changement(p, "guerrier", RULES_VOCS, TRANSITIONS)
	assert recap["retour"] and recap["niveau"] == 4 and recap["cout"] == attendu == 10
	assert vocations.niveau_courant(p) == 4 and p["attribute_points"] == 20


def test_compagnon_recrute_specialite_suit_portrait_reste(prix_auteur):
	av = _perso(niveaux={"guerrier": 4}, points=30, type="aventurier",
				specialite="Pilier.", image="guerrier_m_humain01.jpg")
	av["_id"] = "aventurier:g_1"
	vocations.appliquer_changement(av, "templier", RULES_VOCS, TRANSITIONS)
	assert av["specialite"] == "Gardien." and av["image"] == "guerrier_m_humain01.jpg"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@pytest.fixture
def endpoint(monkeypatch, prix_auteur):
	from routers import user as user_router
	docs = {d["_id"]: d for d in (RULES_VOCS, TRANSITIONS)}
	monkeypatch.setattr(user_router, "get_doc", lambda i: docs.get(i))
	monkeypatch.setattr(user_router, "save_doc", lambda d: docs.__setitem__(d["_id"], d) or d)
	monkeypatch.setattr(user_router, "_fiche_payload", lambda c: {"id": c["_id"], "voc": c["voc"]})

	def appeler(fonction, character, body):
		monkeypatch.setattr(user_router, "_acteur", lambda _u, _b: (character, character))
		# Endpoint `def` (threadpool) ou `async def` selon la route : les deux se jouent ici.
		rendu = getattr(user_router, fonction)(object(), body)
		return asyncio.run(rendu) if asyncio.iscoroutine(rendu) else rendu
	return appeler, docs


def test_endpoint_change_et_resynchronise_la_fiche(endpoint):
	appeler, docs = endpoint
	p = _perso(niveaux={"guerrier": 4}, points=30)
	opts = appeler("vocation_options", p, {})
	assert [o["id"] for o in opts["options"]] == ["templier", "paladin"]
	rep = appeler("changer_vocation", p, {"vocation": "templier"})
	assert rep["voc"] == "templier" and rep["voc_niveau"] == 0 and rep["attribute_points"] == 5
	assert rep["fiche"] == {"id": p["_id"], "voc": "templier"}
	assert docs[p["_id"]]["voc"] == "templier"


def test_endpoint_refuse_sans_rien_ecrire(endpoint):
	appeler, docs = endpoint
	p = _perso(niveaux={"guerrier": 4}, points=3)
	with pytest.raises(HTTPException) as exc:
		appeler("changer_vocation", p, {"vocation": "templier"})
	assert exc.value.status_code == 422
	assert p["voc"] == "guerrier" and p["attribute_points"] == 3 and p["_id"] not in docs


def test_endpoint_refuse_une_monture(endpoint):
	appeler, _docs = endpoint
	monture = _perso()
	monture["_id"] = "monture:m_1"
	with pytest.raises(HTTPException) as exc:
		appeler("vocation_options", monture, {})
	assert exc.value.status_code == 403
