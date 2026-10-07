"""Nécromancien 💀 — maître de la mort ; sa voie ultime mène vers la Liche (Nécromancie)."""
from competences_1_10 import A

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Toucher glacé", "🥶", "frappe", "ombre", "Un toucher qui glace la chair jusqu'à l'os."),
	A(1, "Malaise", "🤢", "entrave", "poison", "Une nausée soudaine qui affaiblit la cible.", malus=("R",)),
	A(1, "Sangsue", "🩸", "drain", "drain", "Il boit un peu de la vie de la cible."),
	A(1, "Linceul", "⚰️", "buff_soi", "tombeau", "Il s'enveloppe d'un linceul qui le protège.", stats=("R", "Vol")),
	# ── Niveau 2 ──
	A(2, "Trait d'os", "🦴", "frappe", "roc", "Un éclat d'os projeté comme une flèche."),
	A(2, "Peste", "☠️", "poison", "poison", "Une maladie qui ronge la cible."),
	A(2, "Murmure des morts", "👻", "poison_pm", "spectre", "Les morts murmurent à l'oreille de la cible et l'épuisent."),
	A(2, "Pas de la tombe", "🪦", "saut", "spectre", "Il disparaît dans le sol et ressort plus loin."),
	# ── Niveau 3 ──
	A(3, "Nuage pestilentiel", "☁️", "zone_cercle", "poison", "Un nuage de pestilence qui empoisonne le groupe."),
	A(3, "Faiblesse", "🦴", "entrave", "ombre", "Les muscles de la cible se changent en chiffons.", malus=("F", "R")),
	# ── Niveau 4 ──
	A(4, "Lance d'ombre", "🌑", "frappe", "ombre", "Une lance d'ombre pure qui transperce."),
	A(4, "Vampirisme", "🧛", "drain", "drain", "Il se nourrit du sang de la cible."),
	A(4, "Siphon d'âme", "👻", "siphon", "spectre", "Il aspire l'énergie magique de la cible."),
	A(4, "Carapace d'os", "🦴", "posture", "tombeau", "Des os se soudent autour de lui en armure.", stats=("R",)),
	# ── Niveau 5 ──
	A(5, "Main du tombeau", "🖐️", "entrave", "tombeau", "Une main sort de terre et agrippe la cible.", malus=("Ag",)),
	A(5, "Explosion de cadavre", "💥", "zone_cercle", "explosion_feu", "Un cadavre éclate au milieu des ennemis.", rayon=2),
	A(5, "Pacte de sang noir", "🩸", "sang", "drain", "Il paie de son sang un sort de mort."),
	A(5, "Énergie sombre", "⚫", "pm_allie", "ombre", "Il transfère de l'énergie sombre à un compagnon."),
	# ── Niveau 6 ──
	A(6, "Souffle de la tombe", "🌫️", "zone_cone", "impact_etincelles/cone_folie", "Un souffle froid venu d'outre-tombe."),
	A(6, "Corruption", "🦠", "poison", "poison", "Une corruption qui ronge le corps lentement."),
	# ── Niveau 7 ──
	A(7, "Doigt de mort", "☝️", "frappe", "ombre", "Il pointe le doigt, et la mort suit."),
	A(7, "Moisson d'âmes", "🌾", "drain", "drain", "Il moissonne la vie de la cible."),
	A(7, "Terreur", "😱", "entrave", "spectre", "Une terreur glaciale paralyse l'ennemi.", malus=("Vol", "Ag")),
	A(7, "Marche des ombres", "🌑", "saut", "ombre", "Il passe d'une ombre à l'autre."),
	# ── Niveau 8 ──
	A(8, "Fléau", "☠️", "zone_cercle", "poison", "Un fléau qui s'abat sur tout un groupe.", rayon=2),
	A(8, "Vol de mana", "💀", "siphon", "spectre", "Il arrache la magie de la cible comme on arrache une âme."),
	A(8, "Peau de cadavre", "🧟", "posture", "tombeau", "Sa peau devient froide et insensible.", stats=("R", "Vol")),
	A(8, "Malédiction de la liche", "📜", "poison_pm", "ombre", "Une malédiction qui empêche toute magie."),
	# ── Niveau 9 ──
	A(9, "Ténèbres dévorantes", "🌑", "frappe", "ombre", "Les ténèbres dévorent la cible."),
	A(9, "Rituel de mort", "⚰️", "rituel", "tombeau", "Un rituel long qui arrache la vie de la cible."),
	A(9, "Nuée de spectres", "👻", "zone_carre", "spectre", "Des spectres tourbillonnent autour de lui et frappent.", rayon=2),
	A(9, "Banquet du vampire", "🧛", "sang", "drain", "Il paie de son sang un coup qui lui en rendra davantage."),
	# ── Niveau 10 ──
	A(10, "Mot de mort", "💀", "frappe", "spectre", "Un mot que seuls les morts connaissent."),
	A(10, "Hiver éternel", "❄️", "entrave", "givre", "Le froid de la tombe fige la cible.", malus=("Ag", "F", "R")),
]
