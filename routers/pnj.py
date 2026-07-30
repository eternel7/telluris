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
from utils import chasse
from utils import quetes
from utils import focalisation
from utils import acces
from utils import donjon
from utils import recrutement
from utils import montures
from utils.combat import (
	instantiate_monsters, build_monster_snapshot, create_combat_doc,
	resolve_first_turns, finalize_combat,
)
from utils.lieux import get_lieu_links
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
		# Épreuves de RANG de guilde (comptoir seulement) : flags qui montrent les choix
		# « une épreuve pour moi ? » / « c'est fait » et placeholders ({espece}/{lieu}/{rang}/
		# {rang_vise}) que le maître d'armes récite. Le rang est propre à la CITÉ (lieu_parent).
		# ⚠️ `rang_max` = « CE COMPTOIR a atteint son plafond » (`rang_max` de son doc lieu, défaut
		# `RANG_GUILDE_MAX_DEFAUT`), et NON « sommet de l'échelle » : une guilde s'arrête à ce que
		# son bestiaire justifie, et son nœud dit bien « ce que cette guilde peut t'offrir ».
		if chasse.est_comptoir(lieu_doc):
			cite = lieu_doc.get("lieu_parent")
			rang_courant = chasse.rang_de(character, cite)
			offre_rang = chasse.offre_rang_courante(character, lieu_doc)
			a_rapporter = chasse.rang_a_rapporter(character, cite)
			flags["rang_offert"] = bool(offre_rang)
			flags["rang_a_rapporter"] = bool(a_rapporter)
			flags["rang_max"] = chasse.rang_plafond_atteint(rang_courant, lieu_doc)
			placeholders["rang"] = rang_courant
			if offre_rang or a_rapporter:
				placeholders.update(_placeholders_rang(offre_rang or a_rapporter, rang_courant))
		# Commissions d'éradication (maître de guilde) : `services.commission.donjon` est le
		# SEUL lien PNJ → donjon. L'offre est REBÂTIE à chaque affichage (pas de champ
		# transitoire `*_offert`, cf. `donjon.offre_commission_pour`) → les placeholders
		# {espece}/{lieu}/{xp} viennent de l'offre courante, ou de la commission en cours
		# quand il n'y a plus rien à proposer (c'est elle que le PNJ relance ou solde).
		commission_conf = (pnj_doc.get("services") or {}).get("commission") or {}
		donjon_doc = get_doc(commission_conf["donjon"]) if commission_conf.get("donjon") else None
		if donjon_doc:
			en_cours = donjon.commission_active(character)
			a_solder = donjon.commission_a_rapporter(character)
			offre_com = donjon.offre_commission_pour(
				character, lieu_doc, donjon_doc, get_doc, find_docs)
			flags["commission_offerte"] = bool(offre_com)
			flags["commission_a_rapporter"] = bool(a_solder)
			# « en cours » exclut « à rapporter » : l'élite abattue, ce n'est plus une relance
			# qu'il faut proposer mais un rapport à rendre (miroir de `transport_en_cours`).
			flags["commission_en_cours"] = bool(en_cours and not a_solder)
			if offre_com or en_cours:
				placeholders.update(_placeholders_commission(offre_com or en_cours))
		# Accès conditionné à un lieu (PNJ gardien) : `services.acces.lieu` est le SEUL
		# lien PNJ → lieu gardé (aucun find_docs, aucun id en dur ici). `{portail}` = le
		# label du lieu gardé, pour que George puisse le nommer sans le citer en dur.
		acces_conf = (pnj_doc.get("services") or {}).get("acces") or {}
		lieu_garde = get_doc(acces_conf["lieu"]) if acces_conf.get("lieu") else None
		if lieu_garde:
			deja = acces.laissez_passer_valide(character, lieu_garde)
			ok, _raison = acces.acces_autorise(character, lieu_garde, get_doc)
			# Mission REMPLIE mais pas encore rapportée : la barrière vient de se refermer
			# (`objectif_atteint: false` côté condition), et le gardien doit pouvoir le dire
			# AUTREMENT qu'en récitant son refus générique — le joueur a fait le travail, lui
			# répondre « pas de commission, pas de descente » serait absurde.
			q_finie = donjon.commission_active_pour_lieu(character, lieu_garde["_id"])
			accompli = bool(q_finie and quetes.objectif_atteint(character, q_finie))
			flags["acces_ouvrable"] = ok and not deja
			flags["acces_accompli"] = accompli
			# ⚠️ `acces_refuse` EXCLUT le cas accompli, sinon les deux choix s'afficheraient
			# ensemble (le refus ET les félicitations).
			flags["acces_refuse"] = not ok and not accompli
			flags["acces_ouvert"] = deja
			# La menace derrière la porte est-elle éliminée ? Reste vrai APRÈS le rapport,
			# contrairement à `acces_accompli` — c'est l'état du LIEU, pas celui de la quête :
			# le gardien peut ainsi parler du monde qui a changé (les mineurs descendent
			# enfin) même une fois la commission archivée.
			# ⚠️ DEUX flags complémentaires, et non un seul : `condition_ok` n'a pas de
			# négation (une condition doit être VRAIE pour afficher son choix), donc « la
			# menace court toujours » a besoin de son propre flag pour porter la variante
			# inverse du même dialogue.
			libere = donjon.donjon_purge(character, lieu_garde["_id"])
			flags["acces_libere"] = libere
			flags["acces_menace"] = not libere
			placeholders["portail"] = lieu_garde.get("label") or lieu_garde.get("nom") or ""
	return pnj.contexte_dialogue(character, pnj_doc, _rel, flags, placeholders)


def _lien_vers(current_user: dict, lieu_courant: str, destination: str) -> str | None:
	"""`_id` du doc `connection` reliant le lieu COURANT à `destination`, ou None s'il n'y en a
	pas — c'est ce que le hook `deplacer` d'un choix de dialogue rend au client.

	⚠️ On ne déplace PAS le personnage ici. Le client rappelle `moveTo(link_id)`, donc l'unique
	endpoint de déplacement (`/api/move_character`), qui porte une quinzaine d'effets de bord
	(quêtes `visite`, focalisation, XP de découverte, sol transitoire, événement de zone,
	conclusion d'intro, courses échues, régén de tour…). Les recopier ici garantirait la
	divergence ; et la garde 403 de `move_character` reste la seule autorité sur le passage —
	un `deplacer` mal placé dans un dialogue ne peut donc pas forcer une porte fermée.

	`filtrer_acces=False` : la barrière est revérifiée par le déplaceur, et au moment où l'on
	résout ce lien le laissez-passer vient peut-être tout juste d'être posé."""
	if not destination or destination == lieu_courant:
		return None
	for link in (get_lieu_links(current_user, filtrer_acces=False) or []):
		if any(n.get("lieu") == destination for n in link.get("nodes", [])):
			return link.get("_id")
	return None


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
	elif action.get("service") == "rang":
		suivant, dits = _resoudre_rang(character, pnj_doc, lieu_doc, action.get("op"), reponse)
		# Même raison que le transport : le contexte a changé (épreuve prise / soldée) → on
		# refiltre les choix sur les nouveaux flags, en conservant les placeholders de l'action.
		contexte = _contexte(character, pnj_doc, lieu_doc, entree)
		contexte["placeholders"].update(dits)
	elif action.get("service") == "commission":
		suivant, dits = _resoudre_commission(character, pnj_doc, lieu_doc,
											 action.get("op"), reponse)
		# Même raison que le rang : la commission vient d'être prise ou soldée → refiltrer
		# les choix sur les nouveaux flags, en conservant les placeholders de l'action.
		contexte = _contexte(character, pnj_doc, lieu_doc, entree)
		contexte["placeholders"].update(dits)
	elif action.get("service") == "acces":
		suivant, dits = _resoudre_acces(current_user, character, pnj_doc, lieu_doc,
										 action.get("op"), reponse)
		contexte = _contexte(character, pnj_doc, lieu_doc, entree)
		contexte["placeholders"].update(dits)
	else:
		suivant = choix.get("next")

	# Hook de DÉPLACEMENT AUTOMATIQUE, utilisable par n'importe quel choix de n'importe quel
	# dialogue : `"deplacer": "lieu:xxx"` → le client enchaîne sur son déplacement normal
	# (`moveTo`), donc sur `/api/move_character` et tous ses effets de bord. Résolu APRÈS
	# l'action : quand c'est un gardien qui vous fait entrer, le laissez-passer doit déjà être
	# posé, sinon le déplaceur refuserait en 403.
	# ⚠️ Un lien manquant est SILENCIEUX ici (`deplacer` absent de la réponse) : le dialogue se
	# déroule normalement, le joueur va au lieu à pied. C'est voulu — un contenu qui vise un
	# lieu non relié ne doit pas casser la conversation. Le contrôle est le linter + le BFS.
	if choix.get("deplacer"):
		link_id = _lien_vers(current_user, character.get("lieu"), choix["deplacer"])
		if link_id:
			reponse["deplacer"] = link_id
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


def _placeholders_rang(q: dict, rang_courant: str) -> dict:
	"""Placeholders qu'un nœud du service `rang` peut citer : espèce et lieu de l'élite à
	traquer, rang courant, rang visé et XP de récompense."""
	obj = q.get("objectif", {}) or {}
	espece_doc = get_doc(obj.get("cible")) if obj.get("cible") else None
	lieu_cible = get_doc(obj.get("lieu")) if obj.get("lieu") else None
	rec = q.get("recompenses") or {}
	return {
		"espece": (espece_doc or {}).get("nom") or (obj.get("cible") or "").split(":", 1)[-1],
		"lieu": (lieu_cible or {}).get("label") or (lieu_cible or {}).get("nom")
		or (obj.get("lieu") or "").split(":", 1)[-1],
		"rang": rang_courant,
		"rang_vise": q.get("rang_vise") or chasse.rang_suivant(rang_courant),
		"xp": rec.get("xp", 0),
	}


def _resoudre_rang(character: dict, pnj_doc: dict, lieu_doc: dict, op: str,
				   reponse: dict) -> tuple[str | None, dict]:
	"""Exécute une action du service `rang` du comptoir de guilde :
	`accepter` : le maître d'armes confie l'épreuve de rang offerte (chasse à l'élite).
	`rapporter`: il solde une épreuve accomplie → promotion de rang (par cité) + XP + prime.
	Renvoie (nœud de résultat, placeholders que ce nœud peut citer)."""
	noeuds = ((pnj_doc.get("services") or {}).get("rang") or {}).get("noeuds") or {}
	cite = lieu_doc.get("lieu_parent")

	if op == "accepter":
		offre = chasse.offre_rang_courante(character, lieu_doc)
		if not offre:
			raise HTTPException(status_code=422, detail="Aucune épreuve de rang à prendre ici.")
		# Calculés AVANT la mutation : l'offre est vidée à l'acceptation, mais le nœud de résultat
		# doit encore pouvoir nommer la cible et le rang visé.
		dits = _placeholders_rang(offre, chasse.rang_de(character, cite))
		q = chasse.accepter_rang(character)
		if not q:
			raise HTTPException(status_code=422, detail="Aucune épreuve de rang à prendre ici.")
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		reponse["rang"] = {"accepte": q.get("titre")}
		reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
		return noeuds.get("accepte"), dits

	if op == "rapporter":
		q = chasse.rang_a_rapporter(character, cite)
		if not q:
			raise HTTPException(status_code=422, detail="Aucune épreuve de rang à solder ici.")
		dits = _placeholders_rang(q, chasse.rang_de(character, cite))
		resultat = chasse.solder_rang(character, q.get("id") or q.get("_id"))
		if not resultat:
			raise HTTPException(status_code=422, detail="Épreuve de rang non accomplie.")
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		# Le rang affiché est désormais le NOUVEAU (après promotion).
		dits["rang"] = resultat["promu"]
		rangs_guilde = character.get("rangs_guilde") or {}
		reponse["rang"] = {
			"promu": resultat["promu"],
			"xp": resultat["recompenses"]["xp"].get("xp_gain", 0),
			"niveau_up": resultat["recompenses"]["xp"].get("niveau_up", False),
			# Le MEILLEUR rang toutes villes confondues + son détail : même calcul que /play
			# (utils/chasse), pour que la carte du joueur se resynchronise sans reload — une
			# promotion à Rhemi ne fait pas forcément remonter l'affichage si Auxerre est
			# déjà mieux classée.
			"meilleur": chasse.meilleur_rang(rangs_guilde),
			"detail": chasse.rangs_guilde_title(rangs_guilde, get_doc),
		}
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
		reponse["vitals"] = _vitals_payload(character)
		reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
		return noeuds.get("rapporte"), dits

	raise HTTPException(status_code=422, detail="Action de rang inconnue.")


def _placeholders_commission(q: dict) -> dict:
	"""Placeholders qu'un nœud du service `commission` peut citer : l'espèce à éradiquer, la
	salle du donjon où elle tient ses galeries, et l'XP promise. Mêmes clés que le service
	`rang` (`{espece}`/`{lieu}`/`{xp}`) — c'est le même geste, traquer une élite désignée."""
	obj = (q or {}).get("objectif") or {}
	espece_doc = get_doc(obj.get("cible")) if obj.get("cible") else None
	lieu_cible = get_doc(obj.get("lieu")) if obj.get("lieu") else None
	rec = (q or {}).get("recompenses") or {}
	return {
		"espece": (espece_doc or {}).get("nom") or (obj.get("cible") or "").split(":", 1)[-1],
		"lieu": (lieu_cible or {}).get("label") or (lieu_cible or {}).get("nom")
		or (obj.get("lieu") or "").split(":", 1)[-1],
		"xp": rec.get("xp", 0),
		"prime": rec.get("cuivre", 0),
	}


def _resoudre_commission(character: dict, pnj_doc: dict, lieu_doc: dict, op: str,
						 reponse: dict) -> tuple[str | None, dict]:
	"""Exécute une action du service `commission` (maître de guilde) :
	`accepter` : il confie une commission d'éradication (quête `chasse` visant une salle de
	  donjon — c'est elle qui, seule, ouvrira la porte gardée du donjon).
	`rapporter`: il solde une commission accomplie → XP + prime (aucune promotion de rang,
	  contrairement au service `rang` : une commission paie, elle n'élève pas).
	Renvoie (nœud de résultat, placeholders que ce nœud peut citer). Miroir de `_resoudre_rang`."""
	commission_conf = (pnj_doc.get("services") or {}).get("commission") or {}
	noeuds = commission_conf.get("noeuds") or {}
	donjon_doc = get_doc(commission_conf["donjon"]) if commission_conf.get("donjon") else None
	if not donjon_doc:
		raise HTTPException(status_code=422, detail="Ce personnage ne mandate aucune commission.")

	if op == "accepter":
		# ⚠️ L'offre est RETIRÉE ici (`offre_commission_pour` la rebâtit à chaque appel, elle
		# n'est jamais mémorisée) : la cible acceptée est celle de CE tirage, pas celle que le
		# joueur croyait avoir lue au nœud précédent s'il a rechargé entre-temps. Assumé — le
		# nœud de résultat récite la cible réellement engagée.
		offre = donjon.offre_commission_pour(character, lieu_doc, donjon_doc, get_doc, find_docs)
		if not offre:
			raise HTTPException(status_code=422, detail="Aucune commission à prendre ici.")
		dits = _placeholders_commission(offre)
		q = donjon.accepter_commission(character, offre)
		if not q:
			raise HTTPException(status_code=422, detail="Aucune commission à prendre ici.")
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		reponse["commission"] = {"accepte": q.get("titre")}
		reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
		return noeuds.get("accepte"), dits

	if op == "rapporter":
		q = donjon.commission_a_rapporter(character)
		if not q:
			raise HTTPException(status_code=422, detail="Aucune commission à solder ici.")
		# Calculés AVANT la mutation : la quête quitte `quetes_actives` au soldement, mais le
		# nœud de résultat doit encore pouvoir nommer la bête et la prime.
		dits = _placeholders_commission(q)
		resultat = donjon.solder_commission(character, q.get("id") or q.get("_id"))
		if not resultat:
			raise HTTPException(status_code=422, detail="Commission non accomplie.")
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		reponse["commission"] = {
			"rapporte": q.get("titre"),
			"xp": resultat["recompenses"]["xp"].get("xp_gain", 0),
			"niveau_up": resultat["recompenses"]["xp"].get("niveau_up", False),
		}
		reponse["purse"] = cuivre_to_purse(money_to_cuivre(character))
		reponse["vitals"] = _vitals_payload(character)
		reponse["fiche_actives"], reponse["fiche_terminees"] = quetes.fiche_details(character)
		return noeuds.get("rapporte"), dits

	raise HTTPException(status_code=422, detail="Action de commission inconnue.")


def _declencher_combat_donjon(character: dict, lieu_garde: dict) -> str | None:
	"""Ouvre le combat d'une salle de donjon, et renvoie son id (None si le donjon n'a rien à
	opposer). Miroir SIMPLIFIÉ de `routers.combat.start_combat` — trois différences assumées :

	· le pool d'espèces vient du doc `donjon:*` (curaté), pas des zones du lieu ;
	· l'élite de la commission est GARANTIE présente, là où `start_combat` ne la marque que si
	  le tirage naturel l'a fait apparaître (ici, franchir la porte EST l'événement de chasse) ;
	· aucune furtivité d'entrée : on descend par un escalier gardé, annoncé, pas en embuscade.

	Anti-doublon repris tel quel : un combat déjà actif est REPRIS plutôt que doublé, sinon
	repasser devant le gardien laisserait des combats orphelins en base."""
	for c in (find_docs({"type": "combat", "user_id": character["user_id"]}) or []):
		if c.get("character_id") == character["_id"] and c.get("status") == "active":
			return c["_id"]

	donjon_doc = donjon.donjon_de_lieu(lieu_garde.get("_id"), find_docs)
	if not donjon_doc:
		return None
	pool_especes = donjon.especes_de_salle(donjon_doc, lieu_garde["_id"], get_doc)
	if not pool_especes:
		return None
	# ⚠️ Le plafond de grade de la salle vaut pour TOUTE la salle, pas seulement pour l'élite :
	# sans lui, les monstres d'accompagnement seraient tirés parmi tous les grades de la base
	# (jusqu'au niveau 6) et pèseraient plus lourd que la cible mandatée elle-même.
	profils = donjon._profils_sous_plafond(
		find_docs({"type": "profil"}) or [],
		donjon.niveau_max_de(donjon_doc, lieu_garde["_id"]),
	)

	compagnons = recrutement.groupe_effectif(character, get_doc)
	montures_groupe = montures.montures_effectives(character, get_doc)
	nb_monstres = 3 + len(compagnons) // 2
	# zone_tags vide : les espèces sont déjà choisies à la main, pas à filtrer par terrain.
	monstres = instantiate_monsters(pool_especes, profils, nb_monstres, [])
	if not monstres:
		return None

	# L'élite mandatée, imposée sur le premier monstre de son espèce — et à défaut sur le
	# premier tout court : sans elle le joueur nettoierait la salle sans jamais pouvoir
	# compléter sa commission (le combat est à usage unique, il n'y a pas de seconde chance).
	q = donjon.commission_active_pour_lieu(character, lieu_garde["_id"])
	narration = None
	if q:
		obj = q.get("objectif") or {}
		espece_doc = next((e for e in pool_especes if e["_id"] == obj.get("cible")), None)
		profil_doc = get_doc(obj.get("profil")) if obj.get("profil") else None
		if espece_doc and profil_doc:
			idx = next(
				(i for i, m in enumerate(monstres) if m.get("espece_id") == obj.get("cible")),
				0,
			)
			ancien = monstres[idx]
			elite = build_monster_snapshot(espece_doc, profil_doc, idx)
			elite["id"] = ancien["id"]
			elite["pos"] = ancien.get("pos", elite["pos"])
			elite["quete_chasse"] = q.get("id") or q.get("_id")
			monstres[idx] = elite
			narration = q.get("narration")

	combat_doc = create_combat_doc(
		character, monstres, list(lieu_garde.get("tags") or []),
		lieu_garde.get("image", ""), battle_map=lieu_garde,
		compagnons=compagnons, montures=montures_groupe,
	)
	if narration:
		combat_doc["chasse_narration"] = narration
	resolve_first_turns(combat_doc)
	if combat_doc["status"] != "active":
		finalize_combat(combat_doc)
	save_doc(combat_doc)
	return combat_doc["_id"]


def _resoudre_acces(current_user: dict, character: dict, pnj_doc: dict, lieu_doc: dict,
					 op: str, reponse: dict) -> tuple[str | None, dict]:
	"""Exécute l'action `passer` du service `acces` (PNJ gardien d'un lieu). Miroir strict de
	`_resoudre_rang`. Renvoie (nœud de résultat, placeholders que ce nœud peut citer).

	DEUX natures de porte, selon le lieu gardé :
	· un lieu EXPLORABLE → on pose un laissez-passer, et le lieu apparaît dans la liste des
	  sous-lieux (comportement d'origine : le temple-portail de Saint-Austrelin) ;
	· une SALLE DE DONJON (`categorie:"battle_map"`) → il n'y a rien à « visiter » (ni
	  `connection`, ni grille d'exploration, ni zones) : franchir la porte OUVRE LE COMBAT.
	  Aucun laissez-passer n'est donc posé — chaque descente est un engagement neuf."""
	acces_conf = (pnj_doc.get("services") or {}).get("acces") or {}
	noeuds = acces_conf.get("noeuds") or {}
	lieu_garde = get_doc(acces_conf["lieu"]) if acces_conf.get("lieu") else None
	if not lieu_garde:
		raise HTTPException(status_code=422, detail="Ce personnage ne garde aucun accès.")
	dits = {"portail": lieu_garde.get("label") or lieu_garde.get("nom") or ""}

	if op == "passer":
		if acces.laissez_passer_valide(character, lieu_garde):
			return noeuds.get("deja"), dits
		ok, _raison = acces.acces_autorise(character, lieu_garde, get_doc)
		if not ok:
			return noeuds.get("refus"), dits
		if lieu_garde.get("categorie") == "battle_map":
			# ⚠️ `_declencher_combat_donjon` SAUVEGARDE le doc combat, jamais le character :
			# rien n'a été muté sur lui (aucun laissez-passer posé), il n'y a donc rien à
			# persister ici — et surtout rien à écraser sur un `_rev` déjà relu.
			combat_id = _declencher_combat_donjon(character, lieu_garde)
			if not combat_id:
				raise HTTPException(status_code=422,
									detail="Ce passage ne mène à aucun danger connu.")
			reponse["combat_id"] = combat_id
			return noeuds.get("ouvre"), dits
		acces.poser_laissez_passer(character, lieu_garde, pnj_doc.get("_id"))
		if save_doc(character) is None:
			raise HTTPException(status_code=409, detail="Conflit de sauvegarde — réessayez.")
		reponse["acces"] = {"lieu": lieu_garde.get("_id"), "nom": dits["portail"]}
		# Sans ceci le portail n'apparaîtrait qu'au prochain rechargement de /play : le
		# laissez-passer vient d'être posé, mais la liste des sous-lieux a été rendue à
		# l'ouverture de la page.
		reponse["links"] = get_lieu_links(current_user)
		return noeuds.get("ouvre"), dits

	raise HTTPException(status_code=422, detail="Action d'accès inconnue.")


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
