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

# Indexes voulus dans CouchDB
db.put_index(fields=["type"], name="idx-tables", ddoc="design_tables")
db.put_index(fields=["type", "user_id"], name="idx-tables-by-user", ddoc="design_tables")


def get_doc(doc_id: str) -> dict | None:
	try:
		return db.get(doc_id)
	except Exception:
		return None

def save_doc(doc: dict) -> dict:
	try:
		return db.put(doc)
	except Exception:
		return None

def find_docs(selector: dict, fields: list[str] = None, limit: int = 10_000) -> list[dict]:
	try:
		if fields:
			result = db.find(selector, fields=fields, limit=limit)
		else:
			result = db.find(selector, limit=limit)
		return result["docs"]
	except Exception:
		return None
		
def delete_doc(doc: dict) -> None:
	try:
		return db.delete(doc)
	except Exception:
		return None