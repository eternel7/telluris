import contextvars
import logging
import os
import time
import couchdb2
import urllib.parse

SECRET_KEY = os.getenv("SECRET_KEY","17c94c78a18143754bsupersecret3a55a73fd47fcee0cf21ca59d2571f98")
ALGORITHM = "HS256"

DB_PASSWORD = os.getenv("COUCHDB_PASSWORD", "password_par_defaut_Non_mais_tente_meme_pas")
DB_USER = os.getenv("COUCHDB_USER", "admin_qui_pourra")

safe_password = urllib.parse.quote_plus(DB_PASSWORD)

DB_HOST = os.getenv("COUCHDB_HOST", "couchdb")
DB_PORT = os.getenv("COUCHDB_PORT", "5984")
DB_NAME = os.getenv("COUCHDB_DB", "telluris")

DB_URL = f"http://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}"
try:
	server = couchdb2.Server(DB_URL)
	db = server[DB_NAME]
	# Indexes voulus dans CouchDB
	db.put_index(fields=["type"], name="idx-tables", ddoc="design_tables")
	db.put_index(fields=["type", "user_id"], name="idx-tables-by-user", ddoc="design_tables")
	db.put_index(fields=["type", "giver"], name="idx-tables-by-giver", ddoc="design_tables")
	# `{"type": "relation", "character_id": …}` (relations_lieux_payload) était servi par
	# idx-tables (["type"]) : CouchDB lisait TOUS les docs relation de TOUS les joueurs pour
	# n'en garder qu'une poignée. Même mécanisme que les trois index ci-dessus, aucune
	# migration de données.
	db.put_index(fields=["type", "character_id"], name="idx-tables-by-character", ddoc="design_tables")
	# `{"type": "item", "sous_categorie": …}` (bois._trouver_item : 6 requêtes par remplissage
	# du tableau de quêtes, plus /api/couper) et `{"type": "lieu", "lieu_parent": …}`
	# (chasse.lieux_chasse_de, quetes.lieux_solidaires) étaient servis par idx-tables
	# (["type"]) : CouchDB lisait TOUS les items / TOUS les lieux et filtrait en mémoire.
	db.put_index(fields=["type", "sous_categorie"], name="idx-tables-by-souscat", ddoc="design_tables")
	db.put_index(fields=["type", "lieu_parent"], name="idx-tables-by-parent", ddoc="design_tables")
except Exception:
	# CouchDB injoignable (ex. pytest en local, hors conteneur) : l'import doit
	# rester possible pour les tests purs ; les helpers ci-dessous renvoient None.
	server = None
	db = None


# ── Cache de documents à portée REQUÊTE ───────────────────────────────────────────
# `get_doc` faisait un aller-retour HTTP vers CouchDB par appel, sans aucun cache. Une
# seule vente en faisait 200 à 350, dont l'immense majorité relisait le MÊME doc `item:*`
# (resolve_item_ref × taille de l'inventaire × nombre de payloads recalculés).
#
# Seuls les docs de CONTENU sont mémorisés (cf. _CACHEABLE_PREFIXES) : tout ce qui porte
# un état de partie est lu, muté et sauvé dans la même requête, donc jamais caché.
#
# ⚠️ Le ContextVar est posé par le MIDDLEWARE et nulle part ailleurs : `get_doc` ne fait
# que MUTER l'objet stocké. Un endpoint `def` tourne dans le threadpool avec une COPIE du
# contexte — la copie partage l'objet, donc les mutations portent ; un `set()` fait depuis
# le thread, lui, serait perdu.

_db_logger = logging.getLogger("telluris.db")

# Kill-switch (A/B et prod). Coupe la MÉMORISATION, pas l'instrumentation : les compteurs
# restent posés pour que le relevé de référence soit comparable.
_CACHE_ENABLED = os.getenv("TELLURIS_DOC_CACHE", "1") != "0"

# Docs de CONTENU : écrits uniquement par les écrans d'administration, jamais mutés au
# cours d'une requête de jeu. Tout ce qui porte un état de partie en est EXCLU
# (character:, aventurier:, monture:, lieu:, relation:, combat:, user:, quete:) — ces
# docs-là sont lus, mutés et sauvés dans la même requête. `str.startswith` accepte un
# tuple → un seul test ; ajouter un préfixe reste une décision par type.
_CACHEABLE_PREFIXES = ("item:", "espece:", "profil:", "recette:", "sort:",
					   "competence:", "rules:", "animation:", "donjon:", "pnj:", "link:",
					   # `zone::coeur_ville`… : définitions de zones d'influence, écrites par
					   # /api/zones (donc couvertes par l'invalidation de save_doc) et jamais
					   # mutées en jeu. Lues par `load_zone_defs_for_lieu` à chaque événement
					   # de zone et à chaque résolution de grade d'une chasse.
					   "zone:")
# ⚠️ `lieu:` reste EXCLU, et ce n'est PAS un oubli : le cache rend une copie de SURFACE, or
# les mutations d'un doc lieu sont IMBRIQUÉES (`stock_vente[i]["qty"]`, `stock_matieres[cle]`)
# — `buy_item` ou `tick_atelier` empoisonneraient le mémo. Là où un gros doc lieu est relu
# plusieurs fois dans une même passe, c'est à l'appelant de mémoïser (cf. `_cached_getter`).


class _RequestDocCache:
	__slots__ = ("docs", "gets", "hits", "finds", "saves")

	def __init__(self):
		self.docs = {}
		self.gets = self.hits = self.finds = self.saves = 0


_doc_cache = contextvars.ContextVar("telluris_doc_cache", default=None)


class RequestDocCacheMiddleware:
	"""Middleware ASGI PUR (aucun import FastAPI/Starlette : le protocole ASGI n'est qu'une
	signature `async def __call__(scope, receive, send)`).

	⚠️ Pur et NON `@app.middleware("http")` : `BaseHTTPMiddleware` exécute l'aval dans une
	tâche anyio distincte, ce qui casserait la propagation du ContextVar.

	Le cache est COUPÉ sur `/admin` : `import-bulk` lit **et** écrit des docs de contenu
	dans la même requête, dans un générateur qui tourne pendant tout le streaming — un même
	`_id` présent deux fois relirait un `_rev` périmé (409), et des milliers de docs
	seraient retenus en mémoire."""

	def __init__(self, app):
		self.app = app

	async def __call__(self, scope, receive, send):
		if scope.get("type") != "http" or scope.get("path", "").startswith("/admin"):
			await self.app(scope, receive, send)
			return
		cache = _RequestDocCache()
		token = _doc_cache.set(cache)
		debut = time.perf_counter()
		try:
			await self.app(scope, receive, send)
		finally:
			_doc_cache.reset(token)
			# Une requête sans aucun accès base (fichier statique) n'a rien à raconter.
			if cache.gets or cache.finds or cache.saves:
				_db_logger.info(
					"%s %s — %d ms | get:%d hit:%d find:%d save:%d",
					scope.get("method", ""), scope.get("path", ""),
					int((time.perf_counter() - debut) * 1000),
					cache.gets, cache.hits, cache.finds, cache.saves,
				)


def _db_get(doc_id: str) -> dict | None:
	"""Lecture brute, sans cache — chemin historique de `get_doc`."""
	try:
		return db.get(doc_id)
	except Exception:
		return None


def get_doc(doc_id: str) -> dict | None:
	cache = _doc_cache.get()
	if cache is None:
		# Tests purs, scripts dev/*, startup : chemin STRICTEMENT identique à avant.
		return _db_get(doc_id)
	cache.gets += 1
	if not _CACHE_ENABLED or not doc_id or not str(doc_id).startswith(_CACHEABLE_PREFIXES):
		return _db_get(doc_id)
	memo = cache.docs.get(doc_id)
	if memo is not None:
		cache.hits += 1
		return dict(memo)
	doc = _db_get(doc_id)
	if doc is None:
		# ⚠️ PAS de cache négatif : `utils/combat._ensure_loot_item` lit `item:<espece>` et
		# le CRÉE s'il est absent — mémoriser l'absence ferait disparaître silencieusement
		# la carcasse fraîchement ramassée du sac (`_inventory_payload` filtre les None).
		return None
	cache.docs[doc_id] = doc
	# ⚠️ Copie de SURFACE, jamais l'exemplaire mémorisé : chaque appelant garde un dict à
	# lui, exactement comme avant, et le cache ne peut pas être empoisonné. `dict()` et non
	# `deepcopy` — les mutations de docs de contenu observées sont toutes de premier niveau
	# (resolve_item_ref écrase poids/item/nom/magies sur son propre dict(doc)), et copier en
	# profondeur `rules:races` à chaque appel coûterait cher pour rien.
	return dict(doc)

def save_doc(doc: dict) -> dict:
	# couchdb2 : db.put() ne RETOURNE rien (None) en cas de succès — il mute `doc`
	# en place (ajout/maj du _rev) — et LÈVE sur conflit (RevisionError) ou erreur.
	# On renvoie donc `doc` (avec son _rev à jour) comme marqueur de succès truthy,
	# et None uniquement si l'écriture a échoué, pour que les appelants puissent
	# tester `save_doc(...) is None`.
	cache = _doc_cache.get()
	if cache is not None:
		cache.saves += 1
		# Ceinture (l'exclusion /admin est la bretelle) : routers/bestiaire écrit des
		# `espece:*`/`profil:*` sous /api, donc dans le cache.
		cache.docs.pop((doc or {}).get("_id"), None)
	try:
		db.put(doc)
		return doc
	except Exception:
		return None

def find_docs(selector: dict, fields: list[str] = None, limit: int = 10_000) -> list[dict]:
	cache = _doc_cache.get()
	if cache is not None:
		cache.finds += 1
	try:
		if fields:
			result = db.find(selector, fields=fields, limit=limit)
		else:
			result = db.find(selector, limit=limit)
		return result["docs"]
	except Exception:
		return None

def delete_doc(doc: dict) -> None:
	cache = _doc_cache.get()
	if cache is not None:
		cache.saves += 1
		cache.docs.pop((doc or {}).get("_id"), None)
	try:
		return db.delete(doc)
	except Exception:
		return None

def dump_all_docs() -> list[dict]:
	"""Tous les documents de la base (dump complet, design docs inclus)."""
	try:
		return list(db)  # couchdb2 : itère sur _all_docs?include_docs=true
	except Exception:
		# Repli Mango « tout matcher » (n'inclut pas les _design).
		return find_docs({"_id": {"$gt": None}}, limit=1_000_000) or []
