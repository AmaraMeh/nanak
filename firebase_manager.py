import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.exceptions import DefaultCredentialsError
from config import Config

class FirebaseManager:
    def __init__(self):
        self.db = None
        self.logger = logging.getLogger(__name__)
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialiser Firebase"""
        try:
            # Stratégie: 1) GOOGLE_APPLICATION_CREDENTIALS si présent
            #            2) Application Default Credentials (ADC)
            #            3) Fallback local sans Firebase

            project_id = Config.FIREBASE_CONFIG.get('projectId')

            gac_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if gac_path and os.path.exists(gac_path):
                cred = credentials.Certificate(gac_path)
                firebase_admin.initialize_app(cred, {'projectId': project_id})
                self.db = firestore.client()
                self.logger.info("Firebase initialisé via GOOGLE_APPLICATION_CREDENTIALS")
                return

            # Essayer ADC (variables d'environnement / métadonnées)
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {'projectId': project_id})
            
            self.db = firestore.client()
            self.logger.info("Firebase initialisé via Application Default Credentials")
            
        except (FileNotFoundError, DefaultCredentialsError, Exception) as e:
            # Journaliser clairement et passer en mode local
            self.logger.error(f"Erreur lors de l'initialisation de Firebase: {str(e)}")
            self.logger.info("Firebase non configuré. Utilisation du stockage local (fallback).")
            self.db = None
    
    def save_course_content(self, course_id, content):
        """Sauvegarder le contenu d'un cours"""
        try:
            if self.db:
                doc_ref = self.db.collection('course_content').document(course_id)
                doc_ref.set({
                    'content': content,
                    'timestamp': content['timestamp'],
                    'last_updated': firestore.SERVER_TIMESTAMP
                })
                self.logger.info(f"Contenu sauvegardé pour le cours {course_id}")
                return True
            else:
                # Fallback: sauvegarde locale
                return self._save_local(course_id, content)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde du cours {course_id}: {str(e)}")
            return self._save_local(course_id, content)
    
    def get_course_content(self, course_id):
        """Récupérer le contenu précédent d'un cours"""
        try:
            if self.db:
                doc_ref = self.db.collection('course_content').document(course_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    return data['content']
                else:
                    return None
            else:
                # Fallback: lecture locale
                return self._load_local(course_id)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du cours {course_id}: {str(e)}")
            return self._load_local(course_id)
    
    def save_changes_log(self, course_id, changes):
        """Sauvegarder un log des changements"""
        try:
            if self.db:
                doc_ref = self.db.collection('changes_log').document()
                doc_ref.set({
                    'course_id': course_id,
                    'changes': changes,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                self.logger.info(f"Log de changements sauvegardé pour le cours {course_id}")
                return True
            else:
                return self._save_changes_local(course_id, changes)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde du log de changements: {str(e)}")
            return self._save_changes_local(course_id, changes)
    
    def _save_local(self, course_id, content):
        """Sauvegarde locale de fallback"""
        try:
            import os
            os.makedirs('local_storage', exist_ok=True)
            
            filename = f"local_storage/course_{course_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Contenu sauvegardé localement pour le cours {course_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde locale: {str(e)}")
            return False
    
    def _load_local(self, course_id):
        """Chargement local de fallback"""
        try:
            import os
            filename = f"local_storage/course_{course_id}.json"
            
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement local: {str(e)}")
            return None
    
    def _save_changes_local(self, course_id, changes):
        """Sauvegarde locale des changements"""
        try:
            import os
            import json
            from datetime import datetime
            
            os.makedirs('local_storage', exist_ok=True)
            
            log_entry = {
                'course_id': course_id,
                'changes': changes,
                'timestamp': datetime.now().isoformat()
            }
            
            filename = f"local_storage/changes_log_{course_id}_{int(datetime.now().timestamp())}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Log de changements sauvegardé localement pour le cours {course_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde locale des changements: {str(e)}")
            return False