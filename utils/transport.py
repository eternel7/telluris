# utils/transport.py
# Quêtes de transport de marchandise : un donneur X confie une cargaison à livrer à un
# magasin Y qui rachète ces biens, dans un délai RÉEL (QUETE_TRANSPORT_DUREE_SECONDES).
# Réussite → +1 relation avec X (+ XP + prime) ; échec (délai dépassé) ou abandon → −1
# relation avec X, la cargaison RESTE dans le sac (le joueur peut la revendre).
#
# DEUX SOURCES d'offre, aiguillées par `poser_transport_offert` :
# - GÉNÉRÉE — le donneur est un magasin (`est_magasin`) : destination, cargaison, délai et
#   XP sont TIRÉS AU HASARD (`generer_transport`), avec la probabilité QUETE_TRANSPORT_PROBA —
#   et seulement s'il a assez confiance (`confiance_suffisante` : relation ≥ QUETE_TRANSPORT_RELATION_MIN
#   ET marchandage non bloqué). Le refus est PARLÉ (`mefiance` → nœud de dialogue), jamais muet.
# - AUTHORÉE — le PNJ présent porte une course ÉCRITE dans `services.transport.offre`
#   (`generer_transport_authore`) : destination, cargaison et récompenses fixes, id stable.
#   N'IMPORTE QUEL PNJ peut ainsi donner une course — le donneur n'a pas à être un magasin
#   (ex. le réceptionniste de la guilde et sa mission d'initiation). Le DESTINATAIRE, lui,
#   reste un lieu marchand : c'est lui qui prend livraison (son tenancier a les nœuds `livre`).
#   Une course écrite peut demander un `retour` : le destinataire prend la marchandise mais ne
#   paie pas — la quête reste active (délai levé) jusqu'à ce que le joueur revienne RENDRE COMPTE
#   au donneur, qui solde alors tout (XP, prime, items — la carte d'aventurier de la guilde).
#   Ses `recompenses.items` sont des références d'INSTANCES : une entrée `lieu_parent: "auto"`
#   est résolue contre la cité du donneur (`items_recompense`) — la carte est un objet générique,
#   c'est l'exemplaire qui dit de quelle guilde on est membre.
#
# L'offre est tirée à l'ENTRÉE du lieu et persistée en champ transitoire
# `character["transport_offert"]` — même sémantique que `pnj_present` : un refresh ne
# re-tire pas, ressortir/rentrer re-tire.
#
# Toute l'interaction passe par le dialogue PNJ (utils/pnj.py) : les magasins n'ayant pas
# de champ `pnj`, `entree_marchand` fournit un tenancier GÉNÉRIQUE par catégorie
# (`pnj:marchand_<categorie>`), injecté dans la résolution de présence.
#
# Géographie : il n'y a aucune coordonnée monde sur les docs `lieu:*`, mais chaque doc
# `connection` boutique↔ville porte la position de la porte DANS la grille de la ville.
# `focalisation.charger_graphe` l'expose déjà → direction cardinale et « près du magasin
# Z » se calculent en comparant les portes dans la grille du parent commun.
#
# Logique pure (DB injectée : get_doc_fn / find_docs_fn / rand_fn / now), mute sans save —
# l'endpoint persiste. Pattern de utils/focalisation.py et utils/pnj.py.

import random
import uuid

from models import character_stats
from utils.characters import item_ref_id, poids_bounds
from utils import focalisation, marche, quetes


# Sentinelle de `recompenses.items[].lieu_parent` dans une offre écrite : « le lieu parent du
# donneur » (cf. `items_recompense`) — la cité dont relève la guilde qui délivre l'objet.
LIEU_PARENT_AUTO = "auto"


# ---------------------------------------------------------------------------
# Magasins & tenancier générique
# ---------------------------------------------------------------------------

def est_magasin(lieu_doc: dict) -> bool:
	"""Le lieu est-il marchand ? Un lieu l'est de fait dès que sa catégorie a des recettes,
	donc des matières à racheter au joueur — c'est déjà le prédicat du bouton 🏷️ Achat-Vente."""
	return bool(marche.besoins_categorie((lieu_doc or {}).get("categorie")))


def entree_marchand(lieu_doc: dict) -> dict | None:
	"""Entrée `pnj` implicite d'un lieu marchand : son tenancier générique de catégorie.
	Aucun doc `lieu:*` ne porte de `pnj` marchand — on le dérive de la catégorie. Présence
	certaine (une boutique a toujours quelqu'un derrière le comptoir : sans lui, aucune
	livraison ne serait possible). None si le lieu n'est pas un magasin."""
	if not est_magasin(lieu_doc):
		return None
	return {
		"character": "pnj:marchand_" + str((lieu_doc or {}).get("categorie")),
		"probabilite": 1.0,
	}


# ---------------------------------------------------------------------------
# Géographie : portes, direction cardinale, repère
# ---------------------------------------------------------------------------

# Octants, dans l'ordre des angles croissants à partir de l'est (y croît vers le BAS
# dans la grille → le nord est en dy négatif).
_OCTANTS = [
	(1, 0, "est"), (1, 1, "sud-est"), (0, 1, "sud"), (-1, 1, "sud-ouest"),
	(-1, 0, "ouest"), (-1, -1, "nord-ouest"), (0, -1, "nord"), (1, -1, "nord-est"),
]


def portes_du_parent(graphe: dict, parent_id: str) -> dict:
	"""{lieu_id: (x, y)} — la porte de chaque lieu enfant DANS la grille du parent.
	Extrait tel quel de `focalisation.charger_graphe` (les arêtes du parent portent la
	position côté parent)."""
	return {a["voisin"]: a["porte"] for a in (graphe or {}).get(parent_id, [])}


def porte_effective(graphe: dict, portes: dict, lieu_id: str) -> tuple | None:
	"""Porte par laquelle ce lieu débouche sur la grille du parent. Un lieu IMBRIQUÉ n'a pas
	de porte à lui (le comptoir de la guilde ouvre sur la réception, qui ouvre sur la façade,
	qui seule ouvre sur la ville) : on remonte alors le graphe jusqu'au premier lieu qui, lui,
	en a une — c'est bien par là que le joueur sortira. None si aucun ancêtre n'en a."""
	if lieu_id in (portes or {}):
		return portes[lieu_id]
	vus = {lieu_id}
	file = [lieu_id]
	while file:
		courant = file.pop(0)
		for arete in (graphe or {}).get(courant, []):
			voisin = arete.get("voisin")
			if not voisin or voisin in vus:
				continue
			if voisin in (portes or {}):
				return portes[voisin]
			vus.add(voisin)
			file.append(voisin)
	return None


def direction_cardinale(depuis: tuple, vers: tuple) -> str | None:
	"""Direction cardinale (8 octants) de `depuis` vers `vers`, en coordonnées de grille
	(y croît vers le BAS → nord = dy < 0). None si les deux portes coïncident."""
	dx = int(vers[0]) - int(depuis[0])
	dy = int(vers[1]) - int(depuis[1])
	if dx == 0 and dy == 0:
		return None
	# Octant de plus grande projection : évite la trigonométrie et reste exact sur les axes.
	meilleur, meilleur_score = None, None
	norme = (dx * dx + dy * dy) ** 0.5
	for ox, oy, nom in _OCTANTS:
		on = (ox * ox + oy * oy) ** 0.5
		score = (dx * ox + dy * oy) / (norme * on)
		if meilleur_score is None or score > meilleur_score:
			meilleur, meilleur_score = nom, score
	return meilleur


def repere_proche(cible_id: str, portes: dict, get_doc_fn, exclure: set | None = None) -> str | None:
	"""Label du lieu dont la porte est la plus proche de celle de `cible_id` dans la grille
	du parent (« tout près de … »). `exclure` = lieux à ignorer (la cible, le donneur).
	None si la cible n'a pas de porte connue ou qu'il n'y a aucun voisin."""
	cible_porte = (portes or {}).get(cible_id)
	if not cible_porte:
		return None
	exclure = set(exclure or ()) | {cible_id}
	meilleur, meilleure_d = None, None
	for lieu_id, porte in portes.items():
		if lieu_id in exclure:
			continue
		doc = get_doc_fn(lieu_id) or {}
		if not est_magasin(doc):
			continue
		d = (porte[0] - cible_porte[0]) ** 2 + (porte[1] - cible_porte[1]) ** 2
		if meilleure_d is None or d < meilleure_d:
			meilleur, meilleure_d = (doc.get("label") or doc.get("nom") or lieu_id), d
	return meilleur


def indice_destination(giver_doc: dict, dest_id: str, find_docs_fn, get_doc_fn) -> dict:
	"""Indices donnés par le marchand quand on l'interroge sur la destination :
	{nom, direction, repere, meme_ville, ville_nom, distance}. `direction`/`repere` ne
	sont renseignés que si les deux magasins partagent la même ville (donc la même grille,
	seule échelle où une direction cardinale a un sens) ; sinon on nomme la ville et on
	donne la distance en nombre d'étapes."""
	dest_doc = get_doc_fn(dest_id) or {}
	nom = dest_doc.get("label") or dest_doc.get("nom") or dest_id
	parent_x = (giver_doc or {}).get("lieu_parent")
	parent_y = dest_doc.get("lieu_parent")
	graphe = focalisation.charger_graphe(find_docs_fn)
	etape = focalisation.prochaine_etape(graphe, (giver_doc or {}).get("_id"), dest_id)
	distance = (etape or {}).get("distance", 0)

	meme_ville = bool(parent_x) and parent_x == parent_y
	direction = repere = None
	ville_nom = None
	if meme_ville:
		portes = portes_du_parent(graphe, parent_x)
		# `porte_effective` et non `portes.get` : un donneur imbriqué (comptoir → réception →
		# façade) n'ouvre pas lui-même sur la ville, mais la direction se mesure depuis la
		# porte par laquelle on en sort.
		porte_x = porte_effective(graphe, portes, (giver_doc or {}).get("_id"))
		porte_y = porte_effective(graphe, portes, dest_id)
		if porte_x and porte_y:
			direction = direction_cardinale(porte_x, porte_y)
		repere = repere_proche(dest_id, portes, get_doc_fn, exclure={(giver_doc or {}).get("_id")})
	else:
		ville_doc = get_doc_fn(parent_y) if parent_y else None
		ville_nom = (ville_doc or {}).get("label") or (ville_doc or {}).get("nom")

	return {
		"nom": nom,
		"direction": direction,
		"repere": repere,
		"meme_ville": meme_ville,
		"ville_nom": ville_nom,
		"distance": distance,
	}


def texte_indice(indice: dict) -> str:
	"""Phrase d'orientation prête à insérer dans un dialogue ({direction} du gabarit)."""
	if indice.get("meme_ville"):
		bout = f"au {indice['direction']} d'ici" if indice.get("direction") else "à deux pas d'ici"
		if indice.get("repere"):
			bout += f", tout près de {indice['repere']}"
		return bout
	if indice.get("ville_nom"):
		return f"à {indice['ville_nom']}, à {indice.get('distance', 0)} étapes de route"
	return "loin d'ici"


# ---------------------------------------------------------------------------
# Génération de l'offre
# ---------------------------------------------------------------------------

def magasins_candidats(giver_doc: dict, find_docs_fn) -> list:
	"""Magasins livrables depuis X : d'abord ceux de sa ville (le cas nominal — tout le
	réseau de boutiques vit dans une ville), puis, à défaut, tous les magasins du monde."""
	giver_id = (giver_doc or {}).get("_id")
	parent = (giver_doc or {}).get("lieu_parent")
	pools = []
	if parent:
		pools.append(find_docs_fn({"type": "lieu", "lieu_parent": parent}) or [])
	pools.append(find_docs_fn({"type": "lieu"}) or [])
	for pool in pools:
		candidats = [d for d in pool if d.get("_id") != giver_id and est_magasin(d)]
		if candidats:
			return candidats
	return []


def items_fournis(giver_doc: dict) -> list:
	"""Item_ids que le magasin X peut sortir de ses réserves : ce qu'il a en rayon
	(`stock_vente`) plus ce que ses recettes produisent."""
	out = []
	for ligne in (giver_doc or {}).get("stock_vente") or []:
		iid = ligne.get("item_id")
		if iid and iid not in out:
			out.append(iid)
	for iid in sorted(marche.produits_categorie((giver_doc or {}).get("categorie"))):
		if iid not in out:
			out.append(iid)
	return out


def items_livrables(giver_doc: dict, dest_doc: dict, get_doc_fn) -> list:
	"""Docs des items que X peut fournir ET que Y rachète — la contrainte « pouvant être
	vendu à un magasin Y »."""
	out = []
	for iid in items_fournis(giver_doc):
		doc = get_doc_fn(iid)
		if doc and marche.lieu_buys(dest_doc, doc):
			out.append(doc)
	return out


def choisir_cargaison(items: list, rand_fn=random.random) -> list:
	"""Empile des instances tirées au hasard parmi `items` (docs) tant que ni le poids
	cumulé (QUETE_TRANSPORT_POIDS_MAX) ni le nombre d'objets (QUETE_TRANSPORT_NB_MAX) ne
	seraient franchis : on s'arrête AVANT l'instance qui dépasserait l'une des deux bornes
	et on garde l'état précédent. Renvoie des références `{item, poids}` (liste vide si
	même un objet seul est trop lourd → pas d'offre)."""
	if not items:
		return []
	poids_max = float(character_stats.QUETE_TRANSPORT_POIDS_MAX)
	nb_max = int(character_stats.QUETE_TRANSPORT_NB_MAX)
	cargaison: list = []
	total = 0.0
	while len(cargaison) < nb_max:
		doc = items[min(int(rand_fn() * len(items)), len(items) - 1)]
		pmin, pmax = poids_bounds(doc)
		poids = round(pmin + (pmax - pmin) * rand_fn(), 2)
		if total + poids > poids_max:
			break
		cargaison.append({"item": doc.get("_id") or doc.get("item"), "poids": poids})
		total += poids
	return cargaison


def _xp_transport(indice: dict) -> int:
	"""XP de la course : la base pour une livraison dans la même ville, multipliée par la
	distance quand il faut prendre la route."""
	base = int(character_stats.QUETE_TRANSPORT_XP)
	if indice.get("meme_ville"):
		return base
	return max(base, base * (1 + int(indice.get("distance", 0) or 0)))


def poids_cargaison(cargaison: list) -> float:
	return round(sum(float(r.get("poids", 0) or 0) for r in cargaison or []), 2)


def confiance_suffisante(character: dict, lieu_doc: dict, get_doc_fn,
						 now: int | None = None) -> bool:
	"""Le tenancier a-t-il assez confiance pour remettre sa marchandise ? DEUX refus, une seule
	porte fermée :
	- **relation < QUETE_TRANSPORT_RELATION_MIN** (50 = la relation neutre ; 0 = garde-fou
	  désactivé) — on ne confie pas un colis à quelqu'un qu'on voit d'un mauvais œil ;
	- **marchandage bloqué** (`marche.marchandage_bloque` : crit d'échec récent) — celui qui vient
	  de se fâcher avec le joueur ne lui confierait pas davantage sa marchandise qu'un prix. Ce
	  blocage est une brouille datée, indépendante de la cote : il vaut même à relation ≥ seuil, et
	  même si le garde-fou de relation est désactivé (sa durée a sa propre world-var,
	  MARCHANDAGE_BLOCAGE_SECONDES).

	Ne vaut que pour les courses GÉNÉRÉES : une course ÉCRITE est confiée par son scénario."""
	relation = marche.get_relation(character, lieu_doc, get_doc_fn)
	now = int(quetes.now_epoch() if now is None else now)
	if marche.marchandage_bloque(relation, now):
		return False
	seuil = int(character_stats.QUETE_TRANSPORT_RELATION_MIN)
	if seuil <= 0:
		return True
	return marche.relation_value(relation) >= seuil


def mefiance(character: dict, lieu_doc: dict, pnj_doc: dict | None, get_doc_fn,
			 now: int | None = None) -> bool:
	"""Le tenancier refuse-t-il de confier une course, faute de confiance ? C'est le pendant
	PARLANT de `confiance_suffisante` : sans lui, le refus serait muet (le choix « une course
	pour moi ? » disparaîtrait, indiscernable d'un simple tirage négatif) et la sanction de
	réputation — comme la brouille d'un marchandage raté — n'existerait pas en jeu.

	Vrai pour un MAGASIN seul (les courses générées) : une course ÉCRITE est confiée par son
	scénario, pas par la cote du joueur. Faux tant qu'une course est en cours — le refus ne
	parle que de confiance, jamais de « pas de course aujourd'hui »."""
	if not est_magasin(lieu_doc) or offre_spec(pnj_doc):
		return False
	if offre_courante(character, lieu_doc) or transports_actifs(character):
		return False
	return not confiance_suffisante(character, lieu_doc, get_doc_fn, now)


def generer_transport(giver_doc: dict, find_docs_fn, get_doc_fn,
					  rand_fn=random.random) -> dict | None:
	"""Construit une offre de transport depuis le magasin X (non persistée, pas encore
	acceptée). None si aucun magasin destinataire ne rachète ce que X peut fournir, ou si
	la cargaison tirée est vide (objet unique trop lourd)."""
	candidats = magasins_candidats(giver_doc, find_docs_fn)
	rand_fn_ = rand_fn
	# On essaie les destinations dans un ordre aléatoire jusqu'à en trouver une qui rachète.
	ordre = sorted(candidats, key=lambda _d: rand_fn_())
	for dest_doc in ordre:
		items = items_livrables(giver_doc, dest_doc, get_doc_fn)
		if not items:
			continue
		cargaison = choisir_cargaison(items, rand_fn)
		if not cargaison:
			continue
		dest_id = dest_doc.get("_id")
		indice = indice_destination(giver_doc, dest_id, find_docs_fn, get_doc_fn)
		xp = _xp_transport(indice)
		cuivre = max(0, round(xp * float(character_stats.QUETE_CUIVRE_PAR_XP)))
		nb = len(cargaison)
		giver_nom = (giver_doc or {}).get("label") or (giver_doc or {}).get("nom") or "Le marchand"
		return {
			"id": "quete:transport_" + uuid.uuid4().hex[:12],
			"type_quete": "transport",
			"titre": f"Livraison : {indice['nom']}",
			# Les enseignes portent déjà leur article (« Le Saloir ») : on les introduit par un
			# deux-points plutôt que par une préposition, qui donnerait « à porter à Le Saloir ».
			"description": (
				f"{giver_nom} vous confie {nb} colis "
				f"({poids_cargaison(cargaison)} kg). Destination : {indice['nom']}, "
				f"{texte_indice(indice)}."
			),
			"rang": "F",
			"giver": (giver_doc or {}).get("_id"),
			"objectif": {"type": "transport", "cible": dest_id, "quantite": 1},
			"cargaison": cargaison,
			"duree": int(character_stats.QUETE_TRANSPORT_DUREE_SECONDES),
			"recompenses": {"xp": xp, "cuivre": cuivre, "items": []},
			"progress": 0,
		}
	return None


# ---------------------------------------------------------------------------
# Offre AUTHORÉE portée par un PNJ (services.transport.offre)
# ---------------------------------------------------------------------------

def offre_spec(pnj_doc: dict) -> dict | None:
	"""La course ÉCRITE que ce PNJ confie, ou None (cas des marchands : leur course est
	tirée au hasard). Miroir de `services.soin` / `services.don` (utils/pnj.py) :
	`services.transport.offre` = {id, destination, cargaison:[{item, quantite, poids?}],
	duree?, proba?, unique?, titre?, description?, recompenses?{xp, cuivre}}."""
	service = (((pnj_doc or {}).get("services") or {}).get("transport") or {})
	spec = service.get("offre")
	if not spec or not spec.get("destination") or not spec.get("cargaison"):
		return None
	return spec


def deja_reussie(character: dict, quete_id: str) -> bool:
	"""Cette quête a-t-elle déjà été MENÉE À BIEN par le personnage ? (Un échec ne compte
	pas : le donneur repropose sa course — on ne condamne pas un joueur pour un retard.)
	Gate des offres `unique`, d'où la nécessité d'un id STABLE sur la spec."""
	if not quete_id:
		return False
	return any(
		t.get("id") == quete_id and not t.get("echec")
		for t in (character or {}).get("quetes_terminees", [])
	)


def cargaison_authoree(spec: dict, get_doc_fn) -> list:
	"""Développe la cargaison écrite en références d'instances `{item, poids}` (une par
	exemplaire). Poids = celui de la spec s'il est donné, sinon le poids mini de l'item.
	Les bornes QUETE_TRANSPORT_POIDS_MAX / _NB_MAX ne s'appliquent PAS : une cargaison
	authorée dit exactement ce qu'elle pèse (le contrôle de charge à l'acceptation, lui,
	joue toujours → nœud « trop chargé »)."""
	cargaison = []
	for ligne in (spec or {}).get("cargaison") or []:
		iid = ligne.get("item")
		if not iid:
			continue
		doc = get_doc_fn(iid)
		if not doc:
			continue
		poids = ligne.get("poids")
		poids = float(poids) if poids is not None else poids_bounds(doc)[0]
		for _ in range(max(1, int(ligne.get("quantite", 1) or 1))):
			cargaison.append({"item": iid, "poids": poids})
	return cargaison


def items_recompense(spec_items: list, giver_doc: dict) -> list:
	"""Références d'INSTANCES des items de récompense. Une entrée peut demander
	`lieu_parent: "auto"` → l'exemplaire remis portera le lieu PARENT du donneur (la cité dont
	relève sa guilde) : une carte d'aventurier est un objet GÉNÉRIQUE, c'est l'instance qui dit
	de quelle guilde on est membre. La même mission copiée dans une autre guilde délivrera donc
	la carte de SA cité. Un id littéral est recopié tel quel ; sans clé, rien n'est ajouté."""
	parent = (giver_doc or {}).get("lieu_parent") or (giver_doc or {}).get("_id")
	sortie = []
	for ligne in spec_items or []:
		ref = dict(ligne)
		if ref.get("lieu_parent") == LIEU_PARENT_AUTO:
			if parent:
				ref["lieu_parent"] = parent
			else:
				ref.pop("lieu_parent")
		sortie.append(ref)
	return sortie


def rang_guilde_recompense(spec_rang, giver_doc: dict) -> dict:
	"""Récompense de RANG DE GUILDE d'une offre écrite, résolue en `{"cite", "rang"}`.

	Miroir exact d'`items_recompense` et pour la même raison : la spec écrit un simple
	`"rang_guilde": "F"` et la CITÉ est dérivée du `lieu_parent` du donneur — la même mission
	copiée dans la guilde d'une autre cité inscrit donc à SA cité. Un `{"cite", "rang"}`
	explicite est recopié tel quel (inscrire ailleurs que chez soi reste possible).
	Renvoie `{}` — donc rien à fusionner — si la spec est vide ou si aucune cité ne se résout."""
	if not spec_rang:
		return {}
	if isinstance(spec_rang, dict):
		return {"rang_guilde": dict(spec_rang)} if spec_rang.get("cite") else {}
	parent = (giver_doc or {}).get("lieu_parent") or (giver_doc or {}).get("_id")
	if not parent:
		return {}
	return {"rang_guilde": {"cite": parent, "rang": spec_rang}}


def generer_transport_authore(spec: dict, giver_doc: dict, find_docs_fn, get_doc_fn) -> dict | None:
	"""Construit l'offre décrite par la spec du PNJ — même structure que `generer_transport`,
	mais rien n'est tiré au sort : destination, cargaison, délai et récompenses sont écrits.
	Titre/description/récompenses absents de la spec sont dérivés comme pour une course
	générée. None si la cargaison ne se résout pas (items introuvables)."""
	cargaison = cargaison_authoree(spec, get_doc_fn)
	if not cargaison:
		return None
	dest_id = spec.get("destination")
	indice = indice_destination(giver_doc, dest_id, find_docs_fn, get_doc_fn)
	rec = dict(spec.get("recompenses") or {})
	xp = int(rec.get("xp", _xp_transport(indice)))
	cuivre = int(rec.get("cuivre", max(0, round(xp * float(character_stats.QUETE_CUIVRE_PAR_XP)))))
	nb = len(cargaison)
	giver_nom = (giver_doc or {}).get("label") or (giver_doc or {}).get("nom") or "Le donneur"
	return {
		"id": spec.get("id") or ("quete:transport_" + uuid.uuid4().hex[:12]),
		"type_quete": "transport",
		"titre": spec.get("titre") or f"Livraison : {indice['nom']}",
		"description": spec.get("description") or (
			f"{giver_nom} vous confie {nb} colis "
			f"({poids_cargaison(cargaison)} kg). Destination : {indice['nom']}, "
			f"{texte_indice(indice)}."
		),
		"rang": spec.get("rang", "F"),
		"giver": (giver_doc or {}).get("_id"),
		"objectif": {"type": "transport", "cible": dest_id, "quantite": 1},
		"cargaison": cargaison,
		"duree": int(spec.get("duree", character_stats.QUETE_TRANSPORT_DUREE_SECONDES)),
		"recompenses": {
			"xp": xp, "cuivre": cuivre,
			"items": items_recompense(rec.get("items"), giver_doc),
			**rang_guilde_recompense(rec.get("rang_guilde"), giver_doc),
		},
		# `retour` : la course ne se solde PAS chez le destinataire — il faut revenir en rendre
		# compte au donneur, qui paie (et remet ses items de récompense : la carte d'aventurier).
		"retour": bool(spec.get("retour")),
		"progress": 0,
	}


# ---------------------------------------------------------------------------
# Offre du lieu (champ transitoire, miroir de pnj_present)
# ---------------------------------------------------------------------------

def transports_actifs(character: dict) -> list:
	return [
		q for q in (character or {}).get("quetes_actives", [])
		if (q.get("objectif") or {}).get("type") == "transport"
	]


def poser_transport_offert(character: dict, lieu_doc: dict, find_docs_fn, get_doc_fn,
						   rand_fn=random.random, pnj_doc: dict | None = None) -> bool:
	"""Tire (une seule fois par entrée) l'offre de transport du lieu courant et la pose dans
	le champ transitoire `transport_offert` (mute sans save). No-op si le tirage a déjà été
	fait pour ce lieu → un refresh ne re-tire pas ; ressortir/rentrer re-tire. Aucune offre
	si le personnage a déjà une course en cours (pas d'empilement de cargaisons). Renvoie
	True si le champ a changé (l'appelant décide de sauvegarder).

	Deux donneurs possibles : le PNJ présent porte une course ÉCRITE (`services.transport.offre`
	— elle prime, et le lieu n'a pas à être un magasin), sinon le lieu est un magasin et sa
	course est TIRÉE AU HASARD. `pnj_doc` = le PNJ déjà arrêté pour cette entrée (le tirage de
	présence, `pnj.poser_pnj_present`, a lieu juste avant côté appelant)."""
	lieu_id = (lieu_doc or {}).get("_id")
	spec = offre_spec(pnj_doc)
	if not lieu_id or not (spec or est_magasin(lieu_doc)):
		# Lieu sans donneur : on nettoie l'offre restée sur l'ancien lieu.
		if (character.get("transport_offert") or {}).get("lieu"):
			character["transport_offert"] = None
			return True
		return False
	offert = character.get("transport_offert") or {}
	if offert.get("lieu") == lieu_id:
		return False
	quete = None
	if not transports_actifs(character):
		if spec:
			deja = bool(spec.get("unique")) and deja_reussie(character, spec.get("id"))
			if not deja and rand_fn() < float(spec.get("proba", 1.0)):
				quete = generer_transport_authore(spec, lieu_doc, find_docs_fn, get_doc_fn)
		elif (confiance_suffisante(character, lieu_doc, get_doc_fn)
				and rand_fn() < float(character_stats.QUETE_TRANSPORT_PROBA)):
			quete = generer_transport(lieu_doc, find_docs_fn, get_doc_fn, rand_fn)
	character["transport_offert"] = {"lieu": lieu_id, "quete": quete}
	return True


def offre_courante(character: dict, lieu_doc: dict) -> dict | None:
	"""L'offre tirée pour le lieu courant, ou None (tirage périmé / pas d'offre)."""
	offert = (character or {}).get("transport_offert") or {}
	lieu_id = (lieu_doc or {}).get("_id")
	if not lieu_id or offert.get("lieu") != lieu_id:
		return None
	return offert.get("quete") or None


def course_du_donneur(character: dict, lieu_id: str) -> dict | None:
	"""La course active CONFIÉE par ce lieu, ou None — de quoi laisser le donneur relancer le
	joueur tant qu'il n'a pas livré (« la viande n'attend pas »)."""
	for q in transports_actifs(character):
		if q.get("giver") == lieu_id:
			return q
	return None


def transport_a_livrer(character: dict, lieu_id: str) -> dict | None:
	"""La course active dont la destination est ce lieu et dont la cargaison n'a pas ENCORE été
	remise (donc livrable ici), ou None. Une course `retour` reste active après la livraison —
	le temps d'aller en rendre compte au donneur — mais elle n'est plus à livrer."""
	for q in transports_actifs(character):
		if (q.get("objectif") or {}).get("cible") == lieu_id and not q.get("livree_at"):
			return q
	return None


def retour_attendu(character: dict, lieu_id: str) -> dict | None:
	"""La course livrée dont il reste à rendre compte AU DONNEUR, si ce lieu est le sien."""
	for q in transports_actifs(character):
		if q.get("livree_at") and q.get("giver") == lieu_id:
			return q
	return None


# ---------------------------------------------------------------------------
# Acceptation / livraison / expiration
# ---------------------------------------------------------------------------

def accepter_transport(character: dict, offre: dict, now: int | None = None) -> dict:
	"""Remet la cargaison au joueur et pose la quête dans `quetes_actives` (mute sans save).
	Le contrôle de charge est fait par l'appelant AVANT (nœud « trop chargé »). Vide l'offre
	du lieu pour qu'elle ne soit pas reprise. Renvoie le snapshot posé."""
	now = int(quetes.now_epoch() if now is None else now)
	snapshot = {
		"id": offre.get("id"),
		"titre": offre.get("titre", "—"),
		"description": offre.get("description", ""),
		"rang": offre.get("rang", "F"),
		"giver": offre.get("giver"),
		"objectif": dict(offre.get("objectif", {})),
		"recompenses": dict(offre.get("recompenses", {})),
		"cargaison": [dict(r) for r in offre.get("cargaison", [])],
		"retour": bool(offre.get("retour")),
		"progress": 0,
		"accepte_at": now,
		"expire_at": now + int(offre.get("duree", character_stats.QUETE_TRANSPORT_DUREE_SECONDES)),
	}
	inv = character.setdefault("inventaire", [])
	for ref in snapshot["cargaison"]:
		inv.append(dict(ref))
	character.setdefault("quetes_actives", []).append(snapshot)
	character["transport_offert"] = None
	return snapshot


def cargaison_manquante(character: dict, q: dict) -> dict:
	"""{item_id: nb manquant} — ce que le joueur ne porte plus de la cargaison confiée
	(vendu, jeté, perdu). Vide = livraison possible."""
	requis: dict = {}
	for ref in q.get("cargaison") or []:
		iid = item_ref_id(ref)
		if iid:
			requis[iid] = requis.get(iid, 0) + 1
	porte: dict = {}
	for ref in character.get("inventaire", []):
		iid = item_ref_id(ref)
		if iid in requis:
			porte[iid] = porte.get(iid, 0) + 1
	return {
		iid: n - porte.get(iid, 0)
		for iid, n in requis.items() if n > porte.get(iid, 0)
	}


def livrer_transport(character: dict, q: dict) -> bool:
	"""Retire la cargaison du sac et marque l'objectif atteint (mute sans save). False si
	le joueur ne porte plus tout (l'appelant route vers le nœud « incomplet »)."""
	if cargaison_manquante(character, q):
		return False
	requis: dict = {}
	for ref in q.get("cargaison") or []:
		iid = item_ref_id(ref)
		if iid:
			requis[iid] = requis.get(iid, 0) + 1
	for iid, n in requis.items():
		quetes.retirer_items(character, iid, n)
	q["progress"] = int((q.get("objectif") or {}).get("quantite", 1) or 1)
	return True


def deposer_en_rayon(dest_doc: dict, cargaison: list, get_doc_fn,
					 rand_fn=random.random) -> dict:
	"""Range la cargaison livrée dans le magasin destinataire : chaque objet a
	`QUETE_TRANSPORT_STOCK_PROBA` de finir en **rayon** (`stock_vente`), à condition que le
	magasin **vende** ce produit (`lieu_produit` — ses recettes le produisent, donc il l'étale).
	Le reste disparaît en arrière-boutique (atelier, consommation) : la livraison garnit
	l'étal sans le remplir d'un coup.

	Mute `dest_doc` en place, NE SAUVEGARDE PAS (l'appelant persiste le doc lieu).
	Renvoie {item_id: nb mis en rayon} — vide si rien n'a été rangé.
	"""
	proba = float(character_stats.QUETE_TRANSPORT_STOCK_PROBA)
	ajouts: dict = {}
	vendable: dict = {}  # cache par item_id : ce magasin l'étale-t-il ?
	for ref in cargaison or []:
		iid = item_ref_id(ref)
		if not iid:
			continue
		if iid not in vendable:
			doc = get_doc_fn(iid)
			vendable[iid] = bool(doc) and marche.lieu_produit(dest_doc, doc)
		if not vendable[iid]:
			continue
		if rand_fn() >= proba:
			continue
		ajouts[iid] = ajouts.get(iid, 0) + 1

	if not ajouts:
		return {}
	rayon = dest_doc.setdefault("stock_vente", [])
	for iid, n in ajouts.items():
		ligne = next((l for l in rayon if l.get("item_id") == iid), None)
		if ligne:
			ligne["qty"] = int(ligne.get("qty", 0) or 0) + n
		else:
			rayon.append({"item_id": iid, "qty": n})
	return ajouts


def archiver(character: dict, q: dict, echec: bool, now: int) -> None:
	"""Sort la quête des actives et l'archive dans `quetes_terminees` (mute sans save)."""
	character["quetes_actives"] = [
		a for a in character.get("quetes_actives", []) if a.get("id") != q.get("id")
	]
	character.setdefault("quetes_terminees", []).append({
		"id": q.get("id"),
		"titre": q.get("titre", "—"),
		"rang": q.get("rang", "F"),
		"echec": bool(echec),
		"recompenses": {} if echec else dict(q.get("recompenses", {})),
		"termine_at": now,
	})


def expirer_transports(character: dict, now: int) -> list:
	"""Sort des actives toutes les courses dont le délai est écoulé et les archive en échec
	(mute sans save). La cargaison RESTE dans le sac — le joueur garde la marchandise, seule
	sa réputation en pâtit. Renvoie les quêtes échues (l'appelant applique le −1 relation)."""
	echues = [
		q for q in transports_actifs(character)
		if int(q.get("expire_at", 0) or 0) and now >= int(q["expire_at"])
	]
	for q in echues:
		archiver(character, q, echec=True, now=now)
	return echues


def traiter_expirations(character: dict, now: int, get_doc_fn, save_doc_fn, find_docs_fn=None) -> list:
	"""Expire les courses échues ET applique la sanction de réputation (−1 chez le donneur ET
	chez tous les lieux de sa maison — même sanction qu'un abandon, cf. `quetes.sanctionner_renoncement`),
	en persistant chaque doc `relation` (doc annexe : il n'est pas dans le character).
	`find_docs_fn` est optionnel (repli sur celui de db.config) : il n'est là que pour l'injection.
	Le personnage est muté SANS save — l'appelant le sauvegarde s'il reçoit une liste non
	vide. Renvoie les quêtes échues (pour le toast client)."""
	echues = expirer_transports(character, now)
	for q in echues:
		lieu_doc = get_doc_fn(q.get("giver")) if q.get("giver") else None
		if not lieu_doc:
			continue
		quetes.sanctionner_renoncement(character, lieu_doc, get_doc_fn, save_doc_fn, find_docs_fn)
	return echues


def _solder(character: dict, q: dict, get_doc_fn, save_doc_fn, now: int) -> dict:
	"""Solde la course : récompenses (XP + prime + items), archivage, +1 relation avec le DONNEUR
	(jamais le destinataire). Le doc `relation` est ANNEXE (hors character) : il est persisté ici ;
	le character est muté sans save — l'endpoint le sauvegarde.

	⚠️ `compagnie` remonte tel quel : ce sont des docs `aventurier:*` mutés (la compagnie a
	gagné la même XP), et ils sont ANNEXES comme la relation — mais persistés par l'ENDPOINT,
	APRÈS son save du personnage, jamais ici (un 409 rejoué les paierait deux fois)."""
	recap = quetes.appliquer_recompenses(character, q)
	archiver(character, q, echec=False, now=now)
	giver_doc = get_doc_fn(q.get("giver")) if q.get("giver") else None
	relation_val = quetes.recompenser_donneur(character, giver_doc, get_doc_fn, save_doc_fn)
	# ⚠️ On PROPAGE le récap du chokepoint (`**recap`) au lieu de le recopier clé par clé :
	# une clé ajoutée en amont — l'inscription au rang de guilde (`rang`) — serait sinon
	# perdue ICI, en silence. Le personnage porterait bien son rang neuf, mais l'endpoint ne
	# l'apprendrait jamais, donc aucun payload de resynchronisation : l'affichage resterait
	# figé sur l'ancien rang jusqu'au prochain rechargement de /play (cf. Conventions §10).
	return {**recap, "relation": relation_val}


def _ranger_chez_le_destinataire(q: dict, lieu_doc: dict, get_doc_fn, save_doc_fn, rand_fn) -> dict:
	"""La marchandise entre chez le destinataire : ce qu'il vend a une chance de rejoindre son
	étal (le joueur voit donc l'effet de sa course sur le stock du magasin). Le doc `lieu` est
	ANNEXE → persisté ici."""
	rayon = deposer_en_rayon(lieu_doc, q.get("cargaison") or [], get_doc_fn, rand_fn)
	if rayon:
		save_doc_fn(lieu_doc)
	return rayon


def reussir_transport(character: dict, q: dict, lieu_doc: dict, get_doc_fn, save_doc_fn,
					  now: int | None = None, rand_fn=random.random) -> dict:
	"""Livraison réussie chez le destinataire, qui SOLDE la course (cas nominal des marchands :
	c'est lui qui paie). Renvoie {xp, purse, relation, rayon}."""
	now = int(quetes.now_epoch() if now is None else now)
	rayon = _ranger_chez_le_destinataire(q, lieu_doc, get_doc_fn, save_doc_fn, rand_fn)
	recap = _solder(character, q, get_doc_fn, save_doc_fn, now)
	recap["rayon"] = rayon
	return recap


def livrer_en_attente_de_retour(character: dict, q: dict, lieu_doc: dict, get_doc_fn,
								save_doc_fn, now: int | None = None,
								rand_fn=random.random) -> dict:
	"""Livraison d'une course `retour` : la marchandise est remise, mais RIEN n'est payé ici —
	la quête reste active, le temps d'aller rendre compte au donneur (`rapporter_transport`).
	Le délai, lui, portait sur la livraison : il est levé, le chemin du retour n'est pas couru
	d'avance. Mute sans save (les docs annexes sont persistés). Renvoie {rayon}."""
	now = int(quetes.now_epoch() if now is None else now)
	rayon = _ranger_chez_le_destinataire(q, lieu_doc, get_doc_fn, save_doc_fn, rand_fn)
	q["livree_at"] = now
	q.pop("expire_at", None)
	return {"rayon": rayon}


def rapporter_transport(character: dict, q: dict, get_doc_fn, save_doc_fn,
						now: int | None = None) -> dict:
	"""Le joueur rend compte au donneur d'une course `retour` déjà livrée : c'est LUI qui solde
	(XP, prime, items de récompense — la carte d'aventurier) et dont la relation monte."""
	now = int(quetes.now_epoch() if now is None else now)
	return _solder(character, q, get_doc_fn, save_doc_fn, now)
