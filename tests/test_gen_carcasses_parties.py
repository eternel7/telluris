"""dev/gen_carcasses_parties.py — portions anatomiques, puis MORCEAUX, jamais une anatomie de portion.

Verrouille ce qu'une relance sur un dump contenant déjà les portions a produit : la « tête d'un
corps » (`item:aigle_geant_corps_tete`). Un import PUT complet l'aurait écrite en silence.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_carcasses_parties as gen
from models import character_stats
from utils import carcasse

# `depecage` sur l'espèce : l'override de `depecage_carcasse`, indépendant de DEPECAGE_TAGS.
MAMMOUTH_ESPECE = {
	"_id": "espece:mammouth", "type": "espece", "nom": "Mammouth", "tags": ["animal"],
	"depecage": [["viande", 3], ["os", 2], ["crane", 1], ["cuir_brut", 2], ["tendons", 1],
				 ["poils", 1]],
}
MAMMOUTH = {"_id": "item:mammouth", "type": "item", "nom": "Carcasse de Mammouth",
			"sous_categorie": "carcasse", "categorie": "composant", "rarete": "rare",
			"poids": [5000, 12000], "source_espece": "espece:mammouth"}
LOUP_ESPECE = {"_id": "espece:loup", "type": "espece", "nom": "Loup", "tags": ["animal"],
			   "depecage": [["viande", 1], ["os", 1]]}
LOUP = {"_id": "item:loup", "type": "item", "sous_categorie": "carcasse", "poids": [20, 40],
		"source_espece": "espece:loup"}
DUMP = [MAMMOUTH_ESPECE, MAMMOUTH, LOUP_ESPECE, LOUP]


def _par_id(docs):
	return {d["_id"]: d for d in docs}


def test_seules_les_carcasses_lourdes_non_generees_sont_sources():
	sortie, resume, _ign, _orph, _inch = gen.generer(DUMP)
	assert [r[0] for r in resume] == ["item:mammouth"]           # le loup est sous le seuil
	assert not gen.est_source(dict(MAMMOUTH, portion_de="item:x"))


def test_relance_sur_un_dump_deja_genere_ne_debite_jamais_une_portion_en_anatomie():
	premiere = gen.generer(DUMP)[0]
	fusion = _par_id(DUMP)
	fusion.update(_par_id(premiere))
	seconde, resume, _i, orphelins, inchanges = gen.generer(list(fusion.values()))
	assert seconde == []                                          # base à jour : lot vide
	assert sorted(inchanges) == sorted(d["_id"] for d in premiere)
	assert resume == gen.generer(DUMP)[1]                         # même découpe complète
	assert orphelins == []
	anatomie = [p for (p, _q, _f) in gen.PROFILS["quadrupede"]]
	for d in premiere:
		reste = d["_id"][len("item:mammouth_"):] if d["_id"].startswith("item:mammouth_") else ""
		# Jamais deux parties d'anatomie à la suite : `corps_tete`, `patte_corps`…
		assert not any(reste.startswith(a + "_") and reste[len(a) + 1:] in anatomie
					   for a in anatomie), d["_id"]


def test_portion_trop_lourde_debitee_en_morceaux_sous_le_seuil():
	seuil = float(character_stats.CARCASSE_DECOUPE_POIDS_MIN)
	docs = _par_id(gen.generer(DUMP)[0])
	portions = [d for d in docs.values() if d.get("portion_de") == "item:mammouth"]
	assert portions
	for p in portions:
		pmax = gen.poids_bornes(p["poids"])[1]
		if pmax <= seuil:
			assert "decoupe" not in p
			continue
		[entree] = p["decoupe"]
		assert entree["fraction"] == 1.0 and p["decoupe_poids_min"] == seuil
		morceau = docs[entree["item"]]
		assert entree["item"] == p["_id"] + gen.SUFFIXE_MORCEAU
		assert morceau["portion_de"] == p["_id"]
		assert "decoupe" not in morceau                            # terminal
		assert morceau["depecage"] == p["depecage"]
		assert gen.poids_bornes(morceau["poids"])[1] < seuil
		# En jeu : la portion à poids max rend n pièces < seuil, masse conservée.
		pieces = carcasse.decouper_ref({"item": p["_id"], "poids": pmax}, p)
		assert len(pieces) == entree["quantite"]
		assert all(x["poids"] < seuil for x in pieces)
		assert round(sum(x["poids"] for x in pieces), 2) == round(pmax, 2)


def test_fractions_de_la_carcasse_somment_a_un():
	docs = _par_id(gen.generer(DUMP)[0])
	assert round(sum(e["fraction"] for e in docs["item:mammouth"]["decoupe"]), 4) == 1.0


def test_nb_morceaux_strictement_sous_le_seuil():
	seuil = float(character_stats.CARCASSE_DECOUPE_POIDS_MIN)
	for pmax in (seuil + 0.01, seuil * 2, seuil * 2 - 0.004, seuil * 62.4):
		n = gen.nb_morceaux(pmax)
		assert round(pmax / n, 2) < seuil
		assert n == 1 or round(pmax / (n - 1), 2) >= seuil        # le plus petit n possible


def test_seul_le_diff_part_a_l_import_et_les_cles_manuelles_survivent():
	premiere = gen.generer(DUMP)[0]
	base = _par_id(DUMP)
	base.update({d["_id"]: dict(d, _rev="1-x") for d in premiere})
	# Une retouche manuelle hors champ généré, et un champ généré devenu faux en base.
	base["item:mammouth_tete"] = dict(base["item:mammouth_tete"], note_admin="garder")
	base["item:mammouth_corps"] = dict(base["item:mammouth_corps"], poids=1)
	sortie, _r, _i, _o, inchanges = gen.generer(list(base.values()))
	assert [d["_id"] for d in sortie] == ["item:mammouth_corps"]  # seul le doc faux repart
	corps = sortie[0]
	assert corps["poids"] != 1 and corps["_rev"] == "1-x"
	assert "item:mammouth_tete" in inchanges                      # clé en plus ≠ changement
	# Un doc repris ne perd pas une clé ajoutée à la main.
	base["item:mammouth_tete"]["poids"] = 1
	tete = next(d for d in gen.generer(list(base.values()))[0] if d["_id"] == "item:mammouth_tete")
	assert tete["note_admin"] == "garder"


def test_ancienne_sous_portion_signalee_comme_orpheline():
	sortie = gen.generer(DUMP)[0]
	vieux = {"_id": "item:mammouth_corps_tete", "type": "item", "sous_categorie": "carcasse",
			 "portion_de": "item:mammouth_corps", "poids": 50}
	orphelins = gen.generer(DUMP + sortie + [vieux])[3]
	assert orphelins == ["item:mammouth_corps_tete"]
