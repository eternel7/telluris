"""Le tenancier générique du NÉGOCIANT (« marchand pur », utils/negoce.py) :
`pnj:marchand_negociant`.

	python dev/gen_negociant.py

Sortie :
	jsons/negociant_a_importer.json   (à coller dans la carte d'import de /admin)

Pourquoi pas `dev/gen_marchands.py` : il dérive ses catégories des RECETTES, et le négociant
n'en a aucune ; et il réécrit tous les `pnj:marchand_*` en PUT complet, ce qui défait les
services posés par `gen_escorte_marchands` / `gen_direction_marchands`.

Ce doc est le MODÈLE des candidats au poste de négociant d'une propriété
(`proprietes.MODELE_PREFIXE` : portrait et race recopiés, nom tiré). Il ne porte ni transport
ni escorte : une boutique sans recette n'est pas un `transport.est_magasin`.

Doc NEUF : refus d'écrire si son `_id` existe déjà dans le dump le plus récent (le PUT complet
de l'import l'écraserait en silence). Relancer régénère le fichier à l'identique."""

import glob
import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "negociant_a_importer.json")
ID = "pnj:marchand_negociant"

DOC = {
	"_id": ID,
	"type": "pnj",
	"nom": "Maître Lombard",
	"race": "humain",
	"vocation": "marchand",
	"portrait": "humain_m_lettre01.jpg",
	"dialogue": {
		"noeud_depart": "accueil",
		"noeuds": {
			"accueil": {
				"texte": (
					"Une balance de changeur trône sur le comptoir, entre deux registres ouverts. "
					"« Bien le bonjour, {prenom}. Je prends tout, et je paie comptant. Ce qui vaut "
					"la peine finit sur mes rayons ; le reste, j'en fais mon affaire. »"
				),
				"choix": [
					{"id": "commission", "label": "Et votre commission ?", "next": "commission"},
					{"id": "rien", "label": "Je ne faisais que passer.", "next": "fin"},
				],
			},
			"commission": {
				"texte": (
					"« Elle dépend de vous, {prenom}. Un client que je connais mal me coûte des "
					"précautions ; un ami de la maison, presque rien. Revenez souvent, et vous "
					"verrez la différence. Mais on ne marchande pas avec moi : mon prix est "
					"juste, et il est le même pour tout ce que vous m'apportez. »"
				),
				"choix": [
					{"id": "retour", "label": "Entendu.", "next": "accueil"},
					{"id": "fin", "label": "Au revoir.", "next": "fin"},
				],
			},
		},
	},
}


def ids_du_dump() -> set:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		return set()
	brut = json.load(open(dumps[-1], encoding="utf-8"))
	return {d.get("_id") for d in brut.get("docs", [])}


def main() -> None:
	if ID in ids_du_dump():
		raise SystemExit(f"{ID} existe déjà dans le dump : l'import l'écraserait. Rien n'est écrit.")
	portrait = os.path.join(RACINE, "templates", "resources", "pnj", DOC["portrait"])
	if not os.path.exists(portrait):
		raise SystemExit(f"Portrait absent : {portrait}")
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump([DOC], f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"1 doc écrit dans {SORTIE}")


if __name__ == "__main__":
	main()
