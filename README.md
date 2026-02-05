# Voice Agent 🎙️

A real-time conversational AI voice agent using **LangChain**, **Whisper**, and **Piper TTS**. Talk naturally with an AI assistant - all running locally on your machine.

## Features

- 🎤 **Real-time Voice Conversation** - Natural bidirectional audio via WebSocket
- 🔇 **Voice Activity Detection** - Silero VAD for accurate speech detection
- 📝 **Speech-to-Text** - FasterWhisper for fast, accurate transcription
- 🤖 **LangChain + Ollama** - Intelligent responses with conversation memory
- 🔊 **Text-to-Speech** - Piper TTS with natural voices
- 🌐 **Modern Web UI** - Clean, responsive interface

## Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **Ollama** running with a model:
  ```bash
  # Install Ollama from https://ollama.ai
  ollama pull llama3.2
  ollama serve
  ```

### 2. Installation

```bash
# Clone and enter directory
cd voice-agent

# Install with pip
pip install -e .

# Or with uv (faster)
uv pip install -e .
```

### 3. Download Voice Model

Download a Piper voice model from [Hugging Face](https://huggingface.co/rhasspy/piper-voices):

```bash
# Create models directory
mkdir -p models/piper

# Download voice (example: en_US-lessac-medium)
cd models/piper
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### 4. Run the Agent

```bash
# Run with CLI
voice-agent

# Or run as module
python -m voice_agent.main

# Or with custom options
voice-agent --host 127.0.0.1 --port 8080
```

### 5. Open the Web Interface

Navigate to `http://localhost:8000` in your browser and start talking!

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | Ollama model name | `llama3.2` |
| `WHISPER_MODEL_SIZE` | Whisper model size | `base` |
| `PIPER_VOICE` | Piper voice name | `en_US-lessac-medium` |
| `SERVER_PORT` | Server port | `8000` |

## Project Structure

```
voice-agent/
├── voice_agent/
│   ├── __init__.py
│   ├── main.py           # CLI entry point
│   ├── server.py         # FastAPI WebSocket server
│   ├── config.py         # Configuration
│   ├── services/
│   │   ├── vad.py        # Voice Activity Detection
│   │   ├── stt.py        # Speech-to-Text (Whisper)
│   │   ├── llm.py        # LangChain + Ollama
│   │   └── tts.py        # Text-to-Speech (Piper)
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
