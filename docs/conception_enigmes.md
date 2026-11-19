# Système d'énigmes — conception

- **Origine :** quête « La pièce derrière le mur » (`docs/lore/personnages/20261119_la_piece_derriere_le_mur.md`), arbitrage de l'Auteur du 19/11 : nouveau système d'énigmes plutôt que du dialogue.
- **Statut :** les choix ci-dessous **font foi** (Auteur, 19/11/2026, trois questionnaires). Rien n'est codé.

## Arbitrage (Auteur, 19/11)

| # | Point | Décision |
|---|---|---|
| 1 | Support | **Panneau dédié** (overlay) ouvert depuis un PNJ, un lieu ou un passage de donjon ; l'énigme est un doc **`enigme:*`** réutilisable, déclenché par un service ; dialogue et combat inchangés |
| 2 | Validation | **Le serveur** : la solution ne part jamais au client (comme les pièges cachés) ; le client envoie un essai, le serveur répond |
| 3 | Construction | **Familles génériques** pilotées par la donnée, réutilisables par d'autres quêtes |
| 4 | Échec | **Rien de perdu** : découvertes et étapes validées conservées, essai faux = remarque, aucune pénalité, jamais de quête bloquée |
| 5 | Déblocage | **Nouvelle condition `enigme_resolue`**, utilisable partout où les conditions existent (dialogue, accès, présence de PNJ) ; l'énigme ignore la quête |
| 6 | Mémoire | **Sur le personnage** (champ `enigmes`, reconstruit à la lecture, aucune migration) ; une énigme résolue le reste pour toujours |
| 7 | Aide | **Indices progressifs** débloqués par le nombre d'essais **+ un indice de groupe** si un membre s'y connaît (vocation, ou escorté comme Aélis) |
| 8 | Cave aux arches | **Dans le panneau** (famille « graphe de passages », journal des transitions), pas de vraies salles |
| 9 | Homme au sac | **Énigme puis combat** : le plan impossible, résolu dans le panneau, ouvre le combat ordinaire contre l'Homme au sac |
| 10 | Édition | **Générateur JSON** (`dev/gen_*.py`, un seul fichier à importer, contrôle que la solution est atteignable) ; éditeur /admin plus tard |
| 11 | Rendu | **Parchemin du jeu** (style des overlays de /play), symboles en SVG simple, journal des découvertes à côté |
| 12 | Ordre | **Toutes les familles d'un coup** (moteur + cinq familles), puis la quête |

## Familles

| Famille | Énigme de la quête |
|---|---|
| Collecte et déduction (indices examinés → conclusion, seuil d'indices essentiels) | l'atelier de Villard |
| Combinaison à crans | le meuble aux trois tiroirs |
| Graphe de passages | la cave aux cinq arches ; la sortie |
| Association | les trois propositions du Púca |
| Placement de symboles | le plan de la Zashiki-warashi (Soleil · Étoile · Lune · Vide) |
| Réseau de liaisons avec objets (clé = ouvrir, pierre = ancrer, miroir = révéler) | le plan impossible, avant l'Homme au sac |
