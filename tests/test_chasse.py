"""Quêtes de « chasse » (utils/chasse.py) — logique pure, sans DB.

Les dépendances DB sont injectées (get_doc_fn / find_docs_fn). Le monde de test : une
cité (Auxerre) avec une grille, une zone forêt placée, et le loup qui y rôde ; quatre
profils de grades croissants dont un réservé aux créatures « magie » — c'est lui qui doit
être écarté quand on résout le grade d'un loup (filtre restriction_tags ⊆ tags de l'espèce).
"""

import random

import pytest

from models import character_stats
from utils import chasse, quetes, combat
from utils.recrutement import RANGS


# ── Monde de test ────────────────────────────────────────────────────────────────

LOUP = {"_id": "espece:loup", "type": "espece", "nom": "Loup",
        "tags": ["animal", "predateur"],
        "base_attributes": {k: {"min": 4, "max": 8} for k in
                            ("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch")}}
LAPIN = {"_id": "espece:lapin", "type": "espece", "nom": "Lapin", "tags": ["animal"],
         "base_attributes": {k: {"min": 2, "max": 4} for k in
                             ("V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch")}}

# Grades : niveaux 1 / 2 / 2 / 3. `apprenti` est réservé aux créatures « magie » → jamais
# un loup. Modificateur qui creuse l'écart de PV pour vérifier « l'élite est plus costaude ».
def _profil(pid, nom, niveau, restr=None):
	return {"_id": pid, "type": "profil", "nom": nom, "niveau": niveau,
	        "restriction_tags": restr or [],
	        "attributs_modifier": {"F": {"min": niveau * 3, "max": niveau * 3},
	                               "R": {"min": niveau * 3, "max": niveau * 3}}}

NOVICE = _profil("profil:novice", "Novice", 1)
APPRENTI = _profil("profil:apprenti", "Apprenti", 2, ["magie"])
COMBATTANT = _profil("profil:combattant", "Combattant", 2)
VETERAN = _profil("profil:veteran", "Vétéran", 3)
MAGE = _profil("profil:mage", "Mage", 3, ["magie"])

# Une zone forêt, placée en rectangle centré (5,5), 10×10 → le point (5,5) est dedans.
FORET_DEF = {"_id": "zone:foret", "type": "zone", "nom": "Forêt", "intensite_max": 1.0}
PLACEMENT = {"zone": "zone:foret", "x": 5, "y": 5, "w": 10, "h": 10, "forme": "rectangle", "rot": 0}

AUXERRE = {
	"_id": "lieu:auxerre", "type": "lieu", "categorie": "ville", "label": "Auxerre",
	"dimensions": {"x": 20, "y": 20},
	"cells": [[0]],
	"zone_influences": [PLACEMENT],
	"rencontres": [{"espece": "espece:loup", "zones": ["zone:foret"]}],
	"profil_weights": {"profil:novice": 5, "profil:apprenti": 1,
	                   "profil:combattant": 1, "profil:veteran": 1},
}
COMPTOIR = {
	"_id": "lieu:comptoir", "type": "lieu", "categorie": "guilde_aventurier_comptoir",
	"label": "Le comptoir", "lieu_parent": "lieu:auxerre",
}
# Un lieu enfant d'Auxerre SANS rencontres/zone → exclu des lieux de chasse.
BOUTIQUE = {"_id": "lieu:boutique", "type": "lieu", "categorie": "forge",
            "label": "La Forge", "lieu_parent": "lieu:auxerre"}

_DOCS = {d["_id"]: d for d in
         [LOUP, LAPIN, NOVICE, APPRENTI, COMBATTANT, VETERAN, MAGE,
          FORET_DEF, AUXERRE, COMPTOIR, BOUTIQUE]}


def _get_doc(doc_id):
	return _DOCS.get(doc_id)


def _find_docs(query):
	if query.get("type") == "lieu" and "lieu_parent" in query:
		return [d for d in _DOCS.values()
		        if d.get("type") == "lieu" and d.get("lieu_parent") == query["lieu_parent"]]
	return [d for d in _DOCS.values() if all(d.get(k) == v for k, v in query.items())]


# ── position_de_chasse ───────────────────────────────────────────────────────────

def test_position_dans_zone_de_lespece():
	pos = chasse.position_de_chasse(AUXERRE, LOUP)
	assert pos == {"x": 5, "y": 5}  # centre du seul placement de la zone du loup


def test_position_none_si_espece_absente_des_zones():
	# Le lapin n'est dans aucune `rencontres` → aucune zone ne le contient.
	assert chasse.position_de_chasse(AUXERRE, LAPIN) is None


def test_position_none_sans_grille():
	sans_grille = dict(AUXERRE)
	sans_grille.pop("dimensions")
	assert chasse.position_de_chasse(sans_grille, LOUP) is None


# ── resoudre_profil_chasse ───────────────────────────────────────────────────────

def test_profil_max_est_le_plus_haut_compatible():
	# Compatibles = novice(1)/combattant(2)/veteran(3) ; apprenti(magie) écarté → max = vétéran.
	pid = chasse.resoudre_profil_chasse(AUXERRE, LOUP, chasse.TIER_MAX, {"x": 5, "y": 5}, _get_doc)
	assert pid == "profil:veteran"


def test_profil_max_moins_1():
	# Un cran sous le max (niv 3) = niv 2 → combattant (le seul niv 2 non-magie).
	pid = chasse.resoudre_profil_chasse(AUXERRE, LOUP, chasse.TIER_MAX_MOINS_1, {"x": 5, "y": 5}, _get_doc)
	assert pid == "profil:combattant"


def test_profil_exclut_restriction_incompatible():
	# Une distribution PUREMENT magie sur une espèce non-magie → aucun profil compatible.
	lieu = dict(AUXERRE, profil_weights={"profil:apprenti": 1, "profil:mage": 1})
	assert chasse.resoudre_profil_chasse(lieu, LOUP, chasse.TIER_MAX, {"x": 5, "y": 5}, _get_doc) is None


def test_profil_egalite_niveau_tiree_au_hasard():
	# Deux profils niv 2 compatibles → max_moins_1 vise niv 1, mais forçons l'égalité au niv max.
	c2 = _profil("profil:combattant2", "Combattant II", 2)
	docs = dict(_DOCS, **{"profil:combattant2": c2})
	lieu = dict(AUXERRE, profil_weights={"profil:combattant": 1, "profil:combattant2": 1})
	tirages = set()
	for seed in range(20):
		random.seed(seed)
		tirages.add(chasse.resoudre_profil_chasse(lieu, LOUP, chasse.TIER_MAX, {"x": 5, "y": 5}, docs.get))
	assert tirages == {"profil:combattant", "profil:combattant2"}  # les deux sortent


def test_profil_none_hors_zone():
	# Un point hors de tout placement de la zone du loup : le repli garde les placements de
	# l'espèce (le point est le centre de l'un d'eux dans le flux normal) → toujours résolu.
	pid = chasse.resoudre_profil_chasse(AUXERRE, LOUP, chasse.TIER_MAX, {"x": 99, "y": 99}, _get_doc)
	assert pid == "profil:veteran"


# ── lieux_chasse_de ──────────────────────────────────────────────────────────────

def test_lieux_chasse_cite_plus_enfants_valides():
	lieux = chasse.lieux_chasse_de("lieu:auxerre", _get_doc, _find_docs)
	ids = {l["_id"] for l in lieux}
	assert "lieu:auxerre" in ids          # la cité elle-même
	assert "lieu:boutique" not in ids     # enfant sans rencontres/zone → exclu
	assert "lieu:comptoir" not in ids     # idem


# ── quetes_chasse_actives ────────────────────────────────────────────────────────

def test_quetes_chasse_actives_filtre_lieu():
	character = {"quetes_actives": [
		{"id": "q1", "objectif": {"type": "chasse", "lieu": "lieu:auxerre", "cible": "espece:loup"}},
		{"id": "q2", "objectif": {"type": "chasse", "lieu": "lieu:ailleurs"}},
		{"id": "q3", "objectif": {"type": "kill", "cible": "espece:loup"}},
	]}
	actives = chasse.quetes_chasse_actives(character, "lieu:auxerre")
	assert [q["id"] for q in actives] == ["q1"]


# ── Rang de guilde ───────────────────────────────────────────────────────────────

def test_rang_de_defaut_F():
	assert chasse.rang_de({}, "lieu:auxerre") == "F"
	assert chasse.rang_de({"rangs_guilde": {"lieu:auxerre": "C"}}, "lieu:auxerre") == "C"


def test_rang_suivant_et_max():
	sommet = RANGS[-1]
	assert chasse.rang_suivant("F") == "E"
	assert chasse.rang_suivant(sommet) == sommet    # plafonné au sommet de l'échelle
	assert chasse.rang_suivant("inconnu") == RANGS[0]
	assert chasse.rang_max_atteint(sommet) is True
	assert chasse.rang_max_atteint("F") is False


def test_promouvoir_mute_et_monte():
	character = {}
	assert chasse.promouvoir(character, "lieu:auxerre") == "E"
	assert chasse.promouvoir(character, "lieu:auxerre") == "D"
	assert character["rangs_guilde"]["lieu:auxerre"] == "D"


# ── offre_rang_pour ──────────────────────────────────────────────────────────────

def test_offre_rang_tire_une_epreuve_max():
	random.seed(1)
	offre = chasse.offre_rang_pour({}, COMPTOIR, _get_doc, _find_docs)
	assert offre is not None
	assert offre["source"] == "rang"
	assert offre["lieu_parent"] == "lieu:auxerre"
	assert offre["objectif"]["type"] == "chasse"
	assert offre["objectif"]["profil"] == "profil:veteran"   # grade MAX
	assert offre["rang_vise"] == "E"
	assert offre["narration"]
	# Le libellé de l'élite vient de l'échelle de bestiaire (niveau 3 → « Farouche »), JAMAIS
	# du `nom` du doc profil, taillé pour un aventurier (« Vétéran »).
	assert "Farouche" in offre["titre"]
	assert "Vétéran" not in offre["titre"]
	assert "Farouche" in offre["description"]
	assert "Farouche" in offre["narration"]


def test_qualificatif_par_niveau_et_bornage():
	assert [chasse.qualificatif_de({"niveau": n}) for n in range(1, 7)] == chasse.QUALIFICATIFS
	assert chasse.qualificatif_de({"niveau": 99}) == "Apocalypse"   # borné en haut
	assert chasse.qualificatif_de({"niveau": 0}) == "Vicieux"       # borné en bas
	assert chasse.qualificatif_de(None) == "Vicieux"                # profil introuvable


def test_offre_rang_none_si_rang_max():
	character = {"rangs_guilde": {"lieu:auxerre": RANGS[-1]}}
	assert chasse.offre_rang_pour(character, COMPTOIR, _get_doc, _find_docs) is None


def test_offre_rang_none_si_deja_active():
	character = {"quetes_actives": [{"source": "rang", "cite": "lieu:auxerre"}]}
	assert chasse.offre_rang_pour(character, COMPTOIR, _get_doc, _find_docs) is None


# ── accepter_rang / solder_rang ──────────────────────────────────────────────────

def _character_avec_offre():
	random.seed(1)
	offre = chasse.offre_rang_pour({}, COMPTOIR, _get_doc, _find_docs)
	return {"rang_offert": {"lieu": "lieu:comptoir", "quete": offre},
	        "quetes_actives": [], "quetes_terminees": [],
	        "xp_total": 0, "vocations_niveaux": {"guerrier": 0}, "voc": "guerrier",
	        "or": 0, "argent": 0, "cuivre": 0, "attribute_points": 0}, offre


def test_accepter_rang_pousse_snapshot_et_vide_offre():
	character, offre = _character_avec_offre()
	q = chasse.accepter_rang(character)
	assert q is not None
	assert q["source"] == "rang"
	assert q["cite"] == "lieu:auxerre"
	assert q["rang_vise"] == "E"
	assert q["narration"] == offre["narration"]
	assert character["rang_offert"]["quete"] is None
	assert len(character["quetes_actives"]) == 1


def test_solder_rang_promeut_et_archive():
	character, _ = _character_avec_offre()
	q = chasse.accepter_rang(character)
	q["progress"] = 1  # objectif atteint (élite abattue)
	res = chasse.solder_rang(character, q["id"])
	assert res["promu"] == "E"
	assert character["rangs_guilde"]["lieu:auxerre"] == "E"
	assert character["quetes_actives"] == []
	assert len(character["quetes_terminees"]) == 1


def test_solder_rang_refuse_si_incomplet():
	character, _ = _character_avec_offre()
	q = chasse.accepter_rang(character)  # progress 0
	assert chasse.solder_rang(character, q["id"]) is None
	assert character["quetes_actives"]  # toujours active


# ── build_monster_snapshot (refactor) + progression ──────────────────────────────

def test_build_monster_snapshot_applique_le_profil():
	elite = combat.build_monster_snapshot(LOUP, VETERAN, 3)
	base = combat.build_monster_snapshot(LOUP, NOVICE, 3)
	assert elite["id"] == "monstre_3"
	assert elite["profil_id"] == "profil:veteran"
	assert elite["niveau"] == 3
	# L'élite (niv 3, gros modificateurs) est plus costaude que le novice (niv 1).
	assert elite["pv_max"] > base["pv_max"]


def test_maj_progress_chasse_seule_lelite_marquee_compte():
	character = {"quetes_actives": [
		{"id": "qc", "objectif": {"type": "chasse", "cible": "espece:loup", "quantite": 1}, "progress": 0},
	]}
	monstres = [
		{"id": "m0", "espece_id": "espece:loup", "vivant": False},               # loup normal mort
		{"id": "m1", "espece_id": "espece:loup", "vivant": False, "quete_chasse": "qc"},  # l'élite
	]
	quetes.maj_progress_chasse(character, monstres)
	assert character["quetes_actives"][0]["progress"] == 1


def test_maj_progress_chasse_ignore_si_elite_vivante():
	character = {"quetes_actives": [
		{"id": "qc", "objectif": {"type": "chasse", "cible": "espece:loup", "quantite": 1}, "progress": 0},
	]}
	monstres = [{"id": "m1", "espece_id": "espece:loup", "vivant": True, "quete_chasse": "qc"}]
	quetes.maj_progress_chasse(character, monstres)
	assert character["quetes_actives"][0]["progress"] == 0


# ── Génération au tableau (utils/quetes, DB monkeypatchée) ────────────────────────

GUILDE = {"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier",
          "lieu_parent": "lieu:auxerre"}


@pytest.fixture
def quetes_db(monkeypatch):
	"""Branche les accès DB de `quetes` sur le monde de test (le loup à Auxerre)."""
	docs = dict(_DOCS, **{GUILDE["_id"]: GUILDE})
	monkeypatch.setattr(quetes, "get_doc", lambda doc_id: docs.get(doc_id))
	monkeypatch.setattr(quetes, "find_docs", _find_docs)
	monkeypatch.setattr(character_stats, "QUETE_CHASSE_XP_FACTEUR", 3.0)
	return docs


def test_generer_quete_chasse_objectif_complet(quetes_db):
	q = quetes.generer_quete(GUILDE, AUXERRE, "chasse", ("lieu:auxerre", "espece:loup"), 1)
	assert q is not None
	obj = q["objectif"]
	assert obj["type"] == "chasse"
	assert obj["cible"] == "espece:loup"
	assert obj["lieu"] == "lieu:auxerre"
	assert obj["profil"] == "profil:combattant"   # board = max−1
	assert obj["position"] == {"x": 5, "y": 5}
	assert q["recompenses"]["xp"] > 0


def test_candidats_chasse_du_tableau(quetes_db):
	candidats = quetes._candidats_chasse("lieu:auxerre")
	assert ("chasse", ("lieu:auxerre", "espece:loup")) in candidats
	# Le lapin n'est dans aucune rencontre → pas de candidat chasse pour lui.
	assert not any(c[1][1] == "espece:lapin" for c in candidats)


# ── dans_zone_chasse (zone 3×3 de déclenchement) ─────────────────────────────────

@pytest.mark.parametrize("jx,jy,attendu", [
	(5, 5, True),    # pile sur la cible
	(6, 4, True),    # coin de la zone 3×3 (Chebyshev 1)
	(4, 6, True),
	(7, 5, False),   # Chebyshev 2 en x
	(5, 3, False),   # Chebyshev 2 en y
])
def test_dans_zone_chasse(jx, jy, attendu):
	obj = {"type": "chasse", "position": {"x": 5, "y": 5}}
	assert chasse.dans_zone_chasse(obj, {"x": jx, "y": jy}) is attendu


def test_dans_zone_chasse_sans_position_toujours_vrai():
	# Lieu sans grille : pas de contrainte de position (comportement historique).
	assert chasse.dans_zone_chasse({"type": "chasse"}, {"x": 99, "y": 99}) is True


def test_dans_zone_chasse_position_joueur_absente():
	obj = {"type": "chasse", "position": {"x": 5, "y": 5}}
	assert chasse.dans_zone_chasse(obj, None) is False
	assert chasse.dans_zone_chasse(obj, {}) is False


# ── _carte_chasse (payload du bouton 🗺️) ─────────────────────────────────────────

def test_carte_chasse_payload(quetes_db, monkeypatch):
	from utils import marche
	monkeypatch.setattr(marche, "_lieu_image_route", lambda lieu: ("auxerre.png", "towns"))
	carte = quetes._carte_chasse({"type": "chasse", "lieu": "lieu:auxerre", "position": {"x": 5, "y": 5}})
	assert carte == {
		"position": {"x": 5, "y": 5},
		"dimensions": {"x": 20, "y": 20},
		"image": "auxerre.png",
		"image_route": "towns",
		"lieu_nom": "Auxerre",
	}


def test_carte_chasse_none_sans_image(quetes_db, monkeypatch):
	from utils import marche
	monkeypatch.setattr(marche, "_lieu_image_route", lambda lieu: (None, None))
	assert quetes._carte_chasse({"lieu": "lieu:auxerre", "position": {"x": 5, "y": 5}}) is None


# ── Direction cardinale (règle par axe, y vers le bas) ───────────────────────────

@pytest.mark.parametrize("depuis,vers,attendu", [
	((0, 0), (1, 1), "sud-est"),
	((1, 1), (0, 0), "nord-ouest"),
	((0, 0), (1, 0), "est"),
	((1, 0), (0, 0), "ouest"),
	((0, 0), (0, 1), "sud"),
	((0, 1), (0, 0), "nord"),
	((3, 3), (3, 3), ""),          # même case → aucune direction
])
def test_direction_cardinale_simple(depuis, vers, attendu):
	assert chasse.direction_cardinale_simple(depuis, vers) == attendu


def test_phrase_direction_prepositions():
	assert quetes._phrase_direction("sud-est") == "Au sud-est du bâtiment de la guilde"
	assert quetes._phrase_direction("nord") == "Au nord du bâtiment de la guilde"
	assert quetes._phrase_direction("est") == "À l'est du bâtiment de la guilde"
	assert quetes._phrase_direction("ouest") == "À l'ouest du bâtiment de la guilde"
	assert quetes._phrase_direction("") == "Sur l'emplacement du bâtiment de la guilde"


def test_carte_chasse_direction_texte(quetes_db, monkeypatch):
	from utils import marche, focalisation
	monkeypatch.setattr(marche, "_lieu_image_route", lambda lieu: ("auxerre.png", "towns"))
	monkeypatch.setattr(focalisation, "charger_graphe", lambda fd: {})
	monkeypatch.setattr(focalisation, "prochaine_etape", lambda g, d, v: {"porte": (2, 2)})
	obj = {"type": "chasse", "lieu": "lieu:auxerre", "position": {"x": 5, "y": 5}}
	carte = quetes._carte_chasse(obj, giver_id="lieu:guilde")
	assert carte["direction_texte"] == "Au sud-est du bâtiment de la guilde"
	# Porte au-delà de la cible → direction inverse.
	monkeypatch.setattr(focalisation, "prochaine_etape", lambda g, d, v: {"porte": (9, 9)})
	carte = quetes._carte_chasse(obj, giver_id="lieu:guilde")
	assert carte["direction_texte"] == "Au nord-ouest du bâtiment de la guilde"


def test_carte_chasse_sans_direction_si_donneur_injoignable(quetes_db, monkeypatch):
	from utils import marche, focalisation
	monkeypatch.setattr(marche, "_lieu_image_route", lambda lieu: ("auxerre.png", "towns"))
	monkeypatch.setattr(focalisation, "charger_graphe", lambda fd: {})
	monkeypatch.setattr(focalisation, "prochaine_etape", lambda g, d, v: None)
	obj = {"type": "chasse", "lieu": "lieu:auxerre", "position": {"x": 5, "y": 5}}
	carte = quetes._carte_chasse(obj, giver_id="lieu:guilde")
	assert "direction_texte" not in carte
	# Sans giver du tout → pas de direction non plus.
	assert "direction_texte" not in quetes._carte_chasse(obj)


def test_quete_detail_carte_seulement_si_chasse_localisee(quetes_db, monkeypatch):
	from utils import marche
	monkeypatch.setattr(marche, "_lieu_image_route", lambda lieu: ("auxerre.png", "towns"))
	# Chasse AVEC position → carte présente.
	q_chasse = {"id": "qc", "objectif": {"type": "chasse", "cible": "espece:loup",
	            "lieu": "lieu:auxerre", "position": {"x": 5, "y": 5}, "quantite": 1}}
	assert "carte" in quetes.quete_detail({}, q_chasse)
	# Kill classique → pas de carte.
	q_kill = {"id": "qk", "objectif": {"type": "kill", "cible": "espece:loup", "quantite": 3}}
	assert "carte" not in quetes.quete_detail({}, q_kill)
