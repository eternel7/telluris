# utils/apport.py
# Quêtes d'APPORT confiées par un PNJ : « rapporte-moi N fois cet objet ». Service de
# dialogue `apport`, logique pure (aucune DB, mute sans save — l'endpoint persiste).
#
# Deux rôles, comme le transport, presque toujours tenus par le même PNJ :
# - DONNEUR : `services.apport.offre = {id, titre?, description?, item, quantite, unique?,
#   recompenses?:{xp, cuivre}}` — l'offre est ÉCRITE (jamais tirée au sort) ;
# - RECEVEUR : `services.apport.quete = "quete:…"` (ou l'`offre.id`) — il prend livraison
#   d'une quête déjà ACTIVE. Un autre PNJ du MÊME lieu peut donc la recevoir (l'aubergiste du
#   Coq de Lutèce, quand Élise n'est plus là) : la remise ne lit que le SNAPSHOT.
#
# La quête est une quête `collect` ORDINAIRE du moteur (`quetes.snapshot_quete`) : même
# progression (`progress` = pièces déjà remises, `quetes.deposer_collect`), même onglet 📜,
# même focalisation 🎯 (biais de récolte), même abandon (sanction de la maison du donneur).
# `giver` = le LIEU du donneur ; la remise exige d'y être (deux lieux peuvent héberger le même
# doc PNJ, un seul a confié la quête).
#
# Remise PARTIELLE permise (les pièces portées sont déposées jusqu'au reste à faire) : sans
# elle, une seule feuille cueillie en trop peu de temps obligerait à tout garder sur soi.
#
# LOCALISATION (optionnelle) : `offre.localisation = {lieu: "lieu:…", position: {x, y}}` — le
# donneur SITUE la proie (la Bête du Gévaudan de Maëlys). Recopiée dans le snapshot, elle
# donne le bouton 🗺️ de l'onglet 📜 (`quetes.quete_detail`, même crop que les chasses). Elle
# n'influe sur AUCUN tirage : c'est une indication, pas une rencontre garantie.

from utils import quetes

NOEUDS_DONNEUR = frozenset({"accepte"})
NOEUDS_RECEVEUR = frozenset({"remis", "partiel"})


def localisation_spec(raw) -> dict | None:
	"""`{lieu, position:{x, y}}` normalisé, ou None si absent ou illisible (lieu hors
	`lieu:`, coordonnées non entières ou négatives). Le linter signale une forme illisible."""
	if not isinstance(raw, dict):
		return None
	lieu, pos = raw.get("lieu"), raw.get("position")
	if not (isinstance(lieu, str) and lieu.startswith("lieu:")) or not isinstance(pos, dict):
		return None
	x, y = pos.get("x"), pos.get("y")
	if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (x, y)):
		return None
	return {"lieu": lieu, "position": {"x": x, "y": y}}


def offre_spec(pnj_doc: dict) -> dict | None:
	"""L'offre ÉCRITE de ce PNJ, normalisée — None si absente ou inexploitable (id hors
	`quete:`, item hors `item:`, quantité < 1). Le linter signale ces mêmes fautes."""
	offre = (((pnj_doc or {}).get("services") or {}).get("apport") or {}).get("offre")
	if not isinstance(offre, dict):
		return None
	qid, item = offre.get("id"), offre.get("item")
	if not (isinstance(qid, str) and qid.startswith("quete:")):
		return None
	if not (isinstance(item, str) and item.startswith("item:")):
		return None
	quantite = offre.get("quantite", 1)
	if isinstance(quantite, bool) or not isinstance(quantite, int) or quantite < 1:
		return None
	return {
		"id": qid,
		"titre": offre.get("titre") or "Un apport",
		"description": offre.get("description") or "",
		"item": item,
		"quantite": quantite,
		"unique": offre.get("unique", True) is not False,
		"recompenses": dict(offre.get("recompenses") or {}),
		# Rang AFFICHÉ de la quête (badge de la fiche) ; absent ⇒ le défaut du snapshot.
		"rang": offre.get("rang"),
		# Où chercher (bouton 🗺️) ; None ⇒ aucune carte.
		"localisation": localisation_spec(offre.get("localisation")),
	}


def quete_id_de(pnj_doc: dict) -> str | None:
	"""L'id de la quête que ce PNJ RECOIT : `services.apport.quete`, sinon celui de son offre."""
	conf = ((pnj_doc or {}).get("services") or {}).get("apport") or {}
	qid = conf.get("quete")
	if isinstance(qid, str) and qid.startswith("quete:"):
		return qid
	spec = offre_spec(pnj_doc)
	return spec["id"] if spec else None


def _active_ici(character: dict, qid: str | None, lieu_id: str | None) -> dict | None:
	"""La quête active `qid` si elle a été confiée par CE lieu (et est bien une collecte)."""
	if not qid or not lieu_id:
		return None
	q = quetes.quete_active(character, qid)
	if not q or q.get("giver") != lieu_id:
		return None
	if (q.get("objectif") or {}).get("type") != "collect":
		return None
	return q


def nb_portes(character: dict, q: dict, porteurs: list | None = None) -> int:
	"""Pièces de la cible portées par le principal ET ses porteurs (compagnons, montures)."""
	cible = (q.get("objectif") or {}).get("cible")
	return quetes.compter_sacs([character] + list(porteurs or []), cible) if cible else 0


def reste_a_remettre(q: dict) -> int:
	obj = q.get("objectif") or {}
	return max(0, int(obj.get("quantite", 0) or 0) - int(q.get("progress", 0) or 0))


def etat(character: dict, pnj_doc: dict, lieu_id: str | None, porteurs: list | None = None) -> dict:
	"""Les FLAGS du service pour CE PNJ dans CE lieu :
	- `apport_offert`   : offre écrite, ni en cours, ni (si `unique`) déjà réussie ;
	- `apport_en_cours` : la quête court (qu'on porte ou non de quoi la remettre) ;
	- `apport_possible` : elle court ET le joueur (ou un de ses `porteurs`) porte au moins une
	  pièce à remettre ;
	- `apport_accompli` : la quête a été menée à bien (miroir de `quete_reussie`)."""
	spec = offre_spec(pnj_doc)
	qid = quete_id_de(pnj_doc)
	q = _active_ici(character, qid, lieu_id)
	reussie = bool(qid) and quetes.quete_reussie(character, qid)
	return {
		"apport_offert": bool(spec) and q is None and quetes.quete_active(character, qid) is None
						 and not (spec["unique"] and reussie),
		"apport_en_cours": q is not None,
		"apport_possible": q is not None and reste_a_remettre(q) > 0 and nb_portes(character, q, porteurs) > 0,
		"apport_accompli": reussie,
	}


def placeholders(character: dict, pnj_doc: dict, lieu_id: str | None, nom_item_fn) -> dict:
	"""{objet} (nom de l'item), {quantite}, {reste}, {xp}, {prime} — depuis la quête active si
	elle court (son snapshot fait foi), sinon depuis l'offre écrite."""
	q = _active_ici(character, quete_id_de(pnj_doc), lieu_id)
	if q:
		obj = q.get("objectif") or {}
		item, quantite, reste = obj.get("cible"), int(obj.get("quantite", 0) or 0), reste_a_remettre(q)
		rec = q.get("recompenses") or {}
	else:
		spec = offre_spec(pnj_doc)
		if not spec:
			return {}
		item, quantite, reste, rec = spec["item"], spec["quantite"], spec["quantite"], spec["recompenses"]
	return {
		"objet": nom_item_fn(item) if item else "",
		"quantite": quantite,
		"reste": reste,
		"xp": rec.get("xp", 0),
		"prime": rec.get("cuivre", 0),
	}


def accepter(character: dict, pnj_doc: dict, lieu_id: str) -> dict | None:
	"""Pose la quête dans `quetes_actives` (mute sans save). None si rien n'est offert."""
	spec = offre_spec(pnj_doc)
	if not spec or not etat(character, pnj_doc, lieu_id)["apport_offert"]:
		return None
	q = quetes.snapshot_quete({
		"_id": spec["id"],
		"titre": spec["titre"],
		"description": spec["description"],
		"giver": lieu_id,
		"objectif": {"type": "collect", "cible": spec["item"], "quantite": spec["quantite"]},
		"recompenses": spec["recompenses"],
		**({"rang": spec["rang"]} if spec.get("rang") else {}),
	})
	if spec.get("localisation"):
		# Hors de `objectif` : une collecte n'a pas de lieu de remise ailleurs que chez le donneur.
		q["localisation"] = {"lieu": spec["localisation"]["lieu"],
							 "position": dict(spec["localisation"]["position"])}
	character.setdefault("quetes_actives", []).append(q)
	return q


def remettre(character: dict, pnj_doc: dict, lieu_id: str,
			 porteurs: list | None = None) -> tuple[dict | None, int, bool, list]:
	"""Dépose les pièces portées par le principal PUIS ses `porteurs` (jusqu'au reste à faire).
	→ (quête, déposées, complète, porteurs touchés à persister par l'appelant).
	(None, 0, False, []) si rien n'est remettable ici. N'archive PAS : l'appelant crédite les
	récompenses d'abord (`quetes.appliquer_recompenses`), puis appelle `archiver`."""
	q = _active_ici(character, quete_id_de(pnj_doc), lieu_id)
	if not q:
		return None, 0, False, []
	n, touches = quetes.deposer_collect(character, q, porteurs)
	return q, n, quetes.objectif_atteint(character, q), touches


def archiver(character: dict, q: dict, now: int) -> None:
	"""Sort la quête des actives et l'archive RÉUSSIE (mute sans save) — même forme que les
	autres voies d'archivage (`giver` recopié, lu par `acces.quete_reussie_cite`)."""
	character["quetes_actives"] = [
		a for a in character.get("quetes_actives", []) if a.get("id") != q.get("id")
	]
	character.setdefault("quetes_terminees", []).append({
		"id": q.get("id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", "F"),
		"recompenses": dict(q.get("recompenses") or {}),
		"giver": q.get("giver"),
		"termine_at": now,
	})
