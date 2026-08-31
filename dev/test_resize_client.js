// dev/test_resize_client.js
//
// Tests d'EXÉCUTION du JavaScript de redimensionnement de grille
// (templates/admin_map_editor.html, carte « 📐 Dimensions »).
//
//   node dev/test_resize_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le redimensionnement est la seule écriture du jeu capable de changer la FORME d'une
// carte, et toute sa logique vit dans un template — hors de portée de pytest. Une erreur d'un
// indice ne casse rien de visible : elle décale silencieusement le terrain, la navigation, les
// zones et les portes les uns par rapport aux autres, et ne se découvre qu'en jouant.
//
// MÉTHODE : on extrait du template les fonctions PURES (par nom, accolades équilibrées) et on les
// exécute dans un contexte `vm` nu. Pas de DOM, donc aucune dépendance — le rendu, la carte et les
// trois écritures du 💾 restent hors de portée et se vérifient en jeu.
//
// ⚠️ L'extraction se fait par NOM : renommer une fonction ici visée fait échouer le test avec
// « fonction introuvable » — c'est voulu, pas un faux positif.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_map_editor.html');
const src = fs.readFileSync(TEMPLATE, 'utf8');

// Le template porte plusieurs blocs <script> : on les concatène, l'extraction se faisant ensuite
// par nom de fonction.
const js = [...src.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
	.map(m => m[1]).join('\n');
assert.ok(js, 'aucun bloc <script> trouvé dans ' + TEMPLATE);

function extraire(nom) {
	const debut = js.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable dans le template');
	let prof = 0;
	for (let j = js.indexOf('{', debut); j < js.length; j++) {
		if (js[j] === '{') prof++;
		else if (js[j] === '}' && --prof === 0) return js.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

// ⚠️ `runInThisContext` et NON `vm.createContext` (ce que fait test_slots_client, qui doit lui
// injecter de fausses globales) : un contexte séparé est un autre realm, donc ses tableaux ont un
// autre prototype `Array` et `deepStrictEqual` les refuse tous. Ces fonctions-ci n'ont besoin
// d'aucune globale — les évaluer dans le realm du test suffit et rend les comparaisons directes.
const ctx = globalThis;
for (const f of ['_resizeIndex', '_grilleTaille', '_resizeMatrice', '_resizeNav', '_resizeZones',
                 '_zonesDeformees', '_resizePos', '_caseLibreProche',
                 // Ces deux-la ne sont PAS pures : elles lisent les globales de l'editeur.
                 // On les amene quand meme, en semant ces globales sur globalThis - c'est le
                 // seul moyen d'eprouver l'IDEMPOTENCE du recalage des portes, le piege du module.
                 '_caseAccessible', '_reappliquerPortes']) {
	vm.runInThisContext(extraire(f));
}

// Table de directions du template, recopiée ici : le test doit pouvoir affirmer que la fonction
// se comporte bien pour CETTE table, sans dépendre de l'ordre du fichier.
const NAV_DIRS = [
	[1, 0, -1], [2, 1, -1], [4, 1, 0], [8, 1, 1],
	[16, 0, 1], [32, -1, 1], [64, -1, 0], [128, -1, -1],
];

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Implémentation de RÉFÉRENCE, transcrite du script Python fourni par l'auteur : c'est elle qui
// définit ce que « plus proche voisin » veut dire ici, et le template doit lui être identique.
function referenceMatrice(m, nx, ny) {
	const oy = m.length, ox = oy > 0 ? m[0].length : 0;
	const out = [];
	for (let y = 0; y < ny; y++) {
		const sy = Math.floor(y * oy / ny);
		const ligne = [];
		for (let x = 0; x < nx; x++) ligne.push(m[sy][Math.floor(x * ox / nx)]);
		out.push(ligne);
	}
	return out;
}

const damier = (w, h) => Array.from({ length: h }, (_, y) =>
	Array.from({ length: w }, (_, x) => (x + y * w)));

console.log('\n── Rééchantillonnage de cells ──');

t('la réduction rend la taille demandée', () => {
	const out = ctx._resizeMatrice(damier(60, 40), 57, 32);
	assert.strictEqual(out.length, 32);
	assert.ok(out.every(l => l.length === 57));
});

t('l’agrandissement rend la taille demandée', () => {
	const out = ctx._resizeMatrice(damier(10, 8), 25, 19);
	assert.strictEqual(out.length, 19);
	assert.ok(out.every(l => l.length === 25));
});

t('identique au script Python de référence (réduction ET agrandissement)', () => {
	for (const [w, h, nx, ny] of [[60, 40, 57, 32], [10, 8, 25, 19], [86, 48, 1, 1], [7, 5, 7, 5]]) {
		const m = damier(w, h);
		assert.deepStrictEqual(ctx._resizeMatrice(m, nx, ny), referenceMatrice(m, nx, ny),
			`écart pour ${w}×${h} → ${nx}×${ny}`);
	}
});

t('taille inchangée = matrice inchangée', () => {
	const m = damier(9, 6);
	assert.deepStrictEqual(ctx._resizeMatrice(m, 9, 6), m);
});

t('la matrice source n’est pas mutée', () => {
	const m = damier(6, 4);
	const copie = m.map(l => [...l]);
	ctx._resizeMatrice(m, 3, 2);
	assert.deepStrictEqual(m, copie);
});

console.log('\n── Taille réelle de la grille (cells fait foi) ──');

t('la taille vient de la matrice, jamais du champ dimensions', () => {
	assert.deepStrictEqual(_grilleTaille(damier(60, 40)), { x: 60, y: 40 });
	assert.deepStrictEqual(_grilleTaille([]), { x: 0, y: 0 });
	assert.deepStrictEqual(_grilleTaille(null), { x: 0, y: 0 });
});

t('sur une grille irrégulière, la largeur est le MAXIMUM des lignes', () => {
	// ⚠️ Prendre `m[0].length` rognerait en silence les lignes plus longues — et rogner sans le
	// dire est exactement ce qu'un outil de réparation ne doit pas faire.
	assert.deepStrictEqual(_grilleTaille([[1, 1], [1, 1, 1, 1], [1]]), { x: 4, y: 3 });
});

t('les trous d’une grille irrégulière sont comblés par le défaut', () => {
	const out = _resizeMatrice([[7, 7, 7, 7], [7, 7]], 4, 2, 1);
	assert.deepStrictEqual(out, [[7, 7, 7, 7], [7, 7, 1, 1]]);
});

t('le défaut vaut 1 (libre) quand il n’est pas fourni', () => {
	assert.deepStrictEqual(_resizeMatrice([[9], []], 1, 2), [[9], [1]]);
});

t('RÉPARATION : une grille 60×40 sous des dimensions menteuses se rééchantillonne bien depuis 60×40', () => {
	// Le cas qui a motivé le geste : le doc annonce 57×32, la grille en fait 60×40. Le résultat
	// doit être celui du script Python appliqué à la GRILLE, pas à l'annonce.
	const m = damier(60, 40);
	assert.deepStrictEqual(_resizeMatrice(m, 57, 32, 1), referenceMatrice(m, 57, 32));
});

console.log('\n── Rééchantillonnage de nav (dict creux) ──');

t('une clé absente reste absente, un masque nul n’est jamais écrit', () => {
	assert.deepStrictEqual(ctx._resizeNav({}, 4, 4, 8, 8, NAV_DIRS), {});
	assert.deepStrictEqual(ctx._resizeNav(null, 4, 4, 8, 8, NAV_DIRS), {});
	assert.deepStrictEqual(ctx._resizeNav({ '1,1': 0 }, 8, 8, 8, 8, NAV_DIRS), {});
});

t('à taille égale, nav est rendu à l’identique', () => {
	const nav = { '3,2': 135, '7,7': 16, '0,0': 4 };
	assert.deepStrictEqual(ctx._resizeNav(nav, 8, 8, 8, 8, NAV_DIRS), nav);
});

t('nav et cells viennent de la MÊME case source', () => {
	// Le mur est posé sur la case source dont le terrain vaut 9 : après coup, toute case portant
	// une entrée nav doit encore porter ce terrain. C'est l'invariante que `_resizeIndex` garantit.
	const cells = damier(10, 10).map((l, y) => l.map((_, x) => (x === 4 && y === 6) ? 9 : 1));
	const nav = { '4,6': 4 };
	const c2 = ctx._resizeMatrice(cells, 23, 17);
	const n2 = ctx._resizeNav(nav, 23, 17, 10, 10, NAV_DIRS);
	assert.ok(Object.keys(n2).length > 0, 'le mur a disparu');
	for (const cle of Object.keys(n2)) {
		const [x, y] = cle.split(',').map(Number);
		assert.strictEqual(c2[y][x], 9, `nav en ${cle} sur un terrain ${c2[y][x]}`);
	}
});

t('AGRANDISSEMENT : un mur ne se duplique pas à l’intérieur de sa propre case', () => {
	// ⚠️ LE défaut que ce module doit éviter : la case source (1,1) interdit la DROITE (bit 4).
	// Dupliquée telle quelle en ×2, elle donnerait le bit 4 sur (2,2) ET (3,2) — celui de (2,2)
	// fermant la frontière 2→3, c'est-à-dire un mur AU MILIEU de ce qui était une case ouverte.
	// Seule la case la plus à droite du bloc a le droit de porter le bit.
	const n2 = ctx._resizeNav({ '1,1': 4 }, 6, 6, 3, 3, NAV_DIRS);
	assert.deepStrictEqual(n2, { '3,2': 4, '3,3': 4 },
		'attendu : le bit DROITE seulement sur la colonne droite du bloc, pas sur la gauche');
});

t('AGRANDISSEMENT : idem pour GAUCHE, HAUT et BAS', () => {
	assert.deepStrictEqual(ctx._resizeNav({ '1,1': 64 }, 6, 6, 3, 3, NAV_DIRS), { '2,2': 64, '2,3': 64 });
	assert.deepStrictEqual(ctx._resizeNav({ '1,1': 1 }, 6, 6, 3, 3, NAV_DIRS), { '2,2': 1, '3,2': 1 });
	assert.deepStrictEqual(ctx._resizeNav({ '1,1': 16 }, 6, 6, 3, 3, NAV_DIRS), { '2,3': 16, '3,3': 16 });
});

t('AGRANDISSEMENT : une diagonale ne survit que sur le coin du bloc', () => {
	// BAS_DROITE (8) sur (1,1) → seul le coin bas-droit du bloc 2×2, soit (3,3).
	assert.deepStrictEqual(ctx._resizeNav({ '1,1': 8 }, 6, 6, 3, 3, NAV_DIRS), { '3,3': 8 });
});

t('un mur en BORD de carte est conservé', () => {
	// Le voisin est hors carte : c'est un vrai mur, il ne doit pas être effacé par la règle.
	assert.deepStrictEqual(ctx._resizeNav({ '0,0': 64 }, 4, 4, 2, 2, NAV_DIRS), { '0,0': 64, '0,1': 64 });
});

t('RÉDUCTION : les murs non échantillonnés disparaissent (perte assumée)', () => {
	const n2 = ctx._resizeNav({ '0,0': 4, '1,0': 4 }, 1, 1, 2, 1, NAV_DIRS);
	assert.deepStrictEqual(n2, { '0,0': 4 }, 'seule la case source échantillonnée survit');
});

console.log('\n── Zones d’influence ──');

t('x/y/w/h suivent l’échelle, rot ne bouge pas, bbox est retiré', () => {
	const out = ctx._resizeZones([{ x: 10, y: 20, w: 8, h: 4, rot: 0, forme: 'ellipse',
		zone: 'zone:foret', bbox: { x_min: 6 } }], 0.5, 0.5);
	assert.deepStrictEqual(out[0], { x: 5, y: 10, w: 4, h: 2, rot: 0, forme: 'ellipse', zone: 'zone:foret' });
});

t('w et h sont planchés à 1 — une zone ne disparaît jamais', () => {
	const out = ctx._resizeZones([{ x: 4, y: 4, w: 2, h: 1, rot: 0 }], 0.1, 0.1);
	assert.strictEqual(out[0].w, 1);
	assert.strictEqual(out[0].h, 1);
});

t('à 90° les axes de la forme sont ÉCHANGÉS', () => {
	const out = ctx._resizeZones([{ x: 0, y: 0, w: 10, h: 4, rot: 90 }], 2, 1);
	assert.strictEqual(out[0].w, 10, 'la largeur d’une forme couchée suit fy');
	assert.strictEqual(out[0].h, 8, 'sa hauteur suit fx');
});

t('la source n’est pas mutée', () => {
	const p = [{ x: 10, y: 20, w: 8, h: 4, rot: 0, bbox: { x_min: 6 } }];
	ctx._resizeZones(p, 0.5, 0.5);
	assert.strictEqual(p[0].x, 10);
	assert.ok(p[0].bbox, 'le bbox de la source a été effacé');
});

t('les zones déformées par une échelle inégale sont nommées', () => {
	const p = [{ rot: 0 }, { rot: 90 }, { rot: 27 }, { rot: 180 }];
	assert.deepStrictEqual(ctx._zonesDeformees(p, 1, 1), [], 'échelle uniforme ⇒ rien à signaler');
	assert.deepStrictEqual(ctx._zonesDeformees(p, 2, 1), [{ rot: 27 }],
		'seuls les angles hors multiples de 90° sont inexprimables');
});

console.log('\n── Portes (pos d’un nœud de connexion) ──');

t('la position suit l’échelle et reste dans la grille', () => {
	assert.deepStrictEqual(ctx._resizePos([20, 10], 0.5, 0.5, 30, 20), [10, 5]);
	assert.deepStrictEqual(ctx._resizePos([85, 47], 0.5, 0.5, 43, 24), [42, 23]);
});

t('une position hors carte est ramenée dans les bornes', () => {
	assert.deepStrictEqual(ctx._resizePos([999, 999], 1, 1, 10, 10), [9, 9]);
	assert.deepStrictEqual(ctx._resizePos([-5, -5], 1, 1, 10, 10), [0, 0]);
});

t('une case déjà praticable n’est pas déplacée', () => {
	assert.deepStrictEqual(ctx._caseLibreProche(3, 3, 10, 10, () => true), [3, 3]);
});

t('la spirale rend la case praticable la PLUS PROCHE', () => {
	// Seule (5,5) est praticable : depuis (3,5), la spirale doit y arriver.
	const ok = (x, y) => (x === 5 && y === 5);
	assert.deepStrictEqual(ctx._caseLibreProche(3, 5, 10, 10, ok), [5, 5]);
	// Deux candidates, l'une à distance 1, l'autre à distance 3 : la plus proche gagne.
	const ok2 = (x, y) => (x === 4 && y === 5) || (x === 8 && y === 5);
	assert.deepStrictEqual(ctx._caseLibreProche(5, 5, 10, 10, ok2), [4, 5]);
});

t('aucune case praticable ⇒ la position bornée est CONSERVÉE, jamais la porte', () => {
	assert.deepStrictEqual(ctx._caseLibreProche(2, 7, 10, 10, () => false), [2, 7]);
});

console.log('\n── Portes : recalage idempotent (_reappliquerPortes) ──');

// Décor : une carte 10×10 entièrement praticable, deux connexions dont une seule touche le lieu
// courant, et un redimensionnement de moitié (20×20 → 10×10) déjà porté par cols/rows.
function _decor() {
	globalThis.currentLocId = 'lieu:ici';
	globalThis.cols = 10;
	globalThis.rows = 10;
	globalThis.grid = Array.from({ length: 10 }, () => Array(10).fill(1));
	globalThis.redimEnAttente = {
		ancien: { x: 20, y: 20 }, connIds: new Set(), origines: new Map(),
	};
	globalThis.lieuxConnections = [
		{ _id: 'link:a', nodes: [{ lieu: 'lieu:ici', pos: [10, 8] }, { lieu: 'lieu:ailleurs', pos: [3, 3] }] },
		{ _id: 'link:b', nodes: [{ lieu: 'lieu:autre', pos: [18, 18] }, { lieu: 'lieu:ailleurs', pos: [1, 1] }] },
	];
}

t('la porte du lieu courant suit l’échelle, celle de l’autre lieu ne bouge PAS', () => {
	_decor();
	assert.strictEqual(_reappliquerPortes(), 1);
	assert.deepStrictEqual(lieuxConnections[0].nodes[0].pos, [5, 4], 'porte du lieu courant');
	assert.deepStrictEqual(lieuxConnections[0].nodes[1].pos, [3, 3],
		'⚠️ la pos du nœud de l’AUTRE lieu est indexée sur SA grille : intouchable');
	assert.deepStrictEqual(lieuxConnections[1].nodes[0].pos, [18, 18], 'connexion étrangère');
	assert.deepStrictEqual([...redimEnAttente.connIds], ['link:a']);
});

t('rejouer le recalage ne dérive pas (idempotence)', () => {
	// ⚠️ LE contrôle de non-régression : `fetchLieuxConnections` rappelle `_reappliquerPortes`
	// après chaque passage par le mode Lieux. Un recalage qui composerait au lieu de repartir de
	// `redimEnAttente.ancien` diviserait la position par deux à chaque fois, en silence.
	_decor();
	_reappliquerPortes();
	const apres1 = [...lieuxConnections[0].nodes[0].pos];
	assert.strictEqual(_reappliquerPortes(), 0, 'plus rien ne doit bouger');
	_reappliquerPortes();
	assert.deepStrictEqual(lieuxConnections[0].nodes[0].pos, apres1);
});

t('un SECOND aperçu repart des origines, il ne compose pas avec le premier', () => {
	// 20×20 → 10×10 puis → 5×5 : la porte [10,8] doit finir en [3,2] (10 et 8 quarts arrondis),
	// et surtout pas en [3,1] (le résultat d'un demi appliqué deux fois).
	_decor();
	_reappliquerPortes();
	globalThis.cols = 5; globalThis.rows = 5;
	globalThis.grid = Array.from({ length: 5 }, () => Array(5).fill(1));
	_reappliquerPortes();
	assert.deepStrictEqual(lieuxConnections[0].nodes[0].pos, [3, 2]);
});

t('une porte qui tombe sur une case bloquée est recalée à côté', () => {
	_decor();
	grid[4][5] = 0;                          // la cible directe devient inaccessible
	_reappliquerPortes();
	const [x, y] = lieuxConnections[0].nodes[0].pos;
	assert.ok(grid[y][x] >= 1, `porte posée sur un terrain ${grid[y][x]}`);
	assert.strictEqual(Math.max(Math.abs(x - 5), Math.abs(y - 4)), 1, 'et sur une case VOISINE');
});

t('une grille plus COURTE que dimensions ne fait pas lever _caseAccessible', () => {
	// Le doc à réparer : `dimensions` annonce plus de lignes que `cells` n'en porte. La ligne
	// manquante doit être refusée, pas lever — sinon le rendu casse et l'éditeur devient
	// inatteignable sur le document même qui a besoin d'être redimensionné.
	_decor();
	globalThis.rows = 20;                    // la grille, elle, n'a que 10 lignes
	assert.strictEqual(_caseAccessible(3, 15), false);
	assert.strictEqual(_caseAccessible(3, 3), true);
});

t('sans redimensionnement en cours, aucune porte n’est touchée', () => {
	_decor();
	globalThis.redimEnAttente = null;
	assert.strictEqual(_reappliquerPortes(), 0);
	assert.deepStrictEqual(lieuxConnections[0].nodes[0].pos, [10, 8]);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
