"""Druide 🌳 — gardien des cycles naturels : plantes, bêtes et saisons (magie de la Nature)."""
from competences_1_10 import A, L

ENTREES = [
	# ── Niveau 1 ──
	A(1, "Épines", "🌵", "frappe", "griffe", "Des épines jaillissent du sol sous la cible."),
	A(1, "Lianes", "🌿", "entrave", "nature_buff", "Des lianes s'enroulent autour des chevilles.", malus=("Ag",)),
	A(1, "Baume de mousse", "🍃", "soin", "soin_nature", "Une mousse fraîche posée sur la plaie."),
	A(1, "Écorce", "🌳", "buff_soi", "nature_buff", "Sa peau se couvre d'une écorce protectrice.", stats=("R",)),
	# ── Niveau 2 ──
	A(2, "Pollen soporifique", "🌼", "entrave", "nature_buff", "Un nuage de pollen qui alourdit les membres.", malus=("Vol", "Ag")),
	A(2, "Sève de chêne", "🌰", "regen_allie", "soin_nature", "La sève du vieux chêne coule dans les veines d'un compagnon."),
	L(2, "Ronces mordantes", "🌵", "griffe", "Des ronces jaillissent autour des jambes de la cible et la retiennent.",
	  {"cible": "ennemi", "jet": "magique", "portee": 5, "cout_pm": 12, "effets": {"degats": "1D{Vol/10}", "buffs": {"V": -2}, "duree": 2}},
	  remplace="ronces"),
	A(2, "Bond du cerf", "🦌", "saut", "nature_buff", "Il bondit avec la grâce du cerf."),
	# ── Niveau 3 ──
	A(3, "Champ de ronces", "🌾", "zone_cercle", "griffe", "Le sol se couvre de ronces acérées sous les ennemis."),
	A(3, "Bénédiction des bois", "🌲", "buff_allie", "nature_buff", "Il appelle la force des bois sur un compagnon.", stats=("R", "Vol")),
	# ── Niveau 4 ──
	A(4, "Racines dévorantes", "🌱", "drain", "soin_nature", "Les racines boivent la vie de la cible pour la lui rendre."),
	A(4, "Nuée d'insectes", "🐝", "poison", "poison", "Un essaim qui pique et harcèle."),
	A(4, "Peau d'écorce", "🪵", "posture", "nature_buff", "Il prend racine, et son corps devient bois.", stats=("R", "Vol")),
	A(4, "Rosée du matin", "💧", "pm_allie", "source", "La rosée d'aube, qui rend force et clarté."),
	# ── Niveau 5 ──
	A(5, "Fouet de liane", "🌿", "frappe", "nature_buff", "Une liane épaisse qui claque comme un fouet."),
	A(5, "Spores étouffantes", "🍄", "zone_cercle", "poison", "Un nuage de spores qui s'abat sur les ennemis.", rayon=2),
	A(5, "Régénération sylvestre", "🌳", "soin_zone", "soin_nature", "La forêt soigne ceux qui l'entourent."),
	L(5, "Sève partagée", "🌳", "soin_nature", "La sève circule entre le druide et le blessé : ce qui guérit l'un nourrit un peu l'autre.",
	  {"cible": "allie", "portee": 4, "cout_pm": 21, "effets": {"soin": "2D6+{Vol/10}", "partage_soin": 25}},
	  remplace="champignon_de_mana"),
	# ── Niveau 6 ──
	A(6, "Colère de la forêt", "🌲", "zone_rect", "griffe", "Des branches fouettent le premier rang ennemi."),
	A(6, "Cercle de vie", "♻️", "cri", "soin_nature", "Un cercle verdoyant qui fortifie ses alliés.", stats=("R", "Vol")),
	# ── Niveau 7 ──
	A(7, "Pieu de bois vivant", "🪵", "frappe", "roc", "Une souche jaillit du sol comme une lance."),
	A(7, "Étreinte du saule", "🌳", "entrave", "nature_buff", "Les branches enserrent l'ennemi et le paralysent.", malus=("Ag", "F")),
	A(7, "Venin de la vipère verte", "🐍", "poison_pm", "poison", "Un venin qui trouble l'esprit."),
	A(7, "Passage des racines", "🌱", "saut", "nature_buff", "Il entre dans le sol et ressort plus loin."),
	# ── Niveau 8 ──
	A(8, "Tempête de feuilles", "🍂", "zone_cone", "impact_plaie/cone_griffe", "Des feuilles tranchantes comme des lames."),
	A(8, "Floraison", "🌸", "soin", "soin_nature", "Une fleur s'ouvre sur la plaie et la referme."),
	A(8, "Bouclier d'épines", "🌵", "posture", "griffe", "Une armure d'épines qui fait payer chaque coup.", stats=("R", "F")),
	L(8, "Racines étouffantes", "🌿", "griffe", "Un parterre de racines qui blesse à chaque pas — même ceux qui ne sont pas visés.",
	  {"cible": "ennemi", "jet": "magique", "portee": 5, "cout_pm": 25, "maintien": 3, "zone": {"forme": "cercle", "origine": "cible", "rayon": 1}, "effets": {"degats": "1D8+{Vol/15}"}},
	  remplace="malediction_des_saisons", zone_persistante=True),
	# ── Niveau 9 ──
	A(9, "Courroux du chêne", "🌳", "frappe", "roc", "Le vieux chêne frappe de toute sa masse."),
	A(9, "Rituel du cycle", "♻️", "rituel", "nature_buff", "Un rituel lent qui retourne la cible à la terre."),
	A(9, "Pluie de vie", "🌧️", "regen_allie", "source", "Une pluie qui ranime et fortifie."),
	A(9, "Marais", "🐸", "zone_cercle", "eau", "Le sol devient un marais qui engloutit les ennemis.", rayon=2),
	# ── Niveau 10 ──
	A(10, "Fureur de Gaïa", "🌍", "zone_carre", "roc", "La terre elle-même se soulève contre l'ennemi.", rayon=2),
	A(10, "Renouveau", "🌱", "soin_zone", "soin_vague", "Le printemps éclate au milieu du combat."),
]
