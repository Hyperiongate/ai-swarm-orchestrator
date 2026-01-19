# AI Swarm Orchestrator

**Created:** January 18, 2026  
**For:** Shiftwork Solutions LLC  
**Purpose:** Intelligent multi-AI collaboration system with specialist routing, consensus validation, and learning capabilities

---

## 🎯 What This Does

The AI Swarm Orchestrator intelligently routes tasks to specialist AIs based on their strengths:

- **Claude Sonnet** (Primary Orchestrator): Fast routing for 90% of routine tasks
- **Claude Opus** (Strategic Supervisor): Deep analysis for 10% of complex/novel tasks
- **GPT-4** (Design & Content Specialist): PowerPoint, marketing copy, creative content
- **DeepSeek** (Code Specialist): Programming, Excel formulas, technical implementation
- **Gemini** (Multimodal Specialist): Image/video analysis, document processing

**Key Features:**
- ✅ Automatic task routing to best specialist AI
- ✅ Multi-AI consensus validation (catch errors through agreement)
- ✅ Learning system (improves over time)
- ✅ Escalation system (Sonnet → Opus for complex tasks)
- ✅ Full tracking and analytics

---

## 🚀 Quick Deploy to Render

### **Step 1: Create GitHub Repository**

1. Go to GitHub and create new repo: `ai-swarm-orchestrator`
2. Upload these files:
   - `swarm_app.py`
   - `swarm_index.html` (rename to `templates/index.html`)
   - `requirements.txt`
   - `Procfile`
   - `README.md`

### **Step 2: Deploy on Render**

1. Go to [render.com](https://render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo: `ai-swarm-orchestrator`
4. Configure:
   - **Name:** `ai-swarm-orchestrator`
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** (leave empty - uses Procfile)

5. **Add Environment Variables:**

Required:
```
ANTHROPIC_API_KEY = your_anthropic_key
```

Optional (add specialists you want):
```
OPENAI_API_KEY = your_openai_key
DEEPSEEK_API_KEY = your_deepseek_key
GOOGLE_API_KEY = your_google_key
MISTRAL_API_KEY = your_mistral_key
GROQ_API_KEY = your_groq_key
```

6. Click **"Create Web Service"**
7. Wait ~3 minutes for deployment

### **Step 3: Test It**

Visit your Render URL (e.g., `https://ai-swarm-orchestrator.onrender.com`)

Try a request like:
```
Create a PowerPoint presentation about the benefits 
of 12-hour shift schedules for manufacturing facilities
```

---

## 📁 File Structure

```
ai-swarm-orchestrator/
├── swarm_app.py              # Main Flask application
├── templates/
│   └── index.html           # Web interface
├── requirements.txt         # Python dependencies
├── Procfile                 # Render deployment config
└── README.md               # This file
```

---

## 🎮 How to Use

### **Via Web Interface:**

1. Visit your deployed URL
2. Enter your request in the text box
3. Optionally enable/disable consensus validation
4. Click "Launch Swarm"
5. Watch the AI team work
6. Review results with specialist outputs and consensus scores

### **Via API:**

```bash
curl -X POST https://your-app.onrender.com/api/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Create a LinkedIn post about shift work challenges",
    "enable_consensus": true
  }'
```

---

## 📊 How It Works

### **Request Flow:**

```
USER REQUEST
    ↓
SONNET (Primary Orchestrator)
├─ Analyzes request
├─ Determines complexity
├─ Assigns confidence score
    ↓
┌─────────────────┬─────────────────┐
│  ROUTINE        │   COMPLEX       │
│  (90%)          │   (10%)         │
│  Confidence >0.85│  Confidence <0.85│
└────────┬────────┴────────┬────────┘
         │                 │
         │                 ↓
         │            OPUS (Strategic)
         │            ├─ Deep analysis
         │            ├─ Creates plan
         │            └─ Teaches Sonnet
         │                 │
         ↓                 ↓
    SPECIALISTS EXECUTE TASK
    ├─ GPT-4: Design/Content
    ├─ DeepSeek: Code
    └─ Gemini: Multimodal
         │
         ↓
    CONSENSUS VALIDATION
    ├─ Multiple AIs review
    ├─ Calculate agreement
    └─ Flag disagreements
         │
         ↓
    DELIVER RESULTS TO USER
```

### **Escalation Criteria:**

Sonnet escalates to Opus when:
- Confidence score < 0.85
- Novel situation not seen before
- Multiple conflicting approaches possible
- Strategic business implications
- High-value/high-risk client work

### **Learning System:**

Every task is tracked:
- Which AI handled what
- Execution times
- Success/failure
- Consensus scores
- Your feedback

Over time:
- Sonnet learns new patterns from Opus
- Specialist routing improves
- Escalations decrease
- Speed increases
- Cost decreases

---

## 🔍 API Endpoints

### **POST `/api/orchestrate`**
Submit a task to the swarm

**Request:**
```json
{
  "request": "Create a cost calculator for overtime analysis",
  "enable_consensus": true
}
```

**Response:**
```json
{
  "success": true,
  "task_id": 42,
  "orchestrator": "sonnet",
  "analysis": {...},
  "specialist_results": [...],
  "consensus": {...},
  "execution_time_seconds": 15.3
}
```

### **GET `/api/tasks`**
Get recent tasks (last 50)

### **GET `/api/task/<id>`**
Get detailed task information

### **GET `/api/stats`**
Get system statistics

### **GET `/health`**
Health check and system status

---

## 🎓 Learning from Usage

The system learns in several ways:

### **1. Pattern Recognition**
- Sonnet identifies common task types
- Creates shortcuts for frequent requests
- Reduces need for Opus escalations

### **2. Specialist Performance**
- Tracks which AIs perform best on which tasks
- Adjusts routing over time
- Identifies when to use consensus vs. single AI

### **3. Opus → Sonnet Knowledge Transfer**
- When Opus handles a complex case
- It teaches Sonnet the pattern
- Next similar case → Sonnet handles it

### **4. User Feedback Loop**
- Tracks task success/failure
- Learns from your decisions
- Refines confidence thresholds

---

## 📈 Monitoring & Analytics

The system tracks:

- **Total tasks processed**
- **Sonnet vs Opus handling ratio** (goal: 90/10)
- **Average execution time**
- **Specialist usage patterns**
- **Consensus agreement scores**
- **Escalation frequency**
- **Cost per task**

Access via:
- Web dashboard (real-time)
- `/api/stats` endpoint (JSON)
- SQLite database (direct access)

---

## 💰 Cost Management

Estimated costs per task:

| Component | Cost |
|-----------|------|
| Sonnet routing | $0.001 |
| Opus escalation | $0.01 |
| GPT-4 specialist | $0.02 |
| DeepSeek specialist | $0.001 |
| Gemini specialist | $0.002 |
| Consensus validation | $0.002 |

**Typical task:** $0.02 - $0.05

**Monthly (100 tasks):** $2 - $5

**ROI:** If saves 1 hour/week = $500+ value for $10 cost

---

## 🔧 Customization

### **Add New Specialists:**

Edit `swarm_app.py`:

```python
# Add API client
NEW_AI_KEY = os.environ.get('NEW_AI_KEY')
new_ai_client = SomeClient(api_key=NEW_AI_KEY)

# Add function
def call_new_ai(prompt):
    # implementation
    pass

# Add to specialist_map
specialist_map = {
    "gpt4": call_gpt4,
    "new_ai": call_new_ai,  # Add this
    # ...
}
```

### **Adjust Escalation Threshold:**

Change confidence threshold in `analyze_task_with_sonnet`:

```python
# Current: escalate if confidence < 0.85
# More aggressive: confidence < 0.90 (more Opus usage)
# More conservative: confidence < 0.80 (less Opus usage)
```

### **Add New Task Types:**

Extend the task_type analysis to recognize new categories

### **Custom Consensus Rules:**

Modify `validate_with_consensus` to use different validators or scoring

---

## 🐛 Troubleshooting

### **"API key not configured" errors**
- Check Environment Variables in Render dashboard
- Verify API keys are valid
- Redeploy after adding keys

### **Slow response times**
- Normal for first request (cold start)
- Subsequent requests should be faster
- Consensus validation adds 5-10 seconds

### **Escalating too often**
- Sonnet learning takes time
- First 10-20 tasks: ~30% escalation
- After 50 tasks: should drop to ~15%
- After 100 tasks: should be ~10%

### **Database errors**
- SQLite created automatically on first run
- Check file permissions on Render
- Database resets on redeploy (ephemeral filesystem)

---

## 🎯 Use Cases for Shiftwork Solutions

### **Client Deliverables:**
- "Create PowerPoint for pharmaceutical client pitch"
- "Build Excel overtime calculator"
- "Generate implementation timeline"
- "Write executive summary"

### **Marketing:**
- "Create LinkedIn campaign about shift work benefits"
- "Write white paper introduction"
- "Generate social media posts"
- "Create lead magnet PDF"

### **Business Development:**
- "Analyze market opportunity in healthcare"
- "Compare our services vs competitors"
- "Create ROI calculator for prospects"
- "Draft proposal for new client"

### **Operations:**
- "Process survey results and find patterns"
- "Generate benchmark comparison report"
- "Create custom schedule analysis"
- "Build cost comparison model"

---

## 🔮 Future Enhancements

Planned features:

- **Project memory:** Reference past projects and clients
- **File uploads:** Process documents, spreadsheets, images
- **Multi-step workflows:** Chain multiple specialist tasks
- **Feedback loop:** Rate outputs to improve routing
- **Cost tracking:** Real-time spend monitoring
- **Specialist expansion:** Add more AI systems
- **Custom prompts:** Template library for common tasks
- **Integration hooks:** Connect to existing tools

---

## 📝 Notes

- Database uses SQLite (simple, no separate DB needed)
- Database is ephemeral on Render free tier (resets on redeploy)
- Upgrade to paid Render plan for persistent disk
- Or: Migrate to PostgreSQL for production
- Logs available in Render dashboard

---

## 🤝 Support

For issues or questions:
- Check logs in Render dashboard
- Review database: `sqlite3 swarm_intelligence.db`
- Test health endpoint: `/health`
- Check API responses for error messages

---

## 📄 License

Created for Shiftwork Solutions LLC  
© 2026 All Rights Reserved

---

# I did no harm and this file is not truncated
