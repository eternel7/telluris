// dev/test_voies_client.js
//
// Tests d'EXÉCUTION du tracé des voies (templates/scripts/voies.js) — carte « 🔍 Analyse
// d'image » de l'éditeur de carte.
//
//   node dev/test_voies_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le tracé sert à JUGER une carte (trou de rempart, gué, enclave). Un tracé faux
// ferait valider une carte cassée — ou chercher un défaut qui n'existe pas. Deux risques
// silencieux : une règle de marche qui dérive du mode test (d'où `pasAutoriseRegle`, partagé),
// et un goulot qui n'en est pas un.
//
// MÉTHODE : identique à dev/test_deplacement_client.js — on charge DIRECTEMENT nav.js,
// deplacement.js puis voies.js, par `vm.runInThisContext` (même realm, `deepStrictEqual`
// accepte les tableaux produits).
//
// HORS DE PORTÉE (à vérifier à l'écran, CLAUDE.md §15) : le dessin sur le canvas, la péremption
// affichée, les contrôles de la carte.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const SCRIPTS = path.join(__dirname, '..', 'templates', 'scripts');
for (const f of ['nav.js', 'deplacement.js', 'voies.js']) {
	const p = path.join(SCRIPTS, f);
	assert.ok(fs.existsSync(p), 'fichier introuvable : ' + p);
	vm.runInThisContext(fs.readFileSync(p, 'utf8'), { filename: p });
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const dims = g => ({ x: g[0].length, y: g.length });
function analyse(g, regle, nav) {
	const graphe = voiesGraphe(g, nav || {}, dims(g), regle || 'exploration');
	const regions = voiesRegions(graphe);
	return { graphe, regions, goulots: voiesGoulots(graphe, regions) };
}
const idx = (g, x, y) => y * g[0].length + x;

// Deux salles de 2×3 séparées par un rempart plein.
const MUR = [
	[1, 1, 0, 1, 1],
	[1, 1, 0, 1, 1],
	[1, 1, 0, 1, 1],
];
// Le même rempart, percé d'une case.
const TROU = [
	[1, 1, 0, 1, 1],
	[1, 1, 1, 1, 1],
	[1, 1, 0, 1, 1],
];

console.log('\n── Régions ────────────────────────────────────────────────────────────────');

t('un rempart plein sépare deux régions', () => {
	assert.deepStrictEqual(analyse(MUR).regions.tailles, [6, 6]);
});

t('un trou d’une case les réunit, et le trou est LE goulot', () => {
	const a = analyse(TROU);
	assert.deepStrictEqual(a.regions.tailles, [13]);
	assert.deepStrictEqual(a.goulots, [{ i: idx(TROU, 2, 1), importance: 6 }]);
});

t('un rempart ouvert EN COIN est un trou (les diagonales comptent)', () => {
	const COIN = [
		[1, 1, 0, 0, 0],
		[1, 1, 0, 0, 0],
		[0, 0, 1, 1, 1],
		[0, 0, 1, 1, 1],
	];
	const a = analyse(COIN);
	assert.deepStrictEqual(a.regions.tailles, [10]);
	assert.deepStrictEqual(a.goulots.map(g => g.i), [idx(COIN, 1, 1), idx(COIN, 2, 2)]);
});

t('l’eau (5) sépare en exploration, relie en combat', () => {
	const FLEUVE = [
		[1, 1, 1],
		[5, 5, 5],
		[1, 1, 1],
	];
	assert.deepStrictEqual(analyse(FLEUVE, 'exploration').regions.tailles, [3, 3]);
	assert.deepStrictEqual(analyse(FLEUVE, 'combat').regions.tailles, [9]);
});

t('un gué peint en 1 relie les deux rives à pied', () => {
	const GUE = [
		[1, 1, 1],
		[5, 1, 5],
		[1, 1, 1],
	];
	const a = analyse(GUE, 'exploration');
	assert.deepStrictEqual(a.regions.tailles, [7]);
	assert.deepStrictEqual(a.goulots, [{ i: idx(GUE, 1, 1), importance: 3 }]);
});

t('la falaise (3) bloque dans les DEUX règles', () => {
	const FALAISE = [
		[1, 1, 1],
		[3, 3, 3],
		[1, 1, 1],
	];
	assert.deepStrictEqual(analyse(FALAISE, 'exploration').regions.tailles, [3, 3]);
	assert.deepStrictEqual(analyse(FALAISE, 'combat').regions.tailles, [3, 3]);
});

t('un mur nav coupe une région, qu’il soit posé sur la source ou sur la cible', () => {
	const COULOIR = [[1, 1]];
	assert.deepStrictEqual(analyse(COULOIR, 'exploration', { '0,0': 4 }).regions.tailles, [1, 1]);
	assert.deepStrictEqual(analyse(COULOIR, 'exploration', { '1,0': 64 }).regions.tailles, [1, 1]);
	assert.deepStrictEqual(analyse(COULOIR, 'exploration', {}).regions.tailles, [2]);
});

t('le graphe est NON ORIENTÉ, nav comprise', () => {
	const g = [
		[1, 1, 1],
		[1, 2, 1],
		[1, 1, 1],
	];
	const nav = { '0,0': 4 | 8, '2,2': 1, '1,0': 16 };
	for (const regle of ['exploration', 'combat']) {
		const { voisins } = voiesGraphe(g, nav, dims(g), regle);
		voisins.forEach((vs, i) => vs.forEach(j => {
			assert.ok(voisins[j].includes(i), `${regle} : ${i}→${j} sans retour`);
		}));
	}
});

t('la région 0 est la plus grande ; les cases hors nœud valent -1', () => {
	const g = [
		[1, 0, 1, 1],
		[0, 0, 1, 1],
	];
	const a = analyse(g);
	assert.deepStrictEqual(a.regions.tailles, [4, 1]);
	assert.strictEqual(a.regions.region[idx(g, 0, 0)], 1);
	assert.strictEqual(a.regions.region[idx(g, 3, 1)], 0);
	assert.strictEqual(a.regions.region[idx(g, 1, 0)], -1);
});

t('sans grille, aucune case n’est praticable — même en combat', () => {
	const graphe = voiesGraphe(null, {}, { x: 3, y: 2 }, 'combat');
	assert.deepStrictEqual(voiesRegions(graphe).tailles, []);
});

console.log('\n── Goulots : seulement ceux qui coupent quelque chose ──────────────────────');

const IMPASSE = [
	[1, 1, 1, 0, 0],
	[1, 1, 1, 1, 1],
	[1, 1, 1, 0, 0],
];

t('une impasse d’une case n’est pas un goulot (seuil par défaut)', () => {
	assert.deepStrictEqual(analyse(IMPASSE).goulots, []);
});

t('… mais l’articulation existe bien, seuil abaissé à 1', () => {
	const a = analyse(IMPASSE);
	assert.deepStrictEqual(voiesGoulots(a.graphe, a.regions, 1), [{ i: idx(IMPASSE, 3, 1), importance: 1 }]);
});

t('une brèche de 2 cases n’a PAS de goulot unique', () => {
	const BRECHE = [
		[1, 1, 0, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 0, 1, 1],
	];
	const a = analyse(BRECHE);
	assert.deepStrictEqual(a.regions.tailles, [18]);
	assert.deepStrictEqual(a.goulots, []);
});

t('une longue file indienne ne fait pas sauter la pile (Tarjan itératif)', () => {
	const FILE = [new Array(20000).fill(1)];
	const a = analyse(FILE);
	assert.strictEqual(a.regions.tailles[0], 20000);
	// Toute case intérieure est une articulation ; celles à moins de 3 cases d'un bout sont filtrées.
	assert.strictEqual(a.goulots.length, 20000 - 2 - 2 * 2);
});

console.log('\n── Carte de passage ───────────────────────────────────────────────────────');

t('le trou du rempart est la case la plus traversée', () => {
	const { graphe } = analyse(TROU);
	const p = voiesPassage(graphe);
	const trou = idx(TROU, 2, 1);
	assert.strictEqual(p[trou], 1);
	p.forEach((v, i) => { if (i !== trou) assert.ok(v < 1, `case ${i} = ${v}`); });
});

t('une case hors nœud vaut 0 ; la carte est déterministe', () => {
	const { graphe } = analyse(TROU);
	const a = voiesPassage(graphe), b = voiesPassage(graphe);
	assert.deepStrictEqual(a, b);
	assert.strictEqual(a[idx(TROU, 2, 0)], 0);
});

t('l’échantillonnage au pas fixe reste borné à [0,1] et déterministe', () => {
	const { graphe } = analyse(TROU);
	const a = voiesPassage(graphe, 3), b = voiesPassage(graphe, 3);
	assert.deepStrictEqual(a, b);
	assert.ok(a.every(v => v >= 0 && v <= 1));
	assert.ok(a.some(v => v === 1));
});

t('une grille sans nœud rend une carte nulle, sans lever', () => {
	const { graphe } = analyse([[0, 0], [0, 0]]);
	assert.ok(voiesPassage(graphe).every(v => v === 0));
});

console.log('\n── Signature : détecter un tracé périmé ───────────────────────────────────');

t('même grille, même nav ⇒ même signature ; l’ordre des clés nav n’y change rien', () => {
	const d = dims(TROU);
	assert.strictEqual(voiesSignature(TROU, { '0,0': 4, '1,1': 2 }, d),
		voiesSignature(TROU.map(l => l.slice()), { '1,1': 2, '0,0': 4 }, d));
});

t('une case, une entrée nav ou les dimensions changent la signature', () => {
	const d = dims(TROU);
	const base = voiesSignature(TROU, {}, d);
	const peinte = TROU.map(l => l.slice()); peinte[1][2] = 0;
	assert.notStrictEqual(voiesSignature(peinte, {}, d), base);
	assert.notStrictEqual(voiesSignature(TROU, { '2,1': 4 }, d), base);
	assert.notStrictEqual(voiesSignature(TROU, {}, { x: 5, y: 2 }), base);
});

console.log('\n── Directions nav près des murs ───────────────────────────────────────────');

// Rempart vertical percé en (2,1) ; nav ferme la DROITE depuis la brèche.
const REMPART = [
	[1, 1, 0, 1, 1],
	[1, 1, 1, 1, 1],
	[1, 1, 0, 1, 1],
];

t('la brèche ET sa voisine de l’autre côté du mur nav sont listées (bidirectionnel)', () => {
	const r = voiesDirectionsNav(REMPART, { '2,1': 4 }, dims(REMPART), 'exploration', 2);
	assert.deepStrictEqual(r, [
		{ i: idx(REMPART, 2, 1), murs: 2,
			autorisees: [[-1, -1], [1, -1], [-1, 0], [-1, 1], [1, 1]], fermeesNav: [[1, 0]] },
		// (3,1) ne porte AUCUNE entrée nav : c'est la brèche qui lui interdit d'entrer par la gauche.
		{ i: idx(REMPART, 3, 1), murs: 2,
			autorisees: [[0, -1], [1, -1], [1, 0], [0, 1], [1, 1]], fermeesNav: [[-1, 0]] },
	]);
});

t('sans restriction nav, rien n’est listé — même contre un mur', () => {
	assert.deepStrictEqual(voiesDirectionsNav(REMPART, {}, dims(REMPART), 'exploration', 1), []);
});

t('un seuil au-dessus du nombre de murs exclut la case', () => {
	assert.deepStrictEqual(voiesDirectionsNav(REMPART, { '2,1': 4 }, dims(REMPART), 'exploration', 3), []);
});

t('la règle compte : en combat, le terrain difficile devient une direction autorisée', () => {
	const DIFFICILE = [
		[0, 0, 1],
		[2, 1, 1],
		[0, 0, 1],
	];
	const cle = idx(DIFFICILE, 1, 1);
	const expl = voiesDirectionsNav(DIFFICILE, { '1,1': 1 }, dims(DIFFICILE), 'exploration', 2).find(d => d.i === cle);
	const comb = voiesDirectionsNav(DIFFICILE, { '1,1': 1 }, dims(DIFFICILE), 'combat', 2).find(d => d.i === cle);
	assert.strictEqual(expl.murs, 4);
	assert.ok(!expl.autorisees.some(([dx, dy]) => dx === -1 && dy === 0), 'terrain 2 refusé à pied');
	assert.ok(comb.autorisees.some(([dx, dy]) => dx === -1 && dy === 0), 'terrain 2 franchi en combat');
});

console.log('\n── Chemin A → B ───────────────────────────────────────────────────────────');

t('le chemin franchit le rempart par le trou', () => {
	const { graphe } = analyse(TROU);
	const a = idx(TROU, 0, 1), b = idx(TROU, 4, 1);
	const c = voiesChemin(graphe, a, b);
	assert.strictEqual(c.length, 5);
	assert.strictEqual(c[0], a);
	assert.strictEqual(c[c.length - 1], b);
	assert.ok(c.includes(idx(TROU, 2, 1)));
	assert.deepStrictEqual(voiesChemin(graphe, a, b), c, 'déterministe');
});

t('pas de chemin à travers un mur plein, ni depuis une case à 0 ; A = B rend [A]', () => {
	const mur = analyse(MUR).graphe;
	assert.strictEqual(voiesChemin(mur, idx(MUR, 0, 1), idx(MUR, 4, 1)), null);
	assert.strictEqual(voiesChemin(mur, idx(MUR, 2, 1), idx(MUR, 4, 1)), null);
	assert.deepStrictEqual(voiesChemin(mur, idx(MUR, 0, 1), idx(MUR, 0, 1)), [idx(MUR, 0, 1)]);
});

console.log('\n── Coupe minimale A ↔ B ───────────────────────────────────────────────────');

t('une brèche de 2 cases : la coupe est exactement ces 2 cases', () => {
	const BRECHE = [
		[1, 1, 0, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 0, 1, 1],
	];
	const { graphe, regions } = analyse(BRECHE);
	const r = voiesCoupeMin(graphe, regions, idx(BRECHE, 0, 1), idx(BRECHE, 4, 1));
	assert.deepStrictEqual(r, { statut: 'coupe', cases: [idx(BRECHE, 2, 1), idx(BRECHE, 2, 2)], collee: null });
});

t('un trou d’une case : la coupe est le trou', () => {
	const { graphe, regions } = analyse(TROU);
	assert.deepStrictEqual(voiesCoupeMin(graphe, regions, idx(TROU, 0, 1), idx(TROU, 4, 1)),
		{ statut: 'coupe', cases: [idx(TROU, 2, 1)], collee: null });
});

t('statuts : séparées, adjacentes, hors voie, identiques', () => {
	const mur = analyse(MUR);
	assert.strictEqual(voiesCoupeMin(mur.graphe, mur.regions, idx(MUR, 0, 1), idx(MUR, 4, 1)).statut, 'separees');
	const trou = analyse(TROU);
	assert.strictEqual(voiesCoupeMin(trou.graphe, trou.regions, idx(TROU, 0, 0), idx(TROU, 1, 0)).statut, 'adjacentes');
	assert.strictEqual(voiesCoupeMin(trou.graphe, trou.regions, idx(TROU, 2, 0), idx(TROU, 4, 1)).statut, 'hors voie');
	assert.strictEqual(voiesCoupeMin(trou.graphe, trou.regions, idx(TROU, 0, 1), idx(TROU, 0, 1)).statut, 'identiques');
});

t('A dans un coin face à une brèche plus large que son voisinage : collee = A', () => {
	const LARGE = [
		[1, 1, 0, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1],
		[1, 1, 0, 1, 1],
	];
	const { graphe, regions } = analyse(LARGE);
	const r = voiesCoupeMin(graphe, regions, idx(LARGE, 0, 0), idx(LARGE, 4, 3));
	assert.deepStrictEqual(r, { statut: 'coupe', cases: [idx(LARGE, 1, 0), idx(LARGE, 0, 1), idx(LARGE, 1, 1)], collee: 'A' });
	assert.deepStrictEqual(voiesCoupeMin(graphe, regions, idx(LARGE, 0, 0), idx(LARGE, 4, 3)), r, 'déterministe');
});

t('collee = coupe faite de voisines de A, même quand un coin en garde une partie de son côté', () => {
	// Brèche de 6 cases en x=4 ; A en (1,1) a 8 voisines, mais le coin (0,0),(1,0),(0,1) ne mène
	// nulle part : la coupe minimale en prend 5 autour de A. Une égalité stricte avec le voisinage
	// (8) la laissait passer pour une vraie brèche — c'est le cas relevé sur Auxerre.
	const COIN = [
		[1, 1, 1, 1, 0, 1, 1],
		[1, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 0, 1, 1],
	];
	const { graphe, regions } = analyse(COIN);
	const r = voiesCoupeMin(graphe, regions, idx(COIN, 1, 1), idx(COIN, 6, 4));
	assert.deepStrictEqual(r, {
		statut: 'coupe',
		cases: [idx(COIN, 2, 0), idx(COIN, 2, 1), idx(COIN, 0, 2), idx(COIN, 1, 2), idx(COIN, 2, 2)],
		collee: 'A',
	});
});

t('un mur nav entre dans la coupe : fermer la brèche par nav sépare les deux salles', () => {
	// Nav interdit toute sortie de la brèche vers la droite (↗ → ↘) : plus rien à couper.
	const a = analyse(TROU, 'exploration', { '2,1': 2 | 4 | 8 });
	assert.strictEqual(voiesCoupeMin(a.graphe, a.regions, idx(TROU, 0, 1), idx(TROU, 4, 1)).statut, 'separees');
});

console.log('\n── Chemins multiples A → B ────────────────────────────────────────────────');

// Rempart vertical (x = 3) percé en haut ET en bas : deux passages bien distincts.
const DEUX_TROUS = [
	[1, 1, 1, 1, 1, 1, 1],
	[1, 1, 1, 0, 1, 1, 1],
	[1, 1, 1, 0, 1, 1, 1],
	[1, 1, 1, 0, 1, 1, 1],
	[1, 1, 1, 1, 1, 1, 1],
];
// Brèche de DEUX cases contiguës : un seul passage, large.
const BRECHE2 = [
	[1, 1, 1, 0, 1, 1, 1],
	[1, 1, 1, 1, 1, 1, 1],
	[1, 1, 1, 1, 1, 1, 1],
	[1, 1, 1, 0, 1, 1, 1],
];

function cheminValide(graphe, c, a, b) {
	assert.strictEqual(c[0], a, 'part de A');
	assert.strictEqual(c[c.length - 1], b, 'finit en B');
	for (let k = 1; k < c.length; k++) {
		assert.ok(graphe.voisins[c[k - 1]].includes(c[k]), `pas ${k} hors graphe`);
	}
}

t('deux trous : deux chemins, un par trou — et pas de troisième', () => {
	const { graphe } = analyse(DEUX_TROUS);
	const a = idx(DEUX_TROUS, 0, 2), b = idx(DEUX_TROUS, 6, 2);
	const haut = idx(DEUX_TROUS, 3, 0), bas = idx(DEUX_TROUS, 3, 4);
	const cs = voiesChemins(graphe, a, b, 3);
	assert.strictEqual(cs.length, 2);
	cs.forEach(c => cheminValide(graphe, c, a, b));
	assert.deepStrictEqual(cs[0], voiesChemin(graphe, a, b), 'le premier est le plus court');
	assert.deepStrictEqual(cs.map(c => [c.includes(haut), c.includes(bas)]).sort(),
		[[false, true], [true, false]], 'chaque trou exactement une fois');
	assert.deepStrictEqual(voiesChemins(graphe, a, b, 3), cs, 'déterministe');
});

t('une brèche de 2 cases : écartés d’une case ⇒ 1 chemin ; strictement disjoints ⇒ 2', () => {
	const { graphe } = analyse(BRECHE2);
	const a = idx(BRECHE2, 0, 1), b = idx(BRECHE2, 6, 1);
	assert.strictEqual(voiesChemins(graphe, a, b, 8).length, 1, 'écart par défaut = 1');
	assert.strictEqual(voiesChemins(graphe, a, b, 8, 1).length, 1);
	assert.strictEqual(voiesChemins(graphe, a, b, 8, 0).length, 2);
});

t('le nombre demandé est respecté, borné à [1, VOIES_CHEMINS_MAX]', () => {
	const { graphe } = analyse(DEUX_TROUS);
	const a = idx(DEUX_TROUS, 0, 2), b = idx(DEUX_TROUS, 6, 2);
	assert.deepStrictEqual(voiesChemins(graphe, a, b, 1), [voiesChemin(graphe, a, b)]);
	assert.strictEqual(voiesChemins(graphe, a, b, 0).length, 1, 'plancher à 1');
	assert.strictEqual(voiesChemins(graphe, a, b, 'n’importe quoi').length, 2, 'repli sur le défaut');
	assert.strictEqual(voiesChemins(analyse(BRECHE2).graphe, idx(BRECHE2, 0, 1), idx(BRECHE2, 6, 1), 99, 0).length, 2);
});

t('cas limites : A = B, A et B voisins (sans boucler), hors voie, mur plein', () => {
	const { graphe } = analyse(TROU);
	assert.deepStrictEqual(voiesChemins(graphe, idx(TROU, 0, 1), idx(TROU, 0, 1), 3), [[idx(TROU, 0, 1)]]);
	assert.deepStrictEqual(voiesChemins(graphe, idx(TROU, 0, 0), idx(TROU, 1, 0), 8),
		[[idx(TROU, 0, 0), idx(TROU, 1, 0)]], 'le chemin tient dans les abords : arrêt');
	assert.deepStrictEqual(voiesChemins(graphe, idx(TROU, 2, 0), idx(TROU, 4, 1), 3), []);
	const mur = analyse(MUR).graphe;
	assert.deepStrictEqual(voiesChemins(mur, idx(MUR, 0, 1), idx(MUR, 4, 1), 3), []);
});

t('un passage OBLIGÉ hors des abords n’empêche plus les variantes (méthode par pénalité)', () => {
	// Rempart x = 4 percé d'UNE porte (4,3), loin de A ; au-delà, un pilier (x = 6, y 2-4) se
	// contourne par le haut OU par le bas. Retirer les cases du premier chemin murait la porte :
	// un seul chemin — c'est le défaut vu sur Auxerre (74 % des paires).
	const PORTE_PILIER = [
		[1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1],
		[1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1],
		[1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1],
		[1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1],
		[1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1],
	];
	const { graphe } = analyse(PORTE_PILIER);
	const a = idx(PORTE_PILIER, 0, 3), b = idx(PORTE_PILIER, 10, 3);
	const porte = idx(PORTE_PILIER, 4, 3);
	const avant = voiesChemin(graphe, a, b);
	const cs = voiesChemins(graphe, a, b, 3);
	assert.strictEqual(cs.length, 2, 'par le haut et par le bas du pilier');
	cs.forEach(c => { cheminValide(graphe, c, a, b); assert.ok(c.includes(porte), 'la porte reste empruntable'); });
	const cote = c => c.some(i => i % 11 === 6 && Math.floor(i / 11) < 2) ? 'haut' : 'bas';
	assert.deepStrictEqual(cs.map(cote).sort(), ['bas', 'haut']);
	assert.ok(cs.every(c => c.length >= cs[0].length), 'le premier est le plus court');
	assert.deepStrictEqual(voiesChemin(graphe, a, b), avant, 'le graphe n’est pas modifié');
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
