"""Catalogues d'admin /admin/sorts et /admin/competences (utils/catalogue_capacites)."""
from utils import catalogue_capacites as cc

VOCS = {"value": [
	{"id": "guerrier", "label": "Guerrier", "icon": "⚔️", "magie": ""},
	{"id": "mage", "label": "Magicien", "icon": "🧙", "magie": "Bataille"},
	{"id": "templier", "label": "Templier", "icon": "🛡", "magie": "Bataille"},
]}


def _sort(_id, **kw):
	return {"_id": _id, "type": "sort", "nom": _id, "cout_pm": 5, "niveau": 0, **kw}


def _comp(_id, **kw):
	return {"_id": _id, "type": "competence", "nom": _id, "niveau": 0, **kw}


def test_sorts_groupes_par_ecole_avec_vocations_qui_la_pratiquent():
	docs = [_sort("sort:b", magie="Bataille"), _sort("sort:n", magie="Nature"),
			_sort("sort:v", vocation="mage"),    # repli d'école d'un doc ancien
			_sort("sort:x"), {"_id": "item:a", "type": "item"}]
	cat = cc.catalogue_sorts(docs, {}, VOCS)
	assert [g["cle"] for g in cat["groupes"]] == ["Bataille", "Nature", cc.SANS_ECOLE]
	bataille = cat["groupes"][0]
	assert {e["id"] for e in bataille["entrees"]} == {"sort:b", "sort:v"}
	assert bataille["detail"] == "Magicien, Templier"


def test_formule_gardee_en_texte_et_valeurs_presentes():
	doc = _sort("sort:dard", magie="Bataille", cible="ennemi", portee="3+{Int/20}",
				maintien="5-{Vol/30}", effets={"degats": "1D{Int/5}", "buffs": {"R": "{Vol/5}"}})
	e = cc.entree_sort(doc, {}, VOCS)
	assert e["portee"] == "3+{Int/20}"
	assert e["maintien"] == "5-{Vol/30}"
	assert e["effets"]["formules_texte"]["degats"] == "1D{Int/5}"
	assert e["effets"]["formules_texte"]["buffs.R"] == "{Vol/5}"
	assert e["effets"]["buffs"]["R"] > 0     # présence et signe justes pour le libellé
	assert e["doc"] is doc


def test_composants_resolus_et_toujours_disponibles():
	doc = _sort("sort:c", magie="Bataille", effets={"buffs": {"F": 10}},
				composants=[{"item": "item:bougie", "consomme": True, "bonus": {"duree": 2}},
							{"item": "item:inconnu", "consomme": False, "bonus": {"buffs": {"F": 5}}}])
	e = cc.entree_sort(doc, {"item:bougie": {"nom": "Bougie", "icon": "🕯️"}}, VOCS)
	assert [(c["nom"], c["consomme"], c["disponible"]) for c in e["composants"]] == [
		("Bougie", True, True), ("item:inconnu", False, True)]
	assert cc.items_composants([doc]) == ["item:bougie", "item:inconnu"]


def test_doc_refuse_par_le_moteur_reste_liste():
	e = cc.entree_sort(_sort("sort:zero", magie="Bataille", cout_pm=0), {}, VOCS)
	assert e["invalide"] and e["ecole"] == "Bataille"
	c = cc.entree_competence(_comp("competence:orpheline"))
	assert c["invalide"] and c["vocation"] == cc.SANS_VOCATION


def test_competences_dans_l_ordre_des_vocations_inconnues_ensuite():
	docs = [_comp("competence:t", vocation="templier"), _comp("competence:g", vocation="guerrier"),
			_comp("competence:z", vocation="zelote"), _comp("competence:o")]
	cat = cc.catalogue_competences(docs, VOCS)
	assert [g["cle"] for g in cat["groupes"]] == ["guerrier", "templier", "zelote", cc.SANS_VOCATION]
	assert cat["groupes"][0]["label"] == "Guerrier" and cat["groupes"][0]["icon"] == "⚔️"
	assert cat["groupes"][2]["label"] == "zelote"


def test_competence_passive_et_active():
	p = cc.entree_competence(_comp("competence:p", vocation="guerrier", mode="passive",
								   effets={"buffs": {"R": 8}}))
	a = cc.entree_competence(_comp("competence:a", vocation="guerrier", mode="active",
								   cible="ennemi", cout_pm=4, effets={"degats": "1D6"}))
	assert p["mode"] == "passive" and p["effets"]["buffs"]["R"] == 8
	assert a["mode"] == "active" and a["jet"] == "cc" and a["cout_pm"] == 4
