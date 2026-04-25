// ─── Paramètres ────────────────────────────────────────────────────────────
const MAX_HEIGHT = 10;
const BLUR_DIST  = 8;

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
const threshold = 30;

function startGame() {
    document.getElementById('start-screen').style.display = 'none';
    document.querySelector('.viewport').style.visibility = 'visible';
    document.querySelector('.controls').style.visibility = 'visible';
    resetPos();
}

// ─── Génération des clip-paths ──────────────────────────────────────────────

function buildViewportClipPath(mh) {
    const s = 'var(--step)';
    const pts = [];
    for (let r = 0; r < mh; r++) {
        const hw = (mh - 1 - r) * 2 + 0.5;
        pts.push(`calc(50% + ${s} * ${hw}) calc(${s} * ${r})`);
        if (r < mh - 1) {
            const hwNext = (mh - 1 - (r + 1)) * 2 + 0.5;
            pts.push(`calc(50% + ${s} * ${hwNext}) calc(${s} * ${r + 1})`);
        }
    }
    pts.push(`calc(50% + ${s} * 0.5) 100%`);
    pts.push(`calc(50% - ${s} * 0.5) 100%`);
    for (let r = mh - 1; r >= 0; r--) {
        const hw = (mh - 1 - r) * 2 + 0.5;
        if (r < mh - 1) {
            const hwNext = (mh - 1 - (r + 1)) * 2 + 0.5;
            pts.push(`calc(50% - ${s} * ${hwNext}) calc(${s} * ${r + 1})`);
        }
        pts.push(`calc(50% - ${s} * ${hw}) calc(${s} * ${r})`);
    }
    return `polygon(${pts.join(', ')})`;
}

function buildBlurClipPath(mh, bd) {
    const s = 'var(--step)';
    const blurStart = mh - bd;
    const outer = `0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%`;
    const inner = [];
    inner.push(`calc(50% + ${s} * 0.5) calc(${s} * ${blurStart})`);
    inner.push(`calc(50% - ${s} * 0.5) calc(${s} * ${blurStart})`);
    for (let r = blurStart; r < mh; r++) {
        const hw = 0.5 + (r - blurStart);
        inner.push(`calc(50% - ${s} * ${hw}) calc(${s} * ${r})`);
        inner.push(`calc(50% - ${s} * ${hw + 1}) calc(${s} * ${r + 1})`);
    }
    const hwBottom = bd + 1.5;
    inner.push(`calc(50% - ${s} * ${hwBottom}) calc(${s} * ${mh})`);
    inner.push(`calc(50% + ${s} * ${hwBottom}) calc(${s} * ${mh})`);
    for (let r = mh - 1; r >= blurStart; r--) {
        const hw = 0.5 + (r - blurStart);
        inner.push(`calc(50% + ${s} * ${hw + 1}) calc(${s} * ${r + 1})`);
        inner.push(`calc(50% + ${s} * ${hw}) calc(${s} * ${r})`);
    }
    inner.push(`calc(50% + ${s} * 0.5) calc(${s} * ${blurStart})`);
    return `polygon(${outer}, ${inner.join(', ')})`;
}

const viewport = document.querySelector('.viewport');
const viewportStyle = document.createElement('style');
viewportStyle.textContent = `
    .viewport { clip-path: ${buildViewportClipPath(MAX_HEIGHT)}; }
    .viewport::after { clip-path: ${buildBlurClipPath(MAX_HEIGHT, BLUR_DIST)}; }
`;
document.head.appendChild(viewportStyle);


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
    
    let nextX = gridX - worldDx; // On inverse car on déplace la carte, pas le token
    let nextY = gridY - worldDy;

    // Limites (basées sur une image de 30x30 cases)
    if (nextX >= 0.5 && nextX <= 30.5) gridX = nextX;
    if (nextY >= 0.5 && nextY <= 30.5) gridY = nextY;
    
    update();
}

function rotate(dir) { 
    angle += dir * 90; 
    update(); 
}

function update() {
    updateStep(); // Recalcule le step actuel
    const imgSize = step * 30;
    
    // Conversion des coordonnées logiques (gridX/Y) en pixels pour l'affichage
    // On centre l'image, puis on décale selon la position dans la grille
    const pxX = (imgSize / 2) - (step * (gridX - 0.5));
    const pxY = (imgSize / 2) - (step * (gridY - 0.5));

    pivot.style.transform = `rotate(${angle}deg)`;
    img.style.transform = `translate(${pxX - (imgSize/2)}px, ${pxY - (imgSize/2)}px)`;
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
        if (Math.abs(dx) > threshold) move(dx > 0 ? 1 : -1, 0);
    } else {
        if (Math.abs(dy) > threshold) move(0, dy < 0 ? -1 : 1);
    }
}, {passive: true});