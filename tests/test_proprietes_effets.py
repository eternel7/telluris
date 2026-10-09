"""Effets des aménagements de propriété (`utils/proprietes.py` § Effets) — logique pure.

Ce que ces tests verrouillent :
1. **NON-CUMUL.** Un réveil REMPLACE celui de la nuit précédente (clé `amenagement:<id>`, même
   d'un autre bien) ; dans le catalogue LIVRÉ, deux aménagements d'un même type ne touchent
   jamais le même terme ; un consommable plus fort l'emporte (`cumul_effets`, meilleur seul).
   Les effets du bien sont des états (revente, candidats, vol limité) : le meilleur, jamais une somme.
2. **`effets_poste` exige l'employé au poste** ; une salle à manger exige un cuisinier en cuisine.
3. **Dormeurs bornés par les places** : personnage, hébergés, puis compagnons dans l'ordre.
4. Le médecin retire les malus PURS, jamais un effet mixte choisi par le joueur.
5. Bibliothèque : scriptorium par VUE (rien de stocké), grimoires du coffre lisibles chez soi.
6. Écurie : la monture laissée ne suit plus le groupe mais reste dans le plafond du troupeau.
7. Récolte une fois par délai ; vol limité à une fraction par fenêtre.

Catalogue : le fichier LIVRÉ (`jsons/proprietes_a_importer.json`), relu, jamais recopié.
"""

import json
import os
import random

import pytest

from utils import consommables
from utils import montures
from utils import proprietes
from utils import recrutement
from utils import sorts as sorts_util

CHEMIN_JSON = os.path.join(os.path.dirname(__file__), "..", "jsons", "proprietes_a_importer.json")
with open(CHEMIN_JSON, encoding="utf-8") as _f:
	LIVRE = {d["_id"]: d for d in json.load(_f)["docs"]}
CAT = proprietes.catalogue(LIVRE.get)


def adef(am_id):
	return proprietes.amenagement_def(CAT, am_id)


def perso(**champs):
	base = {"_id": "character:a", "type": "character", "prenom": "Greta", "nom": "Hazgard",
			"inventaire": [], "groupe": [], "montures": [], "proprietes": [], "effets_actifs": []}
	base.update(champs)
	return base


def compagnon(n, **champs):
	base = {"_id": f"aventurier:{n}", "type": "aventurier", "prenom": f"C{n}", "nom": "",
			"statut": "embauche", "embauche_par": "character:a", "effets_actifs": []}
	base.update(champs)
	return base


def bien(type_id, *amenagements, proprio="character:a"):
	p = proprietes.creer_propriete(proprietes.type_def(CAT, type_id), "lieu:ville",
								   {"lieu": "lieu:ville", "pos": [5, 5]}, perso(_id=proprio),
								   proprietes.MODE_ACHAT, now=1000)
	p["amenagements"] = list(amenagements)
	return p


def employe(metier, poste, prop, n=1):
	return {"_id": f"employe:{metier}_{n}", "type": "employe", "metier": metier, "poste": poste,
			"propriete": prop["_id"], "statut": proprietes.EMPLOYE_ACTIF}


def sources(doc):
	return [consommables.cle_source(e) for e in doc.get("effets_actifs") or []]


# ── Catalogue livré ──────────────────────────────────────────────────────────────

def _termes(bloc):
	return set((bloc or {}).get("buffs") or {}) | {
		k for k in ("regen_pv", "regen_pm", "esquive", "fidele") if (bloc or {}).get(k)}


def test_livre_reveil_jamais_deux_fois_le_meme_terme_par_type():
	"""Le meilleur bonus seul compte : deux aménagements d'un même type sur le même terme,
	c'en serait un payé pour rien."""
	for t in CAT["types"]:
		for cle in ("reveil", "reveil_montures"):
			vus = {}
			for a in proprietes.amenagements_du_type(CAT, t["id"]):
				for bloc in (a.get("effets") or {}, a.get("effets_poste") or {}):
					for terme in _termes(bloc.get(cle)):
						assert terme not in vus, (t["id"], cle, terme, vus.get(terme), a["id"])
						vus[terme] = a["id"]


def test_livre_effet_de_poste_a_un_poste_a_tenir():
	for a in CAT["amenagements"]:
		if a.get("effets_poste"):
			metier = (a.get("activite") or {}).get("metier")
			assert metier in ((a.get("capacite") or {}).get("postes") or {}), a["id"]
			assert proprietes.metier_def(CAT, metier), a["id"]


def test_livre_chaque_effet_a_un_duree_ou_est_un_etat():
	"""Rien ne s'accumule sans borne : un réveil a une durée > 0 ; le reste est un état du bien."""
	etats = {"garde", "vol_limite", "revente_bonus", "registre", "grimoires_coffre", "scriptorium",
			 "releve_auto", "candidats_bonus", "recolte", "dissipe_malus"}
	for a in CAT["amenagements"]:
		for bloc in (a.get("effets") or {}, a.get("effets_poste") or {}):
			for cle, val in bloc.items():
				if cle in ("reveil", "reveil_montures"):
					assert int(val["duree"]) > 0, a["id"]
				else:
					assert cle in etats, (a["id"], cle)
			if "recolte" in bloc:
				assert int(bloc["recolte"]["delai_s"]) > 0, a["id"]


def test_livre_tout_amenagement_sans_capacite_a_desormais_un_effet():
	"""L'objet de la passe : plus d'aménagement installable pour rien (ni capacité, ni poste
	utile, ni effet)."""
	for a in CAT["amenagements"]:
		cap = a.get("capacite") or {}
		utile = (cap.get("stockage_kg") or cap.get("occupants") or cap.get("ecurie")
				 or a.get("effets") or a.get("effets_poste")
				 or ((a.get("activite") or {}).get("categories")))
		assert utile, a["id"]
		assert proprietes.textes_effets(a, CAT) or cap.get("stockage_kg") or cap.get("occupants") \
			or (a.get("activite") or {}).get("categories"), a["id"]


# ── Effets actifs : installation vs poste ────────────────────────────────────────

def test_effet_de_poste_attend_l_employe():
	p = bien("demeure", "infirmerie")
	assert not proprietes.effet_actif(p, CAT, [], "dissipe_malus")
	assert proprietes.effet_actif(p, CAT, [employe("medecin", "infirmerie", p)], "dissipe_malus")
	# Un employé d'un AUTRE métier, ou à un autre poste, ne compte pas.
	assert not proprietes.effet_actif(p, CAT, [employe("garde", "infirmerie", p)], "dissipe_malus")


def test_dormeurs_bornes_par_les_places():
	"""Logement : 2 places — le personnage, puis le premier hébergé ; les compagnons du groupe
	viennent après les hébergés."""
	p = bien("logement")
	moi, h, c1, c2 = perso(), compagnon(1), compagnon(2), compagnon(3)
	assert proprietes.dormeurs(moi, p, CAT, [c1, c2], [h]) == [moi, h]
	assert proprietes.dormeurs(moi, p, CAT, [c1, c2], []) == [moi, c1]
	p["amenagements"] = ["lit_supplementaire"]
	assert proprietes.dormeurs(moi, p, CAT, [c1, c2], []) == [moi, c1, c2]


def test_reveil_remplace_et_ne_s_empile_jamais():
	p = bien("maison", "salon")
	moi = perso()
	proprietes.appliquer_reveil(p, CAT, [], [moi], [])
	moi["effets_actifs"][0]["restants"] = 1
	proprietes.appliquer_reveil(p, CAT, [], [moi], [])
	assert sources(moi) == ["amenagement:salon"]
	assert moi["effets_actifs"][0]["restants"] == adef("salon")["effets"]["reveil"]["duree"]
	# Le même aménagement dans un AUTRE bien : même clé, toujours une seule entrée.
	proprietes.appliquer_reveil(bien("maison", "salon"), CAT, [], [moi], [])
	assert sources(moi) == ["amenagement:salon"]


def test_reveil_ne_l_emporte_pas_sur_un_consommable_plus_fort():
	p = bien("maison", "salle_entrainement")
	moi = perso(effets_actifs=[{"item_id": "item:boeuf", "buffs": {"F": 5}, "restants": 10}])
	proprietes.appliquer_reveil(p, CAT, [], [moi], [])
	assert len(moi["effets_actifs"]) == 2
	assert consommables.cumul_effets(moi["effets_actifs"])["buffs"]["F"] == 5   # le meilleur seul


def test_salle_a_manger_exige_un_cuisinier_en_cuisine():
	p = bien("maison", "salle_a_manger", "grande_cuisine")
	moi = perso()
	proprietes.appliquer_reveil(p, CAT, [], [moi], [])
	assert sources(moi) == []
	proprietes.appliquer_reveil(p, CAT, [employe("cuisinier", "grande_cuisine", p)], [moi], [])
	assert sources(moi) == ["amenagement:salle_a_manger"]


def test_bien_loge_pour_les_compagnons_seulement():
	p = bien("maison", "chambre_domestique")
	moi, c = perso(), compagnon(1)
	bilan = proprietes.appliquer_reveil(p, CAT, [employe("domestique", "chambre_domestique", p)], [moi, c], [])
	assert sources(moi) == [] and sources(c) == ["amenagement:chambre_domestique"]
	assert c["effets_actifs"][0]["fidele"] is True and list(bilan) == [c["_id"]]


def test_compagnon_bien_loge_ne_part_pas(monkeypatch):
	c = compagnon(1, effets_actifs=[{"source_id": "amenagement:x", "fidele": True, "restants": 3}])
	moi = perso(groupe=[c["_id"]], affinites={c["_id"]: 0})
	monkeypatch.setattr(recrutement, "groupe_effectif", lambda ch, g=None: [c])
	assert recrutement.departs_volontaires(moi, None) == []
	c["effets_actifs"] = []
	assert recrutement.departs_volontaires(moi, None) == [c]


def test_medecin_retire_les_malus_purs_seulement():
	poison = {"sort_id": "sort:venin", "nom": "Venin", "regen_pv": -3, "restants": 4}
	malediction = {"sort_id": "sort:mal", "nom": "Malédiction", "buffs": {"F": -5}, "restants": 4}
	mixte = {"item_id": "item:Bougie_noire", "nom": "Bougie noire", "buffs": {"Vol": 8, "Ch": -5}, "restants": 4}
	vol = {"sort_id": "sort:icare", "nom": "Vol", "vol": 1, "regen_pm": -1, "restants": 4}
	moi = perso(effets_actifs=[poison, malediction, mixte, vol])
	p = bien("maison", "salle_de_soins")
	bilan = proprietes.appliquer_reveil(p, CAT, [employe("medecin", "salle_de_soins", p)], [moi], [])
	assert [consommables.cle_source(e) for e in moi["effets_actifs"]] == [
		"item:Bougie_noire", "sort:icare", "amenagement:salle_de_soins"]
	assert "✚ Venin dissipé" in bilan[moi["_id"]] and "✚ Malédiction dissipé" in bilan[moi["_id"]]


def test_infirmerie_soigne_aussi_les_montures():
	p = bien("demeure", "infirmerie")
	bete = {"_id": "monture:a", "type": "monture", "effets_actifs": [{"sort_id": "x", "regen_pv": -2, "restants": 3}]}
	proprietes.appliquer_reveil(p, CAT, [employe("medecin", "infirmerie", p)], [perso()], [bete])
	assert sources(bete) == ["amenagement:infirmerie"]


def test_palefrenier_au_reveil_des_montures_seulement():
	p = bien("demeure", "ecurie_limitee")
	moi, bete = perso(), {"_id": "monture:a", "type": "monture", "effets_actifs": []}
	proprietes.appliquer_reveil(p, CAT, [employe("palefrenier", "ecurie_limitee", p)], [moi], [bete])
	assert sources(moi) == [] and sources(bete) == ["amenagement:ecurie_limitee"]


# ── Ce que le bien ouvre ─────────────────────────────────────────────────────────

def test_scriptorium_par_vue_jamais_stocke():
	p = bien("maison", "bibliotheque")
	e = employe("bibliothecaire", "bibliotheque", p)
	p["employes"] = [e["_id"]]
	docs = dict(LIVRE, **{e["_id"]: e})
	from utils import scriptorium
	assert proprietes.lieu_effectif(p, lambda i: None if i == e["_id"] else docs.get(i)) is p
	vue = proprietes.lieu_effectif(p, docs.get)
	assert scriptorium.lieu_est_scriptorium(vue) and not scriptorium.lieu_est_scriptorium(p)
	assert "tags" not in p
	lieu = {"_id": "lieu:x", "type": "lieu"}
	assert proprietes.lieu_effectif(lieu, docs.get) is lieu


def test_grimoires_du_coffre_lisibles_chez_soi():
	p = bien("maison", "bibliotheque")
	grimoire = {"_id": "item:grimoire_feu", "sous_categorie": "grimoire", "sorts": ["sort:feu"]}
	p["coffre"] = ["item:grimoire_feu"]
	moi = perso(lieu=p["_id"], groupe=["aventurier:1"])
	c = compagnon(1)
	docs = dict(LIVRE, **{p["_id"]: p, moi["_id"]: moi, c["_id"]: c})
	assert proprietes.refs_bibliotheque(moi, docs.get) == ["item:grimoire_feu"]
	assert proprietes.refs_bibliotheque(c, docs.get) == ["item:grimoire_feu"]
	refs = proprietes.refs_bibliotheque(moi, docs.get)
	assert sorts_util.grimoire_pour(moi, "sort:feu", {"item:grimoire_feu": grimoire}.get, refs) is grimoire
	assert sorts_util.grimoire_pour(moi, "sort:feu", {"item:grimoire_feu": grimoire}.get) is None
	# Un visiteur, un compagnon d'autrui, un bien sans bibliothèque : rien.
	assert proprietes.refs_bibliotheque(perso(_id="character:b", lieu=p["_id"]), docs.get) == []
	assert proprietes.refs_bibliotheque(compagnon(9), docs.get) == []
	p["amenagements"] = []
	assert proprietes.refs_bibliotheque(moi, docs.get) == []


def test_revente_decoration_meilleur_bonus_seul():
	tdef = proprietes.type_def(CAT, "maison")
	p = bien("maison")
	p["prix_paye"] = 1000
	base = proprietes.prix_revente(tdef, p, CAT)
	p["amenagements"] = ["decoration"]
	bonus = adef("decoration")["effets"]["revente_bonus"]
	assert proprietes.prix_revente(tdef, p, CAT) == round(1000 * (tdef["revente_facteur"] + bonus))
	assert proprietes.prix_revente(tdef, p, CAT) > base
	# Sans catalogue (appelant d'avant) : inchangé. Type invendable : le reste.
	assert proprietes.prix_revente(tdef, p) == base
	assert proprietes.prix_revente(dict(tdef, revente_facteur=0), p, CAT) == 0


def test_salle_de_gestion_un_candidat_de_plus_par_poste():
	p = bien("domaine", "bureau_administratif", "salle_gestion", "loge_gardien")
	sans = proprietes.generer_candidats(p, CAT, [], LIVRE.get, ["p.jpg"], random.Random(1))
	assert [c["metier"] for c in sans].count("gardien") == 1
	intendant = employe("intendant", "salle_gestion", p)
	avec = proprietes.generer_candidats(p, CAT, [intendant], LIVRE.get, ["p.jpg"], random.Random(1))
	assert [c["metier"] for c in avec].count("gardien") == 1 + adef("salle_gestion")["effets_poste"]["candidats_bonus"]


def test_releve_auto_et_registre():
	p = bien("domaine", "bureau_administratif", "bureau")
	assert not proprietes.releve_auto(p, CAT, [])
	assert proprietes.releve_auto(p, CAT, [employe("intendant", "bureau_administratif", p)])
	p2 = bien("maison", "bureau")
	assert proprietes.registre(p2, CAT) and not proprietes.registre(bien("maison"), CAT)


def test_garde_du_domaine_protege_le_coffre():
	p = bien("domaine", "poste_de_garde")
	assert not proprietes.gardien_present(p, CAT, [])
	assert proprietes.gardien_present(p, CAT, [employe("garde", "poste_de_garde", p)])


# ── Vol limité ───────────────────────────────────────────────────────────────────

def test_dispositifs_defensifs_une_fraction_par_fenetre():
	p = bien("domaine", "poste_de_garde", "dispositifs_defensifs")
	p["coffre"] = [{"item": f"item:{i}", "poids": 10} for i in range(8)]   # 80 kg
	limite = proprietes.vol_limite(p, CAT, [])
	fraction, delai = limite["fraction"], limite["delai_s"]
	pris = 0
	while proprietes.vol_coffre_autorise(p, limite, p["coffre"][0], now=100)[0]:
		proprietes.noter_vol_coffre(p, limite, p["coffre"][0], now=100)
		p["coffre"].pop(0)
		pris += 10
	assert pris == int(80 * fraction)
	# Caisse : une part, une seule fois par fenêtre.
	assert proprietes.fraction_caisse_volable(p, limite, now=100) == fraction
	assert proprietes.fraction_caisse_volable(p, limite, now=100) == 0
	# La fenêtre se rouvre après le délai, mesurée sur ce qui reste.
	assert proprietes.vol_coffre_autorise(p, limite, p["coffre"][0], now=100 + delai)[0]
	assert proprietes.vol_limite(bien("domaine"), CAT, []) is None


def test_relever_caisse_partielle():
	ateliers = [{"caisse_cuivre": 100}, {"caisse_cuivre": 7}]
	assert proprietes.relever_caisse(ateliers, 0.25) == 25 + 1
	assert [a["caisse_cuivre"] for a in ateliers] == [75, 6]
	assert proprietes.relever_caisse(ateliers) == 81 and ateliers[0]["caisse_cuivre"] == 0


# ── Écurie ───────────────────────────────────────────────────────────────────────

def test_ecurie_la_monture_reste_dans_le_plafond():
	p = bien("maison", "cour_interieure")
	bete = {"_id": "monture:a", "type": "monture", "statut": "acquise", "acquise_par": "character:a", "inventaire": []}
	moi = perso(montures=["monture:a"])
	lire = {bete["_id"]: bete}.get
	assert proprietes.capacites(p, CAT)["ecurie"] == adef("cour_interieure")["capacite"]["ecurie"]
	assert proprietes.loger_monture(moi, p, CAT, bete)[0]
	assert montures.montures_effectives(moi, lire) == []
	assert montures.montures_possedees(moi, lire) == [bete]
	assert proprietes.montures_logees(moi, p, lire) == [bete]
	assert not proprietes.peut_ceder(p)[0]
	assert proprietes.reprendre_monture(moi, p, bete)[0]
	assert montures.montures_effectives(moi, lire) == [bete] and p["ecurie"] == []


def test_ecurie_refuse_sac_plein_place_prise_et_monture_d_autrui():
	p = bien("maison", "cour_interieure")
	moi = perso(montures=["monture:a", "monture:b"])
	a = {"_id": "monture:a", "statut": "acquise", "acquise_par": "character:a", "inventaire": ["item:x"]}
	b = {"_id": "monture:b", "statut": "acquise", "acquise_par": "character:a", "inventaire": []}
	autre = {"_id": "monture:c", "statut": "acquise", "acquise_par": "character:z", "inventaire": []}
	assert not proprietes.loger_monture(moi, p, CAT, a)[0]
	assert not proprietes.loger_monture(moi, p, CAT, autre)[0]
	a["inventaire"] = []
	assert proprietes.loger_monture(moi, p, CAT, a)[0]
	assert not proprietes.loger_monture(moi, p, CAT, b)[0]     # une seule place


def test_plafond_du_troupeau_compte_l_ecurie():
	bete = {"_id": "monture:a", "statut": "acquise", "acquise_par": "character:a", "loge_a": "propriete:x"}
	moi = perso(montures=["monture:a"] * montures.plafond_montures(), **{"or": 10 ** 6})
	ok, _ = montures.peut_acquerir(moi, {"prix_cuivre": 1}, {"monture:a": bete}.get)
	assert not ok


# ── Récolte ──────────────────────────────────────────────────────────────────────

def test_recolte_une_fois_par_delai():
	p = bien("maison", "petit_jardin")
	r = adef("petit_jardin")["effets"]["recolte"]
	docs = {i: {"_id": i, "poids": 0.1} for i in r["items"]}
	ok, _, refs = proprietes.recolter(p, CAT, "petit_jardin", docs.get, random.Random(3), now=1000)
	assert ok and len(refs) == r["quantite"] and all(x in r["items"] for x in refs)
	assert not proprietes.recolter(p, CAT, "petit_jardin", docs.get, random.Random(3), now=1001)[0]
	assert proprietes.recoltes(p, CAT, now=1001)[0]["pret"] is False
	assert proprietes.recolter(p, CAT, "petit_jardin", docs.get, random.Random(3), now=1000 + r["delai_s"])[0]
	assert not proprietes.recolter(bien("maison"), CAT, "petit_jardin", docs.get, now=1000)[0]


def test_recolte_poids_d_instance_tire():
	p = bien("domaine", "terrain_prive")
	r = adef("terrain_prive")["effets"]["recolte"]
	docs = {i: {"_id": i, "poids": [0.5, 2.0]} for i in r["items"]}
	_, _, refs = proprietes.recolter(p, CAT, "terrain_prive", docs.get, random.Random(5), now=1)
	assert all(isinstance(x, dict) and 0.5 <= x["poids"] <= 2.0 for x in refs)


def test_textes_d_effets_lisibles():
	assert any("Volonté +3" in t for t in proprietes.textes_effets(adef("salon"), CAT))
	assert any(t.startswith("avec un(e) Médecin") for t in proprietes.textes_effets(adef("infirmerie"), CAT))
	assert any("écurie" in t for t in proprietes.textes_effets(adef("ecuries"), CAT))
