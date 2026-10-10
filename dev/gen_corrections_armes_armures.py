#!/usr/bin/env python
# dev/gen_corrections_armes_armures.py
"""Corrections d'équilibrage des armes et armures — décidées le 10/10/2026 sur le rapport de
`dev/gen_analyse_armes_armures.py`. UN SEUL fichier à importer.

	python dev/gen_corrections_armes_armures.py [--dump jsons/telluris-dump-….json] [--sortie …]

Sortie : jsons/corrections_armes_armures_a_importer.json (carte d'import de /admin).

Ce qui change, et pourquoi :
  1. **Armes de départ sans restriction** — toute arme d'un `equipement_de_base` de
     `rules:vocations` (relu du dump : une vocation ajoutée est couverte) doit être portable
     par un personnage de base. `Epee_argent` reste au répurgateur, cadeau compris.
  2. **Malus de vitesse des armes allégé d'un cran** — −3 → −2, −2 → −1, −1 → retiré.
     Table FIGÉE `(avant, après)` : la règle « +1 » rejouée sur un dump déjà corrigé
     décalerait une seconde fois ; une valeur qui n'est ni l'avant ni l'après (retouche à la
     main) est laissée et signalée.
  3. **Armures lourdes** — malus de V à partir de 14 kg (poids minimal) : −1, à partir de
     20 kg : −2 (le Harnois du Grand Arsenal l'a déjà). Les Épaulières de plates (4 kg)
     perdent le leur. Poids réévalués : Armure de bataille (plates couvrant tout le corps)
     et Jambières de plates étaient trop légères.
  4. **Pièces hors du barème PA × poids** (`gen_armures`) — un peu alourdies ; en échange
     plusieurs boucliers gagnent un malus d'agilité plus faible.
  5. **Régénération de PM** sur la Baguette ouvragée et le Sceptre d'apparat : une arme
     dont `effets` n'a pas de `duree` est lue comme une pièce PORTÉE
     (`characters.arme_effets_portes`). Refusé si l'arme porte une `duree` (l'effet irait à
     la cible). Une pièce qui régénère les PM n'est jamais `commun`.
  6. **Vêtements sans aucun bonus** — petit gain d'Int, de Cha ou de R.
  7. **Raretés** — liste validée (règles par famille de `gen_analyse_armes_armures`),
     armes de départ communes sauf l'Épée d'argent.
  8. **Arc du Grand Atelier** — tag `distance` (inconnu du combat : l'arc ne tirait pas)
     → `tir`. **Chasse-mouches de crin** — insigne de commandement : Cha +5.
  9. **Restrictions relevées de +5 AU TOTAL** (66 % ne bloquaient personne : seuil ≤ départ
     de toute race), réparties entre les caractéristiques citées au prorata de leur seuil
     (plus grand reste) : `{F: 18, Vol: 25}` → `{F: 20, Vol: 28}`. Table FIGÉE `[avant, après]` dans
     `dev/corrections_armes_armures_restrictions.json`, même contrat que le malus de V.
     ⚠️ Plafonnée au MINIMUM de l'espèce qui porte la pièce dans son kit (`items` d'un
     `espece:*`) — sinon `gen_equipement_humanoides` refuserait ce kit à sa relance :
     Arbalète (Ag 15 gardé, F 12), Gladius et Trident barbelé (F 15), Rondache inchangée. Armes de
     départ exclues (aucune restriction, cf. 1).
 10. **Armes de jet sans `bonus_cc`** — le jet lit `bonus_cd` : ce bonus était mort.

Le fichier ne porte que le DIFF : chaque doc est repris ENTIER du dump (l'import est un PUT
complet, CLAUDE.md §11), `_rev` retiré. Base à jour ⇒ aucun fichier. Un `_id` absent, une
pièce qui n'est ni arme ni armure, ou une régénération sur une arme à `duree` refusent TOUT
le lot. Les variantes sur mesure ne sont pas touchées (elles portent leur propre doc figé).
"""

import argparse
import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "corrections_armes_armures_a_importer.json")

RETIRER = None   # valeur cible = retirer le champ

# ── 2. Malus de vitesse des armes : slug → (avant, après) ──────────────────────────
MALUS_V_ARMES = {
	"Arbalete_lourde": (-2, -1), "Bardiche": (-1, None), "Bec_de_corbin": (-2, -1), "Cestus_de_jet": (-1, None),
	"Claymore": (-2, -1), "Corseque": (-1, None), "Da_dao": (-2, -1), "Doloire": (-1, None),
	"Epee_a_deux_mains": (-2, -1), "Epee_batarde": (-1, None), "Epee_large": (-1, None), "Epee_longue": (-1, None),
	"Epee_longue_ordre": (-1, None), "Esponton": (-1, None), "Falarique": (-1, None), "Fauchard_crochet": (-1, None),
	"Faucharde": (-1, None), "Fauchon": (-1, None), "Fleau_arme": (-1, None), "Fleau_monte": (-2, -1),
	"Fourche_de_guerre": (-1, None), "Fourche_fauchard": (-1, None), "Glaive": (-1, None), "Glaive_guisarme": (-2, -1),
	"Grand_cimeterre": (-2, -1), "Guisarme": (-1, None), "Guisarme_vouge": (-2, -1), "Hache_a_deux_mains": (-2, -1),
	"Hache_de_bucheron": (-1, None), "Hache_de_guerre": (-1, None), "Hallebarde": (-1, None), "Ji": (-1, None),
	"Kanabo": (-2, -1), "Khopesh": (-1, None), "Lance_de_cavalerie_lourde": (-3, -2), "Lance_de_cavalerie_moyenne": (-2, -1),
	"Lance_de_joute": (-3, -2), "Lance_longue": (-1, None), "Maillet_de_guerre": (-2, -1), "Marteau_de_lucerne": (-2, -1),
	"Masse_benie": (-1, None), "Masse_cannelee_perse": (-1, None), "Masse_de_fantassin": (-1, None), "Massue": (-1, None),
	"Morgenstern": (-2, -1), "No_dachi": (-1, None), "Partisane": (-1, None), "Pata_a_hampe": (-1, None),
	"Pic_de_fantassin": (-1, None), "Pilum": (-1, None), "Pique": (-2, -1), "Sarisse": (-3, -2),
	"Tetsubo": (-1, None), "Trident": (-1, None), "Trident_barbele": (-1, None), "Vouge": (-1, None),
	"Woludo": (-1, None), "Yari": (-1, None),
}

# ── Champs à valeur ABSOLUE : slug → {champ: valeur | RETIRER} ─────────────────────
# `bonus` est FUSIONNÉ clé à clé (RETIRER ôte la caractéristique ; un `bonus` vidé disparaît).
CHAMPS = {
	# 3. Armures lourdes (seuil 14 kg) et poids réévalués
	"Armure_de_bataille":         {"poids": [16, 21], "bonus_malus_depl": -1},
	"Armure_de_plates_en_bronze": {"bonus_malus_depl": -1},
	"Harnois_complet":            {"bonus_malus_depl": -1},
	"Epaulieres_de_plates":       {"bonus_malus_depl": RETIRER},
	"Jambières_de_plates":        {"poids": 4.0},
	# 4. Barème PA × poids : un peu alourdies, agilité épargnée
	"Armure_plates_surcoat":      {"poids": [10.5, 13]},
	"Bocle":                      {"poids": [0.8, 1.2]},
	"Bouclier_chauffe":           {"poids": [3, 4.5], "bonus": {"Ag": -4}},
	"Bouclier_normand":           {"poids": [4.2, 7], "bonus": {"Ag": -4}},
	"Bouclier_sacre":             {"poids": [2.5, 4]},
	"Pelta":                      {"poids": [1.3, 2]},
	"Rondache":                   {"poids": [1.8, 3], "bonus": {"Ag": RETIRER}},
	"Targe_a_enarmes":            {"poids": [2, 3.2], "bonus": {"Ag": RETIRER}},
	"Gants_cuir_epais":           {"poids": 0.4},
	"Manteau_de_cour_double":     {"poids": [2.5, 4]},
	# 5. Régénération de PM (arme sans `duree` ⇒ effet porté)
	"Baguette_ouvragee":          {"effets": {"regen_pm": 2}},
	"Sceptre_d_apparat":          {"effets": {"regen_pm": 1}},
	# 6. Vêtements : être habillé rapporte un peu
	"Robe_lin_ceinturee":   {"bonus": {"Int": 1}},
	"Bandages_de_poing":    {"bonus": {"R": 1}},
	"Bandeau_meditation":   {"bonus": {"Int": 1}},
	"Bonnet_de_clerc":      {"bonus": {"Int": 2}},
	"Cagoule":              {"bonus": {"R": 1}},
	"Capuche_bordeaux":     {"bonus": {"Cha": 1}},
	"Capuche_de_laine":     {"bonus": {"R": 1}},
	"Capuche_noire":        {"bonus": {"Cha": 1}},
	"Capuchon_de_lin":      {"bonus": {"R": 1}},
	"Chapeau_a_plume":      {"bonus": {"Cha": 2}},
	"Chapeau_large_bord":   {"bonus": {"Cha": 1, "R": 1}},
	"Chapeau_mou":          {"bonus": {"Cha": 1}},
	"Coiffe_plumes":        {"bonus": {"Cha": 2}},
	"Couvre_chef_office":   {"bonus": {"Cha": 2}},
	"Sandales_lierre":      {"bonus": {"Int": 1}},
	"Chausses_laine":       {"bonus": {"R": 1}},
	"Jupe_de_chanvre":      {"bonus": {"R": 1}},
	"Jupe_longue_lin":      {"bonus": {"Cha": 1}},
	"Pantalon_ajuste_noir": {"bonus": {"Cha": 1}},
	"Pantalon_ample":       {"bonus": {"R": 1}},
	"Pantalon_toile":       {"bonus": {"R": 1}},
	"Pantalon_velours":     {"bonus": {"Cha": 2}},
	"Sous_robe_lin":        {"bonus": {"Int": 1}},
	"Sous_robe_noire":      {"bonus": {"Int": 1}},
	# 8. Cas isolés
	"Arc_du_grand_atelier":   {"tags": ["tir"]},
	"Chasse_mouches_de_crin": {"bonus": {"Cha": 5}, "sous_categorie": "insigne"},
	# 10. Armes de jet : le bonus de corps à corps n'est pas lu
	"Hache_apparat_amerindienne": {"bonus_cc": RETIRER},
	"Kunai":                      {"bonus_cc": RETIRER},
	"Pilum":                      {"bonus_cc": RETIRER},
	"Tomahawk":                   {"bonus_cc": RETIRER},
}

# ── 9. Restrictions : slug → [avant, après] (figées sur le dump du 10/10) ──────────
TABLE_RESTRICTIONS = os.path.join(RACINE, "dev", "corrections_armes_armures_restrictions.json")


def charger_restrictions(chemin: str = TABLE_RESTRICTIONS) -> dict:
	with open(chemin, encoding="utf-8") as f:
		return {slug: (avant, apres) for slug, (avant, apres) in json.load(f).items()}


RESTRICTIONS = charger_restrictions()

# ── 7. Raretés ─────────────────────────────────────────────────────────────────────
RARETES = {
	# → commun (le quart le plus faible de leur famille, rien de noble ; armes de départ)
	"Mantelet_de_plumes": "commun", "bijou": "commun", "Pelta": "commun",
	"Attrape_coquin": "commun", "Lance_de_cavalerie_lourde": "commun",
	"Couteau_de_jet_africain": "commun", "dague_rituelle": "commun", "Sceptre_os": "commun",
	"Baton_cornu": "commun", "Chaine_de_combat": "commun", "Baton_bois_vivant": "commun",
	# → peu_commun
	"Cape_de_plumes_noires": "peu_commun",
	"Jambières_cuir_renf": "peu_commun", "Guetres_de_route": "peu_commun",
	"Jambières_de_plates": "peu_commun", "Gantelets_de_plates": "peu_commun",
	"Gants_archer": "peu_commun", "Bottes_de_plates": "peu_commun", "Sandales_moine": "peu_commun",
	"Couronne_branchages": "peu_commun", "Armure_a_bandes": "peu_commun", "Clibanion": "peu_commun",
	"Armure_de_plates": "peu_commun", "Armure_plates_surcoat": "peu_commun",
	"Gorgerin_de_cuir_bouilli": "peu_commun", "Bardiche": "peu_commun", "Doloire": "peu_commun",
	"Hallebarde": "peu_commun", "Vouge": "peu_commun", "Tambour_de_guerre": "peu_commun",
	"Bolas": "peu_commun", "Masse_de_fantassin": "peu_commun", "Pic_de_fantassin": "peu_commun",
	"Talwar": "peu_commun", "Masse_a_brides": "peu_commun", "Epee_batarde": "peu_commun",
	"Fleau_arme": "peu_commun", "Masse_cannelee_perse": "peu_commun", "Schiavona": "peu_commun",
	"Kanabo": "peu_commun",
	# → rare (meilleure pièce d'une famille qui n'en avait aucune)
	"Pavois": "rare", "Barde_de_cuir_bouilli": "rare", "Falarique": "rare", "No_dachi": "rare",
}

# Armes de départ qui gardent une rareté au-dessus de `commun` (décision du 10/10).
DEPART_NON_COMMUNES = {"Epee_argent"}


# ── Moteur ───────────────────────────────────────────────────────────────────────────

def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


def armes_de_depart(docs: list) -> set:
	"""Ids des items d'un `equipement_de_base` de `rules:vocations`."""
	voc = next((d for d in docs if d.get("_id") == "rules:vocations"), None) or {}
	out = set()
	for v in voc.get("value") or []:
		for ref in v.get("equipement_de_base") or []:
			rid = ref.get("item") if isinstance(ref, dict) else ref
			if isinstance(rid, str) and rid.startswith("item:"):
				out.add(rid)
	return out


def _appliquer_champ(doc: dict, champ: str, valeur):
	if champ in ("bonus", "effets"):
		bloc = dict(doc.get(champ) or {})
		for k, v in valeur.items():
			if v is RETIRER:
				bloc.pop(k, None)
			else:
				bloc[k] = v
		if bloc:
			doc[champ] = bloc
		else:
			doc.pop(champ, None)
	elif valeur is RETIRER:
		doc.pop(champ, None)
	else:
		doc[champ] = copy.deepcopy(valeur)


def generer(docs: list, malus=MALUS_V_ARMES, champs=CHAMPS, raretes=RARETES,
			depart_non_communes=DEPART_NON_COMMUNES, restrictions=None):
	"""→ (sortie, erreurs, avertissements). `sortie` = docs modifiés, repris entiers du dump
	sans `_rev` ; `erreurs` non vide ⇒ le lot ne doit pas être écrit."""
	index = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	erreurs, avert = [], []
	travail: dict[str, dict] = {}

	def doc_de(slug_ou_id: str):
		i = slug_ou_id if slug_ou_id.startswith("item:") else "item:" + slug_ou_id
		if i not in travail:
			src = index.get(i)
			if not src:
				erreurs.append(f"{i} : absent du dump")
				return None
			if src.get("categorie") not in ("arme", "armure"):
				erreurs.append(f"{i} : ni arme ni armure ({src.get('categorie')!r})")
				return None
			travail[i] = copy.deepcopy(_sans_rev(src))
		return travail[i]

	# 1. Armes de départ
	depart = armes_de_depart(docs)
	for i in sorted(depart):
		d = doc_de(i)
		if d is None:
			continue
		d.pop("restriction", None)
		slug = i[5:]
		if slug not in depart_non_communes and slug not in raretes:
			d["rarete"] = "commun"

	# 2. Malus de vitesse des armes
	for slug, (avant, apres) in malus.items():
		d = doc_de(slug)
		if d is None:
			continue
		actuel = d.get("bonus_malus_depl")
		if actuel == avant:
			_appliquer_champ(d, "bonus_malus_depl", apres)
		elif actuel != apres:
			avert.append(f"item:{slug} : malus de V {actuel!r} (attendu {avant} ou {apres}) — retouché depuis, laissé")

	# 9. Restrictions relevées (les armes de départ n'en ont plus : jamais dans la table)
	for slug, (avant, apres) in (RESTRICTIONS if restrictions is None else restrictions).items():
		if "item:" + slug in depart:
			erreurs.append(f"item:{slug} : arme de départ — elle ne doit porter aucune restriction")
			continue
		d = doc_de(slug)
		if d is None:
			continue
		actuel = d.get("restriction")
		if actuel == avant:
			d["restriction"] = dict(apres)
		elif actuel != apres:
			avert.append(f"item:{slug} : restriction {actuel!r} (attendu {avant} ou {apres}) — retouchée depuis, laissée")

	# 3-6, 8, 10. Champs absolus
	for slug, modifs in champs.items():
		d = doc_de(slug)
		if d is None:
			continue
		for champ, valeur in modifs.items():
			_appliquer_champ(d, champ, valeur)

	# 7. Raretés
	for slug, rarete in raretes.items():
		d = doc_de(slug)
		if d is not None:
			d["rarete"] = rarete

	# Gardes
	for i, d in travail.items():
		eff = d.get("effets") or {}
		if d.get("categorie") == "arme" and (eff.get("regen_pm") or eff.get("regen_pv")) and eff.get("duree"):
			erreurs.append(f"{i} : régénération sur une arme à `duree` — elle irait à la cible")
		if eff.get("regen_pm") and d.get("rarete") == "commun":
			erreurs.append(f"{i} : régénère les PM mais serait `commun`")

	sortie = [d for i, d in sorted(travail.items()) if d != _sans_rev(index[i])]
	return sortie, erreurs, avert


def _diff(avant: dict, apres: dict) -> str:
	cles = sorted(set(avant) | set(apres))
	parts = []
	for k in cles:
		if k == "_rev" or avant.get(k) == apres.get(k):
			continue
		parts.append(f"{k}: {avant.get(k, '∅')!r} → {apres.get(k, '∅')!r}")
	return " · ".join(parts)


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json"))
				   + glob.glob(os.path.join(RACINE, "telluris-dump-*.json")),
				   key=os.path.basename)
	if not dumps:
		sys.exit("Aucun dump telluris-dump-*.json")
	return dumps[-1]


def main(argv: list) -> int:
	ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
	ap.add_argument("--dump")
	ap.add_argument("--sortie", default=SORTIE)
	a = ap.parse_args(argv[1:])
	chemin = a.dump or dernier_dump()
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	docs = data["docs"] if isinstance(data, dict) else data
	print(f"Dump : {chemin}")
	sortie, erreurs, avert = generer(docs)
	for t in avert:
		print("⚠ " + t)
	if erreurs:
		print("\nLOT REFUSÉ — rien n'est écrit :")
		for t in erreurs:
			print("   ✗ " + t)
		return 1
	index = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	for d in sortie:
		print(f"  {d['_id']:<40}{_diff(index[d['_id']], d)}")
	if not sortie:
		print("Base à jour : aucune correction à importer, aucun fichier écrit.")
		return 0
	with open(a.sortie, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
	print(f"\n{len(sortie)} docs → {a.sortie}")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv))
