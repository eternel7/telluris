"""Matières de VITESSE : les seules sources de V +2 et V +3 d'une pièce sur mesure (Auteur, 11/11).

La V d'équipement ne se cumule plus — entre objets portés (`characters._appliquer_vitesse_max`)
comme entre matières d'une variante (`fabrication.appliquer_modificateurs`) : seul le plus fort
bonus compte. Ce lot donne les paliers au-dessus du +1 des matières communes (sang, cœur, fiole
de sang de bête, os de totem) :

  · V +2 — aile d'Aigle géant, aile de Grand faucon, crin (queue) de Coursier elfique, aile
    d'Hippogriffe, patte de Cŵn Annwn, patte de Bête glatissante, patte du Twrch Trwyth ;
  · V +3 — aile de Pégase, aile de Monture angélique, crin (queue) de Licorne, aile de Grand
    Phénix ;
  · un seul +2 sans chasse : l'**Élixir du coureur** (doc neuf), concentré de Tisane du marcheur
    cuit par l'apothicairerie (4 tisanes → 1 élixir).

Les blocs `fabrication`, tags et rareté des parties vivent dans la table de
dev/gen_fabrication_matieres.py (la table est la vérité : une relance de ce générateur-là ne rend
aucun diff). Ce script ne fait que les poser — ET créer l'élixir et sa recette — dans UN seul
fichier, avec les garde-fous de dev/gen_bourrellerie.py (`main` paramétré : `_id` pris, intrant
sans doc, FAUSSE FEUILLE, grande maison non croisée). Seul intrant : la Tisane, produite sur
place — ⚠️ pas d'herbes médicinales, feuille à débit NUL (dump 11/11) : fausse feuille.

    python dev/gen_vitesse_matieres.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/vitesse_matieres_a_importer.json   (carte d'import de /admin)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_bourrellerie as base  # noqa: E402

SORTIE = os.path.join(base.RACINE, "jsons", "vitesse_matieres_a_importer.json")

# Parties de créatures complétées (docs déjà en base) : leur entrée vient de la table.
PARTIES = (
	"item:aigle_geant_aile", "item:grand_faucon_aile", "item:coursier_elfique_queue",
	"item:hippogriffe_aile", "item:cwn_annwn_patte", "item:bete_glatissante_patte",
	"item:twrch_trwyth_patte", "item:pegase_aile", "item:monture_angelique_aile",
	"item:licorne_queue", "item:grand_phenix_aile",
)
ELIXIR = "Elixir_du_coureur"

RECETTES = {
	ELIXIR: ("apothicairerie", [("item:Tisane_du_marcheur", 4)], 1),
}


def _table():
	# Import DIFFÉRÉ : la table tire `utils.*`, qui fige `get_doc` à l'import (cf. gen_bourrellerie).
	import gen_fabrication_matieres as gfm
	return gfm


def items():
	gfm = _table()
	entree = gfm.MATIERES["item:" + ELIXIR]
	return {ELIXIR: {
		"nom": "Élixir du coureur", "icon": "🧪", "rarete": "peu_commun", "categorie": "composant",
		"slots": [], "poids": 0.2, "tags": sorted(entree["tags"]),
		"description": "Quatre tisanes du marcheur réduites à feu doux jusqu'à n'en garder que "
					   "l'amertume. Les cordonniers en imprègnent le cuir des bottes, qui ne "
					   "pèsent plus au pied.",
		"fabrication": gfm.bloc_fabrication(entree),
	}}


def modifs(index: dict) -> dict:
	"""`{_id: champs changés}` des parties, calculés par `a_ecrire_depuis` contre le dump lu."""
	gfm = _table()
	sortie = {}
	for item_id in PARTIES:
		existant = index.get(item_id)
		if existant is None:
			sortie[item_id] = {}        # signalé « absent du dump » par `main`
			continue
		apres = gfm.a_ecrire_depuis(gfm.MATIERES[item_id], existant)
		if apres is not None:
			sortie[item_id] = {k: v for k, v in apres.items() if existant.get(k) != v}
	return sortie


def controler_table() -> list:
	"""Budget et direction des effets des entrées de ce lot (garde-fous de la table)."""
	gfm = _table()
	lot = {k: gfm.MATIERES[k] for k in PARTIES + ("item:" + ELIXIR,)}
	return gfm.erreurs_de_budget(lot) + gfm.effets_mal_diriges(lot)


if __name__ == "__main__":
	def _items():
		erreurs = controler_table()
		if erreurs:
			print("%d ERREUR(S) de table — rien n'est écrit :" % len(erreurs))
			for e in erreurs:
				print("  ✗ " + e)
			sys.exit(1)
		return items()
	base.main(_items, RECETTES, SORTIE, modifs)
