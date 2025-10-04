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

    def set_bot_ref(self, bot_ref):
        self.bot_ref = bot_ref

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

        # Mapping commandes
        commands = {
            '/start': self._cmd_start,
            '/help': self._cmd_help,
            '/status': self._cmd_status,
            '/list': self._cmd_list_courses,
            '/course': self._cmd_course_details,
            '/rescan': self._cmd_rescan,
            '/rescan_course': self._cmd_rescan_course,
            '/sections': self._cmd_list_sections,
            '/activities': self._cmd_list_activities,
            '/resources': self._cmd_list_resources,
            '/files': self._cmd_list_files,
            '/nav': self._cmd_nav_course,
            '/setmode': self._cmd_set_mode,
            '/delay': self._cmd_set_delay,
            '/search': self._cmd_search,
            '/export': self._cmd_export_course,
            '/courses_count': self._cmd_courses_count,
            '/uptime': self._cmd_uptime,
            '/ping': self._cmd_ping,
            '/latest': self._cmd_latest_changes,
            '/config': self._cmd_show_config,
            '/stopbot': self._cmd_stop_bot,
            '/inline': self._cmd_inline_paginate,
            '/inventory': self._cmd_inventory_course,
            '/versions': self._cmd_versions,
            '/about': self._cmd_about,
            '/today': self._cmd_today,
            '/yesterday': self._cmd_yesterday,
            '/last7': self._cmd_last7,
            '/files_send': self._cmd_send_files_course,
            '/update': self._cmd_today,
            '/departements': self._cmd_departements,
            '/stats': self._cmd_stats,
            '/week': self._cmd_week,
            '/digest': self._cmd_digest_now,
        }
        # Étendre avec alias dynamiques
        self._extend_dynamic_commands(commands)

        handler = commands.get(cmd)
        if handler:
            try:
                await handler(chat_id, args)
            except Exception as e:
                await self._safe_send(chat_id, f"❌ Erreur commande {cmd}: {e}")
        else:
            await self._safe_send(chat_id, "Commande inconnue. Tape /help")

    # =============== Command Handlers (20+) ===============
    async def _cmd_start(self, chat_id, args):
        await self._cmd_help(chat_id, args)

    async def _cmd_help(self, chat_id, args):
        help_text = (
            "🤖 <b>Commandes principales</b>\n"
            "(Guide avancé: /advanced pour >100 commandes spécifiques)\n\n"
            "/status /list /course /sections /activities /resources /files\n"
            "/inventory /nav /inline /search /export /courses_count /uptime /ping\n"
            "/config /setmode /delay /versions /about /rescan /rescan_course\n"
            "/today /yesterday /last7 /update /files_send /stopbot\n"
        )
        await self._safe_send(chat_id, help_text)

    async def _cmd_advanced(self, chat_id, args):
        # Génère liste alias département: /d<id> (snapshot), /dt<id> today, /dy<id> yesterday, /d7<id> last7
        lines = ["📘 <b>Commandes Département</b>"]
        for space in Config.MONITORED_SPACES:
            cid = space['id']
            base = f"/d{cid}"  # snapshot rapide
            lines.append(f"{base} | /dt{cid} | /dy{cid} | /d7{cid}")
        lines.append("Format: /d<ID>=snapshot, /dt<ID>=today, /dy<ID>=yesterday, /d7<ID>=7 jours")
        txt = '\n'.join(lines)
        for chunk in self._paginate(txt):
            await self._safe_send(chat_id, chunk)

    def _extend_dynamic_commands(self, commands: dict):
        # Ajouter alias dynamiques département
        for space in Config.MONITORED_SPACES:
            cid = space['id']
            commands[f"/d{cid}"] = lambda chat_id, args, _cid=cid: self._cmd_course_details(chat_id, [_cid])
            commands[f"/dt{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 1, "Aujourd'hui")
            commands[f"/dy{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 2, "Hier", only_day_offset=1)
            commands[f"/d7{cid}"] = lambda chat_id, args, _cid=cid: self._send_recent_changes_for_course(chat_id, _cid, 7, "7 jours")
        commands['/advanced'] = self._cmd_advanced

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
        await self._safe_send(chat_id, "(Non implémenté: historique des derniers changements)")

    async def _cmd_show_config(self, chat_id, args):
        from config import Config as C
        msg = (
            f"Config:\nMode: {C.INITIAL_SCAN_MODE}\nDelay: {C.MESSAGE_DELAY_SECONDS}s\nInterval: {C.CHECK_INTERVAL_MINUTES}m\n"
        )
        await self._safe_send(chat_id, msg)

    async def _cmd_stop_bot(self, chat_id, args):
        if self.bot_ref:
            self.bot_ref.stop()
            await self._safe_send(chat_id, "🛑 Bot arrêté")

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
        await self._safe_send(chat_id, "Bot de surveillance eLearning — version commandes enrichies.")

    async def _cmd_departements(self, chat_id, args):
        kb = self.build_department_buttons()
        if not kb:
            return await self._safe_send(chat_id, "Inline keyboard non supporté par cette version")
        await self.bot.send_message(chat_id=chat_id, text="Sélectionnez un département (Today):", reply_markup=kb)

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
                    await asyncio.sleep(0.8)
                except Exception as e:
                    self.logger.warning(f"Envoi fichier échoué {f}: {e}")

    # ================= Inline Callback Handling =================
    async def _handle_callback_query(self, cq):
        data = cq.data or ''
        if data.startswith('nav:'):
            _, cid, page_s = data.split(':',2)
            page = int(page_s)
            state_key = f"{cid}"
            st = self.inline_state.get(state_key)
            if not st: return
            await self._edit_inline_page(cq.message.chat_id, cq.message.message_id, cid, st['items'], page)
        elif data.startswith('dep:'):
            # Format dep:<id>:scope  scope in [today,yesterday,last7]
            try:
                _, cid, scope = data.split(':',2)
                if scope == 'today':
                    await self._send_recent_changes_for_course(cq.message.chat_id, cid, 1, "Aujourd'hui")
                elif scope == 'yesterday':
                    await self._send_recent_changes_for_course(cq.message.chat_id, cid, 2, "Hier", only_day_offset=1)
                elif scope == 'last7':
                    await self._send_recent_changes_for_course(cq.message.chat_id, cid, 7, "7 derniers jours")
            except Exception as e:
                self.logger.warning(f"Callback dep parse error: {e}")

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
            
            if is_initial_scan:
                # NE RIEN ENVOYER PAR ÉLÉMENT: construire un bloc final unique
                await self._send_deferred_initial_inventory(course_name, course_url, changes)
            else:
                # Changements normaux (diff incrémental)
                message = self._build_message(course_name, course_url, changes, is_initial_scan)
                await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML', disable_web_page_preview=True)
            
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
            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
        except Exception as e:
            self.logger.warning(f"dept complete msg échoué {course_id}: {e}")

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
        # Paginer si nécessaire
        for chunk in self._paginate(full_text):
            await self.bot.send_message(chat_id=self.chat_id, text=chunk, parse_mode='HTML', disable_web_page_preview=True)

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
            await self.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, disable_web_page_preview=True)
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