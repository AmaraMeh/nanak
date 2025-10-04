import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class Config:
    # Configuration eLearning
    ELEARNING_URL = "https://elearning.univ-bejaia.dz"
    USERNAME = os.getenv('ELEARNING_USERNAME', '242433047620')
    PASSWORD = os.getenv('ELEARNING_PASSWORD', '100060196001960005')
    
    # Configuration Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8489609270:AAGVP7q0VL5RID1OeEWXNjTC1SC0xPhx5Xo')
    TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID', '24358290')
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '847c2d71463d5940bc55648eb9241b51')
    
    # Configuration Firebase
    FIREBASE_CONFIG = {
        "apiKey": "AIzaSyA4UIT_2nxaw-dKTqtKcW9sLKynlnLLCVU",
        "authDomain": "nemi-2308f.firebaseapp.com",
        "projectId": "nemi-2308f",
        "storageBucket": "nemi-2308f.firebasestorage.app",
        "messagingSenderId": "1043106571079",
        "appId": "1:1043106571079:web:b63f8148b670bbb4936262"
    }
    
    # Configuration du bot
    CHECK_INTERVAL_MINUTES = 15
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    # Espaces à surveiller
    MONITORED_SPACES = [
        {
            "name": "Affichage Département de Génie Civil",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19984",
            "id": "19984"
        },
        {
            "name": "Affichage Département de Technologie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19989",
            "id": "19989"
        },
        {
            "name": "Affichage Département d'Hydraulique",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19987",
            "id": "19987"
        },
        {
            "name": "Affichage Département de Génie Mécanique",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19985",
            "id": "19985"
        },
        {
            "name": "Affichage Département de Génie Electrique",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19982",
            "id": "19982"
        },
        {
            "name": "Affichage département ATE",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19983",
            "id": "19983"
        },
        {
            "name": "Affichage Département de Génie des Procédés",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19986",
            "id": "19986"
        },
        {
            "name": "Affichage Département d'Architecture",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19978",
            "id": "19978"
        },
        {
            "name": "Affichage Département des Mines et Géologie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=19988",
            "id": "19988"
        },
        {
            "name": "Espace d'Affichage du vice décanat chargé de la pédagogie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=16918",
            "id": "16918"
        },
        {
            "name": "Affichage Département d'Informatique",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20008",
            "id": "20008"
        },
        {
            "name": "Affichage Département de Chimie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20023",
            "id": "20023"
        },
        {
            "name": "Affichage Département de Physique et SM",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20024",
            "id": "20024"
        },
        {
            "name": "Affichage Département de Recherche Opérationnelle",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20022",
            "id": "20022"
        },
        {
            "name": "Affichage Département de Mathématiques",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20011",
            "id": "20011"
        },
        {
            "name": "Affichage Département des Enseignements de Base en Droit",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20037",
            "id": "20037"
        },
        {
            "name": "Affichage Département de Droit Public",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20038",
            "id": "20038"
        },
        {
            "name": "Affichage Département de Droit Privé",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20039",
            "id": "20039"
        },
        {
            "name": "Affichage Département de Médecine",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20040",
            "id": "20040"
        },
        {
            "name": "Affichage Département des Sciences Infirmières",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20041",
            "id": "20041"
        },
        {
            "name": "affichage département de pharmacie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20042",
            "id": "20042"
        },
        {
            "name": "Affichage département des Enseignements de Base pour le Domaine SEGC-LMD",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20046",
            "id": "20046"
        },
        {
            "name": "Affichage Département des Sciences Commerciales",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20045",
            "id": "20045"
        },
        {
            "name": "Affichage Département des Sciences de Gestion",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20044",
            "id": "20044"
        },
        {
            "name": "Affichage Département des Sciences Economiques",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20043",
            "id": "20043"
        },
        {
            "name": "Affichage Département des Sciences Financières et Comptabilité",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20047",
            "id": "20047"
        },
        {
            "name": "Affichage Département des Sciences Biologiques de l'Environnement",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20031",
            "id": "20031"
        },
        {
            "name": "Affichage Département des Troncs Communs L1",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20030",
            "id": "20030"
        },
        {
            "name": "Affichage Département des Sciences Alimentaires",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20033",
            "id": "20033"
        },
        {
            "name": "Affichage Département du Département de Biologie Physico-Chimique",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20032",
            "id": "20032"
        },
        {
            "name": "Affichage Département de Microbiologie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20034",
            "id": "20034"
        },
        {
            "name": "Affichage Département de Biotechnologie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20035",
            "id": "20035"
        },
        {
            "name": "Espace d'Affichage du Vice décanat chargé de la pédagogie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=18369",
            "id": "18369"
        },
        {
            "name": "Espace d'Affichage relatif au volet: Projets Startup FSNV",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=18370",
            "id": "18370"
        },
        {
            "name": "Affichage Département de Langue et Littérature Anglaises",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20027",
            "id": "20027"
        },
        {
            "name": "Affichage Département de Langue et Littérature Françaises",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20025",
            "id": "20025"
        },
        {
            "name": "Affichage Département de Langue et Littérature Arabes",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20026",
            "id": "20026"
        },
        {
            "name": "Affichage Département de Langue et Culture Amazighes",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20028",
            "id": "20028"
        },
        {
            "name": "Affichage département de Traduction et Interprétariat",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20029",
            "id": "20029"
        },
        {
            "name": "Affichage Département de Sociologie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20048",
            "id": "20048"
        },
        {
            "name": "Affichage Département de Psychologie et d'Orthophonie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20049",
            "id": "20049"
        },
        {
            "name": "Affichage Département d'Histoire et d'Archéologie",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20050",
            "id": "20050"
        },
        {
            "name": "Affichage Département des Sciences de l'Information et de la Communication",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20051",
            "id": "20051"
        },
        {
            "name": "Affichage Département STAPS",
            "url": "https://elearning.univ-bejaia.dz/course/view.php?id=20052",
            "id": "20052"
        }
    ]