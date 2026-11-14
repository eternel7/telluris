"""Entonnoir du panneau marchand : typologie d'un objet en clés de pastilles (utils/filtres_boutique)."""

from utils import filtres_boutique as fb


def _cles_catalogue():
	return {p["cle"] for g in fb.catalogue() for p in g["pastilles"]}


def test_catalogue_cles_completes_et_uniques():
	cles = [p["cle"] for g in fb.catalogue() for p in g["pastilles"]]
	assert len(cles) == len(set(cles))
	assert all(c.split(".", 1)[0] == g["cle"] for g in fb.catalogue() for c in (p["cle"] for p in g["pastilles"]))


def test_armure_partie_protegee_depuis_les_slots():
	assert fb.filtres_item({"categorie": "armure", "slots": ["tete"]}) == ["armure.tete"]
	assert fb.filtres_item({"categorie": "armure", "slots": ["anneau_1", "anneau_2"]}) == ["armure.anneaux"]
	assert fb.filtres_item({"categorie": "armure", "slots": ["monture_dos"]}) == ["armure.monture"]


def test_bouclier_par_sous_categorie_ou_main_gauche_sans_sous_categorie():
	bouclier = fb.filtres_item({"categorie": "armure", "sous_categorie": "bouclier", "slots": ["main_gauche"]})
	assert "armure.bouclier" in bouclier and "prise.gauche" in bouclier
	targe = fb.filtres_item({"categorie": "armure", "sous_categorie": "", "slots": ["main_gauche"]})
	assert "armure.bouclier" in targe
	# Un insigne tenu en main gauche n'est pas un bouclier.
	insigne = fb.filtres_item({"categorie": "armure", "sous_categorie": "insigne", "slots": ["main_gauche"]})
	assert "armure.bouclier" not in insigne and "prise.gauche" in insigne


def test_arme_type_et_prise_en_main():
	hache = fb.filtres_item({"categorie": "arme", "tags": ["cac", "tranchant"],
							 "slots": ["main_droite", "main_gauche"]})
	assert hache == ["arme.cac", "arme.tranchant", "prise.une", "prise.gauche"]
	arc = fb.filtres_item({"categorie": "arme", "sous_categorie": "arc", "tags": ["tir"],
						   "slots": ["main_droite", "main_gauche"], "deux_mains": True})
	assert arc == ["arme.tir", "prise.deux"]   # deux mains : jamais « main gauche »
	epee = fb.filtres_item({"categorie": "arme", "tags": ["cac"], "slots": ["main_droite"]})
	assert "prise.gauche" not in epee and "prise.une" in epee


def test_tags_d_arme_ignores_hors_armes():
	# `tranchant` sur une matière (griffes…) ne fait pas une arme tranchante.
	assert not any(c.startswith("arme.") for c in fb.filtres_item({"categorie": "composant", "tags": ["tranchant"]}))


def test_ingredient_de_sort_calcule_sur_les_sorts():
	sorts = [{"composants": [{"item": "item:Sel_noir", "consomme": False}]},
			 {"composants": [{"item": "item:Sel_noir", "consomme": True}, {"item": "item:os"}]},
			 {"composants": "malformé"}, {}]
	ing = fb.ingredients_sorts(sorts)
	assert ing == frozenset({"item:Sel_noir", "item:os"})
	assert "magie.ingredient" in fb.filtres_item({"_id": "item:Sel_noir", "categorie": "composant"}, ing)
	# Ref d'inventaire résolue : l'id est sous `item`.
	assert "magie.ingredient" in fb.filtres_item({"item": "item:os", "categorie": "composant"}, ing)
	assert "magie.ingredient" not in fb.filtres_item({"_id": "item:Sel_noir", "categorie": "composant"})


def test_catalyseur_et_grimoire():
	assert fb.filtres_item({"categorie": "catalyseur", "slots": ["main_gauche"]}) == [
		"prise.une", "prise.gauche", "magie.catalyseur"]
	assert fb.filtres_item({"categorie": "livre", "sous_categorie": "grimoire"}) == ["magie.grimoire"]
	assert fb.filtres_item({"categorie": "livre", "sous_categorie": "livre_recette"}) == ["divers.livre"]


def test_consommable_par_effet_et_sous_categorie():
	brioche = fb.filtres_item({"categorie": "consommable", "sous_categorie": "boulangerie",
							   "effets": {"pv": 4, "pm": 2, "buffs": {"F": 1}, "duree": 3}})
	assert brioche == ["conso.soin", "conso.mana", "conso.renfort", "conso.nourriture"]
	bougie = fb.filtres_item({"categorie": "consommable", "sous_categorie": "bougie",
							  "effets": {"regen_pm": 1, "duree": 5}})
	assert bougie == ["conso.mana"]
	# Les effets d'une ARME ne font pas d'elle un consommable.
	assert not any(c.startswith("conso.") for c in fb.filtres_item({"categorie": "arme", "effets": {"pv": 3}}))


def test_matieres_premieres():
	assert fb.filtres_item({"categorie": "metal", "sous_categorie": "fer"}) == ["matiere.metal"]
	assert fb.filtres_item({"categorie": "composant", "tags": ["bois"]}) == ["matiere.bois"]
	assert fb.filtres_item({"categorie": "composant", "source_espece": "espece:loup"}) == ["matiere.depouille"]
	assert fb.filtres_item({"categorie": "composant", "sous_categorie": "ossements"}) == ["matiere.depouille"]
	assert fb.filtres_item({"categorie": "composant", "sous_categorie": "encre"}) == ["matiere.autre"]


def test_fabrication_seulement_si_la_matiere_apporte():
	matiere = {"categorie": "composant", "fabrication": {"nom": "de croupon", "modificateurs": {"bonus_pa": 3}}}
	assert "fabrication.ameliore" in fb.filtres_item(matiere)
	# Une VARIANTE déjà fabriquée porte aussi un bloc `fabrication`, mais n'apporte rien.
	variante = {"categorie": "armure", "slots": ["torse"],
				"fabrication": {"base_item": "item:Armure_cuir_runee", "matieres": []}}
	assert "fabrication.ameliore" not in fb.filtres_item(variante)
	assert "fabrication.ameliore" not in fb.filtres_item({"categorie": "composant"})


def test_trophee_seulement_si_produit_par_une_recette_a_trophee():
	issus = frozenset({"item:Tete_naturalisee_balaur"})
	tete = {"_id": "item:Tete_naturalisee_balaur", "categorie": "decoration"}
	assert "fabrication.trophee" in fb.filtres_item(tete, frozenset(), issus)
	# La référence d'inventaire porte son id sous `item`.
	assert "fabrication.trophee" in fb.filtres_item({"item": "item:Tete_naturalisee_balaur"}, frozenset(), issus)
	assert "fabrication.trophee" not in fb.filtres_item(tete)
	assert "fabrication.trophee" not in fb.filtres_item({"_id": "item:autre"}, frozenset(), issus)


def test_items_issus_trophee_lus_sur_les_recettes(monkeypatch):
	"""Seul un intrant `trophee: true` fait d'un produit un objet « à trophée » ; une dépouille
	ordinaire en intrant n'y suffit pas."""
	from utils import marche
	recettes = [
		{"_id": "recette:tete", "objet_final": "Tete_naturalisee_balaur", "lieu_categorie": "cabinet",
		 "matieres_premieres": [{"item": "item:balaur_tete", "quantite": 1, "trophee": True}]},
		{"_id": "recette:bottes", "objet_final": "Bottes_cuir", "lieu_categorie": "tannerie",
		 "matieres_premieres": [{"sous_categorie": "carcasse", "quantite": 1}]},
	]
	monkeypatch.setattr(marche, "_all_recettes", lambda: recettes)
	marche.reset_prix_cache()
	try:
		assert marche.items_issus_trophee() == frozenset({"item:Tete_naturalisee_balaur"})
	finally:
		marche.reset_prix_cache()


def test_divers():
	assert fb.filtres_item({"categorie": "outil", "tags": ["piege"]}) == ["divers.piege"]
	assert fb.filtres_item({"categorie": "outil", "sous_categorie": "contenant", "tags": ["contenant"]}) == ["divers.contenant"]
	assert fb.filtres_item({"categorie": "outil"}) == ["divers.outil"]
	# Outil de crochetage : sa propre pastille (usage non évident), pas « Outils ».
	assert fb.filtres_item({"categorie": "outil", "bonus_desamorcage": 15}) == ["divers.crochetage"]
	assert fb.filtres_item({"categorie": "outil", "bonus_desamorcage": 0}) == ["divers.outil"]
	assert fb.filtres_item({"categorie": "document"}) == ["divers.livre"]
	assert fb.filtres_item({"categorie": "munition"}) == ["divers.munition"]


def test_toute_cle_produite_existe_au_catalogue():
	connues = _cles_catalogue()
	echantillon = [
		{"categorie": "armure", "slots": [s]} for s in fb._SLOT_ARMURE
	] + [
		{"categorie": "arme", "tags": list(fb._TAGS_ARME), "sous_categorie": "instrument", "slots": ["main_gauche"]},
		{"categorie": "consommable", "sous_categorie": "boisson", "effets": {"pv": 1, "pm": 1, "buffs": {"F": 1}}},
		{"categorie": "consommable", "sous_categorie": next(iter(fb._SC_NOURRITURE))},
		{"_id": "item:x", "categorie": "catalyseur", "slots": ["main_droite", "main_gauche"], "deux_mains": True},
		{"categorie": "livre", "sous_categorie": "grimoire"},
		{"categorie": "composant", "fabrication": {"nom": "x"}},
		{"categorie": "outil", "tags": ["piege", "contenant"]},
		{"categorie": "outil", "bonus_desamorcage": 5},
	]
	produites = {c for it in echantillon
				 for c in fb.filtres_item(it, frozenset({"item:x"}), frozenset({"item:x"}))}
	assert produites <= connues, produites - connues


def test_objet_vide_ou_absent():
	assert fb.filtres_item(None) == []
	assert fb.filtres_item({}) == []


def test_les_lignes_d_achat_portent_leurs_filtres(monkeypatch):
	"""Resync §10 : la ligne de rayon arrive classée ; le client ne reclasse rien. La lecture des
	sorts se fait UNE fois par liste, et pas du tout pour un rayon vide."""
	from utils import marche
	casque = {"_id": "item:casque", "type": "item", "nom": "Casque", "categorie": "armure",
			  "slots": ["tete"], "poids": 1.0, "rarete": "commun"}
	sel = {"_id": "item:sel_noir", "type": "item", "nom": "Sel noir", "categorie": "composant",
		   "poids": 0.1, "rarete": "commun"}
	docs = {d["_id"]: d for d in (casque, sel)}
	lectures = []

	def find_docs(selector, fields=None, limit=10_000):
		lectures.append(selector)
		return [{"_id": "sort:x", "composants": [{"item": "item:sel_noir", "consomme": True}]}]

	monkeypatch.setattr(marche, "find_docs", find_docs)
	monkeypatch.setattr(marche, "_all_recettes", lambda: [])
	monkeypatch.setattr(marche, "get_doc", lambda i: docs.get(i))
	monkeypatch.setattr(marche, "resolve_item_ref", lambda i: (dict(docs[i], item=i) if i in docs else None))
	marche.reset_prix_cache()
	try:
		lieu = {"_id": "lieu:echoppe", "type": "lieu", "categorie": "echoppe_test",
				"stock_vente": [{"item_id": "item:casque", "qty": 1}, {"item_id": "item:sel_noir", "qty": 2}]}
		lignes = {l["item_id"]: l["filtres"] for l in marche.resolve_stock_vente(lieu)}
		assert lignes == {"item:casque": ["armure.tete"],
						  "item:sel_noir": ["magie.ingredient", "matiere.autre"]}
		assert lectures == [{"type": "sort"}]
		lectures.clear()
		assert marche.resolve_stock_vente(dict(lieu, stock_vente=[])) == []
		assert lectures == []
	finally:
		marche.reset_prix_cache()
