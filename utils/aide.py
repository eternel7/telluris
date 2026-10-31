"""Aide au démarrage de /play (pur) : les CHIFFRES que le texte de l'aide affiche.

Le texte vit dans le template (`play_town_telluris.html`, `#aide-overlay`) ; tout ce qui est
réglable (variable de monde) ou défini ailleurs dans le code est RELU ici, jamais recopié :
changer le facteur d'armure ou la table des dés met l'aide à jour toute seule.
"""
from models import character_stats
from models.character_stats import _caract_to_dice_
from utils.characters import CUIVRE_PAR_ARGENT, ARGENT_PAR_OR

# Caractéristique la plus haute sondée pour la table des dés : au-delà, la dernière
# tranche (« plus de … ») vaut pour tout le reste.
_SONDE_MAX = 200


def table_des() -> list[dict]:
	"""Tranches de `_caract_to_dice_` : [{"max": borne incluse ou None, "de": faces}].

	Reconstruite en SONDANT la fonction (0 → _SONDE_MAX) : la dernière tranche a
	`max = None` (« au-delà »)."""
	tranches: list[dict] = []
	for v in range(0, _SONDE_MAX + 1):
		de = _caract_to_dice_(v)
		if tranches and tranches[-1]["de"] == de:
			tranches[-1]["max"] = v
		else:
			tranches.append({"max": v, "de": de})
	if tranches:
		tranches[-1]["max"] = None
	return tranches


def regles_aide() -> dict:
	"""Contexte Jinja de l'aide : facteur d'armure EFFECTIF, table des dés, monnaie."""
	return {
		"facteur_armure": character_stats.facteur_degats_armure(),
		"des": table_des(),
		"cuivre_par_argent": CUIVRE_PAR_ARGENT,
		"argent_par_or": ARGENT_PAR_OR,
	}
