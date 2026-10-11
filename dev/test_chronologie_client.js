// dev/test_chronologie_client.js
//
// Tests d'EXÉCUTION du JavaScript de la frise du lore (templates/admin_lore_chronologie.html).
//
//   node dev/test_chronologie_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le serveur (utils/chronologie.py, tests/test_chronologie.py) réduit chaque date à
// un temps normalisé `t` ; tout le reste vit dans le template et aucun test pytest ne l'atteint :
//   1. la projection t → pixels doit rester CONTINUE et MONOTONE d'une ère à l'autre — sinon
//      un événement saute d'un bord à l'autre, ou deux époques se chevauchent à l'écran ;
//   2. l'empilement en couloirs ne doit jamais superposer deux éléments ;
//   3. les filtres (ET entre facettes, OU dans une facette), le regroupement, la
//      contemporanéité et l'export JSON doivent dire la même chose que la source ;
//   4. clic / appui long / glissement : une machine à états qui se trompe ouvre le JSON au
//      lieu de sélectionner, ou sélectionne en faisant défiler.
//
// MÉTHODE : identique aux autres harnais — extraction par nom (accolades équilibrées) et
// exécution dans le realm du test (`runInThisContext`) ; les constantes (`GEO`, délais,
// facettes) sont EXTRAITES, jamais recopiées.
//
// HORS DE PORTÉE (à vérifier à l'écran, CLAUDE.md §15) : le rendu SVG, l'axe collant, la
// mini-carte, l'overlay JSON, le panneau de détail, l'orientation réelle de l'écran.

const path = require('path');
const assert = require('assert');
const vm = require('vm');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_lore_chronologie.html');
const js = scriptsInline(lireAvecIncludes(TEMPLATE));
assert.ok(js, 'aucun bloc <script> dans ' + TEMPLATE);

function extraire(nom) {
	const debut = js.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable');
	let prof = 0;
	for (let j = js.indexOf('{', debut); j < js.length; j++) {
		if (js[j] === '{') prof++;
		else if (js[j] === '}' && --prof === 0) return js.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

// `const NOM = …;` sur une ligne, ou un littéral objet/tableau sur plusieurs (accolades équilibrées).
function extraireConst(nom) {
	const debut = js.search(new RegExp('\\bconst ' + nom + ' = '));
	assert.ok(debut >= 0, 'constante ' + nom + ' introuvable');
	const ouvre = js.indexOf('=', debut) + 1;
	const premier = js.slice(ouvre).trimStart()[0];
	if (premier !== '{' && premier !== '[') return js.slice(debut, js.indexOf(';', debut) + 1);
	const o = js.indexOf(premier, ouvre), f = premier === '{' ? '}' : ']';
	let prof = 0;
	for (let j = o; j < js.length; j++) {
		if (js[j] === premier) prof++;
		else if (js[j] === f && --prof === 0) return js.slice(debut, j + 1) + ';';
	}
	throw new Error('littéral déséquilibré : ' + nom);
}

const CONSTS = ['CHRONO_DELAI_LONG', 'CHRONO_GLISSE', 'FACETTES_LISTES', 'GEO'];
const FONCTIONS = ['chronoEchelle', 'chronoPx', 'chronoGeometrie', 'chronoEtendue', 'chronoCouloirs', '_sansAccent',
	'chronoFiltrer', 'chronoGrouper', 'chronoContemporains', 'chronoSousEnsemble', 'chronoAppuiLong', 'chronoXY', 'chronoPas'];
// `var` plutôt que `const` : les déclarations restent visibles de ce realm après runInThisContext.
vm.runInThisContext(CONSTS.map(n => extraireConst(n).replace(/^const /, 'var ')).join('\n') + '\n'
	+ FONCTIONS.map(extraire).join('\n') + '\n'
	+ 'globalThis.F = {' + FONCTIONS.join(',') + '};');
const C = { CHRONO_DELAI_LONG, CHRONO_GLISSE, GEO };

let echecs = 0, n = 0;
function t(nom, fn) {
	n++;
	try { fn(); console.log('  ok  ' + nom); }
	catch (e) { echecs++; console.log('  ÉCHEC ' + nom + '\n       ' + (e && e.stack || e)); }
}

// ── Données de test (pas de dépendance au contenu réel) ─────────────────────────
const ERES = [
	{ id: 'anc', type: 'ordinal', px_rang: 100, rangs: [{ id: 'r0' }, { id: 'r1' }] },
	{ id: 'p1', type: 'passe', debut: 3000, fin: 750, px_siecle: 30 },
	{ id: 'p2', type: 'passe', debut: 750, fin: 0, px_siecle: 100 },
	{ id: 'jeu', type: 'ordinal', px_rang: 90, rangs: [{ id: 'D' }, { id: 'C' }, { id: 'B' }] },
	{ id: 'fut', type: 'futur', debut: 0, fin: 200, px_siecle: 40 }
];
const borne = (t0, t1, genre) => ({ t: [t0, t1 == null ? t0 : t1], genre: genre || 'exact' });
const point = (id, b, extra) => Object.assign({ id: id, titre: id, titre_court: id, resume: '', notation: '', eres: [], tags: {},
	calc: { forme: 'point', debut: b, fin: b, jalons: [] }, brut: { id: id, ordre: 1 } }, extra || {});
const periode = (id, d, f, extra) => Object.assign(point(id, d, extra), { calc: { forme: 'periode', debut: d, fin: f, jalons: [] } });

// ── Échelle ─────────────────────────────────────────────────────────────────
t('échelle : segments contigus, longueurs selon le type d\'ère', () => {
	const e = F.chronoEchelle(ERES, 1);
	e.segments.forEach((s, i) => { if (i) assert.strictEqual(s.debut, e.segments[i - 1].debut + e.segments[i - 1].longueur); });
	assert.strictEqual(e.segments[0].longueur, 200);                 // 2 rangs × 100
	assert.strictEqual(e.segments[1].longueur, Math.round(2250 / 100 * 30));
	assert.strictEqual(e.segments[2].longueur, 750);
	assert.strictEqual(e.total, e.segments.reduce((a, s) => a + s.longueur, 0));
});

t('échelle : le zoom multiplie les longueurs (plancher compris)', () => {
	const a = F.chronoEchelle(ERES, 1), b = F.chronoEchelle(ERES, 2);
	a.segments.forEach((s, i) => assert.strictEqual(b.segments[i].longueur, Math.max(80, Math.round(s.longueur * 2))));
	assert.ok(F.chronoEchelle(ERES, 0.01).segments.every(s => s.longueur === 80));
});

t('t → px : continu aux frontières, monotone, borné', () => {
	const e = F.chronoEchelle(ERES, 1);
	for (let i = 1; i < ERES.length; i++) {
		assert.strictEqual(F.chronoPx(i, e), e.segments[i].debut);
		assert.ok(Math.abs(F.chronoPx(i - 1e-9, e) - e.segments[i].debut) < 1e-3, 'saut à la frontière ' + i);
	}
	let avant = -1;
	for (let k = 0; k <= 500; k++) {
		const p = F.chronoPx(k / 100, e);
		assert.ok(p >= avant, 'non monotone en t=' + k / 100);
		avant = p;
	}
	assert.strictEqual(F.chronoPx(-3, e), 0);
	assert.strictEqual(F.chronoPx(99, e), e.total);
});

t('pas des graduations : ≥ 70 px entre deux', () => {
	for (const pxParAn of [0.05, 0.3, 1, 1.1, 3]) assert.ok(F.chronoPas(pxParAn) * pxParAn >= 70 || F.chronoPas(pxParAn) === 5000);
	assert.strictEqual(F.chronoPas(1.1), 100);
	assert.strictEqual(F.chronoPas(3), 25);
});

// ── Géométrie ───────────────────────────────────────────────────────────────
t('géométrie : instant exact, instant incertain ⟨ ⟩, période à bornes floues et ouverte', () => {
	const e = F.chronoEchelle(ERES, 1), px = x => F.chronoPx(x, e);
	const exact = F.chronoGeometrie(point('a', borne(2.5)), e);
	assert.strictEqual(exact.marque, px(2.5));
	assert.deepStrictEqual(exact.flous, []);
	const flou = F.chronoGeometrie(point('b', borne(1.2, 1.4, 'incertain')), e);
	assert.deepStrictEqual(flou.flous, [[px(1.2), px(1.4)]]);
	assert.strictEqual(flou.marque, (px(1.2) + px(1.4)) / 2);
	const per = F.chronoGeometrie(periode('c', borne(1.1, 1.3, 'incertain'), borne(3, 3, 'ouvert')), e);
	assert.deepStrictEqual(per.solide, [px(1.3), px(3)]);
	assert.deepStrictEqual(per.flous, [[px(1.1), px(1.3)]]);
	assert.ok(per.fleche);
	assert.strictEqual(per.a0, px(1.1));
	const rang = F.chronoGeometrie(periode('d', borne(0.5, 1, 'rang'), borne(3, 3, 'ouvert')), e);
	assert.strictEqual(rang.solide[0], (px(0.5) + px(1)) / 2, 'un rang se dessine en son milieu');
});

t('géométrie : jalons placés au milieu de leur intervalle', () => {
	const e = F.chronoEchelle(ERES, 1);
	const ev = periode('c', borne(1.1), borne(3, 3, 'ouvert'));
	ev.calc.jalons = [{ libelle: 'avènement', notation: 'x', genre: 'incertain', t: [2.1, 2.3] }];
	const g = F.chronoGeometrie(ev, e);
	assert.strictEqual(g.jalons[0].p, (F.chronoPx(2.1, e) + F.chronoPx(2.3, e)) / 2);
});

t('étendue : le libellé est réservé dans le couloir (h), une hauteur de ligne (v)', () => {
	const e = F.chronoEchelle(ERES, 1);
	const g = F.chronoGeometrie(point('a', borne(2.5)), e);
	const [h0, h1] = F.chronoEtendue(g, 'x'.repeat(20), 'h');
	assert.ok(h1 >= g.marque + 9 + 20 * C.GEO.h.car);
	const [v0, v1] = F.chronoEtendue(g, 'x'.repeat(20), 'v');
	assert.ok(v0 <= g.marque - 12 && v1 >= g.marque + 14 && v1 - v0 < 60);
	assert.ok(h0 <= g.a0);
});

// ── Couloirs ────────────────────────────────────────────────────────────────
t('couloirs : jamais deux éléments qui se chevauchent dans le même couloir', () => {
	const items = [];
	for (let k = 0; k < 60; k++) items.push({ a0: (k * 37) % 400, a1: (k * 37) % 400 + 20 + (k * 13) % 90 });
	const r = F.chronoCouloirs(items, 6);
	for (let i = 0; i < items.length; i++)
		for (let j = i + 1; j < items.length; j++)
			if (r.couloir[i] === r.couloir[j])
				assert.ok(items[i].a1 + 6 <= items[j].a0 || items[j].a1 + 6 <= items[i].a0, `chevauchement ${i}/${j}`);
	assert.strictEqual(r.n, Math.max(...r.couloir) + 1);
});

t('couloirs : éléments disjoints → un seul couloir', () => {
	const r = F.chronoCouloirs([{ a0: 100, a1: 150 }, { a0: 0, a1: 50 }, { a0: 200, a1: 260 }], 6);
	assert.deepStrictEqual(r, { couloir: [0, 0, 0], n: 1 });
});

// ── Filtres, groupes ────────────────────────────────────────────────────────
const FACETTES = {
	couche: [{ id: 'histoire', libelle: 'Histoire' }, { id: 'trame', libelle: 'Trame' }],
	lieux: [{ id: 'rome', libelle: 'Rome' }, { id: 'lutecia', libelle: 'Lutécia' }],
	peuples: [{ id: 'elfes', libelle: 'Elfes' }]
};
const EVS = [
	point('a', borne(1.5), { couche: 'histoire', autorite: 'auteur', eres: ['p1'], tags: { lieux: ['rome'] }, titre: 'Fondation', resume: 'Les élèves' }),
	point('b', borne(2.5), { couche: 'histoire', autorite: 'proposition', eres: ['p2'], tags: { lieux: ['lutecia'], peuples: ['elfes'] } }),
	point('c', borne(3.5), { couche: 'trame', autorite: 'auteur', eres: ['jeu'], tags: {}, contradictions: [{ texte: '?' }] })
];
const ids = s => [...s].sort();

t('filtres : OU dans une facette, ET entre facettes, facette vide neutre', () => {
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { choix: {} }, FACETTES)), ['a', 'b', 'c']);
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { choix: { lieux: new Set(['rome', 'lutecia']) } }, FACETTES)), ['a', 'b']);
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { choix: { lieux: new Set(['rome', 'lutecia']), autorite: new Set(['auteur']) } }, FACETTES)), ['a']);
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { choix: { ere: new Set(['jeu']), couche: new Set() } }, FACETTES)), ['c']);
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { choix: {}, incoherence: true }, FACETTES)), ['c']);
});

t('filtres : recherche sans accents, sur les libellés de tags aussi', () => {
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { texte: 'ELEVES', choix: {} }, FACETTES)), ['a']);
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { texte: 'lutecia elfes', choix: {} }, FACETTES)), ['b']);
	assert.deepStrictEqual(ids(F.chronoFiltrer(EVS, { texte: 'introuvable', choix: {} }, FACETTES)), []);
});

t('grouper : une valeur par couloir, multi-valeurs dupliquées, (sans) en dernier, ordre du vocabulaire', () => {
	const g = F.chronoGrouper(EVS, 'lieux', FACETTES);
	assert.deepStrictEqual(g.map(x => x.cle), ['rome', 'lutecia', '∅']);
	assert.deepStrictEqual(g[2].evenements.map(e => e.id), ['c']);
	const multi = F.chronoGrouper([point('m', borne(1), { tags: { lieux: ['lutecia', 'rome'] } })], 'lieux', FACETTES);
	assert.deepStrictEqual(multi.map(x => x.cle), ['rome', 'lutecia']);
	assert.deepStrictEqual(F.chronoGrouper(EVS, '', FACETTES).map(x => x.evenements.length), [3]);
	assert.deepStrictEqual(F.chronoGrouper(EVS, 'couche', FACETTES).map(x => x.cle), ['histoire', 'trame']);
});

// ── Contemporanéité ─────────────────────────────────────────────────────────
t('contemporains : chevauchement des intervalles POSSIBLES, durables à part', () => {
	const evs = [
		point('x', borne(1.4, 1.6, 'incertain')),
		point('touche', borne(1.6)),                                   // borne commune : coïncide
		point('loin', borne(1.7)),
		periode('ville', borne(1.0), borne(3, 3, 'ouvert')),
		periode('finie', borne(1.0), borne(1.45))
	];
	const r = F.chronoContemporains(evs[0], evs);
	assert.deepStrictEqual(r.ponctuels.sort(), ['finie', 'touche']);
	assert.deepStrictEqual(r.durables, ['ville']);
});

// ── Export ──────────────────────────────────────────────────────────────────
t('sous-ensemble : format de la source, bruts dans l\'ordre de la source, filtrés', () => {
	const entete = { version: 1, eres: ERES, vocabulaire: {} };
	const s = F.chronoSousEnsemble(entete, EVS, ['c', 'a']);
	assert.deepStrictEqual(Object.keys(s), ['version', 'eres', 'vocabulaire', 'evenements']);
	assert.deepStrictEqual(s.evenements.map(e => e.id), ['a', 'c']);
	assert.strictEqual(s.evenements[0], EVS[0].brut, 'le brut part tel quel, pas l\'événement enrichi');
	assert.ok(!('evenements' in entete), 'l\'en-tête n\'est pas modifié');
});

// ── Pointeur ────────────────────────────────────────────────────────────────
const suite = evts => {
	let e = { phase: 'repos' };
	const actions = [];
	for (const ev of evts) { const r = F.chronoAppuiLong(e, ev); e = r.etat; if (r.action) actions.push(r.action); }
	return { etat: e, actions: actions };
};
const D = C.CHRONO_DELAI_LONG;

t('pointeur : appui bref = clic', () => {
	const r = suite([{ type: 'down', t: 0, x: 0, y: 0, id: 'a' }, { type: 'up', t: D - 1 }]);
	assert.deepStrictEqual(r.actions, [{ type: 'clic', id: 'a' }]);
	assert.strictEqual(r.etat.phase, 'repos');
});

t('pointeur : appui long = JSON une seule fois, le relâcher ne clique pas', () => {
	const r = suite([{ type: 'down', t: 0, x: 0, y: 0, id: 'a' }, { type: 'tick', t: D }, { type: 'up', t: D + 300 }]);
	assert.deepStrictEqual(r.actions, [{ type: 'long', id: 'a' }]);
});

t('pointeur : minuterie manquée, l\'appui long est reconnu au relâcher', () => {
	const r = suite([{ type: 'down', t: 0, x: 0, y: 0, id: 'a' }, { type: 'up', t: D + 10 }]);
	assert.deepStrictEqual(r.actions, [{ type: 'long', id: 'a' }]);
});

t('pointeur : un glissement (défilement) annule clic et appui long', () => {
	const r = suite([{ type: 'down', t: 0, x: 0, y: 0, id: 'a' }, { type: 'move', x: C.CHRONO_GLISSE + 1, y: 0 },
		{ type: 'tick', t: D }, { type: 'up', t: D + 10 }]);
	assert.deepStrictEqual(r.actions, []);
	const petit = suite([{ type: 'down', t: 0, x: 0, y: 0, id: 'a' }, { type: 'move', x: 3, y: 3 }, { type: 'up', t: 50 }]);
	assert.deepStrictEqual(petit.actions, [{ type: 'clic', id: 'a' }], 'un tremblement n\'est pas un glissement');
});

t('pointeur : annulation et relâcher orphelin sans effet', () => {
	assert.deepStrictEqual(suite([{ type: 'down', t: 0, x: 0, y: 0, id: 'a' }, { type: 'cancel' }, { type: 'up', t: 10 }]).actions, []);
	assert.deepStrictEqual(suite([{ type: 'up', t: 10 }]).actions, []);
});

// ── Orientation ─────────────────────────────────────────────────────────────
t('orientation : la portrait transpose la paysage (axe ↔ travers)', () => {
	const [hx, hy] = F.chronoXY('h', 120, 40);
	assert.deepStrictEqual([hx, hy], [C.GEO.h.axe + 120, C.GEO.h.bande + 40]);
	const [vx, vy] = F.chronoXY('v', 120, 40);
	assert.deepStrictEqual([vx, vy], [C.GEO.v.bande + 40, C.GEO.v.axe + 120]);
});

console.log(`\n${n - echecs} / ${n} tests passés`);
process.exit(echecs ? 1 : 0);
