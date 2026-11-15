"""`dev/gen_reduction_zones.py` — réduction des zones d'influence des cartes de pays (Auteur, 15/11).

Données synthétiques en constantes (CLAUDE.md §20) :
1. Des ellipses voisines d'une zone de relief deviennent UN rectangle ; aucune case n'en perd une.
2. La mer ne compte pas dans le débordement, la terre si : un rectangle qui mordrait trop sur la
   terre est recoupé.
3. Le fond devient un rectangle couvrant toute la carte.
4. Les zones très dangereuse / danger N et les zones hors familles restent intactes.
5. Une zone qui n'y gagne rien garde ses formes ; un lieu déjà réduit est reconnu.
"""

import importlib.util
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gen_reduction_zones", RACINE / "dev" / "gen_reduction_zones.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

LARG, HAUT = 40, 20


def _ellipse(zone, x, y, w=4, h=4, rot=0, **extra):
	p = {"zone": zone, "x": x, "y": y, "w": w, "h": h, "rot": rot, "forme": "ellipse"}
	p.update(extra)
	return p


def _lieu(placements):
	return {"_id": "lieu:test", "dimensions": {"x": LARG, "y": HAUT}, "zone_influences": placements}


def _terre():
	# Terre : toute la moitié gauche (x < 30), en plaine ; à droite, la mer (aucune zone).
	return gen.rectangle_cases("zone:plaine_ouverte", 0, 0, 30, HAUT)


def _cases(placements, zone):
	out = set()
	for p in placements:
		if p["zone"] == zone:
			out |= gen.cases_de(p, LARG, HAUT)
	return out


def test_ellipses_voisines_de_relief_en_un_rectangle_sans_perte():
	chaine = [_ellipse("zone:montagne", x, 10) for x in (4, 7, 10, 13, 16)]
	lieu = _lieu([_terre()] + chaine)
	zi, rapport = gen.reduire(lieu, "zone:plaine_ouverte")
	montagnes = [p for p in zi if p["zone"] == "zone:montagne"]
	assert len(montagnes) == 1 and montagnes[0]["forme"] == "rectangle"
	assert _cases(chaine, "zone:montagne") <= _cases(montagnes, "zone:montagne")
	gen.controler(lieu["zone_influences"], zi, LARG, HAUT, "test")
	assert ("zone:montagne", len(chaine), 1) == rapport[0][:3]


def test_la_mer_ne_compte_pas_la_terre_si():
	mer = gen.mer(LARG, HAUT, gen.cases_de(_terre(), LARG, HAUT))
	assert (35, 5) in mer and (5, 5) not in mer
	# Deux taches en L sur la terre : leur englobant serait surtout de la terre vide → recoupé.
	S = {(x, 2) for x in range(2, 20)} | {(2, y) for y in range(2, 18)}
	assert len(gen.guillotine(S, mer, gen.SEUIL)) >= 2
	# La même forme en mer (hors de la terre) : le débordement en mer est gratuit.
	S_mer = {(x + 31, y) for (x, y) in S if x + 31 < LARG}
	assert len(gen.guillotine(S_mer, mer | S_mer, gen.SEUIL)) == 1


def test_fond_sur_toute_la_carte_et_lieu_deja_reduit():
	plaines = [gen.rectangle_cases("zone:plaine_ouverte", x, 0, 5, HAUT) for x in range(0, 30, 5)]
	lieu = _lieu(plaines + [_ellipse("zone:montagne", 5, 5)])
	assert not gen.deja_reduit(lieu, "zone:plaine_ouverte")
	zi, _ = gen.reduire(lieu, "zone:plaine_ouverte")
	fonds = [p for p in zi if p["zone"] == "zone:plaine_ouverte"]
	assert len(fonds) == 1
	assert len(_cases(fonds, "zone:plaine_ouverte")) == LARG * HAUT
	assert gen.deja_reduit(_lieu(zi), "zone:plaine_ouverte")


def test_intouchables_et_hors_familles_intacts():
	danger = [_ellipse(z, x, 10, profil_weights={"profil:veteran": 1})
			  for z, x in (("zone:tres_dangereuse", 4), ("zone:tres_dangereuse", 7), ("zone:zone_danger_3", 10))]
	rivieres = [_ellipse("zone:riviere", x, 4) for x in (4, 7, 10)]
	lieu = _lieu([_terre()] + danger + rivieres)
	zi, _ = gen.reduire(lieu, "zone:plaine_ouverte")
	assert [p for p in zi if p["zone"] in gen.INTOUCHABLES] == danger
	assert [p for p in zi if p["zone"] == "zone:riviere"] == rivieres


def test_zone_sans_gain_gardee():
	eparses = [_ellipse("zone:collines", 3, 3), _ellipse("zone:collines", 25, 16)]
	lieu = _lieu([_terre()] + eparses)
	zi, rapport = gen.reduire(lieu, "zone:plaine_ouverte")
	assert [p for p in zi if p["zone"] == "zone:collines"] == eparses
	assert all(r[0] != "zone:collines" for r in rapport)
