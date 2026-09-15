# utils/cadence.py
# Plafond de requêtes PAR IP. Seul état de PROCESS du projet hors caches de marché :
# un dict en mémoire, aucune écriture en base (un compteur par IP dans CouchDB coûterait
# deux allers-retours par requête pour protéger… un aller-retour).
#
# ⚠️ Ce que ce plafond n'est PAS : il n'est ni partagé entre workers uvicorn (chacun a
# le sien, donc N workers = N fois le quota), ni conservé au redémarrage. C'est un
# ralentisseur, pas une serrure — la cadence par compte (utils/motdepasse) reste la
# protection qui, elle, tient dans la base.
#
# ⚠️ Derrière un reverse-proxy, `request.client.host` EST le proxy : tous les joueurs
# tomberaient dans le même seau et se bloqueraient les uns les autres. D'où
# `TRUST_PROXY_HOPS` (défaut 0 = pas de proxy, on croit la socket). À 1, on lit le
# DERNIER maillon de `X-Forwarded-For`, le seul que le proxy ait écrit lui-même : les
# précédents viennent du client et s'inventent. À N, le Nième en partant de la fin.

import os
import time

# Fenêtre glissante et quota. Large exprès : derrière un CGNAT ou le Wi-Fi d'une école,
# beaucoup de joueurs légitimes partagent une seule adresse.
FENETRE_SECONDES = 3600
DEMANDES_MAX_PAR_IP = 20

# Au-delà, on balaie les adresses sans appel récent. Borne la mémoire sous un flot
# distribué, sans payer un parcours complet du dict à chaque requête.
MAX_IP_SUIVIES = 4096

# {ip: [horodatages des appels retenus]}
_appels: dict[str, list[int]] = {}


def hops_de_confiance() -> int:
	"""Nombre de proxies de confiance devant l'app (`TRUST_PROXY_HOPS`). Une valeur
	illisible vaut 0 : une faute de frappe dans `.env` ne doit pas faire tomber
	l'endpoint à chaque requête, seulement rendre le plafond plus strict."""
	try:
		return max(0, int(os.getenv("TRUST_PROXY_HOPS", "0")))
	except ValueError:
		return 0


def ip_du_client(client_host: str, entete_forwarded: str = "", hops: int = None) -> str:
	"""L'adresse à compter. Pur : l'appelant extrait la socket et l'en-tête."""
	sauts = hops_de_confiance() if hops is None else hops
	if sauts > 0 and entete_forwarded:
		maillons = [m.strip() for m in entete_forwarded.split(",") if m.strip()]
		if len(maillons) >= sauts:
			return maillons[-sauts]
	return (client_host or "").strip()


def _balayer(maintenant: int, fenetre: int) -> None:
	for ip in [ip for ip, appels in _appels.items()
			   if not appels or maintenant - appels[-1] >= fenetre]:
		_appels.pop(ip, None)


def plafond_atteint(ip: str, *, now: int = None, maximum: int = None,
					fenetre: int = None) -> bool:
	"""Enregistre l'appel et dit s'il dépasse le quota.

	⚠️ Un appel REFUSÉ n'est pas compté : sinon un acharné resterait bloqué tant qu'il
	tape, et l'IP partagée derrière lui avec — la fenêtre doit pouvoir s'écouler."""
	if not ip:
		# Client non identifiable (pas de socket) : rien à attribuer, donc rien à
		# compter — un seau « sans adresse » bloquerait tout le monde d'un coup.
		return False

	maintenant = int(now if now is not None else time.time())
	fenetre = FENETRE_SECONDES if fenetre is None else fenetre
	maximum = DEMANDES_MAX_PAR_IP if maximum is None else maximum

	if len(_appels) > MAX_IP_SUIVIES:
		_balayer(maintenant, fenetre)

	recents = [t for t in _appels.get(ip, ()) if maintenant - t < fenetre]
	if len(recents) >= maximum:
		_appels[ip] = recents
		return True

	recents.append(maintenant)
	_appels[ip] = recents
	return False


def reinitialiser() -> None:
	"""Vide les compteurs — tests, et rien d'autre."""
	_appels.clear()
