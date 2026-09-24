"""Ce que `routers/commande.py` ÉCRIT et RENVOIE — les deux défauts qu'on ne voit pas en
lisant les modules purs.

⚠️ Ce fichier existe pour un défaut précis, et coûteux : le payload servait une liste de
matières que seule la PIÈCE peut définir, en appelant `_matieres_vue` avec la mauvaise
arité. Il levait donc **après l'écriture** — commande passée, annulée ou retirée en base,
500 côté client, listes jamais redessinées. Le joueur recliquait, et commandait deux fois.

Deux contrats tenus ici :
- tout endpoint qui bouge une commande renvoie les DEUX listes du panneau (CLAUDE.md §10),
  y compris dans une maison qui fabrique sur mesure, et seulement celles de CE lieu ;
- une commande sur mesure mise en attente garde ses matières (§7 cas C), sans quoi
  « Relancer » rend la pièce nue.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from routers import commande as rc  # noqa: E402
from utils import characters, commande as commande_util, marche  # noqa: E402


CATEGORIE_SUR_MESURE = "grand_arsenal"   # une des `LIEU_CATEGORIES_FUSION`

RECETTE = {
	"_id": "recette:payload_epee",
	"type": "recette",
	"lieu_categorie": CATEGORIE_SUR_MESURE,
	"objet_final": "Epee_longue",
	"quantite_produite": 1,
	"matieres_premieres": [{"item": "item:fer", "quantite": 2}],
}

_DB = {
	"item:Epee_longue": {"_id": "item:Epee_longue", "nom": "Épée longue", "icon": "⚔️",
						 "categorie": "arme", "sous_categorie": "", "slots": [], "poids": 2.0},
	"item:fer": {"_id": "item:fer", "nom": "Lingot de fer", "categorie": "metal",
				 "sous_categorie": "fer", "slots": [], "poids": 3.0,
				 "fabrication": {"nom": "en fer", "modificateurs": {"bonus_degats": 1}}},
}

LIEU = {"_id": "lieu:grand_arsenal", "categorie": CATEGORIE_SUR_MESURE,
		"label": "Le Grand Arsenal", "stock_vente": [{"item_id": "item:fer", "qty": 4}]}

_MONDE = dict(_DB, **{LIEU["_id"]: LIEU})


@pytest.fixture
def atelier(monkeypatch):
	"""Le lieu, la recette et les dépendances de bordure du payload. Seuls `commandes` et
	`catalogue` nous intéressent : le reste (sac, vitrine, bourse) est stubbé — il a ses
	propres tests, et le laisser vrai demanderait une base.

	⚠️ `_matieres_fab_memo` semé (cf. `test_commande.py`) : sans lui, l'univers des matières
	irait interroger la base, injoignable ici."""
	marche.reset_prix_cache()
	monkeypatch.setattr(marche, "_recettes_all", [RECETTE])
	monkeypatch.setattr(marche, "_matieres_fab_memo", ["item:fer"])
	monkeypatch.setattr(rc, "get_doc", _MONDE.get)
	monkeypatch.setattr(characters, "get_doc", _MONDE.get)
	monkeypatch.setattr(rc, "_inventory_payload", lambda c: {"inventaire": []})
	monkeypatch.setattr(rc, "_marchand_vendables", lambda *a, **k: [])
	monkeypatch.setattr(rc, "resolve_stock_vente", lambda *a, **k: [])
	monkeypatch.setattr(rc.recrutement, "porteurs_effectifs", lambda *a, **k: [])
	yield
	marche.reset_prix_cache()


def _character(commandes=()):
	return {"_id": "character:j", "lieu": LIEU["_id"], "inventaire": [], "or": 10,
			"commandes": list(commandes)}


def _payload(character):
	return rc._payload_commande(character, LIEU, None, 1000, message="fait")


def test_la_maison_fabrique_bien_sur_mesure():
	# Le garde-fou du fichier : sans lui, tous les tests passeraient par la branche facile.
	assert commande_util.lieu_fabrique_sur_mesure(LIEU) is True


def test_le_payload_se_construit_dans_une_maison_sur_mesure(atelier):
	# ⚠️ LE test de non-régression : c'est ici que `_matieres_vue` levait, APRÈS l'écriture.
	payload = _payload(_character())
	assert payload["catalogue"][0]["item_id"] == "item:Epee_longue"
	assert payload["commandes"] == []


def test_le_payload_renvoie_les_commandes_du_joueur(atelier):
	cmd = commande_util.nouvelle_commande(LIEU, "item:Epee_longue", {"total": 12}, now=1000)
	payload = _payload(_character([cmd]))
	assert [c["id"] for c in payload["commandes"]] == [cmd["id"]]
	assert payload["commandes"][0]["nom"] == "Épée longue"


def test_le_payload_ne_sert_aucune_liste_de_matieres(atelier):
	"""Elle dépend de la PIÈCE (`fabrication_<famille>`), qu'une annulation ou un retrait ne
	connaissent pas : c'est `/api/commande/matieres` qui la sert, à l'ouverture de l'overlay.
	La resservir ici, c'était la servir fausse — ou lever."""
	assert "matieres" not in _payload(_character())


# ── « Vos commandes » ne montre que CET atelier ────────────────────────────────

AILLEURS = {"_id": "lieu:atelier_d_empennage", "categorie": "atelier_de_l_empenneur"}


def test_une_commande_passee_ailleurs_nest_pas_listee(atelier):
	"""Tout se joue sur place : on retire chez celui qui a fabriqué et on relance là où l'on a
	commandé. Une ligne d'un autre atelier n'offrirait ici que des boutons qui refusent — et
	c'est ce qui affichait « Empennage de flèches » à la Maison des Conserves."""
	ici = commande_util.nouvelle_commande(LIEU, "item:Epee_longue", {"total": 12}, now=1000)
	la_bas = commande_util.nouvelle_commande(AILLEURS, "item:Epee_longue", {}, now=1000)
	payload = _payload(_character([la_bas, ici]))
	assert [c["id"] for c in payload["commandes"]] == [ici["id"]]


def test_la_commande_dailleurs_reste_sur_le_personnage(atelier):
	# Masquée, jamais supprimée : elle réapparaît quand le joueur repasse la bonne porte.
	la_bas = commande_util.nouvelle_commande(AILLEURS, "item:Epee_longue", {}, now=1000)
	character = _character([la_bas])
	_payload(character)
	assert [c["id"] for c in character["commandes"]] == [la_bas["id"]]
	assert rc._vue_commandes(character, 1000, AILLEURS["_id"])[0]["id"] == la_bas["id"]


# ── Cas C : une commande en attente garde sa personnalisation ───────────────────

def _passer(monkeypatch, character, body):
	"""Appelle l'endpoint `passer` pour de vrai — c'est son CALL SITE qui est en cause, pas
	`nouvelle_commande`. Les bordures (personnage sélectionné, relation, save) sont stubbées."""
	monkeypatch.setattr(rc, "get_selected_character", lambda u: character)
	monkeypatch.setattr(rc, "get_relation", lambda *a, **k: {"value": 50})
	monkeypatch.setattr(rc, "save_doc", lambda doc: doc)
	return asyncio.run(rc.passer_commande({"_id": "user:j"}, body))


def test_une_commande_sur_mesure_en_attente_garde_ses_matieres(atelier, monkeypatch):
	"""⚠️ Le joueur commande une épée « en fer » sans fer, ni sur lui ni au comptoir : la
	commande naît en attente. Sans `base_item`/`matieres`, « Relancer » la re-résout depuis
	`base_item or item` et `matieres` — et lui rendait une épée NUE, sans un mot. C'est le
	chemin ordinaire depuis que le catalogue du monde alimente la liste des matières."""
	LIEU["stock_vente"] = []                      # ni en rayon…
	character = _character()                      # …ni dans le sac
	rep = _passer(monkeypatch, character,
				  {"item_id": "item:Epee_longue", "matieres": [{"item": "item:fer",
																"quantite": 1}]})
	LIEU["stock_vente"] = [{"item_id": "item:fer", "qty": 4}]

	enr = character["commandes"][0]
	assert enr["statut"] == commande_util.ETAT_ATTENTE_MATERIAUX
	assert enr["base_item"] == "item:Epee_longue"
	assert enr["matieres"] == [{"item": "item:fer", "quantite": 1}]
	assert enr["paye"] == 0                       # rien débité, rien prélevé
	assert rep["commandes"][0]["sur_mesure"] is True


def test_une_quantite_de_matiere_au_dela_du_plafond_est_refusee(atelier, monkeypatch):
	"""L'apport additif est multiplié par la quantité : « fer ×20 » donnait +20 dégâts. Le
	client envoie toujours 1 — c'est la requête FORGÉE que ce plafond ferme, avant tout écrit."""
	from fastapi import HTTPException
	from models import character_stats
	character = _character()
	trop = int(character_stats.COMMANDE_QUANTITE_MAX) + 1
	with pytest.raises(HTTPException) as e:
		_passer(monkeypatch, character, {"item_id": "item:Epee_longue",
										 "matieres": [{"item": "item:fer", "quantite": trop}]})
	assert e.value.status_code == 422
	assert character["commandes"] == []


def test_la_quantite_au_plafond_passe(atelier, monkeypatch):
	from models import character_stats
	character = _character()
	_passer(monkeypatch, character, {"item_id": "item:Epee_longue", "matieres": [
		{"item": "item:fer", "quantite": int(character_stats.COMMANDE_QUANTITE_MAX)}]})
	assert len(character["commandes"]) == 1


def test_une_commande_de_catalogue_en_attente_ne_devient_pas_sur_mesure(atelier, monkeypatch):
	# `base_item` reste vide sans matière demandée : c'est lui qui allume le ✨.
	LIEU["stock_vente"] = []
	character = _character()
	_passer(monkeypatch, character, {"item_id": "item:Epee_longue"})
	LIEU["stock_vente"] = [{"item_id": "item:fer", "qty": 4}]

	enr = character["commandes"][0]
	assert enr["statut"] == commande_util.ETAT_ATTENTE_MATERIAUX
	assert enr["base_item"] == "" and enr["matieres"] == []
