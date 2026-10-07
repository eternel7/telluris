"""Lignes de sidebar d'une propriété (`utils/proprietes.vue_sidebar`) — source unique de /play
et de la resync d'embauche/renvoi (Convention §10 : embaucher ne recharge plus la page).

Verrouille : seuls les ATELIERS (employé actif avec une catégorie) ont leur ligne 🏷️ ; la
caisse n'existe qu'avec un atelier, toujours pour le propriétaire, pour un visiteur seulement
sans gardien au poste (le vol)."""

from utils import proprietes


CAT = {
	"amenagements": [
		{"id": "loge_gardien", "nom": "Loge", "capacite": {"postes": {"gardien": 1}},
		 "effets": {"garde": True}},
	],
	"metiers": [
		{"id": "gardien", "label": "Gardien"},
		{"id": "forgeron", "label": "Forgeron"},
	],
}


def _employe(eid, metier, categorie=None, poste=None, statut=proprietes.EMPLOYE_ACTIF):
	e = {"_id": eid, "type": proprietes.TYPE_EMPLOYE, "prenom": "Jehan", "nom": eid,
		 "metier": metier, "statut": statut}
	if categorie:
		e["categorie"] = categorie
	if poste:
		e["poste"] = poste
	return e


def _prop(amenagements=()):
	return {"_id": "propriete:p", "mode": proprietes.MODE_ACHAT, "amenagements": list(amenagements)}


FORGERON = _employe("employe:f", "forgeron", categorie="forge")
GARDIEN = _employe("employe:g", "gardien", poste="loge_gardien")


def test_seuls_les_ateliers_ont_leur_ligne():
	renvoye = _employe("employe:r", "forgeron", categorie="forge", statut=proprietes.EMPLOYE_RENVOYE)
	vue = proprietes.vue_sidebar(_prop(), CAT, [FORGERON, GARDIEN, renvoye], proprietes.PROPRIETAIRE)
	assert [a["id"] for a in vue["ateliers"]] == ["employe:f"]
	assert vue["ateliers"][0]["metier"] == "Forgeron"
	assert vue["ateliers"][0]["nom"] == proprietes.nom_personnage(FORGERON)


def test_pas_d_atelier_pas_de_caisse():
	assert proprietes.vue_sidebar(_prop(), CAT, [GARDIEN], proprietes.PROPRIETAIRE)["caisse_accessible"] is False


def test_caisse_proprietaire_et_visiteur_sans_gardien():
	gardee = _prop(["loge_gardien"])
	employes = [FORGERON, GARDIEN]
	assert proprietes.vue_sidebar(gardee, CAT, employes, proprietes.PROPRIETAIRE)["caisse_accessible"] is True
	assert proprietes.vue_sidebar(gardee, CAT, employes, proprietes.VISITEUR)["caisse_accessible"] is False
	assert proprietes.vue_sidebar(_prop(), CAT, [FORGERON], proprietes.VISITEUR)["caisse_accessible"] is True
