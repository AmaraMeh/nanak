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
        """Configure et initialise le driver Chrome avec optimisations"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # Désactiver les images pour plus de rapidité
        chrome_options.add_argument('--disable-javascript')  # Désactiver JS si possible
        chrome_options.add_argument('--disable-css')  # Désactiver CSS pour plus de rapidité
        chrome_options.add_argument(f'--user-agent={Config.USER_AGENT}')
        
        # Optimisations de performance
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--max_old_space_size=4096')
        
        # Timeouts
        chrome_options.add_argument('--page-load-strategy=eager')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Configurer les timeouts
        self.driver.set_page_load_timeout(30)
        self.driver.implicitly_wait(10)
        
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
        """Récupérer le contenu d'un cours spécifique avec gestion d'erreurs améliorée"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if not self.driver:
                    if not self.login():
                        return None
                
                # Aller à la page du cours
                self.driver.get(course_url)
                
                # Attendre que la page se charge avec timeout plus long
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "course-content"))
                )
                
                # Extraire le contenu principal
                content = {
                    'course_id': course_id,
                    'url': course_url,
                    'timestamp': time.time(),
                    'sections': []
                }
                
                # Récupérer les sections du cours avec plusieurs sélecteurs
                sections = []
                selectors = [".section", ".course-section", ".course-content .section"]
                
                for selector in selectors:
                    try:
                        sections = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if sections:
                            break
                    except:
                        continue
                
                if not sections:
                    # Essayer de récupérer le contenu même sans sections spécifiques
                    self.logger.warning(f"Aucune section trouvée pour le cours {course_id}, tentative de récupération générale")
                    sections = self.driver.find_elements(By.CSS_SELECTOR, ".course-content > *")
                
                for section in sections:
                    try:
                        section_data = self._extract_section_data(section)
                        if section_data:
                            content['sections'].append(section_data)
                    except Exception as section_error:
                        self.logger.warning(f"Erreur lors de l'extraction d'une section: {str(section_error)}")
                        continue
                
                self.logger.info(f"Contenu récupéré pour le cours {course_id}: {len(content['sections'])} sections")
                return content
                
            except Exception as e:
                retry_count += 1
                self.logger.warning(f"Tentative {retry_count}/{max_retries} échouée pour le cours {course_id}: {str(e)}")
                
                if retry_count < max_retries:
                    time.sleep(2)  # Attendre avant de réessayer
                    # Recréer le driver si nécessaire
                    if "chrome not reachable" in str(e).lower() or "session deleted" in str(e).lower():
                        self.close()
                        self.setup_driver()
                else:
                    self.logger.error(f"Échec définitif pour le cours {course_id} après {max_retries} tentatives")
                    return None
        
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
        """Récupérer le contenu de tous les cours surveillés avec gestion d'erreurs améliorée"""
        all_content = {}
        successful_scans = 0
        failed_scans = 0
        
        self.logger.info(f"Début du scan de {len(Config.MONITORED_SPACES)} espaces d'affichage")
        
        for i, space in enumerate(Config.MONITORED_SPACES, 1):
            self.logger.info(f"[{i}/{len(Config.MONITORED_SPACES)}] Récupération du contenu pour: {space['name']}")
            
            try:
                content = self.get_course_content(space['url'], space['id'])
                if content:
                    all_content[space['id']] = content
                    successful_scans += 1
                    self.logger.info(f"✅ Succès pour: {space['name']}")
                else:
                    failed_scans += 1
                    self.logger.error(f"❌ Échec pour: {space['name']}")
            except Exception as e:
                failed_scans += 1
                self.logger.error(f"❌ Erreur pour {space['name']}: {str(e)}")
            
            # Pause entre les requêtes pour éviter la surcharge
            time.sleep(3)
        
        self.logger.info(f"Scan terminé: {successful_scans} succès, {failed_scans} échecs")
        return all_content
    
    def close(self):
        """Fermer le driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None