---
name: telluris-lore
description: The world of Telluris — canon vs proposals (author decisions in docs/lore/ beat ChatGPT drafts; the live dump beats both), the author's standing writing rules (no wars, no Earth dates/electricity, adapt real myths rather than invent, mysteries never resolved), cosmology (three Aboriginal brothers, portals, the Mana Wave, dungeons, mana crystals), the institutions (Paladins, Templiers, Architectes, Guilde and its Cuivre→Adamantite ranks), the five Lignées, each city-state's portals and identity (Lutecia, Auxerre, Rome, Reykjavik, Alexandrie/Abou Simbel, Venise, Gênes, Bruges, Aix, Cordoue, Constantinople…), the authored NPC arcs (Auxerre mission, Aélis, Milo, Élise) and the rank D→S+ main plot (Échidna, Paradis, Yggdrasil, Révélateurs, Grigori). Load before writing ANY in-world text — dialogue, quest, PNJ, shop/merchant name, item or recipe description, ambience line, image prompt, city history — or answering a question about the setting, even if the request only says « écris un dialogue », « nomme ce marchand », « décris cette ville », « c'est cohérent avec le lore ? », « qui est Aélis ? ».
---

Lore de Telluris. Matière brute : **`docs/lore/`** (50 séances de travail avec ChatGPT, une par fichier, index `docs/lore/README.md`). Synthèse : `docs/Telluris_Document_Maitre.md` (26 sections, corrigée le 08/10/2026 contre les messages de l'Auteur). Elle ne couvre ni les cités, ni les PNJ, ni les quêtes : ne pas la croire exhaustive. Mécanique des dialogues/quêtes en jeu : **telluris-quetes-pnj** ; prompts d'images : `docs/prompts_images.md`.

**Lore rédigé** : `docs/lore/redige/NN_*.md`, prose tirée des niveaux 1-3 d'autorité, premier groupe de `/admin/lore` (badge RÉDIGÉ) — une SYNTHÈSE : elle ne fait jamais foi contre un message de l'Auteur ; une décision nouvelle s'y reporte. Toute page de lecture a un bouton **▶ Lire** (`speechSynthesis`, option « Auteur seulement » sur une séance ; `dev/test_lecture_lore_client.js`).

Lecture rendue dans le navigateur : **`/admin/lore`** (carte 📚 Lore de « Concepts de Telluris », `utils/lore.py`) — tout `.md` déposé sous `docs/lore/` y apparaît sans autre déclaration ; libellé de dossier dans `lore.SECTIONS`, résumé relu du README.

**Chronologie** (`/admin/lore/chronologie`, carte 🕰 en tête de `/admin/lore`, au-dessus des cards 📜 Synthèse / Détails venues de `/admin` — `part-lore-synthese.html`) : frise SVG filtrable (filtrer REPLIE les ères sans élément retenu, sauf « estomper ») lue dans **`docs/lore/chronologie.json`**, la source FORMALISÉE de tout ce qui est daté — ères (antédiluvien · Âge des Remparts · Âge des Portails · Âge des Donjons · temps du joueur par rang · futur), bornes `ans` / `entre` / `rang` / `entre_rangs` / `inconnu` / `ouvert` / `dans`, autorité de l'élément ET de sa date, **origine** (région du monde : catégorie OBLIGATOIRE, liste, vocabulaire `origines` — les Lignées n'en sont pas, elles n'ont ni territoire ni histoire propres), tags par facette (détail : un peuple — Romains, Islandais — reste un tag), sources CITÉES (`tests/test_chronologie.py` vérifie que chaque citation figure dans son fichier), `contradictions` à arbitrer. ⚠️ Une décision qui date ou déplace un événement se reporte AUSSI dans ce JSON (relancer `pytest tests/test_chronologie.py`).


### Qui fait foi
Les séances sont des **échanges de travail, pas un canon**. Ordre d'autorité, du plus fort au plus faible :

1. **Le dump** (`jsons/telluris-dump-*.json`, le plus récent) — ce qui est EN JEU. Il a déjà corrigé des propositions : Dame Éléonore de Rochefort y est **elfe** (ChatGPT : humaine), Frère Martin de Clairvaux **hobbit** (humain), Étienne Morel **nain**, Matthieu Perrin **ogre**. Le dump gagne toujours.
2. **Les messages `## ✍️ Auteur`** des séances — décisions explicites. Le plus récent l'emporte sur le plus ancien.
3. **Une réponse ChatGPT que l'Auteur a adoptée** — adoption explicite (« On va garder ta dernière version », « A retenir », « Je retiens ») ou réutilisée telle quelle dans un message suivant de l'Auteur (Bastion de l'Yonne, Chambre → … → Domaine).
4. **Tout le reste des réponses ChatGPT** = **proposition**. Utilisable comme inspiration, jamais citée comme un fait établi.

Pour ne lire que la parole de l'Auteur : extraire les blocs entre `## ✍️ Auteur` et le `## 🤖 ChatGPT` suivant (≈ 2 300 lignes sur 25 000).

⚠️ Quand une réponse dépend d'une proposition non adoptée, le **dire** (« proposé, non tranché »). Contradiction non arbitrable → la **signaler**, ne pas choisir en silence (§ Contradictions ouvertes). Toujours distinguer **vérité du monde** / **ce que croient les personnages** / **ce que découvre le joueur**.


### Règles d'écriture de l'Auteur
Répétées en tête de presque chaque séance : elles valent pour **tout** texte du monde.

- **Aucune guerre sur Telluris.** « Déplacer une armée sur des territoires hostiles revient à perdre toute guerre à l'avance. » Les rivalités sont commerciales, politiques, d'influence (Gênes et Venise « sans jamais en venir aux mains officiellement »). L'adversaire est la faune, la flore, la magie, l'inconnu.
- **Ne pas comparer** l'histoire de la Terre à celle de Telluris. Raconter Telluris, où **depuis les origines** les flux magiques baignent le monde et les monstres rôdent.
- **Adapter plutôt qu'inventer** : s'appuyer sur les personnages historiques et mythiques réels (Charlemagne, Néfertiti, Salomon, Marco Polo, Averroès…). Les mythes terrestres **ont eu lieu** sur Telluris, mais sont parvenus **déformés** par les siècles. Pour l'Auteur, Telluris est une excuse pour faire découvrir les mythes réels — inventer à leur place va contre le projet. **Toute inversion ou divergence avec l'ordre réel de notre histoire est admise** (Auteur, 11/10) : Néfertiti avant les pyramides, Romulus avant les trois frères, monuments très tardifs à Lutecia.
- **Jumièges appartient au jeu**, pas à l'histoire (Auteur, 11/10) : la quête du rang C, jamais un exemple dans un texte d'histoire du monde.
- **Ni dates terrestres, ni électricité, ni référence au christianisme** dans l'histoire d'une cité. Les édifices gardent leur nom réel (basilique, cathédrale, pape) mais leur **fonction** est tellurienne : un portail, une garnison. Le pape est grand maître des Templiers, **sans lien** avec le christianisme.
- **Mers dangereuses** : serpents géants, dragons de mer, pieuvres et poulpes géants ; **plusieurs** Charybde et Scylla peuplent les côtes méditerranéennes.
- **Mystère jamais résolu** : « toujours des réponses non définitives ». Des personnages portent des **théories contradictoires** ; le joueur construit sa propre compréhension (Aélis est l'une d'eux).
- **La Lignée est secondaire** : distinction par richesse, rang, fonction, réputation ; jamais de racisme institutionnel. Foule mêlée par défaut.
- **Émotion sobre** : les morts marquantes sont **banales** (Élise part chercher des herbes) ; les liens se construisent par l'habitude et la confiance. Pas d'ambiguïté romantique imposée — l'aventurier peut être une femme (correction de l'Auteur sur Aélis).
- **Textes tirés au hasard** (ambiances de nuit, rumeurs…) : chacun **autonome**, aucun ne dépend d'un autre.
- **Pas d'artisanat par le personnage joueur** : ce sont des PNJ marchands qui fabriquent.
- Prompts d'image peuplés : garder **telle quelle** la phrase « Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. » et « Pas de texte visible » ; la foule est **répartie à parts égales** entre les cinq Lignées, même autour d'un tenancier humain (Auteur, 10/10/2026).
- Graphie : **Lutecia** (forme savante, celle de l'Auteur), **Lutèce** admis dans les noms (« Dame Ysabeau de Lutèce ») ; **Rhemi** = Reims (`lieu:rhemi`).


### Le monde en dix lignes (canon)
- Monde médiéval-fantastique **sur la géographie réelle** de la Terre ; les grandes cités historiques sont des **Cités-États fortifiées**. Plus on s'éloigne des remparts, plus le danger croît ; les zones blanches de la carte sont le domaine des légendes.
- Six piliers (Auteur, 12/08) : géographie réelle · combat tactique au tour par tour sur grille carrée · Cités-États · **magie à coût réel** (une boule de feu consomme du soufre : la puissance est un choix économique) · vocations diverses avec transitions · relations vivantes.
- **Cinq Lignées d'Anthropes** : humains, elfes, nains, ogres, hobbits — un même sang façonné par la magie brute, **interfécondes**. Traits : humains polyvalents ; elfes longévifs et savants mais fragiles ; nains endurants, volonté de fer, résistants à la magie ; ogres colossaux, apparences les plus diverses ; hobbits agiles, chanceux, discrets, résistants à la magie.
- **Les monstres précèdent les portails** : ils rendaient déjà les routes mortelles quand les trois frères ont inventé les portails. Tous ne viennent pas des donjons.
- **Les trois frères aborigènes** (australiens, jumeaux) inventent les **portails transversaux** — destination déplacée en faisant tourner une **bolas**. Premiers portails stables, reliant **seulement** des lieux de Telluris. Ils ont **apporté au monde** la connaissance des portails, mais il en existait avant eux : **Saint-Pierre** (Rome, **naturel**) est la seule exception **connue des Occidentaux** ; l'Hekla, la brèche de Cordoue, les portails de Mu ne sont **pas datés** (nul ne sait s'ils sont plus vieux ou plus jeunes). Les premiers portails des frères et de leurs héritiers ne mènent à aucun autre monde ; les naturels étaient alors inconnus ou pas encore apparus. Des portails se **manifestent spontanément**, encore aujourd'hui. **Plusieurs portes peuvent mener au même autre monde** (Auteur, 11/10). Monuments et temples sont le plus souvent **bâtis autour d'un portail** (Notre-Dame, Sainte-Sophie — portail millénaire, édifice de Justinien).
- **Transmission dégradée** : science → artisanat → tradition → savoir partiellement perdu. Créer un portail devient un art rare ; l'entretenir coûte cher.
- **Quatre ères** (Auteur, 11/10, septième arbitrage — remplacent les trois) : **antédiluvien** (jusqu'au **Déluge**) · **Âge des Remparts** (ouvert par **Gilgamesh**, bâtisseur des remparts d'Uruk) · **Âge des Portails** (ouvert par les trois frères = « avant la Vague ») · **Âge des Donjons** (ouvert par la Vague = « après la Vague »). Le Déluge est de nature inconnue (Utnapishtim y survit ; théorie : une première vague de mana ; le Déluge **n'a pas** englouti Mu). Jamais de période terrestre (« Antiquité », « Moyen Âge »). Vague il y a **sept à huit siècles** (Auteur, 11/10), Charlemagne un siècle après. Frise fusionnée : `docs/lore/monde/20261011_frise_chronologique_fusionnee.md` (§ 11).
- **La Vague de mana**, il y a quelques siècles, d'origine inconnue : les portails mal faits ou mal entretenus **changent de couleur**. Les premiers voyageurs y entrent : **premiers donjons** — un champ de céréales, une forêt… ou un autre monde.
- **Cristaux de mana** (couleurs variées) : rares sur Telluris, trouvés dans des mines derrière certains donjons et **dans les carcasses** de monstres. Les portails **originaux** des frères s'en passent presque toujours (magie peut-être plus intense, maîtrise plus innée) ; ceux de leurs **héritiers** en demandent, dès avant la Vague (Auteur, 11/10) ; aujourd'hui les cristaux sont un **apport de mana ou de maîtrise** qui permet aux Architectes de tenir les portails — le **violet** = puissance pure de mana, le **jaune** = stabilisation des effets des portails (Auteur, 11/10). Un donjon est une **épée de Damoclès** (il peut **déborder** s'il n'est pas entretenu) **et** une richesse pour sa cité.
- **La magie des portails échappe aux magiciens** : aucun sort ne déplace entre deux lieux ; la « téléportation » d'un sort se limite à un **saut d'une case** en combat.
- Le monothéisme arrive tard, **minoritaire**, sans conversion par la force (« trop de combats à mener dans Telluris pour en rajouter un ») ; « auberge-relais » est le terme d'**avant** les monothéismes, qui ont depuis transformé une bonne partie d'entre elles en **monastères-relais** (Auteur, 11/10 ; aucun monastère avant eux) et donne des paladins chrétiens « ou autres groupes protecteurs alliés à une religion monothéiste ».


### Institutions
- **Paladins** — protègent les **routes** entre cités, depuis que les Anthropes se sont réfugiés derrière des remparts : l'ordre est **antérieur aux portails** (décision du 21/08, qui corrige celle du 19/08). Guerriers pratiquant la **magie Sainte** (soin). Écument les routes entre **auberges-relais fortifiées** ; certains monastères sont devenus leurs casernes. Seul sort de très haut niveau connu : **Lance de lumière** (trait à la vitesse de la lumière, en ligne droite, perce tout — l'arme contre les monstres volants), perfectionnée à **Montmartre**. Variantes locales : paladins maritimes de l'Arsenal (Venise), Hôpital Saint-Jean (Bruges).
- **Templiers** — gardent les **temples** = forteresses bâties autour d'un **portail de donjon** : garde extérieure, garde intérieure, muraille cerclant le portail, **chaires** qui le surplombent pour les magiciens en cas de déversement. Réglementent l'accès. Ordre **antérieur au christianisme** : à l'origine (Âge des Remparts), ils gardent les **remparts et les lieux derrière** — le Paladin dehors, le Templier dedans ; un **groupe spécialisé** veille sur la grotte du portail sans origine de la future Saint-Pierre avant même Rome, et voit venir Jésus. Après la Vague, recentrage sur les temples : ils **protègent** les donjons et **gèrent** les portails de déplacement encore actifs (Auteur, 11/10). Proposition Romulus/Rémus/la Louve : `docs/lore/monde/20261011_frise_chronologique_fusionnee.md` § 10.
- **Architectes / maîtres des portails** — créent, réparent, étudient les portails ; Lutecia les forme (« institut des architectes de Lutecia »). Aélis de Montfaucon en est une jeune représentante.
- **Guilde des Aventuriers** — « le seul chemin légal vers la fortune pour les non-nobles » ; c'est là que le brassage des Lignées est le plus fort. Rangs (Auteur, 12/08) :

| Métal | Rang | Niveaux |
|---|---|---|
| Cuivre | F | 3 – 10 |
| Fer | E | 10 – 20 |
| Argent | D | 21 – 30 |
| Or | C | 31 – 40 |
| Platine | B | 41 – 50 |
| Mythril | A | 51 – 60 |
| Orichalque | S | 61 – 80 |
| Adamantite | S+ | 81 + |

Les quêtes SSS+ engagent la survie d'une cité-État. **A+** (trame des quêtes) = palier de **fin du rang A**, sans nouveau métal (Auteur, 11/10).

- Formule de l'univers (synthèse adoptée) : *les Cités-États construisent les murs, les Paladins protègent les chemins, les Templiers gardent les portes, les Architectes entretiennent les passages, les Aventuriers franchissent les frontières.*
- Vocations citées par l'Auteur : guerrier, magicien, ménestrel (magie de support), paladin, répurgateur (≈ inquisiteur), lettré, forestier (distance + pistage), nécromancien, chaman — **transitions entre classes** possibles. Liste réelle en jeu : le dump (`rules:*`), pas le lore.


### Le fil rouge du personnage
Fuit son village (pillage, famine, monstres…) → refuge derrière les remparts d'une ville moyenne (**Auxerre**) → Guilde, faire reconnaître sa vocation → la **Capitale** (**Lutecia**) → l'effort mondial contre les monstres. Arc : *survie → compétence → réputation → richesse → exploration → renommée → influence.*

**Trois fins** (Auteur) : devenir **maître d'une guilde** · **découvrir le pot aux roses** sur l'origine des monstres · devenir **une armée à soi tout seul**.

Échelle (Auteur, 24/09) : France d'abord (escortes depuis Montmartre), le **monde après le rang A** — Notre-Dame lui ouvre alors ses portes, voyages par Notre-Dame : **gemme violette** (puissance) vers le reste du monde, **cristal jaune** (stabilisation) vers **Mu** — cristaux jaunes trouvés au fond des catacombes (Auteur, 11/10). Trame des quêtes par rang, Échidna, mondes divins : [references/personnages_quetes.md](references/personnages_quetes.md).

Le joueur ne doit pas apprendre tôt la vérité méta : **Jésus était un joueur** ayant fini le jeu en **Révélateur**, et qui a dû **vulgariser** une vérité inconcevable pour un Anthrope (Platon). Au bout de la route : dieux et aventuriers sont les marionnettes des **joueurs** et des êtres qui ont fait de Telluris leur terrain de jeu. Détail et propositions (Grigori, Hārūt et Mārūt, Hekla) : [references/cosmologie.md](references/cosmologie.md).


### Cités-États
Une ligne par cité ; portails, monuments et décisions de l'Auteur : [references/cites.md](references/cites.md).

- **Lutecia** — capitale du **portail ancien de Notre-Dame** (œuvre d'un des frères), intact grâce au **mana faible**, relie tout lieu du monde connu. Montmartre et le Sacré-Cœur sont tenus par les paladins (défense aérienne). Pas de grandes écoles de magie. Sous-sol : carrières et catacombes.
- **Auxerre** — ville de départ ; **sans** portail transversal ; temple-donjon = mine de cristaux réinitialisée périodiquement ; convois de cristaux vers Lutecia sous escorte paladine.
- **Rome** — la pieuse (Saint-Pierre, portail **naturel** vers le Paradis, gardé par le pape-Templier) et la pécheresse (orgies, Colisée).
- **Reykjavik** — guidée en secret par un **dragon empereur** antérieur aux Anthropes ; Hallgrímskirkja. **Akureyri** — cité fortifiée sœur ; gouffre de l'**Hekla** vers l'Enfer de Lucifer.
- **Égypte** coupée en deux : **Alexandrie** (savoir, magie) au nord, royaume mort-vivant de **Néfertiti** (lamia) à **Abou Simbel** au sud, maître du barrage d'Assouan.
- **Mu** — civilisation **en avance sur son temps** (murailles et gardiens des routes avant Gilgamesh, mais son histoire méconnue n'est citée par aucune autre cité), antérieure aux Cités-États et aux trois frères ; **apprend les portails d'un des frères**, **sombre au moment de la Vague** (pas au Déluge) ; sa cité, **Mu-la-Centrale**, survit sous la mer sous un dôme doré (image `towns/mu_capital.jpg`). **Vérité du monde**, inconnue de presque tous et simple hypothèse même à Mu : elle a **sacrifié un continent pour fermer un portail naturel vorace** qui menaçait le monde. Ses **dirigeants d'alors ont caché** les vraies raisons à leur peuple (tectonique, volcans) ; Mu les a oubliées, et nul au dehors ne connaît son sort (Auteur, 12/10). Maîtres de Mu : plus savants que tous, bien moins que leurs prédécesseurs. **Échidna** (« mère des serpents », jamais Lilith à Mu ; mère des monstres grecs ; prise sous Mu quand la **porte des Enfers d'Hadès** — le portail vorace, autre monde que l'Enfer de Lucifer (Hekla) — fut scellée, alors qu'elle soignait **Cerbère**, resté de l'autre côté ; les **Naga**, fils de **Kadru** venus par les océans, voient en elle une mère) vit sous la cité (rang A) ; **Sept Sages** = les **apkallu** mésopotamiens. Moins on en parle, plus les guildes s'y intéressent ; le **prix du voyage** depuis Lutecia est connu à partir du rang A. Histoire, noms (Sept Sages, Tables de Pierre, Couronne, Retours, Ra-Mu) et arbitrage : `docs/lore/cites/20261011_histoire_de_mu_chatgpt.md`. Gardienne d'un savoir que Lutecia ne maîtrise pas : ses Architectes y **parachèvent** leur formation, par le **portail programmable de Notre-Dame** (un seul seuil, cristal jaune). Enseignements avancés réservés aux dignes ; certains reviennent transformés, d'autres jamais. Antérieure aux frères ; aujourd'hui **continent englouti** connu à Lutecia des seuls **grands Architectes** et **Templiers de Notre-Dame**, ailleurs **image révérée** (culte) de tous les Architectes ; ses anciens élèves, à de très hauts postes, en parlent peu — pas un interdit : « ça ne s'explique pas » (comme les Révélateurs, la caverne de Platon) ; « on n'en sort pas », ils ne savent pas où elle est (Auteur, 11/10).
- **Rhemi** (Reims) — pas une capitale ; la cité **du Sacre** : les Rèmes s'allient plutôt que de résister ; **aucun portail**, la craie boit le mana (Porte de Mars = portail mort-né) ; l'**Ampoule** de Remi, premier Sacre ; épargnée par la Vague. Crayères, « vin du diable », Ange au Sourire.
- **Chartres** — pas une capitale ; **labyrinthe, école, grenier** : lieu consacré des Carnutes où les sages arbitrent ; labyrinthe de Dédale ; **le puits = portail horizontal vers un Minotaure** (donjon gardé par les Templiers) ; **pas de Thésée** (Auteur, 11/10) ; école des « nains sur des épaules de géants » ; Beauce, grenier de Lutecia.
- **Atlantis** — au-delà de Gibraltar, l'une des **premières cités des Lignées** à l'Ouest ; anneaux **tracés par Poséidon** (« la mer est le seul chemin »), **remparts d'orichalque** (première puissance et monnaie d'échange ; insignes du rang S), **temple de Poséidon** au centre. **Seule** à avoir **refusé un des frères** ; un **dirigeant au nom rayé** tenta d'ouvrir la ville, une épidémie suivit, il fut **sacrifié à Poséidon** → règles d'isolement (aucun étranger au-delà du port extérieur, aucun portail, sortie sous l'aval du temple). Aucun donjon de portail. **Cétô** domptée par **Évenor** (prêtre-chaman) protège sa progéniture et la cité ; **guilde du port extérieur** (remparts extérieurs, **par la mer, dès le rang A**). Récits mêlés avec Mu, dont Lutecia et les ports **rient**. Gouvernement ouvert. `docs/lore/cites/20261012_histoire_d_atlantis.md`, image `towns/atlantis_capital.jpg`.
- **Venise**, **Gênes**, **Bruges**, **Aix-la-Chapelle**, **Cordoue**, **Constantinople**, **Babylone**, **Jérusalem** : voir la référence.


### Contradictions ouvertes
À signaler si un texte en dépend, jamais à trancher seul :

- ~~Auberge d'Élise~~ : tranché — le dump la place au **Coq de Lutèce**, dans les **faubourgs** de Lutecia (et pas sur la route d'Auxerre).
- **Origine des Paladins** : nés après la Vague (19/08) vs **antérieurs aux portails** (21/08) — retenir le 21/08.
- ~~Rang A+~~ : tranché — palier de fin du rang A (Auteur, 11/10).
- ~~Atlantis~~ : tranché — antédiluvienne, **existe encore** ; l'isolement « choisi » vient du **refus d'un des frères** puis du **dirigeant sacrifié** (Auteur, 11 et 12/10).
- Points ouverts listés par l'Auteur ou le document maître : nature de la Vague, origine ultime des monstres, limites des Révélateurs, sens de « finir le jeu », règles de stabilisation des portails, taxonomie des écoles de magie, organisation politique de chaque cité, statut juridique des Lignées.


### Méthode pour un texte neuf
1. Chercher la cité, le PNJ ou le thème dans les références, puis dans `docs/lore/` (grep sur le nom) et dans le **dump** (`pnj:*`, `lieu:*` : nom, race, vocation réels).
2. Ne reprendre comme fait que les niveaux 1 à 3 de l'ordre d'autorité ; un nom proposé mais absent du dump se présente comme proposition.
3. Appliquer les règles d'écriture.
4. Ancrer dans du mythe ou de l'histoire réels plutôt que d'inventer.
5. Laisser le mystère ouvert.
