"""`dev/gen_geants_mont_saint_michel.py` — les géants de la baie, sur le dernier dump.

1. **Le Mont est dans la zone** : la case de l'îlot dessiné (23,14) est dans le placement.
2. **Les grades ne se mélangent pas** : aucune case commune avec la zone très dangereuse (le
   grade se somme par placement actif, cf. `zones.resolve_profil_weights`).
3. **La zone est à terre** : sous la côte murée de la baie, à l'est de la mer.
4. **Le géant du Mont est toujours un Seigneur** : pour TOUT profil, chaque caractéristique tirée
   reste dans la fourchette d'un géant ordinaire Seigneur.
5. **Les géants restent sous le maître du Mont** : aucun grade de la zone n'atteint Seigneur.
6. **Idempotent.**
7. **Son équipement** : les deux objets de la légende sont portables par lui (arme/armure à
   emplacement équipable), dans sa liste `items`, et NON FABRICABLES — aucune recette, sur-mesure
   fermé, exclus du générateur de recettes pour orphelins. Faits pour un géant : aucune Lignée
   n'atteint la Force requise, et aucun malus ne pèse sur le géant qui les porte.
"""

import glob
import os

import pytest

from dev import gen_geants_mont_saint_michel as g
from dev import gen_recettes_orphelins
from utils import marche, simulateur
from utils.zones import compute_zone_intensity

DUMPS = sorted(glob.glob(os.path.join(g.RACINE, "jsons", "telluris-dump-*.json")))
pytestmark = pytest.mark.skipif(not DUMPS, reason="aucun dump committé")


@pytest.fixture(scope="module")
def base():
	return g.charger(DUMPS[-1])


@pytest.fixture(scope="module")
def docs(base):
	return g.generer(base)


@pytest.fixture(scope="module")
def france(docs):
	return docs[0]


@pytest.fixture(scope="module")
def geant_du_mont(docs):
	return docs[1]


def _cases(lieu, zone):
	dims = lieu["dimensions"]
	return {(x, y) for y in range(dims["y"]) for x in range(dims["x"])
			if any(compute_zone_intensity(x, y, p, {"intensite_max": 1}) > 0
				   for p in lieu["zone_influences"] if p.get("zone") == zone)}


def test_un_seul_fichier_deux_docs(docs):
	assert [d["_id"] for d in docs] == [g.LIEU_ID, g.GEANT_DU_MONT]
	assert not any("_rev" in d for d in docs)


def test_le_mont_est_dans_la_zone(france):
	assert (23, 14) in _cases(france, g.ZONE)


def test_les_grades_ne_se_melangent_pas(france):
	assert not _cases(france, g.ZONE) & _cases(france, "zone:tres_dangereuse")


def test_la_zone_numerotee_n_est_utilisee_qu_en_france(base):
	# Si l'auteur la pose ailleurs, ses rencontres y amèneraient les géants.
	for doc in base.values():
		if doc.get("type") == "lieu" and doc["_id"] != g.LIEU_ID:
			assert g.ZONE not in {p.get("zone") for p in doc.get("zone_influences") or []}, doc["_id"]


def test_la_zone_est_a_terre(france):
	# Baie : mer au nord de la rangée 14 et à l'ouest du Cotentin (x 27).
	assert all(y >= 14 for x, y in _cases(france, g.ZONE) if x < 27)


@pytest.mark.parametrize("profil_id", ["profil:novice", "profil:combattant", "profil:veteran",
									   "profil:champion", "profil:heros", "profil:seigneur"])
def test_le_geant_du_mont_est_toujours_un_seigneur(base, geant_du_mont, profil_id):
	cible = g.fourchette_seigneur(base[g.GEANT], base[g.SEIGNEUR])
	mods = base[profil_id].get("attributs_modifier") or {}
	for cle, borne in geant_du_mont["base_attributes"].items():
		mod = mods.get(cle) or {}
		# Extrêmes de `combat.roll_monster_stats` : clamp(min + écart, min, max).
		for ecart in (mod.get("min", 0), mod.get("max", 0)):
			tire = max(borne["min"], min(borne["max"], borne["min"] + ecart))
			assert cible[cle]["min"] <= tire <= cible[cle]["max"], (profil_id, cle)


def test_fourchette_relue_du_dump(base, geant_du_mont):
	assert set(geant_du_mont["base_attributes"]) == set(base[g.GEANT]["base_attributes"])
	assert geant_du_mont["description"] == base[g.GEANT_DU_MONT]["description"]


def test_les_geants_restent_sous_le_maitre_du_mont(base):
	assert max(base[p]["niveau"] for p in g.PLACEMENT["profil_weights"]) < base[g.SEIGNEUR]["niveau"]


def test_rencontres(france):
	zones = {r["espece"]: r["zones"] for r in france["rencontres"]}
	assert g.ZONE in zones[g.GEANT]
	assert "zone:tres_dangereuse" in zones[g.GEANT]          # l'existant est conservé
	assert zones[g.GEANT_DU_MONT] == [g.ZONE]


def test_idempotent(base, france):
	assert g.appliquer_france(france) == france


def test_equipement_dans_la_liste_du_geant_du_mont(geant_du_mont):
	assert "humanoide" in geant_du_mont["tags"]           # sans quoi il ne porte rien
	for item in g.EQUIPEMENT:
		assert geant_du_mont["items"].count(item["_id"]) == 1


def test_equipement_portable_par_un_monstre():
	# Règle de `combat.items_equipables_monstre` + premier emplacement du simulateur.
	for item in g.EQUIPEMENT:
		assert item["categorie"] in ("arme", "armure"), item["_id"]
		assert set(item["slots"]) <= set(simulateur.SLOTS_EQUIPABLES), item["_id"]


def test_equipement_non_fabricable(base):
	ids = {item["_id"] for item in g.EQUIPEMENT}
	produits = {marche.objet_final_item_id(r.get("objet_final", ""))
				for r in base.values() if r.get("type") == "recette"}
	assert not ids & produits
	assert ids <= set(gen_recettes_orphelins.EXCLUS)
	for item in g.EQUIPEMENT:
		assert not marche.est_personnalisable(item), item["_id"]


def test_equipement_sans_collision(base):
	docs = g.equipement(base)
	for doc in docs:
		assert doc["_id"] not in base or base[doc["_id"]]["nom"] == doc["nom"]


def test_equipement_hors_de_portee_d_un_anthrope(base):
	"""Force requise au-delà du plafond de toute Lignée (bonus racial compris), et au plus la
	Force minimale du géant du Mont, qui doit pouvoir les porter (le monstre ignore la
	restriction, mais la cohérence du monde le veut)."""
	races = base["rules:races"]["value"]
	plafond = max(r["stats_max"]["F"] + (r.get("max_bonus") or {}).get("F", 0) for r in races)
	force_geant = g.fourchette_seigneur(base[g.GEANT], base[g.SEIGNEUR])["F"]["min"]
	for item in g.EQUIPEMENT:
		assert plafond < item["restriction"]["F"] <= force_geant, item["_id"]


def test_equipement_sans_malus():
	# Un malus pèserait AUSSI sur le géant (même `recompute_equipment_bonus`).
	for item in g.EQUIPEMENT:
		assert all(v >= 0 for v in (item.get("bonus") or {}).values()), item["_id"]
		assert item.get("bonus_malus_depl", 0) >= 0, item["_id"]
