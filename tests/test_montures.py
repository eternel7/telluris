"""Montures de transport (utils/montures.py) — logique pure, sans DB.

Éligibilité de l'étable, propriétés d'espèce (charge_mult / prix_cuivre + replis),
création procédurale d'un doc `monture:*` MIROIR du character, capacité d'emport
démultipliée, plafond du troupeau, achat/relâchement, et mort avec restitution de la
cargaison. Mêmes conventions que tests/test_recrutement.py : les accès DB du module
sont monkeypatchés sur le module lui-même.
"""

import copy

import pytest

from models import character_stats
from utils import montures
from utils import recrutement
from utils import characters as characters_util


# ── Monde de test ────────────────────────────────────────────────────────────────

ETABLE = {
	"_id": "lieu:etable", "type": "lieu", "categorie": "etable", "lieu_parent": "lieu:ville",
	"pnj": [{"character": "pnj:marchand_etable",
			 "montures": ["espece:ane", "espece:cheval"]}],
}
VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville"}

# F fixé (min == max) pour que la charge soit déterministe : F=20 → charge_max_of = 100.
ANE = {
	"_id": "espece:ane", "type": "espece", "nom": "Âne", "image": "ane_transparent.png",
	"base_attributes": {
		"V": {"min": 4, "max": 4}, "F": {"min": 20, "max": 20}, "R": {"min": 30, "max": 30},
		"Ag": {"min": 15, "max": 15}, "Vol": {"min": 20, "max": 20}, "Int": {"min": 5, "max": 5},
		"Cha": {"min": 0, "max": 0}, "Ch": {"min": 0, "max": 0},
	},
	"tags": ["monture", "bete_de_somme", "proie"],
	"proprietes": {"charge_mult": 4.0, "prix_cuivre": 80000},
}
CHEVAL = {
	"_id": "espece:cheval", "type": "espece", "nom": "Cheval", "image": "cheval_transparent.png",
	"base_attributes": {
		"V": {"min": 5, "max": 8}, "F": {"min": 20, "max": 40}, "R": {"min": 25, "max": 45},
		"Ag": {"min": 25, "max": 50}, "Vol": {"min": 15, "max": 30}, "Int": {"min": 5, "max": 10},
		"Cha": {"min": 0, "max": 0}, "Ch": {"min": 0, "max": 0},
	},
	"tags": ["monture", "proie"],
	"proprietes": {"charge_mult": 3.0, "prix_cuivre": 250000},
}
# Espèce sans `proprietes` : doit tomber sur les replis (données non encore peuplées).
POULAIN = {
	"_id": "espece:poulain", "type": "espece", "nom": "Poulain", "image": "poulain.png",
	"base_attributes": {"F": {"min": 10, "max": 10}}, "tags": ["monture"], "proprietes": {},
}
SAC = {"_id": "item:sac", "type": "item", "nom": "Sac", "categorie": "contenant", "poids": 3}
ENCLUME = {"_id": "item:enclume", "type": "item", "nom": "Enclume", "categorie": "outil",
		   "poids": 90}


@pytest.fixture
def monde(monkeypatch):
	"""Base en mémoire branchée sur les accès DB de montures + characters.

	Copie PROFONDE des docs de référence : un test qui règle une propriété d'espèce à
	chaud (c'est tout l'intérêt de la relecture) ne doit pas contaminer les suivants."""
	docs = {d["_id"]: copy.deepcopy(d)
			for d in (ETABLE, VILLE, ANE, CHEVAL, POULAIN, SAC, ENCLUME)}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	monkeypatch.setattr(montures, "get_doc", get_doc_fn)
	monkeypatch.setattr(montures, "now_epoch", lambda: 1000)
	monkeypatch.setattr(characters_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(character_stats, "MONTURE_GROUPE_MAX", 2)
	monkeypatch.setattr(character_stats, "MONTURE_CHARGE_MULT_DEFAUT", 3.0)
	monkeypatch.setattr(character_stats, "MONTURE_PRIX_DEFAUT", 2000)
	return docs


def perso(**champs):
	base = {
		"_id": "character:u_1", "type": "character", "user_id": "user:u",
		"prenom": "Test", "nom": "Héros", "inventaire": [], "slots": {}, "groupe": [],
		"montures": [], "caracteristiques_current": {"F": 20, "R": 20, "V": 5, "Ag": 20,
													 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
		"or": 0, "argent": 0, "cuivre": 0,
	}
	base.update(champs)
	return base


# ── Éligibilité du lieu ──────────────────────────────────────────────────────────

def test_etable_par_categorie(monde):
	assert montures.lieu_vend_montures(ETABLE) is True


def test_etable_par_tag_sans_categorie(monde):
	"""Le OU sur le tag évite une migration : n'importe quel lieu peut vendre."""
	assert montures.lieu_vend_montures(
		{"_id": "lieu:x", "categorie": "auberge", "tags": ["montures"]}) is True


def test_lieu_quelconque_ne_vend_pas(monde):
	assert montures.lieu_vend_montures({"_id": "lieu:x", "categorie": "boucherie"}) is False
	assert montures.lieu_vend_montures(None) is False


def test_especes_offertes_dedupliquees_et_ordonnees(monde):
	lieu = {"pnj": [{"montures": ["espece:ane", "espece:cheval"]},
					{"montures": ["espece:cheval", "espece:poney"]}]}
	assert montures.especes_offertes(lieu) == ["espece:ane", "espece:cheval", "espece:poney"]


def test_especes_offertes_lieu_sans_pnj(monde):
	assert montures.especes_offertes({"_id": "lieu:x"}) == []


# ── Propriétés d'espèce & replis ─────────────────────────────────────────────────

def test_proprietes_lues_sur_l_espece(monde):
	assert montures.charge_mult(ANE) == 4.0
	assert montures.prix_de(ANE) == 80000


def test_replis_si_proprietes_vides(monde):
	"""Une espèce non encore peuplée reste utilisable : replis world-vars."""
	assert montures.charge_mult(POULAIN) == 3.0
	assert montures.prix_de(POULAIN) == 200000


def test_charge_mult_plancher_a_un(monde):
	"""Un multiplicateur < 1 ferait d'une monture un porteur PIRE qu'un humain."""
	assert montures.charge_mult({"proprietes": {"charge_mult": 0.2}}) == 1.0


def test_proprietes_illisibles_tombent_sur_le_repli(monde):
	assert montures.charge_mult({"proprietes": {"charge_mult": "beaucoup"}}) == 3.0
	assert montures.prix_de({"proprietes": {"prix_cuivre": None}}) == 200000


# ── Création ─────────────────────────────────────────────────────────────────────

def test_creation_champs_miroirs(monde):
	m = montures.creer_monture(ANE, ETABLE, perso())
	assert m["type"] == "monture" and m["statut"] == "acquise"
	assert m["_id"].startswith("monture:ane_")
	assert m["espece"] == "espece:ane"
	assert m["acquise_par"] == "character:u_1"
	assert m["giver"] == "lieu:etable" and m["lieu_parent"] == "lieu:ville"
	assert m["nom"] == "Âne" and m["image"] == "ane_transparent.png"
	# Le sous-ensemble de champs qui rend le moteur du character opérant.
	for champ in ("caracteristiques_current", "inventaire", "slots", "equipment_bonus",
				  "effets_actifs", "combats_recompenses"):
		assert champ in m
	assert m["jouable"] is False


def test_creation_pv_pm_au_max(monde):
	m = montures.creer_monture(ANE, ETABLE, perso())
	vit = montures.vitaux_de(m)
	assert m["currentPV"] == vit["pv_max"] > 0
	assert m["currentPM"] == vit["pm_max"]


def test_creation_stats_dans_les_fourchettes(monde):
	"""Deux chevaux ne se valent pas, mais restent bornés par l'espèce."""
	for _ in range(20):
		m = montures.creer_monture(CHEVAL, ETABLE, perso())
		for code, borne in CHEVAL["base_attributes"].items():
			assert borne["min"] <= m["caracteristiques_current"][code] <= borne["max"]


def test_creation_ne_recopie_pas_les_tags_d_espece(monde):
	"""`proie`/`predateur` pilotent l'IA de prédation en furtivité : les recopier sur un
	acteur rangé dans `joueurs` créerait une interaction qu'aucun code n'attend."""
	m = montures.creer_monture(ANE, ETABLE, perso())
	assert "tags" not in m


def test_creation_espece_introuvable(monde):
	assert montures.creer_monture(None, ETABLE, perso()) is None


# ── Capacité d'emport ────────────────────────────────────────────────────────────

def test_charge_max_multipliee(monde):
	"""F=20 → charge_max_of = 100 ; ×4 pour un âne = 400 kg."""
	m = montures.creer_monture(ANE, ETABLE, perso())
	assert characters_util.charge_max_of(m) == 100
	assert montures.charge_max_monture(m) == 400


def test_charge_max_relue_a_chaud(monde):
	"""Le multiplicateur n'est jamais dénormalisé : régler l'espèce prend effet aussitôt."""
	m = montures.creer_monture(ANE, ETABLE, perso())
	monde["espece:ane"]["proprietes"]["charge_mult"] = 6.0
	assert montures.charge_max_monture(m) == 600


def test_charge_max_porteur_aiguille(monde):
	"""Le chokepoint distingue monture et personnage à même Force."""
	m = montures.creer_monture(ANE, ETABLE, perso())
	p = perso()
	assert montures.charge_max_porteur(p) == characters_util.charge_max_of(p) == 100
	assert montures.charge_max_porteur(m) == 400


def test_peut_porter_utilise_la_charge_de_monture(monde):
	"""`recrutement.peut_porter` (l'admission) délègue le plafond à `charge_max_porteur` :
	une enclume de 90 kg — le joueur en porte 1, l'âne bien davantage."""
	m = montures.creer_monture(ANE, ETABLE, perso())
	m["inventaire"] = [{"item": "item:enclume", "poids": 90}] * 3   # 270 kg portés
	assert recrutement.peut_porter(m, {"item": "item:enclume", "poids": 90}) is True
	m["inventaire"].append({"item": "item:enclume", "poids": 90})   # 360 kg
	assert recrutement.peut_porter(m, {"item": "item:enclume", "poids": 90}) is False


def test_transfert_vers_monture_message_nomme_la_bete(monde):
	"""Une monture n'a pas de `prenom` : le refus doit la nommer, pas dire
	« Le destinataire »."""
	m = montures.creer_monture(ANE, ETABLE, perso())
	m["inventaire"] = [{"item": "item:enclume", "poids": 90}] * 4   # 360/400 kg
	source = perso(inventaire=[{"item": "item:enclume", "poids": 90}])
	ok, raison, ref = recrutement.transferer_ref(source, m, 0, "item:enclume")
	assert ok is False and raison.startswith("Âne")
	assert len(source["inventaire"]) == 1   # source jamais amputée sur un refus


# ── Troupeau, achat, relâchement ─────────────────────────────────────────────────

def test_montures_effectives_filtre_appartenance(monde):
	"""Miroir de groupe_effectif : un doc `monture:*` n'a pas de user_id."""
	p = perso()
	mienne = montures.creer_monture(ANE, ETABLE, p)
	autrui = montures.creer_monture(CHEVAL, ETABLE, perso(_id="character:autre"))
	autrui["acquise_par"] = "character:autre"
	morte = montures.creer_monture(ANE, ETABLE, p)
	morte["statut"] = "morte"
	for m in (mienne, autrui, morte):
		monde[m["_id"]] = m
	p["montures"] = [mienne["_id"], autrui["_id"], morte["_id"], "monture:fantome"]

	assert [m["_id"] for m in montures.montures_effectives(p)] == [mienne["_id"]]


def test_peut_acquerir_plafond_avant_bourse(monde):
	"""Annoncer « bourse insuffisante » à qui a déjà son quota serait trompeur."""
	p = perso(or_=0)
	for _ in range(2):
		m = montures.creer_monture(ANE, ETABLE, p)
		monde[m["_id"]] = m
		p.setdefault("montures", []).append(m["_id"])
	ok, raison = montures.peut_acquerir(p, ANE)
	assert ok is False and "davantage" in raison


def test_peut_acquerir_fonds_insuffisants(monde):
	ok, raison = montures.peut_acquerir(perso(cuivre=10), ANE)
	assert ok is False and "payer" in raison


def test_peut_acquerir_ok(monde):
	assert montures.peut_acquerir(perso(**{"or": 10}), ANE) == (True, "")


def test_acquerir_attache_les_deux_docs(monde):
	p = perso()
	m = montures.creer_monture(ANE, ETABLE, p)
	m["acquise_par"] = None
	assert montures.acquerir(p, m) == (True, "")
	assert m["acquise_par"] == "character:u_1" and m["statut"] == "acquise"
	assert p["montures"] == [m["_id"]]
	# Idempotent : pas de doublon dans l'index.
	montures.acquerir(p, m)
	assert p["montures"] == [m["_id"]]


def test_acquerir_refuse_une_monture_morte(monde):
	p = perso()
	m = montures.creer_monture(ANE, ETABLE, p)
	m["statut"] = "morte"
	ok, _ = montures.acquerir(p, m)
	assert ok is False and p["montures"] == []


def test_relacher_retire_du_troupeau(monde):
	p = perso()
	m = montures.creer_monture(ANE, ETABLE, p)
	montures.acquerir(p, m)
	assert montures.relacher(p, m) == (True, "")
	assert p["montures"] == [] and m["statut"] == "relachee"
	assert "acquise_par" not in m


def test_relacher_refuse_si_chargee(monde):
	"""La relâcher chargée ferait disparaître le butin sans que rien ne le signale."""
	p = perso()
	m = montures.creer_monture(ANE, ETABLE, p)
	montures.acquerir(p, m)
	m["inventaire"] = [{"item": "item:sac", "poids": 3}]
	ok, raison = montures.relacher(p, m)
	assert ok is False and "sac" in raison
	assert p["montures"] == [m["_id"]] and m["statut"] == "acquise"


# ── Mort ─────────────────────────────────────────────────────────────────────────

def test_tuer_rend_la_cargaison(monde):
	"""La cargaison ne doit pas disparaître avec la monture : elle est restituée à
	l'appelant, qui la déversera au sol."""
	p = perso()
	m = montures.creer_monture(ANE, ETABLE, p)
	montures.acquerir(p, m)
	m["inventaire"] = [{"item": "item:sac", "poids": 3},
					   {"item": "item:enclume", "poids": 90}]

	cargaison = montures.tuer(p, m)

	assert [r["item"] for r in cargaison] == ["item:sac", "item:enclume"]
	assert m["inventaire"] == []
	assert m["statut"] == "morte" and m["currentPV"] == 0
	assert p["montures"] == []


def test_tuer_sans_cargaison(monde):
	p = perso()
	m = montures.creer_monture(ANE, ETABLE, p)
	montures.acquerir(p, m)
	assert montures.tuer(p, m) == []
	assert p["montures"] == []


def test_perso_sans_montures_se_comporte_comme_une_liste_vide(monde):
	"""Rétro-compat : un character d'avant la feature n'a pas le champ."""
	p = perso()
	p.pop("montures")
	assert montures.montures_effectives(p) == []
	assert montures.peut_acquerir(p, ANE)[0] is False   # bourse vide, pas de crash
