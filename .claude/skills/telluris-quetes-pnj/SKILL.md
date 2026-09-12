---
name: telluris-quetes-pnj
description: Quests, NPCs, dungeons and access gates — guild board and quest engine, transport/hunt/escort quests (incl. generated progeny escorts), NPC dialogue trees and services, the dialogue linter and the /admin/dialogues editor for authored quest offers, gated place access (acces blocks, laissez-passer), dungeons and eradication commissions, resource gathering and zone events, woodcutting, and the intro narrative (utils/quetes.py, transport.py, chasse.py, escorte.py, donjon.py, acces.py, pnj.py, lint_dialogues.py, bois.py, intro.py, routers/quetes.py, routers/pnj.py, jsons/pnj-*.json). Load whenever a request touches a quest, a PNJ or its dialogue JSON, a guard or locked door, a dungeon, table_evenements, harvesting or wood — including French requests such as « écris un dialogue », « quête de transport », « escorte », « un garde bloque l'accès », « laissez-passer », « donjon », « le choix ne s'affiche pas ».
---

Quêtes, PNJ, barrières d'accès et donjons. Tout ce contenu (docs `pnj:*`, blocs `acces`, `donjon:*`) part par `import-bulk`, un PUT complet (CLAUDE.md §11) ; valeurs à jour dans le dump, docs PNJ exportés dans `jsons/pnj-*.json`.


### Quêtes — guilde + moteur
**Lieu guilde** : `categorie:"guilde_aventurier"` + `lieu_parent`. Tableau généré (kill depuis les rencontres, collect depuis les ressources/carcasses du lieu) + quêtes authorées affichées à côté.

- Rotation **paresseuse** : offres générées à durée jittée, purge à l'ouverture et à l'acceptation ; le doc d'offre est supprimé à l'acceptation, l'accepteur en garde un snapshot. Mémoïsation locale à la passe (`_cached_getter`/`_cached_finder`).
- Renoncement ⇒ sanction de maison (`sanctionner_renoncement`) ; réussite ⇒ réputation au donneur (`recompenser_donneur`/`recompenser_lieux`, dédoublonnée par doc relation).
- Une maison peut ne porter qu'UNE cote : `relation_lieu` → `marche.lieu_de_relation` (un seul saut). Contenu `dev/gen_relation_guilde.py` → `jsons/relation_guilde_a_importer.json` (façade, réception et bureau du maître du Bastion).
- ⚠️ **Ne pas toucher `categorie`/`sous_categorie` du bureau** (`bureau_maitre_guilde`) : elles sont lues par les blocs `acces` de la mine et du temple-portail — les changer fermerait définitivement deux portes gardées.

Verrouillé par `tests/test_quetes_board.py`, `tests/test_quetes_endpoints.py`, `tests/test_quetes_relation.py`.


### Quêtes de transport — magasins + tenancier générique
Un magasin X confie une cargaison à livrer à un magasin Y qui la rachète, dans un délai réel. Réussite → +1 relation + XP + prime ; échec/abandon → sanction de maison, cargaison conservée (revendable). Logique pure `utils/transport.py`.

- Tenancier générique dérivé par catégorie (`transport.entree_marchand`) quand le lieu n'a pas de `pnj` explicite.
- **Deux sources d'offre** : générée à l'entrée du magasin (sous condition de confiance), ou **authorée** via `services.transport.offre` — ouverte à n'importe quel PNJ, hors bornes de poids/nombre.
- Cargaison bornée au poids/nombre max ; **courses à retour** (livraison sans paiement immédiat, solde au rapport) ; items de récompense en instances localisées ; géographie dérivée du graphe de portes ; mise en rayon probabiliste à la livraison ; expiration paresseuse.
- ⚠️ **Deux règles d'autorat** : les enseignes portent leur article (« Le Saloir ») — jamais de préposition devant `{destination}`, toujours un deux-points ; et un dialogue ne cite **jamais** un nom de PNJ en dur (les `pnj:marchand_*` sont génériques, chaque lieu rebaptise son tenancier via `nom`) — utiliser `{pnj}`/`{destinataire}`/`{donneur}`, sans pronom genré.
- Rôles de dialogue d'une course (donneur / destinataire) : § Contrôle des dialogues.

Verrouillé par `tests/test_transport.py`.


### Quêtes de chasse (élite à profil élevé) + rang de guilde
Objectif `chasse` : tuer **UN** ennemi d'une espèce marqué d'un **profil élevé**, dans un lieu précis. Logique pure `utils/chasse.py`.

- Deux canaux : tableau de guilde (grade `max−1`) et PNJ du comptoir (grade `max`, condition de gain de rang par cité).
- Grade résolu **à la génération**, jamais au combat (`resoudre_profil_chasse`, filtré par `restriction_tags`).
- Position cible bornée à la carte et ramenée sur une case franchissable (`borner_position`/`case_praticable_proche`, spirale de Chebyshev sur `combat._walkable`).
- En combat, `chasse.marquer_elites` ne promeut qu'**un seul** monstre par contrat, quand le joueur est dans la zone 3×3 de la cible — pas de vol d'élite entre deux contrats sur la même espèce.
- Rang de guilde (`rangs_guilde`, échelle `recrutement.RANGS`) plafonné **par comptoir** (`rang_max_de`, jamais le sommet de l'échelle par défaut). Contenu : `jsons/rang_plafond_borin_correctif.json`.
- **Carte 🗺️** : `quete_detail` ajoute `carte` à toute chasse **localisée** (image, dimensions, position, direction cardinale depuis la porte du donneur). Bouton 🗺️ aux deux rendus (Jinja + `renderFicheQuetes`), overlay `#quest-map-overlay` (`showQuestMap`) = crop 6×6 centré sur la cible. ⚠️ **Limite** : la position n'est garantie ni connectée à la région du joueur, ni dans la forme de sa zone — une cible sur un îlot isolé resterait inatteignable.

Verrouillé par `tests/test_chasse.py`.


### Quêtes d'ESCORTE — retrouver une personne, la ramener vivante
La réussite dépend de ce que le joueur **EMPÊCHE**, pas de ce qu'il tue ou porte. Logique pure `utils/escorte.py`, service PNJ `escorte`.

- Offre **ÉCRITE** (`services.escorte.offre`, n'importe quel PNJ), `rang_min` optionnel dérivé par la même source unique que les commissions de donjon (`acces.rang_de_quete`).
- Doc `protege:*` = miroir du character (stats de base raciales, aucun point dépensé) ; index `character["proteges"]` séparé — un protégé n'est **pas** un porteur.
- En combat, le protégé se comporte **comme une monture** : `jouable:False`, ciblable, hors `ordre_initiative` et hors `_combattants_vivants`.
- Trois formes de rendez-vous (chez le donneur, à l'entrée d'un lieu, zone 3×3 comme une chasse), résolues **à la génération** et figées dans le snapshot. ⚠️ Un rendez-vous se place toujours **derrière** la menace du combat de la mission (barrière `acces.combat_gagne` sur le lieu de rendez-vous), jamais devant.
- Échec (mort en combat ou abandon) ⇒ sanction du donneur et de sa maison, **sans consommer l'unicité**.
- **Focalisation 🎯 interdite** : une escorte ne biaise aucun tirage (même raison que le transport).
- **UI** : aucune UI neuve. Panneau 👥 → `🛡️ Sous votre protection` (cartes non éditables, non cliquables) ; jeton `.ally-token.protege` (anneau doré) ; badge en fin de bandeau d'initiative, ciblable pour le soin ; onglet 📜 : 🗺️ réutilise `_carte_chasse`. Dépose relayée par `sessionStorage` (`escorte_notif`) en **un seul toast MAJEUR** (arrivée · titre · récompenses).
- **Protégés qui SE DÉFENDENT** (`proteges[].se_defend`, ex. les paladins d'un convoi) : toujours `jouable:False` (défaite, échange de places, mort ⇒ échec inchangés) mais DANS `ordre_initiative`, pour un tour **joué par le serveur** (`combat._run_defenseur_turn`, appelé par `_resolve_until_player`) — jamais un pas, un coup sur l'ennemi au contact le plus entamé, budget d'actions ordinaire (`_frapper_monstre`, partagé avec le joueur). `proteges[].equipement` = `{slot: item}` posé dans les `slots` du doc (PA par zone, profil d'arme ; aucun contrôle de `restriction`). ⚠️ Le `bonus_malus_depl` des pièces lourdes retranche de V, donc des **actions**. UI : badge doré (retiré des acteurs hors tour), « ⚔️ Se défend au contact » sur la carte 👥, case + champ `équipement` dans `/admin/dialogues`.

Verrouillé par `tests/test_escorte.py`.

#### Escortes de PROGÉNITURE — les enfants des tenanciers
La seule escorte **GÉNÉRÉE**, et le premier canal qui la rende répétable.

- Un magasin dont l'entrée `pnj` du doc **LIEU** déclare une `progeniture` peut demander qu'on retrouve son enfant ; le comptoir de la guilde recense ces disparitions pour toute la cité.
- **Une quête par enfant**, id bâti sur le lieu du **MAGASIN** (jamais le donneur) : les deux canaux (parent, guilde) partagent l'id et ne permettent pas de ramener deux fois le même enfant.
- Rendez-vous **dérivé** des zones dangereuses de la carte de la cité (`modificateurs.danger > 0`), sans donnée à écrire par boutique.
- Deux portes : relation minimale du tenancier, ou tirage au comptoir. +1 de réputation des deux côtés quand donneur et destination diffèrent.
- Contenu : `dev/gen_escorte_marchands.py`, `dev/gen_progeniture.py`, `dev/gen_escorte_guilde.py`, `jsons/escorte_aline_varnepierre_a_importer.json`. ⚠️ Aline Varnepierre est dans les DEUX canaux et partage le même id — renommer le lieu ou corriger son prénom ferait diverger les ids **en silence** : `gen_progeniture.py` et cet import se retouchent ensemble.


### PNJ de lieu — dialogues à choix + services
- Un `lieu:*` porte `pnj:[{character, portrait, probabilite, conditions?}]` : tirage de présence à l'entrée, éventuellement **conditionné** (vocabulaire des barrières de lieu, fail-closed sans évaluateur injecté).
- Doc `type:"pnj"` : arbre de dialogue (`noeud_depart`, `noeuds`, choix filtrés serveur par condition) + **services** `soin` (gratuit/efficace au-dessus d'un seuil de relation), `don` (contrôle de charge), `acces`, `rang`, `commission`, `transport`, `escorte`.
- `"deplacer": "lieu:xxx"` sur un choix = résolution de la `connection`, jamais un déplacement direct : la logique reste dans `move_character`, avec tous ses effets de bord.
- Un nœud peut porter un **délai de réouverture** (`delai_min`/`noeud_attente`) et une **récompense de relation** versée une seule fois (`relation`, rouverte par `relation_reinit`).
- Conditions `quete_reussie`/`quete_active` = une quête **nommée**, testable depuis n'importe quel PNJ (≠ la clause d'accès homonyme, qui filtre par critères) ; un seul prédicat fail-closed, partagé avec le linter.
- Endpoints **stateless** `GET /api/pnj/dialogue` et `POST /api/pnj/dialogue/choix`, logique pure `utils/pnj.py`. UI `#pnj-panel`, portraits par le mount `/pnj`.

Verrouillé par `tests/test_pnj.py`, `tests/test_quete_reussie.py`, `tests/test_quete_active.py`, `tests/test_indicateurs.py`, `tests/test_guillemets_insecables.py`.


### Contrôle des dialogues PNJ (linter)
Un arbre de dialogue est de la **donnée** : ni typé, ni exécuté à l'import. Un `next` mort, un nœud de service mal nommé ou une condition mal orthographiée ne se voient **qu'en jouant la branche** — et un choix conditionné qui ne s'affiche jamais est indiscernable d'un tirage malheureux. D'où : passer le linter sur tout doc `pnj:*` écrit ou retouché.

- **`utils/lint_dialogues.py`** = logique PURE, source unique de deux appelants : le CLI `python dev/lint_dialogues.py [fichiers]` (sans argument : tous les `jsons/*.json` ⚠️ **sauf les `telluris-dump-*`**, archives d'états passés ; code 1 s'il reste une erreur) et le bouton **🔍 Vérifier les dialogues** de `/admin` (`POST /admin/lint-dialogues`, admin-only, lecture seule, mêmes formats de corps que `/admin/import-bulk`).
- `analyser(payload)` → `{analyses, ignores, erreurs, avertissements, trouvailles[]}` ; un doc sans bloc `dialogue` est *ignoré*, pas fautif.
- **Erreurs** : `noeud_depart` absent/introuvable · `next` vers un nœud inexistant · nœud **inatteignable** · nœud sans choix · deux choix de même `id` dans un nœud (`choix_valide` renvoie le premier, le second est mort) · nœud de service déclaré mais absent · placeholder hors liste · **condition inconnue du moteur** (flag absent = False → le choix ne s'affiche JAMAIS) · action `livrer`/`rapporter` non conditionnée par son flag · nom de PNJ en dur dans un `pnj:marchand_*` · bloc **`relation`** fautif (clé hors `RELATION_CLES`, `delta` nul ou illisible, `lieu` sans préfixe `lieu:`, `unique` non textuel) · **`relation_reinit`** qui ne lève rien — ⚠️ le plus coûteux à diagnostiquer : la récompense reste fermée pour toujours alors que le dialogue se déroule normalement.
- **Avertissements** : choix sans `next` ni `action` (ferme le dialogue comme `fin`, idiome valide) · nœud de service manquant (sauf `accepte` d'une escorte dont CHAQUE acceptation porte `deplacer` : le client quitte le dialogue, le nœud ne serait jamais lu).
- ⚠️ **Le transport a deux rôles**, presque jamais tenus par le même PNJ : **donneur** (`accepte`/`trop_charge`, + `rapporte` si `offre.retour`), que n'importe quel PNJ peut être ; **destinataire** (`livre`/`incomplet`), en pratique un `pnj:marchand_*`. Les exiger de tous ferait crier au défaut sur un donneur correct.
- ⚠️ Les listes de référence (`PLACEHOLDERS_CONNUS`, `FLAGS_CONNUS`, `NOEUDS_REQUIS`, `ACTIONS_A_CONDITIONNER`, `SOUS_FILTRES_CONNUS`) décrivent ce que `routers/pnj.py` consomme **réellement** : les tenir à jour avec tout nouveau service ou flag, sinon le linter signalera du code correct.


### Éditeur de dialogues et de quêtes authorées — `/admin/dialogues`
`admin_dialogues.html` édite un doc `pnj:*` par formulaire (identité, nœuds/choix en overlay, services) et les **quêtes authorées**, qui ne sont pas des `quete:*` mais les specs `services.transport.offre` / `services.escorte.offre`. Vue **graphe SVG en lecture seule** (couches BFS, `_dlgLayoutGraphe`) : nœuds inatteignables, `next` morts.

- ⚠️ **N'écrit RIEN en base** : produit le doc complet à coller dans la carte d'import. Lit `GET /admin/table/data?type=pnj`, se fait contrôler par `POST /admin/lint-dialogues` (accepte un doc seul) — le **linter reste la source** des contrôles ; le client rend seulement la plupart impossibles à saisir (`<select>` partout où le vocabulaire est fini).
- ⚠️ `_dlgFusionDoc` part du doc **relu** : ce que le formulaire ne possède pas doit survivre au niveau du doc, du nœud **et** du choix.
- ⚠️ **Vocabulaire servi par `main._vocabulaire_dialogues`**, jamais recopié en JS (même risque de dérive que `utils/capacites.py`). Il y ajoute `livre_retour` et `deja`, lus par `routers/pnj.py` mais absents des listes du linter.
- Une `action` sur un choix rend son `next` inopérant (la suite vient de `services.<x>.noeuds`) : la fusion le supprime. Une offre sans `destination`+`cargaison` (ou `proteges`) n'est pas écrite — `offre_spec` la rendrait inerte.
- Atteignabilité : les entrées incluent les **nœuds de service**, sans quoi une centaine de nœuds corrects passeraient pour du texte mort.
- Overlay et graphe se disputent la moitié droite : ouvrir l'un replie l'autre (`.dlg-split.compact`).

Verrouillé par `dev/test_dialogues_client.js` (fusion, atteignabilité, placement du graphe).


### Accès conditionné à un lieu — PNJ gardiens
Un `lieu:*` peut porter un bloc `acces` — sur le lieu de **destination**, jamais sur la connexion : `{gardien, refus, cycle, conditions:[...]}`, ET logique, **fail-closed** sur toute clé ou sous-clé inconnue. Logique pure `utils/acces.py`, chokepoint `acces_autorise`.

- **Clés** : `quete_active` (filtres sur une entrée de `quetes_actives` ; `objectif_atteint:false` ferme les boucles de donjon avant turn-in) · `quete_reussie` (`{id, attendu}`, quête archivée sans échec, même prédicat que la condition de dialogue ; masque les paladins d'Auxerre partis avec le convoi de Lutecia) · `item` · `rang_min` (échelle `recrutement.RANGS`) · `combat_gagne` (victoire enregistrée sur la **salle**, pas le décor) · `ou` (seule disjonction du moteur, sert aussi à exprimer le complément d'une conjonction) · `lieu_visite` (passage à usage unique).
- **Laissez-passer** persistant lié au `cycle` du lieu, posé par le service PNJ `acces` (miroir de `services.rang`). Une salle de donjon (`categorie:"battle_map"`) n'en pose jamais : franchir sa porte ouvre directement le combat.
- **Verrou** = lien caché (`get_lieu_links(filtrer_acces=True)`) **et** garde 403 autoritative dans `move_character` — le filtre d'affichage n'est pas le verrou.
- Flags `acces_libere`/`acces_menace` = état du **monde** (menace éliminée ou non, survit au turn-in) ; `acces_accompli` = commission faite mais pas rapportée.
- ⚠️ **Un bloc `acces` n'est pas une porte** : il faut aussi un doc `connection` (contrôlé par un BFS depuis la cité qui ignore les barrières).
- Contenu de référence : `dev/gen_acces_donjon.py`. **Dette assumée** : pas encore d'objectif `eradication` multi-espèces ; le cycle de reset n'est pas câblé (crochet en place).

Verrouillé par `tests/test_acces.py` et `tests/test_lieux_acces.py`, y compris le contrôle `conditions_invalides` (clé de 1er niveau vs sous-filtre).


### Donjons & commissions d'éradication
Un donjon est un lieu de combat **FERMÉ** : on y descend par une porte gardée, avec un mandat. Doc `donjon:*` : `{nom, portail, niveau_max?, niveau_min?, nb_monstres?, battle_maps:[{lieu, especes, niveau_max?, niveau_min?, nb_monstres?}]}`. Logique pure `utils/donjon.py`.

- Contenu **curaté salle par salle** (pas de zones d'influence) ; `donjon_de_lieu` est le seul lien salle → donjon.
- `niveau_max`/`niveau_min` bornent le grade de l'élite **et** de l'escorte, en cascade salle → donjon → aucune (le plancher cède au plafond en cas de conflit).
- `nb_monstres` fixe l'effectif **sans** bonus au nombre de compagnons, pour que les répliques narratives qui comptent les ennemis restent exactes.
- La commission est une quête `chasse` **ordinaire** (`source:"commission"`, hook générique, répétable, sans `unique`) ; son rang dérive de la barrière la plus stricte à franchir pour l'obtenir (`acces.rang_de_quete`, source unique partagée avec les escortes).
- Combat par `_declencher_combat_donjon` (miroir simplifié de `start_combat`, élite garantie, aucune furtivité d'entrée).
- Chaîne de contenu (`dev/gen_acces_donjon.py`) : rang D à Auxerre → Borin ouvre le bureau → Gautier mandate la commission → George contrôle le principe → Armand contrôle la destination et ouvre le combat.

Verrouillé par `tests/test_donjon.py`.


### Récolte de ressources et événements de zone
- Les lieux portent `ressources:[{ressource:"item:x", zones:[…]}]` (mode Ressources de l'éditeur → `PUT /api/lieu/{id}/ressources`).
- En déplacement, `resolve_zone_event` → `resolve_recolte` : les tags de `table_evenements` sont matchés contre `{categorie, sous_categorie, tags}` de l'item → `random.choice`. Résultat = champ transitoire `character["ressource_recoltable"]` (réf `{item, poids}`). `POST /api/recolter` refuse la surcharge (409). UI : 🌿 Récolter.
- ⚠️ **Seuls `combat` et `ressource` sont CONSOMMÉS** (par `/api/combat/start` et `ressource_recoltable`). `pnj`, `ambiance`, `quete`, `commerce`, `malus`, `tresor`, `meteo`, `piege`, `rien` n'ont **aucun code derrière** — `_zone_event_payload` ne publie plus que le combat.
- ⚠️ **Ne PAS les retirer des docs `zone_influence` pour autant** : ils pèsent dans le tirage pondéré comme « il ne se passe rien » ; les enlever redistribuerait leur poids sur les deux autres et ferait **bondir la fréquence des combats aléatoires**. C'est de la dilution volontaire, pas du contenu mort.


### Découpe du bois
Chaîne joueur, distincte des recettes PNJ. Logique pure `utils/bois.py`.

- Item coupable = tag `a_couper` + sous-catégorie ∈ `BOIS_A_COUPER`, découpé en pièces au sol qui conservent le poids exact (`repartir_poids`, bornée par `COUPE_MAX_PIECES`).
- Outil requis **partagé par le groupe** (`bois.a_outil_coupe` : sac + équipement, compagnons inclus).
- `POST /api/couper` (409 sans outil, 422 non coupable), `/api/recolter` étendu. UI : 🪓 Couper / 🪓 Abattre.

Verrouillé par `tests/test_bois.py`.


### Intro narrative — fuite du village natal
Bloc `intro` sur le doc lieu de la cité : spawn en périphérie, choix de raison persisté, conclusion à l'entrée en zone sûre (`est_dans_zone`). Logique pure `utils/intro.py`, verrouillée par `tests/test_intro.py`. ⚠️ Le doc de la cité est complet (avec `cells`) : ne jamais le retaper à la main, partir du dump.
