"""Contenu PAR DÉFAUT de toutes les zones d'influence NATURELLES (cf. `utils/zones.py`, `peupler_lieu`).

Table `TABLE` autorée (Auteur, 15/11, reprise des décisions du 16/11) :

- zones NATURELLES seules : ni zones de cité (`zone::*`, `zone:faubourg`), ni zones habitables, ni
  calques de danger (`tres_dangereuse`, `zone_danger_*`) — `HORS_PERIMETRE` ;
- faune + monstres COMMUNS (humanoïdes, morts-vivants ou esprits ordinaires compris) ; jamais un
  légendaire, un boss, une créature nommée, un ange ni un démon (`TAGS_INTERDITS`, `nom_propre`) ;
- filtre `regions` sur la faune TYPÉE d'une zone partagée par plusieurs continents (loup, cerf →
  europe ; hyènes, fauves → afrique…), rien sur le cosmopolite ni sur un biome déjà typé.

ADDITIF : un défaut déjà présent sur la zone (même id) est gardé tel quel, régions comprises ;
rien n'est retiré. DELTA seul contre le dump : seules les zones qui gagnent une entrée sont émises.

    python dev/gen_defauts_zones_biomes.py [--dump jsons/telluris-dump-….json] [--sortie …]
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import zones  # noqa: E402

SORTIE = os.path.join(RACINE, "jsons", "defauts_zones_biomes_a_importer.json")

TAGS_INTERDITS = {"legendaire", "boss", "ange", "celeste", "demon", "infernal", "divin", "cataclysme"}
HORS_PERIMETRE_IDS = {"zone:faubourg", "zone:tres_dangereuse"}
HORS_PERIMETRE_PREFIXES = ("zone::", "zone:habitable_", "zone:zone_danger_")

# Abréviations des régions de `rules:regions` (relues et vérifiées au lancement).
REG = {"E": "europe", "N": "grand_nord", "S": "steppes", "AN": "afrique_du_nord", "A": "afrique",
	   "O": "oceanie"}

# zone (sans « zone: ») → (rencontres, ressources) ; « id@E,S » = filtre de régions.
TABLE = {
	"alpage": (["lievre", "rapaces", "loup@E,S", "ours@E,S", "oreade@E"],
			   ["Herbes_medicinales", "Fleur_de_souci", "Eau_de_source", "graines", "Herbes_aromatiques"]),
	"banquise": (["ours_polaire", "phoques_et_morses", "poissons_mammiferes_marins"],
				 ["Huile_de_phoque", "Sel"]),
	"bocage": (["lievre", "renard", "petits_animaux_divers", "serpent", "sanglier@E", "cerf@E"],
			   ["Merisier", "Chene", "Charme", "Herbes_medicinales", "Fleur_de_souci", "Cassis", "Miel", "graines"]),
	"campement_bandit": (["gobelin", "orc", "gobelin_chamanique", "loup@E,S"],
						 ["Cendres", "Herbes_a_bruler"]),
	"canyon": (["rapaces", "oiseaux_de_proies", "serpent", "scorpion_geant", "harpie"],
			   ["pierre", "fer", "Sel_gemme", "Eau_de_source"]),
	"carriere": (["rat_geant", "serpent", "rapaces"],
				 ["pierre", "alun", "Salpetre", "fer"]),
	"cascade": (["rapaces", "serpent", "ondin", "naiade@E"],
				["Eau_de_source", "pierre", "Herbes_medicinales", "gemmes"]),
	"cedraie_altitude": ([], ["Herbes_medicinales", "pierre"]),
	"collines": (["rapaces", "serpent", "petits_animaux_divers", "gobelin@E", "orc@E", "hyenes@A,AN", "antilopes@A,AN"],
				 ["Herbes_medicinales", "pierre", "Herbes_aromatiques"]),
	"contreforts": (["rapaces", "aigle_geant", "orc", "loup@E,S,N", "ours@E,S", "troll@E,N"],
					["pierre", "fer", "Sapin", "Pin_sylvestre", "Herbes_medicinales", "Eau_de_source"]),
	"contreforts_arides": (["orc@AN", "nasnas@AN"], ["alun"]),
	"cote_tropicale": (["singes", "serpent"], ["Sel", "Palmier"]),
	"delta": (["flamants", "serpent", "rapaces", "hippopotames@A,AN", "crocodile@A"],
			  ["Papyrus", "Lotus", "Eau_de_source", "Herbes_medicinales", "Sycomore", "Palmier_dattier"]),
	"desert": (["scorpion_geant", "serpent", "nuee_de_scarabees", "rapaces", "ghul_des_sables@AN", "nasnas@AN"],
			   ["Sel_gemme", "pierre", "Natron", "Epines"]),
	"desert_brumeux": (["rapaces"], ["Epines"]),
	"desert_froid": (["serpent", "antilopes@S", "cheval@S"], ["Epines"]),
	"desert_sel": (["scorpion_geant", "nuee_de_scarabees", "rapaces"],
				   ["Sel_gemme", "Sel", "Natron", "alun", "pierre"]),
	"desert_succulentes": (["antilopes", "autruches@A"], []),
	"eboulis": (["rapaces", "serpent", "aigle_geant", "petits_animaux_divers"],
				["pierre", "fer", "plomb", "Lichen"]),
	"erg": (["scorpion_geant", "nuee_de_scarabees", "serpent", "autruches@A,AN", "ghul_des_sables@AN", "nasnas@AN"],
			["Epines"]),
	"estuaire": (["poissons_mammiferes_marins", "serpent", "rapaces", "ondin", "phoques_et_morses@E,N",
				  "flamants@A,AN", "crocodile@A"],
				 ["Sel", "Saule", "Peuplier", "Herbes_medicinales"]),
	"falaise_cotiere": (["rapaces", "harpie", "sirene", "phoques_et_morses@E,N"],
						["pierre", "Sel", "plumes", "Nacre"]),
	"fjord": (["phoques_et_morses", "poissons_mammiferes_marins", "loup", "rapaces", "ours@E,N",
			   "troll@E,N", "draugr@N"],
			  ["pierre", "Sel", "Huile_de_phoque", "Pin_sylvestre", "Bouleau", "Lichen"]),
	"fleuve_tropical": (["serpent_geant", "singes"], ["Iroko", "Okoume"]),
	"foret_bambou": (["singes", "grands_singes", "serpent", "fauves", "araignee"],
					 ["Lianes", "Herbes_medicinales", "graines", "Eau_de_source"]),
	"foret_brulee": (["rapaces", "petits_animaux_divers", "nuee_de_scarabees", "loup@E,S"],
					 ["Cendres", "Herbes_a_bruler", "graines"]),
	"foret_chenes_lieges": (["serpent", "rapaces"],
							["Chene_vert", "Miel", "Truffe", "Herbes_aromatiques"]),
	"foret_claire_seche": (["rapaces", "hyenes@A"], ["graines", "Santal"]),
	"foret_coniferes": (["loup", "ours", "ecureuil", "renard", "rapaces", "homme_arbre", "cerf@E,S", "troll@E,N"],
						["Sapin", "Epicea", "Pin_sylvestre", "Meleze", "Resine_de_pin", "Herbes_medicinales", "Lichen"]),
	"foret_dense": (["araignee", "araignee_geante", "homme_arbre", "ours@E", "dryade@E", "fauves@A", "grands_singes@A"],
					["If", "Truffe"]),
	"foret_equatoriale": (["singes"], ["Okoume", "Iroko", "Palissandre"]),
	"foret_feuillus": (["rapaces", "araignee", "ours@E", "dryade@E", "satyre@E", "gobelin_chamanique@E"],
					   ["Erable", "Tilleul", "Chataignier", "Truffe", "Miel", "Cire_d_abeille", "Racine_de_mandragore"]),
	"foret_galerie": (["hippopotames", "rapaces"], ["Iroko", "Lianes", "Herbes_medicinales"]),
	"foret_mixte_montagne": (["renard", "orc@E", "troll@E,N"],
							 ["Epicea", "Meleze", "Herbes_medicinales", "Resine_de_pin"]),
	"foret_nuages": (["singes", "grands_singes", "rapaces", "serpent", "araignee_geante"],
					 ["Lichen_des_brumes", "Lianes", "Herbes_medicinales", "Eau_de_source"]),
	"foret_persistante": (["ecureuil", "renard", "rapaces", "loup@E", "cerf@E", "ours@E"],
						  ["If", "Pin", "Sapin", "Chene_vert", "Resine_de_pin", "Herbes_medicinales"]),
	"foret_petrifiee": (["rapaces", "serpent", "araignee_geante", "gargouille", "basilic", "squelette"],
						["pierre", "gemmes", "Lichen"]),
	"foret_temperee_humide": (["renard", "ecureuil", "serpent", "cerf@E", "ours@E", "loup@E", "dryade@E"],
							  ["Aulne", "Saule", "Erable", "Epicea", "If", "Herbes_medicinales", "Lichen", "Eau_de_source"]),
	"foret_tropicale_seche": (["rapaces", "araignee"], ["Palissandre", "Santal", "Herbes_medicinales"]),
	"fourre_epineux": (["hyenes@A"], ["Gomme_d_acacia"]),
	"garrigue": (["serpent", "lievre", "renard", "rapaces", "araignee", "sanglier@E,AN", "satyre@E"],
				 ["Herbes_aromatiques", "Chene_vert", "Genevrier", "Miel", "Herbes_a_bruler", "pierre"]),
	"glacier": (["loup", "rapaces", "aigle_geant", "ours_polaire@N", "troll@E,N"],
				["Eau_de_source", "pierre", "Lichen"]),
	"gorge": (["rapaces", "aigle_geant", "harpie", "serpent", "orc", "troll@E,N"],
			  ["pierre", "fer", "Eau_de_source", "Herbes_medicinales"]),
	"gouffre": (["chauve_souris", "chauve_souris_geante", "rat_geant", "araignee_geante", "troglodyte"],
				["pierre", "Eau_de_source", "Salpetre", "Lichen"]),
	"grotte": (["chauve_souris", "chauve_souris_geante", "rat_geant", "araignee_geante", "troglodyte",
				"ours@E,S,N", "gobelin@E"],
			   ["pierre", "Salpetre", "fer", "gemmes", "Lichen"]),
	"hamada": (["scorpion_geant", "serpent", "rapaces", "nasnas@AN", "ghul_des_sables@AN"],
			   ["pierre", "Sel_gemme", "fer", "Epines"]),
	"haut_plateau_froid": ([], ["Eau_de_source"]),
	"haute_mer": (["poissons_mammiferes_marins", "tortues_marines", "triton", "sirene"], ["Sel"]),
	"haute_montagne": (["aigle_geant", "rapaces", "wyvern", "griffon", "troll@E,N", "oreade@E"],
					   ["pierre", "fer", "argent", "gemmes", "Lichen", "Eau_de_source"]),
	"ile": (["tortues_marines", "rapaces", "serpent", "petits_animaux_divers", "singes@A", "nereide@E"],
			["Eau_de_source", "Nacre", "plumes", "Cocotier@A,O", "Pin_parasol@E"]),
	"jungle": (["grands_singes", "singes", "fauves", "serpent_geant", "araignee_geante", "crocodile", "elephants"],
			   ["Acajou", "Ebene", "Okoume", "Palissandre", "Lianes", "Herbes_medicinales"]),
	"karst": (["chauve_souris", "rapaces", "serpent", "lievre", "troglodyte"],
			  ["pierre", "Eau_de_source", "Salpetre", "alun", "Herbes_aromatiques"]),
	"lac": (["serpent", "rapaces", "petits_animaux_divers", "renard", "ondin", "naiade@E"],
			["Saule", "Peuplier", "Aulne", "perles", "Herbes_medicinales"]),
	"lac_alcalin": (["serpent"], ["Tamaris"]),
	"lagune": (["flamants", "serpent", "rapaces", "tortues_marines", "crocodile@A"],
			   ["Sel", "Nacre", "perles", "Tamaris"]),
	"lande": (["lievre", "renard", "rapaces", "loup@E", "cu_sidhe@E"],
			  ["miel_de_bruyere", "Herbes_a_bruler", "Genevrier", "Bouleau", "Herbes_medicinales", "Lichen"]),
	"lande_arctique": (["rapaces"], []),
	"littoral": (["rapaces", "poissons_mammiferes_marins", "triton", "phoques_et_morses@E,N", "tortues_marines@A,O"],
				 ["Sel", "Nacre", "pierre", "plumes"]),
	"mangrove": (["crocodile", "serpent", "serpent_geant", "singes", "rapaces"],
				 ["Lianes", "Sel", "Herbes_medicinales", "perles"]),
	"maquis": (["araignee", "satyre@E"], ["Chene_vert", "Herbes_aromatiques", "Miel"]),
	"marais": (["serpent", "rat_geant", "gobelin_des_marais", "araignee", "petits_animaux_divers", "bunyip@O"],
			   ["Racine_de_mandragore", "Herbes_medicinales", "Saule", "Aulne", "Herbes_a_bruler"]),
	"marais_salant": (["flamants", "serpent", "rapaces", "petits_animaux_divers"],
					  ["Sel", "Tamaris", "Herbes_medicinales"]),
	"marecage_tropical": (["singes", "rapaces"], ["Lianes"]),
	"mer_cotiere": (["poissons_mammiferes_marins", "tortues_marines", "triton", "nereide@E", "phoques_et_morses@E,N"],
					["Sel", "Nacre", "perles"]),
	"mer_froide": (["triton"], ["Sel"]),
	"montagne": (["rapaces", "orc", "harpie", "loup@E,S,N", "ours@E,S", "troll@E,N", "oreade@E"],
				 ["fer", "argent", "plomb", "Herbes_medicinales", "Eau_de_source", "Pin_cembro@E"]),
	"oasis": (["serpent", "scorpion_geant", "rapaces", "antilopes@AN"],
			  ["Palmier_dattier", "Dattes", "Eau_de_source", "Figues", "Tamaris"]),
	"oliveraie": (["lievre"], ["Herbes_aromatiques", "Figuier", "Amandes"]),
	"palmeraie": (["rapaces"], ["Palmier_dattier", "Figues"]),
	"pinede_seche": (["renard", "rapaces"], ["Pin_parasol", "Herbes_aromatiques"]),
	"plage": (["tortues_marines", "rapaces", "phoques_et_morses@E,N"],
			  ["Sel", "Nacre", "plumes", "Cocotier@A,O"]),
	"plaine_ouverte": (["lievre", "renard", "rapaces", "petits_animaux_divers", "loup@E,S", "cerf@E",
						"cheval@S", "antilopes@A,AN", "hyenes@A"],
					   ["Herbes_aromatiques"]),
	"plateau": (["lievre", "rapaces", "renard", "loup@E,S,N", "antilopes@A,AN"],
				["pierre", "Herbes_medicinales", "graines", "Genevrier"]),
	"prairie_altitude_tropicale": ([], ["graines"]),
	"prairie_hautes_herbes": (["antilopes@S", "centaure@S"], ["Herbes_aromatiques"]),
	"recif": (["poissons_mammiferes_marins", "tortues_marines", "triton", "sirene"],
			  ["Nacre", "perles", "Sel"]),
	"recif_corallien": (["tortues_marines", "triton"], ["perles"]),
	"riviere": (["rapaces", "ondin", "naiade@E", "loup@E", "cerf@E"], ["perles", "gemmes", "Frene"]),
	"riziere": ([], ["Herbes_medicinales"]),
	"ruines_maudites": (["squelette", "zombie", "goule", "spectre", "fantome", "rat_geant", "gargouille", "chauve_souris"],
						["pierre", "os", "Racine_de_mandragore"]),
	"savane": (["antilopes", "fauves", "hyenes", "elephants", "buffles", "autruches", "rapaces"],
			   ["graines", "Acacia", "Baobab", "Herbes_medicinales"]),
	"savane_arboree": (["autruches", "rapaces"], ["Acacia", "Gomme_d_acacia"]),
	"source_thermale": (["serpent", "rapaces", "petits_animaux_divers", "elementaux"],
						["Soufre", "alun", "pierre"]),
	"steppe": (["loup", "cheval", "antilopes", "rapaces", "lievre", "centaure@S"],
			   ["graines", "Feuilles_d_absinthe", "Herbes_medicinales", "Fleur_de_souci"]),
	"steppe_aride": (["cheval@S"], []),
	"steppe_epineuse": ([], ["Herbes_medicinales"]),
	"taiga": (["loup", "ours", "rennes", "rapaces", "ecureuil", "cerf", "troll@E,N"],
			  ["Epicea", "Pin_sylvestre", "Meleze", "Bouleau", "Lichen", "Resine_de_pin"]),
	"terres_cultivees": (["lievre", "renard", "petits_animaux_divers", "rat_geant", "rapaces", "sanglier@E"],
						 ["grain_de_froment", "grain_d_orge", "grain_de_seigle", "graines", "Fleur_de_souci"]),
	"toundra": (["rennes", "boeufs_musques", "loup", "rapaces", "mammouth", "ours_polaire@N"],
				["Lichen", "Bouleau", "plumes", "Herbes_medicinales"]),
	"tourbiere": (["serpent", "petits_animaux_divers", "rapaces", "gobelin_des_marais", "loup@E,N"],
				  ["Herbes_a_bruler", "Lichen", "Herbes_medicinales", "Bouleau", "Racine_de_mandragore"]),
	"vallee": (["renard", "lievre", "rapaces", "petits_animaux_divers", "cerf@E", "sanglier@E", "loup@E,S",
				"antilopes@A,AN"],
			   ["Herbes_medicinales", "Fleur_de_souci", "graines", "Eau_de_source", "Peuplier"]),
	"verger": (["petits_animaux_divers", "renard", "lievre", "ecureuil"], ["Miel", "Cire_d_abeille", "Cassis"]),
	"volcan": (["elementaux", "petit_dragon", "rapaces", "serpent"], ["Soufre", "pierre", "Cendres", "fer"]),
}


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def hors_perimetre(zone_id: str) -> bool:
	return zone_id in HORS_PERIMETRE_IDS or zone_id.startswith(HORS_PERIMETRE_PREFIXES)


def entree(brut: str, cle: str, prefixe: str) -> dict:
	"""« id@E,S » → `{cle: "<prefixe>id", "regions": ["europe", "steppes"]}`."""
	ident, _, regs = brut.partition("@")
	out = {cle: prefixe + ident}
	if regs:
		out["regions"] = [REG[r] for r in regs.split(",")]
	return out


def controler(docs: dict) -> list:
	"""Erreurs de la table : zone inconnue ou hors périmètre, id absent du dump, espèce interdite,
	région inconnue, zone naturelle oubliée."""
	err = []
	regions = set(((docs.get(zones.REGLES_REGIONS) or {}).get("regions") or {}))
	for code, rid in REG.items():
		if rid not in regions:
			err.append(f"région {rid} ({code}) absente de rules:regions")
	naturelles = {i for i, d in docs.items() if d.get("type") == "zone_influence" and not hors_perimetre(i)}
	for z, (renc, ress) in TABLE.items():
		zid = "zone:" + z
		if zid not in docs:
			err.append(f"{zid} absente du dump")
		elif hors_perimetre(zid):
			err.append(f"{zid} hors périmètre")
		for brut in renc:
			ident = entree(brut, "espece", "espece:")["espece"]
			esp = docs.get(ident)
			if not esp:
				err.append(f"{zid} : {ident} absente du dump")
			elif set(esp.get("tags") or []) & TAGS_INTERDITS or esp.get("nom_propre"):
				err.append(f"{zid} : {ident} est légendaire, boss, nommée, ange ou démon")
		for brut in ress:
			ident = entree(brut, "ressource", "item:")["ressource"]
			if ident not in docs:
				err.append(f"{zid} : {ident} absent du dump")
		vus = [b.partition("@")[0] for b in renc + ress]
		if len(vus) != len(set(vus)):
			err.append(f"{zid} : doublon dans la table")
	for zid in sorted(naturelles - {"zone:" + z for z in TABLE}):
		err.append(f"{zid} : zone naturelle absente de la table")
	return err


def zones_a_emettre(docs: dict) -> list:
	out = []
	for z, (renc, ress) in TABLE.items():
		zone = docs["zone:" + z]
		neuve = {k: v for k, v in zone.items() if k != "_rev"}
		change = False
		for (champ, cle, champ_defaut), bruts, prefixe in (
				(zones.CHAMPS_CONTENU[0], renc, "espece:"), (zones.CHAMPS_CONTENU[1], ress, "item:")):
			defauts = [dict(d) for d in neuve.get(champ_defaut) or []]
			presents = {d.get(cle) for d in defauts}
			for brut in bruts:
				e = entree(brut, cle, prefixe)
				if e[cle] in presents:
					continue
				defauts.append(e)
				presents.add(e[cle])
				change = True
			if defauts or champ_defaut in neuve:
				neuve[champ_defaut] = defauts
		if change:
			# Même forme que celle qu'écrit /admin/zones : normalisation du moteur.
			for _, cle, champ_defaut in zones.CHAMPS_CONTENU:
				neuve[champ_defaut] = zones.normaliser_defauts(neuve.get(champ_defaut) or [], cle)
			out.append(neuve)
	return out


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	chemin = args.dump or dernier_dump()
	print(f"Dump : {os.path.relpath(chemin, RACINE)}")
	with open(chemin, encoding="utf-8") as f:
		docs = {d["_id"]: d for d in json.load(f)["docs"]}
	err = controler(docs)
	if err:
		sys.exit("Table invalide :\n  " + "\n  ".join(err))
	emis = zones_a_emettre(docs)
	if not emis:
		print("Rien à émettre : tout est déjà à jour.")
		return 0
	n_r = n_s = 0
	for z in emis:
		avant = docs[z["_id"]]
		for _, cle, champ_defaut in zones.CHAMPS_CONTENU:
			anciens = {d.get(cle) for d in avant.get(champ_defaut) or []}
			neufs = [d for d in z[champ_defaut] if d[cle] not in anciens]
			if cle == "espece":
				n_r += len(neufs)
			else:
				n_s += len(neufs)
	ids = [d["_id"] for d in emis]
	assert len(ids) == len(set(ids)), "collision d'_id dans la sortie"
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(emis, f, ensure_ascii=False, indent=1)
		f.write("\n")
	print(f"{len(emis)} zones complétées : +{n_r} rencontres, +{n_s} ressources")
	print(f"→ {os.path.relpath(args.sortie, RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
