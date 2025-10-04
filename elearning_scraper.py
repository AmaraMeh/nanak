import requests
from bs4 import BeautifulSoup
import time
import logging
from urllib.parse import urljoin
from config import Config

class ELearningScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        })
        self.logger = logging.getLogger(__name__)
        self.logged_in = False
        self.enable_file_download = Config.SEND_FILES_AS_DOCUMENTS  # réutiliser le flag
        self.firebase_mgr = None  # sera injecté si besoin
        
    def login(self) -> bool:
        """Se connecter à la plateforme eLearning via HTTP (sans Chrome)."""
        try:
            login_url = urljoin(Config.ELEARNING_URL, '/login/index.php')

            # 1) Charger la page de login pour récupérer le token CSRF (logintoken)
            resp = self.session.get(login_url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'lxml')
            token_input = soup.select_one('input[name="logintoken"]')
            logintoken = token_input['value'] if token_input and token_input.has_attr('value') else ''

            # 2) Poster le formulaire de login
            payload = {
                'username': Config.USERNAME,
                'password': Config.PASSWORD,
                'logintoken': logintoken,
                'anchor': ''
            }
            post_resp = self.session.post(login_url, data=payload, timeout=20, allow_redirects=True)
            post_resp.raise_for_status()

            # 3) Vérifier la réussite de la connexion
            #    - Présence du cookie MoodleSession
            #    - Absence d'un message d'erreur de login
            #    - Présence du menu utilisateur sur la page d'accueil
            has_session_cookie = any(c.name.lower().startswith('moodlesession') for c in self.session.cookies)

            # Vérification contenu après login
            home_resp = self.session.get(Config.ELEARNING_URL, timeout=20)
            home_resp.raise_for_status()
            home_soup = BeautifulSoup(home_resp.text, 'lxml')

            login_error = home_soup.select_one('.loginerrors, #loginerrormessage, .alert-danger')
            user_menu = home_soup.select_one('.usermenu, .user-menu, [data-region="user-menu"]')

            self.logger.info(
                f"Debug login: status={post_resp.status_code}, url={post_resp.url}, session_cookie={has_session_cookie}"
            )

            if has_session_cookie and not login_error and user_menu:
                # Essayer d'afficher un identifiant utilisateur pour debug
                user_name = None
                name_el = home_soup.select_one('.usermenu .usertext, .user-menu .usertext, .logininfo a')
                if name_el and name_el.text.strip():
                    user_name = name_el.text.strip()
                self.logger.info(
                    f"Connexion eLearning réussie{' en tant que ' + user_name if user_name else ''}"
                )
                self.logged_in = True
                return True

            # Si nous arrivons ici, la connexion semble échouée
            self.logger.error("Échec de connexion eLearning: identifiants invalides ou flux modifié")
            return False

        except Exception as e:
            self.logger.error(f"Erreur lors de la connexion: {str(e)}")
            return False
    
    def get_course_content(self, course_url: str, course_id: str):
        """Récupérer le contenu d'un cours spécifique via HTTP."""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 1) Essayer d'abord en anonyme (beaucoup d'espaces d'affichage sont publics)
                resp = self.session.get(course_url, timeout=25, allow_redirects=True)
                resp.raise_for_status()

                # Si redirigé vers la page de login, réessayer login
                if '/login/' in resp.url:
                    self.logger.info("Authentification requise. Tentative de connexion...")
                    if not self.logged_in:
                        if not self.login():
                            return None
                        # Récupérer à nouveau la page du cours après login
                        resp = self.session.get(course_url, timeout=25, allow_redirects=True)
                        resp.raise_for_status()

                soup = BeautifulSoup(resp.text, 'lxml')

                # Détection de login forcé dans le contenu
                if soup.select_one('form#login, form[action*="/login/"]'):
                    self.logger.info("Page de connexion détectée sur le cours. Tentative de connexion...")
                    if not self.logged_in:
                        if not self.login():
                            return None
                        # Récupérer à nouveau la page du cours après login
                        resp = self.session.get(course_url, timeout=25, allow_redirects=True)
                        resp.raise_for_status()
                        soup = BeautifulSoup(resp.text, 'lxml')

                content = {
                    'course_id': course_id,
                    'url': course_url,
                    'timestamp': time.time(),
                    'sections': []
                }

                sections = self._select_sections(soup)
                if not sections:
                    self.logger.warning(
                        f"Aucune section trouvée pour le cours {course_id}, tentative de récupération générale"
                    )
                    # fallback: prendre les enfants de course-content
                    course_content = soup.select_one('.course-content')
                    if course_content:
                        sections = course_content.find_all(recursive=False)

                for section in sections or []:
                    try:
                        section_data = self._extract_section_data(section)
                        if section_data:
                            content['sections'].append(section_data)
                    except Exception as section_error:
                        self.logger.warning(
                            f"Erreur lors de l'extraction d'une section: {str(section_error)}"
                        )
                        continue

                # Option: télécharger les fichiers référencés
                if self.enable_file_download and self.firebase_mgr:
                    self._download_all_files(course_id, content)

                self.logger.info(f"Contenu récupéré pour le cours {course_id}: {len(content['sections'])} sections")
                return content

            except Exception as e:
                retry_count += 1
                self.logger.warning(
                    f"Tentative {retry_count}/{max_retries} échouée pour le cours {course_id}: {str(e)}"
                )
                if retry_count < max_retries:
                    time.sleep(2)
                else:
                    self.logger.error(
                        f"Échec définitif pour le cours {course_id} après {max_retries} tentatives"
                    )
                    return None

        return None
    
    def _select_sections(self, soup: BeautifulSoup):
        """Sélectionner les blocs de section de manière robuste (Moodle varie selon le thème)."""
        # Essayer différents sélecteurs courants
        selectors = [
            '.course-content li.section.main',
            '.course-content li.section',
            '.course-content section[id^="section-"]',
        ]
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                return elements
        return []

    def _extract_section_data(self, section_element):
        """Extraire les données d'une section (BeautifulSoup Tag)."""
        try:
            section_data = {
                'title': '',
                'activities': [],
                'resources': []
            }

            # Titre de la section
            title_el = (section_element.select_one('.sectionname') or
                        section_element.select_one('h3') or
                        section_element.select_one('h2'))
            if title_el and title_el.get_text(strip=True):
                section_data['title'] = title_el.get_text(strip=True)
            else:
                # Identifiant de section comme fallback
                section_data['title'] = section_element.get('id', 'Section')

            # Activités et ressources
            activities = section_element.select('li.activity, div.activity')
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
        """Extraire les données d'une activité (BeautifulSoup Tag)."""
        try:
            activity_data = {
                'title': '',
                'type': '',
                'url': '',
                'description': '',
                'files': []
            }

            # Titre et lien
            title_el = activity_element.select_one('.activityinstance a, aaalink, a')
            if not title_el:
                # Parfois, le lien peut être ailleurs
                possible = activity_element.find('a', href=True)
                title_el = possible
            if title_el:
                activity_data['title'] = title_el.get_text(strip=True)
                activity_data['url'] = urljoin(Config.ELEARNING_URL, title_el.get('href', ''))

            # Type d'activité à partir des classes (Moodle met le type dans la classe)
            class_attr = activity_element.get('class', [])
            classes = ' '.join(class_attr) if isinstance(class_attr, list) else str(class_attr or '')
            for moodle_type in ['resource', 'forum', 'assign', 'url', 'folder', 'page', 'quiz']:
                if moodle_type in classes:
                    activity_data['type'] = 'assignment' if moodle_type == 'assign' else moodle_type
                    break
            if not activity_data['type']:
                activity_data['type'] = 'other'

            # Description si disponible
            desc_el = activity_element.select_one('.activity-description, .contentafterlink, .instancename + .text_to_html')
            if desc_el:
                activity_data['description'] = desc_el.get_text(strip=True)

            # Fichiers associés: récupérer les liens de fichiers 
            file_links = []
            for a in activity_element.select('a[href]'):
                href = a.get('href', '')
                text = a.get_text(strip=True)
                if not href:
                    continue
                # Heuristique: Moodle sert les fichiers via pluginfile.php
                if 'pluginfile.php' in href or any(href.lower().endswith(ext) for ext in [
                    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.zip', '.rar', '.txt'
                ]):
                    file_links.append({'name': text or href.split('/')[-1], 'url': urljoin(Config.ELEARNING_URL, href)})
            activity_data['files'] = file_links

            # Si c'est un dossier (folder), tenter d'extraire les fichiers internes
            if activity_data['type'] == 'folder' and activity_data.get('url'):
                try:
                    internal_files = self._extract_folder_files(activity_data['url'])
                    if internal_files:
                        # Fusionner sans doublons (par URL)
                        existing_urls = {f['url'] for f in activity_data['files']}
                        for f in internal_files:
                            if f['url'] not in existing_urls:
                                activity_data['files'].append(f)
                except Exception as fe:
                    self.logger.warning(f"Extraction dossier échouée {activity_data['url']}: {fe}")

            return activity_data

        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction des données d'activité: {str(e)}")
            return None
    
    def get_all_courses_content(self):
        """Récupérer le contenu de tous les cours surveillés (HTTP)."""
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
            time.sleep(1.5)

        self.logger.info(f"Scan terminé: {successful_scans} succès, {failed_scans} échecs")
        return all_content
    
    def close(self):
        """Aucune ressource à fermer pour HTTP; méthode pour compat."""
        # La session HTTP peut être réutilisée; on ne la ferme pas explicitement
        return

    # ===================== Téléchargement de fichiers helper =====================
    def _download_all_files(self, course_id: str, content: dict):
        try:
            if not self.firebase_mgr:
                return
            sections = content.get('sections', [])
            for section in sections:
                stitle = section.get('title','')
                for act in section.get('activities', []):
                    for f in act.get('files', []):
                        self.firebase_mgr.download_file(self.session, f.get('url',''), course_id, stitle, act.get('title',''))
                for res in section.get('resources', []):
                    for f in res.get('files', []):
                        self.firebase_mgr.download_file(self.session, f.get('url',''), course_id, stitle, res.get('title',''))
        except Exception as e:
            self.logger.warning(f"Erreur download fichiers cours {course_id}: {e}")

    # ===================== Extraction fichiers dossier =====================
    def _extract_folder_files(self, folder_url: str):
        """Ouvrir la page d'un dossier Moodle et récupérer les liens de fichiers internes."""
        try:
            resp = self.session.get(folder_url, timeout=25)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'lxml')
            files = []
            for a in soup.select('a[href]'):
                href = a.get('href','')
                label = a.get_text(strip=True)
                if not href:
                    continue
                if 'pluginfile.php' in href or any(href.lower().endswith(ext) for ext in [
                    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.zip', '.rar', '.txt'
                ]):
                    files.append({'name': label or href.split('/')[-1], 'url': urljoin(Config.ELEARNING_URL, href)})
            return files
        except Exception as e:
            self.logger.warning(f"_extract_folder_files erreur {folder_url}: {e}")
            return []