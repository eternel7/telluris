// dev/test_connexions_client.js
//
// Tests d'EXÉCUTION du JavaScript du FORMULAIRE DE CONNEXION
// (templates/admin_map_editor.html, mode Lieux → « 🔗 Relier à un lieu existant »
//  et le bouton « 🔗 Connexion » de chaque ligne).
//
//   node dev/test_connexions_client.js     # sort en code 1 au premier échec
//
// POURQUOI : deux classes de bug SILENCIEUSES, qu'aucun test pytest ne peut atteindre
// (la logique vit dans un template).
//   1. `PUT /admin/doc` fait un PUT COMPLET et ne refuse RIEN — il rattache même le `_rev`
//      courant. Un `_id` déjà pris ÉCRASE la connexion existante : la porte d'un autre
//      lieu disparaît sans la moindre erreur (CLAUDE.md §11).
//   2. Le doc écrit est le doc ENTIER : ce que le formulaire ne possède pas doit survivre
//      à la fusion — les clés inconnues du doc comme celles de chaque NŒUD.
//
// MÉTHODE : identique à dev/test_lot_lieux_client.js — extraction par nom (accolades
// équilibrées) et exécution dans le realm du test (`runInThisContext`), pour que
// `deepStrictEqual` accepte les tableaux produits.
//
// HORS DE PORTÉE (à vérifier en jeu, cf. CLAUDE.md §15) : le rendu du panneau, la visée
// 🎯 sur la carte (voile rouge, cadre de survol) et l'échange avec `/admin/doc`.
//
// ⚠️ L'extraction se fait par NOM : renommer une fonction ici visée fait échouer le test
// avec « fonction introuvable » — c'est voulu, pas un faux positif.

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

for (const f of ['_cxSlug', '_cxIdPropose', '_cxPosPosable', '_fusionConnexion', '_cxValider']) {
	vm.runInThisContext(extraire(f));
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Une grille 4×3 : la colonne 0 est inaccessible (0), la case [3,2] porte 9 (« Bloqué »),
// la case [1,1] est un terrain difficile (2) — praticable, comme dans `combat._walkable`.
const GRILLE = [
	[0, 1, 1, 1],
	[0, 2, 1, 1],
	[0, 1, 1, 9],
];

// ── _cxSlug ──────────────────────────────────────────────────────────────────
t('_cxSlug retire le préfixe lieu:, et lui seul', () => {
	assert.strictEqual(_cxSlug('lieu:auxerre'), 'auxerre');
	assert.strictEqual(_cxSlug('lieu:le_bastion_de_l_yonne_comptoir'), 'le_bastion_de_l_yonne_comptoir');
	assert.strictEqual(_cxSlug('auxerre'), 'auxerre');
	assert.strictEqual(_cxSlug(null), '');
});

// ── _cxIdPropose ─────────────────────────────────────────────────────────────
t('l_id proposé suit la convention <là-bas>_to_<ici>', () => {
	assert.strictEqual(_cxIdPropose('lieu:la_forge', 'lieu:auxerre', []),
		'link:la_forge_to_auxerre');
});

t('un id déjà pris est suffixé plutôt que réutilisé (sinon écrasement silencieux)', () => {
	assert.strictEqual(
		_cxIdPropose('lieu:la_forge', 'lieu:auxerre', ['link:la_forge_to_auxerre']),
		'link:la_forge_to_auxerre_02');
	assert.strictEqual(
		_cxIdPropose('lieu:la_forge', 'lieu:auxerre',
			['link:la_forge_to_auxerre', 'link:la_forge_to_auxerre_02']),
		'link:la_forge_to_auxerre_03');
});

t("l'id proposé est vide tant qu'il manque un des deux lieux", () => {
	assert.strictEqual(_cxIdPropose('', 'lieu:auxerre', []), '');
	assert.strictEqual(_cxIdPropose('lieu:la_forge', '', []), '');
});

// ── _cxPosPosable ────────────────────────────────────────────────────────────
t('une case praticable passe, terrain difficile compris', () => {
	assert.strictEqual(_cxPosPosable(GRILLE, [1, 0]), '');
	assert.strictEqual(_cxPosPosable(GRILLE, [1, 1]), '');   // terrain difficile (2) : admis
});

t('une case inaccessible est refusée', () => {
	assert.strictEqual(_cxPosPosable(GRILLE, [0, 0]), 'terrain');
	assert.strictEqual(_cxPosPosable(GRILLE, [0, 2]), 'terrain');
});

// ⚠️ Seuil HÉRITÉ de `_caseAccessible` (le voile rouge du mode Lieux, `>= 1`) et repris ici
// À DESSEIN : ce que la visée 🎯 accepte au clic, la saisie à la main doit l'accepter aussi.
// La valeur 9 (« Bloqué (∞) » dans la légende) passe donc ce seuil — c'est le comportement
// de l'outil de repositionnement d'avant ce formulaire, pas une décision prise ici.
t('le seuil est >= 1, celui du voile rouge de la carte — 9 le franchit', () => {
	assert.strictEqual(_cxPosPosable(GRILLE, [3, 2]), '');
});

t('une case hors de la grille est refusée, ligne trop courte comprise', () => {
	assert.strictEqual(_cxPosPosable(GRILLE, [4, 0]), 'hors');
	assert.strictEqual(_cxPosPosable(GRILLE, [0, 3]), 'hors');
	// `dimensions` plus grand que `cells` : la ligne peut ne pas exister du tout.
	assert.strictEqual(_cxPosPosable([[1, 1]], [0, 1]), 'hors');
});

t('une position qui n_est pas un couple d_entiers positifs est invalide', () => {
	assert.strictEqual(_cxPosPosable(GRILLE, [-1, 0]), 'invalide');
	assert.strictEqual(_cxPosPosable(GRILLE, [1.5, 0]), 'invalide');
	assert.strictEqual(_cxPosPosable(GRILLE, [1]), 'invalide');
	assert.strictEqual(_cxPosPosable(GRILLE, null), 'invalide');
});

t('un lieu SANS carte n_oppose aucune règle : [0,0] est la convention des boutiques', () => {
	assert.strictEqual(_cxPosPosable(null, [0, 0]), '');
	assert.strictEqual(_cxPosPosable([], [12, 34]), '');
	// … mais une position mal formée reste mal formée, carte ou pas.
	assert.strictEqual(_cxPosPosable(null, [-1, 0]), 'invalide');
});

// ── _fusionConnexion ─────────────────────────────────────────────────────────
const champs = (destPos, label) => ({
	noeuds: [
		{ lieu: 'lieu:auxerre', pos: [5, 6], label: '' },
		{ lieu: 'lieu:la_forge', pos: destPos || [0, 0], label: label || '' },
	],
	type: 'armurerie',
	status: 'ouvert',
});

t('une création produit exactement la forme des docs en base', () => {
	assert.deepStrictEqual(_fusionConnexion({}, champs()), {
		type: 'connection',
		nodes: [
			{ lieu: 'lieu:auxerre', pos: [5, 6] },
			{ lieu: 'lieu:la_forge', pos: [0, 0] },
		],
		metadata: { type: 'armurerie', status: 'ouvert' },
	});
});

t('un label vide n_est pas écrit (get_lieu_links replie sur celui du lieu)', () => {
	const doc = _fusionConnexion({}, champs([0, 0], 'au-delà des remparts'));
	assert.strictEqual(doc.nodes[0].label, undefined);
	assert.strictEqual(doc.nodes[1].label, 'au-delà des remparts');
});

t('un label retiré au formulaire disparaît du doc, il ne reste pas en place', () => {
	const existant = {
		_id: 'link:la_forge_to_auxerre', _rev: '3-abc', type: 'connection',
		nodes: [
			{ lieu: 'lieu:auxerre', pos: [1, 1], label: 'ancien' },
			{ lieu: 'lieu:la_forge', pos: [0, 0] },
		],
		metadata: { type: 'armurerie', status: 'ouvert' },
	};
	const doc = _fusionConnexion(existant, champs());
	assert.strictEqual('label' in doc.nodes[0], false);
});

t('_rev et les clés inconnues du doc survivent à la fusion (PUT complet)', () => {
	const existant = {
		_id: 'link:la_forge_to_auxerre', _rev: '3-abc', type: 'connection',
		commentaire: 'posée à la main en 2025',
		nodes: [
			{ lieu: 'lieu:auxerre', pos: [1, 1] },
			{ lieu: 'lieu:la_forge', pos: [0, 0] },
		],
		metadata: { type: 'armurerie', status: 'ouvert', auteur: 'gm' },
	};
	const doc = _fusionConnexion(existant, champs());
	assert.strictEqual(doc._id, 'link:la_forge_to_auxerre');
	assert.strictEqual(doc._rev, '3-abc');
	assert.strictEqual(doc.commentaire, 'posée à la main en 2025');
	assert.strictEqual(doc.metadata.auteur, 'gm');   // clé inconnue des métadonnées
	assert.deepStrictEqual(doc.nodes[0].pos, [5, 6]); // … et la position, elle, est bien écrite
});

t('les clés inconnues d_un NŒUD survivent, index par index', () => {
	const existant = {
		type: 'connection',
		nodes: [
			{ lieu: 'lieu:auxerre', pos: [1, 1], acces: 'garde' },
			{ lieu: 'lieu:la_forge', pos: [0, 0], note: 'sortie' },
		],
		metadata: {},
	};
	const doc = _fusionConnexion(existant, champs());
	assert.strictEqual(doc.nodes[0].acces, 'garde');
	assert.strictEqual(doc.nodes[1].note, 'sortie');
});

t('la fusion ne mute jamais le doc existant', () => {
	const existant = {
		type: 'connection',
		nodes: [{ lieu: 'lieu:auxerre', pos: [1, 1] }, { lieu: 'lieu:la_forge', pos: [0, 0] }],
		metadata: { type: 'armurerie', status: 'ouvert' },
	};
	const copie = JSON.parse(JSON.stringify(existant));
	_fusionConnexion(existant, champs([9, 9]));
	assert.deepStrictEqual(existant, copie);
});

// ── _cxValider ───────────────────────────────────────────────────────────────
const bon = () => Object.assign(_fusionConnexion({}, champs()), { _id: 'link:la_forge_to_auxerre' });

t('un doc sain passe', () => {
	assert.strictEqual(_cxValider(bon(), 'lieu:auxerre', [], true), '');
});

t('un id déjà en base est refusé À LA CRÉATION — et seulement là', () => {
	const doc = bon();
	assert.match(_cxValider(doc, 'lieu:auxerre', ['link:la_forge_to_auxerre'], true), /existe déjà/);
	// En édition l'`_id` est GELÉ : se le voir refuser parce qu'il existe serait absurde.
	assert.strictEqual(_cxValider(doc, 'lieu:auxerre', ['link:la_forge_to_auxerre'], false), '');
});

t('un identifiant mal formé est refusé', () => {
	for (const id of ['', 'la_forge_to_auxerre', 'link:', 'link:deux mots']) {
		const doc = Object.assign(bon(), { _id: id });
		assert.match(_cxValider(doc, 'lieu:auxerre', [], true), /identifiant/i, 'accepté : ' + id);
	}
});

t('une connexion doit relier deux lieux DIFFÉRENTS, dont le lieu courant', () => {
	const seul = bon(); seul.nodes = [seul.nodes[0]];
	assert.match(_cxValider(seul, 'lieu:auxerre', [], true), /deux lieux/);

	const memeLieu = bon(); memeLieu.nodes[1].lieu = 'lieu:auxerre';
	assert.match(_cxValider(memeLieu, 'lieu:auxerre', [], true), /lui-même/);

	const vide = bon(); vide.nodes[1].lieu = '';
	assert.match(_cxValider(vide, 'lieu:auxerre', [], true), /requis/);

	// Aucun des deux nœuds n'est le lieu courant : la porte ne serait visible de nulle part ici.
	assert.match(_cxValider(bon(), 'lieu:reims', [], true), /lieu courant/);
});

t('une position mal formée est refusée avant même la grille', () => {
	const doc = bon(); doc.nodes[0].pos = [-1, 2];
	assert.match(_cxValider(doc, 'lieu:auxerre', [], true), /Position invalide/);
});

t('le type et l_état sont requis', () => {
	const sansType = bon(); sansType.metadata.type = '';
	assert.match(_cxValider(sansType, 'lieu:auxerre', [], true), /type/i);
	const sansEtat = bon(); sansEtat.metadata.status = '';
	assert.match(_cxValider(sansEtat, 'lieu:auxerre', [], true), /état/i);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
