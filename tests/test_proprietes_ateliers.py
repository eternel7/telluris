"""Ateliers des propriétés : PNJ marchands employés (`utils/proprietes.py`) — logique pure.

Ce que ces tests verrouillent :
1. **Pas d'approvisionnement gratuit** : un marchand employé ne produit qu'à partir de ce
   qu'on lui confie (`donner`) et du flux de SA propriété.
2. **Le flux du lieu** : ce qu'un employé écoule nourrit l'atelier d'un autre employé du même
   bien — et jamais le `flux_marchand` de la ville.
3. **La caisse** : les ventes automatiques y tombent ; relevée, elle se vide ; pleine, elle
   interdit de céder le bien.
4. **Commandes** : simples pour tout marchand, sur mesure pour une grande maison seulement —
   tranché par les prédicats EXISTANTS de `utils/commande.py` appliqués à l'employé.
5. **Candidats** : fiche du marchand générique recopiée, nom tiré, un par poste libre.

Recettes et docs en mémoire (gabarit `tests/test_flux_pnj.py`), `random` neutralisé.
"""

import pytest

from models import character_stats
from utils import commande as commande_util
from utils import marche
from utils import proprietes


BLE = {"_id": "item:ble", "type": "item", "nom": "Blé", "categorie": "composant",
	   "sous_categorie": "ble", "slots": [], "poids": 1.0, "rarete": "commun"}
FARINE = {"_id": "item:farine", "type": "item", "nom": "Farine", "categorie": "composant",
		  "sous_categorie": "farine", "slots": [], "poids": 1.0, "rarete": "commun"}
PAIN = {"_id": "item:pain", "type": "item", "nom": "Pain", "categorie": "composant",
		"sous_categorie": "pain", "slots": [], "poids": 0.5, "rarete": "commun"}

RECETTES = [
	{"_id": "recette:farine", "type": "recette", "lieu_categorie": "moulin_test",
	 "objet_final": "farine", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "ble", "quantite": 2}]},
	{"_id": "recette:pain", "type": "recette", "lieu_categorie": "boulangerie_test",
	 "objet_final": "pain", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "farine", "quantite": 2}]},
]

VILLE = {"_id": "lieu:ville_test", "type": "lieu", "categorie": "ville", "flux_marchand": {"farine": 7}}
MODELE_MOULIN = {"_id": "pnj:marchand_moulin_test", "type": "pnj", "nom": "Maître Meunier",
				 "race": "nain", "portrait": "meunier.jpg"}
DOCS = {d["_id"]: d for d in (BLE, FARINE, PAIN, VILLE, MODELE_MOULIN)}

CAT = {
	"types": [{"id": "maison", "label": "Maison", "occupants_max": 2, "personnel_max": 3,
			   "stockage_kg": 50}],
	"amenagements": [
		{"id": "moulin", "nom": "Moulin", "types_autorises": ["maison"],
		 "capacite": {"postes": {"meunier": 1}},
		 "activite": {"metier": "meunier", "label": "Meunerie", "categories": ["moulin_test"]}},
		{"id": "loge_gardien", "nom": "Loge", "types_autorises": ["maison"],
		 "capacite": {"postes": {"gardien": 1}}, "effets": {"garde": True}},
	],
	"metiers": [{"id": "meunier", "label": "Meunier", "cout_embauche_cuivre": 10},
				{"id": "gardien", "label": "Gardien", "cout_embauche_cuivre": 5}],
	"reglages": {"candidats_duree_s": 100,
				 "vente_auto": {"proba": 1.0, "fraction": 1.0, "reserve": 1}},
}


class _Toujours:
	"""`rand` déterministe : toute demande est servie, les choix prennent le premier."""
	def random(self):
		return 0.0

	def choice(self, seq):
		return seq[0]


@pytest.fixture(autouse=True)
def _monde(monkeypatch):
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: DOCS.get(i))
	resoudre = lambda i: (dict(DOCS[i], item=i) if i in DOCS else None)
	monkeypatch.setattr(marche, "resolve_item_ref", resoudre)
	monkeypatch.setattr(proprietes, "resolve_item_ref", resoudre)
	monkeypatch.setattr(marche.random, "random", lambda: 0.0)
	monkeypatch.setattr(character_stats, "ATELIER_TRANSFO_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "APPRO_DEBIT_DEFAUT", 5)     # prouverait un appro parasite
	monkeypatch.setattr(character_stats, "VENTE_PNJ_REDISTRIB", 1.0)
	monkeypatch.setattr(character_stats, "FLUX_SURPLUS_PART", 0.0)
	monkeypatch.setattr(character_stats, "FLUX_PART_MAX", 1.0)
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION", {"grand_moulin_test": ["moulin_test"]})
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def propriete(**champs):
	p = {"_id": "propriete:maison_1", "type": "propriete", "type_propriete": "maison",
		 "mode": "achat", "statut": "possedee", "proprietaire": "character:a",
		 "lieu_parent": VILLE["_id"], "amenagements": ["moulin"], "employes": []}
	p.update(champs)
	return p


def atelier(categorie, **champs):
	prop = propriete()
	cand = {"id": "c1", "amenagement": "moulin", "metier": "meunier", "prenom": "Jehan",
			"nom": "Ferrant", "sex": "M", "race": "humain", "portrait": "x.jpg",
			"categorie": categorie, "modele": MODELE_PREFIXE_DE(categorie)}
	e = proprietes.creer_employe(prop, cand, {"_id": "character:a"})
	e.update(champs)
	return e


def MODELE_PREFIXE_DE(categorie):
	return proprietes.MODELE_PREFIXE + categorie


# ── Création ──────────────────────────────────────────────────────────────────────

def test_employe_marchand_a_la_forme_d_une_boutique():
	e = atelier("moulin_test")
	assert proprietes.est_atelier(e)
	assert e["categorie"] == "moulin_test" and e["stock_matieres"] == {} and e["stock_vente"] == []
	assert e["caisse_cuivre"] == 0 and e["lieu_parent"] == VILLE["_id"]
	assert e["propriete"] == "propriete:maison_1" and e["poste"] == "moulin"


def test_employe_non_marchand_n_est_pas_un_atelier():
	cand = {"id": "c", "amenagement": "loge_gardien", "metier": "gardien", "prenom": "A", "nom": "B"}
	e = proprietes.creer_employe(propriete(), cand, {"_id": "character:a"})
	assert not proprietes.est_atelier(e) and "stock_vente" not in e


# ── Matières confiées ─────────────────────────────────────────────────────────────

def test_donner_une_matiere_une_marchandise_ou_rien():
	e = atelier("moulin_test")
	assert proprietes.donner(e, BLE)[0] and e["stock_matieres"] == {"ble": 1}
	assert proprietes.donner(e, FARINE)[0]                      # ce qu'il produit : au rayon
	assert e["stock_vente"] == [{"item_id": "item:farine", "qty": 1}]
	ok, raison = proprietes.donner(e, PAIN)
	assert not ok and "usage" in raison


def test_racheter_a_un_visiteur_absorbe_comme_un_objet_confie():
	e = atelier("moulin_test")
	assert proprietes.racheter(e, BLE)[0] and e["stock_matieres"] == {"ble": 1}
	assert proprietes.racheter(e, FARINE)[0]
	assert e["stock_vente"] == [{"item_id": "item:farine", "qty": 1}]
	assert not proprietes.racheter(e, PAIN)[0]
	assert not e["caisse_cuivre"]                               # le visiteur n'est pas payé d'ici


def test_seul_le_maitre_traite_au_coffre():
	e = atelier("moulin_test")
	lire = {"propriete:maison_1": propriete()}.get
	assert proprietes.vend_au_proprietaire({"_id": "character:a"}, e, lire)
	assert not proprietes.vend_au_proprietaire({"_id": "character:b"}, e, lire)
	assert not proprietes.vend_au_proprietaire({"_id": "character:a"}, VILLE, lire)   # pas un atelier


def test_reprendre_un_produit():
	e = atelier("moulin_test", stock_vente=[{"item_id": "item:farine", "qty": 1}])
	assert proprietes.reprendre_produit(e, "item:farine") and e["stock_vente"] == []
	assert not proprietes.reprendre_produit(e, "item:farine")


# ── Production, ventes, caisse ────────────────────────────────────────────────────

def test_produire_sans_approvisionnement_gratuit():
	e = atelier("moulin_test")
	proprietes.produire(e, None, 1, CAT, prix_fn=lambda _i: 10, rand=_Toujours())
	# APPRO_DEBIT_DEFAUT = 5 : une boutique aurait reçu du blé ; l'employé, rien.
	assert e["stock_matieres"] == {} and e["stock_vente"] == [] and e["caisse_cuivre"] == 0


def test_produire_transforme_vend_et_encaisse():
	e = atelier("moulin_test", stock_matieres={"ble": 6})
	change, gain = proprietes.produire(e, None, 1, CAT, prix_fn=lambda _i: 10, rand=_Toujours())
	reserve = CAT["reglages"]["vente_auto"]["reserve"]
	# 6 blés → 3 farines ; tout part sauf la réserve, au prix injecté.
	assert change and gain == (3 - reserve) * 10 and e["caisse_cuivre"] == gain
	assert e["stock_vente"] == [{"item_id": "item:farine", "qty": reserve}]


def test_flux_du_lieu_entre_deux_marchands_jamais_celui_de_la_ville():
	prop = propriete()
	moulin = atelier("moulin_test", stock_matieres={"ble": 6})
	boulanger = atelier("boulangerie_test")
	flux = proprietes.flux_propriete(prop)
	proprietes.produire(moulin, flux, 1, CAT, prix_fn=lambda _i: 1, rand=_Toujours())
	assert flux["pool"].get("item:farine", 0) > 0 and flux["doc"] is prop
	proprietes.produire(boulanger, flux, 1, CAT, prix_fn=lambda _i: 1, rand=_Toujours())
	assert boulanger["stock_vente"] or boulanger["stock_matieres"], "le boulanger n'a rien reçu"
	marche.persister_flux(flux, lambda d: d)
	assert VILLE["flux_marchand"] == {"farine": 7}             # la ville n'a pas bougé


def test_relever_caisse_et_ceder():
	e = atelier("moulin_test", caisse_cuivre=42)
	prop = propriete(employes=[e["_id"]])
	assert not proprietes.peut_ceder(prop, [e])[0]
	assert proprietes.relever_caisse([e]) == 42 and e["caisse_cuivre"] == 0
	assert proprietes.peut_ceder(prop, [e])[0]


# ── Commandes : simples pour tous, sur mesure pour une grande maison ───────────────

def test_grande_maison_seule_fait_du_sur_mesure():
	simple, grand = atelier("moulin_test"), atelier("grand_moulin_test")
	assert not proprietes.grande_maison(simple) and proprietes.grande_maison(grand)
	assert not commande_util.lieu_fabrique_sur_mesure(simple)
	assert commande_util.lieu_fabrique_sur_mesure(grand)


# ── Marchand choisi ───────────────────────────────────────────────────────────────

def test_atelier_actif_de_cette_propriete_seulement():
	e = atelier("moulin_test")
	prop = propriete(employes=[e["_id"]])
	lire = {e["_id"]: e}.get
	char = {"_id": "character:b", "atelier_courant": e["_id"]}
	assert proprietes.atelier_actif(char, prop, lire) is e
	autre = propriete(_id="propriete:maison_2", employes=[e["_id"]])
	assert proprietes.atelier_actif(char, autre, lire) is None
	assert proprietes.atelier_actif({"_id": "character:b"}, prop, lire) is None


# ── Candidats ─────────────────────────────────────────────────────────────────────

def test_candidats_un_par_poste_libre_fiche_du_modele():
	prop = propriete(amenagements=["moulin", "loge_gardien"])
	cands = proprietes.generer_candidats(prop, CAT, [], DOCS.get, ["p.jpg"], rand=_Toujours())
	par_metier = {c["metier"]: c for c in cands}
	meunier = par_metier["meunier"]
	assert meunier["categorie"] == "moulin_test" and meunier["modele"] == MODELE_MOULIN["_id"]
	assert meunier["portrait"] == MODELE_MOULIN["portrait"] and meunier["race"] == MODELE_MOULIN["race"]
	assert meunier["nom"] != MODELE_MOULIN["nom"]                   # nom TIRÉ, pas le modèle
	assert par_metier["gardien"]["portrait"] == "p.jpg" and "categorie" not in par_metier["gardien"]


def test_candidats_sans_modele_ni_poste_libre():
	prop = propriete(amenagements=["moulin"])
	sans_modele = lambda i: None
	assert proprietes.generer_candidats(prop, CAT, [], sans_modele, [], rand=_Toujours()) == []
	e = atelier("moulin_test")
	assert proprietes.generer_candidats(prop, CAT, [e], DOCS.get, [], rand=_Toujours()) == []


def test_rafraichir_candidats_paresseux():
	prop = propriete()
	assert proprietes.rafraichir_candidats(prop, CAT, [], DOCS.get, [], now=0, rand=_Toujours())
	assert prop["candidats_expire_at"] == CAT["reglages"]["candidats_duree_s"]
	assert not proprietes.rafraichir_candidats(prop, CAT, [], DOCS.get, [], now=1, rand=_Toujours())
	# Poste pourvu entre-temps : le candidat rival disparaît sans re-tirage.
	assert proprietes.rafraichir_candidats(prop, CAT, [atelier("moulin_test")], DOCS.get, [], now=2)
	assert prop["candidats"] == []


def test_rafraichir_candidats_complete_un_poste_ouvert_apres_le_tirage():
	# Tableau tiré AVANT toute installation : vide, mais encore valide.
	prop = propriete(amenagements=[])
	assert proprietes.rafraichir_candidats(prop, CAT, [], DOCS.get, [], now=0, rand=_Toujours())
	assert prop["candidats"] == []
	proprietes.installer(prop, "loge_gardien")
	assert proprietes.rafraichir_candidats(prop, CAT, [], DOCS.get, [], now=1, rand=_Toujours())
	assert [c["metier"] for c in prop["candidats"]] == ["gardien"]
	premier = prop["candidats"][0]["id"]
	proprietes.installer(prop, "moulin")
	assert proprietes.rafraichir_candidats(prop, CAT, [], DOCS.get, [], now=2, rand=_Toujours())
	assert prop["candidats"][0]["id"] == premier                   # l'existant n'est pas re-tiré
	assert sorted(c["metier"] for c in prop["candidats"]) == ["gardien", "meunier"]
	assert prop["candidats_expire_at"] == CAT["reglages"]["candidats_duree_s"]
	# Tableau complet : plus rien ne bouge.
	assert not proprietes.rafraichir_candidats(prop, CAT, [], DOCS.get, [], now=3, rand=_Toujours())
