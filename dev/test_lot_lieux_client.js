// dev/test_lot_lieux_client.js
//
// Tests d'EXÉCUTION du JavaScript du LOT DE LIEUX
// (templates/admin_map_editor.html, mode Lieux → « ➕ Ajouter un lot »).
//
//   node dev/test_lot_lieux_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le lot écrit 2N documents en une requête, dont la moitié sont des
// `connection` dont l'`_id` se dérive d'un COMPTEUR. Or `import-bulk` fait un PUT
// COMPLET : deux docs de même `_id` dans le même lot ne laissent que le dernier en
// base, et les autres boutiques restent SANS PORTE — invisibles en jeu, sans la
// moindre erreur. Le même piège vaut pour l'`_id` du lieu, dérivé du label.
// Aucun test pytest ne peut atteindre cela : la logique vit dans un template.
//
// MÉTHODE : identique à dev/test_resize_client.js — extraction par nom (accolades
// équilibrées) et exécution dans le realm du test (`runInThisContext`), pour que
// `deepStrictEqual` accepte les tableaux produits.
//
// HORS DE PORTÉE (à vérifier en jeu, cf. CLAUDE.md §15) : le rendu du tableau, le
// Maj+clic sur la grille, la barre de progression NDJSON et l'échange avec
// `/api/lieux/enseignes`.
//
// ⚠️ L'extraction se fait par NOM : renommer une fonction ici visée fait échouer le
// test avec « fonction introuvable » — c'est voulu, pas un faux positif.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_map_editor.html');
const src = fs.readFileSync(TEMPLATE, 'utf8');

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

// `_prochainLinkId` et `_slugLieu` ne sont pas pures : la première lit la globale
// `lieuxConnections`, la seconde la constante `_DIACRITIQUES`. On les amène quand même
// — ce sont elles qui produisent les `_id`, donc précisément ce qu'il faut éprouver —
// en semant leurs dépendances sur `globalThis`.
for (const f of ['_lotExpansion', '_lotRotation', '_lotLignes', '_lotDocs', '_lotCollisions',
                 '_slugLieu', '_escRe', '_prochainLinkId']) {
	vm.runInThisContext(extraire(f));
}
vm.runInThisContext(src.match(/const _DIACRITIQUES = [^;]+;/)[0]);
globalThis.lieuxConnections = [];

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const file = (...paires) => paires.map(([cx, cy]) => ({ cx, cy }));

// Un jeu de lignes prêtes à écrire, sans passer par les propositions du serveur.
function lignes(...triplets) {
	return triplets.map(([categorie, label, cx, cy], i) => ({
		categorie, label, image: categorie + '_europe01.png', portrait: '',
		cle: categorie + '#' + (i + 1), rang: i + 1,
		cx, cy, case_ok: cx !== null,
	}));
}

console.log('\n── Expansion de la composition ──');

t('une composition devient une ligne par boutique, dans un ordre stable', () => {
	assert.deepStrictEqual(
		_lotExpansion({ boulangerie: 2, armurerie: 1 }),
		[{ categorie: 'armurerie', rang: 1 },
		 { categorie: 'boulangerie', rang: 1 },
		 { categorie: 'boulangerie', rang: 2 }]);
});

t('une quantité nulle, absente ou illisible ne produit aucune ligne', () => {
	assert.deepStrictEqual(_lotExpansion({ armurerie: 0 }), []);
	assert.deepStrictEqual(_lotExpansion({ armurerie: '' }), []);
	assert.deepStrictEqual(_lotExpansion({ armurerie: 'deux' }), []);
	assert.deepStrictEqual(_lotExpansion({}), []);
	assert.deepStrictEqual(_lotExpansion(null), []);
});

t('une quantité en chaîne est acceptée (elle vient d’un <input>)', () => {
	assert.strictEqual(_lotExpansion({ armurerie: '3' }).length, 3);
});

console.log('\n── Rotation des catalogues (images, portraits) ──');

t('la rotation prend le premier élément encore libre', () => {
	assert.strictEqual(_lotRotation(['a', 'b', 'c'], ['a'], 1), 'b');
	assert.strictEqual(_lotRotation(['a', 'b', 'c'], ['a', 'b'], 2), 'c');
});

t('catalogue entièrement pris ⇒ on tourne, jamais de valeur vide', () => {
	// Une ligne sans image est refusée à l'écriture : mieux vaut un doublon.
	assert.strictEqual(_lotRotation(['a', 'b'], ['a', 'b'], 1), 'a');
	assert.strictEqual(_lotRotation(['a', 'b'], ['a', 'b'], 2), 'b');
	assert.strictEqual(_lotRotation(['a', 'b'], ['a', 'b'], 3), 'a');
});

t('catalogue vide ⇒ chaîne vide (et non une exception)', () => {
	assert.strictEqual(_lotRotation([], [], 1), '');
	assert.strictEqual(_lotRotation(null, [], 1), '');
});

console.log('\n── Construction des lignes ──');

const CATALOGUES = {
	images: { armurerie: ['ar01.png', 'ar02.png'], boulangerie: ['bo01.png'] },
	portraits: { armurerie: ['pa.png', 'pb.png'], boulangerie: ['pc.png'] },
};

t('la ligne i prend la case i de la file, dans l’ordre des Maj+clic', () => {
	const l = _lotLignes(_lotExpansion({ armurerie: 2 }), file([7, 3], [9, 4]),
		{}, {}, CATALOGUES.images, CATALOGUES.portraits);
	assert.deepStrictEqual([l[0].cx, l[0].cy], [7, 3]);
	assert.deepStrictEqual([l[1].cx, l[1].cy], [9, 4]);
	assert.ok(l[0].case_ok && l[1].case_ok);
});

t('une ligne en surnombre sort SANS case plutôt que d’être rognée', () => {
	const l = _lotLignes(_lotExpansion({ armurerie: 3 }), file([7, 3]),
		{}, {}, CATALOGUES.images, CATALOGUES.portraits);
	assert.strictEqual(l.length, 3, 'les 3 lignes doivent rester visibles');
	assert.strictEqual(l[0].case_ok, true);
	assert.strictEqual(l[1].case_ok, false);
	assert.strictEqual(l[2].cx, null);
});

t('des cases en trop dans la file ne créent aucune ligne', () => {
	const l = _lotLignes(_lotExpansion({ armurerie: 1 }), file([7, 3], [9, 4], [1, 1]),
		{}, {}, CATALOGUES.images, CATALOGUES.portraits);
	assert.strictEqual(l.length, 1);
});

t('deux lignes du même métier ne reçoivent pas la même façade', () => {
	const l = _lotLignes(_lotExpansion({ armurerie: 2 }), file([7, 3], [9, 4]),
		{}, {}, CATALOGUES.images, CATALOGUES.portraits);
	assert.notStrictEqual(l[0].image, l[1].image);
	assert.notStrictEqual(l[0].portrait, l[1].portrait);
});

t('une retouche à la main gagne sur la proposition', () => {
	const labels = { 'armurerie#1': 'L’Enclume du Rempart' };
	const edits = { 'armurerie#1': { label: 'La Forge Noire', image: 'ar02.png' } };
	const l = _lotLignes(_lotExpansion({ armurerie: 1 }), file([7, 3]),
		labels, edits, CATALOGUES.images, CATALOGUES.portraits);
	assert.strictEqual(l[0].label, 'La Forge Noire');
	assert.strictEqual(l[0].image, 'ar02.png');
});

t('la retouche est indexée sur <categorie>#<rang>, donc elle SURVIT à un changement '
  + 'de composition', () => {
	const edits = { 'boulangerie#1': { label: 'Le Fournil Choisi' } };
	// La boulangerie était seule ; on ajoute une armurerie AVANT elle dans l'ordre.
	const avant = _lotLignes(_lotExpansion({ boulangerie: 1 }), file([1, 1]),
		{}, edits, CATALOGUES.images, CATALOGUES.portraits);
	const apres = _lotLignes(_lotExpansion({ armurerie: 1, boulangerie: 1 }), file([1, 1], [2, 2]),
		{}, edits, CATALOGUES.images, CATALOGUES.portraits);
	assert.strictEqual(avant[0].label, 'Le Fournil Choisi');
	assert.strictEqual(apres[1].label, 'Le Fournil Choisi', 'la ligne a changé d’index, pas de clé');
});

t('un portrait explicitement vidé le reste (et ne repart pas en rotation)', () => {
	// `portrait: ''` est un choix — « — aucun — » dans le select — et non une absence.
	const edits = { 'armurerie#1': { portrait: '' } };
	const l = _lotLignes(_lotExpansion({ armurerie: 1 }), file([7, 3]),
		{}, edits, CATALOGUES.images, CATALOGUES.portraits);
	assert.strictEqual(l[0].portrait, '');
});

console.log('\n── Les documents écrits ──');

t('chaque ligne donne son lieu PUIS son link (jamais l’inverse)', () => {
	const docs = _lotDocs(lignes(['armurerie', 'L’Enclume', 5, 5]), 'lieu:lutecia',
		_slugLieu, _prochainLinkId);
	assert.strictEqual(docs.length, 2);
	assert.strictEqual(docs[0].type, 'lieu');
	assert.strictEqual(docs[1].type, 'connection');
	// Une connexion écrite avant son lieu casse l'enrichissement `details` du serveur.
	assert.ok(docs.indexOf(docs[0]) < docs.indexOf(docs[1]));
});

t('le doc lieu porte exactement ce qu’un magasin jouable demande', () => {
	const [lieu] = _lotDocs(lignes(['armurerie', 'L’Enclume du Rempart', 5, 5]),
		'lieu:lutecia', _slugLieu, _prochainLinkId);
	assert.strictEqual(lieu._id, 'lieu:l_enclume_du_rempart');
	assert.strictEqual(lieu.categorie, 'armurerie');
	assert.strictEqual(lieu.lieu_parent, 'lieu:lutecia');
	assert.deepStrictEqual(lieu.pnj, [{ character: 'pnj:marchand_armurerie' }]);
	assert.deepStrictEqual(lieu.stock_matieres, {});
	assert.deepStrictEqual(lieu.stock_vente, []);
});

t('un portrait vide n’est PAS écrit (repli voulu sur le doc PNJ générique)', () => {
	const l = lignes(['armurerie', 'L’Enclume', 5, 5]);
	const [sans] = _lotDocs(l, 'lieu:lutecia', _slugLieu, _prochainLinkId);
	assert.ok(!('portrait' in sans.pnj[0]), 'portrait vide écrit malgré tout');
	l[0].portrait = 'marchand_nain_m_armurerie.png';
	const [avec] = _lotDocs(l, 'lieu:lutecia', _slugLieu, _prochainLinkId);
	assert.strictEqual(avec.pnj[0].portrait, 'marchand_nain_m_armurerie.png');
});

t('LE PIÈGE : aucun `pnj` écrit pour une catégorie SANS tenancier générique', () => {
	// `auberge` est la seule catégorie interactive du jeu sans `pnj:marchand_*`, et aucun
	// code d'auberge ne lit `lieu.pnj[]`. Écrire l'entrée quand même poserait N références
	// mortes en base, en silence. Le doc correct est celui de l'auberge d'Auxerre : sans `pnj`.
	const tenanciers = ['pnj:marchand_armurerie', 'pnj:marchand_etable'];
	const docs = _lotDocs(lignes(
		['auberge', 'L’Auberge du Pont', 1, 1],
		['armurerie', 'L’Enclume', 2, 2]), 'lieu:lutecia', _slugLieu, _prochainLinkId, tenanciers);
	const lieux = docs.filter(d => d.type === 'lieu');
	assert.ok(!('pnj' in lieux[0]), 'un pnj:marchand_auberge fantôme a été écrit');
	assert.deepStrictEqual(lieux[1].pnj, [{ character: 'pnj:marchand_armurerie' }]);
	// La porte, elle, est posée dans les deux cas.
	assert.strictEqual(docs.filter(d => d.type === 'connection').length, 2);
});

t('sans liste de tenanciers, le comportement d’avant est conservé', () => {
	// Le paramètre est facultatif : un appelant qui ne le passe pas écrit le `pnj` comme
	// avant. C'est ce qui rend le correctif sans risque pour les sites d'appel existants.
	const [lieu] = _lotDocs(lignes(['auberge', 'L’Auberge', 1, 1]), 'lieu:lutecia',
		_slugLieu, _prochainLinkId);
	assert.deepStrictEqual(lieu.pnj, [{ character: 'pnj:marchand_auberge' }]);
});

t('la connexion pointe la case du lieu courant et [0,0] côté boutique', () => {
	const [, link] = _lotDocs(lignes(['armurerie', 'L’Enclume', 12, 7]), 'lieu:lutecia',
		_slugLieu, _prochainLinkId);
	assert.deepStrictEqual(link.nodes[0], { lieu: 'lieu:lutecia', pos: [12, 7] });
	assert.deepStrictEqual(link.nodes[1].pos, [0, 0]);
	assert.deepStrictEqual(link.metadata, { type: 'armurerie', status: 'ouvert' });
});

t('LE PIÈGE : N boutiques du même métier ⇒ N link:* DISTINCTS', () => {
	// Sans le paramètre `dejaPris` de `_prochainLinkId`, les trois porteraient
	// `link:armurerie01_to_lutecia` : import-bulk n'en garderait qu'une, et deux
	// boutiques resteraient sans porte, invisibles en jeu et sans la moindre erreur.
	globalThis.lieuxConnections = [];
	const docs = _lotDocs(lignes(
		['armurerie', 'L’Enclume', 1, 1],
		['armurerie', 'La Forge', 2, 2],
		['armurerie', 'Le Marteau', 3, 3]), 'lieu:lutecia', _slugLieu, _prochainLinkId);
	const links = docs.filter(d => d.type === 'connection').map(d => d._id);
	assert.deepStrictEqual(links, [
		'link:armurerie01_to_lutecia',
		'link:armurerie02_to_lutecia',
		'link:armurerie03_to_lutecia']);
	assert.strictEqual(new Set(links).size, 3);
});

t('la numérotation REPREND après les liens déjà en base', () => {
	globalThis.lieuxConnections = [
		{ _id: 'link:armurerie01_to_lutecia' },
		{ _id: 'link:armurerie02_to_lutecia' },
	];
	const docs = _lotDocs(lignes(['armurerie', 'L’Enclume', 1, 1], ['armurerie', 'La Forge', 2, 2]),
		'lieu:lutecia', _slugLieu, _prochainLinkId);
	assert.deepStrictEqual(docs.filter(d => d.type === 'connection').map(d => d._id),
		['link:armurerie03_to_lutecia', 'link:armurerie04_to_lutecia']);
	globalThis.lieuxConnections = [];
});

t('les compteurs de deux métiers sont indépendants', () => {
	globalThis.lieuxConnections = [];
	const docs = _lotDocs(lignes(
		['armurerie', 'L’Enclume', 1, 1],
		['boulangerie', 'Le Fournil', 2, 2],
		['armurerie', 'La Forge', 3, 3]), 'lieu:lutecia', _slugLieu, _prochainLinkId);
	assert.deepStrictEqual(docs.filter(d => d.type === 'connection').map(d => d._id),
		['link:armurerie01_to_lutecia', 'link:boulangerie01_to_lutecia',
		 'link:armurerie02_to_lutecia']);
});

t('N lignes ⇒ N _id de lieu distincts quand les enseignes le sont', () => {
	const docs = _lotDocs(lignes(
		['armurerie', 'L’Enclume du Rempart', 1, 1],
		['armurerie', 'La Forge du Parvis', 2, 2],
		['boulangerie', 'Le Fournil des Halles', 3, 3]), 'lieu:lutecia', _slugLieu, _prochainLinkId);
	const ids = docs.filter(d => d.type === 'lieu').map(d => d._id);
	assert.strictEqual(new Set(ids).size, 3);
});

console.log('\n── Collisions d’identifiants ──');

t('deux enseignes qui donnent le MÊME slug sont signalées', () => {
	// « L'Enclume du Rempart » et « L’Enclume, du Rempart ! » se réduisent au même _id.
	const col = _lotCollisions(lignes(
		['armurerie', "L'Enclume du Rempart", 1, 1],
		['armurerie', 'L’Enclume, du Rempart !', 2, 2]), [], _slugLieu);
	assert.deepStrictEqual(col.doublons, ['lieu:l_enclume_du_rempart']);
});

t('une enseigne déjà en base est signalée à part', () => {
	const col = _lotCollisions(lignes(['armurerie', 'L’Enclume du Rempart', 1, 1]),
		['lieu:l_enclume_du_rempart', 'lieu:auxerre'], _slugLieu);
	assert.deepStrictEqual(col.existants, ['lieu:l_enclume_du_rempart']);
	assert.deepStrictEqual(col.doublons, []);
});

t('une ligne sans enseigne est signalée, et ne compte pas comme un doublon', () => {
	const col = _lotCollisions(lignes(
		['armurerie', '', 1, 1],
		['boulangerie', '', 2, 2]), [], _slugLieu);
	assert.deepStrictEqual(col.sansLabel, ['armurerie#1', 'boulangerie#2']);
	assert.deepStrictEqual(col.doublons, []);
});

t('un lot sain ne signale rien', () => {
	const col = _lotCollisions(lignes(
		['armurerie', 'L’Enclume du Rempart', 1, 1],
		['boulangerie', 'Le Fournil des Halles', 2, 2]), ['lieu:auxerre'], _slugLieu);
	assert.deepStrictEqual(col, { doublons: [], existants: [], sansLabel: [] });
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
