#!/usr/bin/env python3
"""
Module de monitoring et de statistiques pour le bot eLearning
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import os

class BotMonitor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.stats_file = "bot_stats.json"
        self.stats = self._load_stats()
    
    def _load_stats(self) -> Dict:
        """Charger les statistiques depuis le fichier"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement des statistiques: {str(e)}")
        
        # Statistiques par défaut
        return {
            'start_time': time.time(),
            'total_scans': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'total_notifications': 0,
            'courses_scanned': {},
            'last_scan_time': None,
            'uptime_hours': 0,
            'errors': []
        }
    
    def _save_stats(self):
        """Sauvegarder les statistiques dans le fichier"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des statistiques: {str(e)}")
    
    def record_scan_start(self):
        """Enregistrer le début d'un scan"""
        self.stats['total_scans'] += 1
        self.stats['last_scan_time'] = time.time()
        self._save_stats()
    
    def record_scan_result(self, course_id: str, course_name: str, success: bool, items_found: int = 0):
        """Enregistrer le résultat d'un scan pour un cours"""
        if course_id not in self.stats['courses_scanned']:
            self.stats['courses_scanned'][course_id] = {
                'name': course_name,
                'total_scans': 0,
                'successful_scans': 0,
                'failed_scans': 0,
                'total_items_found': 0,
                'last_scan_time': None,
                'last_items_count': 0
            }
        
        course_stats = self.stats['courses_scanned'][course_id]
        course_stats['total_scans'] += 1
        course_stats['last_scan_time'] = time.time()
        course_stats['last_items_count'] = items_found
        
        if success:
            self.stats['successful_scans'] += 1
            course_stats['successful_scans'] += 1
            course_stats['total_items_found'] += items_found
        else:
            self.stats['failed_scans'] += 1
            course_stats['failed_scans'] += 1
        
        self._save_stats()
    
    def record_notification(self, course_id: str, changes_count: int):
        """Enregistrer l'envoi d'une notification"""
        self.stats['total_notifications'] += 1
        self._save_stats()
    
    def record_error(self, error_type: str, error_message: str, course_id: str = None):
        """Enregistrer une erreur"""
        error_entry = {
            'timestamp': time.time(),
            'type': error_type,
            'message': error_message,
            'course_id': course_id
        }
        
        self.stats['errors'].append(error_entry)
        
        # Garder seulement les 100 dernières erreurs
        if len(self.stats['errors']) > 100:
            self.stats['errors'] = self.stats['errors'][-100:]
        
        self._save_stats()
    
    def get_uptime(self) -> str:
        """Obtenir le temps de fonctionnement"""
        uptime_seconds = time.time() - self.stats['start_time']
        uptime_hours = uptime_seconds / 3600
        
        if uptime_hours < 1:
            return f"{int(uptime_seconds / 60)} minutes"
        elif uptime_hours < 24:
            return f"{int(uptime_hours)} heures"
        else:
            days = int(uptime_hours / 24)
            hours = int(uptime_hours % 24)
            return f"{days} jours et {hours} heures"
    
    def get_success_rate(self) -> float:
        """Obtenir le taux de succès"""
        total_scans = self.stats['total_scans']
        if total_scans == 0:
            return 0.0
        return (self.stats['successful_scans'] / total_scans) * 100
    
    def get_course_stats(self, course_id: str) -> Dict:
        """Obtenir les statistiques pour un cours spécifique"""
        return self.stats['courses_scanned'].get(course_id, {})
    
    def get_recent_errors(self, hours: int = 24) -> List[Dict]:
        """Obtenir les erreurs récentes"""
        cutoff_time = time.time() - (hours * 3600)
        return [error for error in self.stats['errors'] if error['timestamp'] > cutoff_time]
    
    def get_summary_stats(self) -> Dict:
        """Obtenir un résumé des statistiques"""
        return {
            'uptime': self.get_uptime(),
            'total_scans': self.stats['total_scans'],
            'successful_scans': self.stats['successful_scans'],
            'failed_scans': self.stats['failed_scans'],
            'success_rate': f"{self.get_success_rate():.1f}%",
            'total_notifications': self.stats['total_notifications'],
            'courses_monitored': len(self.stats['courses_scanned']),
            'recent_errors': len(self.get_recent_errors(24))
        }
    
    def generate_report(self) -> str:
        """Générer un rapport détaillé"""
        stats = self.get_summary_stats()
        
        report = "📊 RAPPORT DE STATISTIQUES DU BOT\n"
        report += "=" * 50 + "\n\n"
        
        report += f"⏰ Temps de fonctionnement: {stats['uptime']}\n"
        report += f"📈 Total des scans: {stats['total_scans']}\n"
        report += f"✅ Scans réussis: {stats['successful_scans']}\n"
        report += f"❌ Scans échoués: {stats['failed_scans']}\n"
        report += f"📊 Taux de succès: {stats['success_rate']}\n"
        report += f"📱 Notifications envoyées: {stats['total_notifications']}\n"
        report += f"📚 Cours surveillés: {stats['courses_monitored']}\n"
        report += f"⚠️ Erreurs récentes (24h): {stats['recent_errors']}\n\n"
        
        # Statistiques par cours
        if self.stats['courses_scanned']:
            report += "📋 STATISTIQUES PAR COURS:\n"
            report += "-" * 30 + "\n"
            
            for course_id, course_stats in self.stats['courses_scanned'].items():
                success_rate = 0
                if course_stats['total_scans'] > 0:
                    success_rate = (course_stats['successful_scans'] / course_stats['total_scans']) * 100
                
                report += f"📚 {course_stats['name']}\n"
                report += f"   Scans: {course_stats['total_scans']} (Succès: {course_stats['successful_scans']})\n"
                report += f"   Taux: {success_rate:.1f}%\n"
                report += f"   Éléments trouvés: {course_stats['total_items_found']}\n\n"
        
        # Erreurs récentes
        recent_errors = self.get_recent_errors(24)
        if recent_errors:
            report += "⚠️ ERREURS RÉCENTES (24h):\n"
            report += "-" * 30 + "\n"
            
            for error in recent_errors[-10:]:  # 10 dernières erreurs
                error_time = datetime.fromtimestamp(error['timestamp']).strftime("%H:%M:%S")
                report += f"[{error_time}] {error['type']}: {error['message']}\n"
        
        report += f"\n📅 Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}"
        
        return report
    
    def reset_stats(self):
        """Réinitialiser les statistiques"""
        self.stats = {
            'start_time': time.time(),
            'total_scans': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'total_notifications': 0,
            'courses_scanned': {},
            'last_scan_time': None,
            'uptime_hours': 0,
            'errors': []
        }
        self._save_stats()
        self.logger.info("Statistiques réinitialisées")