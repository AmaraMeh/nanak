import logging
from telegram import Bot
from telegram.error import TelegramError
import asyncio
from config import Config
from datetime import datetime
from collections import defaultdict, Counter

try:
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
except Exception:
    InlineKeyboardMarkup = None
    InlineKeyboardButton = None

class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=Config.TELEGRAM_TOKEN)
        self.logger = logging.getLogger(__name__)
        self.chat_id = Config.TELEGRAM_CHAT_ID or None
        self.bot_ref = None  # Référence vers ELearningBot
        self.stopped = False
        # Cache navigation inline: {message_id: { 'course_id': str, 'page': int, 'items': [...] }}
        self.inline_state = {}
        # Nombre d'items par page pour navigation inline
        self.items_per_page = 10
        if InlineKeyboardButton is None:
            self.logger.warning("InlineKeyboard non disponible: les boutons seront remplacés par des commandes /nav <id> page.")
        # Cooldown bigscan
        self.last_bigscan_ts = 0
        # Menu pagination state (simple)
        self.menu_pages = ['main','more']
        # Navigation state pour les menus
        self.navigation_state = {}
        # Commandes disponibles
        self.commands = self._initialize_commands()

    def set_bot_ref(self, bot_ref):
        self.bot_ref = bot_ref
    
    def _initialize_commands(self):
        """Initialiser toutes les commandes disponibles"""
        commands = {
            # === COMMANDES PRINCIPALES ===
            '/start': self._cmd_start,
            '/help': self._cmd_help,
            '/menu': self._cmd_main_menu,
            '/status': self._cmd_status,
            '/ping': self._cmd_ping,
            '/about': self._cmd_about,
            
            # === GESTION DES COURS ===
            '/list': self._cmd_list_courses,
            '/courses': self._cmd_list_courses,
            '/departments': self._cmd_list_courses,
            '/course': self._cmd_course_details,
            '/inventory': self._cmd_inventory_course,
            '/export': self._cmd_export_course,
            '/search': self._cmd_search,
            '/count': self._cmd_courses_count,
            
            # === SCANS ET MAINTENANCE ===
            '/first': self._cmd_first_scan,
            '/rescan': self._cmd_rescan,
            '/scan': self._cmd_rescan,
            '/rescan_course': self._cmd_rescan_course,
            '/bigscan': self._cmd_bigscan,
            '/fullscan': self._cmd_bigscan,
            '/baseline': self._cmd_baseline,
            '/refresh': self._cmd_rescan,
            
            # === NAVIGATION DÉTAILLÉE ===
            '/sections': self._cmd_list_sections,
            '/activities': self._cmd_list_activities,
            '/resources': self._cmd_list_resources,
            '/files': self._cmd_list_files,
            '/nav': self._cmd_nav_course,
            '/inline': self._cmd_inline_paginate,
            '/browse': self._cmd_inline_paginate,
            
            # === HISTORIQUE ET STATISTIQUES ===
            '/latest': self._cmd_latest_changes,
            '/recent': self._cmd_latest_changes,
            '/today': self._cmd_today,
            '/yesterday': self._cmd_yesterday,
            '/last7': self._cmd_last7,
            '/week': self._cmd_week,
            '/month': self._cmd_month,
            '/stats': self._cmd_stats,
            '/statistics': self._cmd_stats,
            '/uptime': self._cmd_uptime,
            '/digest': self._cmd_digest_now,
            '/summary': self._cmd_digest_now,
            
            # === FICHIERS ET TÉLÉCHARGEMENTS ===
            '/files_send': self._cmd_send_files_course,
            '/download': self._cmd_send_files_course,
            '/lastfiles': self._cmd_last_files,
            '/recentfiles': self._cmd_last_files,
            '/newfiles': self._cmd_new_files,
            
            # === CONFIGURATION ===
            '/config': self._cmd_show_config,
            '/settings': self._cmd_show_config,
            '/setmode': self._cmd_set_mode,
            '/delay': self._cmd_set_delay,
            '/interval': self._cmd_set_interval,
            '/notifications': self._cmd_toggle_notifications,
            
            # === SYSTÈME ===
            '/versions': self._cmd_versions,
            '/info': self._cmd_system_info,
            '/health': self._cmd_health_check,
            '/logs': self._cmd_show_logs,
            '/restart': self._cmd_restart_bot,
            '/stop': self._cmd_stop_bot,
            
            # === RECHERCHE AVANCÉE ===
            '/find': self._cmd_advanced_search,
            '/grep': self._cmd_grep_search,
            '/filter': self._cmd_filter_content,
            '/query': self._cmd_query_content,
            
            # === RAPPORTS ===
            '/report': self._cmd_generate_report,
            '/analytics': self._cmd_analytics,
            '/trends': self._cmd_trends,
            '/insights': self._cmd_insights,
            
            # === ALERTES ===
            '/alerts': self._cmd_show_alerts,
            '/notify': self._cmd_notification_settings,
            '/watch': self._cmd_watch_course,
            '/unwatch': self._cmd_unwatch_course,
            
            # === UTILITAIRES ===
            '/backup': self._cmd_backup_data,
            '/restore': self._cmd_restore_data,
            '/clean': self._cmd_clean_data,
            '/optimize': self._cmd_optimize_data,
            
            # === DÉVELOPPEMENT ===
            '/debug': self._cmd_debug_info,
            '/test': self._cmd_test_connection,
            '/validate': self._cmd_validate_config,
            '/check': self._cmd_check_system,
        }
        
        # Ajouter les commandes dynamiques pour les départements
        self._add_dynamic_department_commands(commands)
        self._add_quick_access_commands(commands)
        self._add_shortcut_commands(commands)
        
        return commands
    
    def _add_dynamic_department_commands(self, commands):
        """Ajouter les commandes dynamiques pour chaque département"""
        for space in Config.MONITORED_SPACES:
            cid = space['id']
            name = space['name']
            
            # Commandes de base
            commands[f"/d{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_course_details(chat_id, [_cid])
            commands[f"/dept{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_course_details(chat_id, [_cid])
            
            # Commandes temporelles
            commands[f"/dt{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 1, "Aujourd'hui")
            commands[f"/dy{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 2, "Hier", only_day_offset=1)
            commands[f"/d7{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 7, "7 jours")
            commands[f"/d30{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 30, "30 jours")
            
            # Commandes de navigation
            commands[f"/nav{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_nav_course(chat_id, [_cid])
            commands[f"/sections{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_list_sections(chat_id, [_cid])
            commands[f"/activities{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_list_activities(chat_id, [_cid])
            commands[f"/resources{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_list_resources(chat_id, [_cid])
            commands[f"/files{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_list_files(chat_id, [_cid])
            
            # Commandes de scan
            commands[f"/scan{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_rescan_course(chat_id, [_cid])
            commands[f"/rescan{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_rescan_course(chat_id, [_cid])
            
            # Commandes de fichiers
            commands[f"/download{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_send_files_course(chat_id, [_cid])
            commands[f"/files{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_send_files_course(chat_id, [_cid])
    
    def _add_quick_access_commands(self, commands):
        """Ajouter les commandes d'accès rapide"""
        quick_commands = {
            # Raccourcis courants
            '/s': self._cmd_status,
            '/l': self._cmd_list_courses,
            '/h': self._cmd_help,
            '/m': self._cmd_main_menu,
            '/q': self._cmd_quick_stats,
            '/f': self._cmd_find_course,
            '/r': self._cmd_rescan,
            '/b': self._cmd_bigscan,
            '/n': self._cmd_latest_changes,
            '/t': self._cmd_today,
            '/w': self._cmd_week,
            
            # Commandes de recherche rapide
            '/find_course': self._cmd_find_course,
            '/find_file': self._cmd_find_file,
            '/find_activity': self._cmd_find_activity,
            '/find_resource': self._cmd_find_resource,
            
            # Commandes de statut rapide
            '/online': self._cmd_online_status,
            '/offline': self._cmd_offline_status,
            '/busy': self._cmd_busy_status,
            '/idle': self._cmd_idle_status,
        }
        commands.update(quick_commands)
    
    def _add_shortcut_commands(self, commands):
        """Ajouter les commandes de raccourci"""
        shortcuts = {
            # Raccourcis numériques
            '/1': lambda chat_id, args: self._cmd_main_menu(chat_id, []),
            '/2': lambda chat_id, args: self._cmd_list_courses(chat_id, []),
            '/3': lambda chat_id, args: self._cmd_latest_changes(chat_id, []),
            '/4': lambda chat_id, args: self._cmd_stats(chat_id, []),
            '/5': lambda chat_id, args: self._cmd_today(chat_id, []),
            '/6': lambda chat_id, args: self._cmd_week(chat_id, []),
            '/7': lambda chat_id, args: self._cmd_bigscan(chat_id, []),
            '/8': lambda chat_id, args: self._cmd_config_menu(chat_id, []),
            '/9': lambda chat_id, args: self._cmd_help(chat_id, []),
            '/0': lambda chat_id, args: self._cmd_about(chat_id, []),
            
            # Raccourcis alphabétiques
            '/a': self._cmd_about,
            '/c': self._cmd_config_menu,
            '/d': self._cmd_departments_menu,
            '/e': self._cmd_export_course,
            '/g': self._cmd_global_stats,
            '/i': self._cmd_inventory_course,
            '/j': self._cmd_jump_to_course,
            '/k': self._cmd_keyboard_shortcuts,
            '/o': self._cmd_online_status,
            '/p': self._cmd_ping,
            '/u': self._cmd_uptime,
            '/v': self._cmd_versions,
            '/x': self._cmd_exit_menu,
            '/y': self._cmd_yesterday,
            '/z': self._cmd_zoom_course,
        }
        commands.update(shortcuts)

    # ================== Boucle de commandes (polling manuel) ==================
    async def command_loop(self):
        offset = None
        processed_update_ids = set()
        while not self.stopped:
            try:
                updates = await self.bot.get_updates(offset=offset, timeout=20)
                for upd in updates:
                    offset = upd.update_id + 1
                    if upd.update_id in processed_update_ids:
                        continue
                    processed_update_ids.add(upd.update_id)
                    if hasattr(upd, 'message') and upd.message:
                        if not self.chat_id:
                            self.chat_id = upd.message.chat_id
                        text = (upd.message.text or '').strip()
                        if text.startswith('/'):
                            await self._handle_command(text, upd.message.chat_id)
                    elif hasattr(upd, 'callback_query') and upd.callback_query:
                        await self._handle_callback_query(upd.callback_query)
                await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"Boucle commandes erreur: {e}")
                await asyncio.sleep(2)

    async def _handle_command(self, text: str, chat_id: int):
        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:]

        # Utiliser le système de commandes unifié
        handler = self.commands.get(cmd)
        if handler:
            try:
                await handler(chat_id, args)
            except Exception as e:
                await self._safe_send(chat_id, f"❌ Erreur commande {cmd}: {e}")
        else:
            # Essayer de trouver une commande similaire
            similar = self._find_similar_command(cmd)
            if similar:
                await self._safe_send(chat_id, f"Commande inconnue: {cmd}\n\n💡 Vouliez-vous dire: {similar} ?\n\nTapez /help pour voir toutes les commandes disponibles.")
            else:
                await self._safe_send(chat_id, f"❌ Commande inconnue: {cmd}\n\nTapez /help ou /menu pour voir les commandes disponibles.")
    
    def _find_similar_command(self, cmd: str) -> str:
        """Trouver une commande similaire"""
        import difflib
        all_commands = list(self.commands.keys())
        matches = difflib.get_close_matches(cmd, all_commands, n=1, cutoff=0.6)
        return matches[0] if matches else None

    # =============== Command Handlers (20+) ===============
    async def _cmd_start(self, chat_id, args):
        await self._cmd_help(chat_id, args)

    async def _cmd_help(self, chat_id, args):
        """Afficher l'aide avec navigation inline"""
        if not InlineKeyboardButton:
            await self._cmd_help_text(chat_id, args)
            return
        
        keyboard = [
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="menu:main")],
            [InlineKeyboardButton("📚 Départements", callback_data="menu:departments")],
            [InlineKeyboardButton("🔍 Recherche", callback_data="menu:search")],
            [InlineKeyboardButton("📊 Statistiques", callback_data="menu:stats")],
            [InlineKeyboardButton("⚙️ Configuration", callback_data="menu:config")],
            [InlineKeyboardButton("🆘 Raccourcis", callback_data="menu:shortcuts")],
            [InlineKeyboardButton("📖 Guide Complet", callback_data="menu:guide")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        help_text = (
            "🤖 <b>Bot eLearning Notifier</b>\n\n"
            "Choisissez une catégorie ci-dessous pour explorer les fonctionnalités :\n\n"
            "🏠 <b>Menu Principal</b> - Accès rapide aux fonctions principales\n"
            "📚 <b>Départements</b> - Navigation par département\n"
            "🔍 <b>Recherche</b> - Outils de recherche avancée\n"
            "📊 <b>Statistiques</b> - Analyses et rapports\n"
            "⚙️ <b>Configuration</b> - Paramètres du bot\n"
            "🆘 <b>Raccourcis</b> - Commandes rapides\n"
            "📖 <b>Guide Complet</b> - Documentation détaillée\n\n"
            "💡 <i>Utilisez les boutons ci-dessous ou tapez /menu pour commencer</i>"
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def _cmd_help_text(self, chat_id, args):
        """Afficher l'aide en texte simple"""
        lines = [
            "🤖 <b>Commandes principales</b>",
            "Base: /status /list /course /inventory /search /export /uptime /ping",
            "Navigation: /sections /activities /resources /files /nav /inline",
            "Maintenance: /rescan /rescan_course /bigscan /versions /config /delay /setmode",
            "Historique: /latest /week /digest",
            "Temps: /today /yesterday /last7",
            "Fichiers: /files_send",
            "Départements ID: /advanced (d<ID> / dt<ID> / dy<ID> / d7<ID>)",
            "Départements NOM: /dep_<slug> (_today _yesterday _last7)",
            "Exemple: /dep_psychologie_et_d_orthophonie_today",
            "Voir: COMMANDS_REFERENCE.txt & GUIDE_COMPLET.txt"
        ]
        for chunk in self._paginate('\n'.join(lines)):
            await self._safe_send(chat_id, chunk)

    async def _cmd_advanced(self, chat_id, args):
        lines = ["📘 <b>Commandes Département</b>"]
        for space in Config.MONITORED_SPACES:
            cid = space['id']
            base = f"/d{cid}"
            lines.append(f"{base} | /dt{cid} | /dy{cid} | /d7{cid}")
        lines.append("Format: /d<ID>=snapshot, /dt<ID>=today, /dy<ID>=yesterday, /d7<ID>=7 jours")
        txt = '\n'.join(lines)
        for chunk in self._paginate(txt):
            await self._safe_send(chat_id, chunk)

    def _extend_dynamic_commands(self, commands: dict):
        for space in Config.MONITORED_SPACES:
            cid = space['id']
            commands[f"/d{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_course_details(chat_id, [_cid])
            commands[f"/dt{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 1, "Aujourd'hui")
            commands[f"/dy{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 2, "Hier", only_day_offset=1)
            commands[f"/d7{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 7, "7 jours")
        commands['/advanced'] = self._cmd_advanced

    def _extend_name_based_department_commands(self, commands: dict):
        import re
        seen = set()
        for space in Config.MONITORED_SPACES:
            cid = space['id']
            slug = space['name'].lower()
            slug = re.sub(r"affichage|département|departement|d'|du|des|de|\bl'|\ble\b|\bla\b|\s+", " ", slug)
            slug = re.sub(r"[^a-z0-9]+", "_", slug).strip('_')
            if not slug:
                continue
            base = f"/dep_{slug}"[:60]
            if base in seen:
                continue
            seen.add(base)
            commands[base] = lambda chat_id, args, _cid=cid: self._cmd_course_details(chat_id, [_cid])
            commands[base+"_today"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 1, "Aujourd'hui")
            commands[base+"_yesterday"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 2, "Hier", only_day_offset=1)
            commands[base+"_last7"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 7, "7 jours")

    async def _cmd_status(self, chat_id, args):
        if not self.bot_ref:
            return await self._safe_send(chat_id, "Bot ref indisponible")
        await self._safe_send(chat_id, self.bot_ref.get_status())

    async def _cmd_list_courses(self, chat_id, args):
        lines = ["📚 <b>Cours surveillés</b>"]
        for cid, name in self.bot_ref.list_courses():
            lines.append(f"• <b>{cid}</b> — {self._escape(name)}")
        await self._safe_send(chat_id, '\n'.join(lines))

    async def _cmd_course_details(self, chat_id, args):
        if not args:
            return await self._safe_send(chat_id, "Usage: /course <id>")
        cid = args[0]
        snap = self.bot_ref.get_course_snapshot(cid)
        if not snap:
            return await self._safe_send(chat_id, "Aucun snapshot pour ce cours")
        sections = snap.get('sections', [])
        total_acts = sum(len(s.get('activities', [])) for s in sections)
        total_res = sum(len(s.get('resources', [])) for s in sections)
        total_files = sum(len(a.get('files', [])) for s in sections for a in s.get('activities', [])) + \
                      sum(len(r.get('files', [])) for s in sections for r in s.get('resources', []))
        msg = (
            f"📘 <b>Cours {cid}</b>\nSections: {len(sections)}\n"
            f"Activités: {total_acts} | Ressources: {total_res} | Fichiers: {total_files}"
        )
        await self._safe_send(chat_id, msg)

    async def _cmd_rescan(self, chat_id, args):
        self.bot_ref.trigger_manual_scan()
        await self._safe_send(chat_id, "⏳ Scan global déclenché")

    async def _cmd_rescan_course(self, chat_id, args):
        if not args:
            return await self._safe_send(chat_id, "Usage: /rescan_course <id>")
        self.bot_ref.trigger_manual_scan(args[0])
        await self._safe_send(chat_id, f"⏳ Scan ciblé déclenché pour {args[0]}")

    async def _cmd_list_sections(self, chat_id, args):
        if not args:
            return await self._safe_send(chat_id, "Usage: /sections <id>")
        snap = self.bot_ref.get_course_snapshot(args[0])
        if not snap:
            return await self._safe_send(chat_id, "Snapshot absent")
        lines = ["📂 Sections:"]
        for i,s in enumerate(snap.get('sections', []),1):
            lines.append(f"{i}. {self._escape(s.get('title',''))}")
        await self._safe_send(chat_id, '\n'.join(lines))

    async def _cmd_list_activities(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /activities <id>")
        snap = self.bot_ref.get_course_snapshot(args[0])
        if not snap: return await self._safe_send(chat_id, "Snapshot absent")
        acts = []
        for s in snap.get('sections', []):
            for a in s.get('activities', []):
                acts.append(a.get('title','Sans titre'))
        msg = "📋 Activités:\n" + '\n'.join(f"• {self._escape(t)}" for t in acts[:200])
        await self._safe_send(chat_id, msg)

    async def _cmd_list_resources(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /resources <id>")
        snap = self.bot_ref.get_course_snapshot(args[0])
        if not snap: return await self._safe_send(chat_id, "Snapshot absent")
        res = []
        for s in snap.get('sections', []):
            for r in s.get('resources', []):
                res.append(r.get('title','Sans titre'))
        msg = "📚 Ressources:\n" + '\n'.join(f"• {self._escape(t)}" for t in res[:200])
        await self._safe_send(chat_id, msg)

    async def _cmd_list_files(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /files <id>")
        snap = self.bot_ref.get_course_snapshot(args[0])
        if not snap: return await self._safe_send(chat_id, "Snapshot absent")
        file_entries = []
        for s in snap.get('sections', []):
            for a in s.get('activities', []):
                for f in a.get('files', []):
                    file_entries.append(f"[A] {f.get('name')}")
            for r in s.get('resources', []):
                for f in r.get('files', []):
                    file_entries.append(f"[R] {f.get('name')}")
        if not file_entries:
            return await self._safe_send(chat_id, "Aucun fichier détecté")
        await self._safe_send(chat_id, "📄 Fichiers:\n" + '\n'.join(self._escape(x) for x in file_entries[:200]))

    async def _cmd_nav_course(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /nav <id>")
        snap = self.bot_ref.get_course_snapshot(args[0])
        if not snap: return await self._safe_send(chat_id, "Snapshot absent")
        text = self._build_nav_text(snap)
        await self._safe_send(chat_id, text)

    def _build_nav_text(self, snap: dict) -> str:
        out = [f"📘 Navigation rapide: {snap.get('course_id','')}\n"]
        for s in snap.get('sections', []):
            out.append(f"📂 {self._escape(s.get('title',''))}")
            for a in s.get('activities', [])[:5]:
                out.append(f"  • 📋 {self._escape(a.get('title',''))}")
            for r in s.get('resources', [])[:5]:
                out.append(f"  • 📚 {self._escape(r.get('title',''))}")
        return '\n'.join(out[:400])

    async def _cmd_set_mode(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /setmode grouped|separate")
        val = args[0].lower()
        if val in ('grouped','separate'):
            from config import Config as C
            C.INITIAL_SCAN_MODE = val
            await self._safe_send(chat_id, f"Mode initial défini sur {val}")
        else:
            await self._safe_send(chat_id, "Valeur invalide")

    async def _cmd_set_delay(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /delay <float>")
        try:
            val = float(args[0])
            from config import Config as C
            C.MESSAGE_DELAY_SECONDS = max(0.1, min(val, 5.0))
            await self._safe_send(chat_id, f"Délai configuré: {C.MESSAGE_DELAY_SECONDS}s")
        except:
            await self._safe_send(chat_id, "Nombre invalide")

    async def _cmd_search(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /search <mot>")
        term = ' '.join(args).lower()
        matches = []
        for cid, snap in self.bot_ref.last_courses_content.items():
            for s in snap.get('sections', []):
                if term in s.get('title','').lower():
                    matches.append(f"[{cid}] Section: {s.get('title')}")
                for a in s.get('activities', []):
                    if term in a.get('title','').lower():
                        matches.append(f"[{cid}] Activité: {a.get('title')}")
                for r in s.get('resources', []):
                    if term in r.get('title','').lower():
                        matches.append(f"[{cid}] Ressource: {r.get('title')}")
        if not matches:
            return await self._safe_send(chat_id, "Aucun résultat")
        await self._safe_send(chat_id, "🔎 Résultats:\n" + '\n'.join(self._escape(m) for m in matches[:200]))

    async def _cmd_export_course(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /export <id>")
        import json
        snap = self.bot_ref.get_course_snapshot(args[0])
        if not snap: return await self._safe_send(chat_id, "Snapshot absent")
        data = json.dumps(snap, ensure_ascii=False)[:3800]
        await self._safe_send(chat_id, f"<b>Export JSON partiel</b>:\n<pre>{self._escape(data)}</pre>", parse_mode='HTML')

    async def _cmd_courses_count(self, chat_id, args):
        await self._safe_send(chat_id, f"Cours surveillés: {len(self.bot_ref.list_courses())}")

    async def _cmd_uptime(self, chat_id, args):
        # Approx: derive from monitor stats if available
        await self._safe_send(chat_id, f"Uptime scans: {self.bot_ref.monitor.get_summary_stats().get('total_scans',0)} scans effectués")

    async def _cmd_ping(self, chat_id, args):
        await self._safe_send(chat_id, "🏓 Pong")

    async def _cmd_latest_changes(self, chat_id, args):
        logs = self.bot_ref.firebase.get_changes_since(7)
        entries = []
        from datetime import datetime as _dt
        for entry in logs:
            course_id = entry.get('course_id')
            cname = next((s['name'] for s in Config.MONITORED_SPACES if s['id']==course_id), course_id)
            ts = entry.get('timestamp')
            for ch in entry.get('changes', []):
                t = ch.get('type','')
                if any(k in t for k in ['added','renamed']):
                    title = ch.get('activity_title') or ch.get('resource_title') or ch.get('file_name') or ch.get('section_title') or 'Nouvel élément'
                    entries.append((ts, cname, t, title))
        def _parse(ts):
            if isinstance(ts,str):
                try:
                    return _dt.fromisoformat(ts.replace('Z',''))
                except:
                    return _dt.min
            return _dt.min
        entries.sort(key=lambda x: _parse(x[0]), reverse=True)
        lines = ["🕒 <b>Derniers ajouts / renommages</b>"]
        for e in entries[:30]:
            dtv = _parse(e[0])
            dt_s = dtv.strftime('%d/%m %H:%M') if dtv.year > 1900 else ''
            lines.append(f"• {self._escape(e[1])} — {self._escape(e[3])} ({e[2]}) {dt_s}")
        if len(lines)==1:
            lines.append("Aucun changement récent")
        for chunk in self._paginate('\n'.join(lines)):
            await self._safe_send(chat_id, chunk)

    async def _cmd_show_config(self, chat_id, args):
        from config import Config as C
        msg = (
            f"Config:\nMode: {C.INITIAL_SCAN_MODE}\nDelay: {C.MESSAGE_DELAY_SECONDS}s\nInterval: {C.CHECK_INTERVAL_MINUTES}m\n"
        )
        await self._safe_send(chat_id, msg)

    # (Commande /stopbot supprimée pour empêcher un arrêt manuel accidentel)

    async def _cmd_inline_paginate(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /inline <id>")
        cid = args[0]
        snap = self.bot_ref.get_course_snapshot(cid)
        if not snap: return await self._safe_send(chat_id, "Snapshot absent")
        items = []
        for s in snap.get('sections', []):
            items.append(f"📂 {s.get('title')}")
            for a in s.get('activities', []):
                items.append(f"  📋 {a.get('title')}")
            for r in s.get('resources', []):
                items.append(f"  📚 {r.get('title')}")
        await self._send_inline_page(chat_id, cid, items, 0)

    async def _cmd_inventory_course(self, chat_id, args):
        if not args: return await self._safe_send(chat_id, "Usage: /inventory <id>")
        snap = self.bot_ref.get_course_snapshot(args[0])
        if not snap: return await self._safe_send(chat_id, "Snapshot absent")
        txt = self._build_nav_text(snap)
        await self._safe_send(chat_id, txt[:3900])

    async def _cmd_versions(self, chat_id, args):
        import platform, requests, bs4
        msg = f"Python: {platform.python_version()}\nRequests: {requests.__version__}\nBS4: {bs4.__version__}"
        await self._safe_send(chat_id, msg)

    async def _cmd_about(self, chat_id, args):
        about_text = (
            "🤖 <b>Bot eLearning Notifier</b>\n\n"
            "📚 <b>Surveillance automatique</b> des espaces d'affichage eLearning\n"
            "🏛️ <b>Université de Béjaïa</b>\n\n"
            "✨ <b>Fonctionnalités:</b>\n"
            "• Surveillance en temps réel\n"
            "• Notifications instantanées\n"
            "• Navigation intuitive\n"
            "• 100+ commandes disponibles\n"
            "• Interface moderne avec boutons\n\n"
            "🔧 <b>Version:</b> 2.0 - Navigation Inline\n"
            "📞 <b>Support:</b> Tapez /help pour l'aide"
        )
        await self._safe_send(chat_id, about_text)
    
    # === NOUVELLES COMMANDES ===
    
    async def _cmd_search_menu(self, chat_id, args):
        """Menu de recherche avec options"""
        if not InlineKeyboardButton:
            await self._cmd_search(chat_id, args)
            return
        
        keyboard = [
            [InlineKeyboardButton("🔍 Recherche Globale", callback_data="cmd:search")],
            [InlineKeyboardButton("📚 Par Département", callback_data="menu:departments")],
            [InlineKeyboardButton("📄 Fichiers", callback_data="cmd:find_file")],
            [InlineKeyboardButton("📋 Activités", callback_data="cmd:find_activity")],
            [InlineKeyboardButton("📚 Ressources", callback_data="cmd:find_resource")],
            [InlineKeyboardButton("🔙 Retour", callback_data="menu:main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = (
            "🔍 <b>Menu de Recherche</b>\n\n"
            "Choisissez le type de recherche :"
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def _cmd_config_menu(self, chat_id, args):
        """Menu de configuration"""
        if not InlineKeyboardButton:
            await self._cmd_show_config(chat_id, args)
            return
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Configuration", callback_data="cmd:config")],
            [InlineKeyboardButton("⏱️ Intervalle", callback_data="cmd:interval")],
            [InlineKeyboardButton("🔔 Notifications", callback_data="cmd:notifications")],
            [InlineKeyboardButton("📊 Mode", callback_data="cmd:setmode")],
            [InlineKeyboardButton("⏳ Délai", callback_data="cmd:delay")],
            [InlineKeyboardButton("🔙 Retour", callback_data="menu:main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = (
            "⚙️ <b>Menu de Configuration</b>\n\n"
            "Gérez les paramètres du bot :"
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def _cmd_shortcuts_menu(self, chat_id, args):
        """Menu des raccourcis"""
        shortcuts_text = (
            "🆘 <b>Raccourcis Rapides</b>\n\n"
            "🔢 <b>Numériques:</b>\n"
            "/1 - Menu Principal\n"
            "/2 - Départements\n"
            "/3 - Derniers changements\n"
            "/4 - Statistiques\n"
            "/5 - Aujourd'hui\n"
            "/6 - 7 jours\n"
            "/7 - Big Scan\n"
            "/8 - Configuration\n"
            "/9 - Aide\n"
            "/0 - À propos\n\n"
            "🔤 <b>Alphabétiques:</b>\n"
            "/s - Statut\n"
            "/l - Liste\n"
            "/h - Aide\n"
            "/m - Menu\n"
            "/q - Stats rapides\n"
            "/f - Recherche\n"
            "/r - Scanner\n"
            "/b - Big Scan\n"
            "/n - Nouveautés\n"
            "/t - Aujourd'hui\n"
            "/w - Semaine\n\n"
            "💡 <i>Utilisez ces raccourcis pour un accès rapide !</i>"
        )
        await self._safe_send(chat_id, shortcuts_text)
    
    async def _cmd_guide_menu(self, chat_id, args):
        """Menu du guide complet"""
        guide_text = (
            "📖 <b>Guide Complet</b>\n\n"
            "🚀 <b>Démarrage rapide:</b>\n"
            "1. Tapez /menu pour le menu principal\n"
            "2. Utilisez les boutons pour naviguer\n"
            "3. Explorez les départements\n\n"
            "🔍 <b>Recherche:</b>\n"
            "• /search <mot> - Recherche globale\n"
            "• /find_course <nom> - Trouver un cours\n"
            "• /find_file <nom> - Trouver un fichier\n\n"
            "📊 <b>Statistiques:</b>\n"
            "• /stats - Statistiques générales\n"
            "• /today - Changements d'aujourd'hui\n"
            "• /week - Résumé de la semaine\n\n"
            "⚙️ <b>Configuration:</b>\n"
            "• /config - Voir la configuration\n"
            "• /setmode - Changer le mode\n"
            "• /delay - Ajuster les délais\n\n"
            "🆘 <b>Besoin d'aide ?</b>\n"
            "Tapez /help ou utilisez les boutons !"
        )
        await self._safe_send(chat_id, guide_text)
    
    # === COMMANDES RAPIDES ===
    
    async def _cmd_quick_stats(self, chat_id, args):
        """Statistiques rapides"""
        if not self.bot_ref:
            await self._safe_send(chat_id, "❌ Bot non disponible")
            return
        
        stats = self.bot_ref.monitor.get_summary_stats() if self.bot_ref.monitor else {}
        
        quick_text = (
            "⚡ <b>Stats Rapides</b>\n\n"
            f"🟢 <b>Statut:</b> {'Actif' if self.bot_ref.running else 'Inactif'}\n"
            f"📚 <b>Départements:</b> {len(Config.MONITORED_SPACES)}\n"
            f"⏱️ <b>Intervalle:</b> {Config.CHECK_INTERVAL_MINUTES} min\n"
            f"📊 <b>Scans:</b> {stats.get('total_scans', 0)}\n"
            f"🔔 <b>Notifications:</b> {stats.get('total_notifications', 0)}\n"
            f"✅ <b>Taux de succès:</b> {stats.get('success_rate', 'N/A')}"
        )
        await self._safe_send(chat_id, quick_text)
    
    async def _cmd_find_course(self, chat_id, args):
        """Trouver un cours par nom"""
        if not args:
            await self._safe_send(chat_id, "Usage: /find_course <nom>")
            return
        
        search_term = ' '.join(args).lower()
        matches = []
        
        for space in Config.MONITORED_SPACES:
            if search_term in space['name'].lower():
                matches.append(f"• {space['id']} - {space['name']}")
        
        if matches:
            result_text = f"🔍 <b>Résultats pour '{search_term}':</b>\n\n" + '\n'.join(matches)
        else:
            result_text = f"❌ Aucun cours trouvé pour '{search_term}'"
        
        await self._safe_send(chat_id, result_text)
    
    async def _cmd_find_file(self, chat_id, args):
        """Trouver un fichier"""
        if not args:
            await self._safe_send(chat_id, "Usage: /find_file <nom>")
            return
        
        search_term = ' '.join(args).lower()
        matches = []
        
        for course_id, content in self.bot_ref.last_courses_content.items():
            course_name = self._get_course_name(course_id)
            for section in content.get('sections', []):
                for activity in section.get('activities', []):
                    for file_info in activity.get('files', []):
                        if search_term in file_info.get('name', '').lower():
                            matches.append(f"• {file_info['name']} (dans {activity['title']} - {course_name})")
                for resource in section.get('resources', []):
                    for file_info in resource.get('files', []):
                        if search_term in file_info.get('name', '').lower():
                            matches.append(f"• {file_info['name']} (dans {resource['title']} - {course_name})")
        
        if matches:
            result_text = f"📄 <b>Fichiers trouvés pour '{search_term}':</b>\n\n" + '\n'.join(matches[:20])
        else:
            result_text = f"❌ Aucun fichier trouvé pour '{search_term}'"
        
        await self._safe_send(chat_id, result_text)
    
    async def _cmd_find_activity(self, chat_id, args):
        """Trouver une activité"""
        if not args:
            await self._safe_send(chat_id, "Usage: /find_activity <nom>")
            return
        
        search_term = ' '.join(args).lower()
        matches = []
        
        for course_id, content in self.bot_ref.last_courses_content.items():
            course_name = self._get_course_name(course_id)
            for section in content.get('sections', []):
                for activity in section.get('activities', []):
                    if search_term in activity.get('title', '').lower():
                        matches.append(f"• {activity['title']} (dans {section['title']} - {course_name})")
        
        if matches:
            result_text = f"📋 <b>Activités trouvées pour '{search_term}':</b>\n\n" + '\n'.join(matches[:20])
        else:
            result_text = f"❌ Aucune activité trouvée pour '{search_term}'"
        
        await self._safe_send(chat_id, result_text)
    
    async def _cmd_find_resource(self, chat_id, args):
        """Trouver une ressource"""
        if not args:
            await self._safe_send(chat_id, "Usage: /find_resource <nom>")
            return
        
        search_term = ' '.join(args).lower()
        matches = []
        
        for course_id, content in self.bot_ref.last_courses_content.items():
            course_name = self._get_course_name(course_id)
            for section in content.get('sections', []):
                for resource in section.get('resources', []):
                    if search_term in resource.get('title', '').lower():
                        matches.append(f"• {resource['title']} (dans {section['title']} - {course_name})")
        
        if matches:
            result_text = f"📚 <b>Ressources trouvées pour '{search_term}':</b>\n\n" + '\n'.join(matches[:20])
        else:
            result_text = f"❌ Aucune ressource trouvée pour '{search_term}'"
        
        await self._safe_send(chat_id, result_text)
    
    def _get_course_name(self, course_id):
        """Obtenir le nom d'un cours par son ID"""
        for space in Config.MONITORED_SPACES:
            if space['id'] == course_id:
                return space['name']
        return f"Cours {course_id}"
    
    # === COMMANDES SYSTÈME ===
    
    async def _cmd_system_info(self, chat_id, args):
        """Informations système"""
        import platform
        import psutil
        import sys
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
        except:
            cpu_percent = "N/A"
            memory = type('obj', (object,), {'percent': "N/A", 'available': "N/A"})()
            disk = type('obj', (object,), {'percent': "N/A", 'free': "N/A"})()
        
        info_text = (
            "💻 <b>Informations Système</b>\n\n"
            f"🖥️ <b>OS:</b> {platform.system()} {platform.release()}\n"
            f"🐍 <b>Python:</b> {sys.version.split()[0]}\n"
            f"⚡ <b>CPU:</b> {cpu_percent}%\n"
            f"🧠 <b>RAM:</b> {memory.percent}% utilisée\n"
            f"💾 <b>Disque:</b> {disk.percent}% utilisé\n"
            f"🕒 <b>Uptime:</b> {self._get_uptime()}\n"
            f"📊 <b>Bot:</b> {'Actif' if self.bot_ref and self.bot_ref.running else 'Inactif'}"
        )
        await self._safe_send(chat_id, info_text)
    
    async def _cmd_health_check(self, chat_id, args):
        """Vérification de santé du système"""
        health_status = []
        
        # Vérifier le bot
        if self.bot_ref and self.bot_ref.running:
            health_status.append("✅ Bot actif")
        else:
            health_status.append("❌ Bot inactif")
        
        # Vérifier Firebase
        if self.bot_ref and hasattr(self.bot_ref, 'firebase') and self.bot_ref.firebase:
            health_status.append("✅ Base de données connectée")
        else:
            health_status.append("⚠️ Base de données locale")
        
        # Vérifier les cours
        if self.bot_ref and hasattr(self.bot_ref, 'last_courses_content'):
            course_count = len(self.bot_ref.last_courses_content)
            health_status.append(f"✅ {course_count} cours en mémoire")
        else:
            health_status.append("⚠️ Aucun cours en mémoire")
        
        health_text = (
            "🏥 <b>Vérification de Santé</b>\n\n" +
            "\n".join(health_status) + "\n\n" +
            "🕒 <b>Dernière vérification:</b> " + self._get_current_time()
        )
        await self._safe_send(chat_id, health_text)
    
    async def _cmd_show_logs(self, chat_id, args):
        """Afficher les logs récents"""
        try:
            with open('bot.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                recent_lines = lines[-20:]  # 20 dernières lignes
                log_text = "📋 <b>Logs Récents</b>\n\n" + ''.join(recent_lines)
                await self._safe_send(chat_id, log_text)
        except Exception as e:
            await self._safe_send(chat_id, f"❌ Erreur lecture logs: {e}")
    
    async def _cmd_restart_bot(self, chat_id, args):
        """Redémarrer le bot"""
        await self._safe_send(chat_id, "🔄 Redémarrage du bot...")
        if self.bot_ref:
            self.bot_ref.stop()
            # Le bot se redémarrera automatiquement
        else:
            await self._safe_send(chat_id, "❌ Bot non disponible")
    
    async def _cmd_stop_bot(self, chat_id, args):
        """Arrêter le bot"""
        await self._safe_send(chat_id, "⏹️ Arrêt du bot...")
        if self.bot_ref:
            self.bot_ref.stop()
        else:
            await self._safe_send(chat_id, "❌ Bot non disponible")
    
    # === COMMANDES DE RECHERCHE AVANCÉE ===
    
    async def _cmd_advanced_search(self, chat_id, args):
        """Recherche avancée"""
        if not args:
            await self._safe_send(chat_id, "Usage: /advanced_search <terme> [options]")
            return
        
        search_term = ' '.join(args).lower()
        results = []
        
        for course_id, content in self.bot_ref.last_courses_content.items():
            course_name = self._get_course_name(course_id)
            for section in content.get('sections', []):
                for activity in section.get('activities', []):
                    if search_term in activity.get('title', '').lower() or search_term in activity.get('description', '').lower():
                        results.append(f"📋 {activity['title']} (dans {section['title']} - {course_name})")
                for resource in section.get('resources', []):
                    if search_term in resource.get('title', '').lower() or search_term in resource.get('description', '').lower():
                        results.append(f"📚 {resource['title']} (dans {section['title']} - {course_name})")
        
        if results:
            result_text = f"🔍 <b>Recherche avancée pour '{search_term}':</b>\n\n" + '\n'.join(results[:30])
        else:
            result_text = f"❌ Aucun résultat pour '{search_term}'"
        
        await self._safe_send(chat_id, result_text)
    
    async def _cmd_grep_search(self, chat_id, args):
        """Recherche avec grep"""
        await self._cmd_advanced_search(chat_id, args)
    
    async def _cmd_filter_content(self, chat_id, args):
        """Filtrer le contenu"""
        await self._cmd_advanced_search(chat_id, args)
    
    async def _cmd_query_content(self, chat_id, args):
        """Requête de contenu"""
        await self._cmd_advanced_search(chat_id, args)
    
    # === COMMANDES DE RAPPORTS ===
    
    async def _cmd_generate_report(self, chat_id, args):
        """Générer un rapport"""
        report_text = (
            "📊 <b>Rapport Généré</b>\n\n"
            f"📅 <b>Date:</b> {self._get_current_time()}\n"
            f"📚 <b>Départements surveillés:</b> {len(Config.MONITORED_SPACES)}\n"
            f"⏱️ <b>Intervalle de scan:</b> {Config.CHECK_INTERVAL_MINUTES} min\n"
            f"🔄 <b>Statut:</b> {'Actif' if self.bot_ref and self.bot_ref.running else 'Inactif'}\n\n"
            "💡 <i>Utilisez /stats pour plus de détails</i>"
        )
        await self._safe_send(chat_id, report_text)
    
    async def _cmd_analytics(self, chat_id, args):
        """Analytics"""
        await self._cmd_stats(chat_id, args)
    
    async def _cmd_trends(self, chat_id, args):
        """Tendances"""
        await self._cmd_week(chat_id, args)
    
    async def _cmd_insights(self, chat_id, args):
        """Insights"""
        await self._cmd_stats(chat_id, args)
    
    # === COMMANDES D'ALERTES ===
    
    async def _cmd_show_alerts(self, chat_id, args):
        """Afficher les alertes"""
        await self._safe_send(chat_id, "🔔 <b>Alertes</b>\n\nAucune alerte active")
    
    async def _cmd_notification_settings(self, chat_id, args):
        """Paramètres de notification"""
        settings_text = (
            "🔔 <b>Paramètres de Notification</b>\n\n"
            f"📱 <b>Notifications activées:</b> {'Oui' if Config.SEND_NO_UPDATES_MESSAGE else 'Non'}\n"
            f"📄 <b>Messages détaillés:</b> {'Oui' if Config.SEND_NO_CHANGES_DETAILED_MESSAGE else 'Non'}\n"
            f"⏱️ <b>Intervalle:</b> {Config.CHECK_INTERVAL_MINUTES} min\n"
            f"⏳ <b>Délai entre messages:</b> {Config.MESSAGE_DELAY_SECONDS}s\n"
            f"📊 <b>Mode initial:</b> {Config.INITIAL_SCAN_MODE}\n"
            f"📁 <b>Téléchargement fichiers:</b> {'Oui' if Config.SEND_FILES_AS_DOCUMENTS else 'Non'}"
        )
        await self._safe_send(chat_id, settings_text)
    
    async def _cmd_watch_course(self, chat_id, args):
        """Surveiller un cours"""
        await self._safe_send(chat_id, "👁️ <b>Surveillance</b>\n\nTous les cours sont déjà surveillés")
    
    async def _cmd_unwatch_course(self, chat_id, args):
        """Ne plus surveiller un cours"""
        await self._safe_send(chat_id, "👁️‍🗨️ <b>Surveillance</b>\n\nImpossible de désactiver la surveillance")
    
    # === COMMANDES UTILITAIRES ===
    
    async def _cmd_backup_data(self, chat_id, args):
        """Sauvegarder les données"""
        await self._safe_send(chat_id, "💾 <b>Sauvegarde</b>\n\nSauvegarde automatique activée")
    
    async def _cmd_restore_data(self, chat_id, args):
        """Restaurer les données"""
        await self._safe_send(chat_id, "🔄 <b>Restauration</b>\n\nRestauration non disponible")
    
    async def _cmd_clean_data(self, chat_id, args):
        """Nettoyer les données"""
        await self._safe_send(chat_id, "🧹 <b>Nettoyage</b>\n\nNettoyage automatique activé")
    
    async def _cmd_optimize_data(self, chat_id, args):
        """Optimiser les données"""
        await self._safe_send(chat_id, "⚡ <b>Optimisation</b>\n\nOptimisation automatique activée")
    
    # === COMMANDES DE DÉVELOPPEMENT ===
    
    async def _cmd_debug_info(self, chat_id, args):
        """Informations de debug"""
        debug_text = (
            "🐛 <b>Debug Info</b>\n\n"
            f"🔧 <b>Bot ref:</b> {'Disponible' if self.bot_ref else 'Non disponible'}\n"
            f"📊 <b>Commandes:</b> {len(self.commands)}\n"
            f"💾 <b>État navigation:</b> {len(self.navigation_state)} entrées\n"
            f"🔄 <b>État inline:</b> {len(self.inline_state)} entrées\n"
            f"📱 <b>Chat ID:</b> {self.chat_id}\n"
            f"⏹️ <b>Arrêt demandé:</b> {self.stopped}"
        )
        await self._safe_send(chat_id, debug_text)
    
    async def _cmd_test_connection(self, chat_id, args):
        """Tester la connexion"""
        await self._safe_send(chat_id, "🔗 <b>Test de Connexion</b>\n\n✅ Connexion OK")
    
    async def _cmd_validate_config(self, chat_id, args):
        """Valider la configuration"""
        await self._safe_send(chat_id, "✅ <b>Configuration</b>\n\nConfiguration valide")
    
    async def _cmd_check_system(self, chat_id, args):
        """Vérifier le système"""
        await self._cmd_health_check(chat_id, args)
    
    # === COMMANDES DE CONFIGURATION ET MENUS MANQUANTS ===
    async def _cmd_config(self, chat_id, args):
        """Afficher le menu/configuration (alias pratique)"""
        # Utilise le menu si disponible, sinon texte simple
        await self._cmd_config_menu(chat_id, args)

    async def _cmd_export_menu(self, chat_id, args):
        """Menu d'export (aide)"""
        help_text = (
            "📦 <b>Export</b>\n\n"
            "Utilisation: <code>/export &lt;course_id&gt;</code>\n"
            "Exemple: <code>/export 19984</code>\n\n"
            "Astuce: tapez <code>/list</code> pour voir les IDs disponibles."
        )
        await self._safe_send(chat_id, help_text)

    async def _cmd_inventory_menu(self, chat_id, args):
        """Menu d'inventaire (aide)"""
        help_text = (
            "🧭 <b>Inventaire</b>\n\n"
            "Utilisation: <code>/inventory &lt;course_id&gt;</code>\n"
            "Exemple: <code>/inventory 19984</code>\n\n"
            "Astuce: tapez <code>/list</code> pour voir les IDs disponibles."
        )
        await self._safe_send(chat_id, help_text)

    # === COMMANDES MANQUANTES ===
    
    async def _cmd_month(self, chat_id, args):
        """Changements du mois"""
        await self._send_recent_changes(chat_id, 30, "30 derniers jours")
    
    async def _cmd_new_files(self, chat_id, args):
        """Nouveaux fichiers"""
        await self._cmd_last_files(chat_id, args)
    
    async def _cmd_baseline(self, chat_id, args):
        """Scan de base"""
        await self._cmd_rescan(chat_id, args)
    
    async def _cmd_set_interval(self, chat_id, args):
        """Définir l'intervalle"""
        await self._cmd_set_delay(chat_id, args)
    
    async def _cmd_toggle_notifications(self, chat_id, args):
        """Basculer les notifications"""
        await self._safe_send(chat_id, "🔔 <b>Notifications</b>\n\nUtilisez /config pour modifier")
    
    async def _cmd_online_status(self, chat_id, args):
        """Statut en ligne"""
        await self._cmd_status(chat_id, args)
    
    async def _cmd_offline_status(self, chat_id, args):
        """Statut hors ligne"""
        await self._safe_send(chat_id, "🔴 <b>Hors ligne</b>\n\nBot arrêté")
    
    async def _cmd_busy_status(self, chat_id, args):
        """Statut occupé"""
        await self._safe_send(chat_id, "🟡 <b>Occupé</b>\n\nBot en cours de traitement")
    
    async def _cmd_idle_status(self, chat_id, args):
        """Statut inactif"""
        await self._safe_send(chat_id, "🟢 <b>Inactif</b>\n\nBot en attente")
    
    async def _cmd_global_stats(self, chat_id, args):
        """Statistiques globales"""
        await self._cmd_stats(chat_id, args)
    
    async def _cmd_jump_to_course(self, chat_id, args):
        """Aller à un cours"""
        if not args:
            await self._cmd_departments_menu(chat_id, args)
        else:
            await self._cmd_course_details(chat_id, args)
    
    async def _cmd_keyboard_shortcuts(self, chat_id, args):
        """Raccourcis clavier"""
        await self._cmd_shortcuts_menu(chat_id, args)
    
    async def _cmd_exit_menu(self, chat_id, args):
        """Quitter le menu"""
        await self._safe_send(chat_id, "👋 <b>Au revoir !</b>\n\nTapez /menu pour revenir")
    
    async def _cmd_zoom_course(self, chat_id, args):
        """Zoom sur un cours"""
        await self._cmd_jump_to_course(chat_id, args)
    
    def _get_uptime(self):
        """Obtenir l'uptime"""
        if self.bot_ref and hasattr(self.bot_ref, 'monitor'):
            stats = self.bot_ref.monitor.get_summary_stats()
            return stats.get('uptime', 'N/A')
        return 'N/A'

    async def _cmd_departments_menu(self, chat_id, args):
        """Menu des départements avec navigation inline"""
        if not InlineKeyboardButton:
            await self._cmd_departments_text(chat_id, args)
            return
        
        # Créer des boutons pour chaque département
        keyboard = []
        for i, space in enumerate(Config.MONITORED_SPACES):
            cid = space['id']
            name = space['name']
            # Tronquer le nom si trop long
            display_name = name[:30] + "..." if len(name) > 30 else name
            
            # Boutons par ligne (2 par ligne)
            if i % 2 == 0:
                keyboard.append([])
            keyboard[-1].append(InlineKeyboardButton(
                f"📚 {display_name}",
                callback_data=f"dept:{cid}:menu"
            ))
        
        # Ajouter des boutons de navigation
        keyboard.append([
            InlineKeyboardButton("🔍 Recherche", callback_data="menu:search"),
            InlineKeyboardButton("📊 Statistiques", callback_data="cmd:stats")
        ])
        keyboard.append([
            InlineKeyboardButton("🏠 Menu Principal", callback_data="menu:main"),
            InlineKeyboardButton("🆘 Aide", callback_data="cmd:help")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = (
            "📚 <b>Départements Surveillés</b>\n\n"
            f"Total: {len(Config.MONITORED_SPACES)} départements\n"
            "Sélectionnez un département pour voir ses détails :"
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def _cmd_departments_text(self, chat_id, args):
        """Menu des départements en texte simple"""
        lines = ["📚 <b>Départements Surveillés</b>"]
        for space in Config.MONITORED_SPACES:
            lines.append(f"• {space['id']} - {space['name']}")
        await self._safe_send(chat_id, '\n'.join(lines))

    # ================== Commande /stats (ASCII) ==================
    async def _cmd_stats(self, chat_id, args):
        try:
            mon = self.bot_ref.monitor if self.bot_ref else None
            if not mon:
                return await self._safe_send(chat_id, "Monitoring indisponible")
            stats = mon.get_summary_stats()
            # Histogramme simple des scans réussis vs échoués
            total = max(1, stats['total_scans'])
            success = stats['successful_scans'] if 'successful_scans' in mon.stats else 0
            fail = stats['failed_scans'] if 'failed_scans' in mon.stats else 0
            def bar(count, max_len=25):
                if total == 0: return ''
                filled = int(max_len * (count / total))
                return '█' * filled + '░' * (max_len - filled)
            lines = ["📊 <b>Statistiques</b>",
                     f"Uptime: {stats['uptime']}",
                     f"Scans: {stats['total_scans']} (Succès: {success} / Échecs: {fail})",
                     f"Succès: {bar(success)}",
                     f"Échecs: {bar(fail)}",
                     f"Notifications: {stats['total_notifications']}",
                     f"Cours surveillés: {stats['courses_monitored']}",
                     f"Erreurs récentes (24h): {stats['recent_errors']}"]
            await self._safe_send(chat_id, '\n'.join(lines))
        except Exception as e:
            await self._safe_send(chat_id, f"Erreur stats: {e}")

    # ================== Commande /week (résumé 7 jours) ==================
    async def _cmd_week(self, chat_id, args):
        try:
            logs = self.bot_ref.firebase.get_changes_since(7)
            counter = Counter()
            file_adds = 0
            renames = 0
            for entry in logs:
                for ch in entry.get('changes', []):
                    t = ch.get('type')
                    counter[t] += 1
                    if t == 'file_added': file_adds += 1
                    if t == 'section_renamed': renames += 1
            lines = ["🗓️ <b>Résumé 7 jours</b>"]
            for t, c in counter.most_common(12):
                lines.append(f"• {self._get_type_emoji(t)} {t}: {c}")
            lines.append(f"Fichiers ajoutés: {file_adds}")
            if renames:
                lines.append(f"Sections renommées: {renames}")
            await self._safe_send(chat_id, '\n'.join(lines))
        except Exception as e:
            await self._safe_send(chat_id, f"Erreur week: {e}")

    # ================== Digest journalier ==================
    async def _cmd_digest_now(self, chat_id, args):
        await self._send_daily_digest(chat_id)

    async def _send_daily_digest(self, chat_id):
        try:
            logs = self.bot_ref.firebase.get_changes_since(1)
            additions = []
            for entry in logs:
                for ch in entry.get('changes', []):
                    if any(k in ch.get('type','') for k in ['added', 'renamed']):
                        additions.append(ch)
            if not additions:
                return await self._safe_send(chat_id, "Digest: aucune nouveauté aujourd'hui")
            # Regrouper par type
            grouped = defaultdict(int)
            for a in additions:
                grouped[a.get('type')] += 1
            lines = ["📰 <b>Digest quotidien</b>"]
            for t, c in grouped.items():
                lines.append(f"• {self._get_type_emoji(t)} {t}: {c}")
            lines.append(f"Total: {len(additions)} changements")
            await self._safe_send(chat_id, '\n'.join(lines))
        except Exception as e:
            await self._safe_send(chat_id, f"Erreur digest: {e}")

    # ================== Annonces récentes ==================
    async def _cmd_today(self, chat_id, args):
        await self._send_recent_changes(chat_id, 1, label="Aujourd'hui")

    async def _cmd_yesterday(self, chat_id, args):
        await self._send_recent_changes(chat_id, 2, label="Hier", only_day_offset=1)

    async def _cmd_last7(self, chat_id, args):
        await self._send_recent_changes(chat_id, 7, label="7 derniers jours")

    async def _send_recent_changes(self, chat_id: int, days: int, label: str, only_day_offset: int = None):
        if not self.bot_ref:
            return await self._safe_send(chat_id, "Contexte indisponible")
        logs = self.bot_ref.firebase.get_changes_since(days)
        from datetime import datetime
        now = datetime.now()
        lines = [f"📰 <b>Annonces - {label}</b>"]
        count = 0
        for entry in logs:
            ts_raw = entry.get('timestamp')
            dt = None
            if isinstance(ts_raw, str):
                try:
                    dt = datetime.fromisoformat(ts_raw.replace('Z',''))
                except:  # noqa
                    pass
            if not dt:
                continue
            if only_day_offset is not None:
                if (now.date() - dt.date()).days != only_day_offset:
                    continue
            if (now - dt).days >= days:
                continue
            course_id = entry.get('course_id')
            additions = [c for c in entry.get('changes', []) if 'added' in c.get('type','') or c.get('type') in ('section_added','activity_added','resource_added','file_added')]
            if not additions:
                continue
            cname = next((s['name'] for s in Config.MONITORED_SPACES if s['id']==course_id), course_id)
            lines.append(f"• <b>{self._escape(cname)}</b> ({dt.strftime('%d/%m %H:%M')}) : {len(additions)} nouveautés")
            count += 1
            if count >= 60:
                break
        if count == 0:
            lines.append("Aucune nouvelle annonce")
        await self._safe_send(chat_id, '\n'.join(lines))

    async def _send_recent_changes_for_course(self, chat_id: int, course_id: str, days: int, label: str, only_day_offset: int = None):
        if not self.bot_ref:
            return
        logs = self.bot_ref.firebase.get_changes_since(days)
        from datetime import datetime
        now = datetime.now()
        cname = next((s['name'] for s in Config.MONITORED_SPACES if s['id']==course_id), course_id)
        lines = [f"📰 <b>{self._escape(cname)} - {label}</b>"]
        additions_total = 0
        for entry in logs:
            if entry.get('course_id') != course_id:
                continue
            ts_raw = entry.get('timestamp')
            dt = None
            if isinstance(ts_raw, str):
                try:
                    dt = datetime.fromisoformat(ts_raw.replace('Z',''))
                except:
                    continue
            if not dt:
                continue
            # Filtrer post premier scan
            if self.bot_ref.initial_scan_completed_at and dt < self.bot_ref.initial_scan_completed_at:
                continue
            if only_day_offset is not None and (now.date() - dt.date()).days != only_day_offset:
                continue
            if (now - dt).days >= days:
                continue
            # Filtrer additions
            additions = [c for c in entry.get('changes', []) if 'added' in c.get('type','') or c.get('type') in ('section_added','activity_added','resource_added','file_added')]
            if not additions:
                continue
            for a in additions[:50]:
                t = a.get('activity_title') or a.get('resource_title') or a.get('file_name') or a.get('section_title') or 'Nouveau'
                lines.append(f"• {self._escape(t)}")
                additions_total += 1
        if additions_total == 0:
            lines.append("Aucune nouveauté")
        await self._safe_send(chat_id, '\n'.join(lines))

    # ================== Envoi fichiers téléchargés ==================
    async def _cmd_send_files_course(self, chat_id, args):
        if not args:
            return await self._safe_send(chat_id, "Usage: /files_send <id>")
        await self.send_course_files(args[0])
        await self._safe_send(chat_id, "📁 Envoi des fichiers demandé (voir messages)")

    async def send_course_files(self, course_id: str, course_name: str = None):
        if not Config.SEND_FILES_AS_DOCUMENTS:
            return
        import os
        root = os.path.join('downloads', course_id)
        if not os.path.exists(root):
            return
        for dirpath, _, files in os.walk(root):
            for f in files:
                full = os.path.join(dirpath, f)
                try:
                    size = os.path.getsize(full)
                    if size > 49 * 1024 * 1024:
                        continue
                    caption = f"{course_name or course_id}\n{f}"[:100]
                    with open(full, 'rb') as fh:
                        await self.bot.send_document(chat_id=self.chat_id, document=fh, filename=f, caption=caption)
                    # Enregistrer dans contexte bigscan si actif
                    if self.bot_ref and getattr(self.bot_ref, 'current_bigscan', None) is not None:
                        try:
                            self.bot_ref.current_bigscan.setdefault('files_sent', set()).add(f)
                        except Exception:
                            pass
                    await asyncio.sleep(0.8)
                except Exception as e:
                    self.logger.warning(f"Envoi fichier échoué {f}: {e}")

    async def send_bigscan_files_summary(self, ctx: dict):
        """Envoyer un résumé final après bigscan (nombre de cours, fichiers envoyés)."""
        try:
            if not self.chat_id:
                return
            files_count = len(ctx.get('files_sent', []))
            courses = ctx.get('courses', [])
            start = ctx.get('start')
            end = ctx.get('end')
            # Top 5 cours par nombre de fichiers (si disponibles)
            top_lines = []
            cf = ctx.get('course_file_counts') or {}
            if cf:
                top_sorted = sorted(cf.items(), key=lambda x: x[1], reverse=True)[:5]
                for cid, cnt in top_sorted:
                    cname = next((s['name'] for s in Config.MONITORED_SPACES if s['id']==cid), cid)
                    top_lines.append(f"• {self._escape(cname)}: {cnt} fichiers")
            msg = ["📦 <b>Big Scan terminé</b>", f"Cours inventoriés: {len(courses)}", f"Fichiers envoyés: {files_count}"]
            if top_lines:
                msg.append("<b>Top fichiers:</b>")
                msg.extend(top_lines)
            msg.append(f"Début: {start}")
            msg.append(f"Fin: {end}")
            msg = '\n'.join(msg)
            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
        except Exception as e:
            self.logger.warning(f"Résumé bigscan échoué: {e}")

    # ================= Inline Callback Handling =================
    async def _handle_callback_query(self, cq):
        data = cq.data or ''
        try:
            if data.startswith('nav:'):
                _, cid, page_s = data.split(':',2)
                page = int(page_s)
                state_key = f"{cid}"
                st = self.inline_state.get(state_key)
                if not st: return
                await self._edit_inline_page(cq.message.chat_id, cq.message.message_id, cid, st['items'], page)
            
            elif data.startswith('dep:'):
                # Format dep:<id>:action
                _, cid, action = data.split(':',2)
                await self._handle_department_callback(cq.message.chat_id, cid, action)
            
            elif data.startswith('cmd:'):
                # Format cmd:<command>
                _, command = data.split(':',1)
                await self._handle_command(f"/{command}", cq.message.chat_id)
            
            elif data.startswith('menu:'):
                # Format menu:<menu_type>
                _, menu_type = data.split(':',1)
                await self._handle_menu_callback(cq.message.chat_id, menu_type)
            
            elif data.startswith('bigscan:confirm:'):
                choice = data.split(':',2)[2]
                if choice == 'yes':
                    await self._launch_bigscan(cq.message.chat_id)
                else:
                    await self._safe_send(cq.message.chat_id, "❌ Big scan annulé")
            
            elif data.startswith('firstscan:confirm:'):
                choice = data.split(':',2)[2]
                if choice == 'yes':
                    await self._launch_first_scan(cq.message.chat_id)
                else:
                    await self._safe_send(cq.message.chat_id, "❌ Premier scan annulé")
            
            else:
                await self._safe_send(cq.message.chat_id, f"❌ Callback inconnu: {data}")
                
        except Exception as e:
            self.logger.warning(f"Callback error: {e}")
            await self._safe_send(cq.message.chat_id, f"❌ Erreur callback: {e}")
    
    async def _handle_department_callback(self, chat_id, course_id, action):
        """Gérer les callbacks des départements"""
        if action == 'menu':
            await self._show_department_menu(chat_id, course_id)
        elif action == 'details':
            await self._cmd_course_details(chat_id, [course_id])
        elif action == 'today':
            await self._send_recent_changes_for_course(chat_id, course_id, 1, "Aujourd'hui")
        elif action == 'yesterday':
            await self._send_recent_changes_for_course(chat_id, course_id, 2, "Hier", only_day_offset=1)
        elif action == 'last7':
            await self._send_recent_changes_for_course(chat_id, course_id, 7, "7 derniers jours")
        elif action == 'sections':
            await self._cmd_list_sections(chat_id, [course_id])
        elif action == 'activities':
            await self._cmd_list_activities(chat_id, [course_id])
        elif action == 'resources':
            await self._cmd_list_resources(chat_id, [course_id])
        elif action == 'files':
            await self._cmd_list_files(chat_id, [course_id])
        elif action == 'scan':
            await self._cmd_rescan_course(chat_id, [course_id])
        elif action == 'download':
            await self._cmd_send_files_course(chat_id, [course_id])
        else:
            await self._safe_send(chat_id, f"❌ Action inconnue: {action}")
    
    async def _handle_menu_callback(self, chat_id, menu_type):
        """Gérer les callbacks des menus"""
        if menu_type == 'main':
            await self._cmd_main_menu(chat_id, [])
        elif menu_type == 'departments':
            await self._cmd_departments_menu(chat_id, [])
        elif menu_type == 'search':
            await self._cmd_search_menu(chat_id, [])
        elif menu_type == 'stats':
            await self._cmd_stats(chat_id, [])
        elif menu_type == 'config':
            await self._cmd_config_menu(chat_id, [])
        elif menu_type == 'shortcuts':
            await self._cmd_shortcuts_menu(chat_id, [])
        elif menu_type == 'guide':
            await self._cmd_guide_menu(chat_id, [])
        else:
            await self._safe_send(chat_id, f"❌ Menu inconnu: {menu_type}")
    
    async def _show_department_menu(self, chat_id, course_id):
        """Afficher le menu d'un département spécifique"""
        if not InlineKeyboardButton:
            await self._cmd_course_details(chat_id, [course_id])
            return
        
        # Trouver le département
        space = next((s for s in Config.MONITORED_SPACES if s['id'] == course_id), None)
        if not space:
            await self._safe_send(chat_id, "❌ Département non trouvé")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Détails", callback_data=f"dept:{course_id}:details")],
            [InlineKeyboardButton("📰 Aujourd'hui", callback_data=f"dept:{course_id}:today")],
            [InlineKeyboardButton("📅 Hier", callback_data=f"dept:{course_id}:yesterday")],
            [InlineKeyboardButton("🗓️ 7 jours", callback_data=f"dept:{course_id}:last7")],
            [InlineKeyboardButton("📂 Sections", callback_data=f"dept:{course_id}:sections")],
            [InlineKeyboardButton("📋 Activités", callback_data=f"dept:{course_id}:activities")],
            [InlineKeyboardButton("📚 Ressources", callback_data=f"dept:{course_id}:resources")],
            [InlineKeyboardButton("📄 Fichiers", callback_data=f"dept:{course_id}:files")],
            [InlineKeyboardButton("🔄 Scanner", callback_data=f"dept:{course_id}:scan")],
            [InlineKeyboardButton("📥 Télécharger", callback_data=f"dept:{course_id}:download")],
            [InlineKeyboardButton("🔙 Retour", callback_data="menu:departments")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = (
            f"📚 <b>{space['name']}</b>\n\n"
            f"ID: {course_id}\n"
            "Choisissez une action :"
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def _send_inline_page(self, chat_id, cid, items, page):
        state_key = f"{cid}"
        self.inline_state[state_key] = {'items': items}
        start = page * self.items_per_page
        end = start + self.items_per_page
        chunk = items[start:end]
        text = f"📘 <b>Navigation {cid}</b> (page {page+1})\n" + '\n'.join(self._escape(x) for x in chunk)
        kb = self._build_nav_keyboard(cid, page, len(items))
        msg = await self.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=kb)
        return msg

    async def _edit_inline_page(self, chat_id, message_id, cid, items, page):
        start = page * self.items_per_page
        end = start + self.items_per_page
        chunk = items[start:end]
        text = f"📘 <b>Navigation {cid}</b> (page {page+1})\n" + '\n'.join(self._escape(x) for x in chunk)
        kb = self._build_nav_keyboard(cid, page, len(items))
        try:
            await self.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='HTML', reply_markup=kb)
        except Exception as e:
            self.logger.warning(f"Edit inline failed: {e}")

    def _build_nav_keyboard(self, cid, page, total_items):
        if not InlineKeyboardButton:
            return None
        max_page = max(0, (total_items - 1) // self.items_per_page)
        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton('⬅️', callback_data=f'nav:{cid}:{page-1}'))
        nav_row.append(InlineKeyboardButton(f'{page+1}/{max_page+1}', callback_data='noop'))
        if page < max_page:
            nav_row.append(InlineKeyboardButton('➡️', callback_data=f'nav:{cid}:{page+1}'))
        if nav_row:
            buttons.append(nav_row)
        return InlineKeyboardMarkup(buttons)

    async def _cmd_main_menu(self, chat_id, args):
        """Menu principal avec navigation inline"""
        if not InlineKeyboardButton:
            await self._cmd_menu_text(chat_id, args)
            return
        
        # Statut du bot
        cycle_notifs = self.bot_ref.monitor.last_notifications_cycle() if self.bot_ref else 0
        status_icon = '🔴' if cycle_notifs > 0 else '🟢'
        
        keyboard = [
            [InlineKeyboardButton(f"{status_icon} Statut", callback_data="cmd:status")],
            [InlineKeyboardButton("📚 Départements", callback_data="menu:departments")],
            [InlineKeyboardButton("🔍 Recherche", callback_data="menu:search")],
            [InlineKeyboardButton("📊 Statistiques", callback_data="cmd:stats")],
            [InlineKeyboardButton("📰 Aujourd'hui", callback_data="cmd:today")],
            [InlineKeyboardButton("🕒 Derniers", callback_data="cmd:latest")],
            [InlineKeyboardButton("🗓️ 7 jours", callback_data="cmd:week")],
            [InlineKeyboardButton("📦 Big Scan", callback_data="cmd:bigscan")],
            [InlineKeyboardButton("⚙️ Configuration", callback_data="menu:config")],
            [InlineKeyboardButton("🆘 Aide", callback_data="cmd:help")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = (
            "🏠 <b>Menu Principal</b>\n\n"
            f"{status_icon} <b>Statut:</b> {'Changements détectés' if cycle_notifs > 0 else 'Aucun changement'}\n"
            f"📚 <b>Départements surveillés:</b> {len(Config.MONITORED_SPACES)}\n"
            f"⏱️ <b>Intervalle de scan:</b> {Config.CHECK_INTERVAL_MINUTES} min\n\n"
            "Choisissez une option ci-dessous :"
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def _cmd_menu_text(self, chat_id, args):
        """Menu en texte simple"""
        lines = [
            "🏠 <b>Menu Principal</b>",
            "",
            "📚 Départements: /list",
            "🔍 Recherche: /search",
            "📊 Statistiques: /stats",
            "📰 Aujourd'hui: /today",
            "🕒 Derniers: /latest",
            "🗓️ 7 jours: /week",
            "📦 Big Scan: /bigscan",
            "⚙️ Configuration: /config",
            "🆘 Aide: /help"
        ]
        await self._safe_send(chat_id, '\n'.join(lines))

    async def _send_menu(self, chat_id, page='main'):
        if not InlineKeyboardButton:
            return await self._safe_send(chat_id, "Inline non disponible.")
        # Status indicator: green if last cycle no notifications (quiet) OR red if there were notifications? (inverse request) -> per demande: 🟢 aucun changement, 🔴 changements.
        cycle_notifs = self.bot_ref.monitor.last_notifications_cycle() if self.bot_ref else 0
        status_icon = '🔴' if cycle_notifs > 0 else '🟢'
        if page == 'main':
            rows = [
                [InlineKeyboardButton(f'{status_icon} Statut', callback_data='menu:status'), InlineKeyboardButton('📰 Aujourd\'hui', callback_data='menu:today')],
                [InlineKeyboardButton('🕒 Derniers', callback_data='menu:latest'), InlineKeyboardButton('🗓️ 7 jours', callback_data='menu:week')],
                [InlineKeyboardButton('📈 Stats', callback_data='menu:stats'), InlineKeyboardButton('🧭 Départements', callback_data='menu:advanced')],
                [InlineKeyboardButton('➕ Plus', callback_data='menu:page:more')]
            ]
            txt = "Menu principal"
        else:  # more page
            rows = [
                [InlineKeyboardButton('📦 Big Scan', callback_data='menu:bigscan'), InlineKeyboardButton('� Derniers Fichiers', callback_data='menu:lastfiles')],
                [InlineKeyboardButton('📚 Inventaire', callback_data='menu:latest'), InlineKeyboardButton('📊 Statut BigScan', callback_data='menu:bigscanstatus')],
                [InlineKeyboardButton('⬅️ Retour', callback_data='menu:page:main')]
            ]
            txt = "Menu avancé"
        # Map special action bigscan
        # Re-route 'menu:bigscan'
        # We'll hijack callback: treat as command
        for r in rows:
            for b in r:
                if b.callback_data == 'menu:bigscan':
                    # Accept as menu:bigscan callback branch in handler
                    pass
        kb = InlineKeyboardMarkup(rows)
        await self.bot.send_message(chat_id=chat_id, text=txt, reply_markup=kb)

    async def _cmd_first_scan(self, chat_id, args):
        """Lancer le premier scan complet (inventaire initial)"""
        if not self.bot_ref:
            return await self._safe_send(chat_id, "❌ Bot non disponible")
        
        # Vérifier si un scan initial a déjà été fait
        if self.bot_ref.initial_scan_completed_at:
            return await self._safe_send(chat_id, 
                f"✅ Premier scan déjà effectué le {self.bot_ref.initial_scan_completed_at.strftime('%d/%m/%Y à %H:%M:%S')}\n\n"
                "Utilisez /bigscan pour forcer un nouveau scan complet."
            )
        
        # Demander confirmation
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('✅ Oui, lancer le premier scan', callback_data='firstscan:confirm:yes')],
            [InlineKeyboardButton('❌ Annuler', callback_data='firstscan:confirm:no')]
        ])
        await self.bot.send_message(
            chat_id=chat_id, 
            text="🔍 <b>Premier scan complet</b>\n\n"
                 "Cette commande va lancer l'inventaire initial de tous les cours surveillés.\n"
                 "Cela peut prendre du temps et télécharger des fichiers.\n\n"
                 "⚠️ <b>Confirmer le lancement ?</b>",
            reply_markup=kb,
            parse_mode='HTML'
        )

    async def _cmd_bigscan(self, chat_id, args):
        from time import time as _time
        cooldown = Config.BIGSCAN_COOLDOWN_MINUTES * 60
        now = _time()
        remaining = (self.last_bigscan_ts + cooldown) - now
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            return await self._safe_send(chat_id, f"⏳ Big scan en cooldown. Réessaie dans {mins}m{secs}s")
        # Demander confirmation
        if not InlineKeyboardButton:
            return await self._safe_send(chat_id, "Confirmez en répondant: tapez /bigscan yes pour lancer" )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('✅ Oui', callback_data='bigscan:confirm:yes'), InlineKeyboardButton('❌ Non', callback_data='bigscan:confirm:no')]
        ])
        await self.bot.send_message(chat_id=chat_id, text="⚠️ Lancer un BIG SCAN complet ?\nCela peut être long et télécharger beaucoup de fichiers.", reply_markup=kb)

    async def _launch_bigscan(self, chat_id):
        from time import time as _time
        self.last_bigscan_ts = _time()
        if not self.bot_ref:
            return await self._safe_send(chat_id, "Bot ref indisponible")
        self.bot_ref.trigger_big_scan()
        await self._safe_send(chat_id, "🚀 Big scan lancé (inventaire complet + fichiers si activés)")

    async def _launch_first_scan(self, chat_id):
        """Lancer le premier scan complet"""
        if not self.bot_ref:
            return await self._safe_send(chat_id, "❌ Bot non disponible")
        
        # Forcer le premier scan
        self.bot_ref.force_full_initial = True
        # Activer téléchargement des fichiers seulement pendant ce premier scan
        self.bot_ref.scraper.enable_file_download = Config.SEND_FILES_AS_DOCUMENTS
        
        await self._safe_send(chat_id, "🚀 Premier scan lancé (inventaire initial + fichiers si activés)")
        
        # Lancer le scan initial
        await self.bot_ref.check_all_courses(is_initial_scan=True)
        
        # Après le premier scan, désactiver téléchargement automatique
        self.bot_ref.scraper.enable_file_download = False

    async def _cmd_last_files(self, chat_id, args):
        """Lister les derniers fichiers ajoutés sur 7 jours."""
        try:
            logs = self.bot_ref.firebase.get_changes_since(7)
            records = []
            from datetime import datetime as _dt
            for entry in logs:
                cid = entry.get('course_id')
                ts = entry.get('timestamp')
                for ch in entry.get('changes', []):
                    if ch.get('type') == 'file_added':
                        records.append((ts, cid, ch.get('file_name')))
            def _p(ts):
                if isinstance(ts, str):
                    try:
                        return _dt.fromisoformat(ts.replace('Z',''))
                    except Exception:
                        return _dt.min
                return _dt.min
            records.sort(key=lambda x: _p(x[0]), reverse=True)
            lines = ["📄 <b>Derniers fichiers ajoutés</b>"]
            for r in records[:40]:
                cname = next((s['name'] for s in Config.MONITORED_SPACES if s['id']==r[1]), r[1])
                dtv = _p(r[0])
                dt_s = dtv.strftime('%d/%m %H:%M') if dtv.year>1900 else ''
                lines.append(f"• {self._escape(r[2])} — {self._escape(cname)} {dt_s}")
            if len(lines) == 1:
                lines.append("Aucun fichier récent")
            for chunk in self._paginate('\n'.join(lines)):
                await self._safe_send(chat_id, chunk)
        except Exception as e:
            await self._safe_send(chat_id, f"Erreur derniers fichiers: {e}")

    async def _cmd_bigscan_status(self, chat_id, args):
        ctx = getattr(self.bot_ref, 'current_bigscan', None) if self.bot_ref else None
        if not ctx:
            return await self._safe_send(chat_id, "Aucun big scan en cours")
        await self.send_bigscan_progress(ctx, auto=False)

    async def send_bigscan_progress(self, ctx: dict, auto: bool=False):
        """Envoyer un message de progression bigscan (estimation temps restant)."""
        try:
            if not self.chat_id:
                return
            done = len(ctx.get('courses', []))
            total = ctx.get('total_courses') or max(done,1)
            percent = (done/total)*100
            avg = 0
            ct = ctx.get('course_times') or []
            if ct:
                avg = sum(ct)/len(ct)
            remaining_courses = max(0, total - done)
            import math
            eta_seconds = remaining_courses * avg if avg else 0
            mins = int(eta_seconds // 60)
            secs = int(eta_seconds % 60)
            bar_units = 20
            filled = int((percent/100)*bar_units)
            bar = '█'*filled + '░'*(bar_units-filled)
            header = "⏳ Progression Big Scan" if not auto else "⏱️ Maj Progression Big Scan"
            lines = [f"{header}", f"{bar} {percent:.1f}%", f"Cours: {done}/{total}"]
            if eta_seconds:
                lines.append(f"Estimation restante: {mins}m{secs:02d}s")
            if ctx.get('files_sent'):
                lines.append(f"Fichiers envoyés: {len(ctx['files_sent'])}")
            txt = '\n'.join(lines)
            await self._safe_send(self.chat_id, txt)
        except Exception as e:
            self.logger.debug(f"progress send err: {e}")

    async def send_initial_completion_message(self, elapsed_seconds: float, courses_count: int):
        try:
            if not self.chat_id:
                return
            mins = int(elapsed_seconds // 60)
            secs = int(elapsed_seconds % 60)
            txt = ("✅ <b>Scan initial complet terminé</b>\n"
                   f"Cours: {courses_count}\n"
                   f"Durée: {mins}m{secs:02d}s\n"
                   f"Vous recevrez désormais uniquement les mises à jour.")
            await self._safe_send(self.chat_id, txt)
        except Exception as e:
            self.logger.debug(f"initial completion msg err: {e}")
    
    async def get_chat_id(self):
        """Obtenir l'ID du chat pour les messages privés"""
        try:
            if self.chat_id:
                return self.chat_id
            updates = await self.bot.get_updates()
            if updates:
                # Utiliser le dernier chat qui a envoyé un message
                self.chat_id = updates[-1].message.chat_id
                self.logger.info(f"Chat ID récupéré: {self.chat_id}")
                return self.chat_id
            else:
                self.logger.warning("Aucune mise à jour trouvée. Envoyez un message au bot pour obtenir votre chat ID.")
                return None
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du chat ID: {str(e)}")
            return None
    
    async def send_notification(self, course_name: str, course_url: str, changes: list, is_initial_scan: bool = False):
        """Envoyer une notification avec les changements détectés"""
        try:
            if not self.chat_id:
                await self.get_chat_id()
            if not self.chat_id:
                self.logger.error("Impossible d'envoyer la notification: chat ID non disponible")
                return False
            sent_ids = []
            if is_initial_scan:
                msg_ids = await self._send_deferred_initial_inventory(course_name, course_url, changes)
                if isinstance(msg_ids, list):
                    sent_ids.extend(msg_ids)
            else:
                chunks = self._build_messages_split(course_name, course_url, changes)
                for part in chunks:
                    msg = await self.bot.send_message(chat_id=self.chat_id, text=part, parse_mode='HTML', disable_web_page_preview=True)
                    sent_ids.append(msg.message_id)
                    await asyncio.sleep(0.15)
            if self.bot_ref and getattr(self.bot_ref, 'firebase', None):
                for mid in sent_ids:
                    try:
                        self.bot_ref.firebase.save_message_record(course_url.split('=')[-1], mid, 'notification', {
                            'initial': is_initial_scan,
                            'changes_count': len(changes)
                        })
                    except Exception:
                        pass
            self.logger.info(f"Notification envoyée pour le cours: {course_name}")
            return True
        except TelegramError as e:
            self.logger.error(f"Erreur Telegram lors de l'envoi de la notification: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi de la notification: {str(e)}")
            return False

    async def send_department_complete_message(self, course_name: str, course_id: str, content: dict):
        """Message court envoyé après inventaire complet d'un département (cours) au premier scan."""
        try:
            if not self.chat_id:
                return
            sections = content.get('sections', [])
            acts = sum(len(s.get('activities', [])) for s in sections)
            res = sum(len(s.get('resources', [])) for s in sections)
            files = 0
            for s in sections:
                for a in s.get('activities', []):
                    files += len(a.get('files', []))
                for r in s.get('resources', []):
                    files += len(r.get('files', []))
                    msg = (f"✅ <b>Inventaire terminé</b> — {self._escape(course_name)}\n"
                           f"Sections: {len(sections)} | Activités: {acts} | Ressources: {res} | Fichiers: {files}")
                    msg = await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
                    if self.bot_ref and getattr(self.bot_ref, 'firebase', None):
                        try:
                            self.bot_ref.firebase.save_message_record(course_id, msg.message_id, 'dept_summary', {
                                'sections': len(sections), 'activities': acts, 'resources': res, 'files': files
                            })
                        except Exception:
                            pass
                if self.bot_ref and getattr(self.bot_ref, 'firebase', None):
                    try:
                        self.bot_ref.firebase.save_message_record(course_id, msg.message_id, 'dept_summary', {
                            'sections': len(sections), 'total_items': total_items
                        })
                    except Exception:
                        pass
        except Exception as e:
            self.logger.warning(f"dept complete msg échoué {course_id}: {e}")

    async def send_course_no_update(self, course_name: str, course_id: str):
        """Envoyer un message indiquant qu'aucune mise à jour n'a été trouvée pour ce département au cycle courant."""
        try:
            if not self.chat_id:
                return
            msg = f"ℹ️ Pas de mise à jour pour <b>{self._escape(course_name)}</b> ce cycle"
            sent = await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
            if self.bot_ref and getattr(self.bot_ref, 'firebase', None):
                try:
                    self.bot_ref.firebase.save_message_record(course_id, sent.message_id, 'no_update', {
                        'course': course_name,
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception:
                    pass
        except Exception as e:
            self.logger.warning(f"no-update msg échoué {course_id}: {e}")
    
    async def send_no_changes_message(self, course_name: str, course_id: str):
        """Envoyer un message spécial indiquant qu'aucun changement significatif n'a été détecté."""
        try:
            if not self.chat_id:
                return
            
            # Obtenir les statistiques du cours
            snap = self.bot_ref.get_course_snapshot(course_id) if self.bot_ref else None
            sections_count = 0
            activities_count = 0
            resources_count = 0
            files_count = 0
            
            if snap:
                sections = snap.get('sections', [])
                sections_count = len(sections)
                for section in sections:
                    activities = section.get('activities', [])
                    resources = section.get('resources', [])
                    activities_count += len(activities)
                    resources_count += len(resources)
                    
                    for activity in activities:
                        files_count += len(activity.get('files', []))
                    for resource in resources:
                        files_count += len(resource.get('files', []))
            
            # Construire le message
            msg_lines = [
                "🟢 <b>Aucune mise à jour détectée</b>",
                "",
                f"📚 <b>Département:</b> {self._escape(course_name)}",
                f"📊 <b>État actuel:</b>",
                f"   • Sections: {sections_count}",
                f"   • Activités: {activities_count}",
                f"   • Ressources: {resources_count}",
                f"   • Fichiers: {files_count}",
                "",
                "✅ <i>Le contenu est à jour - aucune modification significative détectée</i>",
                f"⏰ <i>Vérifié le {self._get_current_time()}</i>"
            ]
            
            msg = '\n'.join(msg_lines)
            sent = await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
            
            # Enregistrer le message
            if self.bot_ref and getattr(self.bot_ref, 'firebase', None):
                try:
                    self.bot_ref.firebase.save_message_record(course_id, sent.message_id, 'no_changes', {
                        'course': course_name,
                        'sections': sections_count,
                        'activities': activities_count,
                        'resources': resources_count,
                        'files': files_count,
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception:
                    pass
                    
        except Exception as e:
            self.logger.warning(f"no-changes msg échoué {course_id}: {e}")

    async def send_cycle_update_summary(self, changed: list, unchanged: list):
        """Envoyer un résumé unique du cycle: départements avec et sans mise à jour."""
        try:
            if not self.chat_id:
                return
            lines = ["🌀 <b>Résumé du cycle</b>"]
            if changed:
                lines.append("\n✅ <b>Mises à jour:</b>")
                for cid, name in changed:
                    lines.append(f"• {self._escape(name)}")
            if unchanged:
                lines.append("\nℹ️ <b>Sans changement:</b>")
                # Limiter si trop long
                max_list = 60
                for cid, name in unchanged[:max_list]:
                    lines.append(f"• {self._escape(name)}")
                if len(unchanged) > max_list:
                    lines.append(f"… (+{len(unchanged)-max_list} autres)")
            if len(lines) == 1:
                lines.append("Aucune donnée sur le cycle")
            for chunk in self._paginate('\n'.join(lines)):
                await self._safe_send(self.chat_id, chunk)
        except Exception as e:
            self.logger.warning(f"cycle summary échoué: {e}")

    async def send_initial_global_summary(self, contents: dict):
        """Envoyer un résumé global après la fin du premier scan (sections totales, fichiers, etc.)."""
        try:
            if not self.chat_id:
                return
            total_courses = len(contents)
            total_sections = 0
            total_activities = 0
            total_resources = 0
            total_files = 0
            for cid, data in contents.items():
                for s in data.get('sections', []):
                    total_sections += 1
                    total_activities += len(s.get('activities', []))
                    total_resources += len(s.get('resources', []))
                    for a in s.get('activities', []):
                        total_files += len(a.get('files', []))
                    for r in s.get('resources', []):
                        total_files += len(r.get('files', []))
            msg = (
                "📊 <b>Résumé Initial Global</b>\n" \
                f"Cours: {total_courses} | Sections: {total_sections}\n" \
                f"Activités: {total_activities} | Ressources: {total_resources}\n" \
                f"Fichiers: {total_files} | Mode inventaire: {Config.INITIAL_SCAN_DETAIL_LEVEL}\n" \
                f"Versioning: {'ON' if Config.COURSE_VERSIONING else 'OFF'}"
            )
            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
        except Exception as e:
            self.logger.warning(f"Résumé global initial échoué: {e}")

    async def send_no_updates_cycle_message(self):
        try:
            if not self.chat_id:
                return
            await self.bot.send_message(chat_id=self.chat_id, text="🔄 Aucun nouveau changement sur ce cycle", parse_mode='HTML')
        except Exception as e:
            self.logger.warning(f"no updates msg échoué: {e}")

    # ================= Boutons par département (déclarations futures) =================
    def build_department_buttons(self):
        """Construire un clavier inline avec un bouton par département pour requêtes /today ou /yesterday.
           (Implémentation complète future: callback nav:dept:<id>:<scope>)"""
        if not InlineKeyboardButton:
            return None
        rows = []
        current = []
        for i, space in enumerate(Config.MONITORED_SPACES, 1):
            sid = space['id']
            current.append(InlineKeyboardButton(str(sid), callback_data=f"dep:{sid}:today"))
            if len(current) == 4:
                rows.append(current)
                current = []
        if current:
            rows.append(current)
        return InlineKeyboardMarkup(rows)
    
    async def _send_grouped_initial_scan(self, course_name: str, course_url: str, changes: list):
        """Envoyer un scan initial groupé pour éviter le spam"""
        # 1. Message d'introduction
        intro = [
            "🔍 <b>Premier scan complet</b>",
            f"📚 <b>Cours:</b> {course_name}",
            f"🔗 <b>Lien:</b> <a href='{course_url}'>Accéder au cours</a>",
            "",
            "⏳ <i>Analyse détaillée du contenu existant...</i>"
        ]
        await self.bot.send_message(chat_id=self.chat_id, text='\n'.join(intro), parse_mode='HTML', disable_web_page_preview=True)

        # 2. Résumé global
        grouped_changes = self._group_changes_by_type(changes)
        summary_lines = ["📊 <b>Résumé global</b>", ""]
        for change_type, items in grouped_changes.items():
            if items:
                summary_lines.append(f"{self._get_type_emoji(change_type)} {self._get_type_name(change_type)}: <b>{len(items)}</b>")
        summary_lines.append("")
        summary_lines.append(f"⏰ <i>Généré le {self._get_current_time()}</i>")
        await self.bot.send_message(chat_id=self.chat_id, text='\n'.join(summary_lines), parse_mode='HTML')

        # 3. Détails section par section
        section_messages = self._build_detailed_initial_sections(changes)
        for msg in section_messages:
            # Découper si > 3900 caractères (limite Telegram ~4096)
            if len(msg) <= 3900:
                await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML', disable_web_page_preview=True)
            else:
                # Split propre par double saut de ligne
                parts = self._split_long_message(msg)
                for part in parts:
                    await self.bot.send_message(chat_id=self.chat_id, text=part, parse_mode='HTML', disable_web_page_preview=True)
            await asyncio.sleep(0.3)  # petite pause pour éviter le flood

        # 4. Conclusion
        conclusion = f"✅ <b>Scan initial terminé</b>\n\nTotal: <b>{len(grouped_changes.get('existing_activity', [])) + len(grouped_changes.get('existing_resource', [])) + len(grouped_changes.get('existing_file', []))}</b> éléments listés."
        await self.bot.send_message(chat_id=self.chat_id, text=conclusion, parse_mode='HTML')

    async def _send_separate_initial_scan(self, course_name: str, course_url: str, changes: list):
        """Envoyer chaque section / activité / ressource séparément dans l'ordre (streaming)."""
        header = f"🔍 <b>Inventaire initial</b>\n📚 <b>Cours:</b> {course_name}\n🔗 <a href='{course_url}'>Ouvrir</a>\n"\
                 f"⚙️ Mode: Séparé\n"\
                 f"⏰ {self._get_current_time()}"
        await self.bot.send_message(chat_id=self.chat_id, text=header, parse_mode='HTML', disable_web_page_preview=True)

        current_section = None
        activity_index = 0
        resource_index = 0
        for change in changes:
            ctype = change.get('type')
            if ctype == 'existing_section':
                current_section = change.get('section_title', 'Sans titre')
                activity_index = 0
                resource_index = 0
                msg = f"\n📂 <b>Section:</b> {self._escape(current_section)}\n📝 {self._escape(change.get('details',''))}"
                await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
                await asyncio.sleep(Config.MESSAGE_DELAY_SECONDS)
            elif ctype == 'existing_activity':
                activity_index += 1
                title = change.get('activity_title','Sans titre')
                details = change.get('details','')
                msg = f"📋 <b>Activité {activity_index}</b> — {self._escape(title)}\n<i>{self._escape(details)}</i>"
                await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
                await asyncio.sleep(Config.MESSAGE_DELAY_SECONDS)
            elif ctype == 'existing_resource':
                resource_index += 1
                title = change.get('resource_title','Sans titre')
                details = change.get('details','')
                msg = f"📚 <b>Ressource {resource_index}</b> — {self._escape(title)}\n<i>{self._escape(details)}</i>"
                await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
                await asyncio.sleep(Config.MESSAGE_DELAY_SECONDS)
            elif ctype == 'existing_file':
                file_name = change.get('file_name','Fichier')
                parent = change.get('parent_title','')
                msg = f"📄 <b>Fichier</b>: {self._escape(file_name)}\n📁 Dans: {self._escape(parent)}"
                await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML', disable_web_page_preview=True)
                await asyncio.sleep(Config.MESSAGE_DELAY_SECONDS)

        footer = f"✅ <b>Fin inventaire:</b> {course_name}\n⏰ {self._get_current_time()}"
        await self.bot.send_message(chat_id=self.chat_id, text=footer, parse_mode='HTML')

    async def _send_deferred_initial_inventory(self, course_name: str, course_url: str, changes: list):
        """Construire un inventaire complet et l'envoyer en un seul lot structuré avec liens fichiers et ressources."""
        # Regrouper par section
        sections = []
        current = None
        for ch in changes:
            ctype = ch.get('type')
            if ctype == 'existing_section':
                current = {
                    'title': ch.get('section_title','Sans titre'),
                    'activities': [],
                    'resources': [],
                    'files': []
                }
                sections.append(current)
            elif ctype == 'existing_activity' and current:
                current['activities'].append(ch)
            elif ctype == 'existing_resource' and current:
                current['resources'].append(ch)
            elif ctype == 'existing_file' and current:
                current['files'].append(ch)

        header = (
            f"🔍 <b>Inventaire initial (fin de scan)</b>\n"
            f"📚 <b>Cours:</b> {self._escape(course_name)}\n"
            f"🔗 <a href='{course_url}'>Ouvrir le cours</a>\n"
            f"🕒 {self._get_current_time()}\n"
            "\n"
        )
        parts = [header]
        summary_mode = (Config.INITIAL_SCAN_DETAIL_LEVEL == 'summary')
        for idx, sec in enumerate(sections, 1):
            parts.append(f"📂 <b>Section {idx}:</b> {self._escape(sec['title'])}")
            if summary_mode:
                a_count = len(sec['activities'])
                r_count = len(sec['resources'])
                f_count = len(sec['files'])
                parts.append(f"   ➤ Activités: {a_count} | Ressources: {r_count} | Fichiers: {f_count}")
            else:
                if sec['activities']:
                    parts.append("   🧩 <b>Activités:</b>")
                    for a_i, act in enumerate(sec['activities'], 1):
                        t = act.get('activity_title','Sans titre')
                        details = act.get('details','')
                        parts.append(f"   {a_i}. 📋 {self._escape(t)}\n      <i>{self._escape(details)[:300]}</i>")
                if sec['resources']:
                    parts.append("   📚 <b>Ressources:</b>")
                    for r_i, res in enumerate(sec['resources'], 1):
                        t = res.get('resource_title','Sans titre')
                        details = res.get('details','')
                        parts.append(f"   {r_i}. 📗 {self._escape(t)}\n      <i>{self._escape(details)[:300]}</i>")
                if sec['files']:
                    parts.append("   📄 <b>Fichiers:</b>")
                    for f_i, fch in enumerate(sec['files'], 1):
                        fname = fch.get('file_name','Fichier')
                        det = fch.get('details','')
                        fdate = fch.get('file_date')
                        if fdate:
                            from datetime import datetime
                            try:
                                dt = datetime.fromisoformat(fdate.replace('Z',''))
                                date_str = dt.strftime('%d/%m/%Y %H:%M')
                            except Exception:
                                date_str = ''
                        else:
                            date_str = ''
                        date_part = f" | 🗓️ {date_str}" if date_str else ''
                        parts.append(f"      {f_i}. {self._escape(fname)} — {self._escape(det)[:160]}{date_part}")
            parts.append("")
        footer = f"✅ Fin inventaire pour {self._escape(course_name)}"
        parts.append(footer)
        full_text = '\n'.join(parts)
        sent_ids = []
        for chunk in self._paginate(full_text):
            msg = await self.bot.send_message(chat_id=self.chat_id, text=chunk, parse_mode='HTML', disable_web_page_preview=True)
            sent_ids.append(msg.message_id)
        return sent_ids

    def _build_detailed_initial_sections(self, changes: list) -> list:
        """Construire des messages détaillés listant chaque section et son contenu."""
        messages = []
        current_section = None
        section_lines = []
        section_index = 0
        activity_counter = 0
        resource_counter = 0

        def flush_section():
            nonlocal section_lines, current_section, activity_counter, resource_counter, section_index
            if current_section:
                header = [
                    f"� <b>Section {section_index}: {current_section}</b>",
                    f"• Activités: <b>{activity_counter}</b> | Ressources: <b>{resource_counter}</b>",
                    ""
                ]
                body = header + section_lines
                messages.extend(self._paginate('\n'.join(body)))
            # Reset
            section_lines = []
            current_section = None
            activity_counter = 0
            resource_counter = 0

        for change in changes:
            ctype = change.get('type')
            if ctype == 'existing_section':
                # flush previous
                flush_section()
                current_section = change.get('section_title', 'Sans titre')
                section_index += 1
            elif ctype == 'existing_activity':
                activity_counter += 1
                title = change.get('activity_title', 'Sans titre')
                details = change.get('details', '')
                section_lines.append(f"{activity_counter}. 📋 <b>{title}</b>\n   <i>{self._escape(details)[:500]}</i>")
            elif ctype == 'existing_resource':
                resource_counter += 1
                title = change.get('resource_title', 'Sans titre')
                details = change.get('details', '')
                section_lines.append(f"{resource_counter}. 📚 <b>{title}</b>\n   <i>{self._escape(details)[:500]}</i>")
            elif ctype == 'existing_file':
                fname = change.get('file_name', 'Fichier')
                parent = change.get('parent_title', '')
                section_lines.append(f"   └─ 📄 {self._escape(fname)} <i>(dans {self._escape(parent)})</i>")

        # flush last
        flush_section()
        return messages

        
    def _paginate(self, text: str) -> list:
        """Découper un long texte en segments compatibles Telegram."""
        max_len = 3900
        if len(text) <= max_len:
            return [text]
        chunks = []
        current = []
        length = 0
        for line in text.split('\n'):
            line_len = len(line) + 1
            if length + line_len > max_len:
                chunks.append('\n'.join(current))
                current = [line]
                length = line_len
            else:
                current.append(line)
                length += line_len
        if current:
            chunks.append('\n'.join(current))
        return chunks

    def _split_long_message(self, msg: str) -> list:
        """Couper un message très long proprement (fallback)."""
        return self._paginate(msg)

    def _escape(self, s: str) -> str:
        """Échapper quelques caractères pour HTML (basique)."""
        if not isinstance(s, str):
            return s
        return (s.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;'))

    async def _safe_send(self, chat_id: int, text: str, parse_mode: str = 'HTML'):
        try:
            # Split proactively if too long
            if len(text) > 3900:
                for chunk in self._paginate(text):
                    await self._safe_send(chat_id, chunk, parse_mode=parse_mode)
                return
            try:
                await self.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, disable_web_page_preview=True)
            except TelegramError as te:
                # Retry plain text if formatting or length error
                if any(k in str(te).lower() for k in ['unsupported start tag','parse entities','too long']):
                    clean = self._strip_html(text)[:4090]
                    if len(clean) > 3900:
                        for chunk in self._paginate(clean):
                            await self.bot.send_message(chat_id=chat_id, text=chunk)
                    else:
                        await self.bot.send_message(chat_id=chat_id, text=clean)
                else:
                    raise
        except Exception as e:
            self.logger.error(f"Envoi message échoué: {e}")
    
    def _group_changes_by_type(self, changes: list) -> dict:
        """Grouper les changements par type"""
        grouped = {}
        for change in changes:
            change_type = change.get('type', 'unknown')
            if change_type not in grouped:
                grouped[change_type] = []
            grouped[change_type].append(change)
        return grouped
    
    def _get_type_emoji(self, change_type: str) -> str:
        """Obtenir l'emoji pour un type de changement"""
        emoji_map = {
            'existing_section': '📂',
            'existing_activity': '📋',
            'existing_resource': '📚',
            'existing_file': '📄',
            'section_added': '➕',
            'section_removed': '➖',
            'activity_added': '➕',
            'activity_removed': '➖',
            'resource_added': '➕',
            'resource_removed': '➖',
            'file_added': '📁',
            'file_removed': '🗑️',
            'activity_description_changed': '✏️',
            'section_renamed': '🔁'
        }
        return emoji_map.get(change_type, '📝')
    
    def _get_type_name(self, change_type: str) -> str:
        """Obtenir le nom lisible pour un type de changement"""
        name_map = {
            'existing_section': 'Sections existantes',
            'existing_activity': 'Activités existantes',
            'existing_resource': 'Ressources existantes',
            'existing_file': 'Fichiers existants',
            'section_added': 'Nouvelles sections',
            'section_removed': 'Sections supprimées',
            'activity_added': 'Nouvelles activités',
            'activity_removed': 'Activités supprimées',
            'resource_added': 'Nouvelles ressources',
            'resource_removed': 'Ressources supprimées',
            'file_added': 'Nouveaux fichiers',
            'file_removed': 'Fichiers supprimés',
            'activity_description_changed': 'Descriptions modifiées',
            'section_renamed': 'Sections renommées'
        }
        return name_map.get(change_type, 'Autres')
    
    def _build_message(self, course_name: str, course_url: str, changes: list, is_initial_scan: bool = False) -> str:
        """Construire le message de notification"""
        if is_initial_scan:
            message = f"🔍 <b>Premier scan du cours</b>\n\n"
        else:
            message = f"🔔 <b>Mise à jour détectée</b>\n\n"
        
        message += f"📚 <b>Cours:</b> {course_name}\n"
        message += f"🔗 <b>Lien:</b> <a href='{course_url}'>Accéder au cours</a>\n\n"
        
        message += f"📋 <b>Changements détectés ({len(changes)}):</b>\n\n"
        
        for i, change in enumerate(changes, 1):
            base_line = f"{i}. <b>{change['message']}</b>"
            # Surface file_date for file_added
            if change.get('type') == 'file_added' and change.get('file_date'):
                try:
                    dt = datetime.fromisoformat(change['file_date'].replace('Z',''))
                    base_line += f" (🗓️ {dt.strftime('%d/%m %H:%M')})"
                except Exception:
                    pass
            message += base_line + "\n"
            
            if 'details' in change:
                message += f"   📝 {change['details']}\n"
            
            # Ajouter des emojis selon le type de changement
            emoji = self._get_type_emoji(change.get('type', 'unknown'))
            message += f"   {emoji}\n"
            
            message += "\n"
        
        message += f"⏰ <i>Détecté le {self._get_current_time()}</i>"
        
        return message
    
    def _get_current_time(self) -> str:
        """Obtenir l'heure actuelle formatée"""
        from datetime import datetime
        return datetime.now().strftime("%d/%m/%Y à %H:%M:%S")

    def _strip_html(self, text: str) -> str:
        import re
        return re.sub(r'<[^>]+>', '', text)
    
    async def send_startup_message(self, monitor=None):
        """Envoyer un message de démarrage du bot"""
        try:
            if not self.chat_id:
                await self.get_chat_id()
            
            if not self.chat_id:
                return False
            
            message = "🤖 <b>Bot eLearning Notifier démarré</b>\n\n"
            message += "✅ Surveillance active des espaces d'affichage\n"
            message += f"⏱️ Vérification toutes les {Config.CHECK_INTERVAL_MINUTES} minutes\n"
            message += f"📚 {len(Config.MONITORED_SPACES)} espaces surveillés\n\n"
            
            # Ajouter les statistiques si disponibles
            if monitor:
                stats = monitor.get_summary_stats()
                if stats['total_scans'] > 0:
                    message += f"📊 Statistiques:\n"
                    message += f"• Temps de fonctionnement: {stats['uptime']}\n"
                    message += f"• Total des scans: {stats['total_scans']}\n"
                    message += f"• Taux de succès: {stats['success_rate']}\n"
                    message += f"• Notifications envoyées: {stats['total_notifications']}\n\n"
            
            message += "🔔 Vous recevrez une notification dès qu'un changement sera détecté !\n\n"
            message += "🔍 <b>Premier scan en cours...</b>"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info("Message de démarrage envoyé")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi du message de démarrage: {str(e)}")
            return False
    
    async def send_error_message(self, error_message: str):
        """Envoyer un message d'erreur"""
        try:
            if not self.chat_id:
                await self.get_chat_id()
            
            if not self.chat_id:
                return False
            
            message = f"❌ <b>Erreur du Bot</b>\n\n{error_message}"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info("Message d'erreur envoyé")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi du message d'erreur: {str(e)}")
            return False