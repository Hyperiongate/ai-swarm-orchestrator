✅ Research Agent initialized with Tavily API
✅ Research Agent routes loaded
[2026-03-05 00:41:45 +0000] [59] [INFO] Starting gunicorn 25.1.0
[2026-03-05 00:41:45 +0000] [59] [INFO] Listening at: http://0.0.0.0:10000 (59)
[2026-03-05 00:41:45 +0000] [59] [INFO] Using worker: sync
[2026-03-05 00:41:45 +0000] [59] [INFO] Control socket listening at /opt/render/project/src/gunicorn.ctl
==> Your service is live 🎉
==> 
==> ///////////////////////////////////////////////////////////
[GET]
ai-swarm-orchestrator.onrender.com/ clientIP="35.197.118.178" requestID="32c7760a-6e6e-4328" responseTimeMS=17 responseBytes=223158 userAgent="Go-http-client/2.0"
==> 
==> Available at your primary URL https://ai-swarm-orchestrator.onrender.com
==> 
==> ///////////////////////////////////////////////////////////
==> No open HTTP ports detected on 0.0.0.0, continuing to scan...
==> No open HTTP ports detected on 0.0.0.0, continuing to scan...
==> No open HTTP ports detected on 0.0.0.0, continuing to scan...
[GET]
ai-swarm-orchestrator.onrender.com/api/stats clientIP="216.131.83.55" requestID="dd4c2034-d6bc-4398" responseTimeMS=126825 responseBytes=29 userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
[GET]
ai-swarm-orchestrator.onrender.com/api/documents clientIP="216.131.83.55" requestID="06760fa3-e3c7-4c11" responseTimeMS=46744 responseBytes=29 userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
[GET]
ai-swarm-orchestrator.onrender.com/api/learning/stats clientIP="216.131.83.55" requestID="c5217dbf-a8fc-464b" responseTimeMS=126688 responseBytes=29 userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
[GET]
ai-swarm-orchestrator.onrender.com/api/learning/stats clientIP="216.131.83.55" requestID="7a2da895-db2d-4054" responseTimeMS=46918 responseBytes=29 userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
[GET]
ai-swarm-orchestrator.onrender.com/api/documents clientIP="216.131.83.55" requestID="f6df0fb9-3452-49c0" responseTimeMS=126705 responseBytes=29 userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
[GET]
ai-swarm-orchestrator.onrender.com/api/stats clientIP="216.131.83.55" requestID="ca96c84f-1f97-47ed" responseTimeMS=46751 responseBytes=29 userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
[GET]
ai-swarm-orchestrator.onrender.com/ clientIP="216.131.83.55" requestID="c6a19b3d-ff54-4686" responseTimeMS=6719 responseBytes=29 userAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
==> No open HTTP ports detected on 0.0.0.0, continuing to scan...
==> No open HTTP ports detected on 0.0.0.0, continuing to scan...
==> Deploying...
[2026-03-05 00:46:19 +0000] [59] [INFO] Handling signal: term
Research Agent API registered
[GET]
ai-swarm-orchestrator.onrender.com/ clientIP="35.197.117.9" requestID="309aad5c-4075-4fe1" responseTimeMS=20 responseBytes=223158 userAgent="Go-http-client/2.0"
==> Your service is live 🎉
==> 
==> ///////////////////////////////////////////////////////////
==> 
==> Available at your primary URL https://ai-swarm-orchestrator.onrender.com
==> 
==> ///////////////////////////////////////////////////////////
==> Running 'gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 180'
File Upload Limit: 100MB (allows large project files)
============================================================
🔄 STEP 1: Running database migration...
🗄️  DB Engine: PostgreSQL (production)
🔄 Running migration 001_initial_schema (Phase 9) on postgresql...
✅ PostgreSQL connection pool created (min=2, max=40)
✅ Migration 001 (Phase 9) complete: 56/56 tables verified on postgresql
✅ Database migration complete
============================================================
✅ Database tables already initialized by migration (STEP 1 in app.py)
✅ Survey tables verified/initialized
Survey tables initialized
Running legacy database migrations...
🔄 Migrating projects table...
   ℹ️  Projects table doesn't exist - will be created by ProjectManager
DEBUG: About to attempt blog_posts migration import...
DEBUG: Import successful, calling function...
📊 Blog Posts Migration: Checking /mnt/project/swarm_intelligence.db...
ℹ️  blog_posts table exists - checking for SEO columns...
   Current columns: id, topic, topic_display, title, url_slug, meta_description, content, angle, created_at, updated_at
   ✓ url_slug exists
   ✓ meta_description exists
✅ blog_posts table already has all SEO columns
✅ Blog Posts table migration complete!
Blog Posts table migration complete!
Error upgrading database: syntax error at or near "PRAGMA"
LINE 1: PRAGMA table_info(projects)
        ^
Error creating table: syntax error at or near "AUTOINCREMENT"
LINE 3:                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                               ^
Improvement reports migration: No module named 'add_improvement_reports_table'
✅ conversation_context table created
Conversation context table added!
✅ user_profiles table created!
Error creating tables: syntax error at or near "AUTOINCREMENT"
LINE 3:                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                               ^
Error creating table: syntax error at or near "AUTOINCREMENT"
LINE 3:                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                               ^
  ✅ add_missing_columns: Added 16 columns: case_studies.problem_summary, case_studies.solution_summary, blog_posts.topic_display, blog_posts.url_slug, blog_posts.meta_description, blog_posts.word_count, blog_posts.seo_title, blog_posts.author_name, blog_posts.tags, projects.project_id, projects.project_phase, projects.storage_path, projects.checklist_data, projects.milestone_data, projects.folder_data, projects.metadata
============================================================
🔧 Phase 9b: Fixing broken table schemas...
============================================================
  ✓ generated_documents OK
  ✓ user_feedback OK
  ✓ introspection_insights OK
  ✓ conversations OK
  ✓ conversation_messages OK
  ✓ tasks OK
  ✓ specialist_calls OK
  ✓ escalations OK
  ✓ learning_patterns OK
  ✓ learning_records OK
  ✓ avoidance_patterns OK
  ✓ smart_analyzer_state OK
  ✓ analysis_sessions OK
  ✓ background_jobs OK
  ✓ proactive_suggestions OK
  ✓ conversation_summaries OK
  ✓ user_patterns OK
  ✓ consensus_validations OK
============================================================
✅ Phase 9b complete:
   Tables fixed: 0
   Tables OK:    18
============================================================
============================================================
🔧 Phase 9c: Fixing missing SERIAL sequences...
============================================================
  Sequences fixed: 0
  Sequences OK:    52
============================================================
============================================================
🔧 Phase 9d: Adding missing boolean columns...
============================================================
  Columns added: 0
  Columns OK:    11
============================================================
Database migrations complete!
Initializing Bulletproof Project Management...
================================================================================
🔧 INITIALIZING PROJECT MANAGER - STORAGE DIAGNOSTICS
================================================================================
   ✅ Using STORAGE_ROOT from environment: /mnt/project/swarm_projects
✅ FINAL STORAGE LOCATION: /mnt/project/swarm_projects
================================================================================
✅ Storage directory exists and is writable: /mnt/project/swarm_projects
================================================================================
Bulletproof Project Manager initialized
Initializing Project Knowledge Base...
Found directory: project_files (40 files)
Starting knowledge base initialization in background thread...
   Gunicorn will accept connections immediately.
   Knowledge search will be available in ~30 seconds.
Initializing ENHANCED Project Knowledge Base...
Knowledge Base initializing in background (~30 seconds)...
App is ready to serve requests immediately.
Pattern-Based Schedule Generator loaded
Output Formatter loaded
  Found 40 files at project_files — proceeding with indexing.
  Indexed: Implementation Manual Sample.docx (4354 words)
  Indexed: Definitive Schedules.xlsx (7687 words)
  Indexed: conients.docx (15 words)
  Indexed: Data Collection.docx (142 words)
  Indexed: Implementation_Manual_Sample_2.docx (3965 words)
  Indexed: Data_Collection.docx (186 words)
  Indexed: Cost of time .xlsx (942 words)
  Indexed: Scope_of_work_by_AI.docx (586 words)
  Indexed: The_Code (4349 words)
  Indexed: Knowledge_base_from_pages (4650 words)
  Indexed: Jims_bio.docx (228 words)
  Indexed: Shiftwork_Solutions_Lessons_Learned.md (18027 words)
  Indexed: Shiftwork Work-Life Balance Survey.docx (2081 words)
  Indexed: Overall_summary (4068 words)
  Indexed: Copy of Kelloggs Math.xlsx (1126 words)
  Indexed: executive summary_SKECHERS_2025.docx (482 words)
  Indexed: Implementation_Manual_Sample.docx (4402 words)
  Indexed: Shiftwork_Solutions_LLC_Company_Profile_-_All_Industry__002_.docx (721 words)
  Indexed: Shiftwork_Solutions_LLC_-_Contract.docx (1727 words)
  Indexed: Definitive_Schedules_v2.xlsx (10832 words)
  Indexed: Project_kickoff_bulletin.docx (309 words)
  Indexed: Implementation Manual.docx (4354 words)
  Indexed: Schedule_Survey_.docx (2386 words)
  Indexed: Implementation_Manual.docx (4402 words)
  Indexed: README.md (4 words)
  Indexed: ACME_Implementation_Manual (1).docx (3427 words)
📚 [task_analysis] Knowledge Management DB path: /mnt/project/knowledge_ingestion.db
Survey Builder not available
Marketing Hub loaded for API endpoints
Opportunity Finder loaded for API endpoints
Project Manager loaded for API endpoints
    Error extracting THE_ESSENTIAL_GUIDE_TO_SHIFTWORK_OPERATIONS_EXCELLENCE.pdf: EOF marker not found
  Indexed: Session_Handoff_SwingShift.docx (1763 words)
  Indexed: Survey_evaluation (5246 words)
  Indexed: About Shiftwork Solutions.docx (1148 words)
  Indexed: Contract_without_name_Corp_A_2025.docx (1699 words)
  Indexed: Definitive Schedules v2.xlsx (9296 words)
  Indexed: Implementation Manual Sample 2.docx (3921 words)
  Indexed: Cost of time Best.xlsx (4103 words)
  Indexed: Example_Client_facing_executive_summary_Andersen_2025.docx (500 words)
  Indexing complete: 34 indexed, 0 errors
  Building semantic search index...
  Semantic index built: 5351 terms
============================================================
KNOWLEDGE BASE INITIALIZATION COMPLETE
  Source path  : project_files
  Files found  : 40
  Docs indexed : 34
  Unique terms : 5351
============================================================
Orchestration Handler API registered
DEBUG: About to import bulletproof project routes...
🔄 Force reloading ProjectManager singleton...
================================================================================
🔧 INITIALIZING PROJECT MANAGER - STORAGE DIAGNOSTICS
================================================================================
   ✅ Using STORAGE_ROOT from environment: /mnt/project/swarm_projects
✅ FINAL STORAGE LOCATION: /mnt/project/swarm_projects
[2026-03-05 00:47:23 +0000] [59] [INFO] Starting gunicorn 25.1.0
[2026-03-05 00:47:23 +0000] [59] [INFO] Listening at: http://0.0.0.0:10000 (59)
[2026-03-05 00:47:23 +0000] [59] [INFO] Using worker: sync
[2026-03-05 00:47:23 +0000] [59] [INFO] Control socket listening at /opt/render/project/src/gunicorn.ctl
[2026-03-05 00:47:23 +0000] [79] [INFO] Booting worker with pid: 79
================================================================================
✅ Storage directory exists and is writable: /mnt/project/swarm_projects
================================================================================
🔄 ProjectManager loaded with storage: /mnt/project/swarm_projects
Bulletproof Project Management API registered
Voice Control WebSocket registered
✅ Research Agent initialized with Tavily API
✅ Research Agent routes loaded
Research Agent API registered
ℹ️  Alert email delivery disabled (configure SMTP settings to enable)
ℹ️  Alert email delivery disabled (configure SMTP settings to enable)
✅ Job Scheduler: Research Agent connected
✅ Alert System routes loaded
Alert System API registered
✅ Intelligence tables initialized
✅ Intelligence routes loaded
Intelligence Dashboard API registered
Content Marketing Engine API registered
Avatar Consultation System API registered
✅ Swarm Self-Evaluation Engine loaded
Swarm Self-Evaluation API registered
✅ Introspection Layer loaded
Introspection Layer API registered
✅ Implementation manual generator tables initialized
Implementation Manual Generator API registered
Adaptive Learning Engine API registered
Predictive Intelligence API registered
Self-Optimization Engine routes not found: No module named 'self_optimization_engine'
✅ Knowledge Ingestion: Direct import succeeded
Knowledge Ingestion API registered
Unified Conversation Learning API registered
Pattern Recognition API registered
Phase 1 Intelligence API registered
  [CaseStudy] case_studies table ready
[CaseStudies] Case Study Generator loaded successfully
Case Study Generator API registered
[BlogPosts] Blog Post Generator loaded successfully with SEO enhancement
Blog Post Generator API registered
Background File Processor API registered
Knowledge Backup routes not found: No module named 'knowledge_backup_routes'
Project Dashboard API registered
Analytics API registered
Workflow Engine API registered
Integration Hub API registered
============================================================
AI Swarm Orchestrator Starting
Workers: 2
Timeout: 180 seconds
Graceful Timeout: 200 seconds
============================================================
AI Swarm Orchestrator ready - accepting connections
Timeout configured: 180s
[KeepAlive] Keep-alive thread started in worker 79
127.0.0.1 - - [05/Mar/2026:00:47:24 +0000] "HEAD / HTTP/1.1" 200 0 "-" "Go-http-client/1.1" 23856
==> New primary port detected: 10000. Restarting deploy to update network configuration...
==> Docs on specifying a port: https://render.com/docs/web-services#port-binding
[2026-03-05 00:48:03 +0000] [59] [INFO] Handling signal: term
[2026-03-05 00:48:03 +0000] [79] [INFO] Worker exiting (pid: 79)
[2026-03-05 00:48:03 +0000] [59] [INFO] Shutting down: Master
✅ Storage directory exists and is writable: /mnt/project/swarm_projects
================================================================================
🔄 ProjectManager loaded with storage: /mnt/project/swarm_projects
Bulletproof Project Management API registered
Voice Control WebSocket registered
✅ Research Agent initialized with Tavily API
✅ Research Agent routes loaded
Research Agent API registered
ℹ️  Alert email delivery disabled (configure SMTP settings to enable)
ℹ️  Alert email delivery disabled (configure SMTP settings to enable)
✅ Job Scheduler: Research Agent connected
✅ Alert System routes loaded
Alert System API registered
✅ Intelligence tables initialized
✅ Intelligence routes loaded
Intelligence Dashboard API registered
Content Marketing Engine API registered
Avatar Consultation System API registered
✅ Swarm Self-Evaluation Engine loaded
Swarm Self-Evaluation API registered
✅ Introspection Layer loaded
Introspection Layer API registered
✅ Implementation manual generator tables initialized
Implementation Manual Generator API registered
Adaptive Learning Engine API registered
Predictive Intelligence API registered
Self-Optimization Engine routes not found: No module named 'self_optimization_engine'
✅ Knowledge Ingestion: Direct import succeeded
Knowledge Ingestion API registered
Unified Conversation Learning API registered
Pattern Recognition API registered
Phase 1 Intelligence API registered
  [CaseStudy] case_studies table ready
[CaseStudies] Case Study Generator loaded successfully
Case Study Generator API registered
[BlogPosts] Blog Post Generator loaded successfully with SEO enhancement
Blog Post Generator API registered
Background File Processor API registered
Knowledge Backup routes not found: No module named 'knowledge_backup_routes'
Project Dashboard API registered
Analytics API registered
Workflow Engine API registered
Integration Hub API registered
============================================================
AI Swarm Orchestrator Starting
Workers: 2
Timeout: 180 seconds
Graceful Timeout: 200 seconds
============================================================
AI Swarm Orchestrator ready - accepting connections
Timeout configured: 180s
==> Running 'gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 180'
File Upload Limit: 100MB (allows large project files)
============================================================
🔄 STEP 1: Running database migration...
🗄️  DB Engine: PostgreSQL (production)
🔄 Running migration 001_initial_schema (Phase 9) on postgresql...
✅ PostgreSQL connection pool created (min=2, max=40)
✅ Migration 001 (Phase 9) complete: 56/56 tables verified on postgresql
✅ Database migration complete
============================================================
✅ Database tables already initialized by migration (STEP 1 in app.py)
✅ Survey tables verified/initialized
Survey tables initialized
Running legacy database migrations...
🔄 Migrating projects table...
   ℹ️  Projects table doesn't exist - will be created by ProjectManager
DEBUG: About to attempt blog_posts migration import...
DEBUG: Import successful, calling function...
📊 Blog Posts Migration: Checking /mnt/project/swarm_intelligence.db...
ℹ️  blog_posts table exists - checking for SEO columns...
   Current columns: id, topic, topic_display, title, url_slug, meta_description, content, angle, created_at, updated_at
   ✓ url_slug exists
   ✓ meta_description exists
✅ blog_posts table already has all SEO columns
✅ Blog Posts table migration complete!
Blog Posts table migration complete!
Error upgrading database: syntax error at or near "PRAGMA"
LINE 1: PRAGMA table_info(projects)
        ^
Error creating table: syntax error at or near "AUTOINCREMENT"
LINE 3:                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                               ^
Improvement reports migration: No module named 'add_improvement_reports_table'
✅ conversation_context table created
Conversation context table added!
✅ user_profiles table created!
Error creating tables: syntax error at or near "AUTOINCREMENT"
LINE 3:                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                               ^
Error creating table: syntax error at or near "AUTOINCREMENT"
LINE 3:                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                               ^
  ✅ add_missing_columns: Added 16 columns: case_studies.problem_summary, case_studies.solution_summary, blog_posts.topic_display, blog_posts.url_slug, blog_posts.meta_description, blog_posts.word_count, blog_posts.seo_title, blog_posts.author_name, blog_posts.tags, projects.project_id, projects.project_phase, projects.storage_path, projects.checklist_data, projects.milestone_data, projects.folder_data, projects.metadata
============================================================
🔧 Phase 9b: Fixing broken table schemas...
============================================================
  ✓ generated_documents OK
  ✓ user_feedback OK
  ✓ introspection_insights OK
  ✓ conversations OK
  ✓ conversation_messages OK
  ✓ tasks OK
  ✓ specialist_calls OK
  ✓ escalations OK
  ✓ learning_patterns OK
  ✓ learning_records OK
  ✓ avoidance_patterns OK
  ✓ smart_analyzer_state OK
  ✓ analysis_sessions OK
  ✓ background_jobs OK
  ✓ proactive_suggestions OK
  ✓ conversation_summaries OK
  ✓ user_patterns OK
  ✓ consensus_validations OK
============================================================
✅ Phase 9b complete:
   Tables fixed: 0
   Tables OK:    18
============================================================
============================================================
🔧 Phase 9c: Fixing missing SERIAL sequences...
============================================================
  Sequences fixed: 0
  Sequences OK:    52
============================================================
============================================================
🔧 Phase 9d: Adding missing boolean columns...
============================================================
  Columns added: 0
  Columns OK:    11
============================================================
Database migrations complete!
Initializing Bulletproof Project Management...
================================================================================
🔧 INITIALIZING PROJECT MANAGER - STORAGE DIAGNOSTICS
================================================================================
   ✅ Using STORAGE_ROOT from environment: /mnt/project/swarm_projects
✅ FINAL STORAGE LOCATION: /mnt/project/swarm_projects
================================================================================
✅ Storage directory exists and is writable: /mnt/project/swarm_projects
================================================================================
Bulletproof Project Manager initialized
Initializing Project Knowledge Base...
Found directory: project_files (40 files)
Starting knowledge base initialization in background thread...
   Gunicorn will accept connections immediately.
   Knowledge search will be available in ~30 seconds.
Initializing ENHANCED Project Knowledge Base...
Knowledge Base initializing in background (~30 seconds)...
App is ready to serve requests immediately.
Pattern-Based Schedule Generator loaded
Output Formatter loaded
  Found 40 files at project_files — proceeding with indexing.
  Indexed: Implementation Manual Sample.docx (4354 words)
  Indexed: Definitive Schedules.xlsx (7687 words)
  Indexed: conients.docx (15 words)
  Indexed: Data Collection.docx (142 words)
  Indexed: Implementation_Manual_Sample_2.docx (3965 words)
  Indexed: Data_Collection.docx (186 words)
  Indexed: Cost of time .xlsx (942 words)
  Indexed: Scope_of_work_by_AI.docx (586 words)
  Indexed: The_Code (4349 words)
  Indexed: Knowledge_base_from_pages (4650 words)
  Indexed: Jims_bio.docx (228 words)
  Indexed: Shiftwork_Solutions_Lessons_Learned.md (18027 words)
  Indexed: Shiftwork Work-Life Balance Survey.docx (2081 words)
  Indexed: Overall_summary (4068 words)
  Indexed: Copy of Kelloggs Math.xlsx (1126 words)
  Indexed: executive summary_SKECHERS_2025.docx (482 words)
  Indexed: Implementation_Manual_Sample.docx (4402 words)
  Indexed: Shiftwork_Solutions_LLC_Company_Profile_-_All_Industry__002_.docx (721 words)
  Indexed: Shiftwork_Solutions_LLC_-_Contract.docx (1727 words)
  Indexed: Definitive_Schedules_v2.xlsx (10832 words)
  Indexed: Project_kickoff_bulletin.docx (309 words)
  Indexed: Implementation Manual.docx (4354 words)
  Indexed: Schedule_Survey_.docx (2386 words)
  Indexed: Implementation_Manual.docx (4402 words)
  Indexed: README.md (4 words)
  Indexed: ACME_Implementation_Manual (1).docx (3427 words)
📚 [task_analysis] Knowledge Management DB path: /mnt/project/knowledge_ingestion.db
Survey Builder not available
Marketing Hub loaded for API endpoints
Opportunity Finder loaded for API endpoints
Project Manager loaded for API endpoints
    Error extracting THE_ESSENTIAL_GUIDE_TO_SHIFTWORK_OPERATIONS_EXCELLENCE.pdf: EOF marker not found
  Indexed: Session_Handoff_SwingShift.docx (1763 words)
  Indexed: Survey_evaluation (5246 words)
  Indexed: About Shiftwork Solutions.docx (1148 words)
  Indexed: Contract_without_name_Corp_A_2025.docx (1699 words)
  Indexed: Definitive Schedules v2.xlsx (9296 words)
  Indexed: Implementation Manual Sample 2.docx (3921 words)
  Indexed: Cost of time Best.xlsx (4103 words)
  Indexed: Example_Client_facing_executive_summary_Andersen_2025.docx (500 words)
  Indexing complete: 34 indexed, 0 errors
  Building semantic search index...
  Semantic index built: 5351 terms
============================================================
KNOWLEDGE BASE INITIALIZATION COMPLETE
  Source path  : project_files
  Files found  : 40
  Docs indexed : 34
  Unique terms : 5351
============================================================
Orchestration Handler API registered
DEBUG: About to import bulletproof project routes...
🔄 Force reloading ProjectManager singleton...
================================================================================
🔧 INITIALIZING PROJECT MANAGER - STORAGE DIAGNOSTICS
================================================================================
   ✅ Using STORAGE_ROOT from environment: /mnt/project/swarm_projects
✅ FINAL STORAGE LOCATION: /mnt/project/swarm_projects
[2026-03-05 00:48:27 +0000] [38] [INFO] Starting gunicorn 25.1.0
[2026-03-05 00:48:27 +0000] [38] [INFO] Listening at: http://0.0.0.0:10000 (38)
[2026-03-05 00:48:27 +0000] [38] [INFO] Using worker: sync
[2026-03-05 00:48:27 +0000] [38] [INFO] Control socket listening at /opt/render/project/src/gunicorn.ctl
==> No open HTTP ports detected on 0.0.0.0, continuing to scan...
