#!/bin/bash

# Script de démarrage du Bot eLearning Notifier
# Université de Béjaïa

echo "🤖 Bot eLearning Notifier - Université de Béjaïa"
echo "=================================================="

# Vérifier si Python est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    echo "Veuillez installer Python 3.8+ avant de continuer"
    exit 1
fi

# Vérifier si le fichier .env existe
if [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env non trouvé"
    if [ -f ".env.example" ]; then
        echo "📋 Copie du fichier .env.example vers .env"
        cp .env.example .env
        echo "✅ Fichier .env créé"
        echo "⚠️  Veuillez modifier le fichier .env avec vos identifiants"
        echo "   nano .env"
        exit 1
    else
        echo "❌ Fichier .env.example non trouvé"
        exit 1
    fi
fi

# Vérifier si les dépendances sont installées
if ! python3 -c "import requests, telegram, firebase_admin, schedule" 2>/dev/null; then
    echo "📦 Installation des dépendances..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Erreur lors de l'installation des dépendances"
        exit 1
    fi
    echo "✅ Dépendances installées"
fi

# Créer le dossier de stockage local
mkdir -p local_storage

# Donner les permissions d'exécution
chmod +x run_bot.py

echo "🚀 Démarrage du bot..."
echo "=================================================="

# Démarrer le bot
python3 run_bot.py