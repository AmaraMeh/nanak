import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

class ChangeDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_changes(self, old_content: Optional[Dict], new_content: Dict) -> List[Dict]:
        """
        Détecter les changements entre l'ancien et le nouveau contenu
        """
        changes = []
        
        if old_content is None:
            # Premier scan - tout est nouveau
            changes.append({
                'type': 'initial_scan',
                'message': 'Premier scan du cours détecté',
                'details': f"Nombre de sections: {len(new_content.get('sections', []))}"
            })
            return changes
        
        # Comparer les sections
        old_sections = old_content.get('sections', [])
        new_sections = new_content.get('sections', [])
        
        section_changes = self._compare_sections(old_sections, new_sections)
        changes.extend(section_changes)
        
        return changes
    
    def _compare_sections(self, old_sections: List[Dict], new_sections: List[Dict]) -> List[Dict]:
        """Comparer les sections entre l'ancien et le nouveau contenu"""
        changes = []
        
        # Créer des dictionnaires pour faciliter la comparaison
        old_sections_dict = {section['title']: section for section in old_sections}
        new_sections_dict = {section['title']: section for section in new_sections}
        
        # Sections ajoutées
        for title, section in new_sections_dict.items():
            if title not in old_sections_dict:
                changes.append({
                    'type': 'section_added',
                    'section_title': title,
                    'message': f'Nouvelle section ajoutée: {title}',
                    'details': self._get_section_summary(section)
                })
        
        # Sections supprimées
        for title, section in old_sections_dict.items():
            if title not in new_sections_dict:
                changes.append({
                    'type': 'section_removed',
                    'section_title': title,
                    'message': f'Section supprimée: {title}',
                    'details': self._get_section_summary(section)
                })
        
        # Sections modifiées
        for title, new_section in new_sections_dict.items():
            if title in old_sections_dict:
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
        for name, file in new_files_dict.items():
            if name not in old_files_dict:
                changes.append({
                    'type': 'file_added',
                    'file_name': name,
                    'parent_title': parent_title,
                    'message': f'Nouveau fichier ajouté: {name}',
                    'details': f'Dans: {parent_title}\nURL: {file.get("url", "N/A")}'
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