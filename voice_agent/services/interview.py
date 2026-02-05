import json
import logging
import os
from typing import Optional, Dict, Any

from ..models.interview import InterviewState, InterviewPhase, InterviewOutput
from .resume import ResumeService

logger = logging.getLogger(__name__)

class InterviewManager:
    """
    Manages the 7-phase interview flow and state.
    """
    def __init__(self, resume_service: ResumeService):
        self.state = InterviewState()
        self.resume_service = resume_service
        self.history = []
        
        # Load System Prompt from file
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "base_prompt.md")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.base_prompt_template = f.read()
        except FileNotFoundError:
            logger.error(f"Prompt file not found at {prompt_path}")
            # Fallback to a minimal prompt to prevent crash
            self.base_prompt_template = "You are a Technical Interviewer. Assess the candidate."

    def update_state(self, update_dict: dict) -> None:
        """Update state from LLM JSON output."""
        if not update_dict:
            return
            
        if "phase" in update_dict:
            try:
                self.state.phase = InterviewPhase(update_dict["phase"])
            except ValueError:
                logger.warning(f"Invalid phase: {update_dict['phase']}")
                
        if "difficulty" in update_dict:
            self.state.difficulty = update_dict["difficulty"]
        if "focus_area" in update_dict:
            self.state.focus_area = update_dict["focus_area"]

    def get_system_prompt(self) -> str:
        """Generate the prompt for natural conversation."""
        phase = self.state.phase
        
        # Start with the file content
        prompt = self.base_prompt_template
        
        # Add Resume Context for personalization
        if self.resume_service:
            # Get comprehensive candidate info
            name_info = self.resume_service.query_resume("name contact", k=1)
            skills_info = self.resume_service.query_resume("skills technologies programming languages", k=2)
            experience_info = self.resume_service.query_resume("experience projects work internship", k=3)
            education_info = self.resume_service.query_resume("education degree university college", k=1)
            
            prompt += f"""

---
## CANDIDATE RESUME INFORMATION

### Basic Info:
{name_info}

### Education:
{education_info}

### Skills & Technologies:
{skills_info}

### Experience & Projects:
{experience_info}

---
Use this information to:
1. Address the candidate by name
2. Ask about SPECIFIC projects/experiences from their resume
3. Probe into skills they claim to have
4. Connect their background to your questions
"""
        
        prompt += """
---
## OUTPUT FORMAT
- Respond ONLY with what you would SAY out loud to the candidate
- Keep it SHORT (1-2 sentences max)
- React briefly to their answer, then ask ONE follow-up question
- Sound natural and conversational - this is a voice interview
"""
        return prompt

    def get_next_phase(self, current_phase: InterviewPhase) -> InterviewPhase:
        """Linear progression helper (LLM can override, but this guides)."""
        phases = list(InterviewPhase)
        idx = phases.index(current_phase)
        if idx < len(phases) - 1:
            return phases[idx + 1]
        return current_phase
