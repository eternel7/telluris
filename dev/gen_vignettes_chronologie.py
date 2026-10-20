"""Vignettes des médaillons et cartouches de la frise du lore (`/admin/lore/chronologie`).

POURQUOI : les images citées par `docs/lore/chronologie.json` (`carte` d'une ère, `image` d'un
fleuve ou d'un événement) pèsent 1 à 3 Mo chacune ; la frise en montre une trentaine en
médaillons de quelques dizaines de pixels. Ce script en tire des JPEG légers dans
`templates/resources/icons/chronologie/` (mount `/icons`), que `utils/chronologie.url_image`
sert à leur place dès qu'ils existent — sans eux, la page charge l'original.

Régénération IDEMPOTENTE : nom dérivé du chemin (`chronologie.nom_vignette`), une vignette
déjà à jour (plus récente que sa source) n'est pas réécrite ; `--force` les refait toutes.

Usage :
  python dev/gen_vignettes_chronologie.py [--force]
"""

import os
import sys

from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import chronologie  # noqa: E402

COTE_MEDAILLON = 144   # carré recadré au centre : un médaillon est rond
COTE_CARTE = 260       # proportions gardées : une carte du monde n'est pas carrée


def images_citees(data: dict) -> dict:
	"""{chemin relatif: forme} — `carte` (proportions gardées) ou `medaillon` (carré)."""
	out = {}
	for e in data.get("eres") or []:
		if e.get("carte"):
			out[e["carte"]] = "carte"
	for x in (data.get("entites") or []) + (data.get("evenements") or []):
		if isinstance(x, dict) and x.get("image"):
			out.setdefault(x["image"], "medaillon")
	return out


def vignette(source, cible, forme: str) -> None:
	with Image.open(source) as im:
		im = ImageOps.exif_transpose(im).convert("RGB")
		if forme == "medaillon":
			im = ImageOps.fit(im, (COTE_MEDAILLON, COTE_MEDAILLON), Image.LANCZOS, centering=(0.5, 0.4))
		else:
			im.thumbnail((COTE_CARTE, COTE_CARTE), Image.LANCZOS)
		im.save(cible, "JPEG", quality=82, optimize=True, progressive=True)


def main(force: bool = False) -> int:
	data = chronologie.charger()
	dossier = chronologie.DOSSIER_VIGNETTES
	dossier.mkdir(parents=True, exist_ok=True)
	faites = gardees = 0
	manquantes = []
	for rel, forme in sorted(images_citees(data).items()):
		if not chronologie.image_existe(rel):
			manquantes.append(rel)
			continue
		source = chronologie.RESSOURCES / rel
		cible = dossier / chronologie.nom_vignette(rel)
		if not force and cible.is_file() and cible.stat().st_mtime >= source.stat().st_mtime:
			gardees += 1
			continue
		vignette(source, cible, forme)
		faites += 1
		print(f"  {rel} → icons/chronologie/{cible.name} ({cible.stat().st_size // 1024} ko)")
	print(f"{faites} vignette(s) écrite(s), {gardees} déjà à jour.")
	for rel in manquantes:
		print(f"  ⚠ image introuvable : {rel}")
	return 1 if manquantes else 0


if __name__ == "__main__":
	sys.exit(main(force="--force" in sys.argv[1:]))
