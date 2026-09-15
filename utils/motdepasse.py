# utils/motdepasse.py
# Sceau Secret oublié — réinitialisation par courriel. Logique PURE, DB injectée
# (get_doc_fn), mute sans jamais sauvegarder : l'appelant persiste.
#
# Le jeton ne vit JAMAIS en clair en base : le doc s'appelle `reset:<sha256(jeton)>`,
# et seul le porteur du lien connaît le jeton. Une fuite du dump ne rend donc aucun
# lien utilisable, et la vérification reste un `get_doc` direct (aucune vue, aucun
# index) puisque l'empreinte EST l'identifiant.
#
#   {"_id": "reset:<empreinte>", "type": "reset",
#    "user_id": "user:x@y.z", "cree_le": <epoch>, "expire_le": <epoch>}
#
# Cycle de vie : créé par la demande, SUPPRIMÉ par l'usage (usage unique) ou périmé par
# `expire_le`. Aucun tick de fond ne le ramasse (CLAUDE.md § 5) : la péremption est
# contrôlée au passage, à la vérification.
#
# ⚠️ `reset:` est hors `_CACHEABLE_PREFIXES` (db/config.py) — c'est un doc d'état, lu
# puis détruit dans la même requête.

import hashlib
import secrets
import time

# Durée de vie d'un lien. Assez court pour qu'un courriel oublié dans une boîte
# partagée ne reste pas une clef, assez long pour un joueur qui relève son courrier.
DUREE_JETON_MINUTES = 60

# Longueur du secret tiré (octets avant encodage url-safe).
OCTETS_JETON = 32

# Cadence maximale des demandes POUR UN MÊME COMPTE. Le joueur qui n'a rien vu passer
# peut relancer sans attendre longtemps ; la boîte visée ne prend jamais plus de douze
# messages par heure. ⚠️ Elle se lit sur les jetons DÉJÀ EN BASE (aucun champ ajouté au
# doc `user:*`, aucune écriture de plus) : un lien consommé efface donc sa propre
# cadence, et c'est voulu — se réinitialiser puis redemander n'est pas un abus.
DELAI_ENTRE_DEMANDES_SECONDES = 300

PREFIXE_JETON = "reset:"

# Réponse UNIQUE de la demande d'oubli, adresse connue ou non : révéler qu'un compte
# existe transformerait l'écran en oracle d'inscription.
MESSAGE_DEMANDE = ("Si un compte porte ce sceau de correspondance, un message vient "
				   "de lui être envoyé. Vérifiez votre courrier.")


def empreinte(jeton: str) -> str:
	"""Empreinte stable d'un jeton — ce qui est stocké, jamais le jeton lui-même."""
	return hashlib.sha256((jeton or "").encode("utf-8")).hexdigest()


def doc_id_jeton(jeton: str) -> str:
	return PREFIXE_JETON + empreinte(jeton)


def nouveau_jeton(user_id: str, *, now: int = None, jeton_fn=None) -> tuple[str, dict]:
	"""Rend `(jeton en clair, doc à sauver)`. Le clair part dans le courriel et n'est
	plus jamais reconstructible ensuite."""
	maintenant = int(now if now is not None else time.time())
	jeton = (jeton_fn or (lambda: secrets.token_urlsafe(OCTETS_JETON)))()
	doc = {
		"_id": doc_id_jeton(jeton),
		"type": "reset",
		"user_id": user_id,
		"cree_le": maintenant,
		"expire_le": maintenant + DUREE_JETON_MINUTES * 60,
	}
	return jeton, doc


def jeton_utilisable(jeton: str, get_doc_fn, *, now: int = None) -> dict | None:
	"""Le doc `reset:*` si le jeton existe ENCORE et n'est pas périmé, sinon None.
	L'appelant supprime le doc dès qu'il s'en sert : le lien ne vaut qu'une fois."""
	if not jeton:
		return None
	doc = get_doc_fn(doc_id_jeton(jeton))
	if not doc or doc.get("type") != "reset" or not doc.get("user_id"):
		return None
	maintenant = int(now if now is not None else time.time())
	if maintenant >= int(doc.get("expire_le", 0)):
		return None
	return doc


def jetons_du_compte(user_id: str, find_docs_fn) -> list[dict]:
	"""Les jetons vivants ou périmés déjà émis pour ce compte. Sélecteur servi par
	l'index `idx-tables-by-user` (`["type", "user_id"]`, db/config.py)."""
	if not user_id:
		return []
	return find_docs_fn({"type": "reset", "user_id": user_id}) or []


def demande_trop_recente(jetons: list[dict], *, now: int = None) -> bool:
	"""Un lien a-t-il déjà été émis il y a moins de `DELAI_ENTRE_DEMANDES_SECONDES` ?
	⚠️ L'appelant REFUSE EN SILENCE (même réponse que d'ordinaire) : un 429 ne
	tomberait que sur les adresses qui ont un compte, et redirait ce que
	`MESSAGE_DEMANDE` s'applique à taire."""
	maintenant = int(now if now is not None else time.time())
	return any(maintenant - int(j.get("cree_le", 0)) < DELAI_ENTRE_DEMANDES_SECONDES
			   for j in jetons)


def jetons_perimes(jetons: list[dict], *, now: int = None) -> list[dict]:
	"""Ceux que l'appelant peut supprimer au passage. Aucun tick de fond ne ramasse les
	jetons expirés (CLAUDE.md § 5) : ils s'effacent ici, à la demande suivante."""
	maintenant = int(now if now is not None else time.time())
	return [j for j in jetons if maintenant >= int(j.get("expire_le", 0))]


def verifier_force(mot_de_passe: str, verification: str) -> str | None:
	"""Message d'erreur si le nouveau sceau ne tient pas la règle affichée à
	l'inscription (8 caractères, une majuscule, un chiffre, un symbole), sinon None."""
	mot_de_passe = mot_de_passe or ""
	if mot_de_passe != (verification or ""):
		return "Les mots de passe ne correspondent pas"
	if len(mot_de_passe) < 8:
		return "Le mot de passe doit faire au moins 8 caractères"
	if not any(c.isupper() for c in mot_de_passe):
		return "Le mot de passe doit contenir au moins une majuscule"
	if not any(c.isdigit() for c in mot_de_passe):
		return "Le mot de passe doit contenir au moins un chiffre"
	if not any(not c.isalnum() for c in mot_de_passe):
		return "Le mot de passe doit contenir au moins un symbole"
	return None


def lien_reinitialisation(base_url: str, jeton: str) -> str:
	return (base_url or "").rstrip("/") + "/reinitialisation?jeton=" + jeton


def courriel_de_reinitialisation(username: str, lien: str) -> tuple[str, str]:
	"""`(sujet, corps)` du message envoyé au joueur."""
	nom = (username or "").strip() or "voyageur"
	sujet = "Telluris — réinitialisation de votre Sceau Secret"
	corps = (
		f"Salutations {nom},\n\n"
		"Quelqu'un — vous, espérons-le — a demandé à refondre le Sceau Secret de ce "
		"compte Telluris. Suivez ce lien pour en graver un nouveau :\n\n"
		f"{lien}\n\n"
		f"Ce lien expire dans {DUREE_JETON_MINUTES} minutes et ne sert qu'une fois.\n"
		"Si vous n'êtes à l'origine d'aucune demande, ignorez ce message : votre sceau "
		"actuel reste valable.\n\n"
		"— Les scribes de Telluris"
	)
	return sujet, corps
