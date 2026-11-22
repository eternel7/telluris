# tests/test_recits.py
#
# Récits historiques (items tagués `ouvrage_historique`) : plafond de TITRES DISTINCTS en rayon,
# un exemplaire de chacun, par catégorie de lieu et selon la cité (capitale) — Auteur, 22/11/2026.
# Tenu à la fabrication (`marche._executer_production_batch`) et à la vente d'un atelier de
# propriété aux boutiques (`marche.recit_refuse` ← `echanges_cite.prix_vente_boutique`).

import pytest

from models import character_stats
from utils import marche, recits


def _resolve(item_id):
	# Stub sans DB : un récit porte le tag, le reste non. Sous-catégorie neutre : aucune recette
	# d'ici ne la consomme, le rayon n'est donc jamais repris comme matière.
	tags = [recits.TAG_RECIT] if item_id.startswith("item:ouvrage_") else []
	return {"_id": item_id, "item": item_id, "categorie": "livre", "sous_categorie": "neutre", "tags": tags}


def _recette(slug):
	return {"type": "recette", "lieu_categorie": "scriptorium", "objet_final": slug, "quantite_produite": 1,
			"matieres_premieres": [{"item": "item:Papier", "quantite": 1}]}


def _lieu(categorie, papier, rayon=()):
	return {"categorie": categorie, "stock_matieres": {"item:Papier": papier},
			"stock_vente": [{"item_id": i, "qty": 1} for i in rayon]}


def _recits_en_rayon(lieu):
	return sorted(e["item_id"] for e in lieu["stock_vente"]
				  if e["item_id"].startswith("item:ouvrage_") and e["qty"] > 0)


# ── Plafond ──────────────────────────────────────────────────────────────────────

def test_plafond_lu_dans_la_table_par_categorie():
	for cat, n in character_stats.RECITS_PLAFOND.items():
		assert recits.plafond({"categorie": cat}, None) == n


def test_plafond_de_capitale_remplace_la_valeur():
	capitale = {"sous_categorie": "capitale"}
	for cat, n in character_stats.RECITS_PLAFOND_CAPITALE.items():
		assert recits.plafond({"categorie": cat}, capitale) == n
		assert recits.plafond({"categorie": cat}, {"sous_categorie": "ville"}) == character_stats.RECITS_PLAFOND[cat]


def test_valeurs_voulues_par_l_auteur():
	# Constantes voulues (Auteur, 22/11/2026) : scriptorium 1, capitale 3, bibliothèque 5, grande 10.
	assert character_stats.RECITS_PLAFOND["scriptorium"] == 1
	assert character_stats.RECITS_PLAFOND_CAPITALE["scriptorium"] == 3
	assert character_stats.RECITS_PLAFOND["bibliotheque"] == 5
	assert character_stats.RECITS_PLAFOND["grande_bibliotheque"] == 10


def test_categorie_sans_plafond():
	assert recits.plafond({"categorie": "boulangerie"}, {"sous_categorie": "capitale"}) is None
	assert recits.plafond({}, None) is None
	assert recits.admis("item:ouvrage_x", {"item:ouvrage_a", "item:ouvrage_b"}, None)


def test_admis_un_exemplaire_par_titre_et_n_titres():
	assert recits.admis("item:ouvrage_b", {"item:ouvrage_a"}, 2)
	assert not recits.admis("item:ouvrage_a", {"item:ouvrage_a"}, 2)            # déjà en rayon
	assert not recits.admis("item:ouvrage_c", {"item:ouvrage_a", "item:ouvrage_b"}, 2)


def test_bibliotheques_reprennent_le_scriptorium():
	assert "scriptorium" in marche.categories_incluses("bibliotheque")
	assert "scriptorium" in marche.categories_incluses("grande_bibliotheque")


# ── Fabrication ──────────────────────────────────────────────────────────────────

def test_scriptorium_ne_fabrique_qu_un_titre(monkeypatch):
	monkeypatch.setattr(marche.random, "choices", lambda pop, weights=None: [pop[0]])
	lieu = _lieu("scriptorium", papier=10)
	recettes = [_recette(f"ouvrage_{c}") for c in "abcd"]
	marche._executer_production_batch(lieu, recettes, resolve_fn=_resolve)
	assert len(_recits_en_rayon(lieu)) == character_stats.RECITS_PLAFOND["scriptorium"]
	assert all(e["qty"] == 1 for e in lieu["stock_vente"])


def test_bibliotheque_fabrique_jusqu_a_son_plafond_un_exemplaire_chacun(monkeypatch):
	monkeypatch.setattr(marche.random, "choices", lambda pop, weights=None: [pop[0]])
	n = character_stats.RECITS_PLAFOND["bibliotheque"]
	lieu = _lieu("bibliotheque", papier=100)
	recettes = [_recette(f"ouvrage_{i}") for i in range(n + 3)]
	marche._executer_production_batch(lieu, recettes, resolve_fn=_resolve)
	assert len(_recits_en_rayon(lieu)) == n
	assert all(e["qty"] == 1 for e in lieu["stock_vente"])


def test_capitale_monte_le_plafond(monkeypatch):
	monkeypatch.setattr(marche.random, "choices", lambda pop, weights=None: [pop[0]])
	monkeypatch.setattr(marche, "_cite_du_lieu", lambda lieu, get_doc_fn=None: {"sous_categorie": "capitale"})
	lieu = _lieu("scriptorium", papier=10)
	marche._executer_production_batch(lieu, [_recette(f"ouvrage_{c}") for c in "abcde"], resolve_fn=_resolve)
	assert len(_recits_en_rayon(lieu)) == character_stats.RECITS_PLAFOND_CAPITALE["scriptorium"]


def test_rayon_deja_plein_rien_de_plus_mais_le_reste_cuit(monkeypatch):
	monkeypatch.setattr(marche.random, "choices", lambda pop, weights=None: [pop[0]])
	lieu = _lieu("scriptorium", papier=2, rayon=["item:ouvrage_vieux"])
	marche._executer_production_batch(lieu, [_recette("ouvrage_neuf"), _recette("grimoire_x")], resolve_fn=_resolve)
	assert _recits_en_rayon(lieu) == ["item:ouvrage_vieux"]
	assert any(e["item_id"] == "item:grimoire_x" for e in lieu["stock_vente"])   # hors plafond


def test_categorie_hors_table_inchangee(monkeypatch):
	monkeypatch.setattr(marche.random, "choices", lambda pop, weights=None: [pop[0]])
	lieu = _lieu("necromancie", papier=3)
	marche._executer_production_batch(lieu, [_recette("ouvrage_a")], resolve_fn=_resolve)
	assert lieu["stock_vente"] == [{"item_id": "item:ouvrage_a", "qty": 3}]


# ── Flux entrant hors fabrication ────────────────────────────────────────────────

def test_recit_refuse_au_dela_du_plafond(monkeypatch):
	monkeypatch.setattr(marche, "_cite_du_lieu", lambda lieu, get_doc_fn=None: None)
	plein = _lieu("scriptorium", 0, rayon=["item:ouvrage_a"])
	assert marche.recit_refuse(plein, _resolve("item:ouvrage_b"), resolve_fn=_resolve)
	assert marche.recit_refuse(plein, _resolve("item:ouvrage_a"), resolve_fn=_resolve)
	vide = _lieu("scriptorium", 0)
	assert not marche.recit_refuse(vide, _resolve("item:ouvrage_b"), resolve_fn=_resolve)
	assert not marche.recit_refuse(plein, _resolve("item:grimoire_x"), resolve_fn=_resolve)


def test_cite_du_lieu_memoisee_et_fail_soft():
	marche.reset_prix_cache()
	appels = []

	def get(i):
		appels.append(i)
		return {"_id": i, "sous_categorie": "capitale"}

	lieu = {"_id": "lieu:test_recits", "lieu_parent": "lieu:cite"}
	assert marche._cite_du_lieu(lieu, get)["sous_categorie"] == "capitale"
	marche._cite_du_lieu(lieu, get)
	assert appels == ["lieu:cite"]
	assert marche._cite_du_lieu({"categorie": "scriptorium"}, get) is None   # fixture sans _id
	marche.reset_prix_cache()


@pytest.mark.parametrize("nom", ["RECITS_PLAFOND", "RECITS_PLAFOND_CAPITALE"])
def test_variables_de_monde_chargees_en_place(nom, monkeypatch):
	import db.config
	table = getattr(character_stats, nom)
	avant = dict(table)
	valeurs = {nom: {"scriptorium": "2", "bibliotheque": "x"}}
	monkeypatch.setattr(db.config, "get_doc", lambda _id: {"value": valeurs})
	try:
		character_stats.load_world_variables()
		assert getattr(character_stats, nom) is table          # muté en place
		assert table == {"scriptorium": 2}                     # valeur illisible écartée
	finally:
		table.clear()
		table.update(avant)
