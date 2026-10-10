# tests/test_gen_specialites_chartres_rhemi.py — le lot de terroir Chartres / Rhemi et le métier
# « cave ». Tests PURS sur les tables : `main()` n'est pas exécuté ici, `brancher_moteur`
# rebranche `db.config` pour tout le process (ses garde-fous sur dump tournent à la génération).

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import gen_specialites_chartres_rhemi as gen  # noqa: E402
from utils import enseignes, lint_dialogues  # noqa: E402

LOT = gen.construire_lot()
PAR_ID = {d["_id"]: d for d in LOT}
RECETTES = [d for d in LOT if d["type"] == "recette"]


def test_aucun_id_en_double_dans_le_lot():
	assert [i for i, n in Counter(d["_id"] for d in LOT).items() if n > 1] == []


def test_chaque_produit_a_son_item_et_sa_recette_portee():
	for slug in gen.PRODUITS:
		assert "item:" + slug in PAR_ID
		r = PAR_ID["recette:specialite_%s" % slug.lower()]
		assert r["objet_final"] == slug
		assert r["lieu_portee"] in (gen.CHARTRES, gen.RHEMI, gen.PAYS)


def test_les_specialites_vont_a_leur_cite():
	portees = {slug: spec[8] for slug, spec in gen.PRODUITS.items()}
	for slug in ("Pate_de_Chartres", "Mentchikoff", "Sable_de_Beauce",
				 "Hydromel_de_Beauce", "Eure_et_Liqueur"):
		assert portees[slug] == gen.CHARTRES
	for slug in ("Biscuit_rose_de_Reims", "Jambon_de_Reims",
				 "Pieds_de_cochon_a_la_Sainte_Menehould", "Champagne",
				 "Ratafia_de_Champagne", "Vinaigre_de_Reims", "Moutarde_de_Reims"):
		assert portees[slug] == gen.RHEMI


def test_noms_de_l_utilisateur_a_la_lettre():
	assert PAR_ID["item:Eure_et_Liqueur"]["nom"] == "Eure-et-Liqueur"
	assert PAR_ID["item:Pate_de_Chartres"]["nom"] == "Pâté de Chartres"


def test_matieres_existantes_reutilisees_et_neuves_generiques():
	# Le miel est celui de la base : le lot ne le recrée pas, il le consomme.
	assert "item:Miel" not in PAR_ID
	intrants = {cle for r in RECETTES for m in r["matieres_premieres"] for cle in [m["item"]]}
	assert "item:Miel" in intrants
	assert "item:Raisin" in PAR_ID
	assert not any("Beauce" in d["_id"] or "Champagne" in d["_id"]
				   for d in LOT if d.get("categorie") == "composant" and d["_id"].startswith("item:")
				   and d["_id"][5:] not in gen.PRODUITS)


def test_un_intermediaire_vient_du_meme_metier_sous_une_portee_qui_le_couvre():
	# Garde-fou de fausse feuille, rejoué sur les tables : Eau-de-vie (toutes caves),
	# Champagne → Vinaigre → Moutarde (caves de Rhemi).
	for slug, spec in gen.PRODUITS.items():
		for cle, _q in spec[9]:
			amont = gen.PRODUITS.get(cle[len("item:"):])
			if amont is None:
				continue
			assert amont[7] == spec[7], (slug, cle)
			assert amont[8] in (spec[8], gen.PAYS), (slug, cle)


def test_les_intermediaires_ont_une_valeur_qui_coupe_la_propagation():
	for slug in gen.VALEURS:
		assert PAR_ID["item:" + slug]["valeur"][0]["cu"] < PAR_ID["item:" + slug]["valeur"][1]["cu"]


def test_matieres_sont_des_composants_valorises():
	for (slug, *_r) in gen.MATIERES:
		doc = PAR_ID["item:" + slug]
		assert doc["categorie"] == "composant" and doc["valeur"]


def test_tenancier_de_la_cave_lint_propre():
	doc = PAR_ID["pnj:marchand_cave"]
	assert doc["services"]["direction"]["noeuds"]
	assert lint_dialogues.analyser_doc(doc) == []


def test_la_cave_a_ses_enseignes():
	assert len(enseignes.tirer_labels("cave", 3, "lieu:chartres")) == 3
	assert enseignes.TOURNURES["cave"]
