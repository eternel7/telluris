// dev/test_guilde_client.js
//
// Tests d'EXÉCUTION du JavaScript de la MAISON DE GUILDE
// (templates/admin_map_editor.html, mode Lieux → bouton « 🏛️ Guilde » d'une façade de guilde).
//
//   node dev/test_guilde_client.js     # sort en code 1 au premier échec
//
// POURQUOI : l'assistant ajoute, derrière une façade `guilde_aventurier_exterieur`, l'étape
// SUIVANTE d'une chaîne réception → comptoir → bureau du maître, en un `POST /admin/import-bulk`
// — un PUT COMPLET (CLAUDE.md §11). Classes de bug SILENCIEUSES, hors de portée de pytest :
//
//   1. La chaîne lue de travers : une étape sautée, ou une deuxième réception bâtie sur une
//      maison dédoublée.
//   2. Un doc RÉÉCRIT pour y poser `relation_lieu` (façade, réception) qui perd une clé, ou un
//      `relation_lieu` déjà posé par l'auteur qui est écrasé.
//   3. Un bureau qui gagne une `sous_categorie` (interdit : cf. utils/recrutement.py § Maison de
//      guilde), ou des `_id` qui ne retrouvent plus ceux du Bastion.
//
// MÉTHODE : identique à dev/test_portes_client.js — extraction par nom, `runInThisContext`.
// DONNÉES : le Bastion d'Auxerre, recopié de jsons/lieu_filtre_categorie_guilde_lieu_parent_auxerre_*
// et jsons/connection_filtre_metadata_guilde_* (13/09/2026).
//
// HORS DE PORTÉE (CLAUDE.md §15, à vérifier en jeu) : le rendu du panneau, les relectures
// réseau et l'échange avec /admin/import-bulk.

const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_map_editor.html');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');
const js = scriptsInline(lireAvecIncludes(TEMPLATE));
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
	const m = new RegExp('^\\s*const ' + nom + ' = .*$', 'm').exec(js);
	assert.ok(m, 'constante ' + nom + ' introuvable dans le template');
	return m[0];
}

for (const c of ['_DIACRITIQUES', 'GUILDE_EXTERIEUR_CATEGORIE']) vm.runInThisContext(extraireConst(c));
for (const f of ['_cxSlug', '_cxIdPropose', '_fusionConnexion',
	'_slugLieu', '_capaciteAccordee', '_tagsApres', '_fusionLieu', '_probaLue', '_fusionPnjEntrees',
	'_gdEtapes', '_gdBase', '_gdLabelDefaut', '_gdRefusDefaut', '_gdChaine', '_gdImages',
	'_gdDocs', '_gdValider']) {
	vm.runInThisContext(extraire(f));
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// ── Le Bastion d'Auxerre ─────────────────────────────────────────────────────
const AUXERRE = 'lieu:auxerre';
const FACADE = 'lieu:le_bastion_de_l_yonne';
const RECEPTION = 'lieu:le_bastion_de_l_yonne_interieur';
const COMPTOIR = 'lieu:le_bastion_de_l_yonne_comptoir';
const BUREAU = 'lieu:bureau_du_maitre_de_guilde_d_auxerre';
const LUTECE_FACADE = 'lieu:le_grand_relais_des_frontieres_exterieur';

function lieux() {
	return [
		{ _id: FACADE, categorie: 'guilde_aventurier_exterieur', label: "Le Bastion de l'Yonne",
			image: 'guilde_aventuriers_exterieur_europe01.png', lieu_parent: AUXERRE },
		{ _id: RECEPTION, categorie: 'guilde_aventurier', label: "Le Bastion de l'Yonne - reception",
			image: 'guilde_aventuriers_interieur_europe01.png', lieu_parent: AUXERRE },
		{ _id: COMPTOIR, categorie: 'guilde_aventurier_comptoir', label: 'Le comptoir du Bastion',
			image: 'guilde_aventuriers_interieur_receptioniste_europe01.jpg', lieu_parent: AUXERRE },
		{ _id: BUREAU, categorie: 'bureau_maitre_guilde', label: 'Bureau de Gautier de Valcroix',
			image: 'guilde_bureau_maitre_de_guilde_europe01.png', lieu_parent: AUXERRE },
		{ _id: AUXERRE, categorie: 'ville', label: 'Auxerre' },
		{ _id: LUTECE_FACADE, categorie: 'guilde_aventurier_exterieur', label: 'Le Grand Relais des Frontières',
			image: 'guilde_aventuriers_exterieur_europe02.png', lieu_parent: 'lieu:lutecia' },
	];
}

function lien(id, a, b) {
	return { _id: id, type: 'connection', nodes: [a, b], metadata: { type: 'guilde_aventurier', status: 'ouvert' } };
}
function connexions() {
	return [
		lien('link:bastion_bureau_maitre_to_bastion_comptoir',
			{ lieu: COMPTOIR, pos: [0, 0], label: 'redescendre au comptoir' },
			{ lieu: BUREAU, pos: [0, 0], label: "monter l'escalier du fond" }),
		lien('link:bastion_comptoir_to_bastion_interieur',
			{ lieu: RECEPTION, pos: [0, 0], label: 'retourner dans la salle commune' },
			{ lieu: COMPTOIR, pos: [0, 0], label: "s'approcher du comptoir" }),
		lien('link:guilde01_to_auxerre', { lieu: AUXERRE, pos: [26, 22] }, { lieu: FACADE, pos: [0, 0] }),
		lien('link:guilde01_to_guilde_ext',
			{ lieu: RECEPTION, pos: [0, 0] }, { lieu: FACADE, pos: [0, 0], label: 'sortir dans la rue' }),
		lien('link:guilde_aventurier_exterieur01_to_lutecia',
			{ lieu: 'lieu:lutecia', pos: [34, 20] }, { lieu: LUTECE_FACADE, pos: [0, 0] }),
	];
}
const sans = (...ids) => connexions().filter(c => ids.indexOf(c._id) === -1);

// Docs RELUS en base (ce que `_gdLireFrais` rendrait).
function relus() {
	return {
		facade: { _id: FACADE, _rev: '8-aaa', type: 'lieu', label: "Le Bastion de l'Yonne",
			image: 'guilde_aventuriers_exterieur_europe01.png', lieu_parent: AUXERRE,
			categorie: 'guilde_aventurier_exterieur', note_de_regie: 'à ne pas perdre' },
		reception: { _id: RECEPTION, _rev: '8-bbb', type: 'lieu', label: "Le Bastion de l'Yonne - reception",
			image: 'guilde_aventuriers_interieur_europe01.png', categorie: 'guilde_aventurier',
			sous_categorie: 'guilde_aventurier', lieu_parent: AUXERRE, tags: ['recrutement'] },
		comptoir: { _id: COMPTOIR, _rev: '5-ccc', type: 'lieu', label: 'Le comptoir du Bastion',
			image: 'guilde_aventuriers_interieur_receptioniste_europe01.jpg', lieu_parent: AUXERRE,
			categorie: 'guilde_aventurier_comptoir', sous_categorie: 'guilde_aventurier',
			pnj: [{ character: 'pnj:borin_barbe_de_jais', portrait: 'nain_m_receptioniste01.png', probabilite: 1 }] },
	};
}

function champs(extra) {
	return Object.assign({
		citeId: AUXERRE, label: 'Un lieu', image: 'guilde_x.png',
		labelVersPrecedent: 'retour', labelVersNouveau: 'aller',
		pnj: { character: '', nom: '', portrait: '' }, rang: 'D', refus: 'Non.', connIdsPris: [],
	}, extra || {});
}
// La chaîne d'Auxerre amputée de ses maillons à partir de `etape`.
function chaineJusqua(etape) {
	const coupes = { reception: ['link:guilde01_to_guilde_ext'], comptoir: ['link:bastion_comptoir_to_bastion_interieur'],
		bureau: ['link:bastion_bureau_maitre_to_bastion_comptoir'] };
	return _gdChaine(sans(...coupes[etape]), lieux(), FACADE);
}
const RANGS = ['F', 'E', 'D', 'C', 'B', 'A', 'S', 'S+'];
const ctx = extra => Object.assign({ lieuIds: [], connIds: [], pnjIds: ['pnj:borin_barbe_de_jais', 'pnj:gautier'], rangs: RANGS }, extra || {});

// ── _gdBase ──────────────────────────────────────────────────────────────────
t('la base retire le préfixe et le suffixe _exterieur', () => {
	assert.strictEqual(_gdBase(FACADE), 'le_bastion_de_l_yonne');
	assert.strictEqual(_gdBase(LUTECE_FACADE), 'le_grand_relais_des_frontieres');
	assert.strictEqual(_gdBase(''), '');
});

// ── _gdChaine ────────────────────────────────────────────────────────────────
t('le Bastion est une maison COMPLÈTE', () => {
	const ch = _gdChaine(connexions(), lieux(), FACADE);
	assert.strictEqual(ch.erreur, '');
	assert.strictEqual(ch.etape, '');
	assert.strictEqual(ch.reception.lieu, RECEPTION);
	assert.strictEqual(ch.comptoir.lieu, COMPTOIR);
	assert.strictEqual(ch.bureau.lieu, BUREAU);
});

t('l’étape suivante est le PREMIER maillon manquant, raccroché au précédent', () => {
	const bureau = chaineJusqua('bureau');
	assert.deepStrictEqual([bureau.etape, bureau.precedent], ['bureau', COMPTOIR]);
	const comptoir = chaineJusqua('comptoir');
	assert.deepStrictEqual([comptoir.etape, comptoir.precedent], ['comptoir', RECEPTION]);
	// Le bureau est encore relié au comptoir, mais le comptoir ne l'est plus à la réception :
	// la chaîne s'arrête là, elle ne saute pas par-dessus le trou.
	assert.strictEqual(comptoir.bureau, null);
	const reception = chaineJusqua('reception');
	assert.deepStrictEqual([reception.etape, reception.precedent], ['reception', FACADE]);
});

t('une façade seule (Lutèce) attend sa réception', () => {
	const ch = _gdChaine(connexions(), lieux(), LUTECE_FACADE);
	assert.deepStrictEqual([ch.erreur, ch.etape, ch.precedent], ['', 'reception', LUTECE_FACADE]);
});

t('la catégorie décide : la connexion vers la cité n’est pas un maillon', () => {
	// La façade est aussi reliée à Auxerre ; seul le voisin `guilde_aventurier` compte.
	assert.strictEqual(chaineJusqua('comptoir').reception.link._id, 'link:guilde01_to_guilde_ext');
});

t('deux réceptions sur une même façade : ERREUR, jamais un choix', () => {
	const conns = connexions().concat([lien('link:doublon',
		{ lieu: FACADE, pos: [0, 0] }, { lieu: 'lieu:autre_reception', pos: [0, 0] })]);
	const ls = lieux().concat([{ _id: 'lieu:autre_reception', categorie: 'guilde_aventurier' }]);
	const ch = _gdChaine(conns, ls, FACADE);
	assert.match(ch.erreur, /link:doublon/);
	assert.strictEqual(ch.etape, '');
	assert.match(_gdValider([{}, {}], ch, ctx()), /link:doublon/);
});

t('un lieu qui n’est pas une façade de guilde est refusé', () => {
	assert.match(_gdChaine(connexions(), lieux(), BUREAU).erreur, /façade de guilde/);
	assert.match(_gdChaine(connexions(), lieux(), 'lieu:inconnu').erreur, /façade de guilde/);
});

// ── _gdDocs : réception ──────────────────────────────────────────────────────
t('réception : retrouve l’_id du Bastion, forme du doc et de sa connexion', () => {
	const ch = chaineJusqua('reception');
	const docs = _gdDocs(ch, champs({ labelVersPrecedent: 'sortir dans la rue', labelVersNouveau: '' }), relus());
	assert.strictEqual(docs.length, 2, 'pas de comptoir : aucun relation_lieu à poser');
	const [lieu, link] = docs;
	assert.strictEqual(lieu._id, RECEPTION);
	assert.strictEqual(lieu.categorie, 'guilde_aventurier');
	assert.strictEqual(lieu.sous_categorie, 'guilde_aventurier');
	assert.strictEqual(lieu.lieu_parent, AUXERRE);
	for (const k of ['tags', 'pnj', 'acces', 'relation_lieu', 'cells', 'dimensions']) assert.ok(!(k in lieu), k);
	assert.strictEqual(link._id, 'link:le_bastion_de_l_yonne_interieur_to_le_bastion_de_l_yonne');
	assert.deepStrictEqual(link.nodes, [
		{ lieu: FACADE, pos: [0, 0], label: 'sortir dans la rue' },
		{ lieu: RECEPTION, pos: [0, 0] },
	]);
	assert.deepStrictEqual(link.metadata, { type: 'guilde_aventurier', status: 'ouvert' });
});

t('le lieu_parent vient de la FAÇADE relue, pas de la carte ouverte', () => {
	const docs = _gdDocs(chaineJusqua('reception'), champs({ citeId: 'lieu:ailleurs' }), relus());
	assert.strictEqual(docs[0].lieu_parent, AUXERRE);
	const sansParent = relus(); delete sansParent.facade.lieu_parent;
	assert.strictEqual(_gdDocs(chaineJusqua('reception'), champs({ citeId: 'lieu:ailleurs' }), sansParent)[0].lieu_parent, 'lieu:ailleurs');
});

t('un _id de connexion déjà pris est suffixé', () => {
	const base = 'link:le_bastion_de_l_yonne_interieur_to_le_bastion_de_l_yonne';
	const docs = _gdDocs(chaineJusqua('reception'), champs({ connIdsPris: [base] }), relus());
	assert.strictEqual(docs[1]._id, base + '_02');
});

// ── _gdDocs : comptoir ───────────────────────────────────────────────────────
t('comptoir : PNJ minimal, et relation_lieu posé sur façade et réception', () => {
	const r = relus(); delete r.comptoir;
	const copie = JSON.parse(JSON.stringify(r));
	const docs = _gdDocs(chaineJusqua('comptoir'),
		champs({ pnj: { character: 'pnj:borin_barbe_de_jais', nom: 'Borin', portrait: '' } }), r);
	const [lieu, link, facade, reception] = docs;
	assert.strictEqual(docs.length, 4);
	assert.strictEqual(lieu._id, COMPTOIR);
	assert.strictEqual(lieu.sous_categorie, 'guilde_aventurier');
	assert.ok(!('relation_lieu' in lieu), 'le comptoir PORTE la cote, il ne la délègue pas');
	// Ni probabilite 1, ni conditions vides, ni montures : l'entrée la plus sobre.
	assert.deepStrictEqual(lieu.pnj, [{ character: 'pnj:borin_barbe_de_jais', nom: 'Borin' }]);
	assert.deepStrictEqual(link.nodes.map(n => n.lieu), [RECEPTION, COMPTOIR]);
	// Les réécrits : le doc relu à l'identique, `relation_lieu` en plus.
	assert.deepStrictEqual(facade, Object.assign({}, copie.facade, { relation_lieu: COMPTOIR }));
	assert.deepStrictEqual(reception, Object.assign({}, copie.reception, { relation_lieu: COMPTOIR }));
	assert.deepStrictEqual(r, copie, 'les docs relus ne sont pas mutés');
});

t('comptoir sans PNJ : aucune clé pnj', () => {
	const docs = _gdDocs(chaineJusqua('comptoir'), champs(), relus());
	assert.ok(!('pnj' in docs[0]));
});

t('un relation_lieu déjà posé n’est JAMAIS réécrit, même divergent', () => {
	const r = relus();
	r.facade.relation_lieu = COMPTOIR;
	r.reception.relation_lieu = 'lieu:un_autre_choix';
	const docs = _gdDocs(chaineJusqua('comptoir'), champs(), r);
	assert.strictEqual(docs.length, 2);
});

t('réception : la frappe d’un PNJ est ignorée (l’étape n’en a pas)', () => {
	const docs = _gdDocs(chaineJusqua('reception'), champs({ pnj: { character: 'pnj:x' } }), relus());
	assert.ok(!('pnj' in docs[0]));
});

// ── _gdDocs : bureau ─────────────────────────────────────────────────────────
t('bureau : pas de sous_categorie, relation_lieu, accès gardé par le PNJ du comptoir', () => {
	const r = relus();
	r.facade.relation_lieu = COMPTOIR;
	r.reception.relation_lieu = COMPTOIR;
	const docs = _gdDocs(chaineJusqua('bureau'),
		champs({ pnj: { character: 'pnj:gautier', nom: '', portrait: 'humain_m_guerrier01.jpg' }, rang: 'C', refus: 'Halte.' }), r);
	assert.strictEqual(docs.length, 2, 'façade et réception déjà consolidées');
	const [lieu, link] = docs;
	assert.strictEqual(lieu._id, 'lieu:le_bastion_de_l_yonne_bureau_du_maitre');
	assert.strictEqual(lieu.categorie, 'bureau_maitre_guilde');
	assert.ok(!('sous_categorie' in lieu));
	assert.strictEqual(lieu.relation_lieu, COMPTOIR);
	assert.deepStrictEqual(lieu.pnj, [{ character: 'pnj:gautier', portrait: 'humain_m_guerrier01.jpg' }]);
	assert.deepStrictEqual(lieu.acces, {
		gardien: 'pnj:borin_barbe_de_jais', refus: 'Halte.', cycle: 1,
		conditions: [{ rang_min: { cite: AUXERRE, rang: 'C' } }],
	});
	assert.deepStrictEqual(link.nodes.map(n => n.lieu), [COMPTOIR, lieu._id]);
	assert.strictEqual(link._id, 'link:le_bastion_de_l_yonne_bureau_du_maitre_to_le_bastion_de_l_yonne_comptoir');
});

t('bureau : répare une façade restée sans relation_lieu', () => {
	const docs = _gdDocs(chaineJusqua('bureau'), champs(), relus());
	assert.deepStrictEqual(docs.slice(2).map(d => [d._id, d.relation_lieu]),
		[[FACADE, COMPTOIR], [RECEPTION, COMPTOIR]]);
});

t('bureau : comptoir sans PNJ ⇒ pas de gardien, la barrière reste', () => {
	const r = relus(); delete r.comptoir.pnj;
	const acces = _gdDocs(chaineJusqua('bureau'), champs(), r)[0].acces;
	assert.ok(!('gardien' in acces));
	assert.deepStrictEqual(acces.conditions, [{ rang_min: { cite: AUXERRE, rang: 'D' } }]);
});

t('une maison complète ne produit aucun document', () => {
	assert.deepStrictEqual(_gdDocs(_gdChaine(connexions(), lieux(), FACADE), champs(), relus()), []);
});

// ── _gdValider ───────────────────────────────────────────────────────────────
t('une étape bien remplie passe', () => {
	const ch = chaineJusqua('bureau');
	const docs = _gdDocs(ch, champs({ pnj: { character: 'pnj:gautier' } }), relus());
	assert.strictEqual(_gdValider(docs, ch, ctx()), '');
});

t('libellé, image, _id pris, lien pris, PNJ inconnu, rang hors échelle : refusés', () => {
	const ch = chaineJusqua('bureau');
	const v = (extra, c) => _gdValider(_gdDocs(ch, champs(extra), relus()), ch, ctx(c));
	assert.match(v({ label: '' }), /libellé/);
	assert.match(v({ image: '' }), /image/);
	assert.match(v({}, { lieuIds: ['lieu:le_bastion_de_l_yonne_bureau_du_maitre'] }), /existe déjà/);
	const linkId = 'link:le_bastion_de_l_yonne_bureau_du_maitre_to_le_bastion_de_l_yonne_comptoir';
	assert.match(v({}, { connIds: [linkId] }), /existe déjà/);
	assert.match(v({ pnj: { character: 'pnj:fantome' } }), /pnj:fantome/);
	assert.match(v({ rang: 'Z' }), /Rang « Z »/);
	assert.match(_gdValider([], _gdChaine(connexions(), lieux(), FACADE), ctx()), /complète/);
});

// ── _gdImages, libellés ──────────────────────────────────────────────────────
const IMAGES = [
	'guilde_aventuriers_exterieur_europe01.png', 'guilde_aventuriers_interieur_europe01.png',
	'guilde_aventuriers_interieur_japon01.png', 'guilde_aventuriers_interieur_receptioniste_europe01.jpg',
	'guilde_aventuriers_interieur_receptioniste_europe01.png', 'guilde_bureau_maitre_de_guilde_europe01.png',
	'guilde_bureau_maitre_de_guilde_europe02.png', 'guilde_dortoir_europe01.png', 'auberge_europe01.png',
];

t('les images de l’étape d’abord, sans celles déjà prises', () => {
	assert.deepStrictEqual(_gdImages(IMAGES, 'reception', ['guilde_aventuriers_interieur_europe01.png']),
		['guilde_aventuriers_interieur_japon01.png']);
	assert.deepStrictEqual(_gdImages(IMAGES, 'comptoir', []), [
		'guilde_aventuriers_interieur_receptioniste_europe01.jpg', 'guilde_aventuriers_interieur_receptioniste_europe01.png']);
	assert.deepStrictEqual(_gdImages(IMAGES, 'bureau', ['guilde_bureau_maitre_de_guilde_europe01.png']),
		['guilde_bureau_maitre_de_guilde_europe02.png']);
});

t('rien pour l’étape ⇒ toutes les guilde* libres ; l’image courante reste offerte', () => {
	const prises = ['guilde_bureau_maitre_de_guilde_europe01.png', 'guilde_bureau_maitre_de_guilde_europe02.png'];
	const repli = _gdImages(IMAGES, 'bureau', prises);
	assert.ok(repli.includes('guilde_dortoir_europe01.png') && !repli.includes('auberge_europe01.png'));
	assert.strictEqual(_gdImages(IMAGES, 'bureau', prises, prises[0])[0], prises[0]);
});

t('libellé proposé : celui de la façade, sans « — extérieur »', () => {
	assert.strictEqual(_gdLabelDefaut('Le Grand Relais — extérieur', 'reception'), 'Le Grand Relais - réception');
	assert.strictEqual(_gdLabelDefaut("Le Bastion de l'Yonne", 'bureau'), "Le Bastion de l'Yonne - bureau du maître");
	assert.strictEqual(_gdLabelDefaut('', 'comptoir'), '');
	assert.match(_gdRefusDefaut('Borin'), /^Borin barre/);
	assert.match(_gdRefusDefaut(''), /^Le réceptionniste barre/);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
