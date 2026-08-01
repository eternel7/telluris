# tests/test_doc_cache.py
#
# Cache de `get_doc` à portée REQUÊTE (db/config.py). Tests PURS : aucun CouchDB — un faux
# `db` est injecté par monkeypatch et compte ses `.get()`, et le contexte de requête (le
# ContextVar que pose normalement le middleware) est posé à la main.
#
# Ce qui est figé ici, c'est la frontière contenu / état de partie : un `item:*` relu dix
# fois dans une réponse ne doit coûter qu'une lecture, un `character:*` doit être relu à
# chaque fois (il est muté et sauvé dans la même requête).

import pytest

from db import config as db_config


class _FakeDB:
    """Faux CouchDB : compte les lectures par id et sert des docs en mémoire."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.reads = {}

    def get(self, doc_id):
        self.reads[doc_id] = self.reads.get(doc_id, 0) + 1
        return self.docs.get(doc_id)

    def put(self, doc):
        self.docs[doc["_id"]] = doc

    def delete(self, doc):
        self.docs.pop(doc.get("_id"), None)


@pytest.fixture
def fake_db(monkeypatch):
    fdb = _FakeDB({
        "item:Epee": {"_id": "item:Epee", "type": "item", "nom": "Épée", "poids": [2, 3]},
        "character:bob": {"_id": "character:bob", "type": "character", "prenom": "Bob"},
    })
    monkeypatch.setattr(db_config, "db", fdb)
    monkeypatch.setattr(db_config, "_CACHE_ENABLED", True)
    return fdb


@pytest.fixture
def requete(fake_db):
    """Contexte de requête posé à la main (ce que fait RequestDocCacheMiddleware)."""
    cache = db_config._RequestDocCache()
    token = db_config._doc_cache.set(cache)
    yield cache
    db_config._doc_cache.reset(token)


# ── Ce qui est mémorisé, ce qui ne l'est pas ─────────────────────────────────────

def test_doc_de_contenu_lu_deux_fois_ne_coute_qu_une_lecture(fake_db, requete):
    db_config.get_doc("item:Epee")
    db_config.get_doc("item:Epee")
    assert fake_db.reads["item:Epee"] == 1
    assert (requete.gets, requete.hits) == (2, 1)


def test_doc_d_etat_de_partie_est_relu_a_chaque_fois(fake_db, requete):
    # Un character est lu, muté et sauvé dans la même requête : le mémoriser rendrait un
    # état périmé au deuxième appelant.
    db_config.get_doc("character:bob")
    db_config.get_doc("character:bob")
    assert fake_db.reads["character:bob"] == 2
    assert requete.hits == 0


def test_le_dict_rendu_est_distinct_de_l_exemplaire_memorise(fake_db, requete):
    a = db_config.get_doc("item:Epee")
    a["nom"] = "Bricolé"          # un appelant mute son dict (resolve_item_ref le fait)
    b = db_config.get_doc("item:Epee")
    assert a is not b
    assert b["nom"] == "Épée"     # le cache n'a pas été empoisonné


def test_pas_de_cache_negatif(fake_db, requete):
    # `_ensure_loot_item` lit `item:<espece>` puis le CRÉE s'il est absent : mémoriser
    # l'absence ferait disparaître la carcasse fraîchement ramassée du sac.
    assert db_config.get_doc("item:Loup") is None
    fake_db.docs["item:Loup"] = {"_id": "item:Loup", "type": "item", "nom": "Carcasse"}
    assert db_config.get_doc("item:Loup")["nom"] == "Carcasse"


def test_save_doc_invalide_l_entree(fake_db, requete):
    db_config.get_doc("item:Epee")
    db_config.save_doc({"_id": "item:Epee", "type": "item", "nom": "Épée longue"})
    assert db_config.get_doc("item:Epee")["nom"] == "Épée longue"
    assert fake_db.reads["item:Epee"] == 2
    assert requete.saves == 1


def test_delete_doc_invalide_l_entree(fake_db, requete):
    db_config.get_doc("item:Epee")
    db_config.delete_doc({"_id": "item:Epee"})
    assert db_config.get_doc("item:Epee") is None


def test_hors_contexte_de_requete_rien_n_est_memorise(fake_db):
    # Tests purs, scripts dev/*, startup : chemin strictement identique à avant.
    assert db_config._doc_cache.get() is None
    db_config.get_doc("item:Epee")
    db_config.get_doc("item:Epee")
    assert fake_db.reads["item:Epee"] == 2


def test_kill_switch_coupe_la_memorisation_pas_l_instrumentation(fake_db, requete, monkeypatch):
    monkeypatch.setattr(db_config, "_CACHE_ENABLED", False)
    db_config.get_doc("item:Epee")
    db_config.get_doc("item:Epee")
    assert fake_db.reads["item:Epee"] == 2
    assert (requete.gets, requete.hits) == (2, 0)   # compteurs toujours posés (relevé A/B)


def test_find_docs_est_compte(fake_db, requete):
    fake_db.find = lambda selector, limit=None, fields=None: {"docs": []}
    db_config.find_docs({"type": "recette"})
    assert requete.finds == 1
