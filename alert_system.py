"""
ALERT SYSTEM - Autonomous Monitoring & Notification Engine
Created: January 23, 2026
Last Updated: March 03, 2026 - KEYERROR FIX in get_alert_counts()

CHANGELOG:
- March 03, 2026: KEYERROR FIX
  * get_alert_counts(): SELECT COUNT(*) had no alias — fetchone()[0] used
    integer index which raises KeyError: 0 on psycopg2 RealDictCursor.
    Fixed by:
      1. Adding AS count alias: SELECT COUNT(*) AS count
      2. Changing fetchone()[0] to row = fetchone() then row['count']
    This fix is compatible with both PostgreSQL (RealDictRow) and
    SQLite (DictRow wrapper which already supports named key access).
  * No other changes — all other functionality preserved exactly.

- March 02, 2026: POSTGRESQL MIGRATION FIX
  * All SQL ? placeholders replaced with %s (PostgreSQL style)
  * All database functions now use try/finally to guarantee conn.close()
  * Removed module-level init_alert_tables() call — was holding a
    connection open during every import. Now called lazily on first use
    via _ensure_tables_initialized() guard.
  * INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
  * BOOLEAN DEFAULT 0/1 -> BOOLEAN DEFAULT FALSE/TRUE
  * is_read = 0 comparisons -> is_read = FALSE
  * is_enabled = 1 comparisons -> is_enabled = TRUE
  * _init_default_jobs() now uses %s and its own try/finally

- January 23, 2026: Initial creation

PURPOSE:
This module provides autonomous monitoring and alerting capabilities for the AI Swarm.
It runs scheduled jobs to monitor various intelligence sources and delivers alerts
via email and the dashboard.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import json
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database import get_db
from db_engine import get_db_type

# =============================================================================
# CONFIGURATION
# =============================================================================

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.sendgrid.net')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'apikey')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or os.environ.get('SENDGRID_API_KEY')
ALERT_FROM_EMAIL = os.environ.get('ALERT_FROM_EMAIL', 'alerts@shiftworksolutions.com')
ALERT_TO_EMAIL = os.environ.get('ALERT_TO_EMAIL', '')

ALERT_CHECK_INTERVAL_MINUTES = int(os.environ.get('ALERT_CHECK_INTERVAL', 60))
ENABLE_EMAIL_ALERTS = os.environ.get('ENABLE_EMAIL_ALERTS', 'false').lower() == 'true'
ENABLE_SCHEDULED_JOBS = os.environ.get('ENABLE_SCHEDULED_JOBS', 'false').lower() == 'true'


class AlertCategory:
    LEAD = 'lead_alert'
    COMPETITOR = 'competitor_alert'
    REGULATORY = 'regulatory_alert'
    CLIENT_NEWS = 'client_news_alert'
    INDUSTRY_TREND = 'industry_trend_alert'
    SYSTEM = 'system_alert'


class AlertPriority:
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

_tables_initialized = False


def _ensure_tables_initialized():
    """Call this at the start of any function that needs the tables."""
    global _tables_initialized
    if not _tables_initialized:
        init_alert_tables()


def init_alert_tables():
    """
    Initialize alert-related database tables.
    Called lazily on first use, not at module import.
    Uses %s placeholders and SERIAL PRIMARY KEY for PostgreSQL.
    """
    global _tables_initialized
    if _tables_initialized:
        return

    db_type = get_db_type()
    pk = 'SERIAL PRIMARY KEY' if db_type == 'postgresql' else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    bool_false = 'FALSE' if db_type == 'postgresql' else '0'
    bool_true = 'TRUE' if db_type == 'postgresql' else '1'

    db = get_db()
    try:
        db.execute(f'''
            CREATE TABLE IF NOT EXISTS alerts (
                id {pk},
                category TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                title TEXT NOT NULL,
                summary TEXT,
                details TEXT,
                source_url TEXT,
                source_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged_at TIMESTAMP,
                dismissed_at TIMESTAMP,
                snoozed_until TIMESTAMP,
                emailed_at TIMESTAMP,
                is_read BOOLEAN DEFAULT {bool_false},
                is_actioned BOOLEAN DEFAULT {bool_false},
                action_taken TEXT,
                metadata TEXT
            )
        ''')

        db.execute(f'''
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id {pk},
                job_name TEXT UNIQUE NOT NULL,
                job_type TEXT NOT NULL,
                schedule_type TEXT DEFAULT 'daily',
                schedule_time TEXT DEFAULT '07:00',
                schedule_days TEXT DEFAULT 'mon,tue,wed,thu,fri',
                is_enabled BOOLEAN DEFAULT {bool_false},
                last_run_at TIMESTAMP,
                next_run_at TIMESTAMP,
                last_result TEXT,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        db.execute(f'''
            CREATE TABLE IF NOT EXISTS job_executions (
                id {pk},
                job_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT DEFAULT 'running',
                alerts_generated INTEGER DEFAULT 0,
                error_message TEXT,
                execution_log TEXT
            )
        ''')

        db.execute(f'''
            CREATE TABLE IF NOT EXISTS alert_subscriptions (
                id {pk},
                email TEXT NOT NULL,
                category TEXT,
                priority_threshold TEXT DEFAULT 'medium',
                is_enabled BOOLEAN DEFAULT {bool_true},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        db.execute(f'''
            CREATE TABLE IF NOT EXISTS monitored_entities (
                id {pk},
                entity_type TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                search_terms TEXT,
                is_enabled BOOLEAN DEFAULT {bool_true},
                last_checked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_category ON alerts(category)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_priority ON alerts(priority)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, dismissed_at)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON scheduled_jobs(next_run_at)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_monitored_type ON monitored_entities(entity_type)')

        db.commit()
        _tables_initialized = True
        print("✅ Alert system tables initialized")
    except Exception as e:
        print(f"⚠️ Alert table init warning: {e}")
    finally:
        db.close()

    # Initialize default jobs (uses its own connection)
    _init_default_jobs()


def _init_default_jobs():
    """Create default scheduled jobs if they don't exist."""
    default_jobs = [
        {
            'job_name': 'daily_lead_scan',
            'job_type': 'lead_finder',
            'schedule_type': 'daily',
            'schedule_time': '07:00',
            'schedule_days': 'mon,tue,wed,thu,fri',
            'config': json.dumps({
                'industries': ['manufacturing', 'pharmaceutical', 'food processing'],
                'max_results': 10
            })
        },
        {
            'job_name': 'daily_regulatory_scan',
            'job_type': 'regulatory_monitor',
            'schedule_type': 'daily',
            'schedule_time': '06:00',
            'schedule_days': 'mon,tue,wed,thu,fri',
            'config': json.dumps({
                'topics': ['OSHA', 'labor law', 'overtime regulations', 'shift work compliance']
            })
        },
        {
            'job_name': 'weekly_competitor_scan',
            'job_type': 'competitor_monitor',
            'schedule_type': 'weekly',
            'schedule_time': '08:00',
            'schedule_days': 'mon',
            'config': json.dumps({
                'competitors': ['shift scheduling software', 'workforce management consulting']
            })
        },
        {
            'job_name': 'daily_briefing_email',
            'job_type': 'daily_briefing',
            'schedule_type': 'daily',
            'schedule_time': '07:30',
            'schedule_days': 'mon,tue,wed,thu,fri',
            'config': json.dumps({
                'include_sections': ['leads', 'regulations', 'industry_news']
            })
        }
    ]

    db = get_db()
    try:
        for job in default_jobs:
            existing = db.execute(
                'SELECT id FROM scheduled_jobs WHERE job_name = %s',
                (job['job_name'],)
            ).fetchone()

            if not existing:
                db.execute('''
                    INSERT INTO scheduled_jobs
                        (job_name, job_type, schedule_type, schedule_time,
                         schedule_days, config, is_enabled)
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                ''', (
                    job['job_name'], job['job_type'], job['schedule_type'],
                    job['schedule_time'], job['schedule_days'], job['config']
                ))
        db.commit()
    except Exception as e:
        print(f"⚠️ Default jobs init warning: {e}")
    finally:
        db.close()


# =============================================================================
# ALERT MANAGEMENT
# =============================================================================

class AlertManager:
    """Manages creation, delivery, and lifecycle of alerts."""

    def __init__(self):
        self.email_enabled = ENABLE_EMAIL_ALERTS and bool(SMTP_PASSWORD) and bool(ALERT_TO_EMAIL)
        if self.email_enabled:
            print(f"✅ Alert email delivery enabled (to: {ALERT_TO_EMAIL})")
        else:
            print("ℹ️  Alert email delivery disabled (configure SMTP settings to enable)")

    def create_alert(self, category, title, summary, priority=AlertPriority.MEDIUM,
                     details=None, source_url=None, source_data=None, metadata=None,
                     send_email=True):
        """Create a new alert and optionally send email notification."""
        _ensure_tables_initialized()

        db = get_db()
        try:
            cursor = db.execute('''
                INSERT INTO alerts
                    (category, priority, title, summary, details,
                     source_url, source_data, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                category, priority, title, summary, details,
                source_url,
                json.dumps(source_data) if source_data else None,
                json.dumps(metadata) if metadata else None
            ))
            alert_id = cursor.lastrowid
            db.commit()
        finally:
            db.close()

        print(f"🔔 Alert created: [{priority.upper()}] {title}")

        if send_email and self.email_enabled:
            if priority in [AlertPriority.CRITICAL, AlertPriority.HIGH]:
                self._send_alert_email(
                    alert_id, category, priority, title, summary, details, source_url
                )

        return alert_id

    def _send_alert_email(self, alert_id, category, priority, title,
                          summary, details, source_url):
        """Send email notification for an alert."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{priority.upper()}] {title} - Shiftwork Solutions Alert"
            msg['From'] = ALERT_FROM_EMAIL
            msg['To'] = ALERT_TO_EMAIL

            text_content = f"""
ALERT: {title}
Priority: {priority.upper()}
Category: {category}

{summary}

{details or ''}

{f'Source: {source_url}' if source_url else ''}

---
View all alerts: https://ai-swarm-orchestrator.onrender.com/
"""
            priority_colors = {
                'critical': '#d32f2f', 'high': '#f57c00',
                'medium': '#1976d2', 'low': '#388e3c'
            }
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .alert-box {{ max-width:600px; margin:20px auto; border:1px solid #e0e0e0; border-radius:8px; overflow:hidden; }}
        .alert-header {{ background:{priority_colors.get(priority,'#1976d2')}; color:white; padding:15px 20px; }}
        .alert-body {{ padding:20px; }}
        .alert-meta {{ font-size:12px; color:#666; margin-top:15px; }}
    </style>
</head>
<body>
    <div class="alert-box">
        <div class="alert-header"><strong>🔔 {priority.upper()} ALERT</strong></div>
        <div class="alert-body">
            <h2 style="margin-top:0;">{title}</h2>
            <p>{summary}</p>
            {f'<div style="padding:15px; background:#f5f5f5; border-radius:6px; margin:15px 0;">{details}</div>' if details else ''}
            {f'<p><a href="{source_url}" style="color:#667eea;">🔗 View Source</a></p>' if source_url else ''}
            <div class="alert-meta">
                <p>Category: {category}<br>Alert ID: {alert_id}<br>
                Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            db = get_db()
            try:
                db.execute(
                    'UPDATE alerts SET emailed_at = %s WHERE id = %s',
                    (datetime.now(), alert_id)
                )
                db.commit()
            finally:
                db.close()

            print(f"📧 Alert email sent to {ALERT_TO_EMAIL}")

        except Exception as e:
            print(f"⚠️ Failed to send alert email: {e}")

    def get_alerts(self, category=None, priority=None, unread_only=False,
                   limit=50, include_dismissed=False):
        """Get alerts with optional filtering."""
        _ensure_tables_initialized()

        db = get_db()
        try:
            query = 'SELECT * FROM alerts WHERE 1=1'
            params = []

            if not include_dismissed:
                query += ' AND dismissed_at IS NULL'

            if category:
                query += ' AND category = %s'
                params.append(category)

            if priority:
                query += ' AND priority = %s'
                params.append(priority)

            if unread_only:
                query += ' AND is_read = FALSE'

            query += ' AND (snoozed_until IS NULL OR snoozed_until < %s)'
            params.append(datetime.now())

            query += ' ORDER BY created_at DESC LIMIT %s'
            params.append(limit)

            rows = db.execute(query, params).fetchall()
        finally:
            db.close()

        alerts = []
        for row in rows:
            alert = dict(row)
            if alert.get('source_data'):
                try:
                    alert['source_data'] = json.loads(alert['source_data'])
                except Exception:
                    pass
            if alert.get('metadata'):
                try:
                    alert['metadata'] = json.loads(alert['metadata'])
                except Exception:
                    pass
            alerts.append(alert)
        return alerts

    def get_alert(self, alert_id):
        """Get a single alert by ID."""
        _ensure_tables_initialized()

        db = get_db()
        try:
            row = db.execute(
                'SELECT * FROM alerts WHERE id = %s', (alert_id,)
            ).fetchone()
        finally:
            db.close()

        if row:
            alert = dict(row)
            if alert.get('source_data'):
                try:
                    alert['source_data'] = json.loads(alert['source_data'])
                except Exception:
                    pass
            if alert.get('metadata'):
                try:
                    alert['metadata'] = json.loads(alert['metadata'])
                except Exception:
                    pass
            return alert
        return None

    def mark_read(self, alert_id):
        """Mark an alert as read."""
        _ensure_tables_initialized()
        db = get_db()
        try:
            db.execute('UPDATE alerts SET is_read = TRUE WHERE id = %s', (alert_id,))
            db.commit()
        finally:
            db.close()

    def acknowledge_alert(self, alert_id):
        """Acknowledge an alert."""
        _ensure_tables_initialized()
        db = get_db()
        try:
            db.execute(
                'UPDATE alerts SET acknowledged_at = %s, is_read = TRUE WHERE id = %s',
                (datetime.now(), alert_id)
            )
            db.commit()
        finally:
            db.close()

    def dismiss_alert(self, alert_id):
        """Dismiss an alert."""
        _ensure_tables_initialized()
        db = get_db()
        try:
            db.execute(
                'UPDATE alerts SET dismissed_at = %s WHERE id = %s',
                (datetime.now(), alert_id)
            )
            db.commit()
        finally:
            db.close()

    def snooze_alert(self, alert_id, hours=24):
        """Snooze an alert for specified hours."""
        _ensure_tables_initialized()
        snooze_until = datetime.now() + timedelta(hours=hours)
        db = get_db()
        try:
            db.execute(
                'UPDATE alerts SET snoozed_until = %s WHERE id = %s',
                (snooze_until, alert_id)
            )
            db.commit()
        finally:
            db.close()

    def action_alert(self, alert_id, action_taken):
        """Mark alert as actioned with description of action."""
        _ensure_tables_initialized()
        db = get_db()
        try:
            db.execute('''
                UPDATE alerts
                SET is_actioned = TRUE, action_taken = %s, acknowledged_at = %s
                WHERE id = %s
            ''', (action_taken, datetime.now(), alert_id))
            db.commit()
        finally:
            db.close()

    def get_alert_counts(self):
        """
        Get counts of alerts by category and priority.

        FIX (March 03, 2026): psycopg2 RealDictCursor returns dict-like rows.
        Integer index access (fetchone()[0]) raises KeyError: 0 on PostgreSQL.
        All COUNT(*) queries now use AS count alias so rows can be accessed
        by name (row['count']), which works on both PostgreSQL and SQLite.
        """
        _ensure_tables_initialized()

        counts = {
            'total_unread': 0,
            'by_category': {},
            'by_priority': {},
            'critical_count': 0,
            'high_count': 0
        }

        db = get_db()
        try:
            # COUNT(*) AS count — named alias required for psycopg2 RealDictCursor
            row = db.execute('''
                SELECT COUNT(*) AS count FROM alerts
                WHERE is_read = FALSE AND dismissed_at IS NULL
                AND (snoozed_until IS NULL OR snoozed_until < %s)
            ''', (datetime.now(),)).fetchone()
            counts['total_unread'] = row['count'] if row else 0

            cat_rows = db.execute('''
                SELECT category, COUNT(*) AS count FROM alerts
                WHERE dismissed_at IS NULL AND is_read = FALSE
                GROUP BY category
            ''').fetchall()
            for row in cat_rows:
                counts['by_category'][row['category']] = row['count']

            pri_rows = db.execute('''
                SELECT priority, COUNT(*) AS count FROM alerts
                WHERE dismissed_at IS NULL AND is_read = FALSE
                GROUP BY priority
            ''').fetchall()
            for row in pri_rows:
                counts['by_priority'][row['priority']] = row['count']
        finally:
            db.close()

        counts['critical_count'] = counts['by_priority'].get('critical', 0)
        counts['high_count'] = counts['by_priority'].get('high', 0)
        return counts


# =============================================================================
# JOB SCHEDULER
# =============================================================================

class JobScheduler:
    """Manages scheduled job execution."""

    def __init__(self):
        self.alert_manager = AlertManager()
        self.research_agent = None
        self._scheduler_thread = None
        self._running = False

        try:
            from research_agent import get_research_agent
            self.research_agent = get_research_agent()
            if self.research_agent.is_available:
                print("✅ Job Scheduler: Research Agent connected")
            else:
                print("ℹ️  Job Scheduler: Research Agent not available (no API key)")
        except ImportError:
            print("ℹ️  Job Scheduler: Research Agent not installed")

    def get_jobs(self, enabled_only=False):
        """Get all scheduled jobs."""
        _ensure_tables_initialized()

        db = get_db()
        try:
            if enabled_only:
                rows = db.execute('''
                    SELECT * FROM scheduled_jobs WHERE is_enabled = TRUE
                    ORDER BY schedule_time
                ''').fetchall()
            else:
                rows = db.execute(
                    'SELECT * FROM scheduled_jobs ORDER BY job_name'
                ).fetchall()
        finally:
            db.close()

        jobs = []
        for row in rows:
            job = dict(row)
            if job.get('config'):
                try:
                    job['config'] = json.loads(job['config'])
                except Exception:
                    pass
            jobs.append(job)
        return jobs

    def get_job(self, job_id):
        """Get a single job by ID."""
        _ensure_tables_initialized()

        db = get_db()
        try:
            row = db.execute(
                'SELECT * FROM scheduled_jobs WHERE id = %s', (job_id,)
            ).fetchone()
        finally:
            db.close()

        if row:
            job = dict(row)
            if job.get('config'):
                try:
                    job['config'] = json.loads(job['config'])
                except Exception:
                    pass
            return job
        return None

    def enable_job(self, job_id):
        """Enable a scheduled job."""
        _ensure_tables_initialized()
        db = get_db()
        try:
            db.execute(
                'UPDATE scheduled_jobs SET is_enabled = TRUE WHERE id = %s', (job_id,)
            )
            db.commit()
        finally:
            db.close()

    def disable_job(self, job_id):
        """Disable a scheduled job."""
        _ensure_tables_initialized()
        db = get_db()
        try:
            db.execute(
                'UPDATE scheduled_jobs SET is_enabled = FALSE WHERE id = %s', (job_id,)
            )
            db.commit()
        finally:
            db.close()

    def run_job_now(self, job_id):
        """Manually trigger a job to run immediately."""
        job = self.get_job(job_id)
        if not job:
            return {'success': False, 'error': 'Job not found'}
        return self._execute_job(job)

    def _execute_job(self, job):
        """Execute a single job."""
        job_type = job['job_type']
        config = job.get('config', {})

        db = get_db()
        try:
            cursor = db.execute('''
                INSERT INTO job_executions (job_id, status)
                VALUES (%s, 'running')
            ''', (job['id'],))
            execution_id = cursor.lastrowid
            db.commit()
        finally:
            db.close()

        alerts_generated = 0
        error_message = None
        execution_log = []

        try:
            execution_log.append(f"Starting job: {job['job_name']}")

            if job_type == 'lead_finder':
                alerts_generated = self._run_lead_finder(config, execution_log)
            elif job_type == 'regulatory_monitor':
                alerts_generated = self._run_regulatory_monitor(config, execution_log)
            elif job_type == 'competitor_monitor':
                alerts_generated = self._run_competitor_monitor(config, execution_log)
            elif job_type == 'daily_briefing':
                alerts_generated = self._run_daily_briefing(config, execution_log)
            elif job_type == 'client_news_monitor':
                alerts_generated = self._run_client_news_monitor(config, execution_log)
            else:
                error_message = f"Unknown job type: {job_type}"
                execution_log.append(error_message)

            execution_log.append(f"Job completed. Alerts generated: {alerts_generated}")

        except Exception as e:
            error_message = str(e)
            execution_log.append(f"Job failed: {error_message}")

        db = get_db()
        try:
            db.execute('''
                UPDATE job_executions
                SET completed_at = %s, status = %s, alerts_generated = %s,
                    error_message = %s, execution_log = %s
                WHERE id = %s
            ''', (
                datetime.now(),
                'failed' if error_message else 'completed',
                alerts_generated,
                error_message,
                '\n'.join(execution_log),
                execution_id
            ))
            db.execute('''
                UPDATE scheduled_jobs
                SET last_run_at = %s, last_result = %s
                WHERE id = %s
            ''', (
                datetime.now(),
                'failed' if error_message else 'success',
                job['id']
            ))
            db.commit()
        finally:
            db.close()

        return {
            'success': error_message is None,
            'alerts_generated': alerts_generated,
            'error': error_message,
            'log': execution_log
        }

    def _run_lead_finder(self, config, log):
        """Run lead finder job using Research Agent."""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping lead search")
            return 0

        alerts_created = 0
        industries = config.get('industries', ['manufacturing'])

        for industry in industries:
            log.append(f"Searching for leads in: {industry}")
            result = self.research_agent.search_potential_leads(industry=industry)

            if result['success'] and result.get('results'):
                for item in result['results'][:3]:
                    db = get_db()
                    try:
                        existing = db.execute(
                            'SELECT id FROM alerts WHERE source_url = %s',
                            (item.get('url'),)
                        ).fetchone()
                    finally:
                        db.close()

                    if not existing:
                        self.alert_manager.create_alert(
                            category=AlertCategory.LEAD,
                            title=f"Potential Lead: {item.get('title', 'Unknown')[:50]}",
                            summary=item.get('content', '')[:200],
                            priority=AlertPriority.HIGH,
                            details=item.get('content'),
                            source_url=item.get('url'),
                            source_data={'industry': industry, 'score': item.get('score')},
                            send_email=True
                        )
                        alerts_created += 1
                        log.append(f"  Created alert for: {item.get('title', 'Unknown')[:40]}")

        return alerts_created

    def _run_regulatory_monitor(self, config, log):
        """Run regulatory monitoring job."""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping regulatory search")
            return 0

        alerts_created = 0
        topics = config.get('topics', ['OSHA shift work'])

        for topic in topics:
            log.append(f"Checking regulatory updates for: {topic}")
            result = self.research_agent.search_regulations(topic=topic)

            if result['success'] and result.get('results'):
                for item in result['results'][:2]:
                    db = get_db()
                    try:
                        existing = db.execute(
                            'SELECT id FROM alerts WHERE source_url = %s',
                            (item.get('url'),)
                        ).fetchone()
                    finally:
                        db.close()

                    if not existing:
                        self.alert_manager.create_alert(
                            category=AlertCategory.REGULATORY,
                            title=f"Regulatory Update: {item.get('title', 'Unknown')[:50]}",
                            summary=item.get('content', '')[:200],
                            priority=AlertPriority.MEDIUM,
                            details=item.get('content'),
                            source_url=item.get('url'),
                            source_data={'topic': topic},
                            send_email=False
                        )
                        alerts_created += 1
                        log.append(f"  Created alert for: {item.get('title', 'Unknown')[:40]}")

        return alerts_created

    def _run_competitor_monitor(self, config, log):
        """Run competitor monitoring job."""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping competitor search")
            return 0

        alerts_created = 0
        log.append("Scanning competitor activity")
        result = self.research_agent.search_competitors()

        if result['success'] and result.get('results'):
            for item in result['results'][:5]:
                db = get_db()
                try:
                    existing = db.execute(
                        'SELECT id FROM alerts WHERE source_url = %s',
                        (item.get('url'),)
                    ).fetchone()
                finally:
                    db.close()

                if not existing:
                    self.alert_manager.create_alert(
                        category=AlertCategory.COMPETITOR,
                        title=f"Competitor Activity: {item.get('title', 'Unknown')[:50]}",
                        summary=item.get('content', '')[:200],
                        priority=AlertPriority.LOW,
                        details=item.get('content'),
                        source_url=item.get('url'),
                        send_email=False
                    )
                    alerts_created += 1
                    log.append(f"  Created alert for: {item.get('title', 'Unknown')[:40]}")

        return alerts_created

    def _run_daily_briefing(self, config, log):
        """Generate and email daily briefing."""
        log.append("Generating daily briefing email")
        yesterday = datetime.now() - timedelta(hours=24)

        db = get_db()
        try:
            alerts = db.execute('''
                SELECT * FROM alerts
                WHERE created_at >= %s AND dismissed_at IS NULL
                ORDER BY priority DESC, created_at DESC
            ''', (yesterday,)).fetchall()
        finally:
            db.close()

        if not alerts:
            log.append("No new alerts in last 24 hours")
            return 0

        by_category = {}
        for alert in alerts:
            cat = alert['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(dict(alert))

        if self.alert_manager.email_enabled:
            self._send_briefing_email(by_category, log)
            return 1
        else:
            log.append("Email not configured - briefing not sent")
            return 0

    def _send_briefing_email(self, alerts_by_category, log):
        """Send daily briefing email."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = (
                f"📰 Daily Intelligence Briefing - "
                f"{datetime.now().strftime('%B %d, %Y')}"
            )
            msg['From'] = ALERT_FROM_EMAIL
            msg['To'] = ALERT_TO_EMAIL

            category_titles = {
                AlertCategory.LEAD: '🎯 New Leads',
                AlertCategory.COMPETITOR: '🏢 Competitor Activity',
                AlertCategory.REGULATORY: '⚖️ Regulatory Updates',
                AlertCategory.CLIENT_NEWS: '📰 Client News',
                AlertCategory.INDUSTRY_TREND: '📈 Industry Trends',
                AlertCategory.SYSTEM: '⚙️ System Alerts'
            }

            html_sections = []
            for category, alerts in alerts_by_category.items():
                section_title = category_titles.get(category, category)
                items_html = ''
                for alert in alerts[:5]:
                    items_html += f'''
                        <div style="padding:10px; margin:5px 0; background:#f9f9f9;
                                    border-radius:6px; border-left:3px solid #667eea;">
                            <strong>{alert['title']}</strong><br>
                            <span style="font-size:13px; color:#666;">
                                {str(alert.get('summary',''))[:150]}...
                            </span>
                            {f'<br><a href="{alert["source_url"]}" style="font-size:12px; color:#667eea;">Read more</a>'
                              if alert.get('source_url') else ''}
                        </div>
                    '''
                html_sections.append(f'''
                    <div style="margin-bottom:25px;">
                        <h3 style="color:#333; border-bottom:2px solid #667eea;
                                   padding-bottom:5px;">{section_title}</h3>
                        {items_html}
                    </div>
                ''')

            html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <style>body{{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }}</style>
</head>
<body style="max-width:700px; margin:0 auto; padding:20px;">
    <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                color:white; padding:20px; border-radius:8px 8px 0 0;">
        <h1 style="margin:0;">📰 Daily Intelligence Briefing</h1>
        <p style="margin:5px 0 0 0; opacity:0.9;">
            {datetime.now().strftime('%A, %B %d, %Y')}
        </p>
    </div>
    <div style="padding:20px; border:1px solid #e0e0e0; border-top:none;
                border-radius:0 0 8px 8px;">
        {''.join(html_sections)}
        <hr style="border:none; border-top:1px solid #e0e0e0; margin:20px 0;">
        <p style="font-size:12px; color:#666; text-align:center;">
            View all alerts and manage subscriptions in the AI Swarm dashboard.
        </p>
    </div>
</body>
</html>
'''
            text_content = (
                f"Daily Intelligence Briefing - "
                f"{datetime.now().strftime('%B %d, %Y')}\n\n"
            )
            for category, alerts in alerts_by_category.items():
                text_content += f"\n{category.upper()}\n{'='*40}\n"
                for alert in alerts[:5]:
                    text_content += (
                        f"\n• {alert['title']}\n"
                        f"  {str(alert.get('summary',''))[:100]}...\n"
                    )

            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            log.append(f"Daily briefing sent to {ALERT_TO_EMAIL}")

        except Exception as e:
            log.append(f"Failed to send briefing: {e}")

    def _run_client_news_monitor(self, config, log):
        """Monitor news about clients."""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping client news")
            return 0

        db = get_db()
        try:
            clients = db.execute('''
                SELECT * FROM monitored_entities
                WHERE entity_type = 'client' AND is_enabled = TRUE
            ''').fetchall()
        finally:
            db.close()

        if not clients:
            log.append("No clients configured for monitoring")
            return 0

        alerts_created = 0
        for client in clients:
            client_name = client['entity_name']
            search_terms = client['search_terms'] or client_name
            log.append(f"Checking news for client: {client_name}")

            result = self.research_agent.search(
                query=f"{search_terms} news",
                search_depth="basic",
                max_results=3
            )

            if result['success'] and result.get('results'):
                for item in result['results']:
                    db = get_db()
                    try:
                        existing = db.execute(
                            'SELECT id FROM alerts WHERE source_url = %s',
                            (item.get('url'),)
                        ).fetchone()
                    finally:
                        db.close()

                    if not existing:
                        self.alert_manager.create_alert(
                            category=AlertCategory.CLIENT_NEWS,
                            title=f"Client News ({client_name}): {item.get('title','')[:40]}",
                            summary=item.get('content', '')[:200],
                            priority=AlertPriority.MEDIUM,
                            details=item.get('content'),
                            source_url=item.get('url'),
                            source_data={'client': client_name},
                            send_email=False
                        )
                        alerts_created += 1

            db = get_db()
            try:
                db.execute(
                    'UPDATE monitored_entities SET last_checked_at = %s WHERE id = %s',
                    (datetime.now(), client['id'])
                )
                db.commit()
            finally:
                db.close()

        return alerts_created


# =============================================================================
# MONITORED ENTITIES MANAGEMENT
# =============================================================================

def add_monitored_client(client_name, search_terms=None):
    """Add a client to monitor for news."""
    _ensure_tables_initialized()
    db = get_db()
    try:
        existing = db.execute(
            'SELECT id FROM monitored_entities WHERE entity_type = %s AND entity_name = %s',
            ('client', client_name)
        ).fetchone()
        if existing:
            return {'success': False, 'error': 'Client already being monitored'}

        db.execute('''
            INSERT INTO monitored_entities (entity_type, entity_name, search_terms)
            VALUES (%s, %s, %s)
        ''', ('client', client_name, search_terms))
        db.commit()
    finally:
        db.close()

    return {'success': True, 'message': f'Now monitoring: {client_name}'}


def add_monitored_competitor(competitor_name, search_terms=None):
    """Add a competitor to monitor."""
    _ensure_tables_initialized()
    db = get_db()
    try:
        existing = db.execute(
            'SELECT id FROM monitored_entities WHERE entity_type = %s AND entity_name = %s',
            ('competitor', competitor_name)
        ).fetchone()
        if existing:
            return {'success': False, 'error': 'Competitor already being monitored'}

        db.execute('''
            INSERT INTO monitored_entities (entity_type, entity_name, search_terms)
            VALUES (%s, %s, %s)
        ''', ('competitor', competitor_name, search_terms))
        db.commit()
    finally:
        db.close()

    return {'success': True, 'message': f'Now monitoring competitor: {competitor_name}'}


def get_monitored_entities(entity_type=None):
    """Get all monitored entities."""
    _ensure_tables_initialized()
    db = get_db()
    try:
        if entity_type:
            rows = db.execute(
                'SELECT * FROM monitored_entities WHERE entity_type = %s',
                (entity_type,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM monitored_entities').fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def remove_monitored_entity(entity_id):
    """Remove a monitored entity."""
    _ensure_tables_initialized()
    db = get_db()
    try:
        db.execute('DELETE FROM monitored_entities WHERE id = %s', (entity_id,))
        db.commit()
    finally:
        db.close()
    return {'success': True}


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_alert_manager = None
_job_scheduler = None


def get_alert_manager():
    """Get or create the alert manager singleton."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def get_job_scheduler():
    """Get or create the job scheduler singleton."""
    global _job_scheduler
    if _job_scheduler is None:
        _job_scheduler = JobScheduler()
    return _job_scheduler

# I did no harm and this file is not truncated
