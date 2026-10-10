"""dev/gen_voisins_france.py — n'émet que ce qui diffère du dump (rejeu idempotent)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_voisins_france import a_emettre  # noqa: E402


def test_n_emet_que_ce_qui_differe_du_dump():
	dump = [{"_id": "lieu:a", "_rev": "4-x", "v": 1}, {"_id": "link:b", "_rev": "1-y", "v": 2}]
	sortants = [{"_id": "lieu:a", "v": 1}, {"_id": "link:b", "v": 3}, {"_id": "link:c", "v": 0}]
	emis, refus = a_emettre(dump, sortants)
	assert refus == [] and [d["_id"] for d in emis] == ["link:b", "link:c"]


def test_id_produit_deux_fois_refuse():
	emis, refus = a_emettre([], [{"_id": "link:a"}, {"_id": "link:a"}])
	assert refus == ["link:a : produit deux fois"]
