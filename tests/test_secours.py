# tests/test_secours.py
#
# Quêtes de SECOURS (utils/secours.py) : 4ᵉ source de la famille escorte. Le comptoir de la
# guilde confie le sauvetage d'aventuriers en péril autour de la cité, ou dans un donjon
# proche. Tests PURS — DB, connexions, générateur d'aventuriers et hasard sont injectés.

import copy

import pytest

from models import character_stats
from utils import combat as combat_util
from utils import escorte as escorte_util
from utils import secours


# ── Monde de test ────────────────────────────────────────────────────────────────

RACES = {"_id": "rules:races", "value": [{"id": "humain", "stats": {
	"V": 5, "F": 20, "R": 20, "Ag": 20, "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20}}]}

CITE = {"_id": "lieu:lutecia", "type": "lieu", "label": "Lutecia", "categorie": "ville",
		"dimensions": {"x": 10, "y": 10}, "cells": [[1] * 10 for _ in range(10)],
		"zone_influences": [{"zone": "zone:coeur", "x": 2, "y": 2},
							{"zone": "zone:foret", "x": 6, "y": 6}]}
FORET_VOISINE = {"_id": "lieu:bois", "type": "lieu", "label": "Le bois de Vincennes",
				 "categorie": "foret", "dimensions": {"x": 10, "y": 10},
				 "cells": [[1] * 10 for _ in range(10)],
				 "zone_influences": [{"zone": "zone:bois_profond", "x": 5, "y": 5}]}
LOIN = {"_id": "lieu:loin", "type": "lieu", "label": "Très loin", "categorie": "foret",
		"dimensions": {"x": 10, "y": 10}, "cells": [[1] * 10 for _ in range(10)],
		"zone_influences": [{"zone": "zone:foret", "x": 5, "y": 5}]}
COMPTOIR = {"_id": "lieu:comptoir", "type": "lieu", "label": "Le Grand Relais",
			"categorie": "guilde_aventurier_comptoir", "lieu_parent": "lieu:lutecia"}

ZONES = [
	{"_id": "zone:coeur", "type": "zone", "modificateurs": {"danger": -3}},
	{"_id": "zone:foret", "type": "zone", "modificateurs": {"danger": 1}},
	{"_id": "zone:bois_profond", "type": "zone", "modificateurs": {"danger": 2}},
]

ETAGE_1 = {"_id": "lieu:cata1", "type": "lieu", "categorie": "battle_map",
		   "label": "Un vaste réseau souterrain", "tags": ["donjon"]}
ETAGE_2 = {"_id": "lieu:cata2", "type": "lieu", "categorie": "battle_map",
		   "label": "Des galeries plus profondes", "tags": ["donjon"]}
CATACOMBES = {"_id": "donjon:cata", "type": "donjon", "nom": "Catacombes de Lutécia",
			  "mode": "etages",
			  "battle_maps": [{"lieu": "lieu:cata1", "niveau_min": 3, "niveau_max": 4},
							  {"lieu": "lieu:cata2", "niveau_min": 4, "niveau_max": 5}]}
# Donjon CLASSIQUE dont le portail est un sous-lieu de la cité (temple d'Orléans) ; sa salle
# laisse les protégés à la porte — elle ne peut donc pas accueillir de rendez-vous.
TEMPLE = {"_id": "lieu:temple", "type": "lieu", "label": "Temple", "lieu_parent": "lieu:lutecia"}
NEF = {"_id": "lieu:nef", "type": "lieu", "categorie": "battle_map", "tags": ["donjon"],
	   "proteges_restent_dehors": True}
CRYPTE = {"_id": "donjon:crypte", "type": "donjon", "nom": "Crypte", "portail": "lieu:temple",
		  "niveau_min": 2, "battle_maps": [{"lieu": "lieu:nef"}]}

CONNEXIONS = {
	"lieu:lutecia": [
		{"_id": "link:a", "nodes": [{"lieu": "lieu:lutecia"}, {"lieu": "lieu:bois"}]},
		{"_id": "link:b", "nodes": [{"lieu": "lieu:cata1"}, {"lieu": "lieu:lutecia"}]},
		{"_id": "link:c", "nodes": [{"lieu": "lieu:lutecia"}, {"lieu": "lieu:temple"}]},
	],
}

BORIN_SECOURS = {"_id": "pnj:prepose", "type": "pnj", "nom": "Préposé",
				 "services": {"escorte": {"secours": {"cite": "lieu:lutecia"},
										  "noeuds": {"secours_accepte": "secours_acceptee"}}}}


def connexions_fn(lieu_id):
	return CONNEXIONS.get(lieu_id, [])


def _correspond(doc, selector):
	for k, v in (selector or {}).items():
		if isinstance(v, dict) and "$in" in v:
			if doc.get(k) not in v["$in"]:
				return False
		elif doc.get(k) != v:
			return False
	return True


@pytest.fixture
def db():
	# Copie PROFONDE : un test qui retouche `modificateurs` ou `tags` ne doit pas fuir dans le suivant.
	docs = {d["_id"]: copy.deepcopy(d) for d in [RACES, CITE, FORET_VOISINE, LOIN, COMPTOIR, *ZONES,
										 ETAGE_1, ETAGE_2, CATACOMBES, TEMPLE, NEF, CRYPTE,
										 BORIN_SECOURS]}

	def get(doc_id):
		d = docs.get(doc_id)
		return copy.deepcopy(d) if d else None

	def save(doc):
		docs[doc["_id"]] = doc
		return doc

	def find(selector, fields=None):
		return [copy.deepcopy(d) for d in docs.values() if _correspond(d, selector)]

	return {"docs": docs, "get": get, "save": save, "find": find}


def character(**champs):
	base = {"_id": "character:u_1", "type": "character", "user_id": "user:u",
			"prenom": "Test", "nom": "Héros", "race": "humain",
			"caracteristiques_current": {"V": 5, "F": 30, "R": 30, "Ag": 30,
										 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
			"quetes_actives": [], "quetes_terminees": [], "proteges": [],
			"lieu": "lieu:comptoir", "position": {"x": 0, "y": 0}}
	base.update(champs)
	return base


def aventurier_factice(niveau_max):
	"""Doc `aventurier:*` minimal, à la forme de `recrutement.generer_aventurier`."""
	return {"prenom": "Aude", "nom": "Ferrand", "race": "humain", "sex": "F",
			"image": "guerrier_f.jpg",
			"caracteristiques_current": {"V": 6, "F": 30, "R": 30, "Ag": 25,
										 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
			"slots": {"main_droite": {"item": "item:epee", "poids": 1.5}, "tete": None}}


def _toujours(x):
	return lambda: x


def _premier(seq):
	return seq[0]


NOW = 1_800_000_000


# ── Le périmètre ─────────────────────────────────────────────────────────────────

def _cles(cands):
	return {(c["lieu"], tuple(c.get("zones") or ()), c.get("donjon")) for c in cands}


def test_perimetre_cite_voisins_et_donjon_joint(db):
	cands = secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)
	assert _cles(cands) == {
		("lieu:lutecia", ("zone:foret",), None),        # zone dangereuse DE la cité
		("lieu:bois", ("zone:bois_profond",), None),    # voisin à un saut
		("lieu:cata1", (), "donjon:cata"),              # étage joint par une connexion
		("lieu:cata2", (), "donjon:cata"),              # étage plus profond du même donjon
	}


def test_le_coeur_de_ville_n_est_pas_un_lieu_de_peril(db):
	"""Filtre STRICT : le repli « toutes les zones » d'escorte.zones_dangereuses n'est pas repris."""
	db["docs"]["zone:foret"]["modificateurs"]["danger"] = 0
	cands = secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)
	assert not [c for c in cands if c["lieu"] == "lieu:lutecia"]


def test_niveau_suit_la_zone_ou_la_salle(db):
	cands = {c["lieu"]: c for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert cands["lieu:bois"]["niveau"] == 2          # danger de la zone
	assert cands["lieu:cata1"]["niveau"] == 3         # niveau_min de la salle
	assert cands["lieu:cata2"]["etage"] == 2


def test_opt_out_par_tag_sur_lieu_salle_ou_donjon(db):
	db["docs"]["lieu:bois"]["tags"] = [secours.TAG_SANS_SECOURS]
	db["docs"]["lieu:cata2"]["tags"] = ["donjon", secours.TAG_SANS_SECOURS]
	lieux = {c["lieu"] for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert "lieu:bois" not in lieux and "lieu:cata2" not in lieux and "lieu:cata1" in lieux
	db["docs"]["donjon:cata"]["tags"] = [secours.TAG_SANS_SECOURS]
	lieux = {c["lieu"] for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert "lieu:cata1" not in lieux


def test_un_rendez_vous_ecrit_est_reserve(db):
	"""La clairière des bûcherons n'accueille pas d'inconnus : un lieu visé par une escorte
	ÉCRITE sort du périmètre."""
	db["docs"]["pnj:gautier"] = {"_id": "pnj:gautier", "type": "pnj", "services": {"escorte": {
		"offre": {"id": "quete:x", "destination": "lieu:comptoir",
				  "rencontre": {"lieu": "lieu:bois"}, "proteges": [{"prenom": "A"}]}}}}
	lieux = {c["lieu"] for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert "lieu:bois" not in lieux


def test_salle_qui_laisse_les_proteges_dehors_exclue(db):
	"""Le donjon classique joint par son portail (sous-lieu de la cité) n'a qu'une salle
	`proteges_restent_dehors` : aucun rendez-vous possible."""
	lieux = {c["lieu"] for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert "lieu:nef" not in lieux
	db["docs"]["lieu:nef"].pop("proteges_restent_dehors")
	cands = {c["lieu"]: c for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert cands["lieu:nef"]["donjon"] == "donjon:crypte" and cands["lieu:nef"]["niveau"] == 2


def test_la_carte_du_pays_n_est_pas_un_voisin(db):
	"""Voisine de toutes ses cités, la carte du pays ferait de tout le pays « les abords »."""
	db["docs"]["lieu:pays"] = {"_id": "lieu:pays", "type": "lieu", "categorie": secours.CATEGORIE_PAYS,
							   "dimensions": {"x": 10, "y": 10},
							   "zone_influences": [{"zone": "zone:foret", "x": 1, "y": 1}]}
	db["docs"]["lieu:temple"]["lieu_parent"] = "lieu:pays"      # portail posé sur la carte du pays
	db["docs"]["lieu:nef"].pop("proteges_restent_dehors")
	locales = [c for c in CONNEXIONS["lieu:lutecia"] if c["_id"] != "link:c"] + [
		{"_id": "link:p", "nodes": [{"lieu": "lieu:lutecia"}, {"lieu": "lieu:pays"}]}]
	lieux = {c["lieu"] for c in secours.candidats(
		"lieu:lutecia", db["get"], db["find"], lambda lid: locales if lid == "lieu:lutecia" else [])}
	assert "lieu:pays" not in lieux and "lieu:nef" not in lieux


def test_un_lieu_hors_du_voisinage_ignore(db):
	lieux = {c["lieu"] for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert "lieu:loin" not in lieux


# ── Rang ─────────────────────────────────────────────────────────────────────────

def test_rang_du_niveau_et_surcharge_du_bloc():
	assert secours.rang_du_niveau(3) == secours.RANGS_PAR_NIVEAU[3]
	assert secours.rang_du_niveau(99) == secours.RANGS_PAR_NIVEAU[secours.NIVEAU_MAX]
	assert secours.rang_du_niveau(3, {"rangs": {"3": "B"}}) == "B"


def test_rang_suit_la_porte_la_plus_stricte(db):
	db["docs"]["lieu:bois"]["acces"] = {"conditions": [{"rang_min": {"cite": "lieu:lutecia", "rang": "B"}}]}
	c = next(x for x in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)
			 if x["lieu"] == "lieu:bois")
	assert secours.rang_du_candidat(c, {}, None) == "B"                  # barrière > niveau 2
	assert secours.rang_du_candidat({"niveau": 1}, {}, None) == "F"


def test_un_lieu_scenarise_est_exclu(db):
	"""Une barrière qui exige autre chose qu'un rang (mandat, quête) : lieu scénarisé, exclu —
	sur un lieu explorable comme sur une salle de donjon."""
	db["docs"]["lieu:bois"]["acces"] = {"conditions": [{"quete_active": {"types": ["escorte"]}}]}
	db["docs"]["lieu:cata1"]["acces"] = {"conditions": [{"quete_active": {"types": ["chasse"]}}]}
	lieux = {c["lieu"] for c in secours.candidats("lieu:lutecia", db["get"], db["find"], connexions_fn)}
	assert "lieu:bois" not in lieux and "lieu:cata1" not in lieux and "lieu:cata2" in lieux


# ── Spec et protégés ─────────────────────────────────────────────────────────────

def test_protege_tire_d_un_aventurier_blesse_qui_se_defend():
	p = secours.protege_de_aventurier(aventurier_factice(2))
	assert p["se_defend"] is True
	assert p["pv_depart"] == character_stats.SECOURS_PV_DEPART
	assert p["equipement"] == {"main_droite": {"item": "item:epee", "poids": 1.5}}   # slot vide écarté
	assert p["caracteristiques"]["F"] == 30


def test_taille_du_groupe_bornee():
	nmin, nmax = character_stats.SECOURS_NB_MIN, character_stats.SECOURS_NB_MAX
	assert len(secours.proteges_de(1, aventurier_factice, _toujours(0.0))) == nmin
	assert len(secours.proteges_de(1, aventurier_factice, _toujours(0.999))) == nmax


def test_spec_de_donjon_porte_le_donjon_et_le_delai(db):
	c = {"lieu": "lieu:cata2", "donjon": "donjon:cata", "etage": 2, "niveau": 4}
	spec = secours.spec_secours(character(), COMPTOIR, {"cite": "lieu:lutecia"}, c, db["get"],
								"C", NOW, aventurier_factice, _toujours(0.0))
	assert spec["rencontre"] == {"lieu": "lieu:cata2", "donjon": "donjon:cata"}
	assert spec["destination"] == "lieu:comptoir" and spec["type_secours"] is True
	assert spec["expire_h"] == character_stats.SECOURS_DELAI_H
	assert spec["rang_min"] == {"cite": "lieu:lutecia", "rang": "C"}
	assert spec["recompenses"]["xp"] == character_stats.SECOURS_XP * 4
	assert "Catacombes de Lutécia, étage 2" in spec["description"]
	assert spec["id"] == secours.id_secours("lieu:cata2", NOW)


def test_id_stable_sur_la_fenetre():
	fenetre = character_stats.SECOURS_FENETRE_H * 3600
	debut = (NOW // fenetre) * fenetre
	assert secours.id_secours("lieu:bois", debut) == secours.id_secours("lieu:bois", debut + fenetre - 1)
	assert secours.id_secours("lieu:bois", debut) != secours.id_secours("lieu:bois", debut + fenetre)


# ── L'offre du comptoir ──────────────────────────────────────────────────────────

INSCRIT = {"lieu:lutecia": "F"}


def _poser(db, perso, rand=0.0, choix=_premier, pnj_doc=BORIN_SECOURS):
	return escorte_util.poser_escorte_offerte(
		perso, COMPTOIR, db["find"], db["get"], rand_fn=_toujours(rand), pnj_doc=pnj_doc,
		choix_fn=choix, now=NOW, connexions_fn=connexions_fn, generer_fn=aventurier_factice)


def test_le_comptoir_ne_secourt_qu_avec_ses_membres(db):
	perso = character()
	_poser(db, perso)
	assert perso["escorte_offerte"]["quete"] is None


def test_le_rang_filtre_avant_le_tirage(db):
	"""Un rang F se voit proposer la zone de rang F, jamais les catacombes (rang D/C)."""
	perso = character(rangs_guilde=dict(INSCRIT))
	vus = []
	_poser(db, perso, choix=lambda seq: vus.extend(seq) or seq[0])
	assert {c["lieu"] for c, _r in vus} == {"lieu:lutecia"}      # foret danger 1 → F
	q = perso["escorte_offerte"]["quete"]
	assert q["type_secours"] is True and q["giver"] == "lieu:comptoir"
	assert q["objectif"]["cible"] == "lieu:comptoir"
	assert len(q["proteges"]) >= character_stats.SECOURS_NB_MIN


def test_un_rang_d_ouvre_les_catacombes(db):
	perso = character(rangs_guilde={"lieu:lutecia": "D"})
	vus = []
	_poser(db, perso, choix=lambda seq: vus.extend(seq) or next(x for x in seq if x[0].get("donjon")))
	assert "lieu:cata1" in {c["lieu"] for c, _r in vus}
	assert "lieu:cata2" not in {c["lieu"] for c, _r in vus}       # niveau 4 → rang C
	q = perso["escorte_offerte"]["quete"]
	assert q["objectif"]["rencontre"] == {"lieu": "lieu:cata1", "donjon": "donjon:cata"}
	assert q["rang"] == "D"


def test_tirage_rate_aucune_offre(db):
	perso = character(rangs_guilde=dict(INSCRIT))
	_poser(db, perso, rand=0.99)
	assert perso["escorte_offerte"]["quete"] is None


def test_une_tranche_deja_prise_n_est_pas_reproposee(db):
	perso = character(rangs_guilde=dict(INSCRIT),
					  quetes_terminees=[{"id": secours.id_secours("lieu:lutecia", NOW), "echec": False}])
	_poser(db, perso)
	assert perso["escorte_offerte"]["quete"] is None


def test_le_registre_vide_laisse_place_au_secours(db):
	"""Même PNJ, deux blocs : sans famille à recenser, le comptoir propose un secours."""
	pnj_doc = {"_id": "pnj:p", "type": "pnj", "services": {"escorte": {
		"recherche": {"cite": "lieu:lutecia"}, "secours": {"cite": "lieu:lutecia"}}}}
	perso = character(rangs_guilde=dict(INSCRIT))
	_poser(db, perso, pnj_doc=pnj_doc)
	assert perso["escorte_offerte"]["quete"]["type_secours"] is True


def test_donneur_present_quatrieme_rang():
	muet = ({}, {"_id": "pnj:muet", "services": {}})
	secourt = ({}, {"_id": "pnj:s", "services": {"escorte": {"secours": {}}}})
	registre = ({}, {"_id": "pnj:r", "services": {"escorte": {"recherche": {"cite": "x"}}}})
	assert escorte_util.donneur_present([muet, secourt]) == secourt     # bloc vide = présent
	assert escorte_util.donneur_present([secourt, registre]) == registre


def test_pas_d_offre_pendant_une_escorte(db):
	perso = character(rangs_guilde=dict(INSCRIT),
					  quetes_actives=[{"id": "quete:e", "objectif": {"type": "escorte"}}])
	_poser(db, perso)
	assert perso["escorte_offerte"]["quete"] is None


# ── Acceptation, délai ───────────────────────────────────────────────────────────

def _accepter(db, perso):
	_poser(db, perso)
	q, docs = escorte_util.accepter_escorte(perso, perso["escorte_offerte"]["quete"], db["get"], now=NOW)
	return q, docs


def test_acceptation_pose_le_delai(db):
	perso = character(rangs_guilde=dict(INSCRIT))
	q, docs = _accepter(db, perso)
	assert docs == []                                   # on les retrouve au rendez-vous
	assert q["type_secours"] is True
	assert q["expire_at"] == NOW + character_stats.SECOURS_DELAI_H * 3600


def test_delai_depasse_echec_sans_sanction(db):
	perso = character(rangs_guilde=dict(INSCRIT))
	q, _ = _accepter(db, perso)
	echus, docs = secours.expirer(perso, q["expire_at"] - 1, db["get"])
	assert echus == [] and perso["quetes_actives"]
	echus, docs = secours.expirer(perso, q["expire_at"], db["get"])
	assert [e["id"] for e in echus] == [q["id"]]
	assert perso["quetes_actives"] == []
	assert perso["quetes_terminees"][-1]["echec"] is True


def test_traiter_deplacement_annonce_le_secours_echu(db):
	perso = character(rangs_guilde=dict(INSCRIT))
	q, _ = _accepter(db, perso)
	maj = escorte_util.traiter_deplacement(perso, CITE, {"x": 0, "y": 0}, db["get"], db["save"],
										   db["find"], now=q["expire_at"] + 1)
	assert maj["secours_echoues"] == [{"titre": q["titre"]}]


def test_une_escorte_ecrite_n_expire_jamais(db):
	perso = character(quetes_actives=[{"id": "quete:e", "objectif": {"type": "escorte"},
									   "expire_at": 1}])
	echus, _ = secours.expirer(perso, NOW, db["get"])
	assert echus == [] and perso["quetes_actives"]


# ── Rendez-vous dans le donjon ───────────────────────────────────────────────────

def _accepter_donjon(db):
	perso = character(rangs_guilde={"lieu:lutecia": "D"})
	escorte_util.poser_escorte_offerte(
		perso, COMPTOIR, db["find"], db["get"], rand_fn=_toujours(0.0), pnj_doc=BORIN_SECOURS,
		choix_fn=lambda seq: next(x for x in seq if x[0].get("donjon")), now=NOW,
		connexions_fn=connexions_fn, generer_fn=aventurier_factice)
	q, _ = escorte_util.accepter_escorte(perso, perso["escorte_offerte"]["quete"], db["get"], now=NOW)
	return perso, q


def test_le_pas_ne_declenche_pas_un_rendez_vous_de_donjon(db):
	perso, q = _accepter_donjon(db)
	maj = escorte_util.traiter_deplacement(perso, {"_id": "lieu:cata1"}, {"x": 1, "y": 1},
										   db["get"], db["save"], db["find"], now=NOW)
	assert maj["rencontres"] == [] and not q.get("rencontre_at")


def test_rencontre_en_combat_incarne_blesses_et_idempotente(db):
	perso, q = _accepter_donjon(db)
	assert escorte_util.rencontres_en_combat(perso, "lieu:cata2", db["get"], now=NOW) == []
	docs = escorte_util.rencontres_en_combat(perso, "lieu:cata1", db["get"], now=NOW)
	assert docs and all(d["se_defend"] for d in docs)
	pv_max = escorte_util.vitaux_de(docs[0])["pv_max"]
	assert docs[0]["currentPV"] == max(1, round(pv_max * character_stats.SECOURS_PV_DEPART))
	assert perso["proteges"] == [d["_id"] for d in docs]
	assert q["rencontre_at"] == NOW
	assert escorte_util.rencontres_en_combat(perso, "lieu:cata1", db["get"], now=NOW) == []


def test_ajouter_proteges_au_combat_en_cours(db):
	perso, _q = _accepter_donjon(db)
	docs = escorte_util.rencontres_en_combat(perso, "lieu:cata1", db["get"], now=NOW)
	combat_doc = {"joueurs": [{"id": "joueur_0", "character_id": perso["_id"]}],
				  "ordre_initiative": ["joueur_0", "monstre_0"], "tour": 3, "log": []}
	snaps = combat_util.ajouter_proteges(combat_doc, docs)
	assert [s["id"] for s in snaps] == [f"joueur_{i + 1}" for i in range(len(docs))]
	assert all(s["est_protege"] and not s["jouable"] and s["se_defend"] for s in snaps)
	# Ils se défendent : ils ont un tour (joué par le serveur).
	assert combat_doc["ordre_initiative"][2:] == [s["id"] for s in snaps]
	assert combat_doc["log"][-1]["kind"] == "sys"
	# Rejouer l'appel ne les double pas.
	assert combat_util.ajouter_proteges(combat_doc, docs) == []


def test_pv_depart_absent_pv_pleins(db):
	doc = escorte_util.creer_protege({"prenom": "Aline", "race": "humain"}, character(),
									 "quete:x", db["get"])
	assert doc["currentPV"] == escorte_util.vitaux_de(doc)["pv_max"]


def test_nom_du_rendez_vous_de_donjon(db):
	assert secours.nom_du_lieu({"lieu": "lieu:cata2", "donjon": "donjon:cata"}, db["get"]) \
		== "Catacombes de Lutécia, étage 2"
	db["docs"]["lieu:nef"].pop("proteges_restent_dehors")
	assert secours.nom_du_lieu({"lieu": "lieu:nef", "donjon": "donjon:crypte"}, db["get"]) == "Crypte"
