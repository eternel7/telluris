#!/usr/bin/env python
# dev/gen_analyse_armes_armures.py
"""Analyse des armes et armures : valorisation, répartition, caractéristiques, bonus et
restrictions — ce que la donnée dit de l'équilibrage. LECTURE SEULE (aucun import produit).

	python dev/gen_analyse_armes_armures.py [--dump jsons/telluris-dump-….json | --dernier]
	                                        [--variantes] [--top N] [--csv chemin.csv]

Sections du rapport :
  1. **Répartition** — familles (mêlée 1 main / 2 mains, hast, jet, tir, instrument,
     bouclier, une famille par zone du corps, bijou, harnachement) × rareté.
  2. **Distribution des champs** — min / médiane / max et taux de présence de chaque
     bonus, par famille.
  3. **Valorisation** — prix (`marche.prix_range_cuivre`, celui du jeu) contre puissance :
     corrélation de rang (Spearman) prix↔puissance et prix↔poids, source du prix, écarts
     au ratio cu/puissance médian de la famille.
  4. **Rareté** — puissance médiane par palier, inversions, pièces hors de leur palier.
  5. **Restrictions** — inertes (toute race les remplit à la création), inaccessibles à
     certaines races, caractéristique incohérente avec la famille, pièces fortes sans
     restriction et faibles mais restreintes.
  6. **Incohérences de champs** — règles du moteur que la donnée contredit (effets inertes,
     portée/tags, deux mains, armure sans PA, clés inconnues…).
  7. **Couverture** — familles × rareté : les trous de la gamme.

────────────────────────────────────────────────────────────────────────────────────────
HYPOTHÈSES
────────────────────────────────────────────────────────────────────────────────────────
A. **Le moteur est celui du jeu.** `db.config` est rebranché sur le dump AVANT l'import de
   `utils.marche` (même branchement que `dev/audit_economy.py`) et les variables de monde
   sont celles du dump : le prix est exactement celui que le marché affiche (pmin =
   coût de revient : `valeur` explicite, sinon recette × `MARGE_TRANSFO`, sinon poids ×
   `MULT_RARETE` × `PRIX_DERIVE_BASE`).

B. **Puissance = « équivalent dégâts » (EqD) par attaque/coup reçu**, somme pondérée des
   bonus, lue comme le moteur les lit (`characters.recompute_equipment_bonus`,
   `compute_derived_stats`) :
     · dégâts : `bonus_degats` + espérance du dé (`bonus_degats_dice` = nombre de faces) ;
     · armure : `bonus_pa` × probabilité que la zone couverte soit touchée
       (`LOCALISATION_TOUCHES` du dump ; bouclier, cou, ceinture, anneaux = partout) ;
     · toucher (`bonus_cc` / `bonus_cd`), initiative, PV, PM, caractéristiques (`bonus`,
       `bonus_malus_depl` = delta de V), effets PORTÉS (`regen_*`, `esquive`,
       `canalisation`), débuffs d'ARME (part durative, plafonnée), portée.
   Les poids sont dans `POIDS` / `POIDS_CARAC`, dérivés des formules des dérivées (ex. +1 F
   = +F//20 de dégâts, +¼ % de cc, +1 PV) ; ils sont DÉCLARÉS, pas mesurés : la puissance
   classe les pièces d'une MÊME famille, elle ne compare pas une épée à un casque. Les
   écarts signalés sont toujours relatifs à la médiane de la famille.

C. **Deux mains** : la puissance n'inclut pas le coût de la main gauche perdue ; la
   section 3 rapporte à part la « prime deux mains » (médiane 2 mains − médiane 1 main),
   à comparer à la puissance médiane d'un bouclier.

D. **Variantes sur mesure** (`fabrication.base_item`) exclues par défaut : elles héritent
   de leur base et leur prix est déjà contrôlé par `audit_economy.py` §7 (`--variantes`
   pour les inclure).

F. **Harnachement** hors estimation : il vaut par la charge portée par la monture
   (`monture.charge_pct`), que la puissance ne mesure pas.

E. **Restriction inerte** = seuil ≤ la valeur de DÉPART de cette caractéristique pour
   TOUTES les races (`rules:races`.stats) : elle ne bloque personne, jamais. **Inaccessible**
   = seuil > `stats_max` + `max_bonus` d'une race (le dépassement du max racial compris).
"""

import argparse
import csv
import math
import os
import statistics
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import audit_economy  # noqa: E402  (branchement du moteur sur le dump)

CATEGORIES = ("arme", "armure")
CARACS = ("F", "R", "Ag", "V", "Vol", "Int", "Cha", "Ch")
RARETES = ("commun", "peu_commun", "rare", "tres_rare", "legendaire", "mythique", "divin")

# ── Pondérations de la puissance (hypothèse B) ─────────────────────────────────────
# Unité : 1 point de dégât espéré sur un coup.
POIDS = {
	"degats": 1.0,         # +1 dégât plat / espérance du dé
	"toucher": 0.2,        # +1 % de cc/cd ≈ 1/50 d'un coup de ~10 dégâts
	"pa": 1.0,             # 1 PA retranché d'un coup reçu sur la zone couverte
	"initiative": 0.05,
	"pv": 0.1,             # 1 PV sur un réservoir de ~60-150
	"pm": 0.1,
	"regen_pv": 1.0,       # par tour
	"regen_pm": 0.8,
	"esquive": 0.2,        # malus au seuil de toucher adverse (%)
	"canalisation": 0.03,  # % retranché à la pénalité de charge magique
	"portee_tir": 0.3,     # case de portée au-delà de 1 (tir/jet)
	"allonge": 1.0,        # case d'allonge au-delà de 1 (toute mêlée) : frappe avant d'être frappé
	"debuff": 0.5,         # part d'un débuff d'arme : × poids carac × durée plafonnée
}
DEBUFF_DUREE_PLAFOND = 3
# +1 point de caractéristique, déroulé sur les dérivées (compute_derived_stats, FACTEUR 20).
POIDS_CARAC = {
	"F": 0.2,     # F//20 dégâts cac + ¼ % cc + 1 PV + charge
	"R": 0.4,     # 3 PV + R//20 PA
	"Ag": 0.25,   # ¾ % cc et cd + Ag//20 dégâts tir + initiative
	"V": 2.0,     # +1 case de déplacement, +6 initiative, +2,5 % cd
	"Vol": 0.3,   # 2 PM + défense magique + toucher magique
	"Int": 0.35,  # 2 PM + ¾ du toucher magique
	"Cha": 0.05,  # marchandage, PNJ — hors combat
	"Ch": 0.1,    # fenêtres de critique
}

# Caractéristique attendue en restriction, par famille (cohérence, section 5).
RESTRICTION_ATTENDUE = {
	"mêlée 1 main": {"F", "Ag"}, "mêlée 2 mains": {"F"}, "hast": {"F", "Ag"},
	"jet": {"F", "Ag"}, "tir": {"Ag", "F"}, "instrument": {"Cha", "Vol", "Int"},
	"bouclier": {"F", "R"}, "bijou": {"Int", "Vol", "Cha"},
}
SEUIL_RATIO_PRIX = 4.0   # ratio cu/puissance hors de [médiane/4, médiane×4] ⇒ signalé
# Barème `bonus_pa = round(poids × facteur)` de dev/gen_armures.py (copie déclarée) : tissu 0,8
# → plates 2,1, bouclier 2,3. Une pièce hors de [0,8 ; 2,3] × poids (±1 d'arrondi) le contredit.
BAREME_PA_MIN, BAREME_PA_MAX = 0.8, 2.3
# Malus de vitesse d'une armure selon son poids MINIMAL (décision du 10/10/2026).
MALUS_V_KG, MALUS_V_LOURD_KG = 14, 20


# ── Lecture des items ────────────────────────────────────────────────────────────────

def est_variante(doc: dict) -> bool:
	bloc = doc.get("fabrication")
	return isinstance(bloc, dict) and bool(bloc.get("base_item"))


def tags_de(doc: dict) -> set:
	return {str(t) for t in (doc.get("tags") or [])}


def famille(doc: dict) -> str:
	"""Famille de comparaison : on ne compare une pièce qu'à ses pareilles."""
	slots = set(doc.get("slots") or [])
	sc = str(doc.get("sous_categorie") or "")
	tags = tags_de(doc)
	if any(s.startswith("monture_") for s in slots):
		return "harnachement"
	if doc.get("categorie") == "arme":
		if sc == "instrument":
			return "instrument"
		if "tir" in tags or sc in ("arc", "arbalete"):
			return "tir"
		if "jet" in tags:
			return "jet"
		if "hast" in tags:
			return "hast"
		return "mêlée 2 mains" if doc.get("deux_mains") else "mêlée 1 main"
	if sc == "bouclier" or (slots == {"main_gauche"} and sc != "insigne"):
		return "bouclier"
	if sc == "bijou" or slots & {"cou", "anneau_1", "anneau_2"}:
		return "bijou"
	if sc == "instrument":
		return "instrument"
	for s in ("torse", "tete", "epaules", "mains", "jambes", "pieds", "ceinture"):
		if s in slots:
			return "armure · " + s
	return "armure · autre"


def esperance_des(raw, character_stats) -> float:
	"""Espérance d'une notation de dés normalisée par le moteur ("1D6", "2D4+1D6", "+2")."""
	s = character_stats.normalize_dice(raw)
	total = 0.0
	for terme in filter(None, s.replace("-", "+-").split("+")):
		if "D" in terme:
			n, f = terme.split("D", 1)
			try:
				total += (int(n or 1)) * (int(f) + 1) / 2
			except ValueError:
				pass
		else:
			try:
				total += int(terme)
			except ValueError:
				pass
	return total


def proba_zones(character_stats) -> dict:
	"""Probabilité d'être touché par zone, depuis les bornes hautes cumulées."""
	bornes = sorted(((int(v), z) for z, v in character_stats.LOCALISATION_TOUCHES.items()))
	out, prec = {}, 0
	for borne, zone in bornes:
		out[zone] = max(0, borne - prec) / 100.0
		prec = borne
	return out


def _num(v) -> float:
	try:
		return float(v or 0)
	except (TypeError, ValueError):
		return 0.0


def poids_min(doc: dict) -> float:
	p = doc.get("poids")
	if isinstance(p, (list, tuple)):
		return _num(p[0]) if p else 0.0
	return _num(p)


def poids_moyen(doc: dict) -> float:
	"""Milieu de la fourchette : chaque exemplaire tire son poids dedans (`tirer_poids`)."""
	p = doc.get("poids")
	if isinstance(p, (list, tuple)) and p:
		return (_num(p[0]) + _num(p[-1])) / 2
	return _num(p)


def puissance(doc: dict, fam: str, zones: dict, characters, character_stats) -> dict:
	"""Composantes de la puissance (hypothèse B) ; `total` = leur somme."""
	c = {}
	c["degats"] = (_num(doc.get("bonus_degats"))
				   + esperance_des(doc.get("bonus_degats_dice"), character_stats)) * POIDS["degats"]
	cc, cd = _num(doc.get("bonus_cc")), _num(doc.get("bonus_cd"))
	if fam in ("tir", "jet"):
		c["toucher"] = cd * POIDS["toucher"]
	elif doc.get("categorie") == "arme":
		c["toucher"] = cc * POIDS["toucher"]
	else:
		c["toucher"] = (cc + cd) / 2 * POIDS["toucher"]
	# PA : la zone de la pièce, ou partout si aucun de ses slots n'en couvre une.
	pzone = 1.0
	for s in doc.get("slots") or []:
		z = characters.SLOT_ZONE.get(str(s))
		if z:
			pzone = zones.get(z, 0.0)
			break
	c["armure"] = _num(doc.get("bonus_pa")) * pzone * POIDS["pa"]
	c["divers"] = (_num(doc.get("bonus_initiative")) * POIDS["initiative"]
				   + _num(doc.get("bonus_pv")) * POIDS["pv"]
				   + _num(doc.get("bonus_pm")) * POIDS["pm"])
	car = 0.0
	for k, v in (doc.get("bonus") or {}).items():
		car += _num(v) * POIDS_CARAC.get(str(k), 0.0)
	car += _num(doc.get("bonus_malus_depl")) * POIDS_CARAC["V"]
	c["caracs"] = car
	eff = doc.get("effets") if isinstance(doc.get("effets"), dict) else {}
	# Arme SANS `duree` : son bloc se lit comme celui d'une pièce portée
	# (`characters.arme_effets_portes`) — la baguette qui régénère son porteur.
	if doc.get("categorie") == "arme" and _num(eff.get("duree")) > 0:
		duree = min(DEBUFF_DUREE_PLAFOND, _num(eff.get("duree")) or 1)
		somme = sum(abs(_num(v)) * POIDS_CARAC.get(str(k), 0.0)
					for k, v in (eff.get("buffs") or {}).items())
		c["effets"] = somme * duree * POIDS["debuff"]
	else:
		c["effets"] = sum(_num(eff.get(k)) * POIDS[k]
						  for k in ("regen_pv", "regen_pm", "esquive", "canalisation"))
	portee = _num(doc.get("portee")) or 1
	if fam in ("tir", "jet"):
		c["portee"] = (portee - 1) * POIDS["portee_tir"]
	elif fam in ("hast", "mêlée 1 main", "mêlée 2 mains"):
		# L'allonge vaut quel que soit le fût : le moteur lit `portee`, jamais le tag `hast`
		# (fouet, chaîne, kusarigama frappent à 2 cases sans être des armes d'hast).
		c["portee"] = (portee - 1) * POIDS["allonge"]
	else:
		c["portee"] = 0.0
	c["total"] = round(sum(c.values()), 2)
	return c


# ── Statistiques ─────────────────────────────────────────────────────────────────────

def rangs(valeurs: list) -> list:
	ordre = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
	r = [0.0] * len(valeurs)
	i = 0
	while i < len(ordre):
		j = i
		while j + 1 < len(ordre) and valeurs[ordre[j + 1]] == valeurs[ordre[i]]:
			j += 1
		moy = (i + j) / 2 + 1
		for k in range(i, j + 1):
			r[ordre[k]] = moy
		i = j + 1
	return r


def spearman(xs: list, ys: list):
	if len(xs) < 4:
		return None
	rx, ry = rangs(xs), rangs(ys)
	mx, my = statistics.fmean(rx), statistics.fmean(ry)
	num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
	den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
	return None if den == 0 else num / den


def fmt_rho(r) -> str:
	return "  n/a" if r is None else f"{r:+.2f}"


def med(xs):
	return statistics.median(xs) if xs else 0


def titre(t: str):
	print()
	print("═" * 96)
	print(t)
	print("═" * 96)


# ── Analyse ──────────────────────────────────────────────────────────────────────────

def analyser(docs: list, meta: dict, avec_variantes: bool, top: int, chemin_csv: str | None):
	character_stats, characters, marche = audit_economy.brancher_moteur(docs)
	index = {d.get("_id"): d for d in docs if isinstance(d, dict)}
	zones = proba_zones(character_stats)
	recettes = marche._get_recipe_map()

	tous = sorted((d for d in docs if isinstance(d, dict) and d.get("type") == "item"
				   and str(d.get("_id", "")).startswith("item:")
				   and d.get("categorie") in CATEGORIES), key=lambda d: d["_id"])
	variantes = [d for d in tous if est_variante(d)]
	items = tous if avec_variantes else [d for d in tous if not est_variante(d)]
	# Le harnachement vaut par la charge qu'il fait porter à la monture, que la puissance
	# ne mesure pas : hors de l'estimation (décision du 10/10).
	harnachement = [d for d in items if famille(d) == "harnachement"]
	items = [d for d in items if famille(d) != "harnachement"]

	races = (index.get("rules:races") or {}).get("value") or []

	lignes = []
	for d in items:
		fam = famille(d)
		p = puissance(d, fam, zones, characters, character_stats)
		pmin, pmax = marche.prix_range_cuivre(d, d["_id"])
		if d.get("valeur") is not None:
			source = "valeur"
		elif d["_id"] in recettes and marche.cout_production_cuivre(d["_id"], d) > \
				characters.item_sale_price_cuivre(d, d["_id"]):
			source = "recette"
		else:
			source = "poids×rareté"
		lignes.append({"doc": d, "id": d["_id"], "fam": fam, "p": p, "pmin": pmin,
					   "pmax": pmax, "source": source, "poids": poids_min(d),
					   "rarete": str(d.get("rarete") or "?")})

	par_fam: dict[str, list] = {}
	for l in lignes:
		par_fam.setdefault(l["fam"], []).append(l)
	familles = sorted(par_fam, key=lambda f: (-len(par_fam[f]), f))

	print("Analyse des armes et armures")
	print(f"Dump : {meta.get('_chemin')} (exporté {meta.get('exported_at', '?')})")
	print(f"{len(lignes)} pièces analysées ({sum(1 for l in lignes if l['doc'].get('categorie') == 'arme')} armes, "
		  f"{sum(1 for l in lignes if l['doc'].get('categorie') == 'armure')} armures) — "
		  f"{len(variantes)} variantes sur mesure "
		  f"{'incluses' if avec_variantes else 'exclues (--variantes pour les inclure)'}, "
		  f"{len(harnachement)} pièces de harnachement hors estimation.")
	print("Puissance en « équivalent dégâts » (EqD) — pondérations déclarées en tête du script, "
		  "comparables DANS une famille seulement.")
	print("Probabilité de toucher par zone : "
		  + ", ".join(f"{z} {p:.0%}" for z, p in zones.items()))

	# ── 1. Répartition ──
	titre("1. RÉPARTITION — familles × rareté")
	rar_vues = [r for r in RARETES if any(l["rarete"] == r for l in lignes)]
	autres = sorted({l["rarete"] for l in lignes} - set(RARETES))
	cols = rar_vues + autres
	print(f"{'famille':<22}{'n':>4}  " + "".join(f"{c[:9]:>10}" for c in cols)
		  + f"{'restr.':>8}{'P méd':>8}{'cu méd':>9}")
	for f in familles:
		ls = par_fam[f]
		cpt = {c: sum(1 for l in ls if l["rarete"] == c) for c in cols}
		restr = sum(1 for l in ls if l["doc"].get("restriction"))
		print(f"{f:<22}{len(ls):>4}  " + "".join(f"{cpt[c] or '·':>10}" for c in cols)
			  + f"{restr / len(ls):>8.0%}{med([l['p']['total'] for l in ls]):>8.1f}"
			  + f"{med([l['pmin'] for l in ls]):>9.0f}")

	# ── 2. Distribution des champs ──
	titre("2. DISTRIBUTION DES CHAMPS — présence %, min / médiane / max (sur les pièces qui l'ont)")
	champs = ["bonus_degats", "bonus_degats_dice", "bonus_cc", "bonus_cd", "bonus_pa",
			  "bonus_malus_depl", "bonus_initiative", "bonus_pv", "bonus_pm", "portee", "poids"]
	for f in familles:
		ls = par_fam[f]
		print(f"\n▸ {f} ({len(ls)})")
		for ch in champs:
			vals = [poids_min(l["doc"]) if ch == "poids" else _num(l["doc"].get(ch)) for l in ls]
			nz = [v for v in vals if v]
			if not nz:
				continue
			print(f"   {ch:<19}{len(nz) / len(ls):>5.0%}   {min(nz):>6g} / {med(nz):>6g} / {max(nz):>6g}")
		carac_vals: dict[str, list] = {}
		for l in ls:
			for k, v in (l["doc"].get("bonus") or {}).items():
				carac_vals.setdefault(str(k), []).append(_num(v))
		for k in sorted(carac_vals):
			v = carac_vals[k]
			print(f"   bonus.{k:<13}{len(v) / len(ls):>5.0%}   {min(v):>6g} / {med(v):>6g} / {max(v):>6g}")

	# ── 3. Valorisation ──
	titre("3. VALORISATION — le prix suit-il la puissance ?")
	print(f"{'famille':<22}{'n':>4}{'ρ prix↔P':>10}{'ρ prix↔poids':>14}{'ρ P↔poids':>11}"
		  f"   source du prix (valeur / recette / poids×rareté)")
	for f in familles:
		ls = par_fam[f]
		P = [l["p"]["total"] for l in ls]
		C = [l["pmin"] for l in ls]
		W = [l["poids"] for l in ls]
		src = {s: sum(1 for l in ls if l["source"] == s) for s in ("valeur", "recette", "poids×rareté")}
		print(f"{f:<22}{len(ls):>4}{fmt_rho(spearman(C, P)):>10}{fmt_rho(spearman(C, W)):>14}"
			  f"{fmt_rho(spearman(P, W)):>11}   {src['valeur']} / {src['recette']} / {src['poids×rareté']}")
	print("\nρ = corrélation de rang (Spearman, −1…+1). Un ρ prix↔poids > ρ prix↔puissance : "
		  "le marché paie le POIDS, pas l'efficacité.")

	m1 = med([l["p"]["total"] for l in par_fam.get("mêlée 1 main", [])])
	m2 = med([l["p"]["total"] for l in par_fam.get("mêlée 2 mains", [])])
	mb = med([l["p"]["total"] for l in par_fam.get("bouclier", [])])
	if par_fam.get("mêlée 1 main") and par_fam.get("mêlée 2 mains"):
		d1 = med([l["p"]["degats"] for l in par_fam["mêlée 1 main"]])
		d2 = med([l["p"]["degats"] for l in par_fam["mêlée 2 mains"]])
		print(f"\nDégâts espérés médians : 1 main {d1:.1f} · 2 mains {d2:.1f} (avant malus de V et toucher).")
		print(f"\nPrime deux mains : médiane 2 mains {m2:.1f} − 1 main {m1:.1f} = {m2 - m1:+.1f} EqD ; "
			  f"bouclier médian {mb:.1f} EqD — "
			  + ("la prime COUVRE le bouclier abandonné." if m2 - m1 >= mb
				 else "la prime NE COUVRE PAS le bouclier abandonné (1 main + bouclier domine)."))

	ecarts_haut, ecarts_bas, sans_puissance = [], [], []
	for f in familles:
		ls = [l for l in par_fam[f] if l["p"]["total"] > 0]
		if len(ls) < 4:
			continue
		ratios = [l["pmin"] / l["p"]["total"] for l in ls]
		mr = med(ratios)
		for l, r in zip(ls, ratios):
			if mr and r > mr * SEUIL_RATIO_PRIX:
				ecarts_haut.append((r / mr, l, mr))
			elif mr and r < mr / SEUIL_RATIO_PRIX:
				ecarts_bas.append((mr / r, l, mr))
	for l in lignes:
		if l["p"]["total"] <= 0:
			sans_puissance.append(l)

	def ligne_prix(k, l, mr):
		return (f"   ×{k:5.1f}  {l['id']:<40}{l['fam']:<20}{l['rarete']:<11}"
				f"P {l['p']['total']:>6.1f}  {l['pmin']:>6} cu ({l['source']}, {l['poids']:g} kg)"
				f"  — attendu ≈ {mr * l['p']['total']:.0f} cu")
	print(f"\nTROP CHÈRES pour leur puissance (ratio cu/P > ×{SEUIL_RATIO_PRIX:g} la médiane de la famille) "
		  f"— {len(ecarts_haut)} :")
	for k, l, mr in sorted(ecarts_haut, key=lambda t: -t[0])[:top]:
		print(ligne_prix(k, l, mr))
	print(f"\nBRADÉES pour leur puissance (ratio < médiane ÷{SEUIL_RATIO_PRIX:g}) — {len(ecarts_bas)} :")
	for k, l, mr in sorted(ecarts_bas, key=lambda t: -t[0])[:top]:
		print(ligne_prix(k, l, mr))
	print(f"\nPUISSANCE NULLE OU NÉGATIVE (rien ne justifie l'équipement) "
		  f"— {len(sans_puissance)} :")
	for l in sorted(sans_puissance, key=lambda l: l["p"]["total"])[:top * 2]:
		print(f"   {l['id']:<40}{l['fam']:<20}{l['rarete']:<11}P {l['p']['total']:>6.1f}  {l['pmin']:>6} cu")

	# ── 4. Rareté ──
	titre("4. RARETÉ — la puissance monte-t-elle avec le palier ?")
	inversions, hors_palier = [], []
	for f in familles:
		ls = par_fam[f]
		paliers = [r for r in RARETES if any(l["rarete"] == r for l in ls)]
		meds = {r: med([l["p"]["total"] for l in ls if l["rarete"] == r]) for r in paliers}
		print(f"{f:<22}" + "   ".join(f"{r} {meds[r]:.1f} ({sum(1 for l in ls if l['rarete'] == r)})"
									   for r in paliers))
		for a, b in zip(paliers, paliers[1:]):
			if meds[b] < meds[a]:
				inversions.append(f"{f} : {b} ({meds[b]:.1f}) < {a} ({meds[a]:.1f})")
		# Hors palier = plus fort que TOUTES les pièces du palier au-dessus, ou plus faible que
		# TOUTES celles du palier en dessous (une médiane sur 2 pièces serait du bruit).
		extremes = {r: [l["p"]["total"] for l in ls if l["rarete"] == r] for r in paliers}
		for l in ls:
			if l["rarete"] not in paliers:
				continue
			i = paliers.index(l["rarete"])
			if i + 1 < len(paliers) and l["p"]["total"] > max(extremes[paliers[i + 1]]):
				hors_palier.append((f, l, f"plus fort que toutes les {paliers[i + 1]} "
										  f"(max {max(extremes[paliers[i + 1]]):.1f})"))
			elif i > 0 and l["p"]["total"] < min(extremes[paliers[i - 1]]):
				hors_palier.append((f, l, f"plus faible que toutes les {paliers[i - 1]} "
										  f"(min {min(extremes[paliers[i - 1]]):.1f})"))
	print(f"\nInversions de médiane — {len(inversions)} :")
	for t in inversions:
		print("   " + t)
	print(f"\nPièces hors de leur palier — {len(hors_palier)} :")
	for f, l, raison in hors_palier[:top * 2]:
		print(f"   {l['id']:<40}{f:<20}{l['rarete']:<11}P {l['p']['total']:>6.1f}  {raison}")

	# ── 5. Restrictions ──
	titre("5. RESTRICTIONS — bloquent-elles quelqu'un, et la bonne caractéristique ?")
	depart_min = {c: min((_num((r.get("stats") or {}).get(c)) for r in races), default=0) for c in CARACS}
	plafonds = {r.get("id"): {c: _num((r.get("stats_max") or {}).get(c)) + _num((r.get("max_bonus") or {}).get(c))
							  for c in CARACS} for r in races}
	print("Valeur de départ minimale toutes races : "
		  + ", ".join(f"{c} {v:g}" for c, v in depart_min.items()))
	inertes, inaccessibles, incoherentes, inconnues = [], [], [], []
	for l in lignes:
		r = l["doc"].get("restriction")
		if not r:
			continue
		if not isinstance(r, dict):
			inconnues.append((l, f"restriction illisible : {r!r}"))
			continue
		toutes_inertes = True
		for c, v in r.items():
			if c not in CARACS:
				inconnues.append((l, f"caractéristique inconnue « {c} »"))
				continue
			if _num(v) > depart_min[c]:
				toutes_inertes = False
			exclues = [rid for rid, pl in plafonds.items() if _num(v) > pl.get(c, 0)]
			if exclues:
				inaccessibles.append((l, f"{c} {v:g} > max de : {', '.join(exclues)}"))
		if toutes_inertes:
			inertes.append(l)
		att = RESTRICTION_ATTENDUE.get(l["fam"])
		if att and not (set(r) & att):
			incoherentes.append((l, f"{dict(r)} — attendu l'une de {sorted(att)}"))
	n_restr = sum(1 for l in lignes if l["doc"].get("restriction"))
	print(f"\n{n_restr} pièces restreintes sur {len(lignes)}.")
	print(f"INERTES (seuil ≤ départ de toute race : ne bloquent jamais personne) — {len(inertes)} "
		  f"({len(inertes) / max(1, n_restr):.0%} des restrictions) :")
	print("   " + ", ".join(l["id"][5:] for l in inertes[: top * 4])
		  + (" …" if len(inertes) > top * 4 else ""))
	print(f"\nINACCESSIBLES à certaines races — {len(inaccessibles)} :")
	for l, t in inaccessibles[:top * 2]:
		print(f"   {l['id']:<40}{l['fam']:<20}{t}")
	print(f"\nCARACTÉRISTIQUE INATTENDUE pour la famille — {len(incoherentes)} :")
	for l, t in incoherentes[:top * 2]:
		print(f"   {l['id']:<40}{l['fam']:<20}{t}")
	for l, t in inconnues:
		print(f"   ⚠ {l['id']:<38}{t}")

	print(f"\n{'famille':<22}{'ρ seuil↔P':>10}   fortes sans restriction (≥ Q3) · faibles restreintes (≤ Q1)")
	fortes_libres, faibles_restr = [], []
	for f in familles:
		ls = par_fam[f]
		if len(ls) < 4:
			continue
		P = sorted(l["p"]["total"] for l in ls)
		q1, q3 = P[len(P) // 4], P[(3 * len(P)) // 4]
		avec = [l for l in ls if isinstance(l["doc"].get("restriction"), dict) and l["doc"]["restriction"]]
		rho = spearman([max(_num(v) for v in l["doc"]["restriction"].values()) for l in avec],
					   [l["p"]["total"] for l in avec]) if len(avec) >= 4 else None
		fl = [l for l in ls if l["p"]["total"] >= q3 and q3 > 0 and not l["doc"].get("restriction")]
		fr = [l for l in avec if l["p"]["total"] <= q1
			  and max(_num(v) - depart_min.get(c, 0) for c, v in l["doc"]["restriction"].items()) > 0]
		fortes_libres += fl
		faibles_restr += fr
		print(f"{f:<22}{fmt_rho(rho):>10}   {len(fl):>3} · {len(fr):>3}")
	print(f"\nFortes sans aucune restriction — {len(fortes_libres)} :")
	for l in sorted(fortes_libres, key=lambda l: -l["p"]["total"])[:top]:
		print(f"   {l['id']:<40}{l['fam']:<20}{l['rarete']:<11}P {l['p']['total']:>6.1f}")
	print(f"\nFaibles mais réellement restreintes — {len(faibles_restr)} :")
	for l in sorted(faibles_restr, key=lambda l: l["p"]["total"])[:top]:
		print(f"   {l['id']:<40}{l['fam']:<20}{l['rarete']:<11}P {l['p']['total']:>6.1f}  {l['doc']['restriction']}")

	# ── 6. Incohérences de champs ──
	titre("6. INCOHÉRENCES DE CHAMPS — ce que le moteur lit autrement que la donnée ne le croit")
	regles: dict[str, list] = {}

	def signaler(regle, l, detail=""):
		regles.setdefault(regle, []).append(f"{l['id']}{(' — ' + detail) if detail else ''}")

	cles_bonus = {"bonus_degats", "bonus_degats_dice", "bonus_cc", "bonus_cd", "bonus_pa",
				  "bonus_malus_depl", "bonus_initiative", "bonus_pv", "bonus_pm"}
	for l in lignes:
		d, fam, tags = l["doc"], l["fam"], tags_de(l["doc"])
		slots = list(d.get("slots") or [])
		eff = d.get("effets") if isinstance(d.get("effets"), dict) else {}
		portee = _num(d.get("portee"))
		if not slots:
			signaler("aucun slot (inéquipable)", l)
		if poids_min(d) <= 0:
			signaler("poids nul ou absent", l)
		if not d.get("rarete") or l["rarete"] not in RARETES:
			signaler("rareté absente ou hors échelle", l, l["rarete"])
		for k in (d.get("bonus") or {}):
			if k not in CARACS:
				signaler("clé de `bonus` inconnue (ignorée par le moteur)", l, str(k))
		for k in ("pv", "pm"):
			if eff.get(k):
				signaler("`effets.pv/pm` sur une pièce d'équipement : INERTE "
						 "(porté : seuls regen_*/esquive/canalisation ; arme : part durative)", l, f"{k}={eff[k]}")
		if d.get("categorie") == "arme":
			buffs = eff.get("buffs") or {}
			cible = str(d.get("cible") or "ennemi")
			if cible == "ennemi" and any(_num(v) > 0 for v in buffs.values()):
				signaler("arme : buff POSITIF posé sur l'ennemi", l, str(buffs))
			if cible == "soi" and any(_num(v) < 0 for v in buffs.values()):
				signaler("arme : débuff posé sur soi", l, str(buffs))
			if buffs and not eff.get("duree"):
				signaler("arme : buffs sans `duree` (lus nulle part)", l)
			if eff.get("duree"):
				for k in ("regen_pv", "regen_pm", "esquive", "canalisation"):
					if _num(eff.get(k)) > 0:
						signaler("arme à `duree` : régén/esquive POSITIVE posée sur la cible", l, k)
			if fam != "instrument" and not d.get("bonus_degats_dice") and not d.get("bonus_degats"):
				signaler("arme sans dé ni bonus de dégâts", l)
			if fam in ("tir", "jet") and _num(d.get("bonus_cc")):
				signaler("arme de tir/jet avec `bonus_cc` (le tir lit `bonus_cd`)", l, f"cc={d['bonus_cc']}")
			if fam in ("mêlée 1 main", "mêlée 2 mains", "hast") and _num(d.get("bonus_cd")):
				signaler("arme de mêlée avec `bonus_cd`", l, f"cd={d['bonus_cd']}")
			if fam in ("tir", "jet") and portee <= 1:
				signaler("arme de tir/jet à portée ≤ 1", l, f"portee={d.get('portee')}")
			if fam == "hast" and portee < 2:
				signaler("arme d'hast à portée < 2", l, f"portee={d.get('portee')}")
			if not d.get("portee"):
				signaler("arme sans `portee`", l)
			if not (tags & {"cac", "jet", "tir"}):
				signaler("arme sans tag cac/jet/tir", l, str(sorted(tags)))
			if "tir" in tags and "cac" in tags:
				signaler("arme taguée à la fois `tir` et `cac`", l)
		else:
			pa = _num(d.get("bonus_pa"))
			if pa and (fam.startswith("armure · ") or fam == "bouclier"):
				p = poids_moyen(d)
				if pa > round(p * BAREME_PA_MAX) + 1:
					signaler(f"PA au-dessus du barème poids × {BAREME_PA_MAX:g} (gen_armures)", l,
							 f"{pa:g} PA pour {p:g} kg (barème max {round(p * BAREME_PA_MAX)})")
				elif pa < round(p * BAREME_PA_MIN) - 1:
					signaler(f"PA sous le barème poids × {BAREME_PA_MIN:g} (tissu)", l,
							 f"{pa:g} PA pour {p:g} kg (barème min {round(p * BAREME_PA_MIN)})")
			if fam == "bouclier" and not _num(d.get("bonus_pa")):
				signaler("bouclier sans `bonus_pa`", l)
			if d.get("portee") or d.get("bonus_degats_dice"):
				signaler("armure portant `portee` / dé de dégâts", l)
			if d.get("deux_mains"):
				signaler("armure `deux_mains`", l)
			# Malus de V des armures selon le poids MINIMAL (décision du 10/10) :
			# ≥ 14 kg → −1, ≥ 20 kg → −2, en dessous aucun.
			attendu = (-2 if poids_min(d) >= MALUS_V_LOURD_KG else -1 if poids_min(d) >= MALUS_V_KG else 0)
			if _num(d.get("bonus_malus_depl")) != attendu:
				signaler(f"malus de V ≠ barème (≥ {MALUS_V_KG:g} kg : −1, ≥ {MALUS_V_LOURD_KG:g} kg : −2)", l,
						 f"{poids_min(d):g} kg, malus {d.get('bonus_malus_depl', 0)} au lieu de {attendu}")
		if _num(eff.get("regen_pm")) > 0 and l["rarete"] == "commun":
			signaler("régénère les PM mais `commun` (plancher : peu commun)", l)
		if d.get("restriction") and not isinstance(d.get("restriction"), dict):
			signaler("`restriction` n'est pas un objet", l)

	if not regles:
		print("Aucune.")
	for regle in sorted(regles, key=lambda k: -len(regles[k])):
		ids = regles[regle]
		print(f"\n▸ {regle} — {len(ids)}")
		for t in ids[: top * 2]:
			print("   " + t)
		if len(ids) > top * 2:
			print(f"   … et {len(ids) - top * 2} autres")

	# ── 7. Couverture ──
	titre("7. COUVERTURE — trous de la gamme (familles sans pièce au-delà de « commun »)")
	for f in familles:
		paliers = {l["rarete"] for l in par_fam[f]}
		manques = [r for r in RARETES[:5] if r not in paliers]
		if manques:
			print(f"{f:<22} aucun : {', '.join(manques)}")

	if chemin_csv:
		absolu = chemin_csv if os.path.isabs(chemin_csv) else os.path.join(RACINE, chemin_csv)
		with open(absolu, "w", encoding="utf-8-sig", newline="") as fh:
			w = csv.writer(fh, delimiter=";")
			comp = ["degats", "toucher", "armure", "divers", "caracs", "effets", "portee", "total"]
			w.writerow(["id", "nom", "categorie", "famille", "rarete", "poids", "pmin", "pmax",
						"source_prix", "restriction"] + [f"P_{c}" for c in comp]
					   + sorted(cles_bonus) + ["bonus", "effets", "tags"])
			for l in lignes:
				d = l["doc"]
				w.writerow([l["id"], d.get("nom"), d.get("categorie"), l["fam"], l["rarete"],
							l["poids"], l["pmin"], l["pmax"], l["source"], d.get("restriction") or ""]
						   + [round(l["p"][c], 2) for c in comp]
						   + [d.get(k, "") for k in sorted(cles_bonus)]
						   + [d.get("bonus") or "", d.get("effets") or "", ",".join(sorted(tags_de(d)))])
		print(f"\nCSV écrit : {absolu} ({len(lignes)} lignes, séparateur « ; »).")


def main(argv: list) -> int:
	ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
	ap.add_argument("dump", nargs="?", help="chemin d'un dump (sinon le plus récent)")
	ap.add_argument("--dump", dest="dump_opt")
	ap.add_argument("--dernier", action="store_true", help="le dump le plus récent (défaut)")
	ap.add_argument("--variantes", action="store_true", help="inclure les variantes sur mesure")
	ap.add_argument("--top", type=int, default=15, help="lignes par liste (défaut 15)")
	ap.add_argument("--csv", help="écrit aussi une ligne par pièce (puissance détaillée, prix)")
	a = ap.parse_args(argv[1:])
	chemin = a.dump_opt or a.dump
	if not chemin:
		candidats = audit_economy.dumps_disponibles()
		if not candidats:
			print("Aucun telluris-dump-*.json trouvé (racine ou jsons/).", file=sys.stderr)
			return 2
		chemin = candidats[0]
	try:
		docs, meta = audit_economy.charger_dump(chemin)
	except OSError as e:
		print(f"Dump illisible : {e}", file=sys.stderr)
		return 2
	meta["_chemin"] = chemin
	analyser(docs, meta, a.variantes, max(1, a.top), a.csv)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv))
