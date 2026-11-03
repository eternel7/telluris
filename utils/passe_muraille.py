"""Passe-muraille (pur) : franchir une porte de rempart d'un seul geste.

Une porte de rempart est une PAIRE (cf. telluris-editeur-carte § Porte de rempart) :
case de la cité → lieu porte (côté A) → passage → lieu porte (côté B) → case de la cité.
Le réglage 🧱 du menu ⚙️ de /play envoie `passe_muraille: true` avec le lien ; quand ce lien
mène à une porte, `move_character` dépose le joueur directement sur la case de la cité au
bout de la paire, sans afficher les deux lieux porte.

Aucune donnée neuve : la paire se LIT dans les connexions. Paire indécidable (zéro ou
plusieurs portes jumelles, zéro ou plusieurs sorties) ⇒ `None`, et le déplacement ordinaire
s'applique — on ne devine jamais un côté.
"""

CATEGORIE_PORTE = "Porte de rempart"


def est_porte(doc) -> bool:
	return isinstance(doc, dict) and doc.get("categorie") == CATEGORIE_PORTE


def _voisins(lieu_id: str, connexions_fn) -> list[dict]:
	"""Nœuds atteignables depuis `lieu_id` : l'autre extrémité de chaque connexion. Écarte les
	connexions internes et celles dont le nœud de départ porte `bouton: false` (même verrou
	que `lieux.depart_interdit`)."""
	out, vus = [], set()
	for conn in connexions_fn(lieu_id) or []:
		cid = (conn or {}).get("_id")
		if cid in vus:
			continue
		vus.add(cid)
		nodes = [n for n in (conn or {}).get("nodes") or [] if isinstance(n, dict)]
		if any(n.get("lieu") == lieu_id and n.get("bouton") is False for n in nodes):
			continue
		autres = [n for n in nodes if n.get("lieu") != lieu_id]
		if len(autres) == 1:
			out.append(autres[0])
	return out


def traversee(porte_id: str, connexions_fn, get_doc_fn) -> tuple[str, dict] | None:
	"""`(porte jumelle, nœud d'arrivée)` pour qui entre dans la porte `porte_id`, ou None.

	Nœud d'arrivée = l'extrémité, hors porte, de la connexion qui sort de la jumelle (la case
	de la cité de l'autre côté du mur), avec un `pos` exploitable."""
	jumelles = [n for n in _voisins(porte_id, connexions_fn) if est_porte(get_doc_fn(n.get("lieu")))]
	if len({n.get("lieu") for n in jumelles}) != 1:
		return None
	jumelle = jumelles[0]["lieu"]
	sorties = [n for n in _voisins(jumelle, connexions_fn)
			   if n.get("lieu") != porte_id and not est_porte(get_doc_fn(n.get("lieu")))]
	if len(sorties) != 1:
		return None
	sortie = sorties[0]
	pos = list(sortie.get("pos") or [])
	if len(pos) < 2 or not all(isinstance(v, int) for v in pos[:2]):
		return None
	return jumelle, sortie
