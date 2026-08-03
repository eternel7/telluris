"""Rend les recettes de l'empenneur disponibles à l'archerie, et inversement.

Les deux métiers travaillent la même matière (le bois de fût, la plume, le tendon)
et se partagent le trait d'arc : ce qu'on sait faire chez l'un, on sait le faire
chez l'autre. Ce script DUPLIQUE donc chaque recette `lieu_categorie` =
`atelier_de_l_empenneur` vers `fletcher` (l'archerie — cf. ses images
`archerie_*.png`) et chaque recette `fletcher` vers `atelier_de_l_empenneur`.

    python dev/gen_recettes_empenneur_archerie.py [chemin/vers/telluris-dump-*.json]

Sortie :
    jsons/recettes_empenneur_archerie_a_importer.json   (carte d'import de /admin)

Lit le dump committé (source unique, cf. CLAUDE.md §11 « Import de contenu ») et
n'écrit QUE les copies manquantes : une recette déjà présente dans la catégorie
cible — même id, ou même produit à partir des mêmes matières sous un autre id —
n'est pas ré-émise. Relancer sur un dump postérieur à l'import ne produit donc
rien : le fichier est idempotent.

⚠️ Conséquence côté marché, à assumer avant d'importer : les recettes d'une
catégorie décident de TOUT chez son marchand (ce qu'il achète au joueur, ce qu'il
auto-approvisionne, ce qu'il produit et met en rayon — cf. CLAUDE.md § Marché).
Dupliquer les recettes, c'est donc aussi ouvrir chez l'empenneur le comptoir de
matières de l'archerie (manches, fer, bronze, plomb, cuir, tendons…) et
réciproquement les plumes chez l'archer. C'est bien l'effet demandé.

⚠️ Aucune recette n'est déplacée ni modifiée : l'original reste intact, la copie
est un doc NEUF (`_rev` retiré, id propre).
"""

import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")

# Les deux métiers à croiser, et le suffixe d'id qui dit où part la copie.
# `fletcher` EST l'archerie (aucun lieu ne porte la catégorie « archerie » :
# c'est la convention d'image qui la nomme ainsi).
METIERS = {
	"atelier_de_l_empenneur": "empenneur",
	"fletcher": "fletcher",
}

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def charger_dump(chemin=None):
	if chemin:
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez le chemin en argument.")
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def recette_matieres(r):
	"""Matières premières → [(cle, quantite)]. Réplique de `marche.recette_matieres`
	(repli sur le champ mono-entrée compris) : ce script reste sans dépendance."""
	mp = r.get("matieres_premieres")
	if isinstance(mp, list) and mp:
		out = [
			(e.get("item") or e.get("sous_categorie"), max(1, int(e.get("quantite", 1) or 1)))
			for e in mp if isinstance(e, dict) and (e.get("item") or e.get("sous_categorie"))
		]
		if out:
			return out
	sc = r.get("matiere_premiere_sous_categorie")
	return [(sc, max(1, int(r.get("quantite_matiere", 1) or 1)))] if sc else []


def signature(r):
	"""Ce qui fait qu'une recette est « la même » qu'une autre, indépendamment de son
	id : le métier, le produit, et les matières consommées. Sert à ne pas recréer sous
	un id neuf une recette que la catégorie cible possède déjà."""
	return (
		r.get("lieu_categorie"),
		r.get("objet_final"),
		tuple(sorted(recette_matieres(r))),
	)


def slug(s):
	return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(s or "").lower())).strip("_")


def id_copie(recette, cible, pris):
	"""Id lisible et STABLE pour la copie. On repart du suffixe de l'id source quand
	il veut dire quelque chose (`recette:arme_arc` → `recette:arme_arc_empenneur`) ;
	les recettes créées par l'éditeur portent un UUID, illisible : on le remplace par
	produit + matières (`recette:cordes_d_arc_boyaux_empenneur`)."""
	base = str(recette.get("_id", ""))[len("recette:"):]
	if not base or UUID.match(base):
		matieres = "_".join(slug(c) for c, _q in recette_matieres(recette))
		base = "_".join(x for x in (slug(recette.get("objet_final")), matieres) if x)
	candidat = "recette:%s_%s" % (base, METIERS[cible])
	# Garde-fou : deux sources différentes ne doivent pas se recouvrir en silence.
	n, final = 1, candidat
	while final in pris:
		n += 1
		final = "%s%02d" % (candidat, n)
	return final


def main():
	dump = charger_dump(sys.argv[1] if len(sys.argv) > 1 else None)
	docs = dump["docs"]

	ids_pris = {d["_id"] for d in docs}
	recettes = [d for d in docs if d.get("type") == "recette"]
	deja = {signature(r) for r in recettes}

	sortie = []
	rapport = []
	for source, cible in (("atelier_de_l_empenneur", "fletcher"),
						  ("fletcher", "atelier_de_l_empenneur")):
		for r in recettes:
			if r.get("lieu_categorie") != source:
				continue
			copie = {k: v for k, v in r.items() if k not in ("_id", "_rev")}
			copie["lieu_categorie"] = cible
			sig = signature(copie)
			if sig in deja:
				continue  # la cible sait déjà le faire — rien à importer
			deja.add(sig)
			copie["_id"] = id_copie(r, cible, ids_pris)
			ids_pris.add(copie["_id"])
			# `type` d'abord pour que le doc se lise comme les autres imports.
			sortie.append({"_id": copie["_id"], "type": "recette", **copie})
			rapport.append("  %-24s -> %-24s %-24s  %s" % (
				source, cible, r.get("objet_final"),
				" + ".join("%s x%d" % (c, q) for c, q in recette_matieres(r)),
			))

	chemin = os.path.join(DOSSIER_JSONS, "recettes_empenneur_archerie_a_importer.json")
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")

	# La console Windows est en cp1252 : sans cela, un accent fait planter le script
	# APRÈS l'écriture du fichier — panne trompeuse.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	print("Recettes dupliquées : %d" % len(sortie))
	print()
	for ligne in rapport:
		print(ligne)
	print()
	print("→ %s" % chemin)


if __name__ == "__main__":
	main()
