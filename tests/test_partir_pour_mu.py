# tests/test_partir_pour_mu.py
# « Partir pour Mu » (dev/gen_partir_pour_mu.py) : les trois états de chaque PNJ touché, la
# barrière du seuil de Mu, la porte de l'ancrage (jamais tirée au sort, servie par Aénor), le
# retour par le Templier de Mu et le cristal en vente à Mu. Docs rebâtis par le générateur sur le
# dump le PLUS RÉCENT (glob, CLAUDE.md §20) — jamais sur le fichier à importer.

import glob
import importlib.util
import json
import os

import pytest

from utils import acces, lint_dialogues, pnj, portails

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_partir_pour_mu.py")
	spec = importlib.util.spec_from_file_location("gen_partir_pour_mu", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


G = _gen()
_DUMPS = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
pytestmark = pytest.mark.skipif(not _DUMPS, reason="aucun dump jsons/telluris-dump-*.json")

if _DUMPS:
	with open(_DUMPS[-1], encoding="utf-8") as _f:
		BASE = {d["_id"]: d for d in json.load(_f)["docs"]}
	DOCS = {d["_id"]: d for d in G.generer(BASE)}

RANG_A = {G.LUTECIA: "A"}
RANG_B = {G.LUTECIA: "B"}


def _visibles(pnj_id, noeud="accueil", actives=(), reussies=(), flags=None, retenues=(), rangs=None,
			  passages=None):
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {},
				"offres_retenues": set(retenues), "rangs_guilde": rangs or {}, "passages": passages or {}}
	contexte.update(flags or {})
	return {c["id"] for c in pnj._choix_visibles(DOCS[pnj_id], noeud, contexte)}


def _perso(escorte=False, reussies=()):
	actives = [{"id": G.QUETE, "objectif": {"type": "escorte", "cible": G.SEUIL}}] if escorte else []
	return {"quetes_actives": actives, "quetes_terminees": [{"id": q, "echec": False} for q in reussies]}


def _get(i):
	return DOCS.get(i) or BASE.get(i)


# ── Contrôles du générateur ─────────────────────────────────────────────────────

def test_le_generateur_ne_produit_aucune_faute():
	assert G.V.controler(list(DOCS.values()), BASE) == []


def test_toute_quete_nommee_est_l_offre_ou_les_vestiges():
	"""Un id de quête mal recopié masquerait un choix en silence (fail-closed)."""
	ajouts = [d for i, d in DOCS.items() if i not in BASE]
	for i in (G.AELIS_ARCHIVES, G.MAELYS, G.AENOR, G.ARCHIVES):
		d = DOCS[i]
		ajouts += [c for c in d.get("dialogue", {}).get("noeuds", {}).get("accueil", {}).get("choix", [])
				   if c["id"].startswith("mu_")]
	texte = json.dumps(ajouts, ensure_ascii=False)
	nommees = {m for m in __import__("re").findall(r'"(quete:[a-z0-9_]+)"', texte)}
	offres = {o["offre"]["id"] for o in DOCS[G.AELIS_ARCHIVES]["services"]["escorte"]["offres"]}
	assert nommees <= offres
	assert {G.QUETE, G.VESTIGES} <= offres


def test_l_offre_d_aelis_s_ajoute_aux_precedentes_sans_les_toucher():
	avant = [o for o in BASE[G.AELIS_ARCHIVES]["services"]["escorte"]["offres"] if o["offre"]["id"] != G.QUETE]
	apres = DOCS[G.AELIS_ARCHIVES]["services"]["escorte"]["offres"]
	assert apres[:-1] == avant and apres[-1]["offre"]["id"] == G.QUETE
	assert apres[-1]["offre"]["destination"] == G.SEUIL and apres[-1]["offre"]["rang_min"] == G.RANG_A


def test_regeneration_idempotente():
	relu = dict(BASE, **{i: dict(d, _rev="1-x") for i, d in DOCS.items()})
	assert G.generer(relu) == list(DOCS.values())


# ── Aélis aux Archives ──────────────────────────────────────────────────────────

def test_aelis_ne_propose_mu_qu_apres_les_vestiges_et_au_rang_a():
	offerte = {"escorte_offerte": True}
	assert "mu_offre" in _visibles(G.AELIS_ARCHIVES, reussies=[G.VESTIGES], flags=offerte,
								   retenues=[G.QUETE], rangs=RANG_A)
	assert "mu_offre" not in _visibles(G.AELIS_ARCHIVES, reussies=[G.VESTIGES], flags=offerte,
									   retenues=[G.QUETE], rangs=RANG_B)
	assert "mu_offre" not in _visibles(G.AELIS_ARCHIVES, flags=offerte, retenues=[G.QUETE], rangs=RANG_A)


def test_aelis_quitte_les_archives_pendant_et_apres():
	entree = next(e for e in DOCS[G.ARCHIVES]["pnj"] if e["character"] == G.AELIS_ARCHIVES)
	jumieges = "quete:escorte_aelis_abbaye_de_jumieges"
	avant = _perso(reussies=[jumieges, G.VESTIGES])
	pendant = _perso(escorte=True, reussies=[jumieges, G.VESTIGES])
	apres = _perso(reussies=[jumieges, G.VESTIGES, G.QUETE])
	ok = lambda c: acces.clauses_remplies(c, entree["conditions"], _get)
	assert ok(avant) and not ok(pendant) and not ok(apres)


# ── Maëlys : elle renvoie aux Archives ─────────────────────────────────────────

def test_maelys_trois_etats():
	avant = _visibles(G.MAELYS, reussies=[G.VESTIGES], rangs=RANG_A)
	pendant = _visibles(G.MAELYS, actives=[G.QUETE], reussies=[G.VESTIGES], rangs=RANG_A)
	apres = _visibles(G.MAELYS, reussies=[G.VESTIGES, G.QUETE], rangs=RANG_A, passages={G.SEUIL: 1})
	assert "mu_offre" in avant and not {"mu_relance", "mu_souvenir"} & avant
	assert "mu_relance" in pendant and not {"mu_offre", "mu_souvenir"} & pendant
	assert "mu_souvenir" in apres and not {"mu_offre", "mu_relance"} & apres
	assert "mu_offre" not in _visibles(G.MAELYS, reussies=[G.VESTIGES], rangs=RANG_B)


def test_maelys_ne_tient_pas_l_offre():
	offres = (DOCS[G.MAELYS]["services"].get("escorte") or {}).get("offres") or []
	assert G.QUETE not in {o["offre"]["id"] for o in offres}


# ── Aénor et la porte de l'ancrage ─────────────────────────────────────────────

def test_aenor_trois_etats():
	avant = _visibles(G.AENOR, reussies=[G.VESTIGES], rangs=RANG_A)
	pendant = _visibles(G.AENOR, actives=[G.QUETE], rangs=RANG_A)
	apres = _visibles(G.AENOR, reussies=[G.QUETE], rangs=RANG_A)
	assert not {"mu_pendant", "mu_apres"} & avant
	assert "mu_pendant" in pendant and "mu_apres" not in pendant
	assert "mu_apres" in apres and "mu_pendant" not in apres


def _liens():
	return [d for d in list(BASE.values()) + list(DOCS.values())
			if d.get("type") == "connection" and (d.get("metadata") or {}).get("type") == portails.TYPE_PORTAIL]


def test_la_porte_de_mu_n_est_jamais_au_tableau_tire():
	assert all(a["lieu"] != G.SEUIL for a in portails.arrivees_candidates(_liens(), G.ANCRAGE))
	portes = portails.arrivees_fixes(_liens(), G.ANCRAGE)
	assert [a["lieu"] for a in portes] == [G.SEUIL]


def test_la_porte_n_a_de_bouton_d_aucun_cote():
	porte = DOCS["link:seuil_de_mu_to_notre_dame_portail"]
	assert all(n["bouton"] is False for n in porte["nodes"])


def test_le_seuil_ne_s_ouvre_qu_a_l_escorte_puis_a_qui_l_a_menee():
	seuil = DOCS[G.SEUIL]
	assert not acces.acces_autorise(_perso(), seuil, _get)[0]
	assert acces.acces_autorise(_perso(escorte=True), seuil, _get)[0]
	assert acces.acces_autorise(_perso(reussies=[G.QUETE]), seuil, _get)[0]
	assert acces.conditions_invalides(seuil["acces"]) == []


# ── Mu : retour et cristal ──────────────────────────────────────────────────────

def test_le_templier_de_mu_ramene_a_notre_dame_contre_un_cristal():
	conf = DOCS[G.TEMPLIER_MU]["services"]["portail"]
	assert conf["fixe"] and conf["ancrage"] == G.SEUIL and conf["cout"]["item"] == G.CRISTAL
	assert [a["lieu"] for a in portails.arrivees_fixes(_liens(), G.SEUIL)] == [G.ANCRAGE]


def test_mu_vend_le_cristal_du_retour():
	"""Mu est sous la mer : sans cristal à vendre, qui arrive sans réserve n'en sortirait plus."""
	articles = DOCS[G.MARCHANDE]["services"]["vente"]["articles"]
	assert any(a["item"] == G.CRISTAL and a["cout_cuivre"] == G.PRIX_CRISTAL for a in articles)
	assert all(a["item"] in BASE for a in articles)


def test_les_portes_de_mu_sont_sur_des_cases_praticables():
	cells = BASE[G.MU]["cells"]
	for lid in ("link:seuil_de_mu_to_mu", "link:fare_des_marees_to_mu", "link:marche_du_dome_to_mu"):
		x, y = next(n["pos"] for n in DOCS[lid]["nodes"] if n["lieu"] == G.MU)
		assert cells[y][x] == 1, lid


def test_aelis_attend_a_l_auberge_apres_la_quete():
	entree = next(e for e in DOCS[G.AUBERGE]["pnj"] if e["character"] == G.AELIS_MU)
	assert entree["conditions"] == [G.APRES]
	assert DOCS[G.AELIS_VOIX]["voix_protege"] == {"quete": G.QUETE, "prenom": "Aélis"}


def test_aucun_dialogue_neuf_ne_porte_de_faute_de_linter():
	for d in DOCS.values():
		fautes = [t for t in lint_dialogues.analyser_doc(d) if t.get("niveau") == "erreur"]
		assert not fautes, (d["_id"], fautes)
