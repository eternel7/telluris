# utils/composition_rencontre.py
# COMPOSITION d'une rencontre groupée (pur) — règles lues dans `rules:affinites_especes`
# (Auteur, 15/11), appliquées par `combat.instantiate_groupes` :
#   • FORME selon la nature de l'espèce : SOLITAIRE (seule, le budget relève son grade),
#     MEUTE (jamais moins de `meute_min`, le grade baisse plutôt que l'effectif), RÔDEUR (au plus
#     `rodeur_max`, le reste du budget va au second groupe) ;
#   • HIÉRARCHIE d'un groupe : un chef relevé d'1 à `chef_crans_max` crans, une suite sous lui ;
#     RÔLES répartis chez les humanoïdes (mêlée / distance / magie selon `restriction_tags`) ;
#   • SECOND GROUPE associé à la première espèce : BANDE nommée (sinon FAMILLE de tags), MAÎTRE
#     ET BÊTES (ou nécromancien et morts), CHASSE EN COURS (proie fuyarde), CHAROGNARDS ;
#     une association tirée parmi celles qui ont un candidat au pool, sinon espèce au hasard.
#     Chance = `RENCONTRE_SECOND_GROUPE_PROBA` × min(1, candidats / `diversite_pleine`).
#
# Doc ABSENT ⇒ `combat.instantiate_groupes` garde le comportement d'avant (CLAUDE.md §4) ;
# doc présent, clé absente ⇒ la valeur de `DEFAUTS`.
# Motif de tag : `x` couvre `x` et `x_<suffixe>` (`ia_embuscade_1`, `magie_necromancie_8_mage`).

DOC_ID = "rules:affinites_especes"

ASSOCIATIONS = ("famille", "maitre_betes", "chasse", "charognards")

ROLE_MELEE, ROLE_DISTANCE, ROLE_MAGIE = "melee", "distance", "magique"
ORDRE_ROLES = (ROLE_MELEE, ROLE_DISTANCE, ROLE_MAGIE)

DEFAUTS = {
	"bandes": [],
	"familles_tags": [],
	"formes": {
		"solitaire_tags": ["boss", "legendaire", "geant"],
		"meute_tags": ["ia_meute"],
		"meute_min": 2,
		"rodeur_tags": ["ia_embuscade", "furtif"],
		"rodeur_max": 2,
	},
	"hierarchie": {"chef_crans_max": 2, "roles_tags": ["humanoide"]},
	"maitre_betes": {
		"maitres_tags": [], "maitres_exclure": [],
		"betes_tags": [], "betes_exclure": [],
		"necromanciens_tags": [], "morts_tags": [],
	},
	"chasse": {"predateurs_tags": [], "proies_tags": [], "proies_exclure": [], "fuite_pct": 70},
	"charognards": {"suivis_tags": [], "tags": [], "exclure": [], "max": 2},
	"diversite_pleine": 3,
}


def regles(doc: dict | None) -> dict | None:
	"""Règles effectives : `DEFAUTS` complétés par le doc (fusion d'un niveau). None sans doc."""
	if not doc:
		return None
	out = {}
	for cle, defaut in DEFAUTS.items():
		val = doc.get(cle)
		if isinstance(defaut, dict):
			out[cle] = {**defaut, **(val if isinstance(val, dict) else {})}
		else:
			out[cle] = val if val is not None else defaut
	return out


def _tags(espece) -> list:
	return list((espece or {}).get("tags") or [])


def tag_correspond(tags, motifs) -> bool:
	"""Un tag de `tags` vaut un motif de `motifs`, ou en est une forme suffixée (`motif_…`)."""
	motifs = [m for m in (motifs or []) if m]
	return any(t == m or t.startswith(m + "_") for t in (tags or []) for m in motifs)


def _filtre(espece, tags, exclure=()) -> bool:
	t = _tags(espece)
	return tag_correspond(t, tags) and not tag_correspond(t, exclure)


# ── Formes ────────────────────────────────────────────────────────────────────

def est_solitaire(espece, r) -> bool:
	return tag_correspond(_tags(espece), r["formes"].get("solitaire_tags"))


def est_meute(espece, r) -> bool:
	return not est_solitaire(espece, r) and tag_correspond(_tags(espece), r["formes"].get("meute_tags"))


def est_rodeur(espece, r) -> bool:
	"""Rôdeur isolé : embuscade / furtif, ni solitaire ni meute (la meute l'emporte)."""
	return (not est_solitaire(espece, r) and not est_meute(espece, r)
			and tag_correspond(_tags(espece), r["formes"].get("rodeur_tags")))


def effectif_max(espece, r) -> int | None:
	"""Plafond PROPRE à l'espèce (1 solitaire, `rodeur_max` rôdeur), None sinon."""
	if est_solitaire(espece, r):
		return 1
	if est_rodeur(espece, r):
		return max(1, int(r["formes"].get("rodeur_max") or 1))
	return None


def effectif_min(espece, r) -> int:
	return max(1, int(r["formes"].get("meute_min") or 1)) if est_meute(espece, r) else 1


# ── Associations du second groupe ─────────────────────────────────────────────

def _membres(bande) -> set:
	"""Ids complets des espèces d'une bande (`orc` et `espece:orc` s'écrivent indifféremment)."""
	return {e if ":" in e else f"espece:{e}" for e in (bande.get("especes") or []) if e}


def bandes_de(espece_id: str, r) -> list:
	return [b for b in r.get("bandes") or [] if espece_id in _membres(b)]


def _famille(principale, autres, r) -> list:
	"""BANDES nommées de la principale ; si elle n'est d'aucune, FAMILLES de tags partagées."""
	bandes = bandes_de(principale.get("_id"), r)
	if bandes:
		membres = set().union(*(_membres(b) for b in bandes))
		return [e for e in autres if e.get("_id") in membres]
	groupes = [f.get("tags") or [] for f in r.get("familles_tags") or []
			   if tag_correspond(_tags(principale), f.get("tags"))]
	return [e for e in autres if any(tag_correspond(_tags(e), g) for g in groupes)]


def _maitre_betes(principale, autres, r) -> list:
	mb = r["maitre_betes"]
	out = []
	if _filtre(principale, mb.get("maitres_tags"), mb.get("maitres_exclure")):
		out += [e for e in autres if _filtre(e, mb.get("betes_tags"), mb.get("betes_exclure"))]
	if tag_correspond(_tags(principale), mb.get("necromanciens_tags")):
		out += [e for e in autres if tag_correspond(_tags(e), mb.get("morts_tags")) and e not in out]
	return out


def _chasse(principale, autres, r) -> list:
	ch = r["chasse"]
	if not tag_correspond(_tags(principale), ch.get("predateurs_tags")):
		return []
	return [e for e in autres if _filtre(e, ch.get("proies_tags"), ch.get("proies_exclure"))]


def _charognards(principale, autres, r) -> list:
	cg = r["charognards"]
	if not tag_correspond(_tags(principale), cg.get("suivis_tags")):
		return []
	return [e for e in autres if _filtre(e, cg.get("tags"), cg.get("exclure"))]


_LECTEURS = {"famille": _famille, "maitre_betes": _maitre_betes,
			 "chasse": _chasse, "charognards": _charognards}


def associations(principale: dict, autres: list, r) -> dict:
	"""{association: candidats} — seulement les associations qui ont au moins un candidat dans
	`autres` (le pool sans la principale ni les solitaires), dans l'ordre d'`ASSOCIATIONS`."""
	out = {}
	for nom in ASSOCIATIONS:
		cands = _LECTEURS[nom](principale, autres, r)
		if cands:
			out[nom] = cands
	return out


def candidats_second(principale: dict, pool: list, r) -> list:
	"""Espèces du pool qui PEUVENT former un second groupe : ni la principale, ni un solitaire."""
	pid = principale.get("_id")
	return [e for e in pool if e.get("_id") != pid and not est_solitaire(e, r)]


def proba_second(base: float, nb_candidats: int, r) -> float:
	"""Chance d'un second groupe : `base` × min(1, candidats / `diversite_pleine`)."""
	pleine = max(1, int(r.get("diversite_pleine") or 1))
	return max(0.0, min(1.0, float(base))) * min(1.0, max(0, nb_candidats) / pleine)


def plafond_association(association: str | None, r) -> int | None:
	"""Effectif maximal propre à l'association (les charognards viennent peu nombreux)."""
	if association == "charognards":
		return max(1, int(r["charognards"].get("max") or 1))
	return None


def fuite_association(association: str | None, r) -> int | None:
	"""Seuil de fuite (% PV) imposé au second groupe : la proie surprise d'une chasse."""
	if association == "chasse":
		return max(0, min(100, int(r["chasse"].get("fuite_pct") or 0))) or None
	return None


# ── Grades : échelle, chef, suite, rôles ──────────────────────────────────────

def niveau(profil) -> int:
	return int((profil or {}).get("niveau") or 0)


def echelle(candidats: list) -> list:
	"""Niveaux distincts des profils candidats, croissants : les CRANS."""
	return sorted({niveau(p) for p in candidats or []})


def au_niveau(candidats: list, niv: int) -> list:
	return [p for p in candidats if niveau(p) == niv]


def decaler(niv: int, crans: int, ech: list) -> int:
	"""Niveau à `crans` (signé) de `niv` sur l'échelle, borné à ses extrémités."""
	if not ech:
		return niv
	i = ech.index(niv) if niv in ech else 0
	return ech[max(0, min(len(ech) - 1, i + crans))]


def role(profil) -> str:
	rt = set((profil or {}).get("restriction_tags") or [])
	if ROLE_DISTANCE in rt:
		return ROLE_DISTANCE
	if ROLE_MAGIE in rt:
		return ROLE_MAGIE
	return ROLE_MELEE


def joue_des_roles(espece, r) -> bool:
	return tag_correspond(_tags(espece), r["hierarchie"].get("roles_tags"))


def role_suivant(comptes: dict, disponibles) -> str | None:
	"""Rôle le moins représenté parmi `disponibles` ; ex æquo : mêlée, distance, magie."""
	dispo = [x for x in ORDRE_ROLES if x in set(disponibles)]
	if not dispo:
		return None
	return min(dispo, key=lambda x: (comptes.get(x, 0), ORDRE_ROLES.index(x)))
