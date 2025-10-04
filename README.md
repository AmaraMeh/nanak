### Elearning Monitor Bot (Moodle) – Bejaia

Un bot Node.js qui se connecte à `elearning.univ-bejaia.dz`, surveille une liste d'espaces d'affichage, stocke des instantanés dans Firebase (Firestore) et vous envoie des notifications Telegram en DM à chaque changement.

- **Scraping sécurisé**: Playwright (Chromium headless)
- **Stockage**: Firebase Firestore via Admin SDK (service account)
- **Notifications**: Telegram Bot API (DM)
- **Automatisation**: cron intégré (toutes les 15 minutes par défaut)

### 1) Prérequis
- Node.js 20+
- Un bot Telegram (via @BotFather) et votre chat ID
- Un projet Firebase avec un compte de service (JSON) et Firestore activé

### 2) Installation
```bash
# Cloner et installer
npm install

# Installer Chromium pour Playwright
npx playwright install chromium

# Configurer l'environnement
cp .env.example .env
# Ouvrir .env et remplir les valeurs (ne partagez jamais ce fichier)
```

Variables indispensables dans `.env`:
- `ELEARNING_USERNAME` / `ELEARNING_PASSWORD` (vos identifiants Moodle)
- `TELEGRAM_BOT_TOKEN` (token du bot Telegram)
- `TELEGRAM_CHAT_ID` (votre chat ID, optionnel si vous laissez l'auto-détection)
- `GOOGLE_APPLICATION_CREDENTIALS` (chemin vers le JSON du service account) ou `FIREBASE_SERVICE_ACCOUNT_JSON` (le JSON inline)

### 3) Lancer
```bash
# Build
npm run build

# Démarrer (exécute immédiatement puis toutes les 15 min)
npm start
```

Au premier lancement, si `TELEGRAM_CHAT_ID` est vide, envoyez un message à votre bot (ex: `/start`). Le bot tentera d'auto-détecter votre chat ID via `getUpdates`.

### 4) Ajouter / retirer des espaces
Modifiez `src/courses.ts` et ajustez le tableau `COURSES`. Redémarrez le bot.

### 5) Déploiement rapide avec Docker
Fichier `Dockerfile` fourni (base Playwright). Exemple:
```bash
# Build image
docker build -t elearning-monitor .

# Run container (montez votre .env et service account)
docker run -it --rm \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  elearning-monitor
```

### 6) Sécurité
- Ne loguez jamais vos secrets. `.env` est ignoré par git.
- Les identifiants sont chargés via variables d'environnement.
- Firestore est accédé via Admin SDK (service account) côté serveur (pas de SDK web en clair).

### 7) Limitations
- Si le site active un CAPTCHA ou SSO non standard, l'automatisation peut échouer.
- Le diff est heuristique (liens/titres). Il fonctionne bien pour la plupart des cas d'usage Moodle.

### 8) Scripts utiles
- Changer la fréquence: éditez `CRON_SCHEDULE` dans `.env` (ex: `*/10 * * * *`).
- Mode headless on/off: `PLAYWRIGHT_HEADLESS=true|false`.
- Concurrence de traitement: `SCRAPE_CONCURRENCY`.

### 9) Support
En cas d'erreur de connexion, vérifiez identifiants, disponibilité du site et rejouez.
