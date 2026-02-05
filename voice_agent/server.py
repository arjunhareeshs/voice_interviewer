"""
Voice Agent Server - FastAPI WebSocket server for voice conversations.
"""

import asyncio
import base64
import json
import logging
import os
import shutil
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import config
from .services import LLMService, STTService, TTSService, VADService
from .services.resume import ResumeService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global services
vad_service: VADService = None
stt_service: STTService = None
llm_service: LLMService = None
tts_service: TTSService = None
resume_service: ResumeService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle handler."""
    global vad_service, stt_service, llm_service, tts_service, resume_service

    logger.info("=" * 50)
    logger.info("Voice Agent Starting...")
    logger.info("=" * 50)

    # Initialize services
    vad_service = VADService()
    stt_service = STTService()
    resume_service = ResumeService()
    llm_service = LLMService()
    tts_service = TTSService()

    try:
        # Resume service doesn't have async init, but we should load the resume if exists
        resume_path = os.path.join(os.getcwd(), "parsed_resume.md")
        if os.path.exists(resume_path):
             logger.info(f"Loading existing resume from {resume_path}")
             resume_service.load_resume(resume_path)

        await asyncio.gather(
            vad_service.initialize(),
            stt_service.initialize(),
            llm_service.initialize(resume_service),
            tts_service.initialize(),
        )
        logger.info("All services initialized successfully!")
        logger.info(f"Server running at http://{config.server.host}:{config.server.port}")
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield

    # Cleanup
    if llm_service:
        await llm_service.close()
    if tts_service:
        await tts_service.close()
    if stt_service:
        await stt_service.close()
    logger.info("Voice Agent stopped.")


app = FastAPI(
    title="Voice Agent",
    description="Real-time conversational AI voice agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend build)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    # Mount assets folder
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the web interface."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return {"message": "Voice Agent API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "vad": vad_service is not None,
            "stt": stt_service is not None and bool(stt_service.api_key),
            "llm": llm_service is not None and llm_service.llm is not None,
            "tts": tts_service is not None and tts_service.available,
        }
    }

@app.get("/api/download-report")
async def download_report():
    """Download the latest evaluation report."""
    report_path = Path("evaluation_report.pdf")
    if report_path.exists():
        return FileResponse(report_path, filename="evaluation_report.pdf", media_type="application/pdf")
    return {"error": "Report not found. Complete a session first."}


# ============================================================================
# RESUME UPLOAD ENDPOINT
# ============================================================================

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a resume file for the interview.
    Supports PDF, DOC, and DOCX formats.
    """
    global resume_service
    
    # Validate file type
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a PDF, DOC, or DOCX file."
        )
    
    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File size too large. Maximum size is 10MB."
        )
    
    # Save file temporarily
    uploads_dir = Path(__file__).parent.parent / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    import uuid
    file_ext = Path(file.filename).suffix
    unique_filename = f"resume_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = uploads_dir / unique_filename
    
    try:
        # Write file
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Initialize resume service and load the resume
        resume_service = ResumeService()
        resume_service.load_resume(str(file_path))
        
        logger.info(f"Resume uploaded and processed: {file.filename}")
        
        return {
            "success": True,
            "message": "Resume uploaded successfully",
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Error processing resume: {e}")
        # Clean up file if processing failed
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process resume: {str(e)}"
        )

# ============================================================================
# CONVERSATION HISTORY ENDPOINTS
# ============================================================================

# Store active sessions for accessing their conversation history
active_sessions: dict = {}


@app.get("/api/conversation/full")
async def get_full_conversation(session_id: str = None):
    """
    Get the complete conversation history (not summarized).
    
    Args:
        session_id: Optional session ID. If not provided, returns global LLM history.
    
    Returns:
        Complete conversation history with all messages
    """
    if session_id and session_id in active_sessions:
        session_llm = active_sessions[session_id]
        return {
            "session_id": session_id,
            "conversation": session_llm.get_full_conversation(),
            "stats": session_llm.get_conversation_stats()
        }
    elif llm_service:
        return {
            "session_id": "global",
            "conversation": llm_service.get_full_conversation(),
            "stats": llm_service.get_conversation_stats()
        }
    return {"error": "No LLM service available"}


@app.get("/api/conversation/formatted")
async def get_formatted_conversation(session_id: str = None):
    """
    Get the complete conversation as a formatted text string.
    Perfect for viewing at the end of a session.
    
    Args:
        session_id: Optional session ID
    
    Returns:
        Formatted text string of the entire conversation
    """
    if session_id and session_id in active_sessions:
        session_llm = active_sessions[session_id]
        return {
            "session_id": session_id,
            "formatted_conversation": session_llm.get_full_conversation_formatted()
        }
    elif llm_service:
        return {
            "session_id": "global",
            "formatted_conversation": llm_service.get_full_conversation_formatted()
        }
    return {"error": "No LLM service available"}


@app.get("/api/conversation/summaries")
async def get_summaries(session_id: str = None):
    """
    Get all generated summaries.
    
    Args:
        session_id: Optional session ID
    
    Returns:
        List of all summaries generated during the conversation
    """
    if session_id and session_id in active_sessions:
        session_llm = active_sessions[session_id]
        return {
            "session_id": session_id,
            "summaries": session_llm.get_summaries(),
            "total_count": len(session_llm.get_summaries())
        }
    elif llm_service:
        return {
            "session_id": "global",
            "summaries": llm_service.get_summaries(),
            "total_count": len(llm_service.get_summaries())
        }
    return {"error": "No LLM service available"}


@app.get("/api/conversation/stats")
async def get_conversation_stats(session_id: str = None):
    """
    Get conversation statistics.
    
    Args:
        session_id: Optional session ID
    
    Returns:
        Statistics about the conversation including exchange count, summarization status
    """
    if session_id and session_id in active_sessions:
        session_llm = active_sessions[session_id]
        return {
            "session_id": session_id,
            **session_llm.get_conversation_stats()
        }
    elif llm_service:
        return {
            "session_id": "global",
            **llm_service.get_conversation_stats()
        }
    return {"error": "No LLM service available"}


@app.get("/api/sessions")
async def list_sessions():
    """
    List all active/preserved conversation sessions.
    
    Returns:
        List of session IDs with their stats
    """
    sessions = []
    for session_id, session_llm in active_sessions.items():
        try:
            stats = session_llm.get_conversation_stats()
            sessions.append({
                "session_id": session_id,
                "exchange_count": stats.get("exchange_count", 0),
                "full_archive_length": stats.get("full_archive_length", 0),
                "summaries_count": stats.get("summaries_count", 0)
            })
        except Exception:
            pass
    return {
        "total_sessions": len(sessions),
        "sessions": sessions
    }


# ============================================================================
# CONVERSATION OUTPUT SAVING
# ============================================================================

def save_conversation_to_file(session_id: str, session_llm: LLMService) -> dict:
    """
    Save conversation history to a file in the outputs directory.
    
    Args:
        session_id: The session ID to use as filename
        session_llm: The LLM service with conversation history
    
    Returns:
        Dictionary with file path and status
    """
    import datetime
    
    outputs_dir = Path(__file__).parent.parent / "data" / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename with session ID and timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conversation_{session_id[:8]}_{timestamp}.json"
    filepath = outputs_dir / filename
    
    # Get conversation data
    conversation_data = {
        "session_id": session_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "conversation": session_llm.get_full_conversation(),
        "formatted_conversation": session_llm.get_full_conversation_formatted(),
        "summaries": session_llm.get_summaries(),
        "stats": session_llm.get_conversation_stats()
    }
    
    # Save to file
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(conversation_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Conversation saved to: {filepath}")
    return {
        "success": True,
        "filepath": str(filepath),
        "filename": filename,
        "session_id": session_id
    }


@app.post("/api/conversation/save")
async def save_conversation(session_id: str = None):
    """
    Save the conversation history to a file in the outputs directory.
    
    Args:
        session_id: The session ID to save
    
    Returns:
        File path and status
    """
    if session_id and session_id in active_sessions:
        session_llm = active_sessions[session_id]
        return save_conversation_to_file(session_id, session_llm)
    elif llm_service:
        import uuid
        return save_conversation_to_file(str(uuid.uuid4())[:8], llm_service)
    return {"error": "No session found", "success": False}


@app.get("/api/outputs")
async def list_outputs():
    """
    List all saved conversation files.
    
    Returns:
        List of saved conversation files
    """
    outputs_dir = Path(__file__).parent.parent / "data" / "outputs"
    if not outputs_dir.exists():
        return {"files": [], "total": 0}
    
    files = []
    for f in outputs_dir.glob("conversation_*.json"):
        files.append({
            "filename": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime
        })
    
    # Sort by modified time (newest first)
    files.sort(key=lambda x: x["modified"], reverse=True)
    
    return {"files": files, "total": len(files)}


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for voice conversations.
    """
    import uuid
    
    await websocket.accept()
    logger.info("WebSocket client connected")
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Create per-session services that have state (VAD and LLM)
    # This prevents users from talking over each other or sharing history
    session_vad = VADService()
    session_llm = LLMService()
    
    # Store session for API access
    active_sessions[session_id] = session_llm
    
    await asyncio.gather(
        session_vad.initialize(),
        session_llm.initialize(resume_service)
    )
    
    # Track connection state
    is_connected = True
    
    async def safe_send(data: dict):
        """Send JSON if still connected."""
        nonlocal is_connected
        if is_connected:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(f"Failed to send message: {e}")
                is_connected = False
    
    # Send initial ready status with session ID
    await safe_send({"type": "status", "status": "ready", "session_id": session_id})
    logger.info(f"Session started: {session_id}")

    try:
        while is_connected:
            try:
                message = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                break
            
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                await safe_send({"type": "error", "message": "Invalid message format"})
                continue

            msg_type = data.get("type")

            if msg_type == "audio":
                try:
                    await process_audio_safe(websocket, data.get("data", ""), safe_send, session_vad, session_llm)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Audio processing error: {e}")
                    logger.debug(traceback.format_exc())
                    await safe_send({"type": "error", "message": "Audio processing failed"})
            
            elif msg_type == "clear":
                try:
                    session_llm.clear_history()
                    session_vad.reset()
                    await safe_send({"type": "cleared"})
                    await safe_send({"type": "status", "status": "ready"})
                except Exception as e:
                    logger.error(f"Error clearing conversation: {e}")

            elif msg_type == "get_history":
                # Return full conversation history via WebSocket
                try:
                    await safe_send({
                        "type": "history",
                        "session_id": session_id,
                        "conversation": session_llm.get_full_conversation(),
                        "formatted": session_llm.get_full_conversation_formatted(),
                        "summaries": session_llm.get_summaries(),
                        "stats": session_llm.get_conversation_stats()
                    })
                except Exception as e:
                    logger.error(f"Error getting history: {e}")
                    await safe_send({"type": "error", "message": "Failed to get history"})

            elif msg_type == "new_session":
                # Start a completely fresh interview session
                try:
                    import uuid as uuid_module
                    
                    # Clear all conversation history
                    session_llm.clear_history()
                    session_vad.reset()
                    
                    # Generate new session ID
                    old_session_id = session_id
                    session_id = str(uuid_module.uuid4())
                    
                    # Update active sessions registry
                    if old_session_id in active_sessions:
                        del active_sessions[old_session_id]
                    active_sessions[session_id] = session_llm
                    
                    logger.info(f"New session started: {session_id} (replaced: {old_session_id})")
                    
                    # Notify client of new session
                    await safe_send({
                        "type": "new_session",
                        "session_id": session_id,
                        "message": "Fresh interview started"
                    })
                    await safe_send({"type": "status", "status": "ready", "session_id": session_id})
                    await safe_send({
                        "type": "stats",
                        "exchange_count": 0,
                        "session_id": session_id
                    })
                    
                    # Send initial greeting to start the interview
                    await safe_send({"type": "status", "status": "thinking"})
                    initial_greeting = "Hello! I'm excited to learn more about you. Let's start with a quick introduction - could you tell me about yourself and what brings you here today?"
                    
                    # Generate TTS for the greeting
                    try:
                        audio_bytes = await tts_service.synthesize(initial_greeting)
                        if audio_bytes:
                            # Send greeting as audio
                            await safe_send({
                                "type": "audio_chunk",
                                "data": base64.b64encode(audio_bytes).decode('utf-8'),
                                "sample_rate": 22050,
                                "is_final": True
                            })
                            # Send transcript
                            await safe_send({
                                "type": "transcript",
                                "role": "assistant",
                                "text": initial_greeting
                            })
                            logger.info(f"Sent initial greeting for session {session_id}")
                    except Exception as greeting_err:
                        logger.error(f"Failed to send initial greeting: {greeting_err}")
                    
                    await safe_send({"type": "status", "status": "ready"})
                except Exception as e:
                    logger.error(f"Error starting new session: {e}")
                    await safe_send({"type": "error", "message": "Failed to start new session"})

            elif msg_type == "end_session":
                # End session and save conversation to outputs folder
                try:
                    # Save conversation to file
                    result = save_conversation_to_file(session_id, session_llm)
                    
                    logger.info(f"Session {session_id} ended and saved to {result.get('filename', 'unknown')}")
                    
                    # Notify client
                    await safe_send({
                        "type": "session_saved",
                        "session_id": session_id,
                        "filename": result.get("filename"),
                        "filepath": result.get("filepath"),
                        "stats": session_llm.get_conversation_stats()
                    })
                except Exception as e:
                    logger.error(f"Error saving session: {e}")
                    await safe_send({"type": "error", "message": "Failed to save session"})

            elif msg_type == "ping":
                # Heartbeat to keep connection alive
                await safe_send({"type": "pong"})

            elif msg_type == "interrupt":
                # User interrupted AI speech - reset VAD and prepare for new input
                try:
                    session_vad.reset()
                    session_vad.set_processing(False)
                    logger.info(f"Session {session_id}: User interrupted AI speech")
                    await safe_send({"type": "interrupted", "message": "AI speech interrupted"})
                    await safe_send({"type": "status", "status": "ready"})
                except Exception as e:
                    logger.error(f"Error handling interrupt: {e}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        logger.debug(traceback.format_exc())
    finally:
        is_connected = False
        # Cleanup - but keep session in active_sessions for later retrieval
        # The session will be kept for 1 hour for history access
        try:
            session_vad.reset()
            # Don't close the LLM session so history can be retrieved
            # await session_llm.close()  # Commented out to preserve history
        except Exception as e:
            logger.error(f"Error during disconnection cleanup: {e}")
        logger.info(f"WebSocket client disconnected. Session {session_id} preserved for history access.")


async def process_audio_safe(websocket: WebSocket, audio_b64: str, safe_send, session_vad: VADService, session_llm: LLMService):
    """Process incoming audio and generate response if speech ended."""
    global stt_service, tts_service

    if not audio_b64:
        logger.warning("Empty audio data received")
        return

    try:
        # Decode audio (16-bit PCM, 16kHz)
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as e:
        logger.error(f"Failed to decode audio: {e}")
        return
    
    if not audio_bytes:
        logger.warning("Decoded audio is empty")
        return
    
    # VAD expects raw int16 bytes
    try:
        speech_ended, speech_audio = await session_vad.process_audio(audio_bytes)
    except Exception as e:
        logger.error(f"VAD processing error: {e}")
        logger.debug(traceback.format_exc())
        return

    if session_vad.is_speaking:
        await safe_send({"type": "status", "status": "listening"})

    if speech_ended and speech_audio is not None:
        # Lock VAD to prevent new detections during processing
        session_vad.set_processing(True)
        
        # Start timing from when user stopped talking
        speech_end_time = time.time()
        logger.info(f"⏱️ [TIMING] Speech ended at {time.strftime('%H:%M:%S', time.localtime(speech_end_time))}")
        
        try:
            # Speech segment complete - process it
            await safe_send({"type": "status", "status": "processing"})

            # Transcribe
            logger.info(f"Transcribing {len(speech_audio)} bytes of audio...")
            transcribe_start = time.time()
            try:
                transcript = await stt_service.transcribe(speech_audio)
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                logger.debug(traceback.format_exc())
                await safe_send({"type": "error", "message": "Transcription failed"})
                return
            
            transcribe_time = time.time() - transcribe_start
            logger.info(f"Transcript: '{transcript}'")
            logger.info(f"⏱️ [TIMING] Transcription took {transcribe_time:.3f}s")

            if transcript.strip():
                # Send user transcript
                await safe_send({
                    "type": "transcript",
                    "role": "user",
                    "text": transcript
                })

                # Stream LLM response with parallel TTS
                await safe_send({"type": "status", "status": "thinking"})
                logger.info("Generating streaming LLM response...")
                
                try:
                    await stream_response_with_tts(transcript, safe_send, session_llm, speech_end_time)
                except Exception as e:
                    logger.error(f"LLM/TTS streaming error: {e}")
                    logger.debug(traceback.format_exc())
                    await safe_send({"type": "error", "message": "Response generation failed"})

            await safe_send({"type": "status", "status": "ready"})
        finally:
            # Unlock VAD after processing complete
            session_vad.set_processing(False)


async def stream_response_with_tts(transcript: str, safe_send, session_llm: LLMService, speech_end_time: float = None):
    """Stream LLM response and synthesize TTS in parallel for faster response."""
    global tts_service
    
    full_response = ""
    text_buffer = ""
    chunk_index = 0
    first_token_time = None
    first_audio_time = None
    response_start_time = time.time()
    
    # Optimized chunking for faster audio delivery
    sentence_endings = {'.', '!', '?'}
    clause_endings = {',', ':', ';'}
    
    try:
        async for token in session_llm.generate_stream(transcript):
            # Track first token timing
            if first_token_time is None:
                first_token_time = time.time()
                if speech_end_time:
                    time_to_first_token = first_token_time - speech_end_time
                    logger.info(f"⏱️ [TIMING] First LLM token received: {time_to_first_token:.3f}s after speech ended")
            
            full_response += token
            text_buffer += token
            
            # AGGRESSIVE chunking for lowest latency - synthesize ASAP
            should_synthesize = False
            word_count = len(text_buffer.split())
            
            # Sentence endings (always trigger)
            if any(char in text_buffer for char in sentence_endings):
                should_synthesize = True
            
            # Clause endings with very low threshold for fast first audio
            elif word_count >= 3 and any(char in text_buffer for char in clause_endings):
                should_synthesize = True
            
            # Small max chunk for fast delivery
            elif word_count >= 6:
                should_synthesize = True
            
            if should_synthesize and text_buffer.strip():
                chunk_text = text_buffer.strip()
                text_buffer = ""
                
                # First chunk - switch to speaking status
                if chunk_index == 0:
                    await safe_send({"type": "status", "status": "speaking"})
                
                # Send text chunk immediately for display
                await safe_send({
                    "type": "text_chunk",
                    "text": chunk_text,
                    "index": chunk_index
                })
                
                # Synthesize and send audio
                logger.info(f"Synthesizing chunk {chunk_index}: '{chunk_text[:40]}...'")
                try:
                    audio = await tts_service.synthesize(chunk_text)
                except Exception as e:
                    logger.error(f"TTS synthesis error for chunk {chunk_index}: {e}")
                    logger.debug(traceback.format_exc())
                    audio = b"" # Default empty logic
                
                if len(audio) > 0:
                    try:
                        # Handle OpenAI MP3 (bytes) vs Piper PCM (numpy)
                        if isinstance(audio, bytes):
                             audio_b64 = base64.b64encode(audio).decode()
                             duration_est = len(audio) / 8000 # Rough estimate for logging
                        else:
                             # Legacy Piper/PCM (numpy)
                             audio = np.clip(audio, -1.0, 1.0)
                             audio_int16 = (audio * 32767).astype(np.int16)
                             audio_b64 = base64.b64encode(audio_int16.tobytes()).decode()
                             duration_est = len(audio) / tts_service.sample_rate
                        
                        await safe_send({
                            "type": "audio_chunk",
                            "data": audio_b64,
                            "sample_rate": tts_service.sample_rate,
                            "index": chunk_index,
                            "format": "mp3" if isinstance(audio, bytes) else "pcm"
                        })
                        
                        # Track first audio timing
                        if first_audio_time is None:
                            first_audio_time = time.time()
                            if speech_end_time:
                                time_to_first_audio = first_audio_time - speech_end_time
                                logger.info(f"⏱️ [TIMING] First audio chunk sent: {time_to_first_audio:.3f}s after speech ended")
                        
                        logger.info(f"Audio chunk {chunk_index} sent (approx {duration_est:.2f}s)")
                    except Exception as e:
                        logger.error(f"Error encoding/sending audio chunk {chunk_index}: {e}")
                
                chunk_index += 1
        
        # Handle any remaining text
        if text_buffer.strip():
            chunk_text = text_buffer.strip()
            
            if chunk_index == 0:
                await safe_send({"type": "status", "status": "speaking"})
            
            await safe_send({
                "type": "text_chunk",
                "text": chunk_text,
                "index": chunk_index
            })
            
            logger.info(f"Synthesizing final chunk: '{chunk_text[:40]}...'")
            try:
                audio = await tts_service.synthesize(chunk_text)
            except Exception as e:
                logger.error(f"TTS synthesis error for final chunk: {e}")
                logger.debug(traceback.format_exc())
                audio = np.array([], dtype=np.float32)
            
            if len(audio) > 0:
                try:
                    # Handle OpenAI MP3 (bytes) vs Piper PCM (numpy)
                    if isinstance(audio, bytes):
                            audio_b64 = base64.b64encode(audio).decode()
                    else:
                            # Legacy Piper/PCM (numpy)
                            audio = np.clip(audio, -1.0, 1.0)
                            audio_int16 = (audio * 32767).astype(np.int16)
                            audio_b64 = base64.b64encode(audio_int16.tobytes()).decode()
                    
                    await safe_send({
                        "type": "audio_chunk",
                        "data": audio_b64,
                        "sample_rate": tts_service.sample_rate,
                        "index": chunk_index,
                        "format": "mp3" if isinstance(audio, bytes) else "pcm",
                        "is_final": True
                    })
                except Exception as e:
                     logger.error(f"Error sending final chunk: {e}")

        
        # Send complete response for history
        await safe_send({
            "type": "transcript",
            "role": "assistant",
            "text": full_response
        })
        
        # Send updated stats (exchange count, etc.)
        try:
            stats = session_llm.get_conversation_stats()
            await safe_send({
                "type": "stats",
                "exchange_count": stats.get("exchange_count", 0),
                "is_summarizing": stats.get("is_summarizing", False),
                "next_summarization_at": stats.get("next_summarization_at", 10)
            })
        except Exception as e:
            logger.debug(f"Failed to send stats: {e}")
        
        # Log final timing summary
        total_time = time.time() - response_start_time
        logger.info(f"Streaming complete. Total response: {len(full_response)} chars")
        if speech_end_time:
            end_to_end_time = time.time() - speech_end_time
            logger.info(f"⏱️ [TIMING] === Response Summary ===")
            logger.info(f"⏱️ [TIMING] Total end-to-end latency: {end_to_end_time:.3f}s (from speech end to response complete)")
            logger.info(f"⏱️ [TIMING] LLM+TTS streaming took: {total_time:.3f}s")
    
    except Exception as e:
        logger.error(f"Error in stream_response_with_tts: {e}")
        logger.debug(traceback.format_exc())
        raise


def run_server():
    """Run the server."""
    import uvicorn
    import socket
    
    # Check if port is available
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((config.server.host, config.server.port))
        sock.close()
    except OSError as e:
        if e.errno == 10048:  # Port already in use
            logger.error(f"Port {config.server.port} is already in use!")
            logger.error("Please either:")
            logger.error(f"  1. Kill the process using port {config.server.port}, or")
            logger.error("  2. Set SERVER_PORT environment variable to a different port")
            logger.error(f"\nTo kill the process on Windows, run: netstat -ano | findstr :{config.server.port}")
            logger.error("Then use: taskkill /F /PID <PID>")
            raise SystemExit(1)
        raise
    
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
