#!/usr/bin/env python
# dev/gen_chasse_sauvage.py
# La Chasse sauvage d'Annwn (docs/lore/cites/20261021_camelot_winchester.md § 2 bis, Auteur,
# 21/10) : certaines nuits, Gwyn ap Nudd et ses chiens sortent des portails qui surgissent
# autour de Camelot — ennemi récurrent de la Table ronde.
#   - `espece:cwn_annwn` : « Chien d'Annwn », espèce de meute (rang C proposé) ;
#   - `espece:gwyn_ap_nudd` : seigneur d'Annwn, être unique, boss (rang A proposé).
# Même cœur que `gen_bestiaire_arthurien.py` (`docs_bestiaire_arthurien(base, NOUVELLES)`) ;
# fichier PROPRE à cette demande, qui ne ressort pas le premier lot (CLAUDE.md §18).
# Images : templates/resources/monsters/<slug>_transparent.png (prompts dans la séance).
#
# ⚠️ Les tables EXHAUSTIVES de `gen_genres_especes.py` et `gen_jetons_especes.py` citent déjà
# ces espèces : elles échouent tant que l'import n'est pas fait et relu dans un dump frais.
#
# Usage : python dev/gen_chasse_sauvage.py [jsons/telluris-dump-….json]
# Sortie : jsons/chasse_sauvage_a_importer.json

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_bestiaire_arthurien import docs_bestiaire_arthurien  # noqa: E402
from gen_equipement_humanoides import _dump_le_plus_recent, charger  # noqa: E402
from gen_vampires import _attrs  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "chasse_sauvage_a_importer.json")

# `carcasse` = (poids min, poids max, rareté). Accord et jeton : tables des générateurs dédiés.
NOUVELLES = {
	# Rang C proposé — calibré au-dessus du Cú Sídhe, chien de l'Autre Monde irlandais.
	"cwn_annwn": {
		"nom": "Chien d'Annwn",
		"description": "Les Cŵn Annwn, chiens de l'Autre Monde, d'un blanc éclatant aux oreilles "
					   "rouges. Certaines nuits ils sortent en meute des portails qui surgissent "
					   "autour de Camelot, avec la Chasse sauvage. Leur aboiement est d'autant plus "
					   "fort qu'ils sont loin, et se fait doux quand ils sont tout près : qui les "
					   "entend chuchoter derrière lui n'a plus le temps de fuir. On dit qu'ils mènent "
					   "les âmes jusqu'à Annwn ; les chevaliers de la Table ronde disent seulement "
					   "qu'ils ne lâchent jamais une piste.",
		"base_attributes": _attrs((7, 9), (45, 65), (40, 60), (55, 80), (45, 65), (20, 35), (0, 0), (30, 50)),
		"tags": ["monstre", "feerique", "nocturne", "rapide", "terreur", "predateur", "insensible_furtivite"],
		"carcasse": ([60, 110], "peu_commun"),
	},
	# Rang A proposé — un boss humanoïde, magicien plus que bretteur.
	"gwyn_ap_nudd": {
		"nom": "Gwyn ap Nudd",
		"description": "Seigneur d'Annwn, qui mène la Chasse sauvage hors des portails par les nuits "
					   "d'orage, son chien Dormarth au museau rouge à ses côtés. Chaque premier jour "
					   "de mai il se bat contre Gwythyr pour la belle Creiddylad, et se battra ainsi "
					   "jusqu'à la fin des temps sans qu'aucun ne l'emporte. Les uns disent qu'il "
					   "demeure sous Glastonbury Tor ; ceux qui l'ont croisé disent qu'il leur a "
					   "parlé avec courtoisie, puis a lâché ses chiens.",
		"base_attributes": _attrs((8, 10), (65, 95), (60, 90), (55, 80), (85, 120), (65, 90), (0, 0), (55, 85)),
		"tags": ["humanoide", "feerique", "magique", "nocturne", "legendaire", "boss", "insensible_furtivite"],
		"carcasse": ([70, 110], "rare"),
	},
}


def main() -> None:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	source = sys.argv[1] if len(sys.argv) > 1 else _dump_le_plus_recent()
	base = {d["_id"]: d for d in charger(source) if isinstance(d, dict) and d.get("_id")}
	docs, deja = docs_bestiaire_arthurien(base, NOUVELLES)
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
