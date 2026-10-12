"""dev/gen_villes_pays.py — chaque cité posée sur la carte de son pays, frontière Égypte ↔
Afrique du Nord (dev/gen_egypte_afrique_du_nord.py), Atlantis et Mu créées sans connexion ;
rejeu idempotent sur le dump."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_egypte_afrique_du_nord as gea  # noqa: E402
from dev import gen_grille_image as ggi  # noqa: E402
from dev import gen_villes_pays as gvp  # noqa: E402
from dev.gen_plaine_europeenne import zone_de  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402


def _taille(nom):
	return (800, 1306) if nom == "abou_simbel_capital.jpg" else (1408, 768)


def _proposer(doc, _options=frozenset()):
	dim = doc["dimensions"]
	return {"cells": [[1] * dim["x"] for _ in range(dim["y"])], "nav": {}, "rapport": {}}


@pytest.fixture(scope="module")
def dump():
	docs = ggi.charger_dump()
	ids = {d.get("_id") for d in docs}
	if not (set(gvp.CITES) - set(gvp.GRILLES_DESSINEES) | set(gvp.ANCRES_PAYS)) <= ids:
		pytest.skip("aucun dump committé avec ces cités et ces pays")
	return docs


@pytest.fixture(scope="module")
def construit(dump):
	return gvp.construire(dump, _taille, _proposer)


def test_aucun_refus(construit):
	assert construit[2] == []


def _liens_cites(liens):
	interieurs = set(gvp.INTERIEURS)
	return [l for l in liens if not l["_id"].startswith("link:afrique_du_nord_to_egypte_")
		and not interieurs & {n["lieu"] for n in l["nodes"]}]


def test_un_lien_par_sortie_chaque_bout_dans_sa_zone(dump, construit):
	par_id = {d["_id"]: d for d in dump}
	par_id.update({d["_id"]: d for d in construit[0]})
	liens = _liens_cites(construit[1])
	assert len(liens) == sum(len(c["sorties"]) for c in gvp.CITES.values())
	assert len({l["_id"] for l in liens}) == len(liens)
	for cite_id, spec in gvp.CITES.items():
		pays = par_id[spec["pays"]]
		zone_pays = zone_de(pays["cells"], pays.get("nav") or {}, gvp.ANCRES_PAYS[spec["pays"]])
		cite = par_id[cite_id]
		for nom, (_, ancre) in spec["sorties"].items():
			lien = next(l for l in liens if l["_id"] == f"link:{gvp.slug(spec['pays'])}_to_{gvp.slug(cite_id)}_{nom}")
			(n_pays, n_cite) = lien["nodes"]
			assert n_pays["lieu"] == spec["pays"] and tuple(n_pays["pos"]) in zone_pays
			assert n_cite["lieu"] == cite_id
			assert tuple(n_cite["pos"]) in zone_de(cite["cells"], cite.get("nav") or {}, ancre)
			assert n_cite["label"].startswith(f"{cite.get('label')} — par ")


def test_cases_du_pays_distinctes_par_cite(construit):
	for cite_id in gvp.CITES:
		poses = [tuple(l["nodes"][0]["pos"]) for l in construit[1] if l["nodes"][1]["lieu"] == cite_id]
		assert len(poses) == len(set(poses))


def test_atlantis_et_mu_creees_sans_connexion(dump, construit):
	"""Créées par ce lot, ou déjà en base (lot importé) : jamais reliées par lui."""
	lieux, liens = construit[0], construit[1]
	par_id = {d["_id"]: d for d in dump if d.get("_id") in ("lieu:atlantis", "lieu:mu")}
	par_id.update({d["_id"]: d for d in lieux if d["_id"] in ("lieu:atlantis", "lieu:mu")})
	assert set(par_id) == {"lieu:atlantis", "lieu:mu"}
	assert {d["image"] for d in par_id.values()} == {"atlantis_capital.jpg", "mu_capital.jpg"}
	assert all(d["categorie"] == "ville" and d["cells"] for d in par_id.values())
	assert not any(n["lieu"] in par_id for l in liens for n in l["nodes"])


def test_abou_simbel_grille_dessinee_posee_sur_l_afrique_du_nord(dump, construit):
	"""Créée avec la grille DESSINÉE (pas la proposition), parent = la carte qui la montre."""
	if any(d.get("_id") == "lieu:abou_simbel" for d in dump):
		pytest.skip("Abou Simbel déjà en base")
	doc = next(d for d in construit[0] if d["_id"] == "lieu:abou_simbel")
	cells, nav = gvp.GRILLES_DESSINEES["lieu:abou_simbel"](_proposer(doc)["cells"])
	assert doc["cells"] == cells and doc["nav"] == nav
	assert doc["lieu_parent"] == "lieu:afrique_du_nord" and doc["image"] == "abou_simbel_capital.jpg"
	assert sum(1 for d in construit[0] if d["_id"] == "lieu:abou_simbel") == 1


def test_parent_pose_s_il_manque_jamais_reecrit():
	assert gvp.rattachee({"_id": "lieu:x", "_rev": "1-a"}, "lieu:p") == {"_id": "lieu:x", "lieu_parent": "lieu:p"}
	assert gvp.rattachee({"_id": "lieu:x", "lieu_parent": "lieu:q"}, "lieu:p")["lieu_parent"] == "lieu:q"


def test_trace_d_un_pont_pas_orthogonaux():
	cases = gvp.trace((12, 26), (17, 25))
	assert cases[0] == (12, 26) and cases[-1] == (17, 25)
	assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(cases, cases[1:]))


def test_lyon_grille_refaite_ponts_ouverts(construit):
	"""Proposition demandée sans enceinte et nav vide, puis les ponts posés à 1 par-dessus."""
	vus = []

	def proposer(doc, options):
		vus.append(options)
		dim = doc["dimensions"]
		return {"cells": [[5] * dim["x"] for _ in range(dim["y"])], "nav": {"0,0": 1}, "rapport": {}}

	lyon = {"_id": "lieu:lyon", "_rev": "3-a", "dimensions": {"x": 88, "y": 48},
		"cells": [[1] * 88 for _ in range(48)], "nav": {"9,9": 4}}
	for x, y in gvp.cases_des_ponts(gvp.GRILLES_REFAITES["lieu:lyon"]["ponts"]):
		lyon["cells"][y][x] = 5
	doc, prop = gvp.grille_refaite(lyon, proposer)
	assert prop and vus == [gvp.GRILLES_REFAITES["lieu:lyon"]["options"]]
	assert {"--nav-vide", "--sans-enceinte"} <= vus[0]
	assert "_rev" not in doc and doc["nav"] == {"0,0": 1}
	ponts = set(gvp.cases_des_ponts(gvp.GRILLES_REFAITES["lieu:lyon"]["ponts"]))
	assert all(doc["cells"][y][x] == (1 if (x, y) in ponts else 5) for y in range(48) for x in range(88))


def test_lyon_refaite_une_seule_fois():
	"""Tous les ponts déjà à 1 en base : le doc relu est gardé (retouches de l'éditeur sauves)."""
	lyon = {"_id": "lieu:lyon", "_rev": "4-b", "cells": [[1] * 88 for _ in range(48)], "nav": {"1,1": 2}}

	def interdit(*_):
		raise AssertionError("ponts déjà ouverts : rien à reproposer")

	doc, prop = gvp.grille_refaite(lyon, interdit)
	assert prop is None and doc == {"_id": "lieu:lyon", "cells": lyon["cells"], "nav": {"1,1": 2}}


def test_rejeu_sur_dump_a_jour_n_emet_rien(dump, construit):
	lieux, liens = construit[0], construit[1]
	emis, refus = a_emettre(dump, lieux + liens)
	assert refus == []
	par_id = {d["_id"]: d for d in dump}
	par_id.update({d["_id"]: d for d in emis})
	rejeu = list(par_id.values())

	def interdit(*_):
		raise AssertionError("Abou Simbel, Atlantis, Mu et Lyon refaite sont en base : aucune grille à proposer")

	l2, d2, r2, _, _ = gvp.construire(rejeu, _taille, interdit)
	assert r2 == [] and a_emettre(rejeu, l2 + d2) == ([], [])


def test_pays_absent_refuse(dump):
	sans = [d for d in dump if d.get("_id") != "lieu:egypte"]
	_, _, refus, _, _ = gvp.construire(sans, _taille, _proposer)
	assert refus == ["absent(s) du dump ou sans grille : lieu:egypte"]


# ── Égypte ↔ Afrique du Nord ──────────────────────────────────────────────────────────────
def test_frontiere_egypte_sans_avertissement_de_compte(construit):
	"""Chaque tronçon a EXACTEMENT un nom par poste de l'Afrique du Nord (une case sur deux)."""
	assert not [a for a in construit[4] if "nom(s) pour" in a]


def test_passages_une_case_sur_deux_cote_afrique_repartis_cote_egypte(construit):
	par_id = {d["_id"]: d for d in construit[0]}
	lignes = gea.lignes(par_id[gea.EGYPTE], par_id[gea.AFRIQUE])
	passages = [l for l in construit[1] if l["_id"].startswith("link:afrique_du_nord_to_egypte_")]
	assert len(passages) == sum(len(n) for n in gea.PASSAGES.values())
	assert [l["_id"] for l in passages] == [f"link:afrique_du_nord_to_egypte_{i:02d}"
		for i in range(1, len(passages) + 1)]
	debut = 0
	for troncon, (ligne_e, ligne_a) in lignes.items():
		noms = gea.PASSAGES[troncon]
		du_troncon = passages[debut:debut + len(noms)]
		debut += len(noms)
		assert [tuple(l["nodes"][0]["pos"]) for l in du_troncon] == ligne_a[0::2]
		# Côté Égypte : répartis d'un bout à l'autre du tronçon, une case chacun.
		cotes_e = [tuple(l["nodes"][1]["pos"]) for l in du_troncon]
		assert cotes_e == gea.postes(ligne_e, len(noms))
		assert cotes_e[0] == ligne_e[0] and cotes_e[-1] in ligne_e[-2:]
		assert len(set(cotes_e)) == len(cotes_e)
		for l, nom in zip(du_troncon, noms):
			assert [n["label"] for n in l["nodes"]] == [f"{nom} — Afrique du Nord", f"{nom} — Égypte"]


def test_territoire_du_voisin_mis_a_zero(construit):
	par_id = {d["_id"]: d for d in construit[0]}
	egy, afr = par_id[gea.EGYPTE], par_id[gea.AFRIQUE]
	for x, y in gea.bande(gea.FRONTIERE_EGYPTE, "ouest", egy["dimensions"]):
		assert egy["cells"][y][x] == 0
	for x, y in gea.bande(gea.FRONTIERE_AFRIQUE, "est", afr["dimensions"]):
		assert afr["cells"][y][x] == 0


def test_liens_des_cites_sur_l_afrique_du_nord_signales(dump, construit):
	"""Alexandrie et Le Caire ↔ Afrique du Nord tombent dans l'Égypte mise à 0 : signalés."""
	coupes = [d["_id"] for d in dump if d.get("type") == "connection"
		and any(n.get("lieu") == gea.AFRIQUE and tuple(n.get("pos") or ())
			in gea.bande(gea.FRONTIERE_AFRIQUE, "est", {"x": 88, "y": 48}) for n in d.get("nodes") or [])]
	if not coupes:
		pytest.skip("anciens liens déjà retirés de la base")
	assert all(any(a.startswith(c + " :") for a in construit[4]) for c in coupes)


def test_abou_simbel_reste_praticable_et_sa_route_y_mene(construit):
	"""Abou Simbel n'est pas sur la carte d'Égypte : elle reste dans la terre de l'Afrique du
	Nord, et le passage le plus proche d'elle est celui qui porte son nom."""
	afr = next(d for d in construit[0] if d["_id"] == gea.AFRIQUE)
	cible = gea.ABOU_SIMBEL_AFRIQUE
	assert cible in zone_de(afr["cells"], afr.get("nav") or {}, gea.ANCRE_AFRIQUE)
	passages = [l for l in construit[1] if l["_id"].startswith("link:afrique_du_nord_to_egypte_")]
	plus_proche = min(passages, key=lambda l: (l["nodes"][0]["pos"][0] - cible[0]) ** 2
		+ (l["nodes"][0]["pos"][1] - cible[1]) ** 2)
	assert plus_proche["nodes"][0]["label"] == "Route d'Abou Simbel — Afrique du Nord"


# ── Grand Temple d'Abou Simbel ────────────────────────────────────────────────────────────
def test_grand_temple_cree_et_relie_a_la_porte_du_temple(dump, construit):
	lieux, liens = construit[0], construit[1]
	spec = gvp.INTERIEURS["lieu:grand_temple_d_abou_simbel"]
	lien = next(l for l in liens if l["_id"] == "link:abou_simbel_to_grand_temple_d_abou_simbel")
	(n_ville, n_temple) = lien["nodes"]
	assert (n_ville["lieu"], tuple(n_ville["pos"])) == ("lieu:abou_simbel", spec["pos_parent"])
	assert (n_temple["lieu"], tuple(n_temple["pos"])) == ("lieu:grand_temple_d_abou_simbel", spec["pos"])
	assert lien["metadata"] == {"type": "temple", "status": "ouvert"}
	if any(d.get("_id") == "lieu:grand_temple_d_abou_simbel" for d in dump):
		pytest.skip("Grand Temple déjà en base")
	temple = next(d for d in lieux if d["_id"] == "lieu:grand_temple_d_abou_simbel")
	assert (temple["cells"], temple["nav"]) == spec["grille"]()
	assert temple["lieu_parent"] == "lieu:abou_simbel" and temple["categorie"] == "temple"


def test_interieur_deja_en_base_garde_sa_grille():
	"""Le lieu relu n'est pas réémis ; seule la connexion l'est, bouts vérifiés."""
	spec = gvp.INTERIEURS["lieu:grand_temple_d_abou_simbel"]
	(px, py), (tx, ty) = spec["pos_parent"], spec["pos"]
	ville = {"_id": "lieu:abou_simbel", "cells": [[0] * 50 for _ in range(82)]}
	temple = {"_id": "lieu:grand_temple_d_abou_simbel", "cells": [[0] * 88 for _ in range(48)]}
	ville["cells"][py][px] = temple["cells"][ty][tx] = 1
	propositions = {}
	docs, refus = gvp.interieurs({d["_id"]: d for d in (ville, temple)}, propositions)
	assert refus == [] and propositions == {} and [d["type"] for d in docs] == ["connection"]
	temple["cells"][ty][tx] = 0
	_, refus = gvp.interieurs({d["_id"]: d for d in (ville, temple)}, {})
	assert len(refus) == 1 and "non libre" in refus[0]
