// dev/check_js.js
//
// Contrôle SYNTAXIQUE du JavaScript inline des templates Jinja.
//
// Tout l'interactif du jeu est du JS vanilla embarqué dans les templates : il n'est ni
// compilé, ni typé, ni couvert par pytest. Une parenthèse manquante ne se voit donc
// qu'en jouant la page — et souvent seulement la branche fautive. D'où ce contrôle,
// miroir de `dev/lint_dialogues.py` pour les arbres de dialogue.
//
//   node dev/check_js.js                    # tous les templates/*.html
//   node dev/check_js.js templates/x.html   # ciblé
//
// Sort en code 1 s'il reste une erreur (utilisable en pré-commit / CI).
//
// ⚠️ Ce contrôle ne prouve QUE la syntaxe : ni les variables non définies, ni les
// fautes de logique. Pour exécuter réellement du code, cf. dev/test_slots_client.js.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Les expressions Jinja sont remplacées par des littéraux de MÊME FORME SYNTAXIQUE,
// sans quoi le parseur bute sur du texte qui n'est pas du JS.
// ⚠️ `(0)` et non `0` : un simple 0 casserait `{{ liste | tojson }}.forEach(...)`, qui
// deviendrait `0.forEach(...)` — invalide en JS, alors que le rendu réel `[].forEach(...)`
// est parfaitement correct. Le faux positif est garanti sinon.
function neutraliserJinja(src) {
	return src
		.replace(/\{\{[\s\S]*?\}\}/g, '(0)')   // {{ expression }}
		.replace(/\{%[\s\S]*?%\}/g, '')        // {% bloc de contrôle %}
		.replace(/\{#[\s\S]*?#\}/g, '');       // {# commentaire #}
}

// ⚠️ `templates/scripts/*.js` en PLUS des templates. Les `<script src="…">` sont sautés
// ci-dessous (ils n'ont pas de corps dans la page), si bien que `nav.js`, `battle_map.js` et
// `deplacement.js` — la RÈGLE DE MARCHE du jeu, qui n'existe nulle part côté serveur —
// n'étaient contrôlés par rien. Rien d'autre à changer : `neutraliserJinja` est inerte sur du
// JS pur, et `new vm.Script` marche tel quel.
function fichiersAControler(args) {
	if (args.length) return args;
	const racine = path.join(__dirname, '..', 'templates');
	const templates = fs.readdirSync(racine)
		.filter(f => f.endsWith('.html'))
		.map(f => path.join('templates', f));
	const scriptsDir = path.join(racine, 'scripts');
	const scripts = fs.existsSync(scriptsDir)
		? fs.readdirSync(scriptsDir)
			.filter(f => f.endsWith('.js'))
			.map(f => path.join('templates', 'scripts', f))
		: [];
	return [...templates, ...scripts];
}

let erreurs = 0, blocsOk = 0, lignesOk = 0;

for (const fichier of fichiersAControler(process.argv.slice(2))) {
	const html = fs.readFileSync(fichier, 'utf8');
	// Un `.js` de scripts/ n'a pas de balise : le fichier ENTIER est son unique bloc — d'où la
	// forme `{1: code, index: 0}`, celle que la boucle attend d'une correspondance de regex.
	// Les <script src="..."> d'un template, eux, n'ont pas de corps à contrôler ici.
	const blocs = fichier.endsWith('.js')
		? [{ 1: html, index: 0 }]
		: [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)];
	if (!blocs.length) continue;

	for (const [i, m] of blocs.entries()) {
		const code = neutraliserJinja(m[1]);
		const ligneBloc = html.slice(0, m.index).split('\n').length;
		try {
			new vm.Script(code, { filename: fichier });
			blocsOk++;
			lignesOk += code.split('\n').length;
		} catch (e) {
			erreurs++;
			console.error(`${fichier} — bloc ${i + 1} (ligne ~${ligneBloc}) : ${e.message}`);
			// La ligne rapportée par le parseur est RELATIVE au bloc : on la ramène au fichier.
			const locale = (e.stack.match(/:(\d+)\n/) || [])[1];
			if (locale) console.error(`   → ligne ${ligneBloc + Number(locale) - 1} du fichier`);
		}
	}
}

if (erreurs) {
	console.error(`\n${erreurs} bloc(s) en erreur.`);
	process.exit(1);
}
console.log(`OK — ${blocsOk} bloc(s) <script>, ${lignesOk} lignes de JS, aucune erreur de syntaxe.`);
