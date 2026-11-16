"""Combat à l'ARRIVÉE dans un lieu explorable, gardien qui RÉAPPARAÎT (pur).

Un lieu `lieu:*` peut porter un bloc `combat_arrivee` :

	{"espece": "espece:…",              # le GARDIEN, toujours présent, un seul
	 "accompagnants": ["espece:…"],     # comparses possibles (facultatif)
	 "nb_accompagnants": 1,             # de base, +1 par tranche de 2 compagnons
	 "reapparition_min": 5,             # délai de réapparition après sa mort (défaut 5)
	 "profil_weights": {"profil:…": n}} # grades (facultatif, sinon tirage uniforme)

Arriver dans ce lieu PAR UNE CONNEXION (branche « lien » de `move_character`) ouvre aussitôt
un combat contre le gardien et ses comparses, sur la carte du lieu, le groupe à la case
d'arrivée — SAUF si le gardien a été abattu depuis moins de `reapparition_min` minutes :
le lieu est alors vide. Une connexion interne, un rafraîchissement ou un pas dans le lieu
n'ouvrent rien.

Le délai est GLOBAL (Auteur, 16/11) : le gardien est unique au monde, abattu par n'importe
quel joueur il manque à tous. Sa mort se note sur un doc d'ÉTAT `reapparition:<lieu>`
(`{type, lieu, tue_at, combat_id}`), créé à la première mort — rien à importer, et un doc
d'état n'entre jamais au cache de contenu (`db/config._CACHEABLE_PREFIXES`). Écrit par
`combat.finalize_combat` dès que le gardien est tombé, quelle que soit l'issue (tué puis
fuite devant ses comparses compte), lu par `routers/user._declencher_combat_arrivee`.
Aucune horloge de fond (CLAUDE.md §5) : la réapparition se constate à l'arrivée suivante.

Rencontre lue par `apport.rencontre_spec` (même forme que la rencontre garantie d'un apport
situé), monstres par `combat.instantiate_rencontre` : le gardien en tête, puis les comparses
tirés parmi les seuls `accompagnants`.
"""

from utils import apport

CHAMP = "combat_arrivee"
PREFIXE_ETAT = "reapparition:"
REAPPARITION_MIN_DEFAUT = 5


def spec(lieu_doc: dict | None) -> dict | None:
	"""Bloc `combat_arrivee` normalisé, ou None (absent ou illisible — fail-closed : une
	donnée fautive n'ouvre aucun combat)."""
	raw = (lieu_doc or {}).get(CHAMP)
	rencontre = apport.rencontre_spec(raw)
	if rencontre is None:
		return None
	delai = raw.get("reapparition_min", REAPPARITION_MIN_DEFAUT)
	if isinstance(delai, bool) or not isinstance(delai, (int, float)) or delai < 0:
		return None
	poids = raw.get("profil_weights")
	if poids is not None and not (isinstance(poids, dict) and all(
			isinstance(k, str) and k.startswith("profil:")
			and not isinstance(v, bool) and isinstance(v, (int, float)) and v >= 0
			for k, v in poids.items())):
		return None
	rencontre["reapparition_min"] = delai
	rencontre["profil_weights"] = dict(poids) if poids else None
	return rencontre


def etat_id(lieu_id: str) -> str:
	"""Id du doc d'état de réapparition d'un lieu : `reapparition:<slug>`."""
	return PREFIXE_ETAT + str(lieu_id or "").split(":", 1)[-1]


def abattu_recemment(etat: dict | None, regle: dict, now: int) -> bool:
	"""Le gardien est-il mort depuis moins de `reapparition_min` minutes ?"""
	tue_at = (etat or {}).get("tue_at")
	if isinstance(tue_at, bool) or not isinstance(tue_at, (int, float)):
		return False
	return now - tue_at < regle["reapparition_min"] * 60


def nb_accompagnants(regle: dict, nb_compagnons: int) -> int:
	"""Comparses : `nb_accompagnants` de base, +1 par tranche de 2 compagnons (règle de la
	rencontre garantie de `start_combat`). Aucun accompagnant possible ⇒ 0."""
	if not regle.get("accompagnants"):
		return 0
	return regle["nb_accompagnants"] + max(0, int(nb_compagnons or 0)) // 2


def marque(lieu_id: str, regle: dict) -> dict:
	"""Ce que le doc combat retient pour que la finalisation sache qui est le gardien."""
	return {"lieu": lieu_id, "espece": regle["espece"]}


def gardien_abattu(combat_doc: dict) -> bool:
	"""Le gardien de ce combat d'arrivée est-il tombé ? (invocations exclues)"""
	m = (combat_doc or {}).get(CHAMP) or {}
	espece = m.get("espece")
	if not espece or not m.get("lieu"):
		return False
	return any(x.get("espece_id") == espece and not x.get("vivant", True)
			   and not x.get("est_invocation")
			   for x in (combat_doc.get("monstres") or []))


def noter_abattu(etat: dict | None, combat_doc: dict, now: int) -> dict | None:
	"""Doc d'état à sauver (copie mutée), ou None s'il n'y a rien à écrire : gardien debout,
	ou mort déjà notée pour CE combat (une re-finalisation ne repousse pas le délai)."""
	if not gardien_abattu(combat_doc):
		return None
	lieu_id = combat_doc[CHAMP]["lieu"]
	doc = dict(etat or {})
	if doc.get("combat_id") and doc.get("combat_id") == combat_doc.get("_id"):
		return None
	doc.update({"_id": etat_id(lieu_id), "type": "reapparition", "lieu": lieu_id,
				"tue_at": int(now), "combat_id": combat_doc.get("_id")})
	return doc
