// conflit.js — un conflit d'écriture (HTTP 409 « Conflit de sauvegarde — réessayez. ») dit en
// douceur au joueur.
//
// Deux actions du MÊME joueur se sont chevauchées côté serveur : la base a refusé la seconde,
// rien n'est perdu, il suffit de recommencer. Ce n'est pas une « Erreur » : pas d'alert(), pas
// de jargon — une bulle discrète, et une seule à la fois.
//
// Chargé dans le <head> de /play et de /combat. Fonctions PURES (aucun DOM) :
// `showToast` y passe tous ses messages, les rares alert() restants s'en servent pour choisir.
// Verrouillé par dev/test_conflit_client.js, qui relit les messages des routeurs.

const MESSAGE_CONFLIT = '⏳ Action non prise en compte — recommencez.';

// Les libellés serveur : « Conflit — … », « Conflit de sauvegarde — … », « Conflit de
// suppression — … », « Conflit d'écriture, … », avec ou sans préfixe (« Erreur : »).
function estConflit(texte) {
	return /Conflit( —| de sauvegarde| de suppression| d['’]écriture)/.test(String(texte ?? ''));
}

// Le message à afficher : celui du conflit, adouci ; tout autre texte, tel quel.
function adoucirConflit(texte) {
	return estConflit(texte) ? MESSAGE_CONFLIT : texte;
}
