# tests/test_combat_lien_vie.py
#
# LIEN DE VIE / PROTECTION : « Lorsqu'une créature liée subit des dégâts, le sort peut
# transférer tout ou partie de ces dégâts vers le protecteur. Le transfert ne crée pas de
# nouveaux dégâts : il déplace la perte de PV d'une cible vers une autre. »
#
# L'exemple du livre de règles, verrouillé tel quel : un paladin lié à un allié qui encaisse
# 20 dégâts en reprend 10 — l'allié perd 10 PV, le paladin 10.
#
# Le vrai risque de la feature est ailleurs, dans `_do_attack_on` : un même coup peut
# désormais faire tomber DEUX corps. D'où l'extraction de `_traiter_ko`, la garde `status`
# sur la déclaration de défaite, et la ligne de journal propre au protecteur — sans laquelle
# sa barre chuterait avant que le coup ne s'anime.

import pytest

from utils import combat as combat_mod
from utils.combat import (
	_do_attack_on, _rediriger_lien_vie, _rompre_concentration, resolve_action,
)
from _fixtures_magie import combat, joueur, monstre, sort, textes


LIEN = dict(cout_pm=6, maintien=3, cible="allie", portee=4, nom="Lien du paladin",
			icon="🔗", effets={"lien_vie": {"part": 50}})


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _duo(part=50, reduction=0, pv_protecteur=100):
	paladin = joueur(0, x=3, y=5, nom="Paladin", pv=pv_protecteur, pm=60)
	ecuyer = joueur(1, x=4, y=5, nom="Écuyer", pv=100)
	doc = combat([paladin, ecuyer], [monstre(x=9, y=5)])
	effets = {"lien_vie": {"part": part, "reduction": reduction}}
	resolve_action(doc, "sort", cible_id="joueur_1",
				   sort=sort(cout_pm=6, maintien=3, cible="allie", portee=4,
							 nom="Lien du paladin", icon="🔗", effets=effets))
	return paladin, ecuyer, doc


# ── Pose ────────────────────────────────────────────────────────────────────────

def test_le_lien_vit_sur_le_protege():
	"""C'est LUI qui encaisse, donc lui que le moteur interroge à chaque coup."""
	paladin, ecuyer, doc = _duo()
	assert ecuyer["lien_vie"]["protecteur_id"] == "joueur_0"
	assert ecuyer["lien_vie"]["part"] == 50
	assert "lien_vie" not in paladin


def test_le_lanceur_porte_la_concentration_qui_le_finance():
	paladin, ecuyer, doc = _duo()
	assert [c["sort_id"] for c in paladin["concentrations"]] == ["sort:essai"]
	assert paladin["concentrations"][0]["cible_id"] == "joueur_1"


def test_on_ne_se_lie_pas_a_soi_meme():
	"""Il encaisserait ce qu'il encaisse déjà, contre un entretien en PM."""
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(cout_pm=6, maintien=3, cible="soi",
										  effets={"lien_vie": {"part": 50}}))
	assert "lien_vie" not in mage


# ── L'arithmétique du transfert ─────────────────────────────────────────────────

def test_l_exemple_du_livre_de_regles():
	"""20 dégâts, part 50 % ⇒ 10 pour l'écuyer, 10 pour le paladin."""
	paladin, ecuyer, doc = _duo(part=50)
	pour_cible, pour_protecteur, protecteur = _rediriger_lien_vie(doc, ecuyer, 20)
	assert (pour_cible, pour_protecteur) == (10, 10)
	assert protecteur is paladin


def test_le_transfert_ne_cree_aucun_degat():
	"""La somme des deux parts est EXACTEMENT le coup reçu."""
	paladin, ecuyer, doc = _duo(part=70)
	pour_cible, pour_protecteur, _ = _rediriger_lien_vie(doc, ecuyer, 30)
	assert pour_cible + pour_protecteur == 30


def test_la_reduction_est_absorbee_AVANT_le_transfert():
	"""« Le sort peut également réduire les dégâts reçus avant d'appliquer la partie
	transférée. » 20 dégâts, 50 % absorbés puis 50 % transférés ⇒ 5 et 5, pas 10 et 5."""
	paladin, ecuyer, doc = _duo(part=50, reduction=50)
	pour_cible, pour_protecteur, _ = _rediriger_lien_vie(doc, ecuyer, 20)
	assert (pour_cible, pour_protecteur) == (5, 5)


def test_une_part_de_cent_pour_cent_transfere_tout():
	paladin, ecuyer, doc = _duo(part=100)
	pour_cible, pour_protecteur, _ = _rediriger_lien_vie(doc, ecuyer, 20)
	assert (pour_cible, pour_protecteur) == (0, 20)


# ── Les protecteurs indisponibles ───────────────────────────────────────────────

def test_sans_lien_le_comportement_d_avant_a_la_lettre():
	mage = joueur()
	doc = combat([mage])
	assert _rediriger_lien_vie(doc, mage, 20) == (20, 0, None)


def test_un_protecteur_a_terre_ne_protege_plus():
	"""Un lien qui absorberait encore alors que son porteur est au sol protégerait
	gratuitement."""
	paladin, ecuyer, doc = _duo()
	paladin["currentPV"] = 0
	assert _rediriger_lien_vie(doc, ecuyer, 20) == (20, 0, None)


def test_un_coup_nul_ne_transfere_rien():
	paladin, ecuyer, doc = _duo()
	assert _rediriger_lien_vie(doc, ecuyer, 0) == (0, 0, None)


# ── Le coup réel : deux corps peuvent tomber ────────────────────────────────────

def _coup_de(doc, degats, cible):
	loup = doc["monstres"][0]
	loup["pos"] = {"x": 5, "y": 5}
	loup["cc"] = 500                          # le coup porte à coup sûr
	loup["degats_cc"] = degats
	loup["pa"] = 0
	cible["pa"] = 0
	cible["pa_zones"] = {}
	_do_attack_on(doc, loup, cible)
	return loup


def test_les_deux_corps_perdent_leurs_pv(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 5)
	paladin, ecuyer, doc = _duo(part=50)
	pv_ec, pv_pal = ecuyer["currentPV"], paladin["currentPV"]
	_coup_de(doc, "4D6", ecuyer)

	perte_ec = pv_ec - ecuyer["currentPV"]
	perte_pal = pv_pal - paladin["currentPV"]
	assert perte_ec > 0 and perte_pal > 0
	assert perte_ec + perte_pal == 20, "4 dés à 5 = 20, ni plus ni moins"


def test_le_protecteur_a_sa_PROPRE_ligne_de_journal(monkeypatch):
	"""⚠️ `_gelerActeurs` (client) ne rembobine que les acteurs qu'une entrée NOMME : sans
	sa propre ligne, la barre du protecteur chuterait dès l'arrivée de la réponse, avant
	que le coup ne s'anime — le défaut même que la révélation différée existe pour éviter."""
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 5)
	paladin, ecuyer, doc = _duo()
	_coup_de(doc, "4D6", ecuyer)

	lignes = [e for e in doc["log"] if "lien de vie détourne" in e["texte"]]
	assert len(lignes) == 1
	assert paladin["id"] in lignes[0]["etat"], "le protecteur doit être gelé par SA ligne"
	assert lignes[0]["etat"][paladin["id"]]["currentPV"] == paladin["currentPV"]


def test_le_protecteur_peut_tomber_sous_le_coup_qu_il_absorbe(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 6)
	paladin, ecuyer, doc = _duo(part=100, pv_protecteur=5)
	_coup_de(doc, "10D6", ecuyer)

	assert paladin["currentPV"] == 0
	assert ecuyer["currentPV"] > 0, "tout est parti sur le protecteur"
	assert any("Paladin est à terre" in t for t in textes(doc))


def test_une_seule_ligne_de_defaite_meme_si_les_deux_tombent(monkeypatch):
	"""⚠️ Le bloc de défaite n'était pas gardé par `status` : il ne pouvait tuer qu'un
	acteur. Avec deux corps par coup, il l'écrivait deux fois."""
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 6)
	paladin, ecuyer, doc = _duo(part=50, pv_protecteur=5)
	ecuyer["currentPV"] = 5
	_coup_de(doc, "10D6", ecuyer)

	assert doc["status"] == "defaite"
	defaites = [t for t in textes(doc) if "Tout le groupe est à terre" in t]
	assert len(defaites) == 1


def test_le_protecteur_ne_passe_pas_par_la_branche_PROIE(monkeypatch):
	"""⚠️ `est_joueur` doit être RECALCULÉ dans `_traiter_ko` depuis la victime : hérité du
	défenseur, un protecteur du camp du joueur serait déclaré dépeçable."""
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 6)
	paladin, ecuyer, doc = _duo(part=100, pv_protecteur=5)
	_coup_de(doc, "10D6", ecuyer)
	assert "tue_par_monstre" not in paladin
	assert "vivant" not in paladin or paladin.get("vivant") is not False


# ── Rupture du lien ─────────────────────────────────────────────────────────────

def test_rompre_la_concentration_efface_le_lien():
	paladin, ecuyer, doc = _duo()
	_rompre_concentration(doc, paladin, paladin["concentrations"][0], "Le lien se rompt.")
	assert "lien_vie" not in ecuyer
	assert _rediriger_lien_vie(doc, ecuyer, 20) == (20, 0, None)


def test_le_lien_tombe_avec_l_entretien_impaye():
	from utils.combat import _reset_turn_budget
	paladin, ecuyer, doc = _duo()
	paladin["currentPM"] = 1                  # moins que les 3 du maintien
	doc["tour"] = 2
	_reset_turn_budget(paladin, doc)

	assert not paladin.get("concentrations")
	assert "lien_vie" not in ecuyer


def test_le_lien_ne_remonte_pas_sur_le_personnage():
	"""C'est un état de SNAPSHOT : il n'a aucun sens hors du combat."""
	from utils.combat import _effets_a_reverser
	paladin, ecuyer, doc = _duo()
	assert _effets_a_reverser(paladin) == []
