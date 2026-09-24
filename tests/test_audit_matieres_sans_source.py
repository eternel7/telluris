"""dev/audit_economy.py §6 — une matière qu'aucune voie du jeu ne fait apparaître.

Le trou qu'il repère : `item:Poison_de_base` portait un bloc `fabrication` et des tags
`fabrication_*`, donc le sur-mesure le proposait — mais rien ne le produisait, ne le livrait,
ne le dépeçait ni ne le faisait tomber. La commande naissait en attente, pour toujours.

Le moteur est injecté : ces tests ne branchent pas `db.config` sur un dump.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.audit_economy import matieres_sans_source  # noqa: E402


def _matiere(slug, **champs):
	return dict({"_id": "item:" + slug, "type": "item", "categorie": "composant"}, **champs)


def _audit(docs, feuilles=(), depecage_tags=None, cible_coupe=None):
	return matieres_sans_source(
		docs,
		matiere_item_id=lambda c: c if str(c).startswith("item:") else "item:" + c,
		objet_final_item_id=lambda s: "item:" + s,
		recette_matieres=lambda r: [((m.get("item") or m.get("sous_categorie")), m.get("quantite", 1))
									for m in r.get("matieres_premieres") or []],
		sous_categorie=lambda d: d.get("sous_categorie") or d.get("categorie") or "",
		feuilles_livrees=set(feuilles),
		depecage_tags=depecage_tags or {},
		est_matiere=lambda d: d.get("categorie") == "composant",
		cible_coupe=cible_coupe,
	)


def _orphelines(*args, **kwargs):
	return [o["item"] for o in _audit(*args, **kwargs)]


POISON = _matiere("Poison_de_base", fabrication={"nom": "Empoisonné", "modificateurs": {"bonus_degats": 1}})


def test_une_matiere_sans_aucune_voie_est_signalee_et_marquee_sur_mesure():
	assert _audit([POISON]) == [{"item": "item:Poison_de_base", "rayon_seulement": False,
								 "recettes": 0, "sorts": 0, "sous_cle": "", "sur_mesure": True}]


def test_un_composant_de_sort_est_un_usage_pas_une_source():
	totem = _matiere("Os_de_totem")
	sorts = [{"_id": "sort:%d" % i, "type": "sort", "composants": [{"item": "item:Os_de_totem"}]}
			 for i in range(2)]
	[o] = _audit([totem] + sorts)
	assert o["sorts"] == 2


def test_une_recette_qui_la_produit_est_une_source():
	recette = {"_id": "recette:p", "type": "recette", "objet_final": "Poison_de_base",
			   "matieres_premieres": [{"item": "item:Capsules_de_pavot", "quantite": 2}]}
	assert _orphelines([POISON, recette]) == []


def test_le_depecage_par_tag_despece_est_une_source():
	assert _orphelines([POISON], depecage_tags={"venin": ["crocs", "item:Poison_de_base"]}) == []


def test_le_depecage_bake_dune_portion_est_une_source():
	tete = _matiere("araignee_geante_tete", sous_categorie="carcasse",
					depecage=[["crocs", 1], ["item:Poison_de_base", 1]])
	assert "item:Poison_de_base" not in _orphelines([POISON, tete])


def test_la_carcasse_dune_espece_est_son_butin():
	carcasse = _matiere("loup")
	assert _orphelines([carcasse, {"_id": "espece:loup", "type": "espece"}]) == []


def test_la_recolte_dun_lieu_est_une_source():
	lieu = {"_id": "lieu:marais", "type": "lieu",
			"ressources": [{"ressource": "item:Poison_de_base"}]}
	assert _orphelines([POISON, lieu]) == []


def test_un_rayon_seul_ne_suffit_pas_il_sepuise():
	lieu = {"_id": "lieu:echoppe", "type": "lieu",
			"stock_vente": [{"item_id": "item:Poison_de_base", "qty": 3}]}
	[o] = _audit([POISON, lieu])
	assert o["rayon_seulement"] is True


def test_letat_de_partie_et_les_sorts_ne_sont_pas_des_sources():
	# Ce qu'un joueur possède ne dit pas où il l'a trouvé ; un sort CONSOMME ses composants.
	joueur = {"_id": "character:x", "type": "character", "inventaire": ["item:Poison_de_base"]}
	sort = {"_id": "sort:x", "type": "sort", "composants": [{"item": "item:Poison_de_base"}]}
	assert _orphelines([POISON, joueur, sort]) == ["item:Poison_de_base"]


def test_une_feuille_livree_est_une_source():
	assert _orphelines([POISON], feuilles=["item:Poison_de_base"]) == []


def test_la_coupe_propage_la_source_le_long_de_lechelle():
	arbre, tronc, rondin = _matiere("Arbre_Chene"), _matiere("Tronc_Chene"), _matiere("Rondin_Chene")
	echelle = {"item:Arbre_Chene": tronc, "item:Tronc_Chene": rondin}
	lieu = {"_id": "lieu:foret", "type": "lieu", "ressources": [{"ressource": "item:Arbre_Chene"}]}
	coupe = lambda d: echelle.get(d["_id"])  # noqa: E731
	assert _orphelines([arbre, tronc, rondin, lieu], cible_coupe=coupe) == []
	# Sans arbre récolté, toute l'échelle reste sans source.
	assert _orphelines([arbre, tronc, rondin], cible_coupe=coupe) == [
		"item:Arbre_Chene", "item:Rondin_Chene", "item:Tronc_Chene"]


def test_seules_les_recettes_dont_la_cle_resout_vers_elle_sont_bloquees():
	mithril = _matiere("mithril", sous_categorie="metaux_precieux")
	par_sous_cle = {"_id": "recette:a", "type": "recette", "objet_final": "Bague",
					"matieres_premieres": [{"sous_categorie": "metaux_precieux", "quantite": 1}]}
	[o] = _audit([mithril, par_sous_cle])
	assert o["recettes"] == 0 and o["sous_cle"] == "metaux_precieux"
	par_id = dict(par_sous_cle, _id="recette:b", matieres_premieres=[{"item": "item:mithril", "quantite": 1}])
	[o] = _audit([mithril, par_id])
	assert o["recettes"] == 1 and o["sous_cle"] == ""


def test_un_objet_fini_nest_pas_une_matiere():
	epee = {"_id": "item:Epee", "type": "item", "categorie": "arme"}
	assert _orphelines([epee]) == []
