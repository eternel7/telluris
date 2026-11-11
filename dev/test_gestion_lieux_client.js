// dev/test_gestion_lieux_client.js
//
// Tests d'EXÉCUTION de la gestion des lieux (templates/admin_lieux.html) et du CONTRAT du mode
// Lieux PARTAGÉ avec l'éditeur de carte (templates/part-lieux-*.html).
//
//   node dev/test_gestion_lieux_client.js     # sort en code 1 au premier échec
//
// POURQUOI :
//   1. La part partagée ne doit lire AUCUNE globale propre à une page : tout passe par
//      `LIEUX_HOTE`. Une lecture directe oubliée (`currentLocId`, `renderGrid`…) marcherait dans
//      l'éditeur et lèverait une ReferenceError sur /admin/lieux — au clic, pas au chargement.
//   2. Les deux pages doivent déclarer TOUTES les clés du contrat.
//   3. Les « lignes affichées » qu'un outil reçoit, et les cases que 📍 propose, sont calculées
//      côté client : un filtre mal lu enverrait des boutiques que l'admin ne voit pas.
//
// MÉTHODE : extraction par nom (dev/_template_js.js développe les includes) et exécution dans le
// realm du test (`runInThisContext`), comme dev/test_lot_lieux_client.js.
//
// HORS DE PORTÉE (CLAUDE.md §15, à vérifier dans le navigateur) : le rendu du tableau, les
// overlays, la scrutation du journal et l'aller-retour réseau des outils.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');

const TEMPLATES = path.join(__dirname, '..', 'templates');
const PAGE = path.join(TEMPLATES, 'admin_lieux.html');
const EDITEUR = path.join(TEMPLATES, 'admin_map_editor.html');
const PART_JS = path.join(TEMPLATES, 'part-lieux-js.html');

const js = scriptsInline(lireAvecIncludes(PAGE));
assert.ok(js, 'aucun bloc <script> trouvé dans ' + PAGE);

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

function extraireDeclaration(re, nom) {
	const m = re.exec(js);
	assert.ok(m, nom + ' introuvable dans le template');
	return m[0];
}

vm.runInThisContext(extraireDeclaration(/const LIEUX_PNJ_ETATS = \[[\s\S]*?\];/, 'LIEUX_PNJ_ETATS'));
vm.runInThisContext(extraireDeclaration(/const LIEUX_PNJ_COULEURS = [^\n]+/, 'LIEUX_PNJ_COULEURS'));
vm.runInThisContext(extraireDeclaration(/const LIEUX_PNJ_RANG = [^\n]+/, 'LIEUX_PNJ_RANG'));
vm.runInThisContext(extraireDeclaration(/const PORTE_CATEGORIE = [^;]+;/, 'PORTE_CATEGORIE'));
vm.runInThisContext(extraireDeclaration(/const GUILDE_EXTERIEUR_CATEGORIE = [^;]+;/, 'GUILDE_EXTERIEUR_CATEGORIE'));
vm.runInThisContext(extraireDeclaration(/const COLS_LIEN = [^;]+;/, 'COLS_LIEN'));
vm.runInThisContext(extraireDeclaration(/const LIEUX_HOTE_REQUIS = \[[\s\S]*?\];/, 'LIEUX_HOTE_REQUIS'));
vm.runInThisContext(extraireDeclaration(/const REGION_TAILLE_MIN = [^;]+;/, 'REGION_TAILLE_MIN'));
for (const f of ['_escHtml', '_connDest', '_connInterne', '_noeudsRepositionnables', 'etatPnjDeLieu', 'lieuxLigneHtml', '_ljConnexion',
				 'valeurLigne', 'colonnesDe', 'lieuxMarchandsVisibles', 'portesDeVille',
				 '_posValide', '_regionCible', '_proposerCases']) {
	vm.runInThisContext(extraire(f));
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const VILLE = 'lieu:lutecia';
function conn(id, posIci, dest, details, meta, ordreInverse) {
	const ici = { lieu: VILLE, pos: posIci };
	const la = { lieu: dest, pos: [0, 0], details };
	return { _id: id, type: 'connection', nodes: ordreInverse ? [la, ici] : [ici, la],
		metadata: meta || { type: (details && details.categorie) || '', status: 'ouvert' } };
}
const AUBERGE = conn('link:auberge01_to_lutecia', [8, 11], 'lieu:auberge_de_la_cite',
	{ label: 'Auberge de la Cité', categorie: 'auberge', image: 'auberge_europe01.png' });
const BOUCHERIE = conn('link:boucherie01_to_lutecia', [12, 20], 'lieu:la_hampe',
	{ label: 'La Hampe', categorie: 'boucherie', pnj: [{ character: 'pnj:marchand_boucherie', nom: 'Nicolas' }] },
	null, true);
const TEMPLE = conn('link:temple_to_lutecia', [30, 9], 'lieu:notre_dame',
	{ label: 'Notre-Dame', categorie: 'temple_portail', pnj: [{ character: 'pnj:dame_eleonore' }, { character: 'pnj:marchand_x' }] });
const PORTE = conn('link:porte_nord', [49, 6], 'lieu:porte_nord_interieur',
	{ label: "Porte <nord> l'intérieur", categorie: 'Porte de rempart' });
const GUILDE = conn('link:guilde_aventurier_exterieur01_to_lutecia', [34, 20], 'lieu:le_grand_relais_des_frontieres_exterieur',
	{ label: 'Le Grand Relais des Frontières', categorie: 'guilde_aventurier_exterieur' });

console.log('\n── 🎯 Repositionner : nœuds déplaçables ──');

t('un 🎯 par nœud posé sur la carte courante, quel que soit le type de connexion', () => {
	// Vers un autre lieu : le seul nœud de la ville, où qu'il soit dans le doc.
	assert.deepStrictEqual(_noeudsRepositionnables(AUBERGE, VILLE), [0]);
	assert.deepStrictEqual(_noeudsRepositionnables(BOUCHERIE, VILLE), [1]);
	assert.deepStrictEqual(_noeudsRepositionnables(PORTE, VILLE), [0]);
	// Interne : les deux bouts.
	const interne = { _id: 'link:x', nodes: [{ lieu: VILLE, pos: [1, 2] }, { lieu: VILLE, pos: [3, 4] }] };
	assert.deepStrictEqual(_noeudsRepositionnables(interne, VILLE), [0, 1]);
	// Maillon sans nœud sur la carte, doc abîmé : rien.
	assert.deepStrictEqual(_noeudsRepositionnables(AUBERGE, 'lieu:ailleurs_hors_reseau'), []);
	assert.deepStrictEqual(_noeudsRepositionnables({ nodes: [null, {}] }, VILLE), []);
	assert.deepStrictEqual(_noeudsRepositionnables(null, VILLE), []);
});

console.log('\n── Valeurs de colonne ──');

t('les colonnes de la connexion viennent de la connexion, les autres du lieu', () => {
	assert.strictEqual(valeurLigne(AUBERGE, 'lieu', VILLE), 'lieu:auberge_de_la_cite');
	assert.strictEqual(valeurLigne(AUBERGE, 'connexion', VILLE), 'link:auberge01_to_lutecia');
	assert.strictEqual(valeurLigne(AUBERGE, 'lien_type', VILLE), 'auberge');
	assert.strictEqual(valeurLigne(AUBERGE, 'lien_status', VILLE), 'ouvert');
	assert.deepStrictEqual(valeurLigne(AUBERGE, 'pos_ici', VILLE), [8, 11]);
	assert.deepStrictEqual(valeurLigne(AUBERGE, 'pos_la', VILLE), [0, 0]);
	assert.strictEqual(valeurLigne(AUBERGE, 'image', VILLE), 'auberge_europe01.png');
	assert.strictEqual(valeurLigne(AUBERGE, 'absente', VILLE), undefined);
});

t("l'ordre des nœuds ne change rien : la ville est « ici », l'autre « là-bas »", () => {
	assert.strictEqual(valeurLigne(BOUCHERIE, 'lieu', VILLE), 'lieu:la_hampe');
	assert.deepStrictEqual(valeurLigne(BOUCHERIE, 'pos_ici', VILLE), [12, 20]);
});

t('colonnes : celles de la connexion en tête, puis les clés des lieux triées', () => {
	const cols = colonnesDe([AUBERGE, BOUCHERIE], VILLE);
	assert.deepStrictEqual(cols.slice(0, COLS_LIEN.length), COLS_LIEN);
	assert.deepStrictEqual(cols.slice(COLS_LIEN.length), ['categorie', 'image', 'label', 'pnj']);
});

console.log('\n── Lignes affichées envoyées aux outils ──');

t('seules les boutiques à tenancier EXPLICITE en 1re entrée, sans doublon', () => {
	const doublon = conn('link:boucherie02_to_lutecia', [13, 20], 'lieu:la_hampe', BOUCHERIE.nodes[0].details);
	assert.deepStrictEqual(lieuxMarchandsVisibles([AUBERGE, BOUCHERIE, TEMPLE, PORTE, doublon], VILLE), ['lieu:la_hampe']);
	assert.deepStrictEqual(lieuxMarchandsVisibles([], VILLE), []);
});

t('portes de la ville : case d\'ici et catégorie du lieu', () => {
	assert.deepStrictEqual(portesDeVille([AUBERGE, BOUCHERIE], VILLE), [
		{ pos: [8, 11], categorie: 'auberge' }, { pos: [12, 20], categorie: 'boucherie' }]);
});

console.log('\n── 📍 Cases proposées ──');

// Grille 8×4 : région 0 partout sauf un mur (-1) en colonne 4 et une enclave (rang 1) en [7,0].
const W = 8, H = 4;
const REGION = new Int32Array(W * H).fill(0);
for (let y = 0; y < H; y++) REGION[y * W + 4] = -1;
REGION[0 * W + 7] = 1;
const dansRegion0 = ([x, y]) => REGION[y * W + x] === 0;

t('jamais hors de la région principale', () => {
	const cases = _proposerCases(REGION, W, [], [], 20, 2);
	assert.ok(cases.length > 0);
	assert.ok(cases.every(dansRegion0), JSON.stringify(cases));
	assert.ok(!cases.some(([x, y]) => x === 7 && y === 0), "l'enclave n'est pas proposée");
});

t('près d\'une boutique quand il y en a une (rayon), sinon repli sur toute la région', () => {
	const [c] = _proposerCases(REGION, W, [[1, 1]], [], 1, 1);
	assert.ok(Math.max(Math.abs(c[0] - 1), Math.abs(c[1] - 1)) <= 1, JSON.stringify(c));
	const [loin] = _proposerCases(REGION, W, [[4, 0]], [], 1, 0);   // l'ancre est sur le mur
	assert.ok(dansRegion0(loin));
});

t('jamais sur une porte du même métier ; la plus loin possible d\'elle', () => {
	const cases = _proposerCases(REGION, W, [], [[0, 0]], 1, 2);
	assert.notDeepStrictEqual(cases[0], [0, 0]);
	// La plus éloignée de [0,0] dans la région 0 : distance de Chebyshev 7 (colonnes 5-7).
	assert.strictEqual(Math.max(Math.abs(cases[0][0]), Math.abs(cases[0][1])), 7);
});

t('plusieurs cases : elles s\'écartent l\'une de l\'autre, et le tirage est déterministe', () => {
	const a = _proposerCases(REGION, W, [], [], 3, 2);
	const b = _proposerCases(REGION, W, [], [], 3, 2);
	assert.deepStrictEqual(a, b);
	assert.strictEqual(new Set(a.map(c => c.join(','))).size, 3);
	const d = (p, q) => Math.max(Math.abs(p[0] - q[0]), Math.abs(p[1] - q[1]));
	assert.ok(d(a[0], a[1]) >= 3, JSON.stringify(a));
});

t('épuisement : rend moins de cases plutôt qu\'un doublon', () => {
	const petite = new Int32Array(2).fill(0);
	assert.strictEqual(_proposerCases(petite, 2, [], [], 5, 2).length, 2);
});

t('`cible` : seules les cases de la région visée sont proposées', () => {
	const cases = _proposerCases(REGION, W, [], [], 5, 2, 1);
	assert.deepStrictEqual(cases, [[7, 0]]);
});

console.log('\n── 📍 Région de la ville (_regionCible) ──');

// Grille 20×12 bâtie par rectangles de rangs : la CAMPAGNE (rang 0, la plus grande) encadre tout.
function grilleRegions(W2, H2, blocs) {
	const g = new Int32Array(W2 * H2).fill(0);
	for (const [r, x0, y0, x1, y1] of blocs) {
		for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) g[y * W2 + x] = r;
	}
	return g;
}
const GW = 20, GH = 12;

t('sans boutique : la ville au CENTRE, pas la campagne plus grande (cas Rhemi, Chartres, Auxerre, Orléans)', () => {
	const g = grilleRegions(GW, GH, [[-1, 5, 3, 14, 8], [1, 6, 4, 13, 7]]);   // mur, puis ville 8×4 = 32 cases
	assert.deepStrictEqual(_regionCible(g, GW, GH, [], null, 20), { rang: 1, raison: 'centre' });
});

t('une poche sous le plancher au centre est ignorée (cas Tokyo)', () => {
	const g = grilleRegions(GW, GH, [[-1, 3, 2, 16, 9], [1, 4, 3, 8, 8], [2, 9, 5, 10, 6]]);  // ville 30 cases, poche 4 au centre
	assert.strictEqual(_regionCible(g, GW, GH, [], null, 20).rang, 1);
	assert.strictEqual(_regionCible(g, GW, GH, [], null, 0).rang, 2, 'sans plancher, la poche gagnerait');
});

t('ville déjà peuplée : la région qui porte le plus de portes, même excentrée (cas Douvres)', () => {
	const g = grilleRegions(GW, GH, [[-1, 6, 3, 13, 8], [1, 7, 4, 12, 7], [2, 0, 0, 3, 3]]);
	const ancres = [[0, 0], [1, 1], [2, 2], [8, 5]];
	assert.deepStrictEqual(_regionCible(g, GW, GH, ancres, null, 0), { rang: 2, raison: 'portes' });
});

t('`zone` de la spec prime sur tout ; hors région ou illisible, elle est ignorée', () => {
	const g = grilleRegions(GW, GH, [[-1, 6, 3, 13, 8], [1, 7, 4, 12, 7]]);
	assert.deepStrictEqual(_regionCible(g, GW, GH, [[8, 5]], [0, 0], 0), { rang: 0, raison: 'zone' });
	for (const z of [[6, 3], [99, 0], [1.5, 2], 'x', null]) {
		assert.strictEqual(_regionCible(g, GW, GH, [[8, 5]], z, 0).raison, 'portes', JSON.stringify(z));
	}
});

t('égalité de portes : la plus grande région ; aucune case praticable : rang -1', () => {
	const g = grilleRegions(GW, GH, [[1, 0, 0, 1, 1]]);
	assert.strictEqual(_regionCible(g, GW, GH, [[0, 0], [10, 10]], null, 0).rang, 0);
	const vide = new Int32Array(GW * GH).fill(-1);
	assert.strictEqual(_regionCible(vide, GW, GH, [], null, 0).rang, -1);
	assert.deepStrictEqual(_proposerCases(vide, GW, [], [], 3, 2, -1), []);
});

t('REGION_TAILLE_MIN : au-dessus des poches mesurées, sous la plus petite cité intra-muros', () => {
	// Mesures du dump du 11/11 citées au commentaire du template : poche de Tokyo 10, Camelot 109.
	assert.ok(REGION_TAILLE_MIN > 10 && REGION_TAILLE_MIN < 109, String(REGION_TAILLE_MIN));
});

t('_posValide : deux entiers positifs', () => {
	assert.ok(_posValide([0, 3]));
	for (const p of [null, [1], [1, -1], [1.5, 2], ['1', 2], [1, 2, 3]]) assert.ok(!_posValide(p), JSON.stringify(p));
});

console.log('\n── Ligne partagée ──');

t('sans `link` : pas de ligne « 🔗 link:… », mais les quatre gestes', () => {
	const html = lieuxLigneHtml(AUBERGE, VILLE, { link: false, porte: false });
	assert.ok(!html.includes('🔗 link:auberge01_to_lutecia'));
	for (const g of ['📄 Fiche', '✏️ Lieu', '🔗 Connexion', '🧾 JSON']) assert.ok(html.includes(g), g);
	assert.ok(lieuxLigneHtml(AUBERGE, VILLE, { link: true }).includes('🔗 link:auberge01_to_lutecia'));
});

t('le label est échappé ; 🏰 Porte seulement si demandé ; ✕ Fermer quand ouvert', () => {
	const html = lieuxLigneHtml(PORTE, VILLE, { porte: false, ouvert: true });
	assert.ok(html.includes('Porte &lt;nord&gt;') && !html.includes('<nord>'));
	assert.ok(!html.includes('🏰 Porte') && html.includes('✕ Fermer'));
	assert.ok(lieuxLigneHtml(PORTE, VILLE, { porte: true }).includes('🏰 Porte'));
	assert.ok(!lieuxLigneHtml(AUBERGE, VILLE, { porte: true }).includes('🏰 Porte'));
});

t('🧾 JSON : connexion résolue dans la liste du lieu, ou dans la liste COMPLÈTE hors liste', () => {
	const maillon = { _id: 'link:reception_to_facade', nodes: [{ lieu: 'lieu:r' }, { lieu: 'lieu:f' }] };
	assert.strictEqual(_ljConnexion(AUBERGE._id, false, [AUBERGE], []), AUBERGE);
	// Un maillon de guilde n'a aucun nœud sur la carte : la liste du lieu ne le voit pas.
	assert.strictEqual(_ljConnexion(maillon._id, false, [AUBERGE], [maillon]), null);
	assert.strictEqual(_ljConnexion(maillon._id, true, [AUBERGE], [maillon]), maillon);
	// Hors liste, la liste du lieu n'est PAS consultée : sa copie enrichie n'est pas celle qu'on édite.
	assert.strictEqual(_ljConnexion(AUBERGE._id, true, [AUBERGE], []), null);
	assert.strictEqual(_ljConnexion(null, true, [AUBERGE], [maillon]), null);
});

t('🏛️ Guilde seulement si demandé, et seulement sur une façade de guilde', () => {
	assert.ok(lieuxLigneHtml(GUILDE, VILLE, { guilde: true }).includes('🏛️ Guilde'));
	assert.ok(!lieuxLigneHtml(GUILDE, VILLE, { guilde: false }).includes('🏛️ Guilde'));
	assert.ok(!lieuxLigneHtml(AUBERGE, VILLE, { guilde: true }).includes('🏛️ Guilde'));
	assert.ok(!lieuxLigneHtml(PORTE, VILLE, { guilde: true, porte: true }).includes('🏛️ Guilde'));
});

console.log('\n── Contrat LIEUX_HOTE ──');

function blocHote(fichier) {
	const src = fs.readFileSync(fichier, 'utf8');
	const debut = src.indexOf('const LIEUX_HOTE = {');
	assert.ok(debut >= 0, 'const LIEUX_HOTE absent de ' + path.basename(fichier));
	let prof = 0;
	for (let j = src.indexOf('{', debut); j < src.length; j++) {
		if (src[j] === '{') prof++;
		else if (src[j] === '}' && --prof === 0) return src.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans LIEUX_HOTE de ' + fichier);
}

for (const fichier of [EDITEUR, PAGE]) {
	t(`${path.basename(fichier)} déclare toutes les clés du contrat et inclut les trois parts`, () => {
		const bloc = blocHote(fichier);
		for (const cle of LIEUX_HOTE_REQUIS) {
			assert.ok(new RegExp('^\\t' + cle + '\\s*:', 'm').test(bloc), 'clé absente : ' + cle);
		}
		const src = fs.readFileSync(fichier, 'utf8');
		for (const part of ['part-lieux-css.html', 'part-lieux-js.html', 'part-lieux-markup.html']) {
			assert.ok(src.includes(`{% include "${part}" %}`), 'include absent : ' + part);
		}
	});
}

t('la part JS ne lit aucune globale propre à une page (hors commentaires)', () => {
	const code = scriptsInline(fs.readFileSync(PART_JS, 'utf8'))
		.replace(/\/\*[\s\S]*?\*\//g, '')
		// ⚠️ `\r?\n` : la part est en CRLF, et `.` ne franchit pas un `\r` — `.*$` n'atteindrait
		// jamais la fin d'une ligne coupée sur `\n` seul, et aucun commentaire ne serait retiré.
		.split(/\r?\n/).map(l => l.replace(/(^|[^:'"`])\/\/.*$/, '$1')).join('\n');
	const interdites = ['currentLocId', 'lieuxSelectedCell', 'lieuxConnections', 'redimEnAttente',
		'renderGrid', 'fetchLieuxConnections', 'renderLieuxConnList', 'setStatus', 'closePorteForm', 'closeGuildeForm',
		'lieuxRepos', 'editMode', 'canvas', 'lieuxFileCases'];
	const trouvees = interdites.filter(nom => new RegExp('\\b' + nom + '\\b').test(code));
	assert.deepStrictEqual(trouvees, []);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
