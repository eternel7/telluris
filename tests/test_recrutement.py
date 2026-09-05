"""Recrutement d'aventuriers (utils/recrutement.py) — logique pure, sans DB.

Génération procédurale des recrues (docs `aventurier:*` MIROIRS du character), rotation
du tableau (purge paresseuse / ré-offre des anciens compagnons), éligibilité du lieu,
embauche/congédiement, affinités et règlement de la part de butin. Les accès DB du module
sont des imports directs de `db.config` : on les monkeypatche sur le module — plus
`utils.characters` / `utils.combat` pour les helpers partagés (équipement, snapshot).
"""

import random

import pytest

from models import character_stats
from models.character_stats import compute_character_level
from utils import recrutement
from utils import characters as characters_util
from utils import combat as combat_util


# ── Monde de test ────────────────────────────────────────────────────────────────

GUILDE = {"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier",
		  "lieu_parent": "lieu:ville"}
VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "sous_categorie": "ville"}
RACES = {
	"_id": "rules:races", "type": "rules",
	"value": [{
		"id": "humain", "label": "Humain",
		"stats": {"V": 5, "F": 20, "R": 20, "Ag": 20, "Vol": 30, "Int": 30, "Cha": 30, "Ch": 20},
		"stats_max": {"V": 8, "F": 50, "R": 50, "Ag": 60, "Vol": 70, "Int": 70, "Cha": 80, "Ch": 60},
	}],
}
VOCATIONS = {
	"_id": "rules:vocations", "type": "rules",
	"value": [{"id": "guerrier", "label": "Guerrier", "blurb": "Pilier de toute troupe.",
			   "equipement_de_base": ["item:Epee_courte"]}],
}
EPEE = {"_id": "item:Epee_courte", "type": "item", "nom": "Épée courte", "categorie": "arme",
		"slots": ["main_droite"], "poids": 2, "portee": 1}
PORTRAITS = ["guerrier_m_humain01.jpg", "guerrier_f_humain01.jpg", "assassin_m_elfe01.jpg"]


@pytest.fixture
def monde(monkeypatch):
	"""Base en mémoire branchée sur les accès DB de recrutement + characters + combat."""
	docs = {d["_id"]: d for d in (GUILDE, VILLE, RACES, VOCATIONS, EPEE)}
	supprimes = []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def find_docs_fn(selector):
		return [d for d in docs.values() if d.get("type") == selector.get("type")]

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def delete_doc_fn(doc):
		docs.pop(doc["_id"], None)
		supprimes.append(doc)
		return None

	monkeypatch.setattr(recrutement, "get_doc", get_doc_fn)
	monkeypatch.setattr(recrutement, "find_docs", find_docs_fn)
	monkeypatch.setattr(recrutement, "save_doc", save_doc_fn)
	monkeypatch.setattr(recrutement, "delete_doc", delete_doc_fn)
	monkeypatch.setattr(recrutement, "now_epoch", lambda: 1000)
	# Helpers partagés (resolve_item_ref, recompute_equipment_bonus, _weapon_attacks…).
	monkeypatch.setattr(characters_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(combat_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_BOARD_DUREE_SECONDES", 7200)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_BOARD_DUREE_JITTER", 0.5)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_GROUPE_TAILLE_MAX", 2)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_PART_BUTIN_MIN", 10)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_PART_BUTIN_MAX", 30)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_CARTE_REQUISE", True)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_COUT_CUIVRE", 300)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_COUT_PAR_NIVEAU", 200)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_PART_FACTEUR", 0.5)
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_PART_MIN", 0)
	return {"docs": docs, "supprimes": supprimes}


def perso(**champs):
	base = {
		"_id": "character:u_1", "type": "character", "user_id": "user:u",
		"prenom": "Test", "nom": "Héros", "inventaire": [], "groupe": [],
		"affinites": {}, "compagnons_connus": {}, "quetes_actives": [],
		"or": 0, "argent": 0, "cuivre": 0,
	}
	base.update(champs)
	return base


def recrue(rid="aventurier:guilde_abc", statut="offert", **champs):
	base = {
		"_id": rid, "type": "aventurier", "statut": statut, "giver": "lieu:guilde",
		"prenom": "Aldric", "nom": "Ferrant", "sex": "M", "race": "humain",
		"voc": "guerrier", "image": "guerrier_m_humain01.jpg", "rang": "F",
		"exigences": {"part_butin_pct": 20, "clauses": []},
		"or": 0, "argent": 0, "cuivre": 0,
		"genere_at": 1000, "expire_at": 9000,
	}
	base.update(champs)
	return base


# ── Génération procédurale ───────────────────────────────────────────────────────

def test_generation_champs_miroirs(monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 2, portraits=PORTRAITS)
	assert av["type"] == "aventurier" and av["statut"] == "offert"
	assert av["_id"].startswith("aventurier:guilde_")
	assert av["giver"] == "lieu:guilde" and av["lieu_parent"] == "lieu:ville"
	for champ in ("prenom", "nom", "sex", "race", "voc", "image",
				  "caracteristiques_current", "currentPV", "currentPM",
				  "vocations_niveaux", "xp_total", "attribute_points", "inventaire",
				  "slots", "equipment_bonus", "sorts_connus", "competences_connues",
				  "competences_bonus", "effets_actifs", "combats_recompenses",
				  "rang", "specialite", "exigences", "genere_at", "expire_at"):
		assert champ in av, champ


def test_generation_stats_bornees(monde):
	race = RACES["value"][0]
	for _ in range(10):
		av = recrutement.generer_aventurier(GUILDE, VILLE, 3, portraits=PORTRAITS)
		for k, v in av["caracteristiques_current"].items():
			assert race["stats"][k] <= v <= race["stats_max"][k], k


def test_generation_equipement_dans_les_slots(monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 0, portraits=PORTRAITS)
	assert av["slots"]["main_droite"] == "item:Epee_courte"
	assert "item:Epee_courte" not in av["inventaire"]


def test_generation_pv_pm_au_max_derive(monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 0, portraits=PORTRAITS)
	c = av["caracteristiques_current"]
	assert av["currentPV"] == c["R"] * 3 + c["F"]
	assert av["currentPM"] == c["Vol"] * 2 + c["Int"] * 2


def test_generation_niveau_et_xp_coherents(monde):
	for _ in range(10):
		av = recrutement.generer_aventurier(GUILDE, VILLE, 3, portraits=PORTRAITS)
		niveau = av["vocations_niveaux"]["guerrier"]
		assert 0 <= niveau <= 3
		assert compute_character_level(av["xp_total"]) == niveau


def test_generation_au_plafond_de_la_CAPITALE(monde):
	"""Le plafond de la capitale est le plus haut du jeu : c'est LUI qui exerce le budget
	de points de niveau (`RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU` × niveau) contre les max
	raciaux. `_monter_niveaux` doit saturer proprement plutôt que dépasser — sinon monter
	le plafond d'un cran fabriquerait des recrues hors barème, sans le moindre symptôme."""
	race = RACES["value"][0]
	plafond = character_stats.RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE["capitale"]["niveau_max"]
	vus = set()
	# ⚠️ Graine posée puis RESTAURÉE : sans elle « le plafond est atteint » serait flaky ;
	# sans la restauration, tout ce qui tire au sort ensuite hériterait de ce flux.
	etat = random.getstate()
	random.seed(20260903)
	try:
		for _ in range(40):
			av = recrutement.generer_aventurier(GUILDE, VILLE, plafond, portraits=PORTRAITS)
			niveau = av["vocations_niveaux"]["guerrier"]
			assert 0 <= niveau <= plafond
			assert compute_character_level(av["xp_total"]) == niveau
			for k, v in av["caracteristiques_current"].items():
				assert race["stats"][k] <= v <= race["stats_max"][k], k
			# `rang = RANGS[min(niveau, len-1)]` : au plafond on doit encore lire un vrai cran.
			assert av["rang"] in recrutement.RANGS
			vus.add(niveau)
	finally:
		random.setstate(etat)
	assert plafond in vus, "le tirage n'atteint jamais son propre plafond"


def test_les_plafonds_de_lOFFRE_sont_ordonnes_et_dans_lechelle():
	"""Invariante de réglage : une capitale offre au moins autant qu'une ville, qui offre
	au moins autant que le défaut — et aucun plafond ne sort de l'échelle des rangs, que
	`generer_aventurier` indexe pour poser le `rang` de la recrue."""
	table = character_stats.RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE
	capitale, ville, defaut = table["capitale"], table["ville"], table["defaut"]
	assert capitale["niveau_max"] >= ville["niveau_max"] >= defaut["niveau_max"] >= 0
	assert capitale["nb"] >= ville["nb"] >= defaut["nb"] >= 1
	assert capitale["niveau_max"] < len(recrutement.RANGS)


def test_generation_portrait_coherent(monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 0, portraits=PORTRAITS)
	assert av["image"].startswith(f"guerrier_{av['sex'].lower()}_humain")


def test_generation_sans_rules_renvoie_none(monde):
	monde["docs"].pop("rules:races")
	assert recrutement.generer_aventurier(GUILDE, VILLE, 0, portraits=PORTRAITS) is None


def test_pivot_build_joueur_snapshot(monde):
	"""LE test pivot du plan : le doc généré est un character valide pour le combat."""
	av = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=PORTRAITS)
	snap = combat_util.build_joueur_snapshot(av, joueur_index=1)
	assert snap["id"] == "joueur_1"
	assert snap["character_id"] == av["_id"]
	assert snap["currentPV"] == av["currentPV"] and snap["pv_max"] > 0
	assert snap["actions_max"] >= 1 and snap["initiative"] > 0
	modes = {p["mode"] for p in snap["attaque_profils"]}
	assert "cac" in modes  # l'épée équipée (ou les poings) donne un profil de mêlée


def test_choisir_portrait_sexe_et_race_stricts():
	pool = ["assassin_f_elfe01.jpg", "assassin_m_nain01.jpg", "voleur_m_humain01.jpg",
			"voleur_m_nain01.jpg"]
	assert recrutement.choisir_portrait("assassin", "F", "elfe", pool) == "assassin_f_elfe01.jpg"
	# Repli de VOCATION seulement : pas de voleur nain M ? si → sinon même sexe + race.
	assert recrutement.choisir_portrait("barbare", "M", "nain", pool) in (
		"assassin_m_nain01.jpg", "voleur_m_nain01.jpg")
	# Aucun portrait de la race (ou du sexe) demandé ⇒ RIEN, jamais une autre race.
	assert recrutement.choisir_portrait("assassin", "F", "nain", pool) == ""
	assert recrutement.choisir_portrait("assassin", "M", "ogre", pool) == ""
	assert recrutement.choisir_portrait("assassin", "M", "elfe", pool) == ""
	assert recrutement.choisir_portrait("barbare", "M", "nain", []) == ""
	# Nom hors règle : ignoré, jamais tiré par défaut.
	assert recrutement.choisir_portrait("assassin", "F", "elfe", ["portrait.jpg"]) == ""


def test_generer_aventurier_portrait_de_sa_race(monde):
	pool = [f"{v}_{s}_{r}01.jpg"
			for v in ("guerrier", "voleur") for s in ("f", "m") for r in ("humain", "elfe")]
	for _ in range(20):
		av = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=pool)
		image = av["image"]
		if not image:
			continue
		voc, sexe, race = recrutement.decomposer_portrait(image)
		assert race == av["race"] and sexe == av["sex"].lower()


# ── Éligibilité du lieu ──────────────────────────────────────────────────────────

def test_lieu_recrute_tag_ou_guilde(monde):
	assert recrutement.lieu_recrute(GUILDE) is True
	assert recrutement.lieu_recrute({"categorie": "taverne", "tags": ["recrutement"]}) is True
	assert recrutement.lieu_recrute({"categorie": "taverne"}) is False


def test_offre_du_lieu_par_sous_categorie(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE", {
		"capitale": {"nb": 6, "niveau_max": 3},
		"ville": {"nb": 4, "niveau_max": 2},
		"defaut": {"nb": 2, "niveau_max": 1},
	})
	assert recrutement.offre_du_lieu(GUILDE, VILLE) == {"nb": 4, "niveau_max": 2}
	assert recrutement.offre_du_lieu(GUILDE, {"sous_categorie": "capitale"}) == {"nb": 6, "niveau_max": 3}
	assert recrutement.offre_du_lieu(GUILDE, {}) == {"nb": 2, "niveau_max": 1}
	# Restrictions du lieu : surcharge champ à champ.
	bride = dict(GUILDE, recrutement_restrictions={"nb": 1})
	assert recrutement.offre_du_lieu(bride, VILLE) == {"nb": 1, "niveau_max": 2}


def test_acces_autorise_exige_la_carte_de_la_cite(monde):
	c = perso(inventaire=[{"item": "item:carte_aventurier", "poids": 0.1, "lieu_parent": "lieu:ville"}])
	assert recrutement.acces_autorise(c, GUILDE)[0] is True
	autre = perso(inventaire=[{"item": "item:carte_aventurier", "poids": 0.1, "lieu_parent": "lieu:autre"}])
	assert recrutement.acces_autorise(autre, GUILDE)[0] is False
	assert recrutement.acces_autorise(perso(), GUILDE)[0] is False


def test_acces_libre_si_carte_non_requise(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "RECRUTEMENT_CARTE_REQUISE", False)
	assert recrutement.acces_autorise(perso(), GUILDE)[0] is True


# ── Rotation du tableau ──────────────────────────────────────────────────────────

def test_recrue_offerte_echue_est_perimee(monde):
	assert recrutement.recrue_perimee(recrue(expire_at=1000), 1000) is True
	assert recrutement.recrue_perimee(recrue(expire_at=1001), 1000) is False


def test_compagnon_embauche_ou_parti_ne_perime_pas(monde):
	assert recrutement.recrue_perimee(recrue(statut="embauche", expire_at=1), 9999) is False
	assert recrutement.recrue_perimee(recrue(statut="parti", expire_at=1), 9999) is False


def test_purge_supprime_les_jamais_embauchees(monde):
	av = recrue(expire_at=500)
	monde["docs"][av["_id"]] = av
	restantes = recrutement.purger_recrues_perimees([av], 1000)
	assert restantes == []
	assert av["_id"] not in monde["docs"]


def test_purge_conserve_un_ancien_compagnon(monde):
	"""Un ancien compagnon ré-offert qui expire repart (statut parti) : son doc porte la
	mémoire du lien, le détruire romprait la ré-offre future."""
	av = recrue(expire_at=500, embauche_par="character:u_1")
	monde["docs"][av["_id"]] = av
	restantes = recrutement.purger_recrues_perimees([av], 1000)
	assert restantes == []
	assert monde["docs"][av["_id"]]["statut"] == "parti"


# ── Retrait du tableau (péremption ET refus des clauses) ─────────────────────────

def test_retirer_du_tableau_supprime_une_recrue_neuve(monde):
	av = recrue()
	monde["docs"][av["_id"]] = av
	recrutement.retirer_du_tableau(av)
	assert av["_id"] not in monde["docs"]
	assert monde["supprimes"] == [av]


def test_retirer_du_tableau_conserve_un_ancien_compagnon(monde):
	"""Refuser les conditions d'un ancien compagnon ne détruit pas son doc : il repasse
	`parti` et pourra être ré-offert — la mémoire du lien survit au refus."""
	av = recrue(embauche_par="character:u_1", expire_at=9000)
	monde["docs"][av["_id"]] = av
	recrutement.retirer_du_tableau(av)
	assert monde["docs"][av["_id"]]["statut"] == "parti"
	assert "expire_at" not in monde["docs"][av["_id"]]
	assert monde["supprimes"] == []


def test_refus_ne_coute_aucune_affinite(monde):
	"""Éconduire quelqu'un n'a pas de coût social : le personnage n'est pas touché."""
	c = perso(affinites={"aventurier:guilde_abc": 70})
	av = recrue(embauche_par="character:u_1")
	monde["docs"][av["_id"]] = av
	recrutement.retirer_du_tableau(av)
	assert c["affinites"] == {"aventurier:guilde_abc": 70}


def test_peut_refuser_seulement_une_offerte(monde):
	assert recrutement.peut_refuser(recrue())[0] is True
	assert recrutement.peut_refuser(recrue(statut="embauche"))[0] is False
	assert recrutement.peut_refuser(recrue(statut="parti"))[0] is False
	assert recrutement.peut_refuser({})[0] is False


def test_remplir_tableau_complete_jusqu_au_nb(monde):
	tableau = recrutement.remplir_tableau_recrues(GUILDE, perso())
	assert len(tableau) == 4  # sous_categorie "ville" → nb 4
	assert all(av["statut"] == "offert" for av in tableau)
	# Idempotent : un second appel ne regénère rien.
	assert len(recrutement.remplir_tableau_recrues(GUILDE, perso())) == 4


def test_remplir_tableau_reoffre_les_anciens_apprecies(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "AFFINITE_SEUIL_REMISE", 60)
	ami = recrue("aventurier:guilde_ami", statut="parti", embauche_par="character:u_1")
	inconnu = recrue("aventurier:guilde_froid", statut="parti", embauche_par="character:u_1")
	monde["docs"][ami["_id"]] = ami
	monde["docs"][inconnu["_id"]] = inconnu
	c = perso(affinites={"aventurier:guilde_ami": 70, "aventurier:guilde_froid": 40})
	tableau = recrutement.remplir_tableau_recrues(GUILDE, c)
	ids = {av["_id"] for av in tableau}
	assert "aventurier:guilde_ami" in ids
	assert "aventurier:guilde_froid" not in ids
	assert monde["docs"]["aventurier:guilde_ami"]["statut"] == "offert"


def test_expire_at_recrue_dans_la_fenetre_jittee(monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 0, portraits=PORTRAITS)
	assert 1000 + 3600 <= av["expire_at"] <= 1000 + 10800  # [D×0.5, D×1.5]


# ── Embauche & congédiement ──────────────────────────────────────────────────────

def test_embauche_nominale(monde):
	c = perso()
	av = recrue()
	ok, _ = recrutement.embaucher(c, av)
	assert ok
	assert av["statut"] == "embauche" and av["embauche_par"] == "character:u_1"
	assert c["groupe"] == [av["_id"]]
	assert c["affinites"][av["_id"]] == character_stats.AFFINITE_INITIALE
	assert av["_id"] in c["compagnons_connus"]


def _embauche(monde, av_id="aventurier:a", **champs):
	"""Compagnon ACTIF déjà en base — le plafond compte désormais les DOCS (places
	réellement occupées), plus une liste d'ids qui pourrait contenir des références mortes."""
	av = recrue(av_id, statut="embauche", embauche_par="character:u_1", **champs)
	monde["docs"][av["_id"]] = av
	return av


def test_embauche_refusee_au_plafond(monde):
	a, b = _embauche(monde, "aventurier:a"), _embauche(monde, "aventurier:b")
	c = perso(groupe=[a["_id"], b["_id"]])
	ok, raison = recrutement.embaucher(c, recrue())
	assert not ok and "complet" in raison


def test_un_id_perime_ne_retient_plus_une_place(monde):
	"""Le plafond lit les docs : un compagnon disparu de la base (ou repassé `parti`) ne
	bloque plus une place, là où `len(groupe)` la retenait indéfiniment."""
	c = perso(groupe=["aventurier:disparu", "aventurier:aussi_disparu"])
	ok, _ = recrutement.embaucher(c, recrue())
	assert ok


def test_points_a_repartir_signale_un_compagnon(monde):
	"""Pastille du bouton 👥 : elle s'allume dès qu'UN compagnon actif a des points."""
	_embauche(monde, "aventurier:a")
	b = _embauche(monde, "aventurier:b")
	c = perso(groupe=["aventurier:a", "aventurier:b"])
	assert not recrutement.compagnons_a_repartir(c)
	b["attribute_points"] = 3
	assert recrutement.compagnons_a_repartir(c)


def test_points_a_repartir_ignore_un_ancien_compagnon(monde):
	"""Même filtre que le reste du groupe : un doc `parti` n'est plus des nôtres, ses points
	ne doivent pas allumer une pastille que rien ne permet d'éteindre."""
	av = _embauche(monde, "aventurier:a", attribute_points=5)
	c = perso(groupe=[av["_id"]])
	assert recrutement.compagnons_a_repartir(c)
	av["statut"] = "parti"
	assert not recrutement.compagnons_a_repartir(c)


def test_points_a_repartir_reutilise_les_docs_deja_charges(monde):
	"""`compagnons` = docs déjà en main : aucune relecture (mêmes précautions que partager_xp)."""
	av = recrue("aventurier:a", statut="embauche", embauche_par="character:u_1")
	av["attribute_points"] = 1
	c = perso(groupe=[av["_id"]])           # le doc n'est PAS en base : sans la liste, rien
	assert not recrutement.compagnons_a_repartir(c)
	assert recrutement.compagnons_a_repartir(c, compagnons=[av])


def test_embauche_refusee_si_plus_offerte(monde):
	ok, _ = recrutement.embaucher(perso(), recrue(statut="embauche"))
	assert not ok


def test_congedier_conserve_le_doc_et_froisse(monde):
	c = perso()
	av = recrue()
	recrutement.embaucher(c, av)
	ok, _ = recrutement.congedier(c, av)
	assert ok
	assert c["groupe"] == [] and av["statut"] == "parti"
	assert c["affinites"][av["_id"]] == 50 + character_stats.AFFINITE_DELTA_CONGEDIE


def test_congedier_en_quete_froisse_davantage(monde):
	c = perso(quetes_actives=[{"id": "quete:x"}])
	av = recrue()
	recrutement.embaucher(c, av)
	recrutement.congedier(c, av)
	assert c["affinites"][av["_id"]] == 50 + character_stats.AFFINITE_DELTA_CONGEDIE_EN_QUETE


def test_groupe_effectif_filtre_les_partis(monde):
	av = recrue(statut="embauche", embauche_par="character:u_1")
	parti = recrue("aventurier:guilde_parti", statut="parti", embauche_par="character:u_1")
	monde["docs"][av["_id"]] = av
	monde["docs"][parti["_id"]] = parti
	c = perso(groupe=[av["_id"], parti["_id"], "aventurier:disparu"])
	assert [a["_id"] for a in recrutement.groupe_effectif(c)] == [av["_id"]]


def test_departs_volontaires_sous_le_seuil(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "AFFINITE_SEUIL_DEPART", 30)
	av = recrue(statut="embauche", embauche_par="character:u_1")
	monde["docs"][av["_id"]] = av
	c = perso(groupe=[av["_id"]], affinites={av["_id"]: 20})
	partis = recrutement.departs_volontaires(c)
	assert [a["_id"] for a in partis] == [av["_id"]]
	assert c["groupe"] == [] and av["statut"] == "parti"


# ── Engagement durable (compagnie) ───────────────────────────────────────────────

def _permanent(monde, c, av_id="aventurier:fidele", affinite=95):
	"""Compagnon actif porté à l'engagement durable (part nulle, hors plafond)."""
	av = _embauche(monde, av_id)
	c["groupe"] = list(c.get("groupe", [])) + [av["_id"]]
	c.setdefault("affinites", {})[av["_id"]] = affinite
	ok, raison = recrutement.engager_permanent(c, av, "La Main d'Argent")
	assert ok, raison
	return av


def test_engager_fonde_la_compagnie(monde):
	c = perso()
	av = _permanent(monde, c)
	assert av["permanent"] is True
	assert c["compagnie"]["nom"] == "La Main d'Argent"
	assert c["compagnie"]["fondee_at"] == 1000


def test_engager_refuse_sous_le_seuil(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "AFFINITE_SEUIL_ENGAGEMENT", 90)
	c = perso()
	av = _embauche(monde)
	c["groupe"] = [av["_id"]]
	c["affinites"] = {av["_id"]: 89}
	ok, raison = recrutement.engager_permanent(c, av, "Trop Tôt")
	assert not ok and "dévoué" in raison
	assert "compagnie" not in c and "permanent" not in av


def test_second_engagement_rejoint_sans_renommer(monde):
	"""Les suivants REJOIGNENT la compagnie : le nom proposé est ignoré, pas appliqué."""
	c = perso()
	_permanent(monde, c, "aventurier:un")
	second = _embauche(monde, "aventurier:deux")
	c["groupe"].append(second["_id"])
	c["affinites"][second["_id"]] = 95
	ok, _ = recrutement.engager_permanent(c, second, "Autre nom")
	assert ok and second["permanent"] is True
	assert c["compagnie"]["nom"] == "La Main d'Argent"


def test_engager_sans_nom_au_premier_engagement_refuse(monde):
	c = perso()
	av = _embauche(monde)
	c["groupe"] = [av["_id"]]
	c["affinites"] = {av["_id"]: 95}
	ok, raison = recrutement.engager_permanent(c, av, "   ")
	assert not ok and "nom" in raison
	assert "compagnie" not in c and "permanent" not in av


def test_engager_refuse_deux_fois(monde):
	c = perso()
	av = _permanent(monde, c)
	ok, raison = recrutement.engager_permanent(c, av, None)
	assert not ok and "déjà" in raison


def test_permanent_hors_plafond(monde):
	"""Le parcours qui prouve la cohérence : 2 compagnons = complet ; engager l'un des
	deux LIBÈRE sa place."""
	a, b = _embauche(monde, "aventurier:a"), _embauche(monde, "aventurier:b")
	c = perso(groupe=[a["_id"], b["_id"]], affinites={a["_id"]: 95})
	assert recrutement.places_occupees(c) == 2
	assert recrutement.embaucher(c, recrue())[0] is False

	recrutement.engager_permanent(c, a, "La Main d'Argent")

	assert recrutement.places_occupees(c) == 1
	assert recrutement.embaucher(c, recrue())[0] is True


def test_permanent_ne_prend_aucune_part_de_butin(monde):
	"""⚠️ 0, pas le plancher PART_BUTIN_MIN : `conditions_effectives` sort AVANT le calcul."""
	c = perso()
	av = _permanent(monde, c, affinite=95)
	av["exigences"] = {"part_butin_pct": 30, "clauses": ["Ne pas fuir."]}
	cond = recrutement.conditions_effectives(av, 50)  # même à affinité NEUTRE
	assert cond["part_butin_pct"] == 0
	assert cond["clauses"] == ["Ne pas fuir."]  # les clauses, elles, tiennent toujours

	res = recrutement.regler_part_butin(c, [av], 1000)
	assert res["parts"][av["_id"]] == 0 and res["reste"] == 1000
	assert av["cuivre"] == 0


def test_permanent_ne_part_jamais_de_lui_meme(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "AFFINITE_SEUIL_DEPART", 30)
	c = perso()
	av = _permanent(monde, c)
	c["affinites"][av["_id"]] = 5  # il vous déteste — l'engagement tient quand même
	assert recrutement.departs_volontaires(c) == []
	assert c["groupe"] == [av["_id"]] and av["permanent"] is True


def test_congedier_un_permanent_coute_plus_cher(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "AFFINITE_DELTA_CONGEDIE_PERMANENT", -15)
	c = perso()
	av = _permanent(monde, c, affinite=95)
	ok, _ = recrutement.congedier(c, av)
	assert ok and av["statut"] == "parti"
	assert c["affinites"][av["_id"]] == 95 - 15
	assert "permanent" not in av           # le lien est rompu…
	assert c["compagnie"]["nom"] == "La Main d'Argent"   # …la compagnie, non


def test_congedier_permanent_ne_cumule_pas_avec_en_quete(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "AFFINITE_DELTA_CONGEDIE_PERMANENT", -15)
	c = perso(quetes_actives=[{"id": "quete:x"}])
	av = _permanent(monde, c, affinite=95)
	recrutement.congedier(c, av)
	assert c["affinites"][av["_id"]] == 95 - 15  # un SEUL delta, priorité au permanent


def test_ancien_permanent_reembauche_repart_sur_un_contrat(monde):
	"""Sans ce filet, l'engagement (part nulle + hors plafond) serait gratuit à la
	deuxième signature."""
	c = perso()
	av = _permanent(monde, c)
	recrutement.congedier(c, av)
	av["statut"] = "offert"
	ok, _ = recrutement.embaucher(c, av)
	assert ok and "permanent" not in av
	assert recrutement.places_occupees(c) == 1


@pytest.mark.parametrize("brut, attendu", [
	("  La Main d'Argent  ", "La Main d'Argent"),
	("Les\tLoups\ndu Nord", "Les Loups du Nord"),
	("Les   Trois   Dagues", "Les Trois Dagues"),
	("A" * 60, "A" * 40),
	("   ", ""),
	(None, ""),
	("​", ""),
])
def test_nettoyer_nom_compagnie(brut, attendu):
	assert recrutement.nettoyer_nom_compagnie(brut) == attendu


def test_nettoyer_nom_compagnie_n_echappe_pas_le_html():
	"""⚠️ On BORNE au serveur, on ÉCHAPPE au rendu — échapper ici doublerait l'échappement."""
	assert recrutement.nettoyer_nom_compagnie("<b>Test</b>&'") == "<b>Test</b>&'"


def test_renommer_compagnie(monde):
	c = perso()
	_permanent(monde, c)
	assert recrutement.renommer_compagnie(c, "  Les Loups gris ")[0] is True
	assert c["compagnie"]["nom"] == "Les Loups gris"
	assert c["compagnie"]["fondee_at"] == 1000  # la fondation ne bouge pas


def test_renommer_sans_compagnie_refuse():
	ok, raison = recrutement.renommer_compagnie(perso(), "Fantôme")
	assert not ok and "compagnie" in raison


# ── Affinités ────────────────────────────────────────────────────────────────────

def test_ajuster_affinite_clamp(monde):
	c = perso()
	assert recrutement.ajuster_affinite(c, "aventurier:x", +200) == 100
	assert recrutement.ajuster_affinite(c, "aventurier:x", -500) == 0


def test_memoriser_liens_post_quete(monde):
	c = perso(affinites={"aventurier:a": 50})
	recrutement.memoriser_liens_post_quete(c, [{"_id": "aventurier:a"}, {"_id": "aventurier:b"}])
	assert c["affinites"]["aventurier:a"] == 50 + character_stats.AFFINITE_DELTA_QUETE
	assert c["affinites"]["aventurier:b"] == 50 + character_stats.AFFINITE_DELTA_QUETE


def test_affinites_detail_payload_actifs_d_abord(monde):
	av = recrue(statut="embauche", embauche_par="character:u_1")
	monde["docs"][av["_id"]] = av
	c = perso(
		groupe=[av["_id"]],
		affinites={av["_id"]: 55, "aventurier:vieux": 90},
		compagnons_connus={
			"aventurier:vieux": {"prenom": "Vieux", "nom": "Frère", "voc": "barbare",
								 "race": "nain", "image": "", "rang": "E"},
			av["_id"]: {"prenom": "Aldric", "nom": "Ferrant", "voc": "guerrier",
						"race": "humain", "image": "", "rang": "F"},
		},
	)
	detail = recrutement.affinites_detail_payload(c)
	assert detail[0]["id"] == av["_id"] and detail[0]["actif"] is True
	assert detail[0]["exigences_effectives"]["part_butin_pct"] == 20
	assert detail[1]["id"] == "aventurier:vieux" and detail[1]["actif"] is False


# ── Exigences & part de butin ────────────────────────────────────────────────────

def test_conditions_effectives_reduction_par_affinite(monde):
	av = recrue()  # part 20
	assert recrutement.conditions_effectives(av, 50)["part_butin_pct"] == 20
	assert recrutement.conditions_effectives(av, 70)["part_butin_pct"] == 18
	# Plancher : jamais sous PART_BUTIN_MIN.
	assert recrutement.conditions_effectives(av, 100)["part_butin_pct"] == 15
	av["exigences"]["part_butin_pct"] = 11
	assert recrutement.conditions_effectives(av, 100)["part_butin_pct"] == 10


def test_regler_part_butin_arrondi_sol_et_credit(monde):
	c = perso(affinites={"aventurier:a": 50})
	av = recrue("aventurier:a", statut="embauche")  # part 20 %
	res = recrutement.regler_part_butin(c, [av], 105)
	assert res["parts"]["aventurier:a"] == 21  # floor(105×20 %)
	assert res["reste"] == 84
	assert av["cuivre"] == 21


def test_regler_part_butin_affinite_reduit_la_part(monde):
	c = perso(affinites={"aventurier:a": 100})
	av = recrue("aventurier:a", statut="embauche")  # part 20 → 15 (plancher)
	res = recrutement.regler_part_butin(c, [av], 100)
	assert res["parts"]["aventurier:a"] == 15
	assert res["reste"] == 85


def test_regler_part_butin_groupe_vide(monde):
	res = recrutement.regler_part_butin(perso(), [], 100)
	assert res == {"parts": {}, "reste": 100}


# ── XP partagée avec la COMPAGNIE ────────────────────────────────────────────────
# Un contrat s'achète (part de butin), un engagement se PARTAGE : le compagnon permanent y
# a renoncé, il gagne la MÊME XP que le joueur à la place. Le compagnon sous contrat garde
# l'XP de COMBAT (utils/combat) et rien d'autre.

def test_partager_xp_permanent_gagne_la_meme_xp(monde):
	permanent = recrue("aventurier:a", statut="embauche", permanent=True, xp_total=0)
	contrat   = recrue("aventurier:b", statut="embauche", xp_total=0)
	rendus = recrutement.partager_xp(perso(), 30, compagnons=[permanent, contrat])
	assert [av["_id"] for av in rendus] == ["aventurier:a"]
	assert permanent["xp_total"] == 30
	assert contrat.get("xp_total", 0) == 0


def test_partager_xp_monte_le_niveau_et_donne_les_points(monde):
	av = recrue("aventurier:a", statut="embauche", permanent=True, xp_total=0,
				attribute_points=0)
	recrutement.partager_xp(perso(), 10_000, compagnons=[av])
	assert av["attribute_points"] > 0   # même règle de montée que le joueur (grant_xp)


def test_partager_xp_nulle_ne_touche_rien(monde):
	av = recrue("aventurier:a", statut="embauche", permanent=True, xp_total=7)
	assert recrutement.partager_xp(perso(), 0, compagnons=[av]) == []
	assert recrutement.partager_xp(perso(), -5, compagnons=[av]) == []
	assert av["xp_total"] == 7


def test_partager_xp_ne_relit_pas_les_docs_fournis(monde):
	"""⚠️ Garde du SECOND dict : recharger un doc que l'appelant tient déjà donnerait deux
	`save_doc` sur le même `_rev`, donc une écriture perdue en silence."""
	av = recrue("aventurier:a", statut="embauche", permanent=True, xp_total=0)
	def _interdit(_doc_id):
		raise AssertionError("aucune lecture ne doit avoir lieu quand les docs sont fournis")
	recrutement.partager_xp(perso(groupe=["aventurier:a"]), 5, compagnons=[av],
							get_doc_fn=_interdit)
	assert av["xp_total"] == 5


def test_compagnie_effective_ne_garde_que_les_permanents(monde):
	docs = monde["docs"]
	docs["aventurier:a"] = recrue("aventurier:a", statut="embauche",
								  embauche_par="character:u_1", permanent=True)
	docs["aventurier:b"] = recrue("aventurier:b", statut="embauche",
								  embauche_par="character:u_1")
	c = perso(groupe=["aventurier:a", "aventurier:b"])
	assert [av["_id"] for av in recrutement.compagnie_effective(c)] == ["aventurier:a"]
	# Complément exact de places_occupees : seul le contrat occupe une place.
	assert recrutement.places_occupees(c) == 1


def test_partager_xp_sans_groupe_ne_lit_rien(monde):
	def _interdit(_doc_id):
		raise AssertionError("un personnage sans groupe ne doit émettre aucune lecture")
	assert recrutement.partager_xp(perso(), 10, get_doc_fn=_interdit) == []


def test_xp_compagnie_payload(monde):
	permanent = recrue("aventurier:a", statut="embauche", permanent=True)
	contrat   = recrue("aventurier:b", statut="embauche")
	# Filtre le MÊME prédicat que partager_xp : on peut lui passer la liste brute du groupe.
	assert recrutement.xp_compagnie_payload([permanent, contrat], 30) == {"membres": 1, "xp": 30}
	assert recrutement.xp_compagnie_payload([], 30) is None
	assert recrutement.xp_compagnie_payload([contrat], 30) is None
	assert recrutement.xp_compagnie_payload([permanent], 0) is None   # rien à annoncer


def test_appliquer_recompenses_partage_avec_la_compagnie(monde):
	from utils import quetes
	permanent = recrue("aventurier:a", statut="embauche", permanent=True, xp_total=0)
	contrat   = recrue("aventurier:b", statut="embauche", xp_total=0)
	c = perso(affinites={"aventurier:a": 50, "aventurier:b": 50})
	q = {"recompenses": {"xp": 40, "cuivre": 100}}

	recap = quetes.appliquer_recompenses(c, q, compagnons=[permanent, contrat])

	assert c["xp_total"] == 40
	assert [av["_id"] for av in recap["compagnie"]] == ["aventurier:a"]
	assert permanent["xp_total"] == 40 and contrat.get("xp_total", 0) == 0
	# ⚠️ L'XP n'est pas une part : le permanent ne prend toujours RIEN sur le cuivre.
	reglement = recrutement.regler_part_butin(c, [permanent, contrat], 100)
	assert reglement["parts"]["aventurier:a"] == 0
	assert reglement["parts"]["aventurier:b"] == 20


def test_tirer_exigences_bornes(monde):
	for niveau in (0, 3):
		for _ in range(10):
			ex = recrutement._tirer_exigences(niveau)
			assert 10 <= ex["part_butin_pct"] <= 30
			assert 0 <= len(ex["clauses"]) <= 2


# ── Tour monde : le groupe régénère avec le joueur ───────────────────────────────
# `_apply_world_turn_regen` vit dans routers/user.py mais ne touche jamais la DB : un doc
# `aventurier:*` étant un miroir du character, elle s'y applique telle quelle. Le helper de
# groupe, lui, lit/sauve des docs → on lui monkeypatche la base en mémoire du fixture.

@pytest.fixture
def tour_monde(monde, monkeypatch):
	from routers import user as user_router
	docs = monde["docs"]
	monkeypatch.setattr(user_router, "get_doc", lambda doc_id: docs.get(doc_id))
	monkeypatch.setattr(user_router, "save_doc", lambda doc: docs.__setitem__(doc["_id"], doc) or doc)
	return user_router


def test_tour_monde_regenere_un_compagnon(tour_monde, monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=PORTRAITS)
	pv_max, pm_max = recrutement.vitaux_de(av)["pv_max"], recrutement.vitaux_de(av)["pm_max"]
	av["currentPV"], av["currentPM"] = 1, 0
	tour_monde._apply_world_turn_regen(av)
	assert av["currentPV"] > 1 and av["currentPM"] > 0
	# Plafonné aux max dérivés, même après beaucoup de tours.
	for _ in range(200):
		tour_monde._apply_world_turn_regen(av)
	assert av["currentPV"] == pv_max and av["currentPM"] == pm_max


def test_tour_monde_tick_les_effets_du_compagnon(tour_monde, monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=PORTRAITS)
	av["effets_actifs"] = [{"item_id": "item:potion", "nom": "Potion", "icon": "",
							"buffs": {"F": 10}, "regen_pv": 0, "regen_pm": 0, "restants": 2}]
	tour_monde._apply_world_turn_regen(av)
	assert av["effets_actifs"][0]["restants"] == 1
	tour_monde._apply_world_turn_regen(av)
	assert av["effets_actifs"] == []


def test_tour_monde_groupe_regenere_les_membres_actifs(tour_monde, monde):
	docs = monde["docs"]
	actif = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=PORTRAITS)
	actif.update({"_id": "aventurier:a", "statut": "embauche", "embauche_par": "character:u_1",
				  "currentPV": 1, "currentPM": 0})
	parti = dict(actif, _id="aventurier:b", statut="parti")
	docs["aventurier:a"], docs["aventurier:b"] = actif, parti
	c = perso(groupe=["aventurier:a", "aventurier:b", "aventurier:fantome"])

	rendus = tour_monde._apply_world_turn_groupe(c)

	assert [av["_id"] for av in rendus] == ["aventurier:a"]  # parti + id périmé ignorés
	assert docs["aventurier:a"]["currentPV"] > 1   # régénéré ET persisté
	assert docs["aventurier:b"]["currentPV"] == 1  # un ex-compagnon ne récupère pas


def test_tour_monde_groupe_partage_l_xp_de_decouverte(tour_monde, monde):
	"""⚠️ L'XP de découverte doit être écrite sur les MÊMES dicts que ceux que cette
	fonction sauve : c'est le seul endroit du déplacement qui charge et persiste les docs
	compagnons — un second chargement en amont perdrait une des deux écritures."""
	docs = monde["docs"]
	permanent = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=PORTRAITS)
	permanent.update({"_id": "aventurier:a", "statut": "embauche",
					  "embauche_par": "character:u_1", "permanent": True, "xp_total": 0})
	contrat = dict(permanent, _id="aventurier:b", xp_total=0)
	contrat.pop("permanent")
	docs["aventurier:a"], docs["aventurier:b"] = permanent, contrat
	c = perso(groupe=["aventurier:a", "aventurier:b"])

	tour_monde._apply_world_turn_groupe(c, 25)

	assert docs["aventurier:a"]["xp_total"] == 25   # la compagnie progresse avec le joueur
	assert docs["aventurier:b"]["xp_total"] == 0    # le contrat ne gagne que l'XP de combat
	assert docs["aventurier:a"]["currentPV"] >= 1   # et la régén a bien été persistée aussi


def test_vitaux_de_expose_courants_et_max(tour_monde, monde):
	av = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=PORTRAITS)
	av["currentPV"] = 3
	vit = recrutement.vitaux_de(av)
	assert vit["currentPV"] == 3 and vit["pv_max"] > 0
	assert vit["currentPM"] == av["currentPM"] and vit["pm_max"] > 0


def test_affinites_detail_vitaux_pour_les_actifs_seuls(monde):
	docs = monde["docs"]
	actif = recrutement.generer_aventurier(GUILDE, VILLE, 1, portraits=PORTRAITS)
	actif.update({"_id": "aventurier:a", "statut": "embauche", "embauche_par": "character:u_1"})
	docs["aventurier:a"] = actif
	c = perso(groupe=["aventurier:a"], affinites={"aventurier:a": 60, "aventurier:z": 40})
	recrutement.memo_compagnon(c, actif)
	# Compagnon oublié en base (doc supprimé) : le mémo suffit, pas de vitaux, pas de crash.
	c["compagnons_connus"]["aventurier:z"] = {"prenom": "Vieux", "nom": "Ami", "voc": "guerrier"}

	detail = {e["id"]: e for e in recrutement.affinites_detail_payload(c, docs.get)}

	assert detail["aventurier:a"]["pv_max"] > 0 and "currentPM" in detail["aventurier:a"]
	assert "pv_max" not in detail["aventurier:z"] and detail["aventurier:z"]["actif"] is False


# ── Contrat d'UNE MISSION ────────────────────────────────────────────────────────
# Troisième mode de lien : payé d'avance en cuivre contre une part de butin réduite, il
# s'achève de lui-même à la première quête rendue DANS une maison de guilde. `contrat`
# absent ⇒ comportement d'avant à la lettre (aucune migration).

COMPTOIR = {"_id": "lieu:comptoir", "type": "lieu",
			"categorie": "guilde_aventurier_comptoir", "sous_categorie": "guilde_aventurier"}
FACADE = {"_id": "lieu:facade", "type": "lieu", "categorie": "guilde_aventurier_exterieur"}
BUREAU = {"_id": "lieu:bureau", "type": "lieu", "categorie": "bureau_maitre_guilde"}
BOUCHERIE = {"_id": "lieu:boucherie", "type": "lieu", "categorie": "boucherie"}


def _mission(monde, c, av_id="aventurier:mission", part=20, affinite=50):
	"""Compagnon actif lié par un contrat d'une mission, déjà attaché au personnage."""
	av = recrue(av_id, exigences={"part_butin_pct": part, "clauses": []})
	monde["docs"][av_id] = av
	termes = recrutement.offre_mission(av)
	ok, raison = recrutement.embaucher(
		c, av, contrat={"mode": "mission", "part_butin_pct": termes["part_butin_pct"],
						"cout_cuivre": termes["cout_cuivre"], "signe_at": 1000,
						"giver": "lieu:guilde"})
	assert ok, raison
	c["affinites"][av_id] = affinite
	return av


def test_lieu_de_guilde_couvre_les_quatre_lieux_de_la_maison(monde):
	# ⚠️ Les quatre docs ont des `categorie` DIFFÉRENTES, et le bureau du maître n'a même
	# pas de `sous_categorie` : aucun prédicat existant ne les couvrait tous.
	for lieu in (GUILDE, COMPTOIR, FACADE, BUREAU):
		assert recrutement.lieu_de_guilde(lieu) is True, lieu["_id"]
	assert recrutement.lieu_de_guilde(BOUCHERIE) is False
	assert recrutement.lieu_de_guilde(None) is False


def test_lieu_de_guilde_ouvert_par_le_tag(monde):
	"""Le tag `guilde` ouvre la porte à une faction future SANS une ligne de code."""
	assert recrutement.lieu_de_guilde({"categorie": "caserne", "tags": ["guilde"]}) is True


def test_offre_mission_le_cout_suit_le_niveau(monde):
	assert recrutement.offre_mission(recrue(xp_total=0))["cout_cuivre"] == 300
	# Un niveau de plus = COUT_PAR_NIVEAU de plus (compute_character_level, pas de barème maison).
	niveau = compute_character_level(400)
	assert recrutement.offre_mission(recrue(xp_total=400))["cout_cuivre"] == 300 + 200 * niveau


def test_offre_mission_part_reduite_depuis_la_part_BRUTE(monde):
	"""⚠️ La part part de l'exigence BRUTE : la réduction d'affinité est appliquée UNE
	seule fois, au règlement — la compter ici la déduirait deux fois."""
	av = recrue(exigences={"part_butin_pct": 20, "clauses": []})
	assert recrutement.offre_mission(av)["part_butin_pct"] == 10  # 20 × 0.5


def test_offre_mission_part_plancheree(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "RECRUTEMENT_MISSION_PART_MIN", 8)
	av = recrue(exigences={"part_butin_pct": 10, "clauses": []})
	assert recrutement.offre_mission(av)["part_butin_pct"] == 8  # 10 × 0.5 = 5 → plancher


def test_embaucher_avec_contrat_estampille_le_doc(monde):
	c = perso()
	av = _mission(monde, c)
	assert av["contrat"]["mode"] == "mission"
	assert av["contrat"]["part_butin_pct"] == 10 and av["contrat"]["cout_cuivre"] == 300
	assert av["statut"] == "embauche" and c["groupe"] == [av["_id"]]


def test_reembauche_sans_contrat_efface_un_contrat_perime(monde):
	"""Miroir exact du filet `permanent` : sans ce pop, la deuxième signature serait
	GRATUITE — le joueur garderait une part réduite sans avoir repayé."""
	c = perso()
	av = _mission(monde, c)
	recrutement.congedier(c, av)
	av["statut"] = "offert"
	ok, _ = recrutement.embaucher(c, av)
	assert ok and "contrat" not in av


def test_conditions_effectives_part_de_mission_et_mode(monde):
	c = perso()
	av = _mission(monde, c, part=20)          # part de mission = 10
	cond = recrutement.conditions_effectives(av, 50)
	assert cond["part_butin_pct"] == 10 and cond["mode"] == "mission"
	# Un contrat ordinaire garde sa part brute et un mode vide.
	ord_av = recrue("aventurier:ord", exigences={"part_butin_pct": 20, "clauses": []})
	assert recrutement.conditions_effectives(ord_av, 50) == {
		"part_butin_pct": 20, "mode": "", "clauses": []}


def test_conditions_effectives_l_affinite_rogne_encore_la_part_de_mission(monde):
	c = perso()
	av = _mission(monde, c, part=20)          # 10 après le facteur
	# +30 d'affinité au-dessus du neutre ⇒ −3 points (AFFINITE_REDUC_PART = 10).
	assert recrutement.conditions_effectives(av, 80)["part_butin_pct"] == 7


def test_conditions_effectives_plancher_propre_au_contrat_de_mission(monde):
	"""⚠️ Le plancher est MISSION_PART_MIN (0 par défaut), et surtout PAS PART_BUTIN_MIN :
	celui-ci ferait REMONTER à 10 % une part déjà payée d'avance."""
	c = perso()
	av = _mission(monde, c, part=20)
	assert recrutement.conditions_effectives(av, 100)["part_butin_pct"] == 5  # 10 − 5


def test_un_permanent_l_emporte_sur_un_contrat_residuel(monde):
	c = perso()
	av = _mission(monde, c)
	av["permanent"] = True                    # état impossible en jeu, garde de sécurité
	cond = recrutement.conditions_effectives(av, 50)
	assert cond["part_butin_pct"] == 0 and cond["mode"] == ""


def test_engager_permanent_absorbe_le_contrat_de_mission(monde):
	c = perso()
	av = _mission(monde, c, affinite=95)
	ok, raison = recrutement.engager_permanent(c, av, "La Main d'Argent")
	assert ok, raison
	assert av["permanent"] is True and "contrat" not in av


def test_regler_part_butin_paie_la_part_reduite(monde):
	"""Le chokepoint de règlement n'a PAS été modifié : il traverse déjà
	`conditions_effectives`, qui aiguille seule vers la part du contrat."""
	c = perso()
	av = _mission(monde, c, part=20)          # 10 %
	reglement = recrutement.regler_part_butin(c, [av], 1000)
	assert reglement["parts"][av["_id"]] == 100 and reglement["reste"] == 900


# ── Clôture des contrats au turn-in ──────────────────────────────────────────────

def test_cloturer_ne_fait_rien_hors_guilde(monde):
	c = perso()
	av = _mission(monde, c)
	assert recrutement.cloturer_contrats_mission(c, BOUCHERIE, compagnons=[av]) == []
	assert c["groupe"] == [av["_id"]] and av["statut"] == "embauche"


def test_cloturer_libere_le_contrat_de_mission_a_la_guilde(monde):
	c = perso()
	av = _mission(monde, c)
	libres = recrutement.cloturer_contrats_mission(c, COMPTOIR, compagnons=[av])
	assert libres == [av]
	assert c["groupe"] == [] and av["statut"] == "parti"
	assert av["contrat"]["echu_at"] == 1000          # le bloc SURVIT (il porte les termes)


def test_cloturer_epargne_ordinaire_et_permanent(monde, monkeypatch):
	# Trois compagnons actifs : le plafond par défaut (2) n'en laisserait pas passer trois.
	monkeypatch.setattr(character_stats, "RECRUTEMENT_GROUPE_TAILLE_MAX", 3)
	c = perso()
	mission = _mission(monde, c, "aventurier:m")
	ordinaire = recrue("aventurier:o")
	monde["docs"]["aventurier:o"] = ordinaire
	recrutement.embaucher(c, ordinaire)
	permanent = recrue("aventurier:p")
	monde["docs"]["aventurier:p"] = permanent
	recrutement.embaucher(c, permanent)
	c["affinites"]["aventurier:p"] = 95
	recrutement.engager_permanent(c, permanent, "La Main d'Argent")

	libres = recrutement.cloturer_contrats_mission(
		c, GUILDE, compagnons=[mission, ordinaire, permanent])

	assert libres == [mission]
	assert ordinaire["statut"] == "embauche" and permanent["statut"] == "embauche"
	assert set(c["groupe"]) == {"aventurier:o", "aventurier:p"}


def test_cloturer_n_ajuste_aucune_affinite(monde):
	"""Le contrat a été HONORÉ jusqu'à son terme : personne n'est froissé. C'est toute la
	différence avec un congédiement."""
	c = perso()
	av = _mission(monde, c, affinite=64)
	recrutement.cloturer_contrats_mission(c, GUILDE, compagnons=[av])
	assert c["affinites"][av["_id"]] == 64


def test_cloturer_est_idempotente(monde):
	c = perso()
	av = _mission(monde, c)
	recrutement.cloturer_contrats_mission(c, GUILDE, compagnons=[av])
	assert recrutement.cloturer_contrats_mission(c, GUILDE, compagnons=[av]) == []


def test_invariant_un_permanent_ne_porte_jamais_de_contrat(monde):
	"""LE test qui protège le câblage de `routers/pnj` : `cloturer_contrats_mission` y
	charge le groupe elle-même pendant que `_sauver_compagnie` sauve les permanents. Les
	deux ensembles doivent être DISJOINTS, sinon ce sont deux dicts du même document."""
	c = perso()
	av = _mission(monde, c, affinite=95)
	recrutement.engager_permanent(c, av, "La Main d'Argent")
	libres = recrutement.cloturer_contrats_mission(c, GUILDE, compagnons=[av])
	partages = recrutement.partager_xp(c, 10, compagnons=[av])
	assert libres == [] and partages == [av]


# ── Rupture ──────────────────────────────────────────────────────────────────────

def test_congedier_un_contrat_de_mission_est_gratuit_a_la_guilde(monde):
	c = perso()
	av = _mission(monde, c, affinite=55)
	ok, _ = recrutement.congedier(c, av, COMPTOIR)
	assert ok and c["affinites"][av["_id"]] == 55   # la clause de sortie fait partie du marché
	assert "contrat" not in av


def test_congedier_un_contrat_de_mission_coute_ailleurs(monde):
	c = perso()
	av = _mission(monde, c, affinite=55)
	recrutement.congedier(c, av, BOUCHERIE)
	assert c["affinites"][av["_id"]] == 55 + character_stats.AFFINITE_DELTA_CONGEDIE


def test_congedier_sans_lieu_garde_le_comportement_d_avant(monde):
	"""`lieu_doc=None` : les appelants d'avant sont inchangés à la lettre."""
	c = perso()
	av = _mission(monde, c, affinite=55)
	recrutement.congedier(c, av)
	assert c["affinites"][av["_id"]] == 55 + character_stats.AFFINITE_DELTA_CONGEDIE


def test_congedier_un_ordinaire_garde_son_malus_a_la_guilde(monde):
	"""La gratuité ne vaut QUE pour un contrat d'une mission : l'ordinaire n'a pas de terme,
	le rompre reste un renvoi."""
	c = perso(affinites={"aventurier:o": 55})
	av = recrue("aventurier:o")
	monde["docs"]["aventurier:o"] = av
	recrutement.embaucher(c, av)
	recrutement.congedier(c, av, COMPTOIR)
	assert c["affinites"]["aventurier:o"] == 55 + character_stats.AFFINITE_DELTA_CONGEDIE


def test_congedier_un_permanent_garde_son_malus_a_la_guilde(monde):
	c = perso()
	av = _permanent(monde, c, "aventurier:fidele", affinite=95)
	recrutement.congedier(c, av, COMPTOIR)
	assert c["affinites"][av["_id"]] == 95 + character_stats.AFFINITE_DELTA_CONGEDIE_PERMANENT


# ── Reprise pour une mission de plus ─────────────────────────────────────────────

def _echu(monde, c, av_id="aventurier:mission"):
	av = _mission(monde, c, av_id)
	recrutement.cloturer_contrats_mission(c, GUILDE, compagnons=[av])
	return av


def test_peut_reprendre_un_contrat_echu(monde):
	c = perso()
	av = _echu(monde, c)
	assert recrutement.peut_reprendre(c, av, monde["docs"].get) == (True, "")


def test_peut_reprendre_refuse_un_autre_employeur(monde):
	"""`embauche_par` est la SEULE preuve du lien passé : un doc `aventurier:*` n'a pas
	de `user_id`."""
	c = perso()
	av = _echu(monde, c)
	av["embauche_par"] = "character:autre"
	ok, raison = recrutement.peut_reprendre(c, av, monde["docs"].get)
	assert not ok and "jamais" in raison


def test_peut_reprendre_refuse_un_contrat_ordinaire(monde):
	c = perso()
	av = recrue("aventurier:o", statut="parti", embauche_par="character:u_1")
	monde["docs"]["aventurier:o"] = av
	ok, raison = recrutement.peut_reprendre(c, av, monde["docs"].get)
	assert not ok and "mission" in raison


def test_peut_reprendre_refuse_une_recrue_re_offerte(monde):
	"""Cas limite ASSUMÉ : le tableau l'a repris entre-temps (statut `offert`) — le joueur
	le ré-embauche alors par le tableau, pas par la reprise."""
	c = perso()
	av = _echu(monde, c)
	av["statut"] = "offert"
	assert recrutement.peut_reprendre(c, av, monde["docs"].get)[0] is False


def test_peut_reprendre_refuse_un_groupe_complet(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "RECRUTEMENT_GROUPE_TAILLE_MAX", 1)
	c = perso()
	av = _echu(monde, c)
	autre = recrue("aventurier:x")
	monde["docs"]["aventurier:x"] = autre
	recrutement.embaucher(c, autre)
	ok, raison = recrutement.peut_reprendre(c, av, monde["docs"].get)
	assert not ok and "complet" in raison


def test_reprendre_rattache_avec_un_contrat_neuf(monde):
	c = perso()
	av = _echu(monde, c)
	contrat = {"mode": "mission", "part_butin_pct": 10, "cout_cuivre": 500,
			   "signe_at": 1000, "giver": "lieu:guilde"}
	ok, raison = recrutement.reprendre(c, av, contrat, monde["docs"].get)
	assert ok, raison
	assert av["statut"] == "embauche" and c["groupe"] == [av["_id"]]
	assert av["contrat"]["cout_cuivre"] == 500 and "echu_at" not in av["contrat"]


def test_vue_contrat_echu_recalcule_les_termes(monde):
	"""Reprendre, c'est signer un contrat NEUF : les termes suivent le niveau atteint, ils
	ne sont pas relus du contrat échu."""
	c = perso()
	av = _echu(monde, c)
	av["contrat"]["cout_cuivre"] = 1           # tarif périmé, jamais relu
	av["xp_total"] = 400
	vue = recrutement.vue_contrat_echu(av)
	attendu = recrutement.offre_mission(av)
	assert vue["cout_cuivre"] == attendu["cout_cuivre"] > 1
	assert vue["part_butin_pct"] == attendu["part_butin_pct"]
	assert vue["id"] == av["_id"] and vue["prenom"] == "Aldric"
