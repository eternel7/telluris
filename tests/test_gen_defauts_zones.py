# tests/test_gen_defauts_zones.py
#
# Amorçage des défauts de zones (dev/gen_defauts_zones.py) : déduction « ≥ SEUIL_LIEUX lieux »,
# sans région (Auteur, 16/11 : une zone par biome), idempotence (un défaut déjà présent — retouché à la main — est gardé).
# Données en constantes : aucun fichier de jsons/ (CLAUDE.md §20).

import importlib.util
from pathlib import Path

from utils import zones

_spec = importlib.util.spec_from_file_location(
	"gen_defauts_zones", Path(__file__).resolve().parent.parent / "dev" / "gen_defauts_zones.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

REGLES = {"_id": zones.REGLES_REGIONS, "regions": {
	"europe": {"nom": "Europe", "lieux": ["lieu:a", "lieu:b"]},
	"afrique_du_nord": {"nom": "AdN", "lieux": ["lieu:c"]},
}}


def _lieu(lid, renc=(), ress=()):
	return {"_id": lid, "rencontres": [{"espece": e, "zones": z} for e, z in renc],
			"ressources": [{"ressource": r, "zones": z} for r, z in ress]}


def test_deduit_ce_que_le_seuil_de_lieux_partage_sans_region():
	lieux = [
		_lieu("lieu:a", renc=[("espece:loup", ["zone:foret"]), ("espece:ours", ["zone:foret"])]),
		_lieu("lieu:b", renc=[("espece:loup", ["zone:foret", "zone:foret@3"])]),
		_lieu("lieu:c", renc=[("espece:loup", ["zone:foret"])], ress=[("item:sel", ["zone:desert"])]),
	]
	d = gen.deduire(lieux, REGLES)
	# Auteur, 16/11 : une zone par biome — l'amorçage n'écrit plus de `regions`.
	assert d == {"zone:foret": {"rencontres": {"espece:loup": []}}}
	assert gen.SEUIL_LIEUX == 2  # l'ours (1 lieu) et le sel (1 lieu) restent des compléments


def test_un_seul_lieu_ne_fait_pas_un_defaut():
	lieux = [_lieu("lieu:a", renc=[("espece:loup", ["zone:foret"])]),
			 _lieu("lieu:x", renc=[("espece:ours", ["zone:foret"])])]
	assert gen.deduire(lieux, REGLES) == {}


def test_zones_a_emettre_garde_les_defauts_existants_et_est_idempotent():
	docs = {"zone:foret": {"_id": "zone:foret", "_rev": "1-x", "nom": "Forêt",
						   "defauts_rencontres": [{"espece": "espece:loup", "regions": ["europe"]}]}}
	deduits = {"zone:foret": {"rencontres": {"espece:loup": ["afrique_du_nord"], "espece:cerf": []}}}
	(z,) = gen.zones_a_emettre(docs, deduits)
	assert "_rev" not in z
	assert z["defauts_rencontres"] == [{"espece": "espece:loup", "regions": ["europe"]},
									   {"espece": "espece:cerf"}]
	docs["zone:foret"] = z
	assert gen.zones_a_emettre(docs, deduits) == []


def test_regles_regions_garde_les_ajouts_d_une_edition():
	existant = {"_id": zones.REGLES_REGIONS, "_rev": "2-y", "type": "rules", "regions": {
		"europe": {"nom": "Europe de l'Ouest", "lieux": ["lieu:atlantis"]},
		"mers": {"nom": "Mers", "lieux": ["lieu:mer"]},
	}}
	r = gen.regles_regions(existant)
	assert r["regions"]["europe"]["nom"] == "Europe de l'Ouest"
	assert r["regions"]["europe"]["lieux"][0] == "lieu:atlantis"
	assert "lieu:france" in r["regions"]["europe"]["lieux"]
	assert r["regions"]["mers"] == {"nom": "Mers", "lieux": ["lieu:mer"]}
	assert list(r["regions"])[: len(gen.REGIONS)] == list(gen.REGIONS)
	assert gen.regles_regions(r) == r
