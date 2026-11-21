# dev/retires/ — scripts à ne plus lancer

Gardés pour l'historique : relire comment un contenu a été produit, retrouver une table ou une règle. **Ne pas les lancer.** Ils ne sont plus au catalogue de `/admin/dev-tools`, et `utils/dev_tools._py` refuse tout chemin sous ce dossier (verrouillé par `tests/test_dev_tools.py`).

⚠️ Ils ne tournent plus tels quels : leur `RACINE` (deux `dirname` au-dessus du fichier) désigne désormais `dev/`, et la plupart lisent un dump qui n'existe plus. Remis en route sur un vieux dump, leur sortie (import = PUT complet, CLAUDE.md §11) écraserait l'état actuel de la base.

Retirés le 21/11/2026 :

| Script | Raison |
|---|---|
| `gen_acces_donjon.py` | dump figé du 26/07 (disparu) ; réécrirait Gautier, Borin, George et Armand sans les quêtes posées depuis |
| `gen_armes_tranchantes.py` | dump figé du 31/08 (disparu) |
| `gen_boulangeries.py` | dump figé du 05/09 (disparu) |
| `gen_coherence_france.py` | dump figé du 08/08 (disparu) ; réécrirait `lieu:france` |
| `gen_convoi_lutecia.py` | dump figé du 13/09 (disparu) ; importé par `gen_garde_notre_dame.py` |
| `gen_garde_notre_dame.py` | dump figé du 13/09 (disparu) |
| `gen_depecage_tags.py` | dump figé du 24/09 (disparu) ; réécrirait `rules:world_variables` en entier |
| `gen_escorte_guilde.py` | dump figé du 08/08 (disparu) |
| `gen_escorte_marchands.py` | dump figé du 08/08 (disparu) |
| `gen_grades_france.py` | dump figé du 08/08 (disparu) ; réécrirait `lieu:france` |
| `gen_lutecia.py` | dump figé du 08/08 (disparu) ; réécrirait `lieu:lutecia` |
| `gen_mission_bucherons.py` | dump figé du 01/09 (disparu) ; réécrirait Gautier sans l'enquête d'Escolives |
| `gen_mission_bucherons_rdv.py` | dump figé du 03/09 (disparu) |
| `gen_relation_guilde.py` | dump figé du 07/08 (disparu) |
| `gen_repurgateur_noire.py` | dump figé du 13/09 (disparu) ; réécrirait `rules:vocations` en entier |
| `gen_stock_cible_ateliers.py` | dump figé du 31/08 (disparu) |
| `gen_quete_rang_c_jumieges.py` | repart de fichiers sources disparus ; effacerait les `offres` de Maëlys (épreuves B et A) |
| `gen_portrait_aelis_jumieges.py` | dépend de `gen_quete_rang_c_jumieges.py` |
| `gen_piece_derriere_le_mur.py` | réécrit l'escorte d'Aélis en offre seule : effacerait « Les vestiges du premier passage » |
| `purge_quetes_acceptees.py` | purge one-shot, arriéré soldé |

Retirer un script : `git mv dev/<script> dev/retires/`, retirer son entrée du catalogue (`utils/dev_tools.py`), ajouter une ligne ici.
