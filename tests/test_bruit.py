# tests/test_bruit.py
# BRUIT DU GROUPE (`utils/bruit.py`, Auteur 17/11) : mesure, effets sur l'effectif tiré dans la
# fourchette (`combat.instantiate_groupes`), sur le second groupe, et sur la fréquence des
# COMBATS de zone (`zones.resolve_zone_event`).
import random

import pytest

from models import character_stats as cs
from utils import bruit, combat, zones
from utils import composition_rencontre as compo


def _pts(compagnons=0, montures=0, proteges=0, taux=0.0):
	return bruit.points(bruit.sources(compagnons, montures, proteges, taux))


# ── Mesure ────────────────────────────────────────────────────────────────────

def test_points_pondere_chaque_source():
	attendu = (1 + 2 * cs.RENCONTRE_BRUIT_COMPAGNON + cs.RENCONTRE_BRUIT_MONTURE
			   + 2 * cs.RENCONTRE_BRUIT_PROTEGE + 0.5 * cs.RENCONTRE_BRUIT_CHARGE)
	assert _pts(2, 1, 2, 0.5) == pytest.approx(attendu)
	assert _pts() == 1   # le joueur seul, sac vide


def test_taux_de_charge():
	assert bruit.taux_charge(50, 200) == 0.25
	assert bruit.taux_charge(10, 0) == 0          # aucune capacité
	assert bruit.taux_charge(None, "x") == 0      # illisible


def test_mesurer_cumule_tous_les_porteurs():
	perso, comp, monture = {"p": 10, "c": 50}, {"p": 20, "c": 50}, {"p": 70, "c": 100}
	b = bruit.mesurer(perso, [comp], [monture], [{}], lambda d: d["p"], lambda d: d["c"])
	assert b["sources"][-1]["cle"] == "charge" and b["sources"][-1]["taux"] == 0.5   # 100 / 200
	assert b["points"] == pytest.approx(_pts(1, 1, 1, 0.5))


def test_niveaux_affiches():
	assert bruit.niveau(_pts())[0] == "discret"
	assert bruit.niveau(cs.RENCONTRE_BRUIT_REFERENCE)[0] == "audible"
	assert bruit.niveau(2 * cs.RENCONTRE_BRUIT_REFERENCE)[0] == "bruyant"


def test_facteurs_bornes():
	ref = cs.RENCONTRE_BRUIT_REFERENCE
	assert bruit.facteur_combat(ref) == 1
	assert bruit.facteur_combat(0) == cs.RENCONTRE_BRUIT_FREQ_MIN
	assert bruit.facteur_combat(100 * ref) == cs.RENCONTRE_BRUIT_FREQ_MAX
	assert bruit.facteur_second(ref) == 1
	assert bruit.facteur_second(100 * ref) == cs.RENCONTRE_BRUIT_SECOND_MAX
	assert bruit.position_fourchette(ref) == 0.5
	assert bruit.position_fourchette(100 * ref) == 1


def test_reference_nulle_desactive(monkeypatch):
	monkeypatch.setattr(cs, "RENCONTRE_BRUIT_REFERENCE", 0.0)
	assert not bruit.actif()
	assert not bruit.s_applique({"_id": "lieu:foret"})
	assert bruit.facteur_combat(10) == 1 and bruit.position_fourchette(10) == 0.5


def test_portee_nature_seulement():
	lieu = {"_id": "lieu:foret"}
	assert bruit.s_applique(lieu)
	assert not bruit.s_applique(lieu, est_ville=True)
	assert not bruit.s_applique(lieu, en_mer=True)
	assert not bruit.s_applique(None)


# ── Effectif dans la fourchette ───────────────────────────────────────────────

class _R:
	def __init__(self, rs):
		self.rs = list(rs)

	def random(self):
		return self.rs.pop(0) if len(self.rs) > 1 else self.rs[0]

	def choice(self, seq):
		return seq[0]

	def choices(self, seq, weights=None, k=1):
		return [seq[0]]


def test_tirage_borne_a_la_fourchette():
	assert bruit.tirer_effectif((3, 6), 0.0, _R([0.0, 0.99])) == 3    # jamais sous le min
	assert bruit.tirer_effectif((3, 6), 1.0, _R([0.99, 0.0])) == 6    # jamais au-delà du max
	assert bruit.tirer_effectif((3, 6), 0.5, _R([0.5, 0.5])) in (4, 5)


def test_solo_en_bas_convoi_en_haut():
	r = random.Random(7)
	f = (3, 6)
	seul = [bruit.tirer_effectif(f, bruit.position_fourchette(_pts()), r) for _ in range(2000)]
	ref = [bruit.tirer_effectif(f, bruit.position_fourchette(cs.RENCONTRE_BRUIT_REFERENCE), r)
		   for _ in range(2000)]
	convoi = [bruit.tirer_effectif(f, 1.0, r) for _ in range(2000)]
	moy = lambda xs: sum(xs) / len(xs)
	assert moy(seul) < moy(ref) < moy(convoi)
	assert max(seul) <= 5 and min(convoi) >= 5
	assert moy(ref) == pytest.approx(bruit.milieu(f), abs=0.15)


_P = {n: {"_id": f"profil:p{n}", "niveau": n} for n in (1, 2, 3)}


def _aff():
	return {"_id": compo.DOC_ID}


def test_instantiate_groupes_suit_le_bruit_et_garde_les_grades():
	orc = {"_id": "espece:orc", "nom": "Orc", "tags": [], "effectif": [2, 6],
		   "base_attributes": {"R": {"min": 40, "max": 60}}}
	couts = lambda e, p: 10 * p["niveau"]
	profils = list(_P.values())
	kw = dict(plafond=8, proba_second=0, affinites=_aff())
	seul = combat.instantiate_groupes([orc], profils, 100, couts, rand=_R([0.5]), bruit=_pts(), **kw)
	convoi = combat.instantiate_groupes([orc], profils, 100, couts, rand=_R([0.5]),
										bruit=4 * cs.RENCONTRE_BRUIT_REFERENCE, **kw)
	assert len(seul) < len(convoi) == 6
	# Grades : la part par spécimen se calcule sur le milieu de la fourchette, pas sur l'effectif.
	assert seul[0]["profil_id"] == convoi[0]["profil_id"]


def test_compagnons_ne_decalent_plus_avec_le_bruit():
	orc = {"_id": "espece:orc", "nom": "Orc", "tags": [], "effectif": [3, 3],
		   "base_attributes": {"R": {"min": 40, "max": 60}}}
	m = combat.instantiate_groupes([orc], [], 100, lambda e, p: 1, plafond=8, proba_second=0,
								   affinites=_aff(), rand=_R([0.5]), compagnons=4, bruit=10.0)
	assert len(m) == 3    # borné à la fourchette (sans bruit : 3 + 4 // 2 = 5)


def test_second_groupe_suit_le_bruit():
	gob = {"_id": "espece:gobelin", "tags": [], "effectif": [2, 2]}
	loup = {"_id": "espece:loup", "tags": [], "effectif": [2, 2]}
	# Diversité pleine dès une espèce candidate : seule la chance de base et le bruit jouent.
	kw = dict(plafond=8, proba_second=0.9, affinites={**_aff(), "diversite_pleine": 1})
	# random = 0,35 : sous 0,9 (référence) mais au-dessus de 0,9 × (1/3) (seul).
	ref = combat.instantiate_groupes([gob, loup], [], 100, lambda e, p: 1, rand=_R([0.35]),
									 bruit=cs.RENCONTRE_BRUIT_REFERENCE, **kw)
	seul = combat.instantiate_groupes([gob, loup], [], 100, lambda e, p: 1, rand=_R([0.35]),
									  bruit=_pts(), **kw)
	assert len({m["espece_id"] for m in ref}) == 2
	assert len({m["espece_id"] for m in seul}) == 1


# ── Fréquence des combats ─────────────────────────────────────────────────────

_PLACEMENT = [{"zone": "zone:foret", "x": 5, "y": 5, "w": 10, "h": 10}]   # centré sur (5, 5)
_DEFS = {"zone:foret": {"_id": "zone:foret", "nom": "Forêt", "intensite_max": 0.5,
						"table_evenements": [{"type": "combat", "poids": 1},
											 {"type": "ressource", "poids": 3}]}}


def _frequences(f, n=20000, seed=3):
	random.seed(seed)
	r = random.Random(seed + 1)
	out = {"combat": 0, "ressource": 0, None: 0}
	for _ in range(n):
		ev = zones.resolve_zone_event(5, 5, _PLACEMENT, _DEFS, rand_fn=r.random, facteur_combat=f)
		out[ev["type"] if ev else None] += 1
	return {k: v / n for k, v in out.items()}


def test_facteur_ne_touche_que_les_combats():
	base, discret, bruyant = _frequences(1.0), _frequences(0.6), _frequences(1.5)
	assert base["combat"] == pytest.approx(0.5 * 1 / 4, abs=0.01)   # intensité × part des combats
	assert discret["combat"] == pytest.approx(base["combat"] * 0.6, abs=0.01)
	assert bruyant["combat"] == pytest.approx(base["combat"] * 1.5, abs=0.01)
	for f in (discret, bruyant):
		assert f["ressource"] == pytest.approx(base["ressource"], abs=0.012)


def test_intensite_renvoyee_reste_celle_de_la_zone():
	ev = zones.resolve_zone_event(5, 5, _PLACEMENT, _DEFS, rand_fn=lambda: 0.0, facteur_combat=1.5)
	assert ev["intensite"] == 0.5   # règle le budget de menace : le bruit n'y touche pas
