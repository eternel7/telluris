---
name: telluris-renseignement
description: Information gathering — "🔎 Se renseigner" lets a party member whose vocation has a method in the current place (tavern veterans, arm-wrestling, notice board, armoury gossip, scriptorium registers, minstrel's song and tale swapping, fences, informants, tracks, beasts and plants, the Falcon spirit) learn WHERE a species or a resource can be found, read automatically from the place `rencontres`/`ressources`, influence zones, dungeon rooms and shop stocks; d100 roll with three precision tiers, false rumours, a "hearsay" mark in the bestiary, a transportable note written by the Lettré, cost × reach, a per-place-and-method delay, place relation, generic tavern informant (planned: utils/renseignement.py, routers/renseignement.py, rules:renseignement). Load when working on rumours, informants, tracking a monster or resource location through an NPC or a place, or the 🔎 button — including French requests such as « se renseigner », « rumeur », « informateur », « où trouver ce monstre », « piste », « ouï-dire ».
---

# Renseignement — apprendre où se trouve une espèce ou une ressource

> ⚠️ **SPÉCIFICATION VALIDÉE (13/11/2026), NON IMPLÉMENTÉE.** Les noms de modules, de champs et de variables ci-dessous sont ceux à créer en phase 2. Mettre à jour cette compétence au fil de l'implémentation : ce qui est fait remplace ce qui est prévu.

## Principe
- **Aucune donnée écrite à la main par piste.** La réponse à « où trouver X » se **DÉRIVE à la lecture** des sources du monde ; le doc `rules:renseignement` ne dit que **qui** peut demander, **où**, **à quel prix** et **sur quelles cibles**.
- **Ajouter une méthode = une entrée du doc**, sans toucher au code (convention 11 : générateur `dev/gen_renseignement.py`, PUT complet).
- Module pur `utils/renseignement.py` (DB injectée, mute sans sauver, hasard par `rand_fn`), router `routers/renseignement.py` (`/api/renseignement/*`).

## Sources d'une piste (toutes, réunies)
- **Lieux** : `rencontres[].espece` et `ressources[].ressource` — mêmes champs que `focalisation.boost_zone_event` et `guides.lieux_de_cible` (repli carcasse → espèce compris). ⚠️ Contenu mince (7 lieux à rencontres, 5 à ressources au dump du 13/11) : les zones et les donjons portent l'essentiel.
- **Zones d'influence** : tables de rencontres/ressources des `zone_influence` peintes sur les cartes de pays → piste = (carte, zone), sans case.
- **Donjons** : espèces des salles curatées (`utils/donjon.py`, mode à étages compris).
- **Boutiques** : pour une ressource, la boutique qui l'a **en stock maintenant** (`marche`), en plus du lieu de récolte.
- **Portée** : seuls les `RENS_PORTEE_LIEUX` lieux les plus proches comptent (`focalisation.distances_depuis` sur le graphe des connexions) ; une zone ou un donjon se mesure à son lieu porteur.

## Qui agit
- **Le groupe** : le meilleur membre de `expedition.membres` (principal EN TÊTE, **jamais de monture**) dont la vocation a une méthode applicable ici — comme `traces.pisteur` ou le négociateur. Ex æquo : le premier gagne (le joueur).
- Le coût en PV/PM est payé par **celui qui agit** ; le coût en monnaie par le **principal**. Sauvegarde : convention 1 (`_save_acteur`, porteur autoritatif d'abord).
- **Vocations sans méthode** : informateur générique **tiré en taverne** (§ Informateur).

## Cible
Désignée dans l'overlay 🔎, parmi :
- **Quêtes actives** kill / collect, préremplies (comme `guides.sujets`) ; l'élite d'une **chasse** active pour l'Assassin seul ;
- **Bestiaire** : toute espèce déjà rencontrée ;
- **Recherche libre** : toute espèce ou matière du catalogue, **filtrée par la méthode** ;
- **« Ce qui traîne »** : sans cible, une source tirée parmi celles de la méthode, pondérée vers les lieux proches.

## Jet et précision
- **Seuil d100** (convention des pièges, `pieges.seuil_detection`) = `50 + moyenne(caractéristiques de la méthode) + bonus de relation`. Clés **du personnage uniquement** : `v f r ag vol int cha ch` — une clé inconnue est **refusée à la lecture** du doc (jamais un 0 silencieux).
- **Trois niveaux** :
  - jet > seuil → **rumeur** (§ Rumeur) ;
  - jet ≤ seuil → **cité ou région** : premier ancêtre notable par `guides.chaine` (la cité, sinon la carte de pays) ; pour une zone : carte + nom de zone ;
  - jet ≤ seuil × `RENS_EXACT_FACTEUR` (défaut 0,5) → **lieu exact + grade** de la pire menace (`traces.menace_lieu`, libellé de rang).
- Méthode **sans test** (Paladin, Templier ; Assassin sur une élite) : directement le niveau que dit la méthode.

## Rumeur (échec)
- **Vague** : une direction ou un type de terrain du lieu visé (« du côté des forêts, vers le sud »).
- **Fausse** une fois sur `RENS_FAUSSE_PCT` : elle désigne une source où la cible n'est **pas**. Le joueur ne sait pas laquelle des deux il a reçue.
- Une rumeur **n'entre jamais au bestiaire** ; seulement au carnet.

## Ce que reçoit le joueur
- **Espèce** : le lieu entre au bestiaire **marqué 👂 « ouï-dire »** ; `journal.noter_rencontres` le passe en « vu » au premier combat contre l'espèce. Plus une ligne de carnet (`journal.nouvelle_entree`).
- **Ressource** : **carnet seul** (pas de registre des ressources).
- **Grade** de la menace au niveau « lieu exact ».
- **Note de renseignement** — **Lettré seulement** :
  - un **seul** doc item générique (« Note de renseignement ») ; la piste vit dans la **référence** (comme l'écrit personnel du scriptorium) : aucun doc par piste ;
  - **la lire** inscrit la piste chez le lecteur (bestiaire 👂 + carnet), même achetée ou reçue ;
  - **vendable aux négociants** : prix dérivé du grade décrit (paliers de `xp_monstre`).
- **XP** : `grant_xp` de `RENS_XP_BELLE` à celui qui agit, **sur belle réussite seulement**.
- Resync (convention 10) : bloc `fiche` si XP, bestiaire/carnet, `inventaire_payload` si note ou monnaie, PV/PM de l'acteur.

## Limites (vérifiées au passage, aucun tick — convention 5)
- **Délai** : une recherche par personnage × **lieu × méthode** pendant `RENS_DELAI_MINUTES` ; horodatage sur le principal (`renseignements_at`, champ absent ⇒ jamais demandé). Deux vocations du groupe = deux méthodes = deux essais.
- **Coût** : `cout` (cuivre) de la méthode × `RENS_COUT_MULT` selon l'échelon atteint (rumeur : coût de base seul) ; débité au serveur.
- **Relation de lieu** (`marche` relations) : **bonus au seuil** = relation × `RENS_RELATION_POIDS`, plafonné à `RENS_RELATION_MAX` ; une recherche payée **améliore la relation** comme un achat.

## Méthodes
| Id | Vocation(s) | Lieu (prédicats existants, OU) | Test | Coût | Cibles |
|---|---|---|---|---|---|
| `veterans` | guerrier | `auberge.lieu_est_taverne` | cha, f | cuivre | espèces, donjons (+ grade) |
| `bras_de_fer` | barbare | taverne | f | **PV** : `RENS_BRAS_DE_FER_PV`, jamais sous 1 | espèces de grade ≥ `grade_min` |
| `tableau` | paladin, templier | taverne (tableau d'information) | — | cuivre | espèces `undead` `non_mort` `demon` `infernal` `monstre`, donjons |
| `salle_d_armes` | duelliste | catégories `armurerie`, `grand_arsenal` OU tag `salle_d_armes` | ag, cha | cuivre | espèces |
| `registres` | lettre | `scriptorium.lieu_est_scriptorium` | int | cuivre | **toutes** sources ; produit la note |
| `ouvrages` | elementaliste, mage, illusionniste | scriptorium | int | cuivre | composants des sorts de **l'école de la vocation** (dérivés de `sorts`, jamais recopiés), espèces `magique`/`elementaire`, items `sous_categorie: cristal` |
| `chanson` | menestrel | taverne | cha | cuivre ; belle réussite ⇒ pourboire `RENS_POURBOIRE` | espèces, zones, donjons |
| `recits` | menestrel | taverne | cha | une paire (espèce, lieu) du bestiaire, jamais échangée dans cette taverne ; il la **garde** | piste neuve de grade ≤ celle cédée |
| `receleurs` | voleur | taverne OU catégorie `negociant` | ag, cha | cuivre | ressources (stocks des boutiques, lieux de vente) |
| `indicateurs` | assassin | taverne | cha | cuivre **élevé** | espèces ; élite de chasse active : lieu exact, **sans jet**, coût maximal |
| `pistes` | forestier | zone sauvage | int, ag | — | espèces et ressources des lieux **contigus** (prolonge `traces.py`) |
| `chasseurs` | forestier | taverne OU catégorie `boucherie` | cha | cuivre | espèces `animal` `proie` `predateur` |
| `betes_plantes` | druide | zone sauvage | int | **PM** | espèces `animal` `proie` `predateur` ; items `herbe` `baie` `graines` `fruit_sec` `arbre` `branche` |
| `faucon` | chaman | catégorie `pays` + **connaît** `competence:il_du_faucon` | int | **PM** de la compétence | zones d'influence de la carte et leurs espèces |

- **Zone sauvage** = catégorie `pays` OU tag nature (`foret` `bois` `clairiere` `clariere` `lande` `montagne` `gorge`…, liste dans la méthode) OU lieu à `rencontres`/`ressources` non vides OU lieu **hors cité** (`guides.cite_de` nul).
- **Nouveau tag** `salle_d_armes` : à recopier dans `utils/capacites.py` ET dans le prédicat d'origine (verrouillé par `tests/test_capacites.py`).
- Une méthode = `{id, vocations, lieu: {categories, tags, predicats}, test: [clés], cout, cout_pv, cout_pm, condition (connait), sources, filtre: {tags_espece, sous_categories, grade_min}, niveau_fixe, produit_note, repliques}`.

## Informateur
- PNJ générique **tiré à l'entrée** de chaque taverne (champ transitoire `pnj_present`, convention 6), pour un joueur dont le groupe n'a **aucune** méthode ici.
- Même moteur : test sur cha, coût × `RENS_INFORMATEUR_MULT`, **jamais de belle réussite** (au mieux cité ou région).

## Interface (/play)
- Bouton **🔎 Se renseigner** dans le panneau du lieu, à côté des services, affiché **dès qu'une méthode s'applique** (dérivé à la lecture, renvoyé avec le payload du lieu).
- Overlay : choix de la méthode si le groupe en a plusieurs → choix de la cible (onglets quêtes / bestiaire / recherche / ce qui traîne) → coût et délai affichés avant validation.
- Convention 8 : ✕ / Échap / clic sur le fond ⇒ **annuler sans rien payer**, la promesse se résout à `null`.

## Variables de monde (défauts « jeu standard »)
| Variable | Défaut |
|---|---|
| `RENS_DELAI_MINUTES` | 240 |
| `RENS_PORTEE_LIEUX` | 12 |
| `RENS_FAUSSE_PCT` | 20 |
| `RENS_EXACT_FACTEUR` | 0,5 |
| `RENS_RELATION_POIDS` / `RENS_RELATION_MAX` | 0,2 / 15 |
| `RENS_BRAS_DE_FER_PV` | `1D6` |
| `RENS_INFORMATEUR_MULT` | 1,5 |
| `RENS_COUT_MULT`, `RENS_POURBOIRE`, `RENS_XP_BELLE` | à fixer à l'implémentation (non tranchés) |

## Tests à écrire (phase 2)
- `tests/test_renseignement.py` : sources réunies, portée, filtres par méthode, trois niveaux (`rand_fn` injecté), rumeur fausse jamais au bestiaire, 👂 → « vu », délai par lieu × méthode, coût par échelon, PV jamais sous 1, clé de caractéristique inconnue refusée, monture jamais acteur.
- Harnais Node si l'overlay porte une logique pure (annulation → `null`).
