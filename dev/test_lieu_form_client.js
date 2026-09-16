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
// Includes développés : le formulaire de lieu vit dans part-lieux-js.html (cf. dev/_template_js.js).
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

for (const f of ['_capaciteAccordee', '_capacitesDe', '_tagsApres', '_fusionLieu',
				 '_escRe', '_portraitsPourCategorie', '_nomDepuisPortrait',
				 '_probaLue', '_nlLigneDepuisEntree', '_fusionPnjEntrees', '_pnjDoublons',
				 '_probaPersonne', '_lieuxDuPnj',
				 '_genreSousFiltre', '_brutDepuisValeur', '_valeurDepuisBrut',
				 '_clauseRepresentable', '_clausesFautives']) {
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

// Une ligne de la section « PNJ du lieu », telle que `_nlChamps` la passe. `src` = indice de
// l'entrée d'ORIGINE dans le doc relu (`null` pour une ligne neuve) : c'est lui, et jamais
// le `character`, qui dit quelle entrée la ligne prolonge.
function ligne(over) {
	return Object.assign({
		src: null, character: '', nom: '', portrait: '', probabilite: 1, conditions: [], ecurie: false,
	}, over || {});
}

t('l’écurie part sur le TENANCIER, pas sur le bâtiment', () => {
	const doc = _fusionLieu({}, champs({
		categorie: 'etable',
		pnj: [ligne({ character: 'pnj:marchand_etable', nom: 'Garin', portrait: 'g.png', ecurie: true })],
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
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie', nom: 'George Dubois', portrait: 'g.png' })],
	}), CATALOGUE);
	assert.deepStrictEqual(doc.pnj[0].progeniture,
		{ nom: 'Dubois', race: 'humain', enfants: [{ prenom: 'Colin' }] });
});

t('stocks, accès, relation, texte et sous-catégorie survivent', () => {
	const avant = boutique();
	const doc = _fusionLieu(avant, champs({
		label: 'La Forge Noire', image: 'armurerie_europe01.png', categorie: 'armurerie',
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie', nom: 'X', portrait: 'g.png' })],
	}), CATALOGUE);
	for (const cle of ['stock_matieres', 'stock_vente', 'stock_cible', 'acces',
					   'relation_lieu', 'texte', 'sous_categorie', 'lieu_parent']) {
		assert.deepStrictEqual(doc[cle], avant[cle], cle + ' perdu');
	}
});

console.log('\n── Fusion : la sous-catégorie ──');

t('le formulaire écrit la sous-catégorie choisie', () => {
	const doc = _fusionLieu(boutique(), champs({ categorie: 'armurerie', sous_categorie: 'forge',
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie' })] }), CATALOGUE);
	assert.strictEqual(doc.sous_categorie, 'forge');
});

t('une sous-catégorie VIDÉE retire la clé, jamais une chaîne vide', () => {
	// La maison de guilde teste l'ABSENCE de sous_categorie sur le bureau du maître.
	const doc = _fusionLieu(boutique(), champs({ categorie: 'armurerie', sous_categorie: '',
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie' })] }), CATALOGUE);
	assert.ok(!('sous_categorie' in doc));
});

t('création sans sous-catégorie : aucune clé écrite', () => {
	assert.ok(!('sous_categorie' in _fusionLieu({}, champs({ sous_categorie: '' }), CATALOGUE)));
});

t('champs SANS sous_categorie (porte, lot, guilde) : celle du doc reste intacte', () => {
	const doc = _fusionLieu(boutique(), champs({ categorie: 'armurerie',
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie' })] }), CATALOGUE);
	assert.strictEqual(doc.sous_categorie, 'quelque_chose');
});

t('les tags de capacité se recalculent sur la sous-catégorie ÉCRITE', () => {
	// La sous-catégorie `guilde_aventurier` accorde « Maison de guilde » : le tag devient redondant.
	const avant = { _id: 'lieu:g', type: 'lieu', categorie: 'grotte', tags: ['guilde', 'foret'] };
	const pose = _fusionLieu(avant, champs({ categorie: 'grotte', sous_categorie: 'guilde_aventurier',
		capacites: { guilde: true } }), CATALOGUE);
	assert.deepStrictEqual(pose.tags, ['foret'], 'accordée par la sous-catégorie : pas de tag redondant');
	// Retirée : la capacité voulue repasse par son tag, sans quoi le lieu la perdrait.
	const retire = _fusionLieu(pose, champs({ categorie: 'grotte', sous_categorie: '',
		capacites: { guilde: true } }), CATALOGUE);
	assert.deepStrictEqual(retire.tags, ['foret', 'guilde']);
});

t('un champ INCONNU du formulaire survit', () => {
	// La base a des champs que ce formulaire n'a jamais vus (`recrutement_restrictions`,
	// `nuit_messages` d'un autre auteur, un champ à venir).
	const avant = Object.assign(boutique(), { recrutement_restrictions: { nb: 1 }, futur: 42 });
	const doc = _fusionLieu(avant, champs({ categorie: 'armurerie',
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie', nom: 'X', portrait: 'g.png' })] }), CATALOGUE);
	assert.deepStrictEqual(doc.recrutement_restrictions, { nb: 1 });
	assert.strictEqual(doc.futur, 42);
});

t('l’_id ne change JAMAIS, quel que soit le label', () => {
	// CouchDB ne renomme pas, et la connexion pointe l'ancien id.
	const doc = _fusionLieu(boutique(), champs({
		label: 'Un Nom Totalement Different', categorie: 'armurerie',
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie', nom: 'X', portrait: 'g.png' })],
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

t('LE PIÈGE : une ligne par entrée — éditer la 1re ne touche pas la 2de', () => {
	// Quatre lieux en base portent plusieurs PNJ (jusqu'à 4). Écraser la liste, ou fusionner
	// une ligne dans la mauvaise entrée, romprait le lien PNJ ↔ lieu sans le dire.
	const avant = {
		_id: 'lieu:la_cathedrale', type: 'lieu', label: 'La Cathédrale',
		image: 'x.png', categorie: 'cathedral',
		pnj: [
			{ character: 'pnj:dame_eleonore', nom: 'Éléonore', description: 'd1', probabilite: 0.5 },
			{ character: 'pnj:frere_martin', nom: 'Martin', description: 'd2', probabilite: 0.5 },
		],
	};
	const lignes = avant.pnj.map((e, i) => _nlLigneDepuisEntree(e, i));
	lignes[0].nom = 'Dame Éléonore';
	lignes[0].portrait = 'e.png';
	const doc = _fusionLieu(avant, champs({
		label: 'La Cathédrale', image: 'x.png', categorie: 'cathedral', pnj: lignes,
	}), CATALOGUE);
	assert.strictEqual(doc.pnj.length, 2);
	assert.deepStrictEqual(doc.pnj[1], avant.pnj[1], 'la seconde entrée a été altérée');
	assert.strictEqual(doc.pnj[0].nom, 'Dame Éléonore');
	assert.strictEqual(doc.pnj[0].description, 'd1', 'les clés hors formulaire survivent');
	assert.strictEqual(doc.pnj[0].probabilite, 0.5);
});

t('retirer toutes les lignes retire bien le champ', () => {
	// Le geste est destructeur — c'est l'interface qui fait confirmer les pertes, pas cette
	// fonction : ici il doit s'appliquer sans détour.
	for (const pnj of [[], null]) {
		const doc = _fusionLieu(boutique(), champs({ categorie: 'armurerie', pnj: pnj }), CATALOGUE);
		assert.ok(!('pnj' in doc));
		assert.deepStrictEqual(doc.stock_vente, [{ item_id: 'item:Dague', qty: 3 }]);
	}
});

t('un nom ou un portrait vidé disparaît de l’entrée', () => {
	// Absents, `nom`/`portrait` font retomber `pnj_payload` sur le doc PNJ générique :
	// c'est un repli voulu, pas une valeur manquante.
	const doc = _fusionLieu(boutique(), champs({ categorie: 'armurerie',
		pnj: [ligne({ src: 0, character: 'pnj:marchand_armurerie', nom: '', portrait: '' })] }), CATALOGUE);
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
		pnj: [ligne({ src: 0, character: 'pnj:marchand_boulangerie', nom: '', portrait: '' })],
	}), CATALOGUE);
	assert.ok(!('montures' in doc.pnj[0]), 'une écurie orpheline que rien ne lit');
});

console.log('\n── PNJ du lieu : plusieurs entrées, sans rompre le lien PNJ ↔ lieu ──');

// Les CINQ `conditions` réelles du dump du 13/09 (trois formes distinctes, les deux paladins
// d'un même lieu portant la même).
const CONDITIONS_REELLES = {
	'grotte_dans_foret_humide[0]': [
		{ quete_active: { types: ['escorte'], cible: 'lieu:bureau_du_maitre_de_guilde_d_auxerre',
						  giver_categorie: 'bureau_maitre_guilde' } },
	],
	'la_cathedrale_saint_etienne_d_auxerre[0,1]': [
		{ quete_active: { types: ['escorte'], cible: 'lieu:notre_dame', giver_categorie: 'cathedral',
						  attendu: false } },
		{ quete_reussie: { id: 'quete:escorte_convoi_de_lutecia', attendu: false } },
	],
	'notre_dame[0,1]': [
		{ quete_reussie: { id: 'quete:escorte_convoi_de_lutecia' } },
	],
};

// Le vocabulaire tel que `acces.vocabulaire_conditions` le sert. ⚠️ Recopié ici comme
// CATALOGUE, pour affirmer un comportement sur CE vocabulaire : c'est `tests/test_acces.py`
// qui verrouille l'accord entre ce payload et le moteur.
const VOCAB = {
	cles: ['combat_gagne', 'item', 'lieu_visite', 'ou', 'quete_active', 'quete_reussie', 'rang_min'],
	sous_filtres: {
		quete_active: ['attendu', 'cible', 'giver_categorie', 'lieu', 'objectif_atteint', 'types'],
		quete_reussie: ['attendu', 'id'], item: ['item', 'lieu_parent'], rang_min: ['cite', 'rang'],
		combat_gagne: ['attendu', 'lieu'], lieu_visite: ['attendu', 'lieu'], ou: [],
	},
	rangs: ['F', 'E', 'D', 'C', 'B', 'A', 'S', 'S+'],
};

// Réplique du Garde-manger des 3 fées : QUATRE entrées pour le même `pnj:marchand_cuisine`.
function gardeManger() {
	return {
		_id: 'lieu:le_garde_manger_des_3_fees', type: 'lieu', label: 'Le Garde-manger des 3 fées',
		image: 'cuisine_europe01.jpg', categorie: 'cuisine',
		pnj: [
			{ character: 'pnj:marchand_cuisine', nom: 'Les 3 fées', portrait: 'marchand_3_fées_cuisine.png' },
			{ character: 'pnj:marchand_cuisine', nom: 'Ysabeau Clairval', portrait: 'marchand_ysabeau_clairval_cuisine.png' },
			{ character: 'pnj:marchand_cuisine', nom: 'Floraine Ventdoux', portrait: 'marchand_floraine_ventdoux_cuisine.png' },
			{ character: 'pnj:marchand_cuisine', nom: 'Sibylle Ormerande', portrait: 'marchand_sibylle_ormerande_cuisine.png' },
		],
	};
}

// Réplique de la cathédrale d'Auxerre : `image`, `description`, un `probabilite: 1` EXPLICITE
// et des conditions — tout ce qu'une édition doit laisser passer.
function cathedrale() {
	const conds = () => JSON.parse(JSON.stringify(CONDITIONS_REELLES['la_cathedrale_saint_etienne_d_auxerre[0,1]']));
	return {
		_id: 'lieu:la_cathedrale_saint_etienne_d_auxerre', type: 'lieu', label: 'Cathédrale Saint-Étienne',
		image: 'cathedrale.png', categorie: 'cathedral',
		pnj: [
			{ character: 'pnj:frere_martin_de_clairvaux', nom: 'Frère Martin de Clairvaux', probabilite: 0.3,
			  image: 'pnj_paladin_frere_martin.jpg', portrait: 'paladin_Frere_Martin_de_Clairvaux_hobbit_m.jpg',
			  description: 'Un paladin hobbit.', conditions: conds() },
			{ character: 'pnj:dame_eleonore_de_rochefort', nom: 'Dame Éléonore de Rochefort',
			  portrait: 'paladin_Dame_Eleonore_de_Rochefort_elfe_f.jpg', probabilite: 1,
			  image: 'pnj_paladin_dame_eleonore.jpg', description: 'Une paladine.', conditions: conds() },
		],
	};
}

const lignesDe = doc => (doc.pnj || []).map((e, i) => _nlLigneDepuisEntree(e, i));

t('ouvrir puis enregistrer sans rien toucher rend des entrées IDENTIQUES', () => {
	for (const avant of [gardeManger(), boutique(), cathedrale()]) {
		const doc = _fusionLieu(avant, champs({
			label: avant.label, image: avant.image, categorie: avant.categorie, pnj: lignesDe(avant),
		}), CATALOGUE);
		assert.deepStrictEqual(doc.pnj, avant.pnj, avant._id);
		assert.strictEqual(JSON.stringify(doc.pnj), JSON.stringify(avant.pnj), avant._id + ' : ordre des clés');
	}
});

t('réordonner : la progéniture et la description SUIVENT leur entrée', () => {
	const avant = boutique();
	avant.pnj.push({ character: 'pnj:apprenti', nom: 'Colin', description: 'le fils' });
	const doc = _fusionLieu(avant, champs({ categorie: 'armurerie', pnj: lignesDe(avant).reverse() }), CATALOGUE);
	assert.deepStrictEqual(doc.pnj, [avant.pnj[1], avant.pnj[0]]);
});

t('doublons : éditer la 3e tenancière ne touche QUE la 3e entrée', () => {
	const avant = gardeManger();
	const lignes = lignesDe(avant);
	lignes[2].nom = 'Floraine la Douce';
	const doc = _fusionLieu(avant, champs({ categorie: 'cuisine', pnj: lignes }), CATALOGUE);
	assert.strictEqual(doc.pnj[2].nom, 'Floraine la Douce');
	assert.strictEqual(doc.pnj[2].portrait, avant.pnj[2].portrait);
	for (const i of [0, 1, 3]) assert.deepStrictEqual(doc.pnj[i], avant.pnj[i], 'entrée ' + i);
});

t('retirer la 2e de 4 : les autres restent identiques', () => {
	const avant = gardeManger();
	const lignes = lignesDe(avant).filter(l => l.src !== 1);
	const doc = _fusionLieu(avant, champs({ categorie: 'cuisine', pnj: lignes }), CATALOGUE);
	assert.deepStrictEqual(doc.pnj, [avant.pnj[0], avant.pnj[2], avant.pnj[3]]);
});

t('probabilité : 1 n’est pas écrite sur une ligne neuve, un 1 EXPLICITE reste', () => {
	const neuve = _fusionPnjEntrees([], [ligne({ character: 'pnj:a', probabilite: 1 })], []);
	assert.ok(!('probabilite' in neuve[0]));
	const reglee = _fusionPnjEntrees([], [ligne({ character: 'pnj:a', probabilite: 0.25 })], []);
	assert.strictEqual(reglee[0].probabilite, 0.25);
	const avant = [{ character: 'pnj:a', probabilite: 1 }];
	assert.strictEqual(_fusionPnjEntrees(avant, lignesDe({ pnj: avant }), [])[0].probabilite, 1);
});

t('probabilité illisible : lue comme le moteur (1), gardée telle quelle tant qu’on n’y touche pas', () => {
	assert.strictEqual(_probaLue('n’importe'), 1);
	assert.strictEqual(_probaLue(undefined), 1);
	assert.strictEqual(_probaLue(null), 1);
	assert.strictEqual(_probaLue('0.4'), 0.4);
	const avant = [{ character: 'pnj:a', probabilite: 'n’importe' }];
	assert.strictEqual(_fusionPnjEntrees(avant, lignesDe({ pnj: avant }), [])[0].probabilite, 'n’importe');
	const reglee = lignesDe({ pnj: avant });
	reglee[0].probabilite = 0.5;
	assert.strictEqual(_fusionPnjEntrees(avant, reglee, [])[0].probabilite, 0.5);
});

t('conditions : vidées ⇒ clé retirée ; nulles et intactes ⇒ laissées telles quelles', () => {
	const avant = [{ character: 'pnj:a', conditions: [{ quete_reussie: { id: 'q' } }] }];
	const videes = lignesDe({ pnj: avant });
	videes[0].conditions = [];
	assert.ok(!('conditions' in _fusionPnjEntrees(avant, videes, [])[0]));
	const nulles = [{ character: 'pnj:a', conditions: null }];
	assert.deepStrictEqual(_fusionPnjEntrees(nulles, lignesDe({ pnj: nulles }), []), nulles);
});

t('des conditions qui ne sont pas une liste ouvrent la ligne en JSON, en ERREUR', () => {
	const l = _nlLigneDepuisEntree({ character: 'pnj:a', conditions: { quete_reussie: { id: 'q' } } }, 0);
	assert.ok(l.jsonErreur, 'l’enregistrement doit rester bloqué');
	assert.deepStrictEqual(JSON.parse(l.json), { quete_reussie: { id: 'q' } });
});

t('l’écurie passe sur la ligne qui la TIENT et quitte l’ancienne', () => {
	const avant = [
		{ character: 'pnj:marchand_etable', montures: ['espece:ane'] },
		{ character: 'pnj:palefrenier' },
	];
	const lignes = lignesDe({ pnj: avant });
	lignes[1].ecurie = true;
	const apres = _fusionPnjEntrees(avant, lignes, ['espece:ane', 'espece:cheval']);
	assert.ok(!('montures' in apres[0]));
	assert.deepStrictEqual(apres[1].montures, ['espece:ane', 'espece:cheval']);
});

t('doublons : masquée derrière une entrée SANS condition, pas derrière une conditionnée', () => {
	assert.deepStrictEqual(_pnjDoublons(lignesDe(gardeManger())), {
		1: { premier: 0, masquee: true }, 2: { premier: 0, masquee: true }, 3: { premier: 0, masquee: true },
	});
	assert.deepStrictEqual(_pnjDoublons([
		ligne({ character: 'pnj:a', conditions: [{ quete_reussie: { id: 'q' } }] }),
		ligne({ character: 'pnj:a' }),
		ligne({ character: 'pnj:b' }),
	]), { 1: { premier: 0, masquee: false } });
});

t('chance que le lieu soit vide : le tirage du moteur, conditions à part', () => {
	const r = _probaPersonne([
		ligne({ character: 'pnj:a', probabilite: 0.5 }),
		ligne({ character: 'pnj:b', probabilite: 0.5 }),
		ligne({ character: 'pnj:c', probabilite: 1, conditions: [{ quete_reussie: { id: 'q' } }] }),
	]);
	assert.deepStrictEqual(r, { personne: 0.25, esperance: 1, horsCalcul: 1 });
	// Un PNJ listé deux fois est là dès que L'UN de ses tirages passe (le moteur retente).
	assert.deepStrictEqual(_probaPersonne([
		ligne({ character: 'pnj:a', probabilite: 0.5 }), ligne({ character: 'pnj:a', probabilite: 0.5 }),
	]), { personne: 0.25, esperance: 0.75, horsCalcul: 0 });
});

t('vue inverse : les AUTRES lieux du PNJ, le lieu courant exclu', () => {
	const lieux = [
		{ _id: 'lieu:temple_de_malakor', label: 'Temple',
		  pnj: [{ character: 'pnj:reverend_malakor', probabilite: 0.7, conditionne: false }] },
		{ _id: 'lieu:temple_de_malakor02', label: 'Temple 2',
		  pnj: [{ character: 'pnj:reverend_malakor', probabilite: 0.3, conditionne: false }] },
		{ _id: 'lieu:ailleurs', label: 'Ailleurs', pnj: [{ character: 'pnj:autre', probabilite: 1, conditionne: true }] },
		{ _id: 'lieu:vide', label: 'Vide' },
	];
	assert.deepStrictEqual(_lieuxDuPnj(lieux, 'pnj:reverend_malakor', 'lieu:temple_de_malakor'), [
		{ _id: 'lieu:temple_de_malakor02', label: 'Temple 2', probabilite: 0.3, conditionne: false },
	]);
	assert.deepStrictEqual(_lieuxDuPnj(lieux, 'pnj:personne', 'lieu:x'), []);
	assert.deepStrictEqual(_lieuxDuPnj(lieux, '', 'lieu:x'), []);
});

console.log('\n── Conditions de présence : le constructeur ne perd rien ──');

t('toutes les conditions réelles s’affichent en constructeur', () => {
	for (const [ou, conds] of Object.entries(CONDITIONS_REELLES)) {
		for (const c of conds) assert.ok(_clauseRepresentable(c, VOCAB), ou + ' : ' + JSON.stringify(c));
	}
});

t('aller-retour par les widgets : chaque sous-filtre réel revient À L’IDENTIQUE', () => {
	for (const conds of Object.values(CONDITIONS_REELLES)) {
		for (const c of conds) {
			const cle = Object.keys(c)[0];
			const relue = {};
			for (const [sous, v] of Object.entries(c[cle])) {
				const g = _genreSousFiltre(sous);
				const retour = _valeurDepuisBrut(_brutDepuisValeur(v, g), g);
				if (retour !== undefined) relue[sous] = retour;
			}
			assert.deepStrictEqual(relue, c[cle], JSON.stringify(c));
		}
		assert.deepStrictEqual(_clausesFautives(conds), []);
	}
});

t('un champ vidé est SUPPRIMÉ, jamais écrit à vide', () => {
	assert.strictEqual(_valeurDepuisBrut('', 'texte'), undefined);
	assert.strictEqual(_valeurDepuisBrut('  ', 'texte'), undefined);
	assert.strictEqual(_valeurDepuisBrut(' , ', 'liste'), undefined);
	assert.strictEqual(_valeurDepuisBrut('', 'bool'), undefined);
	assert.deepStrictEqual(_valeurDepuisBrut('escorte, chasse', 'liste'), ['escorte', 'chasse']);
	assert.strictEqual(_valeurDepuisBrut('false', 'bool'), false);
});

t('une clause hors constructeur reste une carte JSON, intacte', () => {
	for (const c of [
		{ quete_reussie: { ids: 'q' } },                  // sous-filtre inconnu
		{ quete_activ: {} },                              // clé inconnue
		{ quete_active: { types: [] } },                  // liste vide : ≠ absence de filtre
		{ quete_active: { attendu: 'non' } },             // booléen illisible
		{ quete_reussie: { id: ' q ' } },                 // l'espace ne survivrait pas au widget
		{ item: { item: 'x' }, rang_min: { rang: 'D' } }, // deux clés dans une clause
		{ ou: [{ quete_reussie: { idd: 'q' } }] },        // fautive enfouie dans un ou
	]) {
		assert.strictEqual(_clauseRepresentable(c, VOCAB), false, JSON.stringify(c));
	}
	assert.strictEqual(_clauseRepresentable({ ou: [{ lieu_visite: { lieu: 'lieu:x', attendu: false } }] }, VOCAB), true);
});

t('ce que le moteur rendrait faux POUR TOUJOURS bloque l’enregistrement', () => {
	assert.strictEqual(_clausesFautives([{ ou: [] }]).length, 1);
	assert.strictEqual(_clausesFautives([{ combat_gagne: {} }]).length, 1);
	assert.strictEqual(_clausesFautives([{ item: { item: 'x' }, rang_min: { rang: 'D' } }]).length, 1);
	assert.strictEqual(_clausesFautives([{ ou: [{ lieu_visite: {} }] }]).length, 1, 'enfouie dans un ou');
	// « une quête quelconque en cours » : le seul filtre vide qui ait un sens.
	assert.deepStrictEqual(_clausesFautives([{ quete_active: {} }]), []);
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

console.log('\n── Portraits : le filtre par catégorie ──');

// Noms réels de templates/resources/pnj/ : les deux conventions, avec et sans numéro
// de variante. `creationOptions` est la globale que sert /api/lieux/creation_options.
const PORTRAITS = [
	'marchand_elfe_f_boulangerie.jpg',
	'marchand_elfe_f_boulangerie01.jpg',
	'marchand_nain_f_boulangerie01.jpg',
	'marchand_ogre_m_boulangerie.jpg',
	'marchand_elfe_f_bijouterie01.png',
	'marchand_clement_varnepierre_laboratoire_d_alchimie.png',
	'marchand_elfe_f_laboratoire_d_alchimie.png',
	'Gaspard_Briselame.jpg',
];
globalThis.creationOptions = { portraits: PORTRAITS };

t('le numéro de variante ne fait pas écarter un portrait', () => {
	assert.deepStrictEqual(_portraitsPourCategorie('boulangerie'), [
		'marchand_elfe_f_boulangerie.jpg',
		'marchand_elfe_f_boulangerie01.jpg',
		'marchand_nain_f_boulangerie01.jpg',
		'marchand_ogre_m_boulangerie.jpg',
	]);
});

t('une catégorie à rallonge reste filtrée exactement', () => {
	assert.deepStrictEqual(_portraitsPourCategorie('laboratoire_d_alchimie'), [
		'marchand_clement_varnepierre_laboratoire_d_alchimie.png',
		'marchand_elfe_f_laboratoire_d_alchimie.png',
	]);
});

t('un filtre sans résultat rend la liste complète, jamais vide', () => {
	assert.deepStrictEqual(_portraitsPourCategorie('etable'), PORTRAITS);
	assert.deepStrictEqual(_portraitsPourCategorie(''), PORTRAITS);
});

t('le numéro de variante tombe avec le suffixe de catégorie', () => {
	assert.strictEqual(_nomDepuisPortrait('marchand_elfe_f_boulangerie01.jpg', 'boulangerie'), '');
	assert.strictEqual(_nomDepuisPortrait('marchand_elfe_f_boulangerie.jpg', 'boulangerie'), '');
});

t('le tenancier nommé garde son nom', () => {
	assert.strictEqual(
		_nomDepuisPortrait('marchand_clement_varnepierre_laboratoire_d_alchimie.png',
						   'laboratoire_d_alchimie'),
		'Clement Varnepierre');
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
