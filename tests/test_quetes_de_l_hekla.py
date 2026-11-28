# tests/test_quetes_de_l_hekla.py
# L'arc de l'Hekla (dev/gen_quetes_de_l_hekla.py) : contrôles du générateur, chemin depuis Mu et Notre-Dame,
# épreuves exclusives, trois états des donneurs, chaîne des gardiens (salles gardées, `combat_gagne`), registre
# des entrées (`intro_raison`), issue du Cocyte à sens unique, Furies en trois espèces. Docs rebâtis sur le
# dump le PLUS RÉCENT (glob, CLAUDE.md §20) — jamais sur le fichier à importer.

import glob
import importlib.util
import json
import os
import re

import pytest

from utils import acces, combat_arrivee, lint_dialogues, pnj, portails

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_quetes_de_l_hekla.py")
	spec = importlib.util.spec_from_file_location("gen_quetes_de_l_hekla", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


G = _gen()
_DUMPS = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
pytestmark = pytest.mark.skipif(not _DUMPS, reason="aucun dump jsons/telluris-dump-*.json")

# Rangs INJECTÉS (la mesure réelle remplace `db.config.get_doc` dans tout le process) : la valeur n'importe
# pas ici, seuls l'effectif et l'armure naturelle en dépendent.
RANGS = {"espece:" + s: "B" for s in G.M.NOUVELLES}

if _DUMPS:
	with open(_DUMPS[-1], encoding="utf-8") as _f:
		BASE = {d["_id"]: d for d in json.load(_f)["docs"]}
	DOCS = {d["_id"]: d for d in G.generer(BASE, lambda docs: RANGS)}


def _get(i):
	return DOCS.get(i) or BASE.get(i)


def _ok(perso, conditions):
	return acces.clauses_remplies(perso, conditions, _get)


def _perso(actives=(), reussies=(), victoires=(), enigmes=(), inventaire=()):
	return {"quetes_actives": [{"id": q, "objectif": o} for q, o in actives],
			"quetes_terminees": [{"id": q, "echec": False} for q in reussies],
			"battle_maps_gagnees": list(victoires),
			"enigmes": {e: {"resolue": True} for e in enigmes},
			"inventaire": [{"item": i, "poids": 1} for i in inventaire]}


def _visibles(pnj_id, noeud="accueil", actives=(), reussies=(), flags=None, enigmes=(), raison=None):
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {},
				"enigmes_resolues": set(enigmes), "passages": {}, "intro_raison": raison}
	contexte.update(flags or {})
	return {c["id"] for c in pnj._choix_visibles(DOCS[pnj_id], noeud, contexte)}


def _salle(cle):
	return G.GARDIENS[cle][0]


# ── Contrôles du générateur ─────────────────────────────────────────────────────

def test_le_generateur_ne_produit_aucune_faute():
	docs = list(DOCS.values())
	assert G.V.controler(docs, BASE) == []
	assert G.controler_portes(docs, BASE) == []


def test_aucun_dialogue_ne_porte_d_erreur_ni_d_avertissement():
	for d in DOCS.values():
		assert not lint_dialogues.analyser_doc(d), d["_id"]


def test_toute_quete_nommee_existe():
	"""Un id de quête mal recopié masquerait un choix en silence (fail-closed)."""
	neufs = [d for i, d in DOCS.items() if i not in BASE or i == G.AELIS_MU]
	nommees = set(re.findall(r'"(quete:[a-z0-9_]+)"', json.dumps(neufs, ensure_ascii=False)))
	assert nommees <= set(G.QUETES) | {G.Q_PAROLE} | {q for q in nommees if q in json.dumps(BASE[G.AELIS_MU])}
	offres = {serv["offre"]["id"] for d in DOCS.values() for serv in (d.get("services") or {}).values()
			  if isinstance(serv, dict) and isinstance(serv.get("offre"), dict)}
	assert set(G.QUETES) <= offres


def test_toutes_les_clauses_d_acces_et_de_presence_sont_du_vocabulaire_des_barrieres():
	for d in DOCS.values():
		blocs = []
		if d.get("type") == "enigme":
			blocs.append(d.get("conditions") or [])
		if d.get("acces"):
			blocs.append(d["acces"].get("conditions") or [])
		blocs += [e.get("conditions") or [] for e in d.get("pnj") or [] if isinstance(e, dict)]
		for b in blocs:
			assert acces.conditions_invalides({"acces": {"conditions": b}}) == [], d["_id"]


def test_regeneration_idempotente():
	"""Rejouée sur un dump où l'import est fait, la sortie ne change rien (les espèces déjà en base ne sont
	plus réémises par le moteur du bestiaire)."""
	relu = dict(BASE, **{i: dict(d, _rev="1-x") for i, d in DOCS.items()})
	regen = {d["_id"]: d for d in G.generer(relu, lambda docs: RANGS)}
	assert all(DOCS[i] == d for i, d in regen.items() if i in DOCS)
	assert set(DOCS) - set(regen) <= {i for i in DOCS if i.startswith(("espece:", "item:", "competence:"))}


# ── Le chemin : Mu, Notre-Dame, Nidaros, la forteresse ─────────────────────────

def test_aelis_de_mu_donne_rendez_vous_a_l_hekla_une_fois_le_sceau_compris():
	assert "hekla" not in _visibles(G.AELIS_MU)
	assert "hekla" in _visibles(G.AELIS_MU, enigmes=[G.E_SCELLEMENT])


def test_notre_dame_tire_reykjavik_nidaros_et_bruges():
	connexions = [d for d in {**BASE, **DOCS}.values() if d.get("type") == "connection"]
	lieux = {a["lieu"] for a in portails.arrivees_candidates(connexions, "lieu:notre_dame_portail")}
	assert {G.HALLGRIM, G.NIDAROS, G.BRUGES} <= lieux


def test_nidaros_n_est_pas_un_cul_de_sac():
	"""Deux arches à Nidaros : Reykjavik et Bruges — on rentre par Bruges, puis la route."""
	liens = [d for d in DOCS.values() if d.get("type") == "connection" and d["metadata"]["type"] == "portail"]
	bouts = {frozenset(n["lieu"] for n in d["nodes"]) for d in liens}
	assert frozenset({G.HALLGRIM, G.NIDAROS}) in bouts and frozenset({G.BRUGES, G.NIDAROS}) in bouts


def test_la_forteresse_s_ouvre_a_la_copie_ou_a_l_epreuve():
	cond = DOCS[G.FORTERESSE]["acces"]["conditions"]
	assert not _ok(_perso(), cond)
	assert _ok(_perso(inventaire=[G.COPIE]), cond)
	assert _ok(_perso(reussies=[G.Q_RUSE]), cond)


# ── L'épreuve : deux voies, une seule suffit ───────────────────────────────────

def test_les_deux_epreuves_s_excluent():
	offert = {"apport_offert": True}
	assert "offre" in _visibles(G.GIZURR, flags=offert)
	assert "offre" in _visibles(G.SAEMUNDR, flags=offert)
	assert "offre" not in _visibles(G.GIZURR, actives=[G.Q_RUSE], flags=offert)
	assert "offre" not in _visibles(G.SAEMUNDR, reussies=[G.Q_CHASSE], flags=offert)


def test_le_seuil_s_ouvre_apres_l_une_ou_l_autre_epreuve():
	cond = DOCS[G.SEUIL]["acces"]["conditions"]
	assert not _ok(_perso(), cond)
	assert _ok(_perso(reussies=[G.Q_CHASSE]), cond)
	assert _ok(_perso(reussies=[G.Q_RUSE]), cond)


def test_la_cavite_exige_la_chasse_en_cours_et_les_traces_lues():
	cond = DOCS[G.CAVITE]["acces"]["conditions"]
	chasse = [(G.Q_CHASSE, {"type": "collect", "cible": G.DEPOUILLE, "quantite": 1})]
	assert not _ok(_perso(actives=chasse), cond)
	assert _ok(_perso(actives=chasse, enigmes=[G.E_TRACES]), cond)
	assert not _ok(_perso(reussies=[G.Q_CHASSE], enigmes=[G.E_TRACES]), cond)


def test_le_malebranche_de_la_cavite_fuit_a_trente_pour_cent():
	spec = combat_arrivee.spec(DOCS[G.CAVITE])
	assert spec and spec["espece"] == "espece:malebranche"
	assert "ia_fuyard_30" in DOCS["espece:malebranche"]["tags"]
	assert DOCS[G.DEPOUILLE]["source_espece"] == "espece:malebranche"


def test_le_demon_ne_remet_son_aveu_qu_une_fois_demasque():
	pendant = [G.Q_RUSE]
	assert "examiner" in _visibles(G.DEMON, actives=pendant, flags={"don_recu": False})
	assert "aveu" not in _visibles(G.DEMON, actives=pendant, flags={"don_recu": False})
	assert "aveu" in _visibles(G.DEMON, actives=pendant, enigmes=[G.E_DEMON], flags={"don_recu": False})
	assert DOCS[G.E_DEMON]["solution"]["conclusion"] == "ment"


@pytest.mark.parametrize("pid,q", [("GIZURR", "Q_CHASSE"), ("SAEMUNDR", "Q_RUSE"), ("AELIS_HEKLA", "Q_DESCENTE")])
def test_donneurs_trois_etats(pid, q):
	pid, q = getattr(G, pid), getattr(G, q)
	assert "offre" in _visibles(pid, flags={"apport_offert": True})
	en_cours = _visibles(pid, actives=[q], flags={"apport_en_cours": True, "apport_possible": False})
	assert "offre" not in en_cours and "rappel" in en_cours
	assert "remettre" in _visibles(pid, actives=[q], flags={"apport_en_cours": True, "apport_possible": True})
	assert "offre" not in _visibles(pid, reussies=[q], flags={"apport_offert": False})


# ── L'Enfer : la chaîne des gardiens ───────────────────────────────────────────

CHAINE = [  # (espace ou seuil gardé, gardien dont la victoire l'ouvre)
	(G.CORNICHES, "charon"), (G.FANGE, "minos"), (G.PORTE_FESTIN, "ciacco"), (G.PASSERELLES, "plutus"),
	(G.PORTES_DITE, "phlegyas"), (G.PORTE_TOMBEAUX, "furies"), (G.POIX, "geryon"), (G.PUITS_GEANTS, "malacoda"),
	(G.COCYTE, "antee"),
]


@pytest.mark.parametrize("lieu_id,cle", CHAINE)
def test_chaque_passage_s_ouvre_pour_toujours_apres_son_gardien(lieu_id, cle):
	cond = DOCS[lieu_id]["acces"]["conditions"]
	assert not _ok(_perso(), cond)
	assert _ok(_perso(victoires=[_salle(cle)]), cond)


@pytest.mark.parametrize("cle", list(G.GARDIENS))
def test_un_gardien_vaincu_ne_revient_pas(cle):
	salle = DOCS[_salle(cle)]
	assert salle["categorie"] == "battle_map"
	assert not _ok(_perso(victoires=[salle["_id"]]), salle["acces"]["conditions"])
	entree = next(e for e in DOCS[G.GARDIENS[cle][1]]["pnj"] if e["character"] == G.GARDIENS[cle][2])
	if cle != "charon":  # Charon reste, et rame
		assert not _ok(_perso(victoires=[salle["_id"]]), entree["conditions"])
	assert entree["cases"]


@pytest.mark.parametrize("cle", list(G.GARDIENS))
def test_chaque_gardien_ouvre_sa_salle(cle):
	sid, eid, pid, compo, *_ = G.GARDIENS[cle]
	assert DOCS[pid]["services"]["acces"]["lieu"] == sid
	donjon = DOCS["donjon:" + sid.split(":", 1)[1]]
	assert donjon["portail"] == eid and donjon["battle_maps"][0]["composition"] == compo


def test_les_furies_sont_trois_especes_au_role_tenu_par_leur_kit():
	compo = G.GARDIENS["furies"][3]
	assert set(compo) == {"espece:furie_alecto", "espece:furie_megere", "espece:furie_tisiphone"}
	alecto, megere, tisiphone = (DOCS[e] for e in sorted(compo))
	assert "distance" in alecto["tags"] and "competence:monstre_crachat_de_feu" in alecto["competences"]
	assert "magie_demonologie_5" in megere["tags"]
	assert not {"distance", "magique"} & set(tisiphone["tags"]) and "competence:monstre_etreinte" in tisiphone["competences"]


def test_les_geoliers_secondaires_reprennent_leur_poste():
	for eid, (_img, _g, combat) in G.ESPACES.items():
		if combat:
			spec = combat_arrivee.spec(DOCS[eid])
			assert spec and spec["reapparition_min"] > 0 and DOCS[eid]["combat_arrivee"]["profil_weights"], eid


# ── Le registre des entrées, Lucifer, la sortie ────────────────────────────────

@pytest.mark.parametrize("pid,choix_id,raison", [
	("pnj:minos", "sentence", "exil"), ("pnj:minos", "aucune", None), ("pnj:ciacco", "famine", "famine"),
	("pnj:geryon", "pillage", "pillage"), (G.LUCIFER, "secret", "secret")])
def test_chaque_raison_du_depart_a_son_cercle(pid, choix_id, raison):
	assert choix_id in _visibles(pid, raison=raison)
	autre = "famine" if raison != "famine" else "exil"
	assert choix_id not in _visibles(pid, raison=autre)


def test_lucifer_remet_le_givre_pendant_la_descente_seulement():
	assert "givre" in _visibles(G.LUCIFER, actives=[G.Q_DESCENTE], flags={"don_recu": False})
	assert "givre" not in _visibles(G.LUCIFER, flags={"don_recu": False})
	assert DOCS[G.LUCIFER]["services"]["don"]["item"] == G.GIVRE == DOCS[G.AELIS_HEKLA]["services"]["apport"]["offre"]["item"]
	assert DOCS[G.AELIS_HEKLA]["services"]["apport"]["offre"]["recompenses"]["xp"] == 800  # 600 + 200, plan § 12


def test_l_issue_du_cocyte_est_a_sens_unique():
	issue = DOCS["link:coeur_du_cocyte_to_seuil_de_l_hekla_issue"]
	seuil = next(n for n in issue["nodes"] if n["lieu"] == G.SEUIL)
	assert seuil.get("bouton") is False


def test_aelis_compare_selon_la_voie_suivie_a_mu():
	assert "comparer_parole" in _visibles(G.AELIS_HEKLA, "remis", reussies=[G.Q_PAROLE])
	assert "comparer_combat" in _visibles(G.AELIS_HEKLA, "remis")
	assert "comparer_parole" not in _visibles(G.AELIS_HEKLA, "remis")


# ── Images et grilles ──────────────────────────────────────────────────────────

RESSOURCES = os.path.join(RACINE, "templates", "resources")


def test_toutes_les_images_sont_presentes():
	for d in DOCS.values():
		if d.get("type") == "lieu" and d["_id"] not in BASE:
			dossier = "battle_maps" if d.get("cells") else "towns"
			assert os.path.exists(os.path.join(RESSOURCES, dossier, d["image"])), d["_id"]
		if d.get("type") == "pnj" and d["_id"] not in BASE:
			assert os.path.exists(os.path.join(RESSOURCES, "pnj", d["portrait"])), d["_id"]
		if d.get("type") == "espece":
			assert os.path.exists(os.path.join(RESSOURCES, "monsters", d["image"])), d["_id"]


@pytest.mark.parametrize("eid", list(G.ESPACES))
def test_la_grille_d_un_espace_est_d_un_seul_tenant(eid):
	cells = DOCS[eid]["cells"]
	assert len(cells) == G.H_CARTE and all(len(r) == G.L_CARTE for r in cells)
	sol = {(x, y) for y, r in enumerate(cells) for x, v in enumerate(r) if v}
	vus, pile = {min(sol)}, [min(sol)]
	while pile:
		x, y = pile.pop()
		for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
			if q in sol and q not in vus:
				vus.add(q)
				pile.append(q)
	assert vus == sol
