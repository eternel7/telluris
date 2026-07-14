# routers/pnj.py
# Endpoints des PNJ de lieu (dialogues à choix + services) et de l'intro narrative.
# La logique est pure dans utils/pnj.py (et utils/intro.py) ; ici on gère l'interaction :
# résoudre le PNJ présent, naviguer l'arbre, exécuter le service de soin (débit + PV),
# choisir la raison de la fuite. Pattern calqué sur routers/user.py :
# get_selected_character → muter → save_doc is None ⇒ 409.

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body

from db.config import get_doc, save_doc, find_docs
from utils.auth import get_current_user
from utils.characters import (
	get_selected_character, sync_equipment_bonus,
	money_to_cuivre, cuivre_to_purse,
	poids_bounds, carried_weight, charge_max_of, item_ref_id, resolve_item_ref,
)
from utils.marche import (
	debit_character, get_relation, relation_value, relations_lieux_payload,
)
from utils import pnj
from utils import intro
from utils import transport
from utils import quetes
from utils import focalisation
from routers.user import _derived_from_character, _vitals_payload, _inventory_payload

pnj_router = APIRouter()


def _pnj_du_lieu(character: dict) -> tuple[dict, dict, dict]:
	"""(entrée pnj du lieu, doc PNJ, doc lieu) du PNJ présent au lieu courant ; 404 sinon.
	`entree_marchand` fournit le tenancier implicite des magasins (aucun doc `lieu:*`
	marchand ne porte de champ `pnj`)."""
	lieu_doc = get_doc(character.get("lieu", ""))
	entree = pnj.entree_pnj_active(character, lieu_doc or {}, transport.entree_marchand)
	pnj_doc = get_doc(entree["character"]) if entree else None
	if not entree or not pnj_doc:
		raise HTTPException(status_code=404, detail="Personne à qui parler ici.")
	return entree, pnj_doc, lieu_doc


def _contexte(character: dict, pnj_doc: dict, lieu_doc: dict | None = None,
			  entree: dict | None = None) -> dict:
	"""Contexte de dialogue avec la résolution de relation fermée sur la DB (le lieu peut
	ne pas exister → relation neutre sur doc minimal, get_relation ne sauvegarde pas).

	`{pnj}` (le nom sous lequel CE lieu présente son PNJ) est posé pour TOUT dialogue, course
	ou pas : un doc `pnj:marchand_*` est générique, seul le lieu sait comment s'appelle son
	tenancier — un dialogue ne peut donc pas écrire de nom en dur.

	Y ajoute l'état des quêtes de transport du lieu courant : les FLAGS qui rendent
	visibles les choix « une course pour moi ? » / « je vous apporte une livraison », et
	les PLACEHOLDERS d'orientation ({destination}, {direction}, {repere}…) que le donneur
	récite quand on l'interroge sur la destination.

	`transport_en_cours` (course confiée par CE lieu, pas encore livrée) laisse le donneur
	relancer le joueur ; `transport_accompli` (course ÉCRITE `unique` déjà réussie) lui laisse
	saluer un joueur qui a fait ses preuves plutôt que reproposer une mission accomplie."""
	def _rel(lieu_id: str) -> int:
		lieu = get_doc(lieu_id) or {"_id": lieu_id}
		return relation_value(get_relation(character, lieu))

	flags: dict = {}
	placeholders: dict = {"pnj": pnj.nom_effectif(entree or {}, pnj_doc)}
	if lieu_doc:
		offre = transport.offre_courante(character, lieu_doc)
		a_livrer = transport.transport_a_livrer(character, lieu_doc.get("_id"))
		en_cours = transport.course_du_donneur(character, lieu_doc.get("_id"))
		a_rapporter = transport.retour_attendu(character, lieu_doc.get("_id"))
		spec = transport.offre_spec(pnj_doc)
		flags = {
			"transport_offert": bool(offre),
			"transport_a_livrer": bool(a_livrer),
			# Course livrée dont il reste à rendre compte ici (courses `retour`) : c'est le donneur
			# qui solde. `transport_en_cours` (relance) l'exclut — la marchandise est déjà remise.
			"transport_a_rapporter": bool(a_rapporter),
			"transport_en_cours": bool(en_cours and not en_cours.get("livree_at")),
			"transport_accompli": bool(spec and transport.deja_reussie(character, spec.get("id"))),
			# Le tenancier ne confie rien à un joueur mal vu — ni à celui avec qui il vient de se
			# fâcher (marchandage bloqué) : le choix « une course pour moi ? » devient un REFUS
			# parlé, au lieu de disparaître (silence indiscernable d'un tirage négatif — la
			# sanction serait invisible).
			"transport_mefiance": transport.mefiance(character, lieu_doc, pnj_doc, get_doc,
													 quetes.now_epoch()),
		}
		# Une course déjà confiée se raconte avec les mêmes mots qu'une offre (le snapshot a la
		# même forme) : le donneur peut rappeler la destination et le temps qu'il reste.
		if offre or en_cours:
			placeholders.update(_placeholders_offre(offre or en_cours, lieu_doc))
		elif spec:
			# Une course ÉCRITE se raconte même quand elle n'est plus vivante : le nœud « vétéran »
			# ne s'affiche QU'APRÈS la réussite (l'offre a disparu, la quête est archivée) et doit
			# pouvoir nommer qui a reçu la marchandise. Rien n'est tiré au sort dans une course
			# écrite → la reconstruire donne exactement ce que le PNJ avait proposé.
			apercu = transport.generer_transport_authore(spec, lieu_doc, find_docs, get_doc)
			if apercu:
				placeholders.update(_placeholders_offre(apercu, lieu_doc))
	return pnj.contexte_dialogue(character, pnj_doc, _rel, flags, placeholders)


def _nom_pnj(lieu_id: str | None) -> str | None:
	"""Nom du PNJ qui tient ce lieu (le tenancier implicite d'un magasin y compris), sans y
	être : c'est ainsi que le donneur peut nommer la personne à qui livrer, et le destinataire
	celle qui l'envoie. None si le lieu n'existe pas ou n'a personne."""
	lieu = get_doc(lieu_id) if lieu_id else None
	if not lieu:
		return None
	return pnj.nom_pnj_du_lieu(lieu, get_doc, transport.entree_marchand)


def _placeholders_offre(offre: dict, lieu_doc: dict) -> dict:
	"""Valeurs récitées par le donneur pour décrire la course. Fonctionne aussi bien sur une
	offre (pas encore acceptée : `duree`) que sur le snapshot d'une course active (`expire_at`)
	— {delai} = les minutes qu'il RESTE dans ce dernier cas."""
	dest_id = (offre.get("objectif") or {}).get("cible")
	indice = transport.indice_destination(lieu_doc, dest_id, find_docs, get_doc)
	rec = offre.get("recompenses") or {}
	cargaison = offre.get("cargaison") or []
	if offre.get("expire_at"):
		restant = int(offre["expire_at"]) - quetes.now_epoch()
	else:
		restant = int(offre.get("duree", 3600))
	# Un marchand dit « dix kilos », pas « 10.0 kilos » : on ne garde la décimale que si elle
	# porte une information (cargaison aux poids tirés au hasard).
	poids = transport.poids_cargaison(cargaison)
	return {
		"destination": indice["nom"],
		# Le lieu où livrer ({destination}) et la personne à qui livrer ({destinataire}) sont deux
		# choses : « Présente le jeton à Hermine Valcorbe » vs « Destination : Fumée de l'Yonne ».
		"destinataire": _nom_pnj(dest_id) or indice["nom"],
		"direction": transport.texte_indice(indice),
		"repere": indice.get("repere") or indice["nom"],
		"colis": len(cargaison),
		"poids": int(poids) if float(poids).is_integer() else poids,
		"delai": max(1, restant // 60),
		"xp": rec.get("xp", 0),
		"prime": rec.get("cuivre", 0),
	}


@pnj_router.get("/pnj/dialogue")
async def pnj_dialogue(current_user: Annotated[dict, Depends(get_current_user)]):
	"""État initial du panneau de dialogue : PNJ présent + nœud de départ (choix filtrés)."""
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")

	entree, pnj_doc, lieu_doc = _pnj_du_lieu(character)
	# Une course dont le délai vient d'expirer ne doit pas être livrable : on solde les
	# échéances (et leur sanction de réputation) avant de composer le dialogue.
	echues = transport.traiter_expirations(character, quetes.now_epoch(), get_doc, save_doc)
	if echues:
		save_doc(character)
	contexte = _contexte(character, pnj_doc, lieu_doc, entree)
	depart = (pnj_doc.get("dialogue") or {}).get("noeud_depart", "accueil")
	return {
		"pnj": pnj.pnj_payload(entree, pnj_doc),
		"noeud": pnj.noeud_client(pnj_doc, depart, contexte, pnj.soin_effectif(pnj_doc, contexte)),
		# Une course a pu périmer en ouvrant le dialogue : la sanction de réputation est déjà
		# appliquée en base, l'onglet 🤝 (rendu client) doit la voir.
		"relations_lieux": relations_lieux_payload(character) if echues else None,
	}


@pnj_router.post("/pnj/dialogue/choix")
async def pnj_dialogue_choix(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...)):
	"""Résout un choix de dialogue (stateless, revalidé serveur). Body {"noeud", "choix_id"}.
	Un choix à action `{"service":"soin"}` débite et soigne ; `{"service":"don"}` remet un
	objet (contrôle de charge + débit, séquence modèle buy_item) ; un choix simple renvoie
	le nœud suivant, `noeud: null` = fin (le client ferme)."""
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")

	entree, pnj_doc, lieu_doc = _pnj_du_lieu(character)
	echues = transport.traiter_expirations(character, quetes.now_epoch(), get_doc, save_doc)
	if echues:
		save_doc(character)
	contexte = _contexte(character, pnj_doc, lieu_doc, entree)
	noeud_id = body.get("noeud")
	choix = pnj.choix_valide(pnj_doc, noeud_id, body.get("choix_id"), contexte)
	if not choix:
		raise HTTPException(status_code=422, detail="Choix de dialogue invalide.")

	soin = pnj.soin_effectif(pnj_doc, contexte)
	reponse: dict = {}
	if echues:
		# Sanction d'une course périmée en cours de dialogue. Un service `transport` qui solde
		# ensuite une livraison réécrira ce champ avec un payload encore plus frais.
		reponse["relations_lieux"] = relations_lieux_payload(character)

	action = choix.get("action") or {}
	if action.get("service") == "soin":
		if not soin:
			raise HTTPException(status_code=422, detail="Ce personnage ne soigne pas.")
		noeuds_soin = (pnj_doc.get("services", {}).get("soin", {}).get("noeuds", {}))
		eq = sync_equipment_bonus(character)
		derived = _derived_from_character(character, eq)
		if int(character.get("currentPV", derived.pv_max)) >= derived.pv_max:
			# PV pleins : rien débité, le PNJ le fait remarquer.
			suivant = noeuds_soin.get("inutile")
		elif soin["cout_cuivre"] > 0 and debit_character(character, soin["cout_cuivre"]) is None:
			# Bourse vide : rien débité (debit_character n'a pas mutés les fonds), rien sauvé.
			suivant = noeuds_soin.get("sans_fonds")
		else:
			pv_rendu = pnj.appliquer_soin(character, derived.pv_max, soin["fraction_pv"])
			if save_doc(character) is None:
				raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
			suivant = noeuds_soin.get("fait")
			reponse["soin"] = {
				"pv_rendu": pv_rendu,
				"gratuit": soin["gratuit"],
				"cout": soin["cout_cuivre"],
			}
		reponse["vitals"] = _vitals_payload(character)
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
	elif action.get("service") == "don":
		don = pnj.don_effectif(pnj_doc, contexte)
		if not don:
			raise HTTPException(status_code=422, detail="Ce personnage n'a rien à donner.")
		item_doc = get_doc(don["item"])
		if not item_doc:
			raise HTTPException(status_code=422, detail="Objet du don introuvable.")
		noeuds_don = (pnj_doc.get("services", {}).get("don", {}).get("noeuds", {}))
		poids_unitaire = poids_bounds(item_doc)[0]
		poids_total = poids_unitaire * don["quantite"]
		if carried_weight(character) + poids_total > charge_max_of(character):
			# Surcharge : rien donné, rien débité, le PNJ le fait remarquer.
			suivant = noeuds_don.get("trop_charge")
		elif don["cout_cuivre"] > 0 and debit_character(character, don["cout_cuivre"]) is None:
			# Bourse vide : rien débité (fonds non mutés), rien donné.
			suivant = noeuds_don.get("sans_fonds")
		else:
			pnj.appliquer_don(character, don["item"], poids_unitaire, don["quantite"])
			if save_doc(character) is None:
				raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
			suivant = noeuds_don.get("fait")
			reponse["don"] = {
				"item": don["item"],
				"nom": item_doc.get("nom"),
				"icon": item_doc.get("icon"),
				"quantite": don["quantite"],
				"gratuit": don["gratuit"],
				"cout": don["cout_cuivre"],
			}
			reponse["inventaire_payload"] = _inventory_payload(character)
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
	elif action.get("service") == "transport":
		suivant, dits = _resoudre_transport(character, pnj_doc, lieu_doc, action.get("op"), reponse)
		# Le contexte a changé (course acceptée/livrée) → refiltrer les choix du nœud suivant
		# sur les nouveaux FLAGS, sinon le marchand reproposerait la course qu'il vient de
		# confier. Les PLACEHOLDERS, eux, viennent de l'action : l'offre n'existe plus une fois
		# acceptée, mais le nœud de résultat doit encore pouvoir citer le délai et la destination.
		contexte = _contexte(character, pnj_doc, lieu_doc, entree)
		contexte["placeholders"].update(dits)
	else:
		suivant = choix.get("next")

	if not suivant or suivant == "fin":
		reponse["noeud"] = None
	else:
		reponse["noeud"] = pnj.noeud_client(pnj_doc, suivant, contexte, soin)
	return reponse


def _resoudre_transport(character: dict, pnj_doc: dict, lieu_doc: dict, op: str,
						reponse: dict) -> tuple[str | None, dict]:
	"""Exécute une action du service `transport` : renvoie (nœud de résultat, placeholders
	que ce nœud peut citer).

	`accepter` : le donneur remet la cargaison (refus si le sac ne suit pas).
	`livrer`   : le destinataire prend livraison — refus si le joueur ne porte plus tout. Il
	             paie et fait remonter sa recommandation chez le donneur (+1 relation), SAUF
	             pour une course `retour` : il ne fait alors que prendre la marchandise.
	`rapporter`: le donneur d'une course `retour` solde lui-même (XP, prime, items — la carte
	             d'aventurier) une fois la livraison faite.
	Les autres opérations (proposer/informer) sont de simples `next` conditionnés côté
	donnée : elles n'arrivent jamais ici."""
	noeuds = ((pnj_doc.get("services") or {}).get("transport") or {}).get("noeuds") or {}

	if op == "accepter":
		offre = transport.offre_courante(character, lieu_doc)
		if not offre:
			raise HTTPException(status_code=422, detail="Aucune course à prendre ici.")
		# Calculés AVANT la mutation : l'offre disparaît du lieu une fois acceptée, mais le
		# nœud « voilà la marchandise » doit encore pouvoir citer le délai et la destination.
		dits = _placeholders_offre(offre, lieu_doc)
		poids = transport.poids_cargaison(offre.get("cargaison") or [])
		if carried_weight(character) + poids > charge_max_of(character):
			# Surcharge : rien remis, l'offre reste sur la table.
			return noeuds.get("trop_charge"), dits
		q = transport.accepter_transport(character, offre)
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		reponse["transport"] = {"accepte": q.get("titre"), "expire_at": q.get("expire_at")}
		reponse["inventaire_payload"] = _inventory_payload(character)
		reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
		return noeuds.get("accepte"), dits

	if op == "livrer":
		q = transport.transport_a_livrer(character, lieu_doc.get("_id"))
		if not q:
			raise HTTPException(status_code=422, detail="Aucune livraison attendue ici.")
		giver_doc = get_doc(q.get("giver")) if q.get("giver") else None
		rec = q.get("recompenses") or {}
		expediteur = (giver_doc or {}).get("label") or (giver_doc or {}).get("nom") or "l'expéditeur"
		dits = {
			"destination": lieu_doc.get("label") or lieu_doc.get("nom") or "",
			# {expediteur} = l'enseigne d'où part la marchandise ; {donneur} = qui l'a confiée.
			"expediteur": expediteur,
			"donneur": _nom_pnj(q.get("giver")) or expediteur,
			"colis": len(q.get("cargaison") or []),
			"xp": rec.get("xp", 0),
			"prime": rec.get("cuivre", 0),
		}
		if not transport.livrer_transport(character, q):
			# Cargaison incomplète (vendue, jetée) : la quête reste active, le délai court.
			return noeuds.get("incomplet"), dits
		if q.get("retour"):
			# Course à retour : le destinataire prend la marchandise mais ne paie pas — tout se
			# solde chez le donneur, à qui il faut aller rendre compte.
			recap = transport.livrer_en_attente_de_retour(character, q, lieu_doc, get_doc, save_doc)
			if save_doc(character) is None:
				raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
			reponse["transport"] = {"remis": q.get("titre"), "en_rayon": sum(recap["rayon"].values())}
			reponse["inventaire_payload"] = _inventory_payload(character)
			reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
			# Le nœud de reçu, à défaut celui de livraison (les tenanciers génériques n'en ont
			# qu'un : la plupart des courses se paient sur place).
			return noeuds.get("livre_retour") or noeuds.get("livre"), dits
		# Le doc `relation` est annexe (hors character) : reussir_transport le persiste, le
		# character est sauvé juste après — un conflit sur la relation n'annule pas la livraison.
		recap = transport.reussir_transport(character, q, lieu_doc, get_doc, save_doc)
		focalisation.effacer_si_quete(character, q.get("id"))
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		reponse["transport"] = {
			"livre": q.get("titre"),
			"xp": recap["xp"].get("xp_gain", 0),
			"niveau_up": recap["xp"].get("niveau_up", False),
			"relation": recap["relation"],
			# Nombre de colis effectivement montés en rayon (le reste part en arrière-boutique).
			"en_rayon": sum(recap["rayon"].values()),
		}
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
		reponse["vitals"] = _vitals_payload(character)
		reponse["inventaire_payload"] = _inventory_payload(character)
		reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
		reponse["focalisation"] = focalisation.payload_client(character, get_doc)
		# Le doc `relation` du donneur vient de monter : l'onglet 🤝 est rendu 100 % client, il
		# faut lui renvoyer le payload complet (comme le fait /api/marchander), sinon il resterait
		# sur celui injecté au chargement de /play.
		reponse["relations_lieux"] = relations_lieux_payload(character)
		return noeuds.get("livre"), dits

	if op == "rapporter":
		q = transport.retour_attendu(character, lieu_doc.get("_id"))
		if not q:
			raise HTTPException(status_code=422, detail="Aucune course à rapporter ici.")
		rec = q.get("recompenses") or {}
		dest_id = (q.get("objectif") or {}).get("cible")
		dest_doc = get_doc(dest_id) if dest_id else None
		dits = {
			# Le donneur peut citer celle qui a pris livraison (« {destinataire} a sa viande »).
			"destination": (dest_doc or {}).get("label") or (dest_doc or {}).get("nom") or "",
			"destinataire": _nom_pnj(dest_id) or (dest_doc or {}).get("label") or "",
			"colis": len(q.get("cargaison") or []),
			"xp": rec.get("xp", 0),
			"prime": rec.get("cuivre", 0),
		}
		recap = transport.rapporter_transport(character, q, get_doc, save_doc)
		focalisation.effacer_si_quete(character, q.get("id"))
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		# Les items de récompense (la carte d'aventurier) sont entrés au sac avec la prime.
		# `resolve_item_ref` — pas `get_doc` — pour que le toast porte le nom de l'INSTANCE :
		# « Carte d'aventurier (Auxerre) », pas le nom nu du doc générique.
		reponse["transport"] = {
			"livre": q.get("titre"),
			"xp": recap["xp"].get("xp_gain", 0),
			"niveau_up": recap["xp"].get("niveau_up", False),
			"relation": recap["relation"],
			"items": [
				(resolve_item_ref(ref) or {}).get("nom") or item_ref_id(ref)
				for ref in (rec.get("items") or [])
			],
		}
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
		reponse["vitals"] = _vitals_payload(character)
		reponse["inventaire_payload"] = _inventory_payload(character)
		reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
		reponse["focalisation"] = focalisation.payload_client(character, get_doc)
		reponse["relations_lieux"] = relations_lieux_payload(character)
		return noeuds.get("rapporte"), dits

	raise HTTPException(status_code=422, detail="Action de transport inconnue.")


@pnj_router.post("/intro/raison")
async def intro_raison(
	current_user: Annotated[dict, Depends(get_current_user)],
	body: dict = Body(...)):
	"""Persiste la raison de la fuite choisie dans l'overlay d'intro. Body {"raison": id}.
	Renvoie le texte de suite propre à la raison (affiché avant « Prendre la route »)."""
	if not current_user:
		raise HTTPException(status_code=400, detail="Invalid session credentials")
	character = get_selected_character(current_user)
	if not character:
		raise HTTPException(status_code=406, detail="Aucun personnage sélectionné")

	if not intro.intro_en_cours(character):
		raise HTTPException(status_code=409, detail="Aucune introduction en cours.")
	lieu_doc = get_doc(character.get("cite", "")) or {}
	raison = intro.raison_valide(lieu_doc, body.get("raison"))
	if not raison:
		raise HTTPException(status_code=422, detail="Raison inconnue.")

	character["intro"]["raison"] = raison["id"]
	if save_doc(character) is None:
		raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
	return {"raison": raison["id"], "texte_suite": raison.get("texte_suite", "")}
