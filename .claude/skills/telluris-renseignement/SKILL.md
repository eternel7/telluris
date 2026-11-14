---
name: telluris-renseignement
description: Information gathering — "🔎 Se renseigner" lets a party member whose vocation has a method in the current place (tavern veterans, arm-wrestling, notice board, armoury gossip, scriptorium registers, school treatises, minstrel's song and tale swapping, fences, informants, tracks, hunters, beasts and plants, the Falcon spirit) learn WHERE a species or a resource can be found, read automatically from the place `rencontres`/`ressources` and their zones, dungeon rooms and shop stocks; d100 roll with three precision tiers, false rumours, a "hearsay" 👂 mark in the bestiary, a transportable note written by the Lettré, cost × tier, a per-place-and-method delay, place relation, generic tavern informant (utils/renseignement.py, routers/renseignement.py, rules:renseignement, dev/gen_renseignement.py). Load when working on rumours, informants, tracking a monster or resource location through an NPC or a place, the note de renseignement, or the 🔎 button — including French requests such as « se renseigner », « rumeur », « informateur », « où trouver ce monstre », « piste », « ouï-dire ».
---

# Renseignement — apprendre où se trouve une espèce ou une ressource

Spécification validée par l'Auteur (13-14/11/2026), implémentée. Module pur `utils/renseignement.py`, router `routers/renseignement.py` (`/api/renseignement/*`), contenu `dev/gen_renseignement.py` → `jsons/renseignement_a_importer.json` (`rules:renseignement` + `item:note_renseignement`). Verrouillé par `tests/test_renseignement.py` (pur) et `tests/test_renseignement_endpoints.py` (base en mémoire, VRAI doc du générateur).

## Principe
- **Aucune piste écrite à la main** : la réponse se DÉRIVE à la lecture. `rules:renseignement` = `{tags_nature, methodes[]}` ne dit que qui, où, à quel prix, sur quelles cibles. Ajouter une méthode = une entrée du générateur.
- **Méthode** (`normaliser_methode`) : `{id, nom, icon, vocations, informateur, lieu:{predicats, categories, tags}, test:[clés], cout, cout_pv ("monde" = `RENS_BRAS_DE_FER_PV`), cout_pm, connait, sources, portee_max, cibles:{especes, ressources, tags_espece, sous_categories, ecole_vocation, grade_min, elites}, modes, niveau_fixe, niveau_max, note, pourboire, repliques:{intro, description}}`.
- ⚠️ **Clé de caractéristique hors `v f r ag vol int cha ch`, prédicat, source, niveau ou mode inconnus ⇒ méthode REFUSÉE** (`ValueError`) : `methodes_de` l'écarte et la nomme (journal serveur) ; le générateur s'arrête. Jamais un 0 silencieux.

## Sources (`pistes_de`) et portée (`a_portee`)
- Lieux : entrée `rencontres`/`ressources` **avec** zones ⇒ une piste `zone` par zone (porteur = le lieu) ; **sans** zone ⇒ piste `lieu`. Matière sans récolte ⇒ repli carcasse → espèce (comme `guides.lieux_de_cible`).
- Donjons : salles (`battle_maps[].especes`) ⇒ piste `donjon`, mesurée au **portail**, inscrite sur la **salle** (là où le combat confirme l'ouï-dire).
- Boutiques : `stock_vente` à `qty > 0` ⇒ piste `boutique`.
- Portée : distances en liens (`focalisation.distances_depuis`) ; injoignable ⇒ écarté ; seuls les **`RENS_PORTEE_LIEUX` lieux porteurs** les plus proches (⚠️ les porteurs de piste, pas tous les lieux : depuis une taverne, la ville et ses boutiques rempliraient la portée) ; `portee_max` de la méthode en liens (forestier 1, faucon 0).

## Qui agit (`applicables`)
- Meilleur seuil parmi `expedition.membres` (principal EN TÊTE, jamais de monture) dont `voc` ∈ `vocations` et qui `connait` la compétence exigée (`pouvoirs_objets.connait`). Ex æquo : le premier.
- PV/PM et XP ⇒ l'**acteur** ; monnaie, carnet, bestiaire ⇒ le **principal**. Sauvegarde : principal (409), puis compagnon acteur, puis doc relation.
- **Informateur** : méthode `informateur:true`, offerte seulement si AUCUNE méthode de vocation ne s'applique et que `informateur_present` (champ transitoire tiré à l'entrée dans `main.py` après `poser_pnj_present`, `RENS_INFORMATEUR_PROBA`, même sémantique : no-op tant qu'on reste, re-tiré en revenant). Coût × `RENS_INFORMATEUR_MULT`, `niveau_max: region`.

## Cibles (modes)
`quete` (kill / collect / chasse ; chasse + `elites` ⇒ lieu exact et case, **sans jet**) · `bestiaire` · `libre` (`GET /renseignement/catalogue?methode&q`, ≥ 2 lettres, filtre de la méthode ; ⚠️ le `grade_min` n'est vérifié qu'à la recherche) · `hasard` (cibles du monde filtrées, couples déjà au bestiaire exclus, tirage pondéré 1/(1+d)) · `recit` (ménestrel : une paire VUE non encore cédée dans cette taverne, `recits_cedes`, contre une piste de rang ≤).

## Jet, niveaux, rumeur (`resoudre`)
- Seuil = 50 + moyenne des caracs (avec buffs) + `bonus_relation` = (relation − `RELATION_INITIALE`) × `RENS_RELATION_POIDS`, borné ± `RENS_RELATION_MAX` ; seuil borné [5, 95].
- d100 > seuil ⇒ **rumeur** ; ≤ seuil ⇒ **région** (`region_de` : cité, sinon pays) ; ≤ seuil × `RENS_EXACT_FACTEUR` ⇒ **exact** + grade (`rang_piste` : l'espèce, ou la pire espèce de l'endroit pour une ressource ; `potentiel.rang_espece` mémoïsé par révision).
- Rumeur : terrain (`TERRAINS` sur tags de zone/lieu) + distance ; **fausse** une fois sur `RENS_FAUSSE_PCT` (piste d'une AUTRE cible ; en hasard, on nomme une autre cible au terrain de la piste tirée). Sans piste : rumeur toujours fausse, sinon « personne n'en a entendu parler » (`rien`). Le client ne sait jamais si une rumeur est fausse.

## Ce que reçoit le joueur
- `apprendre` : espèce au niveau région/exact ⇒ `journal.noter_oui_dire` (lieu marqué `oui_dire`, payload préfixé **👂**, borné `JOURNAL_BESTIAIRE_LIEUX_MAX`) ; `journal.noter_rencontres` retire la marque au premier combat sur ce lieu. Carnet : une entrée par texte (relire ne répète rien). Ressource et rumeur : carnet seul.
- **Note** (`note:true`, Lettré) au niveau région/exact, jamais sur rumeur : ref `{item: item:note_renseignement, piste, auteur_nom}` dans le sac de l'acteur (si la charge le permet). `resolve_item_ref` en fait la description et le titre ; `item_sale_price_cuivre` ⇒ `prix_note` (XP du plancher du rang, `xp_monstre.prix_de_xp`). `POST /renseignement/lire {index}` (sac du principal, bouton 📖 de la fiche objet) l'inscrit chez le lecteur.
- XP `RENS_XP_BELLE` à l'acteur sur belle réussite **au jet** ; pourboire du ménestrel = `cout × RENS_POURBOIRE_FACTEUR + RENS_POURBOIRE_DES`.

## Limites
- Délai `RENS_DELAI_MINUTES` par lieu × méthode (`renseignements_at`, purgé au passage).
- Bourse ≥ `cout_max` exigée AVANT le jet ; débit = `cout × RENS_COUT_MULT[niveau]` (`rien` ⇒ prix rumeur). PM vérifiés avant ; PV jamais sous 1.
- Recherche payée ⇒ `marche.compter_transaction` sur la relation du lieu.

## Méthodes livrées
| Id | Vocation(s) | Lieu | Test | Coût | Cibles |
|---|---|---|---|---|---|
| `veterans` | guerrier | taverne | cha, f | 12 | espèces |
| `bras_de_fer` | barbare | taverne | f | PV (`monde`) | espèces rang ≥ D |
| `tableau` | paladin, templier | taverne | — (région) | 5 | espèces du Mal |
| `salle_d_armes` | duelliste | `armurerie`, `grand_arsenal`, tag `salle_d_armes` | ag, cha | 10 | espèces |
| `registres` | lettre | scriptorium | int | 15 | tout ; note |
| `ouvrages` | elementaliste, mage, illusionniste | scriptorium | int | 15 | composants de l'école, espèces magiques, cristaux |
| `chanson` | menestrel | taverne | cha | 8 + pourboire | espèces |
| `recits` | menestrel | taverne | cha | — | récit contre piste |
| `receleurs` | voleur | taverne, `negociant` | ag, cha | 12 | ressources (boutiques) |
| `indicateurs` | assassin | taverne | cha | 40 | espèces, élites |
| `pistes` | forestier | sauvage | int, ag | — | ici + contigus |
| `chasseurs` | forestier | taverne, `boucherie` | cha | 8 | bêtes |
| `betes_plantes` | druide | sauvage | int | 6 PM | bêtes, végétaux |
| `faucon` | chaman | pays + Œil du faucon | int | PM de la compétence | zones de la carte |
| `informateur` | — | taverne | cha | 10 × 1,5 | ≤ région |

- **Zone sauvage** (`est_sauvage`) = pays OU `tags_nature` OU rencontres/ressources OU hors cité.
- **`salle_d_armes`** : recopié dans `utils/capacites.py` (case de l'éditeur), verrouillé par `tests/test_capacites.py`. ⚠️ Le prédicat `scriptorium` est recopié de `scriptorium.lieu_est_scriptorium` (verrouillé par `test_predicat_scriptorium_identique_au_vrai`).
- Bouton 🔎 de `/play` : `routers/renseignement.disponible` (index réduit à la chaîne du lieu, pas les 700 lieux) ; panneau `#rens-panel` (⟵ / Échap ferment sans rien payer).

## Variables de monde
`RENS_DELAI_MINUTES` 240 · `RENS_PORTEE_LIEUX` 12 · `RENS_FAUSSE_PCT` 20 · `RENS_EXACT_FACTEUR` 0,5 · `RENS_RELATION_POIDS` 0,2 · `RENS_RELATION_MAX` 15 · `RENS_COUT_MULT` {rumeur 1, region 1,5, exact 2} · `RENS_BRAS_DE_FER_PV` 1D6 · `RENS_INFORMATEUR_MULT` 1,5 · `RENS_INFORMATEUR_PROBA` 0,5 · `RENS_POURBOIRE_FACTEUR` 2 · `RENS_POURBOIRE_DES` 1D10 · `RENS_XP_BELLE` 10.
