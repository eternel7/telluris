# routers/commande.py
# Endpoints de la commande auprès d'un artisan : faire fabriquer ce qui n'est pas en rayon.
#
# TROIS gardes INDÉPENDANTES, et c'est toute l'affaire :
#   `commande.lieu_prend_commandes`      — son catalogue épuré n'est pas vide (tout atelier) ;
#   `commande.lieu_fabrique_sur_mesure`  — réservé aux grandes maisons, SEULE porte vers la
#                                          création d'un doc `item:`/`recette:` en base ;
#   `marche.est_intermediaire`           — porte sur l'OBJET et non sur le lieu : une matière
#                                          ou un demi-produit ne se façonne jamais sur mesure.
# Une commande de catalogue passe chez l'armurier du coin ; la même assortie de matières
# personnalisées ne passe qu'au Grand Arsenal ; et pas sur une hampe, même là-bas.
# Les deux dernières sont réunies dans `_garde_sur_mesure` — elles ne vont jamais l'une sans
# l'autre, et la liste des matières comme le devis doivent les voir pareil.
#
# Pattern calqué sur routers/scriptorium.py (lui-même sur routers/auberge.py) : accès au lieu
# par prédicat, contrôle AVANT dépense, retrait en MÉMOIRE puis un save autoritatif.
#
# ⚠️ Sens d'import : `routers/commande` → `routers/user`, jamais l'inverse.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc
from models import character_stats
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, carried_weight, charge_max_of, credit_character,
	cuivre_to_purse, money_to_cuivre, resolve_item_ref, lieu_label,
)
from utils import commande as commande_util
from utils import fabrication
from utils import marche
from utils import recrutement
from utils.marche import (
	debit_character, get_relation, relation_value, prix_range_cuivre,
	prix_marche, stock_cible_pour, resolve_stock_vente,
)
from routers.user import _inventory_payload, _marchand_vendables

commande_router = APIRouter()


# ── Accès ───────────────────────────────────────────────────────────────────────

def _acces(current_user: dict) -> tuple[dict, dict]:
	"""`(personnage, lieu)` pour toute opération de commande : personnage sélectionné (404),
	atelier capable d'en prendre une (403). Miroir de `_acces_scriptorium`."""
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=404, detail="Personnage introuvable")
	lieu_doc = get_doc(character.get("lieu", ""))
	if not lieu_doc or not commande_util.lieu_prend_commandes(lieu_doc, get_doc):
		raise HTTPException(status_code=403, detail="On ne prend pas de commande ici.")
	return character, lieu_doc


def _garde_relation(character: dict, lieu_doc: dict) -> dict:
	"""Même refus que les trois endpoints mutants du marché : un marchand banni ne traite pas."""
	relation = get_relation(character, lieu_doc)
	if relation_value(relation) <= 0:
		raise HTTPException(status_code=403, detail="Ce marchand refuse de traiter avec vous.")
	return relation


def _prix_achat(relation, lieu_doc):
	"""`prix_fn` pour `commande.sourcer` : le prix d'achat du marché, relation et marchandage
	compris. Injecté plutôt que recodé — il n'existe qu'UNE formule de prix dans le jeu, et
	c'est celle que le panneau d'achat affiche déjà pour la même matière."""
	def prix(item_id, item_doc, en_rayon):
		pmin, pmax = prix_range_cuivre(item_doc, item_id)
		cible = stock_cible_pour(lieu_doc, item_doc)
		return prix_marche(relation, item_id, pmin, pmax, "achat", en_rayon, cible)
	return prix


def _prix_piece(relation, lieu_doc, item_doc, item_id) -> int:
	"""Prix de base d'une pièce commandée : le prix du marché **à stock nul**.

	⚠️ `stock=0` n'est pas un raccourci : c'est exactement la situation — l'objet n'est pas en
	rayon, c'est pour cela qu'on le commande. Le facteur de rareté de `prix_marche` renchérit
	alors la pièce, ce qui est le comportement voulu et déjà éprouvé côté vitrine."""
	pmin, pmax = prix_range_cuivre(item_doc, item_id)
	cible = stock_cible_pour(lieu_doc, item_doc)
	return prix_marche(relation, item_id, pmin, pmax, "achat", 0, cible)


def _save_porteurs(principal: dict, porteurs_mutes: list) -> None:
	"""Persiste le principal (AUTORITATIF : 409 s'il ne passe pas — c'est lui qui porte la
	commande et qui a payé) puis chaque porteur dont le sac a été allégé, en best-effort.

	Même compromis bi-doc que `_save_acteur`/`_save_cast`, faute d'écriture multi-documents
	atomique en CouchDB. L'ordre est celui qui perd le moins : si un compagnon ne passe pas,
	il garde sa matière alors que la commande est enregistrée — le joueur est servi. L'inverse
	lui prendrait sa matière sans rien lui promettre."""
	if save_doc(principal) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	for porteur in porteurs_mutes:
		if porteur is principal:
			continue
		if save_doc(porteur) is None:
			print(f"commande: échec de sauvegarde de {porteur.get('_id')} (matière non prélevée)")


# ── Vue commune ─────────────────────────────────────────────────────────────────

def _vue_commandes(character: dict, now: int) -> list:
	"""Les commandes du joueur, la plus proche d'être prête en tête."""
	vues = [commande_util.vue(c, get_doc, now) for c in (character.get("commandes") or [])]
	return sorted(vues, key=lambda v: (v["statut"] != commande_util.ETAT_TERMINEE, v["pret_dans"]))


def _catalogue_vue(lieu_doc: dict, relation) -> list:
	"""Le catalogue commandable, résolu pour le client (nom, icône, prix indicatif).

	⚠️ Le prix annoncé est celui d'une commande où le joueur n'apporte RIEN : pièce + façon.
	C'est le plafond — apporter des ingrédients ne peut que le faire baisser. L'estimer
	autrement demanderait de sourcer les sacs du groupe pour chaque ligne du catalogue, soit
	un balayage complet de l'inventaire par objet fabricable. Le devis, lui, est exact."""
	lignes = []
	for item_id in commande_util.catalogue_commandable(lieu_doc, get_doc):
		item = resolve_item_ref(item_id)
		if not item:
			continue
		prix = commande_util.devis(_prix_piece(relation, lieu_doc, item, item_id))["total"]
		lignes.append({
			"item_id": item_id,
			"nom": item.get("nom") or item_id,
			"icon": item.get("icon") or "🛠️",
			"poids": round(float(item.get("poids", 0) or 0), 2),
			"prix_cuivre": prix,
			"prix": cuivre_to_purse(prix),
			# ⚠️ Drapeau calculé ICI, jamais redérivé côté client (Convention §10) : une pièce
			# remise au catalogue par le tag `commandable` reste une MATIÈRE, et ne doit pas
			# afficher le bouton « ✨ Sur mesure ».
			"sur_mesure": not marche.est_intermediaire(item),
			**marche.fiche_item_fields(item),
		})
	return sorted(lignes, key=lambda l: l["nom"] or "")


def _matieres_vue(lieu_doc: dict, base_doc: dict) -> list:
	"""Ce que la maison accepte pour CETTE pièce : les items de son rayon qui entrent dans son
	tour de main, plus ceux que leur tag `fabrication_<famille de la pièce>` y destine. Le
	client n'a ainsi qu'à choisir dans une liste déjà filtrée, et rien ne dépend de sa bonne
	volonté — le serveur revérifie tout à `passer`.

	⚠️ La liste dépend de l'objet à façonner : elle ne peut pas être servie par le comptoir,
	qui ne sait pas encore ce que le joueur va commander."""
	lignes = []
	for entree in (lieu_doc.get("stock_vente") or []):
		item_id = entree.get("item_id")
		if not item_id or int(entree.get("qty", 0) or 0) <= 0:
			continue
		item = resolve_item_ref(item_id)
		if not item or not commande_util.matiere_acceptee(lieu_doc, item, base_doc):
			continue
		apporte = fabrication.proprietes_matiere(item)
		lignes.append({
			"item_id": item_id,
			"nom": item.get("nom") or item_id,
			"icon": item.get("icon") or "🧱",
			"qty": int(entree.get("qty", 0) or 0),
			"apporte": apporte["nom"],
			"modificateurs": apporte["modificateurs"],
		})
	return sorted(lignes, key=lambda l: l["nom"] or "")


# ── GET : l'état du comptoir de commande ────────────────────────────────────────

@commande_router.get("/commande")
def comptoir_commande(current_user: Annotated[dict, Depends(get_current_user)]):
	"""Ce que cet artisan sait faire, et où en sont les commandes du joueur.

	⚠️ `def` et non `async def` : lecture PURE (comme `marchand_quotes`), donc FastAPI la
	bascule sur le threadpool et la boucle d'événements n'est pas bloquée pendant les
	lectures. Les endpoints qui écrivent restent `async def`."""
	character, lieu_doc = _acces(current_user)
	relation = get_relation(character, lieu_doc)
	sur_mesure = commande_util.lieu_fabrique_sur_mesure(lieu_doc)
	return {
		"lieu_label": lieu_label(lieu_doc),
		"sur_mesure": sur_mesure,
		"catalogue": _catalogue_vue(lieu_doc, relation),
		# ⚠️ Pas de `matieres` ici : ce que la maison accepte dépend de la PIÈCE
		# (`fabrication_<categorie>`), que le comptoir ne connaît pas encore. L'overlay les
		# demande à l'ouverture (`/api/commande/matieres`).
		"matieres_max": int(character_stats.COMMANDE_MATIERES_MAX),
		"commandes": _vue_commandes(character, commande_util.now_epoch()),
		"purse": cuivre_to_purse(money_to_cuivre(character)),
		"delai": int(character_stats.COMMANDE_DELAI_SECONDES),
		"now": commande_util.now_epoch(),
	}


def _garde_sur_mesure(lieu_doc: dict, base_doc: dict) -> None:
	"""Les DEUX gardes du sur-mesure, ensemble parce qu'elles ne vont jamais l'une sans
	l'autre — et elles ne disent pas la même chose :

	- la MAISON sait-elle inventer ? (`lieu_fabrique_sur_mesure`, SEULE porte vers la création
	  d'un doc `item:`/`recette:`) ;
	- cet OBJET se façonne-t-il ? (`est_intermediaire`, garde INDÉPENDANTE portant sur l'objet)
	  — on ne façonne pas une hampe ou un lingot sur mesure, fût-ce au Grand Arsenal, et elle
	  tient même quand le tag `commandable` a remis la pièce au catalogue : le tag rouvre la
	  commande, jamais la personnalisation."""
	if not commande_util.lieu_fabrique_sur_mesure(lieu_doc):
		raise HTTPException(
			status_code=403,
			detail="Cet artisan ne travaille que sur ses propres modèles.")
	if marche.est_intermediaire(base_doc):
		raise HTTPException(
			status_code=422,
			detail="On ne façonne pas une matière première sur mesure.")


@commande_router.get("/commande/matieres")
def matieres_sur_mesure(
	current_user: Annotated[dict, Depends(get_current_user)],
	item_id: str = "",
):
	"""Les matières que cette maison accepte POUR CETTE PIÈCE — la liste du ✨ sur-mesure.

	⚠️ Servie ici et non par le comptoir : une matière entre dans la pièce soit parce que la
	maison la travaille, soit parce que son tag `fabrication_<famille>` l'y destine — et la
	famille, c'est celle de l'objet que le joueur vient de choisir. Le comptoir ne la connaît
	pas encore.

	`def` et non `async def` : lecture PURE, comme le comptoir."""
	_, lieu_doc = _acces(current_user)
	if not item_id or item_id not in commande_util.catalogue_commandable(lieu_doc, get_doc):
		raise HTTPException(status_code=422, detail="Cet artisan ne sait pas fabriquer cet objet.")
	base_doc = get_doc(item_id)
	if not base_doc:
		raise HTTPException(status_code=422, detail="Objet introuvable")
	_garde_sur_mesure(lieu_doc, base_doc)
	return {"item_id": item_id, "matieres": _matieres_vue(lieu_doc, base_doc)}


# ── Résolution commune devis / passer ───────────────────────────────────────────

def _resoudre(character: dict, lieu_doc: dict, relation, body: dict) -> dict:
	"""Tout ce qu'une commande demande de savoir, SANS rien écrire ni muter.

	Partagé par `devis` (qui s'arrête là) et `passer` (qui enchaîne sur la dépense) : les deux
	doivent voir exactement la même chose, sinon le prix affiché ne serait pas celui débité.
	Rend `{item_id, item_doc, base_doc, matieres_docs, besoins, source, detail, poids}`."""
	item_id = (body or {}).get("item_id")
	if not item_id:
		raise HTTPException(status_code=422, detail="Aucun objet demandé")
	if item_id not in commande_util.catalogue_commandable(lieu_doc, get_doc):
		raise HTTPException(status_code=422, detail="Cet artisan ne sait pas fabriquer cet objet.")

	base_doc = get_doc(item_id)
	if not base_doc:
		raise HTTPException(status_code=422, detail="Objet introuvable")

	matieres_demandees = fabrication.normaliser_matieres((body or {}).get("matieres"))
	if matieres_demandees:
		_garde_sur_mesure(lieu_doc, base_doc)
	if len(matieres_demandees) > int(character_stats.COMMANDE_MATIERES_MAX):
		raise HTTPException(
			status_code=422,
			detail="Pas plus de %d matières dans une même pièce."
				   % int(character_stats.COMMANDE_MATIERES_MAX))

	matieres_docs = []
	for entree in matieres_demandees:
		doc = get_doc(entree["item"])
		if not doc:
			raise HTTPException(status_code=422, detail="Matière introuvable")
		# ⚠️ La pièce est passée : une matière peut être admise par son tag
		# `fabrication_<famille de la pièce>` sans que la maison la travaille. Sans elle,
		# le serveur refuserait ce que l'overlay vient de proposer.
		if not commande_util.matiere_acceptee(lieu_doc, doc, base_doc):
			raise HTTPException(
				status_code=422,
				detail="%s n'entre pas dans le tour de main de cette maison."
					   % (doc.get("nom") or entree["item"]))
		matieres_docs.append((doc, entree["quantite"]))

	# ── DEUX passes, et elles ne se facturent pas pareil ────────────────────────────
	# Les ingrédients de la RECETTE sont déjà compris dans `prix_base` (le coût de revient se
	# propage par les recettes, × MARGE_TRANSFO) : les apporter vaut une REMISE, les laisser à
	# l'artisan ne coûte rien de plus. Les matières SUR MESURE ne sont dans le prix d'aucun
	# objet de base : elles se paient en supplément. Cf. `commande.devis`.
	#
	# ⚠️ Les deux passes PARTAGENT leurs emplacements retenus : sans quoi le même lingot
	# serait crédité comme ingrédient ET fourni gratuitement comme matière sur mesure.
	porteurs = [character] + recrutement.porteurs_effectifs(character, get_doc)
	retenus = set()

	recette = commande_util.recette_pour(lieu_doc, item_id)
	besoins_recette = list(marche.recette_matieres(recette)) if recette else []
	# `atelier=True` : ce que le joueur n'apporte pas, l'artisan le prend dans SA réserve puis
	# dans son rayon, sans rien facturer — c'est déjà payé par le prix de la pièce.
	src_recette = commande_util.sourcer(besoins_recette, porteurs, lieu_doc, get_doc,
										retenus=retenus, atelier=True)

	besoins_sur_mesure = [(e["item"], e["quantite"]) for e in matieres_demandees]
	src_sur_mesure = commande_util.sourcer(besoins_sur_mesure, porteurs, lieu_doc, get_doc,
										   _prix_achat(relation, lieu_doc), retenus)

	# Remise : ce que l'artisan n'aura pas à acheter parce que le client l'a apporté, au coût
	# de revient (pas au prix de vente — le joueur contribue, il ne revend pas).
	credit = sum(marche.cout_production_cuivre(f["item_id"]) for f in src_recette["fournies"])

	source = {
		"fournies": src_recette["fournies"] + src_sur_mesure["fournies"],
		"atelier": src_recette["atelier"],
		"achetees": src_sur_mesure["achetees"],
		"manquantes": src_recette["manquantes"] + src_sur_mesure["manquantes"],
		"cout_matieres": src_sur_mesure["cout_matieres"],
		"credit_matieres": credit,
	}

	prix_base = _prix_piece(relation, lieu_doc, base_doc, item_id)
	detail = commande_util.devis(prix_base, source["cout_matieres"], credit,
								 len(matieres_demandees))
	return {
		"item_id": item_id, "base_doc": base_doc, "matieres_docs": matieres_docs,
		"matieres": matieres_demandees, "source": source,
		"detail": detail, "porteurs": porteurs,
	}


@commande_router.post("/commande/devis")
def devis_commande(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Simulation sans engagement : le prix et l'état des matières, **sans rien écrire**.

	⚠️ Aucun doc `item:`/`recette:` n'est créé ici, même pour une variante inédite — c'est ce
	qui permet au client de rafraîchir le devis à chaque matière ajoutée sans laisser derrière
	lui une traînée de définitions que personne n'a commandées. La variante ne naît qu'au
	moment où le joueur paie."""
	character, lieu_doc = _acces(current_user)
	relation = _garde_relation(character, lieu_doc)
	resolu = _resoudre(character, lieu_doc, relation, body)
	source = resolu["source"]

	apercu = None
	if resolu["matieres_docs"]:
		# Construit EN MÉMOIRE pour montrer ce que la pièce vaudra : mêmes règles que le doc
		# qui sera écrit, mais rien n'est persisté.
		apercu = fabrication.variante_doc(resolu["base_doc"], resolu["matieres_docs"])
	return {
		"item_id": resolu["item_id"],
		"nom": (apercu or resolu["base_doc"]).get("nom"),
		"devis": resolu["detail"],
		"total": cuivre_to_purse(resolu["detail"]["total"]),
		"fournies": [{"cle": f["cle"], "item_id": f["item_id"]} for f in source["fournies"]],
		"atelier": source["atelier"],
		"achetees": source["achetees"],
		"manquantes": source["manquantes"],
		"apercu": apercu,
		"purse": cuivre_to_purse(money_to_cuivre(character)),
	}


# ── POST : passer la commande ───────────────────────────────────────────────────

@commande_router.post("/commande/passer")
async def passer_commande(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Engage la commande : crée la variante s'il y a lieu, prélève les matières, débite la
	bourse et inscrit la commande sur le personnage.

	⚠️ Prélèvement et inscription tiennent dans la MÊME mutation, donc le même `save_doc` :
	la double consommation des matières et la double fabrication sont impossibles par
	construction, sans transaction inter-documents (§8/§18 du cahier des charges).

	⚠️ Une matière introuvable ne fait pas échouer (§7 cas C) : la commande naît
	`en_attente_materiaux`, rien n'est prélevé et rien n'est débité."""
	character, lieu_doc = _acces(current_user)
	relation = _garde_relation(character, lieu_doc)
	resolu = _resoudre(character, lieu_doc, relation, body)
	source = resolu["source"]
	now = commande_util.now_epoch()

	commande_util.purger_commandes(character, now)

	# Cas C : on enregistre l'intention, on ne touche ni au sac ni à la bourse.
	if source["manquantes"]:
		enr = commande_util.nouvelle_commande(
			lieu_doc, resolu["item_id"], resolu["detail"], now=now,
			manquantes=source["manquantes"])
		character.setdefault("commandes", []).append(enr)
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		return _payload_commande(character, lieu_doc, relation, now,
								 message="Il manque de quoi la faire — l'artisan la garde en attente.")

	# La variante n'est créée QU'ICI, au moment où le joueur engage son argent.
	item_id, base_item = resolu["item_id"], ""
	item_doc = resolu["base_doc"]
	if resolu["matieres_docs"]:
		try:
			item_doc, _cree = fabrication.assurer_variante(
				resolu["base_doc"], resolu["matieres_docs"], lieu_doc, get_doc, save_doc,
				cout_base_cuivre=resolu["detail"]["prix_base"],
				cout_matieres_cuivre=resolu["detail"]["cout_matieres"], now=now)
		except ValueError as err:
			raise HTTPException(status_code=409, detail=str(err))
		item_id = item_doc["_id"]
		base_item = resolu["base_doc"]["_id"]
	poids = commande_util.poids_attendu(item_doc)

	purse = debit_character(character, resolu["detail"]["total"])
	if purse is None:
		raise HTTPException(status_code=422, detail="Fonds insuffisants")

	# ⚠️ Retrait en MÉMOIRE d'abord, sauvegarde ensuite (même séquence que le scriptorium) :
	# un échec de save laisse les sacs intacts en base.
	commande_util.retirer_fournitures(source["fournies"])
	commande_util.retirer_du_rayon(lieu_doc, source["achetees"])
	commande_util.consommer_atelier(lieu_doc, source["atelier"])

	enr = commande_util.nouvelle_commande(
		lieu_doc, item_id, resolu["detail"], now=now, base_item=base_item,
		matieres=resolu["matieres"],
		fournies=[{"cle": f["cle"], "item_id": f["item_id"]} for f in source["fournies"]],
		achetees=source["achetees"], poids=poids)
	character.setdefault("commandes", []).append(enr)

	mutes = {id(f["porteur"]): f["porteur"] for f in source["fournies"]}
	_save_porteurs(character, list(mutes.values()))
	save_doc(lieu_doc)   # best-effort : le rayon du lieu est une commodité monde

	return _payload_commande(character, lieu_doc, relation, now, purse=purse,
							 message="Commande passée : %s." % (item_doc.get("nom") or item_id))


# ── POST : relancer une commande en attente de matériaux ────────────────────────

@commande_router.post("/commande/relancer")
async def relancer_commande(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Reprend une commande restée `en_attente_materiaux` (§7 cas C) — le joueur est revenu
	avec ce qui manquait, ou l'artisan s'est réapprovisionné.

	⚠️ Tout est RE-RÉSOLU depuis zéro (même `_resoudre` que `passer`), jamais rejoué depuis le
	devis figé : les prix, les stocks et les sacs ont bougé depuis. Sans cela, une commande
	posée quand le lingot valait 400 serait honorée à ce prix un mois plus tard.

	⚠️ Rien n'a été prélevé ni débité à la création — il n'y a donc rien à rembourser si elle
	manque encore, et aucun risque de double consommation : l'entrée est REMPLACÉE, pas
	dupliquée."""
	character, lieu_doc = _acces(current_user)
	relation = _garde_relation(character, lieu_doc)
	now = commande_util.now_epoch()

	cmd = commande_util.trouver(character, (body or {}).get("commande_id"))
	if cmd is None:
		raise HTTPException(status_code=422, detail="Commande introuvable")
	if commande_util.statut(cmd, now) != commande_util.ETAT_ATTENTE_MATERIAUX:
		raise HTTPException(status_code=422, detail="Cette commande n'attend pas de matériaux.")
	if cmd.get("lieu") != lieu_doc.get("_id"):
		raise HTTPException(status_code=422, detail="Cette commande a été passée ailleurs.")

	resolu = _resoudre(character, lieu_doc, relation,
					   {"item_id": cmd.get("base_item") or cmd.get("item"),
						"matieres": cmd.get("matieres")})
	source = resolu["source"]
	if source["manquantes"]:
		cmd["manquantes"] = source["manquantes"]
		cmd["devis"] = resolu["detail"]
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		return _payload_commande(character, lieu_doc, relation, now,
								 message="Il manque toujours de quoi la faire.")

	item_id, base_item = resolu["item_id"], ""
	item_doc = resolu["base_doc"]
	if resolu["matieres_docs"]:
		try:
			item_doc, _cree = fabrication.assurer_variante(
				resolu["base_doc"], resolu["matieres_docs"], lieu_doc, get_doc, save_doc,
				cout_base_cuivre=resolu["detail"]["prix_base"],
				cout_matieres_cuivre=resolu["detail"]["cout_matieres"], now=now)
		except ValueError as err:
			raise HTTPException(status_code=409, detail=str(err))
		item_id = item_doc["_id"]
		base_item = resolu["base_doc"]["_id"]

	purse = debit_character(character, resolu["detail"]["total"])
	if purse is None:
		raise HTTPException(status_code=422, detail="Fonds insuffisants")

	commande_util.retirer_fournitures(source["fournies"])
	commande_util.retirer_du_rayon(lieu_doc, source["achetees"])
	commande_util.consommer_atelier(lieu_doc, source["atelier"])

	# L'entrée est REMPLACÉE à la même place : le délai de fabrication court à partir de
	# maintenant, puisque c'est maintenant que l'artisan s'y met.
	neuve = commande_util.nouvelle_commande(
		lieu_doc, item_id, resolu["detail"], now=now, base_item=base_item,
		matieres=resolu["matieres"],
		fournies=[{"cle": f["cle"], "item_id": f["item_id"]} for f in source["fournies"]],
		achetees=source["achetees"],
		poids=commande_util.poids_attendu(item_doc))
	neuve["id"] = cmd["id"]
	neuve["cree_at"] = int(cmd.get("cree_at", now) or now)
	character["commandes"] = [neuve if c is cmd else c for c in character.get("commandes", [])]

	mutes = {id(f["porteur"]): f["porteur"] for f in source["fournies"]}
	_save_porteurs(character, list(mutes.values()))
	save_doc(lieu_doc)

	return _payload_commande(character, lieu_doc, relation, now, purse=purse,
							 message="L'artisan s'y met : %s." % (item_doc.get("nom") or item_id))


# ── POST : retirer ──────────────────────────────────────────────────────────────

@commande_router.post("/commande/retirer")
async def retirer_commande(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Retire une pièce terminée. L'exemplaire est une RÉFÉRENCE d'inventaire enrichie
	(`fabrique_par`, `commande_at`), jamais un document : `resolve_item_ref` sait déjà
	l'afficher, et tout le jeu (sac, sol, combat, marché) le voit sans rien changer."""
	character, lieu_doc = _acces(current_user)
	now = commande_util.now_epoch()

	cmd = commande_util.trouver(character, (body or {}).get("commande_id"))
	if cmd is None:
		raise HTTPException(status_code=422, detail="Commande introuvable")
	etat = commande_util.statut(cmd, now)
	if etat == commande_util.ETAT_EXPIREE:
		raise HTTPException(status_code=422, detail="Trop tard : l'artisan a écoulé la pièce.")
	if not commande_util.retirable(cmd, lieu_doc.get("_id"), now):
		raise HTTPException(status_code=422, detail="Cette commande n'est pas prête ici.")

	item = resolve_item_ref(cmd.get("item"))
	if not item:
		# La définition a disparu sous la commande : on rembourse plutôt que de livrer du vide.
		commande_util.marquer(cmd, commande_util.ETAT_IMPOSSIBLE)
		purse = credit_character(character, int(cmd.get("paye", 0) or 0))
		# ⚠️ Purger AVANT le save : après, la liste nettoyée ne serait qu'en mémoire et la
		# commande soldée reviendrait au prochain chargement.
		commande_util.purger_commandes(character, now)
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		relation = get_relation(character, lieu_doc)
		return _payload_commande(character, lieu_doc, relation, now, purse=purse,
								 message="L'artisan ne retrouve pas votre pièce — vous êtes remboursé.")

	ref = commande_util.ref_livree(cmd)
	poids = float(ref.get("poids") or item.get("poids", 0) or 0)
	if carried_weight(character) + poids > charge_max_of(character):
		raise HTTPException(status_code=422, detail="Trop chargé pour emporter cette pièce.")

	# ⚠️ Marquage et ajout dans la MÊME mutation : c'est ce qui rend le double retrait
	# impossible, sans verrou ni transaction.
	character.setdefault("inventaire", []).append(ref)
	commande_util.marquer(cmd, commande_util.ETAT_LIVREE)
	# ⚠️ Purger AVANT le save, pas après : une purge postérieure ne vivrait qu'en mémoire et
	# la commande livrée reviendrait au prochain chargement — un second retrait la trouverait
	# encore. C'est le marquage qui interdit le double retrait, mais la liste doit suivre.
	commande_util.purger_commandes(character, now)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	relation = get_relation(character, lieu_doc)
	payload = _payload_commande(character, lieu_doc, relation, now,
								message="Retiré : %s." % (item.get("nom") or cmd.get("item")))
	payload["retire"] = resolve_item_ref(ref)
	return payload


# ── POST : annuler / oublier ────────────────────────────────────────────────────

@commande_router.post("/commande/annuler")
async def annuler_commande(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...),
):
	"""Annule une commande, ou écarte une commande perdue.

	- **en attente de matériaux** : rien n'a été prélevé ni débité, l'entrée disparaît ;
	- **en fabrication ou prête** : la pièce est entamée — les matières et le prix sont
	  perdus. C'est la contrepartie du délai, et le client l'annonce avant de confirmer ;
	- **expirée** : il n'y a plus rien à perdre, l'entrée est simplement écartée."""
	character, lieu_doc = _acces(current_user)
	now = commande_util.now_epoch()

	cmd = commande_util.trouver(character, (body or {}).get("commande_id"))
	if cmd is None:
		raise HTTPException(status_code=422, detail="Commande introuvable")

	commande_util.marquer(cmd, commande_util.ETAT_ANNULEE)
	commande_util.purger_commandes(character, now)
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")

	relation = get_relation(character, lieu_doc)
	return _payload_commande(character, lieu_doc, relation, now, message="Commande annulée.")


# ── Payload de resynchronisation (CLAUDE.md §10) ────────────────────────────────

def _payload_commande(character: dict, lieu_doc: dict, relation, now: int,
					  purse=None, message: str = "") -> dict:
	"""Les blocs recalculés que le client ne doit JAMAIS reconstruire lui-même.

	Le rayon du lieu peut avoir bougé (matières achetées pour la commande) : `achetables` et
	`vendables` repartent donc avec, sans quoi le panneau du marchand resterait figé sur son
	dernier chargement — un symptôme difficile à relier à sa cause."""
	payload = {
		"commandes": _vue_commandes(character, now),
		"catalogue": _catalogue_vue(lieu_doc, relation),
		"matieres": (_matieres_vue(lieu_doc)
					 if commande_util.lieu_fabrique_sur_mesure(lieu_doc) else []),
		"inventaire_payload": _inventory_payload(character),
		"achetables": resolve_stock_vente(lieu_doc, relation),
		"vendables": _marchand_vendables(character, lieu_doc, relation,
										 recrutement.porteurs_effectifs(character, get_doc)),
		"purse": purse if purse is not None else cuivre_to_purse(money_to_cuivre(character)),
		"now": now,
	}
	if message:
		payload["message"] = message
	return payload
