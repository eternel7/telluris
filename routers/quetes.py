# routers/quetes.py
# Endpoints du tableau de quêtes d'une guilde (`categorie:"guilde_aventurier"`).
# Le moteur (utils/quetes.py) génère/complète les offres à partir du lieu PARENT ;
# ici on gère l'interaction joueur : consulter le tableau, accepter, terminer, abandonner.
# Pattern calqué sur routers/user.py : get_selected_character → muter → save_doc is None ⇒ 409.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, find_docs, delete_doc
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, cuivre_to_purse, money_to_cuivre,
	resolve_item_ref, charge_max_of,
)
from utils import quetes
from utils import focalisation
from utils import recrutement
from utils import escorte
from utils import indicateurs
from utils.marche import debit_character
from utils import marche
from models import character_stats

quetes_router = APIRouter()

GUILDE_CATEGORIE = "guilde_aventurier"


def _guild_lieu(character: dict) -> dict:
	"""Doc du lieu courant si c'est une guilde d'aventuriers ; 403 sinon."""
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or lieu_doc.get("categorie") != GUILDE_CATEGORIE:
		raise HTTPException(status_code=403, detail="Vous n'êtes pas dans une guilde d'aventuriers.")
	return lieu_doc


def _offre_view(o: dict) -> dict:
	"""Vue d'une offre du tableau pour le client (prix éclaté en bourse + nom de cible)."""
	obj = o.get("objectif", {})
	rec = o.get("recompenses", {}) or {}
	purse = cuivre_to_purse(rec.get("cuivre", 0))
	return {
		"id": o.get("_id"),
		"source": o.get("source", "genere"),
		"titre": o.get("titre", "—"),
		"description": o.get("description", ""),
		"rang": o.get("rang", "F"),
		"objectif": obj,
		"cible_nom": quetes._cible_nom(obj),
		"recompenses": {
			"xp": rec.get("xp", 0),
			"or": purse["or"],
			"argent": purse["argent"],
			"cuivre": purse["cuivre"],
		},
	}


def _fiche_payload(character: dict) -> dict:
	"""Sous-payload « fiche » (indépendant d'un lieu) : quêtes détaillées de TOUS les donneurs pour
	l'onglet 📜, bourse et focalisation. Suffit à rafraîchir la fiche depuis n'importe où (abandon
	hors guilde)."""
	# Détails complets (tous donneurs) pour rafraîchir l'onglet 📜 de la fiche côté client.
	fiche_actives, fiche_terminees = quetes.fiche_details(character)
	return {
		"fiche_actives": fiche_actives,
		"fiche_terminees": fiche_terminees,
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		# État de la focalisation pour resynchroniser les boutons 🎯 côté client.
		"focalisation": focalisation.payload_client(character, get_doc),
		# Marques « ? » des lieux : accepter/rendre/abandonner une quête les fait bouger.
		# Gratuit (0 lecture, cf. utils/indicateurs) — donc republié sans arbitrage,
		# contrairement à `relations_lieux` (Conventions §10).
		"lieux_marques": indicateurs.marques_lieux(character),
	}


def _board_payload(character: dict, lieu_doc: dict, completer: bool = False) -> dict:
	"""Offres du tableau + quêtes actives (détaillées) de ce donneur + bourse.

	⚠️ `completer=True` UNIQUEMENT là où une place peut être libre : l'ouverture du tableau
	et l'acceptation. `terminer`/`déposer`/`abandonner` ne retirent AUCUNE offre — la quête
	a quitté le tableau à l'acceptation —, ils se contentent donc de lister l'existant
	(`lister_offres`) au lieu de payer une génération complète pour un tableau identique."""
	offres = quetes.remplir_tableau(lieu_doc) if completer else quetes.lister_offres(lieu_doc)
	giver = lieu_doc.get("_id")
	fiche = _fiche_payload(character)
	# ⚠️ `actives` est un SOUS-ENSEMBLE de `fiche_actives` : les recalculer était une seconde
	# passe de `quete_detail` sur les mêmes quêtes — donc une relecture de plus, par quête de
	# chasse, du doc `lieu:*` complet (28 Ko pour Auxerre). On filtre au lieu de refaire.
	ids_giver = {
		q.get("id") or q.get("_id")
		for q in character.get("quetes_actives", []) if q.get("giver") == giver
	}
	return {
		**fiche,
		"offres": [_offre_view(o) for o in offres],
		"actives": [d for d in fiche["fiche_actives"] if d.get("id") in ids_giver],
		"lieu_parent": lieu_doc.get("lieu_parent"),
	}


@quetes_router.get("/quetes/board")
async def quetes_board(current_user: Annotated[dict, Depends(get_current_user)]):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)
	return _board_payload(character, lieu_doc, completer=True)


@quetes_router.post("/quetes/accepter")
async def quetes_accepter(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)

	quete_id = body.get("quete_id")
	quete_doc = get_doc(quete_id) if quete_id else None
	if not quete_doc or quete_doc.get("type") != "quete":
		raise HTTPException(status_code=404, detail="Quête introuvable")
	if quete_doc.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Cette quête n'est pas proposée ici.")
	if quete_doc.get("statut", "offerte") != "offerte":
		raise HTTPException(status_code=409, detail="Quête déjà prise.")
	if quetes.quete_active(character, quete_id):
		raise HTTPException(status_code=409, detail="Quête déjà acceptée.")

	actives = character.get("quetes_actives", [])
	actives.append(quetes.snapshot_quete(quete_doc))
	character["quetes_actives"] = actives
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	# L'offre quitte le tableau (best-effort : un échec ici n'annule pas l'acceptation,
	# le filtre `quete_active` empêche un double-accept côté joueur).
	#
	# ⚠️ Une offre GÉNÉRÉE est SUPPRIMÉE, pas marquée : le personnage en garde un snapshot
	# (`snapshot_quete`) et plus personne ne relit ce doc — `accepte_par` était écrit sans
	# jamais être lu. La laisser en base faisait grossir SANS BORNE ce que `offres_du_giver`
	# rapatrie à chaque ouverture du tableau (112 docs morts pour 6 vivants sur la base de
	# référence) : c'est cela qui rendait le tableau de plus en plus lent avec le temps.
	# Même geste que `purger_offres_perimees`, même motif.
	# ⚠️ Une quête AUTHORÉE n'est JAMAIS supprimée — c'est une mission ÉCRITE, qu'on doit
	# pouvoir remettre au tableau à la main : elle garde le marquage historique.
	# ⚠️ Conséquence assumée : un second POST sur la même quête répond 404 « introuvable »
	# au lieu de 409 « déjà prise ». La garde qui compte (`quete_active` → 409 plus haut)
	# est intacte, et le bouton se désactive désormais pendant la requête.
	if quete_doc.get("source") == "genere":
		delete_doc(quete_doc)
	else:
		quete_doc["statut"] = "acceptee"
		quete_doc["accepte_par"] = character["_id"]
		save_doc(quete_doc)

	# Une place vient de se libérer : c'est le seul endpoint, avec l'ouverture, qui recomplète.
	payload = _board_payload(character, lieu_doc, completer=True)
	payload["accepte"] = {"titre": quete_doc.get("titre", "—")}
	return payload


@quetes_router.post("/quetes/terminer")
async def quetes_terminer(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)

	quete_id = body.get("quete_id")
	q = quetes.quete_active(character, quete_id)
	if not q:
		raise HTTPException(status_code=404, detail="Quête non active")
	if q.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Rendez-vous à la guilde qui a confié la quête.")
	if not quetes.objectif_atteint(character, q):
		raise HTTPException(status_code=422, detail="Objectif non rempli.")

	# ⚠️ Le groupe est chargé AVANT la récompense et repassé à `appliquer_recompenses` : ce
	# sont les MÊMES dicts que la part de butin crédite et que la boucle de save persiste.
	# Les recharger dans le chokepoint d'XP rendrait un second dict du même document, donc
	# deux `save_doc` sur le même `_rev` — une des deux écritures serait perdue en silence.
	groupe = recrutement.groupe_effectif(character, get_doc)

	# Les collectes ont déjà été consommées au fil des dépôts (`/api/quetes/deposer`) ; le
	# turn-in ne fait que valider la progression et donner la récompense.
	recap = quetes.appliquer_recompenses(character, q, compagnons=groupe)

	# Part de butin des compagnons : chaque membre du groupe prélève sa part EFFECTIVE
	# (affinité déduite) sur le CUIVRE de la récompense, créditée à SON doc ; et une
	# quête réussie ensemble resserre les liens (chokepoint recrutement).
	parts_info = None
	if groupe:
		cuivre_total = int((q.get("recompenses", {}) or {}).get("cuivre", 0) or 0)
		reglement = recrutement.regler_part_butin(character, groupe, cuivre_total)
		preleve = sum(reglement["parts"].values())
		if preleve:
			debit_character(character, preleve)
		recrutement.memoriser_liens_post_quete(character, groupe)
		# ⚠️ Les docs compagnons (bourse créditée) ne sont persistés qu'APRÈS le save du
		# personnage (plus bas) : un 409 rejoué ici les paierait deux fois.
		parts_info = {
			"parts": [
				{"nom": f"{av.get('prenom', '')} {av.get('nom', '')}".strip(),
				 "cuivre": reglement["parts"].get(av["_id"], 0)}
				for av in groupe
			],
			"reste": reglement["reste"],
		}

	# Quête focalisée terminée → la focalisation tombe (même save).
	focalisation.effacer_si_quete(character, quete_id)

	# Retrait des actives + archivage (idempotence : plus dans actives → plus de turn-in).
	character["quetes_actives"] = [
		a for a in character.get("quetes_actives", []) if a.get("id") != quete_id
	]
	termine = character.get("quetes_terminees", [])
	termine.append({
		"id": q.get("id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", "F"),
		"recompenses": q.get("recompenses", {}),
		"termine_at": quetes.now_epoch(),
	})
	character["quetes_terminees"] = termine

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	# Bourses des compagnons + XP de la compagnie (annexes, best-effort) : persistées APRÈS
	# le save du personnage — le turn-in est acquis (quête retirée des actives), un rejeu ne
	# peut plus les créditer deux fois ; un échec ici leur fait juste perdre leur part.
	# ⚠️ `groupe` couvre les DEUX (les permanents en font partie, `engager_permanent` laisse
	# `statut` à "embauche") : rien à sauver en plus pour `recap["compagnie"]`.
	for av in groupe:
		save_doc(av)

	# Réussir une quête monte la réputation chez son donneur. ⚠️ APRÈS le save autoritatif :
	# la quête a quitté `quetes_actives` en base, donc un 409 rejoué ne peut pas payer deux
	# fois. Le donneur EST le lieu courant — la garde 403 plus haut l'exige.
	relation_gain = quetes.recompenser_donneur(character, lieu_doc, get_doc, save_doc)

	payload = _board_payload(character, lieu_doc)
	payload["termine"] = {
		"titre": q.get("titre", "—"),
		"xp": recap["xp"].get("xp_gain", 0),
		"niveau_up": recap["xp"].get("niveau_up", False),
		"recompenses": q.get("recompenses", {}),
		"parts_compagnons": parts_info,
		# La compagnie a touché la MÊME XP : une règle invisible n'existe pas.
		"xp_compagnie": recrutement.xp_compagnie_payload(
			recap["compagnie"], recap["xp"].get("xp_gain", 0)),
	}
	# Liens resserrés par la quête réussie ensemble → resync de l'onglet 🤝 section 👥.
	if groupe:
		payload["affinites_detail"] = recrutement.affinites_detail_payload(character, get_doc)
	# La cote du donneur a bougé → resync de l'onglet 🤝 section 🏪 (Conventions §10).
	# ⚠️ Seulement en cas de gain : ce payload relit tous les docs relation + un doc lieu
	# COMPLET par lieu connu.
	if relation_gain is not None:
		payload["relations_lieux"] = marche.relations_lieux_payload(character)
	return payload


@quetes_router.post("/quetes/deposer")
async def quetes_deposer(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Dépose à la guilde les pièces de collecte portées (jusqu'au reste à faire) : les retire de
	l'inventaire et fait progresser la quête. Permet de remplir une collecte en plusieurs voyages
	sans devoir tout porter d'un coup (utile pour le bois lourd)."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _guild_lieu(character)

	quete_id = body.get("quete_id")
	q = quetes.quete_active(character, quete_id)
	if not q:
		raise HTTPException(status_code=404, detail="Quête non active")
	if q.get("giver") != lieu_doc.get("_id"):
		raise HTTPException(status_code=403, detail="Rendez-vous à la guilde qui a confié la quête.")
	if q.get("objectif", {}).get("type") != "collect":
		raise HTTPException(status_code=422, detail="Cette quête ne se dépose pas.")

	n = quetes.deposer_collect(character, q)
	if n <= 0:
		raise HTTPException(status_code=422, detail="Rien à déposer (aucune pièce portée ou objectif déjà atteint).")
	# Collecte complétée par ce dépôt → la focalisation tombe (même save).
	focalisation.effacer_si_objectif_atteint(character)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	payload = _board_payload(character, lieu_doc)
	payload["depose"] = {"n": n, "titre": q.get("titre", "—"), "complete": quetes.objectif_atteint(character, q)}
	# Le dépôt a retiré des pièces du sac → rafraîchir l'inventaire côté client.
	payload["slots"] = {s: resolve_item_ref(v) if v else None for s, v in character.get("slots", {}).items()}
	payload["inventaire"] = [d for r in character.get("inventaire", []) if (d := resolve_item_ref(r))]
	payload["objets_au_sol"] = [d for r in character.get("objets_au_sol", []) if (d := resolve_item_ref(r))]
	payload["charge_max"] = charge_max_of(character)
	return payload


@quetes_router.post("/quetes/abandonner")
async def quetes_abandonner(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	# Abandonner est autorisé PARTOUT (pas de retour à la guilde imposé) : l'onglet 📜 de la fiche
	# est atteignable n'importe où. On résout le lieu courant sans exiger que ce soit une guilde.
	lieu_doc = get_doc(character.get("lieu", ""))
	est_guilde = bool(lieu_doc and lieu_doc.get("categorie") == GUILDE_CATEGORIE)

	quete_id = body.get("quete_id")
	q = quetes.quete_active(character, quete_id)
	if not q:
		raise HTTPException(status_code=404, detail="Quête non active")
	# Quête focalisée abandonnée → la focalisation tombe (même save).
	focalisation.effacer_si_quete(character, quete_id)
	# Se défausser d'une quête — de quelque type qu'elle soit — coûte la même réputation que
	# laisser filer le délai d'une course : on ne renonce pas sans que le donneur s'en souvienne,
	# et sa MAISON encaisse d'un bloc (lâcher la mission du comptoir fâche aussi la réception).
	# Une cargaison de transport, elle, reste dans le sac : le joueur garde la marchandise.
	giver_doc = get_doc(q.get("giver")) if q.get("giver") else None
	sanction = None
	if giver_doc:
		sanction = quetes.sanctionner_renoncement(character, giver_doc, get_doc, save_doc, find_docs)
	# Les compagnons aussi tiquent quand on renonce : petit malus d'affinité de groupe.
	for av in recrutement.groupe_effectif(character, get_doc):
		recrutement.ajuster_affinite(character, av["_id"],
									 -abs(character_stats.AFFINITE_DELTA_CONGEDIE))
	# Une ESCORTE abandonnée laisse des docs `protege:*` accrochés au groupe : ils
	# continueraient d'apparaître dans les combats et dans le panneau 👥. On les détache
	# (docs ANNEXES, persistés après le save autoritatif). La sanction de réputation, elle,
	# vient d'être appliquée juste au-dessus, comme pour n'importe quelle quête.
	proteges_liberes = []
	if (q.get("objectif") or {}).get("type") == "escorte":
		proteges_liberes = escorte.liberer_proteges(character, q, get_doc)
	character["quetes_actives"] = [
		a for a in character.get("quetes_actives", []) if a.get("id") != quete_id
	]
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	for doc in proteges_liberes:
		save_doc(doc)
	# À la guilde → payload complet (tableau à jour) ; ailleurs → payload léger (fiche + bourse +
	# focalisation), suffisant pour resynchroniser l'onglet 📜.
	payload = _board_payload(character, lieu_doc) if est_guilde else _fiche_payload(character)
	payload["abandonne"] = {"titre": q.get("titre", "—")}
	# La sanction a fait bouger la réputation de toute la maison du donneur → resync de
	# l'onglet 🤝 (Conventions §10) : sans lui, l'onglet resterait figé sur les cotes du
	# dernier chargement de /play. ⚠️ Seulement quand quelque chose a bougé — ce payload
	# relit tous les docs relation + un doc lieu COMPLET par lieu connu.
	if sanction:
		payload["relations_lieux"] = marche.relations_lieux_payload(character)
	return payload
