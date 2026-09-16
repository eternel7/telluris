# tests/test_sorts_renforts.py
#
# Deux règles nées de la suppression du champ `vocation` des sorts :
#   · le sort de DÉPART se choisit parmi les sorts niveau 0 de l'ÉCOLE NATIVE ;
#   · les composants d'une invocation ou d'un sort maintenu RENFORCENT le doc (durée et
#     nombre de créatures, entretien) via `sorts.doc_effectif` — le moteur lit ces champs
#     sur le doc, jamais dans `effets`.

from utils import combat as combat_mod
from utils.combat import build_joueur_snapshot, resolve_action
from utils.sorts import (
	INVOCATION_NOMBRE_MAX, doc_effectif, effets_effectifs, normaliser_sort,
	sort_de_depart_valide, sorts_depart_par_vocation,
)

import test_invocations as inv
from _fixtures_magie import combat, joueur, sort


RULES = {"value": [
	{"id": "druide", "magie": "Nature"},
	{"id": "chaman", "magie": "Nature"},
	{"id": "repurgateur", "magie": "Démonologie", "familles_exclues": ["invocation"]},
	{"id": "demoniste", "magie": "Démonologie"},
	{"id": "guerrier", "magie": ""},
]}


def _s(sid, magie, niveau=0, **extra):
	return {"_id": sid, "type": "sort", "nom": sid, "magie": magie, "niveau": niveau,
			"cout_pm": 5, **extra}


# ── Sort de départ : école native ────────────────────────────────────────────────

def test_un_sort_sans_vocation_est_un_sort_de_depart_de_son_ecole():
	s = normaliser_sort(_s("sort:ronces", "Nature"))
	assert sort_de_depart_valide(s, "druide", RULES)
	assert sort_de_depart_valide(s, "chaman", RULES), "même école, même liste"
	assert not sort_de_depart_valide(s, "demoniste", RULES)
	assert not sort_de_depart_valide(s, "guerrier", RULES), "vocation sans école"


def test_le_depart_exige_le_niveau_0():
	assert not sort_de_depart_valide(normaliser_sort(_s("sort:x", "Nature", niveau=1)),
									 "druide", RULES)
	assert not sort_de_depart_valide(None, "druide", RULES)


def test_une_famille_exclue_n_est_pas_un_sort_de_depart():
	pacte = normaliser_sort(_s("sort:pacte", "Démonologie", famille="invocation"))
	assert sort_de_depart_valide(pacte, "demoniste", RULES)
	assert not sort_de_depart_valide(pacte, "repurgateur", RULES)


def test_liste_de_depart_par_vocation():
	docs = [_s("sort:ronces", "Nature"), _s("sort:flamme", "Démonologie"),
			_s("sort:pacte", "Démonologie", famille="invocation"),
			_s("sort:haut", "Nature", niveau=2)]
	out = sorts_depart_par_vocation(lambda q: docs, RULES)
	ids = {voc: [x["id"] for x in lst] for voc, lst in out.items()}
	assert ids == {
		"druide": ["sort:ronces"], "chaman": ["sort:ronces"],
		"repurgateur": ["sort:flamme"], "demoniste": ["sort:flamme", "sort:pacte"],
	}


def test_le_repli_d_ecole_par_vocation_tient_toujours():
	"""Un doc ancien sans `magie` garde son école dérivée de `vocation` (aucune migration)."""
	ancien = normaliser_sort({"_id": "sort:vieux", "type": "sort", "vocation": "druide",
							  "niveau": 0, "cout_pm": 3})
	assert sort_de_depart_valide(ancien, "druide", RULES)


# ── doc_effectif : renforts de composant ─────────────────────────────────────────

def _invocation(**inv_bloc):
	return normaliser_sort(_s("sort:meute", "Nature", composants=[
		{"item": "item:crocs", "consomme": True, "bonus": {"invocation_nombre": 1, "invocation_duree": 2}},
		{"item": "item:os", "consomme": False, "bonus": {"invocation_duree": 1}},
	], invocation={"espece": "espece:loup", "nombre": 2, "duree": 3, **inv_bloc}))


def test_les_renforts_s_additionnent_au_bloc_invocation():
	s = _invocation()
	doc = doc_effectif(s, effets_effectifs(s, ["item:crocs", "item:os"]))
	assert doc["invocation"]["nombre"] == 3
	assert doc["invocation"]["duree"] == 6
	assert s["invocation"] == {"espece": "espece:loup", "profil": "", "nombre": 2, "duree": 3}, \
		"la vue normalisée n'est jamais mutée"


def test_sans_composant_le_doc_est_inchange():
	s = _invocation()
	assert doc_effectif(s, effets_effectifs(s, [])) == s


def test_le_nombre_reste_borne_apres_addition():
	s = _invocation(nombre=INVOCATION_NOMBRE_MAX)
	doc = doc_effectif(s, effets_effectifs(s, ["item:crocs"]))
	assert doc["invocation"]["nombre"] == INVOCATION_NOMBRE_MAX


def test_la_reduction_d_entretien_ne_descend_pas_sous_1():
	s = normaliser_sort(_s("sort:mur", "Élémentaire", maintien=3, composants=[
		{"item": "item:a", "consomme": True, "bonus": {"maintien_reduction": 2}},
		{"item": "item:b", "consomme": False, "bonus": {"maintien_reduction": 1}},
	]))
	assert doc_effectif(s, effets_effectifs(s, ["item:a"]))["maintien"] == 1
	assert doc_effectif(s, effets_effectifs(s, ["item:a", "item:b"]))["maintien"] == 1, \
		"à 0, le sort cesserait d'être maintenu et changerait de nature"


def test_la_reduction_est_sans_effet_sur_un_sort_non_maintenu():
	s = normaliser_sort(_s("sort:x", "Nature", composants=[
		{"item": "item:a", "consomme": True, "bonus": {"maintien_reduction": 2}}]))
	assert doc_effectif(s, effets_effectifs(s, ["item:a"]))["maintien"] == 0


# ── Bout en bout dans le moteur ──────────────────────────────────────────────────

def test_une_invocation_renforcee_appelle_plus_de_creatures_plus_longtemps(monkeypatch):
	monkeypatch.setattr(combat_mod, "get_doc", {"espece:demon_servant": inv.SERVANT}.get)
	lanceur = inv._lanceur(pm=60)
	doc = inv._combat([lanceur], [inv._monstre()])
	s = normaliser_sort(inv._sort_invocation(nombre=1, duree=3, composants=[
		{"item": "item:sang", "consomme": True, "bonus": {"invocation_nombre": 1, "invocation_duree": 2}}]))
	effets = effets_effectifs(s, ["item:sang"])
	res = resolve_action(doc, "sort", sort={"doc": doc_effectif(s, effets), "effets": effets})

	assert "error" not in res
	assert len(res["invoques"]) == 2
	assert all(i["restants"] == 5 for i in res["invoques"])


def test_un_entretien_reduit_est_celui_qui_est_preleve(monkeypatch):
	monkeypatch.setattr(combat_mod.random, "randint", lambda a, b: 50)
	mage = joueur(pm=30)
	d = combat([mage])
	arg = sort(cout_pm=5, maintien=4, cible="soi", effets={"buffs": {"R": 10}},
			   composants=[{"item": "item:cristal", "consomme": False,
							"bonus": {"maintien_reduction": 1}}])
	s = arg["doc"]
	effets = effets_effectifs(s, ["item:cristal"])
	resolve_action(d, "sort", sort={"doc": doc_effectif(s, effets), "effets": effets})

	assert mage["concentrations"][0]["maintien"] == 3
