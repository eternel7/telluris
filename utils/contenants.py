# Contenants (pur) — un objet à poids fixe qui contient un poids supérieur.
#
# Conception : docs/conception_contenants.md ; lore : docs/lore/monde/20261102_sacs_des_legendes.md.
#
# - Le doc item porte la capacité : `contenant: {capacite_kg, maree?}`.
# - Le CONTENU vit sur la RÉFÉRENCE d'inventaire de l'exemplaire (`ref["contenu"]`), comme le
#   texte d'un livre écrit ou `nom_perso` : il suit le contenant partout (sac, compagnon,
#   monture, coffre, sol) sans une ligne de code ailleurs.
# - RANGÉ = INERTE : tout ce qui lit `inventaire` ne voit que la référence du contenant —
#   vente groupée, quêtes, grimoires, outils, combat, charge physique ET magique (Auteur,
#   02/11 : « il ne pèse rien »). `item_ref_weight` ignore `contenu` : le contenant pèse
#   son seul poids, plein ou vide.
# - Aucun contenant dans un autre (Auteur) ; aucune migration : `contenu` absent = vide, une
#   référence chaîne devient un dict à la première mise.
# - Marée (`contenant.maree`, Sac de Manannán) : temps RÉEL, aucune horloge (cf. portails) ;
#   on dépose à tout moment, on ne voit ni ne reprend le contenu qu'à marée haute.
#
# Pur : mute sans sauver (l'appelant persiste), `now` et les lecteurs injectés.

from models import character_stats
from utils.characters import item_ref_id, item_ref_weight

# Vente à un marchand, don à un atelier : jamais un contenant plein (Auteur, 02/11).
REFUS_PLEIN = "Videz-le d'abord."


def bloc(doc) -> dict:
	b = (doc or {}).get("contenant") if isinstance(doc, dict) else None
	return b if isinstance(b, dict) else {}


def capacite(doc) -> float:
	try:
		return max(0.0, float(bloc(doc).get("capacite_kg") or 0))
	except (TypeError, ValueError):
		return 0.0


def est_contenant(doc) -> bool:
	return capacite(doc) > 0


def a_maree(doc) -> bool:
	return bool(bloc(doc).get("maree"))


def contenu(ref) -> list:
	if isinstance(ref, dict) and isinstance(ref.get("contenu"), list):
		return ref["contenu"]
	return []


def est_vide(ref) -> bool:
	return not contenu(ref)


def poids_contenu(ref, poids_fn=item_ref_weight) -> float:
	return round(sum(poids_fn(r) for r in contenu(ref)), 2)


def poids_total(ref, poids_fn=item_ref_weight) -> float:
	"""Contenant + contenu. ⚠️ Seul usage : la limite de vol d'un coffre (Auteur, 02/11) ;
	partout ailleurs le contenant ne pèse que lui-même."""
	return round(poids_fn(ref) + poids_contenu(ref, poids_fn), 2)


# ── Marée ────────────────────────────────────────────────────────────────────────

def _phase(now: int) -> int:
	"""Secondes écoulées depuis la dernière pleine mer."""
	return (int(now) - int(character_stats.MAREE_REFERENCE_EPOCH)) % int(character_stats.MAREE_PERIODE_S)


def maree_haute(now: int) -> bool:
	"""Fenêtre centrée sur la pleine mer : `fenêtre/2` avant et après."""
	p = _phase(now)
	demi = int(character_stats.MAREE_FENETRE_S) / 2
	return p <= demi or p >= int(character_stats.MAREE_PERIODE_S) - demi


def prochaine_maree(now: int) -> int:
	"""Epoch du début de la prochaine fenêtre de marée haute (strictement après `now` si la
	mer est basse ; si elle est haute, début de la SUIVANTE)."""
	periode = int(character_stats.MAREE_PERIODE_S)
	demi = int(character_stats.MAREE_FENETRE_S) // 2
	p = _phase(now)
	debut = int(now) - p + periode - demi   # début de la fenêtre qui précède la prochaine pleine mer
	while debut <= int(now):
		debut += periode
	return debut


def fin_maree(now: int) -> int | None:
	"""Epoch de fin de la fenêtre en cours, None si la mer est basse."""
	if not maree_haute(now):
		return None
	periode = int(character_stats.MAREE_PERIODE_S)
	demi = int(character_stats.MAREE_FENETRE_S) // 2
	p = _phase(now)
	return int(now) + (demi - p if p <= demi else periode - p + demi)


def accessible(doc, now: int) -> bool:
	"""Le contenu se voit et se reprend : toujours, sauf un contenant à marée hors fenêtre."""
	return not a_maree(doc) or maree_haute(now)


# ── Ranger / sortir ──────────────────────────────────────────────────────────────

def localiser(refs: list, idx, item_id) -> int | None:
	"""Position adressée par index vérifié par `item_id`, repli sur le premier exemplaire
	de l'item (même contrat que `routers/user._take_ref`, sans retirer)."""
	if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(refs) \
			and (item_id is None or item_ref_id(refs[idx]) == item_id):
		return idx
	if item_id is not None:
		return next((i for i, r in enumerate(refs) if item_ref_id(r) == item_id), None)
	return None


def figer_ref(ref, poids_fn=item_ref_weight) -> dict:
	"""La référence en dict : une chaîne legacy prend son poids effectif (la charge portée
	ne bouge pas), comme `characters.renommer_ref`."""
	if isinstance(ref, dict):
		return ref
	return {"item": ref, "poids": poids_fn(ref)}


def peut_ranger(ref_c, doc_c, ref, doc, poids_fn=item_ref_weight) -> tuple[bool, str]:
	if not est_contenant(doc_c):
		return False, "Cet objet n'est pas un contenant."
	if ref is ref_c:
		return False, "Un contenant ne se range pas en lui-même."
	if est_contenant(doc):
		return False, "Un contenant magique ne se range pas dans un autre."
	cap = capacite(doc_c)
	if poids_contenu(ref_c, poids_fn) + poids_fn(ref) > cap + 1e-9:
		return False, f"Le contenant est plein ({cap:g} kg)."
	return True, ""


def ranger(porteur: dict, pos_c: int, pos: int, poids_fn=item_ref_weight) -> dict:
	"""Passe `inventaire[pos]` dans le contenant `inventaire[pos_c]` (gardes faites par
	l'appelant via `peut_ranger`). Renvoie la référence rangée."""
	inv = porteur.get("inventaire") or []
	conteneur = figer_ref(inv[pos_c], poids_fn)
	inv[pos_c] = conteneur
	ref = inv.pop(pos)
	conteneur.setdefault("contenu", []).append(ref)
	porteur["inventaire"] = inv
	return ref


def sortir(porteur: dict, pos_c: int, j: int) -> object:
	"""Remet `contenu[j]` du contenant `inventaire[pos_c]` dans le sac du porteur (charge
	vérifiée par l'appelant). Un contenant vidé perd sa clé `contenu`."""
	inv = porteur.get("inventaire") or []
	conteneur = inv[pos_c]
	ref = conteneur["contenu"].pop(j)
	if not conteneur["contenu"]:
		conteneur.pop("contenu", None)
	inv.append(ref)
	porteur["inventaire"] = inv
	return ref


# ── Vues ─────────────────────────────────────────────────────────────────────────

def resume(ref, doc, now: int, poids_fn=item_ref_weight) -> dict | None:
	"""Bloc léger posé par `resolve_item_ref` sur chaque contenant (sac, sol, coffre…). Hors
	marée, le sac « semble vide » : ni charge ni nombre."""
	if not est_contenant(doc):
		return None
	ouvert = accessible(doc, now)
	out = {
		"capacite_kg": capacite(doc),
		"maree": a_maree(doc),
		"accessible": ouvert,
		"charge_kg": poids_contenu(ref, poids_fn) if ouvert else 0,
		"nb": len(contenu(ref)) if ouvert else 0,
	}
	if out["maree"]:
		out["prochaine_maree_at"] = prochaine_maree(now)
		out["fin_maree_at"] = fin_maree(now)
	return out


def vue(ref, doc, now: int, resolve_fn, poids_fn=item_ref_weight) -> dict:
	"""Bloc complet de `GET /api/contenant` : le résumé + le contenu résolu (indexé par sa
	position réelle), vide hors marée."""
	out = resume(ref, doc, now, poids_fn) or {}
	out["contenu"] = [dict(d, idx=j) for j, r in enumerate(contenu(ref)) if (d := resolve_fn(r))] \
		if out.get("accessible") else []
	return out
