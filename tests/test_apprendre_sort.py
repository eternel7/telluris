# tests/test_apprendre_sort.py
#
# Garde d'apprentissage de `POST /api/apprendre_sort` (routers/user.py). L'endpoint doit
# appliquer la MÊME règle que `sorts_apprenables`, qui alimente la liste affichée : école
# de magie pratiquée (native ou achetée) à un niveau suffisant — et NON la vocation du sort.
#
# Bug d'origine : le garde testait `sort["vocation"] in vocations_niveaux`, si bien qu'un
# moine (école Sainte) se voyait proposer « Soin mineur » (sort de prêtre, école Sainte)
# puis refuser en 422 « Niveau de vocation insuffisant ». Cassait aussi le lettré, qui
# achète une école mais garde sa vocation.
#
# L'endpoint ne touche la base qu'à travers `get_doc`/`save_doc` (importés dans le module),
# et le porteur par `_acteur` : les trois sont monkeypatchés, pas de CouchDB requis.

import asyncio

import pytest
from fastapi import HTTPException


# rules:vocations minimal — moine et prêtre partagent l'école Sainte ; guerrier n'en a pas.
_RULES_VOCS = {"_id": "rules:vocations", "type": "rules", "value": [
	{"id": "moine", "magie": "Sainte"},
	{"id": "pretre", "magie": "Sainte"},
	{"id": "guerrier", "magie": ""},
	{"id": "lettre", "magie": "Illusoire"},
]}

# Le sort réel qui a révélé le bug : vocation `pretre`, école `Sainte`, niveau 0.
_SOIN_MINEUR = {
	"_id": "sort:soin_mineur", "type": "sort", "nom": "Soin mineur", "icon": "✝️",
	"vocation": "pretre", "magie": "Sainte", "niveau": 0, "cout_pm": 8,
	"cible": "soi", "portee": 0, "effets": {"pv": 12},
}

_GRIMOIRE = {
	"_id": "item:grimoire_soin_mineur", "type": "item", "nom": "Grimoire : Soin mineur",
	"categorie": "livre", "sous_categorie": "grimoire", "poids": 1.0,
	"sorts": ["sort:soin_mineur"],
}


def _perso(**overrides):
	"""Aliénor Avale-Tout, réduite à ce que lit l'endpoint : moine niveau 1, grimoire au
	sac, 2 points — soit exactement le coût d'un sort de niveau 0."""
	doc = {
		"_id": "aventurier:alienor", "type": "aventurier", "prenom": "Aliénor",
		"voc": "moine", "vocations_niveaux": {"moine": 1},
		"attribute_points": 2, "sorts_connus": [],
		"inventaire": [{"item": "item:grimoire_soin_mineur", "poids": 1.0}],
		"slots": {},
	}
	doc.update(overrides)
	return doc


@pytest.fixture
def endpoint(monkeypatch):
	"""`apprendre_sort` câblé sur une base en mémoire. Renvoie `(appeler, docs)` où
	`appeler(character, sort_id)` exécute la coroutine et rend sa réponse."""
	from routers import user as user_router

	docs = {d["_id"]: d for d in (_RULES_VOCS, _SOIN_MINEUR, _GRIMOIRE)}
	monkeypatch.setattr(user_router, "get_doc", lambda doc_id: docs.get(doc_id))
	monkeypatch.setattr(user_router, "save_doc", lambda doc: docs.__setitem__(doc["_id"], doc) or doc)
	monkeypatch.setattr(user_router, "find_docs", lambda sel: [
		d for d in docs.values() if all(d.get(k) == v for k, v in (sel or {}).items())
	])
	# `resolve_item_ref` (utils.characters) lit la vraie base : on le rebranche sur `docs`
	# pour que le grimoire du sac soit résolvable. Une réf est un id ou un {item, poids}.
	monkeypatch.setattr(user_router, "resolve_item_ref",
	                    lambda ref: docs.get(ref if isinstance(ref, str) else (ref or {}).get("item")))

	def appeler(character, sort_id="sort:soin_mineur"):
		docs[character["_id"]] = character
		monkeypatch.setattr(user_router, "_acteur", lambda _u, _b: (character, character))
		return asyncio.run(user_router.apprendre_sort(None, {"sort_id": sort_id}))

	return appeler, docs


# ── Le cas d'Aliénor : école partagée, vocation différente ───────────────────────

def test_ecole_native_partagee_vocation_differente(endpoint):
	"""Moine (Sainte) apprenant un sort de prêtre (Sainte) : la vocation diffère, l'école
	non → apprentissage accepté, points débités."""
	appeler, _docs = endpoint
	char = _perso()
	res = appeler(char)

	assert "sort:soin_mineur" in res["sorts_connus"]
	assert res["attribute_points"] == 0          # 2 − (0+1) × SORT_COUT_COEFF
	assert char["sorts_connus"] == ["sort:soin_mineur"]


def test_vocation_sans_magie_refusee(endpoint):
	"""Un guerrier (`magie: ""`) ne pratique aucune école → `niveau_ecole` None → 422."""
	appeler, _docs = endpoint
	char = _perso(voc="guerrier", vocations_niveaux={"guerrier": 5})

	with pytest.raises(HTTPException) as exc:
		appeler(char)
	assert exc.value.status_code == 422
	assert "École de magie" in exc.value.detail


def test_niveau_ecole_insuffisant_refuse(endpoint, monkeypatch):
	"""Même école, mais le sort demande un niveau au-dessus de celui du perso."""
	appeler, docs = endpoint
	docs["sort:soin_mineur"] = dict(_SOIN_MINEUR, niveau=3)
	char = _perso()                                  # moine niveau 1

	with pytest.raises(HTTPException) as exc:
		appeler(char)
	assert exc.value.status_code == 422


# ── Lettré : l'école ACHETÉE doit ouvrir l'apprentissage ─────────────────────────

def test_lettre_ecole_achetee(endpoint):
	"""Le lettré (natif Illusoire) ayant acheté Sainte peut y apprendre — c'est le cas que
	l'ancien garde par vocation rendait définitivement infranchissable."""
	appeler, _docs = endpoint
	char = _perso(voc="lettre", vocations_niveaux={"lettre": 1},
	              magies_apprises={"Sainte": 0})
	res = appeler(char)
	assert "sort:soin_mineur" in res["sorts_connus"]


def test_lettre_ecole_achetee_niveau_trop_bas(endpoint, monkeypatch):
	"""École achetée au niveau 0 → un sort de niveau 1 de cette école reste refusé."""
	appeler, docs = endpoint
	docs["sort:soin_mineur"] = dict(_SOIN_MINEUR, niveau=1)
	char = _perso(voc="lettre", vocations_niveaux={"lettre": 1},
	              magies_apprises={"Sainte": 0})

	with pytest.raises(HTTPException) as exc:
		appeler(char)
	assert exc.value.status_code == 422


# ── Non-régression ───────────────────────────────────────────────────────────────

def test_sort_sans_champ_magie_repli_par_vocation(endpoint, monkeypatch):
	"""Sort d'avant la feature « école » (pas de champ `magie`) : `magie_de_sort` dérive
	l'école de sa vocation → un prêtre l'apprend toujours, sans réimport de données."""
	appeler, docs = endpoint
	docs["sort:soin_mineur"] = {k: v for k, v in _SOIN_MINEUR.items() if k != "magie"}
	char = _perso(voc="pretre", vocations_niveaux={"pretre": 1})
	res = appeler(char)
	assert "sort:soin_mineur" in res["sorts_connus"]


def test_grimoire_requis_toujours_applique(endpoint):
	"""Le garde d'école ne court-circuite pas le grimoire : sac vide → 409."""
	appeler, _docs = endpoint
	char = _perso(inventaire=[])

	with pytest.raises(HTTPException) as exc:
		appeler(char)
	assert exc.value.status_code == 409


def test_points_insuffisants(endpoint):
	appeler, _docs = endpoint
	char = _perso(attribute_points=1)

	with pytest.raises(HTTPException) as exc:
		appeler(char)
	assert exc.value.status_code == 422
	assert "Points insuffisants" in exc.value.detail


def test_sort_deja_connu(endpoint):
	appeler, _docs = endpoint
	char = _perso(sorts_connus=["sort:soin_mineur"])

	with pytest.raises(HTTPException) as exc:
		appeler(char)
	assert exc.value.status_code == 422
	assert exc.value.detail == "Sort déjà connu"
