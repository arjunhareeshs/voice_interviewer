"""
Speech-to-Text Service using Deepgram.
Provides fast, accurate real-time transcription.
"""

import asyncio
import logging
import os
from typing import Optional
import aiohttp
import numpy as np

logger = logging.getLogger(__name__)


class STTService:
    """
    Speech-to-Text using Deepgram.
    Uses pre-recorded API for fast batch transcription with low latency.
    """

    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def initialize(self) -> None:
        """Initialize the STT service."""
        if not self.api_key:
            raise RuntimeError("DEEPGRAM_API_KEY is missing. Please set it in .env")
        
        # Create aiohttp session with optimized settings
        timeout = aiohttp.ClientTimeout(total=10, connect=3)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "Authorization": f"Token {self.api_key}",
            }
        )
        logger.info("Deepgram STT initialized")

    async def transcribe(self, audio: np.ndarray | bytes) -> str:
        """
        Transcribe audio to text using Deepgram's pre-recorded API.
        
        This is much faster than AssemblyAI's polling approach.
        Deepgram returns results in a single request (~200-500ms).

        Args:
            audio: Audio samples (float32 numpy array, 16kHz mono) or raw int16 PCM bytes

        Returns:
            Transcribed text
        """
        if not self.api_key or not self._session:
            raise RuntimeError("STT not initialized properly")

        # Convert audio to int16 bytes if needed
        if isinstance(audio, np.ndarray):
            # Convert float32 [-1, 1] to int16 PCM bytes
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
        else:
            audio_bytes = audio
        
        # Check if audio is too short (less than 0.3 seconds at 16kHz)
        # 16000 samples/sec * 2 bytes/sample * 0.3 sec = 9600 bytes
        if len(audio_bytes) < 9600:
            logger.debug(f"Audio too short ({len(audio_bytes)} bytes), skipping transcription")
            return ""

        try:
            # Deepgram pre-recorded API endpoint with optimized parameters
            url = "https://api.deepgram.com/v1/listen"
            params = {
                "model": "nova-2",          # Best accuracy model
                "language": "en",            # English
                "punctuate": "true",         # Add punctuation
                "smart_format": "true",      # Smart formatting
                "encoding": "linear16",      # Raw PCM format
                "sample_rate": "16000",      # 16kHz
                "channels": "1",             # Mono
            }
            
            headers = {
                "Content-Type": "audio/raw",
            }
            
            async with self._session.post(url, params=params, headers=headers, data=audio_bytes) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Extract transcript from response
                    try:
                        transcript = result["results"]["channels"][0]["alternatives"][0]["transcript"]
                        if transcript:
                            logger.debug(f"Transcribed: {transcript}")
                        return transcript.strip()
                    except (KeyError, IndexError):
                        logger.warning("No transcript in Deepgram response")
                        return ""
                else:
                    error_text = await response.text()
                    logger.error(f"Deepgram STT failed with status {response.status}: {error_text}")
                    return ""
                    
        except asyncio.TimeoutError:
            logger.error("Deepgram STT request timed out")
            return ""
        except aiohttp.ClientError as e:
            logger.error(f"Deepgram STT network error: {e}")
            return ""
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("Deepgram STT session closed")
