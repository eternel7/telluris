# tests/test_enigmes.py — système d'énigmes (utils/enigmes.py ; docs/conception_enigmes.md).
# Pur : aucune base. Les docs d'énigme sont des constantes du test (convention 20).

import copy

import pytest

from utils import acces, enigmes, lint_dialogues, pnj

LIEU = "lieu:atelier_test"
NOW = 1_800_000_000


def _perso(**kw):
	return dict({"_id": "character:t", "lieu": LIEU}, **kw)


def _doc(famille, elements, solution, **kw):
	d = {"_id": f"enigme:{famille}", "type": "enigme", "nom": famille, "famille": famille,
		 "lieux": [LIEU], "elements": elements, "solution": solution,
		 "reussite": "C'est ouvert.", "echec": "Rien ne bouge."}
	d.update(kw)
	return d


DEDUCTION = _doc("deduction",
	{"indices": [{"id": "porte", "label": "La porte", "fait": "Aucune effraction."},
				 {"id": "sol", "label": "Le sol", "fait": "Les traces s'interrompent."},
				 {"id": "tissu", "label": "Le tissu", "fait": "Une matière inconnue."}],
	 "conclusions": [{"id": "vol", "label": "Un voleur est entré."},
					 {"id": "ailleurs", "label": "La boîte est partie sans passer par la porte."}]},
	{"conclusion": "ailleurs", "indices": ["porte", "sol", "tissu"], "seuil": 2})

CRANS = _doc("crans",
	{"pieces": [{"id": "a", "label": "Tiroir A", "crans": 4, "depart": 0},
				{"id": "b", "label": "Tiroir B", "crans": 4, "depart": 2}]},
	{"positions": {"a": 3, "b": 1}})

GRAPHE = _doc("graphe",
	{"salles": [{"id": "entree", "label": "l'entrée"}, {"id": "s1", "label": "la salle humide"},
				{"id": "alcove", "label": "l'alcôve"}],
	 "arches": [{"id": "ligne", "label": "Ligne"}, {"id": "spirale", "label": "Spirale"}],
	 "depart": "entree", "cible": "alcove"},
	{"transitions": {"entree": {"spirale": "s1"}, "s1": {"ligne": "alcove"}}})

ASSOCIATION = _doc("association",
	{"gauche": [{"id": "porte", "texte": "La porte est ouverte…"}, {"id": "chemin", "texte": "Le chemin est visible…"},
				{"id": "objet", "texte": "L'objet est présent…"}],
	 "droite": [{"id": "dest", "texte": "la destination est inaccessible"},
				{"id": "proj", "texte": "une projection"}, {"id": "espace", "texte": "un espace inaccessible"}]},
	{"paires": {"porte": "dest", "chemin": "proj", "objet": "espace"}, "seuil": 2})

PLACEMENT = _doc("placement",
	{"symboles": [{"id": "soleil"}, {"id": "etoile"}, {"id": "lune"}, {"id": "vide"}],
	 "emplacements": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}, {"id": "p4"}]},
	{"placement": {"p1": "soleil", "p2": "etoile", "p3": "lune", "p4": "vide"}})

RESEAU = _doc("reseau",
	{"noeuds": [{"id": "cour"}, {"id": "galerie"}, {"id": "escalier"}, {"id": "inconnue"}],
	 "liaisons": [{"id": "l1", "a": "cour", "b": "galerie"}, {"id": "l2", "a": "galerie", "b": "escalier"}]},
	{"liaisons_cachees": [{"id": "l3", "a": "escalier", "b": "inconnue"}],
	 "actives": ["l1", "l2", "l3"], "ancrees": ["l3"]})

TOUTES = [DEDUCTION, CRANS, GRAPHE, ASSOCIATION, PLACEMENT, RESEAU]


def _agir(doc, perso, action, **body):
	return enigmes.agir(doc, perso, action, body, NOW)


# --- Validation : aucune énigme du test n'est insoluble -----------------------------------

@pytest.mark.parametrize("doc", TOUTES, ids=lambda d: d["famille"])
def test_les_enigmes_de_reference_sont_valides(doc):
	assert enigmes.valider_enigme(doc) == []


def test_chaque_famille_a_son_resolveur_et_une_enigme_de_reference():
	assert set(enigmes._RESOLVEURS) == set(enigmes.FAMILLES)
	assert {d["famille"] for d in TOUTES} == set(enigmes.FAMILLES)


def test_validation_signale_une_enigme_insoluble():
	d = copy.deepcopy(GRAPHE)
	d["solution"]["transitions"] = {"entree": {"spirale": "s1"}}
	assert any("atteignable" in f for f in enigmes.valider_enigme(d))
	d = copy.deepcopy(DEDUCTION)
	d["solution"]["seuil"] = 4
	assert any("insoluble" in f for f in enigmes.valider_enigme(d))
	d = copy.deepcopy(CRANS)
	d["solution"]["positions"]["a"] = 9
	assert enigmes.valider_enigme(d)
	d = copy.deepcopy(RESEAU)
	d["solution"]["ancrees"] = ["l9"]
	assert enigmes.valider_enigme(d)


def test_validation_exige_des_lieux_et_des_zones_qui_designent_un_element():
	d = copy.deepcopy(CRANS)
	d.pop("lieux")
	d["zones"] = [{"cle": "fantome", "x": 0, "y": 0, "w": 1, "h": 1}]
	fautes = enigmes.valider_enigme(d)
	assert any("lieux" in f for f in fautes) and any("fantome" in f for f in fautes)


def test_cycles_de_prerequis_detectes():
	a = {"_id": "enigme:a", "prerequis": ["enigme:b"]}
	b = {"_id": "enigme:b", "prerequis": ["enigme:a"]}
	c = {"_id": "enigme:c", "prerequis": ["enigme:a"]}
	assert enigmes.cycles_prerequis([a, b, c])
	assert enigmes.cycles_prerequis([{"_id": "enigme:x", "prerequis": ["enigme:absente"]}])
	b["prerequis"] = []
	assert enigmes.cycles_prerequis([a, b, c]) == []


# --- Ouverture ---------------------------------------------------------------------------

def test_ouverture_lieu_prerequis_conditions():
	assert enigmes.ouvrable(CRANS, _perso())[0]
	assert not enigmes.ouvrable(CRANS, _perso(lieu="lieu:ailleurs"))[0]
	sans_lieux = dict(CRANS, lieux=None)
	assert not enigmes.ouvrable(sans_lieux, _perso())[0]
	avec_pre = dict(CRANS, prerequis=["enigme:graphe"])
	assert not enigmes.ouvrable(avec_pre, _perso())[0]
	assert enigmes.ouvrable(avec_pre, _perso(enigmes={"enigme:graphe": {"resolue": True}}))[0]
	gardee = dict(CRANS, conditions=[{"quete_active": {"types": ["escorte"]}}])
	assert not enigmes.ouvrable(gardee, _perso())[0]
	assert enigmes.ouvrable(gardee, _perso(), lambda c: True)[0]


# --- La solution ne part jamais au client ------------------------------------------------

@pytest.mark.parametrize("doc", TOUTES, ids=lambda d: d["famille"])
def test_vue_client_sans_solution(doc):
	d = dict(doc, conditions=[{"quete_active": {}}],
			 commentaires=[{"quand": "ouverture", "qui": {"protege": "Aélis"}, "texte": "secret"}])
	vue = enigmes.vue_client(d, _perso())
	texte = repr(vue)
	assert "solution" not in vue and "conditions" not in vue and "commentaires" not in vue
	assert "secret" not in texte
	assert "reussite" not in vue   # pas avant la résolution


def test_vue_deduction_ne_montre_le_fait_qu_au_journal():
	perso = _perso()
	assert "Aucune effraction" not in repr(enigmes.vue_client(DEDUCTION, perso))
	_agir(DEDUCTION, perso, "examiner", cle="porte")
	assert enigmes.vue_client(DEDUCTION, perso)["journal"] == ["Aucune effraction."]


def test_vue_reseau_ne_montre_que_les_liaisons_revelees():
	perso = _perso()
	assert [l["id"] for l in enigmes.vue_client(RESEAU, perso)["elements"]["liaisons"]] == ["l1", "l2"]
	_agir(RESEAU, perso, "reveler", cle="inconnue")
	ids = [l["id"] for l in enigmes.vue_client(RESEAU, perso)["elements"]["liaisons"]]
	assert ids == ["l1", "l2", "l3"]


# --- Familles : échec sans perte, réussite définitive -------------------------------------

def test_deduction():
	perso = _perso()
	r = _agir(DEDUCTION, perso, "conclure", cle="vol")
	assert not r["reussi"] and r["texte"] == "Rien ne bouge." and "echec" in r["evenements"]
	_agir(DEDUCTION, perso, "examiner", cle="porte")
	r = _agir(DEDUCTION, perso, "conclure", cle="ailleurs")
	assert not r["reussi"] and "prouve" in r["texte"]   # bonne idée, pas encore prouvée
	_agir(DEDUCTION, perso, "examiner", cle="sol")
	assert _agir(DEDUCTION, perso, "conclure", cle="ailleurs")["resolue"]
	assert enigmes.lire_etat(perso, DEDUCTION["_id"])["essais"] == 3


def test_crans_garde_la_position_et_borne_les_crans():
	perso = _perso()
	assert not _agir(CRANS, perso, "essayer", positions={"a": 1, "b": 1})["reussi"]
	assert enigmes.vue_client(CRANS, perso)["etat"]["positions"] == {"a": 1, "b": 1}
	with pytest.raises(enigmes.EssaiInvalide):
		_agir(CRANS, perso, "essayer", positions={"a": 4, "b": 1})
	with pytest.raises(enigmes.EssaiInvalide):
		_agir(CRANS, perso, "essayer", positions={"a": 1})
	assert _agir(CRANS, perso, "essayer", positions={"a": 3, "b": 1})["resolue"]


def test_crans_depart_lu_dans_la_donnee():
	assert enigmes.vue_client(CRANS, _perso())["etat"]["positions"] == {"a": 0, "b": 2}


def test_graphe_ordre_de_passage_et_journal():
	perso = _perso()
	r = _agir(GRAPHE, perso, "passer", cle="ligne")       # mauvaise arche : retour à l'entrée
	assert not r["reussi"] and "echec" in r["evenements"]
	_agir(GRAPHE, perso, "passer", cle="spirale")
	assert enigmes.lire_etat(perso, GRAPHE["_id"])["etat"]["position"] == "s1"
	r = _agir(GRAPHE, perso, "passer", cle="ligne")
	assert r["resolue"] and "salle:alcove" in r["evenements"]
	journal = enigmes.lire_etat(perso, GRAPHE["_id"])["journal"]
	assert "Depuis l'entrée, l'arche Spirale mène à la salle humide." in journal
	assert "Depuis l'entrée, l'arche Ligne mène à l'entrée." in journal


def test_graphe_arche_inconnue_refusee():
	with pytest.raises(enigmes.EssaiInvalide):
		_agir(GRAPHE, _perso(), "passer", cle="croix")


def test_association_paires_gardees_et_seuil():
	perso = _perso()
	r = _agir(ASSOCIATION, perso, "associer", gauche="porte", droite="proj")
	assert not r["reussi"] and r["texte"]
	r = _agir(ASSOCIATION, perso, "associer", gauche="porte", droite="dest")
	assert not r["reussi"] and r["texte"] is None and "echec" not in r["evenements"]   # étape juste
	assert _agir(ASSOCIATION, perso, "associer", gauche="chemin", droite="proj")["resolue"]   # seuil 2


def test_placement():
	perso = _perso()
	assert not _agir(PLACEMENT, perso, "essayer", placement={"p1": "lune"})["reussi"]
	assert enigmes.vue_client(PLACEMENT, perso)["etat"]["placement"] == {"p1": "lune"}
	with pytest.raises(enigmes.EssaiInvalide):
		_agir(PLACEMENT, perso, "essayer", placement={"p9": "lune"})
	assert _agir(PLACEMENT, perso, "essayer", placement=dict(PLACEMENT["solution"]["placement"]))["resolue"]


def test_reseau_miroir_cle_pierre():
	perso = _perso()
	with pytest.raises(enigmes.EssaiInvalide):   # liaison cachée pas encore révélée
		_agir(RESEAU, perso, "essayer", actives=["l1", "l2", "l3"], ancrees=["l3"])
	_agir(RESEAU, perso, "reveler", cle="escalier")
	with pytest.raises(enigmes.EssaiInvalide):   # pierre hors d'une liaison ouverte
		_agir(RESEAU, perso, "essayer", actives=["l1"], ancrees=["l2"])
	assert not _agir(RESEAU, perso, "essayer", actives=["l1", "l2", "l3"], ancrees=[])["reussi"]
	assert _agir(RESEAU, perso, "essayer", actives=["l1", "l2", "l3"], ancrees=["l3"])["resolue"]


def test_resolue_pour_toujours_et_plus_rien_ne_bouge():
	perso = _perso()
	_agir(CRANS, perso, "essayer", positions={"a": 3, "b": 1})
	avant = copy.deepcopy(perso["enigmes"])
	r = _agir(CRANS, perso, "essayer", positions={"a": 0, "b": 0})
	assert r["resolue"] and perso["enigmes"] == avant
	assert perso["enigmes"][CRANS["_id"]]["resolue_at"] == NOW


def test_action_inconnue_refusee():
	with pytest.raises(enigmes.EssaiInvalide):
		_agir(CRANS, _perso(), "forcer")


def test_personnage_sans_champ_enigmes_tourne():
	# Convention 4 : champ absent ⇒ rien de commencé, aucune migration.
	assert enigmes.resolues({}) == set()
	assert enigmes.vue_client(GRAPHE, _perso())["etat"]["position"] == "entree"


# --- Commentaires : escortés par prénom, compagnons par vocation ---------------------------

def test_commentaires_selon_les_presents():
	d = dict(CRANS, commentaires=[
		{"quand": "ouverture", "qui": {"protege": "Aélis"}, "texte": "Ce ne sont pas des décors."},
		{"quand": "ouverture", "qui": {"vocation": "forestier"}, "texte": "{nom} sent le bois neuf."},
		{"quand": "echec", "qui": {"protege": "Aélis"}, "texte": "Pas ainsi."}])
	voix = [{"prenom": "Aélis", "protege": True}, {"prenom": "Brun", "vocation": "forestier"}]
	assert enigmes.commentaires(d, ["ouverture"], voix) == [
		{"qui": "Aélis", "texte": "Ce ne sont pas des décors."},
		{"qui": "Brun", "texte": "Brun sent le bois neuf."}]
	assert enigmes.commentaires(d, ["ouverture"], []) == []
	# Un compagnon qui porte le même prénom n'est pas l'escortée.
	assert enigmes.commentaires(d, ["echec"], [{"prenom": "Aélis", "vocation": "guerrier"}]) == []


# --- Condition `enigme_resolue` : dialogue, accès / présence, linter ------------------------

def test_condition_de_dialogue_enigme_resolue():
	perso = _perso(enigmes={"enigme:crans": {"resolue": True}})
	ctx = pnj.contexte_dialogue(perso, {}, lambda _l: 0)
	assert pnj.condition_ok({"enigme_resolue": {"id": "enigme:crans"}}, ctx)
	assert not pnj.condition_ok({"enigme_resolue": {"id": "enigme:crans", "attendu": False}}, ctx)
	assert pnj.condition_ok({"enigme_resolue": {"id": "enigme:graphe", "attendu": False}}, ctx)
	assert not pnj.condition_ok({"enigme_resolue": "enigme:crans"}, ctx)   # fail-closed
	assert "enigme_resolue" in pnj.CONDITIONS_STRUCTUREES
	assert lint_dialogues.CONDITIONS_STRUCTUREES == set(pnj.CONDITIONS_STRUCTUREES)


def test_clause_d_acces_enigme_resolue():
	perso = _perso(enigmes={"enigme:crans": {"resolue": True}})
	assert "enigme_resolue" in acces.CONDITIONS_CONNUES
	assert acces.clauses_remplies(perso, [{"enigme_resolue": {"id": "enigme:crans"}}], lambda _i: None)
	assert not acces.clauses_remplies({}, [{"enigme_resolue": {"id": "enigme:crans"}}], lambda _i: None)
	assert acces.clauses_remplies({}, [{"enigme_resolue": {"id": "enigme:crans", "attendu": False}}], lambda _i: None)


def _pnj_avec_choix(choix):
	return {"_id": "pnj:test", "type": "pnj", "nom": "Test", "dialogue": {"noeud_depart": "a", "noeuds": {
		"a": {"texte": "Bonjour.", "choix": [dict({"id": "c", "label": "Voir", "next": "fin"}, **choix)]}}}}


def test_linter_controle_le_hook_et_la_condition():
	def erreurs(choix):
		return [m for m in lint_dialogues.analyser_doc(_pnj_avec_choix(choix)) if "enigme" in str(m)]
	assert erreurs({"enigme": "enigme:crans", "condition": {"enigme_resolue": {"id": "enigme:graphe"}}}) == []
	assert erreurs({"enigme": "crans"})
	assert erreurs({"condition": {"enigme_resolue": {"id": "quete:x"}}})
	assert erreurs({"condition": {"enigme_resolue": {"id": "enigme:x", "attendus": False}}})


# --- Boutons d'énigme d'un lieu (/play) -----------------------------------------------------

def test_enigmes_du_lieu_seulement_a_bouton_et_ouvrables():
	a_bouton = dict(CRANS, bouton=True)
	ailleurs = dict(GRAPHE, bouton=True, lieux=["lieu:ailleurs"])
	sans_bouton = PLACEMENT
	verrouillee = dict(RESEAU, bouton=True, prerequis=["enigme:crans"])
	perso = _perso()
	assert enigmes.enigmes_du_lieu([verrouillee, sans_bouton, ailleurs, a_bouton], perso) == [
		{"id": "enigme:crans", "nom": "crans", "resolue": False}]
	_agir(CRANS, perso, "essayer", positions={"a": 3, "b": 1})
	ids = [e["id"] for e in enigmes.enigmes_du_lieu([verrouillee, a_bouton], perso)]
	assert ids == ["enigme:crans", "enigme:reseau"]   # ordre stable des ids, prérequis levé
	assert enigmes.enigmes_du_lieu([a_bouton], perso)[0]["resolue"]


# ── Notes de quête dans le carnet 📖 du principal ────────────────────────────────

def test_les_notes_des_enigmes_remontent_au_carnet_et_y_restent():
	"""Le carnet garde les indices de TOUTES les énigmes commencées, résolues comprises : le
	plan d'une énigme vu dans une autre reste lisible pendant qu'on joue la suivante."""
	from utils import journal
	perso = _perso()
	docs = {DEDUCTION["_id"]: DEDUCTION, GRAPHE["_id"]: GRAPHE}
	enigmes.agir(DEDUCTION, perso, "examiner", {"cle": "porte"}, NOW)
	enigmes.agir(DEDUCTION, perso, "examiner", {"cle": "sol"}, NOW)
	enigmes.agir(DEDUCTION, perso, "conclure", {"cle": "ailleurs"}, NOW)       # résolue
	enigmes.agir(GRAPHE, perso, "passer", {"cle": "spirale"}, NOW + 5)
	notes = journal.journal_payload(perso, docs.get)["notes"]
	assert [n["id"] for n in notes] == [GRAPHE["_id"], DEDUCTION["_id"]]     # la plus récente d'abord
	ded = notes[1]
	assert ded["resolue"] and ded["nom"] == DEDUCTION["nom"]
	assert ded["faits"] == ["Aucune effraction.", "Les traces s'interrompent."]
	assert notes[0]["faits"] == ["Depuis l'entrée, l'arche Spirale mène à la salle humide."]
	assert notes[0]["note_at"] == NOW + 5


def test_un_essai_sans_note_ne_change_pas_l_ordre_du_carnet():
	perso = _perso()
	enigmes.agir(DEDUCTION, perso, "examiner", {"cle": "porte"}, NOW)
	enigmes.agir(DEDUCTION, perso, "conclure", {"cle": "vol"}, NOW + 9)        # essai faux, rien noté
	assert enigmes.lire_etat(perso, DEDUCTION["_id"])["note_at"] == NOW


def test_le_carnet_ignore_les_enigmes_sans_note_et_les_etats_illisibles():
	perso = _perso(enigmes={CRANS["_id"]: {"resolue": False, "journal": []}, "enigme:x": "bruit"})
	assert enigmes.notes_du_carnet(perso, {}.get) == []
	assert enigmes.notes_du_carnet(_perso(), {}.get) == []
	# Doc disparu : l'id sert de nom, les notes restent.
	perso = _perso(enigmes={"enigme:disparue": {"journal": ["Un fait."]}})
	assert enigmes.notes_du_carnet(perso, {}.get)[0]["nom"] == "enigme:disparue"
