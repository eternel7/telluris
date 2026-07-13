"""Recrutement d'aventuriers (utils/recrutement.py) — logique pure, sans DB.

Génération procédurale des recrues (docs `aventurier:*` MIROIRS du character), rotation
du tableau (purge paresseuse / ré-offre des anciens compagnons), éligibilité du lieu,
embauche/congédiement, affinités et règlement de la part de butin. Les accès DB du module
sont des imports directs de `db.config` : on les monkeypatche sur le module — plus
`utils.characters` / `utils.combat` pour les helpers partagés (équipement, snapshot).
"""

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


def test_choisir_portrait_replis():
	pool = ["assassin_f_elfe01.jpg", "assassin_m_nain01.jpg", "voleur_m_humain01.jpg"]
	assert recrutement.choisir_portrait("assassin", "F", "elfe", pool) == "assassin_f_elfe01.jpg"
	# Pas de nain F assassin → repli sexe, puis vocation.
	assert recrutement.choisir_portrait("assassin", "F", "nain", pool) == "assassin_f_elfe01.jpg"
	assert recrutement.choisir_portrait("assassin", "M", "ogre", pool) == "assassin_m_nain01.jpg"
	assert recrutement.choisir_portrait("barbare", "M", "ogre", pool) in pool
	assert recrutement.choisir_portrait("barbare", "M", "ogre", []) == ""


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


def test_embauche_refusee_au_plafond(monde):
	c = perso(groupe=["aventurier:a", "aventurier:b"])
	ok, raison = recrutement.embaucher(c, recrue())
	assert not ok and "complet" in raison


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


def test_tirer_exigences_bornes(monde):
	for niveau in (0, 3):
		for _ in range(10):
			ex = recrutement._tirer_exigences(niveau)
			assert 10 <= ex["part_butin_pct"] <= 30
			assert 0 <= len(ex["clauses"]) <= 2
