"""Traversées maritimes (`utils/traversee.py`, `routers/traversee.py`, service PNJ `traversee`).

Ce que ces tests verrouillent :

1. **Le navire ne saute jamais de case** : les points de passage d'une route sont développés en
   cases contiguës sur 8 directions, sans doublon.
2. **Le danger est porté par la ROUTE** : le segment en vigueur, son intensité (et non
   `intensite_max` du zone-def, faite pour l'exploration) et sa zone, posée sur la seule case
   du navire — c'est ce lieu « vu depuis le navire » que lit `start_combat`.
3. **Le cycle embarquer → avancer → débarquer** : état sur le personnage, `lieu` = carte de
   mer pendant le voyage, quais d'arrivée à la fin, état retiré.
4. **Le capitaine vend son quai** : prix par tête + montures, bourse vide ⇒ `sans_fonds` sans
   rien débiter ni sauver, embarquement sinon.
5. **À terre comme en mer, une seule porte** : `move_character` refuse tout pas en mer, et
   `avancer` refuse à terre.
"""

import asyncio

import pytest
from fastapi import HTTPException

from utils import traversee


ROUTE = {
	"_id": "traversee:a_b", "type": "traversee", "label": "Traversée vers B",
	"depart": {"lieu": "lieu:a_quais"},
	"arrivee": {"lieu": "lieu:b_quais", "pos": [3, 4]},
	"carte": "lieu:mer",
	"chemin": [[0, 0], [4, 2], [4, 5]],
	"segments": [{"de": 0, "zone": "zone:mer_cotiere", "intensite": 0.2},
				 {"de": 3, "zone": "zone:haute_mer", "intensite": 0.5}],
	"rencontres": [{"espece": "espece:kraken", "zones": ["zone:haute_mer"]}],
	"prix": {"passager_cuivre": 150, "monture_cuivre": 100},
}
ZONES = {
	"zone:mer_cotiere": {"_id": "zone:mer_cotiere", "intensite_max": 0.9,
						 "table_evenements": [{"type": "combat", "poids": 1, "tags": ["monstre_marin"]}]},
	"zone:haute_mer": {"_id": "zone:haute_mer", "intensite_max": 0.9,
					   "table_evenements": [{"type": "combat", "poids": 1, "tags": ["kraken"]}]},
}


# ── Chemin ───────────────────────────────────────────────────────────────────────

def test_le_chemin_est_contigu_sur_huit_directions():
	cases = traversee.cases_du_chemin(ROUTE["chemin"])
	assert cases[0] == [0, 0] and cases[-1] == [4, 5]
	for (x0, y0), (x1, y1) in zip(cases, cases[1:]):
		assert max(abs(x1 - x0), abs(y1 - y0)) == 1     # jamais de saut, jamais sur place
	assert traversee.total_etapes(ROUTE) == len(cases)


def test_un_point_repete_ne_fait_pas_de_case_double():
	assert traversee.cases_du_chemin([[2, 2], [2, 2], [3, 2]]) == [[2, 2], [3, 2]]


# ── Segments de danger ──────────────────────────────────────────────────────────

def test_le_segment_en_vigueur_est_le_dernier_commence():
	assert traversee.segment_a(ROUTE, 0)["zone"] == "zone:mer_cotiere"
	assert traversee.segment_a(ROUTE, 2)["zone"] == "zone:mer_cotiere"
	assert traversee.segment_a(ROUTE, 3)["zone"] == "zone:haute_mer"


def test_la_probabilite_est_celle_du_segment_pas_du_zone_def():
	# intensite_max du zone-def = 0.9 ; segment = 0.2. Un tirage à 0.5 ne déclenche RIEN.
	assert traversee.evenement_etape(ROUTE, 0, ZONES, rand_fn=lambda: 0.5) is None
	ev = traversee.evenement_etape(ROUTE, 0, ZONES, rand_fn=lambda: 0.1)
	assert ev["type"] == "combat" and ev["intensite"] == pytest.approx(0.2)
	ev = traversee.evenement_etape(ROUTE, 3, ZONES, rand_fn=lambda: 0.4)
	assert ev["zones_actives_ids"] == ["zone:haute_mer"]


def test_sans_zone_connue_aucune_rencontre():
	assert traversee.evenement_etape(ROUTE, 0, {}, rand_fn=lambda: 0.0) is None


def test_le_lieu_vu_du_navire_porte_la_zone_sur_sa_seule_case():
	from utils.zones import compute_zone_intensity
	carte = {"_id": "lieu:mer", "label": "La Manche", "zone_influences": [], "rencontres": []}
	lieu = traversee.lieu_en_mer(carte, ROUTE, 3)
	x, y = traversee.cases_du_chemin(ROUTE["chemin"])[3]
	(placement,) = lieu["zone_influences"]
	assert placement["zone"] == "zone:haute_mer"
	assert compute_zone_intensity(x, y, placement, {"intensite_max": 1}) > 0
	assert compute_zone_intensity(x + 1, y, placement, {"intensite_max": 1}) == 0
	assert lieu["rencontres"] == ROUTE["rencontres"]
	assert carte["zone_influences"] == []                    # la carte n'est jamais mutée


# ── Prix ────────────────────────────────────────────────────────────────────────

def test_prix_par_tete_et_par_monture():
	assert traversee.prix(ROUTE, 1, 0) == 150
	assert traversee.prix(ROUTE, 3, 2) == 3 * 150 + 2 * 100
	assert traversee.prix(ROUTE, 0, 0) == 150               # le joueur paie toujours sa place


def test_texte_bourse():
	assert traversee.texte_bourse(150) == "1 argent et 50 cuivre"
	assert traversee.texte_bourse(10_000) == "1 or"
	assert traversee.texte_bourse(0) == "rien"


# ── Cycle de vie ────────────────────────────────────────────────────────────────

def _perso(**champs):
	base = {"_id": "character:u_1", "type": "character", "user_id": "u",
			"lieu": "lieu:a_quais", "position": {"x": 1, "y": 1},
			"objets_au_sol": [{"item": "item:x"}], "ressource_recoltable": {"item": "item:y"},
			"or": 0, "argent": 5, "cuivre": 0, "groupe": [], "montures": []}
	base.update(champs)
	return base


def test_embarquer_avancer_debarquer():
	char = _perso()
	traversee.embarquer(char, ROUTE, debut=123)
	assert traversee.en_mer(char)
	assert char["lieu"] == "lieu:mer" and char["position"] == {"x": 0, "y": 0}
	assert char["traversee"] == {"route": "traversee:a_b", "etape": 0,
								 "depart_lieu": "lieu:a_quais", "debut": 123}
	assert char["objets_au_sol"] == [] and char["ressource_recoltable"] is None

	total = traversee.total_etapes(ROUTE)
	statuts = [traversee.avancer(char, ROUTE) for _ in range(total - 1)]
	assert statuts[:-1] == ["en_mer"] * (total - 2) and statuts[-1] == "arrivee"
	assert [char["position"]["x"], char["position"]["y"]] == ROUTE["chemin"][-1]

	pos = traversee.debarquer(char, ROUTE)
	assert pos == {"x": 3, "y": 4} and char["lieu"] == "lieu:b_quais"
	assert not traversee.en_mer(char) and "traversee" not in char


def test_avancer_ne_depasse_jamais_la_derniere_case():
	char = _perso()
	traversee.embarquer(char, ROUTE)
	for _ in range(traversee.total_etapes(ROUTE) + 5):
		traversee.avancer(char, ROUTE)
	assert char["traversee"]["etape"] == traversee.total_etapes(ROUTE) - 1


def test_payload_client():
	char = _perso()
	assert traversee.payload_client(char, ROUTE, "B", 900) is None
	traversee.embarquer(char, ROUTE)
	assert traversee.payload_client(char, ROUTE, "B", 900) == {
		"route": "traversee:a_b", "etape": 0, "total": traversee.total_etapes(ROUTE),
		"destination": "B", "pas_ms": 900}


# ── Service PNJ « traversee » ───────────────────────────────────────────────────

CAPITAINE = {"_id": "pnj:capitaine_a", "type": "pnj", "nom": "Capitaine",
			 "services": {"traversee": {"route": "traversee:a_b",
										"noeuds": {"embarque": "a_bord", "sans_fonds": "pauvre"}}}}
QUAIS_A = {"_id": "lieu:a_quais", "type": "lieu", "categorie": "quai", "label": "Quais de A"}
QUAIS_B = {"_id": "lieu:b_quais", "type": "lieu", "categorie": "quai", "label": "Quais de B",
		   "lieu_parent": "lieu:b"}
CITE_B = {"_id": "lieu:b", "type": "lieu", "categorie": "ville", "label": "Bport"}


@pytest.fixture
def base(monkeypatch):
	from routers import pnj as rp
	from routers import traversee as rt
	docs = {d["_id"]: d for d in (ROUTE, CAPITAINE, QUAIS_A, QUAIS_B, CITE_B)}
	sauves = []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		sauves.append(doc["_id"])
		return doc

	for mod in (rp, rt):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
	return {"docs": docs, "sauves": sauves, "rp": rp, "rt": rt}


def test_le_capitaine_annonce_port_tarif_et_passagers(base):
	offre = base["rp"]._offre_traversee(_perso(), CAPITAINE, QUAIS_A)
	assert offre["cout"] == 150
	assert offre["placeholders"] == {"port_arrivee": "Bport", "tarif": "1 argent et 50 cuivre",
									 "passagers": 1}


def test_un_capitaine_ne_vend_que_son_quai(base):
	assert base["rp"]._offre_traversee(_perso(), CAPITAINE, QUAIS_B) is None


def test_embarquer_debite_et_met_en_mer(base):
	char = _perso()
	reponse = {}
	suivant = base["rp"]._resoudre_traversee(char, CAPITAINE, QUAIS_A, "embarquer", reponse)
	assert suivant == "a_bord"
	assert traversee.en_mer(char) and char["lieu"] == "lieu:mer"
	assert reponse["purse"] == {"or": 0, "argent": 3, "cuivre": 50}
	assert reponse["traversee"] == {"port": "Bport"}
	assert base["sauves"] == ["character:u_1"]


def test_bourse_vide_ni_debit_ni_sauvegarde(base):
	char = _perso(argent=1)
	suivant = base["rp"]._resoudre_traversee(char, CAPITAINE, QUAIS_A, "embarquer", {})
	assert suivant == "pauvre"
	assert not traversee.en_mer(char) and char["argent"] == 1
	assert base["sauves"] == []


def test_on_n_embarque_pas_deux_fois(base):
	char = _perso()
	traversee.embarquer(char, ROUTE)
	with pytest.raises(HTTPException) as e:
		base["rp"]._resoudre_traversee(char, CAPITAINE, QUAIS_A, "embarquer", {})
	assert e.value.status_code == 409


# ── Endpoints : une seule porte à terre comme en mer ────────────────────────────

def test_avancer_refuse_a_terre(base, monkeypatch):
	rt = base["rt"]
	monkeypatch.setattr(rt, "get_selected_character", lambda _u: _perso())
	with pytest.raises(HTTPException) as e:
		asyncio.run(rt.traversee_avancer({"_id": "u"}))
	assert e.value.status_code == 409


def test_avancer_debarque_par_les_effets_d_arrivee(base, monkeypatch):
	rt = base["rt"]
	char = _perso()
	traversee.embarquer(char, ROUTE)
	char["traversee"]["etape"] = traversee.total_etapes(ROUTE) - 2
	appels = []

	def effets(c, destination, pos, lieu_doc):
		appels.append((destination, pos, lieu_doc["_id"]))
		return {"moved": 1}

	monkeypatch.setattr(rt, "get_selected_character", lambda _u: char)
	monkeypatch.setattr(rt, "_effets_arrivee", effets)
	data = asyncio.run(rt.traversee_avancer({"_id": "u"}))
	assert data == {"moved": 1, "arrive": True, "port": "Bport"}
	assert appels == [("lieu:b_quais", {"x": 3, "y": 4}, "lieu:b_quais")]
	assert not traversee.en_mer(char)


def test_move_character_refuse_tout_pas_en_mer(monkeypatch):
	from routers import user as ru
	char = _perso()
	traversee.embarquer(char, ROUTE)
	monkeypatch.setattr(ru, "get_selected_character", lambda _u: char)
	for move in ({"x": 1, "y": 0}, {"x": 0, "y": 0}, {"link": "link:x"}):
		with pytest.raises(HTTPException) as e:
			asyncio.run(ru.move_character(None, {"_id": "u"}, move))
		assert e.value.status_code == 409
