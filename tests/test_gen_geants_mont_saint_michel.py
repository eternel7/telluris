"""`dev/gen_geants_mont_saint_michel.py` — les géants de la baie, sur le dernier dump.

1. **Le Mont est dans sa zone** : la case de l'îlot dessiné (23,14) est dans le placement du Mont.
2. **Les deux grades ne se mélangent pas** : aucune case n'est à la fois au Mont et dans
   l'arrière-pays, ni dans l'un d'eux et dans la zone très dangereuse (le grade se somme par
   placement actif, cf. `zones.resolve_profil_weights`).
3. **L'arrière-pays est à terre** : sous la côte murée de la baie (rangée 14).
4. **Le géant du Mont est seul** : round(intensité × 3) = 1 dans sa zone.
5. **Les géants restent sous le maître du Mont** : grades strictement inférieurs.
6. **Idempotent.**
"""

import glob
import os

import pytest

from dev import gen_geants_mont_saint_michel as g
from utils.zones import compute_zone_intensity

DUMPS = sorted(glob.glob(os.path.join(g.RACINE, "jsons", "telluris-dump-*.json")))
pytestmark = pytest.mark.skipif(not DUMPS, reason="aucun dump committé")


@pytest.fixture(scope="module")
def base():
	return g.charger(DUMPS[-1])


@pytest.fixture(scope="module")
def france(base):
	return g.appliquer(base[g.LIEU_ID])


def _cases(lieu, predicat):
	dims = lieu["dimensions"]
	return {(x, y) for y in range(dims["y"]) for x in range(dims["x"])
			if any(compute_zone_intensity(x, y, p, {"intensite_max": 1}) > 0
				   for p in lieu["zone_influences"] if predicat(p))}


def _de(zone):
	return lambda p: p.get("zone") == zone


def test_le_mont_est_dans_sa_zone(france):
	assert (23, 14) in _cases(france, _de(g.ZONE_MONT))


def test_les_grades_ne_se_melangent_pas(france):
	mont = _cases(france, _de(g.ZONE_MONT))
	arriere = _cases(france, _de(g.ZONE_ARRIERE_PAYS))
	dangereuse = _cases(france, _de("zone:tres_dangereuse"))
	assert mont and arriere
	assert not mont & arriere
	assert not (mont | arriere) & dangereuse


def test_les_zones_numerotees_n_etaient_pas_utilisees(base):
	# Si l'auteur pose ailleurs une de ces zones, ses rencontres y amèneraient les géants.
	for doc in base.values():
		if doc.get("type") == "lieu":
			zones = {p.get("zone") for p in doc.get("zone_influences") or []}
			assert not zones & {g.ZONE_MONT, g.ZONE_ARRIERE_PAYS}, doc["_id"]


def test_l_arriere_pays_est_a_terre(france):
	assert min(y for _, y in _cases(france, _de(g.ZONE_ARRIERE_PAYS))) >= 15


def test_le_geant_du_mont_est_seul(base):
	assert round(base[g.ZONE_MONT]["intensite_max"] * 3) == 1


def test_les_geants_restent_sous_le_maitre_du_mont(base):
	def niveaux(spec):
		return [base[pid]["niveau"] for pid in spec["profil_weights"]]
	assert max(niveaux(g.PLACEMENT_ARRIERE_PAYS)) < min(niveaux(g.PLACEMENT_MONT))


def test_rencontres(france):
	zones = {r["espece"]: r["zones"] for r in france["rencontres"]}
	assert g.ZONE_ARRIERE_PAYS in zones[g.GEANT]
	assert "zone:tres_dangereuse" in zones[g.GEANT]          # l'existant est conservé
	assert zones[g.GEANT_DU_MONT] == [g.ZONE_MONT]


def test_idempotent(france):
	assert g.appliquer(france) == france
