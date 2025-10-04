import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import logging
from config import Config

class ELearningScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT
        })
        self.driver = None
        self.logger = logging.getLogger(__name__)
        
    def setup_driver(self):
        """Configure et initialise le driver Chrome"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(f'--user-agent={Config.USER_AGENT}')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
    def login(self):
        """Se connecter à la plateforme eLearning"""
        try:
            self.setup_driver()
            
            # Aller à la page de connexion
            login_url = f"{Config.ELEARNING_URL}/login/index.php"
            self.driver.get(login_url)
            
            # Attendre que la page se charge
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # Remplir les identifiants
            username_field = self.driver.find_element(By.ID, "username")
            password_field = self.driver.find_element(By.ID, "password")
            
            username_field.send_keys(Config.USERNAME)
            password_field.send_keys(Config.PASSWORD)
            
            # Cliquer sur le bouton de connexion
            login_button = self.driver.find_element(By.ID, "loginbtn")
            login_button.click()
            
            # Attendre la redirection
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "user-menu"))
            )
            
            self.logger.info("Connexion réussie à eLearning")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la connexion: {str(e)}")
            return False
    
    def get_course_content(self, course_url, course_id):
        """Récupérer le contenu d'un cours spécifique"""
        try:
            if not self.driver:
                if not self.login():
                    return None
            
            # Aller à la page du cours
            self.driver.get(course_url)
            
            # Attendre que la page se charge
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "course-content"))
            )
            
            # Extraire le contenu principal
            content = {
                'course_id': course_id,
                'url': course_url,
                'timestamp': time.time(),
                'sections': []
            }
            
            # Récupérer les sections du cours
            sections = self.driver.find_elements(By.CSS_SELECTOR, ".section")
            
            for section in sections:
                section_data = self._extract_section_data(section)
                if section_data:
                    content['sections'].append(section_data)
            
            return content
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du contenu du cours {course_id}: {str(e)}")
            return None
    
    def _extract_section_data(self, section_element):
        """Extraire les données d'une section"""
        try:
            section_data = {
                'title': '',
                'activities': [],
                'resources': []
            }
            
            # Titre de la section
            title_element = section_element.find_element(By.CSS_SELECTOR, ".sectionname")
            section_data['title'] = title_element.text.strip()
            
            # Activités et ressources
            activities = section_element.find_elements(By.CSS_SELECTOR, ".activity")
            
            for activity in activities:
                activity_data = self._extract_activity_data(activity)
                if activity_data:
                    if activity_data['type'] == 'resource':
                        section_data['resources'].append(activity_data)
                    else:
                        section_data['activities'].append(activity_data)
            
            return section_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction des données de section: {str(e)}")
            return None
    
    def _extract_activity_data(self, activity_element):
        """Extraire les données d'une activité"""
        try:
            activity_data = {
                'title': '',
                'type': '',
                'url': '',
                'description': '',
                'files': []
            }
            
            # Titre et lien
            title_element = activity_element.find_element(By.CSS_SELECTOR, ".activityinstance a")
            activity_data['title'] = title_element.text.strip()
            activity_data['url'] = title_element.get_attribute('href')
            
            # Type d'activité
            activity_classes = activity_element.get_attribute('class')
            if 'resource' in activity_classes:
                activity_data['type'] = 'resource'
            elif 'forum' in activity_classes:
                activity_data['type'] = 'forum'
            elif 'assign' in activity_classes:
                activity_data['type'] = 'assignment'
            else:
                activity_data['type'] = 'other'
            
            # Description si disponible
            try:
                description_element = activity_element.find_element(By.CSS_SELECTOR, ".activity-description")
                activity_data['description'] = description_element.text.strip()
            except:
                pass
            
            # Fichiers associés
            try:
                file_elements = activity_element.find_elements(By.CSS_SELECTOR, ".file-picker a")
                for file_elem in file_elements:
                    file_data = {
                        'name': file_elem.text.strip(),
                        'url': file_elem.get_attribute('href')
                    }
                    activity_data['files'].append(file_data)
            except:
                pass
            
            return activity_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction des données d'activité: {str(e)}")
            return None
    
    def get_all_courses_content(self):
        """Récupérer le contenu de tous les cours surveillés"""
        all_content = {}
        
        for space in Config.MONITORED_SPACES:
            self.logger.info(f"Récupération du contenu pour: {space['name']}")
            content = self.get_course_content(space['url'], space['id'])
            if content:
                all_content[space['id']] = content
            time.sleep(2)  # Pause entre les requêtes
        
        return all_content
    
    def close(self):
        """Fermer le driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None