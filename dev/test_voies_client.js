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

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
