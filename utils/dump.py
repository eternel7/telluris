"""Dump complet de la base — SOURCE UNIQUE du format et de l'écriture d'un dump frais.

Trois consommateurs, un seul code :
- `/admin/exports` (téléchargement, avec ou sans `user:*`) ;
- le lanceur de `dev/` (`main._preparer_outil`, outils `dump_frais`) ;
- les générateurs `dev/gen_*.py` lancés à la main dans le conteneur, qui se régénèrent leur
  propre dump au lieu de relire un fichier figé (`ecrire_dump_frais`).

⚠️ Un générateur relit un DUMP pour n'injecter que son champ (CLAUDE.md §11) : relu sur un dump
périmé, son import (PUT complet) écraserait les retouches faites depuis. D'où le dump FRAIS.

⚠️ Le dump ÉCRIT dans le dépôt exclut toujours les `user:*` (empreintes de mot de passe, jetons
`reset:*`) : il est destiné à être committé. Seul le téléchargement complet les garde, pour
restaurer à l'identique.

`db.config` est importé PARESSEUSEMENT (`dump_fn` injectable) : le module reste importable et
testable sans base.
"""

import datetime
import json
import os

PREFIXE_USER = "user:"


def maintenant() -> datetime.datetime:
	"""UTC naïf — même convention que les exports historiques (`isoformat() + "Z"`)."""
	return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def payload(docs, now, avec_users: bool = False) -> dict:
	"""`{"db","exported_at","doc_count","docs"}`. `avec_users=False` retire les `user:*`."""
	retenus = [d for d in (docs or [])
			   if avec_users or not str((d or {}).get("_id", "")).startswith(PREFIXE_USER)]
	return {
		"db": "telluris",
		"exported_at": now.isoformat() + "Z",
		"doc_count": len(retenus),
		"docs": retenus,
	}


def nom_fichier(now) -> str:
	return f"telluris-dump-{now:%Y%m%d-%H%M%S}.json"


def _dump_all_docs():
	from db.config import dump_all_docs   # paresseux : aucune connexion à l'import du module
	return dump_all_docs()


def ecrire_dump_frais(racine: str, dump_fn=None, now=None) -> str:
	"""Écrit `jsons/telluris-dump-<horodatage>.json` (sans `user:*`) sous `racine` et rend son
	chemin RELATIF à `racine`. Lève si la base est vide ou injoignable : un générateur qui
	tournerait sur zéro doc écrirait un lot vide sans rien signaler."""
	now = now or maintenant()
	docs = (dump_fn or _dump_all_docs)()
	if not docs:
		raise RuntimeError("dump vide — CouchDB injoignable ?")
	rel = "jsons/" + nom_fichier(now)
	chemin = os.path.join(racine, rel)
	os.makedirs(os.path.dirname(chemin), exist_ok=True)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(payload(docs, now), f, ensure_ascii=False, indent=2)
	return rel


def charger_docs(chemin: str) -> list:
	"""Docs d'un dump ou d'un export admin : tableau nu, ou `{"docs": [...]}`."""
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data
