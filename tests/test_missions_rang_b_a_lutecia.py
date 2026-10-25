# tests/test_missions_rang_b_a_lutecia.py
# Épreuves des rangs B et A de Lutecia (dev/gen_missions_rang_b_a_lutecia.py), toutes chez
# Maëlys via `services.<x>.offres` (utils/offres.py) : rejouées contre le DERNIER dump, puis
# contrôlées — fichier, ids, offres au bon cran, états AVANT / PENDANT / APRÈS de chaque PNJ,
# remise d'un trophée jusqu'au rang, cibles présentes en France, calibrage du puits de Chartres.

import importlib.util
import json
import os
import re
import sys

import pytest

from models import character_stats
from utils import acces, apport, lint_dialogues, offres, pnj, quetes, transport
from utils.recrutement import RANGS

RACINE = os.path.join(os.path.dirname(__file__), "..")
FICHIER = os.path.join(RACINE, "jsons", "missions_rang_b_a_lutecia_a_importer.json")


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_missions_rang_b_a_lutecia.py")
	spec = importlib.util.spec_from_file_location("gen_missions_rang_b_a_lutecia", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


GEN = _gen()
with open(GEN.dernier_dump([]), encoding="utf-8") as _f:
	DUMP = {d["_id"]: d for d in json.load(_f)["docs"]}
DOCS = {d["_id"]: d for d in GEN.generer(DUMP)}
BUREAU = {"_id": GEN.BUREAU, "lieu_parent": GEN.LUTECIA}
MAELYS = DOCS[GEN.MAELYS]


def _perso(rang="C", actives=(), reussies=()):
	return {
		"rangs_guilde": {GEN.LUTECIA: rang},
		"quetes_actives": [{"id": q} for q in actives],
		"quetes_terminees": [{"id": q} for q in reussies],
	}


def _ids_offres(service):
	return [e["offre"]["id"] for e in MAELYS["services"][service]["offres"]]


def _visibles(doc, character, flags=None, noeud="accueil"):
	ctx = pnj.contexte_dialogue(character, doc, lambda _l: 0, flags or {}, {},
								quetes.quetes_reussies(character), quetes.quetes_actives_ids(character))
	return {c["id"] for c in pnj._choix_visibles(doc, noeud, ctx)}


# ── Le fichier ───────────────────────────────────────────────────────────────

def test_le_fichier_est_a_jour_et_passe_le_linter():
	with open(FICHIER, encoding="utf-8") as f:
		fichier = json.load(f)
	assert {d["_id"]: d for d in fichier} == DOCS, "relancer dev/gen_missions_rang_b_a_lutecia.py"
	rapport = lint_dialogues.analyser(fichier)
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


def test_regeneration_idempotente():
	"""Rejouée sur un dump où l'import a déjà eu lieu, la génération rend les mêmes docs."""
	apres_import = dict(DUMP)
	apres_import.update(DOCS)
	assert {d["_id"]: d for d in GEN.generer(apres_import)} == DOCS


def test_les_ids_de_quete_sont_ceux_des_offres():
	ids = {e["offre"]["id"] for s in offres.SERVICES_LISTABLES for e in MAELYS["services"][s]["offres"]}
	assert set(GEN.QUETES_B) | set(GEN.QUETES_A) | {GEN.LETTRE_C} == ids
	nommees = set()
	for doc in DOCS.values():
		blobs = [doc.get("dialogue", {})] + [e.get("conditions") for e in doc.get("pnj") or []] + [doc.get("acces")]
		texte = json.dumps(blobs, ensure_ascii=False)
		nommees |= {m for m in ids if f'"{m}"' in texte}
		# Toute quête de rang nommée par une condition est une offre de Maëlys.
		for brut in re.findall(r'"(quete:rang_[a-z0-9_]+)"', texte):
			assert brut in ids, (doc["_id"], brut)
	assert set(GEN.QUETES_B) | set(GEN.QUETES_A) <= nommees
	# La descente du Temple est nommée par Maëlys (rapport) ET offerte par le commandeur.
	assert f'"{GEN.CRISTAL_OSSUAIRE}"' in json.dumps(MAELYS["dialogue"], ensure_ascii=False)
	assert apport.offre_spec(DOCS[GEN.COMMANDEUR])["id"] == GEN.CRISTAL_OSSUAIRE


def test_plusieurs_missions_par_rang_et_un_seul_type_par_tirage():
	rangs = {}
	for s in offres.SERVICES_LISTABLES:
		for e in MAELYS["services"][s]["offres"]:
			rangs.setdefault(e["offre"]["recompenses"].get("rang_guilde"), []).append(s)
	assert len(rangs["B"]) >= 2 and len(rangs["A"]) >= 2
	assert len(set(rangs["B"])) >= 2 and len(set(rangs["A"])) >= 2, "plusieurs TYPES par montée"


# ── Maëlys : la bonne épreuve au bon cran ────────────────────────────────────

def _vue(character, rand_fn=lambda: 0.0):
	character.pop("offres_tirees", None)
	offres.poser_offres_tirees(character, BUREAU, [MAELYS], rand_fn)
	return offres.vue_pnj(MAELYS, character, BUREAU)


@pytest.mark.parametrize("rang, attendues", [
	("D", {GEN.LETTRE_C}),
	("C", set(GEN.QUETES_B)),
	("B", set(GEN.QUETES_A)),
	("A", set()),
])
def test_les_offres_tirees_sont_celles_du_cran(rang, attendues):
	vues = set()
	for t in (0.0, 0.34, 0.67, 0.99):
		vue = _vue(_perso(rang), lambda t=t: t)
		vues |= set(vue[offres.CLE_RETENUES])
	assert vues == attendues


def test_au_rang_c_maelys_ne_reparle_pas_de_jumieges():
	c = _perso("C")
	vue = _vue(c)
	flags = {"transport_offert": True, "apport_offert": True, "escorte_offerte": True}
	visibles = _visibles(vue, c, flags)
	assert not {x for x in visibles if x.startswith("rang_c_")}
	assert any(x.startswith("b_") and x.endswith("_offre") for x in visibles)
	assert not any(x.startswith("a_") and x.endswith("_offre") for x in visibles)


def test_au_rang_d_l_epreuve_de_jumieges_reste_offerte():
	c = _perso("D")
	c["quetes_terminees"].append({"id": "quete:escorte_convoi_de_lutecia"})
	vue = _vue(c)
	assert "rang_c_offre" in _visibles(vue, c, {"transport_offert": True})


def test_une_epreuve_acceptee_ferme_les_autres_du_meme_cran():
	c = _perso("C", actives=[GEN.B_AIX])
	vue = _vue(c)
	assert vue[offres.CLE_RETENUES] == [GEN.B_AIX]


def test_remettre_la_tete_de_gargouille_monte_au_rang_b():
	c = _perso("C")
	tire = lambda: _ids_offres("apport").index(GEN.B_GARGOUILLE) / len(_ids_offres("apport"))
	vue = _vue(c, tire)
	assert apport.offre_spec(vue)["id"] == GEN.B_GARGOUILLE
	q = apport.accepter(c, vue, GEN.BUREAU)
	assert q and q["rang"] == "B"
	c.setdefault("inventaire", []).append({"item": GEN.TETE_GARGOUILLE, "poids": 20.0})
	vue = offres.vue_pnj(MAELYS, c, BUREAU)
	assert apport.etat(c, vue, GEN.BUREAU)["apport_possible"]
	q, n, complete = apport.remettre(c, vue, GEN.BUREAU)
	assert complete and n == 1
	recap = quetes.appliquer_recompenses(c, q, compagnons=[])
	assert recap["rang"] == "B" and c["rangs_guilde"][GEN.LUTECIA] == "B"


def test_les_courses_ecrites_se_lisent_et_promeuvent():
	for qid in (GEN.B_AIX, GEN.B_TEMPLE):
		e = next(x for x in MAELYS["services"]["transport"]["offres"] if x["offre"]["id"] == qid)
		spec = offres._offre_resolue(e["offre"], BUREAU)
		assert spec["recompenses"]["rang_guilde"] == {"cite": GEN.LUTECIA, "rang": "B"}
		assert DOCS[spec["destination"]]["type"] == "lieu"
		assert set(e["noeuds"]) >= lint_dialogues.TRANSPORT_DONNEUR | lint_dialogues.TRANSPORT_RETOUR


# ── Trois états, PNJ par PNJ ─────────────────────────────────────────────────

ETATS = [
	# Les arches du chancelier sont un sujet NEUTRE (aucun état) : hors de la grille.
	(GEN.CHANCELIER, GEN.B_AIX, set(), {"attente"}, {"apres_pli"}),
	(GEN.CHANCELIER, GEN.A_DELEGATION, set(), {"delegation"}, {"apres_delegation"}),
	(GEN.GARDIENNE, GEN.A_AMPOULE, {"portes"}, {"ampoule"}, {"apres"}),
	# Le commandeur a un PENDANT en plusieurs temps (pli, descente, cristal) : test dédié plus bas.
	(GEN.COMMANDEUR, GEN.B_TEMPLE, {"bonjour"}, set(), {"apres"}),
	(GEN.GARDE_MARS, GEN.B_MARS, {"bonjour"}, {"architecte"}, {"apres"}),
	(GEN.TEMPLIER_CRYPTE, GEN.A_MINOTAURE, {"bonjour"}, set(), {"apres"}),
]


@pytest.mark.parametrize("pnj_id, qid, avant, pendant, apres", ETATS)
def test_trois_etats(pnj_id, qid, avant, pendant, apres):
	doc = DOCS[pnj_id]
	propres = avant | pendant | apres
	v_avant = _visibles(doc, _perso())
	v_pendant = _visibles(doc, _perso(actives=[qid]))
	v_apres = _visibles(doc, _perso(reussies=[qid]))
	assert avant <= v_avant and not ((pendant | apres) - avant) & v_avant
	assert pendant <= v_pendant and not (apres - pendant) & v_pendant
	assert apres <= v_apres and not ((avant | pendant) - apres) & v_apres
	assert propres, "chaque PNJ dit quelque chose dans au moins un état"


# ── La porte qui ne devait pas s'ouvrir : le pli, puis la descente à l'ossuaire ─────

@pytest.mark.parametrize("actives, reussies, flags, attendus, exclus", [
	((), (), {}, {"bonjour"}, {"pli", "descente", "cristal", "relance", "attente", "apres"}),
	((GEN.B_TEMPLE,), (), {"transport_a_livrer": True}, {"pli"}, {"descente", "attente", "bonjour"}),
	((GEN.B_TEMPLE,), (), {"apport_offert": True}, {"descente"}, {"pli", "attente", "relance"}),
	((GEN.B_TEMPLE, GEN.CRISTAL_OSSUAIRE), (), {"apport_en_cours": True}, {"relance"}, {"descente", "cristal", "attente"}),
	((GEN.B_TEMPLE, GEN.CRISTAL_OSSUAIRE), (), {"apport_en_cours": True, "apport_possible": True}, {"cristal"}, {"relance", "attente"}),
	((GEN.B_TEMPLE,), (GEN.CRISTAL_OSSUAIRE,), {}, {"attente"}, {"descente", "cristal", "apres"}),
	((), (GEN.B_TEMPLE, GEN.CRISTAL_OSSUAIRE), {}, {"apres"}, {"bonjour", "attente", "descente"}),
])
def test_le_commandeur_du_pli_a_l_ossuaire(actives, reussies, flags, attendus, exclus):
	visibles = _visibles(DOCS[GEN.COMMANDEUR], _perso(actives=actives, reussies=reussies), flags)
	assert attendus <= visibles and not exclus & visibles, visibles


def test_la_descente_n_est_offerte_qu_apres_le_pli():
	"""L'apport du commandeur n'a pas de condition propre : c'est le CHOIX qui le réserve à
	qui lui a remis le pli de Maëlys."""
	visibles = _visibles(DOCS[GEN.COMMANDEUR], _perso(), {"apport_offert": True})
	assert "descente" not in visibles


def test_maelys_ne_solde_le_temple_qu_apres_l_ossuaire():
	c = _perso("C", actives=[GEN.B_TEMPLE])
	vue = _vue(c)
	flags = {"transport_a_rapporter": True}
	sans = _visibles(vue, c, flags)
	assert "b_temple_attente" in sans and "b_temple_rapport" not in sans
	c["quetes_terminees"].append({"id": GEN.CRISTAL_OSSUAIRE})
	avec = _visibles(vue, c, flags)
	assert "b_temple_rapport" in avec and "b_temple_attente" not in avec


def test_le_cristal_jaune_ne_vient_que_du_coffre_de_l_ossuaire():
	"""La preuve de la descente ne vaut que si le cristal n'a pas d'autre source : ni boutique,
	ni recette, ni autre donjon (personnages du dump exclus : c'est l'état d'un joueur)."""
	sources = [d["_id"] for d in DUMP.values()
			   if d["_id"] != GEN.CRISTAL_JAUNE and d.get("type") != "character"
			   and f'"{GEN.CRISTAL_JAUNE}"' in json.dumps(d, ensure_ascii=False)]
	assert sources == ["donjon:catacombes_de_lutecia"], sources
	salle = next(b for b in DUMP["donjon:catacombes_de_lutecia"]["battle_maps"]
				 if f'"{GEN.CRISTAL_JAUNE}"' in json.dumps(b))
	assert salle["lieu"] == GEN.OSSUAIRE
	assert {"item": GEN.CRISTAL_JAUNE, "quantite": 1} in salle["tresor"]["garanti"]


def test_hugues_n_est_sous_l_arche_qu_apres_l_escorte():
	entree = next(e for e in DOCS[GEN.PORTE_MARS]["pnj"] if e["character"] == GEN.HUGUES)
	get = DUMP.get
	assert not acces.clauses_remplies(_perso(), entree["conditions"], get)
	assert not acces.clauses_remplies(_perso(actives=[GEN.B_MARS]), entree["conditions"], get)
	assert acces.clauses_remplies(_perso(reussies=[GEN.B_MARS]), entree["conditions"], get)


def test_le_puits_ne_s_ouvre_que_tete_a_rapporter():
	salle = DOCS[GEN.LABYRINTHE]
	en_cours = {"quetes_actives": [{"id": GEN.A_MINOTAURE, "objectif": {"type": "collect", "cible": GEN.TETE_MINOTAURE, "quantite": 1}, "progress": 0}]}
	assert acces.acces_autorise(en_cours, salle, DUMP.get)[0]
	assert not acces.acces_autorise(_perso(), salle, DUMP.get)[0]


# ── Cibles et calibrage ──────────────────────────────────────────────────────

def test_les_trophees_existent_et_leurs_especes_rodent_en_france():
	france = DOCS[GEN.FRANCE]
	zones_carte = {z["zone"] for z in france.get("zone_influences") or []}
	for tete, espece in ((GEN.TETE_GARGOUILLE, GEN.GARGOUILLE),
						 (GEN.TETE_GEANT, "espece:geant_du_mont_saint_michel"),
						 (GEN.TETE_BETE, "espece:bete_du_gevaudan")):
		assert tete in DUMP
		zones = {z for r in france["rencontres"] if r["espece"] == espece for z in r["zones"]}
		assert zones & zones_carte, espece


def test_les_portes_sont_sur_des_cases_praticables():
	for lieu, (cite, _cible) in GEN.CIBLES_PORTES.items():
		lien = next(d for d in DOCS.values() if d.get("type") == "connection"
					and any(n["lieu"] == lieu for n in d["nodes"]))
		x, y = next(n["pos"] for n in lien["nodes"] if n["lieu"] == cite)
		assert DUMP[cite]["cells"][y][x] == 1, lieu


def test_deux_minotaures_passent_le_plancher_du_rang_a(monkeypatch):
	"""Calibrage (Auteur, 25/10) : un Minotaure seul n'atteint pas le plancher A ; les deux de
	la salle, au grade le plus BAS de la fourchette du donjon, le passent. ⚠️ Toutes les
	lectures de base passent par le dump : sans quoi l'équipement des humanoïdes vaut 0."""
	from utils import potentiel
	for nom, mod in list(sys.modules.items()):
		if nom.split(".")[0] in ("utils", "models", "db") and hasattr(mod, "get_doc"):
			monkeypatch.setattr(mod, "get_doc", lambda i, *a, **k: DUMP.get(i))
	salle = DOCS[GEN.DONJON_PUITS]["battle_maps"][0]
	tags = set(DUMP[GEN.MINOTAURE].get("tags") or [])
	profils = [p for p in DUMP.values() if p["_id"].startswith("profil:")
			   and salle["niveau_min"] <= p.get("niveau", 0) <= salle["niveau_max"]
			   and set(p.get("restriction_tags") or []) <= tags]
	assert profils
	plancher = character_stats.QUETE_RANG_POTENTIEL_MIN["A"]
	for p in profils:
		seul = potentiel.potentiel_espece(GEN.MINOTAURE, p["_id"], DUMP.get)["total"]
		assert seul < plancher <= salle["nb_monstres"] * seul, (p["_id"], seul)
