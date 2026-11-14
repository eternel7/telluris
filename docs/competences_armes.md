# Exigence d'arme des compétences — proposition

GÉNÉRÉ par `dev/gen_competences_armes.py` depuis `jsons\telluris-dump-20261114-152355.json` — ne pas éditer à la main :
corriger la table `EXCEPTIONS` du script, puis le relancer.

Règles par défaut : frappe `cc` à dés → arme de mêlée ; tir `cd` → arme de tir (arc si le texte parle de flèche) ; magie, soutiens et passives → rien.
Les **exceptions** (⭐) sont écrites à la main : cris, coups de pied ou d'épaule, fioles, poudres, vols, moine, jet, deux armes, boucliers, lames courtes, postures, passives.

- **233** compétences reçoivent une exigence.
- **77** frappes martiales restent **sans exigence** (dernière colonne « — »).
- Boucliers rangés en `sous_categorie: bouclier` : Bouclier de croupon, Targe à énarmes.

⚠️ À relire en priorité : « Héros » (paladin, R +10) devient inactive sans bouclier, « Maîtrise du trait » sans arme de tir ou de jet ; les frappes aux couteaux lancés (éventail, danse, tempête) restent des frappes de MÊLÉE exigeant une lame, pour ne pas devenir interdites au contact.

## assassin

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Frappe sournoise | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Coup de dague | cc | une arme de mêlée (tranchante) | ⭐ une dague |
| 1 | Entaille au tendon | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Lame enduite | cc | une arme de mêlée (tranchante) | ⭐ venin sur le fil d'une lame |
| 2 | Coup dans le dos | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Double lame | cc | deux armes de mêlée | ⭐ « ses deux lames » |
| 2 | Fiole de belladone | cc | — | ⭐ fiole |
| 2 | Garrot | cc | — | ⭐ cordelette |
| 3 | Perce-cœur | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Poudre de pavot | cc | — | ⭐ poudre |
| 3 | Surineur | passive | une arme de mêlée (tranchante) | ⭐ « sa dague trouve l'ouverture » |
| 3 | Venin d'aspic | cc | — | ⭐ poison |
| 3 | Venin de contact | cc | une arme de mêlée (tranchante) | ⭐ venin sur le fil d'une lame |
| 4 | Coup au cœur | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Fleur de lames | cc | deux armes de mêlée | ⭐ « ses deux lames » |
| 4 | Sang du contrat | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Toxine paralysante | cc | — | ⭐ poison |
| 5 | Essence de mandragore | cc | — | ⭐ poison |
| 5 | Venin double | cc | une arme de mêlée (tranchante) | ⭐ deux poisons dans la même entaille |
| 5 | Égorgement | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Lame dans les reins | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Marque de mort | cc | — | ⭐ marque |
| 6 | Maître lames | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Nuage toxique | cc | — | ⭐ fiole lancée |
| 6 | Voler le souffle | cc | — | ⭐ coup au plexus |
| 7 | Assassinat | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Danse des dagues | cc | une arme de mêlée (tranchante) | ⭐ dagues ; reste une frappe de mêlée (un mode `jet` la rendrait interdite engagé) |
| 7 | Saignée silencieuse | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Venin du scorpion noir | cc | — | ⭐ poison |
| 8 | Coup du cobra | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Oubli de la douleur | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Poudre de sommeil | cc | — | ⭐ poudre |
| 8 | Venin de l'âme | cc | — | ⭐ poison |
| 8 | Éventail de dagues | cc | une arme de mêlée (tranchante) | ⭐ couteaux lancés ; reste une frappe de mêlée (même raison) |
| 9 | Brume empoisonnée | cc | — | ⭐ brume |
| 9 | Exécution silencieuse | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Peste noire | cc | — | ⭐ fiole |
| 10 | Exécution | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Fiole du maître empoisonneur | cc | — | ⭐ fiole |
| 10 | Fléau silencieux | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Mort certaine | cc | une arme de mêlée | frappe portée avec l'arme |

## barbare

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Coup de fureur | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Coup de hache | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Hurlement | cc | — | ⭐ cri |
| 1 | Morsure du fer | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Fracas | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Taille sauvage | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Tourbillon de lames | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Tête la première | cc | — | ⭐ coup de tête |
| 3 | Fendeur de crânes | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Griffes de l'ours | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Frappe du mammouth | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Rage qui ronge | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Tourbillon sauvage | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Brise-os | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Charge du sanglier | cc | — | ⭐ charge du corps |
| 5 | Fauche | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Folie sanglante | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Griffe de la bête | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Massacre | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Rugissement | cc | — | ⭐ cri |
| 7 | Fendoir des montagnes | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Festin du carnage | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Hémorragie | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Transe sanglante | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Briseur de lignes | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Coup de tonnerre | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Griffes du grand ours | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Terreur des steppes | cc | — | ⭐ regard |
| 9 | Décapitation | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Folie du massacre | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Séisme | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Carnage | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Coup du fléau des clans | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Sang pour sang | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Spasme de furie | cc | une arme de mêlée | frappe portée avec l'arme |

## chaman

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 1 | Griffe du loup | cc | — | ⭐ griffes d'esprit |
| 3 | Ruée du sanglier-esprit | cc | — | ⭐ ruée |
| 5 | Crocs de l'esprit | cc | — | ⭐ esprit-loup |
| 7 | Esprit du sanglier | cc | — | ⭐ fureur d'esprit |

## druide

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 3 | Trait du chasseur | cd | une arme de tir ou une arme de jet | ⭐ « arc, fronde, javelot, lance » |

## duelliste

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Fente | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Battement | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Coup droit | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | En garde | soi | une arme de mêlée | ⭐ posture de la lame |
| 1 | Poignet souple | passive | une arme de mêlée | ⭐ « la lame tourne dans sa main » |
| 1 | Riposte | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Coup de manchette | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Estafilade | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Flèche | soi | une arme de mêlée | ⭐ course pointe en avant |
| 2 | Taille en tierce | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Botte de mousquetaire | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Danse des lames | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Double attaque | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Désarmement | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Garde élégante | soi | une arme de mêlée | ⭐ posture de la lame |
| 4 | Coup de Jarnac | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Fente basse | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Volte | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Coup de pointe | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Liement | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Moulinet du bretteur | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Saignées multiples | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Coup de maître | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Humiliation | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Parade de maître | soi | une arme de mêlée | ⭐ parade |
| 6 | Éventail d'acier | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Botte secrète | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Coup de pied de salle | cc | — | ⭐ coup de botte |
| 7 | Coup du papillon | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Lame vivante | passive | une arme de mêlée | ⭐ « l'épée … pare d'elle-même » |
| 7 | Prise de fer | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Pointe au cœur | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Saignée d'artère | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Tourbillon du bretteur | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Coup du roi | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Garde absolue | soi | une arme de mêlée | ⭐ « il détourne toutes les lames » |
| 9 | Main paralysée | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Sang du duel | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Vent de lames | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Ballet mortel | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Coup de l'Exécuteur | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Coup parfait | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Maître d'armes | passive | une arme de mêlée | ⭐ « l'arme … c'est le bout de son bras » |

## forestier

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Tir précis | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 1 | Coup de couteau | cc | une arme de mêlée (tranchante) | ⭐ couteau de chasse |
| 1 | Tir aux jambes | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 1 | Trait rapide | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 2 | Tir à longue portée | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 2 | Trait barbelé | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 2 | Volée | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 3 | Cri du faucon | cd | — | ⭐ sifflement |
| 3 | Marque du gibier | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 3 | Tir dans la mêlée | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 3 | Trait perforant | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 4 | Lame et pointe | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Tir à l'œil | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 4 | Trait de chasse | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 5 | Pluie de traits | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 5 | Trait lointain | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 5 | Trait venimeux | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 6 | Clouer au sol | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 6 | Tir d'élite | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 6 | Trait épuisant | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 7 | Saignée de cerf | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 7 | Tir mortel | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 7 | Volée en éventail | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 8 | Couteau du dépeceur | cc | une arme de mêlée (tranchante) | ⭐ couteau |
| 8 | Grêle de traits | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 8 | Tir transperçant | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 8 | Trait aveuglant | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 9 | Maîtrise du trait | passive | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 9 | Tir de suppression | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 9 | Trait du roi des bois | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 9 | Venin du marais | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 10 | Ciel de traits | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 10 | Proie épuisée | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 10 | Trait de légende | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 10 | Trait du chasseur de monstres | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |

## guerrier

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Frappe puissante | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Balayage | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Bousculade | cc | — | ⭐ coup d'épaule |
| 1 | Coup d'estoc | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Garde haute | soi | un bouclier | ⭐ « le bouclier remonte » |
| 2 | Coup de taille | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Pommeau au visage | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Taille horizontale | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Cercle d'acier | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Coup de mercenaire | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Frappe du vétéran | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Mur de boucliers | soi | un bouclier | ⭐ « il lève le bouclier » |
| 3 | Taillade aux jarrets | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Coup de bélier | cc | — | ⭐ coup d'épaule |
| 4 | Coup du maître de corps | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Lame lourde | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Brise-garde | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Estocade | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Fauchage | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Coup de grâce | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Défi | cc | un bouclier | ⭐ « il frappe son bouclier » |
| 6 | Garde de fer | soi | une arme de mêlée | ⭐ garde fermée |
| 6 | Vague d'acier | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Frappe de siège | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Hachoir | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Lame tournoyante | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Moulinet | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Tranche-armure | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Écrasement | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Assaut sanglant | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Coupe-tête | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Fracasse-bouclier | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Ouragan d'acier | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Brise-ligne | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Coup du seigneur de guerre | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Tempête de lames | cc | une arme de mêlée | frappe portée avec l'arme |

## mage

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 1 | Lame chargée | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Lame de mana | cc | — | ⭐ lame de mana pur |
| 6 | Lame enchantée | soi | une arme de mêlée | ⭐ « il enchante sa propre arme » |
| 8 | Frappe runique | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Lame du mage-guerrier | cc | une arme de mêlée | frappe portée avec l'arme |

## menestrel

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 1 | Coup de luth | cc | une arme de mêlée (instrument) | ⭐ le luth |
| 5 | Lame du conteur | cc | une arme de mêlée (tranchante) | ⭐ une dague |

## moine

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Paume de force | cc | — | ⭐ moine : mains nues ou bâton |
| 1 | Balayage de jambe | cc | — | ⭐ moine : mains nues ou bâton |
| 1 | Paume tranchante | cc | — | ⭐ moine : mains nues ou bâton |
| 2 | Coup du dragon | cc | — | ⭐ moine : mains nues ou bâton |
| 2 | Toucher des méridiens | cc | — | ⭐ moine : mains nues ou bâton |
| 3 | Garde du pèlerin | soi | une arme de mêlée | ⭐ « le bâton tenu en travers » |
| 3 | Poing du souffle | cc | — | ⭐ moine : mains nues ou bâton |
| 3 | Roue du vent | cc | — | ⭐ moine : mains nues ou bâton |
| 4 | Frappe du tigre | cc | — | ⭐ moine : mains nues ou bâton |
| 4 | Poing de pierre | cc | — | ⭐ moine : mains nues ou bâton |
| 5 | Coup du serpent | cc | — | ⭐ moine : mains nues ou bâton |
| 6 | Mille poings | cc | — | ⭐ moine : mains nues ou bâton |
| 6 | Poing de légende | cc | — | ⭐ moine : mains nues ou bâton |
| 7 | Pied du phénix | cc | — | ⭐ moine : mains nues ou bâton |
| 8 | Onde de choc | cc | — | ⭐ moine : mains nues ou bâton |
| 8 | Point de pression | cc | — | ⭐ moine : mains nues ou bâton |
| 9 | Danse des mille mains | cc | — | ⭐ moine : mains nues ou bâton |
| 9 | Poing du ciel | cc | — | ⭐ moine : mains nues ou bâton |
| 10 | Paume du néant | cc | — | ⭐ moine : mains nues ou bâton |

## paladin

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 1 | Coup béni | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Frappe du juste | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Frappe du champion | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Châtiment juste | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Jugement | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Frappe du croisé | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Héros | passive | un bouclier | ⭐ « maître du bouclier » |
| 7 | Lame de l'aube | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Croisade | soi | une arme de mêlée | ⭐ « il lève sa masse » |
| 9 | Vague sainte | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Épée de la foi | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Jugement dernier | cc | une arme de mêlée | frappe portée avec l'arme |

## repurgateur

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Sentence | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Lame d'argent | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Sel et cendre | cc | — | ⭐ poignée de sel |
| 2 | Coup de pieu | cc | une arme de mêlée | frappe portée avec l'arme |
| 2 | Eau lustrale | cd | — | ⭐ fiole |
| 2 | Sang contre sang | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Chaînes d'argent | cc | — | ⭐ chaînes |
| 3 | Marque du traqueur | cc | — | ⭐ marque |
| 4 | Croix renversée | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Fouet de flammes | cc | — | ⭐ lanière de feu |
| 5 | Marque d'argent | cc | — | ⭐ marque |
| 5 | Trait béni | cd | une arme de tir ou une arme de jet | ⭐ toute arme de tir ou de jet (trait) |
| 6 | Fer de l'Inquisiteur | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Fer et sel | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Haleine de l'abîme | cc | — | ⭐ souffle |
| 7 | Brise-sortilège | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Lame sanctifiée | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Pieu au cœur | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Tourbillon d'argent | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Pacte rompu | cc | — | ⭐ rupture de pacte |
| 10 | Tueur de démon | cc | une arme de mêlée | frappe portée avec l'arme |

## templier

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 1 | Coup réglementaire | cc | une arme de mêlée | frappe portée avec l'arme |
| 1 | Garde de l'ordre | soi | une arme de mêlée | ⭐ garde réglementaire |
| 1 | Ordre de halte | cc | — | ⭐ commandement |
| 2 | Bouclier repoussant | cc | un bouclier | ⭐ coup de bouclier |
| 2 | Frappe du gardien | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Arme de justice | soi | une arme de mêlée | ⭐ « sa lame » |
| 3 | Ligne de l'ordre | cc | une arme de mêlée | frappe portée avec l'arme |
| 4 | Lame enflammée | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Coup de l'inquisition | cc | une arme de mêlée | frappe portée avec l'arme |
| 5 | Fer rouge | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Bras divin | cc | une arme de mêlée | frappe portée avec l'arme |
| 6 | Taille du gardien des temples | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Lame de foudre | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Rotation du templier | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Défi de l'ordre | cc | — | ⭐ étendard planté |
| 8 | Jugement de l'ordre | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Épée de l'institution | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Sentence capitale | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Verdict | cc | une arme de mêlée | frappe portée avec l'arme |

## voleur

| niv. | compétence | mode | exige | motif |
|---|---|---|---|---|
| 0 | Poudre aveuglante | cc | une arme de mêlée (tranchante) | ⭐ « puis la dague » |
| 1 | Coup bas | cc | — | ⭐ coup de genou |
| 1 | Lame de poche | cc | une arme de mêlée (tranchante) | ⭐ canif |
| 1 | Sable aux yeux | cc | — | ⭐ poignée de sable |
| 2 | Coup de veine | cc | — | ⭐ coup de veine |
| 2 | Couteaux de lancer | cd | une arme de jet | ⭐ couteaux de lancer |
| 2 | Croc-en-jambe | cc | — | ⭐ croc-en-jambe |
| 2 | Surin | cc | une arme de mêlée (tranchante) | ⭐ surin |
| 3 | Coup de coupe-jarret | cc | une arme de mêlée | frappe portée avec l'arme |
| 3 | Coup du pavé | cc | — | ⭐ ce qui traîne dans la rue |
| 3 | Pickpocket de combat | cc | — | ⭐ vol |
| 3 | Poivre des quais | cc | — | ⭐ poivre |
| 4 | Bombe fumigène | cc | — | ⭐ bombe |
| 4 | Cordelette | cc | — | ⭐ cordelette |
| 4 | Faire les poches | cc | — | ⭐ vol |
| 4 | Lame cachée | cc | une arme de mêlée (tranchante) | ⭐ lame de manche |
| 5 | Coup du lapin | cc | — | ⭐ coup à la nuque |
| 5 | Fiel de crapaud | cc | une arme de mêlée (tranchante) | ⭐ lame trempée |
| 5 | Pluie de clous | cc | — | ⭐ clous jetés |
| 5 | Vol à l'arraché | cc | — | ⭐ vol |
| 6 | Cendre au visage | cc | — | ⭐ cendre |
| 6 | Coup de surin | cc | une arme de mêlée (tranchante) | ⭐ surin |
| 6 | Tourbillon de coutelas | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Coup de crosse | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Lame du coupe-jarret | cc | une arme de mêlée | frappe portée avec l'arme |
| 7 | Mauvaise fiole | cc | — | ⭐ fiole |
| 8 | Chausse-trappe lancée | cc | — | ⭐ pointes semées |
| 8 | Coup du maître voleur | cc | une arme de mêlée | frappe portée avec l'arme |
| 8 | Détrousser l'âme | cc | — | ⭐ vol |
| 8 | Feu grégeois de poche | cd | — | ⭐ fiole |
| 9 | Coup du prince des voleurs | cc | une arme de mêlée | frappe portée avec l'arme |
| 9 | Lame dans la manche | cc | une arme de mêlée (tranchante) | ⭐ lame de manche |
| 9 | Nuage de poivre | cc | — | ⭐ poivre |
| 10 | Coup du bandit de grands chemins | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Le grand coup | cc | une arme de mêlée | frappe portée avec l'arme |
| 10 | Tempête de couteaux | cc | une arme de mêlée (tranchante) | ⭐ couteaux ; reste une frappe de mêlée (même raison que l'éventail) |
| 10 | Voleur d'ombres | cc | — | ⭐ vol |

## De la flèche (ou du carreau) au trait

Ces tirs (forestier, Carreau béni) acceptent toute arme de tir ou de jet : leur texte parle désormais de **trait** (flèche, carreau, javelot). L'`_id` ne change pas (barre d'action et compétences connues intactes).

| avant | après | description (après) |
|---|---|---|
| Tir précis | Tir précis (inchangé) | Il retient son souffle, laisse passer un battement de cœur, puis lâche son trait. |
| Flèche rapide | Trait rapide | Vise, lâche : un seul souffle. |
| Tir aux jambes | Tir aux jambes (inchangé) | Un trait bas qui ralentit la course de la proie. |
| Flèche barbelée | Trait barbelé | (inchangée) |
| Tir à longue portée | Tir à longue portée (inchangé) | Un trait qui file plus loin que l'œil ne suit — pour qui a la main assez sûre. |
| Volée | Volée (inchangé) | Une pluie de traits sur une petite clairière. |
| Flèche de franc-archer | Tir dans la mêlée | (inchangée) |
| Flèche perforante | Trait perforant | (inchangée) |
| Flèche de chasse | Trait de chasse | Un trait à large fer, qui handicape plus qu'il ne tue. |
| Tir à l'œil | Tir à l'œil (inchangé) | Un trait qui cherche le seul point que l'armure ne couvre pas. |
| Carreau béni | Trait béni | Un trait trempé dans l'eau bénite. |
| Flèche longue | Trait lointain | (inchangée) |
| Flèche venimeuse | Trait venimeux | (inchangée) |
| Pluie de flèches | Pluie de traits | (inchangée) |
| Clouer au sol | Clouer au sol (inchangé) | Le trait traverse le pied et s'enfonce dans la terre. |
| Flèche épuisante | Trait épuisant | (inchangée) |
| Tir mortel | Tir mortel (inchangé) | Un trait qu'on n'entend qu'une fois. |
| Volée en éventail | Volée en éventail (inchangé) | Trois traits à la fois, ouverts en éventail. |
| Flèche aveuglante | Trait aveuglant | (inchangée) |
| Grêle de flèches | Grêle de traits | (inchangée) |
| Tir transperçant | Tir transperçant (inchangé) | Le projectile traverse le premier et cherche le second. |
| Flèche du roi des bois | Trait du roi des bois | Le trait que l'on garde pour le monstre de la forêt. |
| Maîtrise de l'arc | Maîtrise du trait | Arc, fronde ou javelot : l'arme qui porte loin est devenue une partie de son corps. |
| Tir de suppression | Tir de suppression (inchangé) | Un barrage de traits qui force l'ennemi à se terrer. |
| Ciel de flèches | Ciel de traits | (inchangée) |
| Flèche de légende | Trait de légende | Le trait dont parlent les chansons de chasse. |
| Trait du chasseur de monstres | Trait du chasseur de monstres (inchangé) | Un projectile taillé pour ce qui n'a pas de nom, lancé par quelqu'un que cela n'effraie plus. |

## Variantes sur mesure réalignées sur leur base

Une variante recopie les tags de sa base à sa création : ceux posés ensuite sur la base (typologie `legere` du 10/11, `armure_cuir` / `armure_tissu`) lui manquaient. Ajout seulement.

| variante | base | tags ajoutés |
|---|---|---|
| Armure de cuir gravée de runes encensé Hanté en adamantite | Armure de cuir gravée de runes | armure_cuir |
| Armure de cuir gravée de runes Bestial en adamantite vivante | Armure de cuir gravée de runes | armure_cuir |
| Armure de cuir souple noire Bestial | Armure de cuir souple noire | armure_cuir |
| Armure de cuir souple noire en cuir de chêne Hanté damasquiné | Armure de cuir souple noire | armure_cuir |
| Armure de cuir souple noire Bestial en mithril en orichalque | Armure de cuir souple noire | armure_cuir |
| Armure de cuir souple noire en cuir de chêne doublé de chamois vivante | Armure de cuir souple noire | armure_cuir |
| Armure de cuir souple noire Bestial des Marais | Armure de cuir souple noire | armure_cuir |
| Bandoulière à fioles d’Améthyste en adamantite Relique | Bandoulière à fioles | armure_tissu |
| Bottes de cuir épais Bestial Hanté en adamantite | Bottes de cuir épais | armure_cuir |
| Calotte de cuir runé d’Améthyste en adamantite Relique | Calotte de cuir runé | armure_cuir |
| Casque cornu Bestial en adamantite vivante | Casque cornu | armure_cuir |
| Chaussons silencieux doublé de chamois du Courage | Chaussons silencieux | armure_tissu |
| Dague Bestial en adamantite des Profondeurs | Dague | legere |
| Dague Bestial des Profondeurs en mithril | Dague | legere |
| Dague Bestial des Eaux Sombres en mithril | Dague | legere |
| Dague de scène empreint d'alchimie | Dague de scène | legere |
| Dague de scène du Reflet | Dague de scène | legere |
| Dague de scène à la Mandragore | Dague de scène | legere |
| Dague de scène Bestial | Dague de scène | legere |
| Dague de scène serti d'une gemme | Dague de scène | legere |
| Dague de scène Ténébreux | Dague de scène | legere |
| Dague de scène des Profondeurs | Dague de scène | legere |
| Dague de scène Démoniaque | Dague de scène | legere |
| Dague de scène des Eaux Sombres | Dague de scène | legere |
| Dague de scène d’Améthyste | Dague de scène | legere |
| Dague de scène des Marais | Dague de scène | legere |
| Dague de scène de rituel | Dague de scène | legere |
| Dague de scène salpêtré | Dague de scène | legere |
| Dague de scène Empoisonné | Dague de scène | legere |
| Dague de scène en mithril | Dague de scène | legere |
| Dague de scène à incrustations précieuses | Dague de scène | legere |
| Dague de scène vivante | Dague de scène | legere |
| Gants d'archer doublé de chamois du Reflet Relique | Gants d'archer | armure_cuir |
| Gants de courroyeur Envoûté Bestial en mithril | Gants de courroyeur | armure_cuir |
| Jambières de cuir renforcé Hanté | Jambières de cuir renforcé | armure_cuir |
| Jupe de lanières de cuir en cuir de chêne doublé de chamois du Courage | Jupe de lanières de cuir | armure_cuir |
| Manteau de loup Hanté serti d'une gemme Relique | Manteau de loup | armure_cuir |
| Pelta du Courage vivante en mithril | Pelta | armure_cuir |
| Souliers de cuir Envoûté | Souliers de cuir | armure_cuir |
| Souliers de cuir Hanté | Souliers de cuir | armure_cuir |
| Souliers de cuir en fer | Souliers de cuir | armure_cuir |
| Souliers de cuir Bestial | Souliers de cuir | armure_cuir |
| Souliers de cuir doublé de chamois | Souliers de cuir | armure_cuir |
| Souliers de cuir de croupon | Souliers de cuir | armure_cuir |
| Souliers de cuir plombé | Souliers de cuir | armure_cuir |
| Souliers de cuir de rituel | Souliers de cuir | armure_cuir |
| Souliers de cuir de l’Imitation | Souliers de cuir | armure_cuir |
| Souliers de cuir à garniture de cuir | Souliers de cuir | armure_cuir |
| Souliers de cuir aux runes noires | Souliers de cuir | armure_cuir |
| Souliers de cuir en cuir bouilli | Souliers de cuir | armure_cuir |
| Souliers de cuir serti d'une gemme | Souliers de cuir | armure_cuir |
| Souliers de cuir Relique | Souliers de cuir | armure_cuir |
| Souliers de cuir encensé | Souliers de cuir | armure_cuir |
| Souliers de cuir en cuir de chêne | Souliers de cuir | armure_cuir |
| Vêtements de peau à motifs totémiques du Reflet serti d'une gemme à incrustations précieuses | Vêtements de peau à motifs totémiques | armure_cuir |
| Vêtements de peau à motifs totémiques d’Améthyste en orichalque Relique | Vêtements de peau à motifs totémiques | armure_cuir |
