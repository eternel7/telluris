"""🔎 Renseignement (utils/renseignement.py) — logique pure, sans DB. Compétence telluris-renseignement."""

import pytest

from models import character_stats
from utils import journal, renseignement as rens, scriptorium


class De:
	"""Hasard contrôlé : `randint` dépile `jets` (puis rend le minimum), `random` rend `r`."""

	def __init__(self, jets=(), r=0.0, choix=0):
		self.jets, self.r, self.choix = list(jets), r, choix

	def randint(self, a, b):
		return self.jets.pop(0) if self.jets else a

	def random(self):
		return self.r

	def choice(self, seq):
		return list(seq)[self.choix]

	def choices(self, seq, weights=None, k=1):
		return [list(seq)[self.choix]]


CARACS = {"V": 5, "F": 20, "R": 10, "Ag": 10, "Vol": 10, "Int": 30, "Cha": 10, "Ch": 10}


def perso(voc="lettre", **caracs):
	return {"_id": f"character:{voc}", "voc": voc, "prenom": voc.title(),
			"caracteristiques_current": dict(CARACS, **caracs)}


def methode(**kw):
	base = {"id": "m", "vocations": ["lettre"], "lieu": {"predicats": ["taverne"]}, "test": ["int"], "cout": 10}
	base.update(kw)
	return rens.normaliser_methode(base)


INDEX = {d["_id"]: d for d in [
	{"_id": "lieu:france", "label": "France", "categorie": "pays",
	 "rencontres": [{"espece": "espece:loup", "zones": ["zone:foret"]},
					{"espece": "espece:ours", "zones": ["zone:foret", "zone:montagne"]}],
	 "ressources": [{"ressource": "item:Herbe", "zones": ["zone:foret"]}]},
	{"_id": "lieu:cite", "label": "Lutèce", "categorie": "ville", "lieu_parent": "lieu:france",
	 "rencontres": [{"espece": "espece:rat"}]},
	{"_id": "lieu:auberge", "label": "Au Lion d'or", "categorie": "auberge", "lieu_parent": "lieu:cite"},
	{"_id": "lieu:armurier", "label": "L'Enclume", "categorie": "armurerie", "lieu_parent": "lieu:cite",
	 "stock_vente": [{"item_id": "item:Herbe", "qty": 2}, {"item_id": "item:Epee", "qty": 0}]},
	{"_id": "lieu:clairiere", "label": "Clairière", "categorie": "chemin", "tags": ["clairiere"],
	 "lieu_parent": "lieu:cite"},
	{"_id": "lieu:loin", "label": "Loin", "categorie": "chemin"},
]}
DONJONS = [{"_id": "donjon:crypte", "nom": "La crypte", "portail": "lieu:clairiere",
			"battle_maps": [{"lieu": "lieu:salle", "especes": ["espece:loup", "espece:goule"]}]}]
DISTANCES = {"lieu:auberge": 0, "lieu:cite": 1, "lieu:armurier": 2, "lieu:clairiere": 2, "lieu:france": 3}


# ── Règles ───────────────────────────────────────────────────────────────────────

def test_une_caracteristique_inconnue_refuse_la_methode():
	"""« Sag » n'existe pas : la méthode est refusée, jamais lue comme un test à 0."""
	with pytest.raises(ValueError, match="sag"):
		rens.normaliser_methode({"id": "x", "test": ["sag", "ag"]})


def test_methodes_de_ecarte_et_nomme_les_methodes_invalides():
	valides, erreurs = rens.methodes_de({"methodes": [
		{"id": "ok", "test": ["INT"]}, {"id": "ko", "test": ["dex"]}, {"id": "ko2", "sources": ["ciel"]}]})
	assert [m["id"] for m in valides] == ["ok"]
	assert valides[0]["test"] == ["int"]
	assert len(erreurs) == 2 and "dex" in erreurs[0]


def test_toutes_les_cles_admises_sont_celles_du_personnage():
	assert set(rens.CLES_CARACS.values()) == set(CARACS)


# ── Lieux ────────────────────────────────────────────────────────────────────────

def test_predicat_scriptorium_identique_au_vrai():
	for doc in ({"categorie": "scriptorium"}, {"tags": ["scriptorium"]}, {"categorie": "grand_scriptorium"},
				{"categorie": "auberge"}, {}):
		assert rens.predicat_ok("scriptorium", doc, {}, set()) == scriptorium.lieu_est_scriptorium(doc)


def test_salle_d_armes_par_categorie_ou_tag():
	assert rens.lieu_salle_d_armes({"categorie": "armurerie"})
	assert rens.lieu_salle_d_armes({"categorie": "grand_arsenal"})
	assert rens.lieu_salle_d_armes({"categorie": "chemin", "tags": ["salle_d_armes"]})
	assert not rens.lieu_salle_d_armes({"categorie": "boulangerie"})


def test_zone_sauvage_quatre_definitions_en_ou():
	nature = {"clairiere"}
	assert rens.est_sauvage(INDEX["lieu:france"], INDEX, nature)          # pays
	assert rens.est_sauvage(INDEX["lieu:clairiere"], INDEX, nature)       # tag nature
	assert rens.est_sauvage(INDEX["lieu:cite"], INDEX, set())             # rencontres
	assert rens.est_sauvage(INDEX["lieu:loin"], INDEX, set())             # hors cité
	assert not rens.est_sauvage(INDEX["lieu:auberge"], INDEX, nature)     # auberge en cité


def test_lieu_ok_combine_predicats_categories_et_tags():
	m = methode(lieu={"predicats": ["taverne"], "categories": ["boucherie"], "tags": ["marche_noir"]})
	assert rens.lieu_ok(m, INDEX["lieu:auberge"], INDEX, set())
	assert rens.lieu_ok(m, {"categorie": "boucherie"}, INDEX, set())
	assert rens.lieu_ok(m, {"categorie": "x", "tags": ["marche_noir"]}, INDEX, set())
	assert not rens.lieu_ok(m, INDEX["lieu:armurier"], INDEX, set())


# ── Acteur, seuil ────────────────────────────────────────────────────────────────

def test_seuil_moyenne_des_caracteristiques_bornee():
	m = methode(test=["int", "f"])
	assert rens.seuil(m, perso()) == 50 + 25
	assert rens.seuil(methode(test=["int"]), perso(Int=90)) == rens.SEUIL_MAX
	assert rens.seuil(methode(test=["int"]), perso(Int=0), relation_value=0) == 50 + rens.bonus_relation(0)
	assert rens.bonus_relation(0) < 0


def test_bonus_de_relation_part_de_la_relation_initiale():
	assert rens.bonus_relation(character_stats.RELATION_INITIALE) == 0
	assert rens.bonus_relation(100) == min(character_stats.RENS_RELATION_MAX, round(
		(100 - character_stats.RELATION_INITIALE) * character_stats.RENS_RELATION_POIDS))
	assert rens.bonus_relation(None) == 0


REGLES = {"tags_nature": ["clairiere"], "methodes": [
	{"id": "veterans", "vocations": ["guerrier"], "lieu": {"predicats": ["taverne"]}, "test": ["cha", "f"], "cout": 10},
	{"id": "faucon", "vocations": ["chaman"], "lieu": {"predicats": ["pays"]}, "test": ["int"],
	 "connait": "competence:il_du_faucon"},
	{"id": "informateur", "informateur": True, "lieu": {"predicats": ["taverne"]}, "test": ["cha"], "cout": 10},
]}


def test_l_acteur_est_le_membre_au_plus_haut_seuil_le_principal_gagne_les_ex_aequo():
	chef, comp = perso("guerrier"), perso("guerrier")
	comp["_id"] = "aventurier:x"
	apps = rens.applicables(INDEX["lieu:auberge"], INDEX, [chef, comp], REGLES, lambda m, c: True)
	assert [a["methode"]["id"] for a in apps] == ["veterans"]
	assert apps[0]["acteur"] is chef
	comp["caracteristiques_current"]["Cha"] = 40
	apps = rens.applicables(INDEX["lieu:auberge"], INDEX, [chef, comp], REGLES, lambda m, c: True)
	assert apps[0]["acteur"] is comp


def test_une_competence_exigee_garde_la_methode():
	chaman = perso("chaman")
	assert not rens.applicables(INDEX["lieu:france"], INDEX, [chaman], REGLES, lambda m, c: False)
	assert rens.applicables(INDEX["lieu:france"], INDEX, [chaman], REGLES,
							lambda m, c: c == "competence:il_du_faucon")


def test_informateur_seulement_sans_methode_de_vocation_et_s_il_est_la():
	lettre = perso("lettre")
	assert rens.applicables(INDEX["lieu:auberge"], INDEX, [lettre], REGLES, lambda m, c: True) == []
	apps = rens.applicables(INDEX["lieu:auberge"], INDEX, [lettre], REGLES, lambda m, c: True,
							informateur_present=True)
	assert [a["methode"]["id"] for a in apps] == ["informateur"]
	guerrier = perso("guerrier")
	apps = rens.applicables(INDEX["lieu:auberge"], INDEX, [guerrier], REGLES, lambda m, c: True,
							informateur_present=True)
	assert [a["methode"]["id"] for a in apps] == ["veterans"]


def test_informateur_tire_a_l_entree_et_stable_au_refresh():
	c = {}
	assert rens.poser_informateur(c, INDEX["lieu:auberge"], REGLES, INDEX, De(r=0.0))
	assert rens.informateur_ici(c, "lieu:auberge")
	assert not rens.poser_informateur(c, INDEX["lieu:auberge"], REGLES, INDEX, De(r=0.99))
	assert rens.informateur_ici(c, "lieu:auberge")
	assert rens.poser_informateur(c, INDEX["lieu:cite"], REGLES, INDEX)     # hors taverne : effacé
	assert "informateur_present" not in c
	rens.poser_informateur(c, INDEX["lieu:auberge"], REGLES, INDEX, De(r=0.99))
	assert not rens.informateur_ici(c, "lieu:auberge")


# ── Délai, coûts ─────────────────────────────────────────────────────────────────

def test_delai_par_lieu_et_methode():
	c = {}
	rens.marquer_delai(c, "lieu:auberge", "veterans", now=1000)
	duree = character_stats.RENS_DELAI_MINUTES * 60
	assert rens.disponible_dans(c, "lieu:auberge", "veterans", now=1000) == duree
	assert rens.disponible_dans(c, "lieu:auberge", "chanson", now=1000) == 0
	assert rens.disponible_dans(c, "lieu:cite", "veterans", now=1000) == 0
	assert rens.disponible_dans(c, "lieu:auberge", "veterans", now=1000 + duree) == 0
	rens.marquer_delai(c, "lieu:cite", "veterans", now=1000 + duree)     # l'entrée échue est purgée
	assert list(c["renseignements_at"]) == ["lieu:cite|veterans"]


def test_cout_par_niveau_et_informateur():
	m = methode(cout=10)
	assert [rens.cout_cuivre(m, n) for n in rens.NIVEAUX] == [
		round(10 * character_stats.RENS_COUT_MULT[n]) for n in rens.NIVEAUX]
	assert rens.cout_max(m) == rens.cout_cuivre(m, "exact")
	info = methode(cout=10, informateur=True, niveau_max="region")
	assert rens.cout_cuivre(info, "rumeur") == round(10 * character_stats.RENS_INFORMATEUR_MULT)
	assert rens.cout_max(info) == rens.cout_cuivre(info, "region")


def test_cout_pm_de_la_competence_exigee():
	m = methode(connait="competence:oeil")
	assert rens.cout_pm(m, lambda i: {"cout_pm": 12} if i == "competence:oeil" else None) == 12
	assert rens.cout_pm(methode(cout_pm=6), lambda i: None) == 6


# ── Cibles ───────────────────────────────────────────────────────────────────────

def test_filtres_de_cibles():
	mal = methode(cibles={"tags_espece": ["demon", "undead"], "ressources": False})
	assert rens.cible_ok(mal, "espece:goule", {"tags": ["undead"]})
	assert not rens.cible_ok(mal, "espece:loup", {"tags": ["animal"]})
	assert not rens.cible_ok(mal, "item:Herbe", {"sous_categorie": "herbe"})
	druide = methode(cibles={"tags_espece": ["animal"], "sous_categories": ["herbe"]})
	assert rens.cible_ok(druide, "item:Herbe", {"sous_categorie": "herbe"})
	assert not rens.cible_ok(druide, "item:Fer", {"categorie": "metal"})
	barbare = methode(cibles={"grade_min": "D", "ressources": False})
	assert rens.cible_ok(barbare, "espece:ours", {}, rang_fn=lambda e: "C")
	assert not rens.cible_ok(barbare, "espece:loup", {}, rang_fn=lambda e: "E")
	mage = methode(cibles={"ecole_vocation": True, "sous_categories": ["cristal"]})
	assert rens.cible_ok(mage, "item:Poudre", {"categorie": "composant"}, ecole_items={"item:Poudre"})
	assert rens.cible_ok(mage, "item:Cristal", {"sous_categorie": "cristal"})
	assert not rens.cible_ok(mage, "item:Bois", {"categorie": "composant"}, ecole_items={"item:Poudre"})


def test_recits_cedables_vus_seulement_et_pas_deja_cedes():
	c = {"bestiaire": {"espece:loup": {"lieux": [{"id": "lieu:france", "label": "France"},
												 {"id": "lieu:cite", "label": "Lutèce", "oui_dire": True}]}},
		 "recits_cedes": {"lieu:auberge": []}}
	assert [r["lieu"] for r in rens.recits_cedables(c, "lieu:auberge")] == ["lieu:france"]
	c["recits_cedes"]["lieu:auberge"].append("espece:loup|lieu:france")
	assert rens.recits_cedables(c, "lieu:auberge") == []
	assert len(rens.recits_cedables(c, "lieu:autre")) == 1


# ── Sources et portée ────────────────────────────────────────────────────────────

def test_pistes_d_une_espece_zones_lieux_donjons():
	pistes = rens.pistes_de("espece:loup", list(rens.SOURCES), INDEX, DONJONS, [])
	assert {(p["type"], p["porteur"], p.get("zone")) for p in pistes} == {
		("zone", "lieu:france", "zone:foret"), ("donjon", "lieu:clairiere", None)}
	rats = rens.pistes_de("espece:rat", ["lieu"], INDEX, DONJONS, [])
	assert [(p["type"], p["porteur"]) for p in rats] == [("lieu", "lieu:cite")]
	assert rens.pistes_de("espece:loup", ["lieu"], INDEX, DONJONS, []) == []


def test_pistes_d_une_ressource_recolte_et_boutique_en_stock():
	boutiques = [d for d in INDEX.values() if d.get("stock_vente")]
	pistes = rens.pistes_de("item:Herbe", list(rens.SOURCES), INDEX, DONJONS, boutiques)
	assert {(p["type"], p["porteur"]) for p in pistes} == {("zone", "lieu:france"), ("boutique", "lieu:armurier")}
	assert rens.pistes_de("item:Epee", ["boutique"], INDEX, DONJONS, boutiques) == []   # qty 0


def test_une_carcasse_sans_recolte_retombe_sur_l_espece():
	pistes = rens.pistes_de("item:rat", ["lieu"], INDEX, [], [])
	assert [(p["porteur"], p["cible"]) for p in pistes] == [("lieu:cite", "item:rat")]


def test_portee_les_plus_proches_joignables():
	pistes = rens.pistes_de("espece:loup", list(rens.SOURCES), INDEX, DONJONS, [])
	pistes += [{"type": "lieu", "porteur": "lieu:loin", "lieu": "lieu:loin", "cible": "espece:loup"}]
	tri = rens.a_portee(pistes, DISTANCES, portee_lieux=5)
	assert [p["porteur"] for p in tri] == ["lieu:clairiere", "lieu:france"]     # lieu:loin injoignable
	assert [p["porteur"] for p in rens.a_portee(pistes, DISTANCES, portee_lieux=1)] == ["lieu:clairiere"]
	assert rens.a_portee(pistes, DISTANCES, portee_lieux=5, portee_max=1) == []


# ── Jet et résolution ────────────────────────────────────────────────────────────

def test_trois_niveaux_du_jet():
	s = 60
	assert rens.niveau_du_jet(int(s * character_stats.RENS_EXACT_FACTEUR), s) == "exact"
	assert rens.niveau_du_jet(s, s) == "region"
	assert rens.niveau_du_jet(s + 1, s) == "rumeur"


PISTES = [{"type": "zone", "porteur": "lieu:france", "lieu": "lieu:france", "zone": "zone:foret",
		   "cible": "espece:loup", "distance": 3}]
FAUSSES = [{"type": "lieu", "porteur": "lieu:cite", "lieu": "lieu:cite", "cible": "espece:rat", "distance": 1}]


def test_resoudre_rumeur_vraie_ou_fausse():
	m = methode()
	vraie = rens.resoudre(m, 50, PISTES, rand=De([99, 100]), fausses=FAUSSES)
	assert (vraie["niveau"], vraie["fausse"], vraie["piste"]["cible"]) == ("rumeur", False, "espece:loup")
	fausse = rens.resoudre(m, 50, PISTES, rand=De([99, 1]), fausses=FAUSSES)
	assert (fausse["niveau"], fausse["fausse"], fausse["piste"]["cible"]) == ("rumeur", True, "espece:rat")


def test_resoudre_sans_piste_rien_ou_rumeur_fausse():
	m = methode()
	assert rens.resoudre(m, 50, [], rand=De([10]), fausses=FAUSSES)["niveau"] == "rien"
	r = rens.resoudre(m, 50, [], rand=De([99]), fausses=FAUSSES)
	assert r["fausse"] and r["niveau"] == "rumeur"
	assert rens.resoudre(m, 50, [], rand=De([99]))["niveau"] == "rien"


def test_niveau_fixe_sans_jet_et_plafond():
	assert rens.resoudre(methode(niveau_fixe="region"), 5, PISTES, rand=De([100]))["niveau"] == "region"
	r = rens.resoudre(methode(), 5, PISTES, rand=De([100]), sans_jet=True)
	assert r["niveau"] == "exact" and r["jet"] is None
	assert rens.resoudre(methode(niveau_max="region"), 90, PISTES, rand=De([1]))["niveau"] == "region"


def test_textes_par_niveau():
	args = ("des loups", "Bran", INDEX, {"zone:foret": "Forêt"}, {"zone:foret": ["foret"]}, {})
	exact = rens.texte_resultat({"niveau": "exact", "piste": PISTES[0]}, *args, "D")
	assert "zone « Forêt » de France" in exact["texte"] and "rang D" in exact["texte"]
	assert exact["lieu_id"] == "lieu:france"
	region = rens.texte_resultat({"niveau": "region", "piste": FAUSSES[0]}, *args, None)
	assert region["lieu_id"] == "lieu:cite" and "Lutèce" in region["texte"]
	rumeur = rens.texte_resultat({"niveau": "rumeur", "piste": PISTES[0]}, *args, None)
	assert rumeur["lieu_id"] is None and "forêts" in rumeur["texte"]


def test_tournures_elision_et_matieres():
	assert rens.de("Auxerre") == "d'Auxerre" and rens.de("France") == "de France"
	assert rens.de("Le Puy") == "du Puy" and rens.de("La capitale") == "de la capitale"
	assert rens.nom_cible("item:Herbe", {"nom": "Herbe"}) == "« Herbe »"
	args = (INDEX, {}, {"zone:foret": ["foret"]}, {})
	matiere = rens.texte_resultat({"niveau": "rumeur", "piste": PISTES[0]}, "« Herbe »", "Bran", *args, None,
								  cible_id="item:Herbe")
	assert "on trouverait « Herbe »" in matiere["texte"]


def test_region_premier_ancetre_notable():
	assert rens.region_de("lieu:auberge", INDEX)["_id"] == "lieu:cite"
	assert rens.region_de("lieu:france", INDEX)["_id"] == "lieu:france"
	assert rens.region_de("lieu:loin", INDEX)["_id"] == "lieu:loin"


def test_grade_d_une_ressource_pire_espece_de_la_zone():
	rangs = {"espece:loup": "E", "espece:ours": "C", "espece:goule": "B"}
	piste = {"type": "zone", "porteur": "lieu:france", "zone": "zone:foret", "cible": "item:Herbe"}
	assert rens.rang_piste(piste, INDEX, DONJONS, rangs.get) == "C"
	assert rens.rang_piste({"type": "donjon", "donjon": "donjon:crypte", "porteur": "lieu:clairiere",
							"cible": "item:x"}, INDEX, DONJONS, rangs.get) == "B"
	assert rens.rang_piste({"type": "boutique", "porteur": "lieu:armurier", "cible": "item:Herbe"},
						   INDEX, DONJONS, rangs.get) is None


# ── Ce que le joueur apprend ─────────────────────────────────────────────────────

def test_apprendre_espece_oui_dire_puis_vu_au_combat():
	c = {}
	piste = {"texte": "On trouve des loups en France.", "cible": "espece:loup", "niveau": "exact",
			 "lieu_id": "lieu:france", "lieu_label": "France"}
	assert rens.apprendre(c, piste, now=1)
	assert c["bestiaire"]["espece:loup"]["lieux"] == [{"id": "lieu:france", "label": "France", "oui_dire": True}]
	assert len(c["journal"]) == 1
	assert not rens.apprendre(c, piste, now=2)                       # relire n'écrit rien de plus
	vue = journal.bestiaire_payload(c, lambda i: {"nom": "Loup"})
	assert vue[0]["lieux"] == ["👂 France"] and vue[0]["combats"] == 0
	assert journal.lieux_a_nommer(c, [{"espece_id": "espece:loup"}], "lieu:france")
	journal.noter_rencontres(c, [{"espece_id": "espece:loup", "vivant": False}], "lieu:france", "France")
	assert c["bestiaire"]["espece:loup"]["lieux"] == [{"id": "lieu:france", "label": "France"}]


def test_rumeur_et_ressource_au_carnet_seulement():
	c = {}
	rens.apprendre(c, {"texte": "On aurait vu des loups.", "cible": "espece:loup", "niveau": "rumeur",
					   "lieu_id": None})
	rens.apprendre(c, {"texte": "De l'herbe en France.", "cible": "item:Herbe", "niveau": "exact",
					   "lieu_id": "lieu:france", "lieu_label": "France"})
	assert "bestiaire" not in c and len(c["journal"]) == 2


def test_oui_dire_borne_comme_les_lieux_vus():
	c = {}
	for i in range(character_stats.JOURNAL_BESTIAIRE_LIEUX_MAX + 2):
		journal.noter_oui_dire(c, "espece:loup", f"lieu:{i}", str(i))
	assert len(c["bestiaire"]["espece:loup"]["lieux"]) == character_stats.JOURNAL_BESTIAIRE_LIEUX_MAX


def test_note_porte_la_piste_et_vaut_selon_le_grade():
	piste = {"texte": "t", "cible": "espece:loup", "cible_nom": "des loups", "niveau": "exact",
			 "lieu_id": "lieu:france", "lieu_label": "France", "rang": "F"}
	note = rens.nouvelle_note("Bran", piste, now=5)
	assert rens.est_note(note) and note["item"] == rens.ITEM_NOTE_ID
	assert rens.titre_note("Note", note) == "Note : des loups"
	haute = rens.nouvelle_note("Bran", dict(piste, rang="B"))
	assert rens.prix_note(haute) > rens.prix_note(note) >= 1
	assert not rens.est_note({"item": rens.ITEM_NOTE_ID})


def test_lancer():
	assert rens.lancer("2D6+1", De([3, 4])) == 8
	assert rens.lancer("1D10", De([7])) == 7
	assert rens.lancer("3") == 3
	assert rens.lancer("n'importe quoi") == 0
