"""Négociant — le « marchand pur » (`utils/negoce.py`) : logique pure.

Ce que ces tests verrouillent :
1. **Commission linéaire** en relation (MAX à 0, MIN à 100), sans stock ni marchandage.
2. **Anti-arbitrage** : le négociant paie toujours MOINS que la valeur V (= pmin, plancher de
   vente de toute boutique), et la conversion en cuivre ne dépasse jamais V.
3. **Destin d'un objet racheté** : rayon au-dessus du seuil ; sinon flux si une clé utile le
   réclame et que le pool n'est pas plein ; sinon conversion. La carcasse ne circule jamais.
4. **Il achète tout** (`marche.lieu_buys`), et seulement lui.
5. **En propriété** : un objet confié ou racheté suit le même destin ; la conversion va à la
   caisse.

Docs en mémoire, aucune base. Les seuils sont RELUS du module (Conventions §14).
"""

import pytest

from models import character_stats
from utils import marche
from utils import negoce
from utils import proprietes


def _item(_id, v, sous_categorie=None):
	return {"_id": _id, "type": "item", "nom": _id, "categorie": "composant",
			"sous_categorie": sous_categorie or _id.split(":")[1], "slots": [], "poids": 1.0,
			"rarete": "commun", "valeur": [{"cu": v}, {"cu": 3 * v}]}


SEUIL = character_stats.NEGOCE_SEUIL_REVENTE_CUIVRE
JOYAU = _item("item:joyau", SEUIL)                 # pile au seuil → rayon
CUIR = _item("item:cuir", 40)                      # consommé par la tannerie de test
CAILLOU = _item("item:caillou", 10)                # personne n'en veut
SANGLIER = _item("item:sanglier_carcasse", 50, sous_categorie="carcasse")
DOCS = {d["_id"]: d for d in (JOYAU, CUIR, CAILLOU, SANGLIER)}

RECETTES = [
	{"_id": "recette:botte", "type": "recette", "lieu_categorie": "tannerie_test",
	 "objet_final": "botte", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "cuir", "quantite": 2}]},
]

NEGOCIANT = {"_id": "lieu:comptoir", "type": "lieu", "categorie": "negociant"}
TANNERIE = {"_id": "lieu:tannerie", "type": "lieu", "categorie": "tannerie_test"}


@pytest.fixture(autouse=True)
def _monde(monkeypatch):
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: DOCS.get(i))
	resoudre = lambda i: (dict(DOCS[i], item=i) if i in DOCS else None)
	monkeypatch.setattr(marche, "resolve_item_ref", resoudre)
	monkeypatch.setattr(proprietes, "resolve_item_ref", resoudre)
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def rel(v):
	return {"value": v}


def flux(pool=None):
	return {"doc": {}, "pool": dict(pool or {}), "change": False}


# ── Prix ──────────────────────────────────────────────────────────────────────────

def test_commission_lineaire_en_relation():
	cmin = character_stats.NEGOCE_COMMISSION_MIN
	cmax = character_stats.NEGOCE_COMMISSION_MAX
	assert negoce.commission(rel(0)) == pytest.approx(cmax)
	assert negoce.commission(rel(100)) == pytest.approx(cmin)
	assert negoce.commission(rel(50)) == pytest.approx((cmin + cmax) / 2)
	assert negoce.commission(rel(150)) == pytest.approx(cmin)       # relation bornée 0–100
	assert negoce.commission(None) == pytest.approx(cmax)


def test_commission_par_defaut_de_10_a_30_pourcent():
	"""Les bornes demandées : 30 % à relation nulle, 10 % au mieux."""
	assert character_stats.NEGOCE_COMMISSION_MIN == pytest.approx(0.10)
	assert character_stats.NEGOCE_COMMISSION_MAX == pytest.approx(0.30)


def test_prix_rachat_suit_la_commission():
	assert negoce.prix_rachat(CUIR, rel(0)) == round(40 * (1 - character_stats.NEGOCE_COMMISSION_MAX))
	assert negoce.prix_rachat(CUIR, rel(100)) == round(40 * (1 - character_stats.NEGOCE_COMMISSION_MIN))
	assert negoce.bornes_rachat(CUIR) == (negoce.prix_rachat(CUIR, rel(0)),
										  negoce.prix_rachat(CUIR, rel(100)))


@pytest.mark.parametrize("item", [JOYAU, CUIR, CAILLOU, SANGLIER])
def test_rachat_toujours_sous_la_valeur(item):
	"""Acheter ailleurs (≥ pmin) pour revendre au négociant ne rapporte jamais."""
	v, _ = marche.prix_range_cuivre(item, item["_id"])
	for r in range(0, 101, 5):
		assert negoce.prix_rachat(item, rel(r)) < v


@pytest.mark.parametrize("item", [JOYAU, CUIR, CAILLOU, SANGLIER])
def test_conversion_jamais_au_dessus_de_la_valeur(item):
	"""Acheter à V, confier au négociant, relever la caisse : jamais un gain."""
	v, _ = marche.prix_range_cuivre(item, item["_id"])
	assert negoce.prix_conversion(item) <= v
	assert negoce.prix_conversion(item) == round(
		v * character_stats.RACHAT_FACTEUR * (1 + character_stats.NEGOCE_BONUS_CONVERSION))


# ── Il achète tout ────────────────────────────────────────────────────────────────

def test_le_negociant_achete_tout_les_autres_inchanges():
	for it in DOCS.values():
		assert marche.lieu_buys(NEGOCIANT, it)
	assert marche.lieu_buys(TANNERIE, CUIR)
	assert not marche.lieu_buys(TANNERIE, CAILLOU)
	assert not marche.est_negociant(TANNERIE) and marche.est_negociant(NEGOCIANT)


# ── Destin de l'objet ─────────────────────────────────────────────────────────────

def test_au_dessus_du_seuil_au_rayon():
	doc = dict(NEGOCIANT)
	f = flux()
	assert negoce.absorber(doc, JOYAU, f, {"joyau"}) == ("rayon", 0)
	assert doc["stock_vente"] == [{"item_id": "item:joyau", "qty": 1}]
	assert f["pool"] == {} and not f["change"]


def test_sous_le_seuil_et_utile_au_flux():
	doc = dict(NEGOCIANT)
	f = flux()
	assert negoce.absorber(doc, CUIR, f, marche.cles_consommees()) == ("flux", 0)
	assert f["pool"] == {"item:cuir": 1} and f["change"]
	assert "stock_vente" not in doc


def test_inutile_au_flux_converti():
	f = flux()
	dest, cuivre = negoce.absorber(dict(NEGOCIANT), CAILLOU, f, marche.cles_consommees())
	assert dest == "conversion" and cuivre == negoce.prix_conversion(CAILLOU)
	assert f["pool"] == {} and not f["change"]


def test_pool_plein_converti():
	plein = flux({"item:cuir": character_stats.STOCK_CIBLE_DEFAUT})
	dest, cuivre = negoce.absorber(dict(NEGOCIANT), CUIR, plein, {"cuir"})
	assert dest == "conversion" and cuivre > 0
	assert plein["pool"]["item:cuir"] == character_stats.STOCK_CIBLE_DEFAUT


def test_sans_flux_converti():
	assert negoce.absorber(dict(NEGOCIANT), CUIR, None, {"cuir"})[0] == "conversion"


def test_la_carcasse_ne_circule_jamais():
	dest, _ = negoce.absorber(dict(NEGOCIANT), SANGLIER, flux(), {"carcasse", "item:sanglier_carcasse"})
	assert dest == "conversion"


# ── En propriété ─────────────────────────────────────────────────────────────────

def _negociant_employe():
	prop = {"_id": "propriete:demeure_1", "type": "propriete", "type_propriete": "demeure",
			"mode": "achat", "statut": "possedee", "proprietaire": "character:a",
			"lieu_parent": "lieu:ville", "amenagements": ["bureau_marchand"], "employes": []}
	cand = {"id": "c1", "amenagement": "bureau_marchand", "metier": "marchand", "prenom": "Jehan",
			"nom": "Lombard", "sex": "M", "race": "humain", "portrait": "x.jpg",
			"categorie": "negociant", "modele": proprietes.MODELE_PREFIXE + "negociant"}
	return proprietes.creer_employe(prop, cand, {"_id": "character:a"})


def test_confier_au_negociant_rayon_flux_ou_caisse():
	e = _negociant_employe()
	assert proprietes.est_atelier(e)
	f = flux()
	assert proprietes.donner(e, JOYAU, f, {"cuir"})[0]
	assert e["stock_vente"] == [{"item_id": "item:joyau", "qty": 1}]
	assert proprietes.donner(e, CUIR, f, {"cuir"})[0]
	assert f["pool"] == {"item:cuir": 1}
	assert proprietes.racheter(e, CAILLOU, f, {"cuir"})[0]
	assert e["caisse_cuivre"] == negoce.prix_conversion(CAILLOU)
	assert e["stock_matieres"] == {}


def test_cles_utiles_du_bien_les_autres_ateliers():
	e = _negociant_employe()
	tanneur = {"_id": "employe:t", "type": proprietes.TYPE_EMPLOYE, "statut": proprietes.EMPLOYE_ACTIF,
			   "categorie": "tannerie_test"}
	docs = {"employe:t": tanneur, e["_id"]: e}
	prop = {"employes": [e["_id"], "employe:t"]}
	assert "cuir" in proprietes.cles_utiles_flux(prop, e, docs.get)
	assert proprietes.cles_utiles_flux({"employes": [e["_id"]]}, e, docs.get) == set()
