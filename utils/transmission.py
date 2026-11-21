# Transmettre un objet (pur) — UN geste pour tout ce que le groupe a en main.
#
# Trois sortes d'emplacement, source comme cible :
#   - `sol`        : le tas du lieu où se tient le PRINCIPAL (`objets_au_sol`, transitoire) ;
#   - `sac`        : l'inventaire d'un porteur (principal, compagnon, monture, guide) ;
#   - `contenant`  : le contenu d'un contenant porté (utils/contenants.py), adressé par sa
#                    position dans le sac de son porteur, vérifiée par son item_id.
#
# Règles, reprises des gestes qu'il remplace (poser, ramasser pour un autre, transférer,
# ranger, sortir, poser depuis un contenant) :
#   - vers un SAC : refus DUR si le porteur ne peut pas porter (`recrutement.peut_porter`),
#     jamais d'auto-délestage (on ne fait pas tomber la cargaison d'un autre) ;
#   - vers un CONTENANT : `contenants.peut_ranger` (place, pas un contenant dans un autre,
#     pas en lui-même) ; on dépose à tout moment, marée basse comprise ;
#   - DEPUIS un contenant : seulement s'il est accessible (marée haute) ;
#   - vers le SOL : toujours.
# Refus ⇒ RIEN n'a bougé : on localise et on contrôle avant de retirer.
#
# Pur : mute sans sauver (l'appelant persiste chaque doc touché), `now` et `get_doc_fn`
# injectés.

from utils import contenants
from utils import recrutement
from utils.characters import item_ref_id, item_ref_weight


def emplacement_sol() -> dict:
	return {"genre": "sol"}


def emplacement_sac(porteur: dict) -> dict:
	return {"genre": "sac", "porteur": porteur}


def emplacement_contenant(porteur: dict, index_c, item_id_c) -> dict:
	return {"genre": "contenant", "porteur": porteur, "index": index_c, "item_id": item_id_c}


def _nom(porteur: dict) -> str:
	# Une monture n'a pas de `prenom` : replier sur `nom`, comme `recrutement.transferer_ref`.
	return ((porteur.get("prenom") or "").strip() or (porteur.get("nom") or "").strip()
			or "Le destinataire")


def meme_emplacement(a: dict, b: dict, get_doc_fn) -> bool:
	"""Source et cible désignent-elles le même tas ? (porteur comparé par IDENTITÉ : l'appelant
	résout un même id en un seul dict.)"""
	if a["genre"] != b["genre"]:
		return False
	if a["genre"] == "sol":
		return True
	if a["porteur"] is not b["porteur"]:
		return False
	if a["genre"] == "sac":
		return True
	pa, _ = contenants.contenant_de(a["porteur"], a["index"], a["item_id"], get_doc_fn)
	pb, _ = contenants.contenant_de(b["porteur"], b["index"], b["item_id"], get_doc_fn)
	return pa is not None and pa == pb


def transmettre(source: dict, cible: dict, au_sol: list, idx, item_id, get_doc_fn, now: int,
				poids_fn=item_ref_weight) -> tuple[bool, int, str, object]:
	"""Passe l'objet `idx`/`item_id` de `source` à `cible`. Mute en place `au_sol`, les sacs et
	les contenants concernés ; NE SAUVEGARDE PAS. → (ok, code HTTP du refus, raison, réf).

	Codes : 422 requête incohérente (objet absent, même emplacement), 404 contenant introuvable,
	409 refus de règle (charge, place, marée)."""
	if meme_emplacement(source, cible, get_doc_fn):
		return False, 422, "L'objet y est déjà.", None

	# ── 1. Localiser dans la source, en LECTURE ──────────────────────────────────
	genre_s = source["genre"]
	if genre_s == "sol":
		liste_s = au_sol
		absent = "Objet absent du sol"
	elif genre_s == "sac":
		liste_s = source["porteur"].setdefault("inventaire", [])
		absent = "Objet absent de l'inventaire"
	else:
		pos_c, doc_c = contenants.contenant_de(source["porteur"], source["index"], source["item_id"], get_doc_fn)
		if pos_c is None:
			return False, 404, "Contenant introuvable dans ce sac.", None
		if not contenants.accessible(doc_c, now):
			return False, 409, "La mer s'est retirée : le sac semble vide jusqu'à la prochaine marée haute.", None
		ref_cs = contenants.figer_ref(source["porteur"]["inventaire"][pos_c], poids_fn)
		source["porteur"]["inventaire"][pos_c] = ref_cs
		liste_s = ref_cs.setdefault("contenu", [])
		absent = "Cet objet n'est plus dans le contenant."
	pos = contenants.localiser(liste_s, idx, item_id)
	if pos is None:
		if genre_s == "contenant":
			contenants.nettoyer(ref_cs)
		return False, 422, absent, None
	ref = liste_s[pos]

	# ── 2. Contrôler la cible (réf du contenant visé figée AVANT tout retrait : sa position
	#       peut glisser si l'objet quitte le même sac) ─────────────────────────────
	genre_c = cible["genre"]
	ref_cc = None
	if genre_c == "sac":
		if not recrutement.peut_porter(cible["porteur"], ref):
			if genre_s == "contenant":
				contenants.nettoyer(ref_cs)
			return False, 409, f"{_nom(cible['porteur'])} ne peut pas porter davantage.", None
	elif genre_c == "contenant":
		pos_cc, doc_cc = contenants.contenant_de(cible["porteur"], cible["index"], cible["item_id"], get_doc_fn)
		if pos_cc is None:
			if genre_s == "contenant":
				contenants.nettoyer(ref_cs)
			return False, 404, "Contenant introuvable dans ce sac.", None
		inv_c = cible["porteur"]["inventaire"]
		ok, raison = contenants.peut_ranger(inv_c[pos_cc], doc_cc, ref, get_doc_fn(item_ref_id(ref)), poids_fn)
		if not ok:
			if genre_s == "contenant":
				contenants.nettoyer(ref_cs)
			return False, 409, raison, None
		ref_cc = contenants.figer_ref(inv_c[pos_cc], poids_fn)
		inv_c[pos_cc] = ref_cc

	# ── 3. Retirer, puis remettre ──────────────────────────────────────────────────
	liste_s.pop(pos)
	if genre_s == "contenant":
		contenants.nettoyer(ref_cs)
	if genre_c == "sol":
		au_sol.append(ref)
	elif genre_c == "sac":
		cible["porteur"].setdefault("inventaire", []).append(ref)
	else:
		ref_cc.setdefault("contenu", []).append(ref)
	return True, 0, "", ref
