"""
Configuration for Voice Agent.
Loads settings from environment variables.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


@dataclass
class OllamaConfig:
    """Ollama LLM configuration."""
    base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "mistral"))
    temperature: float = field(default_factory=lambda: float(os.getenv("OLLAMA_TEMPERATURE", "0.7")))


@dataclass
class AssemblyAIConfig:
    """AssemblyAI STT configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("ASSEMBLYAI_API_KEY", ""))


@dataclass
class DeepgramConfig:
    """Deepgram TTS configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))
    voice: str = field(default_factory=lambda: os.getenv("DEEPGRAM_VOICE", "asteria"))


@dataclass
class PiperConfig:
    """Piper TTS configuration."""
    voice: str = field(default_factory=lambda: os.getenv("PIPER_VOICE", "en_US-lessac-medium"))
    models_dir: Path = field(default_factory=lambda: Path(os.getenv("PIPER_MODELS_DIR", str(_project_root / "models" / "piper"))))


@dataclass
class VADConfig:
    """Voice Activity Detection configuration."""
    threshold: float = field(default_factory=lambda: float(os.getenv("VAD_THRESHOLD", "0.6")))
    min_speech_ms: int = field(default_factory=lambda: int(os.getenv("VAD_MIN_SPEECH_MS", "250")))
    min_silence_ms: int = field(default_factory=lambda: int(os.getenv("VAD_MIN_SILENCE_MS", "700")))
    min_audio_level: float = field(default_factory=lambda: float(os.getenv("VAD_MIN_AUDIO_LEVEL", "0.01")))
    sample_rate: int = 16000


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str = field(default_factory=lambda: os.getenv("SERVER_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("SERVER_PORT", "8000")))


@dataclass
class Config:
    """Main configuration container."""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    assemblyai: AssemblyAIConfig = field(default_factory=AssemblyAIConfig)
    deepgram: DeepgramConfig = field(default_factory=DeepgramConfig)
    piper: PiperConfig = field(default_factory=PiperConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


# Global config instance
config = Config()
