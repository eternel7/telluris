# tests/test_offres_multiples.py
# PLUSIEURS offres écrites par service (utils/offres.py) : un PNJ à `offres` n'en tient
# qu'une par service — celle en cours, sinon celle tirée à l'entrée et toujours éligible.
# Éligibilité : unique déjà réussie écartée, épreuve de rang au seul cran du dessous, une
# seule épreuve de rang à la fois chez ce donneur. Condition de dialogue `offre`, linter.

from utils import apport, escorte, lint_dialogues, offres, pnj, transport
from utils.recrutement import RANGS

CITE = "lieu:lutecia"
BUREAU = {"_id": "lieu:bureau", "lieu_parent": CITE}


def _entree(qid, rang=None, **extra):
	offre = {"id": qid, "item": "item:x", "quantite": 1, "recompenses": {"xp": 10}}
	if rang:
		offre["recompenses"]["rang_guilde"] = rang
	offre.update(extra)
	return {"offre": offre, "noeuds": {"accepte": "acc_" + qid[6:]}}


def _maitresse(*entrees_apport, transport_offres=None):
	services = {"apport": {"offres": list(entrees_apport)}}
	if transport_offres is not None:
		services["transport"] = {"offres": transport_offres}
	return {"_id": "pnj:maitresse", "services": services}


def _perso(rang="C", actives=(), terminees=()):
	return {
		"rangs_guilde": {CITE: rang},
		"quetes_actives": [{"id": q} for q in actives],
		"quetes_terminees": [{"id": q} for q in terminees],
	}


def _premier(_n=None):
	return 0.0


def _dernier():
	return 0.999


# ── Compatibilité ────────────────────────────────────────────────────────────

def test_un_doc_sans_offres_est_rendu_tel_quel():
	doc = {"_id": "pnj:x", "services": {"apport": {"offre": {"id": "quete:a"}, "noeuds": {"accepte": "n"}}}}
	vue = offres.vue_pnj(doc, _perso(), BUREAU)
	assert vue["services"] == doc["services"]
	assert vue[offres.CLE_RETENUES] == ["quete:a"]
	assert offres.vue_pnj(None, _perso(), BUREAU) is None


def test_la_vue_ne_mute_pas_le_doc():
	doc = _maitresse(_entree("quete:b1", "B"))
	c = _perso()
	offres.poser_offres_tirees(c, BUREAU, [doc], _premier)
	offres.vue_pnj(doc, c, BUREAU)
	assert "offres" in doc["services"]["apport"] and offres.CLE_RETENUES not in doc


# ── Tirage et retenue ────────────────────────────────────────────────────────

def test_tirage_persiste_un_refresh_ne_retire_pas():
	doc = _maitresse(_entree("quete:b1", "B"), _entree("quete:b2", "B"))
	c = _perso()
	assert offres.poser_offres_tirees(c, BUREAU, [doc], _premier)
	assert offres.vue_pnj(doc, c, BUREAU)["services"]["apport"]["offre"]["id"] == "quete:b1"
	assert not offres.poser_offres_tirees(c, BUREAU, [doc], _dernier), "refresh : aucun nouveau tirage"
	assert offres.vue_pnj(doc, c, BUREAU)["services"]["apport"]["offre"]["id"] == "quete:b1"
	# Ressortir puis rentrer : nouveau tirage.
	offres.poser_offres_tirees(c, {"_id": "lieu:couloir"}, [], _premier)
	offres.poser_offres_tirees(c, BUREAU, [doc], _dernier)
	assert offres.vue_pnj(doc, c, BUREAU)["services"]["apport"]["offre"]["id"] == "quete:b2"


def test_la_vue_reduit_le_service_au_bloc_retenu():
	doc = _maitresse(_entree("quete:b1", "B"), _entree("quete:b2", "B"))
	c = _perso()
	offres.poser_offres_tirees(c, BUREAU, [doc], _dernier)
	conf = offres.vue_pnj(doc, c, BUREAU)["services"]["apport"]
	assert "offres" not in conf
	assert conf["noeuds"] == {"accepte": "acc_b2"}
	assert apport.offre_spec({"services": {"apport": conf}})["id"] == "quete:b2"


def test_la_quete_active_prime_sur_le_tirage():
	doc = _maitresse(_entree("quete:b1", "B"), _entree("quete:b2", "B"))
	c = _perso(actives=["quete:b2"])
	offres.poser_offres_tirees(c, BUREAU, [doc], _premier)
	assert offres.vue_pnj(doc, c, BUREAU)["services"]["apport"]["offre"]["id"] == "quete:b2"


def test_sans_tirage_pour_ce_lieu_rien_n_est_propose():
	doc = _maitresse(_entree("quete:b1", "B"))
	conf = offres.vue_pnj(doc, _perso(), BUREAU)["services"]["apport"]
	assert "offre" not in conf


# ── Éligibilité ──────────────────────────────────────────────────────────────

def test_offre_unique_deja_reussie_ecartee():
	doc = _maitresse(_entree("quete:z"))
	c = _perso(terminees=["quete:z"])
	assert offres.tirer(c, doc, BUREAU, _premier) == {}
	c2 = _perso(terminees=["quete:z"])
	doc2 = _maitresse(_entree("quete:z", unique=False))
	assert offres.tirer(c2, doc2, BUREAU, _premier) == {"apport": "quete:z"}


def test_une_epreuve_de_rang_n_est_ouverte_qu_au_cran_du_dessous():
	doc = _maitresse(_entree("quete:b1", "B"), _entree("quete:a1", "A"))
	i = RANGS.index("B")
	assert offres.tirer(_perso(RANGS[i - 1]), doc, BUREAU, _premier) == {"apport": "quete:b1"}
	assert offres.tirer(_perso("B"), doc, BUREAU, _premier) == {"apport": "quete:a1"}
	assert offres.tirer(_perso("A"), doc, BUREAU, _premier) == {}
	assert offres.tirer(_perso(RANGS[i - 2]), doc, BUREAU, _premier) == {}


def test_rang_gagne_en_cours_de_visite_ferme_les_autres_epreuves_du_meme_cran():
	doc = _maitresse(_entree("quete:b1", "B"))
	c = _perso("C")
	offres.poser_offres_tirees(c, BUREAU, [doc], _premier)
	c["rangs_guilde"][CITE] = "B"
	assert "offre" not in offres.vue_pnj(doc, c, BUREAU)["services"]["apport"]


def test_une_seule_epreuve_de_rang_a_la_fois_tous_services_confondus():
	tr = [{"offre": {"id": "quete:tb", "destination": "lieu:aix", "cargaison": [{"item": "item:pli"}],
					 "recompenses": {"rang_guilde": "B"}}, "noeuds": {}}]
	doc = _maitresse(_entree("quete:b1", "B"), _entree("quete:libre"), transport_offres=tr)
	c = _perso("C", actives=["quete:tb"])
	tire = offres.tirer(c, doc, BUREAU, _premier)
	assert tire == {"apport": "quete:libre"}, "une offre sans rang reste ouverte"
	assert offres.epreuve_active(c, doc, BUREAU) == "quete:tb"


def test_la_recompense_de_rang_est_resolue_pour_la_cite_du_donneur():
	doc = _maitresse(_entree("quete:b1", "B"))
	c = _perso()
	offres.poser_offres_tirees(c, BUREAU, [doc], _premier)
	rec = offres.vue_pnj(doc, c, BUREAU)["services"]["apport"]["offre"]["recompenses"]
	assert rec["rang_guilde"] == {"cite": CITE, "rang": "B"}
	assert doc["services"]["apport"]["offres"][0]["offre"]["recompenses"]["rang_guilde"] == "B"


def test_rang_vise_hors_echelle_ignore():
	assert offres.rang_vise({"recompenses": {"rang_guilde": "Z"}}, BUREAU) is None
	assert offres.rang_vise({"recompenses": {"rang_guilde": {"rang": "B"}}}, BUREAU) is None


def test_l_escorte_porte_sa_recompense_de_rang():
	spec = {"id": "quete:e", "destination": "lieu:aix", "proteges": [{"prenom": "A", "race": "humain"}],
			"recompenses": {"xp": 5, "rang_guilde": "B"}}
	snap = escorte.generer_escorte_authoree(spec, BUREAU, lambda *a, **k: [], lambda i: None)
	assert snap["recompenses"]["rang_guilde"] == {"cite": CITE, "rang": "B"}
	spec["recompenses"].pop("rang_guilde")
	snap = escorte.generer_escorte_authoree(spec, BUREAU, lambda *a, **k: [], lambda i: None)
	assert "rang_guilde" not in snap["recompenses"]


def test_la_course_retenue_est_lue_par_transport():
	tr = [{"offre": {"id": "quete:tb", "destination": "lieu:aix", "cargaison": [{"item": "item:pli"}],
					 "recompenses": {"rang_guilde": "B"}}, "noeuds": {"accepte": "ok"}}]
	doc = _maitresse(transport_offres=tr)
	c = _perso()
	offres.poser_offres_tirees(c, BUREAU, [doc], _premier)
	assert transport.offre_spec(offres.vue_pnj(doc, c, BUREAU))["id"] == "quete:tb"
	assert transport.offre_spec(doc) is None, "le doc brut n'a pas d'offre seule"


# ── Condition `offre` ────────────────────────────────────────────────────────

def test_condition_offre():
	doc = _maitresse(_entree("quete:b1", "B"), _entree("quete:b2", "B"))
	c = _perso()
	offres.poser_offres_tirees(c, BUREAU, [doc], _premier)
	ctx = pnj.contexte_dialogue(c, offres.vue_pnj(doc, c, BUREAU), lambda _l: 0)
	assert pnj.condition_ok({"offre": "quete:b1"}, ctx)
	assert not pnj.condition_ok({"offre": "quete:b2"}, ctx)
	assert not pnj.condition_ok({"offre": 3}, ctx), "fail-closed"
	assert "offre" in pnj.CONDITIONS_STRUCTUREES
	assert set(pnj.CONDITIONS_STRUCTUREES) == set(lint_dialogues.CONDITIONS_STRUCTUREES)


# ── Linter ───────────────────────────────────────────────────────────────────

def _doc_lint(condition_offre):
	return {
		"_id": "pnj:maitresse",
		"services": {"apport": {"offres": [
			{"offre": {"id": "quete:b1", "item": "item:x", "quantite": 1}, "noeuds": {"accepte": "acc_b1"}},
			{"offre": {"id": "quete:b2", "item": "item:x", "quantite": 0}, "noeuds": {"accepte": "acc_b2"}},
		]}},
		"dialogue": {"noeud_depart": "accueil", "noeuds": {
			"accueil": {"texte": "…", "choix": [
				{"id": "a", "label": "…", "condition": {"apport_offert": True, "offre": condition_offre},
				 "action": {"service": "apport", "op": "accepter"}},
				{"id": "fin", "label": "…", "next": "fin"}]},
			"acc_b1": {"texte": "…", "choix": [{"id": "ok", "label": "…", "next": "fin"}]},
			"acc_b2": {"texte": "…", "choix": [{"id": "ok", "label": "…", "next": "fin"}]},
		}},
	}


def test_le_linter_deplie_les_offres():
	msgs = [t["message"] for t in lint_dialogues.analyser_doc(_doc_lint("quete:b1"))]
	assert any("offre` illisible" in m for m in msgs), "l'entrée b2 (quantité 0) est contrôlée"
	assert not any("inatteignable" in m for m in msgs), "les nœuds des entrées sont des entrées"
	assert not any("`offre` " in m and "aucune offre" in m for m in msgs)


def test_le_linter_refuse_une_condition_offre_inconnue():
	msgs = [t["message"] for t in lint_dialogues.analyser_doc(_doc_lint("quete:nulle_part"))]
	assert any("ne désigne aucune offre" in m for m in msgs)
