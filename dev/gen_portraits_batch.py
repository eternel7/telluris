#!/usr/bin/env python
# dev/gen_portraits_batch.py
# Portraits des tenanciers d'une cité, générés par l'API BATCH de Gemini (−50 % du prix
# interactif, résultat sous 24 h). Gabarit : docs/prompts_images.md §2.
#
#   python dev/gen_portraits_batch.py preparer   [--cite lieu:rhemi] [--sauf lieu:x,lieu:y]
#   python dev/gen_portraits_batch.py soumettre  → envoie le lot (PAYANT)
#   python dev/gen_portraits_batch.py etat       → état du lot
#   python dev/gen_portraits_batch.py recuperer  → écrit les images dans templates/resources/pnj/
#   python dev/gen_portraits_batch.py appliquer  → jsons/portraits_<cite>_a_importer.json
#
# Tout l'état vit dans dev/batch/<cite>/ (requetes.jsonl + manifeste.json) : chaque étape
# reprend là où la précédente s'est arrêtée, même d'une session à l'autre.
#
# ⚠️ Le NOM du tenancier n'est jamais dans le prompt (le modèle l'a recopié en signature) ;
# aucune image de référence (le modèle la recopie). Cf. docs/prompts_images.md §2.
# ⚠️ Aucune image existante n'est écrasée : prochain `…NN` libre. Format natif du modèle
# (Flash Lite → .jpg) — seuls les monstres exigent du PNG.
# ⚠️ `appliquer` relit le dump le plus récent et ne change QUE `pnj[0].portrait` : l'import
# est un PUT complet (CLAUDE.md §11), les stocks garnis depuis par le tick survivent.
# La clé GEMINI_API_KEY est lue dans l'environnement (ou le registre Windows), jamais affichée.

import argparse
import base64
import glob
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_PNJ = os.path.join(RACINE, "templates", "resources", "pnj")
API = "https://generativelanguage.googleapis.com"
MODELE = "gemini-3.1-flash-lite-image"
RATIO = "16:9"
GRAINE = 20261008

# Coût réellement observé le 08/10/2026 : 0,16 € pour 4 portraits interactifs → ~0,04 €
# l'image ; le batch en coûte la moitié.
EUR_PAR_IMAGE_INTERACTIF = 0.04
REMISE_BATCH = 0.5

PORTRAIT_GENERIQUE = re.compile(r"^marchand_(elfe|hobbit|humaine?|nain|ogre)_([mf])_")

# Lignée : repère reconnaissable, jamais une règle de corps (docs/prompts_images.md §2).
LIGNEES = {
	"nain": ("Une naine", "Un nain",
			 "nettement plus petit{e} qu'un humain — un humain se tient au même plan, et {il} lui arrive à peine à la taille —, tête et mains grandes pour sa taille"),
	"hobbit": ("Une hobbit", "Un hobbit",
			   "de toute petite taille d'adulte, pieds nus — un humain au même plan le{a} dépasse de deux têtes"),
	"elfe": ("Une elfe", "Un elfe", "aux oreilles longues et pointues"),
	# Jamais vert (consigne de l'auteur, 09/10).
	"ogre": ("Une ogresse", "Un ogre",
			 "bien plus grand{e} et massi{ve} qu'un humain, peau épaisse au teint humain, jamais verte — un humain au même plan lui arrive à la poitrine"),
	"humain": ("Une humaine", "Un humain", ""),
}
AGES = ["jeune", "dans la force de l'âge", "d'âge mûr", "âgé{e}", "très âgé{e}"]
CORPS = ["maigre", "sec{he}", "de corpulence ordinaire", "solide", "fort{e}", "bedonnant{e}", "voûté{e}"]
ALLURES = ["le regard vif", "l'air bourru", "le sourire facile", "l'œil méfiant", "l'air las mais aimable",
		   "le regard franc", "l'air rusé"]
CHEVEUX = ["aux cheveux noirs", "aux cheveux châtains", "aux cheveux roux", "aux cheveux blonds",
		   "aux cheveux gris", "aux cheveux blancs", "au crâne rasé", "aux cheveux tressés"]

# Métier : (qui il est, objet présenté, tenue, décor). Une ligne par catégorie de base.
METIERS = {
	"apothicairerie": ("tient une apothicairerie", "un petit flacon de remède ambré", "longue blouse tachée d'herbes, sacoche de simples", "étagères de bocaux, bouquets d'herbes séchées, mortier et pilon"),
	"armurerie": ("tient une armurerie", "une épée fraîchement forgée", "tablier de cuir roussi, avant-bras nus couverts de suie", "enclume, forge rougeoyante, râteliers d'armes et de cottes de mailles"),
	"atelier_d_artisan": ("tient un atelier d'artisan", "un coffret de bois sculpté", "tablier de travail plein de copeaux", "établi, outils de menuisier, objets ouvragés en exposition"),
	"atelier_de_cirier": ("tient un atelier de cirier", "un grand cierge de cire blonde", "tablier constellé de gouttes de cire", "cuves de cire, grappes de chandelles suspendues, rayons de miel"),
	"atelier_de_l_empenneur": ("tient un atelier d'empenneur", "une flèche finement empennée", "tablier, plumes piquées au col", "faisceaux de flèches, bottes de plumes, fûts de bois droits"),
	"bijouterie": ("tient une bijouterie", "une bague sertie d'une pierre", "vêtements fins, loupe de bijoutier au cou", "comptoir garni d'écrins, balance de précision, petits bijoux"),
	"boucherie": ("tient une boucherie", "un beau quartier de viande", "tablier taché, couperet à la ceinture", "crochets de viandes suspendues, billot de bois, étal"),
	"boulangerie": ("tient une boulangerie", "une miche de pain doré", "tablier enfariné, manches retroussées", "four à pain, corbeilles de pains et de brioches"),
	"bourrellerie": ("tient une bourrellerie", "un collier de cheval en cuir", "tablier de cuir, alêne à la ceinture", "harnais, selles et sangles pendus aux murs"),
	"boyauderie": ("tient une boyauderie", "un écheveau de corde de boyau", "tablier de cuir humide", "bacs de trempage, cordes de boyau qui sèchent sur des perches"),
	"brosserie": ("tient une brosserie", "une brosse à poils de sanglier", "tablier de toile", "brosses, balais et pinceaux de toutes tailles"),
	"corderie": ("tient une corderie", "un rouleau de corde de chanvre", "vêtements de toile, mains calleuses", "rouet de cordier, rouleaux de cordages"),
	"cordonnerie": ("tient une cordonnerie", "une paire de bottes neuves", "tablier de cuir, marteau de cordonnier", "formes à chaussures, établi, bottes alignées"),
	"cuisine": ("tient une cuisine", "un bol de ragoût fumant", "tablier noué, torchon sur l'épaule", "marmites sur le feu, broche, tables de voyageurs"),
	"etable": ("tient une étable", "un licol de cuir neuf aux boucles de laiton", "tablier de cuir, manches retroussées, brins de paille", "stalles de bois, bottes de foin, une mule et un poney"),
	"fletcher": ("tient une archerie", "un arc long de bois d'if", "brassard de cuir, carquois à l'épaule", "arcs suspendus, flèches en faisceaux, cibles de paille"),
	"fumoir": ("tient un fumoir", "un jambon fumé", "tablier noirci par la fumée", "viandes et poissons pendus dans la fumée, foyer couvant"),
	"jardinier": ("tient une jardinerie", "un panier de légumes frais", "chapeau de paille, tablier de toile terreux", "pots de plantes, semis, outils de jardin"),
	"laboratoire_d_alchimie": ("tient un laboratoire d'alchimie", "une fiole au liquide luminescent", "robe tachée, lunettes de protection relevées sur le front", "alambics, cornues, grimoires ouverts"),
	"lutherie": ("tient une lutherie", "un luth au bois verni", "tablier de luthier, copeaux fins", "instruments suspendus, gabarits, pots de vernis"),
	"maroquinerie": ("tient une maroquinerie", "une sacoche de cuir ouvragé", "tablier de cuir, aiguilles à la ceinture", "bourses, ceintures, sacoches en exposition"),
	"necromancie": ("tient une boutique de nécromancie", "un crâne gravé de runes", "robe sombre, amulettes d'os", "ossements, bougies noires, bocaux troubles, grimoires"),
	"negociant": ("tient une maison de négoce", "une bourse pleine et une balance", "vêtements de marchand aisé, chaîne au cou", "coffres, ballots de marchandises, registres de comptes"),
	"plumasserie": ("tient une plumasserie", "un éventail de plumes chatoyantes", "vêtements soignés, plume au chapeau", "plumes multicolores en bouquets, chapeaux ornés"),
	"salaison": ("tient une salaison", "un saucisson sec", "tablier, mains rougies par le sel", "tonneaux de sel, jambons et saucissons pendus"),
	"savonnerie": ("tient une savonnerie", "un pain de savon parfumé", "tablier clair, manches retroussées", "pains de savon empilés, chaudron, fioles de parfum"),
	"scriptorium": ("tient un scriptorium", "un livre relié de cuir", "robe de scribe, doigts tachés d'encre", "pupitres, encriers, parchemins, piles de livres"),
	"tabletterie": ("tient une tabletterie", "un jeu d'échecs en os et ivoire", "tablier fin, loupe", "petits objets d'os et d'ivoire, peignes, dés, boîtes"),
	"tannerie": ("tient une tannerie", "une peau tannée souple", "tablier de cuir épais, bottes hautes", "peaux tendues sur des cadres, cuves de tan"),
	"taxidermie": ("tient un cabinet de taxidermie", "un renard naturalisé", "blouse de travail, outils fins", "animaux naturalisés, têtes de cerfs, bocaux de spécimens"),
	"tissage": ("tient un atelier de tissage", "une étoffe richement tissée", "vêtements de toile fine", "métier à tisser, rouleaux d'étoffes colorées"),
}

# Style d'Auxerre (§0.1), préféré par l'auteur au photoréaliste du lot de Rhemi (09/10) : même
# rendu que les façades de dev/gen_images_magasins.py, où ce portrait part en référence.
STYLE = ("Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de "
		 "gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse "
		 "relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image "
		 "entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun "
		 "monogramme, aucun filigrane, aucune enseigne lisible.")
# §0.2 (phrase de l'auteur, telle quelle) + la variété de la foule d'Auxerre : sans elle, des
# figurants identiques (lot de Rhemi, 09/10). Ogres jamais verts.
FOULE = ("Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, "
		 "chacun différent par l'âge, la carrure, les cheveux et la tenue : elfes bruns, roux, noirs, "
		 "argentés ou blonds, en robe, cape de voyage ou cuir ; nains barbus ou tressés, en armure, "
		 "tablier ou habit de marchand ; hobbits ronds ou fluets, jeunes ou ridés, en gilets colorés ; "
		 "ogres aux teints humains, burinés, rougeauds ou hâlés, jamais verts ; humains de toutes "
		 "origines, aventuriers, gardes, marchands, pèlerins.")


def _accord(texte, f):
	return (texte.replace("{e}", "e" if f else "").replace("{he}", "he" if f else "")
			.replace("{ve}", "ve" if f else "f").replace("{il}", "elle" if f else "il")
			.replace("{a}", "a" if f else ""))


def prompt_tenancier(race, sexe, categorie, cite_nom, rng):
	"""PURE. Prompt du gabarit §2 pour un tenancier (aucun nom propre)."""
	f = sexe == "F"
	une_f, un_m, marqueur = LIGNEES.get(race, LIGNEES["humain"])
	qui, objet, tenue, decor = METIERS[categorie]
	corps = ", ".join([_accord(rng.choice(AGES), f), _accord(rng.choice(CORPS), f),
					   rng.choice(CHEVEUX), rng.choice(ALLURES)])
	il = "Elle" if f else "Il"
	sujet = f"{une_f if f else un_m} {corps}" + (f", {_accord(marqueur, f)}" if marqueur else "")
	# ⚠️ 1re phrase sans « . » interne : `gen_images_magasins.traits_du_portrait` lit la 2e.
	return (f"Portrait illustré d'un personnage de fantasy médiévale, format paysage large. "
			# Pas de « Telluris » : le mot finissait peint en enseigne (essai des façades, 08/10).
			f"{sujet}. {il} {qui} à {cite_nom}, dans un monde médiéval fantastique. "
			f"{il} se tient légèrement décalé{'e' if f else ''} du centre et regarde droit vers le spectateur "
			f"avec l'assurance d'un{'e' if f else ''} commerçant{'e' if f else ''} ; {il.lower()} lui présente {objet}. "
			f"Tenue de travail usée et crédible : {tenue}. Décor de part et d'autre : {decor}. "
			f"{FOULE} {STYLE}")


def nom_libre(dossier, base, ext, pris=()):
	"""Prochain `base01.ext`, `base02.ext`… dont le NOM SANS EXTENSION est absent du disque ET
	de `pris` : `…01.png` existant interdit aussi `…01.jpg` (jamais d'écrasement, jamais deux
	fichiers au même nom)."""
	tiges = {os.path.splitext(f)[0] for f in os.listdir(dossier)} | {os.path.splitext(p)[0] for p in pris}
	n = 1
	while f"{base}{n:02d}" in tiges:
		n += 1
	return f"{base}{n:02d}{ext}"


# ── E/S ─────────────────────────────────────────────────────────────────────────

def _dump_le_plus_recent():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json.")
	return dumps[-1]


def _docs(chemin):
	with open(chemin, encoding="utf-8") as f:
		d = json.load(f)
	return d["docs"] if isinstance(d, dict) and "docs" in d else d


def _cle():
	k = os.environ.get("GEMINI_API_KEY")
	if not k and sys.platform == "win32":
		import winreg
		with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
			k = winreg.QueryValueEx(h, "GEMINI_API_KEY")[0]
	if not k:
		raise SystemExit("ERREUR : GEMINI_API_KEY absente.")
	return k


def _http(url, corps=None, entetes=None, methode=None, brut=False):
	donnees = corps if isinstance(corps, (bytes, type(None))) else json.dumps(corps).encode()
	h = {"x-goog-api-key": _cle(), **({"Content-Type": "application/json"} if donnees and not brut else {}),
		 **(entetes or {})}
	req = urllib.request.Request(url, data=donnees, headers=h, method=methode or ("POST" if donnees else "GET"))
	try:
		with urllib.request.urlopen(req, timeout=300) as r:
			return r.headers, r.read()
	except urllib.error.HTTPError as e:
		raise SystemExit(f"HTTP {e.code} : {e.read().decode('utf-8', 'replace')[:800]}")


def _dossier(cite):
	d = os.path.join(RACINE, "dev", "batch", cite.split(":", 1)[-1])
	os.makedirs(d, exist_ok=True)
	return d


def _manifeste(cite, nouveau=None):
	chemin = os.path.join(_dossier(cite), "manifeste.json")
	if nouveau is not None:
		with open(chemin, "w", encoding="utf-8") as f:
			json.dump(nouveau, f, ensure_ascii=False, indent="\t")
		return nouveau
	if not os.path.exists(chemin):
		raise SystemExit("ERREUR : lancer d'abord `preparer`.")
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


# ── Étapes ──────────────────────────────────────────────────────────────────────

def preparer(cite, sauf):
	docs = _docs(_dump_le_plus_recent())
	lieux = {d["_id"]: d for d in docs if d.get("type") == "lieu"}
	# Boutiques pas encore importées : complétées depuis l'import du peuplement (le dump prime).
	imp = os.path.join(RACINE, "jsons", f"{cite.split(':', 1)[-1]}_magasins_a_importer.json")
	if os.path.exists(imp):
		for d in _docs(imp):
			if d.get("type") == "lieu":
				lieux.setdefault(d["_id"], d)
	cite_nom = (lieux.get(cite) or {}).get("label") or cite.split(":", 1)[-1].capitalize()
	if not (lieux.get(cite) or {}).get("label"):
		cite_nom = {"lieu:rhemi": "Reims"}.get(cite, cite_nom)
	rng = random.Random(GRAINE)
	entrees, ignores = [], []
	for lid, lieu in sorted(lieux.items()):
		if lieu.get("lieu_parent") != cite or lid in sauf:
			continue
		pnj = (lieu.get("pnj") or [{}])[0]
		m = PORTRAIT_GENERIQUE.match(str(pnj.get("portrait") or ""))
		cat = lieu.get("categorie")
		if not m or cat not in METIERS:
			ignores.append(f"{lid} ({cat}, portrait {pnj.get('portrait')})")
			continue
		race = "humain" if m.group(1) == "humaine" else m.group(1)
		sexe = m.group(2).upper()
		entrees.append({"key": lid, "lieu": lid, "categorie": cat, "race": race, "sexe": sexe,
						"tenancier": pnj.get("nom"), "base": f"marchand_{race}_{sexe.lower()}_{cat}",
						"prompt": prompt_tenancier(race, sexe, cat, cite_nom, rng)})
	with open(os.path.join(_dossier(cite), "requetes.jsonl"), "w", encoding="utf-8") as f:
		for e in entrees:
			f.write(json.dumps({"key": e["key"], "request": {
				"contents": [{"parts": [{"text": e["prompt"]}]}],
				"generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": RATIO}},
			}}, ensure_ascii=False) + "\n")
	_manifeste(cite, {"cite": cite, "modele": MODELE, "entrees": entrees, "batch": None, "images": {}})
	unit = EUR_PAR_IMAGE_INTERACTIF * REMISE_BATCH
	print(f"{len(entrees)} portraits préparés → dev/batch/{cite.split(':', 1)[-1]}/requetes.jsonl")
	for i in ignores:
		print("  ignoré :", i)
	print(f"Estimation : {len(entrees)} × {unit:.3f} € ≈ {len(entrees) * unit:.2f} € "
		  f"(batch −50 % sur le coût observé de {EUR_PAR_IMAGE_INTERACTIF:.2f} €/image)")


def soumettre_lot(chemin_jsonl, modele, nom_affiche):
	"""Envoie un fichier de requêtes JSONL à l'API batch (PAYANT) ; rend le nom du lot.
	Partagé avec dev/gen_images_magasins.py."""
	octets = open(chemin_jsonl, "rb").read()
	h, _ = _http(f"{API}/upload/v1beta/files", {"file": {"display_name": nom_affiche}}, {
		"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
		"X-Goog-Upload-Header-Content-Length": str(len(octets)),
		"X-Goog-Upload-Header-Content-Type": "application/jsonl"})
	_, rep = _http(h["x-goog-upload-url"], octets, {"X-Goog-Upload-Offset": "0",
												   "X-Goog-Upload-Command": "upload, finalize"}, brut=True)
	fichier = json.loads(rep)["file"]["name"]
	_, rep = _http(f"{API}/v1beta/models/{modele}:batchGenerateContent",
				   {"batch": {"display_name": nom_affiche, "input_config": {"file_name": fichier}}})
	return json.loads(rep)["name"]


def statut_lot(lot):
	_, rep = _http(f"{API}/v1beta/{lot}")
	return json.loads(rep)


def image_de_reponse(reponse):
	"""PURE. La première partie `inlineData` d'une réponse `generateContent`, ou None."""
	return next((p for c in (reponse or {}).get("candidates", [])
				 for p in (c.get("content") or {}).get("parts", []) if "inlineData" in p), None)


def reponses_lot(lot):
	"""[(clé, partie inlineData | None, ligne brute)] d'un lot terminé ; SystemExit sinon."""
	s = statut_lot(lot)
	meta = s.get("metadata") or {}
	# L'API répond `BATCH_STATE_*` (constaté le 08/10/2026) ; la doc écrit `JOB_STATE_*`.
	if meta.get("state") not in ("BATCH_STATE_SUCCEEDED", "JOB_STATE_SUCCEEDED") and not s.get("done"):
		raise SystemExit(f"Lot pas terminé : {meta.get('state')}")
	rep = (s.get("response") or {}).get("responsesFile") or ((meta.get("output") or {}).get("responsesFile"))
	if not rep:
		raise SystemExit("Aucun fichier de réponses : " + json.dumps(s)[:600])
	_, brut = _http(f"{API}/download/v1beta/{rep}:download?alt=media")
	sortie = []
	for ligne in brut.decode("utf-8").splitlines():
		if ligne.strip():
			r = json.loads(ligne)
			sortie.append((r.get("key"), image_de_reponse(r.get("response")), r))
	return sortie


def afficher_etat(lot):
	s = statut_lot(lot)
	meta = s.get("metadata") or s
	print(lot, "→", meta.get("state"), "| stats :", meta.get("batchStats"))


def soumettre(cite):
	man = _manifeste(cite)
	if man.get("batch"):
		raise SystemExit(f"Déjà soumis : {man['batch']} — `etat` pour suivre.")
	man["batch"] = soumettre_lot(os.path.join(_dossier(cite), "requetes.jsonl"), man["modele"], f"portraits-{cite}")
	_manifeste(cite, man)
	print("Lot soumis :", man["batch"])


def etat(cite):
	man = _manifeste(cite)
	if not man.get("batch"):
		raise SystemExit("Pas encore soumis.")
	afficher_etat(man["batch"])


def recuperer(cite):
	man = _manifeste(cite)
	par_cle = {e["key"]: e for e in man["entrees"]}
	pris, ecrites, erreurs = set(man["images"].values()), 0, []
	for cle, part, r in reponses_lot(man["batch"]):
		if cle in man["images"] or cle not in par_cle:
			continue
		if not part:
			erreurs.append(f"{cle} : {json.dumps(r.get('error') or r)[:200]}")
			continue
		ext = ".jpg" if "jpeg" in part["inlineData"].get("mimeType", "") else ".png"
		nom = nom_libre(DOSSIER_PNJ, par_cle[cle]["base"], ext, pris)
		with open(os.path.join(DOSSIER_PNJ, nom), "wb") as f:
			f.write(base64.b64decode(part["inlineData"]["data"]))
		pris.add(nom)
		man["images"][cle] = nom
		ecrites += 1
	_manifeste(cite, man)
	print(f"{ecrites} image(s) écrite(s) dans templates/resources/pnj/ ; {len(erreurs)} échec(s)")
	for e in erreurs:
		print("  ✗", e)


def appliquer(cite):
	man = _manifeste(cite)
	docs = {d["_id"]: d for d in _docs(_dump_le_plus_recent())}
	sortie, absents = [], []
	for cle, nom in sorted(man["images"].items()):
		doc = docs.get(cle)
		if not doc:
			absents.append(cle)
			continue
		doc = json.loads(json.dumps(doc))
		doc["pnj"][0]["portrait"] = nom
		sortie.append(doc)
	chemin = os.path.join(RACINE, "jsons", f"portraits_{cite.split(':', 1)[-1]}_a_importer.json")
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"{len(sortie)} lieu(x) → {os.path.relpath(chemin, RACINE)}")
	if absents:
		print(f"⚠ {len(absents)} lieu(x) absents du dump (lot pas encore importé ?) : exporter un dump puis relancer.")


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	p = argparse.ArgumentParser()
	p.add_argument("etape", choices=["preparer", "soumettre", "etat", "recuperer", "appliquer"])
	p.add_argument("--cite", default="lieu:rhemi")
	p.add_argument("--sauf", default="", help="lieux à exclure, séparés par des virgules")
	a = p.parse_args()
	if a.etape == "preparer":
		preparer(a.cite, {s for s in a.sauf.split(",") if s})
	else:
		{"soumettre": soumettre, "etat": etat, "recuperer": recuperer, "appliquer": appliquer}[a.etape](a.cite)


if __name__ == "__main__":
	main()
