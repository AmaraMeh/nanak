# 🤖 Bot eLearning Notifier - Université de Béjaïa

Un bot Python automatisé qui surveille les espaces d'affichage de la plateforme eLearning de l'Université de Béjaïa et envoie des notifications Telegram en temps réel dès qu'un changement est détecté.

## ✨ Fonctionnalités

- 🔐 **Connexion sécurisée** à la plateforme eLearning
- 📚 **Surveillance automatique** de 42 espaces d'affichage
- 🔍 **Premier scan complet** : Extraction de tout le contenu existant au démarrage
- 📱 **Notifications Telegram** intelligentes avec gestion du spam initial
- 💾 **Stockage Firebase** avec fallback local sécurisé
- ⏰ **Surveillance continue** toutes les 15 minutes
- 🛡️ **Sécurité maximale** : identifiants stockés dans des variables d'environnement
- 📊 **Monitoring avancé** avec statistiques détaillées et rapports
- 🔄 **Gestion d'erreurs robuste** avec retry automatique et récupération
- 🚀 **Performance optimisée** avec scraping rapide et efficace

## 🚀 Installation Rapide

### 1. Prérequis

- Python 3.8+
- Chrome/Chromium installé
- Compte Telegram avec bot créé

### 2. Installation

```bash
# Cloner le projet
git clone <votre-repo>
cd elearning-notifier-bot

# Installation automatique
python setup.py

# Ou installation manuelle
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copier le fichier de configuration
cp .env.example .env

# Éditer avec vos identifiants
nano .env
```

### 4. Premier démarrage

```bash
python run_bot.py
```

## ⚙️ Configuration

### Variables d'environnement (.env)

```env
# Identifiants eLearning
ELEARNING_USERNAME=242433047620
ELEARNING_PASSWORD=100060196001960005

# Configuration Telegram
TELEGRAM_TOKEN=8489609270:AAGVP7q0VL5RID1OeEWXNjTC1SC0xPhx5Xo
TELEGRAM_API_ID=24358290
TELEGRAM_API_HASH=847c2d71463d5940bc55648eb9241b51
```

### Espaces surveillés

Le bot surveille automatiquement 42 espaces d'affichage incluant :

- Départements d'ingénierie (Génie Civil, Mécanique, Électrique, etc.)
- Départements scientifiques (Mathématiques, Physique, Chimie, etc.)
- Départements de médecine et pharmacie
- Départements de droit et sciences économiques
- Départements de langues et littératures
- Et bien d'autres...

## 📱 Utilisation

### Démarrage du bot

```bash
# Démarrage simple
python run_bot.py

# Démarrage en arrière-plan
nohup python run_bot.py &
```

### Service systemd (recommandé)

```bash
# Activer le service
sudo systemctl enable elearning-bot

# Démarrer le service
sudo systemctl start elearning-bot

# Vérifier le statut
sudo systemctl status elearning-bot

# Voir les logs
sudo journalctl -u elearning-bot -f
```

### Commandes utiles

```bash
# Arrêter le service
sudo systemctl stop elearning-bot

# Redémarrer le service
sudo systemctl restart elearning-bot

# Désactiver le service
sudo systemctl disable elearning-bot

# Voir les statistiques
python stats_command.py print

# Envoyer les statistiques via Telegram
python stats_command.py telegram

# Réinitialiser les statistiques
python stats_command.py reset
```

## 🔧 Architecture

### Structure du projet

```
elearning-notifier-bot/
├── main.py                 # Point d'entrée principal
├── run_bot.py             # Script de démarrage simplifié
├── setup.py               # Script de configuration
├── config.py              # Configuration centralisée
├── elearning_scraper.py   # Scraping eLearning optimisé
├── firebase_manager.py    # Gestion Firebase
├── change_detector.py     # Détection de changements améliorée
├── telegram_notifier.py   # Notifications Telegram intelligentes
├── monitoring.py          # Monitoring et statistiques
├── stats_command.py       # Commandes de statistiques
├── test_bot.py            # Tests complets
├── requirements.txt       # Dépendances Python
├── .env.example          # Exemple de configuration
├── README.md             # Documentation
├── GUIDE_COMPLET.md      # Guide détaillé
├── INSTALLATION_GUIDE.txt # Guide d'installation
├── Dockerfile            # Support Docker
├── docker-compose.yml    # Orchestration Docker
├── start.sh              # Script de démarrage bash
└── local_storage/        # Stockage local (fallback)
```

### Flux de fonctionnement

1. **Démarrage** : Le bot se connecte à eLearning et envoie un message de démarrage
2. **Premier scan** : Extraction complète de tout le contenu existant (peut générer beaucoup de notifications)
3. **Scraping optimisé** : Récupération rapide du contenu de tous les espaces surveillés
4. **Comparaison intelligente** : Comparaison avec la version précédente stockée
5. **Détection avancée** : Identification des changements (ajouts, modifications, suppressions)
6. **Notifications groupées** : Envoi de messages Telegram optimisés pour éviter le spam
7. **Monitoring** : Enregistrement des statistiques et gestion des erreurs
8. **Stockage sécurisé** : Sauvegarde du nouveau contenu avec fallback local
9. **Attente** : Pause de 15 minutes avant la prochaine vérification

## 📊 Types de changements détectés

### Premier scan (extraction complète)
- 📂 **Sections existantes** avec comptage des éléments
- 📋 **Activités existantes** (forums, devoirs, etc.)
- 📚 **Ressources existantes** (fichiers, liens, etc.)
- 📄 **Fichiers existants** avec détails

### Surveillance continue
- ➕ **Nouvelles sections** ajoutées
- ➖ **Sections supprimées**
- ➕ **Nouvelles activités** (forums, devoirs, etc.)
- ➖ **Activités supprimées**
- ➕ **Nouvelles ressources** (fichiers, liens, etc.)
- ➖ **Ressources supprimées**
- 📁 **Nouveaux fichiers** ajoutés
- 🗑️ **Fichiers supprimés**
- ✏️ **Descriptions modifiées**

## 🔒 Sécurité

- **Identifiants sécurisés** : Stockés dans des variables d'environnement
- **Pas de logs sensibles** : Les mots de passe ne sont jamais affichés
- **Connexion HTTPS** : Toutes les communications sont chiffrées
- **Fallback local** : Fonctionnement même sans Firebase

## 🐛 Dépannage

### Problèmes courants

#### Erreur de connexion eLearning
```bash
# Vérifier les identifiants
cat .env | grep ELEARNING

# Tester la connexion manuelle
python -c "from elearning_scraper import ELearningScraper; s = ELearningScraper(); print(s.login())"
```

#### Erreur Telegram
```bash
# Vérifier le token
cat .env | grep TELEGRAM_TOKEN

# Envoyer un message au bot pour obtenir le chat ID
```

#### Erreur Chrome/Selenium
```bash
# Installer Chrome
sudo apt update
sudo apt install google-chrome-stable

# Ou utiliser Chromium
sudo apt install chromium-browser
```

### Logs

```bash
# Voir les logs du bot
tail -f bot.log

# Logs systemd
sudo journalctl -u elearning-bot -f
```

## 🔄 Mise à jour

```bash
# Arrêter le service
sudo systemctl stop elearning-bot

# Mettre à jour le code
git pull

# Redémarrer le service
sudo systemctl start elearning-bot
```

## 📈 Monitoring et Statistiques

### Statistiques détaillées

```bash
# Afficher les statistiques dans le terminal
python stats_command.py print

# Envoyer les statistiques via Telegram
python stats_command.py telegram

# Réinitialiser les statistiques
python stats_command.py reset
```

### Vérifier le statut

```bash
# Statut du service
sudo systemctl status elearning-bot

# Processus en cours
ps aux | grep python

# Utilisation mémoire
htop
```

### Logs et données

- `bot.log` : Logs détaillés du bot
- `bot_stats.json` : Statistiques complètes
- `local_storage/` : Données de fallback
- `journalctl -u elearning-bot` : Logs systemd

### Rapports automatiques

Le bot génère automatiquement des rapports avec :
- Temps de fonctionnement
- Nombre total de scans
- Taux de succès
- Notifications envoyées
- Erreurs récentes
- Statistiques par cours

## 🤝 Support

En cas de problème :

1. Vérifiez les logs : `tail -f bot.log`
2. Testez la configuration : `python setup.py`
3. Vérifiez les identifiants dans `.env`
4. Testez la connexion Telegram en envoyant un message au bot

## 📄 Licence

Ce projet est développé pour l'usage personnel et éducatif. Respectez les conditions d'utilisation de la plateforme eLearning de l'Université de Béjaïa.

---

**⚠️ Important** : Ce bot est conçu pour un usage personnel et éducatif. Respectez les conditions d'utilisation de la plateforme eLearning et n'utilisez pas ce bot de manière abusive.