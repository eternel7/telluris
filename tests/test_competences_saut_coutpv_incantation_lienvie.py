# tests/test_competences_saut_coutpv_incantation_lienvie.py
#
# LES QUATRE MÉCANIQUES OUVERTES AUX COMPÉTENCES : saut, coût en PV, incantation longue
# et lien de vie. Elles existaient pour les sorts seuls — non par choix de conception mais
# parce que leur résolution vivait dans `_lancer_sort`, un chemin que les compétences
# n'empruntaient pas.
#
# ⚠️ Trois d'entre elles étaient le PIRE des silences : `_bonus_dict` normalisait déjà
# `saut`, `cout_pv` et `lien_vie` pour les compétences, et `capacite_utilisable_combat` en
# acceptait même deux. Une compétence qui en portait partait en base, s'utilisait sans la
# moindre erreur, et ne faisait rien.
#
# Ce fichier vérifie le comportement COMPÉTENCE. Le comportement SORT est déjà verrouillé
# par test_combat_saut / test_combat_lien_vie / test_combat_incantation / test_sorts_temps ;
# ce qu'on éprouve ici, c'est que le chokepoint partagé (`_lancer_capacite`) donne bien le
# même résultat des deux côtés.

import pytest

from utils import combat as combat_mod
from utils.combat import _rediriger_lien_vie, _reset_turn_budget, resolve_action
from utils.competences import normaliser_competence
from utils.sorts import est_incantation_longue
from _fixtures_magie import combat, joueur, monstre, sort


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def comp(**champs):
	doc = {"_id": "competence:essai", "type": "competence", "vocation": "assassin",
		   "nom": "Essai", "mode": "active", "cout_pm": 0, "portee": 1, **champs}
	return normaliser_competence(doc)


# ── SAUT ────────────────────────────────────────────────────────────────────────

def test_une_competence_de_saut_teleporte_son_porteur():
	perso = joueur(x=3, y=5)
	doc = combat([perso], [monstre(x=10, y=8)])

	res = resolve_action(doc, "competence", dx=6, dy=5,
						 competence=comp(cible="soi", portee=6, effets={"saut": 4}))

	assert "error" not in res
	assert perso["pos"] == {"x": 6, "y": 5}
	assert res["saut"]["de"] == {"x": 3, "y": 5}
	assert res["saut"]["vers"] == {"x": 6, "y": 5}


def test_le_saut_d_une_competence_franchit_un_mur_comme_celui_d_un_sort():
	"""La raison d'être du saut : aucune ligne de vue, aucun chemin praticable exigé."""
	perso = joueur(x=3, y=5)
	doc = combat([perso], [monstre(x=10, y=8)])
	for y in range(9):
		doc["grid"]["cells"][y][5] = 0

	resolve_action(doc, "competence", dx=6, dy=5,
				   competence=comp(cible="soi", portee=6, effets={"saut": 4}))
	assert perso["pos"] == {"x": 6, "y": 5}


def test_une_destination_invalide_ne_coute_RIEN():
	"""⚠️ Le saut est validé AVANT le moindre débit : une case refusée ne doit pas manger
	les PM ni l'action. Même garde que pour les sorts."""
	perso = joueur(x=3, y=5, pm=60)
	doc = combat([perso], [monstre(x=10, y=8)])
	pa_avant = perso["actions_restantes"]

	res = resolve_action(doc, "competence", dx=99, dy=99,
						 competence=comp(cible="soi", portee=6, cout_pm=9,
										 effets={"saut": 4}))

	assert "error" in res
	assert perso["pos"] == {"x": 3, "y": 5}
	assert perso["currentPM"] == 60, "les PM ne doivent pas être débités"
	assert perso["actions_restantes"] == pa_avant


# ── COÛT EN PV ──────────────────────────────────────────────────────────────────

def test_une_competence_peut_se_payer_en_PV():
	perso = joueur(x=3, y=5, pv=100)
	perso["currentPV"] = 60
	doc = combat([perso], [monstre(x=10, y=8)])

	resolve_action(doc, "competence",
				   competence=comp(cible="soi", effets={"pm": 1, "cout_pv": 7}))

	assert perso["currentPV"] == 53


def test_le_cout_en_PV_ne_peut_pas_assommer_son_auteur():
	"""⚠️ Garde `>` STRICTE, reprise des sorts : une capacité qui met son porteur à terre
	par sa seule facture ouvrirait une condition de défaite absurde."""
	perso = joueur(x=3, y=5)
	perso["currentPV"] = 7
	doc = combat([perso], [monstre(x=10, y=8)])

	res = resolve_action(doc, "competence",
						 competence=comp(cible="soi", effets={"pm": 1, "cout_pv": 7}))

	assert "error" in res
	assert perso["currentPV"] == 7


def test_des_PV_depenses_ne_sont_pas_des_degats_subis():
	"""Ni test de concentration, ni furtivité rompue : c'est un coût, pas un coup."""
	perso = joueur(x=3, y=5)
	perso["currentPV"] = 60
	perso["furtif"] = True
	doc = combat([perso], [monstre(x=10, y=8)])

	resolve_action(doc, "competence",
				   competence=comp(cible="soi", effets={"pm": 1, "cout_pv": 7}))

	assert perso["currentPV"] == 53
	assert perso["furtif"] is True


# ── LIEN DE VIE ─────────────────────────────────────────────────────────────────

def test_une_competence_peut_tisser_un_lien_de_vie():
	protecteur = joueur(0, x=3, y=5, nom="Paladin")
	protege = joueur(1, x=4, y=5, nom="Écuyer")
	doc = combat([protecteur, protege], [monstre(x=9, y=5)])

	res = resolve_action(doc, "competence", cible_id="joueur_1",
						 competence=comp(cible="allie", portee=4,
										 effets={"lien_vie": {"part": 50, "reduction": 0}}))

	assert "error" not in res
	# ⚠️ Le bloc vit sur le PROTÉGÉ (c'est lui qui encaisse) ; `protecteur_id` désigne le
	# porteur, et `source_id` la CAPACITÉ qui l'a tissé — ici une compétence, pas un sort.
	assert protege["lien_vie"]["part"] == 50
	assert protege["lien_vie"]["protecteur_id"] == "joueur_0"
	assert protege["lien_vie"]["source_id"] == "competence:essai"
	assert "lien_vie" not in protecteur


def test_le_lien_d_une_competence_redirige_vraiment_les_degats():
	protecteur = joueur(0, x=3, y=5, nom="Paladin", pv=100)
	protege = joueur(1, x=4, y=5, nom="Écuyer", pv=100)
	doc = combat([protecteur, protege], [monstre(x=9, y=5)])
	resolve_action(doc, "competence", cible_id="joueur_1",
				   competence=comp(cible="allie", portee=4,
								   effets={"lien_vie": {"part": 50, "reduction": 0}}))

	pour_cible, pour_protecteur, trouve = _rediriger_lien_vie(doc, protege, 20)

	# 20 dégâts à 50 % : dix pour chacun. Aucun dégât n'est CRÉÉ.
	assert (pour_cible, pour_protecteur) == (10, 10)
	assert pour_cible + pour_protecteur == 20
	assert trouve is protecteur


# ── INCANTATION LONGUE ──────────────────────────────────────────────────────────

def test_une_competence_porte_desormais_l_incantation():
	assert comp(incantation=4)["incantation"] == 4
	assert comp()["incantation"] == 1, "défaut NEUTRE : aucune migration"
	assert est_incantation_longue(comp(incantation=4))
	assert not est_incantation_longue(comp())


def test_une_incantation_longue_de_competence_s_arme_au_lieu_de_partir():
	"""Elle ne part pas : elle devient un état du snapshot, que les tours font progresser."""
	archer = joueur(0, x=3, y=5, pm=60)
	second = joueur(1, x=3, y=6)          # ⚠️ sinon le tour du canalisateur boucle seul
	loup = monstre(x=8, y=5)
	doc = combat([archer, second], [loup])

	res = resolve_action(doc, "competence", cible_id="monstre_0",
						 competence=comp(cible="ennemi", jet="cd", portee=8, cout_pm=12,
										 incantation=9, effets={"degats": "2D8"}))

	assert "error" not in res
	assert loup["currentPV"] == loup["pv_max"], "la compétence n'est pas encore partie"
	bloc = res["incantation"]
	assert bloc["pa_total"] == 9
	assert bloc["pa_investis"] == 4, "tous les PA du tour y passent"
	# ⚠️ Le TYPE est mémorisé : la résolution a lieu des tours plus tard, depuis
	# `_reset_turn_budget`, qui n'a aucun moyen de redeviner de quoi il s'agit.
	assert bloc["kind"] == "competence"


def test_les_PM_d_une_incantation_de_competence_partent_par_TRANCHES():
	archer = joueur(0, x=3, y=5, pm=60)
	second = joueur(1, x=3, y=6)
	doc = combat([archer, second], [monstre(x=8, y=5)])

	resolve_action(doc, "competence", cible_id="monstre_0",
				   competence=comp(cible="ennemi", jet="cd", portee=8, cout_pm=12,
								   incantation=9, effets={"degats": "2D8"}))

	# tranche = ceil(12 / 9) = 2 PM par PA, 4 PA versés ⇒ 8 PM
	assert archer["currentPM"] == 52
	assert archer["incantation"]["pm_verses"] == 8


def test_une_incantation_de_competence_va_jusqu_au_bout_et_frappe():
	archer = joueur(0, x=3, y=5, pm=60)
	second = joueur(1, x=3, y=6)
	loup = monstre(x=8, y=5)
	doc = combat([archer, second], [loup])
	resolve_action(doc, "competence", cible_id="monstre_0",
				   competence=comp(cible="ennemi", jet="cd", portee=8, cout_pm=12,
								   incantation=9, effets={"degats": "2D8"}))

	for tour in (2, 3):
		archer["actions_restantes"] = 0
		doc["tour"] = tour
		_reset_turn_budget(archer, doc)

	assert archer.get("incantation") is None, "9 PA versés : elle a abouti"
	assert loup["currentPV"] < loup["pv_max"], "et elle a frappé"


def test_commencer_une_incantation_ne_consomme_PAS_le_compteur_de_competences():
	"""⚠️ Ses PA sont déjà décomptés un par un par `canalisation` : l'ajouter ferait payer
	une action de plus le tour où le porteur se contente de commencer."""
	archer = joueur(0, x=3, y=5, pm=60)
	second = joueur(1, x=3, y=6)
	doc = combat([archer, second], [monstre(x=8, y=5)])

	resolve_action(doc, "competence", cible_id="monstre_0",
				   competence=comp(cible="ennemi", jet="cd", portee=8, cout_pm=12,
								   incantation=9, effets={"degats": "2D8"}))

	assert archer.get("competences", 0) == 0


def test_une_seule_incantation_a_la_fois_tous_types_confondus():
	"""Sort et compétence partagent le MÊME emplacement (`joueur["incantation"]`) : en
	commencer une pendant l'autre est refusé, quel que soit le type de la première.

	⚠️ On remet l'archer comme acteur courant : sinon son tour est déjà passé et c'est son
	compagnon — qui n'incante rien — que `resolve_action` ferait jouer."""
	archer = joueur(0, x=3, y=5, pm=60)
	second = joueur(1, x=3, y=6)
	doc = combat([archer, second], [monstre(x=8, y=5)])
	resolve_action(doc, "competence", cible_id="monstre_0",
				   competence=comp(cible="ennemi", jet="cd", portee=8, cout_pm=12,
								   incantation=9, effets={"degats": "2D8"}))
	assert archer["incantation"]["kind"] == "competence"

	doc["acteur_courant_index"] = doc["ordre_initiative"].index("joueur_0")
	archer["actions_restantes"] = 2
	res = resolve_action(doc, "sort", cible_id="monstre_0",
						 sort=sort(cout_pm=6, cible="ennemi", portee=8, incantation=4,
								   effets={"degats": "1D6"}))
	assert res["error"] == "Une incantation est déjà en cours."
