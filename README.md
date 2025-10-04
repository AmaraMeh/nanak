# Elearning Monitor Bot (Moodle) – Python

Un bot Python qui se connecte à `https://elearning.univ-bejaia.dz`, surveille des espaces d'affichage Moodle, détecte les changements (ajouts, modifications, suppressions) et envoie des notifications dans Telegram.

## Fonctionnalités
- Connexion sécurisée à Moodle (login + token).
- Scraping robuste via `cloudscraper` + `BeautifulSoup`.
- Diffing précis entre l'ancien et le nouveau contenu.
- Stockage des snapshots dans Firebase Firestore (Admin SDK).
- Notifications Telegram (Bot API) avec résumés clairs.
- Planification automatique toutes les 15 minutes (APScheduler).
- Configuration des espaces via `config/spaces.json`.
- Dockerfile + système de service (systemd) fournis.

## Sécurité
- Identifiants et tokens chargés depuis des variables d'environnement (`.env`).
- Aucune fuite d'identifiants dans les logs.
- Fichiers sensibles ignorés par git via `.gitignore`.

## Prérequis
- Python 3.11+ (testé 3.13)
- Compte Firebase (Firestore) + clé de service
- Bot Telegram et `chat_id` cible

## Installation locale (venv)
```bash
# 1) Cloner le repo puis créer l'environnement
bash scripts/setup.sh

# 2) Copier et remplir .env
cp .env.example .env
# Éditer .env et renseigner :
# ELEARNING_USERNAME, ELEARNING_PASSWORD
# TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY

# 3) Lancer le bot
bash scripts/run.sh
```

Le bot démarre, effectue un premier check, puis planifie un check toutes les N minutes.

## Variables d'environnement
Voir `.env.example`. Champs essentiels :
- `ELEARNING_USERNAME`, `ELEARNING_PASSWORD`: identifiants Moodle
- `TELEGRAM_BOT_TOKEN`: token du bot
- `TELEGRAM_CHAT_ID`: ID du chat (user ou canal privé)
- `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY`: Firestore (service account)
- `SPACES_JSON`: chemin du fichier JSON contenant les espaces
- `CHECK_INTERVAL_MINUTES`: intervalle en minutes (par défaut 15)
- `REQUEST_TIMEOUT_SECONDS`: timeout HTTP (30s par défaut)
- `LOG_LEVEL`: `INFO` par défaut
- `NOTIFY_ON_FIRST_SNAPSHOT`: `true/false` notifier tout le contenu au premier run

## Configuration des espaces
Éditez `config/spaces.json` pour ajouter/supprimer des espaces. Exemple :
```json
{
  "spaces": [
    { "name": "Affichage Département d'Informatique", "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20008" }
  ]
}
```

## Docker
```bash
# Construire l'image
docker build -t elearning-bot:latest .

# Lancer en injectant l'env et en important le config
docker run --rm \
  --env-file .env \
  -v $(pwd)/config:/app/config:ro \
  elearning-bot:latest
```

## Déploiement via systemd (VPS)
- Copier le repo dans `/opt/elearning-bot`
- Créer le venv et installer les deps :
```bash
cd /opt/elearning-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```
- Créer `.env` en production, remplir les valeurs.
- Installer le service :
```bash
sudo cp tools/elearning-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now elearning-bot
sudo systemctl status elearning-bot
```

## Notes Telegram
- Obtenir `chat_id` en écrivant au bot puis en utilisant un bot utilitaire (ex: `@userinfobot`) ou via un petit script qui logge `update.message.chat.id`.
- Le bot enverra les notifications en DM si `TELEGRAM_CHAT_ID` est votre ID.

## Limitations et amélioration possibles
- Le parsing Moodle varie selon les thèmes/modules. Les sélecteurs génériques sont utilisés mais peuvent nécessiter un ajustement.
- Pour des diffs plus riches, hasher le HTML des sections/annonces spécifiquement.
- Ajouter la persistance des erreurs/transient backoff.
- Supporter la liste dynamique des espaces via Firestore.
