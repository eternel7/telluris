// dev/test_portes_client.js
//
// Tests d'EXÉCUTION du JavaScript des PORTES DE REMPART
// (templates/admin_map_editor.html, mode Lieux → « 🏰 Ajouter une porte de rempart »
//  et le bouton « 🏰 Porte » de chaque ligne de porte).
//
//   node dev/test_portes_client.js     # sort en code 1 au premier échec
//
// POURQUOI : une porte n'est pas une connexion, c'est une construction à CINQ documents
// (2 `lieu:*` + 3 `connection`) écrite en UNE requête `POST /admin/import-bulk`. Or
// `import-bulk` fait un PUT COMPLET, jamais un merge (CLAUDE.md §11) — d'où trois classes
// de bug SILENCIEUSES, qu'aucun test pytest ne peut atteindre (la logique vit dans un
// template) :
//
//   1. Une clé que le formulaire ne possède pas et qui ne survit pas à la fusion
//      DISPARAÎT de la base sans une erreur — au niveau du doc comme de chaque NŒUD.
//   2. `_fusionConnexion` fusionne les nœuds PAR POSITION : passer les deux nœuds dans un
//      ordre différent de celui du doc existant PERMUTE la cité et la porte. La porte
//      change alors de côté du rempart, sans un mot.
//   3. Un `_id` déjà pris parmi les cinq écrase un document existant, également en silence.
//
// MÉTHODE : identique à dev/test_connexions_client.js — extraction par nom (accolades
// équilibrées) et exécution dans le realm du test (`runInThisContext`), pour que
// `deepStrictEqual` accepte les tableaux produits.
//
// ⚠️ Les constantes `PORTE_*` et `_DIACRITIQUES` sont EXTRAITES du template, jamais
// recopiées ici : les recopier les ferait diverger du code en silence — précisément la
// dérive que `utils/capacites.py` documente côté serveur.
//
// HORS DE PORTÉE (à vérifier en jeu, cf. CLAUDE.md §15) : le rendu du panneau, les deux
// visées 🎯 sur la carte et l'échange avec /admin/import-bulk.

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

// Une déclaration `const <nom> = …;` sur UNE ligne — assez pour les constantes de porte et
// la regex des diacritiques, et ça évite de les redire ici.
function extraireConst(nom) {
	const m = new RegExp('^\\s*const ' + nom + ' = .*$', 'm').exec(js);
	assert.ok(m, 'constante ' + nom + ' introuvable dans le template');
	return m[0];
}

for (const c of ['_DIACRITIQUES', 'PORTE_CATEGORIE', 'PORTE_META_TYPE', 'PORTE_LABEL_EXT']) {
	vm.runInThisContext(extraireConst(c));
}
for (const f of ['_cxSlug', '_cxPosPosable', '_fusionConnexion',
	'_slugLieu', '_capaciteAccordee', '_tagsApres', '_fusionLieu',
	'_ptIds', '_ptCote', '_ptOrdonner', '_ptDocs', '_ptPosCarte', '_ptValider',
	'_ptPaireDe', '_ptImagesLibres']) {
	vm.runInThisContext(extraire(f));
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Une grille 8×6 : la colonne 0 est inaccessible (0), [3,3] porte 9 (« Bloqué »).
const GRILLE = [
	[0, 1, 1, 1, 1, 1, 1, 1],
	[0, 1, 1, 1, 1, 1, 1, 1],
	[0, 1, 1, 1, 1, 1, 1, 1],
	[0, 1, 1, 9, 1, 1, 1, 1],
	[0, 1, 1, 1, 1, 1, 1, 1],
	[0, 1, 1, 1, 1, 1, 1, 1],
];

function champs(extra) {
	return Object.assign({
		citeId: 'lieu:auxerre',
		nom: 'Porte sud',
		labelExt: "Porte sud d'Auxerre - exterieur",
		labelInt: "Porte sud d'Auxerre - interieur",
		imageExt: 'porte_de_ville_douves_exterieur02.png',
		imageInt: 'porte_de_ville_douves_interieur02.png',
		posExt: [5, 4],
		posInt: [3, 2],
		labelPorteExt: PORTE_LABEL_EXT,
		labelPorteInt: '',
	}, extra || {});
}

// ── _ptIds ───────────────────────────────────────────────────────────────────
t('les cinq ids suivent la convention et dérivent du nom', () => {
	const ids = _ptIds('lieu:auxerre', 'sud');
	assert.deepStrictEqual(ids, {
		ext: 'lieu:auxerre_porte_sud_exterieur',
		int: 'lieu:auxerre_porte_sud_interieur',
		linkExt: 'link:auxerre_porte_sud_carte_exterieur',
		linkInt: 'link:auxerre_porte_sud_carte_interieur',
		linkPassage: 'link:auxerre_porte_sud_passage',
	});
});

t('un nom ou une cité vide ne produit aucun id', () => {
	assert.strictEqual(_ptIds('lieu:auxerre', '').ext, '');
	assert.strictEqual(_ptIds('', 'Porte sud').ext, '');
	assert.strictEqual(_ptIds('lieu:auxerre', '  !!  ').ext, '');
});

t('les accents et la ponctuation passent par le slug', () => {
	assert.strictEqual(_ptIds('lieu:auxerre', "de l'Évêché").ext,
		'lieu:auxerre_porte_de_l_eveche_exterieur');
});

t('« Porte sud » et « sud » donnent le MÊME id (pas de bégaiement)', () => {
	// La base dit `_porte_douve_`, `_porte_pont_` : le nom y est le qualificatif. Sans
	// cette coupe, taper le nom complet produirait `auxerre_porte_porte_sud_exterieur`.
	assert.strictEqual(_ptIds('lieu:auxerre', 'Porte sud').ext, 'lieu:auxerre_porte_sud_exterieur');
	assert.strictEqual(_ptIds('lieu:auxerre', 'sud').ext, 'lieu:auxerre_porte_sud_exterieur');
	assert.strictEqual(_ptIds('lieu:auxerre', 'douve').linkPassage, 'link:auxerre_porte_douve_passage');
});

// ── _ptCote ──────────────────────────────────────────────────────────────────
t('le côté se lit sur l_id, puis sur le label', () => {
	assert.strictEqual(_ptCote('lieu:auxerre_porte_douve_exterieur01'), 'exterieur');
	assert.strictEqual(_ptCote('lieu:auxerre_porte_douve_interieur01'), 'interieur');
	assert.strictEqual(_ptCote('lieu:x', "Porte sud - intérieur"), 'interieur');
});

t('un côté indécidable rend la chaîne vide (fail-closed)', () => {
	assert.strictEqual(_ptCote('lieu:auxerre_porte_nord'), '');
	// Les deux mots à la fois : on ne devine pas.
	assert.strictEqual(_ptCote('lieu:x_exterieur_vers_interieur'), '');
});

// ── _ptOrdonner ──────────────────────────────────────────────────────────────
t('les nœuds sont réordonnés selon le DOC existant', () => {
	const voulu = [{ lieu: 'lieu:auxerre' }, { lieu: 'lieu:porte' }];
	// Doc dont le premier nœud est la PORTE : l'ordre doit s'inverser.
	const ancien = { nodes: [{ lieu: 'lieu:porte' }, { lieu: 'lieu:auxerre' }] };
	assert.deepStrictEqual(_ptOrdonner(ancien, voulu).map(n => n.lieu),
		['lieu:porte', 'lieu:auxerre']);
	// Doc déjà dans le bon ordre : rien ne bouge.
	const droit = { nodes: [{ lieu: 'lieu:auxerre' }, { lieu: 'lieu:porte' }] };
	assert.deepStrictEqual(_ptOrdonner(droit, voulu).map(n => n.lieu),
		['lieu:auxerre', 'lieu:porte']);
	// Pas de doc existant (création) : l'ordre voulu fait foi.
	assert.deepStrictEqual(_ptOrdonner(null, voulu).map(n => n.lieu),
		['lieu:auxerre', 'lieu:porte']);
});

// ── _ptDocs : création ───────────────────────────────────────────────────────
t('une porte neuve fait CINQ documents', () => {
	const docs = _ptDocs({}, champs());
	assert.strictEqual(docs.length, 5);
	assert.deepStrictEqual(docs.map(d => d.type),
		['lieu', 'lieu', 'connection', 'connection', 'connection']);
});

t('les deux lieux portent la catégorie, le parent, et AUCUNE grille', () => {
	const [ext, int] = _ptDocs({}, champs());
	for (const l of [ext, int]) {
		assert.strictEqual(l.categorie, PORTE_CATEGORIE);
		assert.strictEqual(l.lieu_parent, 'lieu:auxerre');
		// Une porte est une salle de passage : lui écrire une grille serait un contresens.
		assert.ok(!('dimensions' in l), 'pas de dimensions');
		assert.ok(!('cells' in l), 'pas de cells');
		assert.ok(!('nav' in l), 'pas de nav');
	}
	assert.strictEqual(ext.image, 'porte_de_ville_douves_exterieur02.png');
	assert.strictEqual(int.image, 'porte_de_ville_douves_interieur02.png');
});

t('les trois connexions portent « poste de garde », pas la catégorie', () => {
	const docs = _ptDocs({}, champs());
	for (const c of docs.slice(2)) {
		assert.strictEqual(c.metadata.type, PORTE_META_TYPE);
		assert.strictEqual(c.metadata.status, 'ouvert');
		assert.notStrictEqual(c.metadata.type, PORTE_CATEGORIE);
	}
});

t('la porte est en [0,0] sur ses nœuds, la cité sur les cases visées', () => {
	const docs = _ptDocs({}, champs());
	const [ext, int, linkExt, linkInt, passage] = docs;
	assert.deepStrictEqual(_ptPosCarte(linkExt, 'lieu:auxerre'), [5, 4]);
	assert.deepStrictEqual(_ptPosCarte(linkInt, 'lieu:auxerre'), [3, 2]);
	assert.deepStrictEqual(linkExt.nodes.find(n => n.lieu === ext._id).pos, [0, 0]);
	assert.deepStrictEqual(linkInt.nodes.find(n => n.lieu === int._id).pos, [0, 0]);
	// Le passage ne touche PAS la cité : c'est ce qui le rend introuvable dans
	// `lieuxConnections`, et ce qui interdit d'y appliquer `_cxValider`.
	assert.ok(!passage.nodes.some(n => n.lieu === 'lieu:auxerre'));
	assert.deepStrictEqual(passage.nodes.map(n => n.lieu), [ext._id, int._id]);
	passage.nodes.forEach(n => assert.deepStrictEqual(n.pos, [0, 0]));
});

t('« au-delà des remparts » va sur le nœud CARTE extérieur, et nulle part ailleurs', () => {
	const docs = _ptDocs({}, champs());
	const [ext, int, linkExt, linkInt, passage] = docs;
	assert.strictEqual(linkExt.nodes.find(n => n.lieu === 'lieu:auxerre').label, PORTE_LABEL_EXT);
	// Le nœud de la porte n'a pas de label : il afficherait sinon ce texte des deux côtés.
	assert.ok(!('label' in linkExt.nodes.find(n => n.lieu === ext._id)));
	// Le lien intérieur n'en porte aucun : son bouton doit dire le label de la cité.
	assert.ok(!('label' in linkInt.nodes.find(n => n.lieu === 'lieu:auxerre')));
	passage.nodes.forEach(n => assert.ok(!('label' in n)));
});

t('un label vidé est SUPPRIMÉ, jamais écrit à vide', () => {
	const docs = _ptDocs({}, champs({ labelPorteExt: '' }));
	assert.ok(!('label' in docs[2].nodes.find(n => n.lieu === 'lieu:auxerre')));
});

// ── _ptDocs : édition ────────────────────────────────────────────────────────
function existantsRef() {
	return {
		ext: {
			_id: 'lieu:auxerre_porte_douve_exterieur01', _rev: '4-aaa', type: 'lieu',
			label: "Porte sud d'Auxerre - exterieur", image: 'porte_de_ville_douves_exterieur01.png',
			lieu_parent: 'lieu:auxerre', categorie: PORTE_CATEGORIE,
			note_de_regie: 'à ne pas perdre',
		},
		int: {
			_id: 'lieu:auxerre_porte_douve_interieur01', _rev: '5-bbb', type: 'lieu',
			label: "Porte sud d'Auxerre - interieur", image: 'porte_de_ville_douves_interieur03.png',
			lieu_parent: 'lieu:auxerre', categorie: PORTE_CATEGORIE,
		},
		linkExt: {
			_id: 'link:auxerre_poste_de_garde_tour_porte_douve_exterieur01', _rev: '2-ccc',
			type: 'connection', metadata: { type: PORTE_META_TYPE, status: 'ouvert', note: 'x' },
			nodes: [
				{ lieu: 'lieu:auxerre', pos: [58, 37], label: PORTE_LABEL_EXT, secret: 1 },
				{ lieu: 'lieu:auxerre_porte_douve_exterieur01', pos: [0, 0] },
			],
		},
		linkInt: {
			_id: 'link:auxerre_poste_de_garde_tour_porte_douve_interieur01', _rev: '2-ddd',
			type: 'connection', metadata: { type: PORTE_META_TYPE, status: 'ouvert' },
			nodes: [
				{ lieu: 'lieu:auxerre', pos: [56, 35] },
				{ lieu: 'lieu:auxerre_porte_douve_interieur01', pos: [0, 0] },
			],
		},
		linkPassage: {
			_id: 'link:auxerre_porte_douve_interieur_exterieur01', _rev: '2-eee',
			type: 'connection', metadata: { type: PORTE_META_TYPE, status: 'ouvert' },
			nodes: [
				{ lieu: 'lieu:auxerre_porte_douve_exterieur01', pos: [0, 0] },
				{ lieu: 'lieu:auxerre_porte_douve_interieur01', pos: [0, 0] },
			],
		},
	};
}

function champsDepuis(ex) {
	return champs({
		labelExt: ex.ext.label, labelInt: ex.int.label,
		imageExt: ex.ext.image, imageInt: ex.int.image,
		posExt: _ptPosCarte(ex.linkExt, 'lieu:auxerre'),
		posInt: _ptPosCarte(ex.linkInt, 'lieu:auxerre'),
		labelPorteExt: (ex.linkExt.nodes.find(n => n.lieu === 'lieu:auxerre') || {}).label || '',
		labelPorteInt: (ex.linkInt.nodes.find(n => n.lieu === 'lieu:auxerre') || {}).label || '',
	});
}

t('une passe à blanc rend les CINQ documents à l_identique', () => {
	// LE test qui compte : rouvrir une paire, ne rien changer, tout retrouver.
	const ex = existantsRef();
	const docs = _ptDocs(ex, champsDepuis(ex));
	assert.deepStrictEqual(docs, [ex.ext, ex.int, ex.linkExt, ex.linkInt, ex.linkPassage]);
});

t('les _id existants sont GELÉS, jamais recalculés depuis le nom', () => {
	const ex = existantsRef();
	const docs = _ptDocs(ex, champsDepuis(ex));
	// La convention neuve donnerait d'autres ids : on ne rétro-nomme pas.
	assert.strictEqual(docs[0]._id, 'lieu:auxerre_porte_douve_exterieur01');
	assert.strictEqual(docs[4]._id, 'link:auxerre_porte_douve_interieur_exterieur01');
});

t('le _rev et les clés inconnues du DOC survivent', () => {
	const ex = existantsRef();
	const docs = _ptDocs(ex, champsDepuis(ex));
	assert.strictEqual(docs[0]._rev, '4-aaa');
	assert.strictEqual(docs[0].note_de_regie, 'à ne pas perdre');
	assert.strictEqual(docs[2].metadata.note, 'x');
});

t('les clés inconnues de chaque NŒUD survivent', () => {
	const ex = existantsRef();
	const docs = _ptDocs(ex, champsDepuis(ex));
	assert.strictEqual(docs[2].nodes.find(n => n.lieu === 'lieu:auxerre').secret, 1);
});

t('un doc dont la PORTE est le premier nœud n_est pas permuté', () => {
	// Classe de bug n°2 : `_fusionConnexion` fusionne par position. Sans `_ptOrdonner`, ce
	// doc verrait la cité et la porte échanger leurs places — la porte changerait de côté.
	const ex = existantsRef();
	ex.linkExt.nodes = [ex.linkExt.nodes[1], ex.linkExt.nodes[0]];
	const docs = _ptDocs(ex, champsDepuis(ex));
	assert.strictEqual(docs[2].nodes[0].lieu, 'lieu:auxerre_porte_douve_exterieur01');
	assert.deepStrictEqual(docs[2].nodes[0].pos, [0, 0]);
	assert.deepStrictEqual(docs[2].nodes[1].pos, [58, 37]);
});

t('déplacer une porte réécrit la case sans toucher au reste', () => {
	const ex = existantsRef();
	const docs = _ptDocs(ex, champsDepuis(ex));
	const bouge = _ptDocs(ex, Object.assign(champsDepuis(ex), { posExt: [60, 40] }));
	assert.deepStrictEqual(_ptPosCarte(bouge[2], 'lieu:auxerre'), [60, 40]);
	assert.strictEqual(bouge[2]._rev, docs[2]._rev);
	assert.strictEqual(bouge[2].nodes.find(n => n.lieu === 'lieu:auxerre').secret, 1);
});

t('la fusion ne MUTE pas les documents d_origine', () => {
	const ex = existantsRef();
	const copie = JSON.parse(JSON.stringify(ex));
	_ptDocs(ex, Object.assign(champsDepuis(ex), { labelExt: 'Autre', posExt: [1, 1] }));
	assert.deepStrictEqual(ex, copie);
});

// ── _ptValider ───────────────────────────────────────────────────────────────
t('une porte complète et bien posée passe', () => {
	const docs = _ptDocs({}, champs());
	assert.strictEqual(_ptValider(docs, 'lieu:auxerre', GRILLE, [], true), '');
});

t('nom et images sont exigés', () => {
	assert.match(_ptValider(_ptDocs({}, champs({ labelExt: '' })), 'lieu:auxerre', GRILLE, [], true), /nom/i);
	assert.match(_ptValider(_ptDocs({}, champs({ imageExt: '' })), 'lieu:auxerre', GRILLE, [], true), /extérieure/);
	assert.match(_ptValider(_ptDocs({}, champs({ imageInt: '' })), 'lieu:auxerre', GRILLE, [], true), /intérieure/);
});

t('un nom qui ne donne aucun identifiant est refusé', () => {
	const docs = _ptDocs({}, champs({ nom: '!!!' }));
	assert.match(_ptValider(docs, 'lieu:auxerre', GRILLE, [], true), /identifiant/);
});

t('CHACUNE des deux cases est éprouvée sur la grille', () => {
	// Le contrôle doit nommer le côté fautif : sur deux cases, « case invalide » ne dirait
	// pas laquelle corriger.
	const ext = _ptDocs({}, champs({ posExt: [0, 2] }));
	assert.match(_ptValider(ext, 'lieu:auxerre', GRILLE, [], true), /extérieure.*infranchissable/);
	const int = _ptDocs({}, champs({ posInt: [0, 4] }));
	assert.match(_ptValider(int, 'lieu:auxerre', GRILLE, [], true), /intérieure.*infranchissable/);
	const hors = _ptDocs({}, champs({ posInt: [99, 1] }));
	assert.match(_ptValider(hors, 'lieu:auxerre', GRILLE, [], true), /intérieure.*hors/);
});

t('le seuil est >= 1, celui du voile rouge — la case 9 le franchit', () => {
	// ⚠️ Même comportement que dev/test_connexions_client.js : « Bloqué (∞) » de la légende
	// est un COÛT infini, pas un mur. Seul 0 arrête. Épinglé ici pour que le flux porte ne
	// se mette pas à refuser ce que la visée, elle, accepte au clic.
	const docs = _ptDocs({}, champs({ posExt: [3, 3] }));
	assert.strictEqual(_ptValider(docs, 'lieu:auxerre', GRILLE, [], true), '');
});

t('deux cases identiques sont refusées', () => {
	const docs = _ptDocs({}, champs({ posExt: [4, 2], posInt: [4, 2] }));
	assert.match(_ptValider(docs, 'lieu:auxerre', GRILLE, [], true), /identiques/);
});

t('en création, un seul des cinq ids déjà pris suffit à refuser', () => {
	const docs = _ptDocs({}, champs());
	for (const d of docs) {
		assert.match(_ptValider(docs, 'lieu:auxerre', GRILLE, [d._id], true), /existe déjà/);
	}
	// En édition les ids sont gelés : se les voir refuser serait absurde.
	assert.strictEqual(_ptValider(docs, 'lieu:auxerre', GRILLE, docs.map(d => d._id), false), '');
});

t('sans cité, on refuse', () => {
	const docs = _ptDocs({}, champs());
	assert.match(_ptValider(docs, '', GRILLE, [], true), /cité/i);
});

// ── _ptPaireDe ───────────────────────────────────────────────────────────────
const CONNEXIONS = (() => {
	const ex = existantsRef();
	return [
		ex.linkExt, ex.linkInt, ex.linkPassage,
		// Du bruit : d'autres connexions de la cité, qui ne doivent rien perturber.
		{ _id: 'link:boutique', type: 'connection', nodes: [{ lieu: 'lieu:auxerre', pos: [1, 1] }, { lieu: 'lieu:boutique', pos: [0, 0] }] },
	];
})();

t('la paire se reconstitue depuis l_EXTÉRIEUR comme depuis l_INTÉRIEUR', () => {
	const attendu = {
		extId: 'lieu:auxerre_porte_douve_exterieur01',
		intId: 'lieu:auxerre_porte_douve_interieur01',
	};
	for (const depuis of [attendu.extId, attendu.intId]) {
		const p = _ptPaireDe(CONNEXIONS, depuis, 'lieu:auxerre');
		assert.ok(p, 'paire trouvée depuis ' + depuis);
		assert.strictEqual(p.extId, attendu.extId);
		assert.strictEqual(p.intId, attendu.intId);
		assert.strictEqual(p.linkPassage._id, 'link:auxerre_porte_douve_interieur_exterieur01');
		assert.strictEqual(p.linkExt._id, 'link:auxerre_poste_de_garde_tour_porte_douve_exterieur01');
		assert.strictEqual(p.linkInt._id, 'link:auxerre_poste_de_garde_tour_porte_douve_interieur01');
	}
});

t('un lieu sans connexion de passage ne donne aucune paire', () => {
	assert.strictEqual(_ptPaireDe(CONNEXIONS, 'lieu:boutique', 'lieu:auxerre'), null);
});

t('une paire dont il manque un lien carte est refusée', () => {
	const ex = existantsRef();
	const amputee = [ex.linkExt, ex.linkPassage];   // le lien carte intérieur manque
	assert.strictEqual(_ptPaireDe(amputee, ex.ext._id, 'lieu:auxerre'), null);
});

t('un côté indécidable refuse la paire plutôt que de deviner', () => {
	// Fail-closed : rouvrir le formulaire risquerait d'intervertir les deux côtés.
	const a = 'lieu:auxerre_porte_nord_a', b = 'lieu:auxerre_porte_nord_b';
	const conns = [
		{ _id: 'link:a', type: 'connection', nodes: [{ lieu: 'lieu:auxerre', pos: [1, 1] }, { lieu: a, pos: [0, 0] }] },
		{ _id: 'link:b', type: 'connection', nodes: [{ lieu: 'lieu:auxerre', pos: [2, 2] }, { lieu: b, pos: [0, 0] }] },
		{ _id: 'link:p', type: 'connection', nodes: [{ lieu: a, pos: [0, 0] }, { lieu: b, pos: [0, 0] }] },
	];
	assert.strictEqual(_ptPaireDe(conns, a, 'lieu:auxerre'), null);
});

// ── _ptImagesLibres ──────────────────────────────────────────────────────────
// Noms RÉELS du disque : familles variées, noms sans famille, graphie « interieure », .jpg.
const IMAGES_PORTES = [
	'porte_de_ville_douves_exterieur01.png', 'porte_de_ville_pont_exterieur02.png',
	'porte_de_ville_route_interieur01.png', 'porte_de_ville_lutece_exterieur.jpg',
	'porte_de_ville_exterieur01.jpg', 'porte_de_ville_interieure02.jpg',
	'porte_de_ville_douves_interieur03.png', 'auxerre.png', 'grande_porte_exterieur.png',
];

t('toutes les images porte_de_ville* du bon côté, SANS filtre de famille', () => {
	assert.deepStrictEqual(_ptImagesLibres(IMAGES_PORTES, 'exterieur', []), [
		'porte_de_ville_douves_exterieur01.png', 'porte_de_ville_pont_exterieur02.png',
		'porte_de_ville_lutece_exterieur.jpg', 'porte_de_ville_exterieur01.jpg',
	]);
	assert.deepStrictEqual(_ptImagesLibres(IMAGES_PORTES, 'interieur', []), [
		'porte_de_ville_route_interieur01.png', 'porte_de_ville_interieure02.jpg',
		'porte_de_ville_douves_interieur03.png',
	], 'la graphie « interieure » est reconnue');
});

t('les images déjà prises sont écartées ; hors porte_de_ville*, rien n’est proposé', () => {
	assert.deepStrictEqual(
		_ptImagesLibres(IMAGES_PORTES, 'exterieur', ['porte_de_ville_douves_exterieur01.png', 'porte_de_ville_exterieur01.jpg']),
		['porte_de_ville_pont_exterieur02.png', 'porte_de_ville_lutece_exterieur.jpg']);
	assert.ok(!_ptImagesLibres(IMAGES_PORTES, 'exterieur', []).includes('grande_porte_exterieur.png'));
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
