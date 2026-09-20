"""utils/charge_magie.py — la charge portée renchérit la canalisation du mana.

Module PUR : aucune base, aucun snapshot de combat ici (le branchement moteur est couvert
par test_combat_maintien / test_combat_incantation). On verrouille la COURBE, les paliers,
la sensibilité, l'aide d'équipement et les cas limites.

⚠️ Aucune valeur d'équilibrage en dur : les seuils sont relus depuis le module
(CLAUDE.md §14), et les tests de forme épinglent la FORMULE, pas les défauts du monde.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models.character_stats as cs
from utils import charge_magie as cm


@pytest.fixture(autouse=True)
def _reglages(monkeypatch):
	"""Réglages ÉPINGLÉS pour toute la classe de tests — on valide la formule, pas les
	défauts de production (qui sont des world-vars et bougeront à l'équilibrage)."""
	monkeypatch.setattr(cs, "CHARGE_MAGIE_FRANCHISE", 0.25)
	monkeypatch.setattr(cs, "CHARGE_MAGIE_PEN_MAX", 0.60)
	monkeypatch.setattr(cs, "CHARGE_MAGIE_PENTE_SURCHARGE", 1.5)
	monkeypatch.setattr(cs, "CHARGE_MAGIE_PEN_PLAFOND", 3.0)
	monkeypatch.setattr(cs, "SENSIBILITE_CHARGE_DEFAUT", 0.5)
	monkeypatch.setattr(cs, "CANALISATION_REDUCTION_MAX", 90)


def _sort(cout_pm=10, **champs):
	"""Vue normalisée minimale : seules les clés que lit charge_magie."""
	return {"cout_pm": cout_pm, "maintien": 0, **champs}


# ── 1-6. Les six niveaux de charge de la spec ────────────────────────────────────

@pytest.mark.parametrize("ratio, palier_attendu", [
	(0.00, "legere"),
	(0.25, "legere"),        # borne HAUTE incluse : à 25 % pile, on est encore léger
	(0.50, "moderee"),
	(0.75, "importante"),
	(1.00, "lourde"),
	(1.30, "surcharge"),
])
def test_paliers_des_six_niveaux(ratio, palier_attendu):
	assert cm.palier(ratio) == palier_attendu


def test_courbe_nulle_sous_la_franchise():
	# Voyager léger ne coûte RIEN : c'est ce qui rend la mécanique un arbitrage et non
	# une taxe permanente.
	franchise = cs.CHARGE_MAGIE_FRANCHISE
	assert cm.penalite_charge(0.0) == 0.0
	assert cm.penalite_charge(franchise) == 0.0
	assert cm.penalite_charge(franchise / 2) == 0.0


def test_courbe_strictement_croissante_au_dela_de_la_franchise():
	# Propriété, pas table figée : une égalité rendrait un palier inutile, une inversion
	# ferait canaliser MIEUX en portant plus.
	echantillons = [0.3, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.1, 1.5, 2.0]
	valeurs = [cm.penalite_charge(r) for r in echantillons]
	assert valeurs == sorted(valeurs)
	assert len(set(valeurs)) == len(valeurs)


def test_penalite_pile_a_la_capacite_vaut_pen_max():
	# Le point d'ancrage de tout l'équilibrage : à 100 % de la capacité, la pénalité est
	# exactement le réglage, ni plus ni moins.
	assert cm.penalite_charge(1.0) == pytest.approx(cs.CHARGE_MAGIE_PEN_MAX)


def test_aucune_rupture_a_la_capacite():
	# La spec demande « une progression douce jusqu'à la capacité maximale puis une
	# augmentation plus forte » : la VALEUR est continue en 1.0, seule la PENTE change.
	juste_avant = cm.penalite_charge(1.0 - 1e-6)
	juste_apres = cm.penalite_charge(1.0 + 1e-6)
	assert juste_avant == pytest.approx(cs.CHARGE_MAGIE_PEN_MAX, abs=1e-4)
	assert juste_apres == pytest.approx(cs.CHARGE_MAGIE_PEN_MAX, abs=1e-4)


def test_la_surcharge_monte_plus_vite_que_le_regime_normal():
	pente_surcharge = cm.penalite_charge(1.5) - cm.penalite_charge(1.0)
	pente_normale = cm.penalite_charge(1.0) - cm.penalite_charge(0.5)
	assert pente_surcharge > pente_normale


def test_penalite_plafonnee():
	# Même écrasé sous dix fois sa capacité, un mage lance encore : le plafond est ce qui
	# empêche la surcharge de devenir une interdiction déguisée.
	assert cm.penalite_charge(50.0) == pytest.approx(cs.CHARGE_MAGIE_PEN_PLAFOND)


# ── 7-8. Sensibilité du sort ─────────────────────────────────────────────────────

def test_sort_insensible_paie_le_tarif_de_base_meme_en_surcharge():
	pen = cm.penalite_finale(2.0, _sort(sensibilite_charge=0))
	assert pen == 0.0
	assert cm.cout_pm_effectif(10, pen) == 10
	assert cm.maintien_effectif(3, pen) == 3


def test_sort_tres_sensible_prend_la_penalite_pleine():
	ratio = 1.0
	pleine = cm.penalite_finale(ratio, _sort(sensibilite_charge=1))
	assert pleine == pytest.approx(cm.penalite_charge(ratio))
	assert cm.cout_pm_effectif(10, pleine) > 10


def test_sensibilite_absente_retombe_sur_le_defaut_du_monde(monkeypatch):
	monkeypatch.setattr(cs, "SENSIBILITE_CHARGE_DEFAUT", 0.5)
	assert cm.sensibilite_de(_sort()) == 0.5
	monkeypatch.setattr(cs, "SENSIBILITE_CHARGE_DEFAUT", 0.25)
	assert cm.sensibilite_de(_sort()) == 0.25


def test_un_zero_ECRIT_reste_un_zero():
	# Piège classique : tester la véracité au lieu de la présence ferait retomber un
	# « insensible » explicite sur le défaut du monde, silencieusement.
	assert cm.sensibilite_de(_sort(sensibilite_charge=0)) == 0.0
	assert cm.sensibilite_de(_sort(sensibilite_charge=0.0)) == 0.0


def test_sensibilite_clampee_et_illisible_tolérée():
	assert cm.sensibilite_de(_sort(sensibilite_charge=5)) == 1.0
	assert cm.sensibilite_de(_sort(sensibilite_charge=-3)) == 0.0
	assert cm.sensibilite_de(_sort(sensibilite_charge="beaucoup")) == cs.SENSIBILITE_CHARGE_DEFAUT


# ── 9. Objet qui réduit l'effet de la charge ─────────────────────────────────────

def test_aide_a_la_canalisation_reduit_la_penalite():
	nu = cm.penalite_finale(1.0, _sort(sensibilite_charge=1))
	robe = cm.penalite_finale(1.0, _sort(sensibilite_charge=1), canalisation=50)
	assert robe == pytest.approx(nu * 0.5)
	assert cm.cout_pm_effectif(20, robe) < cm.cout_pm_effectif(20, nu)


def test_la_charge_ne_peut_JAMAIS_etre_entierement_annulee():
	# L'invariante qui protège l'arbitrage : un objet ne doit pas rendre le poids gratuit.
	assert cm.modificateur_de(100) > 0
	assert cm.modificateur_de(10 ** 6) > 0
	pen = cm.penalite_finale(1.5, _sort(sensibilite_charge=1), canalisation=10 ** 6)
	assert pen > 0


def test_aide_bornee_par_le_reglage_du_monde(monkeypatch):
	monkeypatch.setattr(cs, "CANALISATION_REDUCTION_MAX", 30)
	assert cm.modificateur_de(90) == pytest.approx(0.7)   # rabotée à 30 %


def test_penalite_jamais_negative():
	assert cm.penalite_finale(0.0, _sort(), canalisation=99) == 0.0


# ── 10. Capacité augmentée temporairement — l'anti-exploit ───────────────────────

def test_la_capacite_PHYSIQUE_n_est_jamais_buffee(monkeypatch):
	"""Le cœur du montage : un buff n'ouvre PAS la limite de portage (CLAUDE.md §3).

	`etat_porteur` mesure contre `characters.charge_max_of`, qui lit `caracteristiques_current`
	BRUT. Un effet actif de Force ne doit donc rien changer au ratio — la ceinture de force
	agit sur la CANALISATION, pas sur le sac."""
	from utils.characters import charge_max_of

	nu = {"caracteristiques_current": {"F": 20}, "inventaire": [], "slots": {}}
	buffe = {
		"caracteristiques_current": {"F": 20},
		"inventaire": [], "slots": {},
		"effets_actifs": [{"nom": "Potion de force", "buffs": {"F": 40}, "restants": 5}],
	}
	assert charge_max_of(nu) == charge_max_of(buffe)
	assert cm.etat_porteur(nu)[0] == cm.etat_porteur(buffe)[0]


def test_l_aide_a_la_canalisation_elle_passe_bien_par_les_buffs():
	# Le pendant du test précédent : ce qu'un buff PEUT faire.
	perso = {
		"caracteristiques_current": {"F": 20}, "inventaire": [], "slots": {},
		"effets_actifs": [{"nom": "Encens", "canalisation": 40, "restants": 5}],
	}
	assert cm.etat_porteur(perso)[1] == 40


# ── 11. L'inventaire bouge → tout se recalcule ───────────────────────────────────

def test_rien_n_est_fige_quand_l_inventaire_change():
	perso = {"caracteristiques_current": {"F": 20},
			 "slots": {}, "inventaire": [{"item": "item:Enclume", "poids": 60.0}]}
	charge_avant = cm.charge_magique_portee(perso)
	perso["inventaire"] = []
	assert cm.charge_magique_portee(perso) == 0.0 < charge_avant


def test_l_equipement_porte_compte_autant_que_le_sac():
	# Miroir de `characters.carried_weight` : porter n'allège pas.
	sac = {"inventaire": [{"item": "item:Plates", "poids": 30.0}], "slots": {}}
	porte = {"inventaire": [], "slots": {"torse": {"item": "item:Plates", "poids": 30.0}}}
	assert cm.charge_magique_portee(sac) == cm.charge_magique_portee(porte) == 30.0


# ── Poids magique par objet (`charge_magique`) ───────────────────────────────────

def test_item_sans_coefficient_pese_son_poids_physique():
	# Aucune migration : tant qu'aucun doc ne porte le champ, charge magique == poids.
	perso = {"inventaire": [{"item": "item:Fer", "poids": 10.0}], "slots": {}}
	docs = {"item:Fer": {"_id": "item:Fer"}}
	assert cm.charge_magique_portee(perso, docs.get) == 10.0


def test_sac_dimensionnel_et_artefact_pesant():
	perso = {"slots": {}, "inventaire": [
		{"item": "item:Sac_dimensionnel", "poids": 10.0},
		{"item": "item:Couronne", "poids": 1.0},
	]}
	docs = {
		"item:Sac_dimensionnel": {"_id": "item:Sac_dimensionnel", "charge_magique": 0.1},
		"item:Couronne": {"_id": "item:Couronne", "charge_magique": 8.0},
	}
	# 10 × 0,1 + 1 × 8 = 9 « kilos magiques » pour 11 kilos réels.
	assert cm.charge_magique_portee(perso, docs.get) == pytest.approx(9.0)


def test_coefficient_borne_et_illisible_tolere():
	assert cm.coefficient_item({"charge_magique": 10 ** 9}) == cs.CHARGE_MAGIQUE_COEF_MAX
	assert cm.coefficient_item({"charge_magique": -4}) == 0.0
	assert cm.coefficient_item({"charge_magique": "lourd"}) == 1.0
	assert cm.coefficient_item(None) == 1.0
	assert cm.coefficient_item({}) == 1.0


def test_sans_resolveur_la_charge_magique_est_le_poids():
	# Le repli assumé des sites qui n'ont pas le droit de lire la base.
	perso = {"inventaire": [{"item": "item:Couronne", "poids": 1.0}], "slots": {}}
	assert cm.charge_magique_portee(perso, None) == 1.0


# ── 12. Charge + effet actif : les deux sources se composent ─────────────────────

def test_charge_et_aide_se_composent_sans_double_comptage():
	perso = {
		"caracteristiques_current": {"F": 20},      # charge_max = 100
		"slots": {}, "inventaire": [{"item": "item:Lingots", "poids": 100.0}],
		"effets_actifs": [{"nom": "Encens", "canalisation": 50, "restants": 3}],
	}
	ratio, canal = cm.etat_porteur(perso)
	assert ratio == pytest.approx(1.0)
	assert canal == 50
	# Une seule application de chaque facteur : ratio → pénalité, × sensibilité, × modif.
	attendu = cm.penalite_charge(1.0) * 1.0 * 0.5
	assert cm.penalite_finale(ratio, _sort(sensibilite_charge=1), canal) == pytest.approx(attendu)


def test_aides_temporaires_non_cumulees_mais_equipement_additif():
	# Miroir exact de la règle d'`esquive` (non-cumul entre effets, additif ailleurs).
	from utils.consommables import canalisation_bonus

	perso = {
		"effets_actifs": [{"nom": "A", "canalisation": 10, "restants": 3},
						  {"nom": "B", "canalisation": 25, "restants": 3}],
		"equipment_bonus": {"canalisation": 5},
		"competences_bonus": {"canalisation": 7},
	}
	assert canalisation_bonus(perso) == 25 + 5 + 7


# ── 13. Sort maintenu sous forte charge ──────────────────────────────────────────

def test_l_entretien_d_un_sort_maintenu_monte_avec_la_charge():
	leger = cm.penalite_finale(0.2, _sort(sensibilite_charge=1))
	lourd = cm.penalite_finale(1.3, _sort(sensibilite_charge=1))
	assert cm.maintien_effectif(4, leger) == 4
	assert cm.maintien_effectif(4, lourd) > 4


def test_un_maintien_nul_le_reste_et_un_maintien_reel_ne_tombe_jamais_a_zero():
	# Un entretien qui tomberait à 0 ferait cesser le sort d'être maintenu.
	assert cm.maintien_effectif(0, 2.0) == 0
	assert cm.maintien_effectif(1, 0.0) == 1


# ── 14. L'hybride lourd : pénalisé, jamais interdit ──────────────────────────────

def test_un_guerrier_barde_peut_TOUJOURS_lancer():
	"""La règle cardinale : la charge renchérit, elle n'interdit pas. Aucun ratio, aussi
	absurde soit-il, ne doit rendre un coût infini ni négatif."""
	for ratio in (0.0, 1.0, 5.0, 100.0, 10 ** 6):
		cout = cm.cout_pm_effectif(12, cm.penalite_finale(ratio, _sort(sensibilite_charge=1)))
		assert 12 <= cout < 10 ** 6
		assert isinstance(cout, int)


def test_le_cout_ne_descend_jamais_sous_la_base():
	for ratio in (0.0, 0.5, 1.0, 3.0):
		pen = cm.penalite_finale(ratio, _sort())
		assert cm.cout_pm_effectif(7, pen) >= 7


# ── Cas limites de la spec §15 ───────────────────────────────────────────────────

@pytest.mark.parametrize("capacite", [0, 0.0, None, "", "abc", -5])
def test_capacite_invalide_ne_penalise_rien(capacite):
	# Un porteur sans capacité valide (doc abîmé, fixture, monture sans espèce) garde sa
	# magie intacte : refuser de canaliser sur une donnée manquante serait le pire choix.
	assert cm.ratio_charge(50, capacite) == 0.0


def test_poids_nul_et_inventaire_absent():
	assert cm.ratio_charge(0, 100) == 0.0
	assert cm.charge_magique_portee({}) == 0.0
	assert cm.charge_magique_portee({"inventaire": None, "slots": None}) == 0.0


def test_cout_nul_d_une_competence_martiale_reste_nul():
	# Beaucoup de compétences de vocation ne coûtent rien : les renchérir ferait payer la
	# charge à des gestes purement martiaux.
	assert cm.cout_pm_effectif(0, 2.0) == 0


def test_arrondi_au_plus_proche_et_non_au_superieur():
	# Au supérieur, la moindre gêne coûtait un PM plein et la franchise devenait une
	# falaise — c'est le choix d'arrondi qui rend la courbe utilisable.
	assert cm.cout_pm_effectif(10, 0.02) == 10      # 10,2 → 10
	assert cm.cout_pm_effectif(10, 0.06) == 11      # 10,6 → 11
	# `floor(x+0.5)` et non `round()` : ce dernier arrondit les demis au pair.
	assert cm.cout_pm_effectif(10, 0.05) == 11      # 10,5 → 11 (et non 10)
	assert cm.cout_pm_effectif(3, 0.5) == 5         # 4,5 → 5  (et non 4)


def test_interrupteur_general(monkeypatch):
	# Le filet de sécurité d'équilibrage : PEN_MAX à 0 éteint toute la mécanique, sans
	# toucher une ligne de code ni redémarrer.
	monkeypatch.setattr(cs, "CHARGE_MAGIE_PEN_MAX", 0.0)
	for ratio in (0.5, 1.0, 3.0):
		assert cm.penalite_charge(ratio) == 0.0
		assert cm.cout_pm_effectif(10, cm.penalite_finale(ratio, _sort())) == 10


def test_palier_sur_une_table_vide(monkeypatch):
	# La table est réglable à chaud : vidée, tout retombe sur « surcharge », ce qui reste
	# lisible — et surtout ne lève pas.
	monkeypatch.setattr(cs, "CHARGE_MAGIE_PALIERS", {})
	assert cm.palier(0.0) == cm.PALIER_SURCHARGE


def test_chaque_palier_a_son_libelle():
	# Relu depuis la table, jamais énuméré à la main : enrichir `CHARGE_MAGIE_PALIERS`
	# sans poser le libellé afficherait un slug brut à l'écran.
	for nom in list(cs.CHARGE_MAGIE_PALIERS) + [cm.PALIER_SURCHARGE]:
		assert nom in cm.PALIER_LABELS, nom
	# Un nom inconnu ne casse rien : il se rend tel quel plutôt que de lever.
	assert cm.palier_label("palier_invente") == "palier_invente"


# ── Payload ──────────────────────────────────────────────────────────────────────

def test_bloc_charge_porte_tout_ce_que_l_interface_affiche():
	bloc = cm.bloc_charge(75.0, 100, 20)
	assert bloc["charge"] == 75.0 and bloc["charge_max"] == 100
	assert bloc["ratio"] == pytest.approx(0.75)
	assert bloc["palier"] == "importante"
	assert bloc["palier_label"] == cm.PALIER_LABELS["importante"]
	assert bloc["canalisation"] == 20
	assert bloc["penalite"] == pytest.approx(cm.penalite_charge(0.75), abs=1e-4)
	assert bloc["modificateur"] == pytest.approx(0.8)


def test_bloc_charge_sur_un_porteur_sans_capacite():
	bloc = cm.bloc_charge(10.0, 0)
	assert bloc["ratio"] == 0.0 and bloc["penalite"] == 0.0
	assert bloc["palier"] == "legere"


# ── Branchement MOTEUR : la garde et le débit lisent le même tarif ───────────────

from _fixtures_magie import combat, joueur, monstre, sort  # noqa: E402


def _mage_charge(pm=60, charge=0.0, capacite=100):
	m = joueur(pm=pm)
	m["charge_max"] = capacite
	m["charge"] = m["charge_magique"] = charge
	return m


def test_le_cout_de_lancement_monte_avec_la_charge():
	from utils.combat import resolve_action

	nu, barde = _mage_charge(), _mage_charge(charge=100.0)
	trait = dict(cout_pm=10, cible="ennemi", portee=5, nom="Trait",
				 effets={"degats": "1D6"}, sensibilite_charge=1)
	for mage in (nu, barde):
		doc = combat([mage], [monstre(0)])
		resolve_action(doc, "sort", sort=sort(**trait), cible_id="monstre_0")
	assert 60 - nu["currentPM"] == 10
	assert 60 - barde["currentPM"] > 10


def test_la_garde_PM_et_le_debit_lisent_le_MEME_tarif():
	"""Le piège que la fonction partagée évite : proposer un sort à un prix et le débiter
	à un autre — ou pire, laisser partir un sort qu'on ne peut plus payer."""
	from utils.combat import resolve_action

	# 12 PM en poche pour un sort à 10 PM de base : payable à vide, pas sous la charge.
	mage = _mage_charge(pm=12, charge=100.0)
	doc = combat([mage], [monstre(0)])
	res = resolve_action(doc, "sort", sort=sort(
		cout_pm=10, cible="ennemi", portee=5, nom="Trait", effets={"degats": "1D6"},
		sensibilite_charge=1), cible_id="monstre_0")
	assert res.get("error") == "PM insuffisants."
	assert mage["currentPM"] == 12, "un refus ne débite rien"


def test_l_incantation_longue_FIGE_son_tarif_a_l_engagement():
	"""Seule entorse au « jamais stocké », et elle est voulue : une incantation absorbe
	tout le budget du lanceur et ne s'abandonne pas. On paie le tarif du moment où l'on
	s'engage — pas celui du butin ramassé trois tours plus tard."""
	from utils.combat import _armer_incantation

	meteore = sort(cout_pm=30, incantation=3, cible="ennemi", portee=5, nom="Météore",
				   effets={"degats": "4D6"}, sensibilite_charge=1)

	# Armée à vide : tarif de base. (On appelle `_armer_incantation` directement — via
	# `resolve_action`, le sort se résoudrait dans le tour même et le bloc disparaîtrait.)
	nu = _mage_charge(pm=90, charge=0.0)
	# 1 seul PA de budget : l'armement en verse un et le bloc SURVIT au tour (avec un
	# budget plein, les 3 PA partiraient d'un coup et le sort se résoudrait aussitôt).
	nu["actions_max"] = nu["actions_restantes"] = 1
	doc = combat([nu], [monstre(0)])
	_armer_incantation(doc, nu, meteore["doc"], meteore["effets"], "monstre_0", 0, 0)
	fige = nu["incantation"]["pm_total"]
	assert fige == 30

	# Se charger APRÈS l'engagement ne renchérit pas ce qui est déjà commencé.
	nu["charge"] = nu["charge_magique"] = 100.0
	assert nu["incantation"]["pm_total"] == fige

	# Mais s'engager DÉJÀ chargé se paie, et se paie d'emblée.
	barde = _mage_charge(pm=90, charge=100.0)
	barde["actions_max"] = barde["actions_restantes"] = 1
	doc2 = combat([barde], [monstre(0)])
	_armer_incantation(doc2, barde, meteore["doc"], meteore["effets"], "monstre_0", 0, 0)
	assert barde["incantation"]["pm_total"] > fige
