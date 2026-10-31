"""Endpoints des guides (`routers/guides.py`) et guide en combat : gardes d'auberge, arrhes,
question payée au cap posé, départ à la sortie de la cité, statut de monture. Base en mémoire, gabarit de test_auberge_endpoints."""

import asyncio

import pytest
from fastapi import HTTPException

from models import character_stats
from utils import characters as characters_util
from utils import combat as combat_util
from utils import focalisation, guides, montures as montures_util

from tests.test_combat_groupe import character as perso_combat, monstre_snap

CARACTS = {"V": 5, "F": 20, "R": 40, "Ag": 40, "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40}
REGLES = {
	"_id": "rules:guides", "tableau_nb": 2, "duree_offre_secondes": 1000,
	"repliques": {"accueil": "Dites.", "accepte": "Vers {lieu}.", "ici": "Ici : {lieu}.",
				  "inconnu": "Connais pas {quete}.", "proche": "{recherche} ?", "sans_chemin": "Pas de route.",
				  "sans_le_sou": "{prix} pour {lieu}.", "adieu": "Je reste à {cite}.", "adieu_portail": "Pas ce portail."},
	"metiers": {
		"routes": {"label": "Routes", "arrhes_cuivre": 50, "question_cuivre": 10,
				   "offre": {"partout": True}, "savoir": {}, "portrait_voc": "forestier",
				   "repliques": {"presentation": "Il connaît."}},
		"marin": {"label": "Marin", "arrhes_cuivre": 100, "question_cuivre": 15,
				  "offre": {"traits": ["port"]}, "savoir": {}},
	},
}
ROUTES = REGLES["metiers"]["routes"]
RACES = {"_id": "rules:races", "value": [{"id": "humain", "stats": CARACTS, "stats_max": {k: 40 for k in CARACTS}}]}
LIEUX = [
	{"_id": "lieu:france", "type": "lieu", "categorie": "pays", "label": "France"},
	{"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "label": "Ville", "lieu_parent": "lieu:france"},
	{"_id": "lieu:auberge", "type": "lieu", "categorie": "auberge", "label": "Auberge", "lieu_parent": "lieu:ville"},
	{"_id": "lieu:etable", "type": "lieu", "categorie": "etable", "label": "Étable", "lieu_parent": "lieu:ville"},
	{"_id": "lieu:bois", "type": "lieu", "categorie": "chemin", "label": "Le Bois", "lieu_parent": "lieu:ville",
	 "rencontres": [{"espece": "espece:loup", "zones": ["zone:a"]}]},
	{"_id": "lieu:etranger", "type": "lieu", "categorie": "chemin", "label": "Ailleurs",
	 "rencontres": [{"espece": "espece:wyvern", "zones": ["zone:a"]}]},
]
LIENS = [
	{"_id": f"link:{a}>{b}", "type": "connection", "nodes": [{"lieu": a, "pos": [0, 0]}, {"lieu": b, "pos": [0, 0]}]}
	for a, b in (("lieu:auberge", "lieu:bois"), ("lieu:bois", "lieu:etable"), ("lieu:bois", "lieu:etranger"))
]


def _perso(**champs):
	base = {"_id": "character:u_1", "type": "character", "lieu": "lieu:auberge", "position": {"x": 0, "y": 0},
			"prenom": "Greta", "nom": "H", "inventaire": [], "slots": {}, "groupe": [], "montures": [],
			"caracteristiques_current": dict(CARACTS), "quetes_actives": [],
			"or": 0, "argent": 1, "cuivre": 0}   # 100 cuivres
	base.update(champs)
	return base


@pytest.fixture
def monde(monkeypatch):
	from routers import guides as rg, montures as rm
	docs = {d["_id"]: d for d in [*LIEUX, *LIENS, REGLES, RACES]}

	def get_doc_fn(i):
		return docs.get(i)

	def save_doc_fn(d):
		docs[d["_id"]] = d
		return d

	def delete_doc_fn(d):
		docs.pop(d.get("_id"), None)

	def find_docs_fn(sel, fields=None, limit=None):
		return [d for d in list(docs.values()) if all(d.get(k) == v for k, v in (sel or {}).items())]

	for mod in (rg, rm, montures_util, characters_util):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
	for mod in (rg, rm):
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
	monkeypatch.setattr(rg, "find_docs", find_docs_fn)
	monkeypatch.setattr(rg, "delete_doc", delete_doc_fn)
	monkeypatch.setattr(rg.recrutement, "portraits_disponibles", lambda: [])
	focalisation.reset_graphe_cache()
	yield {"docs": docs, "rg": rg}
	focalisation.reset_graphe_cache()


def _appel(monde, char, fn, *args):
	rg = monde["rg"]
	monde["docs"][char["_id"]] = char
	origine = rg.get_selected_character
	rg.get_selected_character = lambda _u: char
	try:
		return asyncio.run(fn(*args))
	finally:
		rg.get_selected_character = origine


def _engage(monde, char, metier="routes"):
	data = _appel(monde, char, monde["rg"].tableau, None)
	offre = next(o for o in data["offres"] if o["metier_label"].lower() == metier)
	return _appel(monde, char, monde["rg"].engager, None, {"guide_id": offre["id"]})


def _guide_doc(monde, char):
	return guides.guide_de(char, monde["docs"].get)


def test_tableau_refuse_hors_auberge(monde):
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso(lieu="lieu:etable"), monde["rg"].tableau, None)
	assert e.value.status_code == 403


def test_tableau_ne_montre_que_les_metiers_du_lieu(monde):
	data = _appel(monde, _perso(), monde["rg"].tableau, None)
	assert data["offres"] and {o["metier_label"] for o in data["offres"]} == {"Routes"}


def test_engager_debite_les_arrhes(monde):
	char = _perso()
	data = _engage(monde, char)
	assert data["guide"]["question_cuivre"] == ROUTES["question_cuivre"]
	assert characters_util.money_to_cuivre(char) == 100 - ROUTES["arrhes_cuivre"]


def test_engager_sans_fonds_ne_prend_rien(monde):
	char = _perso(argent=0, cuivre=1)
	offre = _appel(monde, char, monde["rg"].tableau, None)["offres"][0]
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rg"].engager, None, {"guide_id": offre["id"]})
	assert e.value.status_code == 409
	assert char["montures"] == [] and characters_util.money_to_cuivre(char) == 1


def test_un_seul_guide_a_la_fois(monde):
	char = _perso(argent=5)
	data = _engage(monde, char)
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rg"].engager, None, {"guide_id": data["offres"][0]["id"]})
	assert e.value.status_code == 409


def test_offre_d_une_autre_auberge_refusee(monde):
	char = _perso()
	offre = _appel(monde, char, monde["rg"].tableau, None)["offres"][0]
	monde["docs"][offre["id"]]["giver"] = "lieu:ailleurs"
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rg"].engager, None, {"guide_id": offre["id"]})
	assert e.value.status_code == 403


def test_congedier_seulement_a_l_auberge(monde):
	char = _perso()
	_engage(monde, char)
	char["lieu"] = "lieu:etable"
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["rg"].congedier, None)
	assert e.value.status_code == 403
	char["lieu"] = "lieu:auberge"
	data = _appel(monde, char, monde["rg"].congedier, None)
	assert data["guide"] is None and char["montures"] == []


def test_relacher_le_guide_refuse_par_l_etable(monde):
	from routers import montures as rm
	char = _perso()
	_engage(monde, char)
	guide = _guide_doc(monde, char)
	origine = rm.get_selected_character
	rm.get_selected_character = lambda _u: char
	try:
		with pytest.raises(HTTPException) as e:
			asyncio.run(rm.relacher_monture(None, {"monture_id": guide["_id"]}))
	finally:
		rm.get_selected_character = origine
	assert e.value.status_code == 409
	assert guide["_id"] in char["montures"]


def test_quete_kill_pose_le_cap_jusqu_au_bois(monde):
	q = {"id": "q1", "titre": "Loups", "objectif": {"type": "kill", "cible": "espece:loup", "quantite": 3}}
	char = _perso(quetes_actives=[q])
	_engage(monde, char)
	dial = _appel(monde, char, monde["rg"].dialogue, None)
	assert [s["connu"] for s in dial["sujets"]] == [True]
	data = _appel(monde, char, monde["rg"].demander, None, {"quete_id": "q1"})
	assert data["replique"] == "Vers Le Bois."
	assert char["focalisation"]["cible"] == "lieu:bois" and char["focalisation"]["puis_quete"] == "q1"
	assert data["guidage"]["cible"] == "lieu:bois"


def test_quete_hors_zone_il_ne_sait_pas(monde):
	q = {"id": "q1", "titre": "Wyvern", "objectif": {"type": "kill", "cible": "espece:wyvern", "quantite": 1}}
	char = _perso(quetes_actives=[q])
	_engage(monde, char)
	data = _appel(monde, char, monde["rg"].demander, None, {"quete_id": "q1"})
	assert data["replique"] == "Connais pas Wyvern."
	assert not char.get("focalisation")


def test_saisie_exacte_et_approchante(monde):
	char = _perso()
	_engage(monde, char)
	assert _appel(monde, char, monde["rg"].demander, None, {"saisie": "bois"})["replique"] == "Vers Le Bois."
	data = _appel(monde, char, monde["rg"].demander, None, {"saisie": "Le Boi"})
	assert data["suggestions"] == ["Le Bois"] and data["replique"] == "Le Boi ?"


def _bourse(char):
	return characters_util.money_to_cuivre(char)


def test_le_cap_pose_se_paie_une_seule_fois(monde):
	char = _perso()
	_engage(monde, char)
	avant = _bourse(char)
	_appel(monde, char, monde["rg"].demander, None, {"saisie": "bois"})
	assert _bourse(char) == avant - ROUTES["question_cuivre"]
	assert char["focalisation"]["cible"] == "lieu:bois"
	_appel(monde, char, monde["rg"].demander, None, {"saisie": "bois"})
	assert _bourse(char) == avant - ROUTES["question_cuivre"]


def test_un_autre_cap_se_paie_a_nouveau(monde):
	char = _perso()
	_engage(monde, char)
	avant = _bourse(char)
	_appel(monde, char, monde["rg"].demander, None, {"saisie": "bois"})
	_appel(monde, char, monde["rg"].demander, None, {"saisie": "Étable"})
	assert _bourse(char) == avant - 2 * ROUTES["question_cuivre"]


@pytest.mark.parametrize("corps", [
	{"saisie": "Le Boi"},          # proche
	{"saisie": "zzz"},             # inconnu
	{"saisie": "auberge"},         # ici
	{"quete_id": "q_hors_zone"},   # quête qu'il ne connaît pas
	{"quete_id": "q_ici"},         # déjà sur le terrain
])
def test_une_reponse_sans_cap_est_gratuite(monde, corps):
	char = _perso(lieu="lieu:auberge", quetes_actives=[
		{"id": "q_hors_zone", "titre": "W", "objectif": {"type": "kill", "cible": "espece:wyvern", "quantite": 1}},
		{"id": "q_ici", "titre": "I", "objectif": {"type": "visite", "cible": "lieu:auberge"}},
	])
	_engage(monde, char)
	avant = _bourse(char)
	_appel(monde, char, monde["rg"].demander, None, corps)
	assert _bourse(char) == avant


def test_bourse_trop_legere_ni_cap_ni_dette(monde):
	char = _perso()
	_engage(monde, char)
	char["argent"], char["cuivre"] = 0, ROUTES["question_cuivre"] - 1
	data = _appel(monde, char, monde["rg"].demander, None, {"saisie": "bois"})
	assert data["replique"] == f"{ROUTES['question_cuivre']} pour Le Bois."
	assert not char.get("focalisation") and _bourse(char) == ROUTES["question_cuivre"] - 1


# ── Sortie de la cité ────────────────────────────────────────────────────────────

@pytest.fixture
def franchir(monde, monkeypatch):
	from routers import user as ru
	monkeypatch.setattr(ru, "get_doc", monde["docs"].get)
	return lambda char, destination, **move: ru._guide_au_franchissement(char, monde["docs"][destination], move)


def test_vers_le_pays_il_previent_sans_rien_changer(monde, franchir):
	char = _perso(lieu="lieu:etable")
	_engage_ici = dict(char, lieu="lieu:auberge")
	_engage(monde, _engage_ici)
	char["montures"] = _engage_ici["montures"]
	reponse, parti = franchir(char, "lieu:france")
	assert parti is None and reponse["moved"] == 0
	assert reponse["guide_avertissement"]["replique"] == "Je reste à Ville."
	assert char["montures"] and _guide_doc(monde, char)["statut"] == "acquise"


def test_confirme_il_reste_et_le_groupe_continue(monde, franchir):
	char = _perso()
	_engage(monde, char)
	guide = _guide_doc(monde, char)
	reponse, parti = franchir(char, "lieu:france", guide_adieu=True)
	assert reponse is None and parti is guide and guide["statut"] == "parti" and char["montures"] == []


def test_confirme_avec_un_sac_plein_refuse(monde, franchir):
	char = _perso()
	_engage(monde, char)
	guide = _guide_doc(monde, char)
	guide["inventaire"] = ["item:sac"]
	assert franchir(char, "lieu:france")[0]["guide_avertissement"]["sac_plein"] is True
	with pytest.raises(HTTPException) as e:
		franchir(char, "lieu:france", guide_adieu=True)
	assert e.value.status_code == 409 and guide["statut"] == "acquise"


def test_un_lien_portail_le_fait_partir_vers_n_importe_quel_lieu(monde, monkeypatch):
	from routers import user as ru
	monkeypatch.setattr(ru, "get_doc", monde["docs"].get)
	char = _perso()
	_engage(monde, char)
	guide = _guide_doc(monde, char)
	lien = {"metadata": {"type": "portail"}}
	bois = monde["docs"]["lieu:bois"]
	reponse, parti = ru._guide_au_franchissement(char, bois, {}, lien)
	assert parti is None and reponse["guide_avertissement"]["replique"] == "Pas ce portail."
	assert guide["statut"] == "acquise"
	reponse, parti = ru._guide_au_franchissement(char, bois, {"guide_adieu": True}, lien)
	assert reponse is None and parti is guide and char["montures"] == []


def test_ailleurs_que_vers_un_pays_rien(monde, franchir):
	char = _perso()
	_engage(monde, char)
	assert franchir(char, "lieu:bois") == (None, None)
	assert _guide_doc(monde, char)


def test_sans_guide_le_pays_ne_demande_rien(monde, franchir):
	assert franchir(_perso(), "lieu:france") == (None, None)


# ── En combat : le statut d'une monture, mais il se défend ───────────────────────

def test_en_combat_se_defend_immobile_et_porte_comme_un_homme(monde, monkeypatch):
	monkeypatch.setattr(combat_util, "get_doc", monde["docs"].get)
	g = guides.generer_guide("routes", monde["docs"]["lieu:auberge"], guides.index_lieux(
		lambda s, fields=None: LIEUX), REGLES, RACES["value"], [])
	doc = combat_util.create_combat_doc(perso_combat(), [monstre_snap()], [], "", montures=[g])
	snap = doc["joueurs"][1]
	assert snap["jouable"] is False and snap["est_monture"] is True and snap["deplacement"] == 0
	assert snap["se_defend"] is True and snap["id"] in doc["ordre_initiative"]
	assert snap["charge_max"] == characters_util.charge_max_of(g)
	assert character_stats.MONTURE_CHARGE_MULT_DEFAUT > 1   # sinon ce test ne distinguerait rien


def test_guide_frappe_au_contact_sans_bouger_et_ne_retient_pas_la_defaite(monde, monkeypatch):
	monkeypatch.setattr(combat_util, "get_doc", monde["docs"].get)
	monkeypatch.setattr(combat_util.random, "randint", lambda a, b: min(max(10, a), b))   # ni critique ni fumble
	g = guides.generer_guide("routes", monde["docs"]["lieu:auberge"], guides.index_lieux(
		lambda s, fields=None: LIEUX), REGLES, RACES["value"], [])
	doc = combat_util.create_combat_doc(perso_combat(), [monstre_snap()], [], "", montures=[g])
	principal, snap, monstre = doc["joueurs"][0], doc["joueurs"][1], doc["monstres"][0]
	principal["currentPV"] = 0   # la main ne reviendra pas : seul le guide peut agir
	monstre.update(currentPV=1000, pv_max=1000)
	snap["pos"], monstre["pos"] = {"x": 5, "y": 5}, {"x": 6, "y": 5}
	snap["facing"] = 90   # face à l'est : le monstre est devant lui
	pos_avant = dict(snap["pos"])
	doc["acteur_courant_index"] = doc["ordre_initiative"].index(snap["id"])

	combat_util._run_defenseur_turn(doc, snap, combat_util._open_grid())

	assert monstre["currentPV"] < 1000
	assert snap["pos"] == pos_avant
	assert combat_util._combattants_vivants(doc) == []   # debout, il ne compte pas pour la défaite


def test_impossible_d_oter_l_equipement_d_un_guide(monkeypatch):
	from routers import user as ru
	g = {"_id": "monture:guide_x", "type": "monture", "guide": {"metier": "routes"},
		 "slots": {"main_droite": "item:canne"}, "inventaire": []}
	monkeypatch.setattr(ru, "_acteur", lambda u, b: (g, {}))
	with pytest.raises(HTTPException) as e:
		asyncio.run(ru.unequip_item({"user_id": "u"}, {"slot": "main_droite", "compagnon_id": g["_id"]}))
	assert e.value.status_code == 403 and g["slots"]["main_droite"] == "item:canne" and g["inventaire"] == []
