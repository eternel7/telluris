// sceau_visuel.js — icône dynamique du mot de passe, PARTAGÉE entre /auth et /reinitialisation.
// Même hachage partout : deux saisies identiques donnent le même symbole, ce qui vaut
// vérification à l'œil (sceau ↔ contre-sceau).
//
// Chargé en <script> classique (pas de module) : ces const/function sont visibles
// dans le script inline de la page (portée lexicale globale partagée).
// Contrat de markup : `<input class="pass-input">` immédiatement suivi de `<span class="pass-visual">`.

// ︎ = sélecteur de variante texte (glyphe monochrome, teinté par `color`).
const icons = [ "⚔️︎", "🛡️︎", "🏹︎", "🔮︎", "📜︎", "🏰︎", "🐉︎", "🔱︎", "💎︎", "⚖️︎",
				"🗝️︎", "⚒️︎", "🕯️︎", "🧪︎", "🏺︎", "👑︎", "🐺︎", "🦅︎", "🌲︎", "⛰️︎",
				"💀︎", "🕸️︎", "🔥︎", "❄️︎", "🌙︎", "☀️︎", "🧭︎", "⚓︎", "🐎︎", "🐾︎",
				"👣︎", "👁️︎", "🩸︎", "🌿︎", "🍄︎", "⛓️︎", "⚱️︎", "🧱︎"
];
const colors = ["#b87333", "#8a8f98", "#ffd700", "#e5e4e2", "#6fdcff", "#ff7f50", "#ffffff", "initial"];

function getHashCode(str) {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = str.charCodeAt(i) + ((hash << 5) - hash);
	}
	return Math.abs(hash);
}

function getContrastBg(hexcolor) {
	if (hexcolor === "initial") return "var(--parch)";
	hexcolor = hexcolor.replace("#", "");
	const r = parseInt(hexcolor.substr(0,2),16);
	const g = parseInt(hexcolor.substr(2,2),16);
	const b = parseInt(hexcolor.substr(4,2),16);
	const yiq = ((r*299)+(g*587)+(b*114))/1000;
	return (yiq >= 142) ? "var(--ink)" : "var(--parch)";
}

// Peint le symbole de `val` dans `visual` (ou le masque si la saisie est vide).
function afficherSceauVisuel(visual, val) {
	if (val.length > 0) {
		const hash = getHashCode(val);
		const iconIdx = hash % icons.length;
		const colorIdx = hash % colors.length;
		const selectedColor = colors[colorIdx];
		if (selectedColor === "initial") {
			visual.style.backgroundColor = "var(--parch)";
			visual.innerText = icons[iconIdx].replace('︎', '');
			visual.style.color = "";
		} else {
			visual.style.backgroundColor = getContrastBg(selectedColor);
			visual.innerText = icons[iconIdx];
			visual.style.color = selectedColor;
		}
		visual.classList.add('visible');
	} else {
		visual.classList.remove('visible');
	}
}

// Branche chaque `.pass-input` de la page sur son `.pass-visual` voisin.
// À appeler une fois le markup présent (script inline en fin de <body>).
function brancherSceauxVisuels() {
	document.querySelectorAll('.pass-input').forEach(input => {
		input.addEventListener('input', function() {
			afficherSceauVisuel(this.nextElementSibling, this.value);
		});
	});
}
