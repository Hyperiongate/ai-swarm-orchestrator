"""
ALERT SYSTEM - Autonomous Monitoring & Notification Engine
Created: January 23, 2026
Last Updated: January 23, 2026

PURPOSE:
This module provides autonomous monitoring and alerting capabilities for the AI Swarm.
It runs scheduled jobs to monitor various intelligence sources and delivers alerts
via email and the dashboard.

FEATURES:
- Scheduled job execution (daily, weekly, custom intervals)
- Multiple alert categories (leads, competitors, regulations, client news)
- Email delivery via SMTP (SendGrid, Gmail, or custom SMTP)
- Alert prioritization (critical, high, medium, low)
- Alert management (acknowledge, dismiss, snooze)
- Configurable monitoring rules
- Integration with Research Agent for data gathering

ALERT CATEGORIES:
1. LEAD_ALERT - Potential clients discussing scheduling problems
2. COMPETITOR_ALERT - Competitor activity and changes
3. REGULATORY_ALERT - OSHA, labor law, compliance updates
4. CLIENT_NEWS_ALERT - News about current/past clients
5. INDUSTRY_TREND_ALERT - Significant industry changes
6. SYSTEM_ALERT - Internal system notifications

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

# =============================================================================
# CONFIGURATION
# =============================================================================

# Email Configuration (from environment variables)
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.sendgrid.net')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'apikey')  # SendGrid uses 'apikey' as username
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or os.environ.get('SENDGRID_API_KEY')
ALERT_FROM_EMAIL = os.environ.get('ALERT_FROM_EMAIL', 'alerts@shiftworksolutions.com')
ALERT_TO_EMAIL = os.environ.get('ALERT_TO_EMAIL', '')  # Jim's email

# Alert Configuration
ALERT_CHECK_INTERVAL_MINUTES = int(os.environ.get('ALERT_CHECK_INTERVAL', 60))  # Check every hour
ENABLE_EMAIL_ALERTS = os.environ.get('ENABLE_EMAIL_ALERTS', 'false').lower() == 'true'
ENABLE_SCHEDULED_JOBS = os.environ.get('ENABLE_SCHEDULED_JOBS', 'false').lower() == 'true'

# Alert Categories
class AlertCategory:
    LEAD = 'lead_alert'
    COMPETITOR = 'competitor_alert'
    REGULATORY = 'regulatory_alert'
    CLIENT_NEWS = 'client_news_alert'
    INDUSTRY_TREND = 'industry_trend_alert'
    SYSTEM = 'system_alert'

# Alert Priorities
class AlertPriority:
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_alert_tables():
    """Initialize alert-related database tables"""
    db = get_db()
    
    # Alerts table - stores all alerts
    db.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            is_read BOOLEAN DEFAULT 0,
            is_actioned BOOLEAN DEFAULT 0,
            action_taken TEXT,
            metadata TEXT
        )
    ''')
    
    # Scheduled jobs table - defines what jobs to run
    db.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT UNIQUE NOT NULL,
            job_type TEXT NOT NULL,
            schedule_type TEXT DEFAULT 'daily',
            schedule_time TEXT DEFAULT '07:00',
            schedule_days TEXT DEFAULT 'mon,tue,wed,thu,fri',
            is_enabled BOOLEAN DEFAULT 1,
            last_run_at TIMESTAMP,
            next_run_at TIMESTAMP,
            last_result TEXT,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Job execution log - tracks each job run
    db.execute('''
        CREATE TABLE IF NOT EXISTS job_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            alerts_generated INTEGER DEFAULT 0,
            error_message TEXT,
            execution_log TEXT,
            FOREIGN KEY (job_id) REFERENCES scheduled_jobs(id)
        )
    ''')
    
    # Alert subscriptions - what alerts to send to whom
    db.execute('''
        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            category TEXT,
            priority_threshold TEXT DEFAULT 'medium',
            is_enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Monitored entities - clients, competitors, topics to watch
    db.execute('''
        CREATE TABLE IF NOT EXISTS monitored_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            search_terms TEXT,
            is_enabled BOOLEAN DEFAULT 1,
            last_checked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_category ON alerts(category)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_priority ON alerts(priority)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, dismissed_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON scheduled_jobs(next_run_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_monitored_type ON monitored_entities(entity_type)')
    
    db.commit()
    db.close()
    
    # Initialize default scheduled jobs
    _init_default_jobs()
    
    print("✅ Alert system tables initialized")


def _init_default_jobs():
    """Create default scheduled jobs if they don't exist"""
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
    for job in default_jobs:
        existing = db.execute(
            'SELECT id FROM scheduled_jobs WHERE job_name = ?',
            (job['job_name'],)
        ).fetchone()
        
        if not existing:
            db.execute('''
                INSERT INTO scheduled_jobs (job_name, job_type, schedule_type, 
                    schedule_time, schedule_days, config, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (
                job['job_name'], job['job_type'], job['schedule_type'],
                job['schedule_time'], job['schedule_days'], job['config']
            ))
    
    db.commit()
    db.close()


# =============================================================================
# ALERT MANAGEMENT
# =============================================================================

class AlertManager:
    """Manages creation, delivery, and lifecycle of alerts"""
    
    def __init__(self):
        self.email_enabled = ENABLE_EMAIL_ALERTS and SMTP_PASSWORD and ALERT_TO_EMAIL
        if self.email_enabled:
            print(f"✅ Alert email delivery enabled (to: {ALERT_TO_EMAIL})")
        else:
            print("ℹ️  Alert email delivery disabled (configure SMTP settings to enable)")
    
    def create_alert(self, category, title, summary, priority=AlertPriority.MEDIUM,
                     details=None, source_url=None, source_data=None, metadata=None,
                     send_email=True):
        """
        Create a new alert and optionally send email notification.
        
        Args:
            category: Alert category (use AlertCategory constants)
            title: Short alert title
            summary: Brief description
            priority: Alert priority (use AlertPriority constants)
            details: Full details (can be HTML)
            source_url: URL where this info was found
            source_data: Raw data from source (JSON)
            metadata: Additional metadata (JSON)
            send_email: Whether to send email notification
        
        Returns:
            alert_id: ID of created alert
        """
        db = get_db()
        
        cursor = db.execute('''
            INSERT INTO alerts (category, priority, title, summary, details, 
                source_url, source_data, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            category, priority, title, summary, details,
            source_url,
            json.dumps(source_data) if source_data else None,
            json.dumps(metadata) if metadata else None
        ))
        
        alert_id = cursor.lastrowid
        db.commit()
        db.close()
        
        print(f"🔔 Alert created: [{priority.upper()}] {title}")
        
        # Send email if enabled and priority warrants it
        if send_email and self.email_enabled:
            if priority in [AlertPriority.CRITICAL, AlertPriority.HIGH]:
                self._send_alert_email(alert_id, category, priority, title, summary, details, source_url)
        
        return alert_id
    
    def _send_alert_email(self, alert_id, category, priority, title, summary, details, source_url):
        """Send email notification for an alert"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{priority.upper()}] {title} - Shiftwork Solutions Alert"
            msg['From'] = ALERT_FROM_EMAIL
            msg['To'] = ALERT_TO_EMAIL
            
            # Plain text version
            text_content = f"""
ALERT: {title}
Priority: {priority.upper()}
Category: {category}

{summary}

{details or ''}

{f'Source: {source_url}' if source_url else ''}

---
View all alerts: https://your-swarm-url.onrender.com/
"""
            
            # HTML version
            priority_colors = {
                'critical': '#d32f2f',
                'high': '#f57c00',
                'medium': '#1976d2',
                'low': '#388e3c'
            }
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .alert-box {{ 
            max-width: 600px; 
            margin: 20px auto; 
            border: 1px solid #e0e0e0; 
            border-radius: 8px;
            overflow: hidden;
        }}
        .alert-header {{
            background: {priority_colors.get(priority, '#1976d2')};
            color: white;
            padding: 15px 20px;
        }}
        .alert-body {{ padding: 20px; }}
        .alert-meta {{ font-size: 12px; color: #666; margin-top: 15px; }}
        .btn {{
            display: inline-block;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            margin-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="alert-box">
        <div class="alert-header">
            <strong>🔔 {priority.upper()} ALERT</strong>
        </div>
        <div class="alert-body">
            <h2 style="margin-top: 0;">{title}</h2>
            <p>{summary}</p>
            {f'<div style="padding: 15px; background: #f5f5f5; border-radius: 6px; margin: 15px 0;">{details}</div>' if details else ''}
            {f'<p><a href="{source_url}" style="color: #667eea;">🔗 View Source</a></p>' if source_url else ''}
            <div class="alert-meta">
                <p>Category: {category}<br>
                Alert ID: {alert_id}<br>
                Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
            
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            
            # Update alert with email sent timestamp
            db = get_db()
            db.execute('UPDATE alerts SET emailed_at = ? WHERE id = ?', 
                      (datetime.now(), alert_id))
            db.commit()
            db.close()
            
            print(f"📧 Alert email sent to {ALERT_TO_EMAIL}")
            
        except Exception as e:
            print(f"⚠️ Failed to send alert email: {e}")
    
    def get_alerts(self, category=None, priority=None, unread_only=False, 
                   limit=50, include_dismissed=False):
        """Get alerts with optional filtering"""
        db = get_db()
        
        query = 'SELECT * FROM alerts WHERE 1=1'
        params = []
        
        if not include_dismissed:
            query += ' AND dismissed_at IS NULL'
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        if priority:
            query += ' AND priority = ?'
            params.append(priority)
        
        if unread_only:
            query += ' AND is_read = 0'
        
        # Exclude snoozed alerts that haven't expired
        query += ' AND (snoozed_until IS NULL OR snoozed_until < ?)'
        params.append(datetime.now())
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        rows = db.execute(query, params).fetchall()
        db.close()
        
        alerts = []
        for row in rows:
            alert = dict(row)
            if alert.get('source_data'):
                try:
                    alert['source_data'] = json.loads(alert['source_data'])
                except:
                    pass
            if alert.get('metadata'):
                try:
                    alert['metadata'] = json.loads(alert['metadata'])
                except:
                    pass
            alerts.append(alert)
        
        return alerts
    
    def get_alert(self, alert_id):
        """Get a single alert by ID"""
        db = get_db()
        row = db.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,)).fetchone()
        db.close()
        
        if row:
            alert = dict(row)
            if alert.get('source_data'):
                try:
                    alert['source_data'] = json.loads(alert['source_data'])
                except:
                    pass
            if alert.get('metadata'):
                try:
                    alert['metadata'] = json.loads(alert['metadata'])
                except:
                    pass
            return alert
        return None
    
    def mark_read(self, alert_id):
        """Mark an alert as read"""
        db = get_db()
        db.execute('UPDATE alerts SET is_read = 1 WHERE id = ?', (alert_id,))
        db.commit()
        db.close()
    
    def acknowledge_alert(self, alert_id):
        """Acknowledge an alert"""
        db = get_db()
        db.execute('UPDATE alerts SET acknowledged_at = ?, is_read = 1 WHERE id = ?', 
                  (datetime.now(), alert_id))
        db.commit()
        db.close()
    
    def dismiss_alert(self, alert_id):
        """Dismiss an alert"""
        db = get_db()
        db.execute('UPDATE alerts SET dismissed_at = ? WHERE id = ?', 
                  (datetime.now(), alert_id))
        db.commit()
        db.close()
    
    def snooze_alert(self, alert_id, hours=24):
        """Snooze an alert for specified hours"""
        snooze_until = datetime.now() + timedelta(hours=hours)
        db = get_db()
        db.execute('UPDATE alerts SET snoozed_until = ? WHERE id = ?', 
                  (snooze_until, alert_id))
        db.commit()
        db.close()
    
    def action_alert(self, alert_id, action_taken):
        """Mark alert as actioned with description of action"""
        db = get_db()
        db.execute('''
            UPDATE alerts SET is_actioned = 1, action_taken = ?, acknowledged_at = ?
            WHERE id = ?
        ''', (action_taken, datetime.now(), alert_id))
        db.commit()
        db.close()
    
    def get_alert_counts(self):
        """Get counts of alerts by category and priority"""
        db = get_db()
        
        counts = {
            'total_unread': 0,
            'by_category': {},
            'by_priority': {},
            'critical_count': 0,
            'high_count': 0
        }
        
        # Total unread (not dismissed, not snoozed)
        counts['total_unread'] = db.execute('''
            SELECT COUNT(*) FROM alerts 
            WHERE is_read = 0 AND dismissed_at IS NULL 
            AND (snoozed_until IS NULL OR snoozed_until < ?)
        ''', (datetime.now(),)).fetchone()[0]
        
        # By category
        cat_rows = db.execute('''
            SELECT category, COUNT(*) as count FROM alerts 
            WHERE dismissed_at IS NULL AND is_read = 0
            GROUP BY category
        ''').fetchall()
        for row in cat_rows:
            counts['by_category'][row['category']] = row['count']
        
        # By priority
        pri_rows = db.execute('''
            SELECT priority, COUNT(*) as count FROM alerts 
            WHERE dismissed_at IS NULL AND is_read = 0
            GROUP BY priority
        ''').fetchall()
        for row in pri_rows:
            counts['by_priority'][row['priority']] = row['count']
        
        counts['critical_count'] = counts['by_priority'].get('critical', 0)
        counts['high_count'] = counts['by_priority'].get('high', 0)
        
        db.close()
        return counts


# =============================================================================
# JOB SCHEDULER
# =============================================================================

class JobScheduler:
    """Manages scheduled job execution"""
    
    def __init__(self):
        self.alert_manager = AlertManager()
        self.research_agent = None
        self._scheduler_thread = None
        self._running = False
        
        # Try to get research agent
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
        """Get all scheduled jobs"""
        db = get_db()
        
        if enabled_only:
            rows = db.execute('''
                SELECT * FROM scheduled_jobs WHERE is_enabled = 1 
                ORDER BY schedule_time
            ''').fetchall()
        else:
            rows = db.execute('SELECT * FROM scheduled_jobs ORDER BY job_name').fetchall()
        
        db.close()
        
        jobs = []
        for row in rows:
            job = dict(row)
            if job.get('config'):
                try:
                    job['config'] = json.loads(job['config'])
                except:
                    pass
            jobs.append(job)
        
        return jobs
    
    def get_job(self, job_id):
        """Get a single job by ID"""
        db = get_db()
        row = db.execute('SELECT * FROM scheduled_jobs WHERE id = ?', (job_id,)).fetchone()
        db.close()
        
        if row:
            job = dict(row)
            if job.get('config'):
                try:
                    job['config'] = json.loads(job['config'])
                except:
                    pass
            return job
        return None
    
    def enable_job(self, job_id):
        """Enable a scheduled job"""
        db = get_db()
        db.execute('UPDATE scheduled_jobs SET is_enabled = 1 WHERE id = ?', (job_id,))
        db.commit()
        db.close()
    
    def disable_job(self, job_id):
        """Disable a scheduled job"""
        db = get_db()
        db.execute('UPDATE scheduled_jobs SET is_enabled = 0 WHERE id = ?', (job_id,))
        db.commit()
        db.close()
    
    def run_job_now(self, job_id):
        """Manually trigger a job to run immediately"""
        job = self.get_job(job_id)
        if not job:
            return {'success': False, 'error': 'Job not found'}
        
        return self._execute_job(job)
    
    def _execute_job(self, job):
        """Execute a single job"""
        job_type = job['job_type']
        config = job.get('config', {})
        
        # Log job start
        db = get_db()
        cursor = db.execute('''
            INSERT INTO job_executions (job_id, status)
            VALUES (?, 'running')
        ''', (job['id'],))
        execution_id = cursor.lastrowid
        db.commit()
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
        
        # Update execution record
        db = get_db()
        db.execute('''
            UPDATE job_executions 
            SET completed_at = ?, status = ?, alerts_generated = ?, 
                error_message = ?, execution_log = ?
            WHERE id = ?
        ''', (
            datetime.now(),
            'failed' if error_message else 'completed',
            alerts_generated,
            error_message,
            '\n'.join(execution_log),
            execution_id
        ))
        
        # Update job's last run time
        db.execute('''
            UPDATE scheduled_jobs 
            SET last_run_at = ?, last_result = ?
            WHERE id = ?
        ''', (
            datetime.now(),
            'failed' if error_message else 'success',
            job['id']
        ))
        
        db.commit()
        db.close()
        
        return {
            'success': error_message is None,
            'alerts_generated': alerts_generated,
            'error': error_message,
            'log': execution_log
        }
    
    def _run_lead_finder(self, config, log):
        """Run lead finder job using Research Agent"""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping lead search")
            return 0
        
        alerts_created = 0
        industries = config.get('industries', ['manufacturing'])
        
        for industry in industries:
            log.append(f"Searching for leads in: {industry}")
            
            result = self.research_agent.search_potential_leads(industry=industry)
            
            if result['success'] and result.get('results'):
                for item in result['results'][:3]:  # Top 3 per industry
                    # Check if we already have this alert (by URL)
                    db = get_db()
                    existing = db.execute(
                        'SELECT id FROM alerts WHERE source_url = ?',
                        (item.get('url'),)
                    ).fetchone()
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
        """Run regulatory monitoring job"""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping regulatory search")
            return 0
        
        alerts_created = 0
        topics = config.get('topics', ['OSHA shift work'])
        
        for topic in topics:
            log.append(f"Checking regulatory updates for: {topic}")
            
            result = self.research_agent.search_regulations(topic=topic)
            
            if result['success'] and result.get('results'):
                for item in result['results'][:2]:  # Top 2 per topic
                    # Check for duplicates
                    db = get_db()
                    existing = db.execute(
                        'SELECT id FROM alerts WHERE source_url = ?',
                        (item.get('url'),)
                    ).fetchone()
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
                            send_email=False  # Don't email for each, use briefing
                        )
                        alerts_created += 1
                        log.append(f"  Created alert for: {item.get('title', 'Unknown')[:40]}")
        
        return alerts_created
    
    def _run_competitor_monitor(self, config, log):
        """Run competitor monitoring job"""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping competitor search")
            return 0
        
        alerts_created = 0
        log.append("Scanning competitor activity")
        
        result = self.research_agent.search_competitors()
        
        if result['success'] and result.get('results'):
            for item in result['results'][:5]:  # Top 5 competitor items
                # Check for duplicates
                db = get_db()
                existing = db.execute(
                    'SELECT id FROM alerts WHERE source_url = ?',
                    (item.get('url'),)
                ).fetchone()
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
        """Generate and email daily briefing"""
        log.append("Generating daily briefing email")
        
        # Get unread alerts from last 24 hours
        db = get_db()
        yesterday = datetime.now() - timedelta(hours=24)
        
        alerts = db.execute('''
            SELECT * FROM alerts 
            WHERE created_at >= ? AND dismissed_at IS NULL
            ORDER BY priority DESC, created_at DESC
        ''', (yesterday,)).fetchall()
        db.close()
        
        if not alerts:
            log.append("No new alerts in last 24 hours")
            return 0
        
        # Group alerts by category
        by_category = {}
        for alert in alerts:
            cat = alert['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(dict(alert))
        
        # Generate email
        if self.alert_manager.email_enabled:
            self._send_briefing_email(by_category, log)
            return 1
        else:
            log.append("Email not configured - briefing not sent")
            return 0
    
    def _send_briefing_email(self, alerts_by_category, log):
        """Send daily briefing email"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📰 Daily Intelligence Briefing - {datetime.now().strftime('%B %d, %Y')}"
            msg['From'] = ALERT_FROM_EMAIL
            msg['To'] = ALERT_TO_EMAIL
            
            # Build HTML content
            html_sections = []
            
            category_titles = {
                AlertCategory.LEAD: '🎯 New Leads',
                AlertCategory.COMPETITOR: '🏢 Competitor Activity',
                AlertCategory.REGULATORY: '⚖️ Regulatory Updates',
                AlertCategory.CLIENT_NEWS: '📰 Client News',
                AlertCategory.INDUSTRY_TREND: '📈 Industry Trends',
                AlertCategory.SYSTEM: '⚙️ System Alerts'
            }
            
            for category, alerts in alerts_by_category.items():
                section_title = category_titles.get(category, category)
                items_html = ''
                for alert in alerts[:5]:  # Max 5 per category
                    items_html += f'''
                        <div style="padding: 10px; margin: 5px 0; background: #f9f9f9; border-radius: 6px; border-left: 3px solid #667eea;">
                            <strong>{alert['title']}</strong><br>
                            <span style="font-size: 13px; color: #666;">{alert['summary'][:150]}...</span>
                            {f'<br><a href="{alert["source_url"]}" style="font-size: 12px; color: #667eea;">Read more</a>' if alert.get('source_url') else ''}
                        </div>
                    '''
                
                html_sections.append(f'''
                    <div style="margin-bottom: 25px;">
                        <h3 style="color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">{section_title}</h3>
                        {items_html}
                    </div>
                ''')
            
            html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    </style>
</head>
<body style="max-width: 700px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0;">📰 Daily Intelligence Briefing</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    <div style="padding: 20px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
        {''.join(html_sections)}
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
        <p style="font-size: 12px; color: #666; text-align: center;">
            View all alerts and manage subscriptions in the AI Swarm dashboard.
        </p>
    </div>
</body>
</html>
'''
            
            # Plain text version
            text_content = f"Daily Intelligence Briefing - {datetime.now().strftime('%B %d, %Y')}\n\n"
            for category, alerts in alerts_by_category.items():
                text_content += f"\n{category.upper()}\n{'='*40}\n"
                for alert in alerts[:5]:
                    text_content += f"\n• {alert['title']}\n  {alert['summary'][:100]}...\n"
            
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
        """Monitor news about clients"""
        if not self.research_agent or not self.research_agent.is_available:
            log.append("Research Agent not available - skipping client news")
            return 0
        
        # Get monitored clients
        db = get_db()
        clients = db.execute('''
            SELECT * FROM monitored_entities 
            WHERE entity_type = 'client' AND is_enabled = 1
        ''').fetchall()
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
                    # Check for duplicates
                    db = get_db()
                    existing = db.execute(
                        'SELECT id FROM alerts WHERE source_url = ?',
                        (item.get('url'),)
                    ).fetchone()
                    db.close()
                    
                    if not existing:
                        self.alert_manager.create_alert(
                            category=AlertCategory.CLIENT_NEWS,
                            title=f"Client News ({client_name}): {item.get('title', '')[:40]}",
                            summary=item.get('content', '')[:200],
                            priority=AlertPriority.MEDIUM,
                            details=item.get('content'),
                            source_url=item.get('url'),
                            source_data={'client': client_name},
                            send_email=False
                        )
                        alerts_created += 1
            
            # Update last checked
            db = get_db()
            db.execute(
                'UPDATE monitored_entities SET last_checked_at = ? WHERE id = ?',
                (datetime.now(), client['id'])
            )
            db.commit()
            db.close()
        
        return alerts_created


# =============================================================================
# MONITORED ENTITIES MANAGEMENT
# =============================================================================

def add_monitored_client(client_name, search_terms=None):
    """Add a client to monitor for news"""
    db = get_db()
    
    existing = db.execute(
        'SELECT id FROM monitored_entities WHERE entity_type = ? AND entity_name = ?',
        ('client', client_name)
    ).fetchone()
    
    if existing:
        db.close()
        return {'success': False, 'error': 'Client already being monitored'}
    
    db.execute('''
        INSERT INTO monitored_entities (entity_type, entity_name, search_terms)
        VALUES (?, ?, ?)
    ''', ('client', client_name, search_terms))
    
    db.commit()
    db.close()
    
    return {'success': True, 'message': f'Now monitoring: {client_name}'}


def add_monitored_competitor(competitor_name, search_terms=None):
    """Add a competitor to monitor"""
    db = get_db()
    
    existing = db.execute(
        'SELECT id FROM monitored_entities WHERE entity_type = ? AND entity_name = ?',
        ('competitor', competitor_name)
    ).fetchone()
    
    if existing:
        db.close()
        return {'success': False, 'error': 'Competitor already being monitored'}
    
    db.execute('''
        INSERT INTO monitored_entities (entity_type, entity_name, search_terms)
        VALUES (?, ?, ?)
    ''', ('competitor', competitor_name, search_terms))
    
    db.commit()
    db.close()
    
    return {'success': True, 'message': f'Now monitoring competitor: {competitor_name}'}


def get_monitored_entities(entity_type=None):
    """Get all monitored entities"""
    db = get_db()
    
    if entity_type:
        rows = db.execute(
            'SELECT * FROM monitored_entities WHERE entity_type = ?',
            (entity_type,)
        ).fetchall()
    else:
        rows = db.execute('SELECT * FROM monitored_entities').fetchall()
    
    db.close()
    return [dict(row) for row in rows]


def remove_monitored_entity(entity_id):
    """Remove a monitored entity"""
    db = get_db()
    db.execute('DELETE FROM monitored_entities WHERE id = ?', (entity_id,))
    db.commit()
    db.close()
    return {'success': True}


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_alert_manager = None
_job_scheduler = None

def get_alert_manager():
    """Get or create the alert manager singleton"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager

def get_job_scheduler():
    """Get or create the job scheduler singleton"""
    global _job_scheduler
    if _job_scheduler is None:
        _job_scheduler = JobScheduler()
    return _job_scheduler


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Initialize tables when module is imported
try:
    init_alert_tables()
except Exception as e:
    print(f"⚠️ Alert system initialization warning: {e}")


# I did no harm and this file is not truncated
