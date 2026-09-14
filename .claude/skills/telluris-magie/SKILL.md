---
name: telluris-magie
description: Spells, vocation skills and focus — PM-costed spells with components/schools, vocation active/passive skills (mirrors spells), and the guidance/quest-bias focalisation mechanic (utils/sorts.py, competences.py, focalisation.py). Load when working on spells, vocation skills, or the focalisation system.
---

### Sorts — PM, composants, écoles
Doc `sort:*` : `{nom, vocation, magie, niveau, cout_pm (>0), cible, jet, portee, effets, composants[]}`. Logique pure `utils/sorts.py`. Composants consommés (retirés du sac, gros bonus) ou catalyseurs (`consomme:false`, simplement portés, bonus moindre) fusionnent additivement leurs effets. Contexte (combat/exploration) dérivé de la cible et de la présence de dégâts, jamais déclaré. Apprentissage par vocation à la création, par **école de magie** ensuite (`magie` du sort, repli sur l'école de la vocation) — seules les vocations polyvalentes peuvent acheter d'autres écoles que leur école native, sans impact sur les dérivées. Combat : action `"sort"`, PM débités **avant** le jet (raté = dépensés), dégâts magiques sans soustraction de PA. Le champ `jet` (cc/cd/magique, partagé avec les compétences) pilote la résolution du toucher — défaut `cc` pour une compétence, `magique` pour un sort, délibérément différent. Toute cette mécanique est couverte par `tests/test_sorts.py` et `tests/test_sorts_jet.py`.

**UI** : onglet ⚡ (sorts connus + 📖 Apprentissage + 🏫 Écoles) ; en combat l'accès passe par les slots, ciblage **violet**.

Contenu : `jsons/sort-exemples.json`, `update_sorts.json`, `magie_naturelle_sorts.json`, `sorts_nature_elementaire_a_importer.json`, `sorts_bataille_illusoire_noire_sainte_a_importer.json`, `repurgateur_magie_noire_a_importer.json`.


### Familles — exclure un TYPE de sort/compétence d'une vocation
Doc `sort:*`/`competence:*` : `famille` (étiquette libre, ex. `"invocation"`) ; entrée de `rules:vocations` : `familles_exclues: [...]`. L'intersection n'est ni listée (`sorts_apprenables`, `competences_apprenables`) ni achetable (`apprendre_sort`, `apprendre_competence` → 422). Source unique `sorts.apprentissage_exclu`, partagée par les deux familles ; `competences_apprenables(character, find_docs, rules_vocations=None)` — argument omis ⇒ aucune exclusion. Champ absent des deux côtés ⇒ comportement d'avant (aucune migration). Cas d'usage : le **répurgateur** pratique la `Démonologie` du démoniste **sans ses invocations**. Verrouillé par `tests/test_familles_exclues.py`.


### Invocations — une créature alliée de plus sur la grille
Bloc `invocation` d'un doc `sort:*` : `{espece, profil?, nombre (≤ 4), duree}`. `profil` vide = point médian de l'espèce au niveau 1 (**déterministe** ; un `profil:*` passerait par `random`). COMBAT SEULEMENT (`sort_utilisable_exploration` la refuse : il n'y a pas de grille où la poser), et **exclusive** de `effets` — la créature EST l'effet du sort, ses `composants` seraient inertes.

Le snapshot est un `build_monster_snapshot` re-keyé en `joueur_*` (`build_invocation_snapshot`) : `jouable: False` + `est_invocation`, **sans `character_id`** — ce qui suffit à le faire sauter par `finalize_combat` et par les bénéficiaires de `/collect` (ni XP, ni butin, ni doc). Elle a un TOUR, joué par le serveur (`_run_invocation_turn` : A* vers l'ennemi vivant le plus proche puis frappe), donc elle est dans `ordre_initiative` — **insérée juste après l'acteur courant**, jamais à son rang d'initiative (sinon `acteur_courant_index` désignerait un autre acteur en plein tour). Elle se dissipe à `invocation_restants` = 0 ou à 0 PV ; `_purger_invocations` (en tête de `_resolve_until_player`) la retire des DEUX listes et recale l'index. ⚠️ Son id vient de `_prochain_index_joueur` (compteur sur le doc), **jamais de `len(joueurs)`** : un indice libéré par une purge et réattribué ferait s'appliquer à la nouvelle créature les `etat` de journal de l'ancienne. ⚠️ `jouable: False` ⇒ elle ne compte pas dans `_combattants_vivants` : un groupe à terre perd même si elle tient debout. UI : jeton et badge VIOLETS, exclue de la liste « hors tour » du bandeau. Verrouillé par `tests/test_invocations.py`.


### Compétences de vocation — passives + actives (miroir des sorts)
Doc `competence:*` : même schéma d'`effets` que les sorts, sans composants, `cout_pm ≥ 0`. Logique pure `utils/competences.py`. Choix à la création pour toute vocation hors `SORT_VOCATIONS_DEPART` (un sort **ou** une compétence, jamais les deux). Passive = buffs/régén permanents dénormalisés dans `competences_bonus`. Active = 1 action + PM, jet porté par la donnée (martial avec soustraction de PA, magique sans). **Une frappe de contact (`jet:"cc"`) emprunte les dés ET l'allonge de l'arme équipée** (chokepoints `combat._degats_competence`/`_portee_competence`) — sans quoi une active payante frapperait moins fort et moins loin qu'une attaque gratuite ; `ranged` en dérive (`portee > allonge`), ce qui pilote aussi la rupture de furtivité. Furtivité et détection (jet de détection par monstre à son tour, rupture au corps-à-corps, la cible seule tente un jet à distance) sont couvertes par le même chokepoint `_furtivite_apres_offensive`. Toute cette mécanique est couverte par `tests/test_competences.py`.

Apprentissage : `POST /api/apprendre_competence`, coût `(niveau+1)×COMPETENCE_COUT_COEFF`, pas de grimoire. Contenu : `jsons/competences_niveau0.json`, `new_comp0.json`.


### Focalisation — 🧭 lieu / 🎯 quête
Un personnage focalise **UNE seule chose à la fois** (`character["focalisation"]`). Guidage (lieu) par BFS sur le graphe de `connection` + direction A* ; biais (quête) sur le tirage d'événement/espèce (`FOCUS_EVENEMENT_MULT`/`FOCUS_CIBLE_MULT`) ; effacement automatique à l'arrivée, à la fin de quête ou à l'objectif atteint. Logique pure `utils/focalisation.py`, couverte par `tests/test_focalisation.py`. `POST /api/focaliser` → `{focalisation, guidage}`. UI : boutons 🧭 (onglet 🤝) et 🎯 (onglet 📜).

