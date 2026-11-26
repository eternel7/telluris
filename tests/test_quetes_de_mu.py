# tests/test_quetes_de_mu.py
# Les quêtes de Mu (dev/gen_quetes_de_mu.py) : contrôles du générateur, trois états des donneurs,
# barrières des lieux d'affaire, preuves remises par les PNJ des lieux, choix définitif d'Échidna,
# Aélis absente du fare quand elle est ailleurs, calibrage des salles. Docs rebâtis sur le dump le
# PLUS RÉCENT (glob, CLAUDE.md §20) — jamais sur le fichier à importer.

import glob
import importlib.util
import json
import os
import re

import pytest

from models import character_stats
from utils import acces, lint_dialogues, marche, pnj

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_quetes_de_mu.py")
	spec = importlib.util.spec_from_file_location("gen_quetes_de_mu", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


G = _gen()
_DUMPS = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
pytestmark = pytest.mark.skipif(not _DUMPS, reason="aucun dump jsons/telluris-dump-*.json")

# Rangs que mesure le moteur du bestiaire (gen_armure_naturelle.rangs_du_dump, dump du 26/11), INJECTÉS :
# la mesure réelle remplace `db.config.get_doc` dans tout le process et fausserait les autres tests.
RANGS = {"espece:naga": "D", "espece:murene_geante": "D", "espece:echidna": "B"}

if _DUMPS:
	with open(_DUMPS[-1], encoding="utf-8") as _f:
		BASE = {d["_id"]: d for d in json.load(_f)["docs"]}
	DOCS = {d["_id"]: d for d in G.generer(BASE, lambda docs: RANGS)}

# (donneur, quête, objet, quête prérequise) — un apport par donneur.
APPORTS = [
	(G.RANGI, G.Q_EAUX, G.NAGA, G.PARTIR),
	(G.ANA, G.Q_CONFIANCE, G.REGISTRE, G.Q_SERVICE),
	(G.HINE, G.Q_CHANT, G.FRAGMENTS_CHANT, G.PARTIR),
	(G.MERE, G.Q_MARCHAND, G.INVENTAIRE_DEPOT, G.PARTIR),
	(G.ATAAHUA, G.Q_ENFANTS, G.TABLETTE, G.PARTIR),
	(G.TAMATOA, G.Q_POISSONS, G.RELEVE_COURANTS, G.PARTIR),
	(G.KAURI, G.Q_CARTOGRAPHES, G.CARTE_INCERTAINE, G.Q_CONFIANCE),
	(G.MAHINA, G.Q_GARDIEN, G.PLAQUE_ARCHIVE, G.Q_CONFIANCE),
	(G.RAWIRI, G.Q_NOM, G.RAPPORT, G.Q_CONFIANCE),
]
# (PNJ qui remet la preuve, quête, objet, énigme, lieu de l'affaire).
REMISES = [
	(G.KORO, G.Q_CONFIANCE, G.REGISTRE, G.E_SOUFFLEUR, G.ATELIER),
	(G.RAWIRI_SANCTUAIRE, G.Q_CHANT, G.FRAGMENTS_CHANT, G.E_CHANT, G.SANCTUAIRE),
	(G.PIRIPI, G.Q_MARCHAND, G.INVENTAIRE_DEPOT, G.E_DEPOT, G.DEPOT),
	(G.MAHINA_BASSIN, G.Q_ENFANTS, G.TABLETTE, G.E_BASSIN, G.CHAMBRE_HYDRAULIQUE),
	(G.NGAIRE_STRUCTURE, G.Q_POISSONS, G.RELEVE_COURANTS, G.E_COURANTS, G.STRUCTURE),
	(G.WIREMU, G.Q_CARTOGRAPHES, G.CARTE_INCERTAINE, G.E_RELEVES, G.RELEVES),
	(G.SENTINELLE, G.Q_GARDIEN, G.PLAQUE_ARCHIVE, G.E_RITE, G.PORTE_CONDAMNEE),
	(G.HUIA, G.Q_NOM, G.RAPPORT, G.E_REGISTRES, G.RESERVE),
]


def _visibles(pnj_id, noeud="accueil", actives=(), reussies=(), flags=None, enigmes=(), passages=None):
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {},
				"enigmes_resolues": set(enigmes), "passages": passages or {}}
	contexte.update(flags or {})
	return {c["id"] for c in pnj._choix_visibles(DOCS[pnj_id], noeud, contexte)}


def _perso(actives=(), reussies=(), victoires=(), enigmes=(), inventaire=()):
	return {"quetes_actives": [{"id": q, "objectif": o} for q, o in actives],
			"quetes_terminees": [{"id": q, "echec": False} for q in reussies],
			"battle_maps_gagnees": list(victoires),
			"enigmes": {e: {"resolue": True} for e in enigmes},
			"inventaire": [{"item": i, "poids": 1} for i in inventaire]}


def _get(i):
	return DOCS.get(i) or BASE.get(i)


def _ok(perso, conditions):
	return acces.clauses_remplies(perso, conditions, _get)


def _entree(lieu_id, pnj_id):
	return next(e for e in DOCS[lieu_id]["pnj"] if e["character"] == pnj_id)


# ── Contrôles du générateur ─────────────────────────────────────────────────────

def test_le_generateur_ne_produit_aucune_faute():
	assert G.V.controler(list(DOCS.values()), BASE) == []
	assert G._portes_praticables(BASE) == []


def test_aucun_dialogue_ne_porte_d_erreur_ni_d_avertissement():
	for d in DOCS.values():
		assert not lint_dialogues.analyser_doc(d), d["_id"]


def test_toute_quete_nommee_existe():
	"""Un id de quête mal recopié masquerait un choix en silence (fail-closed)."""
	neufs = [d for i, d in DOCS.items() if i not in BASE or i in (G.AUBERGISTE, G.MARCHANDE, G.TEMPLIER, G.AELIS_MU)]
	nommees = set(re.findall(r'"(quete:[a-z0-9_]+)"', json.dumps(neufs, ensure_ascii=False)))
	assert nommees <= set(G.QUETES) | {G.PARTIR}
	offres = set()
	for d in DOCS.values():
		for serv in (d.get("services") or {}).values():
			if isinstance(serv, dict) and isinstance(serv.get("offre"), dict):
				offres.add(serv["offre"]["id"])
	assert set(G.QUETES) <= offres


def test_un_donneur_ne_tient_qu_une_offre_par_service():
	"""Plusieurs `offres` se tirent au hasard sans voir les prérequis du dialogue."""
	for d in DOCS.values():
		for nom, serv in (d.get("services") or {}).items():
			assert not (isinstance(serv, dict) and serv.get("offres")), (d["_id"], nom)


def test_regeneration_idempotente():
	"""Rejouée sur un dump où l'import est fait, la sortie ne change rien. Les espèces déjà en base ne
	sont plus réémises par le moteur du bestiaire (gen_monstres_legendes) : seules elles manquent."""
	relu = dict(BASE, **{i: dict(d, _rev="1-x") for i, d in DOCS.items()})
	regen = {d["_id"]: d for d in G.generer(relu, lambda docs: RANGS)}
	assert all(DOCS[i] == d for i, d in regen.items())
	assert set(DOCS) - set(regen) <= {i for i in DOCS if i.startswith(("espece:", "item:naga", "item:murene", "item:echidna", "competence:"))}


def test_la_porte_du_fare_est_recalee_sur_la_grille():
	x, y = next(n["pos"] for n in DOCS["link:fare_des_marees_to_mu"]["nodes"] if n["lieu"] == G.MU)
	assert BASE[G.MU]["cells"][y][x] == 1


# ── Donneurs : trois états ─────────────────────────────────────────────────────

@pytest.mark.parametrize("donneur, q, item, prerequis", APPORTS)
def test_donneur_trois_etats(donneur, q, item, prerequis):
	assert DOCS[donneur]["services"]["apport"]["offre"]["item"] == item
	avant = _visibles(donneur, reussies=[G.PARTIR, prerequis], flags={"apport_offert": True})
	sans_prerequis = _visibles(donneur, reussies=[G.PARTIR], flags={"apport_offert": True})
	pendant = _visibles(donneur, actives=[q], reussies=[G.PARTIR, prerequis],
						flags={"apport_en_cours": True, "apport_possible": False})
	remise = _visibles(donneur, actives=[q], flags={"apport_en_cours": True, "apport_possible": True})
	apres = _visibles(donneur, reussies=[G.PARTIR, prerequis, q])
	assert "offre" in avant and not {"rappel", "remettre", "souvenir"} & avant
	assert prerequis == G.PARTIR or "offre" not in sans_prerequis
	assert "rappel" in pendant and not {"offre", "souvenir", "remettre"} & pendant
	assert "remettre" in remise
	assert "souvenir" in apres and not {"offre", "rappel"} & apres


@pytest.mark.parametrize("donneur, q, item, prerequis", APPORTS)
def test_issues_parlees_a_la_remise(donneur, q, item, prerequis):
	"""Trois issues là où le lore en donne trois ; une seule fin pour le chant, les enfants et les
	cartographes, dont le récit arbitré fixe la conclusion."""
	remis = DOCS[donneur]["dialogue"]["noeuds"]["remis"]
	attendu = 1 if q in (G.Q_CHANT, G.Q_ENFANTS, G.Q_CARTOGRAPHES) else 3
	assert len(remis["choix"]) == attendu and all(c["next"].startswith("issue_") for c in remis["choix"])


# ── Lieux d'affaire et preuves ─────────────────────────────────────────────────

@pytest.mark.parametrize("remettant, q, item, enigme_id, lieu_id", REMISES)
def test_la_preuve_se_remet_enigme_resolue_et_quete_en_cours(remettant, q, item, enigme_id, lieu_id):
	assert DOCS[remettant]["services"]["don"]["item"] == item
	assert DOCS[remettant]["services"]["don"]["unique"] is True
	assert DOCS[enigme_id]["lieux"] == [lieu_id]
	assert "prendre" not in _visibles(remettant, actives=[q], flags={"don_recu": False})
	assert "regarder" in _visibles(remettant, actives=[q], flags={"don_recu": False})
	assert "prendre" in _visibles(remettant, actives=[q], enigmes=[enigme_id], flags={"don_recu": False})
	assert "prendre" not in _visibles(remettant, actives=[q], enigmes=[enigme_id], flags={"don_recu": True})
	assert "prendre" not in _visibles(remettant, reussies=[q], enigmes=[enigme_id], flags={"don_recu": False})


@pytest.mark.parametrize("remettant, q, item, enigme_id, lieu_id", REMISES)
def test_le_lieu_de_l_affaire_s_ouvre_pendant_et_apres(remettant, q, item, enigme_id, lieu_id):
	lieu = DOCS[lieu_id]
	conditions = (lieu.get("acces") or {}).get("conditions") or []
	if lieu_id in G.PORTES_MU and not conditions:
		# Lieu de ville ouvert à tous : c'est la PRÉSENCE du PNJ qui suit la quête — ou, pour l'atelier
		# du souffleur, que Koro tient tous les jours, l'énigme seule.
		conditions = _entree(lieu_id, remettant)["conditions"] or DOCS[enigme_id]["conditions"]
		if lieu_id == G.ATELIER:
			assert _ok(_perso(reussies=[q]), _entree(lieu_id, remettant)["conditions"])
			assert not _ok(_perso(reussies=[q]), conditions)
			return
	active = [(q, {"type": "collect", "cible": item})]
	assert not _ok(_perso(), conditions)
	assert _ok(_perso(actives=active), conditions)
	assert _ok(_perso(reussies=[q]), conditions)
	assert acces.conditions_invalides({"acces": {"conditions": conditions}}) == []


def test_les_enigmes_ne_s_ouvrent_que_quete_en_cours():
	for _, q, item, enigme_id, _ in REMISES:
		cond = DOCS[enigme_id]["conditions"]
		assert not _ok(_perso(actives=[("quete:autre", {"type": "collect", "cible": "item:autre"})]), cond)
		assert _ok(_perso(actives=[(q, {"type": "collect", "cible": item})]), cond)
		assert not _ok(_perso(reussies=[q]), cond)


def test_toutes_les_clauses_d_acces_et_de_presence_sont_du_vocabulaire_des_barrieres():
	"""`quete_active` n'y connaît pas `id` : un sous-filtre inconnu y est IGNORÉ, donc permissif."""
	for d in DOCS.values():
		blocs = []
		if d.get("type") == "enigme":
			blocs.append(d.get("conditions") or [])
		if d.get("acces"):
			blocs.append(d["acces"].get("conditions") or [])
		blocs += [e.get("conditions") or [] for e in d.get("pnj") or [] if isinstance(e, dict)]
		for b in blocs:
			assert acces.conditions_invalides({"acces": {"conditions": b}}) == [], d["_id"]


def test_la_copie_du_releve_ne_se_vend_pas():
	assert marche.item_invendable(DOCS[G.COPIE_RELEVE])


# ── Eaux troubles et service ──────────────────────────────────────────────────

def test_les_conduites_ne_portent_que_des_naga_tant_que_la_preuve_n_est_pas_remise():
	d = DOCS[G.D_CONDUITES]["battle_maps"][0]
	assert d["especes"] == [G.E_NAGA] and d["composition"] == {G.E_NAGA: 3}
	assert DOCS[G.NAGA]["source_espece"] == G.E_NAGA
	cond = DOCS[G.CONDUITES]["acces"]["conditions"]
	assert _ok(_perso(actives=[(G.Q_EAUX, {"type": "collect", "cible": G.NAGA, "quantite": 1})]), cond)
	assert not _ok(_perso(reussies=[G.Q_EAUX]), cond)


def test_le_sas_exige_la_faille_calme_et_la_piece_de_kahu():
	cond = DOCS[G.SAS]["acces"]["conditions"]
	escorte = [(G.Q_SERVICE, {"type": "escorte", "cible": G.AUBERGE})]
	assert not _ok(_perso(actives=escorte, inventaire=[G.PIECE_SAS]), cond)
	assert not _ok(_perso(actives=escorte, victoires=[G.LISIERE]), cond)
	assert _ok(_perso(actives=escorte, victoires=[G.LISIERE], inventaire=[G.PIECE_SAS]), cond)
	assert any(a["item"] == G.PIECE_SAS for a in DOCS[G.MARCHANDE]["services"]["vente"]["articles"])
	assert DOCS[G.AUBERGISTE]["services"]["escorte"]["offre"]["rencontre"] == {"lieu": G.SAS}


def test_moana_trois_etats():
	avant = _visibles(G.AUBERGISTE, reussies=[G.PARTIR, G.Q_EAUX], flags={"escorte_offerte": True})
	pendant = _visibles(G.AUBERGISTE, actives=[G.Q_SERVICE], reussies=[G.PARTIR, G.Q_EAUX])
	apres = _visibles(G.AUBERGISTE, reussies=[G.PARTIR, G.Q_EAUX, G.Q_SERVICE])
	assert "service_offre" in avant and not {"service_relance", "service_souvenir"} & avant
	assert "service_relance" in pendant and "service_offre" not in pendant
	assert "service_souvenir" in apres and "service_offre" not in apres
	assert "service_offre" not in _visibles(G.AUBERGISTE, reussies=[G.PARTIR], flags={"escorte_offerte": True})


# ── La descente ──────────────────────────────────────────────────────────────

def test_aelis_propose_la_descente_apres_la_confiance():
	offerte = {"escorte_offerte": True}
	assert "descente_offre" in _visibles(G.AELIS_MU, reussies=[G.PARTIR, G.Q_CONFIANCE], flags=offerte)
	assert "descente_offre" not in _visibles(G.AELIS_MU, reussies=[G.PARTIR, G.Q_SERVICE], flags=offerte)


def test_aelis_quitte_le_fare_pendant_la_descente_et_devant_le_sceau():
	cond = _entree(G.AUBERGE, G.AELIS_MU)["conditions"]
	descente = [(G.Q_DESCENTE, {"type": "escorte", "cible": G.CHAMBRE})]
	assert _ok(_perso(reussies=[G.PARTIR]), cond)
	assert not _ok(_perso(actives=descente, reussies=[G.PARTIR]), cond)
	assert not _ok(_perso(reussies=[G.PARTIR, G.Q_DESCENTE]), cond)
	assert _ok(_perso(reussies=[G.PARTIR, G.Q_DESCENTE], enigmes=[G.E_SCELLEMENT]), cond)
	sceau = _entree(G.CHAMBRE, G.AELIS_SCEAU)["conditions"]
	assert _ok(_perso(reussies=[G.Q_DESCENTE]), sceau)
	assert not _ok(_perso(reussies=[G.Q_DESCENTE], enigmes=[G.E_SCELLEMENT]), sceau)


def test_la_chambre_s_ouvre_aux_vannes_reglees_et_l_antre_au_scellement_compris():
	descente = [(G.Q_DESCENTE, {"type": "escorte", "cible": G.CHAMBRE})]
	chambre = DOCS[G.CHAMBRE]["acces"]["conditions"]
	assert not _ok(_perso(actives=descente), chambre)
	assert _ok(_perso(actives=descente, enigmes=[G.E_VANNES]), chambre)
	antre = DOCS[G.ANTRE]["acces"]["conditions"]
	assert not _ok(_perso(reussies=[G.Q_DESCENTE]), antre)
	assert _ok(_perso(reussies=[G.Q_DESCENTE], enigmes=[G.E_SCELLEMENT]), antre)


# ── Échidna : un choix définitif ───────────────────────────────────────────────

def test_parler_ferme_le_combat_et_combattre_fait_fuir_echidna():
	salle = DOCS[G.COMBAT_ANTRE]["acces"]["conditions"]
	parole = [(G.Q_PAROLE, {"type": "transport", "cible": G.INSTITUT})]
	assert _ok(_perso(), salle)
	assert not _ok(_perso(actives=parole), salle)
	assert not _ok(_perso(reussies=[G.Q_PAROLE]), salle)
	assert not _ok(_perso(victoires=[G.COMBAT_ANTRE]), salle)
	echidna = _entree(G.ANTRE, G.ECHIDNA)["conditions"]
	aelis = _entree(G.ANTRE, G.AELIS_ANTRE)["conditions"]
	assert _ok(_perso(), echidna) and not _ok(_perso(), aelis)
	assert not _ok(_perso(victoires=[G.COMBAT_ANTRE]), echidna) and _ok(_perso(victoires=[G.COMBAT_ANTRE]), aelis)


def test_echidna_trois_etats_et_le_releve_sur_la_voie_de_la_parole():
	avant = _visibles(G.ECHIDNA, flags={"transport_offert": True})
	pendant = _visibles(G.ECHIDNA, actives=[G.Q_PAROLE])
	apres = _visibles(G.ECHIDNA, reussies=[G.Q_PAROLE], flags={"don_recu": False})
	assert {"qui", "ecouter", "combattre"} <= avant and not {"parole_en_cours", "releve"} & avant
	assert "parole_en_cours" in pendant and not {"ecouter", "combattre"} & pendant
	assert {"parole_apres", "releve"} <= apres and "combattre" not in apres
	assert DOCS[G.ECHIDNA]["services"]["don"]["item"] == G.COPIE_RELEVE
	assert DOCS[G.AELIS_ANTRE]["services"]["don"]["item"] == G.COPIE_RELEVE
	assert DOCS[G.ECHIDNA]["services"]["transport"]["offre"]["destination"] == G.INSTITUT
	assert "ecaille_livree" == DOCS[G.ANA]["services"]["transport"]["noeuds"]["livre"]


def test_echidna_fuit_et_laisse_sa_mue():
	assert DOCS["item:echidna"]["nom"] == "Mue d'Échidna"
	assert DOCS[G.E_ECHIDNA].get("nom_propre") is True and DOCS[G.E_ECHIDNA]["genre"] == "f"


# ── Calibrage (potentiel mesuré sur le dump augmenté des espèces neuves) ────────

def _potentiel(espece, profil):
	from utils import potentiel
	return potentiel.potentiel_menace(espece, profil, _get)[0]


def test_trois_naga_passent_le_rang_a_et_echidna_le_rang_s():
	plancher = character_stats.QUETE_RANG_POTENTIEL_MIN
	naga = _potentiel(G.E_NAGA, "profil:veteran")
	assert naga < plancher["A"] <= 3 * naga
	assert _potentiel(G.E_ECHIDNA, "profil:heros") >= plancher["S"]
