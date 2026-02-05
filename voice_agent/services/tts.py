"""
Text-to-Speech Service using Deepgram API.
Provides high-quality, low-latency speech synthesis.
"""

import logging
import os
import asyncio
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)


class TTSService:
    """
    Text-to-Speech using Deepgram Aura API.
    
    Deepgram Aura provides high-quality, low-latency text-to-speech
    with natural sounding voices.
    """

    # Available Deepgram Aura voices
    VOICES = {
        "asteria": "aura-asteria-en",      # Female, American English (recommended)
        "luna": "aura-luna-en",            # Female, American English
        "stella": "aura-stella-en",        # Female, American English
        "athena": "aura-athena-en",        # Female, British English
        "hera": "aura-hera-en",            # Female, American English
        "orion": "aura-orion-en",          # Male, American English
        "arcas": "aura-arcas-en",          # Male, American English
        "perseus": "aura-perseus-en",      # Male, American English
        "angus": "aura-angus-en",          # Male, Irish English
        "orpheus": "aura-orpheus-en",      # Male, American English
        "helios": "aura-helios-en",        # Male, British English
        "zeus": "aura-zeus-en",            # Male, American English
    }

    def __init__(self):
        self.api_key: Optional[str] = None
        self.voice: str = "aura-asteria-en"  # Default to Asteria (natural female voice)
        self.sample_rate = 24000  # Deepgram returns 24kHz audio
        self._initialized = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        """Initialize Deepgram TTS service."""
        logger.info("Initializing Deepgram TTS...")
        
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            logger.error("DEEPGRAM_API_KEY not found in environment!")
            logger.error("Please set DEEPGRAM_API_KEY in your .env file")
            return

        # Get voice preference from environment
        voice_name = os.getenv("DEEPGRAM_VOICE", "asteria").lower()
        if voice_name in self.VOICES:
            self.voice = self.VOICES[voice_name]
        else:
            # Check if full voice model name provided
            if voice_name.startswith("aura-"):
                self.voice = voice_name
            else:
                logger.warning(f"Unknown voice '{voice_name}', using default 'asteria'")
                self.voice = self.VOICES["asteria"]
        
        # Create aiohttp session for async requests
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        self._initialized = True
        logger.info(f"Deepgram TTS initialized successfully with voice: {self.voice}")

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesize speech from text using Deepgram Aura.
        Returns MP3 audio bytes.
        
        Args:
            text: The text to synthesize
            
        Returns:
            MP3 audio bytes
        """
        if not self._initialized or not self._session:
            logger.warning("TTS not initialized.")
            return b""

        if not text.strip():
            return b""

        # Filter out purely non-verbal text
        clean_text = text.strip()
        if not any(c.isalnum() for c in clean_text):
            return b""

        try:
            logger.info(f"Deepgram TTS generating: '{clean_text[:50]}...'")
            
            # Deepgram TTS API endpoint
            url = f"https://api.deepgram.com/v1/speak?model={self.voice}&encoding=mp3"
            
            # Request body
            payload = {
                "text": clean_text
            }
            
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    audio_bytes = await response.read()
                    logger.info(f"Deepgram TTS generated {len(audio_bytes)} bytes of audio")
                    return audio_bytes
                else:
                    error_text = await response.text()
                    logger.error(f"Deepgram TTS failed with status {response.status}: {error_text}")
                    return b""

        except asyncio.TimeoutError:
            logger.error("Deepgram TTS request timed out")
            return b""
        except aiohttp.ClientError as e:
            logger.error(f"Deepgram TTS network error: {e}")
            return b""
        except Exception as e:
            logger.error(f"Deepgram TTS synthesis failed: {e}")
            return b""

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("Deepgram TTS session closed")

    @property
    def available(self) -> bool:
        """Check if the TTS service is available."""
        return self._initialized and self._session is not None
