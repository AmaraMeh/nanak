#!/usr/bin/env python3
"""
Script de test pour vérifier le bon fonctionnement du bot
"""

import asyncio
import sys
from elearning_scraper import ELearningScraper
from firebase_manager import FirebaseManager
from change_detector import ChangeDetector
from telegram_notifier import TelegramNotifier
from config import Config

async def test_elearning_connection():
    """Tester la connexion eLearning"""
    print("🔐 Test de connexion eLearning...")
    
    scraper = ELearningScraper()
    try:
        success = scraper.login()
        if success:
            print("✅ Connexion eLearning réussie")
            
            # Tester la récupération d'un cours
            test_course = Config.MONITORED_SPACES[0]
            content = scraper.get_course_content(test_course['url'], test_course['id'])
            
            if content:
                print(f"✅ Récupération du contenu réussie pour: {test_course['name']}")
                print(f"   Sections trouvées: {len(content.get('sections', []))}")
            else:
                print("❌ Échec de la récupération du contenu")
                
        else:
            print("❌ Échec de la connexion eLearning")
            return False
            
    except Exception as e:
        print(f"❌ Erreur lors du test eLearning: {str(e)}")
        return False
    finally:
        scraper.close()
    
    return True

def test_firebase():
    """Tester Firebase"""
    print("🔥 Test Firebase...")
    
    firebase = FirebaseManager()
    try:
        # Test de sauvegarde
        test_data = {
            'test': True,
            'timestamp': 1234567890,
            'sections': []
        }
        
        success = firebase.save_course_content('test_course', test_data)
        if success:
            print("✅ Sauvegarde Firebase réussie")
            
            # Test de récupération
            retrieved_data = firebase.get_course_content('test_course')
            if retrieved_data:
                print("✅ Récupération Firebase réussie")
                return True
            else:
                print("❌ Échec de la récupération Firebase")
        else:
            print("❌ Échec de la sauvegarde Firebase")
            
    except Exception as e:
        print(f"❌ Erreur lors du test Firebase: {str(e)}")
    
    return False

async def test_telegram():
    """Tester Telegram"""
    print("📱 Test Telegram...")
    
    notifier = TelegramNotifier()
    try:
        # Test de récupération du chat ID
        chat_id = await notifier.get_chat_id()
        if chat_id:
            print(f"✅ Chat ID récupéré: {chat_id}")
            
            # Test d'envoi de message
            test_changes = [{
                'type': 'test',
                'message': 'Message de test du bot',
                'details': 'Ceci est un test de fonctionnement'
            }]
            
            success = await notifier.send_notification(
                "Test Bot", 
                "https://example.com", 
                test_changes
            )
            
            if success:
                print("✅ Message Telegram envoyé avec succès")
                return True
            else:
                print("❌ Échec de l'envoi du message Telegram")
        else:
            print("❌ Impossible de récupérer le chat ID")
            print("   Envoyez un message à votre bot pour obtenir votre chat ID")
            
    except Exception as e:
        print(f"❌ Erreur lors du test Telegram: {str(e)}")
    
    return False

def test_change_detection():
    """Tester la détection de changements"""
    print("🔍 Test de détection de changements...")
    
    detector = ChangeDetector()
    
    # Données de test
    old_content = {
        'sections': [
            {
                'title': 'Section 1',
                'activities': [
                    {'title': 'Activité 1', 'type': 'forum', 'files': []}
                ],
                'resources': [
                    {'title': 'Ressource 1', 'files': [{'name': 'fichier1.pdf'}]}
                ]
            }
        ]
    }
    
    new_content = {
        'sections': [
            {
                'title': 'Section 1',
                'activities': [
                    {'title': 'Activité 1', 'type': 'forum', 'files': []},
                    {'title': 'Nouvelle Activité', 'type': 'assignment', 'files': []}
                ],
                'resources': [
                    {'title': 'Ressource 1', 'files': [{'name': 'fichier1.pdf'}]},
                    {'title': 'Nouvelle Ressource', 'files': [{'name': 'fichier2.pdf'}]}
                ]
            }
        ]
    }
    
    try:
        changes = detector.detect_changes(old_content, new_content)
        if changes:
            print(f"✅ {len(changes)} changements détectés:")
            for change in changes:
                print(f"   - {change['message']}")
            return True
        else:
            print("❌ Aucun changement détecté")
            
    except Exception as e:
        print(f"❌ Erreur lors du test de détection: {str(e)}")
    
    return False

def test_configuration():
    """Tester la configuration"""
    print("⚙️ Test de la configuration...")
    
    try:
        # Vérifier les identifiants
        if not Config.USERNAME or not Config.PASSWORD:
            print("❌ Identifiants eLearning manquants")
            return False
        
        if not Config.TELEGRAM_TOKEN:
            print("❌ Token Telegram manquant")
            return False
        
        # Vérifier les espaces surveillés
        if not Config.MONITORED_SPACES:
            print("❌ Aucun espace surveillé configuré")
            return False
        
        print(f"✅ Configuration OK")
        print(f"   Espaces surveillés: {len(Config.MONITORED_SPACES)}")
        print(f"   Intervalle de vérification: {Config.CHECK_INTERVAL_MINUTES} minutes")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de configuration: {str(e)}")
        return False

async def main():
    """Fonction principale de test"""
    print("🧪 Test du Bot eLearning Notifier")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Connexion eLearning", test_elearning_connection),
        ("Firebase", test_firebase),
        ("Détection de changements", test_change_detection),
        ("Telegram", test_telegram)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erreur lors du test {test_name}: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 RÉSULTATS DES TESTS")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
        print(f"{test_name:25} {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"Résultat: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés ! Le bot est prêt à fonctionner.")
        return True
    else:
        print("⚠️  Certains tests ont échoué. Vérifiez la configuration.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {str(e)}")
        sys.exit(1)