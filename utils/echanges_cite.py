"""Échanges des ateliers d'un bien de joueur avec les boutiques de SA cité (pur).

Décisions de l'Auteur (12/11/2026) — compétence `telluris-proprietes` § Échanges avec la cité :

- **Rattrapage paresseux** (aucun tick de fond) : `prop.echanges_at` ; une passe par période
  (`periode_s`, tirée à ±`alea`), au plus `rattrapage_max_s` de temps rattrapé. Absent ⇒ posé à
  la première lecture, aucune passe rétroactive.
- **Vente boutique par boutique** : chaque boutique de la cité est un acheteur DISTINCT — elle
  paie le prix qu'obtiendrait le PROPRIÉTAIRE chez elle (sa relation, ses prix négociés, le
  stock de la boutique) et REFUSE dès que son stock atteint sa cible. Plus offrant d'abord.
  Sans négociant : décote ; avec : bonus de son niveau (jamais au-delà de `pmax`).
- **Achat** (négociant au poste d'un aménagement `achats_cite`) : aux seules boutiques dont le
  rayon DÉPASSE la cible, moins cher d'abord, payé par la caisse de l'atelier servi, posé en
  RÉSERVE (jamais en rayon) ⇒ jamais revendu tel quel.
- **Négociant** : niveau 1-5 DÉRIVÉ de `negoce_xp` ; commerce, formation payée, « Tenir les
  livres » (propriétaire Lettré).
- **Ce qui produit seul** : jardinier d'un aménagement `autoproduction` (la terre fournit ses
  feuilles, en réserve, plafonnées) ; récoltes prêtes cueillies et confiées au négociant, sinon
  rangées.
- **`vente_cite: false`** sur un employé : ni cité ni crieur (le visiteur peut toujours acheter).

Une cité = `marche.est_cite` : la même mécanique s'appliquera telle quelle à une colonie
(relation de son fondateur), docs/lore/systemes/20261112_voie_de_colonisation.md.

Modules purs (CLAUDE.md §2) : lectures injectées, mutent sans sauver — `rattraper` rend les docs
à persister."""

import random
import time

from models import character_stats
from utils import marche
from utils import montures
from utils import proprietes
from utils.characters import item_ref_weight, resolve_item_ref


# ── Réglages (défauts ; `rules:proprietes.reglages.echanges` / `.negociant` les remplacent) ──

ECHANGES_DEFAUT = {
	"periode_s": 3600,            # une passe par heure réelle…
	"alea": 0.5,                  # … tirée entre 30 et 90 minutes
	"rattrapage_max_s": 172800,   # au plus 2 jours rattrapés d'un coup
	"proba_vente": 0.5,           # chance par passe qu'un objet tente sa vente
	"reserve": 1,                 # exemplaires gardés en rayon pour les visiteurs
	"seuil_refus": 1.0,           # une boutique refuse à ce multiple de sa cible
	"decote_sans_negociant": 0.2,
	"prospection_base": 3,        # boutiques comparées par objet, sans négociant
	"portage_kg": 20,             # kg échangés par passe, pour tout le bien
	"achat_cible": 5,             # réserve visée par clé de recette quand le négociant achète
	"caisse_max_cuivre": {"logement": 5000, "maison": 20000, "demeure": 60000, "domaine": 200000},
	"journal_max": 20,
}

NEGOCIANT_DEFAUT = {
	"seuils_xp": [0, 500, 2000, 6000, 15000],   # niveau n atteint à seuils_xp[n-1]
	"bonus_prix": [0.0, 0.05, 0.10, 0.15, 0.20],
	"prospection": [4, 5, 6, 7, 8],
	"xp_par_cuivre": 0.1,                         # 1 point par 10 cu échangés
	"seance_part": 0.25,                          # part de l'écart au niveau suivant
	"seance_delai_s": 86400,
	"formation_cout_par_xp": 2,                   # cuivre par point acheté
	"vocation_livres": "lettre",
}


def reglages(cat: dict) -> dict:
	return {**ECHANGES_DEFAUT, **(proprietes.reglages(cat).get("echanges") or {})}


def reglages_negociant(cat: dict) -> dict:
	return {**NEGOCIANT_DEFAUT, **(proprietes.reglages(cat).get("negociant") or {})}


def _int(v, defaut=0) -> int:
	try:
		return int(v)
	except (TypeError, ValueError):
		return defaut


def _item_id(item_doc: dict | None):
	return (item_doc or {}).get("item") or (item_doc or {}).get("_id")


# ── Le temps ─────────────────────────────────────────────────────────────────────

def passes_ecoulees(prop: dict, regl: dict, now: int, rand=random) -> tuple[int, int]:
	"""(passes, nouvel `echanges_at`). Les périodes sont tirées une à une à ±`alea` dans le temps
	écoulé, plafonné à `rattrapage_max_s` ; le reste de la période entamée est conservé. Jamais
	lu (premier passage) ⇒ (0, now) : aucune passe rétroactive."""
	last = _int(prop.get("echanges_at"))
	if not last:
		return 0, now
	periode = max(60.0, float(regl.get("periode_s") or 3600))
	alea = min(0.9, max(0.0, float(regl.get("alea") or 0)))
	t = float(max(last, now - _int(regl.get("rattrapage_max_s"), 172800)))
	n = 0
	while True:
		d = periode * (1 + alea * (2 * rand.random() - 1))
		if t + d > now:
			break
		t += d
		n += 1
	return n, int(t)


# ── La cité ──────────────────────────────────────────────────────────────────────

def cite_de(prop: dict, get_doc_fn) -> dict | None:
	"""Premier ancêtre `marche.est_cite` du bien (le bien pend à sa ville ; la remontée s'arrête
	à la cité, jamais au pays)."""
	vus = set()
	lid = (prop or {}).get("lieu_parent")
	while lid and lid not in vus and len(vus) < 8:
		vus.add(lid)
		doc = get_doc_fn(lid)
		if not doc:
			return None
		if marche.est_cite(doc):
			return doc
		lid = doc.get("lieu_parent")
	return None


def boutiques_cite(cite_id, find_docs_fn) -> list:
	"""Boutiques de la cité qui achètent et vendent selon leur stock : même requête que la nuit
	d'auberge (`commande.voisins_cite`). Écartés : le négociant de ville (il achète TOUT, sans
	stock visé : il n'y aurait jamais de refus) et le revendeur (étable)."""
	if not cite_id or not find_docs_fn:
		return []
	return [b for b in (find_docs_fn({"type": "lieu", "lieu_parent": cite_id}) or [])
			if b.get("categorie") and not marche.est_cite(b)
			and not marche.est_negociant(b) and not montures.lieu_vend_montures(b)]


# ── Le négociant ─────────────────────────────────────────────────────────────────

def est_negociant(employe: dict) -> bool:
	return proprietes.est_atelier(employe) and marche.est_negociant(employe)


def negociant_du_bien(employes: list) -> dict | None:
	return next((e for e in employes if est_negociant(e)), None)


def niveau_negociant(employe: dict, regln: dict) -> int:
	"""Niveau DÉRIVÉ de l'expérience (jamais stocké)."""
	xp = _int((employe or {}).get("negoce_xp"))
	seuils = regln.get("seuils_xp") or [0]
	return max(1, sum(1 for s in seuils if xp >= _int(s)))


def _par_niveau(regln: dict, cle: str, niveau: int):
	vals = regln.get(cle) or [0]
	return vals[min(len(vals), max(1, niveau)) - 1]


def capacites_negociant(employe: dict, regln: dict) -> dict:
	"""Fiche du négociant (panneau 🏠) : niveau, expérience, seuil suivant, bonus, prospection."""
	niveau = niveau_negociant(employe, regln)
	seuils = regln.get("seuils_xp") or [0]
	suivant = _int(seuils[niveau]) if niveau < len(seuils) else None
	return {"niveau": niveau, "niveau_max": len(seuils), "xp": _int(employe.get("negoce_xp")),
			"xp_suivant": suivant, "bonus_prix": float(_par_niveau(regln, "bonus_prix", niveau)),
			"prospection": _int(_par_niveau(regln, "prospection", niveau))}


def gain_seance(employe: dict, regln: dict) -> int:
	"""Points d'une séance (livres ou formation) : une part de l'écart au niveau suivant, au
	moins 1 ; 0 au niveau maximal."""
	cap = capacites_negociant(employe, regln)
	if cap["xp_suivant"] is None:
		return 0
	seuils = regln.get("seuils_xp") or [0]
	ecart = cap["xp_suivant"] - _int(seuils[cap["niveau"] - 1])
	return max(1, int(round(ecart * float(regln.get("seance_part", 0.25)))))


def cout_formation(employe: dict, regln: dict) -> int:
	return gain_seance(employe, regln) * _int(regln.get("formation_cout_par_xp"), 2)


def _delai_restant(employe: dict, champ: str, regln: dict, now: int) -> int:
	"""Secondes avant la prochaine séance ; jamais faite ⇒ 0."""
	fait = _int((employe or {}).get(champ))
	if not fait:
		return 0
	return max(0, fait + _int(regln.get("seance_delai_s"), 86400) - now)


def tenir_les_livres(character: dict, employe: dict, regln: dict, now: int | None = None) -> tuple[bool, str, int]:
	"""« 📒 Tenir les livres » : le propriétaire de vocation Lettré travaille les comptes avec
	son négociant — gratuit, une fois par délai. (ok, raison, points)."""
	now = int(time.time()) if now is None else now
	if (character or {}).get("voc") != regln.get("vocation_livres", "lettre"):
		return False, "Seul un Lettré sait tenir les livres d'un négoce.", 0
	return _seance(employe, "livres_at", regln, now)


def former(employe: dict, regln: dict, now: int | None = None) -> tuple[bool, str, int]:
	"""Formation payée : mêmes points qu'une séance de livres, délai distinct. Le paiement
	(`cout_formation`, calculé AVANT) reste à l'appelant."""
	now = int(time.time()) if now is None else now
	return _seance(employe, "formation_at", regln, now)


def _seance(employe: dict, champ: str, regln: dict, now: int) -> tuple[bool, str, int]:
	if not est_negociant(employe):
		return False, "Ce PNJ n'est pas un négociant.", 0
	pts = gain_seance(employe, regln)
	if not pts:
		return False, "Votre négociant n'a plus rien à apprendre.", 0
	reste = _delai_restant(employe, champ, regln, now)
	if reste:
		return False, f"Revenez dans {max(1, reste // 3600)} h.", 0
	employe["negoce_xp"] = _int(employe.get("negoce_xp")) + pts
	employe[champ] = now
	return True, "", pts


# ── Contexte d'une passe ─────────────────────────────────────────────────────────

def vente_autorisee(employe: dict) -> bool:
	"""Option du propriétaire (clic sur le PNJ) : absente ⇒ autorisée."""
	return (employe or {}).get("vente_cite") is not False


def _meilleur(prop, cat, employes, cle, defaut=0):
	vals = proprietes.valeurs_effet(prop, cat, employes, cle)
	return max(vals, key=lambda v: float(v) if not isinstance(v, dict) else 0) if vals else defaut


class Contexte:
	"""État partagé par les passes d'un rattrapage : stocks des boutiques en MÉMOIRE (une
	écriture par boutique touchée à la fin), relations du propriétaire lues une fois chacune."""

	def __init__(self, prop, cat, employes, boutiques, get_doc_fn, rand, now):
		self.prop, self.cat, self.employes = prop, cat, employes
		self.boutiques = boutiques
		self.get_doc = get_doc_fn
		self.rand, self.now = rand, now
		self.regl = reglages(cat)
		self.regln = reglages_negociant(cat)
		self.negociant = negociant_du_bien(employes)
		self.niveau = capacites_negociant(self.negociant, self.regln) if self.negociant else None
		self.achats = bool(self.negociant) and proprietes.effet_actif(prop, cat, employes, "achats_cite")
		self.prospection = ((self.niveau or {}).get("prospection") or _int(self.regl["prospection_base"], 3)) \
			+ _int(_meilleur(prop, cat, employes, "prospection"))
		self.portage_passe = float(self.regl["portage_kg"]) + float(_meilleur(prop, cat, employes, "portage_kg"))
		self.remise = float(_meilleur(prop, cat, employes, "remise_achat"))
		crieur = proprietes.valeurs_effet(prop, cat, employes, "crieur")
		self.crieur = max((_int((c or {}).get("unites"), 1) for c in crieur if isinstance(c, dict)), default=0)
		facteur = float(_meilleur(prop, cat, employes, "caisse_facteur", 1) or 1)
		self.caisse_max = int(_int((self.regl.get("caisse_max_cuivre") or {}).get(prop.get("type_propriete")), 5000) * facteur)
		self.proprietaire = {"_id": prop.get("proprietaire")}
		self._relations = {}
		self.touchees = {}
		self.journal = {}
		self.gain = 0
		self.echange = 0
		self.portage = self.portage_passe

	@classmethod
	def libre(cls, proprietaire_id, regl, regln, negociant, get_doc_fn, rand, now, prospection=None,
			  portage_kg=None, crieur=0, caisse_max=5000):
		"""Contexte sans bien urbain ni catalogue `rules:proprietes` : la voie de colonisation
		(`utils/colonisation.echanger`) y vend la production de ses PNJ à ses propres boutiques,
		avec les MÊMES prix (`prix_vente_boutique`) et le même journal."""
		ctx = cls.__new__(cls)
		ctx.prop, ctx.cat, ctx.employes, ctx.boutiques = None, None, [], []
		ctx.get_doc, ctx.rand, ctx.now = get_doc_fn, rand, now
		ctx.regl, ctx.regln = {**ECHANGES_DEFAUT, **(regl or {})}, {**NEGOCIANT_DEFAUT, **(regln or {})}
		ctx.negociant = negociant
		ctx.niveau = capacites_negociant(negociant, ctx.regln) if negociant else None
		ctx.achats = False
		ctx.prospection = prospection if prospection is not None else \
			((ctx.niveau or {}).get("prospection") or _int(ctx.regl["prospection_base"], 3))
		ctx.portage_passe = float(ctx.regl["portage_kg"] if portage_kg is None else portage_kg)
		ctx.remise, ctx.crieur, ctx.caisse_max = 0.0, int(crieur), int(caisse_max)
		ctx.proprietaire = {"_id": proprietaire_id}
		ctx._relations, ctx.touchees, ctx.journal = {}, {}, {}
		ctx.gain = ctx.echange = 0
		ctx.portage = ctx.portage_passe
		return ctx

	def relation(self, boutique):
		bid = boutique.get("_id")
		if bid not in self._relations:
			self._relations[bid] = marche.get_relation(self.proprietaire, boutique, self.get_doc)
		return self._relations[bid]

	def noter(self, sens, item_doc, lieu, qty, cuivre):
		cle = (sens, _item_id(item_doc), (lieu or {}).get("_id"))
		e = self.journal.setdefault(cle, {"sens": sens, "item": (item_doc or {}).get("label") or (item_doc or {}).get("nom") or _item_id(item_doc),
										   "lieu": (lieu or {}).get("label") or "", "qty": 0, "cuivre": 0})
		e["qty"] += qty
		e["cuivre"] += cuivre


# ── Prix ─────────────────────────────────────────────────────────────────────────

def prix_vente_boutique(ctx: Contexte, boutique: dict, item_doc: dict) -> int | None:
	"""Ce que CETTE boutique paie l'objet, ou None si elle n'en veut pas : celui qu'obtiendrait
	le propriétaire (relation, prix négociés, stock de la boutique), décoté sans négociant,
	bonifié par lui (jamais au-delà de `pmax`). Refus dès que son stock atteint sa cible."""
	item_id = _item_id(item_doc)
	if not marche.lieu_buys(boutique, item_doc):
		return None
	pmin, pmax, stock = marche.params_vente_lieu(boutique, item_doc, item_id)
	cible = marche.stock_cible_pour(boutique, item_doc)
	if stock >= cible * float(ctx.regl["seuil_refus"]):
		return None
	p = marche.prix_marche(ctx.relation(boutique), item_id, pmin, pmax, "vente", stock, cible)
	if ctx.negociant:
		p = min(pmax, p + float(ctx.niveau["bonus_prix"]) * max(0, pmax - p))
	else:
		p = p * (1 - float(ctx.regl["decote_sans_negociant"]))
	return max(1, int(round(p)))


def prix_achat_boutique(ctx: Contexte, boutique: dict, item_doc: dict) -> int | None:
	"""Ce que CETTE boutique demande, ou None si elle ne vend pas : seulement au-dessus de sa
	cible ; prix du propriétaire, rapproché de `pmin` par le négociant et le teneur de livres,
	jamais en dessous."""
	item_id = _item_id(item_doc)
	q = next((_int(e.get("qty")) for e in boutique.get("stock_vente") or [] if e.get("item_id") == item_id), 0)
	cible = marche.stock_cible_pour(boutique, item_doc)
	if q <= cible:
		return None
	pmin, pmax = marche.prix_achat_lieu(boutique, item_doc, item_id)
	p = marche.prix_marche(ctx.relation(boutique), item_id, pmin, pmax, "achat", q, cible)
	baisse = min(1.0, float((ctx.niveau or {}).get("bonus_prix") or 0) + ctx.remise)
	return max(pmin, int(round(p - baisse * max(0, p - pmin))))


# ── Vendre ───────────────────────────────────────────────────────────────────────

def _caisse(e) -> int:
	return _int(e.get("caisse_cuivre"))


def _retirer_rayon(doc: dict, item_id, qty: int = 1) -> None:
	for e in doc.get("stock_vente") or []:
		if e.get("item_id") == item_id:
			e["qty"] = _int(e.get("qty")) - qty
	doc["stock_vente"] = [e for e in doc.get("stock_vente") or [] if _int(e.get("qty")) > 0]


def vendre(ctx: Contexte, employe: dict) -> set:
	"""Une passe de vente de l'atelier aux boutiques de la cité. Rend les objets restés sans
	preneur (pour le crieur). Mute l'employé, les boutiques et le contexte."""
	invendus = set()
	if not vente_autorisee(employe):
		return invendus
	reserve = _int(ctx.regl["reserve"], 1)
	for entree in list(employe.get("stock_vente") or []):
		item_id = entree.get("item_id")
		dispo = _int(entree.get("qty")) - reserve
		if dispo <= 0 or ctx.rand.random() >= float(ctx.regl["proba_vente"]):
			continue
		item_doc = resolve_item_ref(item_id)
		if not item_doc:
			continue
		acheteurs = [b for b in ctx.boutiques if marche.lieu_buys(b, item_doc)]
		k = min(len(acheteurs), max(1, ctx.prospection))
		echantillon = ctx.rand.sample(acheteurs, k) if k else []
		poids = float(item_ref_weight(item_id) or 0)
		vendus = 0
		while vendus < dispo and _caisse(employe) < ctx.caisse_max and poids <= ctx.portage:
			offres = [(p, i) for i, b in enumerate(echantillon)
					  if (p := prix_vente_boutique(ctx, b, item_doc)) is not None]
			if not offres:
				break
			prix, i = max(offres, key=lambda o: (o[0], -o[1]))
			b = echantillon[i]
			marche.absorber_achat(b, item_doc)
			_retirer_rayon(employe, item_id)
			proprietes.encaisser(employe, prix)
			ctx.portage -= poids
			ctx.gain += prix
			ctx.echange += prix
			ctx.touchees[b["_id"]] = b
			ctx.noter("vente", item_doc, b, 1, prix)
			vendus += 1
		if not vendus:
			invendus.add(item_id)
	return invendus


def crier(ctx: Contexte, employe: dict, invendus: set, budget: list) -> None:
	"""Le crieur vend aux habitants ce qu'aucune boutique n'a pris, au plus bas prix
	(`pmin × RACHAT_FACTEUR`, sous tout rachat de boutique : jamais un débouché meilleur que la
	cité). `budget` = [unités restantes de la passe pour tout le bien]."""
	if not ctx.crieur or not vente_autorisee(employe):
		return
	reserve = _int(ctx.regl["reserve"], 1)
	for item_id in sorted(invendus):
		while budget[0] > 0 and _caisse(employe) < ctx.caisse_max:
			if next((_int(e.get("qty")) for e in employe.get("stock_vente") or []
					 if e.get("item_id") == item_id), 0) <= reserve:
				break
			item_doc = resolve_item_ref(item_id) or {}
			pmin, _pmax = marche.prix_range_cuivre(item_doc, item_id)
			prix = max(1, int(round(pmin * float(character_stats.RACHAT_FACTEUR))))
			_retirer_rayon(employe, item_id)
			proprietes.encaisser(employe, prix)
			ctx.gain += prix
			ctx.noter("crieur", item_doc, {"label": "les habitants"}, 1, prix)
			budget[0] -= 1


# ── Acheter ──────────────────────────────────────────────────────────────────────

def acheter(ctx: Contexte, employe: dict) -> None:
	"""Le négociant achète pour CET atelier (jamais pour lui-même, qui n'a pas de recette) les
	matières de ses recettes dont la réserve est sous `achat_cible`, aux boutiques qui en ont
	TROP, moins cher d'abord, sur la caisse de l'atelier. Rien de ce qu'il produit."""
	if not ctx.achats or est_negociant(employe) or not proprietes.est_atelier(employe):
		return
	besoins = set(marche.besoins_lieu(employe))
	if not besoins:
		return
	stock = employe.setdefault("stock_matieres", {})
	cible = _int(ctx.regl["achat_cible"], 5)
	if all(_int(stock.get(c)) >= cible for c in besoins):
		return
	k = min(len(ctx.boutiques), max(1, ctx.prospection))
	vendeurs = ctx.rand.sample(ctx.boutiques, k) if k else []
	# Offres : (boutique, item, clé chez l'atelier), clé mémoïsée par objet.
	cles, offres = {}, []
	for b in vendeurs:
		for e in b.get("stock_vente") or []:
			iid = e.get("item_id")
			if iid not in cles:
				doc = resolve_item_ref(iid)
				ok = doc and not marche.lieu_produit(employe, doc)
				cles[iid] = (doc, marche.cle_matiere_lieu(employe.get("categorie"), doc, employe) if ok else None)
			doc, cle = cles[iid]
			if cle in besoins:
				offres.append((b, doc, cle))
	for cle in sorted(besoins):
		while _int(stock.get(cle)) < cible:
			prix_offres = [(p, j) for j, (b, doc, c) in enumerate(offres)
						   if c == cle and (p := prix_achat_boutique(ctx, b, doc)) is not None]
			if not prix_offres:
				break
			prix, j = min(prix_offres)
			b, doc, _c = offres[j]
			poids = float(item_ref_weight(_item_id(doc)) or 0)
			if prix > _caisse(employe) or poids > ctx.portage:
				break
			_retirer_rayon(b, _item_id(doc))
			stock[cle] = _int(stock.get(cle)) + 1
			employe["caisse_cuivre"] = _caisse(employe) - prix
			ctx.portage -= poids
			ctx.echange += prix
			ctx.touchees[b["_id"]] = b
			ctx.noter("achat", doc, b, 1, -prix)


# ── Ce qui produit seul ──────────────────────────────────────────────────────────

def autoproduit(employe: dict, cat: dict) -> bool:
	"""Le poste de cet employé porte `effets_poste.autoproduction` (Jardin, Potager, Verger)."""
	adef = proprietes.amenagement_def(cat, (employe or {}).get("poste")) or {}
	return bool((adef.get("effets_poste") or {}).get("autoproduction"))


def autoproduire(employe: dict) -> bool:
	"""La terre fournit au jardinier ses matières brutes (graines…) comme le fournisseur d'une
	boutique de ville (`marche.appro_leaves_lieu`, débit `_appro_debit_pour`), mais en RÉSERVE
	SEULE et jamais au-delà de `STOCK_CIBLE_DEFAUT` : au comptoir, des graines données seraient
	vendues à la cité ; sans plafond, la réserve gonflerait sans fin pendant une absence."""
	plafond = max(1, int(character_stats.STOCK_CIBLE_DEFAUT))
	stock = employe.setdefault("stock_matieres", {})
	change = False
	for cle in marche.appro_leaves_lieu(employe):
		q = marche._appro_debit_pour(cle)
		actuel = _int(stock.get(cle))
		if q > 0 and actuel < plafond:
			stock[cle] = min(plafond, actuel + q)
			change = True
	return change


def cueillir(prop: dict, cat: dict, negociant: dict | None, flux: dict | None,
			 get_doc_fn, rand, now: int) -> list:
	"""Récoltes prêtes (Petit jardin, Terrain privé) cueillies d'elles-mêmes : confiées au
	négociant si sa vente est autorisée (`proprietes.donner` → `negoce.absorber`), sinon au
	Rangement, dans la limite du stockage — plein, la récolte attend. Rend les lignes du journal."""
	lignes = []
	for r in proprietes.recoltes(prop, cat, now):
		if not r["pret"]:
			continue
		avant = dict(prop.get("recoltes_at") or {})
		ok, _raison, refs = proprietes.recolter(prop, cat, r["amenagement"], get_doc_fn, rand, now)
		if not ok:
			continue
		if negociant and vente_autorisee(negociant):
			utiles = proprietes.cles_utiles_flux(prop, negociant, get_doc_fn)
			for ref in refs:
				proprietes.donner(negociant, resolve_item_ref(ref) or {}, flux, utiles, ref)
			lignes.append({"sens": "recolte", "item": r["nom"], "lieu": proprietes.nom_personnage(negociant),
						   "qty": len(refs), "cuivre": 0})
			continue
		poids = sum(float(item_ref_weight(x) or 0) for x in refs)
		if proprietes.poids_coffre(prop) + poids > proprietes.capacites(prop, cat)["stockage_kg"]:
			prop["recoltes_at"] = avant          # plein : elle attend
			continue
		prop.setdefault("coffre", []).extend(refs)
		lignes.append({"sens": "recolte", "item": r["nom"], "lieu": "Rangement", "qty": len(refs), "cuivre": 0})
	return lignes


# ── Le chokepoint ────────────────────────────────────────────────────────────────

def rattraper(prop: dict, cat: dict, get_doc_fn, find_docs_fn, rand=random, now: int | None = None,
			  passes_extra: int = 0, employes: list | None = None) -> dict:
	"""Joue les passes écoulées (+ `passes_extra`, la nuit du propriétaire) : récoltes,
	autoproduction, achats, production, ventes, crieur. Mute le bien, ses employés et les
	boutiques touchées ; rend `{"passes", "gain", "a_sauver": [docs], "journal"}` — l'appelant
	sauve (le bien EN DERNIER : il porte `echanges_at`)."""
	now = int(time.time()) if now is None else now
	regl = reglages(cat)
	passes, nouvel_at = passes_ecoulees(prop, regl, now, rand)
	passes += max(0, int(passes_extra))
	bouge = _int(prop.get("echanges_at")) != nouvel_at
	prop["echanges_at"] = nouvel_at
	bilan = {"passes": passes, "gain": 0, "a_sauver": [], "journal": []}
	if not passes:
		if bouge:                       # premier passage : l'horloge démarre
			bilan["a_sauver"].append(prop)
		return bilan
	employes = proprietes.employes_effectifs(prop, get_doc_fn) if employes is None else employes
	ateliers = [e for e in employes if proprietes.est_atelier(e)]
	cite = cite_de(prop, get_doc_fn)
	boutiques = boutiques_cite(cite.get("_id"), find_docs_fn) if cite and ateliers else []
	ctx = Contexte(prop, cat, employes, boutiques, get_doc_fn, rand, now)
	flux = proprietes.flux_propriete(prop)
	lignes = cueillir(prop, cat, ctx.negociant, flux, get_doc_fn, rand, now)
	for _ in range(passes):
		ctx.portage = ctx.portage_passe
		budget = [ctx.crieur]
		for e in ateliers:
			if autoproduit(e, cat):
				autoproduire(e)
			acheter(ctx, e)
		for e in ateliers:
			invendus = set()

			def _ecouler(d, _e=e):
				invendus.update(vendre(ctx, _e))
				return []
			proprietes.produire(e, flux, 1, cat, ecouler=_ecouler)
			crier(ctx, e, invendus, budget)
	if ctx.negociant and ctx.echange:
		ctx.negociant["negoce_xp"] = _int(ctx.negociant.get("negoce_xp")) \
			+ int(ctx.echange * float(ctx.regln["xp_par_cuivre"]))
	marche.persister_flux(flux, lambda _d: True)       # écrit le pool sur le bien, sans sauver
	journal = lignes + [dict(v, t=now) for v in ctx.journal.values()]
	if journal:
		prop["echanges_journal"] = (journal + list(prop.get("echanges_journal") or []))[:_int(regl["journal_max"], 20)]
	bilan.update(gain=ctx.gain, journal=journal,
				 a_sauver=list(employes) + list(ctx.touchees.values()) + [prop])
	return bilan


def biens_a_rattraper(character: dict, lieu_doc: dict, get_doc_fn) -> list:
	"""Les biens POSSÉDÉS du personnage dans la cité où il se trouve (rattrapage à distance) :
	`lieu_doc` est la cité ou un lieu dont la cité est le parent direct."""
	if marche.est_cite(lieu_doc):
		cite_id = lieu_doc.get("_id")
	else:
		cite_id = (lieu_doc or {}).get("lieu_parent")
	if not cite_id:
		return []
	return [p for p in proprietes.proprietes_de(character, get_doc_fn)
			if p.get("statut") == proprietes.POSSEDEE and p.get("lieu_parent") == cite_id
			and p.get("mode") == proprietes.MODE_ACHAT]


def persister(bilan: dict, save_doc_fn) -> None:
	"""Sauve ce qu'a touché un rattrapage, le bien EN DERNIER (il porte `echanges_at` : un échec
	plus tôt laisse les passes à rejouer plutôt que perdues). Écritures best-effort, comme le tick
	des boutiques : un conflit sur une boutique ne bloque pas le rendu."""
	docs = bilan.get("a_sauver") or []
	for d in docs:
		save_doc_fn(d)


def rattraper_biens(biens: list, cat: dict, get_doc_fn, find_docs_fn, save_doc_fn,
					rand=random, now: int | None = None, exclure=()) -> int:
	"""Rattrape et sauve chaque bien (`biens_a_rattraper`, registre) ; rend le gain total."""
	gain = 0
	for p in biens:
		if p.get("_id") in exclure:
			continue
		b = rattraper(p, cat, get_doc_fn, find_docs_fn, rand, now)
		persister(b, save_doc_fn)
		gain += b["gain"]
	return gain
