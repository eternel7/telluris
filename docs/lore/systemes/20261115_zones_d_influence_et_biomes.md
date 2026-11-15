# Zones d'influence et biomes — décisions de l'Auteur

- **Arrêtées le :** 15 et 16/11/2026, par questionnaires
- **Sources :** [`docs/zones_biomes_proposition.md`](../../zones_biomes_proposition.md) (catalogue des biomes, validé le 16/11 ; révision au § 8)
- **Statut :** tout ce qui suit est **décidé par l'Auteur**. Les défauts de toutes les zones naturelles sont livrés dans `jsons/defauts_zones_biomes_a_importer.json` (`dev/gen_defauts_zones_biomes.py`) et ne sont en jeu qu'après import.
- **Moteur :** `utils/zones.py` (`peupler_lieu`), édition dans `/admin/zones` et l'éditeur de carte.

Une zone d'influence est une forme posée sur la carte d'un lieu : forêt, rivière, désert, ville… Quand on s'y déplace, elle décide de ce qu'on peut y rencontrer, de ce qu'on peut y récolter et du danger.

---

## 1. Une zone = un biome

- **Une zone par biome, jamais par lieu** : nom et `_id` **génériques**, sans aucune référence à une région, un pays, une île, un massif ou un fleuve réels. La zone décrit le **milieu**.
- Un milieu différent est une **zone neuve**, pas une variante : forêt claire sèche ≠ forêt de feuillus, fleuve tropical ≠ rivière. Les biomes tempérés déjà en base (`foret_feuillus`, `lac`, `riviere`…) restent tempérés.
- Chaque zone porte sa table d'événements (ressource, combat, PNJ, rien), ses modificateurs (danger, visibilité, déplacement) et ses `terrain_tags`, repris du vocabulaire des cartes de combat.

## 2. Le biome apporte son contenu

- La zone porte des **défauts** : `defauts_rencontres` (espèces) et `defauts_ressources` (items à récolter).
- **Tout lieu qui pose la zone en hérite**, sans rien recopier. Le contenu écrit dans le lieu lui-même s'**ajoute** à celui du biome (c'est un complément).
- Poser une forêt sur une carte de pays suffit donc à la peupler : loups, cerfs, chênes, herbes médicinales arrivent avec elle.

## 3. Régions de faune et de flore

- `rules:regions` regroupe les **pays** en régions de faune et de flore, pas en frontières politiques : Europe, Grand Nord, Steppes et Caucase, Afrique du Nord et Orient, Afrique subsaharienne, Océanie.
- Une cité ou un sous-lieu prend la région de son pays (par `lieu_parent`).
- Un défaut peut porter `regions` : il ne vaut alors que dans ces régions. **Révision du 15/11** : le filtre sert à la faune **typée** d'un biome présent sur plusieurs continents (le loup ou le cerf d'une rivière → Europe ; les hyènes d'une plaine → Afrique). Rien de régional sur le cosmopolite (serpent, rapaces), ni sur un biome déjà typé par lui-même (savane, taïga).

## 4. Ce que porte un biome

- **Faune ordinaire et monstres communs** (révision du 15/11) : gobelins et orcs des collines, trolls des montagnes et des fjords, troglodytes et araignées géantes des grottes, goules et spectres des ruines maudites, tritons et sirènes des mers.
- **Jamais** un légendaire, un boss, un être unique ou nommé, un ange ni un démon. Ceux-là sont du **contenu de placement**, posé à la main là où le lore le justifie.
- **Ressources du milieu** : essences d'arbres, herbes, minerais, sel, produits de la mer ou des ruchers.
- **Sans défaut** : les zones de cité (cœur, faubourgs, bas-quartiers, remparts), les zones habitables (propriétés du joueur) et les calques de danger (`tres_dangereuse`, `zone_danger_*`). Ce sont des règles posées sur la carte, pas des milieux.

## 5. Garder la main sur un lieu

- **Exclusion** : un lieu peut retirer un défaut, pour une zone ou pour toutes (`exclusions`).
- **Tout couper** : le tag `sans_defauts_zones` retire tous les défauts du lieu.
- **Placement** : une forme posée peut porter son **propre contenu**, valable dans cette forme seule. C'est là que vivent les créatures des mythes (la clairière d'un loup-garou, le repaire d'un griffon).
- Le contenu écrit d'un lieu ou d'un placement n'est jamais exclu.

## 6. Repères pour écrire

- Une zone ne raconte pas un lieu : la Seine est une `riviere`, pas une zone « Seine ».
- Le danger croît loin des remparts : la faune du biome est la menace ordinaire des routes ; les mythes se cherchent, ils ne tombent pas d'une table.
- Un endémique isolé (une espèce d'une seule région) passe par le filtre `regions` ou par un placement, jamais par une zone à son nom.
