# tests/test_poison.py
#
# POISON = régénération NÉGATIVE. `regen_pv`/`regen_pm` sont SIGNÉES partout (pièges, sorts,
# compétences, armes, consommables ; l'équipement l'était déjà) :
#   • non-cumul « meilleur bonus + pire malus », comme les buffs : une potion CONTRE un
#     poison sans l'effacer, deux poisons ne se cumulent pas ;
#   • en combat, le poison peut mettre à terre (joueur) ou tuer (monstre) ;
#   • hors combat, il ronge mais s'arrête à 1 PV.

import pytest

from utils import combat as combat_mod
from utils import consommables, pieges
from utils.sorts import _bonus_dict, part_durative
from _fixtures_magie import combat, textes
from _fixtures_magie import character as _character
from _fixtures_magie import joueur as _joueur_fixture
from _fixtures_magie import monstre as _monstre_fixture


def joueur(**kw):
	j = _joueur_fixture(**kw)
	combat_mod._refresh_snapshot_stats(j)
	return j


def monstre(**kw):
	m = _monstre_fixture(**kw)
	combat_mod._refresh_snapshot_stats(m)
	return m


def poison(n=4, restants=3, nom="Poison", **extra):
	return dict({"source_id": f"test:{nom}", "nom": nom, "icon": "☠", "buffs": {},
				 "regen_pv": -n, "regen_pm": 0, "esquive": 0, "restants": restants,
				 "pose_tour": -1}, **extra)


# ── Normalisation : le signe survit ─────────────────────────────────────────────

def test_les_normalisations_gardent_la_regen_negative():
	assert consommables.effets_de({"effets": {"regen_pv": -3, "regen_pm": -2}})["regen_pv"] == -3
	assert _bonus_dict({"regen_pv": -5})["regen_pv"] == -5
	assert pieges.normaliser_pose({"item": "item:x", "effets": {"regen_pv": -4, "duree": 3}}
								  )["effets"] == {"regen_pv": -4, "duree": 3}
	# Le reste demeure ≥ 0 : seul le signe de la régén a changé.
	assert consommables.effets_de({"effets": {"pv": -3, "duree": -1}})["pv"] == 0


def test_un_poison_pur_est_une_part_a_duree():
	assert part_durative({"regen_pv": -4, "duree": 3})
	assert not part_durative({"regen_pv": -4})   # sans durée, rien à empiler


def test_une_fiole_de_poison_est_un_consommable_empilable():
	fiole = {"_id": "item:fiole", "categorie": "consommable", "nom": "Fiole",
			 "effets": {"regen_pv": -2, "duree": 2}}
	assert consommables.est_consommable(fiole)
	perso = {"effets_actifs": []}
	entree = consommables.empiler_effet(perso, fiole)
	assert entree["regen_pv"] == -2 and entree["restants"] == 2


# ── Non-cumul signé ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("regens,net", [
	([3, -4], -1),       # la potion CONTRE le poison, elle ne l'efface pas
	([-2, -5], -5),      # deux poisons : le pire seul
	([2, 6], 6),         # deux régén : la meilleure seule (comportement d'avant)
	([-3], -3),
])
def test_cumul_meilleur_bonus_plus_pire_malus(regens, net):
	assert consommables.cumul_effets([{"regen_pv": r} for r in regens])["regen_pv"] == net


def test_les_permanents_restent_additifs_et_signes():
	perso = {"effets_actifs": [{"regen_pv": -4, "restants": 2}],
			 "equipment_bonus": {"regen_pv": 1}, "competences_bonus": {"regen_pv": 2}}
	assert consommables.regen_bonus(perso)[0] == -4 + 1 + 2


# ── Combat ──────────────────────────────────────────────────────────────────────

def test_le_poison_ronge_au_tour_du_porteur():
	j = joueur()
	j["effets_actifs"] = [poison(4)]
	doc = combat([j], [monstre(x=10, y=8)])
	pv = j["currentPV"]
	combat_mod._tick_effets_combat(doc, j)
	assert j["currentPV"] == pv - 4
	assert any("souffre du poison (−4 PV)" in t for t in textes(doc))
	assert j["effets_actifs"][0]["restants"] == 2


def test_le_poison_met_un_joueur_a_terre():
	j = joueur(pv=3)
	j["effets_actifs"] = [poison(4)]
	doc = combat([j], [monstre(x=10, y=8)])
	combat_mod._tick_effets_combat(doc, j)
	assert j["currentPV"] == 0 and doc["status"] == "defaite"


def test_le_poison_tue_un_monstre_et_donne_la_victoire():
	loup = monstre(x=8, y=5, pv=3)
	loup["effets_actifs"] = [poison(4)]
	doc = combat([joueur()], [loup])
	combat_mod._tick_effets_combat(doc, loup)
	assert loup["vivant"] is False and doc["status"] == "victoire"
	assert any("succombe au poison" in t for t in textes(doc))


def test_un_monstre_tue_par_le_poison_ne_joue_pas_son_tour():
	loup = monstre(x=4, y=5, pv=3)
	loup["effets_actifs"] = [poison(4)]
	j = joueur(x=3, y=5)
	other = monstre(idx=1, x=10, y=8)
	doc = combat([j], [loup, other])
	pv = j["currentPV"]
	combat_mod._run_monster_turn(doc, loup, combat_mod.get_combat_grid(doc))
	assert loup["vivant"] is False and j["currentPV"] == pv


def test_le_poison_de_pm_s_arrete_a_zero():
	j = joueur(pm=2)
	j["effets_actifs"] = [poison(0, regen_pm=-5)]
	doc = combat([j], [monstre(x=10, y=8)])
	combat_mod._tick_effets_combat(doc, j)
	assert j["currentPM"] == 0


def test_un_piege_empoisonne_pose_son_poison_sur_le_monstre(monkeypatch):
	monkeypatch.setattr(combat_mod, "roll_dice", lambda notation: 1)
	loup = monstre(x=4, y=5)
	doc = combat([joueur(x=1, y=1)], [loup])
	doc["pieges"] = [pieges.nouveau_piege("piege_j0_0", pieges.CAMP_JOUEUR, 4, 5, 2,
										  effets={"regen_pv": -4, "duree": 3},
										  nom="Aiguille empoisonnée")]
	combat_mod._pieges_au_pas(doc, loup)
	[eff] = [e for e in loup["effets_actifs"] if e["nom"] == "Aiguille empoisonnée"]
	assert eff["regen_pv"] == -4
	pv = loup["currentPV"]
	combat_mod._tick_effets_combat(doc, loup)
	assert loup["currentPV"] == pv - 4


def test_un_sort_offensif_peut_empoisonner(monkeypatch):
	from _fixtures_magie import sort
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	monkeypatch.setattr(combat_mod, "roll_dice", lambda notation: 1)
	loup = monstre(x=5, y=5)
	doc = combat([joueur(x=3, y=5)], [loup])
	res = combat_mod.resolve_action(doc, "sort", cible_id=loup["id"], sort=sort(
		cout_pm=5, cible="ennemi", portee=4, nom="Venin",
		effets={"degats": "1D4", "regen_pv": -3, "duree": 2}))
	assert "error" not in res
	assert any(e.get("regen_pv") == -3 for e in loup["effets_actifs"])


# ── Exploration ─────────────────────────────────────────────────────────────────

def test_hors_combat_le_poison_s_arrete_a_un_pv():
	from routers import user as ru
	perso = _character(currentPV=5, effets_actifs=[{"nom": "Poison", "regen_pv": -50,
													 "restants": 3}])
	ru._apply_world_turn_regen(perso)
	assert perso["currentPV"] == 1
	ru._apply_world_turn_regen(perso)
	assert perso["currentPV"] == 1                          # jamais en dessous
	assert perso["effets_actifs"][0]["restants"] == 1       # il expire normalement


def test_hors_combat_le_poison_contre_la_regen_naturelle():
	from routers import user as ru
	perso = _character(currentPV=50, effets_actifs=[{"nom": "Poison", "regen_pv": -10,
													  "restants": 2}])
	naturelle = -(-perso["caracteristiques_current"]["R"] // 20)   # ceil(R/20)
	ru._apply_world_turn_regen(perso)
	assert perso["currentPV"] == 50 + naturelle - 10
