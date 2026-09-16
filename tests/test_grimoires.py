"""utils/grimoires.py — grimoire UNIQUE + recette de scriptorium par sort non couvert.

Verrouille la règle de couverture (un grimoire multiple ne couvre pas), l'idempotence (rien de
réémis qui soit déjà en base) et le refus d'un `_id` pris par autre chose (import = PUT complet).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import grimoires as g

MATIERES = [{"item": "item:parchemin", "quantite": 2}, {"item": "item:encre", "quantite": 1}]


def _sort(slug, niveau=0, magie="Élémentaire"):
	return {"_id": "sort:" + slug, "type": "sort", "nom": slug.capitalize(), "niveau": niveau,
			"magie": magie, "vocation": "mage"}


def _grimoire(gid, sorts):
	return {"_id": gid, "type": "item", "sous_categorie": "grimoire", "sorts": sorts}


def _recette(rid, objet, matieres=MATIERES):
	return {"_id": rid, "type": "recette", "lieu_categorie": "scriptorium",
			"objet_final": objet, "matieres_premieres": matieres}


def _base(*docs):
	modele = _recette("recette:grimoire_modele", "grimoire_modele")
	return {d["_id"]: d for d in (modele,) + docs}


def _ids(docs):
	return [d["_id"] for d in docs]


def test_sort_sans_grimoire_produit_grimoire_et_recette():
	docs, lignes, erreurs = g.grimoires_manquants(_base(_sort("feu", 4)))
	assert erreurs == [] and len(lignes) == 1
	assert _ids(docs) == ["item:grimoire_feu", "recette:grimoire_feu"]
	grim, rec = docs
	assert grim["sorts"] == ["sort:feu"] and grim["sous_categorie"] == "grimoire"
	assert grim["rarete"] == "rare" and grim["valeur"] == [{"ag": 40}, {"ag": 120}]
	assert rec["objet_final"] == "grimoire_feu" and rec["lieu_categorie"] == "scriptorium"
	assert rec["matieres_premieres"] == MATIERES


@pytest.mark.parametrize("niveau, rarete, valeur", [
	(0, "peu_commun", [{"ag": 5}, {"ag": 15}]),
	(3, "peu_commun", [{"ag": 30}, {"ag": 90}]),
	(4, "rare", [{"ag": 40}, {"ag": 120}]),
	(10, "legendaire", [{"ag": 100}, {"ag": 300}]),
])
def test_rarete_et_valeur_par_niveau(niveau, rarete, valeur):
	assert g.rarete_grimoire(niveau) == rarete and g.valeur_grimoire(niveau) == valeur


def test_grimoire_multiple_ne_couvre_pas():
	multiple = _grimoire("item:tome_elements", ["sort:feu", "sort:givre"])
	docs, _, erreurs = g.grimoires_manquants(_base(_sort("feu"), _sort("givre"), multiple))
	assert erreurs == []
	assert _ids(docs) == ["item:grimoire_feu", "recette:grimoire_feu",
						  "item:grimoire_givre", "recette:grimoire_givre"]
	assert "item:tome_elements" not in _ids(docs)


def test_grimoire_unique_et_multiple_couvert():
	base = _base(_sort("feu"), _grimoire("item:grimoire_feu", ["sort:feu"]),
				 _grimoire("item:tome", ["sort:feu", "sort:givre"]), _sort("givre"))
	docs, _, erreurs = g.grimoires_manquants(base)
	assert erreurs == [] and _ids(docs) == ["item:grimoire_givre", "recette:grimoire_givre"]


def test_recette_deja_en_base_non_reemise():
	base = _base(_sort("feu"), _recette("recette:grimoire_feu", "grimoire_feu"))
	docs, lignes, erreurs = g.grimoires_manquants(base)
	assert erreurs == [] and _ids(docs) == ["item:grimoire_feu"]
	assert lignes[0].endswith("recette déjà en base")


def test_collision_grimoire_qui_n_enseigne_pas_le_sort():
	base = _base(_sort("feu"), _grimoire("item:grimoire_feu", ["sort:autre"]))
	_, _, erreurs = g.grimoires_manquants(base)
	assert len(erreurs) == 1 and "n'enseigne pas sort:feu" in erreurs[0]


def test_collision_grimoire_multiple_sous_l_id_unique():
	base = _base(_sort("feu"), _grimoire("item:grimoire_feu", ["sort:feu", "sort:givre"]))
	_, _, erreurs = g.grimoires_manquants(base)
	assert len(erreurs) == 1 and "parmi d'autres sorts" in erreurs[0]


def test_collision_recette_qui_produit_autre_chose():
	base = _base(_sort("feu"), _recette("recette:grimoire_feu", "epee"))
	_, _, erreurs = g.grimoires_manquants(base)
	assert len(erreurs) == 1 and "ne produit pas item:grimoire_feu" in erreurs[0]


def test_matieres_signature_majoritaire_et_absente():
	autre = [{"item": "item:velin", "quantite": 1}]
	base = {
		"recette:grimoire_a": _recette("recette:grimoire_a", "grimoire_a", autre),
		"recette:grimoire_b": _recette("recette:grimoire_b", "grimoire_b"),
		"recette:grimoire_c": _recette("recette:grimoire_c", "grimoire_c"),
		"recette:pain": _recette("recette:pain", "pain", autre),
	}
	assert g.matieres_grimoire(base) == MATIERES
	with pytest.raises(ValueError):
		g.matieres_grimoire({"recette:pain": base["recette:pain"]})
	# Sans modèle : erreur rendue (rien n'est écrit), pas d'exception.
	_, _, erreurs = g.grimoires_manquants({"sort:feu": _sort("feu")})
	assert len(erreurs) == 1
	# Rien à créer : pas besoin de modèle.
	assert g.grimoires_manquants({}) == ([], [], [])


def test_sorts_en_plus():
	docs, _, _ = g.grimoires_manquants(_base(), [_sort("neuf", 2)])
	assert _ids(docs) == ["item:grimoire_neuf", "recette:grimoire_neuf"]


def test_meme_verdict_pour_l_alerte():
	sorts = [_sort("feu"), _sort("givre", 1, "Nature"), _sort("soin", 0, "Sainte")]
	grims = [_grimoire("item:tome", ["sort:feu", "sort:givre"]), _grimoire("item:grimoire_soin", ["sort:soin"])]
	manquants = g.sorts_sans_grimoire_unique(sorts, grims)
	docs, _, _ = g.grimoires_manquants(_base(*sorts, *grims))
	# Tri école → niveau → id (« Nature » < « Élémentaire » en ordre de code).
	assert [s["_id"] for s in manquants] == ["sort:givre", "sort:feu"]
	assert [d["sorts"][0] for d in docs if d["type"] == "item"] == [s["_id"] for s in manquants]
	# Projection find_docs : grimoire sans `type` reste reconnu.
	assert [s["_id"] for s in g.sorts_sans_grimoire_unique(
		sorts, [{"_id": "item:x", "sous_categorie": "grimoire", "sorts": ["sort:soin"]}])] \
		== ["sort:givre", "sort:feu"]


def test_grimoires_sans_recette():
	base = _base(_grimoire("item:grimoire_modele", ["sort:a"]), _grimoire("item:Grimoire_vide", []))
	assert g.grimoires_sans_recette(base) == ["item:Grimoire_vide"]
