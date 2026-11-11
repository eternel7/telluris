# tests/test_missions_rang_b_a_lutecia.py
# Épreuves des rangs B et A de Lutecia (dev/gen_missions_rang_b_a_lutecia.py), toutes chez
# Maëlys via `services.<x>.offres` (utils/offres.py) : rejouées contre le DERNIER dump, puis
# contrôlées — fichier, ids, offres au bon cran, états AVANT / PENDANT / APRÈS de chaque PNJ,
# remise d'un trophée jusqu'au rang, cibles présentes en France, calibrage du puits de Chartres.

import copy
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
	q, n, complete, _ = apport.remettre(c, vue, GEN.BUREAU)
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


def test_le_cristal_jaune_ne_vient_que_des_coffres_de_donjon():
	"""La preuve de la descente ne vaut que si le cristal n'a d'autre source qu'un coffre de
	donjon — l'ossuaire des catacombes, et le coffre du Minotaure de Chartres (Auteur, 25/10) :
	ni boutique, ni recette (personnages et propriétés du dump exclus : c'est l'état d'un
	joueur — le coffre d'un domaine garde ce que son propriétaire y a rangé). Le
	commandeur DEMANDE le cristal (objet de son apport) : une fois l'import passé il est dans le
	dump, d'où son exclusion — tant qu'il ne fait que le demander."""
	if GEN.COMMANDEUR in DUMP:
		commandeur = copy.deepcopy(DUMP[GEN.COMMANDEUR])
		assert commandeur["services"]["apport"]["offre"].pop("item") == GEN.CRISTAL_JAUNE
		assert f'"{GEN.CRISTAL_JAUNE}"' not in json.dumps(commandeur, ensure_ascii=False)
	sources = [d["_id"] for d in DUMP.values()
			   if d["_id"] not in (GEN.CRISTAL_JAUNE, GEN.COMMANDEUR) and d.get("type") not in ("character", "propriete")
			   and f'"{GEN.CRISTAL_JAUNE}"' in json.dumps(d, ensure_ascii=False)]
	# Le Notre-Dame de dev/gen_portail_notre_dame.py le DEMANDE (prix du passage), il n'en
	# donne pas : écarté s'il est déjà importé.
	sources = [i for i in sources if i != "pnj:aenor_de_sully"]
	assert "donjon:catacombes_de_lutecia" in sources
	assert set(sources) <= {"donjon:catacombes_de_lutecia", GEN.DONJON_PUITS}, sources
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


def test_le_puits_s_ouvre_a_tout_rang_b_ou_plus_avec_ou_sans_mission():
	"""Auteur, 25/10 : le Templier laisse descendre tout rang B ou plus, mission ou non."""
	salle = DOCS[GEN.LABYRINTHE]
	tete = {"id": GEN.A_MINOTAURE, "objectif": {"type": "collect", "cible": GEN.TETE_MINOTAURE, "quantite": 1}, "progress": 0}
	en_epreuve = {**_perso(rang="B"), "quetes_actives": [tete]}
	assert acces.acces_autorise(en_epreuve, salle, DUMP.get)[0]
	assert acces.acces_autorise(_perso(rang="B"), salle, DUMP.get)[0]
	assert acces.acces_autorise(_perso(rang="A", reussies=[GEN.A_MINOTAURE]), salle, DUMP.get)[0]
	# Sous le rang B, ni la mission ni rien d'autre n'ouvre le puits.
	assert not acces.acces_autorise(_perso(), salle, DUMP.get)[0]
	assert not acces.acces_autorise({**_perso(), "quetes_actives": [tete]}, salle, DUMP.get)[0]
	# Salle de donjon : aucun laissez-passer, chaque descente est un combat neuf.
	assert salle["categorie"] == "battle_map"


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


# ── La Bête : située, carte 🗺️ (dev/gen_carte_bete_gevaudan.py) ─────────────────

def _offre_bete():
	return next(e["offre"] for e in MAELYS["services"]["apport"]["offres"] if e["offre"]["id"] == GEN.A_BETE)


def test_la_bete_est_situee_dans_une_zone_ou_elle_rode():
	"""Tout le 3×3 du crop tombe dans un placement de la zone où la Bête est aux rencontres,
	sur des cases praticables de la carte de France : la carte ne ment pas sur le terrain."""
	from utils import zones
	loc = apport.localisation_spec(_offre_bete().get("localisation"))
	assert loc == GEN.LOCALISATION_BETE and loc["lieu"] == GEN.FRANCE
	france = DOCS[GEN.FRANCE]
	assert any(r["espece"] == "espece:bete_du_gevaudan" and GEN.ZONE_BETE in r["zones"]
			   for r in france["rencontres"])
	px, py = loc["position"]["x"], loc["position"]["y"]
	for dx in (-1, 0, 1):
		for dy in (-1, 0, 1):
			assert zones.est_dans_zone(px + dx, py + dy, GEN.ZONE_BETE, france["zone_influences"]), (dx, dy)
			assert france["cells"][py + dy][px + dx] > 0, (dx, dy)


def test_la_carte_de_la_bete_part_de_lutecia(monkeypatch):
	"""De bout en bout sur le dump : Maëlys confie la quête, l'onglet 📜 reçoit la carte de
	France (image servable) et le repère part de Lutecia, la cité du bureau."""
	from utils import focalisation
	monkeypatch.setattr(quetes, "find_docs", lambda sel: [d for d in DUMP.values() if d.get("type") == sel.get("type")])
	monkeypatch.setitem(focalisation._graphe_cache, "graphe", None)
	c = {"inventaire": [], "rangs_guilde": {GEN.LUTECIA: "B"},
		 "offres_tirees": {"lieu": GEN.BUREAU, "tirages": {GEN.MAELYS: {"apport": GEN.A_BETE}}}}
	vue = offres.vue_pnj(MAELYS, c, BUREAU)
	q = apport.accepter(c, vue, GEN.BUREAU)
	assert q and q["id"] == GEN.A_BETE
	detail = quetes.quete_detail(c, q, lambda i: DOCS.get(i) or DUMP.get(i))
	carte = detail["carte"]
	assert carte["position"] == GEN.LOCALISATION_BETE["position"]
	assert carte["image"] == DUMP[GEN.FRANCE]["image"] and carte["image_route"]
	assert carte["direction_texte"] == "Au sud-est de la capitale Lutecia", carte
	monkeypatch.setitem(focalisation._graphe_cache, "graphe", None)


def test_maelys_ne_situe_la_bete_qu_en_la_proposant():
	"""« Où la chercher ? » n'existe qu'à l'offre (AVANT) ; la relance (PENDANT) redit le lieu."""
	n = MAELYS["dialogue"]["noeuds"]
	assert any(c.get("next") == "a_bete_carte" for c in n["a_bete_propose"]["choix"])
	sources = [k for k, nd in n.items() for c in nd.get("choix") or [] if c.get("next") == "a_bete_carte"]
	assert sources == ["a_bete_propose"]
	assert "Gévaudan" in n["a_bete_relance"]["texte"] and "Gévaudan" in n["a_bete_accepte"]["texte"]


def test_le_delta_de_la_carte_est_a_jour_et_ne_touche_que_la_bete():
	chemin = os.path.join(RACINE, "dev", "gen_carte_bete_gevaudan.py")
	spec = importlib.util.spec_from_file_location("gen_carte_bete_gevaudan", chemin)
	delta = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(delta)
	docs = delta.generer(DUMP)
	with open(delta.SORTIE, encoding="utf-8") as f:
		assert json.load(f) == docs, "relancer dev/gen_carte_bete_gevaudan.py"
	assert lint_dialogues.analyser(docs)["erreurs"] == 0
	(doc,) = docs
	avant = DUMP[GEN.MAELYS]
	assert {k for k in doc if doc[k] != avant.get(k)} <= {"services", "dialogue", "_rev"}
	changes = {k for k, v in doc["dialogue"]["noeuds"].items() if v != avant["dialogue"]["noeuds"].get(k)}
	assert changes and all(k.startswith("a_bete_") for k in changes)
	autres = lambda d: [e for e in d["services"]["apport"]["offres"] if e["offre"]["id"] != GEN.A_BETE]
	assert autres(doc) == autres(avant)
	assert delta.generer({**DUMP, GEN.MAELYS: doc}) == docs, "idempotent"


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


# ── La Bête : rencontre garantie dans le 3×3 (apport.rencontre_situee_ici) ───────

class _Capture(Exception):
	pass


def _lancer_combat(monkeypatch, character):
	"""`start_combat` réel sur le dump ; `create_combat_doc` intercepté → monstres tirés."""
	import asyncio
	from routers import combat as rc
	monkeypatch.setattr(rc, "get_selected_character", lambda u: character)
	monkeypatch.setattr(rc, "get_doc", lambda i: DOCS.get(i) or DUMP.get(i))
	monkeypatch.setattr(rc, "find_docs", lambda sel: [] if sel.get("type") == "combat" else
						[d for d in DUMP.values() if d.get("type") == sel.get("type")])

	def capture(_c, monstres, *a, **k):
		raise _Capture(monstres)
	monkeypatch.setattr(rc, "create_combat_doc", capture)
	try:
		asyncio.run(rc.start_combat(rc.StartCombatRequest(), {"_id": "user:test"}))
	except _Capture as e:
		return e.args[0]
	return None


def _chasseur(x, y, localisation=None):
	q = {"id": GEN.A_BETE, "giver": GEN.BUREAU, "progress": 0,
		 "objectif": {"type": "collect", "cible": GEN.TETE_BETE, "quantite": 1},
		 "localisation": copy.deepcopy(localisation or _offre_bete()["localisation"])}
	return {"_id": "character:test", "lieu": GEN.FRANCE, "position": {"x": x, "y": y},
			"inventaire": [], "quetes_actives": [q]}


def test_la_bete_vient_avec_ses_loups_et_rien_d_autre(monkeypatch):
	loc = _offre_bete()["localisation"]
	assert loc["rencontre"] == {"espece": "espece:bete_du_gevaudan", "accompagnants": [GEN.LOUP],
								"nb_accompagnants": 3}
	assert GEN.LOUP in DUMP and "espece:bete_du_gevaudan" in DUMP
	px, py = loc["position"]["x"], loc["position"]["y"]
	for dx, dy in ((0, 0), (-1, 1), (1, -1)):
		monstres = _lancer_combat(monkeypatch, _chasseur(px + dx, py + dy))
		especes = [m["espece_id"] for m in monstres]
		assert especes.count("espece:bete_du_gevaudan") == 1, especes
		assert sorted(especes) == sorted(["espece:bete_du_gevaudan"] + [GEN.LOUP] * 3), especes
		assert len({m["id"] for m in monstres}) == len(monstres)


def test_hors_du_3x3_ou_tete_remise_la_rencontre_redevient_ordinaire(monkeypatch):
	from utils import apport as ap
	loc = _offre_bete()["localisation"]
	px, py = loc["position"]["x"], loc["position"]["y"]
	assert ap.rencontre_situee_ici(_chasseur(px, py), GEN.FRANCE)
	assert ap.rencontre_situee_ici(_chasseur(px + 2, py), GEN.FRANCE) is None
	assert ap.rencontre_situee_ici(_chasseur(px, py), GEN.LUTECIA) is None
	remise = _chasseur(px, py)
	remise["quetes_actives"][0]["progress"] = 1
	assert ap.rencontre_situee_ici(remise, GEN.FRANCE) is None
	# Hors du 3×3, `start_combat` ne compose pas la rencontre : tirage ordinaire de la zone.
	from routers import combat as rc
	appels = []
	monkeypatch.setattr(rc, "instantiate_rencontre", lambda *a, **k: appels.append(a) or [])
	_lancer_combat(monkeypatch, _chasseur(px + 2, py))
	assert appels == []
	_lancer_combat(monkeypatch, _chasseur(px, py))
	assert len(appels) == 1
