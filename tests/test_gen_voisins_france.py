"""dev/gen_voisins_france.py — n'émet que ce qui diffère du dump (rejeu idempotent) ; sur le
dernier dump committé, chaque frontière entre pays porte un passage une case sur deux."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_france_espagne_italie as sud  # noqa: E402
from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_pannonie as pannonie  # noqa: E402
from dev import gen_plaine_europeenne as plaine  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402

# Préfixe → noms : les cinq frontières entre pays.
FRONTIERES = {
	"link:france_to_plaine_europeenne": plaine.PASSAGES_PLAINE,
	"link:france_to_espagne": sud.PASSAGES_ESPAGNE,
	"link:france_to_italie": sud.PASSAGES_ITALIE,
	"link:italie_to_pannonie": pannonie.PASSAGES_ITALIE,
	"link:pannonie_to_roumanie": pannonie.PASSAGES_ROUMANIE,
}


def test_n_emet_que_ce_qui_differe_du_dump():
	dump = [{"_id": "lieu:a", "_rev": "4-x", "v": 1}, {"_id": "link:b", "_rev": "1-y", "v": 2}]
	sortants = [{"_id": "lieu:a", "v": 1}, {"_id": "link:b", "v": 3}, {"_id": "link:c", "v": 0}]
	emis, refus = a_emettre(dump, sortants)
	assert refus == [] and [d["_id"] for d in emis] == ["link:b", "link:c"]


def test_id_produit_deux_fois_refuse():
	emis, refus = a_emettre([], [{"_id": "link:a"}, {"_id": "link:a"}])
	assert refus == ["link:a : produit deux fois"]


def test_frontieres_du_dump_une_case_sur_deux():
	docs = ggi.charger_dump()
	ids = {d.get("_id") for d in docs}
	if not {plaine.FRANCE, plaine.PLAINE, pannonie.PANNONIE} <= ids:
		pytest.skip("aucun dump committé avec les cartes de pays")

	def interdit(*_):
		raise AssertionError("tous les lieux sont en base : aucune grille à proposer")

	lieux_sud, liens, refus, avert = sud.construire(docs, interdit)
	france = next(d for d in lieux_sud if d["_id"] == plaine.FRANCE)
	italie = next(d for d in lieux_sud if d["_id"] == pannonie.ITALIE)
	l_pl, d_pl, r_pl, _, a_pl = plaine.construire(docs, interdit, interdit, france)
	l_pa, d_pa, r_pa, _, a_pa = pannonie.construire(docs, interdit, interdit, interdit, italie)
	assert refus + r_pl + r_pa == []
	# Aucun avertissement : sur chaque frontière, le côté le plus long a EXACTEMENT un poste
	# une case sur deux (`postes`), et le côté court les a tous.
	assert avert + a_pl + a_pa == []
	par_lieu = {d["_id"]: d for d in lieux_sud + l_pl + l_pa}
	liens += d_pl + d_pa
	for prefixe, noms in FRONTIERES.items():
		du_prefixe = [l for l in liens if l["_id"].startswith(prefixe + "_")]
		assert len(du_prefixe) == len(noms) == len(set(noms))
		for l in du_prefixe:
			for n in l["nodes"]:
				x, y = n["pos"]
				assert par_lieu[n["lieu"]]["cells"][y][x] >= 1, (l["_id"], n)
