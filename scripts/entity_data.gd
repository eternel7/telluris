# entity_data.gd
# Équivalent des objets JS { type, icon, name, hp, mvt, cc, ... }
# Utilisé comme Resource pour le joueur et les ennemis.
class_name EntityData
extends Resource

## Identits
@export var entity_name : String = ""
@export var is_player   : bool   = false

## Stats Legende
@export var hp      : int = 10
@export var max_hp  : int = 10
@export var str     : int = 3   # Force      → dégâts
@export var agi     : int = 3   # Agilité    → difficulté à toucher (pour les ennemis)
@export var ac      : int = 0   # Points d'Armure
@export var cc      : int = 3   # Close Combat
@export var rc      : int = 3   # Ranged combat
@export var mvt     : int = 3   # Cases de déplacement par PA

## Points d'action
@export var ap      : int = 2
@export var max_ap  : int = 2

## Position sur la grille
@export var grid_row : int = 0
@export var grid_col : int = 0
@export var icon : String = "!"

## État
@export var alive     : bool = true
@export var defending : bool = false

# Stats de session (non exportées — calculées en jeu)
var stats_kills : int = 0
var stats_dmg   : int = 0
var stats_rec   : int = 0
