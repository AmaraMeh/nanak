import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import difflib

class ChangeDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_changes(self, old_content: Optional[Dict], new_content: Dict, is_initial_scan: bool = False) -> List[Dict]:
        """
        Détecter les changements entre l'ancien et le nouveau contenu
        """
        changes = []
        
        if old_content is None or is_initial_scan:
            # Premier scan - extraire tout le contenu existant
            changes.extend(self._extract_all_existing_content(new_content))
            return changes
        
        # Comparer les sections
        old_sections = old_content.get('sections', [])
        new_sections = new_content.get('sections', [])
        
        section_changes = self._compare_sections(old_sections, new_sections)
        changes.extend(section_changes)
        
        return changes
    
    def _extract_all_existing_content(self, content: Dict) -> List[Dict]:
        """Extraire tout le contenu existant pour le premier scan"""
        changes = []
        
        # Ajouter un message de début de scan
        changes.append({
            'type': 'initial_scan_start',
            'message': '🔍 Premier scan complet du cours - Extraction de tout le contenu existant',
            'details': f"Nombre total de sections: {len(content.get('sections', []))}"
        })
        
        sections = content.get('sections', [])
        total_items = 0
        
        now_iso = datetime.now().isoformat()
        for section in sections:
            section_title = section.get('title', 'Sans titre')
            
            # Compter les éléments dans cette section
            activities = section.get('activities', [])
            resources = section.get('resources', [])
            section_total = len(activities) + len(resources)
            total_items += section_total
            
            if section_total > 0:
                changes.append({
                    'type': 'existing_section',
                    'section_title': section_title,
                    'message': f'📂 Section existante: {section_title}',
                    'details': f"Activités: {len(activities)}, Ressources: {len(resources)}"
                })
                
                # Ajouter chaque activité existante
                for activity in activities:
                    changes.append({
                        'type': 'existing_activity',
                        'activity_title': activity.get('title', 'Sans titre'),
                        'activity_type': activity.get('type', 'unknown'),
                        'message': f'📋 Activité existante: {activity.get("title", "Sans titre")}',
                        'details': self._get_activity_summary(activity)
                    })
                    
                    # Ajouter chaque fichier dans l'activité
                    for file_info in activity.get('files', []):
                        # Date de publication inconnue côté Moodle sans page dédiée => on stocke la date de découverte
                        changes.append({
                            'type': 'existing_file',
                            'file_name': file_info.get('name', 'Sans nom'),
                            'parent_title': activity.get('title', 'Sans titre'),
                            'file_date': now_iso,
                            'message': f"📄 Fichier existant: {file_info.get('name', 'Sans nom')}",
                            'details': f"Dans l'activité: {activity.get('title', 'Sans titre')} | Publié (détecté) : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                        })
                
                # Ajouter chaque ressource existante
                for resource in resources:
                    changes.append({
                        'type': 'existing_resource',
                        'resource_title': resource.get('title', 'Sans titre'),
                        'message': f'📚 Ressource existante: {resource.get("title", "Sans titre")}',
                        'details': self._get_resource_summary(resource)
                    })
                    
                    # Ajouter chaque fichier dans la ressource
                    for file_info in resource.get('files', []):
                        changes.append({
                            'type': 'existing_file',
                            'file_name': file_info.get('name', 'Sans nom'),
                            'parent_title': resource.get('title', 'Sans titre'),
                            'file_date': now_iso,
                            'message': f"📄 Fichier existant: {file_info.get('name', 'Sans nom')}",
                            'details': f"Dans la ressource: {resource.get('title', 'Sans titre')} | Publié (détecté) : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                        })
        
        # Ajouter un message de fin de scan
        changes.append({
            'type': 'initial_scan_complete',
            'message': f'✅ Premier scan terminé - {total_items} éléments trouvés',
            'details': f"Le cours contient {len(sections)} sections avec {total_items} éléments au total"
        })
        
        return changes
    
    def _compare_sections(self, old_sections: List[Dict], new_sections: List[Dict]) -> List[Dict]:
        """Comparer les sections entre l'ancien et le nouveau contenu"""
        changes = []
        
        # Créer des dictionnaires pour faciliter la comparaison
        old_sections_dict = {section['title']: section for section in old_sections}
        new_sections_dict = {section['title']: section for section in new_sections}
        
        # Détection des renommages potentiels via similarité
        unmatched_old = set(old_sections_dict.keys())
        unmatched_new = set(new_sections_dict.keys())
        rename_pairs = []  # (old_title, new_title)
        for old_title in list(unmatched_old):
            best_match = None
            best_ratio = 0.0
            for new_title in list(unmatched_new):
                ratio = difflib.SequenceMatcher(None, old_title, new_title).ratio()
                if ratio > 0.6 and ratio > best_ratio:  # seuil empirique
                    best_ratio = ratio
                    best_match = new_title
            if best_match and old_title != best_match:
                rename_pairs.append((old_title, best_match, best_ratio))
                unmatched_old.discard(old_title)
                unmatched_new.discard(best_match)

        # Sections renommées
        for old_title, new_title, ratio in rename_pairs:
            changes.append({
                'type': 'section_renamed',
                'old_title': old_title,
                'new_title': new_title,
                'similarity': f"{ratio:.2f}",
                'message': f'Section renommée: {old_title} ➜ {new_title}',
                'details': f'Similarité {ratio:.2f} | Ancien résumé: {self._get_section_summary(old_sections_dict[old_title])} | Nouveau résumé: {self._get_section_summary(new_sections_dict[new_title])}'
            })

        # Sections ajoutées (non mappées)
        for title in unmatched_new:
            section = new_sections_dict[title]
            changes.append({
                'type': 'section_added',
                'section_title': title,
                'message': f'Nouvelle section ajoutée: {title}',
                'details': self._get_section_summary(section)
            })
        
        # Sections supprimées (non mappées)
        for title in unmatched_old:
            section = old_sections_dict[title]
            changes.append({
                'type': 'section_removed',
                'section_title': title,
                'message': f'Section supprimée: {title}',
                'details': self._get_section_summary(section)
            })
        
        # Sections modifiées (ignorer celles qui sont renommées -> prendre le nouveau titre uniquement)
        processed_titles = {new for _, new, _ in rename_pairs}
        for title, new_section in new_sections_dict.items():
            if title in old_sections_dict and title not in processed_titles:
                old_section = old_sections_dict[title]
                section_changes = self._compare_section_content(old_section, new_section)
                changes.extend(section_changes)
        
        return changes
    
    def _compare_section_content(self, old_section: Dict, new_section: Dict) -> List[Dict]:
        """Comparer le contenu d'une section"""
        changes = []
        
        # Comparer les activités
        activity_changes = self._compare_activities(
            old_section.get('activities', []),
            new_section.get('activities', [])
        )
        changes.extend(activity_changes)
        
        # Comparer les ressources
        resource_changes = self._compare_resources(
            old_section.get('resources', []),
            new_section.get('resources', [])
        )
        changes.extend(resource_changes)
        
        return changes
    
    def _compare_activities(self, old_activities: List[Dict], new_activities: List[Dict]) -> List[Dict]:
        """Comparer les activités"""
        changes = []
        
        old_activities_dict = {activity['title']: activity for activity in old_activities}
        new_activities_dict = {activity['title']: activity for activity in new_activities}
        
        # Activités ajoutées
        for title, activity in new_activities_dict.items():
            if title not in old_activities_dict:
                changes.append({
                    'type': 'activity_added',
                    'activity_title': title,
                    'activity_type': activity.get('type', 'unknown'),
                    'message': f'Nouvelle activité ajoutée: {title}',
                    'details': self._get_activity_summary(activity)
                })
        
        # Activités supprimées
        for title, activity in old_activities_dict.items():
            if title not in new_activities_dict:
                changes.append({
                    'type': 'activity_removed',
                    'activity_title': title,
                    'activity_type': activity.get('type', 'unknown'),
                    'message': f'Activité supprimée: {title}',
                    'details': self._get_activity_summary(activity)
                })
        
        # Activités modifiées
        for title, new_activity in new_activities_dict.items():
            if title in old_activities_dict:
                old_activity = old_activities_dict[title]
                activity_changes = self._compare_activity_content(old_activity, new_activity)
                changes.extend(activity_changes)
        
        return changes
    
    def _compare_resources(self, old_resources: List[Dict], new_resources: List[Dict]) -> List[Dict]:
        """Comparer les ressources"""
        changes = []
        
        old_resources_dict = {resource['title']: resource for resource in old_resources}
        new_resources_dict = {resource['title']: resource for resource in new_resources}
        
        # Ressources ajoutées
        for title, resource in new_resources_dict.items():
            if title not in old_resources_dict:
                changes.append({
                    'type': 'resource_added',
                    'resource_title': title,
                    'message': f'Nouvelle ressource ajoutée: {title}',
                    'details': self._get_resource_summary(resource)
                })
        
        # Ressources supprimées
        for title, resource in old_resources_dict.items():
            if title not in new_resources_dict:
                changes.append({
                    'type': 'resource_removed',
                    'resource_title': title,
                    'message': f'Ressource supprimée: {title}',
                    'details': self._get_resource_summary(resource)
                })
        
        # Ressources modifiées
        for title, new_resource in new_resources_dict.items():
            if title in old_resources_dict:
                old_resource = old_resources_dict[title]
                resource_changes = self._compare_resource_content(old_resource, new_resource)
                changes.extend(resource_changes)
        
        return changes
    
    def _compare_activity_content(self, old_activity: Dict, new_activity: Dict) -> List[Dict]:
        """Comparer le contenu d'une activité"""
        changes = []
        
        # Comparer les fichiers
        old_files = old_activity.get('files', [])
        new_files = new_activity.get('files', [])
        
        file_changes = self._compare_files(old_files, new_files, old_activity['title'])
        changes.extend(file_changes)
        
        # Comparer la description
        old_desc = old_activity.get('description', '')
        new_desc = new_activity.get('description', '')
        
        if old_desc != new_desc:
            changes.append({
                'type': 'activity_description_changed',
                'activity_title': old_activity['title'],
                'message': f'Description modifiée pour l\'activité: {old_activity["title"]}',
                'details': f'Ancienne: {old_desc[:100]}...\nNouvelle: {new_desc[:100]}...'
            })
        
        return changes
    
    def _compare_resource_content(self, old_resource: Dict, new_resource: Dict) -> List[Dict]:
        """Comparer le contenu d'une ressource"""
        changes = []
        
        # Comparer les fichiers
        old_files = old_resource.get('files', [])
        new_files = new_resource.get('files', [])
        
        file_changes = self._compare_files(old_files, new_files, old_resource['title'])
        changes.extend(file_changes)
        
        return changes
    
    def _compare_files(self, old_files: List[Dict], new_files: List[Dict], parent_title: str) -> List[Dict]:
        """Comparer les fichiers"""
        changes = []
        
        old_files_dict = {file['name']: file for file in old_files}
        new_files_dict = {file['name']: file for file in new_files}
        
        # Fichiers ajoutés
        from datetime import datetime
        for name, file in new_files_dict.items():
            if name not in old_files_dict:
                changes.append({
                    'type': 'file_added',
                    'file_name': name,
                    'parent_title': parent_title,
                    'file_url': file.get('url'),
                    'file_date': datetime.now().isoformat(),
                    'message': f'Nouveau fichier ajouté: {name}',
                    'details': f"Dans: {parent_title}\nURL: {file.get('url', 'N/A')}\nPublié (détecté) : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                })
        
        # Fichiers supprimés
        for name, file in old_files_dict.items():
            if name not in new_files_dict:
                changes.append({
                    'type': 'file_removed',
                    'file_name': name,
                    'parent_title': parent_title,
                    'message': f'Fichier supprimé: {name}',
                    'details': f'Dans: {parent_title}'
                })
        
        return changes
    
    def _get_section_summary(self, section: Dict) -> str:
        """Obtenir un résumé d'une section"""
        activities_count = len(section.get('activities', []))
        resources_count = len(section.get('resources', []))
        return f"Activités: {activities_count}, Ressources: {resources_count}"
    
    def _get_activity_summary(self, activity: Dict) -> str:
        """Obtenir un résumé d'une activité"""
        files_count = len(activity.get('files', []))
        desc = activity.get('description', '')
        desc_preview = desc[:100] + '...' if len(desc) > 100 else desc
        return f"Type: {activity.get('type', 'unknown')}, Fichiers: {files_count}\nDescription: {desc_preview}"
    
    def _get_resource_summary(self, resource: Dict) -> str:
        """Obtenir un résumé d'une ressource"""
        files_count = len(resource.get('files', []))
        desc = resource.get('description', '')
        desc_preview = desc[:100] + '...' if len(desc) > 100 else desc
        return f"Fichiers: {files_count}\nDescription: {desc_preview}"