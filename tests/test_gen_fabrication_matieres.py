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
	assert all(fabrication.apporte({"fabrication": gen.bloc_fabrication(b)}) for b in gen.MATIERES.values())


# ── Paliers : le gain suit la difficulté d'obtention ─────────────────────────────

def test_la_table_reelle_respecte_le_budget_de_chaque_palier():
	assert gen.erreurs_de_budget(gen.MATIERES) == []


def test_le_score_moyen_croit_strictement_avec_le_palier():
	moyennes = []
	for palier in sorted(gen.PALIERS):
		scores = [gen.score_matiere(e["modificateurs"], e["tags"])
				  for e in gen.MATIERES.values() if e["palier"] == palier]
		assert scores, "palier %d vide" % palier
		moyennes.append(sum(scores) / len(scores))
	assert moyennes == sorted(set(moyennes))


def test_aucun_effet_de_la_table_nest_inerte_ni_retourne():
	assert gen.effets_mal_diriges(gen.MATIERES) == []


def test_un_buff_positif_sur_une_matiere_darme_est_refuse():
	# Sur une arme, `effets` vise l'ENNEMI : une régén le soignerait.
	table = {"item:x": {"modificateurs": {"effets": {"regen_pv": 1, "duree": 3}},
						"tags": [gen.TAG_ARME]}}
	assert gen.effets_mal_diriges(table) == [
		"item:x : regen_pv sur une matière d'arme profiterait à l'ENNEMI"]


def test_un_venin_en_pv_negatif_est_refuse():
	# `consommables._as_int` le ramène à 0 : il ne ferait rien, nulle part.
	table = {"item:x": {"modificateurs": {"effets": {"pv": -5}}, "tags": [gen.TAG_ARME]}}
	assert any("négatif" in e for e in gen.effets_mal_diriges(table))


def test_un_score_hors_budget_est_refuse():
	table = {"item:x": {"palier": 1, "modificateurs": {"bonus_degats": 5}, "tags": []}}
	assert gen.erreurs_de_budget(table) == ["item:x : score 5 hors du budget %d-%d du palier 1"
											% gen.PALIERS[1]["budget"]]


def test_le_score_ne_compte_que_ce_qui_agit():
	eff = {"effets": {"pv": 5}}
	assert gen.score_matiere(eff, [gen.TAG_ARME]) == 0            # soin instantané sur une arme
	assert gen.score_matiere(eff, [gen.TAG_CONSOMMABLE]) == 1
	# Débuff : |Δ| × durée / 2.
	assert gen.score_matiere({"effets": {"buffs": {"R": -2}, "duree": 3}}) == 3


# ── Tags et rareté de l'item ─────────────────────────────────────────────────────

PARTIE = {"_id": "item:chimere_tete", "_rev": "2-z", "type": "item", "rarete": "commun",
		  "sous_categorie": "carcasse", "tags": ["monstre", "fabrication_armure", "partie_tete"]}
ENTREE_PARTIE = {"nom": "des Trois Visages", "modificateurs": {"bonus_degats": 4},
				 "palier": 3, "tags": [gen.TAG_ARME], "rarete_item": "rare"}


def test_les_tags_fabrication_sont_remplaces_et_les_autres_gardes():
	doc = gen.a_ecrire_depuis(ENTREE_PARTIE, PARTIE)
	assert doc["tags"] == ["monstre", "partie_tete", gen.TAG_ARME]
	assert doc["rarete"] == "rare"
	assert doc["fabrication"] == {"nom": "des Trois Visages", "modificateurs": {"bonus_degats": 4}}
	assert "palier" not in doc["fabrication"] and "_rev" not in doc


def test_une_partie_deja_a_jour_ne_repart_pas():
	a_jour = dict(PARTIE, tags=["monstre", "partie_tete", gen.TAG_ARME], rarete="rare",
				  fabrication=gen.bloc_fabrication(ENTREE_PARTIE))
	assert gen.a_ecrire_depuis(ENTREE_PARTIE, a_jour) is None


def test_une_entree_sans_tags_ne_touche_pas_aux_tags():
	doc = gen.a_ecrire_depuis(BLOC_ACIER, dict(PARTIE))
	assert doc["tags"] == PARTIE["tags"] and doc["rarete"] == "commun"


def test_une_partie_seulement_ouverte_par_tag_nest_pas_signalee_jamais_travaillee():
	sortie, _abs, jamais, _orph, _inch = gen.generer([PARTIE], {"item:chimere_tete": ENTREE_PARTIE})
	assert jamais == [] and [d["_id"] for d in sortie] == ["item:chimere_tete"]


def test_la_relance_des_carcasses_garde_tags_et_rarete_de_fabrication():
	"""`gen_carcasses_parties` régénère `tags` et `rarete` des parties : sans garde, sa relance
	défaisait ce générateur en silence."""
	from dev import gen_carcasses_parties as carc
	existant = dict(PARTIE, tags=["monstre", "partie_tete", gen.TAG_ARME], rarete="rare")
	genere = dict(PARTIE, tags=["monstre", "partie_tete"], rarete="commun")
	assert carc.a_ecrire_depuis(genere, existant) is None
	# Une rareté plus BASSE en base, elle, est bien remontée à celle de la carcasse.
	plus_bas = dict(existant, rarete="commun")
	assert carc.a_ecrire_depuis(dict(genere, rarete="peu_commun"), plus_bas)["rarete"] == "peu_commun"
