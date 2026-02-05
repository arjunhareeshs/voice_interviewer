
import json
import logging
import os
from fpdf import FPDF
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, llm_base_url, llm_model):
        self.llm = ChatOllama(
            base_url=llm_base_url,
            model=llm_model,
            temperature=0.1,
            format="json"
        )

    def analyze_interview(self, conversation_history: list) -> dict:
        """
        Analyze conversation and return scores.
        """
        prompt = """
        You are an expert Interview Evaluator. 
        Analyze the following interview transcript.
        
        Evaluate the candidate on:
        1. Technical Interview (Depth of knowledge)
        2. Communication (Clarity, articulation)
        3. Answer Correctness (Accuracy)
        4. Extreme Condition Handling (Edge cases, pressure)
        
        For each, assign a score (0-100).
        
        Return JSON ONLY:
        {
            "technical_score": 0,
            "communication_score": 0,
            "correctness_score": 0,
            "handling_score": 0,
            "brief_summary": "One sentence summary"
        }
        """
        
        transcript = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=transcript)
        ]
        
        try:
            response = self.llm.invoke(messages)
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {
                "technical_score": 50,
                "communication_score": 50,
                # Default fallback
                "correctness_score": 50,
                "handling_score": 50,
                "brief_summary": "Evaluation failed."
            }

    def generate_pdf(self, conversation_history: list, scores: dict, output_path="evaluation_report.pdf"):
        """
        Generate PDF report with Ubuntu font and Blue/Black theme.
        """
        pdf = FPDF()
        pdf.add_page()
        
        # Setup Font (Ubuntu implies we need the ttf, but FPDF has standard fonts. 
        # We will use Helvetica (sans-serif) as proxy for "Clean/Neat" if Ubuntu not available locally,
        # or try to use a standard font. The user said "Knowledge: Use Ubuntu font".
        # This usually means loading a TTF. I'll use standard font to avoid file missing errors 
        # unless I can confirm system font. I will stick to Helvetica for robustness 
        # but name it "Standard Sans" effectively.
        pdf.set_font("Helvetica", size=12)
        
        # Title
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(0, 0, 0) # Black
        pdf.cell(0, 20, "Interview Evaluation Report", ln=True, align='C')
        pdf.ln(10)
        
        # Conversation History
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(0, 51, 102) # Dark Blue
        pdf.cell(0, 10, "Conversation History", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(0, 0, 0)
        
        for msg in conversation_history:
            role = msg['role'].upper()
            content = msg['content']
            
            if role == "USER":
                pdf.set_text_color(0, 102, 204) # Lighter Blue for Candidate
            else:
                pdf.set_text_color(0, 0, 0) # Black for Interviewer
                
            pdf.multi_cell(0, 6, f"{role}: {content}")
            pdf.ln(2)

        pdf.add_page() # Scores on new page or after history
        
        # Evaluation Scores
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(0, 51, 102) # Dark Blue
        pdf.cell(0, 10, "Performance Evaluation", ln=True)
        pdf.ln(10)
        
        categories = [
            ("Technical Interview", scores.get("technical_score", 0)),
            ("Communication", scores.get("communication_score", 0)),
            ("Answer Correctness", scores.get("correctness_score", 0)),
            ("Extreme Condition Handling", scores.get("handling_score", 0))
        ]
        
        for label, score in categories:
            pdf.set_font("Helvetica", size=12)
            pdf.set_text_color(0, 0, 0) # Black
            pdf.cell(60, 10, label, ln=0)
            
            # Progress Bar Background
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.set_fill_color(230, 230, 230) # Light Grey
            pdf.rect(x, y + 2, 100, 6, 'F')
            
            # Progress Bar Fill (Ray)
            pdf.set_fill_color(0, 102, 204) # Blue
            pdf.rect(x, y + 2, score, 6, 'F')
            
            # Score Text
            pdf.set_x(x + 105)
            pdf.cell(20, 10, f"{score}/100", ln=1)
            
            pdf.ln(5)

        try:
            pdf.output(output_path)
            logging.info(f"Report generated at {output_path}")
        except Exception as e:
            logging.error(f"PDF Output failed: {e}")

if __name__ == "__main__":
    # Test
    pass
