import time
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import Config

class ELearningScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": Config.USER_AGENT
        })
        self.logger = logging.getLogger(__name__)
        self.logged_in = False

    # -------------------------
    # Authentification (sans Chrome)
    # -------------------------
    def login(self) -> bool:
        """Se connecter à la plateforme eLearning via HTTP (requests) et activer le debug."""
        try:
            login_page_url = urljoin(Config.ELEARNING_URL, "/login/index.php")
            resp = self.session.get(login_page_url, timeout=20)
            if resp.status_code != 200:
                self.logger.error(f"Page de connexion indisponible (HTTP {resp.status_code})")
                return False

            soup = BeautifulSoup(resp.text, "lxml")
            token_input = soup.find("input", {"name": "logintoken"})
            login_token = token_input.get("value") if token_input else None

            self.logger.info(
                f"Préparation de la connexion. logintoken={'trouvé' if login_token else 'absent'}"
            )

            payload = {
                "username": Config.USERNAME,
                "password": Config.PASSWORD,
                # Moodle accepte la connexion sans rememberusername, mais on l'ajoute si présent
                "rememberusername": 1,
            }
            if login_token:
                payload["logintoken"] = login_token

            post_resp = self.session.post(login_page_url, data=payload, timeout=30, allow_redirects=True)

            # Vérifier si une session Moodle est établie
            cookie_names = [c.name for c in self.session.cookies]
            has_session_cookie = any("MoodleSession" in name for name in cookie_names)

            # Déterminer si on est connecté en vérifiant la présence du menu utilisateur
            check_resp = self.session.get(urljoin(Config.ELEARNING_URL, "/"), timeout=20)
            check_soup = BeautifulSoup(check_resp.text, "lxml")
            user_menu = check_soup.select_one(".usermenu, .user-menu, #user-menu")
            user_name_text = None
            if user_menu:
                # Essayer d'extraire le nom utilisateur si disponible
                user_name_el = user_menu.select_one(".usertext, .usertext-mr, .userbutton")
                if user_name_el:
                    user_name_text = user_name_el.get_text(strip=True)

            self.logged_in = bool(user_menu or has_session_cookie)

            if self.logged_in:
                debug_name = user_name_text or "(nom non détecté)"
                self.logger.info(
                    f"Connexion eLearning réussie. Cookies: {cookie_names}. Utilisateur: {debug_name}"
                )
                return True

            # Vérifier si on a été renvoyé vers la page de login (échec)
            if "login" in post_resp.url or "login" in check_resp.url:
                self.logger.error("Échec de la connexion: redirection persistante vers la page de login")
            else:
                self.logger.error("Échec de la connexion: indicateurs utilisateur non détectés")
            return False

        except Exception as auth_error:
            self.logger.error(f"Erreur lors de la connexion HTTP: {str(auth_error)}")
            return False

    # -------------------------
    # Scraping des cours (sans Chrome)
    # -------------------------
    def get_course_content(self, course_url: str, course_id: str) -> Optional[Dict]:
        """Récupérer le contenu d'un cours spécifique par HTTP, avec ré-auth si nécessaire."""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(course_url, timeout=30, allow_redirects=True)

                # Si on est redirigé vers la page de login, tenter de se connecter
                if "login/index.php" in resp.url or self._page_requires_login(resp.text):
                    if not self.logged_in:
                        self.logger.info("Authentification requise. Tentative de connexion...")
                        if not self.login():
                            return None
                        # Refaire la requête après login
                        resp = self.session.get(course_url, timeout=30, allow_redirects=True)

                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")

                content = {
                    "course_id": course_id,
                    "url": course_url,
                    "timestamp": time.time(),
                    "sections": []
                }

                soup = BeautifulSoup(resp.text, "lxml")
                sections = self._find_sections(soup)

                if not sections:
                    self.logger.warning(
                        f"Aucune section trouvée pour le cours {course_id}, tentative de récupération générique"
                    )
                    generic_container = soup.select_one(".course-content") or soup
                    sections = generic_container.find_all(recursive=False)

                for section_soup in sections:
                    try:
                        section_data = self._extract_section_data_from_soup(section_soup)
                        if section_data and (section_data["activities"] or section_data["resources"] or section_data["title"]):
                            content["sections"].append(section_data)
                    except Exception as section_err:
                        self.logger.warning(f"Erreur lors de l'extraction d'une section: {str(section_err)}")
                        continue

                self.logger.info(
                    f"Contenu récupéré pour le cours {course_id}: {len(content['sections'])} sections"
                )
                return content

            except Exception as fetch_error:
                self.logger.warning(
                    f"Tentative {attempt}/{max_retries} échouée pour le cours {course_id}: {str(fetch_error)}"
                )
                if attempt < max_retries:
                    time.sleep(2)
                else:
                    self.logger.error(
                        f"Échec définitif pour le cours {course_id} après {max_retries} tentatives"
                    )
                    return None

        return None

    def _page_requires_login(self, html: str) -> bool:
        """Détecter si la page renvoyée est une page de login Moodle."""
        soup = BeautifulSoup(html, "lxml")
        return bool(soup.select_one("form#login, #login, input[name='username'][type='text']"))

    def _find_sections(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        """Essayer plusieurs sélecteurs pour récupérer les sections de cours."""
        candidates = [
            "#region-main .course-content li.section",
            ".course-content li.section",
            ".course-content .section",
            "li.section",
            "div.section",
        ]
        for selector in candidates:
            found = soup.select(selector)
            if found:
                return found
        return []

    def _extract_section_data_from_soup(self, section: BeautifulSoup) -> Dict:
        """Extraire les données d'une section à partir du HTML."""
        section_data: Dict = {
            "title": "",
            "activities": [],
            "resources": [],
        }

        # Titre de la section
        title_el = section.select_one(".sectionname, h3.sectionname, h3")
        if title_el:
            section_data["title"] = title_el.get_text(strip=True)

        # Activités et ressources
        activities = section.select(".activity")
        for activity in activities:
            activity_data = self._extract_activity_data_from_soup(activity)
            if activity_data:
                if activity_data["type"] == "resource":
                    section_data["resources"].append(activity_data)
                else:
                    section_data["activities"].append(activity_data)

        return section_data

    def _extract_activity_data_from_soup(self, activity: BeautifulSoup) -> Optional[Dict]:
        """Extraire les données d'une activité à partir du HTML."""
        try:
            title_link = activity.select_one(".activityinstance a, .aalink")
            title_text = title_link.get_text(strip=True) if title_link else ""
            url = title_link.get("href") if title_link else ""

            classes = " ".join(activity.get("class", []))
            if "resource" in classes:
                activity_type = "resource"
            elif "forum" in classes:
                activity_type = "forum"
            elif "assign" in classes:
                activity_type = "assignment"
            else:
                activity_type = "other"

            description_el = activity.select_one(".activity-description, .contentafterlink")
            description_text = description_el.get_text(strip=True) if description_el else ""

            files: List[Dict] = []
            # Chercher des liens de fichiers éventuels dans l'activité
            for a in activity.select("a"):
                href = a.get("href") or ""
                name = a.get_text(strip=True)
                if href and name and href != url:
                    # Heuristique simple: conserver quelques liens additionnels comme fichiers
                    if any(ext in href.lower() for ext in [
                        ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".zip", ".rar"
                    ]):
                        files.append({"name": name, "url": href})

            return {
                "title": title_text,
                "type": activity_type,
                "url": url,
                "description": description_text,
                "files": files,
            }
        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction des données d'activité: {str(e)}")
            return None

    def get_all_courses_content(self) -> Dict[str, Dict]:
        """Récupérer le contenu de tous les cours surveillés (HTTP)."""
        all_content: Dict[str, Dict] = {}
        successful_scans = 0
        failed_scans = 0

        self.logger.info(
            f"Début du scan de {len(Config.MONITORED_SPACES)} espaces d'affichage"
        )

        for i, space in enumerate(Config.MONITORED_SPACES, start=1):
            self.logger.info(
                f"[{i}/{len(Config.MONITORED_SPACES)}] Récupération du contenu pour: {space['name']}"
            )
            try:
                content = self.get_course_content(space["url"], space["id"])
                if content:
                    all_content[space["id"]] = content
                    successful_scans += 1
                    self.logger.info(f"✅ Succès pour: {space['name']}")
                else:
                    failed_scans += 1
                    self.logger.error(f"❌ Échec pour: {space['name']}")
            except Exception as e:
                failed_scans += 1
                self.logger.error(f"❌ Erreur pour {space['name']}: {str(e)}")

            time.sleep(1.5)  # throttling soft

        self.logger.info(
            f"Scan terminé: {successful_scans} succès, {failed_scans} échecs"
        )
        return all_content

    def close(self) -> None:
        """Compatibilité: rien à fermer en mode HTTP."""
        return