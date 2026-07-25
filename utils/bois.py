# utils/bois.py
# Découpe du bois : un item « a_couper » (échelle BOIS_A_COUPER, du plus petit au plus
# grand) peut être coupé d'UN niveau → des pièces du tier immédiatement plus petit de la
# MÊME essence, poids conservé (pièces ≈ max, reliquat = chute). `branche` n'a pas le tag
# a_couper → terminal. La coupe nécessite un outil (item taggé OUTIL_COUPE_BOIS_TAG).
#
# Logique pure (get_doc / find_docs injectés), ne sauvegarde jamais — l'endpoint persiste.
# Tunables lus via le module character_stats (réassignés par load_world_variables).

from models import character_stats
from utils.characters import item_ref_id, item_ref_weight, poids_bounds
from utils import expedition


def _item_tags(item_doc) -> list:
	return [str(t).lower() for t in ((item_doc or {}).get("tags") or [])]


def item_est_coupable(item_doc) -> bool:
	"""Item découpable : tag `a_couper` ET `sous_categorie` dans l'échelle BOIS_A_COUPER."""
	if not item_doc:
		return False
	return (
		"a_couper" in _item_tags(item_doc)
		and item_doc.get("sous_categorie") in character_stats.BOIS_A_COUPER
	)


def _essence_de(item_doc) -> str | None:
	"""Essence portée par un tag `essence_<xxx>` (ex. `essence_chene` → `chene`). None si
	aucun tag d'essence. Le premier tag `essence_*` rencontré fait foi."""
	for t in _item_tags(item_doc):
		if t.startswith("essence_") and len(t) > len("essence_"):
			return t[len("essence_"):]
	return None


def _trouver_item(find_docs_fn, essence: str, tier: str):
	"""Item de la même essence (tag `essence_<essence>`) au tier donné."""
	docs = find_docs_fn({"type": "item", "sous_categorie": tier}) or []
	for d in docs:
		if _essence_de(d) == essence:
			return d
	return None


def cible_coupe(item_doc, find_docs_fn):
	"""Item du tier immédiatement plus petit (même essence), en sautant les tiers absents.
	None si l'item n'est pas coupable ou si aucun tier inférieur n'existe."""
	if not item_est_coupable(item_doc):
		return None
	ladder = character_stats.BOIS_A_COUPER
	try:
		idx = ladder.index(item_doc.get("sous_categorie"))
	except ValueError:
		return None
	essence = _essence_de(item_doc)
	if not essence:
		return None
	for j in range(idx - 1, -1, -1):
		cand = _trouver_item(find_docs_fn, essence, ladder[j])
		if cand:
			return cand
	return None


def pieces_legeres(item_doc, find_docs_fn, poids_max: float) -> list:
	"""IDs des items « bois » de la MÊME essence que `item_doc` (toutes tailles de BOIS_A_COUPER)
	dont le **poids max** est `≤ poids_max` → pièces transportables (branche/petit_rondin/rondin…),
	à l'exclusion de fait de l'arbre/tronc/gros_rondin trop lourds. Ordre = échelle (petit→grand)."""
	essence = _essence_de(item_doc)
	if not essence:
		return []
	out = []
	for tier in character_stats.BOIS_A_COUPER:
		cand = _trouver_item(find_docs_fn, essence, tier)
		if not cand:
			continue
		_, pmax = poids_bounds(cand)
		cid = cand.get("_id")
		if cid and pmax <= poids_max and cid not in out:
			out.append(cid)
	return out


def repartir_poids(poids_source: float, tmax: float) -> list:
	"""Découpe un poids en pièces ≈ `tmax` (du plus grand au plus petit), conservation
	exacte : la dernière pièce = reliquat (possiblement < min de la cible = chute). Borné
	par COUPE_MAX_PIECES (au cap, la dernière pièce absorbe tout le restant)."""
	restant = round(float(poids_source or 0), 2)
	tmax = float(tmax or 0)
	if restant <= 0:
		return []
	if tmax <= 0:
		return [restant]
	cap = max(1, int(character_stats.COUPE_MAX_PIECES))
	pieces = []
	while restant > tmax and len(pieces) < cap - 1:
		pieces.append(round(tmax, 2))
		restant = round(restant - tmax, 2)
	if restant > 0:
		pieces.append(restant)
	return pieces


def couper_ref(source_ref, source_item_doc, find_docs_fn):
	"""Coupe une réf d'item d'un niveau → liste de réfs `{item, poids}` (pièces du tier
	inférieur, poids conservé), ou None si non coupable / pas de cible."""
	cible = cible_coupe(source_item_doc, find_docs_fn)
	if not cible:
		return None
	_, tmax = poids_bounds(cible)
	poids_list = repartir_poids(item_ref_weight(source_ref), tmax)
	cible_id = cible.get("_id")
	return [{"item": cible_id, "poids": p} for p in poids_list]


def a_outil_coupe(character, get_doc_fn, compagnons=None) -> bool:
	"""True si un item du sac OU de l'équipement porte le tag outil de coupe.

	Compétences/équipements partagés en exploration : si `compagnons` (liste de docs
	`aventurier:*` du groupe) est fournie, il suffit qu'UN membre de l'expédition — le
	personnage OU un compagnon — porte l'outil. `None` → seul le personnage est scanné
	(comportement historique inchangé).

	Le scan lui-même vit dans `expedition.porteur_avec_tag` (mise en commun des capacités,
	partagée avec les autres tags à venir). ⚠️ Signature CONSERVÉE au profit de ses deux
	appelants et de tests/test_bois.py — le test de non-régression de la mise en commun :
	la liste des porteurs est passée explicitement, là où `expedition.membres` la résout
	depuis la base."""
	return expedition.porteur_avec_tag(
		get_doc_fn, [character, *(compagnons or [])], character_stats.OUTIL_COUPE_BOIS_TAG)
