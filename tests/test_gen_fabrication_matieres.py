"""dev/gen_fabrication_matieres.py — un lot qui ne porte que le DIFF, relancé sur un dump frais.

Verrouille ce que le PUT complet de l'import rendait dangereux : réémettre un doc relu sur un
dump périmé, ou reconstruit sans les clés posées à la main.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_fabrication_matieres as gen
from utils import fabrication

BLOC_ACIER = {"nom": "en acier", "modificateurs": {"bonus_degats": 2}}
BLOC_SEL = {"nom": "au sel", "modificateurs": {"bonus_pm": 1}}
TABLE = {"item:acier": BLOC_ACIER, "item:sel": BLOC_SEL, "item:absente": BLOC_SEL}

ACIER = {"_id": "item:acier", "_rev": "3-x", "type": "item", "nom": "Lingot d'acier",
		 "sous_categorie": "acier", "note_admin": "posée à la main"}
SEL = {"_id": "item:sel", "_rev": "1-y", "type": "item", "nom": "Sel", "categorie": "composant"}
RECETTE = {"_id": "recette:epee", "type": "recette",
		   "matieres_premieres": [{"sous_categorie": "acier", "quantite": 1}]}
DUMP = [ACIER, SEL, RECETTE]


def _par_id(docs):
	return {d["_id"]: d for d in docs}


def test_premier_passage_nemet_que_les_docs_presents_repris_du_dump():
	sortie, absents, jamais, orphelins, inchanges = gen.generer(DUMP, TABLE)
	docs = _par_id(sortie)
	assert sorted(docs) == ["item:acier", "item:sel"]
	assert absents == ["item:absente"]                          # jamais créé de rien
	assert inchanges == [] and orphelins == []
	# Repris du dump : la clé manuelle survit au PUT complet, `_rev` est retiré.
	assert docs["item:acier"]["note_admin"] == "posée à la main"
	assert "_rev" not in docs["item:acier"]
	assert docs["item:acier"]["fabrication"] == BLOC_ACIER
	# Seul le sel n'est consommé par aucune recette (l'acier l'est par sous-catégorie).
	assert jamais == ["item:sel"]


def test_relance_apres_import_rend_un_lot_vide():
	premiere = gen.generer(DUMP, TABLE)[0]
	base = _par_id(DUMP)
	base.update(_par_id(premiere))
	sortie, _abs, _jam, orphelins, inchanges = gen.generer(list(base.values()), TABLE)
	assert sortie == []                                          # base à jour : lot vide
	assert sorted(inchanges) == ["item:acier", "item:sel"]
	assert orphelins == []


def test_seul_le_bloc_modifie_repart():
	base = _par_id(DUMP)
	base["item:acier"] = dict(ACIER, fabrication=BLOC_ACIER)
	base["item:sel"] = dict(SEL, fabrication={"nom": "ancien nom", "modificateurs": {}})
	sortie, _abs, _jam, _orph, inchanges = gen.generer(list(base.values()), TABLE)
	assert [d["_id"] for d in sortie] == ["item:sel"]
	assert sortie[0]["fabrication"] == BLOC_SEL
	assert inchanges == ["item:acier"]


def test_orphelins_listes_mais_jamais_ecrits_et_variantes_ignorees():
	pose_a_la_main = {"_id": "item:gemme", "type": "item",
					  "fabrication": {"nom": "serti", "modificateurs": {"bonus_pm": 1}}}
	variante = {"_id": "item:Epee_1a2b3c4d", "type": "item",
				"fabrication": {"base_item": "item:Epee", "matieres": [], "recette": "r"}}
	sortie, _abs, _jam, orphelins, _inch = gen.generer(DUMP + [pose_a_la_main, variante], TABLE)
	assert orphelins == ["item:gemme"]
	assert "item:gemme" not in {d["_id"] for d in sortie}


def test_erreurs_de_forme_hors_liste_blanche():
	assert gen.erreurs_de_forme(TABLE) == []
	assert gen.erreurs_de_forme({"item:x": {"nom": "", "modificateurs": {"slots": ["tete"]}}}) \
		== ["item:x : `slots` n'est pas un modificateur reconnu"]


def test_la_table_reelle_est_bien_formee_et_apporte():
	assert gen.erreurs_de_forme(gen.MATIERES) == []
	assert all(fabrication.apporte({"fabrication": b}) for b in gen.MATIERES.values())
