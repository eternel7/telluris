#!/usr/bin/env python
# dev/audit_economy.py
"""Audit de l'économie : ce que les recettes et les items disent de la chaîne de production.

Trois indicateurs, calculés sur un DUMP (jamais sur la base live) :

  1. **% d'items sans recette atteignable** — part des docs `type: item` qu'aucune recette
     *dont toute la chaîne d'intrants est fondée* ne produit. Décomposé en « aucune recette
     ne les vise » (normal : butin, carcasses, objets de quête) et « une recette les vise
     mais ne peut jamais cuire » (défaut : chaîne rompue).
  2. **% de recettes dont le produit n'entre jamais en rayon** — part des `type: recette`
     qui ne peuvent jamais aboutir dans le `stock_vente` d'un lieu.
  3. **Marge médiane d'un objet fabriqué** — (prix payé par le joueur − coût des intrants)
     / coût des intrants, médiane sur les items effectivement fabricables.

────────────────────────────────────────────────────────────────────────────────────────
HYPOTHÈSES DE RÉFÉRENCE (ce que « atteignable », « en rayon » et « marge » veulent dire ici)
────────────────────────────────────────────────────────────────────────────────────────

**Le moteur est celui du jeu, pas une réimplémentation.** `db.config.get_doc`/`find_docs`
sont rebranchés sur le dump AVANT l'import de `utils.marche`, puis les variables de monde
sont chargées depuis le `rules:world_variables` du dump. Prix, coûts de revient, index de
recettes et clés matières viennent donc de `utils/marche.py` lui-même : l'audit mesure le
jeu tel qu'il tourne, pas une théorie du jeu.

A. **Approvisionnement d'une clé matière sans production.** Une entrée de recette est soit
   une clé `item:<id>`, soit une sous-catégorie (cf. `marche.recette_matieres`). DEUX
   sources, et il faut les deux :
     · **le joueur l'apporte** — un doc item existe pour cet id, ou au moins un doc item
       porte cette sous-catégorie (`characters.item_sous_categorie`, `categorie` en repli).
       ⚠️ C'est bien la sous-catégorie du doc qui compte, pas son nom : `item:argent` porte
       `sous_categorie: metaux_precieux`, donc le revendre à l'armurier alimente
       `stock_matieres["metaux_precieux"]` et JAMAIS la clé `argent` ;
     · **le fournisseur la livre** — `approvisionner` injecte les feuilles de la catégorie
       (`appro_leaves_categorie`) au débit `_appro_debit_pour(cle)`, directement sous la clé
       demandée. Un débit à 0 (`APPRO_DEBIT["herbe"]`) ne livre rien. Seules les catégories
       portées par un doc `lieu:*` comptent : sans atelier, personne n'est livré.
   C'est cette seconde source qui rend fabricables les armes à l'argent ci-dessus.

B. **Approvisionnement par production.** Une recette cuite fournit son `objet_final` ET
   `objet_final_item_id(objet_final)` — exactement la règle du moteur (`_get_marche_map`,
   qui retranche des « feuilles » les clés présentes dans `outputs` OU `outputs_ids`).
   La sous-catégorie du doc produit n'est PAS ajoutée : le moteur ne la compte pas.

C. **Atteignabilité (indicateur 1) = point fixe global.** On part des clés fournies à la
   source (A), on cuit toute recette dont TOUTES les entrées sont disponibles, on ajoute
   ses sorties (B), on recommence jusqu'à stabilité. Sûr vis-à-vis des cycles : une chaîne
   qui ne tient que par elle-même ne démarre jamais. Une recette sans aucune entrée ne cuit
   pas — le moteur l'écarte déjà (`_executer_production_batch`, filtre `if recette_matieres(r)`).

D. **« Entrer en rayon » (indicateur 2) = APPROVISIONNEMENT AUTONOME.** C'est l'hypothèse
   la plus lourde de ce fichier. Une recette n'entre en rayon que si :
     · un doc `lieu:*` porte sa `lieu_categorie` (sans atelier, rien ne cuit) ;
     · son `objet_final` résout vers un doc item EXISTANT — sinon la ligne est bien écrite
       dans `stock_vente` mais `resolve_stock_vente` la saute (`resolve_item_ref` → None) et
       le joueur ne la voit jamais ;
     · ses intrants sont disponibles SANS le joueur : livrés par `approvisionner` (feuilles
       de la catégorie à débit `APPRO_DEBIT` > 0) ou produits par une autre recette DE LA
       MÊME catégorie (chaînage intra-tick, cf. `_executer_production_batch`).
   Le joueur revendeur est donc EXCLU du calcul de référence. C'est délibéré : ce que le
   joueur apporte n'est pas une propriété de la donnée, et une boutique qui ne se garnit
   que si un joueur l'a garnie est vide au premier jour du monde. La ligne « même en
   supposant le joueur ravitailleur » sous l'indicateur relâche cette hypothèse et ne garde
   que les blocages structurels (pas d'atelier, pas de doc, chaîne globalement rompue).

E. **Marge (indicateur 3).** Pour un objet fabricable :
     · prix payé par le joueur = `prix_base_cuivre(pmin, pmax, RELATION_INITIALE, "achat")`,
       soit le milieu de fourchette à relation neutre (50) ;
     · stock supposé AU stock cible → `facteur_stock` vaut 1, donc `prix_marche` == ce
       prix de base. Aucun marchandage, aucun prix négocié persistant ;
     · coût des intrants = Σ `cout_production_cuivre(intrant) × quantité` ÷
       `quantite_produite`, pris sur la recette la MOINS CHÈRE parmi celles atteignables
       (la route qu'emprunterait un artisan rationnel) ;
     · marge = (prix − coût) / coût. Une marge négative = fabriquer coûte plus cher que
       le prix de vente : l'objet est vendu à perte par sa propre boutique.
   ⚠️ La marge n'est PAS mécaniquement `MARGE_TRANSFO` : `cout_production_cuivre` prend le
   MAX entre le coût propagé et le coût intrinsèque (poids × rareté), et un `valeur`
   explicite sur le doc coupe court à toute propagation. C'est précisément là que les
   écarts se logent.

F. **Déterminisme.** Aucun chemin utilisé ici ne tire de hasard (le hasard du marché vit
   dans `marchander`, `tenter_production` et `ecouler_produits_pnj`, jamais appelés) ; les
   parcours de docs sont triés par `_id` ; `random.seed(0)` est posé par ceinture. Deux
   exécutions sur le même dump rendent le même rapport, chiffre pour chiffre.

────────────────────────────────────────────────────────────────────────────────────────

Usage :
    python dev/audit_economy.py                       # demande quel dump utiliser
    python dev/audit_economy.py jsons/telluris-dump-20260906-081358.json
    python dev/audit_economy.py --dump <chemin>
    python dev/audit_economy.py --dernier              # le dump le plus récent

Le dump est OBLIGATOIRE et n'est jamais deviné TOUT SEUL : sans argument, le script liste
les dumps trouvés et demande lequel prendre — choisir en silence rendrait le rapport non
reproductible d'une semaine à l'autre sans que rien ne le signale.

⚠️ `--dernier` est la seule dérogation, et elle existe pour **l'écran `/admin/dev-tools`** :
la liste blanche de `utils/dev_tools.py` écrit l'argv en dur et `Popen` ne branche aucun
stdin, donc le bouton ne PEUT pas poser la question (sans dump, le script sortirait en code
2 avec la liste). Le rapport nomme le dump retenu en tête : le choix est automatique, il
n'est pas caché.
"""

import glob
import json
import os
import random
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ceinture : rien de ce qui suit ne tire de hasard, mais un changement de moteur ne doit pas
# rendre le rapport instable en silence (cf. hypothèse F).
random.seed(0)

# Console Windows en cp1252 : le rapport est cadré à l'Unicode (filets, « », ⚠, ←) et
# planterait à la PREMIÈRE ligne. On force l'UTF-8 sur la sortie plutôt que d'appauvrir
# la mise en page ; `errors="replace"` couvre les terminaux qui ne suivraient pas.
for _flux in (sys.stdout, sys.stderr):
	try:
		_flux.reconfigure(encoding="utf-8", errors="replace")
	except (AttributeError, OSError):
		pass


# ── Dump : choix et chargement ───────────────────────────────────────────────────

def dumps_disponibles() -> list[str]:
	"""Dumps trouvés (racine du dépôt et `jsons/`), du plus récent au plus ancien.
	Le nom porte l'horodatage (`telluris-dump-AAAAMMJJ-HHMMSS.json`) → tri lexical inverse."""
	trouves = set()
	for motif in ("telluris-dump-*.json", os.path.join("jsons", "telluris-dump-*.json")):
		for chemin in glob.glob(os.path.join(RACINE, motif)):
			trouves.add(os.path.relpath(chemin, RACINE).replace("\\", "/"))
	return sorted(trouves, key=lambda p: os.path.basename(p), reverse=True)


def _abandonner(candidats: list) -> None:
	"""Pas d'interlocuteur : on liste ce qu'on a vu et on sort en 2, sans rien auditer."""
	print("Aucun dump indiqué.", file=sys.stderr)
	if candidats:
		print("Dumps disponibles :", file=sys.stderr)
		for c in candidats:
			print("  " + c, file=sys.stderr)
	print("\nUsage : python dev/audit_economy.py <dump.json>", file=sys.stderr)
	sys.exit(2)


def demander_dump() -> str:
	"""Demande interactivement quel dump auditer, et sort en erreur si personne ne répond :
	un rapport d'équilibrage doit dire de QUELLE photo de la base il parle.

	⚠️ On ne se fie PAS à `sys.stdin.isatty()` seul — sous Git Bash / MSYS une redirection
	depuis `/dev/null` laisse `isatty()` à True et la lecture part droit sur `EOFError`.
	C'est l'`EOFError` qui fait autorité."""
	candidats = dumps_disponibles()
	if not sys.stdin.isatty():
		_abandonner(candidats)
	if candidats:
		print("Quel dump auditer ?")
		for i, c in enumerate(candidats, 1):
			print(f"  {i:2d}. {c}")
		invite = f"Numéro, ou chemin [1 = {candidats[0]}] : "
	else:
		print("Aucun `telluris-dump-*.json` trouvé (racine ou jsons/).")
		invite = "Chemin du dump à auditer : "
	try:
		reponse = input(invite).strip()
	except EOFError:
		print(file=sys.stderr)
		_abandonner(candidats)
	if not reponse:
		return candidats[0] if candidats else ""
	if reponse.isdigit() and 1 <= int(reponse) <= len(candidats):
		return candidats[int(reponse) - 1]
	return reponse


def charger_dump(chemin: str) -> tuple[list, dict]:
	"""Docs d'un dump `{"db","exported_at","doc_count","docs":[…]}` ou d'un export nu."""
	absolu = chemin if os.path.isabs(chemin) else os.path.join(RACINE, chemin)
	with open(absolu, encoding="utf-8") as f:
		data = json.load(f)
	if isinstance(data, dict) and "docs" in data:
		meta = {k: v for k, v in data.items() if k != "docs"}
		return data["docs"], meta
	return data, {}


# ── Branchement du dump à la place de CouchDB ────────────────────────────────────

def brancher_moteur(docs: list):
	"""Rebranche `db.config` sur le dump PUIS importe le moteur de marché.

	⚠️ L'ordre est la seule chose qui compte : `utils/marche.py` fait
	`from db.config import get_doc, find_docs, save_doc` — les noms sont liés à l'import,
	donc `db.config` doit être patché AVANT. Retourne les modules utiles."""
	# Coupe court à la tentative de connexion CouchDB de `db/config.py` (hôte `couchdb` par
	# défaut). Un audit doit lire le dump et RIEN d'autre : même exécuté sur le serveur, il
	# ne doit pas pouvoir mélanger la photo et la base live.
	os.environ["COUCHDB_HOST"] = "127.0.0.1"
	os.environ["COUCHDB_PORT"] = "1"
	if RACINE not in sys.path:
		sys.path.insert(0, RACINE)

	index = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}

	import db.config as dbc

	def _get_doc(doc_id):
		doc = index.get(doc_id)
		return dict(doc) if doc else None

	def _find_docs(selector, fields=None, limit=10_000):
		"""Mango réduit à l'égalité simple — la seule forme utilisée par le moteur, plus
		le `{"_id": {"$gt": None}}` de `dump_all_docs`."""
		out = []
		for doc in docs:
			if all(v == {"$gt": None} or doc.get(k) == v for k, v in (selector or {}).items()):
				out.append(dict(doc))
			if len(out) >= limit:
				break
		return out

	dbc.get_doc = _get_doc
	dbc.find_docs = _find_docs
	dbc.save_doc = lambda doc: doc      # audit en lecture seule : personne ne persiste
	dbc.delete_doc = lambda doc: None
	dbc.server = None
	dbc.db = None

	from models import character_stats
	from utils import characters, marche

	# Les tunables du dump gagnent sur les défauts du code (MARGE_TRANSFO, APPRO_DEBIT,
	# PRIX_DERIVE_BASE, RELATION_INITIALE…) : sinon l'audit décrirait un monde qui n'est
	# pas celui qui tourne.
	character_stats.load_world_variables()
	marche.reset_prix_cache()
	return character_stats, characters, marche


# ── Point fixe d'approvisionnement ───────────────────────────────────────────────

def cles_produites(marche, recette: dict) -> set:
	"""Clés matières qu'une recette cuite met à disposition. Règle du moteur : la clé brute
	`objet_final` ET l'id d'item résolu (cf. `_get_marche_map`, hypothèse B)."""
	slug = recette.get("objet_final") or ""
	if not slug:
		return set()
	return {slug, marche.objet_final_item_id(slug)}


def point_fixe(marche, recettes: list, acquis: set) -> tuple[set, set]:
	"""Cuit en boucle toute recette dont TOUTES les entrées sont disponibles, jusqu'à
	stabilité. Renvoie (`_id` des recettes cuites, clés disponibles au final).
	`acquis` est le point de départ (clés fournies sans production) ; il n'est pas muté.

	⚠️ On indexe par `_id` et jamais par identité d'objet : `find_docs` rend des COPIES,
	donc les docs vus par `lieu_recettes` ne sont pas ceux de la liste du dump."""
	acquis = set(acquis)
	cuites: set[str] = set()
	change = True
	while change:
		change = False
		for r in recettes:
			rid = r.get("_id")
			if rid in cuites:
				continue
			matieres = marche.recette_matieres(r)
			if not matieres:
				continue  # sans intrant, le moteur ne la prépare même pas
			if all(cle in acquis for cle, _q in matieres):
				cuites.add(rid)
				acquis |= cles_produites(marche, r)
				change = True
	return cuites, acquis


# ── Rapport ──────────────────────────────────────────────────────────────────────

# Le motif de blocage « le joueur est la chaîne d'appro » : le seul dont on détaille les
# matières manquantes, parce que c'est le seul qui se corrige en réglant `APPRO_DEBIT`
# ou en ajoutant une recette à la catégorie plutôt qu'en écrivant un doc.
MOTIF_INTRANTS = "intrants non ravitaillés sans le joueur"


def _pct(n: int, total: int) -> str:
	return f"{(100.0 * n / total):5.1f} %" if total else "    — "


def _mediane(valeurs: list) -> float:
	v = sorted(valeurs)
	n = len(v)
	if not n:
		return 0.0
	return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def _quantile(valeurs: list, q: float) -> float:
	v = sorted(valeurs)
	return v[min(len(v) - 1, int(q * len(v)))] if v else 0.0


def auditer(docs: list, meta: dict) -> None:
	character_stats, characters, marche = brancher_moteur(docs)

	par_type: dict[str, list] = {}
	for d in docs:
		if isinstance(d, dict):
			par_type.setdefault(d.get("type"), []).append(d)
	items = sorted(par_type.get("item", []), key=lambda d: d.get("_id", ""))
	recettes = sorted(par_type.get("recette", []), key=lambda d: d.get("_id", ""))
	lieux = par_type.get("lieu", [])

	items_par_id = {d["_id"]: d for d in items if d.get("_id")}
	sous_cats = {sc for d in items if (sc := characters.item_sous_categorie(d))}
	categories_lieu = {l.get("categorie") for l in lieux if l.get("categorie")}

	def apportee_par_le_joueur(cle: str) -> bool:
		"""Hypothèse A, 1re source : un objet du jeu entre dans le stock sous CETTE clé."""
		if str(cle).startswith("item:"):
			return cle in items_par_id
		return cle in sous_cats

	# Hypothèse A, 2e source : ce que le fournisseur livre de lui-même, toutes catégories
	# d'atelier existantes confondues.
	# ⚠️ Balayé par LIEU et non par catégorie : une feuille propre à une spécialité de terroir
	# (`lieu_portee`) n'apparaît que dans `appro_leaves_lieu` d'un atelier dans la portée. Vue
	# par catégorie seule, elle serait tenue pour non livrée et sa recette rapportée en
	# « chaîne rompue » alors qu'elle cuit très bien là où elle doit cuire.
	def auto_appro_de(lieu_doc: dict) -> set:
		return {c for c in marche.appro_leaves_lieu(lieu_doc)
				if marche._appro_debit_pour(c) > 0}

	auto_appro = set().union(set(), *(auto_appro_de(L) for L in lieux))

	toutes_cles = {cle for r in recettes for cle, _q in marche.recette_matieres(r)}
	sans_production = {c for c in toutes_cles if apportee_par_le_joueur(c) or c in auto_appro}

	# ── 1. Items sans recette atteignable ────────────────────────────────────────
	cuites_global, _acquis = point_fixe(marche, recettes, sans_production)
	produits_atteignables = {
		marche.objet_final_item_id(r.get("objet_final", ""))
		for r in recettes if r.get("_id") in cuites_global}
	vises_par_une_recette = {
		marche.objet_final_item_id(r.get("objet_final", "")) for r in recettes}

	sans_recette_atteignable = [d for d in items if d["_id"] not in produits_atteignables]
	chaine_rompue = [d for d in sans_recette_atteignable if d["_id"] in vises_par_une_recette]
	jamais_visee = len(sans_recette_atteignable) - len(chaine_rompue)

	# ── 2. Recettes dont le produit n'entre jamais en rayon ──────────────────────
	# Point fixe par ATELIER, amorcé par le SEUL approvisionnement automatique.
	#
	# ⚠️ Par atelier et non par catégorie, depuis la PORTÉE GÉOGRAPHIQUE (`lieu_portee`) :
	# une spécialité de terroir sort de l'index par catégorie (`marche.lieu_recettes`) et
	# n'est servie que par `marche.recettes_lieu`, qui a besoin du doc lieu. Auditée par
	# catégorie, elle serait rapportée « bloquée » alors qu'elle cuit très bien là où elle
	# doit cuire. On choisit un atelier REPRÉSENTATIF par (catégorie, portée) — le premier
	# par `_id`, pour que deux exécutions rendent le même rapport.
	def _atelier_de(r: dict):
		"""Le lieu par lequel cette recette peut être cuite, ou None si aucun ne le peut."""
		cat = r.get("lieu_categorie")
		portee = r.get("lieu_portee")
		candidats = [L for L in sorted(lieux, key=lambda d: d.get("_id") or "")
					 if cat in marche.categories_incluses(L.get("categorie") or "")
					 and (not portee or portee in marche.portees_lieu(L))]
		return candidats[0] if candidats else None

	point_fixe_atelier: dict[str, tuple] = {}   # lieu_id → (cuites, acquis)
	atelier_par_recette: dict[str, str] = {}
	for r in recettes:
		atelier = _atelier_de(r)
		if atelier is None:
			continue
		lieu_id = atelier["_id"]
		atelier_par_recette[r.get("_id")] = lieu_id
		if lieu_id not in point_fixe_atelier:
			amorce = {c for c in marche.appro_leaves_lieu(atelier)
					  if marche._appro_debit_pour(c) > 0}
			point_fixe_atelier[lieu_id] = point_fixe(
				marche, marche.recettes_lieu(atelier), amorce)

	blocages: dict[str, list] = {}
	cles_bloquantes: dict[str, int] = {}   # clé matière → nb de recettes qu'elle bloque
	for r in recettes:
		cat = r.get("lieu_categorie")
		produit = marche.objet_final_item_id(r.get("objet_final", ""))
		lieu_id = atelier_par_recette.get(r.get("_id"))
		cuites, acquis = point_fixe_atelier.get(lieu_id, (set(), set()))
		if not marche.recette_matieres(r):
			blocages.setdefault("sans intrant (le moteur ne la prépare jamais)", []).append(r)
		elif lieu_id is None:
			motif = (f"aucun lieu de catégorie « {cat} »" if not r.get("lieu_portee")
					 else f"aucun atelier « {cat} » sous la portée {r['lieu_portee']}")
			blocages.setdefault(motif, []).append(r)
		elif produit not in items_par_id:
			blocages.setdefault("produit sans doc item (ligne invisible en rayon)", []).append(r)
		elif r.get("_id") not in cuites:
			blocages.setdefault(MOTIF_INTRANTS, []).append(r)
			for cle, _q in marche.recette_matieres(r):
				if cle not in acquis:
					cles_bloquantes[cle] = cles_bloquantes.get(cle, 0) + 1
	bloquees = [r for lot in blocages.values() for r in lot]
	# Relâchement de l'hypothèse D : le joueur revend ce qu'il a acheté ailleurs. Ne restent
	# que les blocages structurels — pas d'atelier, pas de doc produit, chaîne globalement
	# rompue —, que le meilleur des ravitailleurs ne débloquerait pas.
	bloquees_structurelles = [
		r for r in bloquees
		if not marche.recette_matieres(r)
		or (atelier_par_recette.get(r.get("_id")) is None)
		or (marche.objet_final_item_id(r.get("objet_final", "")) not in items_par_id)
		or (r.get("_id") not in cuites_global)
	]

	# ── 3. Marge médiane d'un objet fabriqué ─────────────────────────────────────
	cout_par_produit: dict[str, float] = {}
	for r in recettes:
		if r.get("_id") not in cuites_global:
			continue
		produit = marche.objet_final_item_id(r.get("objet_final", ""))
		cout = sum(marche.cout_production_cuivre(marche.matiere_item_id(cle)) * q
				   for cle, q in marche.recette_matieres(r))
		cout /= max(1, int(r.get("quantite_produite", 1) or 1))
		if cout > 0 and cout < cout_par_produit.get(produit, float("inf")):
			cout_par_produit[produit] = cout

	marges = []
	for produit in sorted(cout_par_produit):
		doc = items_par_id.get(produit)
		if not doc:
			continue  # produit sans doc : invendable, donc hors marge (compté en §2)
		pmin, pmax = marche.prix_range_cuivre(doc, produit)
		prix = marche.prix_base_cuivre(pmin, pmax, character_stats.RELATION_INITIALE, "achat")
		cout = cout_par_produit[produit]
		marges.append(((prix - cout) / cout, produit, prix, cout))
	valeurs = [m for m, _p, _px, _c in marges]
	a_perte = [m for m in marges if m[0] < 0]

	# ── Sortie ───────────────────────────────────────────────────────────────────
	larg = 86
	print("═" * larg)
	print("AUDIT ÉCONOMIQUE TELLURIS")
	print("═" * larg)
	print(f"dump          : {meta.get('_chemin', '?')}")
	print(f"exporté le    : {meta.get('exported_at', '?')}   ({meta.get('doc_count', len(docs))} docs)")
	print(f"items {len(items):>4}   recettes {len(recettes):>4}   lieux {len(lieux):>3}"
		  f"   catégories d'atelier {len(categories_lieu):>3}")
	print(f"tunables      : MARGE_TRANSFO={character_stats.MARGE_TRANSFO} "
		  f"PRIX_MAX_FACTEUR={character_stats.PRIX_MAX_FACTEUR} "
		  f"PRIX_DERIVE_BASE={character_stats.PRIX_DERIVE_BASE} "
		  f"RELATION_INITIALE={character_stats.RELATION_INITIALE}")
	print()

	print("─" * larg)
	print(f"1. ITEMS SANS RECETTE ATTEIGNABLE            {_pct(len(sans_recette_atteignable), len(items))}"
		  f"   ({len(sans_recette_atteignable)} / {len(items)})")
	print("─" * larg)
	print(f"   · aucune recette ne les vise               {_pct(jamais_visee, len(items))}"
		  f"   ({jamais_visee})   ← butin, carcasses, objets remis")
	print(f"   · visés mais chaîne rompue                 {_pct(len(chaine_rompue), len(items))}"
		  f"   ({len(chaine_rompue)})   ← DÉFAUT")
	for d in chaine_rompue[:6]:
		manquantes = sorted({
			cle
			for r in recettes
			if marche.objet_final_item_id(r.get("objet_final", "")) == d["_id"]
			for cle, _q in marche.recette_matieres(r)
			if cle not in _acquis
		})
		print(f"       {d['_id']:<44} manque : {', '.join(manquantes[:3]) or '(recette sans intrant)'}")
	if len(chaine_rompue) > 6:
		print(f"       … et {len(chaine_rompue) - 6} autres")
	print()

	print("─" * larg)
	print(f"2. RECETTES DONT LE PRODUIT N'ENTRE JAMAIS EN RAYON   {_pct(len(bloquees), len(recettes))}"
		  f"   ({len(bloquees)} / {len(recettes)})")
	print("─" * larg)
	for motif, lot in sorted(blocages.items(), key=lambda kv: (-len(kv[1]), kv[0])):
		print(f"   · {motif:<52} {_pct(len(lot), len(recettes))}   ({len(lot)})")
		exemples = sorted({r.get("objet_final", "?") for r in lot})[:4]
		print(f"       ex. {', '.join(exemples)}")
		if motif == MOTIF_INTRANTS and cles_bloquantes:
			top = sorted(cles_bloquantes.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
			print("       matières manquantes : "
				  + ", ".join(f"{cle} ({n})" for cle, n in top))
	print(f"   dont bloquées MÊME en supposant le joueur ravitailleur : "
		  f"{_pct(len(bloquees_structurelles), len(recettes))} ({len(bloquees_structurelles)})")
	print()

	print("─" * larg)
	mediane = _mediane(valeurs)
	print(f"3. MARGE MÉDIANE D'UN OBJET FABRIQUÉ          {mediane * 100:+7.1f} %"
		  f"   (×{1 + mediane:.2f} sur {len(marges)} objets)")
	print("─" * larg)
	if valeurs:
		print(f"   · 1er quartile {_quantile(valeurs, 0.25) * 100:+8.1f} %"
			  f"      3e quartile {_quantile(valeurs, 0.75) * 100:+8.1f} %")
		print(f"   · min          {min(valeurs) * 100:+8.1f} %"
			  f"      max         {max(valeurs) * 100:+8.1f} %")
		print(f"   · fabriqués À PERTE (marge < 0)            {_pct(len(a_perte), len(marges))}"
			  f"   ({len(a_perte)})")
		print("   · les 6 marges les plus basses :")
		for _m, produit, prix, cout in sorted(marges)[:6]:
			print(f"       {produit:<44} vendu {prix:>7} cu / revient {cout:>9.1f} cu"
				  f"   {_m * 100:+7.1f} %")
	print()
	print("─" * larg)
	print("Hypothèses de référence : cf. docstring en tête de ce fichier (A à F).")
	print("─" * larg)


def main(argv: list) -> int:
	args = [a for a in argv[1:] if a != "--dump"]
	if "--dernier" in args:
		candidats = dumps_disponibles()
		if not candidats:
			print("`--dernier` : aucun telluris-dump-*.json trouvé (racine ou jsons/).",
				  file=sys.stderr)
			return 2
		chemin = candidats[0]
	elif args:
		chemin = args[0]
	else:
		chemin = demander_dump()
	if not chemin:
		print("Aucun dump indiqué — rien à auditer.", file=sys.stderr)
		return 2
	try:
		docs, meta = charger_dump(chemin)
	except OSError as e:
		print(f"Dump illisible : {e}", file=sys.stderr)
		return 2
	meta["_chemin"] = chemin
	auditer(docs, meta)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv))
