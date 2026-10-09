#!/usr/bin/env python
# dev/gen_images_magasins.py
# Façade de chaque boutique (et auberge) d'une cité. Gabarit : docs/prompts_images.md §1 bis.
# Génération par GEMINI (défaut), le PORTRAIT du tenancier joint à la requête, avant le prompt
# (« image 1 ») : c'est bien LE marchand de la boutique. Une auberge n'a pas de tenancier.
#
#   python dev/gen_images_magasins.py preparer  [--cite lieu:rhemi] [--sauf lieu:x,lieu:y]
#   python dev/gen_images_magasins.py essai     [--seulement …] [--limite N]  → interactif, essais/
#   python dev/gen_images_magasins.py soumettre → lot batch Gemini (PAYANT, −50 %)
#   python dev/gen_images_magasins.py etat | recuperer → images dans templates/resources/towns/
#   python dev/gen_images_magasins.py appliquer → jsons/images_magasins_<cite>_a_importer.json
#
# Repli local gratuit : `generer [--essai]` (ComfyUI + FLUX.2 Klein, magasins seulement).
# `generer` exige le serveur ComfyUI lancé par C:\ComfyUI_windows_portable\run_telluris.bat :
# `--bf16-text-enc` (l'encodeur Qwen3 déborde en fp16 → NaN, image de bruit),
# `--fp32-vae`, `--disable-smart-memory` (tout déchargé après chaque image).
# Tout l'état vit dans dev/batch/<cite>/magasins/manifeste.json, sauvé après CHAQUE image :
# une interruption ne perd rien, le rejeu reprend où il s'était arrêté.
#
# ⚠️ Prompt en ANGLAIS, en phrases (encodeur Qwen3) ; Z-Image Turbo n'a PAS de prompt négatif
# (CFG 1) : les exclusions — aucun texte — s'écrivent dans le prompt lui-même.
# ⚠️ Aucun NOM dans le prompt, ni boutique ni tenancier : le modèle le peint en enseigne.
# ⚠️ Le modèle ne reprend pas un personnage d'une image : le tenancier est DÉCRIT par les traits
# tirés pour son portrait (dev/batch/<cite>/manifeste.json), relus seulement si le portrait
# en base est bien celui de ce manifeste.
# ⚠️ Aucune image existante n'est écrasée : prochain `…NN` libre (`nom_libre`).
# ⚠️ `appliquer` relit le dump le plus récent et ne change QUE `image` (import = PUT complet).

import argparse
import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.gen_portraits_batch import (AGES, ALLURES, API, CHEVEUX, CORPS, EUR_PAR_IMAGE_INTERACTIF,
	METIERS, PORTRAIT_GENERIQUE, RATIO, REMISE_BATCH, _accord, _docs, _dump_le_plus_recent, _http,
	afficher_etat, image_de_reponse, nom_libre, reponses_lot, soumettre_lot)
from dev.gen_portraits_batch import MODELE as MODELE_GEMINI

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_TOWNS = os.path.join(RACINE, "templates", "resources", "towns")

COMFY = "http://127.0.0.1:8188"
DOSSIER_PNJ = os.path.join(RACINE, "templates", "resources", "pnj")
# FLUX.2 Klein 4B distillé, graphe du modèle officiel ComfyUI `image_flux2_klein_image_edit_4b_
# distilled` : le PORTRAIT du tenancier part en image de référence (`ReferenceLatent`), pour que
# ce soit bien LE marchand de la boutique. Écartés : DreamShaper XL (08/10, lignées ignorées,
# foule absente) et Z-Image Turbo (09/10, bon rendu mais sans image de référence possible).
# Poids fp8 (~4 Go) : l'iGPU plafonne à 14,4 Go et annonce 0 Go libre dès qu'on en tient ~10
# (`torch.cuda.mem_get_info`, mesuré le 08/10).
MODELE = "flux-2-klein-4b-fp8.safetensors"
ENCODEUR = "qwen_3_4b_fp8_mixed.safetensors"
VAE = "flux2-vae.safetensors"
# 16:9, la taille des images de `towns/`.
LARGEUR, HAUTEUR = 1408, 768
PAS, CFG, SAMPLER = 4, 1.0, "euler"

# Métier : (boutique, marchandises exposées). Mêmes catégories que `METIERS` (verrouillé par test).
METIERS_EN = {
	"apothicairerie": ("apothecary shop", "shelves of jars and vials, bunches of dried herbs, mortar and pestle"),
	"armurerie": ("armorer's forge and shop", "racks of swords and spears, chainmail shirts, helmets, glowing forge"),
	"atelier_d_artisan": ("woodcarver's workshop", "carved wooden boxes, bowls and chairs, workbench with tools"),
	"atelier_de_cirier": ("chandler's workshop", "bunches of hanging candles, large wax tapers, vats of wax, honeycombs"),
	"atelier_de_l_empenneur": ("fletcher's workshop", "bundles of arrows, sheaves of feathers, straight wooden shafts"),
	"bijouterie": ("jeweler's shop", "counter with open jewel cases, rings, necklaces, small precision scale"),
	"boucherie": ("butcher's shop", "meat hanging from hooks, wooden chopping block, cuts of meat on the stall"),
	"boulangerie": ("bakery", "baskets of golden loaves and brioches, bread oven glowing inside"),
	"bourrellerie": ("saddler's and harness maker's shop", "saddles, harnesses, horse collars and straps hanging on the walls"),
	"boyauderie": ("gut-string maker's workshop", "gut strings drying on poles, soaking tubs"),
	"brosserie": ("brush maker's shop", "brushes, brooms and paintbrushes of every size"),
	"corderie": ("rope maker's workshop", "coils of hemp rope, rope-making wheel"),
	"cordonnerie": ("cobbler's shop", "rows of leather boots and shoes, shoe lasts, workbench"),
	"cuisine": ("cookshop", "pots on the fire, roasting spit, steaming stew bowls, tables for travelers"),
	"etable": ("stable", "wooden stalls, hay bales, a mule and a pony, harnesses"),
	"fletcher": ("bowyer and fletcher shop", "longbows hanging, bundles of arrows, quivers, straw targets"),
	"fumoir": ("smokehouse", "hams, sausages and fish hanging in the smoke, smoldering hearth"),
	"jardinier": ("gardener's shop", "potted plants, seedlings, baskets of vegetables, garden tools"),
	"laboratoire_d_alchimie": ("alchemist's laboratory", "alembics, retorts, glowing vials, open grimoires"),
	"lutherie": ("luthier's workshop", "lutes, fiddles and harps hanging, varnish pots"),
	"maroquinerie": ("leather goods shop", "leather bags, purses, belts and satchels on display"),
	"necromancie": ("necromancer's shop", "skulls, bones, black candles, murky jars, dark grimoires"),
	"negociant": ("merchant trading house", "chests, bales of goods, barrels, ledgers and a balance scale"),
	"plumasserie": ("plumassier's shop", "bouquets of colorful feathers, plumed hats, feather fans"),
	# « barrels of salt » → des sacs marqués « SALT » (lot du 09/10).
	"salaison": ("salting house", "open barrels heaped with coarse white salt, hanging hams and dry sausages"),
	"savonnerie": ("soap maker's shop", "stacked bars of soap, cauldron, perfume flasks"),
	"scriptorium": ("scriptorium and bookshop", "writing desks, inkwells, parchments, stacks of leather-bound books"),
	"tabletterie": ("bone and ivory carver's shop", "carved combs, dice, chess sets, small bone boxes"),
	"tannerie": ("tannery", "hides stretched on frames, tanning vats"),
	"taxidermie": ("taxidermist's cabinet", "stuffed animals, deer heads, specimen jars"),
	"tissage": ("weaver's workshop", "loom, rolls of colorful fabric"),
}

# Toponymes d'enseigne → décor de la rue (`{precision_lieu}` + `{repere_cite}` du §1). Clés =
# `TOPONYMES_PAR_LIEU[cite]` (verrouillé par test). Repères réels, aucun symbole religieux.
QUARTIERS_EN = {
	"lieu:rhemi": {
		"du Sacre": "on the square in front of the great gothic cathedral of Reims, its towers rising behind",
		"de la Vesle": "on a quay along the river Vesle, water and a stone bridge nearby",
		"des Coteaux": "on a sloping street of Reims, vineyard hills visible in the distance beyond the ramparts",
		"de la Porte de Mars": ("beside the Porte de Mars, an ancient Roman triumphal arch: three round "
								"classical arches with carved columns, Roman and not gothic"),
		"du Chapitre": "in a narrow lane of old canons' houses at the foot of the gothic cathedral of Reims",
		"des Crayères": "near the entrances of chalk cellars dug into white chalk",
		"du Vieux Cloître": "beside the arcades of an old romanesque cloister",
	},
	"lieu:chartres": {
		"de la Porte Guillaume": ("beside the Porte Guillaume, a fortified city gate flanked by two round "
								  "towers, its bridge crossing the river Eure"),
		"de l'Eure": "on a quay along the river Eure, wash-houses and small wooden footbridges over the water",
		"de la Basse-Ville": ("in a steep lane of the lower town, stone stairways climbing toward the "
							  "great cathedral of Chartres on its hill"),
		"du Cloître": ("in the close at the foot of the great gothic cathedral of Chartres, its two "
					   "mismatched spires, one plain and one ornate, rising behind"),
		"du Tertre": "on a steep stepped street running down the hillside, roofs of the lower town below",
		"de Saint-André": "beside a large old romanesque church on the bank of the river Eure",
		"du Pont Bouju": "beside an old stone bridge with low arches over the river Eure",
		"des Épars": "on a wide market square at the edge of the town, near the ramparts",
	},
}

# Lignée : (homme, femme, repère d'échelle) — repère reconnaissable, jamais une règle de corps.
LIGNEES_EN = {
	# Échelle VISIBLE : en photoréaliste, « plus petit » seul ne suffit pas (essai du 09/10 : un
	# nain rendu en humain trapu) — on le compare aux humains qui passent.
	"nain": ("a dwarf man", "a dwarf woman", "so short that the head only reaches the waist of the humans walking past, large head and hands for the size"),
	"hobbit": ("a halfling man", "a halfling woman", "a grown adult with an adult face, barely reaching the hips of the humans around, barefoot with large hairy feet"),
	"elfe": ("an elf man", "an elf woman", "ears only slightly elongated to a subtle point"),
	"ogre": ("an ogre man", "an ogress woman", "towering head and shoulders above the humans around, massive, thick human-toned skin never green, dressed in work clothes"),
	"humain": ("a human man", "a human woman", ""),
}

# Traits du portrait (gabarits de `gen_portraits_batch`, accordés aux deux sexes à la lecture).
TRAITS_EN = {
	"jeune": "young",
	"dans la force de l'âge": "in the prime of life",
	"d'âge mûr": "middle-aged",
	"âgé{e}": "old",
	"très âgé{e}": "very old",
	"maigre": "skinny",
	"sec{he}": "wiry",
	"de corpulence ordinaire": "of average build",
	"solide": "sturdy",
	"fort{e}": "strong",
	"bedonnant{e}": "pot-bellied",
	"voûté{e}": "stooped",
	"aux cheveux noirs": "black hair",
	"aux cheveux châtains": "brown hair",
	"aux cheveux roux": "red hair",
	"aux cheveux blonds": "blond hair",
	"aux cheveux gris": "grey hair",
	"aux cheveux blancs": "white hair",
	"au crâne rasé": "shaved head",
	"aux cheveux tressés": "braided hair",
	"le regard vif": "sharp eyes",
	"l'air bourru": "gruff look",
	"le sourire facile": "easy smile",
	"l'œil méfiant": "wary eyes",
	"l'air las mais aimable": "tired but kindly look",
	"le regard franc": "frank gaze",
	"l'air rusé": "cunning look",
}
_TRAITS_ACCORDES = {_accord(fr, f): en for fr, en in TRAITS_EN.items() for f in (False, True)}

# §0.2 et §0.1 traduits ; la consigne « aucun texte » DOIT être ici (pas de prompt négatif).
# Chaque lignée avec un trait VISIBLE : la phrase nue ne donnait que des humains.
# Essai du 09/10 : « long pointed ears » → des oreilles en cornes ; « tiny halflings » → un bambin.
# Lot de Rhemi (09/10) : « as in the Lord of the Rings films » → costumes de film en série (hobbits
# tous en gilet vert, elfes tous blonds, ogres tous chauves torse nu). L'auteur préfère la foule
# d'Auxerre : chaque passant DIFFÉRENT — d'où les variations explicites par lignée.
FOULE = ("A lively, varied crowd of ogres, dwarves, halflings, elves and humans goes about its business in "
		 "the street, every passer-by different in age, build, hair and outfit, never the same costume "
		 "twice: elves with fine faces and slightly pointed ears, with dark, auburn, black, silver or fair "
		 "hair, in rich robes, travel cloaks or elegant leather armor; dwarves only waist-high to the "
		 "humans, with red, black, grey or white beards or braids, in plate armor, smith's aprons or "
		 "merchant clothes; halflings the height of a human child but grown adults with adult faces, "
		 "plump or slim, young or wrinkled, barefoot with curly hair, in colorful waistcoats and skirts, "
		 # Jamais verts (consigne de l'auteur, 09/10) : les teints restent humains, en plus rude.
		 "never children or babies; huge ogres with human skin tones, weathered, ruddy, tanned or ashen, "
		 "never green, in "
		 "tunics, furs or armor, towering over the crowd; humans of every origin: adventurers, guards, "
		 "merchants, pilgrims, peasants. Everyone wears medieval clothing; nothing modern.")
# Style d'Auxerre (§0.1), préféré par l'auteur au photoréaliste du lot de Rhemi (09/10).
STYLE = ("Detailed semi-realistic medieval fantasy illustration in the style of a high-end narrative 2D "
		 "RPG: rich digital painting, warm natural light, warm earthy palette with touches of vivid color "
		 "in clothes, awnings and banners, believable proportions, lots of lively detail. Not a photograph. "
		 "Every building is medieval, stone and timber-framed; nothing modern. "
		 "No text anywhere in the image: no letters, no inscription, no readable sign, no lettering on "
		 "banners or awnings, no logo, no signature, no watermark.")


# ── Partie pure ─────────────────────────────────────────────────────────────────

def traits_du_portrait(prompt_fr):
	"""PURE. Traits anglais relus dans un prompt de portrait (`gen_portraits_batch.prompt_tenancier`) :
	sa 2e phrase est « {Un nain} {âge}, {corps}, {cheveux}, {allure}[, repère] ». Un trait inconnu
	est ignoré ; un prompt méconnaissable (portrait fait à la main) rend []."""
	phrases = (prompt_fr or "").split(". ")
	if len(phrases) < 2:
		return []
	sujet = phrases[1].split(" ", 2)
	if len(sujet) < 3:
		return []
	return [_TRAITS_ACCORDES[p] for p in sujet[2].split(", ") if p in _TRAITS_ACCORDES]


def quartier_de(label, cite):
	"""PURE. Le toponyme d'enseigne qui termine `label` (le plus long gagne), ou None."""
	for t in sorted(QUARTIERS_EN.get(cite, {}), key=len, reverse=True):
		if (label or "").endswith(" " + t):
			return t
	return None


def prompt_magasin(categorie, race, sexe, traits, cite, cite_nom, label):
	"""PURE. Prompt du gabarit §1 bis, en phrases. Ni le nom de la boutique ni celui du tenancier.
	Le tenancier EST la personne de l'image 1 (son portrait, joint en référence) ; lignée et traits
	— ceux qui ont servi à générer ce portrait — ne font que la confirmer."""
	boutique, marchandises = METIERS_EN[categorie]
	homme, femme, repere = LIGNEES_EN.get(race, LIGNEES_EN["humain"])
	t = quartier_de(label, cite)
	lieu = QUARTIERS_EN[cite][t] if t else f"in a street of the walled city of {cite_nom}"
	tenancier = ", ".join([homme if sexe == "M" else femme] + list(traits) + ([repere] if repere else []))
	# Pas de « Telluris » : comme un nom de boutique, le mot finissait peint en enseigne (08/10).
	# Le portrait le montre face à nous, souriant, qui vend ; la boutique le montre AU TRAVAIL :
	# lot du 09/10, la pose du portrait était recopiée (consigne de l'auteur).
	return (f"The person shown in image 1 is the shopkeeper: keep exactly the same face, hair, beard, "
			f"body, skin and clothes as in image 1 ({tenancier}), but NOT the same pose or expression. "
			f"Do not reuse the background of image 1. Show this shopkeeper at work at the open front and "
			f"market stall of a medieval fantasy {boutique} in the city of {cite_nom}, {lieu}, busy with "
			f"the trade, absorbed in the task, not looking at the camera, not posing, not presenting "
			f"anything to the viewer. The shop fills about 80% of "
			f"the image, seen from the street in a three-quarter view; its goods are displayed on racks "
			f"and tables and are immediately recognizable: {marchandises}. {FOULE} {STYLE}")


# Auberges dont l'enseigne ne finit pas par un toponyme (`quartier_de` lit les autres).
QUARTIERS_AUBERGES = {
	"lieu:au_bon_vigneron": "des Coteaux",
	"lieu:la_crayere": "des Crayères",
	"lieu:aux_deux_fleches": "du Cloître",
	"lieu:le_relais_de_l_eure": "de l'Eure",
	"lieu:au_grenier_de_beauce": "de la Porte Guillaume",
	"lieu:la_halte_des_pelerins": "de la Basse-Ville",
}


def prompt_auberge(cite, cite_nom, quartier):
	"""PURE. Façade d'auberge (§1 bis sans tenancier : aucun PNJ n'y est posté). Aucun nom propre."""
	lieu = QUARTIERS_EN.get(cite, {}).get(quartier) or f"in a street of the walled city of {cite_nom}"
	return (f"The front of a large medieval fantasy inn and tavern in the city of {cite_nom}, {lieu}. The inn "
			# Pas d'enseigne : « a hanging sign showing only a painted emblem » → faux texte peint ; sans
			# enseigne, il l'a écrit sur un bandeau de façade (essais du 09/10).
			f"fills about 80% of the image, seen from the street in a three-quarter view: a tall stone and "
			f"timber-framed building with bare facade beams — no hanging sign, no signboard, no name board "
			f"or plaque above the door —, wide open door and "
			f"windows revealing a warm firelit common room with long tables, travelers eating and drinking, "
			f"barrels and benches outside the door, a stable yard to one side. {FOULE} {STYLE}")


def requete_gemini(prompt, image_b64=None, mime="image/jpeg"):
	"""PURE. Corps `generateContent` : l'image jointe AVANT le texte (c'est l'« image 1 » du prompt)."""
	parts = ([{"inlineData": {"mimeType": mime, "data": image_b64}}] if image_b64 else []) + [{"text": prompt}]
	return {"contents": [{"parts": parts}],
			"generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": RATIO}}}


# Image ratée par le GPU (NaN dans le sampler) : gris uniforme ou bruit pur. Étalonné le 08/10 :
# bonnes images (générées ou de `towns/`) écart-type 50-78, écart entre voisins 5-10 ; gris
# uniforme écart-type 4,5 ; bruit écart entre voisins ~45.
SEUIL_ECART_TYPE, SEUIL_VOISINS = 15, 25


def image_degeneree(ecart_type, ecart_voisins):
	"""PURE. Motif du rejet d'une image (écart-type et écart moyen entre pixels voisins, en
	niveaux de gris 0-255), ou None si elle est plausible."""
	if ecart_type < SEUIL_ECART_TYPE:
		return "uniforme"
	if ecart_voisins > SEUIL_VOISINS:
		return "bruit"
	return None


def base_image(image, cite):
	"""PURE. `archerie_europe01.png` → `archerie_europe_rhemi` (cf. `auberge_europe_lutecia*`)."""
	tige = re.sub(r"\d*$", "", os.path.splitext(image or "")[0]).rstrip("_")
	return f"{tige}_{cite.split(':', 1)[-1]}"


# ── E/S ─────────────────────────────────────────────────────────────────────────

def _slug(cite):
	return cite.split(":", 1)[-1]


def _chemin_manifeste(cite):
	d = os.path.join(RACINE, "dev", "batch", _slug(cite), "magasins")
	os.makedirs(d, exist_ok=True)
	return os.path.join(d, "manifeste.json")


def _manifeste(cite, nouveau=None):
	chemin = _chemin_manifeste(cite)
	if nouveau is not None:
		with open(chemin, "w", encoding="utf-8") as f:
			json.dump(nouveau, f, ensure_ascii=False, indent="\t")
		return nouveau
	if not os.path.exists(chemin):
		raise SystemExit("ERREUR : lancer d'abord `preparer`.")
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def _portraits(cite):
	"""Manifeste des portraits (gen_portraits_batch) : {lieu: (image, prompt)}."""
	chemin = os.path.join(RACINE, "dev", "batch", _slug(cite), "manifeste.json")
	if not os.path.exists(chemin):
		return {}
	with open(chemin, encoding="utf-8") as f:
		man = json.load(f)
	prompts = {e["key"]: e.get("prompt") for e in man.get("entrees", [])}
	return {k: (img, prompts.get(k)) for k, img in (man.get("images") or {}).items()}


def _portrait_b64(nom):
	"""Portrait du tenancier ramené à ~1 Mpx en JPEG puis base64 : bruts, les 62 portraits
	(~1,2 Mo chacun) gonflaient le JSONL du lot sans rien apporter à la référence."""
	from PIL import Image
	im = Image.open(os.path.join(DOSSIER_PNJ, nom)).convert("RGB")
	r = (1_000_000 / (im.width * im.height)) ** 0.5
	if r < 1:
		im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
	tampon = io.BytesIO()
	im.save(tampon, "JPEG", quality=90)
	return base64.b64encode(tampon.getvalue()).decode("ascii")


def _requete(e):
	return requete_gemini(e["prompt"], _portrait_b64(e["portrait"]) if e.get("portrait") else None)


def _chemin_requetes(cite):
	return os.path.join(os.path.dirname(_chemin_manifeste(cite)), "requetes.jsonl")


def _ecrire_image(dossier, base, part, pris):
	"""Écrit l'image d'une réponse Gemini sous le prochain nom libre ; (nom, None) ou (None, motif)."""
	octets = base64.b64decode(part["inlineData"]["data"])
	rejet = image_degeneree(*_mesures(octets))
	if rejet:
		return None, f"image {rejet}"
	ext = ".jpg" if "jpeg" in part["inlineData"].get("mimeType", "") else ".png"
	nom = nom_libre(dossier, base, ext, pris)
	with open(os.path.join(dossier, nom), "wb") as f:
		f.write(octets)
	return nom, None


def _comfy(chemin, corps=None):
	req = urllib.request.Request(COMFY + chemin, data=json.dumps(corps).encode() if corps is not None else None,
								 headers={"Content-Type": "application/json"} if corps is not None else {})
	with urllib.request.urlopen(req, timeout=30) as r:
		return r.read()


def _mesures(png):
	"""(écart-type, écart moyen entre voisins horizontaux) de l'image en niveaux de gris."""
	import io
	from PIL import Image, ImageChops, ImageStat
	g = Image.open(io.BytesIO(png)).convert("L")
	w, h = g.size
	voisins = ImageChops.difference(g.crop((0, 0, w - 1, h)), g.crop((1, 0, w, h)))
	return ImageStat.Stat(g).stddev[0], ImageStat.Stat(voisins).mean[0]


def _liberer():
	"""Décharge modèles et mémoire de ComfyUI. ⚠️ Sur la Radeon 890M (mémoire partagée), la
	mémoire n'est pas rendue entre deux images : la suivante sortait en bruit ou en gris (NaN),
	ou échouait en « Not enough memory … Have: 0.0GB free ». Constaté le 08/10."""
	_comfy("/free", {"unload_models": True, "free_memory": True})


def _envoyer_portrait(nom):
	"""Dépose le portrait du tenancier dans le dossier `input/` de ComfyUI ; rend son nom là-bas."""
	with open(os.path.join(DOSSIER_PNJ, nom), "rb") as f:
		octets = f.read()
	borne = "----telluris" + zlib.crc32(octets).__format__("x")
	corps = (f"--{borne}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
			 f"--{borne}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{nom}\"\r\n"
			 f"Content-Type: application/octet-stream\r\n\r\n").encode() + octets + f"\r\n--{borne}--\r\n".encode()
	req = urllib.request.Request(COMFY + "/upload/image", data=corps,
								 headers={"Content-Type": f"multipart/form-data; boundary={borne}"})
	with urllib.request.urlopen(req, timeout=60) as r:
		return json.loads(r.read())["name"]


def _workflow(e, portrait):
	return {
		"1": {"class_type": "UNETLoader", "inputs": {"unet_name": MODELE, "weight_dtype": "default"}},
		"2": {"class_type": "CLIPLoader", "inputs": {"clip_name": ENCODEUR, "type": "flux2", "device": "default"}},
		"3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
		"4": {"class_type": "LoadImage", "inputs": {"image": portrait}},
		"5": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["4", 0], "upscale_method": "nearest-exact",
			"megapixels": 1.0, "resolution_steps": 1}},
		"6": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
		"7": {"class_type": "CLIPTextEncode", "inputs": {"text": e["prompt"], "clip": ["2", 0]}},
		"8": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["7", 0]}},
		"9": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["7", 0], "latent": ["6", 0]}},
		"10": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["8", 0], "latent": ["6", 0]}},
		"11": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["9", 0], "negative": ["10", 0], "cfg": CFG}},
		"12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": SAMPLER}},
		"13": {"class_type": "Flux2Scheduler", "inputs": {"steps": PAS, "width": LARGEUR, "height": HAUTEUR}},
		"14": {"class_type": "RandomNoise", "inputs": {"noise_seed": e["graine"]}},
		"15": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": LARGEUR, "height": HAUTEUR, "batch_size": 1}},
		"16": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["14", 0], "guider": ["11", 0],
			"sampler": ["12", 0], "sigmas": ["13", 0], "latent_image": ["15", 0]}},
		"17": {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["3", 0]}},
		"18": {"class_type": "SaveImage", "inputs": {"images": ["17", 0], "filename_prefix": "telluris_magasin"}},
	}


# ── Étapes ──────────────────────────────────────────────────────────────────────

def preparer(cite, sauf):
	docs = _docs(_dump_le_plus_recent())
	lieux = {d["_id"]: d for d in docs if d.get("type") == "lieu"}
	cite_nom = (lieux.get(cite) or {}).get("label") or _slug(cite).capitalize()
	portraits = _portraits(cite)
	entrees, ignores, sans_traits = [], [], []
	for lid, lieu in sorted(lieux.items()):
		if lieu.get("lieu_parent") != cite or lid in sauf:
			continue
		if lieu.get("categorie") == "auberge" and lieu.get("image"):
			q = QUARTIERS_AUBERGES.get(lid) or quartier_de(lieu.get("label"), cite)
			entrees.append({"key": lid, "categorie": "auberge", "quartier": q,
							"base": base_image(lieu["image"], cite), "graine": zlib.crc32(lid.encode()),
							"portrait": None, "prompt": prompt_auberge(cite, cite_nom, q)})
			continue
		pnj = (lieu.get("pnj") or [{}])[0]
		portrait = str(pnj.get("portrait") or "")
		m = PORTRAIT_GENERIQUE.match(portrait)
		cat = lieu.get("categorie")
		if (not m or cat not in METIERS_EN or not lieu.get("image")
				or not os.path.exists(os.path.join(DOSSIER_PNJ, portrait))):
			ignores.append(f"{lid} ({cat}, portrait {portrait or '—'}, image {lieu.get('image') or '—'})")
			continue
		race = "humain" if m.group(1) == "humaine" else m.group(1)
		sexe = m.group(2).upper()
		img_portrait, prompt_fr = portraits.get(lid, (None, None))
		traits = traits_du_portrait(prompt_fr) if img_portrait == portrait else []
		if not traits:
			sans_traits.append(lid)
		prompt = prompt_magasin(cat, race, sexe, traits, cite, cite_nom, lieu.get("label"))
		entrees.append({"key": lid, "categorie": cat, "race": race, "sexe": sexe,
						"quartier": quartier_de(lieu.get("label"), cite),
						"base": base_image(lieu["image"], cite), "graine": zlib.crc32(lid.encode()),
						"portrait": portrait, "prompt": prompt})
	ancien = None
	if os.path.exists(_chemin_manifeste(cite)):
		ancien = _manifeste(cite)
		if ancien.get("batch"):
			raise SystemExit(f"Lot en cours : {ancien['batch']} — `recuperer` avant de re-préparer.")
	images = {k: v for k, v in ((ancien or {}).get("images") or {}).items() if k in {e["key"] for e in entrees}}
	with open(_chemin_requetes(cite), "w", encoding="utf-8") as f:
		for e in entrees:
			if e["key"] not in images:
				f.write(json.dumps({"key": e["key"], "request": _requete(e)}, ensure_ascii=False) + "\n")
	_manifeste(cite, {"cite": cite, "modele": MODELE_GEMINI, "entrees": entrees, "batch": None, "images": images})
	reste = len(entrees) - len(images)
	unit = EUR_PAR_IMAGE_INTERACTIF * REMISE_BATCH
	print(f"{len(entrees)} lieux préparés ({sum(1 for e in entrees if e['categorie'] == 'auberge')} auberge(s))"
		  f" → {os.path.relpath(_chemin_manifeste(cite), RACINE)}"
		  f" ({len(images)} image(s) déjà générée(s) conservée(s))")
	print(f"Lot : {reste} requête(s) → {os.path.relpath(_chemin_requetes(cite), RACINE)} ; "
		  f"estimation {reste} × {unit:.3f} € ≈ {reste * unit:.2f} €")
	for i in ignores:
		print("  ignoré :", i)
	if sans_traits:
		print(f"  {len(sans_traits)} sans traits de portrait (lignée seule) :", ", ".join(sans_traits))


def generer(cite, seulement, limite, essai=False):
	"""`essai` : écrit dans dev/batch/<cite>/magasins/essais/, ignore et ne touche pas le
	manifeste (`images`) — pour régler le gabarit sans rien poser dans `towns/`."""
	man = _manifeste(cite)
	try:
		_comfy("/system_stats")
	except (urllib.error.URLError, OSError):
		raise SystemExit(f"ERREUR : ComfyUI injoignable sur {COMFY} — lancer "
						 "C:\\ComfyUI_windows_portable\\run_telluris.bat.")
	_liberer()
	dossier = DOSSIER_TOWNS
	if essai:
		dossier = os.path.join(os.path.dirname(_chemin_manifeste(cite)), "essais")
		os.makedirs(dossier, exist_ok=True)
	a_faire = [e for e in man["entrees"] if e.get("portrait") and (essai or e["key"] not in man["images"])
			   and (not seulement or e["key"] in seulement)]
	if limite:
		a_faire = a_faire[:limite]
	print(f"{len(a_faire)} image(s) à générer")
	for i, e in enumerate(a_faire, 1):
		t0 = time.time()
		pid = json.loads(_comfy("/prompt", {"prompt": _workflow(e, _envoyer_portrait(e["portrait"]))}))["prompt_id"]
		while True:
			h = json.loads(_comfy(f"/history/{pid}")).get(pid)
			if h:
				break
			time.sleep(2)
		_liberer()
		if (h.get("status") or {}).get("status_str") != "success":
			print(f"  ✗ {e['key']} : {json.dumps((h.get('status') or {}).get('messages', [])[-1:])[:400]}")
			continue
		im = next(im for o in h["outputs"].values() for im in o.get("images", []))
		png = _comfy("/view?" + urllib.parse.urlencode(
			{"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")}))
		rejet = image_degeneree(*_mesures(png))
		if rejet:
			print(f"  ✗ {e['key']} : image {rejet} (GPU), non écrite — relancer `generer`", flush=True)
			continue
		nom = nom_libre(dossier, e["base"], ".png", () if essai else set(man["images"].values()))
		with open(os.path.join(dossier, nom), "wb") as f:
			f.write(png)
		if not essai:
			man["images"][e["key"]] = nom
			_manifeste(cite, man)
		print(f"  [{i}/{len(a_faire)}] {nom} ← {e['key']} ({time.time() - t0:.0f} s)", flush=True)


def essai(cite, seulement, limite):
	"""Gemini INTERACTIF (~0,04 €/image) dans dev/batch/<cite>/magasins/essais/ : ni `towns/` ni
	le manifeste ne bougent — pour juger le gabarit avant de payer le lot."""
	man = _manifeste(cite)
	dossier = os.path.join(os.path.dirname(_chemin_manifeste(cite)), "essais")
	os.makedirs(dossier, exist_ok=True)
	a_faire = [e for e in man["entrees"] if not seulement or e["key"] in seulement]
	if limite:
		a_faire = a_faire[:limite]
	print(f"{len(a_faire)} essai(s), ≈ {len(a_faire) * EUR_PAR_IMAGE_INTERACTIF:.2f} €")
	for e in a_faire:
		t0 = time.time()
		_, rep = _http(f"{API}/v1beta/models/{man['modele']}:generateContent", _requete(e))
		part = image_de_reponse(json.loads(rep))
		if not part:
			print(f"  ✗ {e['key']} : {rep.decode('utf-8', 'replace')[:300]}", flush=True)
			continue
		nom, motif = _ecrire_image(dossier, e["base"], part, ())
		print(f"  {nom or '✗ ' + motif} ← {e['key']} ({time.time() - t0:.0f} s)", flush=True)


def soumettre(cite):
	man = _manifeste(cite)
	if man.get("batch"):
		raise SystemExit(f"Déjà soumis : {man['batch']} — `etat` pour suivre.")
	man["batch"] = soumettre_lot(_chemin_requetes(cite), man["modele"], f"magasins-{cite}")
	_manifeste(cite, man)
	print("Lot soumis :", man["batch"])


def etat(cite):
	man = _manifeste(cite)
	if not man.get("batch"):
		raise SystemExit("Aucun lot en cours.")
	afficher_etat(man["batch"])


def recuperer(cite):
	"""Écrit les images du lot dans `towns/`. Le lot est ensuite CLOS (`lots`) : un `preparer`
	rejoué ne remet en lot que les lieux encore sans image (échecs, images rejetées)."""
	man = _manifeste(cite)
	if not man.get("batch"):
		raise SystemExit("Aucun lot en cours.")
	par_cle = {e["key"]: e for e in man["entrees"]}
	ecrites, erreurs = 0, []
	for cle, part, r in reponses_lot(man["batch"]):
		if cle in man["images"] or cle not in par_cle:
			continue
		if not part:
			erreurs.append(f"{cle} : {json.dumps(r.get('error') or r)[:200]}")
			continue
		nom, motif = _ecrire_image(DOSSIER_TOWNS, par_cle[cle]["base"], part, set(man["images"].values()))
		if not nom:
			erreurs.append(f"{cle} : {motif}")
			continue
		man["images"][cle] = nom
		ecrites += 1
	man.setdefault("lots", []).append(man["batch"])
	man["batch"] = None
	_manifeste(cite, man)
	print(f"{ecrites} image(s) écrite(s) dans templates/resources/towns/ ; {len(erreurs)} échec(s)"
		  f" — {len(man['entrees']) - len(man['images'])} lieu(x) encore sans image")
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
		doc["image"] = nom
		sortie.append(doc)
	chemin = os.path.join(RACINE, "jsons", f"images_magasins_{_slug(cite)}_a_importer.json")
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"{len(sortie)} lieu(x) → {os.path.relpath(chemin, RACINE)}")
	if absents:
		print(f"⚠ {len(absents)} lieu(x) absents du dump : exporter un dump puis relancer.")


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	p = argparse.ArgumentParser()
	p.add_argument("etape", choices=["preparer", "essai", "soumettre", "etat", "recuperer", "generer", "appliquer"])
	p.add_argument("--cite", default="lieu:rhemi")
	p.add_argument("--sauf", default="", help="lieux à exclure, séparés par des virgules")
	p.add_argument("--seulement", default="", help="ne générer que ces lieux, séparés par des virgules")
	p.add_argument("--limite", type=int, default=0, help="nombre maximal d'images à générer")
	p.add_argument("--essai", action="store_true", help="générer dans dev/batch/<cite>/magasins/essais/")
	a = p.parse_args()
	if a.etape == "preparer":
		preparer(a.cite, {s for s in a.sauf.split(",") if s})
	elif a.etape == "essai":
		essai(a.cite, {s for s in a.seulement.split(",") if s}, a.limite)
	elif a.etape == "generer":
		generer(a.cite, {s for s in a.seulement.split(",") if s}, a.limite, a.essai)
	else:
		{"soumettre": soumettre, "etat": etat, "recuperer": recuperer, "appliquer": appliquer}[a.etape](a.cite)


if __name__ == "__main__":
	main()
