"""Variantes fabriquées sur mesure (pur) : un objet de BASE + des MATIÈRES → un item dérivé
et sa recette, tous deux déterministes et idempotents.

Miroir de `utils/grimoires.py` : aucune DB au niveau module, on reçoit des docs et on rend des
docs. `assurer_variante` est le seul point qui écrit, et il est calqué sur
`scriptorium._assurer_item_livre` — un doc déjà en base n'est JAMAIS retouché.

Trois règles portent tout le reste :

1. **Ce qu'une matière apporte vit dans la DONNÉE**, dans son bloc `fabrication` (cf.
   `proprietes_matiere`). Le code ne connaît aucune matière par son nom ; il ne connaît que la
   liste blanche des champs qu'une matière a le droit de toucher (`CLES_MODIFIABLES`).
2. **L'identité d'une variante ne dépend pas de l'ordre de saisie** : les matières sont
   normalisées (agrégées par id, triées) avant d'être hachées. « épée + acier + cristal » et
   « épée + cristal + acier » sont la MÊME variante, donc le même doc.
3. **La recette générée porte `sur_commande: True`** et n'entre pas dans les index de production
   de `utils/marche.py` : elle sert au prix et à l'historique, jamais au tick d'atelier. Sans ce
   drapeau, chaque variante commandée par un joueur se mettrait à être fabriquée et vendue
   spontanément par toutes les boutiques de la catégorie, et ses intrants deviendraient
   achetables au comptoir (`appro_leaves_categorie`).
"""

import hashlib
import json

from models import character_stats

# Le drapeau qui sort une recette des index de production. Lu par `utils/marche.py` ; défini
# ICI parce que c'est ce module qui écrit les recettes qui le portent.
CLE_SUR_COMMANDE = "sur_commande"

PREFIXE_RECETTE = "recette:commande_"

# Longueur de la signature d'une combinaison. 8 hexa = 4 milliards de combinaisons ; la
# collision est contrôlée à l'écriture (`assurer_variante` refuse un `_id` pris par un doc
# qui n'est pas cette variante-là), jamais supposée impossible.
SIGNATURE_LONGUEUR = 8

# ── Ce qu'une matière a le droit de modifier ─────────────────────────────────────
# ⚠️ LISTE BLANCHE, pas une liste noire. Un doc de contenu ne doit pas pouvoir injecter
# `slots` (l'objet changerait d'emplacement), `sorts` (il enseignerait un sort), `carte`,
# `type` ni `_id`. Tout champ hors de cette liste est ignoré en silence — une matière mal
# rédigée n'apporte rien, elle ne casse rien.
#
# Trois façons de composer, choisies par le champ et non par la matière :
#   ADDITIF      : les `bonus_*` scalaires s'ajoutent au base puis entre matières.
#   FUSION       : `bonus` (par caractéristique) et `effets` (par clé d'effet) s'ajoutent
#                  clé à clé — deux matières qui donnent +1 F donnent +2 F.
#   MAX          : `restriction` prend le plus exigeant — alourdir une arme ne peut pas la
#                  rendre plus facile à porter.
#   FACTEUR      : `poids` et `valeur` sont multiplicatifs ({"facteur": 1.1}), parce qu'ils
#                  varient avec la taille de l'objet et non par un delta absolu.
CLES_ADDITIVES = (
	"bonus_degats", "bonus_degats_dice", "bonus_cc", "bonus_cd",
	"bonus_pa", "bonus_pm", "bonus_pv", "bonus_initiative", "bonus_malus_depl",
	"portee",
)
CLES_FUSIONNEES = ("bonus", "effets")
CLES_MAX = ("restriction",)
CLES_FACTEUR = ("poids", "valeur")

CLES_MODIFIABLES = frozenset(CLES_ADDITIVES + CLES_FUSIONNEES + CLES_MAX + CLES_FACTEUR + ("rarete",))

# Bornes de sécurité : une matière ne peut pas transformer un objet en autre chose. Un dé de
# dégâts reste un dé plausible, un facteur reste dans un ordre de grandeur crédible.
DICE_MAX = 20
FACTEUR_MIN = 0.1
FACTEUR_MAX = 10.0


def _slug(item_id: str) -> str:
	"""`item:Epee_longue` → `Epee_longue`. Rend la chaîne telle quelle si elle n'est pas préfixée."""
	return item_id[len("item:"):] if str(item_id or "").startswith("item:") else str(item_id or "")


# ── Ce qu'une matière apporte ────────────────────────────────────────────────────

def proprietes_matiere(item_doc) -> dict:
	"""Bloc `fabrication` d'un doc matière, normalisé `{"nom": str, "modificateurs": dict}`.

	Absent ou malformé ⇒ `{"nom": "", "modificateurs": {}}` : la matière est utilisable (elle
	coûte son prix et pèse son poids) mais n'apporte aucune propriété. C'est le comportement
	voulu pour les 1 324 items déjà en base, dont aucun ne porte ce bloc."""
	bloc = (item_doc or {}).get("fabrication")
	if not isinstance(bloc, dict):
		return {"nom": "", "modificateurs": {}}
	mods = bloc.get("modificateurs")
	return {
		"nom": str(bloc.get("nom") or "").strip(),
		"modificateurs": {k: v for k, v in mods.items() if k in CLES_MODIFIABLES} if isinstance(mods, dict) else {},
	}


def _rang_rarete(rarete) -> float:
	"""Position d'une rareté dans l'échelle des prix. Sert à prendre « la plus haute » sans
	recopier l'ordre : `MULT_RARETE` EST l'échelle (cf. CLAUDE.md §14, aucune valeur en dur)."""
	return float(character_stats.MULT_RARETE.get(str(rarete or ""), 0) or 0)


def _facteur(spec) -> float:
	"""Facteur multiplicatif d'un modificateur `{"facteur": x}`, borné. Une forme inattendue
	vaut 1.0 (neutre) plutôt que de lever : une matière mal rédigée n'apporte rien."""
	if not isinstance(spec, dict):
		return 1.0
	val = spec.get("facteur")
	if not isinstance(val, (int, float)) or isinstance(val, bool):
		return 1.0
	return max(FACTEUR_MIN, min(FACTEUR_MAX, float(val)))


def _nombre(val) -> float:
	return float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else 0.0


def appliquer_modificateurs(base_doc: dict, matieres_docs: list) -> dict:
	"""Champs de l'objet fini = champs du base + apport de chaque matière, selon la règle de
	composition du champ (cf. en-tête). Déterministe : mêmes entrées ⇒ mêmes sorties, quel que
	soit l'ordre des matières (les opérations sont toutes commutatives).

	`matieres_docs` = liste de `(item_doc, quantite)`. La quantité MULTIPLIE l'apport additif
	(deux lingots d'acier valent deux fois le bonus) mais pas les facteurs, qui se composent une
	seule fois par matière — sans quoi commander dix lingots rendrait l'arme dix fois plus lourde
	ET dix fois plus chère, ce qui n'est pas ce que « une épée en acier » veut dire.
	"""
	sortie = {}

	additifs = {k: _nombre((base_doc or {}).get(k)) for k in CLES_ADDITIVES if (base_doc or {}).get(k) is not None}
	fusions = {k: dict((base_doc or {}).get(k) or {}) for k in CLES_FUSIONNEES
			   if isinstance((base_doc or {}).get(k), dict)}
	maxima = {k: dict((base_doc or {}).get(k) or {}) for k in CLES_MAX
			  if isinstance((base_doc or {}).get(k), dict)}
	facteurs = {k: 1.0 for k in CLES_FACTEUR}
	rarete = (base_doc or {}).get("rarete")

	for item_doc, quantite in matieres_docs:
		mods = proprietes_matiere(item_doc)["modificateurs"]
		qte = max(1, int(quantite or 1))
		for cle, val in mods.items():
			if cle in CLES_ADDITIVES:
				additifs[cle] = additifs.get(cle, 0.0) + _nombre(val) * qte
			elif cle in CLES_FUSIONNEES and isinstance(val, dict):
				cible = fusions.setdefault(cle, {})
				for sous_cle, delta in val.items():
					cible[sous_cle] = _nombre(cible.get(sous_cle)) + _nombre(delta) * qte
			elif cle in CLES_MAX and isinstance(val, dict):
				cible = maxima.setdefault(cle, {})
				for sous_cle, seuil in val.items():
					cible[sous_cle] = max(_nombre(cible.get(sous_cle)), _nombre(seuil))
			elif cle in CLES_FACTEUR:
				facteurs[cle] = facteurs[cle] * _facteur(val)
			elif cle == "rarete" and _rang_rarete(val) > _rang_rarete(rarete):
				rarete = val

	for cle, val in additifs.items():
		arrondi = int(round(val))
		if cle == "bonus_degats_dice":
			arrondi = max(0, min(DICE_MAX, arrondi))
		sortie[cle] = arrondi
	for cle, val in fusions.items():
		nettoye = {k: int(round(v)) for k, v in val.items() if int(round(_nombre(v))) != 0}
		if nettoye:
			sortie[cle] = nettoye
	for cle, val in maxima.items():
		nettoye = {k: int(round(v)) for k, v in val.items() if int(round(_nombre(v))) != 0}
		if nettoye:
			sortie[cle] = nettoye
	if rarete:
		sortie["rarete"] = rarete
	sortie["_facteurs"] = facteurs   # consommés par `variante_doc`, jamais écrits sur le doc
	return sortie


# ── Identité d'une combinaison (§14 du cahier des charges) ───────────────────────

def normaliser_matieres(matieres) -> list:
	"""`[{"item": id, "quantite": n}, …]` agrégé par id et trié par id.

	C'est LE point qui rend une variante indépendante de l'ordre de saisie : deux commandes des
	mêmes matières dans un ordre différent produisent la même liste, donc la même signature,
	donc le même doc. Les quantités absentes valent 1 ; les entrées sans id sont écartées."""
	cumul: dict[str, int] = {}
	for entree in (matieres or []):
		if isinstance(entree, str):
			item_id, quantite = entree, 1
		elif isinstance(entree, dict):
			item_id = entree.get("item") or entree.get("_id")
			quantite = entree.get("quantite", 1)
		else:
			continue
		if not item_id:
			continue
		try:
			quantite = max(1, int(quantite or 1))
		except (TypeError, ValueError):
			quantite = 1
		cumul[item_id] = cumul.get(item_id, 0) + quantite
	return [{"item": k, "quantite": cumul[k]} for k in sorted(cumul)]


def signature(base_id: str, matieres) -> str:
	"""Empreinte stable d'une combinaison (base + matières normalisées).

	⚠️ `sha1` et non `hash()` : le hachage natif de Python est salé par processus, deux
	redémarrages du serveur donneraient deux ids pour la même épée."""
	charge = json.dumps(
		{"base": base_id, "matieres": normaliser_matieres(matieres)},
		sort_keys=True, ensure_ascii=False, separators=(",", ":"),
	)
	return hashlib.sha1(charge.encode("utf-8")).hexdigest()[:SIGNATURE_LONGUEUR]


def variante_id(base_doc: dict, matieres) -> str:
	base_id = (base_doc or {}).get("_id") or (base_doc or {}).get("item") or ""
	return "item:%s_%s" % (_slug(base_id), signature(base_id, matieres))


def recette_id(base_doc: dict, matieres) -> str:
	base_id = (base_doc or {}).get("_id") or (base_doc or {}).get("item") or ""
	return "%s%s_%s" % (PREFIXE_RECETTE, _slug(base_id), signature(base_id, matieres))


def nom_variante(base_doc: dict, matieres_docs: list) -> str:
	"""« Épée longue en acier au cristal de feu » — le nom du base suivi du fragment `nom` de
	chaque matière qui en porte un, dans l'ordre NORMALISÉ (par id) pour que la même
	combinaison se lise toujours pareil. Une matière sans fragment ne s'affiche pas."""
	base_nom = (base_doc or {}).get("nom") or _slug((base_doc or {}).get("_id") or "")
	fragments = [f for f in (proprietes_matiere(doc)["nom"] for doc, _q in matieres_docs) if f]
	return " ".join([base_nom] + fragments) if fragments else base_nom


# ── Construction des docs ────────────────────────────────────────────────────────

# Champs du doc de base repris tels quels par la variante. ⚠️ Liste blanche elle aussi : on
# ne recopie PAS `_rev` (la variante est un doc neuf), ni `fabrication` (le base pourrait être
# lui-même une variante — la traçabilité de CELLE-CI est réécrite plus bas), ni `valeur` (elle
# est recalculée et figée, cf. `valeur_variante`).
CHAMPS_HERITES = (
	"icon", "categorie", "sous_categorie", "slots", "tags", "deux_mains",
	"cible", "description",
)


def valeur_variante(cout_base_cuivre: int, cout_matieres_cuivre: int) -> list:
	"""`valeur` explicite de la variante, en cuivre, sous la forme d'une fourchette.

	⚠️ Une `valeur` explicite est AUTORITATIVE pour `marche.cout_production_cuivre`, qui cesse
	alors de propager (« prix maîtrisé à la main, pas de propagation »). C'est délibéré : sans
	elle, le coût se recalculerait `(coût_base + matières) × MARGE_TRANSFO`, et comme le coût du
	base est DÉJÀ le produit d'une étape à ×5, une simple épée en acier vaudrait vingt-cinq fois
	ses intrants. Le sur-mesure a sa propre marge, `COMMANDE_MARGE`."""
	socle = max(1, int(round((int(cout_base_cuivre or 0) + int(cout_matieres_cuivre or 0))
							 * float(character_stats.COMMANDE_MARGE))))
	plafond = max(socle + 1, int(round(socle * float(character_stats.PRIX_MAX_FACTEUR))))
	return [{"cu": socle}, {"cu": plafond}]


def variante_doc(base_doc: dict, matieres_docs: list, lieu_id: str = "",
				 cout_base_cuivre: int = 0, cout_matieres_cuivre: int = 0,
				 now: int = 0) -> dict:
	"""Doc `item:*` complet de la variante. `matieres_docs` = `[(item_doc, quantite), …]`.

	Le résultat conserve les caractéristiques intrinsèques du base (catégorie, emplacements,
	portée, prise à deux mains…) et reçoit les apports des matières. Il porte en plus le bloc
	`fabrication`, qui permet de le RECALCULER ou de le vérifier à partir de ses sources."""
	matieres = normaliser_matieres([{"item": (d or {}).get("_id") or (d or {}).get("item"), "quantite": q}
									for d, q in matieres_docs])
	mods = appliquer_modificateurs(base_doc, matieres_docs)
	facteurs = mods.pop("_facteurs", {})

	doc = {
		"_id": variante_id(base_doc, matieres),
		"type": "item",
		"nom": nom_variante(base_doc, matieres_docs),
	}
	for cle in CHAMPS_HERITES:
		if (base_doc or {}).get(cle) is not None:
			doc[cle] = (base_doc or {}).get(cle)
	doc.setdefault("slots", [])
	doc.update(mods)

	# Poids : le base peut porter [min, max] (poids d'instance) — le facteur s'applique aux deux
	# bornes, la forme est conservée telle quelle.
	poids_base = (base_doc or {}).get("poids", 0)
	facteur_poids = facteurs.get("poids", 1.0)
	if isinstance(poids_base, (list, tuple)) and len(poids_base) >= 2:
		doc["poids"] = [round(float(poids_base[0] or 0) * facteur_poids, 2),
						round(float(poids_base[1] or 0) * facteur_poids, 2)]
	else:
		doc["poids"] = round(float(poids_base or 0) * facteur_poids, 2)

	valeur = valeur_variante(cout_base_cuivre, cout_matieres_cuivre)
	facteur_valeur = facteurs.get("valeur", 1.0)
	if facteur_valeur != 1.0:
		valeur = [{"cu": max(1, int(round(entree["cu"] * facteur_valeur)))} for entree in valeur]
	doc["valeur"] = valeur

	doc["fabrication"] = {
		"base_item": (base_doc or {}).get("_id") or (base_doc or {}).get("item"),
		"matieres": matieres,
		"recette": recette_id(base_doc, matieres),
		"cree_at": int(now or 0),
		"lieu": lieu_id or "",
	}
	return doc


def recette_variante_doc(base_doc: dict, matieres_docs: list, lieu_categorie: str) -> dict:
	"""Doc `recette:*` de la variante — une recette NORMALE du jeu (`type: "recette"`, forme
	`matieres_premieres` déjà lue par `marche.recette_matieres`), à un drapeau près.

	⚠️ `sur_commande: True` la retire des index de PRODUCTION (`marche._get_marche_map`,
	`marche.lieu_recettes`) tout en la laissant dans l'index de PRIX (`marche._get_recipe_map`).
	Elle dit donc comment l'objet a été fait et ce qu'il vaut, sans qu'aucun atelier ne se mette
	à le cuire tout seul.

	⚠️ L'objet de base est un INTRANT de la recette, au même titre que les matières : c'est ce
	qui fait de la variante une transformation traçable et non un objet surgi de rien."""
	matieres = normaliser_matieres([{"item": (d or {}).get("_id") or (d or {}).get("item"), "quantite": q}
									for d, q in matieres_docs])
	base_id = (base_doc or {}).get("_id") or (base_doc or {}).get("item") or ""
	return {
		"_id": recette_id(base_doc, matieres),
		"type": "recette",
		CLE_SUR_COMMANDE: True,
		"lieu_categorie": lieu_categorie or "",
		"base_item": base_id,
		"objet_final": _slug(variante_id(base_doc, matieres)),
		"quantite_produite": 1,
		"matieres_premieres": [{"item": base_id, "quantite": 1}] + [dict(m) for m in matieres],
	}


def assurer_variante(base_doc: dict, matieres_docs: list, lieu_doc: dict,
					 get_doc_fn, save_doc_fn, cout_base_cuivre: int = 0,
					 cout_matieres_cuivre: int = 0, now: int = 0) -> tuple:
	"""`(item_doc, cree)` — la définition de la variante, créée en base si elle n'y est pas.

	Miroir de `scriptorium._assurer_item_livre` : **un doc déjà existant n'est JAMAIS retouché**.
	Une deuxième commande de la même combinaison ne crée donc pas une deuxième définition, elle
	réutilise celle-ci et ne produira qu'un nouvel exemplaire (cf. §14 du cahier des charges).

	⚠️ Un `_id` occupé par un doc qui n'est PAS cette variante (collision de signature, ou
	slug déjà pris par un item authoré) fait lever : un PUT complet l'écraserait en silence
	(CLAUDE.md §11). L'appelant traduit en 409."""
	matieres = normaliser_matieres([{"item": (d or {}).get("_id") or (d or {}).get("item"), "quantite": q}
									for d, q in matieres_docs])
	item_id = variante_id(base_doc, matieres)
	existant = get_doc_fn(item_id)
	if existant is not None:
		if (existant.get("fabrication") or {}).get("base_item") != ((base_doc or {}).get("_id")
																	or (base_doc or {}).get("item")):
			raise ValueError("%s existe déjà et n'est pas une variante de cet objet" % item_id)
		return existant, False

	doc = variante_doc(base_doc, matieres_docs, (lieu_doc or {}).get("_id", ""),
					   cout_base_cuivre, cout_matieres_cuivre, now)
	recette = recette_variante_doc(base_doc, matieres_docs, (lieu_doc or {}).get("categorie", ""))
	# L'item d'abord : une recette qui produirait un item absent serait un trou ; l'inverse est
	# seulement une variante sans historique, récupérable au prochain passage.
	save_doc_fn(doc)
	if get_doc_fn(recette["_id"]) is None:
		save_doc_fn(recette)
	return doc, True
