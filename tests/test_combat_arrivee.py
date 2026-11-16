"""Combat à l'arrivée et gardien qui réapparaît (utils/combat_arrivee.py) — le sommet du Mont.

Verrouille : la lecture fail-closed du bloc `combat_arrivee`, le délai GLOBAL de réapparition
(doc d'état `reapparition:*`), le nombre de comparses (1 + 1 par tranche de 2 compagnons),
la note de mort à la finalisation (toute issue, une seule fois par combat), le déclenchement
côté router (lieu vide pendant le délai, combat actif repris) et le contenu du générateur
`dev/gen_mont_saint_michel_sommet.py` (grille d'un seul tenant, connexion « Gravir le mont »).
"""

import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

from utils import combat_arrivee as ca  # noqa: E402
from utils import combat as combat_util  # noqa: E402
from routers import user as user_router  # noqa: E402

GEANT_DU_MONT = "espece:geant_du_mont_saint_michel"
GEANT = "espece:geant_ou_titan"
LIEU = "lieu:sommet_du_mont_saint_michel"


def _lieu(**bloc):
	base = {"espece": GEANT_DU_MONT, "accompagnants": [GEANT], "nb_accompagnants": 1}
	base.update(bloc)
	return {"_id": LIEU, "type": "lieu", "image": "x.jpg", "tags": ["mont"],
			ca.CHAMP: base}


# ── Lecture du bloc ──────────────────────────────────────────────────────────────

def test_spec_lue_avec_le_delai_par_defaut():
	regle = ca.spec(_lieu())
	assert regle["espece"] == GEANT_DU_MONT
	assert regle["accompagnants"] == [GEANT]
	assert regle["reapparition_min"] == ca.REAPPARITION_MIN_DEFAUT
	assert regle["profil_weights"] is None


@pytest.mark.parametrize("fautif", [
	{"espece": "geant"},                         # préfixe manquant
	{"reapparition_min": -1},
	{"reapparition_min": True},
	{"nb_accompagnants": -2},
	{"profil_weights": {"seigneur": 1}},         # clé hors `profil:`
	{"profil_weights": {"profil:x": "lourd"}},
])
def test_bloc_fautif_n_ouvre_aucun_combat(fautif):
	assert ca.spec(_lieu(**fautif)) is None


def test_lieu_sans_bloc():
	assert ca.spec({"_id": LIEU}) is None
	assert ca.spec(None) is None


# ── Délai de réapparition ────────────────────────────────────────────────────────

def test_abattu_recemment_borne_au_delai():
	regle = ca.spec(_lieu(reapparition_min=5))
	etat = {"tue_at": 1000}
	assert ca.abattu_recemment(etat, regle, 1000 + 5 * 60 - 1)
	assert not ca.abattu_recemment(etat, regle, 1000 + 5 * 60)
	assert not ca.abattu_recemment(None, regle, 1000)
	assert not ca.abattu_recemment({"tue_at": "hier"}, regle, 1000)


def test_etat_id_du_lieu():
	assert ca.etat_id(LIEU) == "reapparition:sommet_du_mont_saint_michel"


def test_comparses_un_plus_un_par_deux_compagnons():
	regle = ca.spec(_lieu())
	assert [ca.nb_accompagnants(regle, n) for n in (0, 1, 2, 3, 4, 5)] == [1, 1, 2, 2, 3, 3]
	assert ca.nb_accompagnants(ca.spec(_lieu(accompagnants=[])), 4) == 0


# ── Mort du gardien ──────────────────────────────────────────────────────────────

def _combat(vivant_gardien, _id="combat:1"):
	return {"_id": _id, ca.CHAMP: ca.marque(LIEU, ca.spec(_lieu())), "monstres": [
		{"espece_id": GEANT_DU_MONT, "vivant": vivant_gardien},
		{"espece_id": GEANT, "vivant": True},
	]}


def test_gardien_abattu_seulement_s_il_est_tombe():
	assert ca.gardien_abattu(_combat(False))
	assert not ca.gardien_abattu(_combat(True))
	assert not ca.gardien_abattu({"monstres": [{"espece_id": GEANT_DU_MONT, "vivant": False}]})


def test_invocation_de_meme_espece_ne_compte_pas():
	c = _combat(True)
	c["monstres"].append({"espece_id": GEANT_DU_MONT, "vivant": False, "est_invocation": True})
	assert not ca.gardien_abattu(c)


def test_noter_abattu_une_seule_fois_par_combat():
	doc = ca.noter_abattu(None, _combat(False), 5000)
	assert doc == {"_id": ca.etat_id(LIEU), "type": "reapparition", "lieu": LIEU,
				   "tue_at": 5000, "combat_id": "combat:1"}
	assert ca.noter_abattu(doc, _combat(False), 9000) is None      # re-finalisation
	suivant = ca.noter_abattu(dict(doc, _rev="1-a"), _combat(False, "combat:2"), 9000)
	assert suivant["tue_at"] == 9000 and suivant["_rev"] == "1-a"
	assert ca.noter_abattu(None, _combat(True), 5000) is None


def test_finalisation_note_la_mort_meme_en_fuite(monkeypatch):
	ecrits = []
	monkeypatch.setattr(combat_util, "get_doc", lambda _id: None)
	monkeypatch.setattr(combat_util, "save_doc", lambda d: ecrits.append(d) or d)
	c = _combat(False)
	c["status"] = "fuite"
	combat_util._noter_gardien_abattu(c)
	assert [d["_id"] for d in ecrits] == [ca.etat_id(LIEU)]
	ecrits.clear()
	combat_util._noter_gardien_abattu({"_id": "combat:x", "monstres": []})   # combat ordinaire
	assert ecrits == []


# ── Déclenchement à l'arrivée (routers/user.py) ──────────────────────────────────

@pytest.fixture
def monde(monkeypatch):
	docs = {GEANT_DU_MONT: {"_id": GEANT_DU_MONT}, GEANT: {"_id": GEANT}}
	combats, sauves, appels = [], [], {}

	def instancier(cible, accomp, profils, nb, profil_weights=None):
		appels["nb"] = nb
		return [{"espece_id": cible["_id"]}] + [{"espece_id": accomp[0]["_id"]}] * nb

	monkeypatch.setattr(user_router, "get_doc", docs.get)
	monkeypatch.setattr(user_router, "find_docs", lambda q: combats if q.get("type") == "combat" else [])
	monkeypatch.setattr(user_router, "save_doc", lambda d: sauves.append(d) or d)
	monkeypatch.setattr(user_router, "instantiate_rencontre", instancier)
	monkeypatch.setattr(user_router, "create_combat_doc",
						lambda ch, monstres, tags, img, **kw: {"_id": "combat:neuf", "status": "active",
															  "monstres": monstres, "kw": kw})
	monkeypatch.setattr(user_router, "resolve_first_turns", lambda c: None)
	monkeypatch.setattr(user_router.recrutement, "groupe_effectif", lambda c, g: [{}, {}])
	monkeypatch.setattr(user_router.montures, "montures_effectives", lambda c, g: [])
	monkeypatch.setattr(user_router.escorte, "proteges_effectifs", lambda c, g: [])
	monkeypatch.setattr(user_router.quetes, "now_epoch", lambda: 10_000)
	return docs, combats, sauves, appels


PERSO = {"_id": "character:u_1", "user_id": "u"}


def test_arrivee_ouvre_le_combat_a_la_case_d_arrivee(monde):
	_docs, _combats, sauves, appels = monde
	cid = user_router._declencher_combat_arrivee(PERSO, _lieu(), {"x": 15, "y": 15})
	assert cid == "combat:neuf"
	combat = sauves[-1]
	assert combat[ca.CHAMP] == {"lieu": LIEU, "espece": GEANT_DU_MONT}
	assert combat["kw"]["point_apparition"] == {"x": 15, "y": 15}
	assert appels["nb"] == 2                    # 1 + 1 pour deux compagnons
	assert combat["monstres"][0]["espece_id"] == GEANT_DU_MONT


def test_lieu_vide_pendant_le_delai_puis_de_nouveau_garde(monde):
	docs, _combats, sauves, _ = monde
	docs[ca.etat_id(LIEU)] = {"tue_at": 10_000 - 4 * 60}
	assert user_router._declencher_combat_arrivee(PERSO, _lieu(), {"x": 1, "y": 1}) is None
	assert sauves == []
	docs[ca.etat_id(LIEU)] = {"tue_at": 10_000 - 5 * 60}
	assert user_router._declencher_combat_arrivee(PERSO, _lieu(), {"x": 1, "y": 1}) == "combat:neuf"


def test_combat_actif_repris_jamais_double(monde):
	_docs, combats, sauves, _ = monde
	combats.append({"_id": "combat:en_cours", "character_id": PERSO["_id"], "status": "active"})
	assert user_router._declencher_combat_arrivee(PERSO, _lieu(), {"x": 1, "y": 1}) == "combat:en_cours"
	assert sauves == []


def test_lieu_ordinaire_ou_gardien_inconnu(monde):
	docs, *_ = monde
	assert user_router._declencher_combat_arrivee(PERSO, {"_id": "lieu:x"}, {"x": 0, "y": 0}) is None
	del docs[GEANT_DU_MONT]
	assert user_router._declencher_combat_arrivee(PERSO, _lieu(), {"x": 0, "y": 0}) is None


# ── Contenu du générateur ────────────────────────────────────────────────────────

def test_generateur_sommet_et_connexion():
	import gen_mont_saint_michel_sommet as gen
	cells = gen.grille()
	assert len(cells) == gen.ROWS and all(len(l) == gen.COLS for l in cells)
	sol = {(x, y) for y in range(gen.ROWS) for x in range(gen.COLS) if cells[y][x] == gen.SOL}
	assert gen.joignables(cells, gen.ARRIVEE) == sol
	assert all(cells[y][x] == gen.VIDE for x, y in gen.obstacles())
	lieu = gen.lieu_doc(cells)
	regle = ca.spec(lieu)
	assert regle["espece"] == GEANT_DU_MONT and regle["accompagnants"] == [GEANT]
	assert regle["nb_accompagnants"] == 1 and regle["reapparition_min"] == 5
	assert regle["profil_weights"] == gen.geants.PLACEMENT["profil_weights"]
	assert lieu["dimensions"] == {"x": gen.COLS, "y": gen.ROWS}
	noeuds = {n["lieu"]: n for n in gen.link_doc()["nodes"]}
	assert noeuds[gen.LIEU_ID]["label"] == "Gravir le mont"
	assert noeuds[gen.LIEU_ID]["pos"] == list(gen.ARRIVEE)
	assert noeuds["lieu:france"]["pos"] == list(gen.MONT_FRANCE)
