# 🎙️ AI SWARM VOICE SERVICE

**Created:** January 28, 2026  
**For:** Jim @ Shiftwork Solutions LLC  
**Purpose:** Real-time voice interaction microservice for AI Swarm Orchestrator

---

## 🎯 WHAT THIS IS

A **FastAPI microservice** that enables voice interaction with your AI Swarm Orchestrator using OpenAI's Realtime API.

**Why a separate service?**
- Flask (WSGI) cannot handle WebSockets natively
- Attempted Hypercorn with ASGI wrapper → Failed with "WSGI wrapper received a non-HTTP scope"
- Solution: Build dedicated FastAPI service for async WebSocket handling

---

## 🏗️ ARCHITECTURE

```
Main App (Flask/Gunicorn)              Voice Service (FastAPI/Uvicorn)
https://your-app.onrender.com          https://ai-swarm-voice.onrender.com
Port 10000                              Port 10000 (Render assigns)
┌──────────────────────┐               ┌──────────────────────────┐
│ /api/orchestrate     │◄──────────────│ HTTP Client              │
│ AI Swarm Logic       │   API Calls   │ OpenAI Realtime API      │
│ Database (SQLite)    │               │ WebSocket Handler        │
│ Conversations        │               │ Audio Streaming          │
└──────────────────────┘               └──────────────────────────┘
                                                  ▲
                                                  │ WebSocket
                                                  │
                                        ┌─────────┴──────────┐
                                        │   Browser Client    │
                                        │   swarm-voice.js    │
                                        └────────────────────┘
```

---

## 📁 FILE STRUCTURE

```
voice_service/
├── main.py                  # FastAPI app with WebSocket endpoint
├── voice_handler.py         # OpenAI Realtime API integration
├── orchestrator_client.py   # HTTP client for main app
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── .env.example            # Environment variables template
```

---

## 🚀 DEPLOYMENT TO RENDER

### **Step 1: Create GitHub Repository**

1. Create new folder in your `ai-swarm-orchestrator` repo:
   ```bash
   cd ai-swarm-orchestrator
   mkdir voice_service
   ```

2. Copy these files into `voice_service/`:
   - `main.py`
   - `voice_handler.py`
   - `orchestrator_client.py`
   - `requirements.txt`
   - `README.md`

3. Commit and push:
   ```bash
   git add voice_service/
   git commit -m "Add voice service microservice"
   git push origin main
   ```

### **Step 2: Create Render Service**

1. Go to [render.com](https://render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo: `ai-swarm-orchestrator`

4. **Configure Service:**
   ```
   Name:              ai-swarm-voice
   Environment:       Python 3
   Region:            Oregon (US West) - same as main app
   Branch:            main
   Root Directory:    voice_service
   Build Command:     pip install -r requirements.txt
   Start Command:     uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

5. **Add Environment Variables:**
   ```
   OPENAI_API_KEY     = your_openai_api_key_here
   MAIN_APP_URL       = https://your-main-app.onrender.com
   ```

6. Click **"Create Web Service"**

7. Wait ~3 minutes for deployment

### **Step 3: Update Main App Frontend**

Update `static/js/swarm-voice.js` in your main Flask app:

```javascript
// OLD (was trying to connect to Flask):
var wsUrl = protocol + '//' + window.location.host + '/api/voice/stream';

// NEW (connect to voice service):
var wsUrl = 'wss://ai-swarm-voice.onrender.com/ws/voice';
```

Commit and push this change to redeploy main app.

### **Step 4: Test**

1. Visit your main app: `https://your-app.onrender.com`
2. Click **"Activate Voice"** button
3. Say **"Hey Swarm, what is a DuPont schedule?"**
4. AI should respond via voice!

---

## 🧪 LOCAL TESTING

### **Option 1: Full Local Stack**

```bash
# Terminal 1 - Main Flask App
cd ai-swarm-orchestrator
python app.py

# Terminal 2 - Voice Service
cd voice_service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
export MAIN_APP_URL=http://localhost:10000
uvicorn main:app --reload --port 10001
```

Update `swarm-voice.js` temporarily:
```javascript
var wsUrl = 'ws://localhost:10001/ws/voice';
```

### **Option 2: Test Voice Service Only**

```bash
cd voice_service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
export MAIN_APP_URL=https://your-app.onrender.com  # Use production
uvicorn main:app --reload --port 10001
```

Use ngrok to expose:
```bash
ngrok http 10001
```

Update `swarm-voice.js` with ngrok URL.

---

## 🔧 HOW IT WORKS

### **1. WebSocket Connection Flow**

```
1. User clicks "Activate Voice" in browser
2. Browser connects to wss://ai-swarm-voice.onrender.com/ws/voice
3. Voice service connects to OpenAI Realtime API
4. Bidirectional audio streaming begins
5. User says "Hey Swarm, [command]"
6. Wake word detected → Route to orchestrator
7. AI Swarm processes command
8. Response streamed back as voice
```

### **2. Audio Format**

- **Input:** PCM16, 24kHz, mono, base64-encoded
- **Output:** PCM16, 24kHz, mono, base64-encoded
- **Browser:** Web Audio API handles capture/playback

### **3. Wake Word Detection**

OpenAI Realtime API handles wake word detection server-side:
- Listens for "Hey Swarm"
- Extracts command after wake word
- Routes to orchestrator

### **4. Message Protocol**

**Client → Server:**
```json
{"type": "audio", "data": "<base64-pcm16>"}
{"type": "interrupt"}
{"type": "ping"}
```

**Server → Client:**
```json
{"type": "ready", "session_id": "...", "conversation_id": "..."}
{"type": "audio", "data": "<base64-pcm16>"}
{"type": "transcript", "text": "AI's response"}
{"type": "user_transcript", "text": "User's speech"}
{"type": "wake_detected"}
{"type": "response_complete"}
{"type": "error", "message": "..."}
```

---

## 📚 LEARNING CHECKPOINTS

As you work through this code, here's what to understand at each stage:

### **Checkpoint 1: FastAPI Basics** ✅
- [ ] Understand async/await pattern
- [ ] Know difference between WSGI (Flask) and ASGI (FastAPI)
- [ ] Understand WebSocket vs HTTP
- [ ] Can explain why Flask can't handle WebSockets

### **Checkpoint 2: WebSocket Lifecycle** ✅
- [ ] Understand WebSocket handshake (accept)
- [ ] Know how bidirectional streaming works
- [ ] Understand connection cleanup (finally block)
- [ ] Can explain WebSocketDisconnect exception

### **Checkpoint 3: Audio Processing** ✅
- [ ] Understand PCM16 audio format
- [ ] Know why 24kHz sample rate
- [ ] Understand base64 encoding for binary data
- [ ] Can explain why mono (1 channel) audio

### **Checkpoint 4: OpenAI Realtime API** ✅
- [ ] Understand session configuration
- [ ] Know voice activity detection (VAD)
- [ ] Understand turn detection
- [ ] Can explain wake word flow

### **Checkpoint 5: Microservices Integration** ✅
- [ ] Understand HTTP vs WebSocket communication
- [ ] Know when to use each protocol
- [ ] Understand async HTTP with httpx
- [ ] Can explain service-to-service calls

---

## 🐛 TROUBLESHOOTING

### **"WebSocket connection failed"**
- Check OPENAI_API_KEY is set in Render
- Verify Render service is running (check logs)
- Test health endpoint: `https://ai-swarm-voice.onrender.com/health`

### **"Voice service can't reach main app"**
- Verify MAIN_APP_URL is correct in Render environment variables
- Check main app is running
- Test: `curl https://your-main-app.onrender.com/health`

### **"Wake word not detecting"**
- Verify OpenAI Realtime API model is correct
- Check session configuration in `voice_handler.py`
- Test with clear pronunciation: "HEY SWARM"

### **"Audio quality poor"**
- Ensure microphone permissions granted in browser
- Check audio format (PCM16, 24kHz)
- Verify Web Audio API is supported (modern browsers)

### **"High latency (>2 seconds)"**
- Check Render region (should be US West for lowest latency)
- Verify OpenAI API is responding quickly
- Check network connection

---

## 💰 COSTS

### **Development:**
- Time: 4-6 hours total
- Cost: $0 (local development)

### **Production:**
- **Main app:** $7/month (existing)
- **Voice service:** $7/month (new Render service)
- **OpenAI Realtime API:** ~$0.30/minute of conversation
- **Total:** $14/month + usage

### **Budget:**
- Set aside $10-20/month for voice experimentation
- **Total investment: ~$30/month**

---

## 🎓 FURTHER LEARNING

### **Recommended Reading:**
1. FastAPI docs: https://fastapi.tiangolo.com/
2. Python asyncio: https://docs.python.org/3/library/asyncio.html
3. OpenAI Realtime API: https://platform.openai.com/docs/guides/realtime
4. WebSocket protocol: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket

### **Experiments to Try:**
1. Add multiple voice options (alloy, echo, shimmer)
2. Implement voice interruption ("Stop")
3. Add session persistence
4. Create voice-activated project creation
5. Build voice-based schedule designer

---

## 🔒 SECURITY NOTES

### **API Key Protection:**
- ✅ NEVER commit API keys to GitHub
- ✅ Always use environment variables
- ✅ Render keeps environment variables encrypted

### **WebSocket Security:**
- ✅ Use WSS (WebSocket Secure) in production
- ✅ Validate all client messages
- ✅ Implement rate limiting if needed

### **CORS Configuration:**
- ⚠️ Currently allows all origins (`allow_origins=["*"]`)
- 🔧 In production, restrict to your domains:
  ```python
  allow_origins=[
      "https://your-app.onrender.com",
      "https://www.shiftworksolutions.com"
  ]
  ```

---

## ✅ SUCCESS CRITERIA

Your deployment is successful when:

1. ✅ Voice service deploys to Render without errors
2. ✅ Health check returns `{"status": "healthy"}`
3. ✅ WebSocket connects from browser
4. ✅ "Hey Swarm" triggers wake word detection
5. ✅ User speech transcribed accurately
6. ✅ Commands route to main orchestrator
7. ✅ AI responds via voice
8. ✅ Response time < 2 seconds
9. ✅ Code generation requests work via voice
10. ✅ You understand the architecture deeply

---

## 📞 SUPPORT

If you encounter issues:

1. **Check logs first:**
   - Render Dashboard → ai-swarm-voice → Logs
   - Look for error messages, stack traces

2. **Test endpoints:**
   ```bash
   # Health check
   curl https://ai-swarm-voice.onrender.com/health
   
   # Stats
   curl https://ai-swarm-voice.onrender.com/api/stats
   ```

3. **Common fixes:**
   - Restart Render service (sometimes helps)
   - Check environment variables are set
   - Verify GitHub repo is up to date
   - Review main app logs too

---

## 🎯 NEXT STEPS

After getting this working:

1. **Add features:**
   - Voice interruption ("Stop")
   - Multiple voice options
   - Session persistence
   - Voice activity visualization

2. **Optimize:**
   - Reduce latency
   - Add caching
   - Implement retry logic
   - Add monitoring/analytics

3. **Expand:**
   - Voice-based project management
   - Voice schedule designer
   - Voice-activated document creation
   - Multi-language support

---

## 🎓 PHILOSOPHICAL NOTE

This is a **learning project**, not just a feature add.

**Goals:**
- ✅ Understand modern async Python
- ✅ Master WebSocket patterns
- ✅ Learn microservices architecture
- ✅ Stay ahead of AI developments

**Not goals:**
- ❌ Quick hacks
- ❌ Duct tape solutions
- ❌ "Just make it work somehow"

**This architecture is reusable for future AI projects!**

---

**Built with care by Claude for Jim @ Shiftwork Solutions LLC**  
**Date: January 28, 2026**

*"The best way to predict the future is to build it." - Alan Kay*

---

# I did no harm and this file is not truncated
