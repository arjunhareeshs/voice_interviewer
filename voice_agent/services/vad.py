"""Voice Activity Detection service using Silero VAD."""

import asyncio
import logging
import numpy as np
import torch

from ..config import config

logger = logging.getLogger(__name__)


# Global cache for the VAD model to avoid reloading for every session
_VAD_MODEL = None
_VAD_LOCK = asyncio.Lock()


class VADService:
    """
    Voice Activity Detection using Silero VAD.
    
    Optimized for low-latency voice conversations with proper noise filtering.
    Silero VAD requires exactly 512 samples at 16kHz sample rate.
    """
    
    # Silero VAD requires exactly 512 samples at 16kHz
    CHUNK_SIZE = 512
    
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = None,
        min_speech_duration: float = None,
        min_silence_duration: float = None,
        max_speech_duration: float = 30.0,
    ):
        """
        Initialize VAD service with optimized settings for real-time conversation.
        
        Args:
            sample_rate: Audio sample rate (must be 16000 for Silero)
            threshold: Speech probability threshold (0.0 - 1.0), higher = less sensitive
            min_speech_duration: Minimum speech duration in seconds to trigger detection
            min_silence_duration: Silence duration to end speech in seconds
            max_speech_duration: Maximum speech duration before forced end (seconds)
        """
        self.sample_rate = sample_rate
        
        # Use moderate threshold - not too strict to miss speech, not too loose to pick up noise
        self.threshold = threshold if threshold is not None else config.vad.threshold
        
        # Minimum speech duration: 300ms for faster detection
        min_speech = min_speech_duration if min_speech_duration is not None else max(config.vad.min_speech_ms / 1000.0, 0.3)
        
        # Wait for 600ms silence = user finished (reduced from 900ms for lower latency)
        min_silence = min_silence_duration if min_silence_duration is not None else max(config.vad.min_silence_ms / 1000.0, 0.6)
        
        self.min_speech_samples = int(min_speech * sample_rate)
        self.min_silence_samples = int(min_silence * sample_rate)
        self.max_speech_samples = int(max_speech_duration * sample_rate)
        
        # Minimum audio level (RMS) - slightly lower to catch softer speech
        self.min_audio_level = config.vad.min_audio_level if config.vad.min_audio_level else 0.012
        
        # Minimum total speech bytes to send for transcription (0.8 seconds = meaningful speech)
        self.min_speech_bytes = int(0.8 * sample_rate * 2)  # 2 bytes per sample
        
        self.model = None
        self._is_speaking = False
        self._speech_buffer = []
        self._speech_samples = 0
        self._silence_samples = 0
        self._pending_audio = np.array([], dtype=np.float32)
        self._processing_lock = False
        self._lock = asyncio.Lock()
        
        # Track consecutive speech/silence for debouncing
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._min_consecutive_speech = 3  # Need 3 consecutive speech chunks to start (faster)
        self._min_consecutive_silence = 4  # Need 4 consecutive silence chunks to end (faster)
        
    async def initialize(self) -> None:
        """Load Silero VAD model (cached globally)."""
        global _VAD_MODEL
        
        if _VAD_MODEL is not None:
            self.model = _VAD_MODEL
            return

        async with _VAD_LOCK:
            if _VAD_MODEL is not None:
                self.model = _VAD_MODEL
                return
                
            logger.info("Loading Silero VAD model into global cache...")
            try:
                model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    trust_repo=True
                )
                _VAD_MODEL = model
                self.model = _VAD_MODEL
                logger.info("Silero VAD model loaded successfully")
                
            except Exception as e:
                logger.error(f"Failed to load Silero VAD: {e}")
                raise
    
    def reset(self) -> None:
        """Reset VAD state for new session."""
        self._is_speaking = False
        self._speech_buffer = []
        self._speech_samples = 0
        self._silence_samples = 0
        self._pending_audio = np.array([], dtype=np.float32)
        self._processing_lock = False
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        logger.debug("VAD state reset")
    
    def set_processing(self, is_processing: bool) -> None:
        """Set processing lock to ignore audio during response generation."""
        self._processing_lock = is_processing
        if is_processing:
            self._speech_buffer = []
            self._speech_samples = 0
            self._silence_samples = 0
            self._is_speaking = False
            self._consecutive_speech = 0
            self._consecutive_silence = 0
    
    def _get_speech_bytes(self) -> bytes | None:
        """Convert speech buffer to bytes if it meets minimum length requirements."""
        if not self._speech_buffer:
            return None
            
        try:
            speech_audio = np.concatenate(self._speech_buffer)
            speech_bytes = (speech_audio * 32768.0).astype(np.int16).tobytes()
            
            # Check minimum speech length
            if len(speech_bytes) < self.min_speech_bytes:
                logger.debug(f"Speech too short ({len(speech_bytes)} bytes), discarding")
                return None
                
            return speech_bytes
        except Exception as e:
            logger.error(f"Error concatenating speech audio: {e}")
            return None
    
    async def process_audio(self, audio_data: bytes) -> tuple[bool, bytes | None]:
        """
        Process audio chunk and detect speech boundaries.
        
        Uses debouncing to avoid false triggers from noise.
        
        Args:
            audio_data: Raw 16-bit PCM audio bytes
            
        Returns:
            Tuple of (speech_ended, speech_audio_bytes or None)
        """
        if self.model is None:
            raise RuntimeError("VAD model not initialized")
        
        if self._processing_lock:
            return (False, None)
        
        async with self._lock:
            try:
                audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            except Exception as e:
                logger.error(f"Error converting audio data: {e}")
                return (False, None)
            
            self._pending_audio = np.concatenate([self._pending_audio, audio])
            
            while len(self._pending_audio) >= self.CHUNK_SIZE:
                chunk = self._pending_audio[:self.CHUNK_SIZE]
                self._pending_audio = self._pending_audio[self.CHUNK_SIZE:]
                
                # Check audio level (RMS) for noise rejection
                rms = np.sqrt(np.mean(chunk ** 2))
                
                if rms < self.min_audio_level:
                    # Audio too quiet - treat as silence
                    self._consecutive_speech = 0
                    self._consecutive_silence += 1
                    
                    if self._is_speaking:
                        self._silence_samples += self.CHUNK_SIZE
                        self._speech_buffer.append(chunk)
                        
                        if self._silence_samples >= self.min_silence_samples:
                            speech_bytes = self._get_speech_bytes()
                            
                            self._is_speaking = False
                            self._speech_buffer = []
                            self._speech_samples = 0
                            self._silence_samples = 0
                            
                            if speech_bytes:
                                logger.debug(f"Speech ended (quiet), {len(speech_bytes)} bytes")
                                return (True, speech_bytes)
                    continue
                
                # Run VAD model
                audio_tensor = torch.from_numpy(chunk).float()
                
                try:
                    loop = asyncio.get_event_loop()
                    speech_prob = await loop.run_in_executor(
                        None,
                        lambda t=audio_tensor: self.model(t, self.sample_rate).item()
                    )
                except Exception as e:
                    logger.error(f"VAD model inference error: {e}")
                    continue
                
                is_speech = speech_prob > self.threshold
                
                if is_speech:
                    self._consecutive_speech += 1
                    self._consecutive_silence = 0
                    self._silence_samples = 0
                    self._speech_samples += self.CHUNK_SIZE
                    self._speech_buffer.append(chunk)
                    
                    # Start speaking only after consecutive speech frames (debounce)
                    if not self._is_speaking:
                        if self._consecutive_speech >= self._min_consecutive_speech and \
                           self._speech_samples >= self.min_speech_samples:
                            self._is_speaking = True
                            logger.debug("Speech started (confirmed)")
                    
                    # Check max duration
                    total_samples = sum(len(c) for c in self._speech_buffer)
                    if self._is_speaking and total_samples >= self.max_speech_samples:
                        logger.info(f"Max speech duration reached ({total_samples / self.sample_rate:.1f}s)")
                        speech_bytes = self._get_speech_bytes()
                        
                        self._is_speaking = False
                        self._speech_buffer = []
                        self._speech_samples = 0
                        self._silence_samples = 0
                        self._consecutive_speech = 0
                        
                        if speech_bytes:
                            return (True, speech_bytes)
                else:
                    self._consecutive_speech = 0
                    self._consecutive_silence += 1
                    
                    if self._is_speaking:
                        self._silence_samples += self.CHUNK_SIZE
                        self._speech_buffer.append(chunk)
                        
                        if self._silence_samples >= self.min_silence_samples:
                            speech_bytes = self._get_speech_bytes()
                            
                            logger.debug(f"Speech ended, {len(self._speech_buffer)} chunks")
                            
                            self._is_speaking = False
                            self._speech_buffer = []
                            self._speech_samples = 0
                            self._silence_samples = 0
                            
                            if speech_bytes:
                                return (True, speech_bytes)
                    else:
                        # Not speaking - if we have accumulated some audio but not enough
                        # consecutive speech, clear the buffer to avoid false triggers
                        if self._consecutive_silence > 5 and self._speech_buffer:
                            self._speech_buffer = []
                            self._speech_samples = 0
            
            return (False, None)
    
    @property
    def is_speaking(self) -> bool:
        """Check if currently detecting speech."""
        return self._is_speaking
