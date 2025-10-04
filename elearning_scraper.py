import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from urllib.parse import urljoin, urlparse
from config import Config

class ELearningScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.logger = logging.getLogger(__name__)
        self.is_logged_in = False
        self.login_token = None
        
    def login(self):
        """Se connecter à la plateforme eLearning via HTTP"""
        try:
            self.logger.info("🔐 Tentative de connexion à eLearning...")
            
            # Étape 1: Récupérer la page de connexion pour obtenir les tokens CSRF
            login_url = f"{Config.ELEARNING_URL}/login/index.php"
            response = self.session.get(login_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraire le token de connexion (logintoken)
            login_token_input = soup.find('input', {'name': 'logintoken'})
            if login_token_input:
                self.login_token = login_token_input.get('value')
                self.logger.info(f"✅ Token de connexion récupéré: {self.login_token[:10]}...")
            else:
                self.logger.warning("⚠️ Aucun token de connexion trouvé")
            
            # Étape 2: Effectuer la connexion
            login_data = {
                'username': Config.USERNAME,
                'password': Config.PASSWORD,
                'logintoken': self.login_token or '',
            }
            
            # Headers pour la requête POST
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': login_url,
            }
            
            response = self.session.post(login_url, data=login_data, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Vérifier si la connexion a réussi
            if self._check_login_success(response):
                self.is_logged_in = True
                self.logger.info("✅ Connexion réussie à eLearning!")
                return True
            else:
                self.logger.error("❌ Échec de la connexion - identifiants incorrects ou problème de session")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Erreur réseau lors de la connexion: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la connexion: {str(e)}")
            return False
    
    def _check_login_success(self, response):
        """Vérifier si la connexion a réussi"""
        try:
            # Vérifier la redirection vers le dashboard
            if response.url and 'login' not in response.url:
                self.logger.info(f"🔄 Redirection détectée vers: {response.url}")
                return True
            
            # Vérifier le contenu de la page pour des indicateurs de succès
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Chercher des éléments qui indiquent une connexion réussie
            success_indicators = [
                soup.find('div', {'class': 'user-menu'}),
                soup.find('div', {'class': 'usermenu'}),
                soup.find('a', {'href': lambda x: x and 'logout' in x}),
                soup.find('div', {'class': 'dashboard'}),
                soup.find('div', {'class': 'course-content'}),
            ]
            
            if any(success_indicators):
                self.logger.info("✅ Indicateurs de connexion réussie détectés")
                return True
            
            # Vérifier s'il y a des messages d'erreur
            error_indicators = [
                soup.find('div', {'class': 'alert-danger'}),
                soup.find('div', {'class': 'error'}),
                soup.find(text=re.compile(r'Invalid login|incorrect|failed', re.I)),
            ]
            
            if any(error_indicators):
                self.logger.error("❌ Messages d'erreur de connexion détectés")
                return False
            
            # Si on arrive ici, c'est ambigu - on considère comme un échec par sécurité
            self.logger.warning("⚠️ Statut de connexion ambigu")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la vérification de connexion: {str(e)}")
            return False
    
    def get_course_content(self, course_url, course_id):
        """Récupérer le contenu d'un cours spécifique via HTTP"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Vérifier la connexion
                if not self.is_logged_in:
                    if not self.login():
                        return None
                
                self.logger.info(f"📖 Récupération du contenu pour le cours {course_id}")
                
                # Récupérer la page du cours
                response = self.session.get(course_url, timeout=30)
                response.raise_for_status()
                
                # Vérifier si on est toujours connecté
                if 'login' in response.url:
                    self.logger.warning("⚠️ Session expirée, reconnexion...")
                    self.is_logged_in = False
                    if not self.login():
                        return None
                    # Réessayer la requête
                    response = self.session.get(course_url, timeout=30)
                    response.raise_for_status()
                
                # Parser le contenu
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extraire le contenu principal
                content = {
                    'course_id': course_id,
                    'url': course_url,
                    'timestamp': time.time(),
                    'sections': [],
                    'title': self._extract_course_title(soup),
                    'raw_content': str(soup)  # Garder le contenu brut pour analyse
                }
                
                # Récupérer les sections du cours
                sections = self._extract_sections(soup)
                content['sections'] = sections
                
                self.logger.info(f"✅ Contenu récupéré pour le cours {course_id}: {len(sections)} sections")
                return content
                
            except requests.exceptions.RequestException as e:
                retry_count += 1
                self.logger.warning(f"⚠️ Tentative {retry_count}/{max_retries} échouée pour le cours {course_id}: {str(e)}")
                
                if retry_count < max_retries:
                    time.sleep(2)  # Attendre avant de réessayer
                else:
                    self.logger.error(f"❌ Échec définitif pour le cours {course_id} après {max_retries} tentatives")
                    return None
            except Exception as e:
                retry_count += 1
                self.logger.error(f"❌ Erreur inattendue pour le cours {course_id}: {str(e)}")
                
                if retry_count < max_retries:
                    time.sleep(2)
                else:
                    return None
        
        return None
    
    def _extract_course_title(self, soup):
        """Extraire le titre du cours"""
        try:
            # Essayer différents sélecteurs pour le titre
            title_selectors = [
                'h1.course-title',
                'h1',
                '.page-header h1',
                '.course-header h1',
                'title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title and len(title) > 3:  # Éviter les titres trop courts
                        return title
            
            return "Titre non trouvé"
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors de l'extraction du titre: {str(e)}")
            return "Titre non trouvé"
    
    def _extract_sections(self, soup):
        """Extraire les sections du cours"""
        sections = []
        
        try:
            # Essayer différents sélecteurs pour les sections
            section_selectors = [
                '.section',
                '.course-section',
                '.course-content .section',
                '.course-content > div',
                '.course-content .activity',
            ]
            
            section_elements = []
            for selector in section_selectors:
                elements = soup.select(selector)
                if elements:
                    section_elements = elements
                    self.logger.info(f"📋 Trouvé {len(elements)} sections avec le sélecteur: {selector}")
                    break
            
            if not section_elements:
                # Si aucune section spécifique trouvée, essayer de récupérer tout le contenu
                self.logger.warning("⚠️ Aucune section spécifique trouvée, extraction du contenu général")
                main_content = soup.select_one('.course-content') or soup.select_one('main') or soup.select_one('body')
                if main_content:
                    section_elements = [main_content]
            
            for section in section_elements:
                section_data = self._extract_section_data(section)
                if section_data:
                    sections.append(section_data)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'extraction des sections: {str(e)}")
        
        return sections
    
    def _extract_section_data(self, section_element):
        """Extraire les données d'une section"""
        try:
            section_data = {
                'title': '',
                'activities': [],
                'resources': [],
                'content': '',
                'links': []
            }
            
            # Titre de la section
            title_selectors = ['.sectionname', '.section-title', 'h2', 'h3', '.title']
            for selector in title_selectors:
                title_elem = section_element.select_one(selector)
                if title_elem:
                    section_data['title'] = title_elem.get_text().strip()
                    break
            
            # Si pas de titre spécifique, utiliser le texte principal
            if not section_data['title']:
                section_data['title'] = section_element.get_text().strip()[:100] + "..." if len(section_element.get_text().strip()) > 100 else section_element.get_text().strip()
            
            # Contenu textuel
            section_data['content'] = section_element.get_text().strip()
            
            # Liens et activités
            links = section_element.find_all('a', href=True)
            for link in links:
                link_data = {
                    'text': link.get_text().strip(),
                    'url': urljoin(Config.ELEARNING_URL, link['href']),
                    'title': link.get('title', '')
                }
                section_data['links'].append(link_data)
                
                # Classifier comme activité ou ressource
                if any(keyword in link_data['text'].lower() for keyword in ['forum', 'discussion', 'chat']):
                    section_data['activities'].append({
                        'title': link_data['text'],
                        'type': 'forum',
                        'url': link_data['url']
                    })
                elif any(keyword in link_data['text'].lower() for keyword in ['devoir', 'assignment', 'travail']):
                    section_data['activities'].append({
                        'title': link_data['text'],
                        'type': 'assignment',
                        'url': link_data['url']
                    })
                elif any(keyword in link_data['text'].lower() for keyword in ['fichier', 'document', 'pdf', 'doc']):
                    section_data['resources'].append({
                        'title': link_data['text'],
                        'type': 'file',
                        'url': link_data['url']
                    })
                else:
                    section_data['resources'].append({
                        'title': link_data['text'],
                        'type': 'link',
                        'url': link_data['url']
                    })
            
            return section_data
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'extraction des données de section: {str(e)}")
            return None
    
    def get_all_courses_content(self):
        """Récupérer le contenu de tous les cours surveillés"""
        all_content = {}
        successful_scans = 0
        failed_scans = 0
        
        self.logger.info(f"🔍 Début du scan de {len(Config.MONITORED_SPACES)} espaces d'affichage")
        
        # S'assurer qu'on est connecté
        if not self.is_logged_in:
            if not self.login():
                self.logger.error("❌ Impossible de se connecter, arrêt du scan")
                return {}
        
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
            time.sleep(2)
        
        self.logger.info(f"📊 Scan terminé: {successful_scans} succès, {failed_scans} échecs")
        return all_content
    
    def close(self):
        """Fermer la session"""
        if self.session:
            self.session.close()
            self.logger.info("🔒 Session fermée")