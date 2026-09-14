// zones_effet.js — MIROIR CLIENT de la géométrie des zones d'effet (`utils/zones_effet.py`).
//
// Sert UNIQUEMENT à l'APERÇU : pendant le ciblage d'un sort ou d'une compétence de zone,
// le joueur doit voir les cases qui vont brûler avant de payer son action. La VÉRITÉ reste
// au serveur — c'est lui qui décide qui est touché, ce fichier ne fait que redessiner la
// même figure. Contrairement à `deplacement.js` (qui EST la règle, faute de règle serveur),
// un écart ici n'ouvre aucun exploit : il ment seulement à l'œil. Ce qui suffit à le rendre
// grave — un aperçu qui ment est pire que pas d'aperçu — d'où `dev/test_zones_effet_client.js`,
// qui rejoue les mêmes cas que `tests/test_zones_effet.py`.
//
// Chargé en <script> classique (pas de module), sans dépendance : ces fonctions sont
// visibles depuis le script inline de la page.
//
// ⚠️ Toute modification de la géométrie se fait DES DEUX CÔTÉS. Le contrat (formes,
// ancre, orientation, `decalage` compté depuis l'ancre incluse) est documenté en tête de
// `utils/zones_effet.py` et n'est pas répété ici.

const ZONE_FORMES = ['cercle', 'carre', 'rectangle', 'cone'];
const ZONE_ANGLE_DEFAUT = 90;
// Mêmes bornes que le serveur : un doc déjà borné à l'écriture repasse inchangé, et un
// payload bricolé ne fait pas tourner la boucle d'aperçu sur la moitié de la carte.
const ZONE_RAYON_MAX = 8;
const ZONE_LONGUEUR_MAX = 12;
const ZONE_LARGEUR_MAX = 12;
const ZONE_DECALAGE_MAX = 12;

// Axe monde d'un `facing` — même convention que `rot()` de combat_telluris.html : l'écran
// regarde vers (0, -1) et le monde tourne sous un joueur qui reste face au haut.
const ZONE_AXE_FACING = { 0: [0, -1], 90: [1, 0], 180: [0, 1], 270: [-1, 0] };
// Les huit directions dans l'ordre trigonométrique depuis l'Est (index de l'arrondi d'atan2).
const ZONE_DIRECTIONS_8 = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];

// Miroir de `consommables._as_int` : entier >= 0, 0 pour tout ce qui ne s'y ramène pas.
function _zoneAsInt(v) {
	const n = parseInt(v, 10);
	return isFinite(n) ? Math.max(0, n) : 0;
}
// Miroir de `zones_effet._champ` : `defaut` pour une clé ABSENTE seulement — une valeur
// écrite, fût-elle 0 ou illisible, passe par _zoneAsInt comme côté serveur.
function _zoneBorne(v, defaut, mini, maxi) {
	const n = (v === undefined || v === null) ? defaut : _zoneAsInt(v);
	return Math.max(mini, Math.min(maxi, n));
}

// Miroir de `normaliser_zone` : rend null pour un bloc absent ou de forme inconnue (⇒ la
// capacité ne touche qu'une case), sinon un objet dont TOUTES les clés sont présentes.
// Le payload serveur arrive déjà normalisé ; repasser dessus ne coûte rien et rend ce
// fichier utilisable tel quel sur une zone écrite à la main (aperçu d'admin, test).
function normaliserZone(raw) {
	if (!raw || typeof raw !== 'object') return null;
	const forme = String(raw.forme || '').trim().toLowerCase();
	if (ZONE_FORMES.indexOf(forme) < 0) return null;
	let origine = String(raw.origine || 'cible').trim().toLowerCase();
	if (origine !== 'cible' && origine !== 'lanceur') origine = 'cible';
	let orientation = String(raw.orientation || 'cible').trim().toLowerCase();
	if (orientation !== 'cible' && orientation !== 'facing') orientation = 'cible';
	return {
		forme: forme,
		origine: origine,
		orientation: orientation,
		rayon: _zoneBorne(raw.rayon, 1, 0, ZONE_RAYON_MAX),
		longueur: _zoneBorne(raw.longueur, 1, 1, ZONE_LONGUEUR_MAX),
		largeur: _zoneBorne(raw.largeur, 1, 1, ZONE_LARGEUR_MAX),
		decalage: _zoneBorne(raw.decalage, 0, 0, ZONE_DECALAGE_MAX),
		angle: _zoneBorne(raw.angle, ZONE_ANGLE_DEFAUT, 1, 360),
	};
}

function zoneOrientee(zone) {
	return !!zone && (zone.forme === 'rectangle' || zone.forme === 'cone');
}

function zoneAxeFacing(facing) {
	const q = ((parseInt(facing, 10) || 0) % 360 + 360) % 360;
	return ZONE_AXE_FACING[q] || ZONE_AXE_FACING[0];
}

// Case d'ancre : celle du lanceur ou celle de la cible désignée.
function zoneAncre(zone, lanceur, cible) {
	return (zone && zone.origine === 'lanceur') ? [lanceur[0], lanceur[1]] : [cible[0], cible[1]];
}

// Axe de la forme, ramené au huitième de tour le plus proche. Repli sur le facing quand
// la cible est posée sur le lanceur (zone ancrée sur soi, sans direction à lire).
function zoneAxe(zone, lanceur, cible, facing) {
	if (zone && zone.orientation === 'facing') return zoneAxeFacing(facing);
	const dx = cible[0] - lanceur[0], dy = cible[1] - lanceur[1];
	if (dx === 0 && dy === 0) return zoneAxeFacing(facing);
	const k = ((Math.round(Math.atan2(dy, dx) / (Math.PI / 4)) % 8) + 8) % 8;
	return ZONE_DIRECTIONS_8[k];
}

// Géométrie PURE : ni bornes de carte, ni terrain, ni ligne de vue (cf. casesEffet).
// Rendue triée par (y, x), comme côté serveur — les deux listes se comparent telles quelles.
function casesZone(zone, lanceur, cible, facing) {
	if (!zone || ZONE_FORMES.indexOf(zone.forme) < 0) return [];
	const ancre = zoneAncre(zone, lanceur, cible);
	const ax = ancre[0], ay = ancre[1];
	const cases = [];

	if (zone.forme === 'cercle' || zone.forme === 'carre') {
		const r = zone.rayon;
		for (let dy = -r; dy <= r; dy++) {
			for (let dx = -r; dx <= r; dx++) {
				// `carre` = disque de Chebyshev (les 8 cases autour à rayon 1) ;
				// `cercle` = disque euclidien (la croix à rayon 1). Deux figures, pas
				// deux écritures de la même.
				if (zone.forme === 'carre' || dx * dx + dy * dy <= r * r) cases.push([ax + dx, ay + dy]);
			}
		}
		return _zoneTrier(cases);
	}

	const axe = zoneAxe(zone, lanceur, cible, facing);
	const fx = axe[0], fy = axe[1];
	const debut = zone.decalage;
	const fin = debut + zone.longueur - 1;

	if (zone.forme === 'rectangle') {
		// Perpendiculaire directe : diagonale elle aussi sur un axe diagonal, pour que le
		// balayage en biais couvre une bande en biais et non un escalier.
		const px = -fy, py = fx;
		const demi = Math.floor((zone.largeur - 1) / 2);   // largeur paire ⇒ une case de plus à droite
		for (let i = debut; i <= fin; i++) {
			for (let j = -demi; j <= zone.largeur - demi - 1; j++) {
				cases.push([ax + i * fx + j * px, ay + i * fy + j * py]);
			}
		}
		return _zoneTrier(cases);
	}

	// Cône : anneaux de Chebyshev debut..fin, filtrés par le cosinus à l'axe (pas d'atan2
	// par case). La marge accepte la diagonale exacte d'une ouverture de 90°.
	const cosMin = Math.cos((zone.angle / 2) * Math.PI / 180) - 1e-9;
	const normeAxe = Math.hypot(fx, fy);
	for (let dy = -fin; dy <= fin; dy++) {
		for (let dx = -fin; dx <= fin; dx++) {
			const d = Math.max(Math.abs(dx), Math.abs(dy));
			if (d < debut || d > fin) continue;
			if (d === 0) { cases.push([ax, ay]); continue; }   // l'ancre : aucun angle à mesurer
			if ((dx * fx + dy * fy) / (Math.hypot(dx, dy) * normeAxe) >= cosMin) cases.push([ax + dx, ay + dy]);
		}
	}
	return _zoneTrier(cases);
}

function _zoneTrier(cases) {
	const vues = new Set();
	const out = [];
	cases.forEach(c => {
		const cle = c[0] + ',' + c[1];
		if (vues.has(cle)) return;
		vues.add(cle);
		out.push(c);
	});
	out.sort((a, b) => (a[1] - b[1]) || (a[0] - b[0]));
	return out;
}

// Miroir de `combat._passable` : case TRANSPARENTE à la vision (terrain >= 1). ⚠️ Ce n'est
// PAS `caseFranchissable` de deplacement.js — une falaise (3) laisse passer un souffle et
// une flèche, alors qu'elle interdit le pas à qui ne vole pas.
// ⚠️ `cells` absente ⇒ TRUE ici (on dessine la forme entière), FALSE côté serveur (rien
// n'est touché). La divergence est volontaire et sans portée : la grille de combat porte
// toujours ses `cells`, et un aperçu vide vaudrait moins qu'un aperçu non filtré.
function caseTransparenteZone(cells, x, y) {
	if (!cells) return true;
	const row = cells[y];
	return !!row && row[x] >= 1;
}

// Miroir de `combat._line_of_sight` (Bresenham) : bloquée par une case INTERMÉDIAIRE non
// transparente, jamais par les extrémités.
function ligneDeVueZone(cells, x0, y0, x1, y1) {
	if (!cells) return true;
	const dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
	const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
	let err = dx - dy, x = x0, y = y0;
	for (;;) {
		if (!(x === x0 && y === y0) && !(x === x1 && y === y1) && !caseTransparenteZone(cells, x, y)) return false;
		if (x === x1 && y === y1) return true;
		const e2 = 2 * err;
		if (e2 > -dy) { err -= dy; x += sx; }
		if (e2 < dx) { err += dx; y += sy; }
	}
}

// Cases RÉELLEMENT touchées : la forme, moins les murs et moins ce que l'ancre ne voit pas.
// `dims` (facultatif) écarte en plus ce qui sort de la carte — l'aperçu n'a rien à peindre
// hors du décor. Miroir de `zones_effet.cases_effet`, dont les deux prédicats sont ici
// figés sur la grille de combat (le serveur, lui, les reçoit injectés).
function casesEffet(zone, lanceur, cible, facing, cells, dims) {
	const ancre = zoneAncre(zone, lanceur, cible);
	return casesZone(zone, lanceur, cible, facing).filter(c => {
		const x = c[0], y = c[1];
		if (dims && (x < 0 || y < 0 || x >= dims.x || y >= dims.y)) return false;
		if (!caseTransparenteZone(cells, x, y)) return false;
		if (x === ancre[0] && y === ancre[1]) return true;
		return ligneDeVueZone(cells, ancre[0], ancre[1], x, y);
	});
}

// Étiquette courte d'une zone, pour l'infobulle d'une case de la barre d'action et la
// liste des sorts de la fiche. Rend '' quand il n'y a pas de zone : l'appelant concatène
// sans condition.
function libelleZone(zone) {
	if (!zone) return '';
	const ou = zone.origine === 'lanceur' ? 'autour de soi' : 'sur la cible';
	if (zone.forme === 'cercle') return `💥 cercle rayon ${zone.rayon} ${ou}`;
	if (zone.forme === 'carre') return `💥 carré rayon ${zone.rayon} ${ou}`;
	const depart = zone.origine === 'lanceur' ? 'devant soi' : 'depuis la cible';
	if (zone.forme === 'rectangle') return `💥 ${zone.longueur}×${zone.largeur} cases ${depart}`;
	return `💥 cône ${zone.longueur} cases (${zone.angle}°) ${depart}`;
}
