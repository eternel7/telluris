"""Guides locaux d'auberge (utils/guides.py) — logique pure, sans DB."""

import random

import pytest

from utils import focalisation, guides, montures

STATS = {"V": 10, "F": 10, "R": 10, "Ag": 10, "Vol": 10, "Int": 10, "Cha": 10, "Ch": 10}
RACES = [{"id": "humain", "stats": STATS, "stats_max": {k: 40 for k in STATS}}]

REGLES = {
	"tableau_nb": 2, "duree_offre_secondes": 100, "seuil_alerte_tours": 3,
	"repliques": {"accepte": "Pour {lieu}, par ici."},
	"metiers": {
		"routes": {"label": "Routes", "forfait_cuivre": 50, "forfait_tours": 10, "offre": {"partout": True},
				   "savoir": {}, "portrait_voc": "forestier"},
		"marin": {"label": "Marin", "forfait_cuivre": 80, "forfait_tours": 10, "offre": {"traits": ["port"]},
				  "savoir": {"categories": ["quai"]}, "repliques": {"accepte": "Cap sur {lieu}."}},
		"interprete": {"label": "Interprète", "forfait_cuivre": 90, "forfait_tours": 10,
					   "offre": {"sous_categories": ["capitale"]}, "savoir": {}},
		"survivant": {"label": "Survivant", "forfait_cuivre": 90, "forfait_tours": 10,
					  "offre": {"traits": ["donjon"]}, "savoir": {"tags": ["donjon"]}},
		"montagnard": {"label": "Montagnard", "forfait_cuivre": 90, "forfait_tours": 10,
					   "offre": {"traits": ["montagne"]}, "savoir": {}},
	},
}

INDEX = {d["_id"]: d for d in [
	{"_id": "lieu:france", "categorie": "pays"},
	{"_id": "lieu:angleterre", "categorie": "pays"},
	{"_id": "lieu:capitale", "categorie": "ville", "sous_categorie": "capitale", "lieu_parent": "lieu:france"},
	{"_id": "lieu:bourg", "categorie": "ville", "sous_categorie": "ville", "lieu_parent": "lieu:france"},
	{"_id": "lieu:port", "categorie": "ville", "lieu_parent": "lieu:angleterre"},
	{"_id": "lieu:auberge", "categorie": "auberge", "lieu_parent": "lieu:capitale"},
	{"_id": "lieu:auberge_bourg", "categorie": "auberge", "lieu_parent": "lieu:bourg"},
	{"_id": "lieu:auberge_port", "categorie": "auberge", "lieu_parent": "lieu:port"},
	{"_id": "lieu:quai", "categorie": "quai", "lieu_parent": "lieu:port"},
	{"_id": "lieu:temple", "categorie": "temple_portail", "lieu_parent": "lieu:capitale"},
	{"_id": "lieu:loin", "categorie": "chemin", "lieu_parent": "lieu:bourg",
	 "rencontres": [{"espece": "espece:loup", "zones": ["zone:a"]}],
	 "ressources": [{"ressource": "item:herbe", "zones": ["zone:a"]}]},
	{"_id": "lieu:pres", "categorie": "chemin", "lieu_parent": "lieu:capitale",
	 "rencontres": [{"espece": "espece:loup", "zones": ["zone:a"]}]},
	{"_id": "lieu:etranger", "categorie": "chemin", "lieu_parent": "lieu:port",
	 "rencontres": [{"espece": "espece:wyvern", "zones": ["zone:a"]}]},
	{"_id": "lieu:sans_parent", "categorie": "grotte", "tags": ["donjon"]},
]}


def _arete(a, b):
	return {"link_id": f"{a}>{b}", "voisin": b, "porte": (0, 0)}


GRAPHE = {
	"lieu:auberge": [_arete("lieu:auberge", "lieu:pres")],
	"lieu:pres": [_arete("lieu:pres", "lieu:auberge"), _arete("lieu:pres", "lieu:loin"),
				  _arete("lieu:pres", "lieu:etranger"), _arete("lieu:pres", "lieu:sans_parent")],
	"lieu:loin": [_arete("lieu:loin", "lieu:pres")],
	"lieu:etranger": [_arete("lieu:etranger", "lieu:pres")],
	"lieu:sans_parent": [_arete("lieu:sans_parent", "lieu:pres")],
}


def _guide(metier="routes", tours=10, zone="lieu:france"):
	return {"_id": "monture:guide_a", "type": "monture", "statut": "acquise", "acquise_par": "character:1",
			"caracteristiques_current": dict(STATS), "inventaire": [], "slots": {},
			"guide": {"metier": metier, "zone": zone, "tours_restants": tours}}


def _perso(**extra):
	return {"_id": "character:1", "lieu": "lieu:auberge", "montures": ["monture:guide_a"],
			"quetes_actives": [], **extra}


# ── Localisation ─────────────────────────────────────────────────────────────────

def test_marin_seulement_dans_une_cite_a_quai():
	assert "marin" not in guides.metiers_offerts("lieu:auberge", INDEX, REGLES)
	assert "marin" in guides.metiers_offerts("lieu:auberge_port", INDEX, REGLES)


def test_tag_port_suffit_sans_quai():
	index = dict(INDEX)
	index["lieu:bourg"] = dict(INDEX["lieu:bourg"], tags=["port"])
	assert "marin" in guides.metiers_offerts("lieu:auberge_bourg", index, REGLES)


def test_interprete_a_la_capitale_seulement():
	assert "interprete" in guides.metiers_offerts("lieu:auberge", INDEX, REGLES)
	assert "interprete" not in guides.metiers_offerts("lieu:auberge_bourg", INDEX, REGLES)


def test_survivant_lit_le_temple_de_la_cite():
	assert "survivant" in guides.metiers_offerts("lieu:auberge", INDEX, REGLES)
	assert "survivant" not in guides.metiers_offerts("lieu:auberge_bourg", INDEX, REGLES)


def test_montagnard_suit_un_tag_d_ancetre():
	assert "montagnard" not in guides.metiers_offerts("lieu:auberge", INDEX, REGLES)
	index = dict(INDEX)
	index["lieu:france"] = dict(INDEX["lieu:france"], tags=["montagne"])
	assert "montagnard" in guides.metiers_offerts("lieu:auberge", index, REGLES)


def test_regles_absentes_aucun_metier():
	assert guides.metiers_offerts("lieu:auberge", INDEX, {}) == []


# ── Savoir ───────────────────────────────────────────────────────────────────────

def test_zone_est_le_pays():
	assert guides.zone_de("lieu:auberge", INDEX) == "lieu:france"


def test_connait_son_pays_pas_l_etranger():
	g = _guide()
	assert guides.connait(g, "lieu:loin", INDEX, REGLES)
	assert not guides.connait(g, "lieu:etranger", INDEX, REGLES)
	assert not guides.connait(g, "lieu:sans_parent", INDEX, REGLES)


def test_le_metier_elargit_le_savoir():
	assert guides.connait(_guide("marin"), "lieu:quai", INDEX, REGLES)
	assert guides.connait(_guide("survivant"), "lieu:sans_parent", INDEX, REGLES)


def _quete(**objectif):
	return {"id": "q1", "titre": "Q", "objectif": {"quantite": 1, **objectif}}


def test_kill_vise_le_lieu_le_plus_proche():
	piste = guides.piste_quete(_quete(type="kill", cible="espece:loup"), _guide(), "lieu:auberge",
							   INDEX, GRAPHE, REGLES)
	assert piste == {"lieu": "lieu:pres", "distance": 1}


def test_collect_recolte_puis_repli_carcasse():
	g = _guide()
	assert guides.piste_quete(_quete(type="collect", cible="item:herbe"), g, "lieu:auberge",
							  INDEX, GRAPHE, REGLES)["lieu"] == "lieu:loin"
	assert guides.piste_quete(_quete(type="collect", cible="item:loup"), g, "lieu:auberge",
							  INDEX, GRAPHE, REGLES)["lieu"] == "lieu:pres"


def test_cible_hors_de_sa_zone_pas_de_piste():
	assert guides.piste_quete(_quete(type="kill", cible="espece:wyvern"), _guide(), "lieu:auberge",
							  INDEX, GRAPHE, REGLES) is None


def test_chasse_visite_escorte_lisent_leur_lieu():
	g = _guide()
	depuis = "lieu:auberge"
	assert guides.piste_quete(_quete(type="chasse", cible="espece:x", lieu="lieu:loin"), g, depuis,
							  INDEX, GRAPHE, REGLES)["lieu"] == "lieu:loin"
	assert guides.piste_quete(_quete(type="visite", cible="lieu:loin"), g, depuis,
							  INDEX, GRAPHE, REGLES)["lieu"] == "lieu:loin"
	escorte = _quete(type="escorte", cible="lieu:loin", rencontre={"lieu": "lieu:pres"})
	assert guides.piste_quete(escorte, g, depuis, INDEX, GRAPHE, REGLES)["lieu"] == "lieu:pres"
	escorte["rencontre_at"] = 1
	assert guides.piste_quete(escorte, g, depuis, INDEX, GRAPHE, REGLES)["lieu"] == "lieu:loin"


def test_transport_hors_sujet():
	assert guides.piste_quete(_quete(type="transport", cible="lieu:loin"), _guide(), "lieu:auberge",
							  INDEX, GRAPHE, REGLES) is None


def test_sujet_sans_piste_reste_listé():
	perso = _perso(quetes_actives=[_quete(type="kill", cible="espece:wyvern")])
	sujets = guides.sujets(perso, _guide(), INDEX, GRAPHE, REGLES)
	assert [s["connu"] for s in sujets] == [False]


# ── Forfait ──────────────────────────────────────────────────────────────────────

def test_engager_credite_le_forfait():
	g = dict(_guide(tours=0), statut="offert", expire_at=5)
	perso = {"_id": "character:1", "montures": []}
	ok, _ = guides.engager(perso, g, REGLES)
	assert ok and g["statut"] == "acquise" and "expire_at" not in g
	assert guides.tours_restants(g) == REGLES["metiers"]["routes"]["forfait_tours"]
	assert g["_id"] in perso["montures"]


def test_renouveler_cumule():
	g = _guide(tours=2)
	assert guides.ajouter_forfait(g, REGLES) == 2 + REGLES["metiers"]["routes"]["forfait_tours"]


def test_decompte_alerte_puis_epuisement_efface_le_cap():
	g = _guide(tours=REGLES["seuil_alerte_tours"] + 1)
	perso = _perso()
	guides.poser_cap(perso, g, "lieu:loin")
	regles = lambda: REGLES
	assert guides.decompter_tour(perso, [g], regles)["alerte"] == "bientot"
	for _ in range(REGLES["seuil_alerte_tours"] - 1):
		assert guides.decompter_tour(perso, [g], regles)["alerte"] is None
	assert perso["focalisation"]["cible"] == "lieu:loin"
	fin = guides.decompter_tour(perso, [g], regles)
	assert fin == {"tours_restants": 0, "alerte": "epuise"}
	assert perso["focalisation"] is None and not guides.actif(g)
	# Déjà épuisé : plancher, plus d'alerte.
	assert guides.decompter_tour(perso, [g], regles) == {"tours_restants": 0, "alerte": None}


def test_epuisement_laisse_le_cap_du_joueur():
	g = _guide(tours=1)
	perso = _perso(focalisation={"type": "lieu", "cible": "lieu:loin", "posee_at": 1})
	guides.decompter_tour(perso, [g], lambda: REGLES)
	assert perso["focalisation"]["cible"] == "lieu:loin"


def test_sans_guide_ne_lit_pas_les_regles():
	def interdit():
		raise AssertionError("règles lues sans guide")
	assert guides.decompter_tour(_perso(), [{"type": "monture", "_id": "monture:ane"}], interdit) is None


def test_congedier_refuse_un_sac_plein_et_retire_le_cap():
	g = _guide()
	perso = _perso()
	guides.poser_cap(perso, g, "lieu:loin")
	g["inventaire"] = ["item:x"]
	assert guides.congedier(perso, g)[0] is False
	g["inventaire"] = []
	assert guides.congedier(perso, g)[0] is True
	assert perso["montures"] == [] and perso["focalisation"] is None and g["statut"] == "parti"


# ── Exceptions de monture ────────────────────────────────────────────────────────

def test_plafond_du_troupeau_ignore_le_guide(monkeypatch):
	monkeypatch.setattr(montures.character_stats, "MONTURE_GROUPE_MAX", 1)
	g = _guide()
	perso = {"_id": "character:1", "montures": [g["_id"]], "cuivre": 10, "or": 0, "argent": 0}
	espece = {"proprietes": {"prix_cuivre": 1}}
	assert montures.peut_acquerir(perso, espece, lambda i: g)[0] is True


def test_guide_ni_relache_ni_harnache_et_porte_comme_un_homme():
	g = _guide()
	assert montures.relacher(_perso(), g)[0] is False
	assert montures.slot_admis(g, "monture_dos") is False
	assert montures.charge_max_monture(g) == montures.charge_max_of(g)


def test_mort_du_guide_efface_son_cap_et_verse_le_sac():
	g = dict(_guide(), inventaire=["item:x"])
	perso = _perso()
	guides.poser_cap(perso, g, "lieu:loin")
	assert montures.tuer(perso, g) == ["item:x"]
	assert perso["focalisation"] is None and perso["montures"] == []


# ── Focalisation ─────────────────────────────────────────────────────────────────

def test_cap_inerte_si_le_guide_n_accompagne_plus():
	perso = _perso()
	guides.poser_cap(perso, _guide(), "lieu:loin")
	assert focalisation.focalisation_effective(perso)["lieu_cible"] == "lieu:loin"
	perso["montures"] = []
	assert focalisation.focalisation_effective(perso) is None


def test_arrivee_passe_au_biais_de_la_quete():
	q = _quete(type="kill", cible="espece:loup")
	q["objectif"]["quantite"] = 3
	perso = _perso(quetes_actives=[q])
	guides.poser_cap(perso, _guide(), "lieu:pres", "q1")
	assert focalisation.effacer_si_lieu_atteint(perso, "lieu:pres") is True
	assert perso["focalisation"]["type"] == "quete" and perso["focalisation"]["cible"] == "q1"
	assert focalisation.focalisation_effective(perso)["mode"] == "kill"


def test_arrivee_sans_quete_efface_simplement():
	perso = _perso()
	guides.poser_cap(perso, _guide(), "lieu:pres")
	assert focalisation.effacer_si_lieu_atteint(perso, "lieu:pres") is True
	assert perso["focalisation"] is None


def test_distances_depuis():
	d = focalisation.distances_depuis(GRAPHE, "lieu:auberge")
	assert d["lieu:auberge"] == 0 and d["lieu:loin"] == 2


# ── Tableau ──────────────────────────────────────────────────────────────────────

def test_generer_guide_fixe_zone_et_vitaux():
	g = guides.generer_guide("routes", INDEX["lieu:auberge"], INDEX, REGLES, RACES, [], random.Random(1))
	assert montures.est_guide(g) and g["statut"] == "offert"
	assert g["guide"]["zone"] == "lieu:france" and g["currentPV"] > 0
	assert g["_id"].startswith("monture:guide_")


def test_tableau_purge_et_complete_en_variant():
	vieux = guides.generer_guide("routes", INDEX["lieu:auberge"], INDEX, REGLES, RACES, [], random.Random(1))
	vieux["expire_at"] = 0
	sauves, supprimes = [], []
	offres = guides.remplir_tableau(
		INDEX["lieu:auberge"], INDEX, REGLES, RACES, [],
		lambda sel, **k: [vieux], lambda d: sauves.append(d) or "rev", supprimes.append,
		now=10, rand=random.Random(2))
	assert supprimes == [vieux]
	assert len(offres) == REGLES["tableau_nb"]
	metiers = {o["guide"]["metier"] for o in offres}
	assert len(metiers) == REGLES["tableau_nb"]


def test_tableau_sans_regles_vide():
	assert guides.remplir_tableau(INDEX["lieu:auberge"], INDEX, {}, RACES, [],
								  lambda sel, **k: [], lambda d: "rev", lambda d: None) == []


def test_replique_du_metier_prime_sur_la_commune():
	assert guides.replique(_guide("marin"), REGLES, "accepte", lieu="X") == "Cap sur X."
	assert guides.replique(_guide("routes"), REGLES, "accepte", lieu="X") == "Pour X, par ici."


def test_generateur_catalogue_coherent():
	import importlib.util
	import os
	chemin = os.path.join(os.path.dirname(__file__), "..", "dev", "gen_guides.py")
	spec = importlib.util.spec_from_file_location("gen_guides", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	for mid, m in mod.DOC["metiers"].items():
		assert m["forfait_cuivre"] > 0 and m["forfait_tours"] > 0, mid
		assert m["offre"], mid
		assert m["repliques"]["presentation"], mid
	for cle in ("accueil", "accepte", "ici", "inconnu", "proche", "sans_chemin", "epuise", "renouvele"):
		assert mod.DOC["repliques"][cle], cle


def _generateur():
	import importlib.util
	import os
	chemin = os.path.join(os.path.dirname(__file__), "..", "dev", "gen_guides.py")
	spec = importlib.util.spec_from_file_location("gen_guides", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


def test_chaque_metier_est_arme_pour_la_melee_avec_des_objets_du_dump():
	"""Le tour de défense ne frappe qu'au corps à corps (`_run_defenseur_turn`) : une arme de
	tir laisserait le guide à mains nues. Aucune restriction : tout guide, de toute race."""
	mod = _generateur()
	dump = mod._dump_recent()
	if not dump:
		pytest.skip("aucun dump")
	items = {d["_id"]: d for d in dump["docs"] if str(d.get("_id", "")).startswith("item:")}
	for mid, m in mod.DOC["metiers"].items():
		armes = 0
		for slot, iid in m["equipement"].items():
			item = items[iid]
			assert slot in item["slots"], (mid, iid)
			assert not item.get("restriction"), (mid, iid)
			if item.get("categorie") == "arme":
				armes += 1
				assert not {"tir", "jet"} & set(item.get("tags") or []), (mid, iid)
		assert armes >= 1, mid


def test_guide_genere_porte_l_equipement_de_son_metier():
	regles = {"metiers": {"routes": dict(REGLES["metiers"]["routes"], equipement={
		"main_droite": "item:canne", "tete": "item:disparu"})}}
	docs = {"item:canne": {"_id": "item:canne", "categorie": "arme", "poids": 0.9, "slots": ["main_droite"]}}
	g = guides.generer_guide("routes", INDEX["lieu:auberge"], INDEX, regles, RACES, [], random.Random(1),
							 get_doc_fn=docs.get)
	assert g["slots"] == {"main_droite": {"item": "item:canne", "poids": 0.9}}   # objet disparu : slot vide


def test_a_sa_mort_le_guide_verse_son_sac_et_son_equipement():
	"""Décision de l'auteur : le corps est là, rien ne disparaît — tant pis pour l'anti-jeu."""
	g = dict(_guide(), inventaire=["item:sac"], slots={"main_droite": "item:canne"})
	assert montures.tuer(_perso(), g) == ["item:sac", "item:canne"]
	assert g["slots"] == {"main_droite": None}
