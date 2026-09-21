"""utils/dump.py — format commun des dumps (exports, outils de dev/, générateurs)."""

import datetime
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import dump

NOW = datetime.datetime(2026, 9, 21, 18, 8, 55)
DOCS = [{"_id": "item:a"}, {"_id": "user:x@y.z", "hash": "h"}, {"_id": "_design/i"}]


def test_payload_retire_les_users_sauf_demande():
	p = dump.payload(DOCS, NOW)
	assert [d["_id"] for d in p["docs"]] == ["item:a", "_design/i"]
	assert p["doc_count"] == 2 and p["db"] == "telluris"
	assert p["exported_at"] == "2026-09-21T18:08:55Z"
	assert dump.payload(DOCS, NOW, avec_users=True)["doc_count"] == len(DOCS)


def test_ecrire_dump_frais(tmp_path):
	rel = dump.ecrire_dump_frais(str(tmp_path), lambda: DOCS, NOW)
	assert rel == "jsons/telluris-dump-20260921-180855.json"
	data = json.loads((tmp_path / rel).read_text(encoding="utf-8"))
	assert data["doc_count"] == 2
	assert dump.charger_docs(str(tmp_path / rel)) == data["docs"]


def test_dump_vide_refuse(tmp_path):
	with pytest.raises(RuntimeError):
		dump.ecrire_dump_frais(str(tmp_path), lambda: [], NOW)
