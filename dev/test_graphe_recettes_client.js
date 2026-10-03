// dev/test_graphe_recettes_client.js
//
// Tests d'EXÉCUTION du JavaScript du GRAPHE DES RECETTES
// (templates/admin_recettes_graphe.html, écran /admin/recettes-graphe).
//
//   node dev/test_graphe_recettes_client.js     # sort en code 1 au premier échec
//
// POURQUOI : toute la logique de l'écran (voisinage, filtres, rôles, recherche, état ↔ URL,
// disposition en colonnes) vit dans le template, hors de portée de pytest. Le graphe, lui,
// est produit par utils/graphe_recettes.py (verrouillé par tests/test_graphe_recettes.py) :
// le jeu d'essai ci-dessous en reprend la FORME (nœuds item/famille, arêtes recette/membre).
//
// MÉTHODE : identique à dev/test_dialogues_client.js — extraction par nom (accolades
// équilibrées), exécution dans le realm du test (`runInThisContext`). Les constantes de tête
// (PROFONDEUR_*, MAX_MEMBRES_DEPLIES, _URL_*) sont extraites de la même façon.
//
// HORS DE PORTÉE (à vérifier dans un navigateur, cf. CLAUDE.md §15) : le rendu Cytoscape,
// le tactile, la fiche (bottom-sheet) et le tiroir de filtres.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_recettes_graphe.html');
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

function extraireConst(nom) {
	const m = js.match(new RegExp('^const ' + nom + ' = [^\\n]*$', 'm'));
	assert.ok(m, 'constante ' + nom + ' introuvable dans le template');
	return m[0].replace(/^const /, 'globalThis.');
}

const FONCTIONS = ['filtresParDefaut', 'normaliserRecherche', 'indexerGraphe', 'roleNoeud',
	'areteVisible', 'noeudVisible', '_restreindreAbsents', 'filtrerGraphe', '_parcourir',
	'voisinage', 'disposerCouches', 'rangsGlobaux', 'chercherNoeuds', 'chercherMetiers', 'valeursFiltres',
	'recettesDe', 'compterFiltresActifs', 'etatVersUrl', 'urlVersEtat',
	'estOrphelin', 'orphelins', 'rangsOrphelins'];
const CONSTANTES = ['PROFONDEUR_MAX', 'PROFONDEUR_DEFAUT', 'MAX_MEMBRES_DEPLIES', '_URL_LISTES', '_URL_BOOLS', 'MODES', 'CHOIX_SUR_MESURE'];
vm.runInThisContext(CONSTANTES.map(extraireConst).join('\n') + '\n'
	+ FONCTIONS.map(n => extraire(n) + '\nglobalThis.' + n + ' = ' + n + ';').join('\n'));

// ── Jeu d'essai ────────────────────────────────────────────────────────────────
// minerai ─2→ lingot ─1→ épée ─1→ épée_fine (forge)          lingot ─1→ casque (forge)
// ⟨cuir⟩ ─1→ ceinture (tannerie) ; peau_loup, peau_ours ∈ ⟨cuir⟩
// essence ─1→ potion (alchimie, sur_commande) ; herbe ─1→ tisane (auberge, terroir)
// fantome : produit d'une recette sans doc (absent) ; galet : isolé (seulement membre de
// ⟨pierre⟩, sous-catégorie `hors_recette` : aucune recette ne la cite).
// Cycle : cendre ─1→ braise ─1→ cendre (fourneau).
// Sur-mesure : gemme ┄→ ⚒arme, gemme ┄→ ⚒armure, poudre ┄→ ⚒arme (arêtes `fabrication`).
function item(id, label, categorie, extra) {
	return Object.assign({ id, type: 'item', label, icon: '', categorie, sous_categorie: '', rarete: 'commun', absent: false }, extra || {});
}
function rec(rid, n, source, target, lieu, extra) {
	return Object.assign({ id: rid + '|' + n, source, target, kind: 'recette', recette: rid,
		lieu_categorie: lieu, lieu_portee: '', quantite: 1, quantite_produite: 1, sur_commande: false }, extra || {});
}
const GRAPHE = {
	nodes: [
		item('item:minerai', 'Minerai de fer', 'matiere'),
		item('item:lingot', 'Lingot', 'matiere'),
		item('item:epee', 'Épée', 'arme', { rarete: 'rare' }),
		item('item:epee_fine', 'Épée fine', 'arme', { rarete: 'rare' }),
		item('item:casque', 'Casque', 'armure'),
		item('item:peau_loup', 'Peau de loup', 'matiere', { sous_categorie: 'cuir' }),
		item('item:peau_ours', 'Peau d’ours', 'matiere', { sous_categorie: 'cuir' }),
		item('item:ceinture', 'Ceinture', 'armure'),
		item('item:essence', 'Essence', 'matiere'),
		item('item:potion', 'Potion', 'consommable'),
		item('item:herbe', 'Herbe', 'matiere'),
		item('item:tisane', 'Tisane', 'consommable'),
		item('item:fantome', 'fantome', '', { rarete: '', absent: true }),
		item('item:galet', 'Galet', 'matiere', { sous_categorie: 'pierre' }),
		item('item:cendre', 'Cendre', 'matiere'),
		item('item:braise', 'Braise', 'matiere'),
		{ id: 'sc:cuir', type: 'famille', label: 'cuir', icon: '', categorie: '', sous_categorie: 'cuir', rarete: '', absent: false },
		{ id: 'sc:pierre', type: 'famille', label: 'pierre', icon: '', categorie: '', sous_categorie: 'pierre', rarete: '', absent: false, hors_recette: true },
		item('item:gemme', 'Gemme', 'matiere', { matiere_fabrication: true, fabrication_nom: 'serti' }),
		item('item:poudre', 'Poudre', 'matiere', { matiere_fabrication: true }),
		{ id: 'fab:arme', type: 'piece', label: 'arme', icon: '⚒', categorie: '', sous_categorie: '', rarete: '', absent: false, pieces: ['item:epee', 'item:epee_fine'] },
		{ id: 'fab:armure', type: 'piece', label: 'armure', icon: '⚒', categorie: '', sous_categorie: '', rarete: '', absent: false, pieces: ['item:casque', 'item:ceinture'] },
	],
	edges: [
		rec('recette:lingot', 0, 'item:minerai', 'item:lingot', 'forge', { quantite: 2 }),
		rec('recette:epee', 0, 'item:lingot', 'item:epee', 'forge'),
		rec('recette:epee_fine', 0, 'item:epee', 'item:epee_fine', 'forge'),
		rec('recette:casque', 0, 'item:lingot', 'item:casque', 'forge'),
		rec('recette:ceinture', 0, 'sc:cuir', 'item:ceinture', 'tannerie'),
		{ id: 'item:peau_loup>sc:cuir', source: 'item:peau_loup', target: 'sc:cuir', kind: 'membre' },
		{ id: 'item:peau_ours>sc:cuir', source: 'item:peau_ours', target: 'sc:cuir', kind: 'membre' },
		{ id: 'item:galet>sc:pierre', source: 'item:galet', target: 'sc:pierre', kind: 'membre' },
		rec('recette:potion', 0, 'item:essence', 'item:potion', 'alchimie', { sur_commande: true }),
		rec('recette:tisane', 0, 'item:herbe', 'item:tisane', 'auberge', { lieu_portee: 'lieu:val' }),
		rec('recette:fantome', 0, 'item:herbe', 'item:fantome', 'auberge'),
		rec('recette:braise', 0, 'item:cendre', 'item:braise', 'fourneau'),
		rec('recette:cendre', 0, 'item:braise', 'item:cendre', 'fourneau'),
		{ id: 'item:gemme~fab:arme', source: 'item:gemme', target: 'fab:arme', kind: 'fabrication' },
		{ id: 'item:gemme~fab:armure', source: 'item:gemme', target: 'fab:armure', kind: 'fabrication' },
		{ id: 'item:poudre~fab:arme', source: 'item:poudre', target: 'fab:arme', kind: 'fabrication' },
		// Arête vers un nœud inconnu : ignorée par l'index, jamais une exception.
		rec('recette:orpheline', 0, 'item:inconnu', 'item:lingot', 'forge'),
	],
};
const IDX = indexerGraphe(GRAPHE);
const F = () => filtresParDefaut();
const ids = (v) => v.noeuds.map(n => n.id);

let ok = 0;
function test(nom, fn) {
	try { fn(); ok++; } catch (err) { console.error('ÉCHEC — ' + nom + '\n', err.message); process.exit(1); }
}

// ── Index ─────────────────────────────────────────────────────────────────────
test('index : arête vers un nœud inconnu ignorée, recettes regroupées', () => {
	assert.ok(!IDX.aretes['recette:orpheline|0']);
	assert.deepStrictEqual(IDX.recettes['recette:lingot'].entrees, [{ id: 'item:minerai', quantite: 2 }]);
	assert.strictEqual(IDX.lieux.forge, 4);
});

// ── Rôles ─────────────────────────────────────────────────────────────────────
test('rôles : brut / intermédiaire / fini / isolé / famille, membre compte comme « sert »', () => {
	assert.strictEqual(roleNoeud(IDX, 'item:minerai'), 'brut');
	assert.strictEqual(roleNoeud(IDX, 'item:lingot'), 'intermediaire');
	assert.strictEqual(roleNoeud(IDX, 'item:epee_fine'), 'fini');
	assert.strictEqual(roleNoeud(IDX, 'item:galet'), 'isole');
	assert.strictEqual(roleNoeud(IDX, 'sc:cuir'), 'famille');
	assert.strictEqual(roleNoeud(IDX, 'item:peau_loup'), 'brut');
	assert.strictEqual(roleNoeud(IDX, 'item:inexistant'), '');
});

// ── Orphelins ─────────────────────────────────────────────────────────────────
// Orphelins du jeu d'essai : galet (membre d'une famille `hors_recette` seulement), gemme et
// poudre (liens de FABRICATION seulement : le rôle ne parle que des recettes).
const ORPHELINS = ['item:galet', 'item:gemme', 'item:poudre'];

test('orphelins : items ni produits ni utilisés, jamais une famille ni un absent', () => {
	assert.deepStrictEqual(orphelins(IDX, F()), ORPHELINS);
	for (const id of ORPHELINS) assert.ok(estOrphelin(IDX, id), id);
	for (const id of ['item:minerai', 'item:epee_fine', 'item:peau_loup', 'item:fantome', 'sc:pierre', 'fab:arme', 'item:inexistant']) {
		assert.ok(!estOrphelin(IDX, id), id);
	}
});

test('orphelins : les filtres d’item s’appliquent, ceux de recette non', () => {
	assert.deepStrictEqual(orphelins(IDX, Object.assign(F(), { raretes: ['rare'] })), []);
	assert.deepStrictEqual(orphelins(IDX, Object.assign(F(), { sousCategories: ['pierre'] })), ['item:galet']);
	assert.deepStrictEqual(orphelins(IDX, Object.assign(F(), { lieux: ['forge'] })), ORPHELINS);
});

test('exergue : réseau complet + orphelins, malgré « masquer les isolés »', () => {
	const sans = filtrerGraphe(IDX, F());
	assert.ok(!sans.ids.includes('item:galet'));
	const avec = filtrerGraphe(IDX, Object.assign(F(), { exergueOrphelins: true }));
	assert.deepStrictEqual(avec.aretes, sans.aretes);
	assert.deepStrictEqual(avec.ids, [...new Set([...sans.ids, ...ORPHELINS])].sort());
	// Sans les liens de fabrication, gemme et poudre ne restent dans la vue que par l'exergue.
	const f = Object.assign(F(), { fabrications: false, exergueOrphelins: true });
	for (const id of ORPHELINS) assert.ok(filtrerGraphe(IDX, f).ids.includes(id), id);
});

test('orphelins : une colonne par catégorie, la plus fournie d’abord', () => {
	const g = { nodes: [item('item:a', 'A', 'outil'), item('item:b', 'B', 'matiere'), item('item:c', 'C', 'matiere')], edges: [] };
	const idx = indexerGraphe(g);
	const r = Object.fromEntries(rangsOrphelins(idx, orphelins(idx, F())).map(n => [n.id, n.rang]));
	assert.deepStrictEqual(r, { 'item:a': 1, 'item:b': 0, 'item:c': 0 });
});

// ── Voisinage ─────────────────────────────────────────────────────────────────
test('voisinage : profondeurs amont/aval respectées', () => {
	const v = voisinage(IDX, 'item:lingot', 1, 1, F());
	assert.deepStrictEqual(ids(v), ['item:casque', 'item:epee', 'item:lingot', 'item:minerai']);
	const v2 = voisinage(IDX, 'item:lingot', 0, 2, F());
	assert.deepStrictEqual(ids(v2), ['item:casque', 'item:epee', 'item:epee_fine', 'item:lingot']);
	const v0 = voisinage(IDX, 'item:lingot', 0, 0, F());
	assert.deepStrictEqual(ids(v0), ['item:lingot']);
	assert.deepStrictEqual(v.aretes, ['recette:casque|0', 'recette:epee|0', 'recette:lingot|0']);
});

test('voisinage : rangs signés (amont négatif, aval positif, centre 0)', () => {
	const v = voisinage(IDX, 'item:lingot', 2, 2, F());
	const r = Object.fromEntries(v.noeuds.map(n => [n.id, n.rang]));
	assert.deepStrictEqual(r, { 'item:casque': 1, 'item:epee': 1, 'item:epee_fine': 2, 'item:lingot': 0, 'item:minerai': -1 });
});

test('voisinage : passer par une famille ne coûte pas de profondeur', () => {
	// peau_loup → ⟨cuir⟩ → ceinture : la ceinture est à distance 1 de la peau.
	const v = voisinage(IDX, 'item:peau_loup', 0, 1, F());
	assert.deepStrictEqual(ids(v), ['item:ceinture', 'item:peau_loup', 'sc:cuir']);
	const p = Object.fromEntries(v.noeuds.map(n => [n.id, n.profondeur]));
	assert.strictEqual(p['item:ceinture'], 1);
	// En remontant de la ceinture, profondeur 1 montre la famille ET ses membres.
	const h = voisinage(IDX, 'item:ceinture', 1, 0, F());
	assert.deepStrictEqual(ids(h), ['item:ceinture', 'item:peau_loup', 'item:peau_ours', 'sc:cuir']);
});

test('voisinage : une famille trop peuplée reste repliée, sauf au centre', () => {
	const h = voisinage(IDX, 'item:ceinture', 1, 0, F(), 1);
	assert.deepStrictEqual(ids(h), ['item:ceinture', 'sc:cuir']);
	assert.deepStrictEqual(h.replies, { 'sc:cuir': 2 });
	const c = voisinage(IDX, 'sc:cuir', 1, 0, F(), 1);
	assert.deepStrictEqual(ids(c), ['item:peau_loup', 'item:peau_ours', 'sc:cuir']);
	assert.deepStrictEqual(c.replies, {});
});

test('voisinage : un cycle ne boucle pas', () => {
	const v = voisinage(IDX, 'item:cendre', 5, 5, F());
	assert.deepStrictEqual(ids(v), ['item:braise', 'item:cendre']);
});

test('voisinage : centre inconnu → vide', () => {
	assert.deepStrictEqual(voisinage(IDX, 'item:rien', 2, 2, F()), { noeuds: [], aretes: [], replies: {} });
});

test('voisinage : un nœud filtré n’est ni montré ni traversé, le centre reste', () => {
	const f = F(); f.categories = ['matiere'];
	const v = voisinage(IDX, 'item:lingot', 2, 2, f);
	assert.deepStrictEqual(ids(v), ['item:lingot', 'item:minerai']);
	const g = F(); g.categories = ['arme'];
	const w = voisinage(IDX, 'item:minerai', 0, 3, g);
	assert.deepStrictEqual(ids(w), ['item:minerai']);   // le lingot coupe le chemin vers l'épée
});

// ── Filtres ───────────────────────────────────────────────────────────────────
test('filtres par défaut : isolés masqués, sur mesure masqué, terroir montré', () => {
	const g = filtrerGraphe(IDX, F());
	assert.ok(!g.ids.includes('item:galet'));
	assert.ok(!g.ids.includes('item:potion') && !g.ids.includes('item:essence'));
	assert.ok(g.aretes.includes('recette:tisane|0'));
	assert.ok(g.ids.includes('sc:cuir'));
});

test('filtre sur mesure / terroir', () => {
	const f = F(); f.surMesure = true; f.terroir = false;
	const g = filtrerGraphe(IDX, f);
	assert.ok(g.aretes.includes('recette:potion|0'));
	assert.ok(!g.aretes.includes('recette:tisane|0') && !g.ids.includes('item:tisane'));
});

test('filtre isolés désactivé : le galet apparaît', () => {
	const f = F(); f.masquerIsoles = false;
	assert.ok(filtrerGraphe(IDX, f).ids.includes('item:galet'));
});

test('filtre métier : seules ses recettes, famille sans recette visible retirée', () => {
	const f = F(); f.lieux = ['forge'];
	const g = filtrerGraphe(IDX, f);
	assert.deepStrictEqual(g.ids, ['item:casque', 'item:epee', 'item:epee_fine', 'item:lingot', 'item:minerai']);
	assert.ok(!g.ids.includes('sc:cuir'));
});

test('filtre familles : décoché, plus de famille ni de membre orphelin', () => {
	const f = F(); f.familles = false;
	const g = filtrerGraphe(IDX, f);
	assert.ok(!g.ids.includes('sc:cuir') && !g.ids.includes('item:peau_loup') && !g.ids.includes('item:ceinture'));
});

test('filtres rareté / rôle / sous-catégorie, combinés', () => {
	const f = F(); f.raretes = ['rare'];
	assert.deepStrictEqual(filtrerGraphe(IDX, f).ids, ['item:epee', 'item:epee_fine']);
	const r = F(); r.roles = ['fini']; r.masquerIsoles = false;
	assert.deepStrictEqual(filtrerGraphe(IDX, r).ids,
		// la potion reste : isolés montrés, et son rôle est global (sa recette sur mesure compte)
		// les nœuds de structure (familles, ⚒ pièces) ne passent pas par les filtres d'item
		['fab:arme', 'fab:armure', 'item:casque', 'item:ceinture', 'item:epee_fine', 'item:fantome', 'item:potion', 'item:tisane', 'sc:cuir']);
	const s = F(); s.sousCategories = ['cuir'];
	assert.deepStrictEqual(filtrerGraphe(IDX, s).ids, ['item:peau_loup', 'item:peau_ours', 'sc:cuir']);
	const c = F(); c.categories = ['arme']; c.raretes = ['commun'];
	assert.deepStrictEqual(filtrerGraphe(IDX, c).ids, []);
});

test('diagnostic absents : nœud absent et ses voisins seulement', () => {
	const f = F(); f.absentsSeuls = true;
	assert.deepStrictEqual(filtrerGraphe(IDX, f).ids, ['item:fantome', 'item:herbe']);
	const v = voisinage(IDX, 'item:herbe', 1, 1, f);
	assert.deepStrictEqual(ids(v), ['item:fantome', 'item:herbe']);
});

test('compte des filtres actifs', () => {
	assert.strictEqual(compterFiltresActifs(F()), 0);
	const f = F(); f.lieux = ['forge']; f.surMesure = true; f.familles = false;
	assert.strictEqual(compterFiltresActifs(f), 3);
});

test('valeurs de filtres relues du graphe, triées par effectif', () => {
	const v = valeursFiltres(IDX);
	const nbMatieres = GRAPHE.nodes.filter(n => n.type === 'item' && n.categorie === 'matiere').length;
	assert.deepStrictEqual(v.categories[0], ['matiere', nbMatieres]);
	assert.ok(v.categories.some(([c]) => c === ''));       // l'item absent sans catégorie
	assert.deepStrictEqual(v.lieux[0], ['forge', 4]);
	assert.deepStrictEqual(v.sousCategories.find(([s]) => s === 'cuir'), ['cuir', 2]);
});

// ── Recherche ─────────────────────────────────────────────────────────────────
test('normalisation : accents, casse, séparateurs', () => {
	assert.strictEqual(normaliserRecherche('  Épée_Fine-de:Ours '), 'epee fine de ours');
	assert.strictEqual(normaliserRecherche(null), '');
});

test('recherche : accents/casse ignorés, ordre de pertinence', () => {
	assert.deepStrictEqual(chercherNoeuds(IDX, 'EPEE').map(n => n.id), ['item:epee', 'item:epee_fine']);
	assert.deepStrictEqual(chercherNoeuds(IDX, 'loup').map(n => n.id), ['item:peau_loup']);
	// sous-catégorie et id : la famille d'abord (libellé exact), puis les membres.
	const cuir = chercherNoeuds(IDX, 'cuir').map(n => n.id);
	assert.strictEqual(cuir[0], 'sc:cuir');
	assert.deepStrictEqual(cuir.slice(1).sort(), ['item:peau_loup', 'item:peau_ours']);
	assert.deepStrictEqual(chercherNoeuds(IDX, ''), []);
	assert.strictEqual(chercherNoeuds(IDX, 'e', null, 2).length, 2);
});

test('recherche restreinte à la vue (surlignage)', () => {
	assert.deepStrictEqual(chercherNoeuds(IDX, 'epee', new Set(['item:epee_fine', 'item:lingot'])).map(n => n.id), ['item:epee_fine']);
});

test('recherche de métier', () => {
	assert.deepStrictEqual(chercherMetiers(IDX, 'FORG'), [{ lieu: 'forge', n: 4 }]);
	assert.deepStrictEqual(chercherMetiers(IDX, ''), []);
});

// ── Recettes d'un nœud ────────────────────────────────────────────────────────
test('recettesDe : produit par / sert à (direct et via famille) / membres', () => {
	const l = recettesDe(IDX, 'item:lingot');
	assert.deepStrictEqual(l.produitPar.map(r => r.id), ['recette:lingot']);
	assert.deepStrictEqual(l.sertA.map(x => x.recette.id), ['recette:casque', 'recette:epee']);
	const p = recettesDe(IDX, 'item:peau_ours');
	assert.deepStrictEqual(p.sertA.map(x => [x.recette.id, x.via]), [['recette:ceinture', 'sc:cuir']]);
	assert.deepStrictEqual(recettesDe(IDX, 'sc:cuir').membres, ['item:peau_loup', 'item:peau_ours']);
});

// ── Disposition ───────────────────────────────────────────────────────────────
test('disposition : colonnes ordonnées par rang, axes échangés en portrait', () => {
	const v = voisinage(IDX, 'item:lingot', 2, 2, F());
	const pos = disposerCouches(v.noeuds, IDX, false);
	assert.ok(pos['item:minerai'].x < pos['item:lingot'].x && pos['item:lingot'].x < pos['item:epee'].x);
	assert.ok(pos['item:epee'].x < pos['item:epee_fine'].x);
	assert.strictEqual(pos['item:epee'].x, pos['item:casque'].x);
	assert.notStrictEqual(pos['item:epee'].y, pos['item:casque'].y);
	const vert = disposerCouches(v.noeuds, IDX, true);
	assert.ok(vert['item:minerai'].y < vert['item:lingot'].y && vert['item:lingot'].y < vert['item:epee'].y);
	// Idempotente (rendu stable, CLAUDE.md §17).
	assert.deepStrictEqual(disposerCouches(v.noeuds, IDX, false), pos);
});

test('disposition : une colonne trop haute se replie sans chevauchement', () => {
	const nodes = [{ id: 'c', type: 'item', label: 'c', categorie: '' }];
	const edges = [];
	for (let i = 0; i < 40; i++) {
		nodes.push({ id: 'n' + i, type: 'item', label: 'n' + String(i).padStart(2, '0'), categorie: '' });
		edges.push({ id: 'e' + i, source: 'n' + i, target: 'c', kind: 'recette', recette: 'r' + i, lieu_categorie: 'x', quantite: 1 });
	}
	const idx = indexerGraphe({ nodes, edges });
	const v = voisinage(idx, 'c', 1, 0, F());
	const pos = disposerCouches(v.noeuds, idx, false);
	const cles = new Set(Object.values(pos).map(p => p.x + ',' + p.y));
	assert.strictEqual(cles.size, 41);
	const xs = new Set(v.noeuds.filter(n => n.id !== 'c').map(n => pos[n.id].x));
	assert.ok(xs.size > 1);
	assert.ok(Math.max(...xs) < pos.c.x);
});

test('rangs globaux : plus long chemin, cycle et nœud isolé placés sans boucler', () => {
	const g = filtrerGraphe(IDX, Object.assign(F(), { masquerIsoles: false }));
	const r = Object.fromEntries(rangsGlobaux(g.ids, g.aretes.map(id => IDX.aretes[id])).map(n => [n.id, n.rang]));
	assert.strictEqual(r['item:minerai'], 0);
	assert.strictEqual(r['item:lingot'], 1);
	assert.strictEqual(r['item:epee_fine'], 3);
	assert.strictEqual(r['item:galet'], 0);
	assert.strictEqual(r['sc:cuir'], 1);
	assert.strictEqual(r['item:ceinture'], 2);
	// cendre ⇄ braise : l'un à 0, l'autre juste après.
	assert.deepStrictEqual([r['item:braise'], r['item:cendre']].sort(), [0, 1]);
	assert.strictEqual(Object.keys(r).length, g.ids.length);
});

test('disposition : hauteur de colonne forcée (réseau complet)', () => {
	const g = filtrerGraphe(IDX, Object.assign(F(), { masquerIsoles: false }));
	const rangs = rangsGlobaux(g.ids, g.aretes.map(id => IDX.aretes[id]));
	const pos = disposerCouches(rangs, IDX, false, 2);
	assert.strictEqual(new Set(Object.values(pos).map(p => p.x + ',' + p.y)).size, g.ids.length);
});

// ── Fabrication sur mesure ────────────────────────────────────────────────────
test('fabrication : affichée par défaut, masquée par l’interrupteur', () => {
	const g = filtrerGraphe(IDX, F());
	assert.ok(g.aretes.includes('item:gemme~fab:arme') && g.ids.includes('fab:arme') && g.ids.includes('item:gemme'));
	const f = F(); f.fabrications = false;
	const h = filtrerGraphe(IDX, f);
	assert.ok(!h.aretes.some(id => id.includes('~fab:')));
	assert.ok(!h.ids.includes('fab:arme') && !h.ids.includes('fab:armure'));
	assert.ok(!h.ids.includes('item:gemme'));            // plus aucun lien visible : masquée
	assert.ok(h.ids.includes('item:lingot'));             // les recettes, elles, restent
	const v = voisinage(IDX, 'item:gemme', 0, 2, f);
	assert.deepStrictEqual(v.noeuds.map(n => n.id), ['item:gemme']);
});

test('fabrication : un filtre de métier masque les liens (ils ne sont la recette d’aucun métier)', () => {
	const f = F(); f.lieux = ['forge'];
	const g = filtrerGraphe(IDX, f);
	assert.ok(!g.ids.includes('fab:arme') && !g.aretes.some(id => id.includes('~fab:')));
});

test('fabrication : voisinage, coût d’une profondeur, repli des matières d’une ⚒ famille', () => {
	const v = voisinage(IDX, 'item:gemme', 0, 1, F());
	assert.deepStrictEqual(ids(v), ['fab:arme', 'fab:armure', 'item:gemme']);
	const p = Object.fromEntries(v.noeuds.map(n => [n.id, n.profondeur]));
	assert.strictEqual(p['fab:arme'], 1);
	assert.deepStrictEqual(ids(voisinage(IDX, 'item:gemme', 0, 0, F())), ['item:gemme']);
	// Au centre, toutes ses matières, même au-delà du plafond de repli (une ⚒ famille n'a pas
	// d'arête sortante : on ne la remonte jamais hors centre, le repli ne la concerne pas).
	assert.deepStrictEqual(ids(voisinage(IDX, 'fab:arme', 1, 0, F(), 1)), ['fab:arme', 'item:gemme', 'item:poudre']);
});

test('fabrication : ne change pas les rôles, recettesDe expose les deux sens', () => {
	assert.strictEqual(roleNoeud(IDX, 'item:gemme'), 'isole');
	assert.strictEqual(roleNoeud(IDX, 'fab:arme'), 'piece');
	assert.deepStrictEqual(recettesDe(IDX, 'item:gemme').faconne, ['fab:arme', 'fab:armure']);
	assert.deepStrictEqual(recettesDe(IDX, 'fab:arme').matieresFab, ['item:gemme', 'item:poudre']);
	assert.deepStrictEqual(recettesDe(IDX, 'item:lingot').faconne, []);
});

test('fabrication : recherche par famille, filtre compté, URL', () => {
	assert.strictEqual(chercherNoeuds(IDX, 'armure')[0].id, 'fab:armure');
	const f = F(); f.fabrications = false;
	assert.strictEqual(compterFiltresActifs(f), 1);
	const etat = { item: 'fab:arme', mode: 'voisinage', amont: 2, aval: 2, q: '', filtres: f };
	assert.ok(etatVersUrl(etat).includes('fabr=0'));
	assert.deepStrictEqual(urlVersEtat(etatVersUrl(etat)), etat);
});

// ── Toutes les sous-catégories (familles `hors_recette`) ──────────────────────
test('sous-catégorie hors recette : masquée par défaut, n’en fait pas une matière « brute »', () => {
	assert.strictEqual(roleNoeud(IDX, 'item:galet'), 'isole');
	const g = filtrerGraphe(IDX, F());
	assert.ok(!g.ids.includes('sc:pierre') && !g.ids.includes('item:galet'));
	assert.ok(!voisinage(IDX, 'item:galet', 0, 2, F()).noeuds.some(n => n.id === 'sc:pierre'));
	// Au centre, elle montre ses membres même bascule décochée.
	assert.deepStrictEqual(ids(voisinage(IDX, 'sc:pierre', 1, 0, F())), ['item:galet', 'sc:pierre']);
});

test('toutes les sous-catégories : nœuds et liens d’appartenance affichés', () => {
	const f = F(); f.toutesSousCategories = true;
	const g = filtrerGraphe(IDX, f);
	assert.ok(g.ids.includes('sc:pierre') && g.ids.includes('item:galet'));
	assert.ok(g.aretes.includes('item:galet>sc:pierre'));
	assert.deepStrictEqual(ids(voisinage(IDX, 'item:galet', 0, 1, f)), ['item:galet', 'sc:pierre']);
	// …indépendamment de la bascule des familles d'entrées de recette.
	f.familles = false;
	assert.ok(filtrerGraphe(IDX, f).ids.includes('sc:cuir'));
	// Un filtre de métier ne parle que de recettes : il les masque.
	const m = F(); m.toutesSousCategories = true; m.lieux = ['forge'];
	assert.ok(!filtrerGraphe(IDX, m).ids.includes('sc:pierre'));
});

test('toutes les sous-catégories : filtre compté, URL', () => {
	const f = F(); f.toutesSousCategories = true;
	assert.strictEqual(compterFiltresActifs(f), 1);
	const etat = { item: '', mode: 'complet', amont: 2, aval: 2, q: '', filtres: f };
	assert.ok(etatVersUrl(etat).includes('tsc=1'));
	assert.deepStrictEqual(urlVersEtat(etatVersUrl(etat)), etat);
});

// ── Filtre « Fabrication sur mesure » ───────────────────────────────────────────
// Concernés : gemme, poudre (matières) ; épée, épée fine, casque, ceinture (pièces des ⚒).
test('sur-mesure : matières et pièces indexées, une matière reste « matiere »', () => {
	assert.deepStrictEqual(IDX.surMesure, {
		'item:epee': 'piece', 'item:epee_fine': 'piece', 'item:casque': 'piece', 'item:ceinture': 'piece',
		'item:gemme': 'matiere', 'item:poudre': 'matiere',
	});
	const g = indexerGraphe({ nodes: [item('item:x', 'X', 'matiere', { matiere_fabrication: true }),
		{ id: 'fab:arme', type: 'piece', label: 'arme', pieces: ['item:x', 'item:fantome_hors_graphe'] }], edges: [] });
	assert.deepStrictEqual(g.surMesure, { 'item:x': 'matiere' });
});

test('sur-mesure : exclure / seulement filtrent les items, pas les familles ni les ⚒', () => {
	const base = Object.assign(F(), { masquerIsoles: false });
	const tous = filtrerGraphe(IDX, base).ids;
	const excl = filtrerGraphe(IDX, Object.assign({}, base, { surMesureItems: 'exclure' })).ids;
	const seul = filtrerGraphe(IDX, Object.assign({}, base, { surMesureItems: 'seulement' })).ids;
	const concernes = Object.keys(IDX.surMesure).sort();
	assert.deepStrictEqual(excl, tous.filter(id => !IDX.surMesure[id]));
	assert.deepStrictEqual(seul.filter(id => id.startsWith('item:')), concernes);
	assert.ok(seul.includes('fab:arme') && excl.includes('fab:arme'));
	// Combiné au mode orphelins : gemme et poudre sont les orphelins sur mesure.
	assert.deepStrictEqual(orphelins(IDX, Object.assign(F(), { surMesureItems: 'seulement' })), ['item:gemme', 'item:poudre']);
	assert.deepStrictEqual(orphelins(IDX, Object.assign(F(), { surMesureItems: 'exclure' })), ['item:galet']);
});

test('sur-mesure : voisinage, le centre reste même exclu', () => {
	const v = voisinage(IDX, 'item:lingot', 2, 2, Object.assign(F(), { surMesureItems: 'exclure' }));
	assert.deepStrictEqual(ids(v), ['item:lingot', 'item:minerai']);
});

test('sur-mesure : URL et compte des filtres', () => {
	for (const v of CHOIX_SUR_MESURE) {
		const f = F(); f.surMesureItems = v;
		const etat = { item: '', mode: 'voisinage', amont: PROFONDEUR_DEFAUT, aval: PROFONDEUR_DEFAUT, q: '', filtres: f };
		assert.strictEqual(etatVersUrl(etat), v ? 'fsm=' + v : '');
		assert.deepStrictEqual(urlVersEtat('?' + etatVersUrl(etat)), etat);
		assert.strictEqual(compterFiltresActifs(f), v ? 1 : 0);
	}
	assert.strictEqual(urlVersEtat('fsm=nimporte').filtres.surMesureItems, '');
});

// ── État ↔ URL ────────────────────────────────────────────────────────────────
test('URL : état par défaut → chaîne vide, aller-retour complet', () => {
	const defaut = { item: '', mode: 'voisinage', amont: PROFONDEUR_DEFAUT, aval: PROFONDEUR_DEFAUT, q: '', filtres: F() };
	assert.strictEqual(etatVersUrl(defaut), '');
	assert.deepStrictEqual(urlVersEtat(''), defaut);
	const f = F(); f.lieux = ['forge', 'tannerie']; f.roles = ['brut']; f.surMesure = true; f.masquerIsoles = false;
	f.categories = ['arme & armure'];
	const etat = { item: 'item:Épée', mode: 'complet', amont: 4, aval: 0, q: 'épée', filtres: f };
	assert.deepStrictEqual(urlVersEtat('?' + etatVersUrl(etat)), etat);
});

test('URL : mode orphelins et exergue en aller-retour', () => {
	const f = F(); f.exergueOrphelins = true;
	const etat = { item: '', mode: 'orphelins', amont: PROFONDEUR_DEFAUT, aval: PROFONDEUR_DEFAUT, q: '', filtres: f };
	assert.strictEqual(etatVersUrl(etat), 'mode=orphelins&orph=1');
	assert.deepStrictEqual(urlVersEtat('?' + etatVersUrl(etat)), etat);
	assert.strictEqual(compterFiltresActifs(f), 1);
	for (const m of MODES) assert.strictEqual(urlVersEtat('mode=' + m).mode, m);
});

test('URL : profondeurs bornées, valeurs invalides → défaut', () => {
	const e = urlVersEtat('amont=99&aval=-3&mode=n_importe');
	assert.strictEqual(e.amont, PROFONDEUR_MAX);
	assert.strictEqual(e.aval, 0);
	assert.strictEqual(e.mode, 'voisinage');
	assert.strictEqual(urlVersEtat('amont=abc').amont, PROFONDEUR_DEFAUT);
});

console.log(`OK — ${ok} tests du graphe des recettes passés.`);
