from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, APIRouter, Response, Request, Body
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import bcrypt
import math
import re
import uuid
import random
import os
from db.config import save_doc, get_doc, delete_doc, find_docs
from utils.auth import get_current_user, create_access_token
from utils.characters import (
	get_user_characters, get_selected_character, grant_xp,
	sync_equipment_bonus, carried_weight, charge_max_of,
	restriction_satisfaite,
	main_occupee_par_deux_mains, liberer_pour_deux_mains,
	item_ref_id, item_ref_weight, resolve_item_ref, poids_bounds,
	money_to_cuivre, cuivre_to_purse, credit_character,
)
from utils.marche import (
	debit_character, merchant_cha, prix_range_cuivre, marchander,
	convertir_apres_achat, resolve_stock_vente, tick_atelier, lieu_buys, params_vente_lieu,
	fiche_item_fields,
	get_relation, relation_value, marchandage_bloque, appliquer_marchandage,
	prix_courant, prix_marche, stock_cible_pour, _relation_seuil_bonus, now_epoch,
	relations_lieux_payload,
)
from utils.lieux import get_lieu_links, get_lieu_directions
from utils.zones import resolve_zone_event, load_zone_defs_for_lieu, resolve_recolte
from utils import quetes
from utils import bois
from utils import consommables
from utils import sorts as sorts_util
from utils import competences as competences_util
from utils import slots_actions
from utils import focalisation
from utils import intro
from utils import transport
from utils import recrutement
from utils import montures
from models import character_stats
from models.character_stats import (
	BaseStats, EquipmentBonus, compute_derived_stats, DerivedStats,
	compute_xp_cost, compute_stat_cap, compute_character_level
)

class User(BaseModel):
	email: str
	username: str | None = None
	disabled: bool | None = None
	
user_router = APIRouter()

class RegisterRequest(BaseModel):
	username: str
	email: str
	password: str
	password_again: str

@user_router.post("/register")
async def register_user(user: RegisterRequest, response: Response):
	user_id = "user:"+user.email
	user_doc = get_doc(user_id)
	if user_doc:
		raise HTTPException(status_code=400, detail="L'utilisateur existe déjà")
	
	if user.password != user.password_again:
		raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas")
	
	hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
	token = create_access_token({"user_id": user_id})

	save_doc({
		"_id": user_id,
		"username": user.username,
		"email": user.email,
		"type": "user",
		"password": hashed_pw.decode(),
		"token": token
	})
	content = {"token": token, "user_id": user_id, "username": user.username}
	response = JSONResponse(content=content)
	response.set_cookie(key="auth_token", value=token, httponly=True, samesite="lax")
	return response

class LoginRequest(BaseModel):
	email: str
	password: str
	
@user_router.post("/login")
async def login_user(user: LoginRequest, response: Response):
	user_doc = get_doc("user:"+user.email)
	if not user_doc or not bcrypt.checkpw(user.password.encode(), user_doc["password"].encode()):
		raise HTTPException(status_code=400, detail="Invalid credentials")
		
	token = create_access_token({"user_id": user_doc["_id"]})
	content = {"token": token, "user_id":	user_doc["_id"], "username":	user_doc["username"]}
	response = JSONResponse(content=content)
	response.set_cookie(key="auth_token", value=token, httponly=True, samesite="lax")
	return	response
	
@user_router.post("/character")
async def add_character(response: Response, current_user: Annotated[User, Depends(get_current_user)], characterinfo: dict = Body(...),):
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	user_id = current_user["_id"]
	db_user = get_doc(user_id)
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")

	# Le portrait est obligatoire : on rejette une image manquante, non-string,
	# avec séparateur de chemin (anti path-traversal) ou absente du dossier des portraits.
	image = characterinfo.get("image") if characterinfo else None
	characters_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "resources", "characters")
	if (not isinstance(image, str) or not image
			or "/" in image or "\\" in image
			or not os.path.isfile(os.path.join(characters_dir, image))):
		raise HTTPException(status_code=422, detail="Un portrait valide est requis pour créer un personnage.")

	if (characterinfo and "bonusStats" in characterinfo):
		caractUp = characterinfo["bonusStats"]
		points_depenses = sum(
			sum(i * character_stats.XP_COEFF.get(key, 1) for i in range(1, bonus + 1))
			for key, bonus in caractUp.items()
		)
		if points_depenses>10:
			raise HTTPException(status_code=406, detail="Incorrect info for character creation, to much points spend.")
		races = get_doc("rules:races")
		race = next((r for r in races["value"] if r["id"] == characterinfo["race"]), None)
		caract = {
			k: race['stats'].get(k, 0) + caractUp.get(k, 0)
			for k in race['stats']
		}
		base = BaseStats(
			v=caract.get("V", 0),
			f=caract.get("F", 0),
			r=caract.get("R", 0),
			ag=caract.get("Ag", 0),
			vol=caract.get("Vol", 0),
			int_=caract.get("Int", 0),
			cha=caract.get("Cha", 0),
			ch=caract.get("Ch", 0),
		)
		derived = compute_derived_stats(base=base, niveau=0)
		lieu = get_doc(characterinfo["cite"])
		position = lieu.get("default_position",{"x" : 0, "y" : 0})
		vocations = get_doc("rules:vocations")
		vocation = next((v for v in vocations["value"] if v["id"] == characterinfo["voc"]), None)
		inventaire_de_base = vocation.get("equipement_de_base", []) if vocation else []

		# Garde anti-faute-de-frappe : chaque réf d'équipement de départ doit résoudre
		# vers un item existant (IDs CouchDB sensibles à la casse). Une réf morte est
		# ignorée ET signalée — sinon elle resterait dans l'inventaire du personnage,
		# invisible et non équipable (resolve_item_ref / _inventory_payload la filtrent
		# silencieusement à l'affichage).
		inventaire_valide = []
		for ref in inventaire_de_base:
			if resolve_item_ref(ref):
				inventaire_valide.append(ref)
			else:
				print(f"[add_character] equipement_de_base ignoré (item introuvable) : "
					f"{item_ref_id(ref)!r} — vocation {characterinfo['voc']!r}")
		inventaire_de_base = inventaire_valide

		# Sort de départ : les vocations « pures magiciennes » (SORT_VOCATIONS_DEPART)
		# choisissent UN sort niveau 0 de leur vocation à la création (validé serveur).
		# Dégradé gracieux : si aucun sort niveau 0 n'existe encore en base pour la
		# vocation (contenu non importé), on laisse créer sans sort.
		sorts_init: list = []
		if characterinfo["voc"] in character_stats.SORT_VOCATIONS_DEPART:
			sort_initial = characterinfo.get("sort_initial")
			if sort_initial:
				sort_doc = sorts_util.normaliser_sort(get_doc(sort_initial))
				if (not sort_doc or sort_doc["vocation"] != characterinfo["voc"]
						or sort_doc["niveau"] != 0):
					raise HTTPException(status_code=422, detail="Sort de départ invalide pour cette vocation.")
				sorts_init = [sort_doc["id"]]
			else:
				candidats = [s for d in find_docs({"type": "sort"})
							 if (s := sorts_util.normaliser_sort(d))
							 and s["vocation"] == characterinfo["voc"] and s["niveau"] == 0]
				if candidats:
					raise HTTPException(status_code=422, detail="Choisissez un sort de départ pour cette vocation.")

		# Compétence de départ : miroir exact du sort pour TOUTES les autres vocations
		# (complément de SORT_VOCATIONS_DEPART) — on choisit un sort OU une compétence de
		# niveau 0, jamais les deux. Même dégradé gracieux si le contenu n'est pas importé.
		competences_init: list = []
		if competences_util.vocation_choisit_competence(characterinfo["voc"]):
			competence_initiale = characterinfo.get("competence_initiale")
			if competence_initiale:
				comp_doc = competences_util.normaliser_competence(get_doc(competence_initiale))
				if (not comp_doc or comp_doc["vocation"] != characterinfo["voc"]
						or comp_doc["niveau"] != 0):
					raise HTTPException(status_code=422, detail="Compétence de départ invalide pour cette vocation.")
				competences_init = [comp_doc["id"]]
			else:
				candidats = [c for d in find_docs({"type": "competence"})
							 if (c := competences_util.normaliser_competence(d))
							 and c["vocation"] == characterinfo["voc"] and c["niveau"] == 0]
				if candidats:
					raise HTTPException(status_code=422, detail="Choisissez une compétence de départ pour cette vocation.")

		unique_id = "character:" + user_id + "_" + str(uuid.uuid4())
		character_dict = {
			'_id' : unique_id,
			'user_id' : user_id,
			'type' : "character",
			'sex': characterinfo["sex"],
			'race': characterinfo["race"],
			'voc': characterinfo["voc"],
			'image': characterinfo["image"],
			'prenom': characterinfo["prenom"],
			'nom': characterinfo["nom"],
			'cite': characterinfo["cite"],
			'lieu': characterinfo["cite"],
			'position': position,
			'caracteristiques_current': caract,
			'currentPV': derived.pv_max,
			'currentPM': derived.pm_max,
			'lieux_visites': [characterinfo["cite"]],
			'xp_total': 0,
			'attribute_points': 0,
			'vocations_niveaux': {characterinfo["voc"]: 0},
			'inventaire': list(inventaire_de_base),
			'slots': {s: None for s in ['main_droite', 'main_gauche', 'torse', 'tete', 'jambes', 'pieds', 'mains', 'anneau_1', 'anneau_2', 'cou', 'ceinture']},
			'equipment_bonus': {},
			'or': 0,
			'argent': 0,
			'cuivre': 0,
			'quetes_actives': [],
			'quetes_terminees': [],
			# Rang de guilde par cité (clé = lieu_parent) — progresse via les épreuves de rang
			# du comptoir (utils/chasse). Absent ⇒ rang F ; v1 = prestige/affichage seul.
			'rangs_guilde': {},
			'sorts_connus': sorts_init,
			'competences_connues': competences_init,
			'competences_bonus': {},
			}
		# Une compétence passive buffe en permanence : on dénormalise son bonus, puis on
		# recalcule les max pour démarrer PV/PM pleins DANS les valeurs bufffées (une passive
		# en R relève pv_max). `caracteristiques_current` reste la valeur brute, jamais bufffée.
		competences_util.recompute_competences_bonus(character_dict, get_doc)
		if character_dict['competences_bonus'].get('buffs'):
			stats = consommables.caracts_avec_buffs(character_dict)
			derived = compute_derived_stats(base=BaseStats(
				v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
				ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
				cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
			), niveau=0)
			character_dict['currentPV'] = derived.pv_max
			character_dict['currentPM'] = derived.pm_max
		# Intro narrative : si la cité porte un bloc `intro`, le personnage démarre à
		# `position_depart` (périphérie) avec le statut en_cours — l'overlay du premier
		# /play racontera la fuite du village natal. Sans bloc : comportement inchangé.
		intro.demarrer(character_dict, lieu)
		save_doc(character_dict)
	
	return get_user_characters(current_user)
	
@user_router.delete("/character")
async def delete_character(	
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	characterinfo: dict = Body(...)):

	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	current_user_id = current_user["_id"]
	db_user = get_doc(current_user_id)
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if characterinfo:
		index = characterinfo["id"]
		character_id = characterinfo["character"]["_id"]	
		characterToDelete = get_doc(character_id)
		character = characterinfo["character"]
		if (
			characterToDelete["user_id"] == current_user_id and 
			characterToDelete["sex"] == character["sex"] and
			characterToDelete["voc"] == character["voc"] and
			characterToDelete["race"] == character["race"] and
			characterToDelete["nom"] == character["nom"] and
			characterToDelete["prenom"] == character["prenom"]
		 ):
			delete_doc(characterToDelete)
		else:
			raise HTTPException(status_code=404, detail="Character not found")
	
	return get_user_characters(current_user)	
	
@user_router.post("/select_character")
async def select_character(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	characterinfo: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	current_user_id = current_user["_id"]
	db_user = get_doc(current_user_id)
	if not db_user:
		raise HTTPException(status_code=404, detail="User not found")
		
	if characterinfo:
		index = characterinfo["id"]
		character_id = characterinfo["character"]["_id"]	
		characterSelected = get_doc(character_id)
		character = characterinfo["character"]
		if (
			characterSelected["user_id"] == current_user_id and 
			characterSelected["sex"] == character["sex"] and
			characterSelected["voc"] == character["voc"] and
			characterSelected["race"] == character["race"] and
			characterSelected["nom"] == character["nom"] and
			characterSelected["prenom"] == character["prenom"]
		 ):
			db_user["selected_character"] = character_id
			save_doc(db_user)
			return characterSelected
		else:
			raise HTTPException(status_code=404, detail="Character not found")
	else:
		raise HTTPException(status_code=404, detail="Invalid character selection")

@user_router.post("/update_character_portrait")
async def update_character_portrait(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	portrait_info: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	
	if portrait_info:
		# Le cadrage appartient au PORTEUR affiché : la fiche sert aussi les compagnons, et le
		# leur vit sur leur doc `aventurier:*` (les jetons alliés du combat le relisent).
		# Sans `compagnon_id`, `_acteur` rend le personnage sélectionné — comportement d'avant.
		character_to_update, _principal = _acteur(current_user, portrait_info)

		match = re.search(r"translate\((-?\d+\.?\d*)px,\s*(-?\d+\.?\d*)px\)", portrait_info["value"])
		zoom = portrait_info["zoom"]
		if match:
			x = float(match.group(1))
			y = float(match.group(2))
			character_to_update["portrait_translate"] = {"x": x, "y": y}
			character_to_update["portrait_zoom"] = zoom
			save_doc(character_to_update)
			return character_to_update
		else:
			raise HTTPException(status_code=406, detail="Incorrect info for character portrait update")
	else:
		raise HTTPException(status_code=405, detail="No info for character portrait update")

def _set_ressource_recoltable(character: dict, zone_event: dict | None, lieu_doc: dict,
	favori: tuple | None = None) -> None:
	"""Pose (ou efface) le champ transitoire `ressource_recoltable` selon l'événement de zone.
	Si l'événement est de type « ressource » et qu'une ressource est récoltable, on stocke une
	réf `{item, poids}` (poids d'instance tiré dans les bornes de l'item) ; sinon None.
	`favori` (focalisation) = (item_id, mult) → pondère le tirage de récolte."""
	item_id = resolve_recolte(zone_event, lieu_doc, get_doc,
		favori=favori[0] if favori else None,
		favori_mult=favori[1] if favori else 1.0)
	if not item_id:
		character["ressource_recoltable"] = None
		return
	item = get_doc(item_id)
	pmin, pmax = poids_bounds(item)
	poids = round(random.uniform(pmin, pmax), 2) if pmax > pmin else pmin
	character["ressource_recoltable"] = {"item": item_id, "poids": poids}


def _echecs_payload(echues: list) -> list:
	"""Courses de transport dont le délai vient d'expirer, pour le toast client."""
	return [{"titre": q.get("titre", "—")} for q in echues or []]


def _recolte_payload(character: dict) -> dict | None:
	"""Ressource récoltable résolue pour l'affichage (sidebar) : {item, nom, icon, poids} ou None."""
	ref = character.get("ressource_recoltable")
	if not ref:
		return None
	doc = resolve_item_ref(ref)
	if not doc:
		return None
	return {
		"item": doc.get("item"),
		"nom": doc.get("nom", "Ressource"),
		"icon": doc.get("icon", "🌿"),
		"poids": doc.get("poids", 0),
		"a_couper": bois.item_est_coupable(doc),
	}


@user_router.post("/move_character")
async def move_character(
	response: Response, 
	current_user: Annotated[User, Depends(get_current_user)], 
	move: dict = Body(...)):
	
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
		
	if move :
		character_to_update = get_selected_character(current_user)
		if not character_to_update:
			raise HTTPException(status_code=406, detail="Incorrect info for character move")
			
		position = character_to_update["position"]
		lieu_courant = character_to_update["lieu"]

		# Surcharge : on ne peut pas se DÉPLACER si le poids porté dépasse la charge max
		# (cas typique : on a ramassé un objet trop lourd, inventaire vide → bloqué tant
		# qu'on ne s'est pas délesté). Le « wait » (move 0,0) reste autorisé pour pouvoir
		# ouvrir l'inventaire / régénérer.
		est_deplacement = ("link" in move) or bool(move.get("x")) or bool(move.get("y"))
		if est_deplacement and carried_weight(character_to_update) > charge_max_of(character_to_update):
			raise HTTPException(status_code=409, detail="Trop chargé pour vous déplacer — déposez un objet.")

		if "link" in move:
			links = get_lieu_links(current_user)
			target_id = move["link"]
			# 1. Trouver le bon lien par son _id
			link = next((l for l in links if l["_id"] == target_id), None)

			# 2. Trouver le nœud qui n'a PAS le lieu_id
			if link:
				node = next((n for n in link["nodes"] if n["lieu"] != lieu_courant), None)
				if node:
					destination = node["lieu"]
					lieu_doc = get_doc(destination)
					if lieu_doc:
						destination_pos = {"x": node["pos"][0], "y": node["pos"][1] }
						print("move to ", destination, destination_pos)
						character_to_update["lieu"] = destination
						character_to_update["position"] = destination_pos
						# Progression des quêtes « aller en X » (persistée avec le déplacement).
						quetes.maj_progress_visite(character_to_update, destination)
						# Focalisation : arrivée au lieu guidé → effacée + toast côté client.
						focus_atteint = focalisation.effacer_si_lieu_atteint(character_to_update, destination)
						xp_gain = 0
						niveau_up = False
						niveau_new = compute_character_level(character_to_update.get("xp_total", 0))
						lieux_visites = character_to_update.get("lieux_visites", [])
						if destination not in lieux_visites:
							lieux_visites.append(destination)
							character_to_update["lieux_visites"] = lieux_visites
							xp_gain = lieu_doc.get("xp_decouverte", character_stats.XP_DECOUVERTE_LIEU)
							# XP + montée de niveau : règle partagée avec les combats.
							info = grant_xp(character_to_update, xp_gain)
							niveau_up = info["niveau_up"]
							niveau_new = info["niveau_apres"]
						# Changement de lieu : le sol (objets posés) est transitoire et perdu.
						character_to_update["objets_au_sol"] = []
						# Événement de zone résolu AVANT le save pour persister la ressource récoltable.
						zone_event = None
						if lieu_doc.get("zone_influences"):
							zone_defs = load_zone_defs_for_lieu(lieu_doc, get_doc)
							zone_event = resolve_zone_event(
								destination_pos["x"], destination_pos["y"],
								lieu_doc["zone_influences"], zone_defs,
								boost=focalisation.boost_zone_event(character_to_update, lieu_doc)
							)
						_set_ressource_recoltable(character_to_update, zone_event, lieu_doc,
							favori=focalisation.favori_recolte(character_to_update))
						# Intro : une arrivée par porte peut déposer directement en zone
						# sûre de la cité (le reload affichera la conclusion via sessionStorage).
						intro_terminee = intro.conclure_si_en_securite(character_to_update, lieu_doc)
						if intro_terminee and intro_terminee.get("xp"):
							info = grant_xp(character_to_update, intro_terminee["xp"])
							niveau_up = niveau_up or info["niveau_up"]
							niveau_new = info["niveau_apres"]
						# Courses de transport échues (expiration paresseuse : pas de tick de fond).
						transports_echoues = transport.traiter_expirations(
							character_to_update, quetes.now_epoch(), get_doc, save_doc)
						_apply_world_turn_regen(character_to_update)
						_apply_world_turn_groupe(character_to_update)
						save_doc(character_to_update)
						return {"moved": 1, "transports_echoues": _echecs_payload(transports_echoues), "xp_gain": xp_gain, "niveau_up": niveau_up, "niveau": niveau_new, "zone_event": zone_event, "vitals": _vitals_payload(character_to_update), "ressource_recoltable": _recolte_payload(character_to_update), "effets_actifs": consommables.effets_actifs_payload(character_to_update), "caracts_detail": _caracts_payload(character_to_update), "focalisation_atteinte": {"lieu": destination, "nom": lieu_doc.get("label", destination)} if focus_atteint else None, "intro_terminee": intro_terminee}
				raise HTTPException(status_code=404, detail="Incorrect movement info")
		elif ("x" in move and "y" in move
			and isinstance(move["x"], int) and isinstance(move["y"], int)):
			ancienne_pos = {"x": position["x"], "y": position["y"]}
			movex = (move["x"] > 0) - (move["x"] < 0) # -1 0 1
			movey = (move["y"] > 0) - (move["y"] < 0) # -1 0 1
			position["x"] += movex
			position["y"] += movey
			lieu_doc = get_doc(lieu_courant)
			if (lieu_doc and
				position["x"]>=0 and position["y"]>=0
				and position["x"]<=lieu_doc["dimensions"]["x"] and position["y"]<=lieu_doc["dimensions"]["y"]):
				character_to_update["position"] = position
				# Déplacement effectif (≠ « wait » 0,0) : le sol transitoire est vidé.
				ground_cleared = (position["x"], position["y"]) != (ancienne_pos["x"], ancienne_pos["y"])
				if ground_cleared:
					character_to_update["objets_au_sol"] = []
				access = get_lieu_directions(current_user, lieu_doc, position)
				# Événement de zone résolu AVANT le save pour persister la ressource récoltable.
				zone_event = None
				if lieu_doc.get("zone_influences"):
					zone_defs = load_zone_defs_for_lieu(lieu_doc, get_doc)
					zone_event = resolve_zone_event(
						position["x"], position["y"],
						lieu_doc["zone_influences"], zone_defs,
						boost=focalisation.boost_zone_event(character_to_update, lieu_doc)
					)
				_set_ressource_recoltable(character_to_update, zone_event, lieu_doc,
					favori=focalisation.favori_recolte(character_to_update))
				# Intro : conclusion quand le pas atteint la zone de sécurité de la cité.
				intro_terminee = intro.conclure_si_en_securite(character_to_update, lieu_doc)
				intro_xp = {"gain": 0, "niveau_up": False, "niveau": None}
				if intro_terminee and intro_terminee.get("xp"):
					info = grant_xp(character_to_update, intro_terminee["xp"])
					intro_xp = {"gain": intro_terminee["xp"], "niveau_up": info["niveau_up"], "niveau": info["niveau_apres"]}
				# Courses de transport échues (expiration paresseuse : pas de tick de fond).
				transports_echoues = transport.traiter_expirations(
					character_to_update, quetes.now_epoch(), get_doc, save_doc)
				_apply_world_turn_regen(character_to_update)
				_apply_world_turn_groupe(character_to_update)
				save_doc(character_to_update)
				links = get_lieu_links(current_user)
				# Un pas ne recharge pas la page : la sanction de réputation (−1 chez le donneur ET
				# sa maison) doit repartir avec la réponse, sinon l'onglet 🤝 — rendu 100 % client —
				# resterait sur le payload injecté au chargement. Payload calculé seulement en cas
				# d'échec (il relit les docs relation) ; la branche « lien », elle, recharge /play.
				relations_lieux = relations_lieux_payload(character_to_update) if transports_echoues else None
				return {"transports_echoues": _echecs_payload(transports_echoues), "relations_lieux": relations_lieux, "position": character_to_update["position"], "links": links, "access": access, "zone_event": zone_event, "vitals": _vitals_payload(character_to_update), "ground_cleared": ground_cleared, "ressource_recoltable": _recolte_payload(character_to_update), "effets_actifs": consommables.effets_actifs_payload(character_to_update), "caracts_detail": _caracts_payload(character_to_update), "affinites_detail": recrutement.affinites_detail_payload(character_to_update, get_doc), "guidage": focalisation.guidage(character_to_update, lieu_doc, find_docs, get_doc), "intro_terminee": intro_terminee, "intro_xp": intro_xp}
	raise HTTPException(status_code=404, detail="Incorrect movement info")


@user_router.post("/focaliser")
async def focaliser(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...)):
	"""Pose / retire (toggle) la focalisation du personnage.

	Body {"type": "lieu"|"quete", "cible": id}. Une seule focalisation à la fois
	(poser remplace l'existante). Réponse : {focalisation, guidage} pour resync client.
	"""
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")

	type_ = body.get("type")
	cible = body.get("cible")
	if type_ not in ("lieu", "quete") or not cible:
		raise HTTPException(status_code=422, detail="Focalisation invalide (type lieu|quete + cible requis)")
	if type_ == "lieu":
		doc = get_doc(cible)
		if not doc or doc.get("type") != "lieu":
			raise HTTPException(status_code=404, detail="Lieu introuvable")
		if cible == character.get("lieu"):
			raise HTTPException(status_code=422, detail="Vous êtes déjà sur place")
	else:
		q = quetes.quete_active(character, cible)
		if not q:
			raise HTTPException(status_code=404, detail="Quête introuvable dans vos quêtes actives")
		if not focalisation.quete_focalisable(q):
			raise HTTPException(status_code=422, detail="Cette quête ne peut pas être focalisée.")

	focalisation.poser_focalisation(character, type_, cible)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit d'écriture, réessayez")

	lieu_doc = get_doc(character.get("lieu")) or {}
	return {
		"focalisation": focalisation.payload_client(character, get_doc),
		"guidage": focalisation.guidage(character, lieu_doc, find_docs, get_doc),
	}


_VALID_STATS = {"V", "F", "R", "Ag", "Vol", "Int", "Cha", "Ch"}

_VALID_SLOTS = {
    "main_droite", "main_gauche", "torse", "tete", "jambes",
    "pieds", "mains", "anneau_1", "anneau_2", "cou", "ceinture",
}


def _derived_from_character(character: dict, equipment: EquipmentBonus) -> DerivedStats:
    # Buffs de consommables inclus : les dérivées (pv_max, dégâts…) en profitent partout
    # (vitals, régén, equip/unequip). Volontairement PAS bufées : charge_max_of (un buff
    # F expiré ne doit pas bloquer le déplacement en surcharge), les plafonds/coûts d'XP
    # (spend_xp) et restriction_satisfaite à l'équipement (anti-exploit).
    stats = consommables.caracts_avec_buffs(character)
    base = BaseStats(
        v=stats.get("V", 0), f=stats.get("F", 0),
        r=stats.get("R", 0), ag=stats.get("Ag", 0),
        vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
        cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
    )
    voc_niveau = character.get("vocations_niveaux", {}).get(character.get("voc", ""), 0)
    return compute_derived_stats(base, niveau=voc_niveau, equipment=equipment)


def _apply_world_turn_regen(character: dict) -> None:
    """Régén à chaque tour de jeu hors combat : ceil(R/20) PV et ceil(Vol/20) PM (+ les
    bonus regen_pv/regen_pm des effets actifs), plafonnés aux max. Puis décrémente les
    effets actifs (ordre régén-puis-tick : duree N = N applications). Si un buff expire,
    les max ont pu redescendre → re-clamp."""
    eq = sync_equipment_bonus(character)
    derived = _derived_from_character(character, eq)
    caracts = consommables.caracts_avec_buffs(character)
    bonus_pv, bonus_pm = consommables.regen_bonus(character)
    regen_pv = math.ceil(caracts.get("R", 1) / 20) + bonus_pv
    regen_pm = math.ceil(caracts.get("Vol", 1) / 20) + bonus_pm
    character["currentPV"] = min(derived.pv_max, character.get("currentPV", derived.pv_max) + regen_pv)
    character["currentPM"] = min(derived.pm_max, character.get("currentPM", derived.pm_max) + regen_pm)
    if consommables.tick_effets(character):
        derived = _derived_from_character(character, eq)
        character["currentPV"] = min(character["currentPV"], derived.pv_max)
        character["currentPM"] = min(character["currentPM"], derived.pm_max)


def _apply_world_turn_groupe(character: dict) -> list:
    """Le tour monde vaut pour TOUT le groupe : chaque compagnon régénère PV/PM et
    décrémente ses effets actifs exactement comme le joueur — un doc `aventurier:*` est
    un miroir du character, `_apply_world_turn_regen` s'y applique tel quel. Les docs
    compagnons sont ANNEXES au personnage : sauvés ici, séparément.

    Les MONTURES régénèrent au même titre : leur doc est le même miroir, elles pansent
    donc leurs plaies en marchant comme le reste de l'expédition. Elles ne sont pas
    renvoyées — l'appelant ne se sert du retour que pour les compagnons."""
    compagnons = recrutement.groupe_effectif(character, get_doc)
    for porteur in compagnons + montures.montures_effectives(character, get_doc):
        _apply_world_turn_regen(porteur)
        save_doc(porteur)
    return compagnons


def _caracts_payload(character: dict) -> dict:
    """Détail par caract (base/total/delta/sources nommées) pour la grille « Profil modifié »
    de la fiche : l'équipement doit être resynchronisé avant tout repli de buffs."""
    sync_equipment_bonus(character)
    return consommables.caracts_detail(character)


def _vitals_payload(character: dict) -> dict:
    """PV/PM courants + max, pour rafraîchir les jauges côté client sans recharger."""
    eq = sync_equipment_bonus(character)
    derived = _derived_from_character(character, eq)
    return {
        "currentPV": character.get("currentPV", derived.pv_max),
        "pv_max": derived.pv_max,
        "currentPM": character.get("currentPM", derived.pm_max),
        "pm_max": derived.pm_max,
    }


def _acteur(current_user, body: dict) -> tuple[dict, dict]:
	"""Résout le PORTEUR d'une action de fiche : le personnage sélectionné, ou l'un de ses
	compagnons — ou l'une de ses montures — si le corps porte un `compagnon_id`. Renvoie
	`(porteur, principal)` — les deux sont le MÊME dict hors mode compagnon (un seul
	`save_doc` suffit alors).

	Un doc `aventurier:*` comme un doc `monture:*` est un miroir du character (mêmes champs),
	donc tous les helpers de ce module s'y appliquent tels quels — c'est déjà ce que fait
	`_apply_world_turn_groupe` et, en combat, `_actor_character_id`. Ni l'un ni l'autre n'a
	de `user_id` : l'unique preuve d'appartenance est `porteurs_effectifs` (statut + lien
	vers CE personnage — « embauche »/`embauche_par`, « acquise »/`acquise_par`)."""
	principal = get_selected_character(current_user)
	if not principal:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	compagnon_id = (body or {}).get("compagnon_id")
	if not compagnon_id:
		return principal, principal

	av = next(
		(a for a in recrutement.porteurs_effectifs(principal, get_doc) if a.get("_id") == compagnon_id),
		None,
	)
	if av is None:
		raise HTTPException(status_code=403, detail="Ce porteur ne fait pas partie de votre groupe")
	return av, principal


def _cible_alliee(principal: dict, lanceur: dict, body: dict) -> dict:
	"""Résout la CIBLE d'un effet bénéfique hors combat (`cible: "allie"`) : le personnage
	principal, un compagnon ou une monture du groupe, désigné par `cible_id`.

	⚠️ Le LANCEUR est testé EN PREMIER. `porteurs_effectifs` relit les docs en base : si la
	cible est le lanceur lui-même, en passer par là rendrait un SECOND dict du même document
	— deux `save_doc` concurrents sur un `_rev` identique, donc une écriture perdue en
	silence. Renvoyer le dict déjà en main garantit qu'on ne manipule qu'un seul objet.

	Miroir de `_acteur` pour la preuve d'appartenance : un doc `aventurier:*`/`monture:*`
	n'a pas de `user_id`, seul `porteurs_effectifs` atteste du lien avec CE personnage.
	"""
	cible_id = (body or {}).get("cible_id")
	if not cible_id:
		raise HTTPException(status_code=422, detail="Cet effet demande une cible")
	if cible_id == lanceur.get("_id"):
		return lanceur
	if cible_id == principal.get("_id"):
		return principal
	cible = next(
		(a for a in recrutement.porteurs_effectifs(principal, get_doc) if a.get("_id") == cible_id),
		None,
	)
	if cible is None:
		raise HTTPException(status_code=403, detail="Cette cible ne fait pas partie de votre groupe")
	return cible


def _save_cast(lanceur: dict, cible: dict, principal: dict) -> None:
	"""Persiste un lancement hors combat : jusqu'à TROIS docs distincts (le lanceur qui
	paie les PM, la cible qui reçoit l'effet, le principal qui porte le groupe).

	Le LANCEUR est autoritatif (409 s'il ne passe pas) : c'est lui qui a payé. Un échec sur
	la cible est signalé mais non bloquant — même compromis best-effort que `_save_acteur`
	et que la séquence bi-doc du combat, faute d'écriture multi-documents atomique en
	CouchDB. Les doublons sont écartés par IDENTITÉ (`is`), pas par id : deux dicts du même
	doc ne doivent jamais arriver ici (cf. `_cible_alliee`)."""
	if save_doc(lanceur) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	deja = [lanceur]
	for autre in (cible, principal):
		if any(autre is d for d in deja):
			continue
		deja.append(autre)
		if save_doc(autre) is None:
			print(f"cast: échec de sauvegarde de {autre.get('_id')} (effet non persisté)")


def _save_acteur(porteur: dict, principal: dict) -> None:
	"""Sauve le porteur (autoritatif : 409 en cas de conflit) puis, si l'action a aussi muté
	le personnage principal (le sol lui appartient), son doc en best-effort — même séquence
	bi-doc que le recrutement et le combat."""
	if save_doc(porteur) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	if principal is not porteur:
		save_doc(principal)


@user_router.post("/spend_xp")
async def spend_xp(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")

	stat_key  = body.get("stat")
	new_value = body.get("new_value")
	use_bonus = body.get("use_max_bonus", False)

	if stat_key not in _VALID_STATS or not isinstance(new_value, int):
		raise HTTPException(status_code=422, detail="Paramètres invalides")

	character, _principal = _acteur(current_user, body)

	races = get_doc("rules:races")
	race  = next((r for r in races["value"] if r["id"] == character["race"]), None)
	if not race:
		raise HTTPException(status_code=404, detail="Race introuvable")

	stats_max_race     = race.get("stats_max", {})
	race_min           = race.get("stats", {}).get(stat_key, 0)
	nb_max_accessibles = race.get("nb_max_accessibles", 3)
	max_bonus          = race.get("max_bonus")
	max_bonus_used     = character.get("max_bonus_used")

	current_stats = character.get("caracteristiques_current", {})
	current_val   = current_stats.get(stat_key, 0)

	if new_value <= current_val:
		raise HTTPException(status_code=422, detail="La nouvelle valeur doit être supérieure à la valeur actuelle")

	# Calculer le plafond effectif (avant d'activer un éventuel bonus)
	effective_bonus_used = max_bonus_used
	if use_bonus:
		if max_bonus_used is not None:
			raise HTTPException(status_code=422, detail="Le bonus racial est déjà utilisé")
		if not max_bonus:
			raise HTTPException(status_code=422, detail="Cette race n'a pas de bonus de dépassement")
		effective_bonus_used = stat_key

	cap = compute_stat_cap(
		stat_key=stat_key,
		stats_max=stats_max_race,
		nb_max_accessibles=nb_max_accessibles,
		current_stats=current_stats,
		max_bonus=max_bonus,
		max_bonus_used=effective_bonus_used,
	)

	if new_value > cap:
		raise HTTPException(status_code=422, detail=f"Plafond de {cap} atteint pour {stat_key}")

	cost = compute_xp_cost(stat_key, current_val, new_value, race_min)
	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cost:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cost}, disponible {attribute_points})")

	# Appliquer la montée de stat
	character["caracteristiques_current"][stat_key] = new_value
	character["attribute_points"] = attribute_points - cost
	if use_bonus:
		character["max_bonus_used"] = stat_key

	save_doc(character)

	# Dérivées bufées + équipées (mêmes valeurs que la fiche : le client les recopie tel
	# quel dans #sh-drv-*). Les plafonds, eux, restent calculés sur les caracts BRUTES.
	derived = _derived_from_character(character, sync_equipment_bonus(character))
	stats_cur = character["caracteristiques_current"]

	new_caps = {
		code: compute_stat_cap(
			stat_key=code,
			stats_max=stats_max_race,
			nb_max_accessibles=nb_max_accessibles,
			current_stats=stats_cur,
			max_bonus=max_bonus,
			max_bonus_used=character.get("max_bonus_used"),
		)
		for code in _VALID_STATS
	}

	return {
		"stat":          stat_key,
		"new_value":     new_value,
		"attribute_points": character["attribute_points"],
		"stat_caps":     new_caps,
		# Le bonus racial vient peut-être d'être consommé : sans ce retour, le client
		# continuerait à offrir le geste sur les AUTRES caracts jusqu'au prochain /play.
		"max_bonus_used": character.get("max_bonus_used"),
		"derived_stats": derived.model_dump(),
		"caracts_detail": consommables.caracts_detail(character),
	}


@user_router.post("/equip")
async def equip_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	item_id = body.get("item_id")
	slot    = body.get("slot")

	if not item_id or slot not in _VALID_SLOTS:
		raise HTTPException(status_code=422, detail="Paramètres invalides")

	character, _principal = _acteur(current_user, body)

	inventaire = character.get("inventaire", [])
	# Référence correspondant à l'item (chaîne legacy ou objet {item, poids}).
	ref = next((r for r in inventaire if item_ref_id(r) == item_id), None)
	if ref is None:
		raise HTTPException(status_code=422, detail="Objet absent de l'inventaire")

	item = get_doc(item_id)
	if not item:
		raise HTTPException(status_code=404, detail="Objet introuvable")

	if slot not in item.get("slots", []):
		raise HTTPException(status_code=422, detail=f"Slot '{slot}' incompatible avec cet objet")

	# Prérequis de caractéristiques (armes) : blocage dur à l'équipement (sémantique ET).
	ok, manque = restriction_satisfaite(
		item.get("restriction"), character.get("caracteristiques_current", {})
	)
	if not ok:
		besoin = ", ".join(f"{c} {m}" for c, m in manque.items())
		raise HTTPException(
			status_code=422,
			detail=f"Caractéristiques insuffisantes pour équiper {item.get('nom', 'cet objet')} ({besoin}).",
		)

	slots = character.get("slots", {})

	# Arme à deux mains dans l'AUTRE main : rien n'est stocké dans le slot bloqué (pas de
	# double comptage du poids/des bonus), donc c'est ici, à la lecture, qu'on le refuse.
	bloquant = main_occupee_par_deux_mains(slots, lambda r: get_doc(item_ref_id(r)), slot)
	if bloquant:
		raise HTTPException(
			status_code=422,
			detail=f"Main occupée par {bloquant.get('nom', 'une arme à deux mains')} — déséquipez-la d'abord.",
		)

	displaced = slots.get(slot)
	if displaced:
		inventaire.append(displaced)

	# Une arme à deux mains libère l'AUTRE main en s'équipant : son éventuel occupant
	# repart au sac, comme le displaced du slot cible ci-dessus.
	autre = liberer_pour_deux_mains(slots, item, slot)
	if autre and slots.get(autre):
		inventaire.append(slots[autre])
		slots[autre] = None

	slots[slot] = ref          # garde la référence (poids d'instance préservé)
	inventaire.remove(ref)
	character["slots"]      = slots
	character["inventaire"] = inventaire

	eq_bonus = sync_equipment_bonus(character)
	save_doc(character)

	derived = _derived_from_character(character, eq_bonus)
	return {
		"slots":           {s: resolve_item_ref(v) if v else None for s, v in slots.items()},
		"inventaire":      [d for r in inventaire if (d := resolve_item_ref(r))],
		"equipment_bonus": character["equipment_bonus"],
		"derived_stats":   derived.model_dump(),
		"caracts_detail":  consommables.caracts_detail(character),
	}


@user_router.post("/unequip")
async def unequip_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	slot = body.get("slot")

	if slot not in _VALID_SLOTS:
		raise HTTPException(status_code=422, detail="Slot invalide")

	character, _principal = _acteur(current_user, body)

	slots   = character.get("slots", {})
	ref = slots.get(slot)
	if not ref:
		raise HTTPException(status_code=422, detail="Slot déjà vide")

	inventaire = character.get("inventaire", [])
	inventaire.append(ref)     # remet la référence (poids d'instance préservé)
	slots[slot] = None
	character["slots"]      = slots
	character["inventaire"] = inventaire

	eq_bonus = sync_equipment_bonus(character)
	save_doc(character)

	derived = _derived_from_character(character, eq_bonus)
	return {
		"slots":           {s: resolve_item_ref(v) if v else None for s, v in slots.items()},
		"inventaire":      [d for r in inventaire if (d := resolve_item_ref(r))],
		"equipment_bonus": character["equipment_bonus"],
		"derived_stats":   derived.model_dump(),
		"caracts_detail":  consommables.caracts_detail(character),
	}


def _inventory_payload(character: dict, sol_doc: dict | None = None) -> dict:
	"""Réponse partagée par drop/pickup : inventaire, sol et slots résolus en docs
	(poids d'instance inclus), plus la charge courante et la charge max.

	Le SOL n'appartient pas au porteur mais au lieu où se tient le personnage principal :
	un compagnon n'a ni `lieu` ni `position`. Quand le porteur est un compagnon, on passe
	donc le doc du principal en `sol_doc` — sac du compagnon, sol du joueur.

	⚠️ `charge_max` passe par `montures.charge_max_porteur` : le porteur peut être une
	monture, dont la capacité est démultipliée. `charge_max_of` seul sous-évaluerait son
	sac d'un facteur 3 à 5, et le client recopie cette valeur pour griser ses flèches."""
	slots = character.get("slots", {})
	sol   = sol_doc if sol_doc is not None else character
	return {
		"slots":         {s: resolve_item_ref(v) if v else None for s, v in slots.items()},
		"inventaire":    [d for r in character.get("inventaire", []) if (d := resolve_item_ref(r))],
		"objets_au_sol": [d for r in sol.get("objets_au_sol", []) if (d := resolve_item_ref(r))],
		"charge":        round(carried_weight(character), 2),
		"charge_max":    montures.charge_max_porteur(character),
	}


def _take_ref(refs: list, idx, item_id):
	"""Retire et renvoie la référence d'item ciblée. On adresse par index (deux
	exemplaires d'un même item peuvent avoir des poids d'instance distincts), vérifié
	via `item_id` ; repli sur le premier exemplaire de l'item si l'index est désaligné.
	None si introuvable."""
	if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(refs) \
			and (item_id is None or item_ref_id(refs[idx]) == item_id):
		return refs.pop(idx)
	if item_id is not None:
		pos = next((i for i, r in enumerate(refs) if item_ref_id(r) == item_id), None)
		if pos is not None:
			return refs.pop(pos)
	return None


@user_router.post("/drop_item")
async def drop_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Pose au sol un objet de l'inventaire (transitoire : perdu au prochain déplacement).
	Un compagnon pose au sol DU JOUEUR : le sac est le sien, le tas par terre est celui du
	lieu où se tient le principal."""
	character, principal = _acteur(current_user, body)

	inventaire = character.get("inventaire", [])
	ref = _take_ref(inventaire, body.get("index"), body.get("item_id"))
	if ref is None:
		raise HTTPException(status_code=422, detail="Objet absent de l'inventaire")

	au_sol = principal.get("objets_au_sol", [])
	au_sol.append(ref)
	character["inventaire"]    = inventaire
	principal["objets_au_sol"] = au_sol

	_save_acteur(character, principal)
	return _inventory_payload(character, principal)


@user_router.post("/pickup_item")
async def pickup_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Reprend un objet posé au sol. Si la charge max est alors dépassée, des objets
	ALÉATOIRES de l'inventaire (hors l'exemplaire repris) tombent au sol jusqu'à repasser
	sous la limite. Si l'objet repris seul (ou l'équipement) suffit à dépasser, on reste
	surchargé (déplacement bloqué tant qu'on ne se déleste pas).

	Un compagnon ramasse DANS LE SOL DU JOUEUR : le tas par terre est celui du lieu où se
	tient le principal, le sac (et la charge max qui borne le ramassage) sont ceux du porteur —
	mêmes règles que le principal (miroir de drop_item)."""
	character, principal = _acteur(current_user, body)

	au_sol = principal.get("objets_au_sol", [])
	picked = _take_ref(au_sol, body.get("index"), body.get("item_id"))
	if picked is None:
		raise HTTPException(status_code=422, detail="Objet absent du sol")

	inventaire = character.get("inventaire", [])
	inventaire.append(picked)
	character["inventaire"]     = inventaire
	principal["objets_au_sol"]  = au_sol

	# Auto-délestage : on protège exactement l'exemplaire ramassé (par identité), le
	# reste est candidat au largage aléatoire tant que le poids porté dépasse la limite.
	cmax = charge_max_of(character)
	auto_dropped = []
	while carried_weight(character) > cmax:
		candidats_idx = [i for i, r in enumerate(inventaire) if r is not picked]
		if not candidats_idx:
			break
		victime = inventaire.pop(random.choice(candidats_idx))
		au_sol.append(victime)
		doc = resolve_item_ref(victime)
		auto_dropped.append(doc.get("nom") if doc else item_ref_id(victime))
	character["inventaire"]     = inventaire
	principal["objets_au_sol"]  = au_sol

	_save_acteur(character, principal)
	payload = _inventory_payload(character, principal)
	payload["auto_dropped"] = auto_dropped
	return payload


@user_router.post("/consommer")
async def consommer_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Consomme un item du sac (potion, nourriture…) : applique la part instantanée
	(pv/pm, clampée aux max) et empile l'éventuel effet à durée (buffs/régén, décrémenté
	à chaque tour monde). Pas de garde de surcharge : consommer allège."""
	character, principal = _acteur(current_user, body)

	inventaire = character.get("inventaire", [])
	ref = _take_ref(inventaire, body.get("index"), body.get("item_id"))
	if ref is None:
		raise HTTPException(status_code=422, detail="Objet absent de l'inventaire")
	item = resolve_item_ref(ref)
	if not item or not consommables.est_consommable(item):
		# Rien n'a été sauvegardé : la ref poppée reste en mémoire seulement.
		raise HTTPException(status_code=422, detail="Cet objet ne peut pas être consommé")
	character["inventaire"] = inventaire

	# Buff empilé AVANT le calcul des max : une potion mixte soigne dans le max bufffé.
	effet = consommables.empiler_effet(character, item)
	eq = sync_equipment_bonus(character)
	derived = _derived_from_character(character, eq)
	rendu = consommables.appliquer_instantane(character, item, derived.pv_max, derived.pm_max)

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	payload = _inventory_payload(character, principal)
	payload["vitals"] = _vitals_payload(character)
	payload["effets_actifs"] = consommables.effets_actifs_payload(character)
	payload["caracts_detail"] = _caracts_payload(character)
	payload["consomme"] = {
		"nom": item.get("nom", "?"),
		"icon": item.get("icon", "🧪"),
		"pv_rendu": rendu["pv_rendu"],
		"pm_rendu": rendu["pm_rendu"],
		"effet": dict(effet) if effet else None,
	}
	return payload


@user_router.post("/lancer_sort")
async def lancer_sort(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Lance un sort connu HORS combat : débite les PM du LANCEUR, applique la part
	instantanée (pv/pm clampés) et empile l'éventuel effet à durée (buffs/régén,
	décrémenté au tour monde) sur la CIBLE. Les composants engagés (`composants` = ids
	item) sont re-vérifiés : les consommés quittent le sac, les catalyseurs restent.

	Deux personnages peuvent être en jeu, et il ne faut pas les confondre :
	  • le LANCEUR = `_acteur` (`compagnon_id`) — il connaît le sort, paie les PM et
	    fournit les composants ; c'est SA fiche qui est ouverte ;
	  • la CIBLE = lui-même (`cible: "soi"`) ou un allié désigné par `cible_id`
	    (`cible: "allie"` — compagnon ou monture, cf. `_cible_alliee`).
	⚠️ Cet endpoint lisait `get_selected_character` et ignorait donc `compagnon_id` : un
	sort lancé depuis la fiche d'un compagnon débitait les PM du PRINCIPAL et le buffait
	lui. Même classe de bug que le mélange des barres de slots du 2026-07-19."""
	character, principal = _acteur(current_user, body)

	sort_id = body.get("sort_id")
	if sort_id not in (character.get("sorts_connus") or []):
		raise HTTPException(status_code=422, detail="Sort inconnu du personnage")
	sort = sorts_util.normaliser_sort(get_doc(sort_id))
	if not sort or not sorts_util.sort_utilisable_exploration(sort):
		raise HTTPException(status_code=422, detail="Ce sort ne peut pas être lancé hors combat")
	if int(character.get("currentPM", 0) or 0) < sort["cout_pm"]:
		raise HTTPException(status_code=409, detail="PM insuffisants")

	# Composants engagés : indisponibles/inconnus ignorés (mode dégradé, jamais bloquant).
	etat = {c["item"]: c for c in sorts_util.composants_etat(sort, character)}
	inventaire = character.get("inventaire", [])
	engages: list = []
	for cid in body.get("composants") or []:
		c = etat.get(cid)
		if not c or not c["disponible"] or cid in engages:
			continue
		if c["consomme"] and _take_ref(inventaire, None, cid) is None:
			continue
		engages.append(cid)
	character["inventaire"] = inventaire
	effets = sorts_util.effets_effectifs(sort, engages)

	# Cible : soi-même, ou l'allié désigné. Résolue APRÈS les gardes du lanceur pour
	# qu'un sort inconnu ou sans PM échoue sur SA vraie cause.
	cible = _cible_alliee(principal, character, body) if sort["cible"] == "allie" else character

	# Buff empilé AVANT le calcul des max (même règle que les consommables), puis
	# débit PM (LANCEUR) et part instantanée clampée aux max bufffés (CIBLE).
	effet = sorts_util.empiler_effet_sort(cible, sort, effets)
	eq = sync_equipment_bonus(cible)
	derived = _derived_from_character(cible, eq)
	character["currentPM"] = max(0, int(character.get("currentPM", 0) or 0) - sort["cout_pm"])
	avant_pv = int(cible.get("currentPV", 0) or 0)
	avant_pm = int(cible.get("currentPM", 0) or 0)
	cible["currentPV"] = min(derived.pv_max, avant_pv + effets["pv"])
	cible["currentPM"] = min(derived.pm_max, avant_pm + effets["pm"])

	_save_cast(character, cible, principal)
	payload = _inventory_payload(character, principal)
	payload["vitals"] = _vitals_payload(character)
	payload["effets_actifs"] = consommables.effets_actifs_payload(character)
	payload["caracts_detail"] = _caracts_payload(character)
	payload["sorts"] = sorts_util.liste_sorts_payload(character, get_doc, "exploration")
	payload["lance"] = {
		"nom": sort["nom"],
		"icon": sort["icon"],
		"pv_rendu": cible["currentPV"] - avant_pv,
		"pm_rendu": cible["currentPM"] - avant_pm,
		"effet": dict(effet) if effet else None,
		# Renseignés seulement pour un sort d'allié : le client sait alors que les PV/PM
		# rendus ne concernent PAS la fiche ouverte, et rafraîchit la bonne carte.
		"cible_id": cible.get("_id") if cible is not character else None,
		"cible_nom": cible.get("nom") if cible is not character else None,
		"cible_vitaux": _vitals_payload(cible) if cible is not character else None,
	}
	return payload


@user_router.post("/apprendre_sort")
async def apprendre_sort(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Apprend un sort : coût en points de caractéristique ((niveau+1) × SORT_COUT_COEFF),
	école de magie pratiquée à un niveau suffisant (native ou achetée — MÊME règle que
	`sorts_apprenables`, qui alimente la liste affichée) et grimoire l'enseignant porté
	(sac ou équipé, NON consommé — un livre se relit). Ajoute l'id à `sorts_connus`. Un
	compagnon apprend avec SES points et le grimoire porté dans SON sac (d'où le transfert
	d'objets du groupe)."""
	character, _principal = _acteur(current_user, body)

	sort = sorts_util.normaliser_sort(get_doc(body.get("sort_id")))
	if not sort:
		raise HTTPException(status_code=422, detail="Sort introuvable")
	if sort["id"] in (character.get("sorts_connus") or []):
		raise HTTPException(status_code=422, detail="Sort déjà connu")
	vocations = get_doc("rules:vocations")
	ecole = sorts_util.magie_de_sort(sort, vocations)
	niveau = sorts_util.niveau_ecole(character, ecole, vocations)
	if niveau is None or niveau < sort["niveau"]:
		raise HTTPException(status_code=422, detail="École de magie non pratiquée ou niveau insuffisant")
	if sorts_util.grimoire_pour(character, sort["id"], resolve_item_ref) is None:
		raise HTTPException(status_code=409, detail="Grimoire requis pour apprendre ce sort")

	cout = sorts_util.cout_apprentissage(sort)
	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cout:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cout}, disponible {attribute_points})")

	character["attribute_points"] = attribute_points - cout
	character.setdefault("sorts_connus", []).append(sort["id"])
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	return {
		"attribute_points": character["attribute_points"],
		"sorts_connus": list(character["sorts_connus"]),
		"sorts": sorts_util.liste_sorts_payload(character, get_doc, "exploration"),
		"apprenables": sorts_util.sorts_apprenables(character, find_docs, resolve_item_ref, vocations),
		"sorts_magies": sorts_util.apprentissage_magies_payload(character, vocations),
		"appris": {"nom": sort["nom"], "icon": sort["icon"]},
	}


@user_router.post("/utiliser_competence")
async def utiliser_competence(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Utilise une compétence ACTIVE hors combat : débite les PM éventuels du LANCEUR,
	applique la part instantanée (pv/pm clampés) et empile l'effet à durée sur la CIBLE
	(soi, ou l'allié désigné par `cible_id`). Miroir exact de `lancer_sort`, sans
	composants — une compétence ne consomme aucun objet. Les passives ne s'« utilisent »
	pas : leur bonus est permanent (competences_bonus).

	⚠️ Même correctif que `lancer_sort` : cet endpoint lisait `get_selected_character` et
	ignorait `compagnon_id`, donc une compétence lancée depuis la fiche d'un compagnon
	s'appliquait au principal."""
	character, principal = _acteur(current_user, body)

	competence_id = body.get("competence_id")
	if competence_id not in (character.get("competences_connues") or []):
		raise HTTPException(status_code=422, detail="Compétence inconnue du personnage")
	comp = competences_util.normaliser_competence(get_doc(competence_id))
	if not comp or not competences_util.competence_utilisable_exploration(comp):
		raise HTTPException(status_code=422, detail="Cette compétence ne peut pas être utilisée hors combat")
	if int(character.get("currentPM", 0) or 0) < comp["cout_pm"]:
		raise HTTPException(status_code=409, detail="PM insuffisants")

	# Buff empilé AVANT le calcul des max (même règle que les consommables et les sorts),
	# puis débit PM et part instantanée clampée aux max bufffés.
	effets = comp["effets"]
	cible = _cible_alliee(principal, character, body) if comp["cible"] == "allie" else character
	effet = competences_util.empiler_effet_competence(cible, comp)
	eq = sync_equipment_bonus(cible)
	derived = _derived_from_character(cible, eq)
	character["currentPM"] = max(0, int(character.get("currentPM", 0) or 0) - comp["cout_pm"])
	avant_pv = int(cible.get("currentPV", 0) or 0)
	avant_pm = int(cible.get("currentPM", 0) or 0)
	cible["currentPV"] = min(derived.pv_max, avant_pv + effets["pv"])
	cible["currentPM"] = min(derived.pm_max, avant_pm + effets["pm"])

	_save_cast(character, cible, principal)
	payload = _inventory_payload(character, principal)
	payload["vitals"] = _vitals_payload(character)
	payload["effets_actifs"] = consommables.effets_actifs_payload(character)
	payload["caracts_detail"] = _caracts_payload(character)
	payload["competences"] = competences_util.liste_competences_payload(character, get_doc, "exploration")
	payload["utilisee"] = {
		"nom": comp["nom"],
		"icon": comp["icon"],
		"pv_rendu": cible["currentPV"] - avant_pv,
		"pm_rendu": cible["currentPM"] - avant_pm,
		"effet": dict(effet) if effet else None,
		"cible_id": cible.get("_id") if cible is not character else None,
		"cible_nom": cible.get("nom") if cible is not character else None,
		"cible_vitaux": _vitals_payload(cible) if cible is not character else None,
	}
	return payload


@user_router.post("/apprendre_competence")
async def apprendre_competence(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Apprend une compétence de sa vocation : coût en points de caractéristique
	((niveau + 1) × COMPETENCE_COUT_COEFF) et niveau de vocation suffisant. Miroir de
	`apprendre_sort`, sans grimoire (l'équivalent viendra avec l'arbre de compétences).
	Ajoute l'id à `competences_connues` et re-dénormalise le bonus des passives."""
	character, _principal = _acteur(current_user, body)

	comp = competences_util.normaliser_competence(get_doc(body.get("competence_id")))
	if not comp:
		raise HTTPException(status_code=422, detail="Compétence introuvable")
	if comp["id"] in (character.get("competences_connues") or []):
		raise HTTPException(status_code=422, detail="Compétence déjà connue")
	if comp["vocation"] != character.get("voc"):
		raise HTTPException(status_code=422, detail="Cette compétence n'est pas de votre vocation")
	niveaux = character.get("vocations_niveaux", {})
	if niveaux.get(comp["vocation"], 0) < comp["niveau"]:
		raise HTTPException(status_code=422, detail="Niveau de vocation insuffisant")

	cout = competences_util.cout_apprentissage(comp)
	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cout:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cout}, disponible {attribute_points})")

	character["attribute_points"] = attribute_points - cout
	character.setdefault("competences_connues", []).append(comp["id"])
	# Une passive apprise buffe immédiatement : re-dénormaliser AVANT le save.
	competences_util.recompute_competences_bonus(character, get_doc)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	return {
		"attribute_points": character["attribute_points"],
		"competences_connues": list(character["competences_connues"]),
		"competences": competences_util.liste_competences_payload(character, get_doc, "exploration"),
		"competences_apprenables": competences_util.competences_apprenables(character, find_docs),
		"vitals": _vitals_payload(character),
		"caracts_detail": _caracts_payload(character),
		"appris": {"nom": comp["nom"], "icon": comp["icon"]},
	}


@user_router.post("/apprendre_magie")
async def apprendre_magie(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Achète la PRATIQUE d'une nouvelle école de magie (réservé aux vocations
	polyvalentes — le lettré). Coût en points de caractéristique = cout_ecole(0). Ajoute
	l'école à `magies_apprises` au niveau 0 ; débloque l'apprentissage de ses sorts."""
	character, _principal = _acteur(current_user, body)
	if not sorts_util.peut_apprendre_magie(character):
		raise HTTPException(status_code=403, detail="Cette vocation ne peut pas apprendre d'autres écoles de magie.")

	vocations = get_doc("rules:vocations")
	ecole = str(body.get("ecole") or "").strip()
	if not ecole or ecole not in sorts_util.ecoles_du_monde(vocations):
		raise HTTPException(status_code=422, detail="École de magie inconnue")
	if ecole not in sorts_util.ecoles_achetables(character, vocations):
		raise HTTPException(status_code=422, detail="École déjà pratiquée")

	cout = sorts_util.cout_ecole(0)
	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cout:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cout}, disponible {attribute_points})")

	character["attribute_points"] = attribute_points - cout
	character.setdefault("magies_apprises", {})[ecole] = 0
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	return {
		"attribute_points": character["attribute_points"],
		"sorts_magies": sorts_util.apprentissage_magies_payload(character, vocations),
		"apprenables": sorts_util.sorts_apprenables(character, find_docs, resolve_item_ref, vocations),
		"apprise": {"ecole": ecole},
	}


@user_router.post("/monter_magie")
async def monter_magie(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Monte d'un niveau une école ACHETÉE (dans `magies_apprises`). Coût =
	cout_ecole(niveau courant). L'école native se monte via spend_xp_vocation."""
	character, _principal = _acteur(current_user, body)

	vocations = get_doc("rules:vocations")
	ecole = str(body.get("ecole") or "").strip()
	apprises = character.get("magies_apprises") or {}
	if ecole not in apprises:
		raise HTTPException(status_code=422, detail="École non pratiquée (achetée)")

	niveau = int(apprises[ecole])
	cout = sorts_util.cout_ecole(niveau)
	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cout:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cout}, disponible {attribute_points})")

	character["attribute_points"] = attribute_points - cout
	character["magies_apprises"][ecole] = niveau + 1
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	return {
		"attribute_points": character["attribute_points"],
		"sorts_magies": sorts_util.apprentissage_magies_payload(character, vocations),
		"apprenables": sorts_util.sorts_apprenables(character, find_docs, resolve_item_ref, vocations),
		"ecole": {"ecole": ecole, "niveau": niveau + 1},
	}


@user_router.post("/slot_action")
async def slot_action(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Pose (ou vide) une action dans une case de la barre de combat.

	Corps : `{position, entree: {type, ref} | null, compagnon_id?}` — `entree: null`
	vide la case. Les trois actions obligatoires (mêlée, ramasser, fuir) ne se vident
	pas : elles se DÉPLACENT (`/slot_deplacer`), d'où le 422 renvoyé par `vider_slot`."""
	character, _principal = _acteur(current_user, body)

	try:
		entree = body.get("entree")
		if entree is None:
			slots_actions.vider_slot(character, body.get("position"), get_doc)
		else:
			slots_actions.poser_slot(character, body.get("position"), entree, get_doc)
	except ValueError as err:
		raise HTTPException(status_code=422, detail=str(err))

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	return {"slots": slots_actions.slots_payload(character, get_doc)}


@user_router.post("/slot_deplacer")
async def slot_deplacer(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Échange deux cases de la barre (glisser-déposer). Seul geste capable de bouger une
	action obligatoire — l'échange garantit qu'aucune ne peut être perdue au passage."""
	character, _principal = _acteur(current_user, body)

	try:
		slots_actions.deplacer_slot(character, body.get("source"), body.get("cible"), get_doc)
	except ValueError as err:
		raise HTTPException(status_code=422, detail=str(err))

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	return {"slots": slots_actions.slots_payload(character, get_doc)}


@user_router.post("/recolter")
async def recolter_ressource(
	current_user: Annotated[User, Depends(get_current_user)],
):
	"""Récolte la ressource rendue disponible par le dernier événement de zone « ressource »
	(champ transitoire `ressource_recoltable`). Ajoute l'item au sac (refus 409 si la charge
	max serait dépassée), puis vide le champ (consommé)."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	ref = character.get("ressource_recoltable")
	if not ref:
		raise HTTPException(status_code=404, detail="Rien à récolter ici.")

	doc = resolve_item_ref(ref)
	if not doc:
		# Item disparu de la base : on nettoie le champ.
		character["ressource_recoltable"] = None
		save_doc(character)
		raise HTTPException(status_code=404, detail="Ressource introuvable.")

	# Bois (item « a_couper ») : récolter = abattre AVEC un outil ; les pièces (tier
	# immédiatement plus petit) tombent au SOL (pas de contrôle de charge), à ramasser
	# ensuite. Sans outil → refus.
	if bois.item_est_coupable(doc):
		if not bois.a_outil_coupe(character, get_doc, recrutement.groupe_effectif(character, get_doc)):
			raise HTTPException(status_code=409, detail="Il faut un outil de coupe (hache, scie…) pour récolter du bois.")
		pieces = bois.couper_ref(ref, doc, find_docs) or [ref]
		au_sol = character.get("objets_au_sol", [])
		au_sol.extend(pieces)
		character["objets_au_sol"] = au_sol
		character["ressource_recoltable"] = None
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		payload = _inventory_payload(character)
		payload["recolte"] = {"nom": doc.get("nom", "Bois"), "icon": doc.get("icon", "🪵"), "coupe": True, "n": len(pieces)}
		payload["ressource_recoltable"] = None
		return payload

	if carried_weight(character) + item_ref_weight(ref) > charge_max_of(character):
		raise HTTPException(status_code=409, detail="Trop chargé pour récolter — déposez un objet.")

	inventaire = character.get("inventaire", [])
	inventaire.append(ref)
	character["inventaire"] = inventaire
	character["ressource_recoltable"] = None

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	payload = _inventory_payload(character)
	payload["recolte"] = {"nom": doc.get("nom", "Ressource"), "icon": doc.get("icon", "🌿")}
	payload["ressource_recoltable"] = None
	return payload


@user_router.post("/couper")
async def couper_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Coupe un item « a_couper » (bois) d'un niveau : retire la source du sac (du personnage
	OU d'un compagnon via `compagnon_id`) OU du sol, et dépose au SOL du principal les pièces du
	tier immédiatement plus petit (poids conservé). Nécessite un outil de coupe (item taggé),
	PARTAGÉ par le groupe. Body : {index, item_id, source:"sac"|"sol", compagnon_id?}."""
	porteur, principal = _acteur(current_user, body)

	if not bois.a_outil_coupe(principal, get_doc, recrutement.groupe_effectif(principal, get_doc)):
		raise HTTPException(status_code=409, detail="Il faut un outil de coupe (hache, scie…).")

	source = body.get("source")
	# Le sac coupé est celui du PORTEUR (compagnon si `compagnon_id`) ; le sol est TOUJOURS
	# celui du principal (il appartient au lieu — un compagnon n'a ni lieu ni position).
	refs = principal.get("objets_au_sol", []) if source == "sol" else porteur.get("inventaire", [])
	idx, item_id = body.get("index"), body.get("item_id")

	target_ref = _find_ref(refs, idx, item_id)
	if target_ref is None:
		raise HTTPException(status_code=422, detail="Objet introuvable.")
	pieces = bois.couper_ref(target_ref, get_doc(item_ref_id(target_ref)), find_docs)
	if not pieces:
		raise HTTPException(status_code=422, detail="Cet objet ne peut pas être coupé davantage.")

	if _take_ref(refs, idx, item_id) is None:
		raise HTTPException(status_code=409, detail="Conflit — réessayez.")
	if source == "sol":
		principal["objets_au_sol"] = refs
	else:
		porteur["inventaire"] = refs
	au_sol = principal.get("objets_au_sol", [])
	au_sol.extend(pieces)
	principal["objets_au_sol"] = au_sol

	# Porteur autoritatif (409 si conflit) puis principal en best-effort — le sol lui
	# appartient (bi-doc). Hors mode compagnon, porteur EST principal → un seul save.
	_save_acteur(porteur, principal)

	cible_doc = get_doc(pieces[0]["item"])
	payload = _inventory_payload(porteur, principal)
	payload["coupe"] = {
		"n": len(pieces),
		"nom": cible_doc.get("nom", "pièces") if cible_doc else "pièces",
		"taille": cible_doc.get("sous_categorie", "") if cible_doc else "",
	}
	return payload


def _current_lieu_doc(character: dict) -> dict | None:
	"""Doc du lieu où se trouve le personnage (repli sur sa cité)."""
	return get_doc(character.get("lieu", character.get("cite")))


def _find_ref(refs: list, idx, item_id):
	"""Comme _take_ref mais sans retirer : renvoie la réf ciblée (index vérifié item_id,
	repli premier exemplaire), ou None. Utilisé par le marchandage (lecture seule)."""
	if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(refs) \
			and (item_id is None or item_ref_id(refs[idx]) == item_id):
		return refs[idx]
	if item_id is not None:
		return next((r for r in refs if item_ref_id(r) == item_id), None)
	return None


def _marchand_vendables(character: dict, lieu_doc: dict, relation: dict | None = None,
						porteurs_tiers: list | None = None) -> list:
	"""Liste des items que le marchand du lieu achète, **agrégée sur toute l'expédition** :
	le sac du personnage principal PUIS celui de chaque porteur — compagnon OU monture (une
	bête de somme est là pour rapporter du butin lourd : ce qu'elle porte doit être vendable
	sans transfert préalable). Chaque entrée porte son prix courant (négocié ou base pondéré
	relation) et sa fourchette min–max. Adressée par `index` (dans le sac de SON porteur,
	vérifié par item_id : deux exemplaires peuvent peser/valoir différemment) +
	`compagnon_id` (None = principal → le porteur de l'objet). La relation/le marchandage
	restent ceux du principal : c'est lui qui traite et encaisse."""
	# (compagnon_id, doc, nom affiché, icône) — None pour le principal (objets non badgés
	# côté UI). Une monture n'a pas de `prenom`, seulement un `nom`.
	porteurs = [(None, character, "", "")]
	for c in (porteurs_tiers or []):
		icon = "🐴" if montures.est_monture(c) else "👤"
		porteurs.append((c.get("_id"), c, c.get("prenom") or c.get("nom") or "Porteur", icon))

	vendables = []
	for compagnon_id, porteur, nom, porteur_icon in porteurs:
		for idx, ref in enumerate(porteur.get("inventaire", [])):
			item = resolve_item_ref(ref)
			if not item or not lieu_buys(lieu_doc, item):
				continue
			item_id = item.get("item") or item.get("_id")
			pmin, pmax, stock_mat = params_vente_lieu(lieu_doc, item, item_id, ref)
			cible = stock_cible_pour(lieu_doc, item)
			prix_cuivre = prix_marche(relation, item_id, pmin, pmax, "vente", stock_mat, cible)
			negocie = (relation or {}).get("prix_negocies", {}).get(item_id, {}).get("vente") is not None
			vendables.append({
				"index": idx,
				"compagnon_id": compagnon_id,
				"porteur_nom": nom,
				"porteur_icon": porteur_icon,
				"item_id": item_id,
				"nom": item.get("nom"),
				"icon": item.get("icon"),
				"poids": round(float(item.get("poids", 0) or 0), 2),
				"prix_cuivre": prix_cuivre,
				"prix": cuivre_to_purse(prix_cuivre),
				"prix_min_purse": cuivre_to_purse(pmin),
				"prix_max_purse": cuivre_to_purse(pmax),
				"negocie": negocie,
				**fiche_item_fields(item),
			})
	return vendables


@user_router.get("/marchand/quotes")
async def marchand_quotes(
	current_user: Annotated[User, Depends(get_current_user)],
):
	"""Liste initiale du panneau Vente : objets vendables ici + bourse + relation au lieu."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = _current_lieu_doc(character)
	relation = get_relation(character, lieu_doc)
	porteurs = recrutement.porteurs_effectifs(character, get_doc)
	return {
		"lieu_label": (lieu_doc or {}).get("label"),
		"vendables": _marchand_vendables(character, lieu_doc, relation, porteurs),
		"achetables": resolve_stock_vente(lieu_doc, relation),
		"cha_marchand": merchant_cha(lieu_doc),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"relation": relation_value(relation),
		"bloque_jusqu": int(relation.get("marchandage_bloque_jusqu", 0) or 0),
		"now": now_epoch(),
		"relations_lieux": relations_lieux_payload(character),
	}


def _player_cha(character: dict) -> int:
	"""Cha courant du personnage (échelle ×10), 0 si absent."""
	return int((character.get("caracteristiques_current") or {}).get("Cha", 0) or 0)


@user_router.post("/sell_item")
async def sell_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Vend un objet au marchand du lieu courant. L'objet peut appartenir au personnage OU
	à un compagnon du groupe (`compagnon_id` optionnel) — l'expédition met en commun ses
	biens —, mais **l'argent revient toujours au personnage principal** (qui rétribue déjà
	ses compagnons via leur part de butin). Adressage par index vérifié par item_id (robuste
	au décalage après chaque vente puisqu'on re-render depuis `vendables`)."""
	porteur, principal = _acteur(current_user, body)

	lieu_doc = _current_lieu_doc(principal)
	relation = get_relation(principal, lieu_doc)
	if relation_value(relation) <= 0:
		raise HTTPException(status_code=403, detail="Ce marchand refuse de traiter avec vous.")

	inventaire = porteur.get("inventaire", [])
	ref = _take_ref(inventaire, body.get("index"), body.get("item_id"))
	if ref is None:
		raise HTTPException(status_code=422, detail="Objet absent de l'inventaire")

	item = resolve_item_ref(ref)
	if not item or not lieu_buys(lieu_doc, item):
		# On a `pop` la ref mais on raise avant tout save_doc : sans effet sur le doc.
		raise HTTPException(status_code=422, detail="Le marchand n'achète pas cet objet")

	# Prix appliqué = prix marché (prix courant relation/marchandage modulé par le stock du
	# marchand en cette matière), calculé AVANT que le lieu n'absorbe l'objet.
	item_id = item.get("item") or item.get("_id")
	pmin, pmax, stock_mat = params_vente_lieu(lieu_doc, item, item_id, ref)
	cible = stock_cible_pour(lieu_doc, item)
	prix = prix_marche(relation, item_id, pmin, pmax, "vente", stock_mat, cible)
	purse = credit_character(principal, prix)   # l'argent va au principal, l'objet quitte le porteur
	porteur["inventaire"] = inventaire

	# Le lieu absorbe l'objet acheté → matières → stock vendable (mute lieu_doc).
	convertir_apres_achat(lieu_doc, item)

	# Porteur d'abord (autoritatif : l'objet est retiré pour de bon → pas de double vente),
	# puis le principal (monnaie, best-effort si compagnon). Même séquence bi-doc que drop.
	_save_acteur(porteur, principal)
	save_doc(lieu_doc)  # best-effort : le stock du lieu est une commodité monde

	porteurs = recrutement.porteurs_effectifs(principal, get_doc)
	payload = _inventory_payload(principal)
	payload["purse"] = purse
	payload["vendables"] = _marchand_vendables(principal, lieu_doc, relation, porteurs)
	payload["achetables"] = resolve_stock_vente(lieu_doc, relation)
	payload["vendu"] = {"nom": item.get("nom"), "prix": cuivre_to_purse(prix)}
	payload["relation"] = relation_value(relation)
	return payload


@user_router.post("/buy_item")
async def buy_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Achète un objet du stock de vente du lieu courant. Marchandage à l'achat (le
	joueur veut le prix le plus bas). Refus si fonds insuffisants ou surcharge."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")

	lieu_doc = _current_lieu_doc(character) or {}
	relation = get_relation(character, lieu_doc)
	if relation_value(relation) <= 0:
		raise HTTPException(status_code=403, detail="Ce marchand refuse de traiter avec vous.")

	item_id = body.get("item_id")
	stock_vente = lieu_doc.get("stock_vente", [])
	entry = next((e for e in stock_vente if e.get("item_id") == item_id and int(e.get("qty", 0)) > 0), None)
	if entry is None:
		raise HTTPException(status_code=422, detail="Objet indisponible à la vente ici")

	item = resolve_item_ref(item_id)
	if not item:
		raise HTTPException(status_code=422, detail="Objet introuvable")

	# Prix marché à l'achat (relation/marchandage modulé par le stock en rayon de ce produit),
	# calculé avant le décrément du stock.
	pmin, pmax = prix_range_cuivre(item, item_id)
	cible = stock_cible_pour(lieu_doc, item)
	prix = prix_marche(relation, item_id, pmin, pmax, "achat", int(entry.get("qty", 0)), cible)

	if carried_weight(character) + item_ref_weight(item_id) > charge_max_of(character):
		raise HTTPException(status_code=422, detail="Trop chargé pour porter cet objet")

	purse = debit_character(character, prix)
	if purse is None:
		raise HTTPException(status_code=422, detail="Fonds insuffisants")

	# Décrément du stock du lieu + ajout à l'inventaire (ref chaîne = poids min de l'item).
	entry["qty"] = int(entry.get("qty", 0)) - 1
	lieu_doc["stock_vente"] = [e for e in stock_vente if int(e.get("qty", 0)) > 0]
	character.setdefault("inventaire", []).append(item_id)

	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	# Tick marché à l'achat aussi (approvisionnement + production + écoulement PNJ), comme à la
	# vente et à l'entrée du lieu — l'achat vient de retirer du stock à reconstituer.
	tick_atelier(lieu_doc)
	save_doc(lieu_doc)  # best-effort : décrément du stock monde

	payload = _inventory_payload(character)
	payload["purse"] = purse
	payload["vendables"] = _marchand_vendables(character, lieu_doc, relation, recrutement.porteurs_effectifs(character, get_doc))
	payload["achetables"] = resolve_stock_vente(lieu_doc, relation)
	payload["achete"] = {"nom": item.get("nom"), "prix": cuivre_to_purse(prix)}
	payload["relation"] = relation_value(relation)
	return payload


@user_router.post("/marchander")
async def marchander_item(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Tente un marchandage explicite sur un objet (sens "vente" ou "achat"). Jet Cha
	joueur vs Cha marchand + bonus de relation. Réussite → persiste le prix négocié pour
	cet objet. Crit réussite (roll ≤ MAX) → +1 relation ; crit échec (roll ≥ MIN) →
	−1 relation ET blocage du marchandage pendant MARCHANDAGE_BLOCAGE_SECONDES. Ne touche
	ni l'inventaire ni la bourse (le prix s'applique à la prochaine vente/achat)."""
	# Le porteur peut être un compagnon (marchandage d'un objet du groupe) ; le principal
	# reste celui qui négocie et dont dépend la relation au marchand.
	porteur, principal = _acteur(current_user, body)
	character = principal

	sens = body.get("sens")
	if sens not in ("vente", "achat"):
		raise HTTPException(status_code=422, detail="Sens de marchandage invalide")

	lieu_doc = _current_lieu_doc(character) or {}
	relation = get_relation(character, lieu_doc)
	if relation_value(relation) <= 0:
		raise HTTPException(status_code=403, detail="Ce marchand refuse de traiter avec vous.")

	now = now_epoch()
	if marchandage_bloque(relation, now):
		raise HTTPException(status_code=403, detail="Le marchand refuse de négocier pour l'instant.")

	# Résoudre l'objet et sa fourchette de prix (vente : ref du sac du porteur ; achat : stock du lieu).
	item_id = body.get("item_id")
	if sens == "vente":
		ref = _find_ref(porteur.get("inventaire", []), body.get("index"), item_id)
		if ref is None:
			raise HTTPException(status_code=422, detail="Objet absent de l'inventaire")
		item = resolve_item_ref(ref)
		if not item or not lieu_buys(lieu_doc, item):
			raise HTTPException(status_code=422, detail="Le marchand n'achète pas cet objet")
		item_id = item.get("item") or item.get("_id")
		pmin, pmax, _ = params_vente_lieu(lieu_doc, item, item_id, ref)
	else:  # achat
		entry = next((e for e in lieu_doc.get("stock_vente", [])
					  if e.get("item_id") == item_id and int(e.get("qty", 0)) > 0), None)
		if entry is None:
			raise HTTPException(status_code=422, detail="Objet indisponible à la vente ici")
		item = resolve_item_ref(item_id)
		if not item:
			raise HTTPException(status_code=422, detail="Objet introuvable")
		pmin, pmax = prix_range_cuivre(item, item_id)

	seuil_bonus = _relation_seuil_bonus(relation_value(relation))
	deal = marchander(pmin, pmax, _player_cha(character), merchant_cha(lieu_doc), sens, seuil_bonus)
	issue = appliquer_marchandage(relation, item_id, sens, deal, now)

	if save_doc(relation) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	return {
		"sens": sens,
		"deal": deal,
		"crit": issue["crit"],
		"relation": issue["relation"],
		"prix_negocie": cuivre_to_purse(issue["prix_negocie"]) if issue["prix_negocie"] is not None else None,
		"bloque_jusqu": issue["bloque_jusqu"],
		"now": now,
		"vendables": _marchand_vendables(character, lieu_doc, relation, recrutement.groupe_effectif(character, get_doc)),
		"achetables": resolve_stock_vente(lieu_doc, relation),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"relations_lieux": relations_lieux_payload(character),
	}


@user_router.post("/spend_xp_vocation")
async def spend_xp_vocation(
	current_user: Annotated[User, Depends(get_current_user)],
	body: dict = Body(default={}),
):
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")

	character, _principal = _acteur(current_user, body)

	voc = character.get("voc", "")
	vocations_niveaux = character.get("vocations_niveaux", {})
	voc_niveau = vocations_niveaux.get(voc, 0)
	cout = (voc_niveau + 1) * character_stats.XP_VOC_COEFF

	attribute_points = character.get("attribute_points", 0)
	if attribute_points < cout:
		raise HTTPException(status_code=422, detail=f"Points insuffisants (besoin {cout}, disponible {attribute_points})")

	vocations_niveaux[voc] = voc_niveau + 1
	character["vocations_niveaux"] = vocations_niveaux
	character["attribute_points"] = attribute_points - cout
	save_doc(character)

	return {
		"attribute_points": character["attribute_points"],
		"voc_niveau":    voc_niveau + 1,
		"xp_cout_next":  (voc_niveau + 2) * 5,
	}