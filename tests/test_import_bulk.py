"""main.admin_import_bulk — import en masse de /admin, base simulée (`get_doc` / `save_doc`).

Verrouille la suppression par lot : un `{"_id", "_deleted": true}` efface un doc présent (son
`_rev` réattaché) et, sur un doc DÉJÀ absent, compte comme réussi sans écrire — avant, CouchDB
refusait l'écriture sans `_rev` et le ré-import d'un lot déjà appliqué annonçait de faux échecs.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402

ADMIN = {"_id": "user:admin", "admin": 1}


def _importer(monkeypatch, base, docs):
	"""(événement `done`, écritures) d'un import de `docs` sur `base` ({_id: doc})."""
	ecrits = []

	def save_doc(doc):
		ecrits.append(dict(doc))
		if doc.get("_deleted"):
			base.pop(doc["_id"], None)
		else:
			base[doc["_id"]] = dict(doc, _rev="2-x")
		return doc

	monkeypatch.setattr(main, "get_doc", lambda _id: base.get(_id))
	monkeypatch.setattr(main, "save_doc", save_doc)
	reponse = main.admin_import_bulk(ADMIN, docs)

	async def lire():
		return [ligne async for ligne in reponse.body_iterator]

	lignes = [json.loads(l) for morceau in asyncio.run(lire()) for l in morceau.splitlines() if l]
	return next(e for e in lignes if e["event"] == "done"), ecrits


def test_suppression_d_un_doc_present_rev_reattache(monkeypatch):
	base = {"link:a": {"_id": "link:a", "_rev": "3-abc", "type": "connection"}}
	fin, ecrits = _importer(monkeypatch, base, [{"_id": "link:a", "_deleted": True}])
	assert (fin["imported"], fin["failed"]) == (1, 0)
	assert ecrits == [{"_id": "link:a", "_deleted": True, "_rev": "3-abc"}]
	assert "link:a" not in base


def test_suppression_d_un_doc_deja_absent_reussie_sans_ecriture(monkeypatch):
	fin, ecrits = _importer(monkeypatch, {}, [{"_id": "link:a", "_deleted": True},
		{"_id": "link:b", "type": "connection"}])
	assert (fin["imported"], fin["failed"], fin["errors"]) == (2, 0, [])
	assert [d["_id"] for d in ecrits] == ["link:b"]  # rien d'écrit pour la suppression


def test_echec_d_ecriture_toujours_compte(monkeypatch):
	monkeypatch.setattr(main, "get_doc", lambda _id: None)
	monkeypatch.setattr(main, "save_doc", lambda doc: None)
	reponse = main.admin_import_bulk(ADMIN, [{"_id": "link:c", "type": "connection"}])

	async def lire():
		return [ligne async for ligne in reponse.body_iterator]

	fin = [json.loads(l) for m in asyncio.run(lire()) for l in m.splitlines() if l][-1]
	assert (fin["imported"], fin["failed"]) == (0, 1)
