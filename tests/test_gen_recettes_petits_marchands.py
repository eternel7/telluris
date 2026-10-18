"""Recettes des petits marchands (dev/gen_recettes_petits_marchands.py) — forme du lot, sans base.

Les garde-fous économiques (fausse feuille par cité, portée, grande maison croisée) sont
ceux de dev/gen_bourrellerie.py et tournent sur le dump au lancement ; ici, les décisions de
contenu et la forme des docs, quel que soit le dump.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_bourrellerie as base
from dev import gen_brosserie
from dev import gen_fabrication_matieres as fab
from dev import gen_recettes_petits_marchands as gen
from utils import pieges


def _table():
	return gen.table_items()


def _lot():
	table = _table()
	return {d["_id"]: d for d in (base.item_doc(s, table) for s in table)}


def test_items_bien_formes_et_ids_uniques():
	assert base.controler_items(list(_lot().values())) == []
	ids = [base.recette_doc(s, gen.RECETTES)["_id"] for s in gen.RECETTES]
	assert len(ids) == len(set(ids))
	assert not set(gen.ITEMS) & (set(base.ITEMS) | set(gen_brosserie.ITEMS))


def test_tout_item_neuf_est_produit_sauf_les_matieres_brutes():
	produits = set(gen.RECETTES)
	assert set(gen.ITEMS) - produits == set(gen.BRUTES)
	for slug in gen.BRUTES:
		assert _lot()["item:" + slug]["sous_categorie"] == slug
		assert _lot()["item:" + slug]["valeur"]


def test_les_caves_de_chartres_restent_dans_leur_portee():
	for slug, (cat, _m, _q, *portee) in gen.RECETTES.items():
		doc = base.recette_doc(slug, gen.RECETTES)
		if cat == "cave":
			assert portee == [gen.CHARTRES] and doc["lieu_portee"] == gen.CHARTRES
		elif not portee:
			assert "lieu_portee" not in doc


def test_les_outils_de_crochetage_portent_un_bonus_croissant():
	lot = _lot()
	bonus = {i: d.get(pieges.CLE_BONUS_OUTIL) for i, d in lot.items() if d.get(pieges.CLE_BONUS_OUTIL)}
	bonus |= {i: m[pieges.CLE_BONUS_OUTIL] for i, m in gen.MODIFS.items() if pieges.CLE_BONUS_OUTIL in m}
	assert bonus["item:Trousse_de_crochetage_fine"] == max(bonus.values())
	assert set(bonus) >= {"item:Crochets_d_os", "item:Passe_partout", "item:Crochets", "item:Crochet_serrurier"}


def test_les_matieres_de_sur_mesure_suivent_la_table_de_fabrication():
	"""Bloc et tags posés à la création = ce que dev/gen_fabrication_matieres.py écrirait :
	relancé après l'import, il ne rend aucun diff pour elles."""
	lot = _lot()
	fab_du_lot = {i for i in fab.MATIERES if i in lot}
	assert fab_du_lot >= {"item:Cuir_fume", "item:Cuir_tanne_au_chene", "item:Peau_chamoisee",
						  "item:Croupon_epais", "item:Griffe_montee", "item:Oeil_de_bete_conserve"}
	for i in fab_du_lot:
		assert fab.a_ecrire_depuis(fab.MATIERES[i], lot[i]) is None, i
	assert fab.erreurs_de_budget({i: fab.MATIERES[i] for i in fab_du_lot}) == []
	assert fab.effets_mal_diriges({i: fab.MATIERES[i] for i in fab_du_lot}) == []


def test_l_aiguille_et_les_demi_produits_ont_un_debouche():
	consommateurs = {}
	for cat, matieres, *_r in gen.RECETTES.values():
		for cle, _n in matieres:
			consommateurs.setdefault(cle, set()).add(cat)
	assert "atelier_d_artisan" in consommateurs["item:aiguille"]
	assert consommateurs["item:Aiguille_d_os"] == {"tannerie", "taxidermie"}
	assert consommateurs["item:Colle_d_os"] == {"lutherie", "atelier_de_l_empenneur", "tabletterie"}
	for demi in ("item:Cuir_fume", "item:Cuir_tanne_au_chene", "item:Peau_chamoisee", "item:Croupon_epais"):
		assert consommateurs[demi] - {"fumoir", "tannerie"}, demi
