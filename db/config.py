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