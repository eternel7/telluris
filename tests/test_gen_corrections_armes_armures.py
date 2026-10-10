"""dev/gen_corrections_armes_armures.py — un lot qui ne porte que le DIFF et ne décale jamais deux
fois : la table des malus est FIGÉE en (avant, après), sinon la règle « +1 » rejouée sur une
base déjà corrigée retirerait un cran de plus à chaque import.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_corrections_armes_armures as gen

VOCATIONS = {"_id": "rules:vocations", "_rev": "1-a", "value": [
	{"id": "guerrier", "equipement_de_base": ["item:Hache"]},
	{"id": "repurgateur", "equipement_de_base": ["item:Epee_argent"]},
]}
HACHE = {"_id": "item:Hache", "_rev": "2-b", "type": "item", "categorie": "arme", "rarete": "peu_commun",
		 "restriction": {"F": 14}, "bonus_malus_depl": -1, "note_admin": "posée à la main"}
ARGENT = {"_id": "item:Epee_argent", "_rev": "1-c", "type": "item", "categorie": "arme",
		  "rarete": "peu_commun", "restriction": {"Int": 10}}
PIQUE = {"_id": "item:Pique", "_rev": "1-d", "type": "item", "categorie": "arme", "bonus_malus_depl": -2}
BAGUETTE = {"_id": "item:Baguette", "_rev": "1-e", "type": "item", "categorie": "arme", "rarete": "rare"}
ROND = {"_id": "item:Rond", "_rev": "1-f", "type": "item", "categorie": "armure", "bonus": {"Ag": -1},
		"poids": [1.5, 3]}
DUMP = [VOCATIONS, HACHE, ARGENT, PIQUE, BAGUETTE, ROND]

MALUS = {"Hache": (-1, None), "Pique": (-2, -1)}
CHAMPS = {"Baguette": {"effets": {"regen_pm": 2}},
		  "Rond": {"poids": [1.8, 3], "bonus": {"Ag": gen.RETIRER}}}


def _gen(docs, **kw):
	kw.setdefault("malus", MALUS)
	kw.setdefault("champs", CHAMPS)
	kw.setdefault("raretes", {})
	kw.setdefault("restrictions", {})
	return gen.generer(docs, **kw)


def _par_id(docs):
	return {d["_id"]: d for d in docs}


def test_premier_passage():
	sortie, erreurs, avert = _gen(DUMP)
	assert erreurs == [] and avert == []
	d = _par_id(sortie)
	# Arme de départ : plus de restriction, commune, malus −1 retiré ; clé manuelle gardée.
	assert "restriction" not in d["item:Hache"] and d["item:Hache"]["rarete"] == "commun"
	assert "bonus_malus_depl" not in d["item:Hache"]
	assert d["item:Hache"]["note_admin"] == "posée à la main" and "_rev" not in d["item:Hache"]
	# L'Épée d'argent perd sa restriction mais reste peu commune (cadeau du répurgateur).
	assert "restriction" not in d["item:Epee_argent"] and d["item:Epee_argent"]["rarete"] == "peu_commun"
	assert d["item:Pique"]["bonus_malus_depl"] == -1
	assert d["item:Baguette"]["effets"] == {"regen_pm": 2}
	# Un `bonus` vidé disparaît.
	assert "bonus" not in d["item:Rond"] and d["item:Rond"]["poids"] == [1.8, 3]


def test_relance_apres_import_ne_decale_pas_une_seconde_fois():
	base = _par_id(DUMP)
	base.update(_par_id(_gen(DUMP)[0]))
	sortie, erreurs, avert = _gen(list(base.values()))
	assert sortie == [] and erreurs == [] and avert == []


def test_malus_retouche_a_la_main_est_laisse_et_signale():
	docs = [VOCATIONS, ARGENT, BAGUETTE, ROND, dict(HACHE, bonus_malus_depl=-1), dict(PIQUE, bonus_malus_depl=-4)]
	sortie, erreurs, avert = _gen(docs)
	assert "item:Pique" not in _par_id(sortie)                   # −4 : ni l'avant ni l'après
	assert any("item:Pique" in t for t in avert)


def test_id_absent_refuse_le_lot():
	_sortie, erreurs, _avert = _gen(DUMP, champs={"Fantome": {"poids": 1}})
	assert any("item:Fantome" in e for e in erreurs)


def test_regen_sur_arme_a_duree_refusee():
	docs = [VOCATIONS, HACHE, ARGENT, PIQUE, ROND, dict(BAGUETTE, effets={"buffs": {"V": -1}, "duree": 2})]
	_sortie, erreurs, _avert = _gen(docs)
	assert any("duree" in e for e in erreurs)


def test_regen_pm_jamais_commune():
	_sortie, erreurs, _avert = _gen(DUMP, raretes={"Baguette": "commun"})
	assert any("commun" in e for e in erreurs)


def test_restriction_relevee_une_seule_fois():
	docs = [VOCATIONS, HACHE, ARGENT, PIQUE, BAGUETTE, ROND,
			{"_id": "item:Arc", "type": "item", "categorie": "arme", "restriction": {"Ag": 14, "F": 10}}]
	table = {"Arc": ({"Ag": 14, "F": 10}, {"Ag": 19, "F": 15})}
	sortie, erreurs, avert = _gen(docs, restrictions=table)
	assert erreurs == [] and avert == []
	assert _par_id(sortie)["item:Arc"]["restriction"] == {"Ag": 19, "F": 15}
	base = _par_id(docs)
	base.update(_par_id(sortie))
	assert _gen(list(base.values()), restrictions=table)[0] == []          # pas de +10


def test_arme_de_depart_dans_la_table_des_restrictions_refusee():
	_s, erreurs, _a = _gen(DUMP, restrictions={"Hache": ({"F": 14}, {"F": 19})})
	assert any("item:Hache" in e and "départ" in e for e in erreurs)


def test_table_reelle_des_restrictions():
	# +5 AU TOTAL réparti entre les caractéristiques, jamais de baisse, mêmes caractéristiques
	# avant/après (le plafond « minimum de l'espèce porteuse » peut seulement retenir la hausse).
	assert gen.RESTRICTIONS
	for slug, (avant, apres) in gen.RESTRICTIONS.items():
		assert set(avant) == set(apres), slug
		assert all(apres[c] >= avant[c] for c in avant), slug
		assert sum(apres[c] - avant[c] for c in avant) <= 5, slug
		assert apres != avant, slug


def test_tables_reelles_sans_doublon_ni_conflit():
	# Une pièce ne peut pas recevoir deux raretés, et toute régén de PM vise une pièce non commune.
	for slug, modifs in gen.CHAMPS.items():
		if (modifs.get("effets") or {}).get("regen_pm"):
			assert gen.RARETES.get(slug, "rare") != "commun", slug
	assert all(apres is None or apres == avant + 1 for avant, apres in gen.MALUS_V_ARMES.values())
	assert all(avant < 0 for avant, _ in gen.MALUS_V_ARMES.values())
