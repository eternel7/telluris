# utils/statiques.py
# Montages statiques à règle propre.

import os

from fastapi.staticfiles import StaticFiles


class PortraitsStatic(StaticFiles):
	"""/characters : les portraits `guide_*` vivent dans pnj/ mais s'y servent aussi. Toutes les
	vues d'un compagnon (panneau 👥, fiche, dialogue, jeton de combat) préfixent `/characters/` :
	la règle tient ici en un point, sans copier d'image ni toucher chaque vue."""

	def __init__(self, *args, dossier_guides: str, **kwargs):
		super().__init__(*args, **kwargs)
		self._guides = StaticFiles(directory=dossier_guides)

	def lookup_path(self, path):
		if os.path.basename(path).lower().startswith("guide_"):
			return self._guides.lookup_path(path)
		return super().lookup_path(path)
