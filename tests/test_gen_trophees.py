"""Contenu des recettes à trophée (dev/gen_trophees.py) — forme du lot, sans base.

Les garde-fous qui demandent le monde (budget du palier, feuilles inchangées, catalogue de
chaque grande maison, prix) tournent sur le dump au lancement du générateur ; ici, ce qui
doit tenir quel que soit le dump.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_trophees as gen  # noqa: E402
from utils import marche  # noqa: E402


def test_chaque_recette_porte_un_seul_trophee_en_tete():
	for slug in gen.PIECES:
		r = gen.recette_doc(slug)
		assert marche.cles_trophee(r) == {gen.PIECES[slug]["trophee"]}, slug
		assert r["matieres_premieres"][0] == {"item": gen.PIECES[slug]["trophee"],
											  "quantite": 1, "trophee": True}
		assert r["objet_final"] == slug and r["lieu_categorie"] == gen.PIECES[slug]["categorie"]


def test_ids_uniques():
	ids = [gen.recette_doc(s)["_id"] for s in gen.PIECES]
	assert len(ids) == len(set(ids))


def test_palier_suit_la_dangerosite():
	def espece(total):
		# Un seul attribut, milieu = total.
		return {"base_attributes": {"F": {"min": total, "max": total}}}
	bornes = [s for s, _p in gen.SEUILS_PALIER]
	assert [gen.palier_espece(espece(b)) for b in bornes] == [p for _s, p in gen.SEUILS_PALIER]
	assert gen.palier_espece(espece(bornes[-1] + 1)) == gen.PALIER_MAX


def test_apport_compose_sur_le_socle():
	socle = {"_id": "item:socle", "nom": "Socle", "rarete": "commun", "poids": 1, "valeur": 9,
			 "categorie": "arme", "slots": ["main_droite"], "bonus_degats": 2,
			 "bonus": {"F": 1}, "restriction": {"F": 20},
			 "effets": {"buffs": {"Vol": -4}, "duree": 2}}
	jeu = gen.appliquer_apport(socle, {"bonus_degats": 3, "bonus": {"F": 2, "Ag": 1},
									   "restriction": {"F": 15, "Vol": 10},
									   "effets": {"buffs": {"Vol": -2, "R": -1}, "duree": 3}})
	assert jeu["bonus_degats"] == 5 and jeu["bonus"] == {"F": 3, "Ag": 1}
	assert jeu["restriction"] == {"F": 20, "Vol": 10}           # maximum, jamais abaissée
	assert jeu["effets"] == {"buffs": {"Vol": -6, "R": -1}, "duree": 3}
	# Identité et prix du socle ne passent pas à la pièce.
	assert not {"_id", "nom", "rarete", "poids", "valeur"} & set(jeu)
	assert socle["bonus"] == {"F": 1}                            # socle non muté


def test_la_piece_prend_la_rarete_la_plus_haute():
	socle = {"rarete": "rare", "categorie": "armure", "slots": ["main_gauche"]}
	slug = next(iter(gen.PIECES))
	assert gen.item_doc(slug, socle, "peu_commun")["rarete"] == "rare"
	assert gen.item_doc(slug, dict(socle, rarete="commun"), "peu_commun")["rarete"] == "peu_commun"
