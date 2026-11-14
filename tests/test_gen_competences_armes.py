# tests/test_gen_competences_armes.py
#
# Règles du générateur `dev/gen_competences_armes.py` (exigence d'arme posée sur les
# compétences), sur des docs construits ici — jamais sur un `*_a_importer.json` (CLAUDE.md §20).

import importlib.util
import os

from utils import exigence_arme

_CHEMIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
					   "dev", "gen_competences_armes.py")
_spec = importlib.util.spec_from_file_location("gen_competences_armes", _CHEMIN)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def _doc(slug="x", **champs):
	doc = {"_id": f"competence:{slug}", "type": "competence", "vocation": "guerrier",
		   "mode": "active", "cible": "ennemi", "jet": "cc", "nom": "N", "description": "",
		   "effets": {"degats": "1D6"}}
	doc.update(champs)
	return doc


def test_regles_par_defaut():
	assert gen.regle(_doc())[0] == {"mode": "cac"}
	assert gen.regle(_doc(jet="cd", nom="Tir d'élite"))[0] == {"mode": "tir"}
	assert gen.regle(_doc(jet="cd", nom="Flèche rapide"))[0] == {"mode": "tir", "tags": ["arc"]}
	# Ni magie, ni frappe sans dés, ni soutien, ni passive.
	assert gen.regle(_doc(jet="magique"))[0] is None
	assert gen.regle(_doc(effets={"buffs": {"V": -2}, "duree": 2}))[0] is None
	assert gen.regle(_doc(cible="soi"))[0] is None
	assert gen.regle(_doc(mode="passive"))[0] is None


def test_l_exception_l_emporte_sur_la_regle():
	assert gen.exigence_de(_doc("paume_de_force"))[:2] == (None, "moine : mains nues ou bâton")
	assert gen.exigence_de(_doc("couteaux_de_lancer", jet="cd"))[0] == {"mode": "jet"}
	assert gen.exigence_de(_doc("autre"))[2] == "règle"


def test_traits_tir_ou_jet_et_textes_reecrits_sans_toucher_l_id():
	for slug in gen.TRAITS:
		assert gen.EXCEPTIONS[slug][0] == {"mode": ["tir", "jet"]}, slug
	doc = _doc("fleche_rapide", jet="cd", nom="Flèche rapide", description="Encoche, vise, lâche.")
	apres = gen.textes_reecrits(doc)
	assert (apres["_id"], apres["nom"]) == ("competence:fleche_rapide", "Trait rapide")
	assert "flèche" not in apres["description"].lower()
	# Nom inchangé (None) : seul le texte bouge ; hors table : le doc tel quel.
	assert gen.textes_reecrits(_doc("tir_precis", nom="Tir précis"))["nom"] == "Tir précis"
	autre = _doc("autre")
	assert gen.textes_reecrits(autre) is autre


def test_toutes_les_exceptions_sont_des_exigences_valides():
	for slug, (arme, motif) in gen.EXCEPTIONS.items():
		assert motif, slug
		assert arme is None or exigence_arme.normaliser_arme(arme) is not None, slug


def test_tags_manquants_realigne_une_variante_sur_sa_base_sans_la_contredire():
	base = {"tags": ["cac", "tranchant", "legere"]}
	assert gen.tags_manquants({"tags": ["cac", "tranchant"]}, base) == ["legere"]
	assert gen.tags_manquants({"tags": ["cac", "tranchant", "legere"]}, base) == []
	# Une typologie contraire déjà portée n'est pas contredite.
	assert gen.tags_manquants({"tags": ["cac", "lourde"]}, base) == ["tranchant"]
	# Matériau d'armure : exclusif aussi ; variante sans tags (None) : tout est repris.
	assert gen.tags_manquants({"tags": ["armure_metal"]}, {"tags": ["armure_cuir"]}) == []
	assert gen.tags_manquants({"tags": None}, {"tags": ["armure_cuir"]}) == ["armure_cuir"]


def test_avec_arme_place_le_champ_apres_jet_et_le_retire_si_aucun():
	doc = _doc(arme={"mode": "tir"})
	cles = list(gen._avec_arme(doc, {"mode": "cac"}))
	assert cles[cles.index("jet") + 1] == "arme"
	assert "arme" not in gen._avec_arme(doc, None)
