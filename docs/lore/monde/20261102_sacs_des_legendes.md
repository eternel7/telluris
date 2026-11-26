# Le sac de Manannán et le sac de Rhiannon — contenants des légendes

Certains objets contiennent bien plus que leur taille. Les légendes en ont gardé quelques-uns, et les Architectes ont appris à en faire des copies.

## Le sac de Manannán

**Aoife** fut changée en grue par une rivale jalouse. Elle vécut deux cents ans dans la maison de **Manannán mac Lir**, le dieu de la mer, et à sa mort il fit de sa peau un sac. Le sac passa de main en main, de Manannán à Lug, jusqu'à Fionn, sans jamais se perdre. Il a une règle : quand la mer est pleine, ses trésors apparaissent ; quand elle se retire, le sac paraît vide. On peut y déposer à toute heure, mais on n'en reprend rien qu'à **marée haute**, deux fois trois heures par jour, où que l'on soit dans le monde.

Le sac est **unique**. Il repose sur l'**île de Man**, que Manannán cache sous la brume des mers d'Irlande, et il attend les aventuriers du **rang A**. Il contient jusqu'à **cinq cents kilos**. Manannán lui-même n'apparaît jamais : on parle de lui dans les livres, chez les marins et dans les légendes, et son sac est l'héritage qu'il a laissé.

## Le sac de Rhiannon

Promise contre son gré à Gwawl, **Rhiannon** choisit Pwyll. Quand Gwawl revint réclamer la fiancée, elle donna à Pwyll un petit sac qu'aucune nourriture ne pouvait remplir, tant qu'un homme de haut rang n'y tassait pas les mets de ses pieds en disant « assez ». Gwawl y entra, et on referma le sac sur lui. Ce piège appartient au récit ; sur Telluris, le sac de Rhiannon est un très grand contenant, **unique**, d'une contenance de **mille kilos**, qui se trouve derrière un **portail d'Annwn**, du côté de Glastonbury Tor et de Camelot, au **rang S**.

## Les autres reliques

- Les **carquois d'Arjuna**, qui ne se vidaient jamais de flèches dans l'épopée, sont ici un contenant comme les autres : un poids fixe pour une contenance bien supérieure, **trois cents kilos**. Où le trouver se dira quand l'Inde sera décrite.
- Dans les **zones blanches** d'Afrique, au-delà de la carte connue, attendent au **rang S** la **coquille d'Oduduwa**, de laquelle le dieu versa assez de terre pour faire toute la terre ferme, relique unique et la plus vaste de toutes (**deux mille kilos**), et les **pots d'Anansi**, où l'araignée voulut enfermer toute la sagesse du monde ; il y en a plusieurs, de **trois cents kilos** chacun.
- Le **grenier céleste** des Dogon, l'Igbá Odù, les nkisi et le navire pliable Skíðblaðnir n'existent que dans les récits.

Une relique pèse ce que pèse l'objet ordinaire qu'elle imite, et peut contenir n'importe quel objet. Chacun ne peut en porter qu'**une**. Les **reliques interdites** (Necronomicon, Table d'émeraude…) sont une autre famille, qui ne se compte pas avec celle-ci (voir [Les reliques interdites](20261126_reliques_interdites.md)).

## Les copies des Architectes

Copier ces reliques est un **art d'Architecte**, aussi rare et coûteux que celui des portails : un contenant est, en somme, un portail à une seule ouverture. Il en existe trois paliers :

| Copie | Contenance | Prix |
|---|---|---|
| **Besace profonde** | 100 kg | 50 000 cuivres |
| **Urne intérieure** | 300 kg | 200 000 cuivres |
| **Coffre de retrait** | 1 000 kg | 750 000 cuivres |

Une copie peut dépasser une relique, et c'est voulu : une relique vaut par sa légèreté et sa légende, pas par son volume. On les achète à prix fixe, sans condition de rang, à Lutecia et dans les cités qui entretiennent un portail transversal, auprès d'un Architecte de l'Institut. À Lutecia, c'est **Maître Villard de Honnecourt**, un nain maître d'œuvre, à la Cour des Arches, aux côtés d'Aélis.

Villard vend aussi deux **sacs à dos taillés dans un monstre**, à condition qu'on lui laisse un morceau de la bête : le **Sac de Grendel**, fait d'une aile de dragon comme la poche immense du monstre de *Beowulf* (deux cents kilos, dix pièces d'or), et le **Havresac de mimique**, taillé dans la carcasse du coffre qui mord, plus vaste dedans que dehors (cent cinquante kilos, huit pièces d'or). Il cite le havresac de Frère Lustig et la besace du soldat qui enferma la Mort, sans trancher : était-ce l'œuvre d'un Architecte, ou d'un saint ?

On trouve aussi, sans qu'ils soient uniques, les **coffres du Livre de Thot**, la **tente de Pari Banou**, l'**outre d'Éole**, la **gourde de Li Tieguai** et la **kibisis** de Persée.

## Les règles des contenants

Un contenant a son propre inventaire, qui ne pèse rien pour son porteur. **Aucun être vivant** n'y entre. Et l'on ne range **jamais un contenant magique dans un autre** : les légendes racontent ce qui est arrivé à ceux qui ont essayé, sans dire quoi. Le « sac sans fond » des contes modernes n'existe pas sur Telluris ; le sac de Manannán et ses copies en tiennent lieu. Les Treize Trésors de l'île de Bretagne attendent leur propre séance.

## 🗂 Échanges de travail

- **Source :** séance Claude Code du 02/11/2026. L'Auteur cherche des objets de légende qui **contiennent plus que leur taille**, où l'on dépose des choses pour les reprendre plus tard (la corne d'abondance, elle, produit sans fin).
- **Créée :** 02/11/2026
- **Statut :** intention de l'Auteur, puis **arbitrage** par huit questionnaires qui **fait foi** ; le reste des réponses Claude Code et ChatGPT = propositions. Rien n'est implémenté en jeu.
- **Au dump (02/11)** : aucun des deux sacs, ni Manannán, ni Rhiannon, ni Pwyll. Contenants existants, tous ordinaires : `item:Besace_de_cuir_fume` (ceinture, `bonus_initiative`), `item:Petite_bourse_vide` (outil), `item:Selle_a_sacoches` (harnachement, `monture.charge_pct` 25 — seul objet qui touche à la charge). La charge physique se lit dans `charge_max_of` (règle anti-exploit : caractéristiques **brutes**).
- **Séance complète :** archivée dans `docs/archives/lore/monde/20261102_sacs_des_legendes.md`.
