# tests/test_combat_maintien.py
#
# SORTS MAINTENUS : « Le sort est lancé normalement et son coût initial en PM est payé. À
# chaque round, le jeteur doit dépenser le coût de maintien en PM. Tant qu'il peut payer ce
# coût, le sort reste actif. Le maintien ne consomme pas de PA et n'empêche pas le jeteur
# de lancer d'autres sorts. »
#
# Le piège central que ce fichier verrouille : l'entrée d'`effets_actifs` d'un sort
# maintenu ne se DÉCRÉMENTE PAS. Sa durée n'est pas un compte à rebours mais la capacité de
# son lanceur à payer — sinon le sort tomberait au bout de `duree` tours alors même que le
# mage paie, ce qui est exactement ce que « sort maintenu » exclut.

import pytest

from utils import combat as combat_mod
from utils.combat import (
	_effets_a_reverser, _payer_maintiens, _reset_turn_budget, _rompre_concentration,
	resolve_action,
)
from _fixtures_magie import combat, joueur, monstre, sort, textes


BOUCLIER = dict(cout_pm=5, maintien=4, cible="soi", nom="Bouclier magique", icon="🛡",
				effets={"buffs": {"R": 10}})


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _tour(doc, acteur, tour):
	doc["tour"] = tour
	_reset_turn_budget(acteur, doc)


# ── Pose ────────────────────────────────────────────────────────────────────────

def test_un_sort_maintenu_s_inscrit_dans_les_concentrations():
	mage = joueur(pm=30)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))

	assert [c["sort_id"] for c in mage["concentrations"]] == ["sort:essai"]
	assert mage["concentrations"][0]["maintien"] == 4
	assert mage["currentPM"] == 25, "seul le coût de LANCEMENT est payé au lancement"


def test_un_sort_maintenu_sans_duree_pose_quand_meme_sa_chip():
	"""Un Mur de feu ou un Lien de vie n'a aucun buff propre — son effet vit ailleurs —
	mais il doit se voir, sans quoi le joueur paierait pour de l'invisible."""
	mage = joueur(pm=30)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(cout_pm=5, maintien=3, cible="soi",
										  effets={"pv": 1}))
	chips = mage["effets_actifs"]
	assert len(chips) == 1
	assert chips[0]["maintenu"] is True
	assert chips[0]["maintien"] == 3


def test_un_sort_ordinaire_n_entretient_rien():
	mage = joueur(pm=30)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(cout_pm=5, cible="soi",
										  effets={"buffs": {"R": 10}, "duree": 3}))
	assert not mage.get("concentrations")
	assert not mage["effets_actifs"][0].get("maintenu")


# ── Prélèvement round après round ───────────────────────────────────────────────

def test_l_entretien_est_preleve_au_debut_de_chaque_tour_du_lanceur():
	mage = joueur(pm=30)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	assert mage["currentPM"] == 25

	for tour, attendu in ((2, 21), (3, 17), (4, 13)):
		_tour(doc, mage, tour)
		assert mage["currentPM"] == attendu
		assert mage["concentrations"], "le sort tient tant qu'il est payé"


def test_l_entretien_ne_coute_aucun_pa():
	"""« Le maintien ne consomme pas de PA et n'empêche pas le jeteur de lancer d'autres
	sorts. »"""
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	_tour(doc, mage, 2)
	assert mage["actions_restantes"] == mage["actions_max"]


def test_la_duree_d_un_sort_maintenu_ne_se_decremente_jamais():
	"""⚠️ LE piège du système : `restants` doit rester figé tant que le mage paie."""
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(cout_pm=5, maintien=2, cible="soi",
										  effets={"buffs": {"R": 10}, "duree": 1}))
	restants_initial = mage["effets_actifs"][0]["restants"]
	for tour in (2, 3, 4, 5, 6):
		_tour(doc, mage, tour)
	assert mage["effets_actifs"], "un effet maintenu ne doit pas avoir expiré"
	assert mage["effets_actifs"][0]["restants"] == restants_initial


def test_un_effet_ORDINAIRE_continue_de_se_decrementer():
	"""Non-régression : la clause `maintenu` ne doit pas geler tous les effets."""
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(cout_pm=5, cible="soi",
										  effets={"buffs": {"R": 10}, "duree": 3}))
	_tour(doc, mage, 2)
	assert mage["effets_actifs"][0]["restants"] == 2


# ── Chute faute de PM ───────────────────────────────────────────────────────────

def test_le_sort_tombe_quand_le_lanceur_ne_peut_plus_payer():
	mage = joueur(pm=8)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	assert mage["currentPM"] == 3        # 8 − 5, il ne reste pas les 4 du maintien

	_tour(doc, mage, 2)
	assert not mage.get("concentrations")
	assert not mage["effets_actifs"], "l'effet part avec la concentration"
	assert mage["currentPM"] == 3, "rien n'est prélevé quand on ne peut pas payer"
	assert any("n'a plus les 4 PM du maintien" in t for t in textes(doc))


def test_les_derivees_suivent_la_chute():
	"""Le buff de R gonflait `pv_max` : il doit redescendre dès que le sort tombe.

	⚠️ Le repère est un mage IDENTIQUE resté nu, et non la valeur du snapshot avant le
	sort : `_refresh_snapshot_stats` recompose les dérivées depuis `caracts_base`, donc
	elle écrase ce que la fixture avait posé à la main."""
	from utils.combat import _refresh_snapshot_stats
	temoin = joueur(pm=8)
	_refresh_snapshot_stats(temoin)
	pv_max_nu = temoin["pv_max"]

	mage = joueur(pm=8)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	assert mage["pv_max"] > pv_max_nu, "le buff de R doit gonfler les PV max"

	_tour(doc, mage, 2)
	assert mage["pv_max"] == pv_max_nu


def test_chacun_est_tente_dans_l_ordre_de_pose():
	"""⚠️ Le premier impayable tombe, les SUIVANTS — moins chers — peuvent encore tenir :
	faire tomber toute la file punirait le mage prévoyant qui garde un petit sort."""
	mage = joueur(pm=100)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(cout_pm=1, maintien=40, cible="soi",
										  _id="sort:cher", nom="Cher",
										  effets={"buffs": {"R": 5}}))
	resolve_action(doc, "sort", sort=sort(cout_pm=1, maintien=2, cible="soi",
										  _id="sort:modeste", nom="Modeste",
										  effets={"buffs": {"Ag": 5}}))
	mage["currentPM"] = 10               # de quoi payer le modeste, pas le cher

	_tour(doc, mage, 2)
	tenus = [c["sort_id"] for c in mage["concentrations"]]
	assert tenus == ["sort:modeste"]
	assert mage["currentPM"] == 8


# ── Arrêt volontaire ────────────────────────────────────────────────────────────

def test_on_peut_cesser_d_entretenir_un_sort():
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))

	res = resolve_action(doc, "interrompre", cible_id="sort:essai")
	assert res["interrompu"] is True
	assert not mage.get("concentrations")
	assert not mage["effets_actifs"]


def test_cesser_est_gratuit():
	"""Faire payer la sortie enfermerait un mage dans son sort jusqu'à épuisement."""
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	avant = mage["actions_restantes"]
	resolve_action(doc, "interrompre", cible_id="sort:essai")
	assert mage["actions_restantes"] == avant


def test_interrompre_un_sort_qu_on_n_entretient_pas_est_refuse():
	mage = joueur(pm=60)
	doc = combat([mage])
	assert resolve_action(doc, "interrompre", cible_id="sort:inconnu")["error"] == (
		"Vous n'entretenez pas ce sort.")


# ── Relance : une source = une entrée ───────────────────────────────────────────

def test_relancer_le_meme_sort_ne_double_pas_l_entretien():
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	assert len(mage["concentrations"]) == 1
	assert len(mage["effets_actifs"]) == 1


# ── Sortie de combat ────────────────────────────────────────────────────────────

def test_un_effet_maintenu_ne_remonte_pas_sur_le_personnage():
	"""⚠️ Il n'y a pas de round en exploration : reversé tel quel, ce serait un buff
	permanent que plus rien ne prélève ni ne fait tomber — un exploit."""
	mage = joueur(pm=60)
	doc = combat([mage])
	resolve_action(doc, "sort", sort=sort(**BOUCLIER))
	resolve_action(doc, "sort", sort=sort(cout_pm=5, cible="soi", _id="sort:ordinaire",
										  effets={"buffs": {"Ag": 5}, "duree": 4}))

	reverses = _effets_a_reverser(mage)
	assert [e["source_id"] for e in reverses] == ["sort:ordinaire"]
	assert all("maintenu" not in e and "maintien" not in e for e in reverses)


# ── Sort maintenu OFFENSIF : l'effet vit sur la VICTIME ─────────────────────────

MUR_DE_FEU = dict(cout_pm=5, maintien=3, cible="ennemi", portee=6, nom="Mur de feu",
				  icon="🔥", effets={"degats": "2D6", "buffs": {"Ag": -10}, "duree": 2})


def test_le_lanceur_voit_ce_qu_il_paie_meme_quand_l_effet_est_ailleurs():
	"""⚠️ Un Mur de feu pose sa part durative sur ses VICTIMES : sans chip de suivi sur le
	lanceur, il paierait 3 PM par round pour quelque chose d'invisible — et sans pouvoir
	le relâcher, puisque la chip EST le bouton."""
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=8, y=5)])
	resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**MUR_DE_FEU))

	chips = [e for e in mage["effets_actifs"] if e.get("maintenu")]
	assert len(chips) == 1
	assert chips[0]["maintien"] == 3
	assert chips[0]["source_id"] == "sort:essai"


def test_rompre_retire_le_debuff_pose_sur_la_VICTIME():
	"""⚠️ Le vrai piège : `maintenu` exempte l'entrée du décrément, donc un débuff laissé
	sur un monstre après la chute du sort n'aurait JAMAIS été retiré par personne."""
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**MUR_DE_FEU))
	assert any(e.get("source_id") == "sort:essai" for e in loup["effets_actifs"])

	_rompre_concentration(doc, mage, mage["concentrations"][0], "Le mur s'éteint.")
	assert not any(e.get("source_id") == "sort:essai" for e in loup["effets_actifs"])
	assert not any(e.get("source_id") == "sort:essai" for e in mage["effets_actifs"])


def test_le_debuff_d_un_mur_ne_se_decremente_pas_non_plus():
	"""Il tient tant que le mage paie — comme la chip du lanceur."""
	mage = joueur(pm=60)
	loup = monstre(x=8, y=5)
	doc = combat([mage], [loup])
	resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**MUR_DE_FEU))
	entree = next(e for e in loup["effets_actifs"] if e.get("source_id") == "sort:essai")
	restants = entree["restants"]

	for tour in (2, 3, 4):
		doc["tour"] = tour
		_reset_turn_budget(loup, doc)
	assert entree["restants"] == restants


# ── Invocations tenues par une concentration ────────────────────────────────────

def test_une_invocation_maintenue_cesse_de_compter_ses_tours(monkeypatch):
	"""Deux horloges pour une seule créature, c'est la plus courte qui gagnerait."""
	SERVANT = {
		"_id": "espece:servant", "type": "espece", "nom": "Servant", "tags": [],
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 3), ("F", 20), ("R", 20), ("Ag", 20),
							 ("Vol", 10), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: {"espece:servant": SERVANT}.get(i))
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])
	resolve_action(doc, "sort", sort=sort(
		cout_pm=8, maintien=4, cible="soi", _id="sort:appel", nom="Appel",
		invocation={"espece": "espece:servant", "nombre": 1, "duree": 1}))

	creature = next(j for j in doc["joueurs"] if j.get("est_invocation"))
	assert creature["sort_maintenu"] == "sort:appel"
	restants = creature["invocation_restants"]
	combat_mod._run_invocation_turn(doc, creature, doc["grid"])
	assert creature["invocation_restants"] == restants, "le compteur est gelé"
	assert not creature.get("dissipe")


def test_rompre_la_concentration_dissipe_la_creature(monkeypatch):
	SERVANT = {
		"_id": "espece:servant", "type": "espece", "nom": "Servant", "tags": [],
		"base_attributes": {c: {"min": v, "max": v} for c, v in
							(("V", 3), ("F", 20), ("R", 20), ("Ag", 20),
							 ("Vol", 10), ("Int", 10), ("Cha", 10), ("Ch", 10))},
	}
	monkeypatch.setattr(combat_mod, "get_doc", lambda i: {"espece:servant": SERVANT}.get(i))
	mage = joueur(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])
	resolve_action(doc, "sort", sort=sort(
		cout_pm=8, maintien=4, cible="soi", _id="sort:appel", nom="Appel",
		invocation={"espece": "espece:servant", "nombre": 1, "duree": 5}))
	creature = next(j for j in doc["joueurs"] if j.get("est_invocation"))

	_rompre_concentration(doc, mage, mage["concentrations"][0], "L'appel se rompt.")
	assert creature["dissipe"] is True
	assert creature["currentPV"] == 0, "sa case doit redevenir libre"


# ── Une COMPÉTENCE maintenue se facture comme un sort ───────────────────────────

def test_une_competence_maintenue_est_bien_facturee():
	"""⚠️ Sans l'enregistrement de la concentration, `_empiler_effet_combat` posait une
	entrée `maintenu: True` — donc EXEMPTÉE du décrément — que rien ne facturait ni ne
	retirait jamais : un buff permanent et gratuit, c'est-à-dire un exploit."""
	from utils.competences import normaliser_competence
	mage = joueur(pm=30)
	doc = combat([mage])
	comp = normaliser_competence({
		"_id": "competence:garde", "type": "competence", "vocation": "guerrier",
		"nom": "Garde haute", "mode": "active", "cible": "soi", "cout_pm": 4,
		"maintien": 3, "effets": {"esquive": 10},
	})
	resolve_action(doc, "competence", competence=comp)
	assert [c["sort_id"] for c in mage["concentrations"]] == ["competence:garde"]
	assert mage["currentPM"] == 26

	_tour(doc, mage, 2)
	assert mage["currentPM"] == 23, "l'entretien est bien prélevé"
	mage["currentPM"] = 1
	_tour(doc, mage, 3)
	assert not mage.get("concentrations"), "et la garde tombe quand elle n'est plus payée"
	assert not mage["effets_actifs"]


# ── Le pseudo-doc du simulateur ─────────────────────────────────────────────────

def test_le_prelevement_tolere_le_pseudo_doc_du_simulateur():
	"""⚠️ `utils/simulateur` appelle `_reset_turn_budget(acteur, {"tour", "log"})` : ni
	`joueurs`, ni `monstres`, ni `ordre_initiative`. Toucher `combat_doc["joueurs"]`
	casserait /admin/simulateur, que les tests de combat ne couvrent pas."""
	acteur = joueur(pm=10)
	acteur["concentrations"] = [{"sort_id": "sort:x", "nom": "X", "icon": "✨",
								 "maintien": 3, "cible_id": ""}]
	pseudo = {"tour": 0, "log": []}
	_payer_maintiens(pseudo, acteur)
	assert acteur["currentPM"] == 7

	acteur["currentPM"] = 1
	_payer_maintiens(pseudo, acteur)          # doit tomber sans lever
	assert not acteur["concentrations"]


def test_reset_turn_budget_sans_doc_ne_leve_pas():
	acteur = joueur(pm=10)
	_reset_turn_budget(acteur)
	assert acteur["actions_restantes"] == acteur["actions_max"]
