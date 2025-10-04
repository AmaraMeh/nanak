#!/usr/bin/env python3
"""
Script de configuration et d'installation du bot
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def install_dependencies():
    """Installer les dépendances Python"""
    print("📦 Installation des dépendances...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dépendances installées avec succès")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'installation des dépendances: {e}")
        return False

def setup_environment():
    """Configurer l'environnement"""
    print("🔧 Configuration de l'environnement...")
    
    # Créer le fichier .env s'il n'existe pas
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            shutil.copy('.env.example', '.env')
            print("✅ Fichier .env créé à partir de .env.example")
            print("⚠️  Veuillez modifier le fichier .env avec vos identifiants")
        else:
            print("❌ Fichier .env.example non trouvé")
            return False
    else:
        print("✅ Fichier .env existe déjà")
    
    # Créer le dossier de stockage local
    os.makedirs('local_storage', exist_ok=True)
    print("✅ Dossier de stockage local créé")
    
    return True

def setup_firebase():
    """Configurer Firebase (optionnel)"""
    print("🔥 Configuration Firebase...")
    print("ℹ️  Firebase est déjà configuré avec les identifiants fournis")
    print("ℹ️  Le bot utilisera le stockage local en cas de problème avec Firebase")
    return True

def test_configuration():
    """Tester la configuration"""
    print("🧪 Test de la configuration...")
    
    try:
        from config import Config
        print(f"✅ Configuration chargée: {len(Config.MONITORED_SPACES)} espaces surveillés")
        
        # Test des imports
        import requests
        import telegram
        import firebase_admin
        import schedule
        print("✅ Tous les modules importés avec succès")
        
        return True
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

def create_systemd_service():
    """Créer un service systemd pour l'exécution automatique"""
    print("🔧 Création du service systemd...")
    
    current_dir = os.getcwd()
    python_path = sys.executable
    
    service_content = f"""[Unit]
Description=eLearning Notifier Bot
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'root')}
WorkingDirectory={current_dir}
ExecStart={python_path} {current_dir}/run_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = "/etc/systemd/system/elearning-bot.service"
    
    try:
        with open(service_file, 'w') as f:
            f.write(service_content)
        print(f"✅ Service systemd créé: {service_file}")
        print("ℹ️  Pour activer le service: sudo systemctl enable elearning-bot")
        print("ℹ️  Pour démarrer le service: sudo systemctl start elearning-bot")
        return True
    except PermissionError:
        print("⚠️  Permissions insuffisantes pour créer le service systemd")
        print("ℹ️  Vous pouvez créer le service manuellement")
        return False

def main():
    """Fonction principale de configuration"""
    print("🚀 Configuration du Bot eLearning Notifier")
    print("=" * 60)
    
    steps = [
        ("Installation des dépendances", install_dependencies),
        ("Configuration de l'environnement", setup_environment),
        ("Configuration Firebase", setup_firebase),
        ("Test de la configuration", test_configuration),
        ("Création du service systemd", create_systemd_service)
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ Échec de l'étape: {step_name}")
            sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 Configuration terminée avec succès!")
    print("\n📝 Prochaines étapes:")
    print("1. Modifiez le fichier .env avec vos identifiants")
    print("2. Testez le bot avec: python run_bot.py")
    print("3. Pour l'exécution automatique: sudo systemctl enable elearning-bot")

if __name__ == "__main__":
    main()