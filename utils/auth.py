from fastapi import Request
import jwt
from datetime import datetime, timedelta
from db.config import get_doc, save_doc, delete_doc, find_docs, SECRET_KEY, ALGORITHM
from utils import session

# Jeton d'ACCÈS court : la durée de la session vient du jeton de rafraîchissement
# (utils/session.py), renouvelé à chaque usage.
ACCESS_TOKEN_EXPIRE_MINUTES = session.ACCES_MINUTES

def create_access_token(data: dict):
	to_encode = data.copy()
	maintenant = datetime.utcnow()
	expire = maintenant + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
	to_encode.update({"exp": expire, "iat": maintenant})
	encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
	return encoded_jwt


def expiration_acces(token: str):
	"""`exp` (epoch) d'un jeton d'accès valide, None s'il est invalide ou périmé."""
	try:
		payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
	except jwt.PyJWTError:
		return None
	return payload.get("exp")


def ouvrir_session(response, user_id: str) -> None:
	"""Connexion : pose l'accès ET une nouvelle famille de rafraîchissement sur `response`.
	Ramasse au passage les jetons périmés du joueur (aucun tick de fond)."""
	for doc in session.perimes(find_docs({"type": "refresh", "user_id": user_id}) or []):
		delete_doc(doc)
	jeton, doc = session.nouveau_jeton(user_id)
	save_doc(doc)
	session.poser_cookie_acces(response, create_access_token({"user_id": user_id}))
	session.poser_cookie_rafraichissement(response, jeton)


def fermer_session(request: Request, response) -> None:
	"""Déconnexion : révoque la famille du jeton présenté et efface les cookies."""
	for doc in session.revoquer(request.cookies.get(session.COOKIE_RAFRAICHISSEMENT), get_doc):
		delete_doc(doc)
	session.effacer_cookies(response)


def revoquer_sessions(user_id: str) -> None:
	"""Toutes les sessions du joueur (changement de mot de passe)."""
	for doc in find_docs({"type": "refresh", "user_id": user_id}) or []:
		delete_doc(doc)


def get_current_user(request: Request):
	token = request.cookies.get(session.COOKIE_ACCES)
	if not token:
		return None

	try:
		payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
	except jwt.PyJWTError:
		return None

	user_id: str = payload.get("user_id")

	user_doc = get_doc(user_id)
	if not user_doc or user_doc is None:
		return None

	# clean up before share to any other function
	user_doc.pop("password", None)
	user_doc.pop("token", None)
	return user_doc
