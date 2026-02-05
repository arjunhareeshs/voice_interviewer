# Voice Interview Agent 🎙️

A real-time AI voice interviewer that conducts technical placement interviews. Built with **LangChain + Ollama** for AI, **Deepgram** for speech, and **React** for the frontend.

## 🚀 Quick Start (5 minutes)

### 1. Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Ollama** running locally:
  ```bash
  # Install from https://ollama.ai, then:
  ollama pull qwen3:8b
  ollama pull nomic-embed-text
  ollama serve
  ```

### 2. Get Deepgram API Key

1. Go to [console.deepgram.com](https://console.deepgram.com/)
2. Create a free account (free credits included)
3. Copy your API key

### 3. Configure Environment

Edit `.env` file in project root:
```bash
DEEPGRAM_API_KEY=your_api_key_here
```

### 4. Install & Run Backend

```bash
# Install Python dependencies
pip install -e .

# Run the server
python run.py
```

### 5. Run Frontend (Optional - for development)

```bash
cd frontend
npm install
npm run dev
```

### 6. Use the App

1. Open `http://localhost:8000` in your browser
2. Upload your resume (PDF/DOCX)
3. Click "Start Interview" and speak!

---

## 📁 Project Structure

```
voice-agent/
├── run.py              # Start server here
├── .env                # Configuration (API keys)
├── voice_agent/        # Backend Python code
│   ├── server.py       # FastAPI WebSocket server
│   ├── config.py       # Configuration loader
│   ├── services/       # Core services
│   │   ├── llm.py      # LangChain + Ollama
│   │   ├── stt.py      # Speech-to-Text (Deepgram)
│   │   ├── tts.py      # Text-to-Speech (Deepgram)
│   │   ├── vad.py      # Voice Activity Detection
│   │   ├── resume.py   # Resume parsing + RAG
│   │   └── interview.py# Interview state management
│   └── prompts/        # System prompts
├── frontend/           # React frontend
└── data/               # Uploads and outputs
```

## ⚙️ Configuration

All settings in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | LLM model for AI responses | `qwen3:8b` |
| `DEEPGRAM_API_KEY` | API key for speech services | Required |
| `DEEPGRAM_VOICE` | TTS voice (asteria, orion, etc.) | `asteria` |
| `SERVER_PORT` | Backend server port | `8000` |
| `VAD_MIN_SILENCE_MS` | Silence before processing | `600` |

## 🎯 Features

- **Real-time Voice Interview**: Natural conversation flow
- **Resume-Aware Questions**: AI asks about YOUR experience
- **7-Phase Interview Structure**: From greeting to wrap-up
- **Evaluation Report**: PDF with scores after interview
- **Low Latency**: Optimized for fast responses

## 🔧 Troubleshooting

**"Port 8000 already in use"**
```bash
# Find and kill the process:
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

**"DEEPGRAM_API_KEY is missing"**
- Make sure `.env` file exists with your API key

**"Ollama connection failed"**
- Run `ollama serve` in a terminal
- Check if models are downloaded: `ollama list`
│   └── static/
│       └── index.html    # Web interface
├── models/
│   └── piper/            # Piper voice models
├── pyproject.toml
├── .env
└── README.md
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web interface |
| `GET /health` | Health check |
| `WS /ws/voice` | WebSocket for voice streaming |

### WebSocket Protocol

**Client → Server:**
```json
{"type": "audio", "data": "<base64_pcm_16bit_16khz>"}
{"type": "clear"}
```

**Server → Client:**
```json
{"type": "status", "status": "listening|processing|speaking|ready"}
{"type": "transcript", "role": "user|assistant", "text": "..."}
{"type": "audio", "data": "<base64>", "sample_rate": 22050}
```

## Troubleshooting

### Ollama Connection Error
Make sure Ollama is running:
```bash
ollama serve
```

### No Voice Model
Download Piper voice models to `models/piper/`:
```bash
# Check available voices at https://huggingface.co/rhasspy/piper-voices
```

### CUDA Out of Memory
Use a smaller Whisper model:
```bash
# In .env
WHISPER_MODEL_SIZE=tiny
```

### Microphone Not Working
- Check browser permissions
- Ensure HTTPS or localhost
- Try a different browser

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run with auto-reload
voice-agent --reload

# Run tests
pytest
```

## License

MIT License

## Credits

- [LangChain](https://langchain.com/) - LLM framework
- [Ollama](https://ollama.ai/) - Local LLM inference
- [FasterWhisper](https://github.com/guillaumekln/faster-whisper) - Speech recognition
- [Piper](https://github.com/rhasspy/piper) - Text-to-speech
- [Silero VAD](https://github.com/snakers4/silero-vad) - Voice activity detection
