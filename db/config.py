import os
import couchdb2
import urllib.parse

SECRET_KEY = os.getenv("SECRET_KEY","17c94c78a18143754bsupersecret3a55a73fd47fcee0cf21ca59d2571f98")
ALGORITHM = "HS256"

DB_PASSWORD = os.getenv("COUCHDB_PASSWORD", "password_par_defaut_Non_mais_tente_meme_pas")
DB_USER = os.getenv("COUCHDB_USER", "admin_qui_pourra")

safe_password = urllib.parse.quote_plus(DB_PASSWORD)

DB_URL = f"http://{DB_USER}:{safe_password}@couchdb:5984"
server = couchdb2.Server(DB_URL)
db = server["telluris"]

async def get_doc(doc_id: str) -> dict | None:
	try:
		return await db.get(doc_id)
	except Exception:
		return None

async def save_doc(doc: dict) -> dict:
	return await db.put(doc)

async def find_docs(selector: dict, limit: int = 1000, fields: list[str] =["_id", "type"]) -> list[dict]:
	result = await db.find(selector, limit=limit, fields=fields)
	return result["docs"]