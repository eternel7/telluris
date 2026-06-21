// nav.js — logique de navigation par bitmask, PARTAGÉE entre play_town et combat.
// ⚠️ Miroir client de utils/lieux.py (get_final_mask / VALID_MOVES) — garder synchro.
//
// Bitmask par case : chaque bit = une direction INTERDITE depuis cette case
// (absence d'entrée = 0 = aucune interdiction). Vérification bidirectionnelle :
// une direction n'est permise que si la case source ET la case cible la laissent passer.
//
// Chargé en <script> classique (pas de module) : ces const/function sont visibles
// dans le script inline de la page (portée lexicale globale partagée).

// Directions nommées (compat play_town).
const DIRS = {
	HAUT:        1,   // 00000001
	HAUT_DROITE: 2,   // 00000010
	DROITE:      4,   // 00000100
	BAS_DROITE:  8,   // 00001000
	BAS:         16,  // 00010000
	BAS_GAUCHE:  32,  // 00100000
	GAUCHE:      64,  // 01000000
	HAUT_GAUCHE: 128, // 10000000
};

// [bit, dx, dy, bit opposé]
const VALID_MOVES = [
	[1, 0, -1, 16], [2, 1, -1, 32], [4, 1, 0, 64], [8, 1, 1, 128],
	[16, 0, 1, 1], [32, -1, 1, 2], [64, -1, 0, 4], [128, -1, -1, 8],
];

// (dx,dy) -> bit de direction.
const DIR_BIT = {};
VALID_MOVES.forEach(([bit, dx, dy]) => { DIR_BIT[`${dx},${dy}`] = bit; });

// Masque des directions AUTORISÉES depuis (x,y) (vérif bidirectionnelle source <-> cible).
function getFinalMask(nav, x, y) {
	const cur = (nav && nav[`${x},${y}`]) || 0;
	let mask = 0;
	for (const [bit, dx, dy, op] of VALID_MOVES) {
		if (cur & bit) continue;                          // direction interdite ici
		const tgt = (nav && nav[`${x + dx},${y + dy}`]) || 0;
		if (tgt & op) continue;                           // la cible interdit l'entrée
		mask |= bit;
	}
	return mask;
}

// La direction (dx,dy) depuis (x,y) est-elle autorisée par nav ? nav vide -> tout permis.
function navAllows(nav, x, y, dx, dy) {
	if (!nav || Object.keys(nav).length === 0) return true;
	const bit = DIR_BIT[`${dx},${dy}`];
	if (!bit) return false;
	return !!(getFinalMask(nav, x, y) & bit);
}
