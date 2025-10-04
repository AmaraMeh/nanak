# 📖 Guide Complet - Bot eLearning Notifier

## 🎯 Vue d'ensemble

Ce guide vous accompagne pas à pas pour installer, configurer et utiliser le Bot eLearning Notifier de l'Université de Béjaïa. Ce bot surveille automatiquement tous les espaces d'affichage et vous envoie des notifications Telegram dès qu'un changement est détecté.

## 📋 Table des matières

1. [Prérequis](#prérequis)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Premier démarrage](#premier-démarrage)
5. [Utilisation avancée](#utilisation-avancée)
6. [Dépannage](#dépannage)
7. [Sécurité](#sécurité)
8. [Maintenance](#maintenance)

## 🔧 Prérequis

### Système d'exploitation
- **Linux** (Ubuntu/Debian recommandé)
- **Windows** (avec WSL recommandé)
- **macOS**

### Logiciels requis
- **Python 3.8+**
- **Git** (optionnel)

### Comptes nécessaires
- **Compte eLearning** Université de Béjaïa
- **Compte Telegram** avec bot créé

## 🚀 Installation

### Méthode 1 : Installation automatique (Recommandée)

```bash
# 1. Télécharger le projet
wget https://github.com/votre-repo/elearning-notifier-bot/archive/main.zip
unzip main.zip
cd elearning-notifier-bot-main

# 2. Installation automatique
python setup.py
```

### Méthode 2 : Installation manuelle

```bash
# 1. Créer le dossier du projet
mkdir elearning-bot
cd elearning-bot

# 2. Télécharger les fichiers
# (Copier tous les fichiers .py, requirements.txt, etc.)

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer l'environnement
cp .env.example .env
```

### Installation des dépendances système

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3 python3-pip
```

#### CentOS/RHEL
```bash
sudo yum install python3 python3-pip
```

#### Windows
```bash
# Installer Python depuis python.org
```

## ⚙️ Configuration

### 1. Configuration des identifiants

Éditez le fichier `.env` :

```bash
nano .env
```

Contenu du fichier `.env` :
```env
# Identifiants eLearning Université de Béjaïa
ELEARNING_USERNAME=242433047620
ELEARNING_PASSWORD=100060196001960005

# Configuration Telegram
TELEGRAM_TOKEN=8489609270:AAGVP7q0VL5RID1OeEWXNjTC1SC0xPhx5Xo
TELEGRAM_API_ID=24358290
TELEGRAM_API_HASH=847c2d71463d5940bc55648eb9241b51
```

### 2. Configuration Telegram

#### Créer un bot Telegram
1. Ouvrir Telegram
2. Chercher `@BotFather`
3. Envoyer `/newbot`
4. Suivre les instructions
5. Copier le token reçu

#### Obtenir votre Chat ID
1. Envoyer un message à votre bot
2. Le bot récupérera automatiquement votre Chat ID
3. Vous recevrez une notification de confirmation

### 3. Test de la configuration

```bash
# Tester la configuration
python setup.py

# Vérifier les imports
python -c "import requests, bs4, telegram, firebase_admin, schedule; print('✅ Tous les modules OK')"
```

## 🎮 Premier démarrage

### Démarrage simple

```bash
# Démarrer le bot
python run_bot.py
```

Vous devriez voir :
```
🤖 Démarrage du Bot eLearning Notifier
==================================================
✅ Toutes les dépendances sont installées
✅ Configuration vérifiée
📚 Surveillance de 42 espaces d'affichage
⏱️ Vérification toutes les 15 minutes
==================================================
```

### Premier message Telegram

Dès le démarrage, vous recevrez :
```
🤖 Bot eLearning Notifier démarré

✅ Surveillance active des espaces d'affichage
⏱️ Vérification toutes les 15 minutes
📚 42 espaces surveillés

🔔 Vous recevrez une notification dès qu'un changement sera détecté !
```

## 🔄 Utilisation avancée

### Service systemd (Recommandé pour la production)

#### Créer le service
```bash
sudo python setup.py
```

#### Gérer le service
```bash
# Activer le démarrage automatique
sudo systemctl enable elearning-bot

# Démarrer le service
sudo systemctl start elearning-bot

# Vérifier le statut
sudo systemctl status elearning-bot

# Voir les logs en temps réel
sudo journalctl -u elearning-bot -f

# Arrêter le service
sudo systemctl stop elearning-bot

# Redémarrer le service
sudo systemctl restart elearning-bot
```

### Exécution en arrière-plan

#### Avec nohup
```bash
nohup python run_bot.py > bot_output.log 2>&1 &
```

#### Avec screen
```bash
screen -S elearning-bot
python run_bot.py
# Ctrl+A, D pour détacher
# screen -r elearning-bot pour rattacher
```

#### Avec tmux
```bash
tmux new-session -d -s elearning-bot 'python run_bot.py'
tmux attach-session -t elearning-bot
```

### Configuration personnalisée

#### Modifier l'intervalle de vérification
Éditez `config.py` :
```python
CHECK_INTERVAL_MINUTES = 10  # Vérifier toutes les 10 minutes
```

#### Ajouter/retirer des espaces
Éditez `config.py`, section `MONITORED_SPACES` :
```python
MONITORED_SPACES = [
    {
        "name": "Mon nouvel espace",
        "url": "https://elearning.univ-bejaia.dz/course/view.php?id=XXXXX",
        "id": "XXXXX"
    },
    # ... autres espaces
]
```

## 🐛 Dépannage

### Problèmes de connexion eLearning

#### Erreur : "Connexion échouée"
```bash
# Vérifier les identifiants
cat .env | grep ELEARNING

# Tester la connexion manuelle
python -c "
from elearning_scraper import ELearningScraper
scraper = ELearningScraper()
print('Connexion:', scraper.login())
scraper.close()
"
```

#### Erreur : "Page non trouvée"
- Vérifier que l'URL eLearning est accessible
- Vérifier votre connexion internet
- Essayer de vous connecter manuellement

### Problèmes Telegram

#### Erreur : "Token invalide"
```bash
# Vérifier le token
cat .env | grep TELEGRAM_TOKEN

# Tester le token
python -c "
from telegram import Bot
import asyncio
async def test():
    bot = Bot('VOTRE_TOKEN')
    me = await bot.get_me()
    print('Bot:', me.username)
asyncio.run(test())
"
```

#### Erreur : "Chat ID non trouvé"
1. Envoyez un message à votre bot
2. Le bot récupérera automatiquement votre Chat ID
3. Redémarrez le bot

### Notes sur Selenium/Chrome
Le bot n'utilise plus Selenium/Chrome. Le scraping est effectué via HTTP (requests + BeautifulSoup) et fonctionne en environnements cloud sans navigateur.

#### Erreur : "Permission denied"
```bash
# Donner les permissions d'exécution
chmod +x run_bot.py
chmod +x setup.py
```

### Problèmes Firebase

#### Erreur : "Firebase non initialisé"
- Le bot utilisera automatiquement le stockage local
- Vérifiez votre connexion internet
- Les données seront sauvegardées dans `local_storage/`

### Logs et debugging

#### Voir les logs
```bash
# Logs du bot
tail -f bot.log

# Logs systemd
sudo journalctl -u elearning-bot -f

# Logs avec plus de détails
python run_bot.py --verbose
```

#### Mode debug
Modifiez `config.py` :
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🔒 Sécurité

### Protection des identifiants

#### Variables d'environnement
```bash
# Ne jamais commiter le fichier .env
echo ".env" >> .gitignore

# Permissions restrictives
chmod 600 .env
```

#### Rotation des mots de passe
1. Changez régulièrement vos mots de passe eLearning
2. Mettez à jour le fichier `.env`
3. Redémarrez le bot

### Sécurité réseau

#### Firewall
```bash
# Autoriser seulement les connexions sortantes nécessaires
sudo ufw allow out 443  # HTTPS
sudo ufw allow out 80   # HTTP
sudo ufw allow out 53  # DNS
```

#### Proxy (si nécessaire)
```bash
# Configurer le proxy dans .env
HTTP_PROXY=http://proxy:port
HTTPS_PROXY=http://proxy:port
```

### Audit de sécurité

#### Vérifications régulières
```bash
# Vérifier les permissions
ls -la .env

# Vérifier les processus
ps aux | grep python

# Vérifier les connexions réseau
netstat -tulpn | grep python
```

## 🔧 Maintenance

### Mise à jour du bot

```bash
# Arrêter le service
sudo systemctl stop elearning-bot

# Sauvegarder la configuration
cp .env .env.backup

# Mettre à jour le code
git pull  # ou télécharger la nouvelle version

# Restaurer la configuration
cp .env.backup .env

# Redémarrer le service
sudo systemctl start elearning-bot
```

### Nettoyage des logs

```bash
# Nettoyer les anciens logs
sudo journalctl --vacuum-time=30d

# Nettoyer le fichier de log du bot
echo "" > bot.log
```

### Sauvegarde des données

```bash
# Sauvegarder le stockage local
tar -czf backup_$(date +%Y%m%d).tar.gz local_storage/

# Sauvegarder la configuration
cp .env backup_config_$(date +%Y%m%d).env
```

### Monitoring

#### Vérification du statut
```bash
# Script de monitoring
#!/bin/bash
if systemctl is-active --quiet elearning-bot; then
    echo "✅ Bot actif"
else
    echo "❌ Bot inactif"
    sudo systemctl start elearning-bot
fi
```

#### Surveillance des ressources
```bash
# Utilisation mémoire
ps aux | grep python | awk '{print $4, $11}'

# Utilisation CPU
top -p $(pgrep -f "python.*run_bot")
```

## 📊 Statistiques et rapports

### Logs d'activité
Le bot génère des logs détaillés dans `bot.log` :
- Connexions réussies/échouées
- Changements détectés
- Notifications envoyées
- Erreurs rencontrées

### Données stockées
- `local_storage/course_*.json` : Contenu des cours
- `local_storage/changes_log_*.json` : Historique des changements

## 🆘 Support et assistance

### En cas de problème

1. **Vérifiez les logs** : `tail -f bot.log`
2. **Testez la configuration** : `python setup.py`
3. **Vérifiez les identifiants** : `cat .env`
4. **Testez la connexion** : Essayez de vous connecter manuellement à eLearning

### Ressources utiles

- **Documentation Python** : https://docs.python.org/
- **Documentation Telegram Bot API** : https://core.telegram.org/bots/api
- **Documentation Firebase** : https://firebase.google.com/docs
- **Documentation Selenium** : https://selenium-python.readthedocs.io/

### Contact

Pour toute question ou problème :
1. Vérifiez d'abord ce guide
2. Consultez les logs d'erreur
3. Testez chaque composant individuellement

---

**🎉 Félicitations !** Vous avez maintenant un bot eLearning Notifier entièrement fonctionnel qui vous tiendra informé de tous les changements sur la plateforme eLearning de l'Université de Béjaïa.

**⚠️ Rappel important** : Ce bot est conçu pour un usage personnel et éducatif. Respectez les conditions d'utilisation de la plateforme eLearning et n'utilisez pas ce bot de manière abusive.