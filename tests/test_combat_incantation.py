# tests/test_combat_incantation.py
#
# INCANTATION MULTI-ROUND : « Certains sorts nécessitent plusieurs Points d'Action pour
# être lancés. Lorsque leur coût dépasse les PA disponibles en un round, leur lancement se
# poursuit sur les rounds suivants. »
#
# Le cœur du fichier est l'exemple du livre de règles, joué à la virgule : un Météore de
# 15 PM demandant 6 PA, lancé par un mage à 3 PA par round, prend deux rounds, coûte 3 PM
# par action, et son DERNIER PA est gratuit (les 15 PM sont déjà versés).
#
# On y éprouve aussi ce qui casse silencieusement : le compteur `canalisation` (poser
# `actions_restantes = 0` serait écrasé au prochain recalcul), le tour qui doit passer
# SEUL sans rendre la main au client, et l'absence de boucle infinie quand il le fait.

import pytest

from utils import combat as combat_mod
from utils.combat import resolve_action, _reset_turn_budget, _resolve_until_player
from _fixtures_magie import combat, joueur, monstre, sort, textes


METEORE = dict(cout_pm=15, incantation=6, cible="ennemi", portee=8,
			   nom="Météore", effets={"degats": "4D6"})


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	"""Jet à 50 : hors fenêtre de critique, et sous un seuil large ⇒ tout touche."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def _mage(idx=0, **overrides):
	j = joueur(idx, **overrides)
	j["actions_max"] = j["actions_restantes"] = 3
	return j


def _tour_du_mage(doc, mage, tour):
	"""Rejoue le début du tour du mage — c'est là que l'incantation avance."""
	doc["tour"] = tour
	_reset_turn_budget(mage, doc)


# ── L'exemple du livre de règles ─────────────────────────────────────────────────

def test_meteore_quinze_pm_six_pa_trois_pa_par_round():
	"""15 PM / 6 PA à 3 PA par round : deux rounds, 3 PM par action, dernier PA gratuit."""
	mage = _mage(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])

	resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**METEORE))
	# ⚠️ Le premier round est joué DANS l'appel : trois PA entrent, le budget tombe à zéro,
	# et la queue de `resolve_action` enchaîne les tours jusqu'à ce que le sort parte.
	assert mage.get("incantation") is None, "l'incantation doit avoir abouti"
	assert mage["currentPM"] == 45, "exactement 15 PM, pas un de plus"


def test_les_pm_partent_par_tranches_de_trois():
	"""Round par round : 3 PA à 3 PM font 9 PM versés, pas les 15 d'un coup."""
	mage = _mage(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])
	# On arme sans laisser la queue enchaîner : un seul tour à la main.
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)

	inc = mage["incantation"]
	assert (inc["pa_investis"], inc["pm_verses"]) == (3, 9)
	assert mage["currentPM"] == 51
	assert mage["actions_restantes"] == 0, "les trois PA du tour y sont passés"


def test_le_dernier_pa_est_gratuit():
	"""5 PA couvrent les 15 PM ; le 6ᵉ — celui qui déclenche — ne coûte rien."""
	mage = _mage(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)

	_tour_du_mage(doc, mage, 2)   # PA 4, 5 (3 PM chacun) puis PA 6 (gratuit)
	assert mage.get("incantation") is None
	assert mage["currentPM"] == 45, "9 + 3 + 3 + 0 = 15"


def test_les_pa_investis_sont_conserves_d_un_round_a_l_autre():
	mage = _mage(pm=60)
	mage["actions_max"] = mage["actions_restantes"] = 2
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	assert mage["incantation"]["pa_investis"] == 2

	_tour_du_mage(doc, mage, 2)
	assert mage["incantation"]["pa_investis"] == 4, "les 2 PA du round 1 ne sont pas perdus"
	_tour_du_mage(doc, mage, 3)
	assert mage.get("incantation") is None, "6 PA atteints au troisième round"


def test_le_sort_frappe_vraiment_a_la_fin():
	mage = _mage(pm=60)
	loup = monstre(x=9, y=5)
	doc = combat([mage], [loup])
	resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**METEORE))
	assert loup["currentPV"] < 200
	assert any("Météore" in t for t in textes(doc))


def test_les_pa_restants_apres_le_lancement_sont_rejouables():
	"""4 PA par round, 6 PA de sort : le second round en dépense 3, il en reste un."""
	mage = _mage(pm=60)
	mage["actions_max"] = mage["actions_restantes"] = 4
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	assert mage["incantation"]["pa_investis"] == 4

	_tour_du_mage(doc, mage, 2)
	assert mage.get("incantation") is None
	assert mage["actions_restantes"] == 2, "4 PA − les 2 PA qui restaient à verser"


# ── Le budget est un COMPTEUR, jamais une affectation ───────────────────────────

def test_la_canalisation_est_un_compteur_que_le_recalcul_respecte():
	"""⚠️ `actions_restantes` est recalculé depuis les compteurs à ~15 endroits : poser 0
	à la main serait écrasé au premier `_refresh_actions` venu."""
	from utils.combat import _armer_incantation, _refresh_actions
	mage = _mage(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	assert mage["canalisation"] == 3
	_refresh_actions(mage)
	assert mage["actions_restantes"] == 0, "le recalcul doit RETROUVER le budget épuisé"


def test_la_canalisation_est_remise_a_zero_a_chaque_tour():
	mage = _mage(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	_tour_du_mage(doc, mage, 2)
	# L'incantation a abouti : le compteur ne doit pas traîner d'un tour sur l'autre.
	_tour_du_mage(doc, mage, 3)
	assert mage["canalisation"] == 0
	assert mage["actions_restantes"] == mage["actions_max"]


# ── Une seule incantation à la fois ─────────────────────────────────────────────

def test_on_ne_commence_pas_deux_incantations():
	"""« Pendant l'incantation, le jeteur ne peut pas commencer une autre incantation. »"""
	mage = _mage(pm=60)
	mage["actions_max"] = mage["actions_restantes"] = 1
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	mage["actions_restantes"] = 2   # on lui rend de quoi agir, pour isoler le refus

	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=sort(**METEORE))
	assert res["error"] == "Une incantation est déjà en cours."


# ── Échecs et abandon ───────────────────────────────────────────────────────────

def test_l_incantation_s_effondre_faute_de_pm_en_cours_de_route():
	mage = _mage(pm=10)          # de quoi payer 3 tranches, pas les 5
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)

	_tour_du_mage(doc, mage, 2)
	assert mage.get("incantation") is None
	assert any("PM" in t and "défait" in t for t in textes(doc))


def test_les_pm_deja_verses_sont_perdus_a_l_interruption():
	"""« Une interruption peut donc faire perdre les PM déjà dépensés. »"""
	mage = _mage(pm=60)
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation, _rompre_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	assert mage["currentPM"] == 51

	_rompre_incantation(doc, mage, "Le mage renonce.")
	assert mage.get("incantation") is None
	assert mage["currentPM"] == 51, "aucun remboursement"
	assert any("9 PM perdus" in t for t in textes(doc))


def test_une_incantation_ne_s_abandonne_pas():
	"""⚠️ Décision de conception, pas un oubli : l'incantation absorbe tout le budget du
	tour, donc la main ne revient jamais au joueur tant qu'elle dure. Commencer un Météore,
	c'est s'y engager — seuls un coup encaissé ou le manque de PM l'arrêtent. `interrompre`
	ne vise QUE les sorts maintenus."""
	mage = _mage(pm=60)
	mage["actions_max"] = mage["actions_restantes"] = 4
	doc = combat([mage], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(cout_pm=15, incantation=12, cible="ennemi", portee=8,
				effets={"degats": "4D6"})["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)
	mage["actions_restantes"] = 1   # on lui rend de quoi agir, pour isoler le refus

	assert resolve_action(doc, "interrompre")["error"] == "Vous n'entretenez pas ce sort."
	assert mage.get("incantation") is not None


def test_le_sort_se_perd_si_la_cible_meurt_pendant_l_incantation():
	mage = _mage(pm=60)
	loup = monstre(x=9, y=5)
	doc = combat([mage], [loup])
	from utils.combat import _armer_incantation
	sdoc = sort(**METEORE)["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)

	loup["vivant"] = False       # abattue entre-temps par un allié
	_tour_du_mage(doc, mage, 2)
	assert mage.get("incantation") is None
	assert any("dans le vide" in t for t in textes(doc))
	assert mage["currentPM"] == 45, "les PM sont partis quand même"


# ── Le tour passe SEUL, sans boucle infinie ─────────────────────────────────────

def test_le_tour_d_un_canalisateur_ne_rend_pas_la_main_au_client():
	"""⚠️ Le client n'aurait aucune action à jouer et `resolve_action` lui refuserait tout,
	`passer` compris : il resterait devant une interface morte."""
	mage = _mage(pm=60)
	mage["actions_max"] = mage["actions_restantes"] = 1
	compagnon = joueur(1, x=4, y=5, nom="Brann")
	doc = combat([mage, compagnon], [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(cout_pm=15, incantation=8, cible="ennemi", portee=8,
				effets={"degats": "4D6"})["doc"]
	_armer_incantation(doc, mage, sdoc, sdoc["effets"], "monstre_0", None, None)

	doc["acteur_courant_index"] = 0
	_resolve_until_player(doc, doc["grid"], start_at_current=True)
	acteur = doc["ordre_initiative"][doc["acteur_courant_index"]]
	assert acteur != mage["id"], "la main ne doit pas s'arrêter sur le canalisateur"


def test_un_groupe_entier_qui_canalise_ne_boucle_pas_a_l_infini():
	"""Garde-fou `max_iter` : sans la marge d'INCANTATION_PA_MAX, le compteur s'épuiserait
	en silence et le combat ressortirait avec la main plantée sur un lanceur."""
	mages = [_mage(idx, x=2 + idx, y=5, pm=60) for idx in range(3)]
	for m in mages:
		m["actions_max"] = m["actions_restantes"] = 1
	doc = combat(mages, [monstre(x=9, y=5)])
	from utils.combat import _armer_incantation
	sdoc = sort(cout_pm=12, incantation=12, cible="ennemi", portee=8,
				effets={"degats": "1D6"})["doc"]
	for m in mages:
		_armer_incantation(doc, m, sdoc, sdoc["effets"], "monstre_0", None, None)

	doc["acteur_courant_index"] = 0
	_resolve_until_player(doc, doc["grid"], start_at_current=True)
	assert doc["tour"] > 1, "les tours doivent avoir défilé, pas tourner sur place"
