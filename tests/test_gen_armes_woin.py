"""dev/gen_armes_woin.py — la table de PIECES couvre EXACTEMENT la liste de travail.

Pur : aucun dump. Le contrôle contre la base (collisions, fausses feuilles) est fait par le
script lui-même à chaque lancement ; ici on verrouille la forme de la table, qui ne dépend
pas du contenu de la base.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_armes_woin as g


def _liste():
	with open(g.LISTE, encoding="utf-8-sig") as fh:
		return [a["nom"] for a in json.load(fh)["armes"]]


def test_la_table_couvre_exactement_la_liste_de_travail():
	listees = {g._norm(n) for n in _liste()}
	produites = {g._norm(it["nom"]) for (it, _l, _m) in g.PIECES}
	ecartees = {g._norm(n) for n in g.ALIAS}
	assert produites | ecartees == listees
	assert not (produites & ecartees)   # un nom écarté n'est pas aussi produit


def test_ids_uniques_et_objet_final_synchrone():
	ids = [it["_id"] for (it, _l, _m) in g.PIECES]
	assert len(ids) == len(set(ids))
	for (it, _l, _m) in g.PIECES:
		assert it["_id"].startswith("item:") and it["categorie"] == "arme"


def test_forme_des_armes():
	for (it, lieu, matieres) in g.PIECES:
		assert lieu == "armurerie" and matieres
		assert it["slots"] in (g.UNE, g.AMB)
		assert it["portee"] >= 1 and it["bonus_degats_dice"] >= 2
		# une arme `hast` a une hampe, et une hampe donne la portée ≥ 2 (cf. telluris-economie) ;
		# l'inverse est faux : le Jō est un bâton (`cac`, comme Baton_de_combat), pas une arme d'hast
		hampe = any(c == "hampe" for (c, _q) in matieres)
		assert "hast" not in it["tags"] or hampe, it["_id"]
		assert not hampe or it["portee"] >= 2, it["_id"]
		# jamais une fausse feuille connue : produites ailleurs que dans l'atelier
		assert not {c for (c, _q) in matieres} & {"cuir", "tendons"}, it["_id"]
