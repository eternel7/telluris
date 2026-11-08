# Le sac de Manannán et le sac de Rhiannon — contenants des légendes

- **Source :** séance Claude Code du 02/11/2026. L'Auteur cherche des objets de légende qui **contiennent plus que leur taille**, où l'on dépose des choses pour les reprendre plus tard (la corne d'abondance, elle, produit sans fin).
- **Créée :** 02/11/2026
- **Statut :** intention de l'Auteur, puis **arbitrage** par huit questionnaires (deux messages ✍️) (§ ✍️ dernier message) qui **fait foi** ; le reste des réponses Claude Code et ChatGPT = propositions. Rien n'est implémenté en jeu.
- **Au dump (02/11)** : aucun des deux sacs, ni Manannán, ni Rhiannon, ni Pwyll. Contenants existants, tous ordinaires : `item:Besace_de_cuir_fume` (ceinture, `bonus_initiative`), `item:Petite_bourse_vide` (outil), `item:Selle_a_sacoches` (harnachement, `monture.charge_pct` 25 — seul objet qui touche à la charge). La charge physique se lit dans `charge_max_of` (règle anti-exploit : caractéristiques **brutes**).

---

## ✍️ Auteur (02/11/2026)

Est-ce qu'il existe des légendes sur des objets à la contenance importante ? Je vois la corne d'abondance, et ça pourrait être un objet de Telluris, mais la corne d'abondance, c'est plutôt pour générer de la bouffe de manière infinie. C'est pas vraiment quelque chose dans lequel on peut mettre des choses pour après les retirer. Est-ce qu'il y a d'autres légendes, d'autres objets qui pourraient avoir un peu plus ce genre d'utilité ?

> Dictée vocale : « labels » = légendes.

## ✍️ Auteur (02/11/2026)

Prends le sac de Manannán et le sac de Rhiannon, prépare la séance de lore.

De plus, j'aimerais des précisions sur les 13 trésors de l'île de Bretagne. En Afrique, il n'y a aucun objet magique qui permettrait de stocker des choses de manière plus importante que la taille de l'objet ?

## 🤖 Claude Code — les mythes

### Le sac de peau de grue de Manannán (*corrbolg*)
- **Source** : un poème du *Duanaire Finn* (recueil de ballades du cycle de Fionn), où Caoilte raconte à Fionn l'histoire du sac.
- **Origine du sac** : **Aoife**, fille de Dealbhaoth, aimée d'Ilbhreac, est changée en **grue** par une rivale jalouse, **Iuchra**. Elle vit **deux cents ans** dans la maison de **Manannán mac Lir**. À sa mort, le dieu fait de sa peau un sac.
- **Contenu** (le poème en dresse la liste) : la chemise et le couteau de Manannán, la ceinture de **Goibniu** le forgeron, le crochet du forgeron, les **cisailles du roi d'Écosse**, le **casque du roi de Lochlann**, une ceinture en **peau de baleine**, les **os des porcs d'Asal**.
- **La règle des marées** : « quand la mer était pleine, ses trésors se voyaient en son milieu ; quand la mer furieuse se retirait, le sac à son tour était vide ». Le contenu existe toujours, mais on ne le voit, et on ne le prend, qu'à **marée haute**.
- **Transmission** : de Manannán à **Lug**, puis aux fils de Cermait, à **Cumhall**, enfin à **Fionn mac Cumhaill**. Un objet qui **passe de main en main**, jamais perdu.
- **Manannán mac Lir** : dieu de la mer des Irlandais, seigneur d'**Emain Ablach** (l'île des pommiers) et des îles de l'Autre Monde ; il passe pour mener les morts et les égarés **au-delà des vagues**. Il possède la barque **Scuabtuinne** (« balaie-vagues », qui va sans voile ni rame), le cheval **Enbarr** (qui court sur la mer) et un **manteau de brume** qui rend invisible. L'**île de Man** porte son nom ; il la cache sous la brume.

### Le sac de Rhiannon (sac de Pwyll)
- **Source** : la **première branche du Mabinogi**, *Pwyll, prince de Dyfed*.
- **Avant** : **Pwyll** échange d'apparence et de royaume pour **un an** avec **Arawn, roi d'Annwn**, et tue pour lui son rival Hafgan. On l'appelle depuis **Pen Annwn**, « tête d'Annwn ».
- **Rhiannon** apparaît sur la butte d'**Arberth** (Gorsedd Arberth), à cheval ; nul ne la rattrape, même au galop, alors que sa monture semble aller au pas. Promise contre son gré à **Gwawl fils de Clud**, elle choisit Pwyll.
- **Le piège** : au festin des noces, Pwyll promet imprudemment d'accorder une faveur à un inconnu : c'est Gwawl, qui demande Rhiannon. Elle donne alors à Pwyll **un petit sac** (*cod fechan*). Un an plus tard, Pwyll revient en mendiant et demande seulement qu'on remplisse son sac de nourriture. **Le sac ne se remplit jamais**, quoi qu'on y verse. Rhiannon explique qu'il ne sera plein que lorsqu'un homme de haut rang **tassera la nourriture de ses pieds** en disant « assez ». Gwawl entre dans le sac ; Pwyll le referme sur sa tête et le noue.
- **Le « blaireau dans le sac »** (*broch yng nghod*) : chaque homme de Pwyll qui entre frappe le sac en demandant « qu'y a-t-il là ? » — « un blaireau ». Gwawl n'est relâché que contre le serment de **ne jamais se venger**. Le récit donne ainsi l'origine d'un jeu.
- **Rhiannon** est souvent rapprochée d'une déesse cavalière (Epona) ; ses **oiseaux** chantent un chant qui réveille les morts et endort les vivants.

## 🤖 Claude Code — ancrages possibles (propositions, non tranchées)

### Deux sacs, deux règles
| | Sac de Manannán | Sac de Rhiannon |
|---|---|---|
| Ce qu'il fait | **Garde** des objets, sans limite connue | **Ne se remplit jamais** |
| Contrainte | On ne voit et ne reprend le contenu qu'à **marée haute** | Celui qui **tasse le contenu de ses pieds** en disant « assez » y est piégé |
| Usage naturel | Coffre portatif d'aventurier | Grand chargement ponctuel (vivres, butin) ; piège ou prison |
| Ancrage | Irlande, mer, îles de l'Autre Monde | Pays de Galles, **Annwn** (déjà au lore : Glastonbury Tor, rang S) |

### Pistes Telluris
1. **Manannán** : un dieu de la mer **de plus**, distinct de **Tangaroa** (Mu) et de **Poséidon** (Atlantis) — chaque mer ses maîtres. L'**île de Man** cachée sous la brume pourrait être un lieu de légende des mers d'Irlande.
2. **La règle des marées en jeu** : marée haute/basse tirée de l'heure du jeu, ou de la proximité de la mer — pas de tick de fond, contrôle **au passage** (convention 5).
3. **Rhiannon et Annwn** : le sac vient d'une femme liée à Annwn, que la Chasse sauvage et les portails de Camelot fréquentent déjà ; il se trouverait **derrière un portail d'Annwn** (rang S) ou chez ceux qui en reviennent.
4. **Êtres uniques** : chacun des deux sacs existe **une fois** (comme le corrbolg qui passe de Lug à Fionn) ; des **imitations** d'Architectes ou de mages pourraient exister, moins puissantes.
5. **Mécanique de charge**, deux formes possibles :
   - **bonus de charge** sur le porteur, comme la `Selle_a_sacoches` sur une monture (`charge_pct`) ;
   - **poids annulé** pour ce qui est dans le sac (un **inventaire séparé**, comme le coffre d'une propriété) — plus fidèle au mythe, plus lourd à construire.
6. **Le joueur ne fabrique pas** : les deux sacs se trouvent, se gagnent ou s'achètent, jamais ne se craftent.

## 🤖 Claude Code — les Treize Trésors de l'île de Bretagne

*Tri Thlws ar Ddeg Ynys Prydain* : listes galloises des XVe–XVIe siècles, qui varient d'un manuscrit à l'autre (quelques objets changent, le compte aussi). Une tradition veut que **Merlin** (Myrddin) les ait réunis puis emportés dans sa **maison de verre** (sur **Ynys Enlli**, Bardsey, selon certains), d'où ils ne sont jamais revenus.

| # | Trésor | Pouvoir |
|---|---|---|
| 1 | **Dyrnwyn**, épée de Rhydderch Hael | S'embrase de la garde à la pointe quand un homme digne la tire ; nul autre ne peut la manier |
| 2 | **Panier** de Gwyddno Garanhir | On y met la nourriture d'un homme, on en retire celle de cent |
| 3 | **Corne** de Brân Galed | Donne la boisson qu'on souhaite |
| 4 | **Char** de Morgan Mwynfawr | Mène très vite qui s'y assoit où il veut |
| 5 | **Licol** de Clydno Eiddyn | Attaché au pied du lit, il fait venir dedans le cheval souhaité |
| 6 | **Couteau** de Llawfrodedd le Cavalier | Sert vingt-quatre hommes à table |
| 7 | **Chaudron** de Dyrnwch le Géant | Ne fait pas cuire la viande d'un lâche, cuit vite celle d'un brave |
| 8 | **Pierre à aiguiser** de Tudwal Tudglyd | Aiguisée par un brave, la lame tue qui elle blesse ; par un lâche, elle ne coupe rien |
| 9 | **Tunique** de Padarn Beisrudd | Va à un homme bien né, jamais à un rustre |
| 10 | **Plat et pot** de Rhygenydd le Clerc | Donnent la nourriture qu'on souhaite |
| 11 | **Échiquier** (*gwyddbwyll*) de Gwenddoleu ap Ceidio | Plateau d'or, pièces d'argent, qui jouent seules |
| 12 | **Manteau** d'Arthur en Cornouailles | Rend invisible qui s'en couvre |
| 13 | selon les listes : **manteau de Tegau Eurfron** (ne couvre que la femme fidèle), **pierre et anneau d'Eluned** (rendent invisible, donnés à Owain) | — |

- **Aucun n'est un contenant** : panier, corne, plat, couteau sont des objets **d'abondance** (même famille que la corne d'abondance et le chaudron d'Annwn, déjà retenu à Camelot à la place du Graal). Les autres **jugent** leur porteur (digne, brave, bien né, fidèle).
- ⚠️ **Le char de Morgan** contredit une règle du monde : **aucune magie ne déplace entre deux lieux** hors des portails. À écarter, ou à réduire à un char très rapide sur route.
- Lien avec le lore existant : Camelot et Merlin (Architecte **ou** fils d'un incube, théories concurrentes) ; la maison de verre serait un lieu de légende de plus.

## 🤖 Claude Code — et en Afrique ?

À ma connaissance, **aucun mythe africain ne décrit un sac de rangement** au sens du corrbolg. Mais plusieurs contenants **tiennent bien plus que leur taille**, presque tous à l'échelle **du monde** ou **du savoir** plutôt que du bagage :

| Contenant | Peuple | Ce qu'il contient |
|---|---|---|
| **La coquille d'escargot d'Oduduwa** (ou d'Obatala selon les versions) | Yoruba (Nigeria, Bénin) | Descendu du ciel le long d'une chaîne au-dessus des eaux primordiales, le dieu verse de cette **petite coquille** assez de **terre** pour faire toute la terre ferme ; une poule la gratte et l'étale, à **Ilé-Ifè**. Le cas le plus net : un tout petit objet qui contient un continent. |
| **L'Igbá Odù**, la calebasse d'Odù | Yoruba (culte d'Ifá) | Calebasse sacrée du pouvoir d'Odù, qu'aucun initié ne doit regarder. Le monde lui-même y est pensé comme **deux moitiés de calebasse** (ciel et terre). |
| **Le grenier céleste** | Dogon (Mali) | Une arche-grenier descend du ciel et porte les ancêtres, **toutes les espèces** d'animaux et de plantes, et le modèle du monde. Récit transmis par Marcel Griaule (*Dieu d'eau*), dont la fidélité est **discutée** par les ethnologues. |
| **Le pot de la sagesse d'Anansi** | Akan (Ghana) | L'araignée rassemble **toute la sagesse du monde** dans un pot (ou une calebasse) pour la garder pour elle ; en voulant le cacher au sommet d'un arbre, elle le brise, et la sagesse se répand partout. Anansi a aussi acheté au dieu du ciel **Nyame** la boîte de **toutes les histoires**. |
| **Les nkisi** | Kongo (Congo, Angola) | Statues creuses, sacs et paquets qui **enferment une puissance** (un esprit) ; on la réveille en y plantant un clou. Un contenant de **confinement**, comme la kibisis. |
| **Les coffres du Livre de Thot** | Égypte (conte de Setné Khâemouaset) | Le livre est caché au fond du Nil, à Coptos, dans des **coffres emboîtés** (fer, bronze, bois, ivoire et ébène, argent, or), gardés par des serpents. Le confinement, encore. |

- **Le plus proche de ton besoin** : la **coquille d'Oduduwa**. Elle répond au critère (contenu sans commune mesure avec le contenant), mais c'est un objet de **création du monde** et non un sac de voyage.
- **Ancrage Telluris** : l'Afrique du lore se limite aujourd'hui à Alexandrie, Abou Simbel et Aksoum. Ilé-Ifè, le pays dogon, le pays akan et le Kongo sont **hors de la carte** décrite : zones blanches, domaine des légendes.

## ✍️ Auteur (02/11/2026)

Le carquois inépuisable d'Arjuna (Mythologie hindoue / Mahabharata) : Dans l'épopée, le héros Arjuna possède des carquois divins (Akshayashtuka) qui ne se vident jamais, contenant une réserve infinie de flèches. C'est un entre-deux intéressant : un contenant fermé d'où l'on retire constamment des objets sans qu'il ne devienne jamais vide.

Le Sac de stockage extradimensionnel (Pop-culture moderne et folklore inspiré) : Le concept moderne le plus célèbre de ce que vous cherchez est le Sac sans fond (Bag of Holding) popularisé par les jeux de rôle sur table comme Donjons & Dragons, ou encore les poches magiques infinies qu'on retrouve dans la fantasy (comme la bourse de Mary Poppins ou les technologies de stockage de type Telluris). Ces objets ont l'air tout à fait ordinaires de l'extérieur, mais abritent un espace infini ou gigantesque à l'intérieur.

## 🤖 Claude Code — le carquois d'Arjuna, le sac sans fond

### Les carquois inépuisables d'Arjuna
- **Le nom** : « Akshayashtuka » n'est pas un terme attesté. Le Mahabharata parle de **deux carquois inépuisables** (*akṣaya tūṇīra*, « carquois qui ne s'épuisent pas »).
- **Source** : le *Khāṇḍava-dāha* (l'incendie de la forêt de Khāṇḍava, *Ādi Parva*). **Agni**, le feu, veut dévorer la forêt qu'**Indra** protège par la pluie. Pour l'y aider, il obtient de **Varuṇa**, dieu des eaux, et donne à Arjuna l'arc **Gāṇḍīva**, les deux carquois et un char aux chevaux blancs ; **Krishna** reçoit le disque **Sudarśana**.
- **La fin** : au début du *Mahāprasthānika Parva*, quand les Pāṇḍava partent pour leur dernier voyage, Agni demande à Arjuna de **rendre l'arc et les carquois à Varuṇa** : Arjuna les jette **dans la mer**. Les objets retournent à leur propriétaire, comme le corrbolg passe de main en main.
- **Nature** : un objet d'**abondance** (même famille que la corne, le panier de Gwyddno), restreint aux **munitions**. Il ne garde rien de ce qu'on y met.
- **En jeu, aujourd'hui** : les flèches existent comme objets (`item:Carquois_20`, `item:Carreaux_argentes`, catégorie `munition`) et des carquois d'équipement (`item:Carquois_de_cuir_bouilli`, `item:Carquois_emplume`, slot `ceinture`), mais **le combat ne décompte aucune munition**. Un carquois inépuisable n'aurait donc **aucun effet mécanique** tant que les flèches ne s'usent pas.
- **Ancrage** : l'Inde n'est pas décrite dans le lore ; seule **Muziris** (côte de Malabar) y apparaît, comme destination des portails de Petra et d'Aksoum.

### Le sac sans fond (*Bag of Holding*)
- **Ce n'est pas un mythe** : il vient des jeux de rôle (Donjons & Dragons, 1974) ; le sac de Mary Poppins vient du roman de P. L. Travers (1934) et du film (1964). Les règles de l'Auteur demandent d'**adapter des mythes réels** plutôt que d'inventer ou d'emprunter.
- **Le besoin de jeu reste le même** : un objet d'apparence ordinaire, avec un grand espace dedans. **Le sac de Manannán y répond déjà** à partir d'un mythe réel, avec en plus une contrainte (les marées) qui le rend moins puissant que le sac de D&D.
- La mention « technologies de stockage de type Telluris » ne renvoie à rien de connu : ni le lore, ni le dump.

## 🤖 ChatGPT (réponse transmise par l'Auteur, 02/11/2026)

> Texte transmis par l'Auteur (« de nombreuses remarques intéressantes ») ; images et renvois de sources retirés. **Proposition** : ne fait foi que ce que l'arbitrage ci-dessous retient.

Il existe plusieurs objets mythologiques ou folkloriques qui pourraient servir de base à un équivalent du sac sans fond, du coffre dimensionnel ou de la réserve de stockage magique : un objet qui ne crée rien, ne transforme rien, mais permet de transporter et de conserver une quantité de choses bien supérieure à son volume apparent.

Trois propriétés à distinguer :
- **Contenance extradimensionnelle** : l'objet contient un espace intérieur bien plus grand que son apparence.
- **Stockage sans limite apparente** : on peut y ajouter des objets presque indéfiniment.
- **Conservation** : ce qui est placé à l'intérieur ne vieillit pas, ne pourrit pas ou ne se détériore pas.

1. **La besace de Manannán (Crane Bag)** — la meilleure correspondance : une besace faite de la peau d'une grue, qui contient armes, vêtements, outils et objets merveilleux, associée à Lugh et à plusieurs héros irlandais ; les trésors deviennent visibles à marée haute et disparaissent à marée basse. Un objet de stockage véritable, sans être un objet de création ou de multiplication.
2. **Les gourdes magiques taoïstes** — celle de **Li Tieguai**, l'un des Huit Immortels, est emblématique ; elles transportent élixirs, remèdes et substances merveilleuses. Un récipient rigide dont l'intérieur est plus grand que l'ouverture ; déclinaisons possibles (liquides, substances alchimiques, capture de créatures, réserve de matériaux) — ce sont des adaptations, pas des propriétés d'une même gourde dans les légendes.
3. **Le sac magique des contes populaires** — motif répandu (Europe, Asie, Amériques), répertorié par l'index de Stith Thompson sous **D1193, « Magic bag (sack) »** : une famille d'objets plutôt qu'une relique précise.
4. **Skíðblaðnir** — le navire de Freyr, plié comme un tissu et rangé dans une poche : non pas un espace intérieur, mais un objet immense réduit à une taille transportable (tente, charrette, embarcation).
5. **Objets d'abondance, pas de stockage** : l'**Akshaya Patra** (hindou, nourriture inépuisable), la corne de Brân Galed, le panier de Gwyddno Garanhir, les vases **Óðrerir, Boðn et Són** (hydromel de poésie, nordique).

**Proposition pour Telluris** : non pas un objet légendaire universel, mais une **famille d'artefacts**, les **contenants spatiaux** :
- **Besace profonde** — usage courant chez les aventuriers fortunés : plusieurs centaines de kilos de matériel dans un volume réduit.
- **Urne intérieure** — contenant rigide, pour matériaux, minerais, cristaux de mana et marchandises.
- **Coffre de retrait** — artefact exceptionnel : un véritable espace clos accessible depuis un petit coffre (marchandises, réserves, mobilier, objets volumineux).

**Règles proposées** : le poids extérieur n'est pas le poids intérieur ; le volume reste limité ; la conservation n'est pas automatique ; les êtres vivants ne peuvent pas nécessairement y séjourner ; un contenant spatial dans un autre peut provoquer une anomalie.

**Lien avec les Architectes** : un portail relie deux espaces ; un contenant spatial serait un portail à **une seule ouverture**, l'entrée d'un espace intérieur artificiel. Certains Architectes se spécialiseraient dans les portails de transport, d'autres dans les espaces de stockage. Préférence : la besace de Manannán comme inspiration principale, et les contenants spatiaux comme **branche de l'artisanat magique**.

### 🤖 Claude Code — vérification
- Les références tiennent : gourde de Li Tieguai, motif **D1193** de Stith Thompson, Skíðblaðnir, Akshaya Patra (le récipient que Sūrya donne à Draupadī), Óðrerir, Boðn et Són. Une gourde qui **capture** existe bien dans *La Pérégrination vers l'Ouest* (la calebasse qui aspire qui répond à son nom).
- **Compatible avec les règles** : les contenants sont fabriqués par des **PNJ** (le joueur ne fabrique pas) ; un art d'Architecte reste **rare et coûteux**, comme la création d'un portail (transmission dégradée).
- **La conservation** n'a pas d'objet aujourd'hui : rien ne pourrit dans le jeu.

## ✍️ Auteur (02/11/2026) — arbitrage par cinq questionnaires

Réponses de l'Auteur ; elles **font foi**.

1. **Unicité** : les sacs de Manannán et de Rhiannon sont **uniques** ; des **copies moins puissantes** existent aussi.
2. **Lieux** : le sac de **Manannán** se trouve sur l'**île de Man**, cachée sous la brume des mers d'Irlande ; celui de **Rhiannon** derrière un **portail d'Annwn** (Glastonbury Tor, Camelot).
3. **Rangs** : **Manannán au rang A**, **Rhiannon au rang S**.
4. **Manannán** : **récit seulement** — on parle de lui (livres, PNJ, légendes de marins), il n'apparaît jamais ; son sac est l'héritage qu'il a laissé.
5. **Mécanique** : **inventaire séparé** — le contenant a son propre contenu, qui ne pèse rien pour le porteur, dans une **limite propre** à chaque contenant.
6. **Marées** (Manannán) : **gardées en jeu, sur l'heure du jeu** (deux marées hautes par jour), partout dans le monde ; on dépose à tout moment, on ne **reprend qu'à marée haute**.
7. **Piège de Rhiannon** (la règle du « assez ») : **récit seulement** ; en jeu, le sac est un grand contenant.
8. **Treize Trésors** : **plus tard**, dans une séance consacrée à Camelot.
9. **Afrique** : « Dès maintenant tu mets les listes et propose des mécaniques via des questionnaires » → les contenants africains sont listés (§ « et en Afrique ? ») et leurs mécaniques arbitrées aux points 17 à 20.
10. **Carquois d'Arjuna** : **retenu**, mais pas pour des flèches infinies : « c'est un objet avec un poids fixe et qui va pouvoir contenir un poids supérieur ». Un contenant comme les autres.
11. **Sac sans fond** : **hors du jeu** en tant que tel ; le **sac de Manannán** (et ses copies) tient ce rôle.
12. **Architectes** (idée de ChatGPT) : **oui, c'est leur art** — les copies sont l'œuvre d'**Architectes spécialisés** (contenants spatiaux), art rare et coûteux comme celui des portails.
13. **Contenu du carquois** : « Tout ça me semble trop compliqué d'essayer de faire autre chose » → **aucune restriction** de contenu (lecture de Claude Code : rester simple).
14. **Paliers des copies** : **trois** — **Besace profonde** (courante chez les aventuriers aisés), **Urne intérieure** (rigide, matériaux et marchandises), **Coffre de retrait** (rare, objets volumineux) ; contenance et prix croissants.
15. **Emboîtement** : **interdit** — le jeu refuse de ranger un contenant magique dans un autre ; les légendes racontent ce qui arrive à ceux qui ont essayé (mystère ouvert).
16. **Êtres vivants** : **jamais** — seuls les objets entrent dans un contenant.
17. **Coquille d'Oduduwa** : **contenant simple** (poids fixe, contenance très supérieure, tout objet) ; relique **unique**, la plus vaste de toutes.
18. **Grenier céleste dogon** : **récit seulement**.
19. **Pot de la sagesse d'Anansi** : **contenant simple**, tout objet.
20. **Reliques africaines** : obtenues au **rang S**, en voyage dans les **zones blanches**, au-delà de la carte connue.

## ✍️ Auteur (02/11/2026) — second arbitrage, trois questionnaires sur les points ouverts

Réponses de l'Auteur ; elles **font foi** et complètent le premier arbitrage.

21. **Contenance des copies** : Besace profonde **100 kg** · Urne intérieure **300 kg** · Coffre de retrait **1 000 kg**.
22. **Contenance des reliques** (la plus modeste des échelles proposées) : Carquois d'Arjuna et Pot d'Anansi **300 kg** · Sac de Manannán **500 kg** · Sac de Rhiannon **1 000 kg** · Coquille d'Oduduwa **2 000 kg**.
23. **Copie au-dessus d'une relique** : le Coffre de retrait (1 000 kg) dépasse le Sac de Manannán et égale celui de Rhiannon — **« c'est voulu »** : une relique vaut par sa légèreté et sa légende, pas par son volume.
24. **Poids propre** : **celui de l'objet ordinaire** qu'il imite — sac 0,5 kg, carquois 1 kg, pot 3 kg, urne 8 kg, coffre 20 kg, coquille 0,1 kg (valeurs proposées par Claude Code dans la question, retenues avec l'option).
25. **Prix des copies** : Besace profonde **10 000 cuivres** · Urne intérieure **40 000** · Coffre de retrait **150 000**.
26. **Vendeurs** : **Lutecia** (institut des Architectes) **et les cités qui entretiennent un portail transversal** (Rome, Constantinople, Petra…).
27. **Rang des copies** : **aucun** — « Pourquoi il devrait y avoir des limites de rang ? Le prix et le fait d'arriver à tel endroit qui en propose est déjà amplement suffisant. »
28. **Carquois d'Arjuna** (unicité, lieu) : **plus tard**, quand Muziris ou l'Inde seront décrites.
29. **Pot d'Anansi** : **plusieurs pots**, et non une relique unique.
30. **Autres contenants devenus objets** : **coffres du Livre de Thot**, **gourde de Li Tieguai**, **tente de Pari Banou**, **kibisis de Persée**, **outre d'Éole**. **Récit seulement** : Igbá Odù, nkisi, Skíðblaðnir.
31. **Marée haute** (Sac de Manannán) : chaque fenêtre dure **3 heures**, deux fois par jour (6 heures par jour en tout).

## Ce qui est retenu

| Contenant | Nature | Contenance | Poids | Contrainte | Où, quand |
|---|---|---|---|---|---|
| **Sac de Manannán** | relique unique | 500 kg | 0,5 kg | on ne reprend qu'à **marée haute** (2 × 3 h par jour, heure du jeu) | île de Man, rang **A** |
| **Sac de Rhiannon** | relique unique | 1 000 kg | 0,5 kg | — | derrière un portail d'Annwn, rang **S** |
| **Carquois d'Arjuna** | relique | 300 kg | 1 kg | — | **plus tard** |
| **Coquille d'Oduduwa** | relique unique, la plus vaste | 2 000 kg | 0,1 kg | — | zones blanches, rang **S** |
| **Pots d'Anansi** | plusieurs exemplaires | 300 kg | 3 kg | — | zones blanches, rang **S** |
| **Besace profonde** | copie d'Architectes | 100 kg | 0,5 kg | — | 10 000 cuivres |
| **Urne intérieure** | copie d'Architectes | 300 kg | 8 kg | — | 40 000 cuivres |
| **Coffre de retrait** | copie d'Architectes | 1 000 kg | 20 kg | — | 150 000 cuivres |
| **Coffres du Livre de Thot** | objet | 1 000 kg | 30 kg | — | à trancher |
| **Tente de Pari Banou** | objet | 1 500 kg | 2 kg | — | à trancher |
| **Outre d'Éole** | objet | 300 kg | 1,5 kg | — | à trancher |
| **Gourde de Li Tieguai** | objet | 200 kg | 1 kg | — | à trancher |
| **Kibisis de Persée** | objet | 100 kg | 0,5 kg | — | à trancher |

Copies : vendues à **Lutecia** et dans les **cités à portail transversal**, **sans condition de rang**. Règles communes : **inventaire séparé**, le contenu ne pèse rien pour le porteur, **limite propre** à chaque contenant ; **aucun être vivant** ; **aucun contenant magique dans un autre**. Récit seulement : Manannán lui-même, le piège de Rhiannon, le grenier céleste dogon, Igbá Odù, nkisi, Skíðblaðnir.

## Points encore ouverts

- **Cinq nouveaux objets** : contenance et poids arbitrés (02/11, « selon leur légende », `../../conception_contenants.md`) ; **pas uniques** (Auteur, 08/11) ; restent lieu et rang.
- **Reliques** : **une par personnage** ; copies vendues **à prix fixe par un PNJ Architecte de l'institut** (Auteur, 02/11) — à Lutecia, **à la Cour des Arches, avec Aélis** (Auteur, 08/11) : Maître Villard de Honnecourt.
- **Carquois d'Arjuna** : unicité, lieu, rang — quand Muziris ou l'Inde seront décrites.
- **Pots d'Anansi** : « plusieurs pots » mais obtention au rang S dans les zones blanches (point 20) — à confirmer.
- **Treize Trésors** : séance Camelot à venir.
- **Mécanique en jeu** : conçue et arbitrée dans `../../conception_contenants.md`, implémentée le 02/11 (reste le contenu à importer).
- Aucune date : rien à reporter dans `chronologie.json` tant que l'Auteur ne place pas ces récits dans une ère.
