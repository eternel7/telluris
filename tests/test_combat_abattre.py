# tests/test_combat_abattre.py
#
# ABATTRE (`effets.abattre`, part à durée) : le volant TOUCHÉ est cloué au sol tant que
# l'entrée vit — ailes d'espèce comme vol magique (`vol.abattu`, lu par `combat._can_fly`).
# S'il surplombe une falaise, il y tombe aussitôt par le chokepoint de la chute
# (`combat._atterrir`, un dé par case). À l'expiration il reprend l'air, sans rien d'autre.
# Contenu : Harpon arcanique, Cisaille des vents, Liane d'abattage (dev/gen_maitres_ecoles.py).

import pytest

from utils import combat as combat_mod
from utils import sorts as sorts_util
from utils import vol as vol_util
from utils.combat import TERRAIN_FALAISE, _can_fly, _tick_effets_combat, resolve_action
from _fixtures_magie import combat, joueur, monstre, sort, textes


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	"""d100 à 50 (touche, pas de critique), chaque autre dé à 2."""
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50 if b == 100 else 2)


def _harpon(duree=2, **effets):
	return sort(cout_pm=5, cible="ennemi", portee=8, nom="Harpon", icon="🪝",
				effets={"degats": "1D6", "abattre": 1, "duree": duree, **effets})


def _volant(**champs):
	return monstre(x=6, y=5, vol_espece=True, volant=True, **champs)


def test_abattre_est_une_cle_normalisee_bornee_a_1_et_une_part_a_duree():
	assert sorts_util._bonus_dict({"abattre": 4})["abattre"] == 1
	assert sorts_util._bonus_dict({})["abattre"] == 0
	assert sorts_util.part_durative({"abattre": 1, "duree": 2})
	assert not sorts_util.part_durative({"abattre": 1, "duree": 0})
	assert sorts_util.effets_agissent_sur_cible({"abattre": 1, "duree": 2})


def test_un_composant_peut_porter_abattre_sans_le_cumuler():
	eff = sorts_util.fusionner_effets({"abattre": 1, "duree": 2}, [{"abattre": 1}])
	assert eff["abattre"] == 1


def test_le_volant_touche_est_cloue_au_sol():
	bete = _volant()
	doc = combat([joueur()], [bete])
	assert _can_fly(bete)
	res = resolve_action(doc, "sort", cible_id=bete["id"], sort=_harpon())
	assert not res.get("error") and res["hit"]
	assert vol_util.abattu(bete) and not _can_fly(bete)
	assert any("cloué au sol" in t for t in textes(doc))


def test_le_vol_magique_ne_resiste_pas_non_plus():
	bete = monstre(x=6, y=5)
	bete.setdefault("effets_actifs", []).append({"source_id": "sort:v", "nom": "V", "vol": 1,
												  "restants": 5})
	bete["vol_magique"] = True
	doc = combat([joueur()], [bete])
	resolve_action(doc, "sort", cible_id=bete["id"], sort=_harpon())
	assert not _can_fly(bete)


def test_un_coup_rate_ne_cloue_rien(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 99 if b == 100 else 2)
	bete = _volant()
	doc = combat([joueur(toucher_magique=0)], [bete])
	resolve_action(doc, "sort", cible_id=bete["id"], sort=_harpon())
	assert _can_fly(bete) and not vol_util.abattu(bete)


def test_au_dessus_d_une_falaise_il_tombe_un_d20_par_case(monkeypatch):
	notations = []

	def _des(notation):
		notations.append(notation)
		return 5
	monkeypatch.setattr(combat_mod, "roll_dice", _des)
	bete = _volant()
	doc = combat([joueur()], [bete])
	doc["grid"]["cells"][5][6] = TERRAIN_FALAISE
	resolve_action(doc, "sort", cible_id=bete["id"], sort=_harpon())
	assert bete["pos"] != {"x": 6, "y": 5}
	assert combat_mod._walkable(doc["grid"]["cells"], bete["pos"]["x"], bete["pos"]["y"])
	assert "1D20" in notations, "chute depuis la falaise : un D20 par case"
	cloue = next(i for i, t in enumerate(textes(doc)) if "cloué au sol" in t)
	chute = next(i for i, t in enumerate(textes(doc)) if "chute" in t)
	assert cloue < chute, "cloué au sol PUIS chute"


def test_une_cible_qui_ne_volait_pas_n_a_pas_de_ligne_de_chute():
	bete = monstre(x=6, y=5)
	doc = combat([joueur()], [bete])
	resolve_action(doc, "sort", cible_id=bete["id"], sort=_harpon())
	assert not any("cloué au sol" in t for t in textes(doc))


def test_a_l_expiration_il_reprend_l_air():
	bete = _volant()
	doc = combat([joueur()], [bete])
	resolve_action(doc, "sort", cible_id=bete["id"], sort=_harpon(duree=1))
	assert not _can_fly(bete)
	doc["tour"] = int(doc.get("tour", 0) or 0) + 1
	_tick_effets_combat(doc, bete)
	assert not vol_util.abattu(bete) and _can_fly(bete)
