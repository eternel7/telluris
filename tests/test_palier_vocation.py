# tests/test_palier_vocation.py
#
# Palier de vocation (utils/palier_vocation.py) : monter de n à n+1 exige d'avoir appris au
# moins VOC_TALENTS_MIN talents du niveau n — compétences de la vocation + sorts de son école
# native —, plafonné à ce que le palier offre. Garde de `POST /api/spend_xp_vocation`.

import pytest
from fastapi import HTTPException

from models import character_stats
from utils import palier_vocation


_RULES_VOCS = {"_id": "rules:vocations", "type": "rules", "value": [
	{"id": "moine", "magie": "Sainte", "familles_exclues": ["invocation"]},
	{"id": "guerrier", "magie": ""},
]}


def _comp(cid, voc, niveau, **kw):
	return {"_id": cid, "type": "competence", "vocation": voc, "niveau": niveau, **kw}


def _sort(sid, magie, niveau, **kw):
	return {"_id": sid, "type": "sort", "magie": magie, "niveau": niveau, **kw}


_DOCS = [
	_comp("competence:poing", "moine", 0),
	_comp("competence:souffle", "moine", 0),
	_comp("competence:garde", "moine", 1),
	_comp("competence:charge", "guerrier", 0),
	_sort("sort:benir", "Sainte", 0),
	_sort("sort:ange", "Sainte", 0, famille="invocation"),   # exclu pour le moine
	_sort("sort:feu", "Ignee", 0),                            # autre école : hors palier
]


def _find(docs):
	return lambda sel: [d for d in docs if all(d.get(k) == v for k, v in (sel or {}).items())]


def _perso(niveau=0, comps=(), sorts=(), voc="moine"):
	return {"_id": "character:x", "voc": voc, "vocations_niveaux": {voc: niveau},
			"competences_connues": list(comps), "sorts_connus": list(sorts), "attribute_points": 100}


def _etat(perso, docs=_DOCS):
	return palier_vocation.etat_palier(perso, _find(docs), _RULES_VOCS)


def test_un_seul_talent_ne_suffit_pas():
	e = _etat(_perso(comps=["competence:poing"]))
	assert (e["requis"], e["maitrises"], e["manque"], e["ok"]) == (character_stats.VOC_TALENTS_MIN, 1, 1, False)
	assert "1 talent de niveau 0" in palier_vocation.motif_refus(e)


def test_competence_et_sort_natif_comptent_ensemble():
	assert _etat(_perso(comps=["competence:poing"], sorts=["sort:benir"]))["ok"]


def test_talent_dun_autre_niveau_ou_dune_autre_ecole_ne_compte_pas():
	e = _etat(_perso(comps=["competence:poing", "competence:garde"], sorts=["sort:feu"]))
	assert e["maitrises"] == 1 and not e["ok"]


def test_famille_exclue_hors_du_plafond_mais_comptee_si_connue():
	# Moine niveau 0 : talents apprenables = poing, souffle, benir (ange exclu).
	assert _etat(_perso(sorts=["sort:ange"]))["maitrises"] == 1


def test_exigence_plafonnee_au_contenu_du_palier():
	# Niveau 1 : une seule compétence existe ⇒ une seule exigée.
	e = _etat(_perso(niveau=1, comps=["competence:garde"]))
	assert e["requis"] == 1 and e["ok"]
	# Palier vide ⇒ rien n'est exigé.
	assert _etat(_perso(niveau=2))["ok"]


def test_vocation_sans_magie_ne_compte_que_ses_competences():
	e = _etat(_perso(voc="guerrier", sorts=["sort:benir"]))
	assert (e["requis"], e["maitrises"]) == (1, 0)   # charge seule existe au niveau 0


def test_minimum_lu_dans_la_variable_de_monde(monkeypatch):
	monkeypatch.setattr(character_stats, "VOC_TALENTS_MIN", 3)
	assert _etat(_perso(comps=["competence:poing", "competence:souffle"]))["requis"] == 3


# ── Garde de l'endpoint ──────────────────────────────────────────────────────────

@pytest.fixture
def monter(monkeypatch):
	from routers import user as user_router
	monkeypatch.setattr(user_router, "save_doc", lambda doc: doc)
	monkeypatch.setattr(user_router, "_fiche_payload", lambda character: {})
	monkeypatch.setattr(user_router, "find_docs", _find(_DOCS))
	monkeypatch.setattr(user_router, "get_doc", lambda i: _RULES_VOCS if i == "rules:vocations" else None)

	def appeler(character):
		monkeypatch.setattr(user_router, "_acteur", lambda _u, _b: (character, character))
		return user_router.spend_xp_vocation(object(), {})
	return appeler


def test_endpoint_refuse_sans_rien_depenser(monter):
	perso = _perso(comps=["competence:poing"])
	with pytest.raises(HTTPException) as exc:
		monter(perso)
	assert exc.value.status_code == 422
	assert perso["attribute_points"] == 100 and perso["vocations_niveaux"]["moine"] == 0


def test_endpoint_monte_palier_maitrise(monter):
	assert monter(_perso(comps=["competence:poing", "competence:souffle"]))["voc_niveau"] == 1
