// dev/test_lieu_form_client.js
//
// Tests d'EXÉCUTION du formulaire de lieu de l'éditeur de carte
// (templates/admin_map_editor.html, mode Lieux → « ➕ Ajouter un lieu » / « ✏️ Éditer »).
//
//   node dev/test_lieu_form_client.js     # sort en code 1 au premier échec
//
// POURQUOI : `PUT /admin/doc` écrit le document ENTIER. Un formulaire d'édition qui
// reconstruirait le doc au lieu de le FUSIONNER effacerait, en silence et sans erreur,
// tout ce qu'il ne connaît pas : les stocks d'une boutique, son bloc `acces`, et surtout
// la `progeniture` d'un PNJ — la chaîne d'escorte de ses enfants (10 en base). Rien ne le
// signalerait avant qu'un joueur ne trouve plus la quête.
//
// La seconde classe de bug visée est le CATALOGUE DE CAPACITÉS : une capacité accordée
// par la catégorie ne peut pas être retirée (il n'existe aucun anti-tag), et les tags qui
// ne lui appartiennent pas doivent traverser intacts.
//
// MÉTHODE : celle de dev/test_resize_client.js — extraction par nom (accolades
// équilibrées) et exécution dans le realm du test (`runInThisContext`), pour que
// `deepStrictEqual` accepte les objets produits.
//
// HORS DE PORTÉE (à vérifier en jeu, cf. CLAUDE.md §15) : le rendu des cases, le grisage
// d'une capacité acquise, la confirmation de retrait d'un PNJ, et l'aller-retour réseau.
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

for (const f of ['_capaciteAccordee', '_capacitesDe', '_tagsApres', '_fusionLieu']) {
	vm.runInThisContext(extraire(f));
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Le catalogue tel que `utils/capacites.py` le sert. ⚠️ Recopié ici pour que le test
// affirme un comportement pour CE catalogue, sans dépendre d'un fichier Python : c'est
// `tests/test_capacites.py` qui verrouille l'accord entre la table et les vrais prédicats.
const CATALOGUE = [
	{ id: 'taverne', label: 'Taverne', tag: 'taverne',
	  categories: ['auberge'], sous_categories: [], note: '…' },
	{ id: 'montures', label: 'Étable', tag: 'montures',
	  categories: ['etable'], sous_categories: [], note: '…' },
	{ id: 'scriptorium', label: 'Scriptorium', tag: 'scriptorium',
	  categories: ['scriptorium'], sous_categories: [], note: '…' },
	{ id: 'recrutement', label: 'Recrutement', tag: 'recrutement',
	  categories: ['guilde_aventurier'], sous_categories: [], note: '…' },
	{ id: 'guilde', label: 'Maison de guilde', tag: 'guilde',
	  categories: ['guilde_aventurier', 'guilde_aventurier_comptoir',
				   'guilde_aventurier_exterieur', 'bureau_maitre_guilde'],
	  sous_categories: ['guilde_aventurier'], note: '…' },
];

// Champs par défaut d'un formulaire — surchargés au cas par cas.
function champs(over) {
	return Object.assign({
		label: 'Le Chaudron', image: 'auberge_europe01.png', categorie: 'auberge',
		capacites: {}, nuit_messages: [], montures: [], pnj: null,
	}, over || {});
}

console.log('\n── Capacités : ce que la catégorie accorde ──');

t('la catégorie accorde sa capacité', () => {
	assert.strictEqual(_capacitesDe({ categorie: 'auberge' }, CATALOGUE).taverne, true);
	assert.strictEqual(_capacitesDe({ categorie: 'etable' }, CATALOGUE).montures, true);
	assert.strictEqual(_capacitesDe({ categorie: 'boulangerie' }, CATALOGUE).taverne, false);
});

t('le tag accorde la capacité à n’importe quelle catégorie', () => {
	// C'est l'échappatoire annoncée par les docstrings du jeu : ouvrir une salle commune
	// à une halte ou une salle de guilde, sans une ligne de code.
	const caps = _capacitesDe({ categorie: 'chemin', tags: ['taverne'] }, CATALOGUE);
	assert.strictEqual(caps.taverne, true);
	assert.strictEqual(caps.montures, false);
});

t('la maison de guilde est accordée par QUATRE catégories et une sous-catégorie', () => {
	for (const c of ['guilde_aventurier', 'guilde_aventurier_comptoir',
					 'guilde_aventurier_exterieur', 'bureau_maitre_guilde']) {
		assert.strictEqual(_capacitesDe({ categorie: c }, CATALOGUE).guilde, true, c);
	}
	assert.strictEqual(
		_capacitesDe({ categorie: 'grotte', sous_categorie: 'guilde_aventurier' }, CATALOGUE).guilde,
		true);
});

t('un doc vide, nul ou sans tags ne fait rien lever', () => {
	for (const doc of [null, {}, { tags: null }, { categorie: null }]) {
		const caps = _capacitesDe(doc, CATALOGUE);
		assert.strictEqual(Object.keys(caps).length, CATALOGUE.length);
		assert.ok(Object.keys(caps).every(k => caps[k] === false));
	}
});

console.log('\n── Les tags écrits ──');

t('cocher une capacité pose son tag', () => {
	assert.deepStrictEqual(_tagsApres([], { taverne: true }, CATALOGUE, 'chemin'), ['taverne']);
});

t('décocher le retire', () => {
	assert.deepStrictEqual(_tagsApres(['taverne'], { taverne: false }, CATALOGUE, 'chemin'), []);
});

t('LE PIÈGE : un tag hors capacité survit toujours', () => {
	// `#bm-tags` écrit des tags de pondération de carte de combat sur le même champ.
	// Les perdre à l'édition d'un lieu changerait le tirage des cartes, sans symptôme.
	const avant = ['foret', 'taverne', 'riviere'];
	assert.deepStrictEqual(_tagsApres(avant, { taverne: false }, CATALOGUE, 'chemin'),
		['foret', 'riviere']);
	const apres = _tagsApres(avant, { taverne: true, montures: true }, CATALOGUE, 'chemin');
	assert.deepStrictEqual(apres.slice(0, 2), ['foret', 'riviere'], 'ordre d’origine conservé');
	assert.deepStrictEqual(apres.slice(2).sort(), ['montures', 'taverne']);
});

t('un tag redondant avec la catégorie n’est pas posé', () => {
	// L'auberge de référence (`lieu:auberge_de_la_tour_de_l_horloge`) ne porte aucun tag.
	assert.deepStrictEqual(_tagsApres([], { taverne: true }, CATALOGUE, 'auberge'), []);
	assert.deepStrictEqual(_tagsApres(['taverne'], { taverne: true }, CATALOGUE, 'auberge'), []);
});

console.log('\n── Fusion : la création ──');

t('sur une base vide, la fusion produit un doc de lieu minimal', () => {
	const doc = _fusionLieu({}, champs(), CATALOGUE);
	assert.deepStrictEqual(doc, {
		type: 'lieu', label: 'Le Chaudron',
		image: 'auberge_europe01.png', categorie: 'auberge',
	});
	// ⚠️ Exactement la forme de l'unique auberge du jeu : ni `pnj`, ni `tags`, ni stocks.
	assert.ok(!('pnj' in doc) && !('tags' in doc) && !('nuit_messages' in doc));
});

t('le récit de la nuit n’est écrit que s’il y a quelque chose à dire', () => {
	assert.ok(!('nuit_messages' in _fusionLieu({}, champs({ nuit_messages: [] }), CATALOGUE)));
	const doc = _fusionLieu({}, champs({ nuit_messages: ['une', 'deux'] }), CATALOGUE);
	assert.deepStrictEqual(doc.nuit_messages, ['une', 'deux']);
});

t('l’écurie part sur le TENANCIER, pas sur le bâtiment', () => {
	const doc = _fusionLieu({}, champs({
		categorie: 'etable',
		pnj: { character: 'pnj:marchand_etable', nom: 'Garin', portrait: 'g.png' },
		montures: ['espece:ane', 'espece:cheval'],
	}), CATALOGUE);
	assert.deepStrictEqual(doc.pnj, [{
		character: 'pnj:marchand_etable', nom: 'Garin', portrait: 'g.png',
		montures: ['espece:ane', 'espece:cheval'],
	}]);
	assert.ok(!('montures' in doc), 'l’écurie ne doit PAS être à la racine du lieu');
});

console.log('\n── Fusion : l’édition, et ce qu’elle NE DOIT PAS détruire ──');

// Une boutique réelle, réduite mais fidèle (cf. `lieu:l_enclume_du_rempart`).
function boutique() {
	return {
		_id: 'lieu:l_enclume_du_rempart', _rev: '7-abc', type: 'lieu',
		label: "L'Enclume du Rempart", image: 'armurerie_europe03.png',
		categorie: 'armurerie', lieu_parent: 'lieu:auxerre',
		pnj: [{
			character: 'pnj:marchand_armurerie', nom: 'George Dubois',
			portrait: 'marchand_george_dubois_armurerie.png',
			progeniture: { nom: 'Dubois', race: 'humain', enfants: [{ prenom: 'Colin' }] },
		}],
		stock_matieres: { acier: 85, fer: 144 },
		stock_vente: [{ item_id: 'item:Dague', qty: 3 }],
		stock_cible: { item: { 'item:manche': 12 } },
		acces: { gardien: 'pnj:x' },
		relation_lieu: 'lieu:autre',
		texte: 'Une ambiance.',
		sous_categorie: 'quelque_chose',
	};
}

t('LE PIÈGE : la progéniture d’un PNJ survit à une édition', () => {
	// Elle porte une chaîne d'escorte. La perdre casse la quête, sans erreur ni symptôme.
	const doc = _fusionLieu(boutique(), champs({
		label: 'La Forge Noire', image: 'armurerie_europe01.png', categorie: 'armurerie',
		pnj: { character: 'pnj:marchand_armurerie', nom: 'George Dubois', portrait: 'g.png' },
	}), CATALOGUE);
	assert.deepStrictEqual(doc.pnj[0].progeniture,
		{ nom: 'Dubois', race: 'humain', enfants: [{ prenom: 'Colin' }] });
});

t('stocks, accès, relation, texte et sous-catégorie survivent', () => {
	const avant = boutique();
	const doc = _fusionLieu(avant, champs({
		label: 'La Forge Noire', image: 'armurerie_europe01.png', categorie: 'armurerie',
		pnj: { character: 'pnj:marchand_armurerie', nom: 'X', portrait: 'g.png' },
	}), CATALOGUE);
	for (const cle of ['stock_matieres', 'stock_vente', 'stock_cible', 'acces',
					   'relation_lieu', 'texte', 'sous_categorie', 'lieu_parent']) {
		assert.deepStrictEqual(doc[cle], avant[cle], cle + ' perdu');
	}
});

t('un champ INCONNU du formulaire survit', () => {
	// La base a des champs que ce formulaire n'a jamais vus (`recrutement_restrictions`,
	// `nuit_messages` d'un autre auteur, un champ à venir).
	const avant = Object.assign(boutique(), { recrutement_restrictions: { nb: 1 }, futur: 42 });
	const doc = _fusionLieu(avant, champs({ categorie: 'armurerie',
		pnj: { character: 'pnj:marchand_armurerie', nom: 'X', portrait: 'g.png' } }), CATALOGUE);
	assert.deepStrictEqual(doc.recrutement_restrictions, { nb: 1 });
	assert.strictEqual(doc.futur, 42);
});

t('l’_id ne change JAMAIS, quel que soit le label', () => {
	// CouchDB ne renomme pas, et la connexion pointe l'ancien id.
	const doc = _fusionLieu(boutique(), champs({
		label: 'Un Nom Totalement Different', categorie: 'armurerie',
		pnj: { character: 'pnj:marchand_armurerie', nom: 'X', portrait: 'g.png' },
	}), CATALOGUE);
	assert.strictEqual(doc._id, 'lieu:l_enclume_du_rempart');
	assert.strictEqual(doc.label, 'Un Nom Totalement Different');
});

t('la fusion ne mute pas le doc d’origine', () => {
	// `nlDocExistant` doit rester relisable si l'écriture échoue.
	const avant = boutique();
	const copie = JSON.parse(JSON.stringify(avant));
	_fusionLieu(avant, champs({ label: 'Autre', categorie: 'auberge', pnj: null }), CATALOGUE);
	assert.deepStrictEqual(avant, copie);
});

t('LE PIÈGE : les entrées pnj[1..] survivent', () => {
	// Trois lieux en base portent plusieurs PNJ (jusqu'à 4). Le formulaire n'édite que
	// la première entrée ; écraser la liste perdrait les autres sans le dire.
	const avant = {
		_id: 'lieu:la_cathedrale', type: 'lieu', label: 'La Cathédrale',
		image: 'x.png', categorie: 'cathedral',
		pnj: [
			{ character: 'pnj:dame_eleonore', nom: 'Éléonore', description: 'd1', probabilite: 0.5 },
			{ character: 'pnj:frere_martin', nom: 'Martin', description: 'd2', probabilite: 0.5 },
		],
	};
	const doc = _fusionLieu(avant, champs({
		label: 'La Cathédrale', image: 'x.png', categorie: 'cathedral',
		pnj: { character: 'pnj:dame_eleonore', nom: 'Dame Éléonore', portrait: 'e.png' },
	}), CATALOGUE);
	assert.strictEqual(doc.pnj.length, 2);
	assert.deepStrictEqual(doc.pnj[1], avant.pnj[1], 'la seconde entrée a été perdue');
	assert.strictEqual(doc.pnj[0].nom, 'Dame Éléonore');
	assert.strictEqual(doc.pnj[0].description, 'd1', 'les clés hors formulaire survivent');
	assert.strictEqual(doc.pnj[0].probabilite, 0.5);
});

t('décocher « avec un PNJ » retire bien le champ', () => {
	// Le geste est destructeur — c'est l'interface qui le fait confirmer, pas cette
	// fonction : ici il doit s'appliquer sans détour.
	const doc = _fusionLieu(boutique(), champs({ categorie: 'armurerie', pnj: null }), CATALOGUE);
	assert.ok(!('pnj' in doc));
	assert.deepStrictEqual(doc.stock_vente, [{ item_id: 'item:Dague', qty: 3 }]);
});

t('un nom ou un portrait vidé disparaît de l’entrée', () => {
	// Absents, `nom`/`portrait` font retomber `pnj_payload` sur le doc PNJ générique :
	// c'est un repli voulu, pas une valeur manquante.
	const doc = _fusionLieu(boutique(), champs({ categorie: 'armurerie',
		pnj: { character: 'pnj:marchand_armurerie', nom: '', portrait: '' } }), CATALOGUE);
	assert.ok(!('nom' in doc.pnj[0]) && !('portrait' in doc.pnj[0]));
	assert.strictEqual(doc.pnj[0].character, 'pnj:marchand_armurerie');
	assert.ok(doc.pnj[0].progeniture, 'la progéniture survit quand même');
});

t('décocher « Étable » vide vraiment l’écurie', () => {
	const avant = {
		_id: 'lieu:e', type: 'lieu', label: 'E', image: 'e.png', categorie: 'etable',
		pnj: [{ character: 'pnj:marchand_etable', montures: ['espece:ane'] }],
	};
	const doc = _fusionLieu(avant, champs({
		label: 'E', image: 'e.png', categorie: 'boulangerie', montures: [],
		pnj: { character: 'pnj:marchand_boulangerie', nom: '', portrait: '' },
	}), CATALOGUE);
	assert.ok(!('montures' in doc.pnj[0]), 'une écurie orpheline que rien ne lit');
});

console.log('\n── Fusion : les tags, en édition ──');

t('devenir une taverne par le tag n’efface pas les autres tags', () => {
	const avant = { _id: 'lieu:x', type: 'lieu', label: 'X', image: 'x.png',
					categorie: 'chemin', tags: ['foret', 'brumeux'] };
	const doc = _fusionLieu(avant, champs({
		label: 'X', image: 'x.png', categorie: 'chemin', capacites: { taverne: true },
	}), CATALOGUE);
	assert.deepStrictEqual(doc.tags, ['foret', 'brumeux', 'taverne']);
});

t('un doc qui perd son dernier tag n’en garde pas un champ vide', () => {
	const avant = { _id: 'lieu:x', type: 'lieu', label: 'X', image: 'x.png',
					categorie: 'chemin', tags: ['taverne'] };
	const doc = _fusionLieu(avant, champs({
		label: 'X', image: 'x.png', categorie: 'chemin', capacites: { taverne: false },
	}), CATALOGUE);
	assert.ok(!('tags' in doc), 'un `tags: []` inutile reste en base');
});

t('passer la catégorie à `auberge` retire le tag devenu redondant, sans rien changer', () => {
	const avant = { _id: 'lieu:x', type: 'lieu', label: 'X', image: 'x.png',
					categorie: 'chemin', tags: ['taverne'] };
	const doc = _fusionLieu(avant, champs({
		label: 'X', image: 'x.png', categorie: 'auberge', capacites: { taverne: true },
	}), CATALOGUE);
	assert.ok(!('tags' in doc));
	assert.strictEqual(_capacitesDe(doc, CATALOGUE).taverne, true, 'la capacité reste acquise');
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
