"""Session : jeton d'accès court + jeton de rafraîchissement à rotation (utils/session.py).

Logique pure (rotation, grâce, réutilisation, révocation, péremption) sur une base en
mémoire, puis le middleware ASGI de bout en bout avec une application factice.
"""

import asyncio
import itertools

from utils import session

T0 = 1_700_000_000


class Base:
	def __init__(self):
		self.docs = {}

	def get(self, doc_id):
		d = self.docs.get(doc_id)
		return dict(d) if d else None

	def save(self, doc):
		self.docs[doc["_id"]] = dict(doc)
		return doc

	def delete(self, doc):
		self.docs.pop(doc["_id"], None)


def _jetons():
	compteur = itertools.count()
	return lambda: f"jeton{next(compteur)}"


def _ouvrir(base, jeton_fn, now=T0):
	jeton, doc = session.nouveau_jeton("user:a", now=now, jeton_fn=jeton_fn)
	base.save(doc)
	return jeton


def _appliquer(base, res):
	for d in res["a_supprimer"]:
		base.delete(d)
	for d in res["a_sauver"]:
		base.save(d)


def test_le_jeton_ne_vit_en_base_que_par_son_empreinte():
	base, jf = Base(), _jetons()
	jeton = _ouvrir(base, jf)
	(doc_id,) = base.docs
	assert jeton not in doc_id and doc_id == session.doc_id_jeton(jeton)


def test_rotation_remplace_le_jeton_dans_la_meme_famille():
	base, jf = Base(), _jetons()
	j0 = _ouvrir(base, jf)
	res = session.rafraichir(j0, base.get, now=T0 + 60, jeton_fn=jf)
	assert res["etat"] == "rotation" and res["user_id"] == "user:a"
	assert res["jeton"] and res["jeton"] != j0
	ancien, neuf = res["a_sauver"]
	assert ancien["remplace_par"] == neuf["_id"] and neuf["precedent"] == ancien["_id"]
	assert neuf["famille"] == ancien["famille"]
	assert neuf["expire_le"] == T0 + 60 + session.RAFRAICHISSEMENT_JOURS * 86400


def test_un_jeton_remplace_reste_accepte_pendant_la_grace_sans_nouveau_jeton():
	base, jf = Base(), _jetons()
	j0 = _ouvrir(base, jf)
	_appliquer(base, session.rafraichir(j0, base.get, now=T0 + 60, jeton_fn=jf))
	res = session.rafraichir(j0, base.get, now=T0 + 60 + session.GRACE_SECONDES, jeton_fn=jf)
	assert res["etat"] == "grace" and res["user_id"] == "user:a" and res["jeton"] is None
	assert not res["a_sauver"] and not res["a_supprimer"]


def test_reutilisation_hors_grace_revoque_toute_la_famille():
	base, jf = Base(), _jetons()
	j0 = _ouvrir(base, jf)
	r1 = session.rafraichir(j0, base.get, now=T0 + 60, jeton_fn=jf)
	_appliquer(base, r1)
	# Le voleur (ou le joueur) rejoue j0 bien après : tout tombe, j1 compris.
	res = session.rafraichir(j0, base.get, now=T0 + 60 + session.GRACE_SECONDES + 1, jeton_fn=jf)
	assert res["etat"] == "reutilise" and res["user_id"] is None
	_appliquer(base, res)
	assert base.docs == {}
	assert session.rafraichir(r1["jeton"], base.get, now=T0 + 200)["etat"] == "invalide"


def test_la_chaine_reste_courte():
	base, jf = Base(), _jetons()
	jeton, now = _ouvrir(base, jf), T0
	for _ in range(6):
		now += session.ACCES_MINUTES * 60
		res = session.rafraichir(jeton, base.get, now=now, jeton_fn=jf)
		_appliquer(base, res)
		jeton = res["jeton"]
	# Le jeton vivant et celui qu'il remplace (détection du vol) : rien de plus.
	assert len(base.docs) == 2


def test_jeton_inconnu_ou_perime():
	base, jf = Base(), _jetons()
	assert session.rafraichir("", base.get)["etat"] == "invalide"
	assert session.rafraichir("nimporte", base.get)["etat"] == "invalide"
	j0 = _ouvrir(base, jf)
	res = session.rafraichir(j0, base.get, now=T0 + session.RAFRAICHISSEMENT_JOURS * 86400)
	assert res["etat"] == "invalide" and len(res["a_supprimer"]) == 1


def test_revoquer_ferme_la_famille_et_perimes_trie():
	base, jf = Base(), _jetons()
	j0 = _ouvrir(base, jf)
	r1 = session.rafraichir(j0, base.get, now=T0 + 60, jeton_fn=jf)
	_appliquer(base, r1)
	for d in session.revoquer(r1["jeton"], base.get):
		base.delete(d)
	assert base.docs == {}
	vieux = {"expire_le": T0}
	jeune = {"expire_le": T0 + 10}
	assert session.perimes([vieux, jeune], now=T0 + 1) == [vieux]


# ── Middleware ──────────────────────────────────────────────────────────────

def _middleware(base, acces_valides, jf):
	vus = {}

	async def app(scope, receive, send):
		vus["cookies"] = session._lire_cookies(scope["headers"])
		await send({"type": "http.response.start", "status": 200, "headers": []})
		await send({"type": "http.response.body", "body": b""})

	mw = session.RafraichissementMiddleware(
		app,
		decoder_acces=lambda t: acces_valides.get(t),
		creer_acces=lambda data: "acces-" + data["user_id"],
		get_doc_fn=base.get, save_doc_fn=base.save, delete_doc_fn=base.delete,
		ignorer=("/scripts/",),
	)
	return mw, vus


def _requete(mw, path="/api/x", cookies=None):
	entetes = []
	if cookies:
		entetes.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
	recus = []

	async def send(message):
		recus.append(message)

	async def receive():
		return {"type": "http.request", "body": b""}

	asyncio.run(mw({"type": "http", "path": path, "headers": entetes}, receive, send))
	return recus[0]["headers"]


def _set_cookies(headers):
	return {v.split(b"=", 1)[0].decode(): v.decode() for n, v in headers if n == b"set-cookie"}


def test_middleware_recharge_un_acces_absent_depuis_le_rafraichissement():
	base, jf = Base(), _jetons()
	j0 = _ouvrir(base, jf, now=int(__import__("time").time()))
	mw, vus = _middleware(base, {}, jf)
	headers = _requete(mw, cookies={"refresh_token": j0})
	poses = _set_cookies(headers)
	assert "acces-user:a" in poses["auth_token"]
	assert "refresh_token" in poses and j0 not in poses["refresh_token"]
	# L'aval voit l'accès NEUF dès cette requête.
	assert vus["cookies"]["auth_token"] == "acces-user:a"
	assert (b"x-session", b"aucune") not in headers


def test_middleware_sans_session_signale_et_efface():
	base, jf = Base(), _jetons()
	mw, vus = _middleware(base, {}, jf)
	headers = _requete(mw, cookies={"auth_token": "perime", "refresh_token": "inconnu"})
	assert (b"x-session", b"aucune") in headers
	poses = _set_cookies(headers)
	assert set(poses) == {"auth_token", "refresh_token"}
	assert all("Max-Age=0" in v for v in poses.values())


def test_middleware_acces_valide_ne_touche_a_rien():
	base, jf = Base(), _jetons()
	exp = int(__import__("time").time()) + 600
	mw, vus = _middleware(base, {"bon": exp}, jf)
	headers = _requete(mw, cookies={"auth_token": "bon"})
	assert headers == []


def test_middleware_ignore_les_fichiers_statiques():
	base, jf = Base(), _jetons()
	mw, vus = _middleware(base, {}, jf)
	assert _requete(mw, path="/scripts/session.js") == []
