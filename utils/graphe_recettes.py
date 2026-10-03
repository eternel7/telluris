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
# Arêtes `recette` : une par (recette, entrée), de l'entrée vers le produit.

from utils import marche
from utils.characters import item_sous_categorie

PREFIXE_FAMILLE = "sc:"


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
	}


def construire_graphe(recettes: list, items: list) -> dict:
	"""{"nodes": [...], "edges": [...]} : tous les items (même isolés — le filtre « isolés »
	de l'écran en a besoin), les familles citées, une arête par entrée de recette et une
	arête `membre` par item d'une famille citée."""
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

	return {"nodes": sorted(noeuds.values(), key=lambda n: n["id"]), "edges": aretes}
