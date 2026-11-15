# tests/test_gen_carcasses_biomes.py
#
# Carcasses à poids réaliste de la faune des zones par biome (dev/gen_carcasses_biomes.py) :
# une carcasse par espèce de `gen_zones_biomes.ESPECES`, accord du nom (h aspiré), découpe par
# `gen_carcasses_parties` au-delà du seuil, carcasse déjà en base jamais recréée. Données en
# constantes (CLAUDE.md §20).

import importlib.util
import sys
from pathlib import Path

from models import character_stats

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dev"))
_spec = importlib.util.spec_from_file_location("gen_carcasses_biomes", RACINE / "dev" / "gen_carcasses_biomes.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def _espece(slug, tags=("animal",)):
	return {"_id": f"espece:{slug}", "type": "espece", "nom": gen.ESPECES[slug][0], "tags": list(tags),
			"depecage": [["viande", 2], ["os", 1], ["cuir_brut", 1]]}


def test_une_carcasse_par_espece_de_faune():
	assert set(gen.CARCASSES) == set(gen.ESPECES)
	for slug, (pmin, pmax) in gen.CARCASSES.items():
		assert 0 < pmin < pmax, slug


def test_nom_accorde_et_forme_des_carcasses_du_bestiaire():
	assert gen.carcasse_doc("hyenes")["nom"] == "Carcasse de Hyènes"        # h aspiré
	assert gen.carcasse_doc("antilopes")["nom"] == "Carcasse d'Antilopes"
	d = gen.carcasse_doc("elephants")
	assert d["sous_categorie"] == "carcasse" and d["loot_defaut"] is True
	assert d["source_espece"] == "espece:elephants" and d["poids"] == gen.CARCASSES["elephants"]


def test_lourde_debitee_legere_entiere_existante_gardee():
	seuil = float(character_stats.CARCASSE_DECOUPE_POIDS_MIN)
	assert gen.CARCASSES["elephants"][1] > seuil and gen.CARCASSES["flamants"][1] <= seuil
	existante = {"_id": "item:singes", "type": "item", "sous_categorie": "carcasse", "poids": 9,
				 "source_espece": "espece:singes", "nom": "Carcasse retouchée"}
	dump = [_espece("elephants"), _espece("flamants"), _espece("singes"), existante]
	sortie, avert = gen.construire(dump)
	par_id = {d["_id"]: d for d in sortie}
	assert par_id["item:elephants"]["decoupe"] and "item:elephants_corps" in par_id
	assert "decoupe" not in par_id["item:flamants"]
	assert "item:singes" not in par_id                                     # jamais recréée
	# Seules les espèces absentes de la fixture sont signalées.
	signalees = {a.split()[0] for a in avert if a.startswith("espece:")}
	assert signalees == {f"espece:{s}" for s in gen.CARCASSES} - {"espece:elephants", "espece:flamants",
																  "espece:singes"}


def test_espece_absente_du_dump_signalee():
	_, avert = gen.construire([])
	assert any(a.startswith("espece:") for a in avert)
