# tests/test_vestiges_premier_passage.py
# « Les vestiges du premier passage » (dev/gen_vestiges_premier_passage.py) : les trois états de
# chaque PNJ touché, les barrières des lieux neufs, les énigmes. Docs rebâtis par le générateur
# sur le dump le PLUS RÉCENT (glob, CLAUDE.md §20) — jamais sur le fichier à importer.

import glob
import importlib.util
import json
import os

import pytest

from utils import acces, enigmes, lint_dialogues, pnj

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_vestiges_premier_passage.py")
	spec = importlib.util.spec_from_file_location("gen_vestiges_premier_passage", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


G = _gen()
_DUMPS = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
pytestmark = pytest.mark.skipif(not _DUMPS, reason="aucun dump jsons/telluris-dump-*.json")


def _docs():
	with open(_DUMPS[-1], encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f)["docs"]}
	relus = [G.aelis_archives(base[G.AELIS_ARCHIVES]), G.commandeur(base[G.COMMANDEUR]),
			 G.lieu_archives(base[G.ARCHIVES])]
	neufs = G.lieux_neufs() + G.pnj_neufs() + G.enigmes() + [G.donjon()]
	return base, {d["_id"]: d for d in relus + neufs}


if _DUMPS:
	BASE, DOCS = _docs()

RANG_B = {G.LUTECIA: "B"}
RANG_C = {G.LUTECIA: "C"}


def _visibles(pnj_id, noeud="accueil", actives=(), reussies=(), flags=None, retenues=(), rangs=None):
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {},
				"offres_retenues": set(retenues), "rangs_guilde": rangs or {}}
	contexte.update(flags or {})
	return {c["id"] for c in pnj._choix_visibles(DOCS[pnj_id], noeud, contexte)}


def _perso(escorte_active=False, reussies=()):
	actives = [{"id": G.QUETE, "objectif": {"type": "escorte", "cible": G.RETOUR}}] if escorte_active else []
	return {"quetes_actives": actives, "quetes_terminees": [{"id": q, "echec": False} for q in reussies],
			"enigmes": {}}


# ── Aélis aux Archives ──────────────────────────────────────────────────────────

def test_aelis_ne_propose_les_vestiges_qu_apres_la_piece_et_au_rang_b():
	offerte = {"escorte_offerte": True}
	# Pièce réussie, rang B, offre retenue : la proposition.
	assert "vestiges_offre" in _visibles(G.AELIS_ARCHIVES, reussies=[G.PIECE], flags=offerte,
										  retenues=[G.QUETE], rangs=RANG_B)
	# Rang C seulement : rien.
	assert "vestiges_offre" not in _visibles(G.AELIS_ARCHIVES, reussies=[G.PIECE], flags=offerte,
											  retenues=[G.QUETE], rangs=RANG_C)
	# Pièce pas faite : rien.
	assert "vestiges_offre" not in _visibles(G.AELIS_ARCHIVES, flags=offerte, retenues=[G.QUETE], rangs=RANG_B)


def test_aelis_trois_etats():
	avant = _visibles(G.AELIS_ARCHIVES, reussies=[G.PIECE], rangs=RANG_B)
	pendant = _visibles(G.AELIS_ARCHIVES, actives=[G.QUETE], reussies=[G.PIECE], rangs=RANG_B)
	apres = _visibles(G.AELIS_ARCHIVES, reussies=[G.PIECE, G.QUETE], rangs=RANG_B)
	assert not {"vestiges_offre", "vestiges_apres"} & (avant | pendant)
	assert "vestiges_apres" in apres and "vestiges_offre" not in apres


def test_l_offre_de_la_piece_ne_s_affiche_plus_pour_celle_des_vestiges():
	# `escorte_offerte` vaut pour les deux offres : la pièce exige désormais d'être l'offre retenue.
	jumieges = ["quete:escorte_aelis_abbaye_de_jumieges"]
	offerte = {"escorte_offerte": True}
	assert "piece_offre" in _visibles(G.AELIS_ARCHIVES, reussies=jumieges, flags=offerte, retenues=[G.PIECE])
	assert "piece_offre" not in _visibles(G.AELIS_ARCHIVES, reussies=jumieges, flags=offerte,
										  retenues=[G.QUETE], rangs=RANG_B)


def test_l_escorte_d_aelis_porte_les_deux_offres():
	offres = DOCS[G.AELIS_ARCHIVES]["services"]["escorte"]["offres"]
	# La pièce puis les vestiges, une fois chacune ; une offre ajoutée depuis (Mu) vient après.
	ids = [o["offre"]["id"] for o in offres]
	assert ids[:2] == [G.PIECE, G.QUETE] and ids.count(G.QUETE) == 1
	assert "offre" not in DOCS[G.AELIS_ARCHIVES]["services"]["escorte"]


# ── Le commandeur de l'Enclos ───────────────────────────────────────────────────

def test_commandeur_trois_etats():
	vestiges = {"vestiges_connu", "vestiges_inconnu", "vestiges_apres"}
	assert not vestiges & _visibles(G.COMMANDEUR)
	assert vestiges & _visibles(G.COMMANDEUR, actives=[G.QUETE]) == {"vestiges_inconnu"}
	assert vestiges & _visibles(G.COMMANDEUR, actives=[G.QUETE], reussies=[G.CRISTAL]) == {"vestiges_connu"}
	assert vestiges & _visibles(G.COMMANDEUR, reussies=[G.QUETE]) == {"vestiges_apres"}


def test_le_commandeur_garde_la_galerie():
	assert DOCS[G.COMMANDEUR]["services"]["acces"]["lieu"] == G.GALERIE
	assert DOCS[G.GALERIE]["acces"]["gardien"] == G.COMMANDEUR


# ── Lieux, présences, barrières ─────────────────────────────────────────────────

@pytest.mark.parametrize("lieu", ["GALERIE", "ANTICHAMBRE", "SALLE", "RETOUR"])
def test_les_barrieres_sont_lisibles(lieu):
	assert acces.conditions_invalides(DOCS[getattr(G, lieu)]) == []


def test_aelis_quitte_les_archives_pendant_l_escorte():
	entree = next(e for e in DOCS[G.ARCHIVES]["pnj"] if e["character"] == G.AELIS_ARCHIVES)
	cond = entree.get("conditions")
	jumieges = "quete:escorte_aelis_abbaye_de_jumieges"
	assert acces.clauses_remplies(_perso(reussies=[jumieges]), cond, lambda _i: None)
	assert not acces.clauses_remplies(_perso(escorte_active=True, reussies=[jumieges]), cond, lambda _i: None)


def test_la_porte_est_refermee_hors_de_l_escorte():
	# Anneaux réglés pour toujours, mais l'escorte rendue : l'antichambre ne se rouvre pas.
	perso = _perso(reussies=[G.QUETE])
	perso["enigmes"] = {G.E_ANNEAUX: {"resolue": True}}
	ok, _raison = acces.conditions_remplies(perso, DOCS[G.ANTICHAMBRE], lambda _i: None)
	assert not ok
	perso.update(_perso(escorte_active=True))
	perso["enigmes"] = {G.E_ANNEAUX: {"resolue": True}}
	ok, _raison = acces.conditions_remplies(perso, DOCS[G.ANTICHAMBRE], lambda _i: None)
	assert ok


def test_aelis_est_dans_la_salle_du_combat():
	assert not DOCS[G.SALLE].get("proteges_restent_dehors")
	assert DOCS[G.DONJON]["battle_maps"][0]["composition"] == {G.PENANGGALAN: 3}


def test_grille_de_la_salle_lue_sur_l_image():
	# Relevé sur battle_maps/salle_de_l_arche_eteinte.jpg (1232×864 → 20 × 14 cases de 61,6 px).
	salle = DOCS[G.SALLE]
	cells = salle["cells"]
	assert (salle["dimensions"]["x"], salle["dimensions"]["y"]) == (20, 14)
	assert len(cells) == 14 and all(len(r) == 20 for r in cells)
	assert all(cells[2][x] == 0 for x in range(7, 13))      # massif de l'arche
	assert all(cells[3][x] == 0 for x in range(7, 13))
	assert cells[11][8] == cells[11][11] == 0                # piliers du chambranle
	assert cells[13][9] == cells[13][10] == 1                # couloir de la porte
	assert cells[2][2] == cells[11][17] == 1                 # angles du dallage
	assert all(cells[y][1] == 0 and cells[y][18] == 0 for y in range(14))


def test_les_quetes_citees_existent():
	offres = {o["offre"]["id"] for o in DOCS[G.AELIS_ARCHIVES]["services"]["escorte"]["offres"]}
	assert {G.PIECE, G.QUETE} <= offres
	assert DOCS[G.COMMANDEUR]["services"]["apport"]["offre"]["id"] == G.CRISTAL


# ── La voix d'Aélis escortée : où aller, étape par étape ────────────────────────

def _etape(passages=None, resolues=()):
	contexte = {"quetes_actives": {G.QUETE}, "quetes_reussies": set(), "flags": {},
				"passages": passages or {}, "enigmes_resolues": set(resolues)}
	vus = {c["id"] for c in pnj._choix_visibles(DOCS[G.AELIS_ESCORTE], "accueil", contexte)}
	return vus - {"fin"}


def test_la_voix_d_aelis_est_celle_de_l_escortee_des_vestiges():
	v = DOCS[G.AELIS_ESCORTE]["voix_protege"]
	offre = next(o["offre"] for o in DOCS[G.AELIS_ARCHIVES]["services"]["escorte"]["offres"]
				 if o["offre"]["id"] == G.QUETE)
	assert v["quete"] == G.QUETE
	assert v["prenom"] == offre["proteges"][0]["prenom"]
	assert set(v["sauf_lieux"]) == {G.GALERIE, G.ANTICHAMBRE}


def test_aelis_indique_une_seule_etape_a_la_fois():
	g, a, r = G.GALERIE, G.ANTICHAMBRE, G.RETOUR
	assert _etape() == {"enclos"}                                       # jamais descendu
	assert _etape({g: 1}) == {"galerie"}
	assert _etape({g: 1}, [G.E_GRAVURES]) == {"anneaux"}
	assert _etape({g: 1}, [G.E_GRAVURES, G.E_ANNEAUX]) == {"anneaux"}   # pas encore entré
	assert _etape({g: 1, a: 1}, [G.E_GRAVURES, G.E_ANNEAUX]) == {"arche"}
	assert _etape({g: 1, a: 1}, [G.E_GRAVURES, G.E_ANNEAUX, G.E_ARCHE]) == {"serrure"}
	assert _etape({g: 1, a: 1, r: 1}, [G.E_GRAVURES, G.E_ANNEAUX, G.E_ARCHE, G.E_RETOUR]) == set()


def test_aelis_dit_le_point_de_contact_a_l_acceptation():
	texte = DOCS[G.AELIS_ARCHIVES]["dialogue"]["noeuds"]["vestiges_accepte"]["texte"]
	assert "Enclos du Temple" in texte and "commandeur" in texte and "catacombes" in texte


# ── Énigmes et dialogues ────────────────────────────────────────────────────────

def test_les_enigmes_sont_solubles_et_chainees_sans_cycle():
	es = G.enigmes()
	for d in es:
		assert enigmes.valider_enigme(d) == [], d["_id"]
	assert enigmes.cycles_prerequis(es) == []
	assert [d.get("prerequis") for d in es] == [None, [G.E_GRAVURES], [G.E_ANNEAUX], [G.E_ARCHE]]


def test_le_retour_demande_le_sceau_de_la_boite():
	retour = next(d for d in G.enigmes() if d["_id"] == G.E_RETOUR)
	assert retour["solution"]["placement"]["serrure"] == "trois_cercles"
	assert {"combat_gagne": {"lieu": G.SALLE}} in retour["conditions"]


def test_aucune_erreur_de_linter():
	for d in DOCS.values():
		fautes = [t for t in lint_dialogues.analyser_doc(d) if t.get("niveau") == "erreur"]
		assert fautes == [], d["_id"]
