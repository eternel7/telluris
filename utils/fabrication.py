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
#                  clé à clé — deux matières qui donnent +1 F donnent +2 F (⚠️ SAUF un bonus
#                  de V POSITIF, composé par MAX : sang + cœur = +1 V) — et de sous-dict
#                  en sous-dict : `effets.buffs` d'un consommable se fusionne comme le reste,
#                  il ne se perd pas parce qu'il n'est pas un nombre.
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
# Exception à la FUSION de `bonus` : la Vitesse se compose par MAX (cf. `appliquer_modificateurs`).
CARACT_VITESSE = "V"
CLES_MAX = ("restriction",)
CLES_FACTEUR = ("poids", "valeur")

CLES_MODIFIABLES = frozenset(CLES_ADDITIVES + CLES_FUSIONNEES + CLES_MAX + CLES_FACTEUR + ("rarete",))

# ── Bonus selon la FAMILLE de la pièce ───────────────────────────────────────────
# Une matière porte UN bloc de modificateurs, quelle que soit la pièce où elle entre ; la
# pièce n'en retient que les bonus de SON rôle. Sans ce filtre, un casque en mithril donnait
# +7 dégâts à toutes les attaques, et un fouet +6 PA — hors de toute zone, donc PARTOUT.
# Bonus hors famille : ignoré si le base ne le porte pas, sinon la valeur finale est plafonnée
# à base × `FABRICATION_PLAFOND_HORS_FAMILLE` (Dague de parade, Pelta : la matière renforce ce
# que la pièce sait déjà faire, elle ne lui donne pas un rôle neuf).
# `effets` n'est pas filtré ici : sa direction (cible vs porteur) est contrôlée par matière
# à la génération (`dev/gen_fabrication_matieres.effets_mal_diriges`) et le lecteur d'une
# pièce portée n'en lit que les clés de porteur. `restriction`, `poids`, `valeur` et `rarete`
# ne sont pas des bonus : jamais filtrés.
CLES_FILTREES_FAMILLE = CLES_ADDITIVES + ("bonus",)
_PORTE = frozenset({"bonus_pv", "bonus_pm", "bonus"})
CLES_PAR_FAMILLE = {
	"arme": frozenset({"bonus_degats", "bonus_degats_dice", "bonus_cc", "bonus_cd", "portee",
					   "bonus_initiative", "bonus"}),
	"armure": _PORTE | {"bonus_pa", "bonus_malus_depl"},
	"bijou": _PORTE,
	"catalyseur": _PORTE,
	"consommable": frozenset(),
}
# Emplacements d'une `armure` qui ne PROTÈGENT pas : une pièce qui n'occupe qu'eux est un bijou.
SLOTS_BIJOU = frozenset({"cou", "ceinture", "anneau_1", "anneau_2"})


def famille_piece(base_doc) -> str | None:
	"""Famille de la pièce à façonner, au sens des bonus qu'elle peut recevoir (cf.
	`CLES_PAR_FAMILLE`). `None` = catégorie hors de la table : aucun filtre (comportement
	d'avant)."""
	doc = base_doc or {}
	categorie = doc.get("categorie")
	if categorie == "armure":
		slots = set(doc.get("slots") or [])
		return "bijou" if slots and slots <= SLOTS_BIJOU else "armure"
	return categorie if categorie in CLES_PAR_FAMILLE else None


def _borne(base_val, val, plafond):
	"""Valeur hors famille : celle du base si le base ne porte pas ce bonus (≤ 0), sinon
	`val` plafonnée à base × plafond. Rend `None` quand la clé doit disparaître."""
	b = _nombre(base_val)
	if b <= 0:
		return base_val if base_val is not None else None
	return min(_nombre(val), b * plafond)


def borner_hors_famille(base_doc, valeurs: dict) -> dict:
	"""Applique la règle de famille aux bonus déjà composés (`valeurs`, mutée et rendue) :
	clés de `CLES_FILTREES_FAMILLE` hors de la famille de `base_doc` ramenées au base ou
	plafonnées. Source unique : `appliquer_modificateurs` et `dev/gen_bonus_famille_variantes.py`
	(correction des variantes déjà en base)."""
	famille = famille_piece(base_doc)
	if famille is None:
		return valeurs
	permises = CLES_PAR_FAMILLE[famille]
	plafond = float(character_stats.FABRICATION_PLAFOND_HORS_FAMILLE)
	base = base_doc or {}
	for cle in CLES_FILTREES_FAMILLE:
		if cle in permises or cle not in valeurs:
			continue
		if cle == "bonus":
			base_bonus = base.get("bonus") if isinstance(base.get("bonus"), dict) else {}
			bonus = {}
			for car, val in (valeurs.get("bonus") or {}).items():
				borne = _borne(base_bonus.get(car), val, plafond)
				if borne is not None:
					bonus[car] = int(round(borne)) if isinstance(borne, float) else borne
			if bonus:
				valeurs["bonus"] = bonus
			else:
				valeurs.pop("bonus")
			continue
		borne = _borne(base.get(cle), valeurs[cle], plafond)
		if borne is None:
			valeurs.pop(cle)
		else:
			valeurs[cle] = int(round(borne)) if isinstance(borne, float) else borne
	return valeurs

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


def apporte(item_doc) -> bool:
	"""Cette matière apporte-t-elle quelque chose à une pièce ? Un nom de variante, des
	modificateurs, ou les deux.

	SOURCE UNIQUE de la question, parce que deux modules la posent : `commande.matiere_acceptee`
	pour admettre une matière (une matière sans apport ne ferait que renchérir la pièce sans
	rien y changer) et `marche.matieres_fabrication` pour dresser l'univers des matières
	possibles. Elle vit ICI parce que c'est ce module qui définit ce qu'est un bloc bien
	formé — et `marche` ne peut pas importer `commande` (cycle)."""
	props = proprietes_matiere(item_doc)
	return bool(props["nom"] or props["modificateurs"])


# ── Un seul métal par pièce ──────────────────────────────────────────────────────
# Les lingots et l'acier plissé (« damasquiné ») ne se COMBINENT pas : une pièce sur mesure
# reçoit au plus un métal. Le métal se lit sur le tag `metal` de la DONNÉE (choix de
# l'Auteur : la Grenaille précieuse, catégorie `metal` sans le tag, reste combinable) —
# poser ou retirer le tag suffit, aucune matière n'est nommée ici.
TAG_METAL = "metal"
MATIERES_METAL_MAX = 1   # règle de jeu voulue : « un seul métal sur les trois matières »


def est_metal(item_doc) -> bool:
	"""Cette matière est-elle un métal au sens de la règle « un seul métal par pièce » ?"""
	return TAG_METAL in ((item_doc or {}).get("tags") or [])


def metaux_combines(matieres_docs: list) -> list:
	"""Les docs métal de `[(item_doc, quantite), …]` SI la pièce en compte plus que
	`MATIERES_METAL_MAX`, sinon `[]`. La quantité compte : deux lingots du même métal sont
	deux métaux — la règle ne dépend pas du plafond `COMMANDE_QUANTITE_MAX`."""
	metaux = [(doc, q) for doc, q in (matieres_docs or []) if est_metal(doc)]
	total = sum(max(0, int(q or 0)) for _doc, q in metaux)
	return [doc for doc, _q in metaux] if total > MATIERES_METAL_MAX else []


def _rang_rarete(rarete) -> float:
	"""Position d'une rareté dans l'échelle des prix. Sert à prendre « la plus haute » sans
	recopier l'ordre : `MULT_RARETE` EST l'échelle (cf. CLAUDE.md §14, aucune valeur en dur)."""
	return float(character_stats.MULT_RARETE.get(str(rarete or ""), 0) or 0)


# Une matière peut conférer UN palier de rareté de plus qu'elle n'en a (le travail l'anoblit :
# mithril rare → pièce très rare), jamais davantage. Au-delà, sa propre rareté ment
# (adamantite à 20 or « peu commune » qui rend une pièce légendaire).
RARETE_ECART_MAX = 1


def rarete_minimale_matiere(item_doc) -> str | None:
	"""Rareté minimale cohérente du doc matière, ou None s'il est déjà cohérent (ou sans
	rareté conférée). Échelle = ordre de `MULT_RARETE` par valeur (aucun ordre recopié)."""
	conferee = proprietes_matiere(item_doc)["modificateurs"].get("rarete")
	echelle = sorted(character_stats.MULT_RARETE, key=lambda r: character_stats.MULT_RARETE[r])
	if conferee not in echelle:
		return None
	propre = (item_doc or {}).get("rarete")
	if propre not in echelle:
		return None   # rareté absente : rien d'affirmé, rien à corriger (et le prix en dépend)
	cible = echelle[max(0, echelle.index(conferee) - RARETE_ECART_MAX)]
	return cible if echelle.index(propre) < echelle.index(cible) else None


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


def _copie(val) -> dict:
	"""Copie PROFONDE d'un bloc fusionnable. ⚠️ Une copie de surface partagerait les sous-dicts
	avec le doc de base — or celui-ci sort du cache de requête (`get_doc` mémorise les `item:`),
	et l'abîmer ici l'abîmerait pour tout le reste de la requête."""
	return {k: (_copie(v) if isinstance(v, dict) else v) for k, v in (val or {}).items()}


def _fusionner(cible: dict, apport: dict, qte: int) -> dict:
	"""Ajoute `apport` à `cible` clé à clé, en DESCENDANT dans les sous-dicts (`effets.buffs`).
	Mute et rend `cible`.

	⚠️ Quand les deux côtés ne sont pas de même nature (un sous-dict d'un côté, un nombre de
	l'autre), le base l'emporte et l'apport est ignoré : une matière mal rédigée n'apporte
	rien, elle ne casse rien — et surtout elle n'efface pas ce que la pièce portait déjà."""
	for cle, delta in (apport or {}).items():
		courant = cible.get(cle)
		if isinstance(delta, dict):
			if isinstance(courant, dict) or courant is None:
				cible[cle] = _fusionner(courant if isinstance(courant, dict) else {}, delta, qte)
		elif not isinstance(courant, dict):
			cible[cle] = _nombre(courant) + _nombre(delta) * qte
	return cible


def _nettoyer(val: dict) -> dict:
	"""Bloc fusionné prêt à écrire : nombres arrondis, zéros retirés (une matière qui annule un
	bonus ne doit pas laisser `{"Int": 0}`), sous-dicts NETTOYÉS À LEUR TOUR.

	⚠️ Ce qu'on ne sait pas additionner, on le CONSERVE. C'est ici que `effets.buffs` se
	perdait : `_nombre({"Int": 5})` vaut 0, le sous-dict passait donc pour un zéro et sautait
	avec — une bougie arcanique sur mesure perdait son +5 Int, et 53 items du dump portent ce
	bloc."""
	sortie = {}
	for cle, v in (val or {}).items():
		if isinstance(v, dict):
			sous = _nettoyer(v)
			if sous:
				sortie[cle] = sous
		elif isinstance(v, (int, float)) and not isinstance(v, bool):
			if int(round(v)) != 0:
				sortie[cle] = int(round(v))
		elif v not in (None, ""):
			sortie[cle] = v
	return sortie


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
	fusions = {k: _copie((base_doc or {}).get(k)) for k in CLES_FUSIONNEES
			   if isinstance((base_doc or {}).get(k), dict)}
	maxima = {k: _copie((base_doc or {}).get(k)) for k in CLES_MAX
			  if isinstance((base_doc or {}).get(k), dict)}
	facteurs = {k: 1.0 for k in CLES_FACTEUR}
	rarete = (base_doc or {}).get("rarete")
	# Vitesse NON CUMULATIVE (miroir de `characters._appliquer_vitesse_max`) : parmi le base et
	# les matières, seul le plus fort bonus de V compte, quantité comprise ; les malus de V
	# s'additionnent comme le reste de `bonus`.
	v_max = 0.0
	if "bonus" in fusions:
		v_max = max(0.0, _nombre(fusions["bonus"].get(CARACT_VITESSE)))
		if v_max:
			fusions["bonus"].pop(CARACT_VITESSE)

	for item_doc, quantite in matieres_docs:
		mods = proprietes_matiere(item_doc)["modificateurs"]
		qte = max(1, int(quantite or 1))
		for cle, val in mods.items():
			if cle in CLES_ADDITIVES:
				additifs[cle] = additifs.get(cle, 0.0) + _nombre(val) * qte
			elif cle == "bonus" and isinstance(val, dict) and _nombre(val.get(CARACT_VITESSE)) > 0:
				v_max = max(v_max, _nombre(val[CARACT_VITESSE]))
				reste = {c: d for c, d in val.items() if c != CARACT_VITESSE}
				_fusionner(fusions.setdefault(cle, {}), reste, qte)
			elif cle in CLES_FUSIONNEES and isinstance(val, dict):
				_fusionner(fusions.setdefault(cle, {}), val, qte)
			elif cle in CLES_MAX and isinstance(val, dict):
				cible = maxima.setdefault(cle, {})
				for sous_cle, seuil in val.items():
					cible[sous_cle] = max(_nombre(cible.get(sous_cle)), _nombre(seuil))
			elif cle in CLES_FACTEUR:
				facteurs[cle] = facteurs[cle] * _facteur(val)
			elif cle == "rarete" and _rang_rarete(val) > _rang_rarete(rarete):
				rarete = val

	if v_max:
		bonus = fusions.setdefault("bonus", {})
		bonus[CARACT_VITESSE] = _nombre(bonus.get(CARACT_VITESSE)) + v_max

	for cle, val in additifs.items():
		arrondi = int(round(val))
		if cle == "bonus_degats_dice":
			arrondi = max(0, min(DICE_MAX, arrondi))
		sortie[cle] = arrondi
	for cle, val in list(fusions.items()) + list(maxima.items()):
		nettoye = _nettoyer(val)
		if nettoye:
			sortie[cle] = nettoye
	borner_hors_famille(base_doc, sortie)
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


def description_variante(base_doc: dict, matieres_docs: list) -> str:
	"""La description INITIALE du base, suivie de la ligne de façonnage qui nomme les matières
	(« Façonné sur mesure : Lingot de mithril, Cuir ×2. »), dans l'ordre NORMALISÉ (par id),
	comme le nom. Sans description au base, la ligne de façonnage seule ; sans rien, ""."""
	noms, saisie = {}, []
	for doc, quantite in matieres_docs:
		item_id = (doc or {}).get("_id") or (doc or {}).get("item")
		if item_id:
			noms[item_id] = (doc or {}).get("nom") or _slug(item_id)
			saisie.append({"item": item_id, "quantite": quantite})
	morceaux = []
	for m in normaliser_matieres(saisie):
		nom = noms[m["item"]]
		morceaux.append("%s ×%d" % (nom, m["quantite"]) if m["quantite"] > 1 else nom)
	initiale = str((base_doc or {}).get("description") or "").strip()
	facon = ("Façonné sur mesure : %s." % ", ".join(morceaux)) if morceaux else ""
	return " ".join(p for p in (initiale, facon) if p)


# ── Construction des docs ────────────────────────────────────────────────────────

# Champs du doc de base repris tels quels par la variante. ⚠️ Liste blanche elle aussi : on
# ne recopie PAS `_rev` (la variante est un doc neuf), ni `fabrication` (le base pourrait être
# lui-même une variante — la traçabilité de CELLE-CI est réécrite plus bas), ni `valeur` (elle
# est recalculée et figée, cf. `valeur_variante`).
CHAMPS_HERITES = (
	"icon", "categorie", "sous_categorie", "slots", "tags", "deux_mains",
	"cible",
)


def facteur_valeur_borne(facteur) -> float:
	"""Produit des facteurs `valeur` des matières, borné à
	`[FACTEUR_MIN, COMMANDE_FACTEUR_VALEUR_MAX]`. Sans plafond, trois matières précieuses se
	composaient à ×8 (adamantite ×3,5 · relique ×1,8 · améthyste ×1,3)."""
	try:
		f = float(facteur)
	except (TypeError, ValueError):
		f = 1.0
	return max(FACTEUR_MIN, min(float(character_stats.COMMANDE_FACTEUR_VALEUR_MAX), f))


def facon_et_complexite(prix_base: int, matieres_distinctes: int = 0) -> tuple:
	"""`(façon, supplément de complexité)` d'une pièce dont l'objet de base vaut `prix_base`.
	SOURCE UNIQUE de `commande.devis` (ce que paie le client) et de `valeur_variante` (ce que
	vaut la pièce) : la façon (`COMMANDE_FACON_PART`) se paie toujours, la complexité
	(`COMMANDE_COMPLEXITE_PART`) à partir de la DEUXIÈME matière."""
	prix_base = max(0, int(prix_base or 0))
	facon = int(round(prix_base * float(character_stats.COMMANDE_FACON_PART)))
	sup = int(round(prix_base * float(character_stats.COMMANDE_COMPLEXITE_PART)
					* max(0, int(matieres_distinctes or 0) - 1)))
	return facon, sup


def valeur_variante(plancher_cuivre: int = 0, haut_base_cuivre: int = 0, haut_matieres_cuivre: int = 0,
					matieres_distinctes: int = 0, facteur_valeur: float = 1.0) -> list:
	"""`valeur` explicite de la variante, en cuivre : `[bas, haut]` — ce que COÛTE sa
	fabrication, du devis le plus favorable au moins favorable. Arguments :
	`commande.prix_variante` (source unique) + le facteur `valeur` des matières.

	    bas  = plancher de commande : devis(bas du base, Σ bas des matières)
	    haut = devis(haut du base × facteur borné, Σ haut des matières)
	    (devis = base + matières + façon + complexité, `facon_et_complexite`)

	Règle de l'Auteur (08/11) : **une pièce vaut AU MOINS la somme de ce qui l'a faite** —
	objet de base, matières, façon. Chaque borne de la variante dépasse donc la borne
	homologue de son objet de base : à relation et rareté égales, une dague sur mesure est
	toujours plus chère qu'une dague. Avant, le haut était plafonné au plancher de commande
	et tombait sous le haut du base (fourchette ×`PRIX_MAX_FACTEUR`) : la dague façonnée de
	l'Arsenal se vendait 1 333 cu, la dague simple 1 869.

	- **jamais le devis d'UN client** : relation, stock du jour et matières apportées
	  (comptées 0) faisaient varier la valeur ×2,4 entre trois anneaux ;
	- **le facteur ne touche que le base, et que la borne haute** : la matière est déjà à son
	  prix, le bas reste le moins qu'on puisse payer la pièce ;
	- **anti-arbitrage par le BAS** : une variante ne se rachète jamais qu'en bande de rachat
	  (≤ son bas, `marche.params_vente_lieu`) ou chez un négociant (≤ son bas) — le bas étant
	  le plancher de commande, commander puis revendre ne rapporte rien.

	⚠️ Une `valeur` explicite est AUTORITATIVE pour `marche.cout_production_cuivre`, qui cesse
	alors de propager : sans elle, le coût se recalculerait `(base + matières) × MARGE_TRANSFO`,
	et le base étant DÉJÀ le produit d'une étape à ×5, la pièce vaudrait ×25 ses intrants."""
	bas = max(1, int(plancher_cuivre or 0))
	base = int(round(max(0, int(haut_base_cuivre or 0)) * facteur_valeur_borne(facteur_valeur)))
	facon, sup = facon_et_complexite(base, matieres_distinctes)
	haut = max(bas, base + max(0, int(haut_matieres_cuivre or 0)) + facon + sup)
	return [{"cu": bas}, {"cu": haut}]


def variante_doc(base_doc: dict, matieres_docs: list, lieu_id: str = "",
				 now: int = 0, **prix) -> dict:
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
	description = description_variante(base_doc, matieres_docs)
	if description:
		doc["description"] = description
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

	# `prix` = `commande.prix_variante` (plancher, hauts, matières distinctes).
	doc["valeur"] = valeur_variante(facteur_valeur=facteurs.get("valeur", 1.0), **prix)

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
					 get_doc_fn, save_doc_fn, now: int = 0, **prix) -> tuple:
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

	doc = variante_doc(base_doc, matieres_docs, (lieu_doc or {}).get("_id", ""), now, **prix)
	recette = recette_variante_doc(base_doc, matieres_docs, (lieu_doc or {}).get("categorie", ""))
	# L'item d'abord : une recette qui produirait un item absent serait un trou ; l'inverse est
	# seulement une variante sans historique, récupérable au prochain passage.
	save_doc_fn(doc)
	if get_doc_fn(recette["_id"]) is None:
		save_doc_fn(recette)
	return doc, True
