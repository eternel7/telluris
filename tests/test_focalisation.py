# tests/test_focalisation.py
#
# Tests purs du système de focalisation (utils/focalisation.py) et des biais qu'il
# injecte dans les tirages (utils/zones.py, utils/combat.py). La DB est simulée par
# des fakes (find_docs_fn / get_doc_fn) ; db/config tolère l'absence de CouchDB à
# l'import → lançable en local comme dans le conteneur.

import random

import pytest

import models.character_stats as cs
import utils.focalisation as foc
from utils.zones import resolve_zone_event, resolve_recolte
from utils.combat import instantiate_monsters


# ── Fabriques ────────────────────────────────────────────────────────────────────

def _char(focalisation=None, quetes_actives=None, lieu="lieu:a", position=None):
    return {
        "_id": "character:test",
        "lieu": lieu,
        "position": position or {"x": 0, "y": 0},
        "focalisation": focalisation,
        "quetes_actives": quetes_actives or [],
    }


def _quete(qid="quete:q1", type_="kill", cible="espece:loup", quantite=3, progress=0):
    return {
        "id": qid,
        "titre": "Chasse test",
        "objectif": {"type": type_, "cible": cible, "quantite": quantite},
        "progress": progress,
    }


def _connections():
    """Graphe : a—b—c (chemin), a—d (cul-de-sac), a—e et e—c (autre chemin vers c,
    même longueur 2 que via b — le BFS renvoie le premier trouvé, ordre d'insertion)."""
    def link(lid, l1, p1, l2, p2):
        return {"_id": lid, "type": "connection",
                "nodes": [{"lieu": l1, "pos": p1}, {"lieu": l2, "pos": p2}]}
    return [
        link("link:ab", "lieu:a", [1, 1], "lieu:b", [0, 0]),
        link("link:bc", "lieu:b", [5, 5], "lieu:c", [2, 2]),
        link("link:ad", "lieu:a", [9, 9], "lieu:d", [0, 0]),
    ]


def _find_docs(selector):
    if selector.get("type") == "connection":
        return _connections()
    return []


def _get_doc(doc_id):
    docs = {
        "lieu:a": {"_id": "lieu:a", "type": "lieu", "label": "Alpha"},
        "lieu:b": {"_id": "lieu:b", "type": "lieu", "label": "Beta"},
        "lieu:c": {"_id": "lieu:c", "type": "lieu", "label": "Gamma"},
    }
    return docs.get(doc_id)


@pytest.fixture(autouse=True)
def _graphe_frais():
    # Le graphe est mis en cache process-lifetime (TTL) : chaque test repart à neuf.
    foc.reset_graphe_cache()
    yield
    foc.reset_graphe_cache()


# ── Cycle de vie ─────────────────────────────────────────────────────────────────

def test_focalisation_de_legacy_sans_champ():
    assert foc.focalisation_de({"_id": "character:vieux"}) is None


def test_poser_puis_toggle_off():
    c = _char()
    f = foc.poser_focalisation(c, "lieu", "lieu:b")
    assert f["type"] == "lieu" and f["cible"] == "lieu:b" and c["focalisation"] is f
    # Re-cliquer la même cible = toggle off.
    assert foc.poser_focalisation(c, "lieu", "lieu:b") is None
    assert c["focalisation"] is None


def test_poser_remplace_l_existante():
    c = _char(focalisation={"type": "lieu", "cible": "lieu:b", "posee_at": 0})
    f = foc.poser_focalisation(c, "quete", "quete:q1")
    assert f["type"] == "quete" and c["focalisation"]["cible"] == "quete:q1"


def test_effective_lieu_et_quete_kill():
    c = _char(focalisation={"type": "lieu", "cible": "lieu:c"})
    assert foc.focalisation_effective(c) == {
        "mode": "guidage", "lieu_cible": "lieu:c", "source": "lieu", "quete_id": None}
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"},
              quetes_actives=[_quete()])
    eff = foc.focalisation_effective(c)
    assert eff["mode"] == "kill" and eff["espece"] == "espece:loup"


def test_effective_quete_dangling_inerte():
    # La quête focalisée n'est plus active → focalisation inerte (aucun biais fantôme).
    c = _char(focalisation={"type": "quete", "cible": "quete:disparue"})
    assert foc.focalisation_effective(c) is None
    assert foc.boost_zone_event(c, {"rencontres": [{"espece": "espece:loup", "zones": ["z1"]}]}) is None
    assert foc.espece_weights_focus(c) is None
    assert foc.favori_recolte(c) is None


def test_effective_quete_visite_devient_guidage():
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"},
              quetes_actives=[_quete(type_="visite", cible="lieu:c")])
    eff = foc.focalisation_effective(c)
    assert eff["mode"] == "guidage" and eff["lieu_cible"] == "lieu:c" and eff["source"] == "quete"


def test_effacer_si_quete():
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"})
    assert foc.effacer_si_quete(c, "quete:autre") is False
    assert foc.effacer_si_quete(c, "quete:q1") is True
    assert c["focalisation"] is None


def test_effacer_si_lieu_atteint():
    c = _char(focalisation={"type": "lieu", "cible": "lieu:c"})
    assert foc.effacer_si_lieu_atteint(c, "lieu:b") is False
    assert foc.effacer_si_lieu_atteint(c, "lieu:c") is True
    assert c["focalisation"] is None


def test_effacer_si_objectif_atteint():
    q = _quete(progress=2, quantite=3)
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"}, quetes_actives=[q])
    assert foc.effacer_si_objectif_atteint(c) is False  # 2/3 : pas encore
    q["progress"] = 3
    assert foc.effacer_si_objectif_atteint(c) is True
    assert c["focalisation"] is None


def test_payload_client():
    c = _char(focalisation={"type": "lieu", "cible": "lieu:c"})
    assert foc.payload_client(c, _get_doc) == {"type": "lieu", "cible": "lieu:c", "label": "Gamma"}
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"}, quetes_actives=[_quete()])
    assert foc.payload_client(c, _get_doc)["label"] == "Chasse test"
    assert foc.payload_client(_char(), _get_doc) is None


# ── Graphe / BFS ─────────────────────────────────────────────────────────────────

def test_prochaine_etape_premier_hop_et_porte():
    graphe = foc.charger_graphe(_find_docs)
    etape = foc.prochaine_etape(graphe, "lieu:a", "lieu:c")
    # a → c passe par b ; la porte est la pos du node CÔTÉ a du lien a—b.
    assert etape["suivant"] == "lieu:b"
    assert etape["link_id"] == "link:ab"
    assert etape["porte"] == (1, 1)
    assert etape["distance"] == 2


def test_prochaine_etape_voisin_direct():
    graphe = foc.charger_graphe(_find_docs)
    etape = foc.prochaine_etape(graphe, "lieu:b", "lieu:a")
    # Sens inverse du lien : porte côté b.
    assert etape["suivant"] == "lieu:a" and etape["porte"] == (0, 0) and etape["distance"] == 1


def test_prochaine_etape_injoignable_et_sur_place():
    graphe = foc.charger_graphe(_find_docs)
    assert foc.prochaine_etape(graphe, "lieu:a", "lieu:isole") is None
    assert foc.prochaine_etape(graphe, "lieu:a", "lieu:a") is None
    assert foc.prochaine_etape(graphe, "lieu:inconnu", "lieu:a") is None


def test_guidage_payload_complet_et_injoignable():
    c = _char(focalisation={"type": "lieu", "cible": "lieu:c"}, lieu="lieu:a")
    lieu_doc = {"cells": [[1, 1], [1, 1]], "nav": {}}
    g = foc.guidage(c, lieu_doc, _find_docs, _get_doc)
    assert g["etape"] == "lieu:b" and g["etape_nom"] == "Beta"
    assert g["cible_nom"] == "Gamma" and g["link_id"] == "link:ab"
    assert g["porte"] == {"x": 1, "y": 1}
    assert g["direction"] == {"dx": 1, "dy": 1, "bit": 8}  # BAS_DROITE
    # Cible hors graphe → injoignable (focalisation conservée, message côté client).
    c2 = _char(focalisation={"type": "lieu", "cible": "lieu:isole"}, lieu="lieu:a")
    g2 = foc.guidage(c2, lieu_doc, _find_docs, lambda i: {"label": "Île"})
    assert g2["injoignable"] is True


# ── Direction dans le lieu courant (A*) ──────────────────────────────────────────

def test_direction_vers_contourne_un_mur():
    # Colonne x=2 murée en y=0..1 : le plus court chemin (0,0)→(4,0) passe par (2,2),
    # donc le premier pas est la diagonale bas-droite.
    cells = [
        [1, 1, 0, 1, 1],
        [1, 1, 0, 1, 1],
        [1, 1, 1, 1, 1],
    ]
    d = foc.direction_vers({"cells": cells}, {"x": 0, "y": 0}, (4, 0))
    assert (d["dx"], d["dy"]) == (1, 1)


def test_direction_vers_respecte_nav():
    # Grille 1×3 ouverte mais nav interdit DROITE (bit 4) depuis (0,0) : aucun détour
    # possible sur une seule ligne → pas de chemin → None.
    lieu = {"cells": [[1, 1, 1]], "nav": {"0,0": 4}}
    assert foc.direction_vers(lieu, {"x": 0, "y": 0}, (2, 0)) is None


def test_direction_vers_cas_limites():
    assert foc.direction_vers({}, {"x": 0, "y": 0}, (1, 0)) is None            # pas de grille
    assert foc.direction_vers({"cells": [[1]]}, {"x": 0, "y": 0}, (0, 0)) is None  # sur la porte
    assert foc.direction_vers({"cells": [[1, 1]]}, {"x": 0, "y": 0}, (9, 9)) is None  # porte hors grille


# ── Biais boost_zone_event (helper + application) ────────────────────────────────

def test_boost_zone_event_kill_et_zones():
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"}, quetes_actives=[_quete()])
    lieu = {"rencontres": [
        {"espece": "espece:loup", "zones": ["z1", "z2"]},
        {"espece": "espece:rat", "zones": ["z3"]},
    ]}
    b = foc.boost_zone_event(c, lieu)
    assert b["type"] == "combat" and b["zones"] == {"z1", "z2"}
    assert b["mult"] == cs.FOCUS_EVENEMENT_MULT
    # Cible absente du lieu → pas de boost.
    assert foc.boost_zone_event(c, {"rencontres": [{"espece": "espece:rat", "zones": ["z1"]}]}) is None


def test_boost_zone_event_collect_ressource_puis_carcasse():
    q = _quete(type_="collect", cible="item:rondin")
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"}, quetes_actives=[q])
    lieu = {"ressources": [{"ressource": "item:rondin", "zones": ["z9"]}]}
    b = foc.boost_zone_event(c, lieu)
    assert b["type"] == "ressource" and b["zones"] == {"z9"}
    # Collecte de carcasse (item:loup ↔ espece:loup) : repli sur les combats.
    q2 = _quete(type_="collect", cible="item:loup")
    c2 = _char(focalisation={"type": "quete", "cible": "quete:q1"}, quetes_actives=[q2])
    lieu2 = {"rencontres": [{"espece": "espece:loup", "zones": ["z1"]}]}
    b2 = foc.boost_zone_event(c2, lieu2)
    assert b2["type"] == "combat" and b2["zones"] == {"z1"}


def _capture_choices(monkeypatch):
    captured = {}
    orig = random.choices
    def fake(seq, weights=None, k=1):
        captured["weights"] = list(weights) if weights is not None else None
        return orig(seq, weights=weights, k=k)
    monkeypatch.setattr(random, "choices", fake)
    return captured


def test_resolve_zone_event_applique_le_boost(monkeypatch):
    monkeypatch.setattr("utils.zones.compute_zone_intensity", lambda *a: 1.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # déclenchement forcé
    captured = _capture_choices(monkeypatch)
    zone_defs = {"z1": {"_id": "z1", "intensite_max": 1.0, "table_evenements": [
        {"type": "combat", "poids": 2}, {"type": "ressource", "poids": 2}]}}
    placements = [{"zone": "z1"}]

    boost = {"type": "combat", "mult": 3.0, "zones": {"z1"}}
    resolve_zone_event(0, 0, placements, zone_defs, boost=boost)
    assert captured["weights"] == [6.0, 2.0]  # seul le poids des entrées `combat` est ×3

    resolve_zone_event(0, 0, placements, zone_defs)  # rétro-compat : sans boost
    assert captured["weights"] == [2.0, 2.0]

    resolve_zone_event(0, 0, placements, zone_defs,
                       boost={"type": "combat", "mult": 3.0, "zones": {"zX"}})
    assert captured["weights"] == [2.0, 2.0]  # zone du boost inactive → inchangé


def test_resolve_recolte_favorise_la_cible(monkeypatch):
    captured = _capture_choices(monkeypatch)
    event = {"type": "ressource", "zones_actives_ids": ["z1"], "tags": []}
    lieu = {"ressources": [
        {"ressource": "item:a", "zones": ["z1"]},
        {"ressource": "item:b", "zones": ["z1"]},
    ]}
    resolve_recolte(event, lieu, lambda i: None, favori="item:b", favori_mult=4.0)
    assert captured["weights"] == [1.0, 4.0]
    # Sans favori (ou favori hors candidats) : tirage uniforme (random.choice, pas choices).
    captured.clear()
    assert resolve_recolte(event, lieu, lambda i: None) in ("item:a", "item:b")
    assert "weights" not in captured
    captured.clear()
    resolve_recolte(event, lieu, lambda i: None, favori="item:absent", favori_mult=4.0)
    assert "weights" not in captured


def test_instantiate_monsters_pondere_l_espece(monkeypatch):
    captured = _capture_choices(monkeypatch)
    especes = [
        {"_id": "espece:loup", "nom": "Loup", "tags": [], "base_attributes": {}},
        {"_id": "espece:rat", "nom": "Rat", "tags": [], "base_attributes": {}},
    ]
    monstres = instantiate_monsters(especes, [], 1, [], espece_weights={"espece:loup": 5.0})
    assert len(monstres) == 1
    assert captured["weights"] == [5.0, 1.0]
    # Rétro-compat : sans espece_weights, tirage uniforme (random.choice).
    captured.clear()
    monstres = instantiate_monsters(especes, [], 2, [])
    assert len(monstres) == 2 and "weights" not in captured
    # Poids tous nuls → repli uniforme (pas de ValueError).
    captured.clear()
    monstres = instantiate_monsters(
        especes, [], 1, [], espece_weights={"espece:loup": 0.0, "espece:rat": 0.0})
    assert len(monstres) == 1 and "weights" not in captured


def test_espece_weights_et_favori_recolte():
    c = _char(focalisation={"type": "quete", "cible": "quete:q1"}, quetes_actives=[_quete()])
    assert foc.espece_weights_focus(c) == {"espece:loup": cs.FOCUS_CIBLE_MULT}
    q = _quete(type_="collect", cible="item:loup")
    c2 = _char(focalisation={"type": "quete", "cible": "quete:q1"}, quetes_actives=[q])
    assert foc.espece_weights_focus(c2) == {"espece:loup": cs.FOCUS_CIBLE_MULT}
    assert foc.favori_recolte(c2) == ("item:loup", cs.FOCUS_CIBLE_MULT)
    assert foc.favori_recolte(_char()) is None
