# tests/test_doc_cache.py
#
# Cache de `get_doc` à portée REQUÊTE (db/config.py). Tests PURS : aucun CouchDB — un faux
# `db` est injecté par monkeypatch et compte ses `.get()`, et le contexte de requête (le
# ContextVar que pose normalement le middleware) est posé à la main.
#
# Ce qui est figé ici, c'est la frontière contenu / état de partie : un `item:*` relu dix
# fois dans une réponse ne doit coûter qu'une lecture (et survit à la requête), un
# `character:*` est mémoïsé pour la requête seule, en copie profonde (muté et sauvé dans la
# même requête).

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
    # Le cache de process survit aux requêtes — donc aux tests : chacun part d'un cache vide.
    db_config.reset_cache_process()
    yield fdb
    db_config.reset_cache_process()


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


def test_doc_d_etat_de_partie_memoise_en_copie_profonde(fake_db, requete):
    # Un character est lu, muté et sauvé dans la même requête : chaque lecture rend une copie
    # PROFONDE de la version base (une mutation non sauvée ne se voit pas), et `save_doc`
    # invalide — exactement ce qu'aurait rendu une relecture, sans l'aller-retour.
    a = db_config.get_doc("character:bob")
    a["prenom"] = "Bobby"
    assert db_config.get_doc("character:bob")["prenom"] == "Bob"
    assert fake_db.reads["character:bob"] == 1
    assert requete.hits == 1
    db_config.save_doc(a)
    assert db_config.get_doc("character:bob")["prenom"] == "Bobby"
    assert fake_db.reads["character:bob"] == 2


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


# ── Cache de contenu à portée PROCESS ─────────────────────────────────────────────

def _nouvelle_requete():
    """Pose un contexte de requête neuf ; rend (cache, token)."""
    cache = db_config._RequestDocCache()
    return cache, db_config._doc_cache.set(cache)


def test_contenu_lu_une_seule_fois_pour_deux_requetes(fake_db):
    for _ in range(2):
        cache, token = _nouvelle_requete()
        try:
            assert db_config.get_doc("item:Epee")["nom"] == "Épée"
        finally:
            db_config._doc_cache.reset(token)
    assert fake_db.reads["item:Epee"] == 1


def test_mutation_imbriquee_ne_deborde_pas_de_sa_requete(fake_db):
    cache, token = _nouvelle_requete()
    try:
        db_config.get_doc("item:Epee")["poids"].append(99)   # mutation IMBRIQUÉE
    finally:
        db_config._doc_cache.reset(token)
    cache, token = _nouvelle_requete()
    try:
        assert db_config.get_doc("item:Epee")["poids"] == [2, 3]
    finally:
        db_config._doc_cache.reset(token)


def test_ecriture_hors_requete_invalide_le_cache_de_process(fake_db):
    # Les écritures de /admin tournent SANS contexte de requête (middleware coupé).
    cache, token = _nouvelle_requete()
    try:
        db_config.get_doc("item:Epee")
    finally:
        db_config._doc_cache.reset(token)
    db_config.save_doc({"_id": "item:Epee", "type": "item", "nom": "Épée longue"})
    cache, token = _nouvelle_requete()
    try:
        assert db_config.get_doc("item:Epee")["nom"] == "Épée longue"
    finally:
        db_config._doc_cache.reset(token)


def test_delete_hors_requete_invalide_le_cache_de_process(fake_db):
    cache, token = _nouvelle_requete()
    try:
        db_config.get_doc("item:Epee")
    finally:
        db_config._doc_cache.reset(token)
    db_config.delete_doc({"_id": "item:Epee"})
    cache, token = _nouvelle_requete()
    try:
        assert db_config.get_doc("item:Epee") is None
    finally:
        db_config._doc_cache.reset(token)


def test_ttl_relit_la_base(fake_db, monkeypatch):
    horloge = {"t": 1000.0}
    monkeypatch.setattr(db_config.time, "monotonic", lambda: horloge["t"])
    for avance in (0, db_config._PROCESS_TTL + 1):
        horloge["t"] += avance
        cache, token = _nouvelle_requete()
        try:
            db_config.get_doc("item:Epee")
        finally:
            db_config._doc_cache.reset(token)
    assert fake_db.reads["item:Epee"] == 2   # périmé : relu


def test_lecture_concurrente_d_une_ecriture_ne_repose_pas_l_ancienne_version(fake_db):
    # Pendant la lecture base, une autre requête écrit le doc : la version lue ne doit pas
    # être reposée au cache de process (elle serait servie périmée jusqu'au TTL).
    lecture = fake_db.get

    def get_puis_ecriture(doc_id):
        doc = lecture(doc_id)
        fake_db.get = lecture
        db_config.save_doc({"_id": "item:Epee", "type": "item", "nom": "Épée longue"})
        return doc

    fake_db.get = get_puis_ecriture
    cache, token = _nouvelle_requete()
    try:
        assert db_config.get_doc("item:Epee")["nom"] == "Épée"
    finally:
        db_config._doc_cache.reset(token)
    assert "item:Epee" not in db_config._process_cache


# ── Docs d'état (ici lieu:) à copie profonde — mémo de REQUÊTE seule ──────────────────

LIEU = {"_id": "lieu:forge", "type": "lieu", "stock_vente": [{"item_id": "item:Epee", "qty": 2}]}


def test_lieu_relu_dans_la_requete_ne_coute_qu_une_lecture(fake_db, requete):
    fake_db.docs[LIEU["_id"]] = LIEU
    db_config.get_doc("lieu:forge")
    db_config.get_doc("lieu:forge")
    assert fake_db.reads["lieu:forge"] == 1


def test_lieu_mutation_imbriquee_non_sauvee_invisible_a_la_relecture(fake_db, requete):
    # Exactement ce qu'aurait rendu CouchDB : une mutation non sauvée ne se voit pas.
    fake_db.docs[LIEU["_id"]] = LIEU
    a = db_config.get_doc("lieu:forge")
    a["stock_vente"][0]["qty"] = 0
    assert db_config.get_doc("lieu:forge")["stock_vente"][0]["qty"] == 2


def test_lieu_sauve_est_relu_en_base(fake_db, requete):
    fake_db.docs[LIEU["_id"]] = LIEU
    a = db_config.get_doc("lieu:forge")
    a["stock_vente"][0]["qty"] = 1
    db_config.save_doc(a)
    assert db_config.get_doc("lieu:forge")["stock_vente"][0]["qty"] == 1
    assert fake_db.reads["lieu:forge"] == 2


def test_lieu_jamais_au_cache_de_process(fake_db):
    fake_db.docs[LIEU["_id"]] = LIEU
    for _ in range(2):
        cache, token = _nouvelle_requete()
        try:
            db_config.get_doc("lieu:forge")
        finally:
            db_config._doc_cache.reset(token)
    assert fake_db.reads["lieu:forge"] == 2


# ── Écriture groupée (save_docs) ──────────────────────────────────────────────────

def test_save_docs_un_aller_retour_rev_pose_caches_invalides(fake_db, requete):
    appels = []

    def update(docs):
        appels.append([d["_id"] for d in docs])
        out = []
        for d in docs:
            if d["_id"] == "lieu:refus":
                out.append((False, d["_id"], "conflict", "Document update conflict."))
            else:
                fake_db.docs[d["_id"]] = d
                out.append((True, d["_id"], "2-abc"))
        return out

    fake_db.update = update
    db_config.get_doc("item:Epee")                   # au cache de process
    db_config.get_doc("character:bob")               # au mémo de requête
    epee = {"_id": "item:Epee", "type": "item", "nom": "Épée longue"}
    bob = {"_id": "character:bob", "type": "character", "prenom": "Robert"}
    refus = {"_id": "lieu:refus", "type": "lieu"}
    assert db_config.save_docs([epee, refus, bob]) == [True, False, True]
    assert appels == [["item:Epee", "lieu:refus", "character:bob"]]   # UN envoi
    assert epee["_rev"] == "2-abc" and "_rev" not in refus
    assert requete.saves == 1
    assert db_config.get_doc("item:Epee")["nom"] == "Épée longue"
    assert db_config.get_doc("character:bob")["prenom"] == "Robert"


def test_save_docs_base_injoignable_tout_echoue(fake_db, requete):
    def update(docs):
        raise ConnectionError("NAS")
    fake_db.update = update
    assert db_config.save_docs([{"_id": "lieu:a"}, {"_id": "lieu:b"}]) == [False, False]
    assert db_config.save_docs([]) == []


# ── Recherches de contenu au cache de process ─────────────────────────────────────

def _compter_finds(fake_db):
    appels = []

    def find(selector, limit=None, fields=None):
        appels.append(selector)
        return {"docs": [d for d in fake_db.docs.values()
                         if all(d.get(k) == v for k, v in selector.items())]}
    fake_db.find = find
    return appels


def test_find_de_contenu_servi_d_une_requete_a_l_autre(fake_db):
    appels = _compter_finds(fake_db)
    for _ in range(2):
        cache, token = _nouvelle_requete()
        try:
            docs = db_config.find_docs({"type": "item"})
            docs[0]["poids"].append(99)          # mutation imbriquée : reste dans la requête
        finally:
            db_config._doc_cache.reset(token)
    assert appels == [{"type": "item"}]
    cache, token = _nouvelle_requete()
    try:
        assert db_config.find_docs({"type": "item"})[0]["poids"] == [2, 3]
    finally:
        db_config._doc_cache.reset(token)


def test_find_d_etat_jamais_au_cache(fake_db):
    appels = _compter_finds(fake_db)
    for _ in range(2):
        cache, token = _nouvelle_requete()
        try:
            db_config.find_docs({"type": "character"})
        finally:
            db_config._doc_cache.reset(token)
    assert len(appels) == 2


def test_ecrire_un_contenu_vide_les_find_de_contenu(fake_db):
    appels = _compter_finds(fake_db)
    cache, token = _nouvelle_requete()
    try:
        db_config.find_docs({"type": "item"})
    finally:
        db_config._doc_cache.reset(token)
    db_config.save_doc({"_id": "item:Hache", "type": "item", "nom": "Hache"})   # hors requête
    cache, token = _nouvelle_requete()
    try:
        noms = {d["nom"] for d in db_config.find_docs({"type": "item"})}
    finally:
        db_config._doc_cache.reset(token)
    assert noms == {"Épée", "Hache"} and len(appels) == 2
