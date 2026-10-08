# tests/test_competences_echange.py
#
# ÉCHANGE DE PLACE — `effets.echange` sur une capacité `cible: "allie"` OU `"ennemi"` (sort OU
# compétence) : le lanceur et la cible désignée PERMUTENT leurs cases (« Attention, messire ! »).
# Sur un ennemi, l'échange passe par le jet de toucher et épargne les cadavres.
#
# Ce qui est verrouillé ici :
#   · la permutation, et UNE ligne de journal `move` qui nomme les deux corps ;
#   · aucune limite de distance dans le moteur : c'est la PORTÉE de la capacité qui décide ;
#   · les refus (allié à terre, grande créature, case intenable, tiers sur une case) ne
#     coûtent RIEN — validés avant le débit et avant tout soutien posé ;
#   · combinable : échange + lien de vie (version paladin) ;
#   · combat seulement (aucune case à permuter en exploration).

import pytest

from utils import combat as combat_mod
from utils.combat import resolve_action
from utils.competences import competence_utilisable_exploration, normaliser_competence
from utils.sorts import capacite_utilisable_combat
from _fixtures_magie import combat, joueur, monstre


@pytest.fixture(autouse=True)
def _des_fixes(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)


def comp(**champs):
	doc = {"_id": "competence:attention_messire", "type": "competence", "vocation": "guerrier",
		   "nom": "Attention, messire !", "mode": "active", "cout_pm": 12, "cible": "allie",
		   "portee": 1, "effets": {"echange": 1}, **champs}
	return normaliser_competence(doc)


def _duo(ecuyer_x=4, **ecuyer):
	garde = joueur(0, x=3, y=5, nom="Garde", pm=60)
	ecuyer = joueur(1, x=ecuyer_x, y=5, nom="Écuyer", **ecuyer)
	doc = combat([garde, ecuyer], [monstre(x=9, y=5)])
	return garde, ecuyer, doc


def test_le_lanceur_et_l_allie_permutent_leurs_cases():
	garde, ecuyer, doc = _duo()
	res = resolve_action(doc, "competence", cible_id="joueur_1", competence=comp())
	assert "error" not in res, res
	assert garde["pos"] == {"x": 4, "y": 5} and ecuyer["pos"] == {"x": 3, "y": 5}
	assert res["echange"]["allie_id"] == "joueur_1"
	assert garde["currentPM"] == 60 - 12


def test_une_seule_ligne_de_journal_pour_les_deux_corps():
	"""Les deux jetons doivent glisser ensemble à la révélation de la MÊME ligne."""
	garde, ecuyer, doc = _duo()
	resolve_action(doc, "competence", cible_id="joueur_1", competence=comp())
	moves = [e for e in doc["log"] if e["kind"] == "move"]
	assert len(moves) == 1
	assert "Garde" in moves[0]["texte"] and "Écuyer" in moves[0]["texte"]


def test_aucune_limite_de_distance_dans_le_moteur_la_portee_decide():
	garde, ecuyer, doc = _duo(ecuyer_x=6)
	assert "error" in resolve_action(doc, "competence", cible_id="joueur_1", competence=comp())
	res = resolve_action(doc, "competence", cible_id="joueur_1", competence=comp(portee=3))
	assert "error" not in res, res
	assert garde["pos"] == {"x": 6, "y": 5} and ecuyer["pos"] == {"x": 3, "y": 5}


@pytest.mark.parametrize("cas", ["a_terre", "grand", "falaise", "tiers"])
def test_un_echange_refuse_ne_coute_rien(cas):
	garde, ecuyer, doc = _duo()
	if cas == "a_terre":
		ecuyer["currentPV"] = 0
	elif cas == "grand":
		ecuyer["jeton"] = {"largeur": 2, "profondeur": 2, "forme": "ellipse"}
		ecuyer["cap"] = "bas"
	elif cas == "falaise":
		# Le garde VOLE au-dessus d'une falaise : l'écuyer, à pied, n'y tiendrait pas.
		doc["grid"]["cells"][5][3] = combat_mod.TERRAIN_FALAISE
		garde["volant"] = True
	elif cas == "tiers":
		# Une grande monture traversée couvre la case du garde : ils se superposeraient.
		ane = joueur(2, x=2, y=4, nom="Âne", jouable=False)
		ane["jeton"] = {"largeur": 2, "profondeur": 2, "forme": "ellipse"}
		ane["cap"] = "bas"
		doc["joueurs"].append(ane)
	res = resolve_action(doc, "competence", cible_id="joueur_1", competence=comp())
	assert "error" in res
	assert garde["currentPM"] == 60, "une capacité qui ne part pas ne se paie pas"
	assert garde["pos"] == {"x": 3, "y": 5} and ecuyer["pos"] == {"x": 4, "y": 5}


def test_echange_et_lien_de_vie_version_paladin():
	garde, ecuyer, doc = _duo()
	res = resolve_action(doc, "competence", cible_id="joueur_1", competence=comp(
		vocation="paladin", maintien="4-{Vol/30}",
		effets={"echange": 1, "lien_vie": {"part": "25+{Vol/4}", "reduction": 0}}))
	assert "error" not in res, res
	assert garde["pos"] == {"x": 4, "y": 5}
	assert ecuyer["lien_vie"]["protecteur_id"] == "joueur_0"
	assert ecuyer["lien_vie"]["part"] == 40                   # 25 + 60/4
	assert garde["concentrations"][0]["maintien"] == 2        # 4 − 60/30


def test_un_sort_peut_aussi_echanger():
	"""Même chokepoint (`_lancer_capacite`) pour les deux familles."""
	from _fixtures_magie import sort
	garde, ecuyer, doc = _duo()
	res = resolve_action(doc, "sort", cible_id="joueur_1",
						 sort=sort(cible="allie", portee=1, effets={"echange": 1}))
	assert "error" not in res, res
	assert garde["pos"] == {"x": 4, "y": 5}


# ── Avec un ENNEMI ──────────────────────────────────────────────────────────────

def _face_a_face(**loup):
	garde = joueur(0, x=3, y=5, nom="Garde", pm=60)
	bete = monstre(x=4, y=5, **loup)
	return garde, bete, combat([garde], [bete])


def comp_ennemi(**champs):
	return comp(**{"cible": "ennemi", "effets": {"echange": 1}, **champs})


def test_on_peut_echanger_sa_place_avec_un_ennemi_touche():
	garde, bete, doc = _face_a_face()
	res = resolve_action(doc, "competence", cible_id=bete["id"], competence=comp_ennemi())
	assert "error" not in res, res
	assert garde["pos"] == {"x": 4, "y": 5} and bete["pos"] == {"x": 3, "y": 5}
	assert res["echange"]["allie_id"] == bete["id"]


def test_un_echange_rate_ne_deplace_personne_mais_se_paie():
	"""Un effet offensif passe par le jet : raté, les PM sont partis (comme une frappe)."""
	garde, bete, doc = _face_a_face()
	garde["cc"] = 0
	res = resolve_action(doc, "competence", cible_id=bete["id"], competence=comp_ennemi())
	assert not res.get("hit") and "echange" not in res
	assert garde["pos"] == {"x": 3, "y": 5} and bete["pos"] == {"x": 4, "y": 5}
	assert garde["currentPM"] == 60 - 12


def test_on_ne_prend_pas_la_place_d_un_cadavre():
	garde, bete, doc = _face_a_face(pv=1)
	res = resolve_action(doc, "competence", cible_id=bete["id"],
						 competence=comp_ennemi(effets={"echange": 1, "degats": "1D6"}))
	assert not bete["vivant"] and "echange" not in res
	assert garde["pos"] == {"x": 3, "y": 5}


def test_un_echange_impossible_avec_un_ennemi_ne_coute_rien():
	garde, bete, doc = _face_a_face()
	bete["jeton"] = {"largeur": 2, "profondeur": 2, "forme": "ellipse"}
	bete["cap"] = "bas"
	res = resolve_action(doc, "competence", cible_id=bete["id"], competence=comp_ennemi())
	assert "grande créature" in res.get("error", "")
	assert garde["currentPM"] == 60


def test_la_garde_de_donnees_accepte_un_echange_sur_un_ennemi():
	import os, sys
	sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))
	import check_competences_doc as check
	doc = {"_id": "competence:x", "type": "competence", "vocation": "guerrier", "nom": "X",
		   "mode": "active", "cout_pm": 5, "cible": "ennemi", "portee": 1, "niveau": 2,
		   "effets": {"echange": 1}}
	assert not any("echange" in m for m in check.verifier_competence(doc, "x", niveaux=None))


def test_combat_seulement():
	assert capacite_utilisable_combat(comp())
	assert not competence_utilisable_exploration(comp())


def test_la_garde_de_donnees_refuse_un_echange_sans_allie():
	import os, sys
	sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))
	import check_competences_doc as check
	doc = {"_id": "competence:x", "type": "competence", "vocation": "guerrier", "nom": "X",
		   "mode": "active", "cout_pm": 5, "cible": "soi", "portee": 1, "niveau": 2,
		   "effets": {"echange": 1}}
	assert any("echange" in m for m in check.verifier_competence(doc, "x", niveaux=None))
