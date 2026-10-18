#!/usr/bin/env python
# dev/gen_mimique.py
# La MIMIQUE : le coffre qui n'en est pas un — effet `mimique` du piège d'un trésor d'étage
# (utils/tresor.py). Espèce INVENTÉE à la demande de l'Auteur (18/10), sans mythe terrestre
# derrière elle : son origine reste ouverte (théories contradictoires dans la description).
#
# Docs :
#   - `espece:mimique` (neuve) + sa carcasse `item:mimique` (sous le seuil de découpe) ;
#   - `donjon:catacombes_de_lutecia`, RELU dans le dump : le bloc `tresor` du dernier étage tel
#     que l'écrit `gen_tresor_catacombes.TRESOR` (source unique), effet `mimique` compris.
#
# Accord (`genre: f`) et jeton (1x1) : tables EXHAUSTIVES de `gen_genres_especes.py` et
# `gen_jetons_especes.py`, qui échouent tant qu'un dump frais n'a pas relu l'espèce.
# Image à générer : templates/resources/monsters/mimique_transparent.png (prompt ci-dessous).
#
# Usage : python dev/gen_mimique.py [jsons/telluris-dump-….json]
# Sortie : jsons/mimique_a_importer.json

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_equipement_humanoides import _dump_le_plus_recent, charger  # noqa: E402
from gen_genres_especes import accord_de  # noqa: E402
from gen_jetons_especes import TABLE as JETONS  # noqa: E402
from gen_loups_garous import _carcasse  # noqa: E402
from gen_tresor_catacombes import DONJON_ID, maj_donjon  # noqa: E402
from gen_vampires import _attrs, _sans_rev  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "mimique_a_importer.json")
SLUG = "mimique"

# Grade d'un étage de catacombes (3-4) : plus lente qu'une goule, aussi dure qu'une gargouille
# — elle n'a pas à courir, on vient à elle.
MIMIQUE = {
	"nom": "Mimique",
	"description": "Coffre de bois noirci cerclé de fer, en tout point semblable à ceux qu'on "
				   "abandonne au fond des donjons — jusqu'à ce qu'on en soulève le couvercle. "
				   "Le bois s'ouvre alors en gueule, frangée de dents d'ébène, et une langue "
				   "poisseuse saisit la main qui fouillait. Les uns disent qu'un donjon imite ce "
				   "qu'il a englouti, les autres qu'elle se nourrit de l'avidité des pilleurs ; "
				   "aucun Templier n'a jamais vu une mimique se déplacer quand on la regardait.",
	"base_attributes": _attrs((3, 5), (40, 60), (45, 70), (15, 30), (30, 50), (5, 15), (0, 0), (20, 35)),
	"tags": ["monstre", "gardien", "insensible_furtivite"],
	"carcasse": ([30, 70], "rare"),
}

PROMPT_IMAGE = (
	"Réalise l'image de la Mimique, une créature de donjon : un coffre de bois noirci cerclé de "
	"fer, posé au sol, dont le couvercle s'ouvre en une gueule frangée de dents d'ébène ; une "
	"longue langue poisseuse et violacée en jaillit, des ferrures tordues comme des griffes "
	"agrippent la pierre. La créature est tapie, prête à mordre. Illustration en pied ; la "
	"créature occupe environ 80 % de l'image, entière, sans partie coupée par le cadre, en vue "
	"de trois-quarts. Fond parfaitement uni et plat, vert vif pur, sans dégradé, sans décor, "
	"sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche "
	"de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG "
	"narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude "
	"et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun "
	"panneau lisible, aucun logo, aucune signature, aucun filigrane."
)


def _espece() -> dict:
	accord = accord_de(SLUG)
	doc = {"_id": "espece:" + SLUG, "type": "espece", "nom": MIMIQUE["nom"],
		   "genre": accord["genre"],
		   **{k: True for k in ("nom_propre", "pluriel", "h_aspire") if accord.get(k)}}
	if JETONS[SLUG]:
		doc["jeton"] = {"taille": JETONS[SLUG][0], "forme": JETONS[SLUG][1]}
	doc.update({
		"image": SLUG + "_transparent.png",
		"description": MIMIQUE["description"],
		"base_attributes": copy.deepcopy(MIMIQUE["base_attributes"]),
		"tags": list(MIMIQUE["tags"]),
		"proprietes": {},
	})
	return doc


def docs_mimique(base: dict) -> tuple[list, list]:
	"""(docs à importer, ids déjà à jour) d'après les docs du dump `base` ({_id: doc})."""
	if SLUG not in JETONS:
		sys.exit("ERREUR : espece:mimique absente de gen_jetons_especes.TABLE")
	if DONJON_ID not in base:
		sys.exit(f"ERREUR : {DONJON_ID} absent du dump")
	espece = _espece()
	docs, deja = [], []
	for d in (espece, _carcasse(espece["_id"], espece["nom"], *MIMIQUE["carcasse"])):
		if d["_id"] not in base:
			docs.append(d)
		elif _sans_rev(base[d["_id"]]) == d:
			deja.append(d["_id"])
		else:
			sys.exit(f"ERREUR : {d['_id']} déjà en base sous une autre forme — collision d'_id")
	donjon = _sans_rev(base[DONJON_ID])
	neuf = maj_donjon(donjon)
	if neuf == donjon:
		deja.append(DONJON_ID)
	else:
		docs.append(neuf)
	return docs, deja


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = sys.argv[1] if len(sys.argv) > 1 else _dump_le_plus_recent()
	base = {d["_id"]: d for d in charger(source) if isinstance(d, dict) and d.get("_id")}
	docs, deja = docs_mimique(base)
	print(f"relu {os.path.relpath(source, RACINE)}")
	for d in docs:
		print(f"   à importer {d['_id']}")
	for i in deja:
		print(f"   déjà en base {i}")
	if not docs:
		print("rien à importer — la base est à jour")
		return
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} doc(s) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
