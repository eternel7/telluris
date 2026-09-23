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
// Includes développés : le formulaire de connexion vit dans part-lieux-js.html (cf. dev/_template_js.js).
const src = require('./_template_js').lireAvecIncludes(TEMPLATE);

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

for (const f of ['_cxSlug', '_cxIdPropose', '_cxIdInterne', '_cxPosPosable', '_fusionConnexion', '_cxValider', '_lieuxHorsTerrain',
				 '_connInterne', '_connAutreBout']) {
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

t('une connexion relie deux nœuds, dont le lieu courant', () => {
	const seul = bon(); seul.nodes = [seul.nodes[0]];
	assert.match(_cxValider(seul, 'lieu:auxerre', [], true), /deux lieux/);

	const vide = bon(); vide.nodes[1].lieu = '';
	assert.match(_cxValider(vide, 'lieu:auxerre', [], true), /requis/);

	// Aucun des deux nœuds n'est le lieu courant : la porte ne serait visible de nulle part ici.
	assert.match(_cxValider(bon(), 'lieu:reims', [], true), /lieu courant/);
});

t('id d’une connexion INTERNE : les deux cases dans l’id, suffixé s’il est pris', () => {
	assert.strictEqual(_cxIdInterne('lieu:tour', [2, 3], [9, 1], []), 'link:tour_9_1_to_tour_2_3');
	assert.strictEqual(_cxIdInterne('lieu:tour', [2, 3], [9, 1], ['link:tour_9_1_to_tour_2_3']),
		'link:tour_9_1_to_tour_2_3_02');
	// Case pas encore visée (champ vide ⇒ -1) : rien à proposer.
	assert.strictEqual(_cxIdInterne('lieu:tour', [2, 3], [-1, -1], []), '');
});

t('connexion INTERNE (deux cases de la même carte) : cases distinctes, deux labels', () => {
	const interne = (posLa, labelIci, labelLa) => Object.assign(_fusionConnexion({}, {
		noeuds: [
			{ lieu: 'lieu:auxerre', pos: [5, 6], label: labelIci },
			{ lieu: 'lieu:auxerre', pos: posLa, label: labelLa },
		],
		type: 'passage', status: 'ouvert',
	}), { _id: 'link:auxerre_9_2_to_auxerre_5_6' });
	assert.strictEqual(_cxValider(interne([9, 2], 'redescendre', 'monter au rempart'), 'lieu:auxerre', [], true), '');
	assert.match(_cxValider(interne([5, 6], 'a', 'b'), 'lieu:auxerre', [], true), /même case/);
	// Sans label, les deux boutons liraient le nom de la carte : indiscernables en jeu.
	assert.match(_cxValider(interne([9, 2], 'redescendre', ''), 'lieu:auxerre', [], true), /label/);
	assert.match(_cxValider(interne([9, 2], '', 'monter'), 'lieu:auxerre', [], true), /label/);
});

t('l’autre bout d’une connexion : miroir de lieux.noeud_destination (tests/test_lieux.py)', () => {
	const ordinaire = { nodes: [{ lieu: 'lieu:auxerre', pos: [4, 5] }, { lieu: 'lieu:forge', pos: [0, 0] }] };
	assert.ok(!_connInterne(ordinaire));
	assert.strictEqual(_connAutreBout(ordinaire, 'lieu:auxerre', [4, 5]).lieu, 'lieu:forge');
	const escalier = { nodes: [{ lieu: 'lieu:tour', pos: [2, 3] }, { lieu: 'lieu:tour', pos: [9, 1] }] };
	assert.ok(_connInterne(escalier));
	assert.deepStrictEqual(_connAutreBout(escalier, 'lieu:tour', [2, 3]).pos, [9, 1]);
	assert.deepStrictEqual(_connAutreBout(escalier, 'lieu:tour', [9, 1]).pos, [2, 3]);
	const plat = { nodes: [{ lieu: 'lieu:tour', pos: [2, 3] }, { lieu: 'lieu:tour', pos: [2, 3] }] };
	assert.strictEqual(_connAutreBout(plat, 'lieu:tour', [2, 3]), null);
});

t('alerte terrain : les DEUX bouts d’une connexion interne sont éprouvés', () => {
	const G = [[1, 2], [3, 1]];
	const escalier = { _id: 'link:e', nodes: [
		{ lieu: 'lieu:auxerre', pos: [1, 0], details: { label: 'descendre' } },
		{ lieu: 'lieu:auxerre', pos: [0, 1], details: { label: 'monter' } }] };
	const r = _lieuxHorsTerrain([escalier], 'lieu:auxerre', G);
	assert.deepStrictEqual(r.map(c => [c.cx, c.cy, c.v, c.lieux[0].label]),
		[[1, 0, 2, 'monter'], [0, 1, 3, 'descendre']]);
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

// ── _lieuxHorsTerrain ────────────────────────────────────────────────────────
// Alerte du mode Lieux : le prédicat est `!== 1`, PAS celui de `_cxPosPosable` (`>= 1`) — une
// porte sur terrain difficile se pose, mais sort des flèches de déplacement de play_town.
function lien(id, posIci, destId, label) {
	const dest = { lieu: destId, pos: [0, 0] };
	if (label) dest.details = { label };
	return { _id: id, nodes: [{ lieu: 'lieu:auxerre', pos: posIci }, dest] };
}

t('une case 1 n_est pas signalée ; 0, 2 et 9 le sont, avec leur valeur', () => {
	const r = _lieuxHorsTerrain([
		lien('link:libre', [1, 0], 'lieu:libre'),
		lien('link:zero', [0, 0], 'lieu:zero'),
		lien('link:deux', [1, 1], 'lieu:deux'),
		lien('link:neuf', [3, 2], 'lieu:neuf'),
	], 'lieu:auxerre', GRILLE);
	assert.deepStrictEqual(r.map(c => [c.cx, c.cy, c.v]), [[0, 0, 0], [1, 1, 2], [3, 2, 9]]);
});

t('une position hors grille est signalée avec v: null', () => {
	const r = _lieuxHorsTerrain([lien('link:loin', [7, 1], 'lieu:loin'), lien('link:neg', [1, -1], 'lieu:neg')],
		'lieu:auxerre', GRILLE);
	assert.deepStrictEqual(r.map(c => [c.cx, c.cy, c.v]), [[1, -1, null], [7, 1, null]]);
});

t('un nœud sans pos, ou une connexion sans nœud sur le lieu courant, est ignoré', () => {
	const sansPos = { _id: 'link:sans_pos', nodes: [{ lieu: 'lieu:auxerre' }, { lieu: 'lieu:x', pos: [0, 0] }] };
	const ailleurs = { _id: 'link:ailleurs', nodes: [{ lieu: 'lieu:reims', pos: [0, 0] }, { lieu: 'lieu:x', pos: [0, 0] }] };
	assert.deepStrictEqual(_lieuxHorsTerrain([sansPos, ailleurs, null], 'lieu:auxerre', GRILLE), []);
});

t('deux connexions sur la même case sont regroupées, label replié sur l_id du lieu', () => {
	const r = _lieuxHorsTerrain([
		lien('link:a', [0, 1], 'lieu:forge', 'La Forge'),
		lien('link:b', [0, 1], 'lieu:tannerie'),
	], 'lieu:auxerre', GRILLE);
	assert.strictEqual(r.length, 1);
	assert.deepStrictEqual(r[0].lieux, [
		{ connId: 'link:a', destId: 'lieu:forge', label: 'La Forge' },
		{ connId: 'link:b', destId: 'lieu:tannerie', label: 'lieu:tannerie' },
	]);
});

t('sans grille, aucune règle : rien n_est signalé', () => {
	const conns = [lien('link:zero', [0, 0], 'lieu:zero')];
	assert.deepStrictEqual(_lieuxHorsTerrain(conns, 'lieu:auxerre', []), []);
	assert.deepStrictEqual(_lieuxHorsTerrain(conns, 'lieu:auxerre', null), []);
});

t('les cases sont triées par ligne puis par colonne', () => {
	const r = _lieuxHorsTerrain([
		lien('link:c', [3, 2], 'lieu:c'),
		lien('link:b', [0, 2], 'lieu:b'),
		lien('link:a', [0, 0], 'lieu:a'),
	], 'lieu:auxerre', GRILLE);
	assert.deepStrictEqual(r.map(c => [c.cx, c.cy]), [[0, 0], [0, 2], [3, 2]]);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
