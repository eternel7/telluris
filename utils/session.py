# utils/session.py
# Session de jeu : jeton d'ACCÈS court + jeton de RAFRAÎCHISSEMENT long, à rotation.
#
#   - accès (`auth_token`) : JWT signé, ACCES_MINUTES — lu par `auth.get_current_user` ;
#   - rafraîchissement (`refresh_token`) : secret OPAQUE, RAFRAICHISSEMENT_JOURS, cookie
#     httponly. En base sous son EMPREINTE (`refresh:<sha256>`, comme `reset:*`) : une fuite
#     du dump ne rend aucune session utilisable, et la vérification reste un `get_doc` direct.
#
#   {"_id": "refresh:<empreinte>", "type": "refresh", "user_id", "famille",
#    "cree_le", "expire_le", "precedent"?, "remplace_le"?, "remplace_par"?}
#
# ROTATION : chaque usage remplace le jeton par un neuf de la même FAMILLE (une famille =
# une connexion). Un jeton déjà remplacé, présenté au-delà de GRACE_SECONDES, est une
# RÉUTILISATION — il a fuité : toute la famille est révoquée et le joueur se reconnecte.
# La grâce couvre les requêtes PARALLÈLES d'une même page (elles partent toutes avec
# l'ancien cookie) : elles reçoivent un accès neuf, sans nouveau jeton.
#
# Chaîne courte : à la rotation de N, N-1 (remplacé hors grâce) est supprimé — la famille
# ne garde que le jeton vivant et celui qu'il remplace, qui suffit à détecter le vol
# (le voleur et le joueur présentent le MÊME jeton). Révoquer suit `precedent`/`remplace_par`,
# sans requête Mango. Les familles abandonnées périment par `expire_le`, ramassées à la
# connexion (`perimes`) — aucun tick de fond (CLAUDE.md § 5).
#
# Logique PURE, DB injectée, mute sans sauver — sauf `RafraichissementMiddleware`, qui
# reçoit ses fonctions d'écriture et persiste lui-même.
# ⚠️ `refresh:` est hors `_CACHEABLE_PREFIXES` (db/config.py) : doc d'état.

import hashlib
import os
import secrets
import time

from anyio import to_thread
from starlette.responses import Response

ACCES_MINUTES = 15
RAFRAICHISSEMENT_JOURS = 30
# Fenêtre pendant laquelle un jeton tout juste remplacé reste accepté (requêtes parallèles).
GRACE_SECONDES = 30
# Un accès qui expire dans moins de MARGE_SECONDES est renouvelé d'avance : la requête
# ne doit pas échouer entre le middleware et l'endpoint.
MARGE_SECONDES = 60
OCTETS_JETON = 32

COOKIE_ACCES = "auth_token"
COOKIE_RAFRAICHISSEMENT = "refresh_token"
# En-tête posé sur toute réponse servie SANS session valide : le client (scripts/session.js)
# renvoie alors vers /auth, quel que soit le code d'erreur de l'endpoint.
ENTETE_SESSION = "x-session"
SESSION_AUCUNE = "aucune"

PREFIXE = "refresh:"


def doc_id_jeton(jeton: str) -> str:
	return PREFIXE + hashlib.sha256(jeton.encode()).hexdigest()


def nouveau_jeton(user_id: str, *, famille: str = None, precedent: str = None,
		now: int = None, jeton_fn=None) -> tuple[str, dict]:
	"""(jeton en clair pour le cookie, doc à sauver). Sans `famille`, en ouvre une."""
	maintenant = int(now if now is not None else time.time())
	jeton = (jeton_fn or (lambda: secrets.token_urlsafe(OCTETS_JETON)))()
	doc = {
		"_id": doc_id_jeton(jeton),
		"type": "refresh",
		"user_id": user_id,
		"famille": famille or secrets.token_hex(8),
		"cree_le": maintenant,
		"expire_le": maintenant + RAFRAICHISSEMENT_JOURS * 86400,
	}
	if precedent:
		doc["precedent"] = precedent
	return jeton, doc


def _chaine(doc: dict, get_doc_fn) -> list[dict]:
	"""Le doc et tous ceux qu'il relie (en arrière par `precedent`, en avant par `remplace_par`)."""
	docs, vus = [doc], {doc["_id"]}
	for cle in ("precedent", "remplace_par"):
		courant = doc
		while courant.get(cle) and courant[cle] not in vus:
			suivant = get_doc_fn(courant[cle])
			if not suivant or suivant.get("type") != "refresh":
				break
			vus.add(suivant["_id"])
			docs.append(suivant)
			courant = suivant
	return docs


def _doc_valide(jeton: str, get_doc_fn) -> dict | None:
	if not jeton:
		return None
	doc = get_doc_fn(doc_id_jeton(jeton))
	if not doc or doc.get("type") != "refresh" or not doc.get("user_id"):
		return None
	return doc


def rafraichir(jeton: str, get_doc_fn, *, now: int = None, jeton_fn=None) -> dict:
	"""Échange un jeton de rafraîchissement. Rend
	`{"etat", "user_id", "jeton", "a_sauver", "a_supprimer"}` :
	  - `rotation`  : jeton neuf (`jeton`) ; sauver `a_sauver` DANS L'ORDRE (l'ancien d'abord :
	                  s'il est en conflit, une requête parallèle a gagné → traiter en `grace`) ;
	  - `grace`     : déjà remplacé il y a moins de GRACE_SECONDES — accès neuf, pas de jeton ;
	  - `reutilise` : remplacé depuis plus longtemps → famille entière dans `a_supprimer` ;
	  - `invalide`  : inconnu ou périmé (périmé : à supprimer)."""
	maintenant = int(now if now is not None else time.time())
	res = {"etat": "invalide", "user_id": None, "jeton": None, "a_sauver": [], "a_supprimer": []}
	doc = _doc_valide(jeton, get_doc_fn)
	if not doc:
		return res
	if maintenant >= int(doc.get("expire_le", 0)):
		res["a_supprimer"] = [doc]
		return res
	if doc.get("remplace_le") is not None:
		if maintenant - int(doc["remplace_le"]) <= GRACE_SECONDES:
			res.update(etat="grace", user_id=doc["user_id"])
		else:
			res.update(etat="reutilise", a_supprimer=_chaine(doc, get_doc_fn))
		return res
	neuf, doc_neuf = nouveau_jeton(doc["user_id"], famille=doc.get("famille"),
		precedent=doc["_id"], now=maintenant, jeton_fn=jeton_fn)
	doc["remplace_le"] = maintenant
	doc["remplace_par"] = doc_neuf["_id"]
	res.update(etat="rotation", user_id=doc["user_id"], jeton=neuf, a_sauver=[doc, doc_neuf])
	ancien = get_doc_fn(doc["precedent"]) if doc.get("precedent") else None
	if (ancien and ancien.get("type") == "refresh" and ancien.get("remplace_le") is not None
			and maintenant - int(ancien["remplace_le"]) > GRACE_SECONDES):
		res["a_supprimer"] = [ancien]
	return res


def revoquer(jeton: str, get_doc_fn) -> list[dict]:
	"""Docs à supprimer pour fermer la session portée par `jeton` (déconnexion)."""
	doc = _doc_valide(jeton, get_doc_fn)
	return _chaine(doc, get_doc_fn) if doc else []


def perimes(docs: list[dict], *, now: int = None) -> list[dict]:
	"""Parmi les `refresh:*` d'un joueur, ceux qui ont expiré (ramassés à la connexion)."""
	maintenant = int(now if now is not None else time.time())
	return [d for d in docs if maintenant >= int(d.get("expire_le", 0))]


# ── Cookies ─────────────────────────────────────────────────────────────────

def cookies_securises() -> bool:
	"""`Secure` dès que l'app est servie en HTTPS (même règle que le SessionMiddleware)."""
	return os.getenv("APP_BASE_URL", "").startswith("https://")


def poser_cookie_acces(response: Response, jeton: str) -> None:
	response.set_cookie(key=COOKIE_ACCES, value=jeton, max_age=ACCES_MINUTES * 60,
		httponly=True, samesite="lax", secure=cookies_securises())


def poser_cookie_rafraichissement(response: Response, jeton: str) -> None:
	response.set_cookie(key=COOKIE_RAFRAICHISSEMENT, value=jeton,
		max_age=RAFRAICHISSEMENT_JOURS * 86400,
		httponly=True, samesite="lax", secure=cookies_securises())


def effacer_cookies(response: Response) -> None:
	for cle in (COOKIE_ACCES, COOKIE_RAFRAICHISSEMENT):
		response.delete_cookie(key=cle, httponly=True, samesite="lax", secure=cookies_securises())


# ── Middleware ──────────────────────────────────────────────────────────────

def _lire_cookies(headers) -> dict:
	cookies = {}
	for nom, valeur in headers:
		if nom != b"cookie":
			continue
		for morceau in valeur.decode("latin-1").split(";"):
			cle, _, val = morceau.strip().partition("=")
			if cle:
				cookies.setdefault(cle, val)
	return cookies


def _remplacer_cookie(headers, cle: str, valeur: str | None) -> list:
	"""En-têtes de la requête où le cookie `cle` vaut `valeur` (retiré si None) : l'aval
	(`get_current_user`) lit ainsi l'accès NEUF dès cette requête."""
	cookies = {k: v for k, v in _lire_cookies(headers).items() if k != cle}
	if valeur is not None:
		cookies[cle] = valeur
	autres = [(n, v) for n, v in headers if n != b"cookie"]
	if cookies:
		autres.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode("latin-1")))
	return autres


class RafraichissementMiddleware:
	"""Renouvelle l'accès de façon TRANSPARENTE, pour les pages comme pour /api : un accès
	absent, périmé ou à moins de MARGE_SECONDES de l'être est rechargé depuis le jeton de
	rafraîchissement (rotation), réécrit dans la requête et reposé en cookie sur la réponse.
	Échec (jeton inconnu, périmé, réutilisé) : cookies effacés, requête servie sans session.
	Toute réponse sans session valide porte `x-session: aucune`.

	ASGI PUR, comme RequestDocCacheMiddleware (BaseHTTPMiddleware casserait les ContextVar).
	`ignorer` : préfixes de chemin servis tels quels (fichiers statiques)."""

	def __init__(self, app, *, decoder_acces, creer_acces, get_doc_fn, save_doc_fn,
			delete_doc_fn, ignorer=()):
		self.app = app
		# decoder_acces(jeton) -> `exp` (epoch) d'un accès valide, None sinon.
		self.decoder_acces = decoder_acces
		self.creer_acces = creer_acces
		self.get_doc = get_doc_fn
		self.save_doc = save_doc_fn
		self.delete_doc = delete_doc_fn
		self.ignorer = tuple(ignorer)

	def _echanger(self, jeton: str) -> dict:
		res = rafraichir(jeton, self.get_doc)
		for d in res["a_supprimer"]:
			self.delete_doc(d)
		if res["etat"] == "rotation":
			ancien, neuf = res["a_sauver"]
			if self.save_doc(ancien) is None:
				# Conflit : une requête parallèle a fait la rotation — elle pose le jeton neuf.
				res.update(etat="grace", jeton=None)
			elif self.save_doc(neuf) is None:
				res.update(etat="grace", jeton=None)
		return res

	async def __call__(self, scope, receive, send):
		if scope.get("type") != "http" or scope.get("path", "").startswith(self.ignorer):
			await self.app(scope, receive, send)
			return
		cookies = _lire_cookies(scope.get("headers") or [])
		acces = cookies.get(COOKIE_ACCES)
		rafr = cookies.get(COOKIE_RAFRAICHISSEMENT)
		exp = self.decoder_acces(acces) if acces else None
		session_ok = exp is not None
		a_poser = Response()
		modifie = False
		if rafr and (exp is None or exp - time.time() < MARGE_SECONDES):
			res = await to_thread.run_sync(self._echanger, rafr)
			if res["user_id"]:
				neuf = self.creer_acces({"user_id": res["user_id"]})
				poser_cookie_acces(a_poser, neuf)
				if res["jeton"]:
					poser_cookie_rafraichissement(a_poser, res["jeton"])
				scope = dict(scope, headers=_remplacer_cookie(scope.get("headers") or [], COOKIE_ACCES, neuf))
				session_ok = modifie = True
			else:
				# Accès encore valide (dans la marge) : on ne retire que le jeton refusé.
				if session_ok:
					a_poser.delete_cookie(key=COOKIE_RAFRAICHISSEMENT, httponly=True,
						samesite="lax", secure=cookies_securises())
				else:
					effacer_cookies(a_poser)
				modifie = True
		elif acces and not session_ok:
			effacer_cookies(a_poser)
			scope = dict(scope, headers=_remplacer_cookie(scope.get("headers") or [], COOKIE_ACCES, None))
			modifie = True
		ajouts = [(n, v) for n, v in a_poser.raw_headers if n == b"set-cookie"] if modifie else []

		async def envoyer(message):
			if message["type"] == "http.response.start":
				headers = list(message.get("headers") or [])
				# Une réponse qui pose DÉJÀ la session (connexion, déconnexion) a le dernier mot.
				deja = any(n.lower() == b"set-cookie" and v.split(b"=", 1)[0].strip().decode("latin-1")
					in (COOKIE_ACCES, COOKIE_RAFRAICHISSEMENT) for n, v in headers)
				if not deja:
					headers.extend(ajouts)
					if not session_ok:
						headers.append((ENTETE_SESSION.encode(), SESSION_AUCUNE.encode()))
				message = dict(message, headers=headers)
			await send(message)

		await self.app(scope, receive, envoyer)
