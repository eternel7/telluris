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

function fichiersAControler(args) {
	if (args.length) return args;
	const dir = path.join(__dirname, '..', 'templates');
	return fs.readdirSync(dir)
		.filter(f => f.endsWith('.html'))
		.map(f => path.join('templates', f));
}

let erreurs = 0, blocsOk = 0, lignesOk = 0;

for (const fichier of fichiersAControler(process.argv.slice(2))) {
	const html = fs.readFileSync(fichier, 'utf8');
	// Les <script src="..."> n'ont pas de corps à contrôler ici (scripts/ est servi tel quel).
	const blocs = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)];
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
