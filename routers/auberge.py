# routers/auberge.py
# Endpoints de la taverne : la salle commune (tables + tableau d'information) et la nuit.
# Le moteur (utils/auberge.py) borne, périme et nettoie ; ici on gère l'interaction joueur,
# l'argent et la persistance. Pattern calqué sur routers/montures.py : prélude d'accès
# commun, `_payload` qui RECALCULE tout le bloc (Convention §10), doc principal AUTORITATIF
# sauvé en premier, `save_doc(...) is None ⇒ 409`.
#
# ⚠️ C'est le premier endroit du jeu où un joueur écrit pour d'AUTRES joueurs. Le texte est
# BORNÉ ici et ÉCHAPPÉ au rendu (Convention §9) ; le nom de l'auteur est dénormalisé dans le
# message parce qu'on n'a pas le droit de relire le `character:*` d'autrui.
#
# ⚠️ `GET /auberge/salle` est en `def` (lecture ⇒ threadpool, la boucle d'événements n'est
# pas bloquée — c'est la cible du sondage). Les écrivains restent `async def`, donc
# SÉRIALISÉS : la nuit écrit une soixantaine de docs lieu, et deux nuits en parallèle
# ouvriraient une fenêtre où deux joueurs approvisionnent le même étal.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, delete_doc, find_docs
from models import character_stats
from utils.auth import get_current_user
from utils.characters import get_selected_character, cuivre_to_purse, money_to_cuivre
from utils.marche import debit_character, tick_atelier, lieu_recettes, appro_leaves_categorie
from utils import auberge
from utils import recrutement
from utils import montures
# ⚠️ Sens d'import : `routers/auberge` → `routers/user`, jamais l'inverse (précédent :
# `routers/recrutement`). `routers/user` importe `utils/auberge`, pas ce module.
from routers.user import _inventory_payload

auberge_router = APIRouter()


def _acces_auberge(current_user: dict) -> tuple[dict, dict]:
	"""(personnage, lieu) pour toute opération de taverne : personnage sélectionné (404),
	lieu qui EST une taverne (403). Miroir exact de `_acces_etable` — la seule garde est
	d'être physiquement dans l'auberge, y compris pour retirer une annonce."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or not auberge.lieu_est_taverne(lieu_doc):
		raise HTTPException(status_code=403, detail="Il n'y a pas de salle commune ici.")
	return character, lieu_doc


def _message_view(m: dict, character_id: str) -> dict:
	"""Vue client d'un message. ⚠️ `texte` et `auteur_nom` partent BRUTS (bornés à
	l'écriture) : c'est `escapeHtml` qui les neutralise au rendu, échapper ici produirait un
	double échappement. `mien` évite au client de comparer des ids."""
	return {
		"id": m.get("_id", ""),
		"auteur_nom": m.get("auteur_nom", ""),
		# Portrait DÉNORMALISÉ à l'écriture : aucune lecture de `character:*` ici, ni pour
		# soi ni pour autrui. Clés absentes sur un message hérité ⇒ silhouette générique.
		"auteur_image": m.get("auteur_image", ""),
		"auteur_zoom": m.get("auteur_zoom"),
		"auteur_translate": m.get("auteur_translate"),
		"texte": m.get("texte", ""),
		"cree_at": int(m.get("cree_at", 0) or 0),
		"expire_at": m.get("expire_at"),
		"mien": m.get("auteur") == character_id,
	}


def _table_view(t: dict, messages: list, character_id: str) -> dict:
	"""Vue client d'une table. Les messages y sont INCLUS : la salle est publique en lecture,
	et les inclure évite une requête par table à chaque sondage.

	⚠️ On publie les NOMS des attablés, JAMAIS `participants` : un `_id` de personnage s'écrit
	`character:user:<email>_<uuid>`, l'exposer livrerait l'adresse e-mail de chaque joueur à
	toute la salle (même règle que `mien`, calculé serveur dans `_message_view`).

	⚠️ `occupants` RESTE publié à côté : il est le repli du client quand `noms` est plus court —
	une table déjà en base, où l'on s'est assis avant que le nom n'y soit dénormalisé."""
	miens = auberge.de_support(messages, auberge.SUPPORT_TABLE, t.get("_id"))
	return {
		"id": t.get("_id", ""),
		"numero": int(t.get("numero", 0) or 0),
		"occupants": len(t.get("participants") or []),
		"noms": auberge.noms_attables(t),
		"assis": character_id in (t.get("participants") or []),
		"messages": [_message_view(m, character_id) for m in miens],
	}


def _payload(character: dict, lieu_doc: dict, tables=None, messages=None) -> dict:
	"""TOUT le bloc « salle commune », recalculé (Convention §10) : sans lui, le panneau
	resterait figé sur l'état du dernier chargement.

	⚠️ `now` part avec le payload — le client dérive ses horodatages de l'horloge SERVEUR et
	jamais de la sienne, qui dérive (même précaution que les chronos de quêtes)."""
	lieu_id = lieu_doc.get("_id", "")
	char_id = character.get("_id", "")
	if tables is None or messages is None:
		tables, messages = _salle(lieu_id)
	# ⚠️ Une table où ce personnage a DORMI ne lui est plus montrée du tout — c'est le sens
	# d'`anciens`. Elle existe toujours pour les convives restés attablés.
	visibles = [t for t in tables if not auberge.table_fermee_pour(t, char_id)]
	return {
		"now": auberge.now_epoch(),
		"tables": [_table_view(t, messages, char_id) for t in visibles],
		"tables_max": int(character_stats.AUBERGE_TABLES_MAX),
		# ⚠️ Le compte porte sur TOUTES les tables, y compris celles qu'on ne lui montre pas :
		# elles occupent la salle. Sinon le client offrirait d'en ouvrir une de plus et le
		# serveur refuserait, sans que le joueur comprenne pourquoi.
		"tables_total": len(tables),
		"ma_table": (auberge.table_du_personnage(tables, char_id) or {}).get("_id"),
		"tableau": [_message_view(m, char_id)
					for m in auberge.de_support(messages, auberge.SUPPORT_TABLEAU)],
		"annonce_max": int(character_stats.AUBERGE_ANNONCE_LONGUEUR_MAX),
		"messages_max": int(character_stats.AUBERGE_TABLE_MESSAGES_MAX),
		# Détail et non booléen : le refus doit pouvoir dire CE QUI manque, sinon le joueur
		# ne sait pas quoi aller acheter. ⚠️ Testé sur le personnage SEUL — on écrit avec sa
		# propre plume ; passer `expedition.membres(...)` la partagerait comme la hache.
		"fournitures": auberge.fournitures_presentes(get_doc, [character]),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"cout_nuit": auberge.cout_nuit(lieu_doc),
		# ⚠️ Le log part AVEC la salle, et pas seulement dans la réponse de la nuit : le
		# client doit l'avoir EN MAIN au moment du clic pour l'égrener PENDANT que le POST
		# est en vol. Le recevoir après coup ne couvrirait plus rien — or c'est justement
		# l'attente des dizaines d'étals qu'il est là pour habiller.
		"nuit_log": auberge.messages_nuit(lieu_doc, auberge.NUIT_LOG_LIGNES),
	}


def _salle(lieu_id: str) -> tuple[list, list]:
	"""Tables + messages VIVANTS d'une auberge, les échus supprimés au passage.

	⚠️ Une écriture dans un chemin de lecture est assumée : c'est déjà ce que fait
	`tick_atelier` au rendu de `/play`. La péremption est PARESSEUSE — aucun tick de fond
	dans le jeu —, donc elle ne peut se faire qu'ici, au moment où quelqu'un regarde."""
	now = auberge.now_epoch()
	tables = auberge.tables_du_lieu(lieu_id, find_docs)
	messages = auberge.purger_messages_perimes(
		auberge.messages_du_lieu(lieu_id, find_docs), now, delete_doc)
	return _purger_tables_vides(tables, messages)


def _purger_tables_vides(tables: list, messages: list) -> tuple[list, list]:
	"""Supprime les tables où PLUS PERSONNE n'est assis — AVEC tout ce qu'elles portent
	encore. Rend `(tables_restantes, messages_restants)`.

	⚠️ Des propos flottant dans une salle déserte n'ont aucun sens : une table se vide, elle
	disparaît, et sa conversation avec elle. C'est aussi ce qui empêche `anciens` de grossir
	sans borne — la mémoire de la soirée part avec la table."""
	restantes, efface = [], set()
	for t in tables or []:
		if not auberge.table_vide(t):
			restantes.append(t)
			continue
		for m in auberge.de_support(messages, auberge.SUPPORT_TABLE, t.get("_id")):
			delete_doc(m)
			efface.add(m.get("_id"))
		delete_doc(t)
	return restantes, [m for m in messages or [] if m.get("_id") not in efface]


@auberge_router.get("/auberge/salle")
def salle(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Cible du SONDAGE (~4 s tant que le panneau est ouvert). En `def` : lecture pure côté
	jeu, donc threadpool. Deux `find_docs` indexés par `(type, lieu)`.

	⚠️ Une écriture PARESSEUSE s'y greffe — comme la purge des messages échus de `_salle` :
	le personnage courant y (re)pose son nom sur les tables où il est assis. Sans elle, un
	convive attablé AVANT que le champ `noms` n'existe ne serait jamais rattrapé et sa table
	resterait à moitié muette. Best-effort et **une seule fois** : `rafraichir_mon_nom` ne rend
	que ce qui a vraiment changé, donc les sondages suivants n'écrivent plus rien."""
	character, lieu_doc = _acces_auberge(current_user)
	tables, messages = _salle(lieu_doc.get("_id", ""))
	for table in auberge.rafraichir_mon_nom(tables, character):
		save_doc(table)      # annexe : un conflit se rejouera au sondage suivant
	return _payload(character, lieu_doc, tables, messages)


@auberge_router.post("/auberge/table")
async def prendre_table(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""S'asseoir à une table existante (`table_id`) ou en ouvrir une neuve. Un personnage
	n'occupe QU'UNE table à la fois — il quitte donc la précédente, ⚠️ **en y laissant
	mourir ses messages** : une conversation appartient à ceux qui sont attablés."""
	character, lieu_doc = _acces_auberge(current_user)
	lieu_id = lieu_doc.get("_id", "")
	tables, messages = _salle(lieu_id)

	table_id = body.get("table_id") or ""
	if table_id:
		table = next((t for t in tables if t.get("_id") == table_id), None)
		if table is None:
			raise HTTPException(status_code=404, detail="Cette table n'existe plus.")
	else:
		# ⚠️ Le plafond porte sur TOUTES les tables de la salle, y compris celles qu'on ne
		# montre plus à ce personnage : elles occupent la place tout de même.
		table = auberge.nouvelle_table(lieu_id, tables)
		if table is None:
			raise HTTPException(
				status_code=409,
				detail="Toutes les tables sont prises ; asseyez-vous à l'une d'elles.")
		tables.append(table)

	# ⚠️ `sauf` : se rasseoir à SA propre table ne doit pas effacer ce qu'on vient d'y dire.
	modifiees, a_supprimer = auberge.quitter_tables(character, tables, messages,
													sauf=table.get("_id"))
	ok, raison = auberge.asseoir(table, character)
	if not ok:
		raise HTTPException(status_code=409, detail=raison)

	# La table porte l'état visible de ce geste : elle est autoritative. Le personnage suit
	# (il porte le marqueur `taverne_table`, sans lequel sortir de l'auberge ne le relèverait
	# plus) — 409 aussi, sinon le marqueur mentirait dès le prochain déplacement.
	if save_doc(table) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	for m in a_supprimer:
		delete_doc(m)
	efface = {m.get("_id") for m in a_supprimer}
	messages = [m for m in messages if m.get("_id") not in efface]
	for autre in modifiees:
		save_doc(autre)          # best-effort : il vient d'en être levé
	tables, messages = _purger_tables_vides(tables, messages)
	return _payload(character, lieu_doc, tables, messages)


@auberge_router.post("/auberge/message")
async def poster_message(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Parler à sa table. Le plafond s'applique APRÈS l'ajout : le plus ancien saute."""
	character, lieu_doc = _acces_auberge(current_user)
	lieu_id = lieu_doc.get("_id", "")
	char_id = character.get("_id", "")
	tables, messages = _salle(lieu_id)

	table = auberge.table_du_personnage(tables, char_id)
	if table is None:
		raise HTTPException(status_code=409, detail="Prenez d'abord une table.")

	# Une ligne de conversation : les blancs sont écrasés, pas de multi-ligne ici. Borné à la
	# longueur d'une annonce faute d'avoir besoin d'un second réglage pour si peu.
	texte = auberge.nettoyer_ligne(body.get("texte"), int(character_stats.AUBERGE_ANNONCE_LONGUEUR_MAX))
	if not texte:
		raise HTTPException(status_code=422, detail="Un message vide ne se dit pas.")

	doc = auberge.nouveau_message(lieu_id, character, texte,
								  support=auberge.SUPPORT_TABLE, table_id=table.get("_id"))
	if save_doc(doc) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	messages.append(doc)

	# Plafond : les plus ANCIENS de CETTE table sautent (les messages sont triés par cree_at).
	de_la_table = auberge.de_support(messages, auberge.SUPPORT_TABLE, table.get("_id"))
	for vieux in auberge.messages_en_trop(de_la_table):
		delete_doc(vieux)
		messages = [m for m in messages if m.get("_id") != vieux.get("_id")]

	table["activite_at"] = auberge.now_epoch()
	save_doc(table)             # annexe : la table survit très bien à un horodatage périmé
	return _payload(character, lieu_doc, tables, messages)


@auberge_router.post("/auberge/annonce")
async def poser_annonce(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Épingler une annonce au tableau d'information. Exige papier, encre ET plume d'oie, et
	DÉPENSE le papier et l'encre — la plume est un `outil`, elle sert et ressert. Écrire
	coûte donc à chaque fois, et le scriptorium y gagne un débouché."""
	character, lieu_doc = _acces_auberge(current_user)

	manquantes = auberge.fournitures_manquantes(get_doc, [character])
	if manquantes:
		libelles = {"papier": "du papier", "encre": "de l'encre",
					"plume_a_ecrire": "une plume à écrire"}
		raise HTTPException(
			status_code=422,
			detail="Il vous manque " + ", ".join(libelles.get(m, m) for m in manquantes) + ".")

	texte = auberge.nettoyer_texte(body.get("texte"),
								   int(character_stats.AUBERGE_ANNONCE_LONGUEUR_MAX))
	if not texte:
		raise HTTPException(status_code=422, detail="Une annonce vide ne s'affiche pas.")

	# ⚠️ MÊME SÉQUENCE que `consommer` / `lancer_sort` : on retire en MÉMOIRE, on sauve
	# l'objet produit, puis le personnage. Un échec du premier save laisse donc le sac
	# intact en base — le joueur ne perd jamais ses fournitures sans avoir son avis.
	retire, _ = auberge.retirer_fournitures(get_doc, character)
	if not retire:
		# Le contrôle vient de passer : on ne tombe ici qu'en cas de course entre deux
		# écritures. Mieux vaut un refus qu'une annonce gratuite.
		raise HTTPException(status_code=409, detail="Vos fournitures viennent de vous manquer.")

	doc = auberge.nouveau_message(lieu_doc.get("_id", ""), character, texte,
								  support=auberge.SUPPORT_TABLEAU)
	if save_doc(doc) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	payload = _payload(character, lieu_doc)
	payload["consomme"] = list(auberge.FOURNITURES_CONSOMMEES)
	# ⚠️ Le SAC vient de changer (Convention §10) : sans ce bloc, la fiche resterait figée sur
	# l'inventaire du dernier chargement de /play et le joueur y verrait encore son papier.
	payload["inventaire_payload"] = _inventory_payload(character)
	return payload


@auberge_router.post("/auberge/annonce/retirer")
async def retirer_annonce(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Décrocher une annonce. ⚠️ AUCUN contrôle de propriété — n'importe qui dans l'auberge
	peut retirer n'importe quel avis, c'est le geste physique d'un tableau de village. La
	seule garde est d'être dans CETTE auberge : on ne décloue pas à distance (le message doit
	appartenir à ce lieu ET au tableau, sinon un id forgé effacerait une conversation)."""
	character, lieu_doc = _acces_auberge(current_user)
	message_id = body.get("message_id") or ""
	doc = get_doc(message_id) if message_id else None
	if (not doc or doc.get("type") != auberge.TYPE_MESSAGE
			or doc.get("lieu") != lieu_doc.get("_id")
			or doc.get("support") != auberge.SUPPORT_TABLEAU):
		raise HTTPException(status_code=404, detail="Cette annonce n'est plus affichée.")
	if delete_doc(doc) is None:
		raise HTTPException(status_code=409, detail="Conflit de suppression — réessayez.")
	return _payload(character, lieu_doc)


@auberge_router.post("/auberge/nuit")
async def passer_la_nuit(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Passer la nuit : PV/PM au maximum pour toute l'expédition, étals de la cité
	réapprovisionnés, tableau de recrues renouvelé, et fin de soirée du personnage.

	⚠️ `async def` DÉLIBÉRÉMENT : cet endpoint écrit une soixantaine de docs lieu, et du
	parallélisme réel ouvrirait une fenêtre où deux joueurs approvisionnent le même étal.
	⚠️ Aucune horloge n'avance : rien n'est partagé, rien n'est écrit sur le monde qu'un
	autre joueur n'aurait pas pu déclencher en visitant les mêmes boutiques."""
	character, lieu_doc = _acces_auberge(current_user)

	# 1. Le débit passe APRÈS toutes les gardes : on ne prend l'argent que si la nuit a lieu.
	cout = auberge.cout_nuit(lieu_doc)
	if cout and debit_character(character, cout) is None:
		raise HTTPException(status_code=409, detail="Vous n'avez pas de quoi payer la chambre.")

	# 2. Repos — le principal, puis chaque compagnon et chaque monture. Les trois docs sont
	#    des miroirs, `reposer` s'y applique telle quelle.
	vitals = auberge.reposer(character)
	compagnons = recrutement.groupe_effectif(character, get_doc)
	betes = montures.montures_effectives(character, get_doc)
	for porteur in compagnons + betes:
		auberge.reposer(porteur)

	# 3. Les étals de la CITÉ. Même garde qu'à la visite (`main.py`) : on ne tick que ce qui
	#    a du stock ou un approvisionnement configuré, sinon un lieu sans commerce ne
	#    pourrait de toute façon rien produire.
	parent_id = lieu_doc.get("lieu_parent") or character.get("cite") or ""
	passes = int(character_stats.AUBERGE_NUIT_PASSES_ATELIER)
	magasins = 0
	voisins = (find_docs({"type": "lieu", "lieu_parent": parent_id}) or []) if parent_id else []
	for boutique in voisins:
		categorie = boutique.get("categorie")
		if not (boutique.get("stock_matieres") or boutique.get("stock_vente")
				or appro_leaves_categorie(categorie)):
			continue
		# `lieu_recettes` est mémoïsé par process : les dizaines d'appels touchent le mémo.
		recettes = lieu_recettes(categorie)
		change = False
		for _ in range(passes):
			change = tick_atelier(boutique, recettes) or change
		if change and save_doc(boutique) is not None:
			magasins += 1

	# 4. Les recrues. ⚠️ On PÉRIME au lieu de supprimer : c'est ce qui fait traverser
	#    `retirer_du_tableau`, le chokepoint qui sait qu'un ANCIEN COMPAGNON repasse `parti`
	#    au lieu d'être détruit — son doc porte l'affinité mémorisée, le supprimer romprait
	#    le lien. Les tableaux de QUÊTES ne tournent pas ici : ils gardent leur péremption.
	recrues = 0
	for voisin in voisins:
		if not recrutement.lieu_recrute(voisin):
			continue
		for av in recrutement.recrues_du_giver(voisin.get("_id", "")):
			av["expire_at"] = auberge.now_epoch() - 1
			save_doc(av)
		recrues += len(recrutement.remplir_tableau_recrues(voisin, character))

	# 5. Fin de soirée : ses messages de table s'effacent, ses tables se ferment POUR LUI.
	tables, messages = _salle(lieu_doc.get("_id", ""))
	modifiees, a_supprimer = auberge.fermer_soiree(character, tables, messages)

	# 6. Le personnage est AUTORITATIF (il porte la bourse et les PV) ; tout le reste est
	#    annexe, best-effort — au pire une table garde un dormeur une minute de plus.
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	for porteur in compagnons + betes:
		save_doc(porteur)
	for m in a_supprimer:
		delete_doc(m)
	efface = {x.get("_id") for x in a_supprimer}
	messages = [m for m in messages if m.get("_id") not in efface]

	# Les tables qu'il vient de quitter sont persistées, puis celles que plus personne
	# n'occupe s'effacent avec ce qu'elles portent. ⚠️ La purge passe sur `messages` DÉJÀ
	# amputé des siens, sinon une table qu'il était seul à occuper survivrait à vide.
	for t in modifiees:
		save_doc(t)
	tables, messages = _purger_tables_vides(tables, messages)

	payload = _payload(character, lieu_doc, tables, messages)
	payload.update({
		"log": auberge.messages_nuit(lieu_doc, auberge.NUIT_LOG_LIGNES),
		"vitals": vitals,
		"cout": cout,
		"magasins": magasins,
		"recrues": recrues,
		"compagnons": len(compagnons),
		"montures": len(betes),
	})
	return payload
