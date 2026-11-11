# tests/test_apport.py
# Quête d'APPORT confiée par un PNJ (utils/apport.py, service `apport`) : offre écrite,
# acceptation → quête `collect` ordinaire, remise partielle puis complète, réception par un
# AUTRE PNJ du même lieu, linter. Exemple : les feuilles d'argentine d'Élise.

from utils import apport, lint_dialogues, quetes

COQ = "lieu:le_coq_de_lutece"
QID = "quete:plantes_d_elise"
ITEM = "item:Feuilles_d_argentine"


def _donneur(**offre):
	base = {"id": QID, "titre": "Trois plantes", "item": ITEM, "quantite": 3,
			"recompenses": {"xp": 40}}
	base.update(offre)
	return {"_id": "pnj:elise", "services": {"apport": {"offre": base}}}


def _receveur():
	return {"_id": "pnj:aubergiste", "services": {"apport": {"quete": QID}}}


def _feuilles(n):
	return [{"item": ITEM, "poids": 0.1} for _ in range(n)]


# ── Offre ────────────────────────────────────────────────────────────────────

def test_offre_illisible_ignoree():
	assert apport.offre_spec(_donneur(id="plantes")) is None
	assert apport.offre_spec(_donneur(item="argentine")) is None
	assert apport.offre_spec(_donneur(quantite=0)) is None
	assert apport.offre_spec(_donneur(quantite=True)) is None
	assert apport.offre_spec({"services": {}}) is None


def test_le_receveur_ne_offre_rien_mais_connait_la_quete():
	assert apport.offre_spec(_receveur()) is None
	assert apport.quete_id_de(_receveur()) == QID
	assert apport.quete_id_de(_donneur()) == QID


# ── Localisation (bouton 🗺️) ─────────────────────────────────────────────────

LOC = {"lieu": "lieu:france", "position": {"x": 55, "y": 32}}


def test_localisation_lisible_ou_ignoree():
	assert apport.offre_spec(_donneur())["localisation"] is None
	assert apport.offre_spec(_donneur(localisation=LOC))["localisation"] == LOC
	for faute in ({"lieu": "france", "position": {"x": 1, "y": 1}},
				  {"lieu": "lieu:france"},
				  {"lieu": "lieu:france", "position": {"x": -1, "y": 1}},
				  {"lieu": "lieu:france", "position": {"x": True, "y": 1}},
				  {"lieu": "lieu:france", "position": [55, 32]}):
		assert apport.localisation_spec(faute) is None, faute
		# Une localisation illisible n'invalide pas l'offre : seulement la carte.
		assert apport.offre_spec(_donneur(localisation=faute))["id"] == QID


def test_rencontre_lisible_sinon_toute_la_localisation_tombe():
	r = {"espece": "espece:bete", "accompagnants": ["espece:loup"], "nb_accompagnants": 3}
	assert apport.localisation_spec(dict(LOC, rencontre=r))["rencontre"] == r
	assert apport.rencontre_spec({"espece": "espece:bete"}) == {
		"espece": "espece:bete", "accompagnants": [], "nb_accompagnants": 0}
	assert apport.rencontre_spec({"espece": "espece:bete", "nb_accompagnants": 2})["nb_accompagnants"] == 0
	for faute in ({"espece": "bete"}, dict(r, accompagnants=["loup"]), dict(r, nb_accompagnants=-1),
				  dict(r, nb_accompagnants=True), dict(r, accompagnants="espece:loup")):
		assert apport.localisation_spec(dict(LOC, rencontre=faute)) is None, faute


def test_rencontre_situee_ici_dans_le_3x3_tant_que_rien_n_est_remis():
	r = {"espece": "espece:bete", "accompagnants": ["espece:loup"], "nb_accompagnants": 3}
	c = {"position": {"x": 54, "y": 33}}
	q = apport.accepter(c, _donneur(localisation=dict(LOC, rencontre=r)), COQ)
	assert apport.rencontre_situee_ici(c, "lieu:france") is q
	assert apport.rencontre_situee_ici(dict(c, position={"x": 53, "y": 32}), "lieu:france") is None
	assert apport.rencontre_situee_ici(c, COQ) is None
	assert apport.rencontre_situee_ici({k: v for k, v in c.items() if k != "position"}, "lieu:france") is None
	q["progress"] = q["objectif"]["quantite"]
	assert apport.rencontre_situee_ici(c, "lieu:france") is None
	# Localisation SANS rencontre : carte seule, aucune garantie.
	c2 = {"position": {"x": 55, "y": 32}}
	apport.accepter(c2, _donneur(localisation=LOC), COQ)
	assert apport.rencontre_situee_ici(c2, "lieu:france") is None


def test_instantiate_rencontre_une_cible_et_ses_seuls_accompagnants():
	from utils import combat
	cible = {"_id": "espece:bete", "nom": "Bête", "base_attributes": {}}
	loup = {"_id": "espece:loup", "nom": "Loup", "base_attributes": {}}
	monstres = combat.instantiate_rencontre(cible, [loup], [], 3)
	assert [m["espece_id"] for m in monstres] == ["espece:bete"] + ["espece:loup"] * 3
	assert len({m["id"] for m in monstres}) == 4
	assert [m["espece_id"] for m in combat.instantiate_rencontre(cible, [], [], 3)] == ["espece:bete"]
	assert combat.instantiate_rencontre(None, [loup], [], 3) == []


def test_accepter_recopie_la_localisation_hors_de_l_objectif():
	c = {}
	q = apport.accepter(c, _donneur(localisation=LOC), COQ)
	assert q["localisation"] == LOC and "lieu" not in q["objectif"]
	q["localisation"]["position"]["x"] = 0
	assert LOC["position"]["x"] == 55, "copie, jamais l'offre du doc"
	assert "localisation" not in apport.accepter({}, _donneur(), COQ)


def test_quete_detail_carte_d_un_apport_situe(monkeypatch):
	"""Même crop que les chasses (`_carte_chasse`), ancré sur le DONNEUR, repère dans la
	progression ; sans localisation, aucune carte."""
	from utils import focalisation, marche
	docs = {"lieu:france": {"_id": "lieu:france", "label": "France", "dimensions": {"x": 88, "y": 48}},
			COQ: {"_id": COQ, "label": "Le Coq de Lutèce", "lieu_parent": "lieu:lutecia"},
			"lieu:lutecia": {"_id": "lieu:lutecia", "label": "Lutecia"}}
	monkeypatch.setattr(marche, "_lieu_image_route", lambda lieu: ("france.png", "maps"))
	monkeypatch.setattr(focalisation, "charger_graphe", lambda fd: {})
	monkeypatch.setattr(focalisation, "prochaine_etape", lambda g, d, v: {"porte": (44, 12)})
	monkeypatch.setattr(quetes, "find_docs", lambda *a, **k: [])
	c = {"inventaire": []}
	q = apport.accepter(c, _donneur(localisation=LOC), COQ)
	detail = quetes.quete_detail(c, q, docs.get)
	assert detail["carte"]["position"] == LOC["position"]
	assert detail["carte"]["image"] == "france.png" and detail["carte"]["lieu_nom"] == "France"
	assert detail["carte"]["direction_texte"] == "Au sud-est de Lutecia"
	assert detail["progress_txt"].endswith("· Au sud-est de Lutecia")
	assert quetes._ancre_de({"label": "Le Coq de Lutèce"}) == "du Coq de Lutèce"
	assert quetes._ancre_de({"label": "La capitale Lutecia"}) == "de la capitale Lutecia"
	sans = apport.accepter({}, _donneur(), COQ)
	assert "carte" not in quetes.quete_detail({"inventaire": []}, sans, docs.get)


# ── Cycle de vie ─────────────────────────────────────────────────────────────

def test_accepter_pose_une_quete_collect_ordinaire():
	c = {}
	assert apport.etat(c, _donneur(), COQ)["apport_offert"]
	q = apport.accepter(c, _donneur(), COQ)
	assert q["id"] == QID and q["giver"] == COQ
	assert q["objectif"] == {"type": "collect", "cible": ITEM, "quantite": 3}
	assert c["quetes_actives"] == [q]
	e = apport.etat(c, _donneur(), COQ)
	assert not e["apport_offert"] and e["apport_en_cours"] and not e["apport_possible"]
	assert apport.accepter(c, _donneur(), COQ) is None, "pas deux fois la même quête"


def test_remise_partielle_puis_complete():
	c = {"inventaire": _feuilles(2)}
	apport.accepter(c, _donneur(), COQ)
	assert apport.etat(c, _donneur(), COQ)["apport_possible"]
	q, n, complete, _ = apport.remettre(c, _donneur(), COQ)
	assert (n, complete) == (2, False) and c["inventaire"] == []
	assert apport.reste_a_remettre(q) == 1
	assert not apport.etat(c, _donneur(), COQ)["apport_possible"], "plus rien en poche"
	c["inventaire"] = _feuilles(2)
	q, n, complete, _ = apport.remettre(c, _donneur(), COQ)
	assert (n, complete) == (1, True)
	assert len(c["inventaire"]) == 1, "on ne prend pas plus que le reste à faire"
	apport.archiver(c, q, now=123)
	assert c["quetes_actives"] == []
	assert c["quetes_terminees"][-1]["giver"] == COQ
	assert quetes.quete_reussie(c, QID)
	e = apport.etat(c, _donneur(), COQ)
	assert e["apport_accompli"] and not e["apport_offert"], "offre unique : pas reproposée"


def test_offre_non_unique_reproposee():
	c = {"quetes_terminees": [{"id": QID}]}
	assert apport.etat(c, _donneur(unique=False), COQ)["apport_offert"]
	assert not apport.etat(c, _donneur(), COQ)["apport_offert"]


def test_un_echec_rouvre_l_offre():
	c = {"quetes_terminees": [{"id": QID, "echec": True}]}
	assert apport.etat(c, _donneur(), COQ)["apport_offert"]


def test_un_autre_pnj_du_meme_lieu_recoit_la_remise():
	c = {"inventaire": _feuilles(3)}
	apport.accepter(c, _donneur(), COQ)
	assert apport.etat(c, _receveur(), COQ)["apport_possible"]
	assert not apport.etat(c, _receveur(), COQ)["apport_offert"]
	q, n, complete, _ = apport.remettre(c, _receveur(), COQ)
	assert (n, complete) == (3, True)


def test_la_remise_exige_le_lieu_du_donneur():
	c = {"inventaire": _feuilles(3)}
	apport.accepter(c, _donneur(), COQ)
	assert not apport.etat(c, _receveur(), "lieu:ailleurs")["apport_possible"]
	assert apport.remettre(c, _receveur(), "lieu:ailleurs") == (None, 0, False, [])
	assert len(c["inventaire"]) == 3


def test_les_pieces_portees_par_les_porteurs_comptent():
	"""Compagnon (Bob) ou monture : leurs sacs fournissent les pièces, le principal EN TÊTE (§7)."""
	c = {"inventaire": _feuilles(1)}
	bob = {"_id": "aventurier:bob", "inventaire": _feuilles(1)}
	mule = {"_id": "monture:mule", "inventaire": _feuilles(2)}
	apport.accepter(c, _donneur(), COQ)
	assert not apport.etat({"quetes_actives": c["quetes_actives"]}, _donneur(), COQ)["apport_possible"]
	assert apport.etat({"quetes_actives": c["quetes_actives"]}, _donneur(), COQ,
					   [bob])["apport_possible"], "seul Bob porte : la remise est possible"
	q, n, complete, touches = apport.remettre(c, _donneur(), COQ, [bob, mule])
	assert (n, complete) == (3, True)
	assert c["inventaire"] == [] and bob["inventaire"] == []
	assert len(mule["inventaire"]) == 1, "on ne prend que le reste à faire"
	assert touches == [bob, mule], "les sacs vidés sont à persister par l'appelant"


def test_placeholders_depuis_l_offre_puis_le_snapshot():
	nom = lambda iid: "Feuilles d'argentine"
	c = {"inventaire": _feuilles(1)}
	assert apport.placeholders(c, _donneur(), COQ, nom)["reste"] == 3
	apport.accepter(c, _donneur(), COQ)
	apport.remettre(c, _donneur(), COQ)
	p = apport.placeholders(c, _receveur(), COQ, nom)
	assert p == {"objet": "Feuilles d'argentine", "quantite": 3, "reste": 2, "xp": 40, "prime": 0}


# ── Linter ───────────────────────────────────────────────────────────────────

def _doc_lint(services, choix):
	return {"_id": "pnj:x", "type": "pnj", "services": services,
			"dialogue": {"noeud_depart": "a", "noeuds": {
				"a": {"texte": "…", "choix": choix},
				"ok": {"texte": "…", "choix": [{"id": "fin", "next": "fin", "label": "."}]},
			}}}


def test_linter_offre_illisible_et_remise_non_conditionnee():
	doc = _doc_lint({"apport": {"offre": {"id": "x"}, "noeuds": {"remis": "ok", "partiel": "ok", "accepte": "ok"}}},
					[{"id": "r", "label": ".", "action": {"service": "apport", "op": "remettre"}}])
	messages = [t["message"] for t in lint_dialogues.analyser([doc])["trouvailles"]]
	assert any("services.apport.offre" in m for m in messages)
	assert any("apport/remettre" in m and "apport_possible" in m for m in messages)


def test_linter_localisation_illisible():
	noeuds = {"remis": "ok", "partiel": "ok", "accepte": "ok"}
	choix = [{"id": "f", "label": ".", "next": "ok"}]
	offre = {"id": QID, "item": ITEM, "quantite": 1}
	bonne = _doc_lint({"apport": {"offre": dict(offre, localisation=LOC), "noeuds": noeuds}}, choix)
	assert not any("localisation" in t["message"] for t in lint_dialogues.analyser([bonne])["trouvailles"])
	mauvaise = _doc_lint({"apport": {"offre": dict(offre, localisation={"lieu": "france"}), "noeuds": noeuds}}, choix)
	assert any("localisation" in t["message"] for t in lint_dialogues.analyser([mauvaise])["trouvailles"])


def test_linter_receveur_sans_quete():
	doc = _doc_lint({"apport": {"noeuds": {"remis": "ok", "partiel": "ok"}}},
					[{"id": "f", "label": ".", "next": "ok"}])
	assert lint_dialogues.analyser([doc])["erreurs"] >= 1


# ── Routeur : accepter → remise partielle → remise complète ─────────────────

def test_router_cycle_complet(monkeypatch):
	from routers import pnj as rp
	sauves = []
	monkeypatch.setattr(rp, "get_doc", lambda _id: {"nom": "Feuilles d'argentine"} if _id == ITEM else None)
	monkeypatch.setattr(rp, "save_doc", lambda d: sauves.append(d) or d)
	monkeypatch.setattr(rp, "_inventory_payload", lambda c: {"n": len(c.get("inventaire", []))})
	monkeypatch.setattr(rp, "_vitals_payload", lambda c: {})
	monkeypatch.setattr(rp.quetes, "fiche_details", lambda c, *a, **k: ([], []))
	monkeypatch.setattr(rp.quetes, "recompenser_donneur", lambda *a, **k: None)
	monkeypatch.setattr(rp.recrutement, "groupe_effectif", lambda c, g: [])
	elise = {**_donneur(), "services": {"apport": {**_donneur()["services"]["apport"],
				"noeuds": {"accepte": "a", "partiel": "p", "remis": "r"}}}}
	lieu = {"_id": COQ}
	c = {"inventaire": _feuilles(1), "xp_total": 0, "cuivre": 0}

	rep = {}
	assert rp._resoudre_apport(c, elise, lieu, "accepter", rep)[0] == "a"
	assert rep["apport"] == {"accepte": "Trois plantes"}

	rep = {}
	suivant, dits = rp._resoudre_apport(c, elise, lieu, "remettre", rep)
	assert suivant == "p" and dits["reste"] == 2 and rep["apport"]["depose"] == 1

	c["inventaire"] = _feuilles(2)
	rep = {}
	suivant, dits = rp._resoudre_apport(c, elise, lieu, "remettre", rep)
	assert suivant == "r" and rep["apport"]["remis"] and rep["apport"]["xp"] == 40
	assert quetes.quete_reussie(c, QID) and c["quetes_actives"] == []

	import pytest
	from fastapi import HTTPException
	with pytest.raises(HTTPException):
		rp._resoudre_apport(c, elise, lieu, "remettre", {})
