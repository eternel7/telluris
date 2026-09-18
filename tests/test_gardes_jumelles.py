# tests/test_gardes_jumelles.py
#
# LES GARDES JUMELLES : le router filtre une capacité avec un prédicat PUR
# (`sort_utilisable_combat` / `competence_utilisable_combat`), puis le moteur la revérifie
# dans `resolve_action`. Tant que ces tests vivaient dans deux expressions booléennes
# recopiées à la main, ils pouvaient diverger — et ils l'ont fait : la recopie des
# compétences omettait `degats_pm`, si bien qu'une siphonie de compétence était listée et
# épinglable, puis refusée au moment de frapper. Aucun test ne l'a vu.
#
# Ce fichier ne teste donc PAS une mécanique de plus : il teste l'ACCORD entre le prédicat
# et le moteur, pour les deux familles et sur la même batterie d'effets. C'est le seul
# test qui aurait attrapé la divergence, et le seul qui attrapera la suivante.
#
# ⚠️ Ne pas le confondre avec `test_combat_degats_pm.py` (que fait la siphonie) ni avec
# `test_competences.py` (ce qu'une compétence sait faire) : ici on ne regarde que « le
# router et le moteur disent-ils la même chose ».

import pytest

from utils import combat as combat_mod
from utils.combat import resolve_action
from utils.competences import (
	competence_utilisable_combat, competence_utilisable_exploration, normaliser_competence,
)
from utils.sorts import (
	effets_agissent_sur_cible, sort_utilisable_combat, sort_utilisable_exploration,
)
from _fixtures_magie import combat, joueur, monstre, sort


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


# Batterie d'effets, jugée par les DEUX gardes — qui ne posent pas la même question :
#   `lançable`  → y a-t-il de quoi agir en combat ?      (capacite_utilisable_combat)
#   `sur_cible` → y a-t-il de quoi faire à un ENNEMI ?   (effets_agissent_sur_cible)
# Un soin est lançable en combat mais n'a rien à faire à un monstre : les deux colonnes
# diffèrent légitimement, et c'est précisément ce que ce fichier doit fixer par écrit.
# La siphonie pure est le cas qui avait divergé entre le prédicat et le moteur.
EFFETS_OFFENSIFS = [
	#              effets                                          lançable  sur_cible
	pytest.param({"degats": "2D6"},                                True, True,
				 id="degats-seuls"),
	pytest.param({"degats_pm": "2D6"},                             True, True,
				 id="siphonie-PURE"),
	pytest.param({"degats": "1D6", "degats_pm": "2D6"},            True, True,
				 id="degats-et-siphonie"),
	pytest.param({"buffs": {"Ag": -10}, "duree": 2},               True, True,
				 id="debuff-pur"),
	pytest.param({"degats_pm": "2D6", "buffs": {"F": -5}, "duree": 2}, True, True,
				 id="siphonie-et-debuff"),
	pytest.param({},                                               False, False,
				 id="rien"),
	pytest.param({"buffs": {"Ag": -10}},                           False, False,
				 id="buff-sans-duree"),
	# Lançable (un soin agit en combat), mais rien à faire à un monstre : le moteur doit
	# le refuser à la SECONDE garde, pas à la première.
	pytest.param({"pv": 10},                                       True, False,
				 id="soin-sur-un-ennemi"),
]

SANS_EFFET_CIBLE = ("n'a aucun effet sur une cible", "n'a aucun effet utilisable en combat")


def _competence(**champs):
	doc = {"_id": "competence:essai", "type": "competence", "vocation": "repurgateur",
		   "nom": "Essai", "mode": "active", "cout_pm": 0, "portee": 1, **champs}
	return normaliser_competence(doc)


def _refus_faute_d_effet(res) -> bool:
	"""Le moteur a-t-il refusé la capacité comme « sans effet » ? (Les autres refus —
	cible invalide, hors de portée — ne nous regardent pas ici.)"""
	err = (res or {}).get("error") or ""
	return any(motif in err for motif in SANS_EFFET_CIBLE)


# ── L'accord prédicat ↔ moteur, pour les deux familles ──────────────────────────

@pytest.mark.parametrize("effets, lançable, sur_cible", EFFETS_OFFENSIFS)
def test_le_predicat_et_le_moteur_disent_la_meme_chose_pour_un_sort(
		effets, lançable, sur_cible):
	s = sort(cout_pm=4, cible="ennemi", jet="magique", portee=6, effets=effets)
	assert sort_utilisable_combat(s["doc"]) is lançable

	doc = combat([joueur(x=3, y=5)], [monstre(x=6, y=5)])
	res = resolve_action(doc, "sort", cible_id="monstre_0", sort=s)
	assert _refus_faute_d_effet(res) is not sur_cible, (
		f"le moteur et les prédicats divergent sur {effets}")


@pytest.mark.parametrize("effets, lançable, sur_cible", EFFETS_OFFENSIFS)
def test_le_predicat_et_le_moteur_disent_la_meme_chose_pour_une_competence(
		effets, lançable, sur_cible):
	"""⚠️ LE test de non-régression : `degats_pm` seul passait le prédicat du router et se
	faisait refuser par le moteur, parce que la sous-branche `ennemi` des compétences
	omettait la clé."""
	comp = _competence(cible="ennemi", jet="cc", effets=effets)
	assert competence_utilisable_combat(comp) is lançable

	doc = combat([joueur(x=3, y=5)], [monstre(x=4, y=5)])
	res = resolve_action(doc, "competence", cible_id="monstre_0", competence=comp)
	assert _refus_faute_d_effet(res) is not sur_cible, (
		f"le moteur et les prédicats divergent sur {effets}")


@pytest.mark.parametrize("effets, lançable, sur_cible", EFFETS_OFFENSIFS)
def test_sort_et_competence_sont_jugés_identiquement(effets, lançable, sur_cible):
	"""Les deux familles partagent le même contrat d'effets : rien ne justifie qu'une
	capacité soit lançable sous un type et pas sous l'autre."""
	s = sort(cout_pm=4, cible="ennemi", jet="magique", portee=6, effets=effets)
	comp = _competence(cible="ennemi", jet="cc", effets=effets)
	assert sort_utilisable_combat(s["doc"]) is lançable
	assert competence_utilisable_combat(comp) is lançable
	assert effets_agissent_sur_cible(s["effets"]) is sur_cible
	assert effets_agissent_sur_cible(comp["effets"]) is sur_cible


# ── La siphonie de compétence, bout en bout ─────────────────────────────────────

def test_une_siphonie_de_competence_vide_bien_les_PM_sans_toucher_les_PV():
	"""La régression exacte : acceptée par le router, refusée par le moteur. Elle doit
	désormais partir, et faire ce qu'elle annonce."""
	comp = _competence(cible="ennemi", jet="cc", effets={"degats_pm": "2D6"})
	loup = monstre(x=4, y=5)
	pm_avant, pv_avant = loup["currentPM"], loup["currentPV"]
	doc = combat([joueur(x=3, y=5)], [loup])

	res = resolve_action(doc, "competence", cible_id="monstre_0", competence=comp)

	assert "error" not in res
	assert res["dmg_pm"] > 0
	assert loup["currentPM"] == pm_avant - res["dmg_pm"]
	assert loup["currentPV"] == pv_avant, "une siphonie ne touche pas les PV"


# ── L'exploration, même accord ──────────────────────────────────────────────────

EFFETS_EXPLORATION = [
	pytest.param({"pv": 10}, "soi", True, id="soin-sur-soi"),
	pytest.param({"buffs": {"F": 5}, "duree": 3}, "soi", True, id="buff-a-duree"),
	pytest.param({"degats": "2D6"}, "ennemi", False, id="offensif-hors-combat"),
	pytest.param({"saut": 4}, "soi", False, id="saut-sans-grille"),
	pytest.param({"lien_vie": {"part": 50}}, "allie", False, id="lien-sans-grille"),
	pytest.param({}, "soi", False, id="rien"),
]


@pytest.mark.parametrize("effets, cible, attendu", EFFETS_EXPLORATION)
def test_les_deux_familles_s_accordent_aussi_hors_combat(effets, cible, attendu):
	s = sort(cout_pm=4, cible=cible, portee=1, effets=effets)
	comp = _competence(cible=cible, effets=effets)
	assert sort_utilisable_exploration(s["doc"]) is attendu
	assert competence_utilisable_exploration(comp) is attendu


# ── Ce qui reste PROPRE à chaque famille ────────────────────────────────────────

def test_une_passive_n_est_jamais_lançable():
	"""Le seul écart légitime côté compétences : une passive n'a pas de lancement."""
	passive = _competence(mode="passive", effets={"degats": "2D6"})
	assert competence_utilisable_combat(passive) is False
	assert competence_utilisable_exploration(passive) is False


def test_une_invocation_reste_propre_aux_sorts():
	"""Un sort invoque sans porter le moindre `effets` ; `normaliser_competence` ne lit pas
	le bloc, donc une compétence ne peut pas en porter — et le prédicat partagé ne la rend
	pas lançable pour autant."""
	s = sort(cout_pm=4, cible="soi", effets={},
			 invocation={"espece": "espece:loup", "nombre": 2})
	assert sort_utilisable_combat(s["doc"]) is True

	comp = normaliser_competence({
		"_id": "competence:essai", "type": "competence", "vocation": "chaman",
		"nom": "Essai", "mode": "active", "effets": {},
		"invocation": {"espece": "espece:loup", "nombre": 2}})
	assert "invocation" not in comp
	assert competence_utilisable_combat(comp) is False


def test_une_capacite_maintenue_est_lançable_des_deux_cotes_sans_duree():
	"""Une posture n'a pas de `duree` : c'est l'entretien qui la tient. Les deux familles
	doivent l'accepter en combat et la refuser hors combat."""
	s = sort(cout_pm=4, cible="soi", maintien=3, effets={"buffs": {"R": 10}})
	comp = _competence(cible="soi", maintien=3, effets={"buffs": {"R": 10}})
	assert sort_utilisable_combat(s["doc"]) is True
	assert competence_utilisable_combat(comp) is True
	assert sort_utilisable_exploration(s["doc"]) is False
	assert competence_utilisable_exploration(comp) is False
