# tests/test_sorts_caracteristiques.py
#
# FORMULES À CARACTÉRISTIQUES : un effet lit la caractéristique EFFECTIVE (buffs compris)
# de son lanceur — `"degats": "1D{Int/5}"`, `"soin": "1D6+{Vol/10}"`, `"duree": "1+{Vol/20}"`,
# `"buffs": {"R": "{Vol/5}"}`, `"portee": "3+{Int/20}"`.
#
# Ce qui est verrouillé ici :
#   · la grammaire (division entière, plancher d'un dé, jeton inconnu neutre) ;
#   · un doc SANS formule ressort identique (aucune migration) ;
#   · le `soin` est tiré UNE fois par lancement — une zone sert tout le monde du même jet ;
#   · les prédicats voient un effet porté par la seule formule ;
#   · en combat, un buff de caract renforce le sort ; la portée suit sa formule ;
#   · une incantation longue fige ses formules à l'armement ;
#   · le simulateur résout par le même chokepoint.

import pytest

from utils import combat as combat_mod
from utils import simulateur
from utils import sorts as S
from utils.combat import resolve_action
from _fixtures_magie import combat, joueur, monstre, sort


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	"""d100 à 50 (touche, pas de critique) et chaque dé à 6 : dégâts prévisibles."""
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 6)


CARACTS = {"V": 5, "F": 20, "R": 30, "Ag": 25, "Vol": 40, "Int": 47, "Cha": 30, "Ch": 20}


# ── Grammaire ───────────────────────────────────────────────────────────────────

def test_jetons_remplaces_par_division_entiere():
	assert S.resoudre_notation("1D{Int/5}+{Vol/10}", CARACTS) == "1D9+4"
	assert S.resoudre_notation("{Cha}", CARACTS) == "30"


def test_la_taille_d_un_de_ne_descend_jamais_sous_le_plancher():
	"""`1D{Int/50}` à Int 47 ferait un D0 : `random.randint(1, 0)` lèverait."""
	assert S.resoudre_notation("1D{Int/50}", CARACTS) == "1D%d" % S.DES_FACES_MIN
	# Un BONUS plat, lui, peut valoir 0.
	assert S.resoudre_notation("1D6+{Int/50}", CARACTS) == "1D6+0"


def test_jeton_inconnu_vaut_zero():
	assert S.resoudre_notation("2+{Mana/2}", CARACTS) == "2+0"
	assert S.evaluer_formule("{Foo}", CARACTS) == 0


def test_notation_sans_jeton_inchangee():
	assert S.resoudre_notation("2D6+3", CARACTS) == "2D6+3"


def test_formule_entiere_signee():
	assert S.evaluer_formule("1+{Vol/20}", CARACTS) == 3
	assert S.evaluer_formule("-{Int/10}", CARACTS) == -4
	assert S.evaluer_formule(7, CARACTS) == 7


# ── Normalisation et fusion ─────────────────────────────────────────────────────

def test_un_champ_entier_a_formule_est_range_dans_formules():
	eff = S._bonus_dict({"duree": "1+{Vol/20}", "buffs": {"R": "{Vol/5}", "F": 5},
						 "soin": "1D6+{Vol/10}"})
	assert eff["duree"] == 0, "la formule ne doit pas être lue comme un entier"
	assert eff["buffs"] == {"F": 5}
	assert eff["formules"] == {"duree": "1+{Vol/20}", "buffs": {"R": "{Vol/5}"}}
	assert eff["soin"] == "1D6+{Vol/10}"


def test_un_effet_sans_formule_ressort_identique():
	eff = S._bonus_dict({"degats": "2D6", "pv": 4, "buffs": {"F": 10}, "duree": 3})
	assert "formules" not in eff
	resolu = S.resoudre_effets(eff, CARACTS)
	assert resolu == eff


def test_fusion_formule_plus_bonus_constant_de_composant():
	base = S._bonus_dict({"buffs": {"R": "{Vol/5}"}, "duree": "1+{Vol/20}"})
	out = S.fusionner_effets(base, [S._bonus_dict({"buffs": {"R": 5}, "duree": 2}),
									S._bonus_dict({"duree": "{Int/47}"})])
	resolu = S.resoudre_effets(out, CARACTS)
	assert resolu["buffs"] == {"R": 8 + 5}
	assert resolu["duree"] == 3 + 2 + 1
	assert "formules" not in resolu


def test_soin_tire_une_seule_fois_et_ajoute_aux_pv():
	appels = []

	def des(notation):
		appels.append(notation)
		return 5

	eff = S.fusionner_effets(S._bonus_dict({"soin": "1D6+{Vol/10}", "pv": 2}),
							 [S._bonus_dict({"soin": "1D4"})])
	resolu = S.resoudre_effets(eff, CARACTS, des_fn=des)
	assert appels == ["1D6+4+1D4"]
	assert resolu["pv"] == 2 + 5
	assert resolu["soin"] == ""


def test_pourcentages_re_clampes_apres_resolution():
	eff = S._bonus_dict({"drain_pv": "{Int}", "partage_soin": "{Int}", "cout_pv": "-{Int}"})
	resolu = S.resoudre_effets(eff, {"Int": 300})
	assert resolu["drain_pv"] == S.DRAIN_PCT_MAX
	assert resolu["partage_soin"] == S.PARTAGE_SOIN_PCT_MAX
	assert resolu["cout_pv"] == 0, "un coût ne devient jamais un gain"


# ── Prédicats ───────────────────────────────────────────────────────────────────

def test_un_soin_pur_est_lancable_partout():
	doc = S.normaliser_sort({"_id": "sort:s", "type": "sort", "cout_pm": 5, "cible": "allie",
							 "effets": {"soin": "1D6+{Vol/10}"}})
	assert S.sort_utilisable_combat(doc)
	assert S.sort_utilisable_exploration(doc)


def test_une_part_durative_portee_par_formule_compte():
	eff = S._bonus_dict({"buffs": {"R": "{Vol/5}"}, "duree": "1+{Vol/20}"})
	assert S.part_durative(eff)


def test_un_debuff_par_formule_agit_sur_un_ennemi():
	eff = S._bonus_dict({"buffs": {"Vol": "-{Cha/5}"}, "duree": 2})
	assert S.effets_agissent_sur_cible(eff)


# ── Portée ──────────────────────────────────────────────────────────────────────

def test_portee_a_formule():
	doc = S.normaliser_sort({"_id": "sort:p", "type": "sort", "cout_pm": 5,
							 "cible": "ennemi", "portee": "3+{Int/20}",
							 "effets": {"degats": "1D4"}})
	assert doc["portee"] == 3, "part constante pour qui ignore la formule"
	assert S.portee_effective(doc, CARACTS) == 5
	assert S.portee_effective(doc, {}) == 3


# ── Combat ──────────────────────────────────────────────────────────────────────

def _frappe(**champs):
	# `{Int}` seul = un dégât plat égal à l'Int : lisible sans dé (la magie ignore les PA).
	return sort(cout_pm=5, cible="ennemi", portee=8, effets={"degats": "{Int}"}, **champs)


def test_le_sort_lit_l_int_du_lanceur():
	mage = joueur()
	loup = monstre(x=6, y=5, pv=500)
	doc = combat([mage], [loup])
	resolve_action(doc, "sort", cible_id="monstre_0", sort=_frappe())
	assert 500 - loup["currentPV"] == mage["caracts_base"]["Int"]


def test_un_buff_d_int_renforce_le_sort():
	"""Décision de conception : les formules lisent la caract EFFECTIVE, buffs compris."""
	mage = joueur()
	mage.setdefault("effets_actifs", []).append(
		{"source_id": "potion", "nom": "Élixir", "buffs": {"Int": 20}, "restants": 3})
	combat_mod._refresh_snapshot_stats(mage)
	loup = monstre(x=6, y=5, pv=500)
	doc = combat([mage], [loup])
	resolve_action(doc, "sort", cible_id="monstre_0", sort=_frappe())
	assert 500 - loup["currentPV"] == mage["caracts_base"]["Int"] + 20


def test_la_portee_suit_sa_formule():
	mage = joueur()   # Int 60 ⇒ portée 1 + 60/30 = 3
	sort_p = sort(cout_pm=5, cible="ennemi", portee="1+{Int/30}", effets={"degats": "1D4"})
	loin = combat([mage], [monstre(x=7, y=5, pv=50)])
	assert resolve_action(loin, "sort", cible_id="monstre_0", sort=sort_p)["error"] \
		== "Cible hors de portée."
	pres = combat([joueur()], [monstre(x=6, y=5, pv=50)])
	assert "error" not in resolve_action(pres, "sort", cible_id="monstre_0", sort=sort_p)


def test_une_zone_de_soin_sert_tout_le_monde_du_meme_jet(monkeypatch):
	appels = []

	def des(notation):
		appels.append(notation)
		return 9

	monkeypatch.setattr(combat_mod, "roll_dice", des)
	mage = joueur(currentPV=10)
	a1 = joueur(idx=1, x=4, y=5, nom="Bjorn", currentPV=10)
	a2 = joueur(idx=2, x=3, y=6, nom="Sigrid", currentPV=10)
	doc = combat([mage, a1, a2], [monstre(x=10, y=5)])
	soin = sort(cout_pm=5, cible="soi", zone={"forme": "cercle", "origine": "lanceur", "rayon": 2},
				effets={"soin": "1D6+{Vol/10}"})
	resolve_action(doc, "sort", sort=soin)
	assert appels == ["1D6+6"], "un seul jet pour toute la zone"
	assert mage["currentPV"] == a1["currentPV"] == a2["currentPV"] == 19


def test_une_incantation_longue_fige_ses_formules_a_l_armement(monkeypatch):
	"""Les effets ARMÉS (stockés dans le bloc d'incantation, relus au départ du sort) sont
	déjà résolus : la puissance se fige à l'engagement, comme le tarif."""
	armes = []
	vrai = combat_mod._armer_incantation

	def espion(combat_doc, joueur_, sdoc, effets, *args, **kwargs):
		armes.append(effets)
		return vrai(combat_doc, joueur_, sdoc, effets, *args, **kwargs)

	monkeypatch.setattr(combat_mod, "_armer_incantation", espion)
	mage = joueur()
	doc = combat([mage], [monstre(x=6, y=5, pv=500)])
	resolve_action(doc, "sort", cible_id="monstre_0",
				   sort=_frappe(incantation=S.INCANTATION_PA_MAX))
	assert len(armes) == 1
	assert armes[0]["degats"] == str(mage["caracts_base"]["Int"])
	assert "formules" not in armes[0]


# ── Simulateur ──────────────────────────────────────────────────────────────────

def test_le_simulateur_resout_ses_options_offensives():
	capa = S.normaliser_sort({"_id": "sort:d", "type": "sort", "cout_pm": 5, "cible": "ennemi",
							  "portee": "3+{Int/20}", "effets": {"degats": "1D{Int/5}"}})
	resolu = simulateur._resoudre_capacite(capa, CARACTS)
	assert resolu["effets"]["degats"] == "1D9"
	assert resolu["portee"] == 5


def test_le_simulateur_tire_le_soin_a_chaque_usage():
	actor = {"nom": "Frida", "currentPV": 10, "pv_max": 100, "currentPM": 50, "pm_max": 50,
			 "actions_max": 3}
	soutien = {"kind": "sort", "id": "sort:s", "label": "Soin", "icon": "✨", "cout_pm": 5,
			   "effets": S._bonus_dict({"soin": "{Vol}"}), "caracts": {"Vol": 30},
			   "compteur": "sorts", "source": {}}
	assert simulateur._utiliser_soutien(actor, soutien, {"tour": 1, "log": []})
	assert actor["currentPV"] == 40
