"""Égypte ↔ Levant (dev/gen_egypte_levant.py) — sur le dump committé le plus récent."""

import pytest

from dev import gen_egypte_levant as gel
from dev import gen_grille_image as ggi


@pytest.fixture(scope="module")
def dump():
	docs = ggi.charger_dump()
	ids = {d.get("_id") for d in docs}
	if not {gel.EGYPTE, gel.LEVANT} <= ids:
		pytest.skip("aucun dump committé avec l'Égypte et le Levant")
	return docs


@pytest.fixture(scope="module")
def construit(dump):
	return gel.construire(dump)


def test_un_passage_par_nom_sans_refus_ni_alerte(construit):
	liens, refus, avert = construit
	assert refus == [] and avert == []
	assert [d["_id"] for d in liens if not d.get("_deleted")] == \
		[f"{gel.PREFIXE}_{i:02d}" for i in range(1, len(gel.PASSAGES) + 1)]


def test_chaque_bout_sur_la_frontiere_peinte_de_sa_carte(dump, construit):
	"""Côté praticable, contre une case FERMÉE de la bande du voisin."""
	par_id = {d["_id"]: d for d in dump}
	colonnes = {gel.EGYPTE: gel.COLONNE_EGYPTE, gel.LEVANT: gel.COLONNE_LEVANT}
	for lien in construit[0]:
		for n in lien["nodes"]:
			x, y = n["pos"]
			cells = par_id[n["lieu"]]["cells"]
			x_ligne, x_ferme = colonnes[n["lieu"]]
			assert x == x_ligne and cells[y][x] == 1 and cells[y][x_ferme] == 0


def test_les_passages_se_suivent_du_nord_au_sud_des_deux_cotes(construit):
	for lieu in (gel.EGYPTE, gel.LEVANT):
		ys = [next(n["pos"][1] for n in d["nodes"] if n["lieu"] == lieu) for d in construit[0]]
		assert ys == sorted(ys)
