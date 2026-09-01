# utils/indicateurs.py
# Marques « ! » / « ? » posées sur les LIEUX (boutons de sous-lieux de la sidebar).
# Convention MMO : « ! » = une offre neuve t'attend, « ? » = une quête en cours attend une
# remise ou une rencontre ici. La marque d'un PNJ et celle d'un choix de dialogue vivent
# ailleurs (`utils/pnj.marque_noeud` / `marque_de_condition`, dérivées des conditions).
#
# ⚠️ ON NE POSE JAMAIS DE « ! » SUR UN BOUTON DE SOUS-LIEU. Les offres sont des champs
# TRANSITOIRES tirés au sort à l'ENTRÉE (`transport_offert`, `escorte_offerte`,
# `rang_offert`), posés par des `poser_*` qui MUTENT le personnage et ne valent que pour le
# lieu COURANT. Savoir « il y a une offre chez le voisin » exigerait de rejouer le tirage
# sur un autre lieu : effet de bord, non idempotent, menteur. Le « ! » reste donc réservé au
# PNJ du lieu courant et à ses choix, où il est exact par construction.
#
# ⚠️ AUCUNE LECTURE DB — ni `get_doc`, ni `find_docs`. Tout est dérivé de
# `character["quetes_actives"]` par les PRÉDICATS EXISTANTS, qu'on ne recopie jamais : on
# bâtit l'ensemble des lieux CANDIDATS depuis les quêtes, puis on demande son verdict à
# chacun. C'est ce qui rend la map republiable partout sans coût (contrairement à
# `relations_lieux`, cf. CLAUDE.md Conventions §10).
#
# ⛔ Ne JAMAIS appeler d'ici `quetes.remplir_tableau` (~38 requêtes), `quetes.lister_offres`
# (elle SUPPRIME des docs), `marche.relations_lieux_payload` ou `quete_detail` : tous
# relisent des docs `lieu:*`, les plus gros du jeu et exclus du cache de requête.
#
# ⚠️ MODULE À PART, obligatoire : il importe quetes + chasse + transport + escorte. Le loger
# dans `utils/quetes.py` créerait un cycle (`utils/escorte.py` importe `quetes`) ; dans
# `utils/lieux.py`, ce serait pire (`utils/acces.py`, qu'il importe, fait déjà un import
# PARESSEUX de `quetes` pour cette raison exacte). Personne n'importe `indicateurs` →
# aucun cycle possible.

from models import character_stats
from utils import chasse, escorte, quetes, transport

MARQUE_RAPPORT = "?"

# Sources de quête `chasse` — tableau de guilde, épreuve de rang, commission de donjon.
# ⚠️ C'est le TYPE D'OBJECTIF qui aiguille vers `chasse.chasse_accomplie`, jamais la source :
# `chasse_accomplie` a `quantite` par défaut **1**, `quetes.objectif_atteint` par défaut **0**
# (piège documenté dans CLAUDE.md). Utiliser le mauvais des deux marquerait « à rendre » une
# chasse à peine acceptée, dont l'objectif ne porte pas le champ.


def _marquer(marques: dict, lieu_id) -> None:
	"""Pose la marque de remise sur un lieu, si l'id en est bien un."""
	if isinstance(lieu_id, str) and lieu_id:
		marques[lieu_id] = MARQUE_RAPPORT


def marques_lieux(character: dict) -> dict:
	"""`{lieu_id: "?"}` — les lieux où une quête active attend quelque chose du joueur.

	Renvoie TOUS les lieux concernés, **lieu courant inclus** : c'est gratuit, indépendant de
	`links`, et ça évite d'appeler `get_lieu_links` là où il n'est pas déjà appelé. C'est le
	client qui fait l'intersection avec les portes qu'il affiche.

	| objectif            | lieu marqué                      | quand                     |
	|---------------------|----------------------------------|---------------------------|
	| transport aller     | `objectif.cible` (destinataire)  | cargaison pas encore remise |
	| transport retour    | `giver`                          | livrée, reste à rendre compte |
	| escorte rendez-vous | `objectif.rencontre.lieu`        | `rencontre_at` absent     |
	| escorte dépose      | `objectif.cible`                 | personne récupérée        |
	| chasse / rang / commission | `giver`                   | élite abattue             |
	| kill / collect / visite | `giver`                      | objectif rempli           |
	"""
	if not character_stats.INDICATEURS_ACTIFS:
		return {}
	marques: dict = {}
	for q in (character or {}).get("quetes_actives") or []:
		obj = q.get("objectif") or {}
		type_ = obj.get("type")
		giver = q.get("giver")
		if type_ == "transport":
			# Les deux étapes sont exclusives par construction : `transport_a_livrer` exclut
			# les courses déjà livrées, `retour_attendu` n'accepte qu'elles.
			cible = obj.get("cible")
			if isinstance(cible, str) and transport.transport_a_livrer(character, cible):
				_marquer(marques, cible)
			if isinstance(giver, str) and transport.retour_attendu(character, giver):
				_marquer(marques, giver)
		elif type_ == "escorte":
			# ⚠️ EXACTEMENT UNE des deux étapes est marquée à la fois. `escorte_vers` ne teste
			# PAS `rencontre_at` (elle ne filtre que sur `objectif.cible`) : sans la garde, la
			# destination porterait un « ? » alors que la personne n'a pas encore été retrouvée
			# — le joueur irait déposer quelqu'un qu'il n'a pas.
			rdv = (obj.get("rencontre") or {}).get("lieu")
			if isinstance(rdv, str) and escorte.rencontre_attendue(character, rdv):
				_marquer(marques, rdv)
			elif q.get("rencontre_at"):
				cible = obj.get("cible")
				if isinstance(cible, str) and escorte.escorte_vers(character, cible):
					_marquer(marques, cible)
		elif type_ == "chasse":
			if chasse.chasse_accomplie(q):
				_marquer(marques, giver)
		else:
			# `kill` / `collect` / `visite` — le générique, `quantite` par défaut 0.
			if quetes.objectif_atteint(character, q):
				_marquer(marques, giver)
	return marques
