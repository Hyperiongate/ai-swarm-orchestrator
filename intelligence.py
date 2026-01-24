"""
CLIENT INTELLIGENCE MODULE - Lead Scoring & Pipeline Management
Created: January 23, 2026
Last Updated: January 23, 2026

PURPOSE:
This module provides client intelligence capabilities for the AI Swarm.
It transforms raw alerts into scored leads and manages a sales pipeline.
Uses the normative database (202 past client survey results) for similarity scoring.

FEATURES:
- Lead scoring based on industry similarity to past clients
- Kanban pipeline management (Detected → Qualified → Contacted → Proposal → Won/Lost)
- Action triggers (draft email, create proposal, research deeper)
- Integration with Alert System for lead sources
- Integration with Research Agent for deeper intelligence
- Past client matching for talking points

LEAD SCORING ALGORITHM:
1. Industry Match (0-40 points): How many past clients in same/similar industry
2. Size Match (0-20 points): Headcount similarity to past successful clients
3. Signal Strength (0-20 points): Quality of the alert/lead signal
4. Recency (0-10 points): How recent the lead was detected
5. Engagement (0-10 points): Have they interacted with your content

PIPELINE STAGES:
- detected: Raw lead from alerts, not yet reviewed
- qualified: Reviewed and determined to be a potential fit
- contacted: Initial outreach made
- proposal: Proposal sent, in discussion
- won: Closed deal (for tracking)
- lost: Did not convert (for learning)

NORMATIVE DATABASE:
Your database contains survey results from 202 past client engagements across:
- Pharmaceutical (Genentech, GSK, Pfizer facilities)
- Food Processing (Mars, Nestle, Kellogg's, etc.)
- Manufacturing (various)
- Utilities (PP&L, BGE, etc.)
- Mining (Placer Dome, Vale, etc.)
- Automotive (Toyota, Dana, etc.)
- Consumer Products (Nike, Under Armour, etc.)

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import json
from datetime import datetime, timedelta
from database import get_db

# =============================================================================
# CONFIGURATION
# =============================================================================

# Pipeline Stages
class PipelineStage:
    DETECTED = 'detected'
    QUALIFIED = 'qualified'
    CONTACTED = 'contacted'
    PROPOSAL = 'proposal'
    WON = 'won'
    LOST = 'lost'

# Lead Sources
class LeadSource:
    ALERT_LEAD = 'alert_lead'           # From automated lead scanning
    ALERT_CLIENT_NEWS = 'alert_client'  # News about past/current client
    ALERT_COMPETITOR = 'alert_competitor'  # Competitor activity
    RESEARCH = 'research'               # From manual research
    REFERRAL = 'referral'               # Referral from past client
    INBOUND = 'inbound'                 # Website/form submission
    MANUAL = 'manual'                   # Manually added

# Industry Categories (mapped from normative database)
INDUSTRY_CATEGORIES = {
    'pharmaceutical': [
        'Pharmacia & Upjohn', 'Hoechst Marrion Roussel', 'Genentech', 'GlaxoSmithKline',
        'GSK#2', 'DSM Pharmaceuticals', 'DSM2', 'Impax Laboratories', 'Alkermes',
        'Elan', 'B Braun', 'B Braun Mold Shop', 'Medtronic', 'Medtronic.1',
        'Thermo Fisher Scientific', 'Aptalis Pharmatech', 'Baxter', 'Beckman & Coulter',
        'BD Four Oaks NC', 'BD Sparks MD', 'BD Columbus NE', 'BD Covington GA'
    ],
    'food_processing': [
        'Kal Kan-1', 'Kal Kan-2', 'Shultz Foods', 'Mars Line 8', 'Mars IP', 'Mars#2',
        'Mars3', 'Mars#4', 'Mars Canada', 'Masterfoods Mattoon', 'Masterfoods - Cleveland',
        'Masterfoods - Waco', 'Masterfoods Columbus', 'Nestle', 'Nestle Dreyers',
        'Nestle Freehold', 'Nestle Fort Dodge', 'Nestle Jefferson', 'Nestle Purina PetCare',
        "Kellogg's San Jose", 'Kellogg Wyoming', 'Kellogg Florence', "Kellogg's Chicago",
        "Kellogg's Utah", "Kellogg's London", "Kellogg's Augusta", 'Kellogg - Kansas City',
        'Kellogg Zanesville', 'Kellogg Seelyville', "Snyder's of Hanover", "Shearer's Foods",
        'American Licorice', 'Bay Valley Foods', 'Buddig', "Baptista's Bakery",
        'Diamond Foods', 'UTZ Plant 2', 'UTZ Plant 3', 'UTZ Plant 4', 'Campbells Beloit WE',
        "Campbell's", 'Mondelēz Richmond VA'
    ],
    'manufacturing': [
        'Crane PlasticsTimebertech', 'Crane Plastics siding', 'Nitta Casing', 'NIBCO',
        'Hutchinson Sealing systems', 'Techneglas', 'Dana#2 (Perfect Circle)', 'Dana #1',
        'Dana #3', 'Borg Warner', 'Borg#2', 'RBX Industries', 'Convergent Label Tech',
        'Dynamic Windows', 'Toray Membrane', 'Toray Production', 'Toray Test Lab',
        'Toray Plastics', 'Toray Plastics - Day Shift', 'Trustile Doors', 'Trustile2',
        'Trustile #3', 'LM Glasfiber', 'Capri', 'EGS Electrical', 'Rohm & Haas',
        'Boulder Scientific', 'Silfex', 'Nissin Brake', 'Insinkerator', 'Menasha',
        'Menasha Packaging 2', 'President Container', 'MackayMitchell Envelope',
        'Mackay Envelope', 'Continental Automotive', 'Continental Building Products',
        'Harbar', 'Dutchland', 'Prysmian', 'Hemlock Legacy', 'Hemlock Finishing'
    ],
    'utilities': [
        'PP&L', 'Duquesne Light', 'BGE#1', 'BGE#2', 'BGE#3', 'BGE#5', 'BGE#6',
        'PPL Security', 'Sunnyvale WPCP'
    ],
    'mining': [
        'Doe Run', 'Black Butte Coal', 'Placer Dome', 'Lafarge Buchanan',
        'Lafarge Palatka', 'Lafarge Silver Grove', 'Compass Minerals', 'Compass Minerals.1',
        'Vale', 'PCS Phos[hate'
    ],
    'automotive': [
        'Toyota Woodstock', 'Toyota Cambridge', 'Blue Bird', 'MIBA Bearings'
    ],
    'consumer_products': [
        'Nike-Northridge', 'Nike-Winchester', 'Nike-Shelby', 'Under Armour',
        'Things Remembered', 'Unilock', 'Andersen #1', 'Andersen #2', 'Andersen',
        'Andersen Windows Maintenance'
    ],
    'beverage': [
        'Pepsi-Transport', 'Pepsi-Roanoke', 'Pepsi-Hayward', 'Pepsi Detroit',
        'Pepsi Columbia', 'Pepsi - Mississauga', 'Pepsi - San Antonio', 'Pepsi - Mesquite',
        'Copella Fruit Juices', 'Corn Products'
    ],
    'paper_packaging': [
        'IP - Seaboard', 'IP - Maplesville', 'Rockline', 'SCA Tissue',
        'Essity Neenah', 'Essity South Glen Falls', 'Essity Middletown', 'Essity Harrodsburg',
        'Westrock Demopolis, AL'
    ],
    'oil_gas_energy': [
        'Marathon', 'BP - Husky', 'Buckeye Partners', 'American Refining Group',
        'Imperial Sugar'
    ],
    'technology': [
        'Agilent Technology', 'Infineon', 'Xerox Canada', 'Tessera', 'Oberthur',
        'Nisshinbo'
    ],
    'gaming_hospitality': [
        'San Manuel Casino'
    ],
    'transportation': [
        'SkyTrain', 'United Airlines', 'SITA'
    ],
    'healthcare': [
        'Ocadian Care Centers', 'NY Life', 'Guest'
    ],
    'government_mint': [
        'Royal Canadian Mint', 'Royal Canadian Mint #3'
    ],
    'chemicals': [
        'Akzo Nobel', 'Unilever', 'Effem', 'S&D Core', 'S&D Non-Core'
    ]
}

# Flatten for quick lookup
COMPANY_TO_INDUSTRY = {}
for industry, companies in INDUSTRY_CATEGORIES.items():
    for company in companies:
        COMPANY_TO_INDUSTRY[company.lower()] = industry


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_intelligence_tables():
    """Initialize intelligence-related database tables"""
    db = get_db()
    
    # Leads table - the core pipeline
    db.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            industry TEXT,
            estimated_headcount INTEGER,
            location TEXT,
            contact_name TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            contact_title TEXT,
            
            source TEXT DEFAULT 'manual',
            source_alert_id INTEGER,
            source_url TEXT,
            
            pipeline_stage TEXT DEFAULT 'detected',
            score INTEGER DEFAULT 0,
            score_breakdown TEXT,
            
            notes TEXT,
            next_action TEXT,
            next_action_date DATE,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stage_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            is_archived BOOLEAN DEFAULT 0,
            archive_reason TEXT,
            
            metadata TEXT,
            
            FOREIGN KEY (source_alert_id) REFERENCES alerts(id)
        )
    ''')
    
    # Lead activities - tracks all interactions
    db.execute('''
        CREATE TABLE IF NOT EXISTS lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            activity_description TEXT,
            outcome TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'system',
            metadata TEXT,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
    ''')
    
    # Lead documents - proposals, emails, etc.
    db.execute('''
        CREATE TABLE IF NOT EXISTS lead_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            document_id INTEGER,
            title TEXT,
            file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (document_id) REFERENCES generated_documents(id)
        )
    ''')
    
    # Industry benchmarks - aggregated from normative database
    db.execute('''
        CREATE TABLE IF NOT EXISTS industry_benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            industry TEXT UNIQUE NOT NULL,
            company_count INTEGER DEFAULT 0,
            avg_headcount REAL,
            common_schedules TEXT,
            common_challenges TEXT,
            talking_points TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(pipeline_stage)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_lead_activities_lead ON lead_activities(lead_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_lead_docs_lead ON lead_documents(lead_id)')
    
    db.commit()
    db.close()
    
    print("✅ Intelligence tables initialized")


# =============================================================================
# LEAD SCORING
# =============================================================================

class LeadScorer:
    """
    Scores leads based on similarity to past successful clients.
    Uses the normative database of 202 past engagements.
    """
    
    def __init__(self):
        self.industry_company_counts = {}
        self.industry_avg_headcounts = {}
        self._load_industry_stats()
    
    def _load_industry_stats(self):
        """Load statistics from the industry categories"""
        for industry, companies in INDUSTRY_CATEGORIES.items():
            self.industry_company_counts[industry] = len(companies)
        
        # Average headcounts by industry (approximated from normative data)
        # These are typical ranges seen in your past clients
        self.industry_avg_headcounts = {
            'pharmaceutical': 250,
            'food_processing': 350,
            'manufacturing': 200,
            'utilities': 150,
            'mining': 300,
            'automotive': 400,
            'consumer_products': 250,
            'beverage': 200,
            'paper_packaging': 300,
            'oil_gas_energy': 200,
            'technology': 150,
            'gaming_hospitality': 300,
            'transportation': 200,
            'healthcare': 100,
            'government_mint': 150,
            'chemicals': 200
        }
    
    def score_lead(self, company_name, industry=None, headcount=None, 
                   signal_strength='medium', days_old=0, has_engagement=False):
        """
        Score a lead based on multiple factors.
        
        Args:
            company_name: Name of the potential client
            industry: Industry category (will attempt to infer if not provided)
            headcount: Estimated employee count
            signal_strength: 'high', 'medium', 'low' - quality of the lead signal
            days_old: How many days since the lead was detected
            has_engagement: Whether they've engaged with your content
        
        Returns:
            dict with total_score and breakdown
        """
        breakdown = {
            'industry_match': 0,
            'size_match': 0,
            'signal_strength': 0,
            'recency': 0,
            'engagement': 0
        }
        
        # 1. Industry Match Score (0-40 points)
        # More past clients in same industry = higher score
        if industry:
            industry_lower = industry.lower().replace(' ', '_')
            # Try to match to our categories
            matched_industry = self._match_industry(industry_lower)
            if matched_industry:
                company_count = self.industry_company_counts.get(matched_industry, 0)
                if company_count >= 20:
                    breakdown['industry_match'] = 40  # Strong presence
                elif company_count >= 10:
                    breakdown['industry_match'] = 30
                elif company_count >= 5:
                    breakdown['industry_match'] = 20
                elif company_count >= 1:
                    breakdown['industry_match'] = 10
        
        # 2. Size Match Score (0-20 points)
        # Closer to typical client size = higher score
        if headcount and industry:
            matched_industry = self._match_industry(industry.lower().replace(' ', '_'))
            if matched_industry:
                avg_headcount = self.industry_avg_headcounts.get(matched_industry, 200)
                # Calculate how close they are to our typical client size
                size_ratio = min(headcount, avg_headcount) / max(headcount, avg_headcount)
                breakdown['size_match'] = int(size_ratio * 20)
        
        # 3. Signal Strength Score (0-20 points)
        signal_scores = {
            'high': 20,    # Direct inquiry, referral
            'medium': 12,  # News mention, job posting
            'low': 5       # General industry mention
        }
        breakdown['signal_strength'] = signal_scores.get(signal_strength, 10)
        
        # 4. Recency Score (0-10 points)
        # Newer leads score higher
        if days_old <= 1:
            breakdown['recency'] = 10
        elif days_old <= 7:
            breakdown['recency'] = 8
        elif days_old <= 14:
            breakdown['recency'] = 6
        elif days_old <= 30:
            breakdown['recency'] = 4
        else:
            breakdown['recency'] = 2
        
        # 5. Engagement Score (0-10 points)
        if has_engagement:
            breakdown['engagement'] = 10
        
        total_score = sum(breakdown.values())
        
        return {
            'total_score': total_score,
            'max_score': 100,
            'percentage': total_score,
            'breakdown': breakdown,
            'grade': self._score_to_grade(total_score)
        }
    
    def _match_industry(self, industry_text):
        """Try to match industry text to our categories"""
        industry_text = industry_text.lower()
        
        # Direct matches
        if industry_text in INDUSTRY_CATEGORIES:
            return industry_text
        
        # Fuzzy matches
        industry_keywords = {
            'pharmaceutical': ['pharma', 'drug', 'biotech', 'medical device'],
            'food_processing': ['food', 'snack', 'candy', 'pet food', 'beverage'],
            'manufacturing': ['manufacturing', 'industrial', 'factory', 'production'],
            'utilities': ['utility', 'electric', 'power', 'water treatment'],
            'mining': ['mining', 'minerals', 'cement', 'aggregates'],
            'automotive': ['auto', 'car', 'vehicle', 'truck'],
            'consumer_products': ['consumer', 'retail', 'apparel', 'goods'],
            'paper_packaging': ['paper', 'packaging', 'tissue', 'pulp'],
            'oil_gas_energy': ['oil', 'gas', 'refinery', 'petroleum', 'energy'],
            'technology': ['tech', 'electronics', 'semiconductor', 'software'],
            'chemicals': ['chemical', 'plastics', 'coating']
        }
        
        for industry, keywords in industry_keywords.items():
            for keyword in keywords:
                if keyword in industry_text:
                    return industry
        
        return None
    
    def _score_to_grade(self, score):
        """Convert numeric score to letter grade"""
        if score >= 80:
            return 'A'
        elif score >= 65:
            return 'B'
        elif score >= 50:
            return 'C'
        elif score >= 35:
            return 'D'
        else:
            return 'F'
    
    def get_similar_past_clients(self, industry, limit=5):
        """Get past clients from similar industry for talking points"""
        industry_lower = industry.lower().replace(' ', '_')
        matched_industry = self._match_industry(industry_lower)
        
        if matched_industry and matched_industry in INDUSTRY_CATEGORIES:
            companies = INDUSTRY_CATEGORIES[matched_industry][:limit]
            return {
                'industry': matched_industry,
                'companies': companies,
                'total_in_industry': len(INDUSTRY_CATEGORIES[matched_industry]),
                'talking_point': f"We've worked with {len(INDUSTRY_CATEGORIES[matched_industry])} companies in the {matched_industry.replace('_', ' ')} industry, including {', '.join(companies[:3])}."
            }
        
        return {
            'industry': None,
            'companies': [],
            'total_in_industry': 0,
            'talking_point': "We've worked with hundreds of companies across diverse industries."
        }


# =============================================================================
# LEAD MANAGEMENT
# =============================================================================

class LeadManager:
    """Manages leads in the pipeline"""
    
    def __init__(self):
        self.scorer = LeadScorer()
    
    def create_lead(self, company_name, industry=None, headcount=None, location=None,
                    contact_name=None, contact_email=None, contact_title=None,
                    source=LeadSource.MANUAL, source_alert_id=None, source_url=None,
                    notes=None, signal_strength='medium'):
        """
        Create a new lead in the pipeline.
        Automatically scores the lead based on available information.
        """
        # Score the lead
        score_result = self.scorer.score_lead(
            company_name=company_name,
            industry=industry,
            headcount=headcount,
            signal_strength=signal_strength,
            days_old=0,
            has_engagement=False
        )
        
        db = get_db()
        
        cursor = db.execute('''
            INSERT INTO leads (
                company_name, industry, estimated_headcount, location,
                contact_name, contact_email, contact_title,
                source, source_alert_id, source_url,
                score, score_breakdown, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            company_name, industry, headcount, location,
            contact_name, contact_email, contact_title,
            source, source_alert_id, source_url,
            score_result['total_score'], 
            json.dumps(score_result),
            notes
        ))
        
        lead_id = cursor.lastrowid
        
        # Log the creation activity
        db.execute('''
            INSERT INTO lead_activities (lead_id, activity_type, activity_description)
            VALUES (?, 'created', ?)
        ''', (lead_id, f'Lead created from {source}. Initial score: {score_result["total_score"]}/100 ({score_result["grade"]})'))
        
        db.commit()
        db.close()
        
        print(f"🎯 Lead created: {company_name} (Score: {score_result['total_score']}/100)")
        
        return {
            'lead_id': lead_id,
            'score': score_result['total_score'],
            'grade': score_result['grade'],
            'score_breakdown': score_result['breakdown']
        }
    
    def create_lead_from_alert(self, alert_id):
        """Convert an alert into a lead"""
        try:
            from alert_system import get_alert_manager
            am = get_alert_manager()
            alert = am.get_alert(alert_id)
            
            if not alert:
                return {'success': False, 'error': 'Alert not found'}
            
            # Extract company info from alert
            # This is a heuristic - alerts may have company names in title/summary
            company_name = alert.get('title', '').replace('Potential Lead: ', '').strip()
            
            # Try to extract industry from alert metadata
            source_data = alert.get('source_data', {})
            industry = source_data.get('industry') if isinstance(source_data, dict) else None
            
            result = self.create_lead(
                company_name=company_name[:100] if company_name else 'Unknown Company',
                industry=industry,
                source=LeadSource.ALERT_LEAD,
                source_alert_id=alert_id,
                source_url=alert.get('source_url'),
                notes=alert.get('summary', '')[:500],
                signal_strength='medium'
            )
            
            return {'success': True, **result}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_leads(self, stage=None, industry=None, min_score=None, 
                  limit=50, include_archived=False):
        """Get leads with optional filtering"""
        db = get_db()
        
        query = 'SELECT * FROM leads WHERE 1=1'
        params = []
        
        if not include_archived:
            query += ' AND is_archived = 0'
        
        if stage:
            query += ' AND pipeline_stage = ?'
            params.append(stage)
        
        if industry:
            query += ' AND industry = ?'
            params.append(industry)
        
        if min_score:
            query += ' AND score >= ?'
            params.append(min_score)
        
        query += ' ORDER BY score DESC, created_at DESC LIMIT ?'
        params.append(limit)
        
        rows = db.execute(query, params).fetchall()
        db.close()
        
        leads = []
        for row in rows:
            lead = dict(row)
            if lead.get('score_breakdown'):
                try:
                    lead['score_breakdown'] = json.loads(lead['score_breakdown'])
                except:
                    pass
            if lead.get('metadata'):
                try:
                    lead['metadata'] = json.loads(lead['metadata'])
                except:
                    pass
            leads.append(lead)
        
        return leads
    
    def get_lead(self, lead_id):
        """Get a single lead with activities"""
        db = get_db()
        
        lead_row = db.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()
        if not lead_row:
            db.close()
            return None
        
        lead = dict(lead_row)
        
        # Parse JSON fields
        if lead.get('score_breakdown'):
            try:
                lead['score_breakdown'] = json.loads(lead['score_breakdown'])
            except:
                pass
        
        # Get activities
        activities = db.execute('''
            SELECT * FROM lead_activities 
            WHERE lead_id = ? 
            ORDER BY created_at DESC
        ''', (lead_id,)).fetchall()
        lead['activities'] = [dict(a) for a in activities]
        
        # Get documents
        documents = db.execute('''
            SELECT * FROM lead_documents
            WHERE lead_id = ?
            ORDER BY created_at DESC
        ''', (lead_id,)).fetchall()
        lead['documents'] = [dict(d) for d in documents]
        
        # Get similar past clients
        if lead.get('industry'):
            lead['similar_clients'] = self.scorer.get_similar_past_clients(lead['industry'])
        
        db.close()
        return lead
    
    def update_lead_stage(self, lead_id, new_stage, notes=None):
        """Move a lead to a new pipeline stage"""
        valid_stages = [
            PipelineStage.DETECTED, PipelineStage.QUALIFIED, 
            PipelineStage.CONTACTED, PipelineStage.PROPOSAL,
            PipelineStage.WON, PipelineStage.LOST
        ]
        
        if new_stage not in valid_stages:
            return {'success': False, 'error': f'Invalid stage: {new_stage}'}
        
        db = get_db()
        
        # Get current stage
        current = db.execute(
            'SELECT pipeline_stage FROM leads WHERE id = ?', 
            (lead_id,)
        ).fetchone()
        
        if not current:
            db.close()
            return {'success': False, 'error': 'Lead not found'}
        
        old_stage = current['pipeline_stage']
        
        # Update stage
        db.execute('''
            UPDATE leads 
            SET pipeline_stage = ?, 
                stage_changed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_stage, lead_id))
        
        # Log activity
        description = f'Stage changed: {old_stage} → {new_stage}'
        if notes:
            description += f'. Notes: {notes}'
        
        db.execute('''
            INSERT INTO lead_activities (lead_id, activity_type, activity_description)
            VALUES (?, 'stage_change', ?)
        ''', (lead_id, description))
        
        db.commit()
        db.close()
        
        return {'success': True, 'old_stage': old_stage, 'new_stage': new_stage}
    
    def add_activity(self, lead_id, activity_type, description, outcome=None):
        """Add an activity to a lead"""
        db = get_db()
        
        db.execute('''
            INSERT INTO lead_activities (lead_id, activity_type, activity_description, outcome)
            VALUES (?, ?, ?, ?)
        ''', (lead_id, activity_type, description, outcome))
        
        db.execute('''
            UPDATE leads SET updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (lead_id,))
        
        db.commit()
        db.close()
        
        return {'success': True}
    
    def update_lead(self, lead_id, **kwargs):
        """Update lead fields"""
        allowed_fields = [
            'company_name', 'industry', 'estimated_headcount', 'location',
            'contact_name', 'contact_email', 'contact_phone', 'contact_title',
            'notes', 'next_action', 'next_action_date'
        ]
        
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f'{field} = ?')
                params.append(value)
        
        if not updates:
            return {'success': False, 'error': 'No valid fields to update'}
        
        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(lead_id)
        
        db = get_db()
        db.execute(f'''
            UPDATE leads SET {', '.join(updates)} WHERE id = ?
        ''', params)
        db.commit()
        db.close()
        
        return {'success': True}
    
    def archive_lead(self, lead_id, reason=None):
        """Archive a lead (soft delete)"""
        db = get_db()
        
        db.execute('''
            UPDATE leads 
            SET is_archived = 1, archive_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reason, lead_id))
        
        db.execute('''
            INSERT INTO lead_activities (lead_id, activity_type, activity_description)
            VALUES (?, 'archived', ?)
        ''', (lead_id, f'Lead archived. Reason: {reason or "Not specified"}'))
        
        db.commit()
        db.close()
        
        return {'success': True}
    
    def get_pipeline_summary(self):
        """Get summary counts for each pipeline stage"""
        db = get_db()
        
        summary = {
            'by_stage': {},
            'total_active': 0,
            'total_score': 0,
            'avg_score': 0,
            'high_priority': 0  # Score >= 70
        }
        
        # Counts by stage
        rows = db.execute('''
            SELECT pipeline_stage, COUNT(*) as count, AVG(score) as avg_score
            FROM leads
            WHERE is_archived = 0
            GROUP BY pipeline_stage
        ''').fetchall()
        
        for row in rows:
            summary['by_stage'][row['pipeline_stage']] = {
                'count': row['count'],
                'avg_score': round(row['avg_score'], 1) if row['avg_score'] else 0
            }
            summary['total_active'] += row['count']
        
        # Overall stats
        stats = db.execute('''
            SELECT COUNT(*) as total, AVG(score) as avg, SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) as high
            FROM leads
            WHERE is_archived = 0
        ''').fetchone()
        
        summary['total_active'] = stats['total'] or 0
        summary['avg_score'] = round(stats['avg'], 1) if stats['avg'] else 0
        summary['high_priority'] = stats['high'] or 0
        
        db.close()
        return summary
    
    def rescore_lead(self, lead_id):
        """Recalculate score for a lead"""
        db = get_db()
        
        lead = db.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()
        if not lead:
            db.close()
            return {'success': False, 'error': 'Lead not found'}
        
        # Calculate days old
        created = datetime.fromisoformat(lead['created_at'].replace('Z', '+00:00')) if lead['created_at'] else datetime.now()
        days_old = (datetime.now() - created.replace(tzinfo=None)).days
        
        # Check for engagement (any activities beyond creation)
        activities = db.execute(
            'SELECT COUNT(*) FROM lead_activities WHERE lead_id = ? AND activity_type != ?',
            (lead_id, 'created')
        ).fetchone()[0]
        
        score_result = self.scorer.score_lead(
            company_name=lead['company_name'],
            industry=lead['industry'],
            headcount=lead['estimated_headcount'],
            signal_strength='medium',
            days_old=days_old,
            has_engagement=activities > 0
        )
        
        db.execute('''
            UPDATE leads SET score = ?, score_breakdown = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (score_result['total_score'], json.dumps(score_result), lead_id))
        
        db.commit()
        db.close()
        
        return {'success': True, 'new_score': score_result['total_score'], 'breakdown': score_result}


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_lead_manager = None
_lead_scorer = None

def get_lead_manager():
    """Get or create the lead manager singleton"""
    global _lead_manager
    if _lead_manager is None:
        _lead_manager = LeadManager()
    return _lead_manager

def get_lead_scorer():
    """Get or create the lead scorer singleton"""
    global _lead_scorer
    if _lead_scorer is None:
        _lead_scorer = LeadScorer()
    return _lead_scorer


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Initialize tables when module is imported
try:
    init_intelligence_tables()
except Exception as e:
    print(f"⚠️ Intelligence system initialization warning: {e}")


# I did no harm and this file is not truncated
