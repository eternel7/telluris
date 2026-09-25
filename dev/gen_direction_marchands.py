#!/usr/bin/env python
# dev/gen_direction_marchands.py
# Permet de DEMANDER SON CHEMIN aux tenanciers génériques `pnj:marchand_*`.
#
# Le moteur sait déjà tout faire (service `direction` de `routers/pnj.py`, recherche pure
# `utils/transport.chercher_lieu_nomme`) ; ce qui manque à chaque tenancier, ce sont les MOTS :
# un choix d'accueil, le nœud où le joueur SAISIT le nom du lieu, et les trois réponses
# (trouvé / approchant / inconnu). Ce fichier n'ajoute QUE cela — identique pour tous : la
# réponse est entièrement calculée, aucun tenancier n'a de texte à lui.
#
# ⚠️ POURQUOI UN SCRIPT QUI RELIT LE DUMP (même raison que `dev/gen_escorte_marchands.py`) :
# `admin_import_bulk` fait un PUT COMPLET, jamais un merge. On RELIT donc les docs depuis le
# dump et on n'y injecte que le fragment de direction : régénérer est idempotent, et tout ce
# que la base a de particulier (escorte, lore de l'étable, retouches à la main) survit.
#
# Usage : python dev/gen_direction_marchands.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/direction_marchands_a_importer.json

import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260924-220941.json"

PREFIXE = "pnj:marchand_"
SORTIE = "jsons/direction_marchands_a_importer.json"

# Nœuds de résultat que `routers/pnj._resoudre_direction` va chercher par leur clé.
NOEUDS_DIRECTION = {
	"trouve": "direction_trouve",
	"proche": "direction_proche",
	"inconnu": "direction_inconnu",
}

# Sans condition : n'importe qui peut demander son chemin.
CHOIX_ACCUEIL_DIRECTION = [
	{"id": "direction", "label": "Vous sauriez m'indiquer un lieu ?", "next": "direction_demande"},
]

_SUITE = [
	{"id": "direction_encore", "label": "Et un autre lieu ?", "next": "direction_demande"},
	{"id": "direction_merci", "label": "Merci bien.", "next": "fin"},
]

NOEUDS_DIALOGUE_DIRECTION = {
	"direction_demande": {
		"texte": "« Je connais la ville comme ma poche, {prenom}. Quel lieu cherchez-vous ? »",
		"choix": [
			# `saisie` : le client affiche un champ texte, sa valeur part avec ce choix.
			{"id": "direction_chercher", "label": "Demander", "saisie": True,
			 "action": {"service": "direction"}},
			{"id": "direction_annuler", "label": "Laissez, ce n'est rien.", "next": "accueil"},
		],
	},
	"direction_trouve": {
		"texte": "« {lieu} ? C'est {direction}. Impossible de vous tromper. »",
		"choix": _SUITE,
	},
	"direction_proche": {
		"texte": "« “{recherche}” ? Connais pas. » Un temps de réflexion. "
				 "« Vous ne voulez pas plutôt dire {suggestions} ? »",
		"choix": _SUITE,
	},
	"direction_inconnu": {
		"texte": "« “{recherche}” ? » Une moue perplexe. "
				 "« Je ne connais rien de ce nom-là par ici, {prenom}. »",
		"choix": _SUITE,
	},
}


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def injecter(doc: dict) -> dict:
	"""Pose le fragment de direction sur un doc marchand relu en base. IDEMPOTENT : les nœuds
	sont écrasés par leur version de référence et les choix sont remplacés PAR LEUR ID —
	relancer ce script deux fois ne duplique rien."""
	doc = json.loads(json.dumps(doc))          # copie profonde : on ne mute pas le dump

	services = doc.setdefault("services", {})
	services.setdefault("direction", {})["noeuds"] = dict(NOEUDS_DIRECTION)

	dialogue = doc.setdefault("dialogue", {})
	noeuds = dialogue.setdefault("noeuds", {})
	for nid, contenu in NOEUDS_DIALOGUE_DIRECTION.items():
		noeuds[nid] = json.loads(json.dumps(contenu))

	accueil = noeuds.get(dialogue.get("noeud_depart") or "accueil")
	if accueil is None:
		raise SystemExit(f"{doc['_id']} : pas de nœud d'accueil, fragment non posable.")
	nouveaux = {c["id"] for c in CHOIX_ACCUEIL_DIRECTION}
	# Réinséré JUSTE AVANT le choix de sortie : « Je ne faisais que passer » reste la dernière
	# ligne de la liste, c'est la porte de sortie du joueur.
	restants = [c for c in accueil.get("choix") or [] if c.get("id") not in nouveaux]
	sorties = [c for c in restants if (c.get("next") == "fin" and not c.get("condition"))]
	avant = [c for c in restants if c not in sorties]
	accueil["choix"] = avant + [json.loads(json.dumps(c)) for c in CHOIX_ACCUEIL_DIRECTION] + sorties
	return doc


def main() -> None:
	base = charger(SRC_DUMP)
	marchands = [d for d in base
				 if isinstance(d, dict) and str(d.get("_id", "")).startswith(PREFIXE)]
	if not marchands:
		raise SystemExit(f"Aucun doc `{PREFIXE}*` dans {SRC_DUMP} — dump périmé ?")
	docs = [injecter(d) for d in sorted(marchands, key=lambda d: d["_id"])]
	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
	print(f"{len(docs)} tenanciers renseignent leur chemin -> {SORTIE}")


if __name__ == "__main__":
	main()
