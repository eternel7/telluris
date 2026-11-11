"""dev/gen_vitesse_matieres.py — matières de V +2 / +3 et l'Élixir du coureur.

La V d'équipement ne se cumule pas (characters + fabrication) : ces matières sont la seule voie
au-dessus du +1. Verrouille les paliers voulus par l'Auteur (11/11) et le diff posé sur les docs.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_vitesse_matieres as gen  # noqa: E402

gfm = gen._table()


def _v(item_id):
	return gfm.MATIERES[item_id]["modificateurs"]["bonus"]["V"]


def test_vitesse_plus_deux_et_plus_trois_seulement():
	vitesses = {i: _v(i) for i in gen.PARTIES + ("item:" + gen.ELIXIR,)}
	assert set(vitesses.values()) == {2, 3}
	assert {i for i, v in vitesses.items() if v == 3} == {
		"item:pegase_aile", "item:monture_angelique_aile", "item:licorne_queue", "item:grand_phenix_aile"}
	# Aucune autre matière de la table ne dépasse le +1 de V.
	autres = [i for i in gfm.MATIERES if i not in vitesses]
	assert all((gfm.MATIERES[i]["modificateurs"].get("bonus") or {}).get("V", 0) <= 1 for i in autres)


def test_le_lot_respecte_budget_et_direction_des_effets():
	assert gen.controler_table() == []


def test_la_vitesse_entre_dans_une_armure():
	for item_id in gen.PARTIES + ("item:" + gen.ELIXIR,):
		assert gfm.TAG_ARMURE in gfm.MATIERES[item_id]["tags"], item_id


def test_modifs_ne_portent_que_les_champs_changes_et_gardent_le_reste():
	aile = {"_id": "item:pegase_aile", "_rev": "2-a", "type": "item", "nom": "Aile de Pegase",
			"rarete": "peu_commun", "tags": ["vol", "partie_aile"], "note_admin": "à la main"}
	modifs = gen.modifs({"item:pegase_aile": aile})
	assert set(modifs["item:pegase_aile"]) == {"fabrication", "rarete", "tags"}
	assert modifs["item:pegase_aile"]["tags"][:2] == ["vol", "partie_aile"]
	# Une partie absente du dump est remontée (vide) pour que `main` la signale.
	assert modifs["item:aigle_geant_aile"] == {}
	# Déjà à jour : rien.
	a_jour = aile | modifs["item:pegase_aile"]
	assert "item:pegase_aile" not in gen.modifs({"item:pegase_aile": a_jour})


def test_elixir_porte_le_bloc_de_la_table():
	doc = gen.items()[gen.ELIXIR]
	assert doc["fabrication"] == gfm.bloc_fabrication(gfm.MATIERES["item:" + gen.ELIXIR])
	assert gen.RECETTES[gen.ELIXIR][0] == "apothicairerie"
