import contextvars
import logging
import json
import os
import pickle
import threading
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
	# `{"type": "message", "lieu": …}` et `{"type": "table", "lieu": …}` (la salle commune
	# d'une auberge, SONDÉE toutes les quelques secondes tant qu'un joueur y est) : sans cet
	# index, idx-tables (["type"]) ferait lire à CouchDB TOUS les messages du monde à chaque
	# rafraîchissement. Même faute, même remède que les cinq index ci-dessus.
	db.put_index(fields=["type", "lieu"], name="idx-tables-by-lieu", ddoc="design_tables")
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
# (character:, aventurier:, monture:, lieu:, relation:, combat:, user:, quete:, reset:)
# — ces docs-là sont lus, mutés et sauvés dans la même requête. `str.startswith` accepte un
# tuple → un seul test ; ajouter un préfixe reste une décision par type.
_CACHEABLE_PREFIXES = ("item:", "espece:", "profil:", "recette:", "sort:",
					   "competence:", "rules:", "animation:", "donjon:", "pnj:", "link:",
					   # `zone::coeur_ville`… : définitions de zones d'influence, écrites par
					   # /api/zones (donc couvertes par l'invalidation de save_doc) et jamais
					   # mutées en jeu. Lues par `load_zone_defs_for_lieu` à chaque événement
					   # de zone et à chaque résolution de grade d'une chasse.
					   "zone:")
# ⚠️ Les docs d'ÉTAT (lieu:, character:, user:, relation:…) n'en sont PAS : le cache de contenu
# rend une copie de SURFACE, or leurs mutations sont IMBRIQUÉES (`stock_vente[i]["qty"]`,
# `stock_matieres[cle]`) — `buy_item` ou `tick_atelier` empoisonneraient le mémo.
#
# Ils ont leur propre mémo, de REQUÊTE SEULE, rendu en COPIE PROFONDE (pickle) : chaque lecture
# rend exactement ce qu'aurait rendu CouchDB — un appelant qui mute son exemplaire sans le
# sauver ne touche pas le mémo, et `save_doc` l'invalide (la lecture suivante voit le `_rev`
# neuf). Né des relectures en boucle (225 lectures de 3 lieux par achat, `user:3/1` et
# `character:2/1` à chaque action au relevé du 09/10). Jamais au cache de process : l'état
# bouge sous les autres requêtes. Seule différence avec une relecture base : une écriture
# faite par une AUTRE requête pendant celle-ci n'est pas vue — le `save_doc` suivant de cet
# exemplaire part en 409 au lieu d'écraser l'autre écriture.

# ── Cache de CONTENU à portée PROCESS ──────────────────────────────────────────────
# Le cache de requête faisait relire à CHAQUE requête les mêmes docs de contenu (un pas :
# item:30 zone:13 competence:11 ≈ 550 ms sur 700, à ~10 ms l'aller-retour au relevé du
# 09/10). Ils ne bougent que par l'admin, dont toutes les écritures passent par `save_doc` /
# `delete_doc`, qui les invalident ici. Le TTL n'est qu'un filet pour une édition faite HORS
# de l'app (Fauxton) : elle met au plus `_PROCESS_TTL` à se voir en jeu.
# Stockés PICKLÉS : chaque requête en reçoit sa copie profonde, puis le cache de requête
# reprend son contrat habituel — une mutation imbriquée ne peut pas déborder de la requête
# qui l'a faite (exactement comme avant). Lus seulement DANS une requête de jeu : /admin,
# tests purs et scripts lisent toujours la base.
_PROCESS_TTL = float(os.getenv("TELLURIS_PROCESS_CACHE_TTL", "300"))
_process_cache: dict = {}		# _id -> (instant, bytes picklés)
# Résultats de `find_docs` sur un `type` de CONTENU (le catalogue des 1 014 compétences, des
# 204 sorts : relus et retransférés à CHAQUE achat par la fiche). Clé = sélecteur + champs +
# limite. Vidé EN ENTIER à toute écriture d'un doc de contenu : un nouvel item ou sort change
# le résultat de requêtes qu'on ne sait pas énumérer.
_process_finds: dict = {}		# clé -> (instant, bytes picklés)
_TYPES_CONTENU = frozenset(p.rstrip(":") for p in _CACHEABLE_PREFIXES)
_process_lock = threading.Lock()
# Incrémenté à chaque invalidation : une lecture base commencée AVANT une écriture ne doit pas
# reposer au cache la version qu'elle a lue (elle est peut-être déjà périmée).
_process_gen = 0


def reset_cache_process() -> None:
	"""Vide le cache de contenu à portée process (tests, import massif)."""
	global _process_gen
	with _process_lock:
		_process_cache.clear()
		_process_finds.clear()
		_process_gen += 1


def _invalider_process(doc_id) -> None:
	global _process_gen
	if not doc_id:
		return
	with _process_lock:
		_process_cache.pop(doc_id, None)
		if str(doc_id).startswith(_CACHEABLE_PREFIXES):
			_process_finds.clear()
		_process_gen += 1


class _RequestDocCache:
	__slots__ = ("docs", "profonds", "gets", "hits", "finds", "saves", "db_s", "lus")

	def __init__(self):
		self.docs = {}
		# _id -> bytes picklés des docs d'état, copie profonde à chaque lecture.
		self.profonds = {}
		self.gets = self.hits = self.finds = self.saves = 0
		# Temps passé dans les allers-retours CouchDB : sépare, dans le relevé, l'attente
		# base du calcul Python (deux remèdes différents).
		self.db_s = 0.0
		# Lectures parties en base, par `_id` : dit QUELS docs coûtent (et lesquels sont relus).
		self.lus = {}


def _compter_db(debut: float) -> None:
	"""Ajoute au relevé de la requête le temps d'un aller-retour base commencé à `debut`."""
	cache = _doc_cache.get()
	if cache is not None:
		cache.db_s += time.perf_counter() - debut


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
					"%s %s — %d ms (base %d ms) | get:%d hit:%d find:%d save:%d | lus %s",
					scope.get("method", ""), scope.get("path", ""),
					int((time.perf_counter() - debut) * 1000), int(cache.db_s * 1000),
					cache.gets, cache.hits, cache.finds, cache.saves, _resume_lus(cache.lus),
				)


def _resume_lus(lus: dict) -> str:
	"""`lieu:31/4 relation:12/1 …` — lectures en base / docs distincts, par préfixe, les plus
	coûteux d'abord. Lectures ≫ docs ⇒ un même doc relu : un mémo le paierait une fois."""
	par_prefixe: dict = {}
	for doc_id, n in lus.items():
		prefixe = str(doc_id).split(":", 1)[0] + ":"
		lectures, docs = par_prefixe.get(prefixe, (0, 0))
		par_prefixe[prefixe] = (lectures + n, docs + 1)
	ordre = sorted(par_prefixe.items(), key=lambda kv: -kv[1][0])
	return " ".join(f"{p}{l}/{d}" for p, (l, d) in ordre[:6]) or "-"


def _db_get(doc_id: str) -> dict | None:
	"""Lecture brute, sans cache — chemin historique de `get_doc`."""
	cache = _doc_cache.get()
	if cache is not None:
		cache.lus[doc_id] = cache.lus.get(doc_id, 0) + 1
	debut = time.perf_counter()
	try:
		return db.get(doc_id)
	except Exception:
		return None
	finally:
		_compter_db(debut)


def get_doc(doc_id: str) -> dict | None:
	cache = _doc_cache.get()
	if cache is None:
		# Tests purs, scripts dev/*, startup : chemin STRICTEMENT identique à avant.
		return _db_get(doc_id)
	cache.gets += 1
	if not _CACHE_ENABLED or not doc_id:
		return _db_get(doc_id)
	if not str(doc_id).startswith(_CACHEABLE_PREFIXES):
		return _get_doc_profond(cache, doc_id)
	memo = cache.docs.get(doc_id)
	if memo is not None:
		cache.hits += 1
		return dict(memo)
	doc = _get_doc_process(cache, doc_id)
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

def _get_doc_profond(cache: _RequestDocCache, doc_id: str) -> dict | None:
	"""Doc d'état mémoïsé pour la requête, rendu en copie profonde (cf. _CACHEABLE_PREFIXES)."""
	memo = cache.profonds.get(doc_id)
	if memo is not None:
		cache.hits += 1
		return pickle.loads(memo)
	doc = _db_get(doc_id)
	if doc is not None:
		# Instantané AVANT de rendre le doc : l'appelant peut le muter dès qu'il l'a.
		cache.profonds[doc_id] = pickle.dumps(doc, pickle.HIGHEST_PROTOCOL)
	return doc


def _get_doc_process(cache: _RequestDocCache, doc_id: str) -> dict | None:
	"""Doc de contenu depuis le cache de process, sinon la base (et l'y repose)."""
	now = time.monotonic()
	entree = _process_cache.get(doc_id)
	if entree is not None and now - entree[0] < _PROCESS_TTL:
		cache.hits += 1
		return pickle.loads(entree[1])
	gen = _process_gen
	doc = _db_get(doc_id)
	if doc is not None:
		blob = pickle.dumps(doc, pickle.HIGHEST_PROTOCOL)
		with _process_lock:
			if gen == _process_gen:
				_process_cache[doc_id] = (now, blob)
	return doc


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
		cache.profonds.pop((doc or {}).get("_id"), None)
	debut = time.perf_counter()
	try:
		db.put(doc)
		return doc
	except Exception:
		return None
	finally:
		_compter_db(debut)
		# HORS du `if` : les écritures de /admin (import massif, éditeurs) tournent sans
		# contexte de requête et doivent quand même périmer le cache de process. APRÈS le
		# `put` : une lecture concurrente commencée avant voit la génération bouger et ne
		# repose pas l'ancienne version.
		_invalider_process((doc or {}).get("_id"))

def save_docs(docs: list) -> list[bool]:
	"""Écriture GROUPÉE (`_bulk_docs`) : un seul aller-retour pour N docs, là où N `save_doc`
	en coûtaient N (74 écritures pour une nuit d'auberge au relevé du 09/10). Même contrat doc
	par doc que `save_doc` : le `_rev` neuf est posé sur le dict, les caches sont invalidés, et
	le résultat dit, dans l'ordre, lesquels sont passés (False = conflit ou erreur). ⚠️ Pas de
	transaction : un échec n'annule pas les autres — réservé aux docs ANNEXES, best-effort."""
	docs = [d for d in (docs or []) if d]
	if not docs:
		return []
	cache = _doc_cache.get()
	if cache is not None:
		cache.saves += 1
		for d in docs:
			cache.docs.pop(d.get("_id"), None)
			cache.profonds.pop(d.get("_id"), None)
	debut = time.perf_counter()
	try:
		resultats = db.update(docs)
	except Exception:
		return [False] * len(docs)
	finally:
		_compter_db(debut)
		for d in docs:
			_invalider_process(d.get("_id"))
	ok = []
	for doc, res in zip(docs, resultats):
		passe = bool(res and res[0])
		if passe:
			doc["_rev"] = res[2]
		ok.append(passe)
	return ok + [False] * (len(docs) - len(ok))

def _cle_find_contenu(selector, fields, limit) -> str | None:
	"""Clé du cache de process pour une recherche sur un `type` de contenu, sinon None."""
	if not _CACHE_ENABLED or not isinstance(selector, dict) 			or not isinstance(selector.get("type"), str) or selector["type"] not in _TYPES_CONTENU:
		return None
	try:
		return json.dumps([selector, fields, limit], sort_keys=True, ensure_ascii=False)
	except (TypeError, ValueError):
		return None


def find_docs(selector: dict, fields: list[str] = None, limit: int = 10_000) -> list[dict]:
	cache = _doc_cache.get()
	if cache is not None:
		cache.finds += 1
		cle = _cle_find_contenu(selector, fields, limit)
		if cle is not None:
			return _find_contenu(cache, cle, selector, fields, limit)
	return _db_find(selector, fields, limit)


def _find_contenu(cache: _RequestDocCache, cle: str, selector, fields, limit) -> list[dict] | None:
	"""Recherche de contenu servie par le cache de process (copie profonde par appel)."""
	now = time.monotonic()
	entree = _process_finds.get(cle)
	if entree is not None and now - entree[0] < _PROCESS_TTL:
		cache.hits += 1
		return pickle.loads(entree[1])
	gen = _process_gen
	docs = _db_find(selector, fields, limit)
	if docs is not None:
		blob = pickle.dumps(docs, pickle.HIGHEST_PROTOCOL)
		with _process_lock:
			if gen == _process_gen:
				_process_finds[cle] = (now, blob)
	return docs


def _db_find(selector: dict, fields: list[str] = None, limit: int = 10_000) -> list[dict] | None:
	"""Recherche brute, sans cache — chemin historique de `find_docs`."""
	debut = time.perf_counter()
	try:
		if fields:
			result = db.find(selector, fields=fields, limit=limit)
		else:
			result = db.find(selector, limit=limit)
		return result["docs"]
	except Exception:
		return None
	finally:
		_compter_db(debut)

def delete_doc(doc: dict) -> None:
	cache = _doc_cache.get()
	if cache is not None:
		cache.saves += 1
		cache.docs.pop((doc or {}).get("_id"), None)
		cache.profonds.pop((doc or {}).get("_id"), None)
	try:
		return db.delete(doc)
	except Exception:
		return None
	finally:
		_invalider_process((doc or {}).get("_id"))

def dump_all_docs() -> list[dict]:
	"""Tous les documents de la base (dump complet, design docs inclus)."""
	try:
		return list(db)  # couchdb2 : itère sur _all_docs?include_docs=true
	except Exception:
		# Repli Mango « tout matcher » (n'inclut pas les _design).
		return find_docs({"_id": {"$gt": None}}, limit=1_000_000) or []
