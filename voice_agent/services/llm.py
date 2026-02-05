"""
LLM Service using LangChain Agent with Ollama.
Now integrated with InterviewManager for structured, 7-phase technical interviews.
"""

import asyncio
import datetime
import logging
import json
import os
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_ollama import ChatOllama
# We keep agent imports if we need tools later, but strictly speaking 
# the interview flow is now driven by the InterviewManager's prompts.
# We will use the direct LLM invoke for the tight control required by the prompt.

from ..config import config
from ..models.interview import InterviewOutput
from .resume import ResumeService
from .interview import InterviewManager

logger = logging.getLogger(__name__)

SUMMARIZATION_PROMPT = """You are a conversation summarizer. Create a concise 2-sentence summary of the following conversation segment.
Conversation to summarize:
{conversation}
Provide ONLY the 2-sentence summary, nothing else."""

class LLMService:
    """
    LLM Service for Technical Interviewing.
    Orchestrates ResumeService and InterviewManager.
    """

    def __init__(self):
        self.llm: Optional[ChatOllama] = None
        self.resume_service: Optional[ResumeService] = None
        self.interview_manager: Optional[InterviewManager] = None
        
        # Memory management
        self.conversation_history: List[BaseMessage] = []
        self.max_history = 20 # Keep it tighter for interview focus
        
        self.full_conversation_archive: List[dict] = []
        self.exchange_count: int = 0

    async def initialize(self, resume_service: ResumeService) -> None:
        """Initialize LLM and Interview Manager with shared ResumeService."""
        logger.info(f"Initializing Interviewer with Ollama: {config.ollama.model}")
        
        self.resume_service = resume_service
        
        # Create two LLM instances:
        # 1. Streaming LLM without JSON format for fast, token-by-token responses
        self.llm = ChatOllama(
            base_url=config.ollama.base_url,
            model=config.ollama.model,
            temperature=config.ollama.temperature,
            verbose=False,
        )
        
        
        # 2. JSON LLM for structured state updates (used after streaming completes)
        self.llm_json = ChatOllama(
            base_url=config.ollama.base_url,
            model=config.ollama.model,
            temperature=config.ollama.temperature,
            verbose=False,
            format="json"
        )
        
        # Initialize Interview Manager with the shared resume service
        self.interview_manager = InterviewManager(self.resume_service)
        
        # Test connection
        try:
            # Quick test
            pass 
            logger.info("Interviewer System initialized")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    async def close(self) -> None:
        """Close services and generate report."""
        try:
           from .report import ReportGenerator
           
           # Generate Report
           if self.full_conversation_archive:
               logging.info("Generating evaluation report...")
               reporter = ReportGenerator(config.ollama.base_url, config.ollama.model)
               scores = reporter.analyze_interview(self.full_conversation_archive)
               reporter.generate_pdf(self.full_conversation_archive, scores, "evaluation_report.pdf")
               logging.info("Evaluation report generated.")
        except Exception as e:
            logging.error(f"Failed to generate report on close: {e}")
            
    def clear_history(self) -> None:
        self.conversation_history.clear()
        self.full_conversation_archive.clear()
        self.exchange_count = 0
    
    def _archive_message(self, role: str, content: str) -> None:
        self.full_conversation_archive.append({
            "exchange_number": self.exchange_count,
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Save to output.json immediately (robustness)
        try:
            with open("output.json", "w", encoding="utf-8") as f:
                json.dump(self.full_conversation_archive, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save output.json: {e}")
    
    def get_full_conversation_formatted(self) -> str:
        return str(self.full_conversation_archive)

    async def generate_response(self, user_message: str) -> str:
        """Video Interview Logic."""
        if self.llm is None or self.interview_manager is None:
            raise RuntimeError("Service not initialized.")

        # 0. Add User Message
        self.conversation_history.append(HumanMessage(content=user_message))
        self._archive_message("user", user_message)

        # 1. Get Prompt from Manager (State Aware)
        # We need to supply the system prompt. The Manager does the heavy lifting.
        system_prompt = self.interview_manager.get_system_prompt()
        
        # We construct messages. 
        # Note: We need to be careful with history. The Prompt changes every turn 
        # to reflect the CURRENT phase. So we might treat history strictly as context
        # but the System Instruction is the primary driver.
        messages = [
            SystemMessage(content=system_prompt),
            *self.conversation_history[-10:] # Keep recent context mainly
        ]

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.llm.invoke(messages)
            )
            
            content = response.content.strip()
            logger.debug(f"LLM Raw JSON: {content}")
            
            # 2. Parse JSON
            try:
                data = json.loads(content)
                interview_output = InterviewOutput(**data)
                
                # 3. Update State
                self.interview_manager.update_state(interview_output.interview_state_update)
                
                response_text = interview_output.interviewer_message
            except Exception as parse_error:
                logger.error(f"JSON Parse Error: {parse_error} in content: {content}")
                response_text = "Could you clarify that? I missed the details." 
            
            # 4. Update History
            self.conversation_history.append(AIMessage(content=response_text))
            self.exchange_count += 1
            self._archive_message("assistant", response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return "Let's move on. Tell me about your next experience."

    async def generate_stream(self, user_message: str):
        """
        TRUE STREAMING: Yield sentences as they form for low-latency TTS.
        
        State Machine:
        1. Stream tokens from LLM
        2. Accumulate into sentence buffer
        3. On sentence boundary (.!?), yield for TTS immediately
        4. Archive full response after completion
        """
        self.exchange_count += 1
        messages = self._build_messages(user_message)
        
        full_response = ""
        sentence_buffer = ""
        sentence_endings = {'.', '!', '?'}
        yielded_count = 0
        
        try:
            # TRUE STREAMING: yield sentences as they complete
            async for chunk in self.llm.astream(messages):
                # Extract token from chunk
                if hasattr(chunk, 'content'):
                    token = chunk.content
                elif isinstance(chunk, str):
                    token = chunk
                else:
                    continue
                
                if not token:
                    continue
                    
                full_response += token
                sentence_buffer += token
                
                # Check for sentence boundaries - yield immediately for fast TTS
                # This is the key latency optimization!
                if any(char in token for char in sentence_endings):
                    # Clean up the sentence
                    sentence = sentence_buffer.strip()
                    if sentence and len(sentence) > 5:  # Avoid yielding tiny fragments
                        logger.info(f"⏱️ [STREAMING] Yielding sentence {yielded_count}: '{sentence[:50]}...'")
                        yield sentence
                        yielded_count += 1
                        sentence_buffer = ""
            
            # Yield any remaining text
            if sentence_buffer.strip() and len(sentence_buffer.strip()) > 3:
                yield sentence_buffer.strip()
                yielded_count += 1
            
            # Archive the complete response
            if full_response.strip():
                self.conversation_history.append(AIMessage(content=full_response))
                self._archive_message("assistant", full_response)
            
            logger.info(f"⏱️ [STREAMING] Complete: yielded {yielded_count} sentences, total {len(full_response)} chars")
                
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield "I apologize, could you please repeat that?"
    
    def _build_messages(self, user_message: str) -> list:
        """Build message list for LLM with system prompt and conversation history."""
        # Add user message to history first
        self.conversation_history.append(HumanMessage(content=user_message))
        self._archive_message("user", user_message)
        
        # Get system prompt from interview manager
        system_prompt = self.interview_manager.get_system_prompt() if self.interview_manager else ""
        
        messages = [
            SystemMessage(content=system_prompt),
            *self.conversation_history[-10:]  # Keep recent context
        ]
        return messages
    
    async def _check_and_search(self, user_message: str):
        pass  # Deprecated in Interview Mode
    
    def get_full_conversation(self) -> list:
        """Return the complete conversation archive."""
        return self.full_conversation_archive
    
    def get_summaries(self) -> list:
        """Return conversation summaries (not implemented for interviews)."""
        return []
    
    def get_conversation_stats(self) -> dict:
        return {
            "phase": self.interview_manager.state.phase.value if self.interview_manager else "N/A",
            "exchanges": self.exchange_count,
            "exchange_count": self.exchange_count,
            "full_archive_length": len(self.full_conversation_archive)
        }

