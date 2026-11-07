"""Filtres du panneau marchand (pur) : la TYPOLOGIE d'un objet, en clés de pastilles.

Chaque ligne d'achat, de vente et du catalogue de commande porte `filtres: [clé, …]`,
calculé ICI (Convention §10 : le client ne reclasse jamais un objet). Le client n'affiche que
les pastilles qui ont au moins un objet dans le panneau, et garde une ligne dès qu'UNE de ses
clés est active (inclusion : « Tête » + « Tranchante » montre les deux familles).

Tout se RELIT dans la donnée existante — aucun champ neuf sur les items, aucune migration
(Convention §4) :
- armure  : `slots` (la partie protégée), `sous_categorie` (bouclier) ;
- arme    : tags `cac` / `jet` / `tir` (chaque arme en porte exactement un), `hast`,
            `tranchant`, sous-catégorie `instrument` ;
- prise   : `deux_mains`, `slots` main droite / main gauche (armes, boucliers, catalyseurs) ;
- magie   : catégorie `catalyseur`, item cité par le bloc `composants` d'un SORT (calculé sur
            les sorts : un sort neuf qui cite un objet en fait un ingrédient), livres de sort ;
- conso.  : les EFFETS (soin, mana, renfort) et la sous-catégorie (nourriture, boisson) ;
- matière : catégorie `metal` / `composant` (bois, dépouille de bête, le reste) ;
- fabrication : la matière APPORTE quelque chose à une pièce sur mesure — son bloc
            `fabrication` bien formé (`fabrication.apporte`, source unique). ⚠️ Une VARIANTE
            déjà fabriquée porte aussi un bloc `fabrication` (`base_item`…), qui n'apporte rien :
            elle n'est pas une matière de fabrication ;
- divers  : outils, pièges, outils de CROCHETAGE (`bonus_desamorcage` > 0 : leur usage n'est
            pas évident, la pastille le met en avant), contenants, livres et documents, munitions.

⚠️ « Ingrédient de sort » ne distingue pas consommé / conservé : le même objet est consommé
par un sort et conservé par un autre (12 des 38 ingrédients du dump du 2026-11-05).
"""

from utils import fabrication
from utils import pieges

# ── Catalogue des pastilles ─────────────────────────────────────────────────────
# Ordre = ordre d'affichage dans l'overlay. (clé de groupe, icône, libellé, pastilles) ;
# une pastille = (clé, libellé). La clé complète est `<groupe>.<pastille>`.
GROUPES = (
	("armure", "🛡️", "Armure", (
		("tete", "Tête"), ("cou", "Cou"), ("epaules", "Épaules"), ("torse", "Torse"),
		("mains", "Mains"), ("ceinture", "Ceinture"), ("jambes", "Jambes"), ("pieds", "Pieds"),
		("anneaux", "Anneaux"), ("bouclier", "Bouclier"), ("monture", "Monture"),
	)),
	("arme", "⚔️", "Arme", (
		("cac", "Corps à corps"), ("hast", "Hast"), ("jet", "Jet"), ("tir", "Tir"),
		("tranchant", "Tranchante"), ("instrument", "Instrument"),
	)),
	("prise", "✋", "Prise en main", (
		("une", "Une main"), ("deux", "Deux mains"), ("gauche", "Main gauche"),
	)),
	("magie", "✨", "Magie", (
		("catalyseur", "Catalyseur"), ("ingredient", "Ingrédient de sort"), ("grimoire", "Grimoire"),
	)),
	("conso", "🧪", "Consommable", (
		("soin", "Soin"), ("mana", "Mana"), ("renfort", "Renfort"),
		("nourriture", "Nourriture"), ("boisson", "Boisson"),
	)),
	("matiere", "🪵", "Matières premières", (
		("metal", "Métaux"), ("bois", "Bois"), ("depouille", "Dépouilles"), ("autre", "Autres matières"),
	)),
	("fabrication", "🔨", "Fabrication", (
		("ameliore", "Améliore une pièce"),
	)),
	("divers", "🎒", "Divers", (
		("outil", "Outils"), ("piege", "Pièges"), ("crochetage", "Crochetage"), ("contenant", "Contenants"),
		("livre", "Livres & documents"), ("munition", "Munitions"),
	)),
)

# Emplacement d'armure → pastille. Les deux anneaux n'en font qu'une ; la monture regroupe
# ses trois pièces de harnachement.
_SLOT_ARMURE = {
	"tete": "tete", "cou": "cou", "epaules": "epaules", "torse": "torse", "mains": "mains",
	"ceinture": "ceinture", "jambes": "jambes", "pieds": "pieds",
	"anneau_1": "anneaux", "anneau_2": "anneaux",
	"monture_dos": "monture", "monture_poitrail": "monture", "monture_tete": "monture",
}
_TAGS_ARME = ("cac", "hast", "jet", "tir", "tranchant")
_SC_GRIMOIRE = frozenset({"grimoire", "livre_sort"})
_SC_NOURRITURE = frozenset({"boulangerie", "cuisine", "legume", "fruit", "salaison"})
# Sous-catégories de composant tirées d'une bête, en plus de `source_espece` / `portion_de`.
_SC_DEPOUILLE = frozenset({"carcasse", "ossements"})


def catalogue() -> list:
	"""Le catalogue sérialisé pour le client : `[{cle, icon, nom, pastilles: [{cle, nom}]}]`,
	clés de pastille COMPLÈTES (`armure.tete`)."""
	return [{"cle": g, "icon": icon, "nom": nom,
			 "pastilles": [{"cle": f"{g}.{p}", "nom": libelle} for p, libelle in pastilles]}
			for g, icon, nom, pastilles in GROUPES]


def ingredients_sorts(sort_docs) -> frozenset:
	"""`item:*` cités par le bloc `composants` d'au moins un sort, consommés ou non."""
	ids = set()
	for doc in sort_docs or []:
		comps = (doc or {}).get("composants")
		for c in (comps if isinstance(comps, list) else []):
			if isinstance(c, dict) and isinstance(c.get("item"), str) and c["item"]:
				ids.add(c["item"])
	return frozenset(ids)


def _nombre_positif(v) -> bool:
	try:
		return float(v) > 0
	except (TypeError, ValueError):
		return False


def filtres_item(item: dict, ingredients: frozenset = frozenset()) -> list:
	"""Clés de pastilles d'un doc item (résolu), sans doublon.

	`ingredients` : `ingredients_sorts(...)`, calculé UNE fois par liste par l'appelant."""
	item = item or {}
	cat = item.get("categorie") or ""
	sc = item.get("sous_categorie") or ""
	tags = set(item.get("tags") or [])
	slots = list(item.get("slots") or [])
	item_id = item.get("item") or item.get("_id")
	cles = []

	if cat == "armure":
		cles += ["armure." + _SLOT_ARMURE[s] for s in slots if s in _SLOT_ARMURE]
		if sc == "bouclier" or (sc == "" and "main_gauche" in slots):
			cles.append("armure.bouclier")

	if cat == "arme":
		cles += ["arme." + t for t in _TAGS_ARME if t in tags]
		if sc == "instrument":
			cles.append("arme.instrument")

	if "main_droite" in slots or "main_gauche" in slots:
		if item.get("deux_mains"):
			cles.append("prise.deux")
		else:
			cles.append("prise.une")
			if "main_gauche" in slots:
				cles.append("prise.gauche")

	if cat == "catalyseur":
		cles.append("magie.catalyseur")
	if item_id in ingredients:
		cles.append("magie.ingredient")
	if cat == "livre" and sc in _SC_GRIMOIRE:
		cles.append("magie.grimoire")

	if cat == "consommable":
		effets = item.get("effets") if isinstance(item.get("effets"), dict) else {}
		if _nombre_positif(effets.get("pv")) or _nombre_positif(effets.get("regen_pv")):
			cles.append("conso.soin")
		if _nombre_positif(effets.get("pm")) or _nombre_positif(effets.get("regen_pm")):
			cles.append("conso.mana")
		if effets.get("buffs"):
			cles.append("conso.renfort")
		if sc in _SC_NOURRITURE:
			cles.append("conso.nourriture")
		if sc == "boisson":
			cles.append("conso.boisson")

	if cat == "metal":
		cles.append("matiere.metal")
	elif cat == "composant":
		if "bois" in tags:
			cles.append("matiere.bois")
		elif item.get("source_espece") or item.get("portion_de") or sc in _SC_DEPOUILLE:
			cles.append("matiere.depouille")
		else:
			cles.append("matiere.autre")

	if fabrication.apporte(item):
		cles.append("fabrication.ameliore")

	est_piege = "piege" in tags
	est_contenant = "contenant" in tags or sc == "contenant" or isinstance(item.get("contenant"), dict)
	if est_piege:
		cles.append("divers.piege")
	est_crochetage = _nombre_positif(item.get(pieges.CLE_BONUS_OUTIL))
	if est_crochetage:
		cles.append("divers.crochetage")
	if est_contenant:
		cles.append("divers.contenant")
	if cat == "outil" and not (est_piege or est_contenant or est_crochetage):
		cles.append("divers.outil")
	if cat == "document" or (cat == "livre" and sc not in _SC_GRIMOIRE):
		cles.append("divers.livre")
	if cat == "munition":
		cles.append("divers.munition")

	vus = set()
	return [c for c in cles if not (c in vus or vus.add(c))]
