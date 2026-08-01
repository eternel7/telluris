// ─── Paramètres ────────────────────────────────────────────────────────────
const MAX_HEIGHT = 10;
const BLUR_DIST  = 8;
var GRID_X_SIZE = 0;
var GRID_Y_SIZE = 0;
var CURRENT_GRID = [];
var CURRENT_LINKS = [];
var CURRENT_LOCATION = SERVER_DATA.lieu;

function initializeMap(data) {
	// Initialisation de la carte avec les données reçues	
	GRID_X_SIZE = data.dims.x;
	GRID_Y_SIZE = data.dims.y;
	CURRENT_GRID = data.grid;
	CURRENT_LINKS = data.links;
	// --- Bloc de Debugging ---
	console.group("Données Telluris Chargées");
	console.log("Dimensions de la carte :", GRID_X_SIZE, "x", GRID_Y_SIZE);

	if (CURRENT_LINKS && CURRENT_LINKS.length > 0) {
		console.log(`Nombre de liens trouvés : ${CURRENT_LINKS.length}`);
		
		CURRENT_LINKS.forEach((link, index) => {
			// On identifie le noeud qui correspond au lieu actuel (ex: lutecia)
			// Note: Remplacez 'lutecia' par une variable si le lieu est dynamique
			const depart = link.nodes.find(n => n.lieu === CURRENT_LOCATION);
			const destination = link.nodes.find(n => n.lieu !== CURRENT_LOCATION);

			if (depart && destination) {
				console.log(`Lien #${index + 1}:`);
				console.log(`  - Départ (ici) : [${depart.pos[0]}, ${depart.pos[1]}]`);
				console.log(`  - Vers : ${destination.lieu} en [${destination.pos[0]}, ${destination.pos[1]}]`);
			}
		});
	} else {
		console.warn("Aucun lien (CURRENT_LINKS) n'a été récupéré.");
	}
	console.groupEnd();
}

async function loadMapData(lieuId) {
    try {
        const response = await fetch(`/api/map-data/${lieuId}`);
        const data = await response.json();
        
        initializeMap(data);
    } catch (error) {
        console.error("Erreur lors du chargement :", error);
    }
}

// Appeler la fonction au démarrage
loadMapData(CURRENT_LOCATION);

document.documentElement.style.setProperty('--max-height', MAX_HEIGHT);
document.documentElement.style.setProperty('--blur-dist',  BLUR_DIST);

// ─── Logique de positionnement ──────────────────────────────────────────────
// On stocke désormais la position en "cases" (grid units) plutôt qu'en pixels
const startX = 2, startY = 21, startRotation = 3; 
let gridX = startX, gridY = startY; // Position logique sur la grille
let angle = startRotation * 90;

const pivot = document.getElementById('rotation-pivot');
const img   = document.getElementById('bg-image');
const zone  = document.getElementById('swipe-zone');
let step = 0, touchStartX = 0, touchStartY = 0;

function startGame() {
    document.getElementById('start-screen').style.display = 'none';
    document.querySelector('.viewport').style.visibility = 'visible';
    document.querySelector('.ui-container').style.visibility = 'visible';
    document.querySelector('.controls').style.visibility = 'visible';
    resetPos();
}

// ─── Logique de déplacement ─────────────────────────────────────────────────
function updateStep() {
    const width = window.innerWidth;
    const viewWidth = width > 800 ? width * 0.5 : width;
    step = viewWidth / 17;
    document.documentElement.style.setProperty('--step', step + 'px');
}

function resetPos() {
    updateStep();
    gridX = startX;
    gridY = startY;
    angle = startRotation * 90;
    update();
}

function move(viewDx, viewDy) {
    const rad = (angle * Math.PI) / 180;
    // Calcul du déplacement logique
    const worldDx = viewDx * Math.cos(rad) + viewDy * Math.sin(rad);
    const worldDy = -viewDx * Math.sin(rad) + viewDy * Math.cos(rad);
    
    let nextX = Math.round(gridX - worldDx); // On inverse car on déplace la carte, pas le token
    let nextY = Math.round(gridY - worldDy);

    // Limites (basées sur une image de GRID_X_SIZExGRID_Y_SIZE cases)
    if (nextX >= 0.5 && nextX <= GRID_X_SIZE + 0.5) gridX = nextX;
    if (nextY >= 0.5 && nextY <= GRID_Y_SIZE + 0.5) gridY = nextY;
    console.log(`  - Position : [${gridX}, ${gridY}]`);
    update();
}

function rotate(dir) { 
    angle += dir * 90; 
    update(); 
}

function update() {
    updateStep(); // Recalcule le step actuel
    const imgXSize = step * GRID_X_SIZE;
    const imgYSize = step * GRID_Y_SIZE;
    
    // Conversion des coordonnées logiques (gridX/Y) en pixels pour l'affichage
    // On centre l'image, puis on décale selon la position dans la grille
    const pxX = (imgXSize / 2) - (step * (gridX - 0.5));
    const pxY = (imgYSize / 2) - (step * (gridY - 0.5));

    pivot.style.transform = `rotate(${angle}deg)`;
    img.style.transform = `translate(${pxX - (imgXSize/2)}px, ${pxY - (imgYSize/2)}px)`;
}

// ─── Events ────────────────────────────────────────────────────────────────
window.onresize = () => {
    update(); // L'appel à update() recalcule tout en fonction du nouveau step
};


zone.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
}, {passive: true});

zone.addEventListener('touchend', (e) => {
    let dx = e.changedTouches[0].screenX - touchStartX;
    let dy = e.changedTouches[0].screenY - touchStartY;
    if (Math.abs(dx) > Math.abs(dy)) {
        if (Math.abs(dx) > GRID_X_SIZE) move(dx > 0 ? 1 : -1, 0);
    } else {
        if (Math.abs(dy) > GRID_Y_SIZE) move(0, dy < 0 ? -1 : 1);
    }
}, {passive: true});