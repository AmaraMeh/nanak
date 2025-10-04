import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.exceptions import DefaultCredentialsError
from config import Config

class FirebaseManager:
    """Gestionnaire de persistance.

    Actuellement orienté Firebase, mais expose une interface qui pourra être implémentée
    par un adaptateur Supabase (mêmes signatures) sans toucher le reste du code.
    """
    def __init__(self):
        self.db = None
        self.logger = logging.getLogger(__name__)
        self.provider = Config.DB_PROVIDER
        self.download_root = 'downloads'
        os.makedirs(self.download_root, exist_ok=True)
        if self.provider == 'firebase':
            self._initialize_firebase()
        elif self.provider == 'supabase':
            # Placeholder: initialisation différée (besoin URL + service key)
            self.logger.info("Mode SUPABASE sélectionné - adaptateur non encore implémenté")
        else:
            self.logger.warning(f"Provider inconnu {self.provider}, fallback local")
    
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
        """Sauvegarder le contenu d'un cours (avec versioning possible)."""
        try:
            if self.provider == 'supabase':
                return self._save_supabase_course(course_id, content)
            if self.db:
                doc_ref = self.db.collection('course_content').document(course_id)
                existing = doc_ref.get()
                version = 1
                if existing.exists and Config.COURSE_VERSIONING:
                    try:
                        version = int(existing.to_dict().get('version', 1)) + 1
                    except Exception:
                        version = 1
                doc_ref.set({
                    'content': content,
                    'timestamp': content['timestamp'],
                    'version': version,
                    'last_updated': firestore.SERVER_TIMESTAMP
                })
                self.logger.info(f"Contenu sauvegardé (firebase) {course_id}")
                return True
            return self._save_local(course_id, content)
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde cours {course_id}: {e}")
            return self._save_local(course_id, content)
    
    def get_course_content(self, course_id):
        try:
            if self.provider == 'supabase':
                return self._load_supabase_course(course_id)
            if self.db:
                doc_ref = self.db.collection('course_content').document(course_id)
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    return data.get('content')
                return None
            return self._load_local(course_id)
        except Exception as e:
            self.logger.error(f"Erreur get cours {course_id}: {e}")
            return self._load_local(course_id)
    
    def save_changes_log(self, course_id, changes):
        """Sauvegarder un lot de changements (avec déduplication basique)."""
        try:
            # Calcul hash pour éviter doublons exacts
            import hashlib, json as _json
            payload = _json.dumps(changes, sort_keys=True, ensure_ascii=False)
            digest = hashlib.sha1(payload.encode('utf-8')).hexdigest()
            if self._is_duplicate_change_hash(course_id, digest):
                self.logger.info(f"Changements ignorés (dup hash) {course_id}")
                return False
            if self.provider == 'supabase':
                return self._save_supabase_changes(course_id, changes, digest)
            if self.db:
                doc_ref = self.db.collection('changes_log').document()
                doc_ref.set({
                    'course_id': course_id,
                    'changes': changes,
                    'hash': digest,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                self._remember_change_hash(course_id, digest)
                self.logger.info(f"Log changements (firebase) {course_id}")
                return True
            ok = self._save_changes_local(course_id, changes, digest)
            if ok:
                self._remember_change_hash(course_id, digest)
            return ok
        except Exception as e:
            self.logger.error(f"Erreur save changes {course_id}: {e}")
            return False
    
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
    
    def _save_changes_local(self, course_id, changes, digest=None):
        """Sauvegarde locale des changements"""
        try:
            import os
            import json
            from datetime import datetime
            
            os.makedirs('local_storage', exist_ok=True)
            
            log_entry = {
                'course_id': course_id,
                'changes': changes,
                'hash': digest,
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

    # ===================== Téléchargement de fichiers =====================
    def download_file(self, session, file_url: str, course_id: str, section_title: str = '', parent_title: str = ''):
        """Télécharger un fichier et le stocker localement. Retourne le chemin ou None."""
        try:
            import re
            import hashlib
            safe_section = re.sub(r'[^a-zA-Z0-9_-]+', '_', section_title)[:40] if section_title else 'root'
            safe_parent = re.sub(r'[^a-zA-Z0-9_-]+', '_', parent_title)[:40] if parent_title else 'item'
            course_folder = os.path.join(self.download_root, course_id, safe_section)
            os.makedirs(course_folder, exist_ok=True)
            # Nom basé sur hash pour éviter collisions
            name_part = file_url.split('/')[-1].split('?')[0]
            h = hashlib.sha1(file_url.encode('utf-8')).hexdigest()[:8]
            filename = f"{safe_parent}_{h}_{name_part}"[:120]
            path = os.path.join(course_folder, filename)
            if os.path.exists(path):
                return path  # déjà téléchargé
            resp = session.get(file_url, timeout=40)
            if resp.status_code != 200 or not resp.content:
                self.logger.warning(f"Téléchargement échoué {file_url} -> status {resp.status_code}")
                return None
            # Taille limite 50MB
            if len(resp.content) > 50 * 1024 * 1024:
                self.logger.warning(f"Fichier ignoré (taille >50MB): {file_url}")
                return None
            with open(path, 'wb') as f:
                f.write(resp.content)
            return path
        except Exception as e:
            self.logger.error(f"Erreur téléchargement fichier {file_url}: {e}")
            return None

    # ===================== Requêtes historiques =====================
    def get_changes_since(self, days: int = 1):
        """Récupérer les logs de changements sur N jours (local uniquement simplifié)."""
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        if self.db:
            try:
                query = self.db.collection('changes_log').where('timestamp', '>=', cutoff)
                docs = query.stream()
                for d in docs:
                    data = d.to_dict()
                    results.append(data)
            except Exception as e:
                self.logger.error(f"Erreur récupération logs Firebase: {e}")
        # Local fallback
        try:
            import glob, json
            for path in glob.glob('local_storage/changes_log_*.json'):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    ts = data.get('timestamp')
                    # timestamp iso ou int
                    if isinstance(ts, str):
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(ts.replace('Z',''))
                        except:
                            continue
                        if dt >= cutoff:
                            results.append(data)
                except Exception:
                    continue
        except Exception:
            pass
        return results

    # ===================== Hash mémoire pour dédup =====================
    def _remember_change_hash(self, course_id, digest):
        try:
            os.makedirs('local_storage', exist_ok=True)
            path = 'local_storage/changes_hashes.json'
            store = {}
            if os.path.exists(path):
                with open(path,'r',encoding='utf-8') as f:
                    store = json.load(f)
            course_hashes = store.get(course_id, [])
            course_hashes.append(digest)
            # limiter mémoire
            store[course_id] = course_hashes[-200:]
            with open(path,'w',encoding='utf-8') as f:
                json.dump(store,f,ensure_ascii=False,indent=2)
        except Exception:
            pass

    def _is_duplicate_change_hash(self, course_id, digest):
        try:
            path = 'local_storage/changes_hashes.json'
            if not os.path.exists(path):
                return False
            with open(path,'r',encoding='utf-8') as f:
                store = json.load(f)
            return digest in store.get(course_id, [])
        except Exception:
            return False

    # ===================== Supabase placeholders =====================
    def _save_supabase_course(self, course_id, content):
        # TODO: implémenter via supabase-py
        return self._save_local(course_id, content)

    def _load_supabase_course(self, course_id):
        return self._load_local(course_id)

    def _save_supabase_changes(self, course_id, changes, digest):
        return self._save_changes_local(course_id, changes, digest)