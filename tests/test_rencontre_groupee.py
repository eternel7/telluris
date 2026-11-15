# tests/test_rencontre_groupee.py
# Rencontre GROUPÉE PAR ESPÈCE (`combat.instantiate_groupes`, budget de menace) et ARMURE
# NATURELLE des espèces (`combat.armure_naturelle_espece`, `dev/gen_armure_naturelle.py`).
import copy
import os
import sys

from models.character_stats import BaseStats, EquipmentBonus
from utils import combat, simulateur

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))
import gen_armure_naturelle as gen  # noqa: E402


def _espece(slug, **extra):
	return {"_id": f"espece:{slug}", "nom": slug.capitalize(), "tags": [],
			"base_attributes": {"R": {"min": 40, "max": 60}}, **extra}


class _Rand:
	"""Hasard piloté : `choice` / `choices` prennent l'élément d'index `pick`, `random` rend `r`."""
	def __init__(self, r=0.99, pick=0):
		self.r, self.pick, self.weights = r, pick, []

	def choice(self, seq):
		return seq[self.pick % len(seq)]

	def choices(self, seq, weights=None, k=1):
		self.weights.append(list(weights))
		return [seq[self.pick % len(seq)]]

	def random(self):
		return self.r


def _couts(table):
	return lambda e, p: table[e["_id"]]


# ── Budget de menace ──────────────────────────────────────────────────────────

def test_le_nombre_baisse_quand_la_puissance_monte():
	rat, troll = _espece("rat"), _espece("troll")
	couts = _couts({"espece:rat": 10, "espece:troll": 100})
	nb_rats = len(combat.instantiate_groupes([rat], [], 40, couts, plafond=8, proba_second=0))
	nb_trolls = len(combat.instantiate_groupes([troll], [], 40, couts, plafond=8, proba_second=0))
	assert nb_rats == 4    # 4 × 10 tiennent dans 40
	assert nb_trolls == 1  # trop cher, mais un groupe a toujours son premier spécimen


def test_un_seul_groupe_homogene_sans_second():
	pool = [_espece("loup"), _espece("rat")]
	monstres = combat.instantiate_groupes(pool, [], 100, _couts({"espece:loup": 20, "espece:rat": 5}),
										  plafond=8, proba_second=0, rand=_Rand(pick=0))
	assert {m["espece_id"] for m in monstres} == {"espece:loup"}
	assert len(monstres) == 5
	assert [m["id"] for m in monstres] == [f"monstre_{i}" for i in range(5)]


def test_plafond_respecte():
	monstres = combat.instantiate_groupes([_espece("rat")], [], 1000, _couts({"espece:rat": 1}),
										  plafond=3, proba_second=0)
	assert len(monstres) == 3


def test_second_groupe_depense_le_reste():
	pool = [_espece("gobelin"), _espece("loup")]
	couts = _couts({"espece:gobelin": 30, "espece:loup": 20})
	# r = 0 < proba : second groupe. Gobelins : 3 × 30 = 90 sur 100, reste 10 → au moins un loup.
	monstres = combat.instantiate_groupes(pool, [], 100, couts, plafond=8, proba_second=0.2,
										  rand=_Rand(r=0.0, pick=0))
	assert [m["espece_id"] for m in monstres] == ["espece:gobelin"] * 3 + ["espece:loup"]
	# r au-dessus de la proba : pas de second groupe.
	sans = combat.instantiate_groupes(pool, [], 100, couts, plafond=8, proba_second=0.2,
									  rand=_Rand(r=0.5, pick=0))
	assert {m["espece_id"] for m in sans} == {"espece:gobelin"}


def test_second_groupe_borne_par_le_plafond():
	pool = [_espece("rat"), _espece("loup")]
	monstres = combat.instantiate_groupes(pool, [], 1000, _couts({"espece:rat": 1, "espece:loup": 1}),
										  plafond=4, proba_second=1.0, rand=_Rand(r=0.0))
	assert len(monstres) == 4 and {m["espece_id"] for m in monstres} == {"espece:rat"}


def test_pool_d_une_seule_espece_sans_second_groupe():
	monstres = combat.instantiate_groupes([_espece("loup")], [], 30, _couts({"espece:loup": 20}),
										  plafond=8, proba_second=1.0, rand=_Rand(r=0.0))
	assert len(monstres) == 1


def test_cout_illisible_ne_fait_pas_une_nuee():
	monstres = combat.instantiate_groupes([_espece("x")], [], 500, lambda e, p: None,
										  plafond=8, proba_second=0)
	assert len(monstres) == 1


def test_focalisation_pondere_l_espece_principale():
	pool = [_espece("loup"), _espece("rat")]
	r = _Rand()
	combat.instantiate_groupes(pool, [], 10, _couts({"espece:loup": 5, "espece:rat": 5}),
							   plafond=8, proba_second=0, espece_weights={"espece:loup": 3.0}, rand=r)
	assert r.weights[0] == [3.0, 1.0]


def test_pool_vide():
	assert combat.instantiate_groupes([], [], 100, lambda e, p: 1) == []


def test_cout_mesure_au_grade_tire():
	"""Le coût reçoit le PROFIL tiré : un grade plus haut coûte plus, donc vient moins nombreux."""
	vus = []
	profil = {"_id": "profil:veteran", "niveau": 3}
	combat.instantiate_groupes([_espece("loup")], [profil], 50,
							   lambda e, p: vus.append(p and p["_id"]) or 20, plafond=8, proba_second=0)
	assert vus and set(vus) == {"profil:veteran"}


# ── Armure naturelle ──────────────────────────────────────────────────────────

def test_armure_naturelle_ajoutee_aux_pa():
	sans = combat.build_monster_snapshot(_espece("bete"), None, 0, calculer_xp=False)
	avec = combat.build_monster_snapshot(_espece("bete", armure_naturelle=3), None, 0, calculer_xp=False)
	assert avec["pa"] == sans["pa"] + 3
	assert avec["pa_zones"] == sans["pa_zones"] == {}
	assert avec["armure_naturelle"] == 3
	assert "armure_naturelle" not in sans and "equipment_bonus" not in sans


def test_armure_naturelle_survit_au_recalcul_des_stats():
	snap = combat.build_monster_snapshot(_espece("bete", armure_naturelle=4), None, 0, calculer_xp=False)
	pa = snap["pa"]
	combat._refresh_snapshot_stats(snap)
	assert snap["pa"] == pa


def test_armure_naturelle_gardee_par_le_banc():
	snap = combat.build_monster_snapshot(_espece("bete", armure_naturelle=2), None, 0, calculer_xp=False)
	base = snap["pa"]
	equipe = simulateur._equiper_snapshot(copy.deepcopy(snap), {"cou": "item:inexistant"})
	assert equipe["pa"] == base


def test_armure_naturelle_illisible_vaut_zero():
	assert combat.armure_naturelle_espece({"armure_naturelle": "x"}) == 0
	assert combat.armure_naturelle_espece({"armure_naturelle": -2}) == 0
	assert combat.armure_naturelle_espece({}) == 0


def test_avec_armure_naturelle_garde_l_invariant():
	eq = EquipmentBonus(pa=5, pa_hors_zone=1, pa_zones={"torse": 4})
	combat.avec_armure_naturelle(eq, 3)
	assert eq.pa == eq.pa_hors_zone + sum(eq.pa_zones.values()) == 8


# ── Générateur ────────────────────────────────────────────────────────────────

def test_bareme_par_rang():
	assert [gen.bonus_armure(r, []) for r in ("F", "E", "D", "C", "B", "A", "S", "S+")] == \
		[0, 0, 0] + [gen.BAREME[r] for r in ("C", "B", "A", "S", "S+")]


def test_nature_module_seulement_a_partir_du_rang_c():
	cuirasse, sans_corps = [gen.TAGS_CUIRASSE[0]], [gen.TAGS_SANS_CORPS[0]]
	assert gen.bonus_armure("D", cuirasse) == 0
	assert gen.bonus_armure("B", cuirasse) == gen.BAREME["B"] + 1
	assert gen.bonus_armure("B", sans_corps) == gen.BAREME["B"] - 1
	assert gen.bonus_armure("C", sans_corps) == 0          # jamais sous 0
	assert gen.bonus_armure("B", cuirasse + sans_corps) == gen.BAREME["B"]


def test_delta_idempotent_et_retrait():
	a = _espece("a")
	b = _espece("b", armure_naturelle=gen.BAREME["B"])
	c = _espece("c", armure_naturelle=2)  # rang D : le champ doit partir
	rangs = {a["_id"]: "A", b["_id"]: "B", c["_id"]: "D"}
	sortie = gen.delta([a, b, c], rangs)
	assert [d["_id"] for d in sortie] == [a["_id"], c["_id"]]
	assert sortie[0]["armure_naturelle"] == gen.BAREME["A"]
	assert "armure_naturelle" not in sortie[1]
	assert {k: v for k, v in sortie[0].items() if k != "armure_naturelle"} == a
	# Rejeu sur le résultat : plus rien à importer.
	assert gen.delta([sortie[0], b, sortie[1]], rangs) == []
