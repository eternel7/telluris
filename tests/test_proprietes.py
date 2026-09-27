"""Propriétés résidentielles (`utils/proprietes.py`) — logique pure, sans DB.

Ce que ces tests verrouillent :
1. **Aucune conversion de type** : rien, hors `creer_propriete`, n'écrit `type_propriete`.
2. **La contrainte de type vit dans la DONNÉE** (`types_autorises`) : une Maison n'installe
   pas une écurie réservée à la Demeure ; prérequis et doublons refusés.
3. **Capacités DÉRIVÉES** (type + aménagements), jamais stockées.
4. **Le vol** : possible chez un propriétaire sans gardien, impossible dès qu'un gardien est
   AU POSTE (la loge vide ne garde rien) ; une chambre louée est inviolable.
5. **Location paresseuse**, cession (aménagements conservés sur le bien cédé), zones.
6. Le catalogue LIVRÉ (`jsons/proprietes_a_importer.json`) respecte les interdictions du
   cahier des charges — relu depuis le fichier, jamais recopié.

Les accès DB passent par des `get_doc_fn` injectés ; les références d'items portent leur
poids d'instance (`{item, poids}`), `item_ref_weight` ne lit donc rien.
"""

import copy
import inspect
import json
import os

import pytest

from utils import proprietes


# ── Monde de test ─────────────────────────────────────────────────────────────────

CAT = {
	"types": [
		{"id": "chambre", "label": "Chambre", "rang": 1, "prix_cuivre": 100, "revente_facteur": 0.5,
		 "occupants_max": 1, "personnel_max": 1, "stockage_kg": 10,
		 "location": {"prix_cuivre": 5, "duree_s": 100}},
		{"id": "maison", "label": "Maison", "rang": 3, "prix_cuivre": 1000, "revente_facteur": 0.6,
		 "occupants_max": 2, "personnel_max": 2, "stockage_kg": 50},
		{"id": "demeure", "label": "Demeure", "rang": 4, "prix_cuivre": 5000, "revente_facteur": 0,
		 "occupants_max": 5, "personnel_max": 5, "stockage_kg": 100},
	],
	"amenagements": [
		{"id": "loge_gardien", "nom": "Loge", "types_autorises": ["chambre", "maison", "demeure"],
		 "cout_cuivre": 10, "capacite": {"postes": {"gardien": 1}}, "effets": {"garde": True}},
		{"id": "cave", "nom": "Cave", "types_autorises": ["maison"], "cout_cuivre": 10,
		 "capacite": {"stockage_kg": 30}},
		{"id": "chambres", "nom": "Chambres", "types_autorises": ["maison", "demeure"],
		 "cout_cuivre": 10, "capacite": {"occupants": 2}},
		{"id": "labo", "nom": "Laboratoire", "types_autorises": ["maison"], "cout_cuivre": 10,
		 "capacite": {"postes": {"alchimiste": 1}},
		 "activite": {"metier": "alchimiste", "label": "Alchimie"}},
		{"id": "ecurie", "nom": "Écurie", "types_autorises": ["demeure"], "cout_cuivre": 10},
		{"id": "recherche", "nom": "Recherche", "types_autorises": ["maison"], "cout_cuivre": 10,
		 "prerequis": ["labo"]},
	],
	"metiers": [
		{"id": "gardien", "label": "Gardien", "cout_embauche_cuivre": 5},
		{"id": "alchimiste", "label": "Alchimiste", "cout_embauche_cuivre": 5},
	],
}

VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville",
		 "zone_influences": [
			 {"x": 5, "y": 5, "w": 4, "h": 4, "rot": 0, "forme": "rectangle",
			  "zone": "zone:habitable_maison"},
			 {"x": 5, "y": 5, "w": 4, "h": 4, "rot": 0, "forme": "rectangle", "zone": "zone:foret"},
		 ]}
ZONES = {
	"zone:habitable_maison": {"_id": "zone:habitable_maison", "type": "zone_influence",
							  "type_propriete": "maison", "intensite_max": 0},
	"zone:foret": {"_id": "zone:foret", "type": "zone_influence", "intensite_max": 1},
}


def perso(**champs):
	base = {"_id": "character:a", "prenom": "Greta", "nom": "Hazgard", "inventaire": [],
			"groupe": [], "proprietes": []}
	base.update(champs)
	return base


def maison(**champs):
	p = proprietes.creer_propriete(CAT["types"][1], "lieu:ville",
								   {"lieu": "lieu:ville", "pos": [5, 5]}, perso(),
								   proprietes.MODE_ACHAT, now=1000)
	p.update(champs)
	return p


def chambre_louee(expire_at=2000, **champs):
	p = proprietes.creer_propriete(CAT["types"][0], "lieu:ville",
								   {"lieu": "lieu:auberge", "pos": [0, 0]}, perso(),
								   proprietes.MODE_LOCATION, now=1000)
	p["expire_at"] = expire_at
	p.update(champs)
	return p


def employe(metier, poste, prop):
	return {"_id": f"employe:{metier}_1", "type": "employe", "metier": metier, "poste": poste,
			"propriete": prop["_id"], "statut": proprietes.EMPLOYE_ACTIF}


# ── Type figé ─────────────────────────────────────────────────────────────────────

def test_aucune_fonction_ne_reecrit_le_type():
	"""Seule la création pose `type_propriete` : aucune conversion de type n'existe."""
	source = inspect.getsource(proprietes)
	ecritures = [l for l in source.splitlines()
				 if '"type_propriete"' in l and ":" in l and "get(" not in l and "==" not in l]
	assert ecritures == ['\t\t"type_propriete": type_id,']


def test_creation_et_lien():
	p = maison()
	assert p["type"] == proprietes.TYPE_DOC and p["type_propriete"] == "maison"
	assert p["statut"] == proprietes.POSSEDEE and p["proprietaire"] == "character:a"
	assert p["label"] == "Maison de Greta Hazgard"
	lien = proprietes.creer_lien(p)
	assert lien["_id"] == p["lien"] and lien["type"] == "connection"
	assert lien["nodes"] == [{"lieu": "lieu:ville", "pos": [5, 5]}, {"lieu": p["_id"], "pos": [0, 0]}]


# ── Aménagements ──────────────────────────────────────────────────────────────────

def test_contrainte_de_type():
	p = maison()
	ok, raison = proprietes.peut_installer(p, CAT, "ecurie")
	assert not ok and "Maison" in raison
	assert proprietes.peut_installer(p, CAT, "cave")[0]


def test_prerequis_et_doublon():
	p = maison()
	assert not proprietes.peut_installer(p, CAT, "recherche")[0]
	proprietes.installer(p, "labo")
	assert proprietes.peut_installer(p, CAT, "recherche")[0]
	assert not proprietes.peut_installer(p, CAT, "labo")[0]


def test_disponibles_filtre_type_doublon_prerequis():
	p = maison(amenagements=["cave"])
	ids = [a["id"] for a in proprietes.amenagements_disponibles(p, CAT)]
	assert ids == ["loge_gardien", "chambres", "labo"]


def test_chambre_louee_non_amenageable():
	assert not proprietes.peut_installer(chambre_louee(), CAT, "loge_gardien")[0]


# ── Capacités dérivées ────────────────────────────────────────────────────────────

def test_capacites_derivees():
	p = maison(amenagements=["cave", "chambres", "labo", "loge_gardien"])
	cap = proprietes.capacites(p, CAT)
	base = CAT["types"][1]
	assert cap["stockage_kg"] == base["stockage_kg"] + 30
	assert cap["occupants_max"] == base["occupants_max"] + 2
	assert cap["personnel_max"] == base["personnel_max"]
	assert cap["postes"] == {"alchimiste": 1, "gardien": 1}
	assert "capacites" not in p   # jamais stockées


# ── Personnel, activités, gardien ─────────────────────────────────────────────────

def test_engager_exige_un_poste_libre():
	p = maison()
	assert not proprietes.peut_engager(p, CAT, [], "alchimiste", "labo")[0]
	proprietes.installer(p, "labo")
	assert proprietes.peut_engager(p, CAT, [], "alchimiste", "labo")[0]
	e = employe("alchimiste", "labo", p)
	assert not proprietes.peut_engager(p, CAT, [e], "alchimiste", "labo")[0]


def test_plafond_de_personnel_du_type():
	p = maison(amenagements=["labo", "loge_gardien"])
	deja = [employe("x", "?", p) for _ in range(CAT["types"][1]["personnel_max"])]
	ok, raison = proprietes.peut_engager(p, CAT, deja, "gardien", "loge_gardien")
	assert not ok and "personnel" in raison


def test_creer_employe_attache_a_la_propriete():
	p = maison(amenagements=["labo"])
	e = proprietes.creer_employe(p, CAT["metiers"][1], "labo", perso())
	assert e["propriete"] == p["_id"] and e["poste"] == "labo" and e["metier"] == "alchimiste"
	proprietes.engager(p, e)
	assert proprietes.employes_effectifs(p, {e["_id"]: e}.get) == [e]


def test_activite_exercee_seulement_avec_le_pnj():
	p = maison(amenagements=["labo"])
	assert proprietes.activites(p, CAT, [])[0]["exercee"] is False
	acts = proprietes.activites(p, CAT, [employe("alchimiste", "labo", p)])
	assert acts[0]["exercee"] is True and acts[0]["label"] == "Alchimie"


def test_gardien_present_exige_loge_et_employe():
	p = maison()
	g = employe("gardien", "loge_gardien", p)
	assert not proprietes.gardien_present(p, CAT, [g])       # loge non installée
	proprietes.installer(p, "loge_gardien")
	assert not proprietes.gardien_present(p, CAT, [])        # loge vide
	assert proprietes.gardien_present(p, CAT, [g])


# ── Accès et vol ──────────────────────────────────────────────────────────────────

def test_roles_achat():
	p = maison()
	assert proprietes.role_de(perso(), p) == proprietes.PROPRIETAIRE
	assert proprietes.role_de(perso(_id="character:b"), p) == proprietes.VISITEUR
	assert proprietes.acces_propriete(perso(_id="character:b"), p)[0]


def test_vol_possible_sans_gardien_impossible_avec():
	p = maison()
	assert proprietes.peut_retirer(proprietes.VISITEUR, p, gardien=False)[0]
	assert not proprietes.peut_retirer(proprietes.VISITEUR, p, gardien=True)[0]
	assert not proprietes.peut_deposer(proprietes.VISITEUR, p, CAT, {"item": "x", "poids": 1})[0]


def test_chambre_louee_inviolable():
	p = chambre_louee()
	autre = perso(_id="character:b")
	assert proprietes.role_de(autre, p, now=1500) is None
	assert not proprietes.acces_propriete(autre, p, now=1500)[0]
	assert proprietes.role_de(perso(), p, now=1500) == proprietes.LOCATAIRE


def test_location_expire_paresseusement():
	p = chambre_louee(expire_at=2000)
	assert not proprietes.traiter_expiration_location(p, now=1999)
	assert proprietes.traiter_expiration_location(p, now=2000)
	assert p["statut"] == proprietes.EXPIREE
	# Le locataire garde l'accès à ses affaires, mais n'y dort plus.
	assert proprietes.role_de(perso(), p, now=3000) == proprietes.ANCIEN_LOCATAIRE
	assert proprietes.peut_retirer(proprietes.ANCIEN_LOCATAIRE, p, False)[0]
	assert not proprietes.peut_dormir(perso(), p, now=3000)


def test_prolonger_ne_perd_jamais_de_temps():
	p = chambre_louee(expire_at=2000)
	proprietes.prolonger_location(p, 100, now=1500)
	assert p["expire_at"] == 2100
	p["statut"] = proprietes.EXPIREE
	proprietes.prolonger_location(p, 100, now=5000)
	assert p["expire_at"] == 5100 and p["statut"] == proprietes.LOUEE


def test_nuit_chez_soi():
	assert proprietes.peut_dormir(perso(), maison())
	assert not proprietes.peut_dormir(perso(_id="character:b"), maison())


# ── Coffre ────────────────────────────────────────────────────────────────────────

def test_depot_borne_par_le_stockage_derive():
	p = maison()
	plafond = proprietes.capacites(p, CAT)["stockage_kg"]
	assert proprietes.peut_deposer(proprietes.PROPRIETAIRE, p, CAT, {"item": "x", "poids": plafond})[0]
	assert not proprietes.peut_deposer(proprietes.PROPRIETAIRE, p, CAT,
									   {"item": "x", "poids": plafond + 1})[0]
	proprietes.installer(p, "cave")
	assert proprietes.peut_deposer(proprietes.PROPRIETAIRE, p, CAT,
								   {"item": "x", "poids": plafond + 1})[0]


def test_deposer_retirer():
	c = perso(inventaire=[{"item": "item:a", "poids": 2}])
	p = maison()
	proprietes.deposer(c, p, 0)
	assert c["inventaire"] == [] and p["coffre"] == [{"item": "item:a", "poids": 2}]
	assert proprietes.poids_coffre(p) == 2
	proprietes.retirer(c, p, 0)
	assert p["coffre"] == [] and c["inventaire"] == [{"item": "item:a", "poids": 2}]


# ── Possession et cession ─────────────────────────────────────────────────────────

def test_une_seule_residence():
	c = perso()
	a, b = maison(), maison()
	assert proprietes.occuper(c, a)[0] and c["residence"] == a["_id"]
	assert proprietes.occuper(c, b)[0] and c["residence"] == b["_id"]
	assert not proprietes.quitter(c, a)[0]
	assert not proprietes.occuper(perso(_id="character:b"), a)[0]


def test_ceder_garde_les_amenagements_et_renvoie_le_personnel():
	c = perso()
	p = maison(amenagements=["cave", "labo"])
	proprietes.acquerir(c, p, 1000)
	c["residence"] = p["_id"]
	e = employe("alchimiste", "labo", p)
	p["employes"] = [e["_id"]]
	proprietes.ceder(c, p, proprietes.VENDUE, [e])
	assert p["amenagements"] == ["cave", "labo"]
	assert p["statut"] == proprietes.VENDUE and p["proprietaire"] is None
	assert e["statut"] == proprietes.EMPLOYE_RENVOYE and p["employes"] == []
	assert c["proprietes"] == [] and c["residence"] is None
	assert not proprietes.acces_propriete(c, p)[0]


def test_ceder_refuse_coffre_ou_hebergés():
	assert not proprietes.peut_ceder(maison(coffre=[{"item": "x", "poids": 1}]))[0]
	assert not proprietes.peut_ceder(maison(heberges=["aventurier:x"]))[0]
	assert proprietes.peut_ceder(maison())[0]


def test_revente_type_et_cite():
	maison_def, demeure_def = CAT["types"][1], CAT["types"][2]
	assert proprietes.revente_autorisee(maison_def, VILLE)[0]
	assert not proprietes.revente_autorisee(demeure_def, VILLE)[0]      # facteur 0
	assert not proprietes.revente_autorisee(maison_def, {"proprietes": {"revente": False}})[0]
	assert proprietes.prix_revente(maison_def) == round(
		maison_def["prix_cuivre"] * maison_def["revente_facteur"])


def test_proprietes_de_preuve_d_appartenance():
	c = perso()
	p = maison()
	proprietes.acquerir(c, p, 1000)
	docs = {p["_id"]: p}
	assert proprietes.proprietes_de(c, docs.get) == [p]
	p["proprietaire"] = "character:b"
	assert proprietes.proprietes_de(c, docs.get) == []


# ── Compagnons hébergés ───────────────────────────────────────────────────────────

def test_heberger_puis_reprendre(monkeypatch):
	monkeypatch.setattr(proprietes.recrutement, "taille_max_groupe", lambda: 2)
	c = perso(groupe=["aventurier:x"])
	av = {"_id": "aventurier:x", "statut": "embauche", "embauche_par": "character:a"}
	p = maison()
	assert proprietes.heberger(c, p, CAT, av)[0]
	assert c["groupe"] == [] and av["loge_a"] == p["_id"] and p["heberges"] == ["aventurier:x"]
	assert proprietes.heberges_effectifs(c, p, {av["_id"]: av}.get) == [av]
	assert proprietes.reprendre(c, p, av, {av["_id"]: av}.get)[0]
	assert c["groupe"] == ["aventurier:x"] and "loge_a" not in av and p["heberges"] == []


def test_heberger_borne_par_les_occupants():
	p = maison()
	places = proprietes.capacites(p, CAT)["occupants_max"]
	c = perso(residence=p["_id"], groupe=[f"aventurier:{i}" for i in range(places)])
	avs = [{"_id": f"aventurier:{i}", "statut": "embauche", "embauche_par": "character:a"}
		   for i in range(places)]
	# Le résident compte : il reste `places - 1` lits.
	resultats = [proprietes.heberger(c, p, CAT, av)[0] for av in avs]
	assert resultats == [True] * (places - 1) + [False]


# ── Zones habitables ──────────────────────────────────────────────────────────────

def test_achetable_dans_la_zone_seulement():
	lire = ZONES.get
	assert proprietes.types_achetables_ici(VILLE, {"x": 5, "y": 5}, lire) == ["maison"]
	assert proprietes.types_achetables_ici(VILLE, {"x": 30, "y": 30}, lire) == []
	pas_ville = dict(VILLE, categorie="auberge")
	assert proprietes.types_achetables_ici(pas_ville, {"x": 5, "y": 5}, lire) == []


# ── Le catalogue LIVRÉ ────────────────────────────────────────────────────────────

CHEMIN_JSON = os.path.join(os.path.dirname(__file__), "..", "jsons", "proprietes_a_importer.json")


@pytest.fixture(scope="module")
def livre():
	with open(CHEMIN_JSON, encoding="utf-8") as f:
		docs = json.load(f)["docs"]
	par_id = {d["_id"]: d for d in docs}
	cat = proprietes.catalogue(par_id.get)
	return cat, par_id


def test_livre_cinq_types_dans_l_ordre(livre):
	cat, _ = livre
	assert [t["id"] for t in sorted(cat["types"], key=lambda t: t["rang"])] == \
		["chambre", "logement", "maison", "demeure", "domaine"]


def test_livre_une_zone_habitable_par_type(livre):
	cat, par_id = livre
	for t in cat["types"]:
		z = par_id[f"zone:habitable_{t['id']}"]
		assert z["type"] == "zone_influence" and z["type_propriete"] == t["id"]
		assert z["intensite_max"] == 0   # aucune incidence sur les tirages d'événements


def test_livre_chambre_sans_personnel_sauf_gardien(livre):
	"""Interdictions de la Chambre : ni atelier, ni cuisine, ni personnel permanent — la
	loge du gardien est la seule exception, ouverte à TOUS les types."""
	cat, _ = livre
	for a in proprietes.amenagements_du_type(cat, "chambre"):
		postes = (a.get("capacite") or {}).get("postes") or {}
		assert not postes or a["id"] == "loge_gardien", a["id"]
	gardien = proprietes.amenagement_def(cat, "loge_gardien")
	assert set(gardien["types_autorises"]) == {t["id"] for t in cat["types"]}
	assert gardien["effets"]["garde"] is True


def test_livre_references_coherentes(livre):
	cat, _ = livre
	metiers = {m["id"] for m in cat["metiers"]}
	ids = [a["id"] for a in cat["amenagements"]]
	assert len(ids) == len(set(ids))
	types = {t["id"] for t in cat["types"]}
	for a in cat["amenagements"]:
		assert set(a["types_autorises"]) <= types, a["id"]
		assert set((a.get("capacite") or {}).get("postes") or {}) <= metiers, a["id"]
		for p in a.get("prerequis") or []:
			assert set(a["types_autorises"]) <= set(proprietes.amenagement_def(cat, p)["types_autorises"])


def test_livre_seule_la_chambre_se_loue(livre):
	cat, _ = livre
	assert [t["id"] for t in cat["types"] if proprietes.location_de(t)] == ["chambre"]


def test_livre_images_presentes(livre):
	"""/play lève 404 sur une image introuvable : chaque type doit en pointer une réelle."""
	cat, _ = livre
	racine = os.path.join(os.path.dirname(__file__), "..", "templates", "resources", "towns")
	for t in cat["types"]:
		assert os.path.exists(os.path.join(racine, t["image"])), t["image"]
