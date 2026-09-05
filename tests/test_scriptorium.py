"""utils/scriptorium.py + routers/scriptorium.py.

Deux mécaniques distinctes à couvrir séparément :

1. L'écrit personnel (`POST /api/scriptorium/ecrire`) — même règle papier/encre/plume que
   l'annonce d'auberge, mais produit un item transportable et non un message.
2. La production automatique (`recettes_effectives`/`recettes_virtuelles`) — recettes
   construites EN MÉMOIRE, jamais persistées, scopées au lieu_parent du scriptorium qui
   tick ; au plus UN sujet par pool (sort/recette/carte) et par appel.
"""

import asyncio

import pytest

from models import character_stats
from utils import auberge
from utils import characters
from utils import scriptorium


PAPIER = {"_id": "item:Papier", "type": "item", "categorie": "composant",
		  "sous_categorie": "papier"}
ENCRE = {"_id": "item:Encre", "type": "item", "categorie": "composant",
		 "sous_categorie": "encre"}
PLUME = {"_id": "item:Plume_d_oie", "type": "item", "categorie": "outil",
		 "sous_categorie": "plume_a_ecrire"}

CARACTS = {"V": 5, "F": 40, "R": 40, "Ag": 40, "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40}

SCRIPTORIUM = {"_id": "lieu:scriptorium", "type": "lieu", "categorie": "scriptorium",
			   "label": "Le Codex", "lieu_parent": "lieu:auxerre"}
ETABLE = {"_id": "lieu:etable", "type": "lieu", "categorie": "etable",
		  "lieu_parent": "lieu:auxerre"}


def _perso(**champs):
	base = {
		"_id": "character:u_1", "type": "character", "lieu": "lieu:scriptorium",
		"prenom": "Greta", "nom": "Hazgard", "cite": "lieu:auxerre",
		"inventaire": [], "slots": {}, "groupe": [], "montures": [],
		"caracteristiques_current": dict(CARACTS),
		"currentPV": 1, "currentPM": 0,
		"or": 5, "argent": 0, "cuivre": 0,
	}
	base.update(champs)
	return base


def _fournitures(**overrides):
	inv = [PAPIER["_id"], ENCRE["_id"], PLUME["_id"]]
	return {"inventaire": inv, **overrides}


# ── Point 1 : l'écrit personnel ─────────────────────────────────────────────────

def test_lieu_est_scriptorium_categorie_ou_tag():
	assert scriptorium.lieu_est_scriptorium(SCRIPTORIUM) is True
	assert scriptorium.lieu_est_scriptorium({"categorie": "etable", "tags": ["scriptorium"]}) is True
	assert scriptorium.lieu_est_scriptorium(ETABLE) is False
	assert scriptorium.lieu_est_scriptorium(None) is False


def test_nouveau_livre_et_titre():
	auteur = _perso()
	ref = scriptorium.nouveau_livre(auteur, "Il pleuvait sur Auxerre.")
	assert ref["item"] == scriptorium.ITEM_LIVRE_ECRIT_ID
	assert ref["texte"] == "Il pleuvait sur Auxerre."
	assert ref["auteur_nom"] == "Greta Hazgard"
	assert scriptorium.titre_livre("Manuscrit relié", ref) == "Manuscrit relié de Greta Hazgard"
	assert scriptorium.titre_livre("Manuscrit relié", {}) == "Manuscrit relié"


@pytest.fixture
def monde(monkeypatch):
	"""`routers/scriptorium` câblé sur une base en mémoire."""
	from routers import scriptorium as rs

	item_livre = {"_id": scriptorium.ITEM_LIVRE_ECRIT_ID, "type": "item",
				  "nom": "Manuscrit relié", "categorie": "livre",
				  "sous_categorie": "livre_ecrit", "slots": [], "poids": 0.3}
	docs = {d["_id"]: d for d in (SCRIPTORIUM, ETABLE, PAPIER, ENCRE, PLUME, item_livre)}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def find_docs_fn(selector, fields=None):
		return [d for d in list(docs.values())
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	for mod in (rs, auberge, scriptorium, characters):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
	return {"docs": docs, "rs": rs}


def _appel(monde, character, coro_fn, *args):
	rs = monde["rs"]
	monde["docs"][character["_id"]] = character
	origine = rs.get_selected_character
	try:
		rs.get_selected_character = lambda _u: character
		resultat = coro_fn(*args)
		return asyncio.run(resultat) if asyncio.iscoroutine(resultat) else resultat
	finally:
		rs.get_selected_character = origine


def test_ecrire_refuse_hors_scriptorium(monde):
	from fastapi import HTTPException
	char = _perso(lieu="lieu:etable", **_fournitures())
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rs"].ecrire_scriptorium, None, {"texte": "salut"})
	assert e.value.status_code == 403


def test_ecrire_refuse_sans_fournitures(monde):
	from fastapi import HTTPException
	char = _perso(inventaire=[])
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rs"].ecrire_scriptorium, None, {"texte": "salut"})
	assert e.value.status_code == 422
	assert "papier" in str(e.value.detail)


def test_ecrire_refuse_texte_vide(monde):
	from fastapi import HTTPException
	char = _perso(**_fournitures())
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rs"].ecrire_scriptorium, None, {"texte": "   "})
	assert e.value.status_code == 422


def test_ecrire_depense_papier_et_encre_garde_la_plume(monde):
	char = _perso(**_fournitures())
	data = _appel(monde, char, monde["rs"].ecrire_scriptorium, None, {"texte": "Il pleuvait."})
	assert set(data["consomme"]) == {"papier", "encre"}
	assert PLUME["_id"] in char["inventaire"]
	assert PAPIER["_id"] not in char["inventaire"]
	assert ENCRE["_id"] not in char["inventaire"]
	livres = [r for r in char["inventaire"] if isinstance(r, dict)
			  and r.get("item") == scriptorium.ITEM_LIVRE_ECRIT_ID]
	assert len(livres) == 1 and livres[0]["texte"] == "Il pleuvait."
	assert data["livre"]["nom"] == "Manuscrit relié de Greta Hazgard"
	assert data["livre"]["description"] == "Il pleuvait."
	assert "inventaire_payload" in data  # écrivain == principal


def test_ecrire_par_un_compagnon_ne_publie_pas_inventaire_du_principal(monde, monkeypatch):
	from utils import expedition
	principal = _perso()
	compagnon = {"_id": "aventurier:compagnon", "type": "aventurier",
				 "prenom": "Bran", "nom": "Osier",
				 "caracteristiques_current": dict(CARACTS), **_fournitures()}
	monkeypatch.setattr(expedition, "membres", lambda c, get_doc_fn=None: [principal, compagnon])
	data = _appel(monde, principal, monde["rs"].ecrire_scriptorium, None,
				  {"texte": "Notes de route.", "ecrivain_id": compagnon["_id"]})
	assert data["ecrivain_compagnon"] is True
	assert data["ecrivain"] == "Bran Osier"
	assert "inventaire_payload" not in data
	assert principal["inventaire"] == []  # le sac du principal n'a pas bougé
	assert any(isinstance(r, dict) and r.get("item") == scriptorium.ITEM_LIVRE_ECRIT_ID
			   for r in compagnon["inventaire"])


def test_ecrire_compagnon_inconnu_refuse(monde, monkeypatch):
	from fastapi import HTTPException
	from utils import expedition
	principal = _perso()
	monkeypatch.setattr(expedition, "membres", lambda c, get_doc_fn=None: [principal])
	with pytest.raises(HTTPException) as e:
		_appel(monde, principal, monde["rs"].ecrire_scriptorium, None,
			   {"texte": "salut", "ecrivain_id": "aventurier:fantome"})
	assert e.value.status_code == 403


# ── Point 2 : production automatique ────────────────────────────────────────────

GRIMOIRE = {"_id": "item:grimoire_test", "type": "item", "sous_categorie": "grimoire",
			"sorts": ["sort:eclair", "sort:soin"]}
SORT_ECLAIR = {"_id": "sort:eclair", "type": "sort", "nom": "Éclair", "niveau": 2,
			   "cout_pm": 4, "magie": "elementaire", "cible": "ennemi", "jet": "magique"}
SORT_SOIN = {"_id": "sort:soin", "type": "sort", "nom": "Soin", "niveau": 1}
RECETTE_PAIN = {"_id": "recette:pain", "type": "recette", "lieu_categorie": "boulangerie",
				"objet_final": "pain", "quantite_produite": 2,
				"matieres_premieres": [{"item": "item:Farine", "quantite": 2}]}
FARINE = {"_id": "item:Farine", "type": "item", "nom": "Farine"}

MAGASIN_ARMES = {"_id": "lieu:armurerie", "type": "lieu", "categorie": "boulangerie",
				  "lieu_parent": "lieu:auxerre", "stock_vente": [{"item_id": GRIMOIRE["_id"], "qty": 1}]}
CONNECTION = {"_id": "connection:auxerre_armurerie", "type": "connection",
			  "nodes": [{"lieu": "lieu:auxerre", "pos": [3, 4]},
						{"lieu": "lieu:armurerie", "pos": [0, 0]}]}
AUXERRE = {"_id": "lieu:auxerre", "type": "lieu", "categorie": "ville",
		   "label": "Auxerre", "image": "auxerre.png", "dimensions": {"x": 50, "y": 50}}


def _base_docs():
	return {d["_id"]: d for d in (
		SCRIPTORIUM, MAGASIN_ARMES, CONNECTION, AUXERRE,
		GRIMOIRE, SORT_ECLAIR, SORT_SOIN, RECETTE_PAIN, FARINE,
	)}


def _fake_find_docs(docs):
	def find_docs_fn(selector, fields=None):
		return [d for d in docs.values() if all(d.get(k) == v for k, v in (selector or {}).items())]
	return find_docs_fn


def test_sorts_documentables_scanne_tous_les_enfants(monkeypatch):
	docs = _base_docs()
	find_docs_fn = _fake_find_docs(docs)
	get_doc_fn = docs.get
	monkeypatch.setattr("utils.marche._all_recettes", lambda: [RECETTE_PAIN])
	out = scriptorium.sorts_documentables("lieu:auxerre", find_docs_fn, get_doc_fn)
	assert out == ["sort:eclair", "sort:soin"]


def test_recettes_documentables_par_categorie(monkeypatch):
	docs = _base_docs()
	find_docs_fn = _fake_find_docs(docs)
	monkeypatch.setattr("utils.marche._all_recettes", lambda: [RECETTE_PAIN])
	monkeypatch.setattr("utils.marche._recettes_par_lieu", None)
	out = scriptorium.recettes_documentables("lieu:auxerre", find_docs_fn)
	assert out == ["recette:pain"]


def test_lieux_documentables_porte_directe(monkeypatch):
	docs = _base_docs()
	find_docs_fn = _fake_find_docs(docs)
	monkeypatch.setattr("utils.focalisation._graphe_cache", {"at": 0.0, "graphe": None})
	out = scriptorium.lieux_documentables("lieu:auxerre", find_docs_fn)
	assert out == [{"id": "lieu:armurerie", "porte": (3, 4)}]


def test_recettes_virtuelles_au_plus_un_sujet_par_pool(monkeypatch):
	docs = _base_docs()
	find_docs_fn = _fake_find_docs(docs)
	monkeypatch.setattr("utils.marche._all_recettes", lambda: [RECETTE_PAIN])
	monkeypatch.setattr("utils.marche._recettes_par_lieu", None)
	monkeypatch.setattr("utils.focalisation._graphe_cache", {"at": 0.0, "graphe": None})

	crees = []

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		crees.append(doc["_id"])
		return doc

	out = scriptorium.recettes_virtuelles(SCRIPTORIUM, find_docs_fn, docs.get, save_doc_fn)
	assert len(out) == 3  # un sort, une recette, une carte — jamais tout le catalogue
	assert len(crees) == 3
	for r in out:
		assert r["lieu_categorie"] == "scriptorium"
		assert r["quantite_produite"] == 1
		matieres = {m["item"]: m["quantite"] for m in r["matieres_premieres"]}
		assert matieres == {"item:Papier": character_stats.SCRIPTORIUM_LIVRE_PAPIER,
							 "item:Encre": character_stats.SCRIPTORIUM_LIVRE_ENCRE}


def test_recettes_virtuelles_ne_recree_jamais_un_item_existant(monkeypatch):
	# Scriptorium ISOLÉ (pas de connexion, pas d'autre magasin) : seul le pool "sort" est
	# non vide, avec un SEUL sujet possible (déterministe) — son item existe déjà et ne doit
	# jamais être recréé/retouché.
	grimoire_un_sort = dict(GRIMOIRE, sorts=["sort:eclair"])
	scripto = dict(SCRIPTORIUM, stock_vente=[{"item_id": grimoire_un_sort["_id"], "qty": 1}])
	docs = {scripto["_id"]: scripto, grimoire_un_sort["_id"]: grimoire_un_sort,
			SORT_ECLAIR["_id"]: SORT_ECLAIR,
			"item:livre_sort_eclair": {"_id": "item:livre_sort_eclair", "type": "item"}}
	find_docs_fn = _fake_find_docs(docs)
	monkeypatch.setattr("utils.marche._all_recettes", lambda: [])
	monkeypatch.setattr("utils.marche._recettes_par_lieu", None)
	monkeypatch.setattr("utils.focalisation._graphe_cache", {"at": 0.0, "graphe": None})

	appels_save = []
	out = scriptorium.recettes_virtuelles(scripto, find_docs_fn, docs.get, appels_save.append)
	assert len(out) == 1
	assert appels_save == []  # déjà là : jamais recréé


def test_recettes_effectives_hors_scriptorium_inchange(monkeypatch):
	docs = _base_docs()
	monkeypatch.setattr("utils.marche._all_recettes", lambda: [RECETTE_PAIN])
	monkeypatch.setattr("utils.marche._recettes_par_lieu", None)

	appels = {"find": 0, "save": 0}

	def find_docs_fn(*a, **k):
		appels["find"] += 1
		return []

	def save_doc_fn(*a, **k):
		appels["save"] += 1

	out = scriptorium.recettes_effectives(MAGASIN_ARMES, find_docs_fn, docs.get, save_doc_fn)
	assert out == [RECETTE_PAIN]
	assert appels == {"find": 0, "save": 0}  # aucun coût pour un lieu non concerné


def test_recettes_effectives_scriptorium_sans_rien_a_documenter(monkeypatch):
	"""lieu_parent sans grimoire/recette/lieu enfant ⇒ fail-soft, aucune exception."""
	docs = {SCRIPTORIUM["_id"]: SCRIPTORIUM}
	find_docs_fn = _fake_find_docs(docs)
	monkeypatch.setattr("utils.marche._all_recettes", lambda: [])
	monkeypatch.setattr("utils.marche._recettes_par_lieu", None)
	monkeypatch.setattr("utils.focalisation._graphe_cache", {"at": 0.0, "graphe": None})
	out = scriptorium.recettes_effectives(SCRIPTORIUM, find_docs_fn, docs.get, lambda d: d)
	assert out == []
