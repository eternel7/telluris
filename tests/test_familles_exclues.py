# tests/test_familles_exclues.py
#
# Exclusion de TYPES de sorts et de compétences à l'apprentissage : un doc `sort:*` /
# `competence:*` porte une `famille` (étiquette libre), une vocation de `rules:vocations`
# porte `familles_exclues`. Ce qui tombe dans l'intersection n'est ni listé ni achetable.
#
# Verrouille aussi la rétro-compatibilité, qui est ici toute la difficulté : ni la famille
# ni l'exclusion n'existaient hier, et leur absence doit rendre EXACTEMENT le comportement
# d'avant (règle « aucune migration »).
#
# Logique pure : aucun accès DB.

from utils.sorts import (
    FAMILLE_INVOCATION, apprentissage_exclu, famille_de, familles_exclues,
    normaliser_sort, purger_sorts_hors_ecole, sorts_apprenables,
)
from utils.competences import competences_apprenables, normaliser_competence


# rules:vocations minimal : le répurgateur pratique la Démonologie du démoniste, mais pas
# ses invocations — c'est le cas d'usage qui a fait naître le mécanisme.
_RULES_VOCS = {"_id": "rules:vocations", "type": "rules", "value": [
    {"id": "demoniste", "magie": "Démonologie"},
    {"id": "repurgateur", "magie": "Démonologie", "familles_exclues": ["invocation"]},
    {"id": "guerrier", "magie": ""},
]}


def _sort(**overrides):
    doc = {
        "_id": "sort:flamme", "type": "sort", "nom": "Flamme", "icon": "🔥",
        "vocation": "demoniste", "magie": "Démonologie", "niveau": 0, "cout_pm": 8,
        "cible": "ennemi", "portee": 6, "effets": {"degats": "2D4"},
    }
    doc.update(overrides)
    return doc


def _comp(**overrides):
    doc = {
        "_id": "competence:sentence", "type": "competence", "nom": "Sentence",
        "vocation": "repurgateur", "niveau": 0, "mode": "active", "cout_pm": 10,
        "cible": "ennemi", "effets": {"degats": "1D6"},
    }
    doc.update(overrides)
    return doc


def _perso(voc="repurgateur", **overrides):
    char = {
        "_id": "character:test", "voc": voc, "vocations_niveaux": {voc: 3},
        "sorts_connus": [], "competences_connues": [], "inventaire": [], "slots": {},
    }
    char.update(overrides)
    return char


# ── Normalisation de la famille ──────────────────────────────────────────────────

def test_famille_absente_vaut_chaine_vide():
    """Le champ est neuf : tout doc déjà en base n'a pas de famille, donc aucune."""
    assert famille_de(None) == ""
    assert famille_de({}) == ""
    assert famille_de({"famille": None}) == ""
    assert famille_de({"famille": "  "}) == ""
    assert famille_de({"famille": " invocation "}) == "invocation"


def test_famille_traverse_la_normalisation_des_deux_familles():
    """Sorts ET compétences portent le champ : c'est la même règle des deux côtés."""
    assert normaliser_sort(_sort(famille=FAMILLE_INVOCATION))["famille"] == "invocation"
    assert normaliser_sort(_sort())["famille"] == ""
    assert normaliser_competence(_comp(famille="invocation"))["famille"] == "invocation"
    assert normaliser_competence(_comp())["famille"] == ""


# ── Lecture des exclusions sur rules:vocations ───────────────────────────────────

def test_familles_exclues_lit_la_vocation_et_tolere_tout_le_reste():
    assert familles_exclues("repurgateur", _RULES_VOCS) == {"invocation"}
    assert familles_exclues("demoniste", _RULES_VOCS) == set()      # champ absent
    assert familles_exclues("inconnue", _RULES_VOCS) == set()       # vocation absente
    assert familles_exclues("repurgateur", None) == set()           # doc absent
    # La `value` nue est acceptée comme le doc complet (même tolérance que les écoles).
    assert familles_exclues("repurgateur", _RULES_VOCS["value"]) == {"invocation"}


def test_apprentissage_exclu_ne_mord_que_sur_la_famille_nommee():
    voc = "repurgateur"
    assert apprentissage_exclu(_sort(famille="invocation"), voc, _RULES_VOCS) is True
    assert apprentissage_exclu(_sort(famille="malediction"), voc, _RULES_VOCS) is False
    assert apprentissage_exclu(_sort(), voc, _RULES_VOCS) is False   # sans famille
    # Le démoniste, lui, n'exclut rien : la MÊME donnée reste apprenable pour lui.
    assert apprentissage_exclu(_sort(famille="invocation"), "demoniste", _RULES_VOCS) is False


def test_apprentissage_exclu_accepte_doc_brut_et_vue_normalisee():
    """Les endpoints valident une vue normalisée, les générateurs un doc brut."""
    doc = _sort(famille="invocation")
    assert apprentissage_exclu(doc, "repurgateur", _RULES_VOCS) is True
    assert apprentissage_exclu(normaliser_sort(doc), "repurgateur", _RULES_VOCS) is True


# ── Listes d'apprenables ─────────────────────────────────────────────────────────

_DOCS_SORTS = [
    _sort(_id="sort:flamme", nom="Flamme"),
    _sort(_id="sort:pacte", nom="Pacte", famille="invocation",
          invocation={"espece": "espece:demon_servant", "duree": 3}),
]


def _find_sorts(selector):
    return [d for d in _DOCS_SORTS if d["type"] == selector.get("type")]


def test_sorts_apprenables_retire_la_famille_exclue():
    perso = _perso("repurgateur")
    ids = [s["id"] for s in sorts_apprenables(perso, _find_sorts, lambda r: None, _RULES_VOCS)]
    assert ids == ["sort:flamme"]          # le pacte est de famille `invocation`


def test_sorts_apprenables_laisse_tout_a_qui_n_exclut_rien():
    perso = _perso("demoniste")
    ids = sorted(s["id"] for s in sorts_apprenables(perso, _find_sorts, lambda r: None, _RULES_VOCS))
    assert ids == ["sort:flamme", "sort:pacte"]


_DOCS_COMPS = [
    _comp(_id="competence:sentence", nom="Sentence"),
    _comp(_id="competence:appel", nom="Appel", famille="invocation"),
]


def _find_comps(selector):
    return [d for d in _DOCS_COMPS if d["type"] == selector.get("type")]


def test_competences_apprenables_retire_la_famille_exclue():
    perso = _perso("repurgateur")
    ids = [c["id"] for c in competences_apprenables(perso, _find_comps, _RULES_VOCS)]
    assert ids == ["competence:sentence"]


def test_competences_apprenables_sans_rules_vocations_nexclut_rien():
    """Signature rétro-compatible : un appelant qui ne passe pas le doc obtient la liste
    d'avant, exclusions comprises — c'est ce qui autorise l'argument optionnel."""
    perso = _perso("repurgateur")
    ids = sorted(c["id"] for c in competences_apprenables(perso, _find_comps))
    assert ids == ["competence:appel", "competence:sentence"]


# ── Purge paresseuse des sorts d'une école qu'on ne pratique plus ────────────────
# Pendant utile de l'exclusion : changer la `magie` d'une vocation ferme sa liste « à
# apprendre », mais `sorts_connus` n'est relu contre l'école NULLE PART ailleurs — les sorts
# déjà achetés se lanceraient indéfiniment. La purge se fait au passage (/play) et réécrit
# le doc à ce moment-là.

_SORTS_BASE = {
    "sort:flamme": _sort(_id="sort:flamme", nom="Flamme", magie="Démonologie"),
    "sort:feu_pur": _sort(_id="sort:feu_pur", nom="Feu purificateur",
                          vocation="repurgateur", magie="Sainte"),
    "sort:sceau": _sort(_id="sort:sceau", nom="Sceau", vocation="repurgateur", magie="Sainte"),
}


def _get_doc(doc_id):
    return _SORTS_BASE.get(doc_id)


def test_purge_retire_les_sorts_de_l_ecole_abandonnee():
    perso = _perso("repurgateur", sorts_connus=["sort:flamme", "sort:feu_pur", "sort:sceau"])
    partis = purger_sorts_hors_ecole(perso, _get_doc, _RULES_VOCS)

    assert [p["id"] for p in partis] == ["sort:feu_pur", "sort:sceau"]
    assert partis[0]["magie"] == "Sainte" and partis[0]["nom"] == "Feu purificateur"
    assert perso["sorts_connus"] == ["sort:flamme"]      # l'école pratiquée reste


def test_purge_est_idempotente_et_ne_touche_rien_sans_raison():
    """Deuxième passage : plus rien à retirer, donc rien à réécrire (`change` reste faux)."""
    perso = _perso("repurgateur", sorts_connus=["sort:flamme"])
    assert purger_sorts_hors_ecole(perso, _get_doc, _RULES_VOCS) == []
    assert perso["sorts_connus"] == ["sort:flamme"]
    assert purger_sorts_hors_ecole(_perso("demoniste", sorts_connus=[]), _get_doc, _RULES_VOCS) == []


def test_purge_ne_detruit_jamais_sur_une_lecture_qui_echoue():
    """Id mort ou doc illisible : LAISSÉ EN PLACE. Une lecture ratée ne doit pas effacer ce
    qu'un joueur a payé — c'est le seul endroit du jeu qui retire un sort acquis."""
    perso = _perso("repurgateur", sorts_connus=["sort:disparu", "sort:feu_pur"])
    partis = purger_sorts_hors_ecole(perso, lambda i: None if i == "sort:disparu" else _get_doc(i),
                                     _RULES_VOCS)
    assert [p["id"] for p in partis] == ["sort:feu_pur"]
    assert perso["sorts_connus"] == ["sort:disparu"]


def test_purge_garde_un_sort_dont_l_ecole_n_est_pas_resoluble():
    """Sort sans `magie`, d'une vocation non magique : aucune école identifiable. Le retirer
    reviendrait à punir un contenu mal tagué."""
    docs = {"sort:orphelin": _sort(_id="sort:orphelin", vocation="guerrier", magie=None)}
    perso = _perso("repurgateur", sorts_connus=["sort:orphelin"])
    assert purger_sorts_hors_ecole(perso, docs.get, _RULES_VOCS) == []
    assert perso["sorts_connus"] == ["sort:orphelin"]


def test_purge_ignore_le_niveau_d_ecole():
    """Le niveau NATIF vaut 0 à la création : `niveau_ecole` rend 0, pas None. Un test de
    vérité sur cette valeur purgerait tout le répertoire d'un personnage neuf."""
    perso = _perso("demoniste", sorts_connus=["sort:flamme"])
    perso["vocations_niveaux"] = {"demoniste": 0}
    assert purger_sorts_hors_ecole(perso, _get_doc, _RULES_VOCS) == []
    assert perso["sorts_connus"] == ["sort:flamme"]


def test_purge_garde_une_ecole_ACHETEE_par_un_polyvalent():
    """Un lettré qui a acheté la Sainte la pratique : ses sorts Saints ne bougent pas, quelle
    que soit l'école native de sa vocation."""
    perso = _perso("lettre", sorts_connus=["sort:feu_pur"])
    perso["magies_apprises"] = {"Sainte": 1}
    assert purger_sorts_hors_ecole(perso, _get_doc, _RULES_VOCS) == []


def test_purge_nettoie_les_epingles_sans_creer_la_cle():
    """Clé présente → filtrée. Clé ABSENTE → laissée absente : l'absence est un état à part
    entière (auto-épinglage du premier sort connu), la poser figerait un choix non fait."""
    perso = _perso("repurgateur", sorts_connus=["sort:flamme", "sort:feu_pur"],
                   sorts_epingles=["sort:feu_pur", "sort:flamme"])
    purger_sorts_hors_ecole(perso, _get_doc, _RULES_VOCS)
    assert perso["sorts_epingles"] == ["sort:flamme"]

    sans_cle = _perso("repurgateur", sorts_connus=["sort:flamme", "sort:feu_pur"])
    assert "sorts_epingles" not in sans_cle
    purger_sorts_hors_ecole(sans_cle, _get_doc, _RULES_VOCS)
    assert "sorts_epingles" not in sans_cle
