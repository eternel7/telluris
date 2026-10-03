# utils/graphe_recettes.py
# Graphe des recettes (pur) : « l'objet A sert à fabriquer l'objet B », pour l'écran
# /admin/recettes-graphe. Aucune règle n'est recopiée : les entrées d'une recette viennent
# de `marche.recette_matieres`, son produit de `marche.objet_final_item_id`, l'appartenance
# d'un item à une famille de `characters.item_sous_categorie` — les mêmes fonctions que le
# tick d'atelier et le coût de revient. Ne lit ni n'écrit la base : l'appelant fournit
# recettes et items.
#
# Nœuds :
#   - `item`    : un doc `item:*` (ou un id CITÉ par une recette sans doc → `absent`) ;
#   - `famille` : `sc:<clé>`, une entrée de recette donnée par SOUS-CATÉGORIE (« 2 acier ») :
#                 n'importe quel item de la famille la satisfait. Ses membres y sont reliés
#                 par une arête `membre`, d'où le chemin membre → famille → produit.
#   - `piece`   : `fab:<famille>`, une famille de pièces façonnables SUR MESURE (arme, armure…).
#                 Ses pièces sont listées (`pieces`) mais pas reliées : `arme` en compte des
#                 centaines.
# Arêtes `recette` : une par (recette, entrée), de l'entrée vers le produit.
# Arêtes `fabrication` : matière → `fab:<famille>`, lien POTENTIEL du sur-mesure — la matière
#   apporte quelque chose (`fabrication.apporte`) et porte le tag `fabrication_<famille>` ;
#   les pièces d'une famille sont celles que `commande.tags_fabrication` y range (même
#   critère que `commande.matiere_acceptee`). L'autre porte de `matiere_acceptee` (le métier
#   de la maison achète la matière) dépend du LIEU : elle n'est pas un lien d'item.

from utils import commande, fabrication, marche
from utils.characters import item_sous_categorie

PREFIXE_FAMILLE = "sc:"
PREFIXE_PIECE = "fab:"


def id_famille(cle: str) -> str:
	return PREFIXE_FAMILLE + str(cle)


def _noeud_item(item_id: str, doc: dict | None) -> dict:
	doc = doc or {}
	return {
		"id": item_id,
		"type": "item",
		"label": doc.get("nom") or item_id.split(":", 1)[-1],
		"icon": doc.get("icon") or "",
		"categorie": doc.get("categorie") or "",
		"sous_categorie": doc.get("sous_categorie") or "",
		"rarete": doc.get("rarete") or "",
		"absent": not doc,
		"matiere_fabrication": bool(doc) and fabrication.apporte(doc),
		"fabrication_nom": fabrication.proprietes_matiere(doc)["nom"] if doc else "",
	}


def construire_graphe(recettes: list, items: list) -> dict:
	"""{"nodes": [...], "edges": [...]} : tous les items (même isolés — le filtre « isolés »
	de l'écran en a besoin), les familles citées, une arête par entrée de recette, une
	arête `membre` par item d'une famille citée et une arête `fabrication` par (matière,
	famille de pièces qu'elle ouvre)."""
	docs = {d["_id"]: d for d in (items or []) if isinstance(d, dict) and d.get("_id")}
	noeuds: dict[str, dict] = {i: _noeud_item(i, d) for i, d in docs.items()}
	aretes: list[dict] = []
	familles: set = set()

	def _item(item_id: str) -> str:
		if item_id not in noeuds:
			noeuds[item_id] = _noeud_item(item_id, docs.get(item_id))
		return item_id

	for r in recettes or []:
		if not isinstance(r, dict):
			continue
		produit = r.get("objet_final")
		if not produit:
			continue
		cible = _item(marche.objet_final_item_id(produit))
		rid = r.get("_id") or ""
		for n, (cle, quantite) in enumerate(marche.recette_matieres(r)):
			if str(cle).startswith("item:"):
				source = _item(cle)
			else:
				source = id_famille(cle)
				familles.add(cle)
			aretes.append({
				"id": f"{rid}|{n}",
				"source": source,
				"target": cible,
				"kind": "recette",
				"recette": rid,
				"lieu_categorie": r.get("lieu_categorie") or "",
				"lieu_portee": r.get("lieu_portee") or "",
				"quantite": quantite,
				"quantite_produite": int(r.get("quantite_produite", 1) or 1),
				"sur_commande": marche.est_sur_commande(r),
			})

	# Familles : membres = items dont la sous-catégorie marchande (repli sur la catégorie,
	# comme le moteur) vaut la clé. Une famille sans aucun membre est `absent` : aucune
	# matière ne peut satisfaire l'entrée qui la cite.
	membres: dict[str, list] = {cle: [] for cle in familles}
	for item_id, doc in docs.items():
		sc = item_sous_categorie(doc)
		if sc in membres:
			membres[sc].append(item_id)
	for cle in sorted(familles):
		fid = id_famille(cle)
		noeuds[fid] = {
			"id": fid, "type": "famille", "label": cle, "icon": "",
			"categorie": "", "sous_categorie": cle, "rarete": "",
			"absent": not membres[cle],
		}
		for item_id in sorted(membres[cle]):
			aretes.append({
				"id": f"{item_id}>{fid}", "source": item_id, "target": fid, "kind": "membre",
			})

	# Fabrication sur mesure : familles ouvertes par les matières, puis leurs pièces.
	prefixe = commande.TAG_FABRICATION_PREFIXE
	ouvertes: dict[str, list] = {}
	for item_id, doc in sorted(docs.items()):
		if not fabrication.apporte(doc):
			continue
		for tag in sorted({str(t) for t in (doc.get("tags") or []) if str(t).startswith(prefixe)}):
			ouvertes.setdefault(tag[len(prefixe):], []).append(item_id)
	pieces: dict[str, list] = {fam: [] for fam in ouvertes}
	for item_id, doc in sorted(docs.items()):
		for tag in commande.tags_fabrication(doc):
			fam = tag[len(prefixe):]
			if fam in pieces:
				pieces[fam].append(item_id)
	for fam in sorted(ouvertes):
		pid = PREFIXE_PIECE + fam
		noeuds[pid] = {
			"id": pid, "type": "piece", "label": fam, "icon": "⚒",
			"categorie": "", "sous_categorie": "", "rarete": "",
			"absent": not pieces[fam], "pieces": pieces[fam],
		}
		for item_id in ouvertes[fam]:
			aretes.append({
				"id": f"{item_id}~{pid}", "source": item_id, "target": pid, "kind": "fabrication",
			})

	return {"nodes": sorted(noeuds.values(), key=lambda n: n["id"]), "edges": aretes}
