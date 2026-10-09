"""Endpoints des propriétés (`routers/proprietes.py`) et leurs points d'intégration.

Ce que la logique pure ne voit pas :
1. **L'achat crée DEUX docs** — la propriété et sa connexion depuis la case d'achat — et
   n'est offert que sur une zone habitable du bon type.
2. **Céder supprime la porte et reconduit dehors** : on ne reste pas dans un lieu sans porte.
3. **Le vol** passe par le coffre (`coffre/transferer`) ou la caisse ; un gardien au poste le bloque.
4. **La nuit chez soi est gratuite** et emprunte le flux de l'auberge (`_acces_nuit`).
5. **Louer deux fois la même chambre la prolonge** au lieu d'en créer une seconde.

Base en mémoire, gabarit de `tests/test_auberge_endpoints.py`.
"""

import asyncio
import json
import os

import pytest

from fastapi import HTTPException

from utils import characters as characters_util
from utils.characters import item_ref_id
from utils import marche
from utils import proprietes


with open(os.path.join(os.path.dirname(__file__), "..", "jsons", "proprietes_a_importer.json"),
		  encoding="utf-8") as _f:
	CATALOGUE_DOCS = json.load(_f)["docs"]

VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "label": "Ville",
		 "zone_influences": [{"x": 5, "y": 5, "w": 4, "h": 4, "rot": 0, "forme": "rectangle",
							  "zone": "zone:habitable_maison"}]}
# Une recette de laboratoire : l'alchimiste de test a l'usage de l'herbe et produit l'élixir.
HERBE = {"_id": "item:herbe", "type": "item", "nom": "Herbe", "categorie": "composant",
		 "sous_categorie": "herbe", "slots": [], "poids": 1.0, "rarete": "commun"}
# Un CONSOMMABLE et non une matière : seul un produit fini entre au catalogue de commande.
ELIXIR = {"_id": "item:elixir", "type": "item", "nom": "Élixir", "categorie": "consommable",
		  "sous_categorie": "potion", "slots": [], "poids": 0.5, "rarete": "commun"}
RECETTES = [{"_id": "recette:elixir", "type": "recette", "lieu_categorie": "laboratoire_d_alchimie",
			 "objet_final": "elixir", "quantite_produite": 1,
			 "matieres_premieres": [{"sous_categorie": "herbe", "quantite": 2}]}]
MODELE_ALCHIMISTE = {"_id": "pnj:marchand_laboratoire_d_alchimie", "type": "pnj",
					 "nom": "Maître Corvin", "race": "humain", "portrait": "humain_m_mage01.jpg"}
AUBERGE = {"_id": "lieu:auberge", "type": "lieu", "categorie": "auberge", "label": "Auberge",
		   "lieu_parent": "lieu:ville"}
CARACTS = {"V": 5, "F": 40, "R": 40, "Ag": 40, "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40}


def _perso(**champs):
	base = {
		"_id": "character:a", "type": "character", "lieu": "lieu:ville",
		"position": {"x": 5, "y": 5}, "prenom": "Greta", "nom": "Hazgard", "cite": "lieu:ville",
		"inventaire": [], "slots": {}, "groupe": [], "montures": [],
		"caracteristiques_current": dict(CARACTS), "currentPV": 1, "currentPM": 0,
		"or": 100, "argent": 0, "cuivre": 0,
	}
	base.update(champs)
	return base


@pytest.fixture
def monde(monkeypatch):
	from routers import proprietes as rp
	from routers import auberge as ra
	from utils import auberge

	docs = {d["_id"]: json.loads(json.dumps(d)) for d in [*CATALOGUE_DOCS, VILLE, AUBERGE, MODELE_ALCHIMISTE, HERBE, ELIXIR]}
	supprimes = []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def delete_doc_fn(doc):
		docs.pop(doc.get("_id"), None)
		supprimes.append(doc.get("_id"))
		return doc

	def find_docs_fn(selector, fields=None):
		return [d for d in list(docs.values())
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	from routers import user as ru
	for mod in (rp, ra, ru, auberge, characters_util, proprietes, marche):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
		monkeypatch.setattr(mod, "delete_doc", delete_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_docs", lambda ds: [bool(save_doc_fn(d)) for d in ds],
							raising=False)
	# Vue `reseau/liens_cases` en mémoire : connexions dont un nœud est sur le lieu.
	monkeypatch.setattr(rp, "connexions_du_lieu", lambda lieu_id: [
		d for d in list(docs.values()) if d.get("type") == "connection"
		and any(n.get("lieu") == lieu_id for n in d.get("nodes") or [])])
	# Recettes en mémoire : aucune lecture de la vraie base par les index du marché.
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	marche.reset_prix_cache()
	yield {"docs": docs, "supprimes": supprimes, "rp": rp, "ra": ra, "ru": ru}
	marche.reset_prix_cache()


def _appel(monde, character, coro_fn, *args, module="rp"):
	mod = monde[module]
	monde["docs"][character["_id"]] = character
	origine = mod.get_selected_character
	try:
		mod.get_selected_character = lambda _u: character
		return asyncio.run(coro_fn(*args))
	finally:
		mod.get_selected_character = origine


def _quotes(monde, character):
	"""`marchand_quotes` est un `def` (threadpool), pas une coroutine : appel direct."""
	ru = monde["ru"]
	monde["docs"][character["_id"]] = character
	origine = ru.get_selected_character
	try:
		ru.get_selected_character = lambda _u: character
		return ru.marchand_quotes(None)
	finally:
		ru.get_selected_character = origine


def _cat(monde):
	return proprietes.catalogue(monde["docs"].get)


def _acheter_maison(monde, char):
	return _appel(monde, char, monde["rp"].acheter, None, {"type": "maison"})


# ── Achat ─────────────────────────────────────────────────────────────────────────

def test_offre_dans_la_zone(monde):
	data = _appel(monde, _perso(), monde["rp"].offre, None)
	assert [t["id"] for t in data["types"]] == ["maison"]
	assert data["location"] is None


def test_offre_refusee_hors_zone(monde):
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso(position={"x": 40, "y": 40}), monde["rp"].offre, None)
	assert e.value.status_code == 403


def test_achat_cree_propriete_et_connexion(monde):
	char = _perso()
	avant = characters_util.money_to_cuivre(char)
	data = _acheter_maison(monde, char)
	prop = monde["docs"][data["achetee"]["id"]]
	lien = monde["docs"][prop["lien"]]
	assert prop["type_propriete"] == "maison" and prop["statut"] == proprietes.POSSEDEE
	assert lien["nodes"][0] == {"lieu": "lieu:ville", "pos": [5, 5]}
	prix = proprietes.type_def(_cat(monde), "maison")["prix_cuivre"]
	assert characters_util.money_to_cuivre(char) == avant - prix
	assert char["proprietes"] == [prop["_id"]]


def test_achat_majore_par_les_biens_deja_sur_la_case(monde):
	"""Le second acheteur de la même case paie le multiplicateur d'occupation, recalculé au
	serveur ; l'offre l'annonce avec son prix de base."""
	base = proprietes.type_def(_cat(monde), "maison")["prix_cuivre"]
	m = proprietes.PRIX_ACHAT_DEFAUT["multiplicateur_occupation"]
	_acheter_maison(monde, _perso())
	second = _perso(_id="character:b", **{"or": 10 ** 6})
	offre = _appel(monde, second, monde["rp"].offre, None)["types"][0]
	assert offre["prix"] == base * m and offre["prix_base"] == base
	assert offre["majoration"]["proprietes_case"] == 1
	avant = characters_util.money_to_cuivre(second)
	data = _acheter_maison(monde, second)
	assert characters_util.money_to_cuivre(second) == avant - base * m
	assert monde["docs"][data["achetee"]["id"]]["prix_paye"] == base * m
	# La revente suit le prix PAYÉ, pas le prix du type.
	second["lieu"], second["position"] = data["achetee"]["id"], {"x": 0, "y": 0}
	facteur = proprietes.type_def(_cat(monde), "maison")["revente_facteur"]
	assert _appel(monde, second, monde["rp"].vendre, None)["gain"] == round(base * m * facteur)


def test_achat_majore_par_une_boutique_voisine(monde):
	monde["docs"]["lieu:forge"] = {"_id": "lieu:forge", "type": "lieu", "categorie": "laboratoire_d_alchimie"}
	monde["docs"]["link:forge"] = {"_id": "link:forge", "type": "connection",
								   "nodes": [{"lieu": "lieu:ville", "pos": [6, 5]}, {"lieu": "lieu:forge", "pos": [0, 0]}]}
	base = proprietes.type_def(_cat(monde), "maison")["prix_cuivre"]
	offre = _appel(monde, _perso(), monde["rp"].offre, None)["types"][0]
	assert offre["prix"] > base and offre["majoration"]["voisinage_pct"] > 0


def test_achat_d_un_autre_type_refuse(monde):
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso(), monde["rp"].acheter, None, {"type": "demeure"})
	assert e.value.status_code == 403


def test_achat_sans_fonds_ne_cree_rien(monde):
	char = _perso(**{"or": 0})
	n = len(monde["docs"])
	with pytest.raises(HTTPException) as e:
		_acheter_maison(monde, char)
	assert e.value.status_code == 409
	assert len(monde["docs"]) == n + 1       # seul le personnage a été posé par `_appel`


# ── Dans la propriété ─────────────────────────────────────────────────────────────

def _entrer(monde, char):
	pid = _acheter_maison(monde, char)["achetee"]["id"]
	char["lieu"] = pid
	char["position"] = {"x": 0, "y": 0}
	return monde["docs"][pid]


def test_installer_debite_et_resynchronise(monde):
	char = _perso()
	prop = _entrer(monde, char)
	data = _appel(monde, char, monde["rp"].installer, None, {"amenagement": "cave"})
	assert "cave" in prop["amenagements"]
	assert [a["id"] for a in data["installes"]] == ["cave"]
	assert "cave" not in [a["id"] for a in data["disponibles"]]
	with pytest.raises(HTTPException):
		_appel(monde, char, monde["rp"].installer, None, {"amenagement": "ecurie_limitee"})


def test_vol_puis_gardien(monde):
	proprio = _perso()
	prop = _entrer(monde, proprio)
	prop["coffre"] = [{"item": "item:a", "poids": 1}, {"item": "item:b", "poids": 1}]
	voleur = _perso(_id="character:b", lieu=prop["_id"])
	data = _appel(monde, voleur, monde["rp"].coffre_transferer, None,
				  {"sens": "vers_principal", "index": 0, "item_id": "item:a"})
	assert data["vol"] is True and voleur["inventaire"] == [{"item": "item:a", "poids": 1}]

	_appel(monde, proprio, monde["rp"].installer, None, {"amenagement": "loge_gardien"})
	_engager(monde, proprio, "gardien")
	with pytest.raises(HTTPException) as e:
		_appel(monde, voleur, monde["rp"].coffre_transferer, None,
			   {"sens": "vers_principal", "index": 0, "item_id": "item:b"})
	assert e.value.status_code == 403
	vue = _appel(monde, voleur, monde["rp"].coffre, None)
	assert vue["role"] == "visiteur" and vue["gardien"] is True
	assert vue["coffre"]["visible"] is False and vue["coffre"]["inventaire"] == []


def test_visiteur_ne_gere_pas(monde):
	prop = _entrer(monde, _perso())
	voleur = _perso(_id="character:b", lieu=prop["_id"])
	with pytest.raises(HTTPException) as e:
		_appel(monde, voleur, monde["rp"].installer, None, {"amenagement": "cave"})
	assert e.value.status_code == 403


def test_vendre_supprime_la_porte_et_reconduit_dehors(monde):
	char = _perso()
	prop = _entrer(monde, char)
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "cave"})
	avant = characters_util.money_to_cuivre(char)
	data = _appel(monde, char, monde["rp"].vendre, None)
	tdef = proprietes.type_def(_cat(monde), "maison")
	assert data["gain"] == proprietes.prix_revente(tdef, prop)
	assert characters_util.money_to_cuivre(char) == avant + data["gain"]
	assert prop["lien"] in monde["supprimes"]
	assert prop["amenagements"] == ["cave"] and prop["statut"] == proprietes.VENDUE
	assert char["lieu"] == "lieu:ville" and char["position"] == {"x": 5, "y": 5}
	assert char["proprietes"] == []


def test_deposer_renvoie_le_sac(monde):
	char = _perso(inventaire=[{"item": "item:a", "poids": 2}])
	prop = _entrer(monde, char)
	data = _appel(monde, char, monde["rp"].coffre_transferer, None,
				  {"sens": "vers_coffre", "index": 0, "item_id": "item:a"})
	assert prop["coffre"] == [{"item": "item:a", "poids": 2}]
	assert data["principal"]["inventaire"] == [] and data["coffre"]["charge"] == 2


def _compagnon(monde, char, av_id="aventurier:x", **champs):
	av = {"_id": av_id, "type": "aventurier", "prenom": "Ulf", "nom": "", "statut": "embauche",
		  "embauche_par": char["_id"], "inventaire": [], "slots": {},
		  "caracteristiques_current": dict(CARACTS), **champs}
	monde["docs"][av_id] = av
	char["groupe"] = [*char.get("groupe", []), av_id]
	return av


def test_coffre_expose_et_sert_le_sac_d_un_compagnon(monde):
	char = _perso()
	prop = _entrer(monde, char)
	av = _compagnon(monde, char, inventaire=[{"item": "item:herbe", "poids": 1.0}])
	vue = _appel(monde, char, monde["rp"].coffre, None)
	assert [p["id"] for p in vue["porteurs"]] == ["aventurier:x"]
	assert vue["porteurs"][0]["monture"] is False
	assert [d["nom"] for d in vue["porteurs"][0]["inventaire"]] == ["Herbe"]

	data = _appel(monde, char, monde["rp"].coffre_transferer, None,
				  {"sens": "vers_coffre", "index": 0, "item_id": "item:herbe", "compagnon_id": "aventurier:x"})
	assert av["inventaire"] == [] and prop["coffre"] == [{"item": "item:herbe", "poids": 1.0}]
	assert data["porteurs"][0]["inventaire"] == [] and data["coffre"]["charge"] == 1.0

	_appel(monde, char, monde["rp"].coffre_transferer, None,
		   {"sens": "vers_principal", "index": 0, "item_id": "item:herbe", "compagnon_id": "aventurier:x"})
	assert av["inventaire"] == [{"item": "item:herbe", "poids": 1.0}] and prop["coffre"] == []
	assert char["inventaire"] == []


def test_coffre_refuse_le_compagnon_d_autrui(monde):
	char = _perso()
	_entrer(monde, char)
	autre = _perso(_id="character:b")
	_compagnon(monde, autre, inventaire=[{"item": "item:herbe", "poids": 1.0}])
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rp"].coffre_transferer, None,
			   {"sens": "vers_coffre", "index": 0, "item_id": "item:herbe", "compagnon_id": "aventurier:x"})
	assert e.value.status_code == 403


def test_visiteur_ne_depose_rien(monde):
	prop = _entrer(monde, _perso())
	visiteur = _perso(_id="character:b", lieu=prop["_id"], inventaire=[{"item": "item:a", "poids": 1}])
	with pytest.raises(HTTPException) as e:
		_appel(monde, visiteur, monde["rp"].coffre_transferer, None,
			   {"sens": "vers_coffre", "index": 0, "item_id": "item:a"})
	assert e.value.status_code == 409


# ── Embauche et marchands employés ────────────────────────────────────────────────

def _engager(monde, proprio, metier):
	"""Ouvre le tableau d'embauche et engage le premier candidat du métier voulu."""
	board = _appel(monde, proprio, monde["rp"].embauche, None)
	prop = monde["docs"][proprio["lieu"]]
	cand = next(c for c in prop["candidats"] if c["metier"] == metier)
	assert any(c["id"] == cand["id"] for c in board["candidats"])
	data = _appel(monde, proprio, monde["rp"].engager, None, {"candidat_id": cand["id"]})
	return data, next(e for e in prop["employes"] if monde["docs"][e]["metier"] == metier)


def _marchand(monde, proprio):
	"""Installe un petit laboratoire et y engage un alchimiste — le marchand de test."""
	_appel(monde, proprio, monde["rp"].installer, None, {"amenagement": "petit_laboratoire"})
	_, eid = _engager(monde, proprio, "alchimiste")
	return monde["docs"][eid]


def test_embaucher_un_marchand_reprend_la_fiche_du_modele(monde):
	proprio = _perso()
	_entrer(monde, proprio)
	e = _marchand(monde, proprio)
	modele = monde["docs"][proprietes.MODELE_PREFIXE + "laboratoire_d_alchimie"]
	assert proprietes.est_atelier(e) and e["categorie"] == "laboratoire_d_alchimie"
	assert e["portrait"] == modele["portrait"] and e["modele"] == modele["_id"]


def test_choisir_un_marchand_commande_simple_pas_sur_mesure(monde):
	proprio = _perso()
	prop = _entrer(monde, proprio)
	e = _marchand(monde, proprio)
	visiteur = _perso(_id="character:b", lieu=prop["_id"])
	vue = _appel(monde, visiteur, monde["rp"].atelier_choisir, None, {"employe_id": e["_id"]})
	assert visiteur["atelier_courant"] == e["_id"]
	assert vue["sur_mesure"] is False and vue["grande"] is False


def test_donner_puis_caisse_relevee_ou_volee(monde):
	proprio = _perso(inventaire=[{"item": "item:rien", "poids": 1}])
	prop = _entrer(monde, proprio)
	e = _marchand(monde, proprio)
	with pytest.raises(HTTPException) as err:           # il n'a pas l'usage de cet objet
		_appel(monde, proprio, monde["rp"].atelier_donner, None,
			   {"employe_id": e["_id"], "index": 0, "item_id": "item:rien"})
	assert err.value.status_code == 409

	e["caisse_cuivre"] = 30
	voleur = _perso(_id="character:b", lieu=prop["_id"])
	avant = characters_util.money_to_cuivre(voleur)
	data = _appel(monde, voleur, monde["rp"].caisse_relever, None)
	assert data["vol"] is True and characters_util.money_to_cuivre(voleur) == avant + 30
	assert e["caisse_cuivre"] == 0
	with pytest.raises(HTTPException) as err:           # caisse vide
		_appel(monde, proprio, monde["rp"].caisse_relever, None)
	assert err.value.status_code == 409


def test_ceder_refuse_tant_que_la_caisse_est_pleine(monde):
	proprio = _perso()
	_entrer(monde, proprio)
	e = _marchand(monde, proprio)
	e["caisse_cuivre"] = 5
	with pytest.raises(HTTPException) as err:
		_appel(monde, proprio, monde["rp"].vendre, None)
	assert err.value.status_code == 409


# ── Location ──────────────────────────────────────────────────────────────────────

def test_louer_puis_prolonger_la_meme_chambre(monde):
	char = _perso(lieu="lieu:auberge", position={"x": 0, "y": 0})
	d1 = _appel(monde, char, monde["rp"].louer, None)
	d2 = _appel(monde, char, monde["rp"].louer, None)
	assert d1["louee"]["id"] == d2["louee"]["id"]
	duree = proprietes.location_de(proprietes.type_def(_cat(monde), "chambre"))["duree_s"]
	assert d2["louee"]["expire_at"] - d1["louee"]["expire_at"] == duree
	chambres = [d for d in monde["docs"].values() if d.get("type") == "propriete"]
	assert len(chambres) == 1 and chambres[0]["mode"] == proprietes.MODE_LOCATION


def test_chambre_louee_refuse_un_intrus(monde):
	char = _perso(lieu="lieu:auberge", position={"x": 0, "y": 0})
	pid = _appel(monde, char, monde["rp"].louer, None)["louee"]["id"]
	intrus = _perso(_id="character:b", lieu=pid)
	with pytest.raises(HTTPException) as e:
		_appel(monde, intrus, monde["rp"].ici, None)
	assert e.value.status_code == 403


# ── La nuit chez soi ──────────────────────────────────────────────────────────────

def test_nuit_gratuite_chez_soi(monde):
	char = _perso()
	_entrer(monde, char)
	avant = characters_util.money_to_cuivre(char)
	data = _appel(monde, char, monde["ra"].passer_la_nuit, None, module="ra")
	assert data["cout"] == 0 and characters_util.money_to_cuivre(char) == avant


def test_nuit_refusee_chez_autrui(monde):
	prop = _entrer(monde, _perso())
	intrus = _perso(_id="character:b", lieu=prop["_id"])
	with pytest.raises(HTTPException) as e:
		_appel(monde, intrus, monde["ra"].passer_la_nuit, None, module="ra")
	assert e.value.status_code == 403


def test_visiteur_achete_au_marchand_le_prix_va_en_caisse(monde):
	proprio = _perso()
	prop = _entrer(monde, proprio)
	e = _marchand(monde, proprio)
	e["stock_vente"] = [{"item_id": "item:elixir", "qty": 3}]
	client = _perso(_id="character:b", lieu=prop["_id"])
	_appel(monde, client, monde["rp"].atelier_choisir, None, {"employe_id": e["_id"]})
	avant = characters_util.money_to_cuivre(client)
	_appel(monde, client, monde["ru"].buy_item, None, {"item_id": "item:elixir"}, module="ru")
	paye = avant - characters_util.money_to_cuivre(client)
	assert paye > 0 and e["caisse_cuivre"] >= paye           # + ventes auto éventuelles du tick
	assert any(item_ref_id(r) == "item:elixir" for r in client["inventaire"])
	assert "flux_marchand" not in monde["docs"]["lieu:ville"]   # jamais le flux de la ville


def test_visiteur_vend_au_marchand_employe_paye_comme_en_boutique(monde):
	proprio = _perso()
	prop = _entrer(monde, proprio)
	e = _marchand(monde, proprio)
	client = _perso(_id="character:b", lieu=prop["_id"], inventaire=[{"item": "item:herbe", "poids": 1}])
	vue = _appel(monde, client, monde["rp"].atelier_choisir, None, {"employe_id": e["_id"]})
	assert vue["echange"] is True
	quotes = _quotes(monde, client)
	assert [v["item_id"] for v in quotes["vendables"]] == ["item:herbe"]
	avant = characters_util.money_to_cuivre(client)
	_appel(monde, client, monde["ru"].sell_item, None, {"index": 0, "item_id": "item:herbe"}, module="ru")
	assert characters_util.money_to_cuivre(client) > avant
	assert client["inventaire"] == []
	assert not e.get("caisse_cuivre")                        # payé comme en boutique, caisse intacte
	assert "flux_marchand" not in monde["docs"]["lieu:ville"]   # jamais le flux de la ville


def test_le_proprietaire_ne_vend_ni_nachete_a_son_marchand(monde):
	proprio = _perso(inventaire=[{"item": "item:herbe", "poids": 1}])
	_entrer(monde, proprio)
	e = _marchand(monde, proprio)
	vue = _appel(monde, proprio, monde["rp"].atelier_choisir, None, {"employe_id": e["_id"]})
	assert vue["echange"] is False
	assert _quotes(monde, proprio)["vendables"] == []
	with pytest.raises(HTTPException) as err:
		_appel(monde, proprio, monde["ru"].sell_item, None, {"index": 0, "item_id": "item:herbe"}, module="ru")
	assert err.value.status_code == 403


def test_le_proprietaire_confie_une_matiere(monde):
	proprio = _perso(inventaire=[{"item": "item:herbe", "poids": 1}])
	_entrer(monde, proprio)
	e = _marchand(monde, proprio)
	data = _appel(monde, proprio, monde["rp"].atelier_donner, None,
				  {"employe_id": e["_id"], "index": 0, "item_id": "item:herbe"})
	assert proprio["inventaire"] == [] and e["stock_matieres"] == {"herbe": 1}
	assert data["ateliers"][0]["matieres"] == [{"cle": "herbe", "qty": 1}]


def test_confier_et_reprendre_depuis_le_sac_d_un_compagnon(monde):
	proprio = _perso()
	_entrer(monde, proprio)
	e = _marchand(monde, proprio)
	av = _compagnon(monde, proprio, inventaire=[{"item": "item:herbe", "poids": 1}])
	_appel(monde, proprio, monde["rp"].atelier_donner, None,
		   {"employe_id": e["_id"], "index": 0, "item_id": "item:herbe", "compagnon_id": av["_id"]})
	assert av["inventaire"] == [] and e["stock_matieres"] == {"herbe": 1}

	e["stock_vente"] = [{"item_id": "item:elixir", "qty": 1}]
	data = _appel(monde, proprio, monde["rp"].atelier_reprendre, None,
				  {"employe_id": e["_id"], "item_id": "item:elixir", "compagnon_id": av["_id"]})
	assert [item_ref_id(r) for r in av["inventaire"]] == ["item:elixir"] and proprio["inventaire"] == []
	assert [d["nom"] for d in data["porteurs"][0]["inventaire"]] == ["Élixir"]


def test_confier_refuse_le_compagnon_d_autrui(monde):
	proprio = _perso()
	_entrer(monde, proprio)
	e = _marchand(monde, proprio)
	_compagnon(monde, _perso(_id="character:b"), inventaire=[{"item": "item:herbe", "poids": 1}])
	with pytest.raises(HTTPException) as err:
		_appel(monde, proprio, monde["rp"].atelier_donner, None,
			   {"employe_id": e["_id"], "index": 0, "item_id": "item:herbe", "compagnon_id": "aventurier:x"})
	assert err.value.status_code == 403


def test_comptoir_de_commande_adresse_le_marchand_choisi(monkeypatch, monde):
	"""`routers/commande._acces` traite le marchand choisi comme l'artisan : commande simple
	ouverte dès qu'il a un catalogue (ici l'élixir de sa recette)."""
	from routers import commande as rc
	monkeypatch.setattr(rc, "get_doc", monde["docs"].get)
	proprio = _perso()
	prop = _entrer(monde, proprio)
	e = _marchand(monde, proprio)
	client = _perso(_id="character:b", lieu=prop["_id"])
	_appel(monde, client, monde["rp"].atelier_choisir, None, {"employe_id": e["_id"]})
	monkeypatch.setattr(rc, "get_selected_character", lambda _u: client)
	_, lieu = rc._acces(None)
	assert lieu is e


# ── Négociant (« marchand pur », utils/negoce.py) ────────────────────────────────

CAILLOU = {"_id": "item:caillou", "type": "item", "nom": "Caillou", "categorie": "divers",
		   "sous_categorie": "caillou", "slots": [], "poids": 1.0, "rarete": "commun"}
COMPTOIR = {"_id": "lieu:comptoir", "type": "lieu", "categorie": "negociant", "label": "Le Comptoir",
			"lieu_parent": "lieu:ville"}


def test_negociant_de_ville_achete_tout_au_flux_ou_converti(monde):
	from utils import negoce
	monde["docs"].update({d["_id"]: json.loads(json.dumps(d)) for d in (CAILLOU, COMPTOIR)})
	client = _perso(lieu=COMPTOIR["_id"], inventaire=[{"item": "item:herbe", "poids": 1}, "item:caillou"])
	quotes = _quotes(monde, client)
	assert quotes["negociant"] is True
	assert quotes["commission"] == round(negoce.commission({"value": quotes["relation"]}) * 100)
	assert sorted(v["item_id"] for v in quotes["vendables"]) == ["item:caillou", "item:herbe"]
	attendu = next(v["prix_cuivre"] for v in quotes["vendables"] if v["item_id"] == "item:herbe")
	assert attendu == negoce.prix_rachat(HERBE, {"value": quotes["relation"]})

	avant = characters_util.money_to_cuivre(client)
	data = _appel(monde, client, monde["ru"].sell_item, None, {"index": 0, "item_id": "item:herbe"}, module="ru")
	assert characters_util.money_to_cuivre(client) == avant + attendu
	assert monde["docs"]["lieu:ville"]["flux_marchand"] == {"item:herbe": 1}   # l'alchimiste en a l'usage
	assert "commission" in data

	_appel(monde, client, monde["ru"].sell_item, None, {"index": 0, "item_id": "item:caillou"}, module="ru")
	assert monde["docs"]["lieu:ville"]["flux_marchand"] == {"item:herbe": 1}   # personne : converti
	assert client["inventaire"] == [] and not monde["docs"][COMPTOIR["_id"]].get("stock_vente")


def test_negociant_ne_marchande_pas_ce_qu_il_rachete(monde):
	monde["docs"][COMPTOIR["_id"]] = json.loads(json.dumps(COMPTOIR))
	client = _perso(lieu=COMPTOIR["_id"], inventaire=[{"item": "item:herbe", "poids": 1}])
	with pytest.raises(HTTPException) as err:
		_appel(monde, client, monde["ru"].marchander_item, None,
			   {"sens": "vente", "index": 0, "item_id": "item:herbe"}, module="ru")
	assert err.value.status_code == 403


def test_confier_au_negociant_du_bien_caisse_ou_flux(monde):
	from utils import negoce
	monde["docs"][CAILLOU["_id"]] = json.loads(json.dumps(CAILLOU))
	proprio = _perso(inventaire=["item:caillou", {"item": "item:herbe", "poids": 1}])
	prop = _entrer(monde, proprio)
	_marchand(monde, proprio)                       # l'alchimiste : SEUL consommateur du flux du bien
	cand = {"id": "n1", "amenagement": "bureau_marchand", "metier": "marchand", "prenom": "Jehan",
			"nom": "Lombard", "sex": "M", "race": "humain", "portrait": "x.jpg",
			"categorie": "negociant", "modele": proprietes.MODELE_PREFIXE + "negociant"}
	neg = proprietes.creer_employe(prop, cand, proprio)
	proprietes.engager(prop, neg)
	monde["docs"][neg["_id"]] = neg

	_appel(monde, proprio, monde["rp"].atelier_donner, None,
		   {"employe_id": neg["_id"], "index": 0, "item_id": "item:caillou"})
	assert neg["caisse_cuivre"] == negoce.prix_conversion(CAILLOU)
	_appel(monde, proprio, monde["rp"].atelier_donner, None,
		   {"employe_id": neg["_id"], "index": 0, "item_id": "item:herbe"})
	assert prop["flux_marchand"] == {"item:herbe": 1}
	assert "flux_marchand" not in monde["docs"]["lieu:ville"]   # jamais le flux de la ville


# ── Effets des aménagements ──────────────────────────────────────────────────────

def test_nuit_chez_soi_pose_le_reveil_et_resynchronise_la_fiche(monde):
	"""Le salon pose son effet à durée au réveil ; une seconde nuit le REMPLACE. La réponse
	porte le bilan et la fiche du dormeur (Convention §10)."""
	char = _perso()
	_entrer(monde, char)
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "salon"})
	data = _appel(monde, char, monde["ra"].passer_la_nuit, None, module="ra")
	assert [e.get("source_id") for e in char["effets_actifs"]] == ["amenagement:salon"]
	assert data["reveil"][0]["id"] == char["_id"] and data["reveil"][0]["effets"]
	assert data["fiches"][0]["id"] == char["_id"]
	assert any(e.get("source_id") == "amenagement:salon" for e in data["fiches"][0]["effets_actifs"])
	_appel(monde, char, monde["ra"].passer_la_nuit, None, module="ra")
	assert len(char["effets_actifs"]) == 1


def test_nuit_le_medecin_dissipe_le_poison(monde):
	char = _perso(effets_actifs=[{"sort_id": "sort:venin", "nom": "Venin", "regen_pv": -3, "restants": 9}])
	_entrer(monde, char)
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "salle_de_soins"})
	_engager(monde, char, "medecin")
	data = _appel(monde, char, monde["ra"].passer_la_nuit, None, module="ra")
	assert [e.get("source_id") or e.get("sort_id") for e in char["effets_actifs"]] == ["amenagement:salle_de_soins"]
	assert any("Venin" in t for t in data["reveil"][0]["effets"])


def test_nuit_ailleurs_aucun_reveil(monde):
	char = _perso(lieu="lieu:auberge")
	data = _appel(monde, char, monde["ra"].passer_la_nuit, None, module="ra")
	assert data["reveil"] == [] and "fiches" not in data and not char.get("effets_actifs")


def test_recolter_au_jardin_puis_attendre(monde):
	for i in ("item:Herbes_aromatiques", "item:Herbes_medicinales"):
		monde["docs"][i] = {"_id": i, "type": "item", "nom": i.split(":")[1], "poids": 0.1, "slots": []}
	char = _perso()
	_entrer(monde, char)
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "petit_jardin"})
	data = _appel(monde, char, monde["rp"].recolter, None, {"amenagement": "petit_jardin"})
	assert len(char["inventaire"]) == len(data["recolte"]) > 0
	assert data["recoltes"][0]["pret"] is False and data["inventaire_payload"]
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rp"].recolter, None, {"amenagement": "petit_jardin"})
	assert e.value.status_code == 409


def test_registre_releve_les_caisses_du_bien(monde):
	char = _perso()
	_entrer(monde, char)
	marchand = _marchand(monde, char)
	marchand["caisse_cuivre"] = 30
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rp"].registre_relever, None)
	assert e.value.status_code == 403                 # sans bureau, pas de registre
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "bureau"})
	avant = characters_util.money_to_cuivre(char)
	data = _appel(monde, char, monde["rp"].registre_relever, None)
	assert data["releve"] == 30 and characters_util.money_to_cuivre(char) == avant + 30
	assert marchand["caisse_cuivre"] == 0


def test_ecurie_laisser_puis_reprendre_une_monture(monde):
	bete = {"_id": "monture:a", "type": "monture", "statut": "acquise", "acquise_par": "character:a",
			"nom": "Rosse", "inventaire": [], "caracteristiques_current": dict(CARACTS)}
	monde["docs"][bete["_id"]] = bete
	char = _perso(montures=["monture:a"])
	_entrer(monde, char)
	with pytest.raises(HTTPException):
		_appel(monde, char, monde["rp"].ecurie_loger, None, {"monture_id": "monture:a"})   # pas d'écurie
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "cour_interieure"})
	data = _appel(monde, char, monde["rp"].ecurie_loger, None, {"monture_id": "monture:a"})
	assert bete["loge_a"] == char["lieu"] and [m["id"] for m in data["ecurie"]["logees"]] == ["monture:a"]
	assert data["ecurie"]["logeables"] == []
	data = _appel(monde, char, monde["rp"].ecurie_reprendre, None, {"monture_id": "monture:a"})
	assert "loge_a" not in bete and data["ecurie"]["logees"] == []


def test_coffre_de_la_bibliotheque_resynchronise_la_fiche(monde):
	char = _perso(inventaire=[{"item": "item:herbe", "poids": 1}])
	_entrer(monde, char)
	data = _appel(monde, char, monde["rp"].coffre_transferer, None,
				  {"sens": "vers_coffre", "index": 0, "item_id": "item:herbe"})
	assert "fiche" not in data
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "bibliotheque"})
	data = _appel(monde, char, monde["rp"].coffre_transferer, None,
				  {"sens": "vers_principal", "index": 0, "item_id": "item:herbe"})
	assert data["fiche"]["id"] == char["_id"]


def test_bibliothecaire_ouvre_le_scriptorium(monkeypatch, monde):
	from routers import scriptorium as rs
	char = _perso()
	prop = _entrer(monde, char)
	monkeypatch.setattr(rs, "get_doc", monde["docs"].get)
	monkeypatch.setattr(rs, "get_selected_character", lambda _u: char)
	with pytest.raises(HTTPException) as e:
		rs._acces_scriptorium(None)
	assert e.value.status_code == 403
	_appel(monde, char, monde["rp"].installer, None, {"amenagement": "bibliotheque"})
	_engager(monde, char, "bibliothecaire")
	_c, lieu = rs._acces_scriptorium(None)
	assert "scriptorium" in lieu["tags"] and "tags" not in monde["docs"][prop["_id"]]


def test_revente_suit_la_decoration(monde):
	char = _perso()
	_entrer(monde, char)
	sans = _appel(monde, char, monde["rp"].ici, None)["revente"]["prix"]
	data = _appel(monde, char, monde["rp"].installer, None, {"amenagement": "decoration"})
	assert data["revente"]["prix"] > sans
	deco = next(a for a in data["installes"] if a["id"] == "decoration")
	assert deco["effets"] and deco["actif"] is True and deco["poste_requis"] is False
