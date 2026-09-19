"""Propositions de NOMS D'ENSEIGNE pour la création d'un lot de lieux (pur).

Ce module ne connaît ni la base ni le web : il croise une tournure de métier avec un
complément de lieu et rend des libellés distincts. Il sert le tableau du lot de
`/admin/editor` (mode Lieux), dont c'était le seul verrou — poser trente boutiques
demande trente noms, et c'est ce qui rendait le geste impraticable à la main.

⚠️ `rand_fn` est INJECTÉ (cf. CLAUDE.md §14) : un test qui tire au hasard n'est pas un
test. Le défaut est `random.shuffle`, un test passe le sien.

⚠️ Le tirage ne garantit **que la distinction**, jamais le goût : un nom proposé est un
point de départ que l'auteur réécrit dans le tableau. C'est pourquoi le catalogue reste
volontairement court — l'enrichir se fait ici, sans toucher à une ligne de code.
"""

import random

# ── Tournures par catégorie ─────────────────────────────────────────────────────
# La clé est la `categorie` du doc lieu — donc aussi le suffixe de `pnj:marchand_*`.
# Les 48 catégories à tenancier générique sont couvertes ; une catégorie absente
# retombe sur `_tournures_repli` (bâti sur le nom de catégorie), jamais sur rien.
TOURNURES = {
    # — Les trente métiers de base —
    "apothicairerie": [
        "L'Herbier", "L'Officine", "Le Mortier", "La Simple", "L'Alambic",
        "Le Mortier d'Or", "La Racine", "Le Jardin des Simples", "La Fiole",
        "Le Bocal aux Herbes", "La Réserve des Simples", "Le Pilon",
        "La Feuille Séchée", "Le Remède", "La Pharmacie des Moines", "L'Élixir",
        "La Racine Amère", "Le Mortier Vert", "La Coupe aux Herbes", "Le Baume"
    ],
    "armurerie": [
        "L'Enclume", "La Forge", "Le Marteau", "L'Écu", "La Trempe",
        "Le Fer Rouge", "La Lame", "Le Gantelet", "Le Bouclier", "La Côte de Maille",
        "Le Heaume", "Le Fer Battu", "La Lame d'Acier", "Le Harnois",
        "La Forge aux Armes", "Le Marteau Noir", "Le Fer du Guerrier", "La Bonne Lame",
        "Le Glaive", "Le Fer Trempé"
    ],
    "atelier_d_artisan": [
        "L'Établi", "Le Copeau", "La Varlope", "Le Rabot", "La Besogne",
        "Le Maillet", "Le Ciseau", "Le Compas", "La Plane", "Le Bois Ouvré",
        "Le Trait de Scie", "La Belle Ouvrage", "Le Bois Taillé", "Le Tour",
        "Le Banc d'Œuvre", "La Main Habile", "Le Travailleur", "Le Bois et le Fer",
        "L'Ouvrage Fin", "Le Petit Atelier"
    ],
    "atelier_de_cirier": [
        "La Mèche", "Le Cierge", "La Chandelle", "La Cire", "La Veilleuse",
        "Le Flambeau", "La Torche", "Le Pain de Cire", "La Chandelle Blanche",
        "La Flamme", "Le Cierge Sacré", "La Cire Jaune", "Le Moule à Bougies",
        "La Lumière", "Le Feu de Cire", "La Flamme Douce", "Le Cierge d'Abeille",
        "La Chandelle du Soir", "La Cire Fondue", "Le Flambeau d'Or"
    ],
    "atelier_de_l_empenneur": [
        "La Plume et l'Encoche", "L'Empennage", "La Penne", "Le Trait Droit",
        "La Flèche Empennée", "La Plume Blanche", "L'Encoche", "Le Vol de la Flèche",
        "La Plume du Tireur", "Le Trait Juste", "L'Aile de la Flèche", "La Flèche Fine",
        "Le Fût et la Plume", "Le Plumier du Chasseur", "La Flèche Droite",
        "L'Empenneur", "La Plume Rouge", "Le Trait du Faucon", "La Flèche du Vent",
        "Le Vol Droit"
    ],
    "bijouterie": [
        "L'Écrin", "Le Chaton", "La Sertissure", "Le Camée", "L'Orfroi",
        "La Pierrerie", "Le Joyau", "Le Rubis", "Le Diadème", "La Gemme",
        "L'Anneau d'Or", "La Perle", "Le Collier", "La Pierre Fine", "L'Or et l'Argent",
        "Le Joyau Taillé", "La Couronne", "Le Cabinet des Gemmes", "L'Émeraude",
        "Le Saphir"
    ],
    "boucherie": [
        "Le Billot", "Le Couperet", "L'Étal", "La Hampe", "Le Quartier",
        "Le Croc de Boucher", "La Bonne Viande", "Le Coutelas", "Le Rôt",
        "La Pièce de Viande", "Le Gigot", "La Côte Rouge", "Le Bœuf Gras",
        "Le Porc Salé", "Le Quartier de Viande", "La Bonne Découpe",
        "Le Croc Rouge", "La Viande du Marché", "Le Billot Noir", "Le Rôti Doré"
    ],
    "boulangerie": [
        "Le Fournil", "Le Four Banal", "La Huche", "Le Levain", "La Miche",
        "La Boulange", "Le Pain Doré", "La Croûte d'Or", "Le Pétrin",
        "La Farine Blanche", "Le Pain Chaud", "La Bonne Miche", "Le Pain des Halles",
        "La Fournée", "Le Gros Pain", "La Miche Chaude", "Le Pain de Seigle",
        "Le Levain Royal", "La Belle Croûte", "Le Four à Bois"
    ],
    "bourrellerie": [
        "Le Harnais", "La Bricole", "Le Collier", "La Sangle", "L'Attelage",
        "Le Licol", "Le Bât", "La Bride", "La Rênette", "Le Trait",
        "Le Harnachement", "La Courroie", "Le Cuir à Cheval", "Le Porte-Selle",
        "La Selle du Cavalier", "Le Harnais Fort", "La Boucle de Cuir",
        "Le Bourrelier", "Le Cuir et la Sangle", "L'Écurie du Bourrelier"
    ],
    "boyauderie": [
        "La Corde de Boyau", "Le Fil Tendu", "La Baudruche", "Le Boyau Filé",
        "Le Boyau Fin", "La Corde Blanche", "Le Fil de Tripaille", "La Membrane",
        "Le Boyau Séché", "La Fine Corde", "Le Fil de Boyau", "La Baudruche Fine",
        "Le Boyau de Mouton", "La Corde Sonore", "Le Fil Torsadé", "Le Boyau Tendu"
    ],
    "brosserie": [
        "La Soie et le Manche", "La Brosse", "Le Crin", "L'Époussette",
        "Le Balai Fin", "La Brosse de Crin", "Le Poil et le Bois", "La Brossière",
        "Le Plumeau", "La Brosse Ronde", "Le Balai de Cour", "La Brosse à Cheveux",
        "Le Crin Noir", "La Brosse Fine", "Le Manche et le Crin", "La Brosse du Palais"
    ],
    "corderie": [
        "Le Chanvre Tressé", "Le Commettage", "L'Aussière", "Le Toron",
        "La Corde Forte", "Le Chanvre Filé", "Le Gros Cordage", "La Tresse",
        "Le Câble", "La Corde Marine", "Le Fil de Chanvre", "Le Toron Tressé",
        "La Corde à Puits", "Le Cordage Fort", "La Chanvrière", "Le Câble Torsadé"
    ],
    "cordonnerie": [
        "L'Alêne", "Le Soulier", "La Forme", "L'Empeigne", "Le Bon Pas",
        "Le Cordon", "La Semelle", "Le Talon", "Le Soufflet", "Le Bottier",
        "La Bonne Chaussure", "Le Cuir Souple", "Le Soulier Doré", "La Chaussure Fine",
        "Le Pas Sûr", "L'Atelier du Soulier", "La Semelle Forte", "Le Cordon de Cuir"
    ],
    "cuisine": [
        "Le Fourneau", "La Marmite", "Le Chaudron", "L'Écuelle", "La Braise",
        "Le Pot au Feu", "La Grande Marmite", "Le Coquemar", "La Cuillère de Bois",
        "Le Faitout", "Le Chaudron Fumé", "La Bonne Cuisine", "Le Ragoût",
        "La Broche", "Le Potager et le Chaudron", "Le Feu de Cuisine",
        "La Marmite Noire", "Le Bouillon", "La Broche Tournante", "Le Grand Fourneau"
    ],
    "etable": [
        "Le Sabot", "Le Pré aux Bêtes", "La Litière", "L'Avoine", "Le Licol",
        "L'Étable du Pré", "Le Foin Doré", "La Mangeoire", "Le Râtelier",
        "Le Bœuf et l'Avoine", "Le Bon Fourrage", "La Crèche aux Bêtes",
        "Le Pré Vert", "Le Foin Sec", "L'Abreuvoir", "La Bonne Étable",
        "Le Sabot Ferré", "La Grange aux Bêtes", "Le Râtelier Plein", "Le Pré aux Chevaux"
    ],
    "fletcher": [
        "L'Arc et la Corde", "La Flèche", "Le Fût d'If", "La Coche",
        "L'Arc Long", "Le Bois d'If", "La Corde d'Arc", "Le Trait du Chasseur",
        "L'Arc Tendu", "La Flèche Blanche", "Le Fût de Frêne", "Le Carquois",
        "La Bonne Flèche", "L'Arc du Forestier", "Le Bois et la Corde",
        "Le Tir Juste", "La Flèche du Chasseur", "L'Arc Vert", "Le Trait de l'Archer",
        "Le Carquois Plein"
    ],
    "fumoir": [
        "Le Haloir", "La Fumée Lente", "Le Lard Pendu", "Le Boucanage",
        "La Fumée Blanche", "Le Jambon Fumé", "Le Crochet à Viande", "Le Feu Lent",
        "Le Fumoir des Halles", "La Viande Fumée", "Le Bois de Fumée", "Le Jambon au Feu",
        "La Fumée Douce", "Le Lard de Chêne", "Le Crochet Noir", "Le Fumage Lent"
    ],
    "jardinier": [
        "Le Carré de Simples", "La Serpe", "Le Plant", "La Treille", "Le Semis",
        "Le Jardin Clos", "La Bêche", "Le Râteau", "Le Potager", "La Graine",
        "Le Verger", "La Serre", "Le Jardinier", "Le Plant de Vigne",
        "La Terre Fertile", "Le Carré Vert", "La Bonne Graine", "Le Verger Fleuri",
        "La Houe", "Le Jardin des Moines"
    ],
    "laboratoire_d_alchimie": [
        "Le Cabinet des Sels", "L'Athanor", "Le Creuset", "La Cornue",
        "La Fiole d'Or", "Le Mortier Alchimique", "La Table des Sels",
        "Le Feu Secret", "La Retorte", "Le Vase Hermétique", "Le Four des Sages",
        "La Pierre Rouge", "Le Bain-Marie", "La Fiole Verte", "Le Creuset Noir",
        "L'Œuvre Alchimique", "Le Cabinet des Élixirs", "La Cornue d'Argent",
        "Le Feu des Philosophes", "L'Athanor Rouge"
    ],
    "lutherie": [
        "La Table d'Harmonie", "L'Éclisse", "Le Chevalet", "L'Accord Juste",
        "La Corde Vibrante", "Le Bois Chantant", "La Rosace", "Le Manche",
        "La Belle Mélodie", "Le Luthier", "La Table Sonore", "Le Bois d'Érable",
        "La Caisse Harmonieuse", "Le Son Juste", "Le Chevalet d'Or",
        "La Corde Fine", "L'Instrument Chantant", "La Rosace Dorée", "Le Bois Sonore"
    ],
    "maroquinerie": [
        "Le Cuir Repoussé", "La Gaine", "L'Étui", "La Basane", "Le Maroquin",
        "Le Cuir Fin", "La Bourse", "Le Sac de Voyage", "La Courroie",
        "Le Cuir Gravé", "La Belle Peau", "L'Étui à Dague", "La Bourse de Cuir",
        "Le Coffret Gainé", "Le Cuir Souple", "La Maison du Maroquin",
        "Le Sac du Marchand", "La Gaine Dorée", "Le Cuir Ouvragé"
    ],
    "necromancie": [
        "L'Ossuaire", "Le Suaire", "La Veille des Morts", "Le Cercle Éteint",
        "La Crypte", "Le Crâne Noir", "Le Livre des Morts", "La Pierre Tombale",
        "Le Cercle des Ombres", "La Veille Funèbre", "Le Caveau", "L'Osselet",
        "Le Sceau des Morts", "La Chambre des Crânes", "Le Cercle Noir",
        "Le Suaire Gris", "La Crypte Souterraine", "Le Dernier Souffle",
        "Le Reliquaire des Morts"
    ],
    "plumasserie": [
        "La Coiffe", "La Parure", "Le Duvet", "L'Aigrette", "Le Plumail",
        "La Plume d'Oiseau", "Le Panache", "La Plume Blanche", "La Coiffe à Plumes",
        "Le Plumier", "La Parure de Plumes", "Le Grand Panache", "La Plume Dorée",
        "L'Aigrette Blanche", "Le Duvet Fin", "La Plume de Paon",
        "Le Panache Royal", "La Coiffe d'Oiseau", "Le Plumage"
    ],
    "salaison": [
        "Le Saloir", "La Saumure", "Le Muid Salé", "Le Sel Gris",
        "Le Jambon au Sel", "La Barrique de Sel", "Le Cochon Salé", "Le Bac à Saumure",
        "La Viande au Sel", "Le Sel Marin", "Le Jambon des Halles", "Le Muid de Saumure",
        "La Salaison Royale", "Le Lard Salé", "Le Sel et la Viande", "La Barrique Salée"
    ],
    "savonnerie": [
        "La Cendre et l'Huile", "Le Savon Dur", "La Buanderie", "L'Essence",
        "Le Pain de Savon", "La Lessive", "Le Chaudron à Savon", "La Savonnette",
        "Le Parfum", "La Cendre Blanche", "Le Savon Parfumé", "La Maison du Savon",
        "L'Huile et la Cendre", "Le Savon des Lavandières", "La Bonne Lessive",
        "Le Savon de Marseille", "La Fleur de Savon", "Le Bain Parfumé"
    ],
    "scriptorium": [
        "Le Calame", "La Plume et l'Encre", "Le Pupitre", "Le Vélin",
        "Le Parchemin", "L'Encrier", "La Belle Écriture", "Le Manuscrit",
        "Le Livre Relié", "La Plume d'Oie", "Le Copiste", "L'Encre Noire",
        "Le Parchemin Fin", "La Lettre Dorée", "Le Codex", "La Bibliothèque",
        "Le Rouleau", "Le Livre des Scribes", "La Plume Blanche", "Le Vélin Doré"
    ],
    "tabletterie": [
        "L'Os Tourné", "Le Buis", "Le Tour", "La Plaquette", "L'Ivoire Feint",
        "Le Peigne de Buis", "La Boîte Sculptée", "Le Jeton", "Le Pion",
        "Le Coffret d'Os", "Le Buis Tourné", "La Petite Sculpture",
        "L'Os Gravé", "Le Peigne Fin", "Le Jeu de Buis", "La Boîte à Bijoux",
        "Le Tourneur d'Os", "La Plaque Gravée"
    ],
    "tannerie": [
        "Le Tan", "La Fosse", "Le Cuir Vert", "L'Écorce", "Le Corroi",
        "La Peau Brute", "Le Bain de Tan", "La Fosse à Cuir", "Le Cuir Souple",
        "Le Tan Rouge", "La Peau Trempée", "Le Cuir Fort", "La Grande Fosse",
        "Le Corroyeur", "L'Écorce de Chêne", "Le Cuir Brun", "La Peau Fine"
    ],
    "taxidermie": [
        "Le Trophée de Chasse", "L'Œil de Verre", "La Bête Montée", "L'Empaillage",
        "Le Cabinet des Bêtes", "La Tête de Cerf", "Le Renard Monté", "La Bête Sauvage",
        "Le Trophée", "Le Cerf et le Sanglier", "La Grande Chasse",
        "Le Cabinet du Chasseur", "La Peau Montée", "La Bête Immobile",
        "Le Bestiaire", "Le Regard de Verre", "Le Trophée Royal"
    ],
    "tissage": [
        "La Navette", "Le Métier Haut", "L'Ourdissoir", "La Trame", "Le Lissier",
        "Le Fil d'Or", "La Bobine", "Le Métier à Tisser", "La Chaîne et la Trame",
        "Le Rouet", "La Toison", "Le Fil de Lin", "La Belle Étoffe",
        "Le Tissage Fin", "La Trame Dorée", "Le Fil de Laine", "Le Métier du Tisserand"
    ],

    # — Les grandes maisons —
    "cabinet_des_specimens": [
        "Le Cabinet des Spécimens", "La Grande Vitrine", "Le Muséum",
        "La Galerie des Curiosités", "Le Cabinet des Merveilles",
        "La Collection Royale", "La Grande Collection", "Le Cabinet Naturel",
        "La Salle des Curiosités", "Le Bestiaire Savant", "La Maison des Curiosités",
        "Le Grand Cabinet"
    ],
    "grand_arsenal": [
        "Le Grand Arsenal", "La Fonderie Royale", "L'Armurerie Majeure",
        "L'Arsenal du Royaume", "La Grande Forge", "Le Marteau Royal",
        "La Forge des Maîtres", "Le Grand Harnois", "La Manufacture des Armes",
        "Le Fer Royal", "L'Arsenal des Couronnes", "La Grande Armurerie"
    ],
    "grand_atelier_d_empennage": [
        "Le Grand Atelier d'Empennage", "La Maison du Trait",
        "La Grande Flèche", "L'Atelier des Archers", "La Maison de la Plume",
        "Le Grand Empenneur", "La Manufacture des Flèches",
        "Le Trait Royal", "La Grande Plume", "L'Atelier du Tir Juste"
    ],
    "grand_laboratoire_alchimique": [
        "Le Grand Athanor", "Le Laboratoire Majeur", "La Grande Cornue",
        "Le Cabinet des Philosophes", "La Maison des Élixirs",
        "Le Grand Creuset", "L'Athanor Royal", "La Manufacture des Élixirs",
        "Le Laboratoire des Sages", "La Grande Œuvre"
    ],
    "grand_scriptorium": [
        "Le Grand Scriptorium", "La Grande Librairie", "La Maison des Livres",
        "Le Palais des Manuscrits", "Le Grand Atelier des Scribes",
        "La Bibliothèque Royale", "Le Scriptorium des Maîtres",
        "La Grande Salle des Livres", "Le Cabinet des Manuscrits",
        "La Maison du Vélin"
    ],
    "grande_apothicairerie": [
        "La Grande Officine", "La Maison des Simples", "Le Grand Herbier",
        "La Grande Pharmacie", "Le Jardin des Remèdes", "L'Officine Royale",
        "Le Cabinet des Élixirs", "La Maison des Baumes", "La Grande Herboristerie",
        "Le Mortier Royal"
    ],
    "grande_boulangerie": [
        "Le Grand Fournil", "La Halle au Pain", "La Grande Boulange",
        "Le Fournil Royal", "La Maison du Pain", "La Grande Fournée",
        "Le Palais du Pain", "La Halle des Boulangers", "Le Grand Pétrin",
        "La Maison de la Miche"
    ],
    "grande_corderie": [
        "La Grande Corderie", "La Maison du Câble", "La Corderie Royale",
        "Le Grand Cordage", "La Manufacture du Chanvre",
        "La Maison des Aussières", "Le Grand Toron", "La Corderie des Ports",
        "La Halle aux Cordages", "La Grande Chanvrière"
    ],
    "grande_maison_des_arts": [
        "La Maison des Arts", "Le Grand Atelier", "Le Palais des Métiers",
        "La Grande Maison des Artisans", "Le Hall des Maîtres",
        "La Maison des Compagnons", "Le Grand Ouvrage", "La Galerie des Métiers",
        "Le Palais des Artisans", "La Maison des Maîtres"
    ],
    "grande_manufacture_du_cuir": [
        "La Grande Mégisserie", "La Manufacture du Cuir", "La Maison des Peaux",
        "La Grande Tannerie", "La Manufacture des Peaux",
        "Le Palais du Cuir", "La Grande Mégisserie Royale",
        "La Maison du Cuir Fin", "La Halle aux Peaux", "Le Grand Corroi"
    ],
    "grande_manufacture_textile": [
        "La Manufacture des Toiles", "La Grande Draperie", "La Manufacture Royale",
        "La Maison des Étoffes", "La Grande Filature", "Le Palais des Tisserands",
        "La Halle aux Draps", "La Manufacture des Laines",
        "La Maison des Toiles", "Le Grand Métier"
    ],
    "grande_orfevrerie": [
        "L'Orfèvrerie Royale", "La Grande Orfèvrerie", "La Maison de l'Or",
        "Le Palais des Orfèvres", "La Manufacture des Joyaux",
        "La Grande Pierrerie", "L'Atelier Royal des Gemmes",
        "La Maison des Joyaux", "Le Trésor des Orfèvres", "La Grande Maison de l'Or"
    ],
    "grandes_halles_alimentaires": [
        "Les Grandes Halles", "La Halle aux Vivres", "Les Halles Royales",
        "Le Grand Marché", "La Halle des Marchands", "Les Greniers du Royaume",
        "La Grande Halle", "Le Marché aux Vivres", "Les Halles du Bourg",
        "La Halle des Provisions"
    ],
    "institut_de_thanaturgie": [
        "L'Institut de Thanaturgie", "Le Grand Ossuaire", "La Maison des Morts",
        "Le Collège des Thanaturges", "Le Cabinet des Défunts",
        "La Grande Crypte", "L'Institut des Derniers Souffles",
        "Le Conservatoire des Morts", "La Maison du Suaire", "Le Grand Caveau"
    ],
    "institut_medico_alchimique": [
        "L'Institut des Humeurs", "Le Grand Cabinet", "La Maison des Médecines",
        "L'Institut des Remèdes", "Le Collège des Alchimistes",
        "Le Grand Cabinet Médical", "La Maison des Élixirs",
        "L'Institut des Savoirs Médicaux", "Le Cabinet des Humeurs",
        "Le Collège des Médecins-Alchimistes"
    ],
    "maison_des_conserves": [
        "La Maison des Conserves", "Le Grand Saloir", "La Maison des Réserves",
        "Le Grenier Royal", "La Grande Réserve", "Le Conservatoire des Vivres",
        "La Maison des Provisions", "Le Grand Garde-Manger",
        "La Halle des Conserves", "Les Réserves du Royaume"
    ],
    "manufacture_des_instruments": [
        "La Manufacture des Instruments", "La Grande Lutherie",
        "La Maison des Instruments", "Le Palais des Musiciens",
        "La Manufacture Royale", "Le Grand Atelier Musical",
        "La Maison des Maîtres Luthiers", "La Grande Maison du Son",
        "Le Conservatoire des Instruments", "L'Atelier des Harmonies"
    ],
    "manufacture_des_savons_et_parfums": [
        "La Maison des Parfums", "La Grande Savonnerie", "La Manufacture des Essences",
        "Le Palais des Parfums", "La Maison des Fragrances",
        "La Grande Parfumerie", "La Manufacture Royale des Senteurs",
        "Le Jardin des Essences", "La Maison des Bains",
        "La Manufacture des Senteurs"
    ],
}

# ── Compléments de lieu ─────────────────────────────────────────────────────────
# Ce qui donne à l'enseigne son ancrage : « du Rempart », « de l'Yonne ». Une cité
# absente de la table prend `TOPONYMES_DEFAUT` — donc ouvrir une ville neuve ne
# demande rien, et l'enrichir se fait en ajoutant une entrée ici.
TOPONYMES_PAR_LIEU = {
	"lieu:auxerre": [
		"du Rempart", "de l'Yonne", "de Sainte-Colombe", "du Pont", "de Saint-Germain",
		"du Vieux Quai", "de la Tour de l'Horloge", "des Fossés", "du Faubourg",
	],
	"lieu:lutecia": [
		"de la Seine", "du Parvis", "des Halles", "de la Cité", "du Petit-Pont",
		"des Écoles", "de la Grève", "du Palais", "des Faubourgs", "de la Montagne",
	],
	"lieu:rhemi": [
		"du Sacre", "de la Vesle", "des Coteaux", "de la Porte de Mars", "du Chapitre",
		"des Crayères", "du Vieux Cloître",
	],
}

TOPONYMES_DEFAUT = [
	"du Marché", "de la Grand-Rue", "du Vieux Puits", "de la Place", "du Beffroi",
	"des Trois Chemins", "du Pilori", "de la Halle", "du Guet", "de la Poterne",
]

# Suffixes de désambiguïsation quand tournures × toponymes ne suffisent plus.
# ⚠️ Épuisés à leur tour, on repart sur un compteur décimal (cf. `_suffixes`) : la
# fonction doit TOUJOURS rendre `n` libellés, sans quoi une ligne du tableau naîtrait
# sans nom et l'admin ne saurait pas laquelle.
_ROMAINS = ["II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def toponymes_de(lieu_parent: str) -> list:
	"""Compléments de lieu d'une cité — les siens, sinon les génériques."""
	return list(TOPONYMES_PAR_LIEU.get(lieu_parent or "") or TOPONYMES_DEFAUT)


def _tournures_repli(categorie: str) -> list:
	"""Tournure bâtie sur le nom de catégorie, pour une catégorie hors catalogue.

	`atelier_de_cirier` → « Atelier De Cirier ». Laid, mais nommé : mieux vaut un
	libellé perfectible qu'une ligne vide que l'admin devra remplir à la main."""
	mots = [m for m in str(categorie or "").replace("_", " ").split() if m]
	if not mots:
		return ["L'Échoppe"]
	return [" ".join(m.capitalize() for m in mots)]


def _suffixes():
	"""Suite infinie de désambiguïsateurs : II, III… X, puis 11, 12, 13…

	⚠️ `_ROMAINS` commence à **II** et couvre donc les rangs 2 à 10 : la suite décimale
	reprend à `len + 2`, pas à `len + 1`. Sinon « X » et « 10 » nommeraient deux
	boutiques différentes du même rang."""
	for r in _ROMAINS:
		yield r
	n = len(_ROMAINS) + 2
	while True:
		yield str(n)
		n += 1


def tirer_labels(categorie, n, lieu_parent="", exclus=(), rand_fn=random.shuffle) -> list:
	"""`n` enseignes DISTINCTES pour cette catégorie, aucune dans `exclus`.

	Croise les tournures du métier avec les compléments de la cité, mélange, et
	complète au suffixe numéroté si le produit ne suffit pas. Rend toujours
	exactement `n` libellés (ou `[]` si `n <= 0`).

	⚠️ `exclus` est comparé TEL QUEL, sans normalisation : l'appelant y met les
	labels déjà en base ET ceux déjà posés dans le tableau du lot. C'est le seul
	rempart contre deux `lieu:<slug>` identiques, l'`_id` se déduisant du label.
	⚠️ `rand_fn` reçoit la liste et la mélange EN PLACE (contrat de `random.shuffle`).
	"""
	try:
		combien = int(n)
	except (TypeError, ValueError):
		return []
	if combien <= 0:
		return []

	tournures = list(TOURNURES.get(categorie) or _tournures_repli(categorie))
	toponymes = toponymes_de(lieu_parent)

	# Produit complet, mélangé une fois : le tirage doit être stable pour un même
	# `rand_fn`, donc on ne re-mélange jamais en cours de route.
	candidats = ["%s %s" % (t, top) for t in tournures for top in toponymes]
	rand_fn(candidats)

	pris = set(exclus or ())
	labels = []
	for c in candidats:
		if len(labels) >= combien:
			break
		if c in pris:
			continue
		pris.add(c)
		labels.append(c)

	if len(labels) < combien:
		# Catalogue épuisé : on re-suffixe les candidats dans le même ordre mélangé.
		for suffixe in _suffixes():
			for c in candidats:
				if len(labels) >= combien:
					break
				propose = "%s %s" % (c, suffixe)
				if propose in pris:
					continue
				pris.add(propose)
				labels.append(propose)
			if len(labels) >= combien:
				break
	return labels
