from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class InterviewPhase(str, Enum):
    GREETING = "PHASE 1: GREETING (Professional Start)"
    INTRO = "PHASE 2: INTRODUCTION"
    RESUME_DEEP_DIVE = "PHASE 3: RESUME DEEP DIVE"
    TECHNICAL = "PHASE 4: TECHNICAL EVALUATION"
    CROSS_QUESTION = "PHASE 5: CROSS QUESTIONING"
    BEHAVIORAL = "PHASE 6: BEHAVIORAL (Ownership Focus)"
    TWIST = "PHASE 7: INTERVIEW TWIST"
    WRAPUP = "PHASE 8: WRAP-UP"

class InterviewState(BaseModel):
    phase: InterviewPhase = InterviewPhase.GREETING
    difficulty: str = "Medium"
    focus_area: str = "General"
    candidate_name: str = "Candidate"
    
class InterviewOutput(BaseModel):
    interviewer_message: str = Field(description="The question or response to the candidate")
    interview_state_update: dict = Field(description="Updates to phase, difficulty, or focus_area")
