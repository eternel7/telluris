"""Génère l'import d'un LOT de magasins décrit par une spec JSON.

Version générique de `dev/gen_magasins_auxerre.py` (dont le catalogue d'enseignes reste du
contenu authoré) : la ville, les métiers, les enseignes et les cases viennent de la spec, pas
du script. Lancée depuis /admin/lieux, outil « 🏪 Magasins depuis un JSON ».

    python dev/gen_magasins.py --dump <telluris-dump-*.json> --spec <spec.json>

Spec :
    {"cite": "lieu:lutecia",
     "magasins": [{"categorie": "auberge", "label": "Au Cheval Blanc",
                   "image": "auberge_europe01.png", "pos": [12, 30],
                   "nom": "…", "portrait": "…",          # optionnels, tenancier générique
                   "tags": ["taverne"], "nuit_messages": ["…"]}]}   # optionnels

Sortie : jsons/magasins_a_importer.json (+ rapport console).

⚠️ MÊME FORME que le lot de lieux de l'éditeur (`_lotDocs`, admin_map_editor.html) : un
`lieu:<slug du label>` à stocks vides (garnis au premier `tick_atelier`) + sa connexion
`link:<categorie><NN>_to_<cité>`. `pnj` n'est écrit QUE si `pnj:marchand_<categorie>` existe —
sinon ce serait une référence morte (l'auberge n'a pas de tenancier).

⚠️ REFUS AVANT TOUTE ÉCRITURE (code 1, aucun fichier) : `_id` déjà pris (dump ou spec), case
absente, hors grille, de terrain ≠ 1, ou déjà porteuse d'un magasin du MÊME métier. Le terrain
exigé est `== 1`, le prédicat des flèches de play_town — plus strict que le voile rouge de
l'éditeur (`>= 1`) : un magasin posé par cet outil est atteignable à pied. Sur /admin/lieux,
« 📍 Compléter les positions » propose des cases de la région principale (voies.js).

⚠️ L'import est un PUT COMPLET (CLAUDE.md §11) : ce script ne réémet JAMAIS un doc existant.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join("jsons", "magasins_a_importer.json")
DOSSIER_IMAGES = os.path.join(RACINE, "templates", "resources", "towns")

DIACRITIQUES = re.compile("[\\u0300-\\u036f]")


def slug_lieu(label):
	"""« Le Chaudron des Brumes » → « le_chaudron_des_brumes ».

	Réplique exacte de `_slugLieu` (part-lieux-js.html) : les ids créés par l'éditeur et
	ceux créés ici doivent suivre la même règle."""
	s = unicodedata.normalize("NFD", str(label or ""))
	s = DIACRITIQUES.sub("", s).lower()
	s = re.sub(r"[^a-z0-9]+", "_", s)
	return re.sub(r"_+", "_", s).strip("_")


def charger_docs(chemin):
	"""Docs d'un dump `{"docs": [...]}` ou d'un export nu."""
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def _liste_de_chaines(valeur):
	return isinstance(valeur, list) and all(isinstance(v, str) for v in valeur)


def construire(docs, spec, images_presentes):
	"""PURE. Rend {docs, lignes, erreurs, avertissements, images_manquantes}.

	`erreurs` non vide ⇒ `docs` est vide : un lot à moitié valide ne part jamais."""
	erreurs, avert, lignes, manquantes, sortie = [], [], [], [], []
	if not isinstance(spec, dict):
		return {"docs": [], "lignes": [], "erreurs": ["La spec doit être un objet JSON."],
				"avertissements": [], "images_manquantes": []}
	par_id = {d.get("_id"): d for d in docs if isinstance(d, dict) and d.get("_id")}
	cite = spec.get("cite")
	cite_doc = par_id.get(cite) if isinstance(cite, str) else None
	magasins = spec.get("magasins")
	if not cite_doc or cite_doc.get("type") != "lieu":
		erreurs.append(f"Cité introuvable dans le dump : {cite!r}.")
	if not isinstance(magasins, list) or not magasins:
		erreurs.append("`magasins` doit être une liste non vide.")
	if erreurs:
		return {"docs": [], "lignes": [], "erreurs": erreurs, "avertissements": [],
				"images_manquantes": []}

	cells = cite_doc.get("cells") or []
	cite_slug = cite.split(":", 1)[-1]
	tenanciers = {i for i in par_id if str(i).startswith("pnj:marchand_")}
	ids_pris = set(par_id)

	# Ce que la cité porte déjà : métiers par case, et numéros de connexion par métier.
	cats_de_case, numeros = {}, {}
	for c in docs:
		if not isinstance(c, dict) or c.get("type") != "connection":
			continue
		nodes = c.get("nodes") or []
		ici = next((n for n in nodes if n.get("lieu") == cite), None)
		la = next((n for n in nodes if n.get("lieu") != cite), None)
		if not ici or not la:
			continue
		cat = (par_id.get(la.get("lieu")) or {}).get("categorie")
		if cat:
			cats_de_case.setdefault(tuple(ici.get("pos") or [0, 0]), set()).add(cat)
			m = re.match(r"^link:" + re.escape(cat) + r"(\d+)_to_" + re.escape(cite_slug) + r"$",
						 c.get("_id", ""))
			if m:
				numeros[cat] = max(numeros.get(cat, 0), int(m.group(1)))

	for i, m in enumerate(magasins, start=1):
		ou = f"magasin #{i}"
		if not isinstance(m, dict):
			erreurs.append(f"{ou} : un objet est attendu.")
			continue
		cat = m.get("categorie")
		label = m.get("label")
		image = m.get("image")
		if not isinstance(cat, str) or not cat.strip():
			erreurs.append(f"{ou} : `categorie` requise.")
			continue
		cat = cat.strip()
		if not isinstance(label, str) or not slug_lieu(label):
			erreurs.append(f"{ou} ({cat}) : `label` requis.")
			continue
		ou = f"magasin #{i} « {label} »"
		if not isinstance(image, str) or not image.strip():
			erreurs.append(f"{ou} : `image` requise.")
			continue
		lieu_id = "lieu:" + slug_lieu(label)
		if lieu_id in ids_pris:
			erreurs.append(f"{ou} : {lieu_id} existe déjà — changez le label.")
			continue

		pos = m.get("pos")
		if not (isinstance(pos, list) and len(pos) == 2
				and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in pos)):
			erreurs.append(f"{ou} : `pos` [x, y] requise (📍 Compléter les positions sur /admin/lieux).")
			continue
		x, y = pos
		ligne = cells[y] if y < len(cells) else None
		if not isinstance(ligne, list) or x >= len(ligne):
			erreurs.append(f"{ou} : [{x}, {y}] est hors de la grille de {cite}.")
			continue
		if ligne[x] != 1:
			erreurs.append(f"{ou} : [{x}, {y}] porte le terrain {ligne[x]} — seul 1 est atteignable aux flèches.")
			continue
		if cat in cats_de_case.get((x, y), set()):
			erreurs.append(f"{ou} : [{x}, {y}] porte déjà un magasin « {cat} ».")
			continue

		ids_pris.add(lieu_id)
		cats_de_case.setdefault((x, y), set()).add(cat)
		numeros[cat] = numeros.get(cat, 0) + 1
		link_id = "link:%s%02d_to_%s" % (cat, numeros[cat], cite_slug)
		if link_id in ids_pris:
			erreurs.append(f"{ou} : {link_id} existe déjà.")
			continue
		ids_pris.add(link_id)

		lieu = {
			"_id": lieu_id,
			"type": "lieu",
			"label": label,
			"image": image,
			"categorie": cat,
			"lieu_parent": cite,
			"stock_matieres": {},
			"stock_vente": [],
		}
		tenancier = "pnj:marchand_" + cat
		if tenancier in tenanciers:
			entree = {"character": tenancier}
			# Champs vides jamais écrits : `pnj_payload` retombe sur le doc PNJ générique.
			if isinstance(m.get("portrait"), str) and m["portrait"]:
				entree["portrait"] = m["portrait"]
			if isinstance(m.get("nom"), str) and m["nom"]:
				entree["nom"] = m["nom"]
			lieu["pnj"] = [entree]
		elif m.get("nom") or m.get("portrait"):
			avert.append(f"{ou} : `nom`/`portrait` ignorés — aucun {tenancier} en base.")
		for champ in ("tags", "nuit_messages"):
			if champ in m:
				if _liste_de_chaines(m[champ]) and m[champ]:
					lieu[champ] = list(m[champ])
				elif m[champ]:
					erreurs.append(f"{ou} : `{champ}` doit être une liste de chaînes.")
		sortie.append(lieu)
		sortie.append({
			"_id": link_id,
			"type": "connection",
			"nodes": [
				{"lieu": cite, "pos": [x, y]},
				{"lieu": lieu_id, "pos": [0, 0]},
			],
			"metadata": {"type": cat, "status": "ouvert"},
		})
		absente = image not in images_presentes
		if absente:
			manquantes.append(image)
		lignes.append("  %-24s %-34s [%2d,%2d]  %s%s%s" % (
			cat, label, x, y, image, "   ← IMAGE MANQUANTE" if absente else "",
			"" if "pnj" in lieu else "   (sans tenancier)"))

	if erreurs:
		sortie, lignes = [], []
	return {"docs": sortie, "lignes": lignes, "erreurs": erreurs, "avertissements": avert,
			"images_manquantes": manquantes}


def main(argv=None):
	# Console Windows en cp1252 : sans cela, un accent fait planter le rapport.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	p.add_argument("--dump", required=True)
	p.add_argument("--spec", required=True)
	args = p.parse_args(argv)

	docs = charger_docs(args.dump)
	with open(args.spec, encoding="utf-8") as f:
		spec = json.load(f)
	images = set(os.listdir(DOSSIER_IMAGES)) if os.path.isdir(DOSSIER_IMAGES) else set()
	res = construire(docs, spec, images)

	print(f"dump : {args.dump}")
	print(f"cité : {spec.get('cite') if isinstance(spec, dict) else '?'}")
	for a in res["avertissements"]:
		print("⚠ " + a)
	if res["erreurs"]:
		print()
		print(f"✗ {len(res['erreurs'])} refus — AUCUN fichier écrit :")
		for e in res["erreurs"]:
			print("  · " + e)
		return 1

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(res["docs"], f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"Magasins créés : {len(res['docs']) // 2} ({len(res['docs'])} docs avec les connexions)")
	print(f"Images manquantes : {len(res['images_manquantes'])}")
	print()
	for ligne in res["lignes"]:
		print(ligne)
	print()
	print("→ " + SORTIE.replace("\\", "/"))
	return 0


if __name__ == "__main__":
	sys.exit(main())
