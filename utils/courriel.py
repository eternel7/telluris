# utils/courriel.py
# Envoi de courriel — seule dépendance sortante du serveur, `smtplib` de la stdlib.
# Aucune logique métier ici : l'appelant compose sujet et corps (cf. utils/motdepasse).
#
# Configuration par variables d'environnement (docker compose `env_file: .env`) :
#   SMTP_HOST · SMTP_PORT (587) · SMTP_USER · SMTP_PASSWORD · SMTP_FROM
#   SMTP_SSL=1     → TLS implicite (port 465), sinon STARTTLS
#   SMTP_STARTTLS=0 → coupe STARTTLS (relais local en clair)
#
# ⚠️ SANS `SMTP_HOST`, rien n'est envoyé : le message est ÉCRIT DANS LE JOURNAL du
# serveur (niveau WARNING, corps compris). C'est ce qui rend le parcours « sceau
# oublié » jouable sur une instance de développement sans relais SMTP — le lien se
# lit dans `docker compose logs`. Une instance publique DOIT donc configurer SMTP,
# sinon les liens de réinitialisation défilent dans ses journaux.
#
# Les variables sont lues À L'APPEL, jamais à l'import : un `.env` corrigé prend effet
# au redémarrage du conteneur sans dépendre de l'ordre des imports.

import logging
import os
import smtplib
from email.message import EmailMessage

_logger = logging.getLogger("telluris.courriel")


def smtp_configure() -> bool:
	return bool(os.getenv("SMTP_HOST"))


def expediteur() -> str:
	return os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "no-reply@telluris"


def envoyer(destinataire: str, sujet: str, corps: str) -> bool:
	"""True si le message est parti. False si SMTP n'est pas configuré ou si le relais
	a refusé — l'appelant ne doit RIEN en dire au client (cf. MESSAGE_DEMANDE)."""
	if not destinataire:
		return False

	if not smtp_configure():
		_logger.warning(
			"SMTP non configuré — courriel NON envoyé à %s.\nSujet : %s\n%s",
			destinataire, sujet, corps,
		)
		return False

	message = EmailMessage()
	message["From"] = expediteur()
	message["To"] = destinataire
	message["Subject"] = sujet
	message.set_content(corps)

	host = os.getenv("SMTP_HOST")
	port = int(os.getenv("SMTP_PORT", "587"))
	user = os.getenv("SMTP_USER")
	password = os.getenv("SMTP_PASSWORD")
	try:
		if os.getenv("SMTP_SSL") == "1":
			serveur = smtplib.SMTP_SSL(host, port, timeout=10)
		else:
			serveur = smtplib.SMTP(host, port, timeout=10)
		with serveur:
			if os.getenv("SMTP_SSL") != "1" and os.getenv("SMTP_STARTTLS", "1") != "0":
				serveur.starttls()
			if user and password:
				serveur.login(user, password)
			serveur.send_message(message)
		return True
	except Exception:
		_logger.exception("Échec de l'envoi du courriel à %s", destinataire)
		return False
