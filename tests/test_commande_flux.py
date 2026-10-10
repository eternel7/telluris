# tests/test_commande_flux.py
#
# LA COMMANDE PASSE AVANT LE FLUX DE LA CITÉ, et L'ÉTABLE PREND COMMANDE.
#
# - Ce que l'artisan n'a ni en réserve ni en rayon, il le prend dans le pool `flux_marchand`
#   de sa ville : la ligne entière si besoin (pas de `FLUX_PART_MAX`), même s'il produit
#   lui-même la matière (la garde `lieu_produit` du tick ne vaut pas pour un client).
# - L'étable, sans recette, prend commande du harnachement que fabriquent les boutiques de sa
#   cité : la pièce vient du pool, puis du rayon d'une boutique qui la produit.
#
# Logique pure : recettes et docs servis en mémoire, aucun accès DB.

import pytest

from models import character_stats
from utils import commande, marche

CUIR = {"_id": "item:cuir", "type": "item", "nom": "Cuir", "categorie": "composant",
		"sous_categorie": "cuir", "slots": [], "poids": 1.0, "rarete": "commun"}
SELLE = {"_id": "item:selle", "type": "item", "nom": "Selle", "categorie": "armure",
		 "slots": ["monture_dos"], "poids": 8.0, "rarete": "commun"}
CEINTURE = {"_id": "item:ceinture", "type": "item", "nom": "Ceinture", "categorie": "armure",
			"slots": ["taille"], "poids": 0.5, "rarete": "commun"}
HARNAIS = {"_id": "item:harnais", "type": "item", "nom": "Harnais", "categorie": "armure",
		   "slots": ["monture_dos"], "poids": 4.0, "rarete": "commun"}

RECETTES = [
	{"_id": "recette:selle", "type": "recette", "lieu_categorie": "bourrellerie_test",
	 "objet_final": "selle", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "cuir", "quantite": 3}]},
	{"_id": "recette:ceinture", "type": "recette", "lieu_categorie": "bourrellerie_test",
	 "objet_final": "ceinture", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "cuir", "quantite": 1}]},
	# Le bourrelier consomme ce qu'il produit lui-même : le cas de la garde `lieu_produit`.
	{"_id": "recette:harnais", "type": "recette", "lieu_categorie": "bourrellerie_test",
	 "objet_final": "harnais", "quantite_produite": 1,
	 "matieres_premieres": [{"item": "item:ceinture", "quantite": 2}]},
]

CATALOGUE = {d["_id"]: d for d in (CUIR, SELLE, CEINTURE, HARNAIS)}


@pytest.fixture(autouse=True)
def _marche_en_memoire(monkeypatch):
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: CATALOGUE.get(i))
	monkeypatch.setattr(marche, "resolve_item_ref",
						lambda i: (dict(CATALOGUE[i], item=i) if i in CATALOGUE else None))
	# Une part de tick minuscule : la commande doit l'ignorer.
	monkeypatch.setattr(character_stats, "FLUX_PART_MAX", 0.1)
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def _get(i):
	return CATALOGUE.get(i)


def _bourrelier(_id="lieu:bourrelier", **extra):
	doc = {"_id": _id, "type": "lieu", "categorie": "bourrellerie_test",
		   "lieu_parent": "lieu:cite", "stock_matieres": {}, "stock_vente": []}
	doc.update(extra)
	return doc


def _etable(_id="lieu:etable", **extra):
	doc = {"_id": _id, "type": "lieu", "categorie": "etable", "lieu_parent": "lieu:cite"}
	doc.update(extra)
	return doc


def _flux(**pool):
	return {"doc": {}, "pool": {"item:" + k: v for k, v in pool.items()}, "change": False}


def _qty(lieu, item_id):
	return next((e["qty"] for e in lieu.get("stock_vente", []) if e["item_id"] == item_id), 0)


# ── L'artisan puise au pool de la cité ──────────────────────────────────────────

def test_l_artisan_complete_sa_reserve_dans_le_pool_de_la_cite():
	lieu = _bourrelier(stock_matieres={"cuir": 1})
	flux = _flux(cuir=10)
	res = commande.sourcer([("cuir", 3)], [{"_id": "character:j", "inventaire": []}],
						   lieu, _get, atelier=True, flux=flux)
	assert res["manquantes"] == []
	part = res["atelier"][0]
	assert part["reserve"] == 1 and part["rayon"] == 0
	assert part["flux"] == [{"item_id": "item:cuir", "quantite": 2}]
	assert flux["pool"]["item:cuir"] == 10, "sourcer ne retire rien : c'est consommer_atelier"


def test_la_commande_prend_plus_que_la_part_du_tick():
	"""`FLUX_PART_MAX` (0,1 ici) limite un atelier au tick ; une commande prend ce qu'il faut."""
	flux = _flux(cuir=3)
	res = commande.sourcer([("cuir", 3)], [], _bourrelier(), _get, atelier=True, flux=flux)
	assert res["manquantes"] == []
	assert res["atelier"][0]["flux"] == [{"item_id": "item:cuir", "quantite": 3}]


def test_la_commande_puise_meme_ce_que_l_artisan_produit():
	"""Au tick, `puiser_flux` saute ce que le lieu produit (manège corde → arc) ; une commande
	de harnais, elle, prend les ceintures du pool."""
	lieu = _bourrelier()
	assert marche.lieu_produit(lieu, dict(CEINTURE, item="item:ceinture"))
	res = commande.sourcer([("item:ceinture", 2)], [], lieu, _get, atelier=True,
						   flux=_flux(ceinture=2))
	assert res["manquantes"] == []


def test_pool_insuffisant_la_commande_attend():
	res = commande.sourcer([("cuir", 3)], [], _bourrelier(stock_matieres={"cuir": 1}), _get,
						   atelier=True, flux=_flux(cuir=1))
	assert res["manquantes"] == [{"cle": "cuir", "quantite": 3}]
	assert res["atelier"] == []


def test_sans_flux_comportement_d_avant():
	res = commande.sourcer([("cuir", 3)], [], _bourrelier(stock_matieres={"cuir": 1}), _get,
						   atelier=True)
	assert res["manquantes"] == [{"cle": "cuir", "quantite": 3}]


def test_une_ligne_du_pool_ne_sert_pas_deux_fois():
	"""Deux clés qui désignent la même ligne (sous-catégorie et id) ne la comptent qu'une fois."""
	res = commande.sourcer([("cuir", 2), ("item:cuir", 2)], [], _bourrelier(), _get,
						   atelier=True, flux=_flux(cuir=3))
	assert len(res["atelier"]) == 1
	assert res["manquantes"] == [{"cle": "item:cuir", "quantite": 2}]


def test_consommer_atelier_entame_le_pool_et_le_marque():
	lieu = _bourrelier(stock_matieres={"cuir": 1})
	flux = _flux(cuir=2)
	res = commande.sourcer([("cuir", 3)], [], lieu, _get, atelier=True, flux=flux)
	assert commande.consommer_atelier(lieu, res["atelier"], flux) == []
	assert "item:cuir" not in flux["pool"] and flux["change"] is True
	assert "cuir" not in lieu["stock_matieres"]


# ── L'étable prend commande ─────────────────────────────────────────────────────

def test_l_etable_commande_le_harnachement_produit_dans_sa_cite():
	cat = commande.catalogue_commandable(_etable(), _get, [_bourrelier()])
	# Selle et harnais s'équipent sur une monture ; la ceinture non, le cuir est une matière.
	assert cat == ["item:harnais", "item:selle"]


def test_sans_voisines_l_etable_ne_prend_aucune_commande():
	assert commande.catalogue_commandable(_etable(), _get) == []
	assert commande.lieu_prend_commandes(_etable(), _get) is False
	assert commande.lieu_prend_commandes(_etable(), _get, [_bourrelier()]) is True


def test_une_etable_ne_commande_pas_chez_sa_voisine():
	voisine = _etable("lieu:etable_2", stock_vente=[{"item_id": "item:selle", "qty": 3}])
	assert commande.catalogue_commandable(_etable(), _get, [voisine]) == []


def test_l_atelier_ignore_ses_voisines():
	assert "item:ceinture" in commande.catalogue_commandable(_bourrelier(), _get, None)


def test_la_piece_vient_d_abord_du_pool():
	voisin = _bourrelier(stock_vente=[{"item_id": "item:selle", "qty": 2}])
	res = commande.sourcer_revente("item:selle", _flux(selle=1), [voisin], _get)
	assert res["manquantes"] == []
	part = res["atelier"][0]
	assert part["flux"] == [{"item_id": "item:selle", "quantite": 1}]
	assert part["boutiques"] == []


def test_puis_du_rayon_d_une_boutique_qui_la_produit():
	etranger = {"_id": "lieu:mercier", "type": "lieu", "categorie": "autre",
				"lieu_parent": "lieu:cite", "stock_vente": [{"item_id": "item:selle", "qty": 5}]}
	voisin = _bourrelier(stock_vente=[{"item_id": "item:selle", "qty": 2}])
	res = commande.sourcer_revente("item:selle", None, [etranger, voisin], _get)
	assert res["atelier"][0]["boutiques"] == [{"lieu": "lieu:bourrelier", "quantite": 1}]

	mutes = commande.consommer_atelier(_etable(), res["atelier"], None, [etranger, voisin])
	assert mutes == [voisin]
	assert _qty(voisin, "item:selle") == 1
	assert _qty(etranger, "item:selle") == 5


def test_nulle_part_la_commande_d_etable_attend():
	# 2 cuirs au pool pour une selle qui en demande 3 : la voisine ne peut pas la fabriquer.
	res = commande.sourcer_revente("item:selle", _flux(cuir=2), [_bourrelier()], _get)
	assert res["manquantes"] == [{"cle": "item:selle", "quantite": 1}]
	assert res["atelier"] == []


# ── Option A : l'artisan FABRIQUE l'intermédiaire qui manque ────────────────────

def test_l_artisan_fabrique_l_intermediaire_manquant():
	"""Harnais = 2 ceintures, aucune en rayon : il les cuit avec le cuir de sa réserve."""
	lieu = _bourrelier(stock_matieres={"cuir": 2})
	res = commande.sourcer([("item:ceinture", 2)], [], lieu, _get, atelier=True)
	assert res["manquantes"] == []
	fab = res["atelier"][0]["fabrique"]
	assert fab["produit"] == "item:ceinture" and fab["fois"] == 2 and fab["surplus"] == 0
	assert fab["intrants"][0]["reserve"] == 2

	commande.consommer_atelier(lieu, res["atelier"])
	assert "cuir" not in lieu["stock_matieres"]
	assert _qty(lieu, "item:ceinture") == 0, "la pièce part à la commande, pas en rayon"


def test_le_rayon_sert_avant_la_fabrication():
	lieu = _bourrelier(stock_matieres={"cuir": 5},
					   stock_vente=[{"item_id": "item:ceinture", "qty": 1}])
	res = commande.sourcer([("item:ceinture", 2)], [], lieu, _get, atelier=True)
	part = res["atelier"][0]
	assert part["rayon"] == 1 and part["fabrique"]["fois"] == 1


def test_fabrication_impossible_rien_n_est_promis():
	"""Un seul cuir pour deux ceintures : échec, et le cuir reste libre pour la clé suivante."""
	lieu = _bourrelier(stock_matieres={"cuir": 1})
	res = commande.sourcer([("item:ceinture", 2), ("cuir", 1)], [], lieu, _get, atelier=True)
	assert res["manquantes"] == [{"cle": "item:ceinture", "quantite": 2}]
	assert res["atelier"][0]["cle"] == "cuir" and res["atelier"][0]["reserve"] == 1


def test_une_matiere_ne_sert_pas_deux_fois():
	"""Les ceintures fabriquées prennent les deux cuirs : la clé `cuir` suivante manque."""
	lieu = _bourrelier(stock_matieres={"cuir": 2})
	res = commande.sourcer([("item:ceinture", 2), ("cuir", 1)], [], lieu, _get, atelier=True)
	assert res["manquantes"] == [{"cle": "cuir", "quantite": 1}]


def test_la_fabrication_puise_aussi_au_pool():
	lieu = _bourrelier()
	flux = _flux(cuir=2)
	res = commande.sourcer([("item:ceinture", 2)], [], lieu, _get, atelier=True, flux=flux)
	assert res["manquantes"] == []
	commande.consommer_atelier(lieu, res["atelier"], flux)
	assert flux["pool"] == {} and flux["change"] is True


def test_profondeur_nulle_aucune_fabrication(monkeypatch):
	monkeypatch.setattr(commande, "COMMANDE_PROFONDEUR", 0)
	res = commande.sourcer([("item:ceinture", 2)], [], _bourrelier(stock_matieres={"cuir": 2}),
						   _get, atelier=True)
	assert res["manquantes"] == [{"cle": "item:ceinture", "quantite": 2}]


def test_le_surplus_d_un_lot_va_en_rayon(monkeypatch):
	recettes = [dict(r, quantite_produite=3) if r["_id"] == "recette:ceinture" else r
				for r in RECETTES]
	monkeypatch.setattr(marche, "_all_recettes", lambda: recettes)
	marche.reset_prix_cache()
	lieu = _bourrelier(stock_matieres={"cuir": 1})
	res = commande.sourcer([("item:ceinture", 2)], [], lieu, _get, atelier=True)
	assert res["atelier"][0]["fabrique"]["surplus"] == 1
	commande.consommer_atelier(lieu, res["atelier"])
	assert _qty(lieu, "item:ceinture") == 1


def test_l_etable_fait_fabriquer_la_piece_chez_le_bourrelier():
	voisin = _bourrelier(stock_matieres={"cuir": 3})
	res = commande.sourcer_revente("item:selle", None, [voisin], _get)
	assert res["manquantes"] == []
	part = res["atelier"][0]
	assert part["fabrique_chez"] == "lieu:bourrelier"

	mutes = commande.consommer_atelier(_etable(), res["atelier"], None, [voisin])
	assert mutes == [voisin]
	assert "cuir" not in voisin["stock_matieres"]
	assert _qty(voisin, "item:selle") == 0


def test_l_etable_fabrique_sur_deux_niveaux():
	"""Harnais (2 ceintures ← 2 cuirs) : la voisine cuit les ceintures puis le harnais."""
	voisin = _bourrelier(stock_matieres={"cuir": 2})
	res = commande.sourcer_revente("item:harnais", None, [voisin], _get)
	assert res["manquantes"] == []
	assert res["atelier"][0]["fabrique"]["intrants"][0]["fabrique"]["produit"] == "item:ceinture"


# ── Le rayon des boutiques sœurs ────────────────────────────────────────────────

def _boucher(**extra):
	doc = {"_id": "lieu:boucher", "type": "lieu", "categorie": "boucherie_test",
		   "lieu_parent": "lieu:cite", "stock_vente": [{"item_id": "item:cuir", "qty": 25}]}
	doc.update(extra)
	return doc


def test_l_artisan_prend_au_rayon_d_une_voisine():
	boucher = _boucher()
	lieu = _bourrelier()
	res = commande.sourcer([("cuir", 3)], [], lieu, _get, atelier=True, voisins=[boucher])
	assert res["manquantes"] == []
	assert res["atelier"][0]["boutiques"] == [{"lieu": "lieu:boucher", "item_id": "item:cuir",
											   "quantite": 3}]
	mutes = commande.consommer_atelier(lieu, res["atelier"], None, [boucher])
	assert mutes == [boucher] and _qty(boucher, "item:cuir") == 22


def test_la_voisine_sert_avant_la_fabrication():
	"""Une ceinture en rayon chez la voisine : on la prend plutôt que de la cuire."""
	voisine = _bourrelier("lieu:bourrelier_2", stock_vente=[{"item_id": "item:ceinture", "qty": 2}])
	res = commande.sourcer([("item:ceinture", 2)], [], _bourrelier(stock_matieres={"cuir": 5}),
						   _get, atelier=True, voisins=[voisine])
	part = res["atelier"][0]
	assert "fabrique" not in part and part["boutiques"][0]["lieu"] == "lieu:bourrelier_2"


def test_la_fabrication_puise_au_rayon_des_voisines():
	"""Harnais : ceintures à cuire, cuir pris chez le boucher."""
	boucher = _boucher()
	lieu = _bourrelier()
	res = commande.sourcer([("item:ceinture", 2)], [], lieu, _get, atelier=True, voisins=[boucher])
	assert res["manquantes"] == []
	commande.consommer_atelier(lieu, res["atelier"], None, [boucher])
	assert _qty(boucher, "item:cuir") == 23


def test_ni_soi_ni_un_revendeur_ne_sont_des_voisines():
	lieu = _bourrelier(stock_vente=[{"item_id": "item:cuir", "qty": 0}])
	etable = _etable(stock_vente=[{"item_id": "item:cuir", "qty": 9}])
	res = commande.sourcer([("cuir", 1)], [], lieu, _get, atelier=True, voisins=[lieu, etable])
	assert res["manquantes"] == [{"cle": "cuir", "quantite": 1}]


def test_le_rayon_d_une_voisine_ne_sert_pas_deux_fois():
	boucher = _boucher(stock_vente=[{"item_id": "item:cuir", "qty": 3}])
	res = commande.sourcer([("cuir", 3), ("item:cuir", 1)], [], _bourrelier(), _get,
						   atelier=True, voisins=[boucher])
	assert res["manquantes"] == [{"cle": "item:cuir", "quantite": 1}]


def test_l_etable_fait_fabriquer_avec_la_matiere_du_boucher():
	boucher = _boucher()
	bourrelier = _bourrelier()
	voisins = [boucher, bourrelier]
	res = commande.sourcer_revente("item:selle", None, voisins, _get)
	assert res["manquantes"] == []
	assert res["atelier"][0]["fabrique_chez"] == "lieu:bourrelier"
	mutes = commande.consommer_atelier(_etable(), res["atelier"], None, voisins)
	assert _qty(boucher, "item:cuir") == 22
	assert {m["_id"] for m in mutes} == {"lieu:boucher", "lieu:bourrelier"}


# ── Fabrication chez la voisine qui a la recette ────────────────────────────────

def test_l_intermediaire_d_un_autre_metier_se_fabrique_chez_la_voisine(monkeypatch):
	"""Le cas de la bride : le fil poissé est une recette du CIRIER, pas du bourrelier."""
	fil = {"_id": "item:fil", "type": "item", "nom": "Fil poissé", "categorie": "composant",
		   "sous_categorie": "fil", "slots": [], "poids": 0.1, "rarete": "commun"}
	monkeypatch.setitem(CATALOGUE, "item:fil", fil)
	recettes = RECETTES + [
		{"_id": "recette:fil", "type": "recette", "lieu_categorie": "cirier_test",
		 "objet_final": "fil", "quantite_produite": 1,
		 "matieres_premieres": [{"sous_categorie": "cuir", "quantite": 2}]},
		{"_id": "recette:bride", "type": "recette", "lieu_categorie": "bourrellerie_test",
		 "objet_final": "harnais", "quantite_produite": 1,
		 "matieres_premieres": [{"item": "item:fil", "quantite": 1}]},
	]
	monkeypatch.setattr(marche, "_all_recettes", lambda: recettes)
	marche.reset_prix_cache()
	cirier = {"_id": "lieu:cirier", "type": "lieu", "categorie": "cirier_test",
			  "lieu_parent": "lieu:cite", "stock_matieres": {"cuir": 2}, "stock_vente": []}
	# Le bourrelier a lui aussi 2 cuirs : par lieu, ils ne se décomptent pas l'un l'autre.
	lieu = _bourrelier(stock_matieres={"cuir": 2})
	res = commande.sourcer([("item:fil", 1), ("cuir", 2)], [], lieu, _get, atelier=True,
						   voisins=[cirier])
	assert res["manquantes"] == []
	assert res["atelier"][0]["fabrique_chez"] == "lieu:cirier"
	mutes = commande.consommer_atelier(lieu, res["atelier"], None, [cirier])
	assert mutes == [cirier]
	assert "cuir" not in cirier["stock_matieres"] and "cuir" not in lieu["stock_matieres"]
