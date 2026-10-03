"""Tests du graphe des recettes (`utils/graphe_recettes.py`, écran /admin/recettes-graphe).

Le module ne recopie aucune règle : ces tests vérifient qu'il suit bien celles de
`utils/marche.py` (entrées par item ou par sous-catégorie, champ legacy mono-entrée,
override `_OBJET_FINAL_ITEM_ID`, `sur_commande`) et de `characters.item_sous_categorie`.
La logique d'écran (voisinage, filtres, recherche) est verrouillée par
dev/test_graphe_recettes_client.js.
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import graphe_recettes as gr  # noqa: E402
from utils import commande, fabrication, marche  # noqa: E402


def _item(iid, **kw):
	return {"_id": iid, "type": "item", "nom": kw.pop("nom", iid.split(":", 1)[1]), **kw}


def _index(g):
	return {n["id"]: n for n in g["nodes"]}, g["edges"]


def test_entree_par_item_et_par_sous_categorie():
	recettes = [{
		"_id": "recette:ceinture", "type": "recette", "lieu_categorie": "tannerie",
		"objet_final": "ceinture", "quantite_produite": 2,
		"matieres_premieres": [{"sous_categorie": "cuir", "quantite": 3}, {"item": "item:boucle", "quantite": 1}],
	}]
	items = [_item("item:ceinture"), _item("item:boucle"),
			 _item("item:peau_loup", sous_categorie="cuir"), _item("item:peau_ours", sous_categorie="cuir")]
	noeuds, aretes = _index(gr.construire_graphe(recettes, items))
	rec = sorted((e["source"], e["target"], e["quantite"]) for e in aretes if e["kind"] == "recette")
	assert rec == [("item:boucle", "item:ceinture", 1), ("sc:cuir", "item:ceinture", 3)]
	assert all(e["quantite_produite"] == 2 and e["lieu_categorie"] == "tannerie"
			   for e in aretes if e["kind"] == "recette")
	membres = sorted(e["source"] for e in aretes if e["kind"] == "membre")
	assert membres == ["item:peau_loup", "item:peau_ours"]
	assert noeuds["sc:cuir"]["type"] == "famille" and not noeuds["sc:cuir"]["absent"]


def test_appartenance_suit_item_sous_categorie_du_moteur():
	# Sans sous_categorie, le moteur se replie sur la catégorie : la famille aussi.
	recettes = [{"_id": "recette:x", "type": "recette", "lieu_categorie": "l", "objet_final": "x",
				 "matiere_premiere_sous_categorie": "matiere", "quantite_matiere": 2}]
	items = [_item("item:x"), _item("item:sans_sc", categorie="matiere", sous_categorie="")]
	_, aretes = _index(gr.construire_graphe(recettes, items))
	assert ("item:sans_sc", "sc:matiere") in [(e["source"], e["target"]) for e in aretes if e["kind"] == "membre"]
	# …et le champ legacy mono-entrée est lu par `recette_matieres`.
	assert [(e["source"], e["quantite"]) for e in aretes if e["kind"] == "recette"] == [("sc:matiere", 2)]


def test_produit_resolu_par_objet_final_item_id():
	slug, attendu = next(iter(marche._OBJET_FINAL_ITEM_ID.items()))
	recettes = [{"_id": "recette:o", "type": "recette", "lieu_categorie": "l", "objet_final": slug,
				 "matieres_premieres": [{"item": "item:a", "quantite": 1}]}]
	noeuds, aretes = _index(gr.construire_graphe(recettes, [_item("item:a"), _item(attendu)]))
	assert aretes[0]["target"] == attendu
	assert not noeuds[attendu]["absent"]
	assert "item:" + slug not in noeuds   # pas de doublon « absent » sous l'id naïf


def test_absents_items_et_familles():
	recettes = [{"_id": "recette:f", "type": "recette", "lieu_categorie": "l", "objet_final": "fantome",
				 "matieres_premieres": [{"item": "item:disparu", "quantite": 1},
										{"sous_categorie": "introuvable", "quantite": 1}]}]
	noeuds, _ = _index(gr.construire_graphe(recettes, []))
	assert noeuds["item:fantome"]["absent"] and noeuds["item:disparu"]["absent"]
	assert noeuds["sc:introuvable"]["absent"]
	assert noeuds["item:fantome"]["label"] == "fantome"


def test_sur_commande_portee_et_items_isoles():
	recettes = [
		{"_id": "recette:v", "type": "recette", "lieu_categorie": "forge", "objet_final": "var",
		 "sur_commande": True, "matieres_premieres": [{"item": "item:a"}]},
		{"_id": "recette:t", "type": "recette", "lieu_categorie": "auberge", "objet_final": "tis",
		 "lieu_portee": "lieu:val", "matieres_premieres": [{"item": "item:a"}]},
		{"_id": "recette:vide", "type": "recette", "lieu_categorie": "x"},   # sans objet_final : ignorée
	]
	items = [_item("item:a"), _item("item:var"), _item("item:tis"), _item("item:galet")]
	noeuds, aretes = _index(gr.construire_graphe(recettes, items))
	par_rec = {e["recette"]: e for e in aretes}
	assert par_rec["recette:v"]["sur_commande"] is True and par_rec["recette:t"]["sur_commande"] is False
	assert par_rec["recette:t"]["lieu_portee"] == "lieu:val"
	assert "recette:vide" not in par_rec
	assert "item:galet" in noeuds       # isolé mais présent : le filtre « isolés » en a besoin


def test_noeuds_uniques_et_aretes_identifiees():
	recettes = [{"_id": f"recette:{i}", "type": "recette", "lieu_categorie": "l", "objet_final": "b",
				 "matieres_premieres": [{"item": "item:a"}, {"item": "item:a", "quantite": 2}]} for i in range(3)]
	g = gr.construire_graphe(recettes, [_item("item:a"), _item("item:b")])
	assert [n["id"] for n in g["nodes"]] == ["item:a", "item:b"]
	assert len({e["id"] for e in g["edges"]}) == len(g["edges"]) == 6


_FAB = {"nom": "serti", "modificateurs": {"bonus_cc": 1}}


def test_fabrication_matiere_vers_famille_de_pieces():
	items = [
		_item("item:gemme", categorie="matiere", fabrication=_FAB, tags=["fabrication_arme", "fabrication_bague", "autre"]),
		_item("item:epee", categorie="arme"),
		# La famille se lit sur la catégorie OU la sous-catégorie (commande.tags_fabrication).
		_item("item:anneau", categorie="bijou", sous_categorie="bague"),
	]
	noeuds, aretes = _index(gr.construire_graphe([], items))
	fab = sorted((e["source"], e["target"]) for e in aretes if e["kind"] == "fabrication")
	assert fab == [("item:gemme", "fab:arme"), ("item:gemme", "fab:bague")]
	assert noeuds["fab:arme"]["type"] == "piece" and noeuds["fab:arme"]["pieces"] == ["item:epee"]
	assert noeuds["fab:bague"]["pieces"] == ["item:anneau"]
	assert not noeuds["fab:arme"]["absent"]
	assert noeuds["item:gemme"]["matiere_fabrication"] and noeuds["item:gemme"]["fabrication_nom"] == "serti"
	assert not noeuds["item:epee"]["matiere_fabrication"]


def test_fabrication_sans_tag_sans_apport_ou_sans_piece():
	items = [
		# Apporte mais aucun tag : seule la porte « métier de la maison » (dépend du lieu) l'ouvre.
		_item("item:cire", fabrication=_FAB, tags=[]),
		# Tag mais bloc vide : `fabrication.apporte` la refuse, aucun lien.
		_item("item:caillou", fabrication={}, tags=["fabrication_arme"]),
		# Famille ouverte sans aucune pièce : nœud signalé absent.
		_item("item:plume", fabrication=_FAB, tags=["fabrication_arc"]),
	]
	noeuds, aretes = _index(gr.construire_graphe([], items))
	assert [(e["source"], e["target"]) for e in aretes if e["kind"] == "fabrication"] == [("item:plume", "fab:arc")]
	assert noeuds["item:cire"]["matiere_fabrication"] and not noeuds["item:caillou"]["matiere_fabrication"]
	assert "fab:arme" not in noeuds
	assert noeuds["fab:arc"]["absent"] and noeuds["fab:arc"]["pieces"] == []


def test_template_compile_sous_jinja():
	# `${{ … }}` d'un template literal JS est lu par Jinja comme une expression : la page
	# entière tombe en 500, et `dev/check_js.js` (syntaxe JS seule) ne le voit pas.
	import jinja2
	chemin = os.path.join(os.path.dirname(__file__), "..", "templates", "admin_recettes_graphe.html")
	with open(chemin, encoding="utf-8") as fh:
		jinja2.Environment().parse(fh.read())


def _dernier_dump():
	dumps = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "jsons", "telluris-dump-*.json")))
	if not dumps:
		return None
	with open(dumps[-1], encoding="utf-8") as fh:
		return json.load(fh)["docs"]


def test_graphe_du_dump_coherent():
	docs = _dernier_dump()
	if docs is None:
		return
	recettes = [d for d in docs if d.get("type") == "recette"]
	items = [d for d in docs if d.get("type") == "item"]
	g = gr.construire_graphe(recettes, items)
	ids = {n["id"] for n in g["nodes"]}
	assert len(ids) == len(g["nodes"])
	assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
	assert {d["_id"] for d in items} <= ids
	# Une arête par entrée de recette (comptes RELUS du dump, rien en dur).
	attendu = sum(len(marche.recette_matieres(r)) for r in recettes if r.get("objet_final"))
	assert sum(1 for e in g["edges"] if e["kind"] == "recette") == attendu
	# Une arête de fabrication par tag `fabrication_*` d'une matière qui apporte (RELU).
	prefixe = commande.TAG_FABRICATION_PREFIXE
	attendu_fab = sum(len({t for t in (d.get("tags") or []) if str(t).startswith(prefixe)})
					  for d in items if fabrication.apporte(d))
	assert sum(1 for e in g["edges"] if e["kind"] == "fabrication") == attendu_fab
