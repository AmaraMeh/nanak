# 📝 Changelog - Bot eLearning Notifier

## Version 2.0 - Améliorations majeures

### 🔍 Premier scan complet
- **NOUVEAU** : Extraction de tout le contenu existant au premier lancement
- Le bot envoie des notifications pour chaque élément trouvé (sections, activités, ressources, fichiers)
- Gestion intelligente du spam initial avec messages groupés pour les gros volumes

### 📱 Notifications améliorées
- **AMÉLIORÉ** : Messages groupés pour éviter le spam lors du premier scan
- **NOUVEAU** : Résumés par type d'élément (sections, activités, ressources, fichiers)
- **AMÉLIORÉ** : Messages plus détaillés avec emojis spécifiques par type

### 🚀 Performance et robustesse
- **AMÉLIORÉ** : Scraping optimisé avec désactivation des images/CSS/JS
- **NOUVEAU** : Système de retry automatique (3 tentatives par cours)
- **AMÉLIORÉ** : Gestion d'erreurs robuste avec récupération automatique
- **NOUVEAU** : Timeouts configurables et gestion des sessions Chrome

### 📊 Monitoring et statistiques
- **NOUVEAU** : Module de monitoring complet (`monitoring.py`)
- **NOUVEAU** : Statistiques détaillées par cours et globales
- **NOUVEAU** : Commandes de statistiques (`stats_command.py`)
- **NOUVEAU** : Rapports automatiques avec taux de succès
- **NOUVEAU** : Historique des erreurs avec timestamps

### 🔧 Améliorations techniques
- **AMÉLIORÉ** : Détection de changements plus précise
- **NOUVEAU** : Support de plusieurs sélecteurs CSS pour la robustesse
- **AMÉLIORÉ** : Logs plus détaillés avec progression des scans
- **NOUVEAU** : Sauvegarde automatique des statistiques dans `bot_stats.json`

### 📚 Documentation
- **NOUVEAU** : Guide complet (`GUIDE_COMPLET.md`)
- **NOUVEAU** : Guide d'installation (`INSTALLATION_GUIDE.txt`)
- **AMÉLIORÉ** : README avec nouvelles fonctionnalités
- **NOUVEAU** : Support Docker avec `Dockerfile` et `docker-compose.yml`

## Version 1.0 - Version initiale

### Fonctionnalités de base
- Connexion sécurisée à eLearning
- Surveillance de 42 espaces d'affichage
- Détection de changements basique
- Notifications Telegram simples
- Stockage Firebase avec fallback local
- Surveillance toutes les 15 minutes

---

## 🎯 Prochaines améliorations prévues

- [ ] Interface web pour la configuration
- [ ] Notifications par email en plus de Telegram
- [ ] Filtres personnalisables pour les types de changements
- [ ] API REST pour l'intégration avec d'autres systèmes
- [ ] Support de plusieurs comptes eLearning
- [ ] Mode de surveillance sélective par département