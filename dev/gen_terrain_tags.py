"""Génère l'import qui pose `terrain_tags` sur les docs `zone_influence`.

POURQUOI un script et pas un JSON écrit à la main : `admin_import_bulk` fait un PUT
COMPLET, jamais un merge — ajouter un champ oblige à reproduire le doc entier. On relit
donc l'export comme SOURCE UNIQUE et on n'y injecte que le champ ajouté, ce qui rend la
régénération IDEMPOTENTE : une retouche faite à la main en base survit à un nouvel
export, et réimporter ne peut rien annuler en silence.

`terrain_tags` = vocabulaire de DÉCOR (foret, ville, falaise…), lu par
`utils.combat.select_battle_map` pour choisir la battle map d'un combat. À NE PAS
CONFONDRE avec les `tags` d'une entrée de `table_evenements` qui, pour une entrée
`type:"combat"`, sont des noms de créatures (loup, brigand…) : c'est précisément cette
confusion qui faisait tirer la mine aux cristaux en pleine forêt.

Usage : python dev/gen_terrain_tags.py
"""

import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "jsons", "zone_influence_20260729-181825.json")
CIBLE = os.path.join(RACINE, "jsons", "zone_terrain_tags_a_importer.json")

# Orthographe alignée sur les tags des battle maps DÉJÀ en base (`foret`, `clariere` :
# sans accent). Un tag mal orthographié ne matche rien et retombe silencieusement sur le
# repli — c'est la seule erreur que ce fichier peut produire.
#
# Le vocabulaire est PROSPECTIF : `ville`, `marais`, `montagne`… ne correspondent à
# aucune carte aujourd'hui. Le repli de `select_battle_map` (aucun match → tirage
# uniforme sur le pool hors donjon) les protège, et l'import d'une future carte urbaine
# suffira à les activer sans toucher au code.
TERRAIN_TAGS = {
	# ── Urbain / civilisé ──────────────────────────────────────────────────────
	"zone::coeur_capitale": ["ville", "urbain", "rue", "place"],
	"zone::coeur_cite": ["ville", "urbain", "rue", "place"],
	"zone::coeur_ville": ["ville", "urbain", "rue", "place"],
	"zone::coeur_village": ["village", "rural", "place", "chemin"],
	"zone::coeur_hameau": ["village", "rural", "ferme", "chemin"],
	"zone::faubourg_hameau": ["rural", "ferme", "champ", "chemin"],
	"zone::faubourg_village": ["village", "rural", "faubourg", "chemin"],
	"zone::faubourg_ville": ["ville", "urbain", "faubourg", "ruelle"],
	"zone:faubourg": ["ville", "urbain", "faubourg", "ruelle"],
	"zone::quartier_bas_capitale": ["ville", "urbain", "ruelle", "taudis"],
	"zone::quartier_bas_cite": ["ville", "urbain", "ruelle", "taudis"],
	"zone::quartier_marchand_ville": ["ville", "urbain", "rue", "place", "marche"],
	"zone::quartier_noble_cite": ["ville", "urbain", "rue", "jardin"],
	"zone::quartier_politique_capitale": ["ville", "urbain", "palais", "jardin"],
	"zone::remparts_capitale": ["ville", "rempart", "muraille", "pierre"],
	"zone::remparts_cite": ["ville", "rempart", "muraille", "pierre"],
	# ── Sauvage ────────────────────────────────────────────────────────────────
	"zone:campement_bandit": ["camp", "clariere", "foret", "bois"],
	"zone:foret_coniferes": ["foret", "bois", "conifere", "chemin"],
	"zone:foret_dense": ["foret", "bois", "chemin"],
	"zone:foret_feuillus": ["foret", "bois", "clariere", "chemin"],
	"zone:foret_persistante": ["foret", "bois", "conifere", "chemin"],
	"zone:foret_petrifiee": ["foret", "pierre", "ruines", "desolation"],
	"zone:foret_temperee_humide": ["foret", "bois", "riviere", "chemin"],
	"zone:jungle": ["jungle", "foret", "tropical"],
	"zone:mangrove": ["mangrove", "marais", "eau", "tropical"],
	"zone:marais": ["marais", "eau", "boue"],
	"zone:montagne": ["montagne", "falaise", "pierre", "chemin"],
	"zone:plaine_ouverte": ["plaine", "herbe", "champ", "chemin"],
	"zone:riviere": ["riviere", "eau", "berge", "bois"],
	"zone:ruines_maudites": ["ruines", "pierre", "souterrain"],
	"zone:taiga": ["foret", "bois", "conifere", "neige"],
}


def _avec_terrain_tags(doc: dict, tags: list) -> dict:
	"""Recopie le doc en insérant `terrain_tags` juste après `nom` (lisibilité de
	l'export ; l'ordre des clés n'a aucun sens pour CouchDB). Un `terrain_tags` déjà
	présent est REMPLACÉ — la table de ce script fait autorité."""
	sortie = {}
	for cle, valeur in doc.items():
		if cle == "terrain_tags":
			continue
		sortie[cle] = valeur
		if cle == "nom":
			sortie["terrain_tags"] = list(tags)
	if "terrain_tags" not in sortie:  # doc sans `nom` : on ajoute en queue
		sortie["terrain_tags"] = list(tags)
	return sortie


def main() -> int:
	with open(SOURCE, encoding="utf-8") as f:
		zones = json.load(f)

	docs, sans_table = [], []
	for doc in zones:
		zone_id = doc.get("_id")
		tags = TERRAIN_TAGS.get(zone_id)
		if tags is None:
			sans_table.append(zone_id)
			continue
		docs.append(_avec_terrain_tags(doc, tags))

	inconnus = sorted(set(TERRAIN_TAGS) - {d["_id"] for d in zones if d.get("_id")})

	with open(CIBLE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")

	print(f"{len(docs)} zones écrites dans {os.path.relpath(CIBLE, RACINE)}")
	# Les deux listes doivent rester vides : une zone hors table garderait le tirage
	# uniforme (repli), une entrée orpheline signale une zone renommée ou supprimée.
	if sans_table:
		print(f"  ⚠ zones de l'export SANS entrée dans la table : {sans_table}")
	if inconnus:
		print(f"  ⚠ entrées de la table absentes de l'export : {inconnus}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
