# tests/test_partage_soin.py
#
# PARTAGE DE SOIN (`effets.partage_soin`, %) : le lanceur recueille une part des PV
# RÉELLEMENT rendus aux AUTRES bénéficiaires de son lancement. Calqué sur le drain :
#   · assiette = PV effectivement rendus (un allié plein ne rapporte rien) ;
#   · le lanceur est EXCLU de l'assiette (dans sa propre zone il est déjà soigné) ;
#   · UNE fois par lancement, sur la SOMME — jamais par bénéficiaire ;
#   · crédit borné au PV max du lanceur.

import pytest

from utils import combat as combat_mod
from utils import sorts as S
from utils.combat import resolve_action
from _fixtures_magie import combat, joueur, monstre, sort, textes


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint",
						lambda a, b: 50 if b == 100 else 6)


def _soin(pct, cible="allie", zone=None, pv=40):
	champs = {"zone": zone} if zone else {}
	return sort(cout_pm=5, cible=cible, portee=3,
				effets={"pv": pv, "partage_soin": pct}, **champs)


def _recueille(doc):
	return [t for t in textes(doc) if "soin partagé" in t]


def test_le_lanceur_recueille_sa_part_du_soin_donne():
	mage = joueur(currentPV=50)
	allie = joueur(idx=1, x=4, y=5, nom="Bjorn", currentPV=10)
	doc = combat([mage, allie], [monstre(x=10, y=5)])
	res = resolve_action(doc, "sort", cible_id="joueur_1", sort=_soin(25))
	assert allie["currentPV"] == 50
	assert res["partage_soin"] == 10
	assert mage["currentPV"] == 60
	assert len(_recueille(doc)) == 1


def test_un_allie_plein_ne_rapporte_rien():
	mage = joueur(currentPV=50)
	allie = joueur(idx=1, x=4, y=5, nom="Bjorn")   # PV pleins
	doc = combat([mage, allie], [monstre(x=10, y=5)])
	res = resolve_action(doc, "sort", cible_id="joueur_1", sort=_soin(50))
	assert "partage_soin" not in res
	assert mage["currentPV"] == 50
	assert not _recueille(doc)


def test_le_lanceur_est_exclu_de_l_assiette_de_sa_propre_zone():
	"""Sort `soi` + zone : le lanceur reçoit son soin, plus 50 % de ce qu'a reçu l'allié —
	jamais 50 % de son propre soin."""
	mage = joueur(currentPV=10)
	allie = joueur(idx=1, x=4, y=5, nom="Bjorn", currentPV=10)
	doc = combat([mage, allie], [monstre(x=10, y=5)])
	zone = {"forme": "cercle", "origine": "lanceur", "rayon": 2}
	res = resolve_action(doc, "sort", sort=_soin(50, cible="soi", zone=zone, pv=20))
	assert allie["currentPV"] == 30
	assert res["partage_soin"] == 10
	assert mage["currentPV"] == 10 + 20 + 10


def test_une_zone_ne_credite_qu_une_fois_sur_la_somme():
	mage = joueur(currentPV=10)
	a1 = joueur(idx=1, x=4, y=5, nom="Bjorn", currentPV=10)
	a2 = joueur(idx=2, x=5, y=5, nom="Sigrid", currentPV=10)
	a3 = joueur(idx=3, x=4, y=6, nom="Ulf", currentPV=10)
	doc = combat([mage, a1, a2, a3], [monstre(x=11, y=8)])
	zone = {"forme": "cercle", "origine": "cible", "rayon": 2}
	res = resolve_action(doc, "sort", cible_id="joueur_1", sort=_soin(10, zone=zone, pv=30))
	assert a1["currentPV"] == a2["currentPV"] == a3["currentPV"] == 40
	# Le lanceur, à 1 case du désigné, est AUSSI dans la zone : soigné, mais hors assiette.
	assert res["partage_soin"] == 90 * 10 // 100
	assert len(_recueille(doc)) == 1


def test_le_credit_est_borne_au_pv_max_du_lanceur():
	mage = joueur(currentPV=98)
	allie = joueur(idx=1, x=4, y=5, nom="Bjorn", currentPV=10)
	doc = combat([mage, allie], [monstre(x=10, y=5)])
	res = resolve_action(doc, "sort", cible_id="joueur_1", sort=_soin(100))
	assert mage["currentPV"] == mage["pv_max"]
	assert res["partage_soin"] == 2


def test_partage_par_formule_et_clamp_apres_fusion():
	eff = S.fusionner_effets(S._bonus_dict({"partage_soin": 80}),
							 [S._bonus_dict({"partage_soin": 50})])
	assert eff["partage_soin"] == S.PARTAGE_SOIN_PCT_MAX
	formule = S.resoudre_effets(S._bonus_dict({"partage_soin": "{Vol/4}"}), {"Vol": 60})
	assert formule["partage_soin"] == 15


def test_exploration_le_lanceur_recoit_sa_part(monkeypatch):
	from routers import user as user_router

	class _Derive:
		pv_max = 100

	monkeypatch.setattr(user_router, "sync_equipment_bonus", lambda c: None)
	monkeypatch.setattr(user_router, "_derived_from_character", lambda c, eq: _Derive())
	lanceur = {"_id": "character:a", "currentPV": 50}
	compagnon = {"_id": "aventurier:b", "currentPV": 10}
	recu = user_router._partager_soin_exploration(lanceur, compagnon, {"partage_soin": 25}, 40)
	assert recu == 10 and lanceur["currentPV"] == 60
	# Sur soi : rien à partager.
	assert user_router._partager_soin_exploration(lanceur, lanceur, {"partage_soin": 25}, 40) == 0
