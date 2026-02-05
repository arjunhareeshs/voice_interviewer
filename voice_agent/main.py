"""
Voice Agent Main Entry Point.
"""

import argparse
import sys


def main():
    """Main entry point for the voice agent."""
    parser = argparse.ArgumentParser(
        description="Voice Agent - Real-time conversational AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    args = parser.parse_args()

    # Update config with CLI args
    from .config import config
    config.server.host = args.host
    config.server.port = args.port

    print("""
---------------------------------------------------------------
              Voice Interview Agent
           Real-time AI Voice Interviewer
---------------------------------------------------------------
  Powered by:
    * LangChain + Ollama (LLM)
    * Deepgram Nova-2 (Speech-to-Text)
    * Deepgram Aura (Text-to-Speech)
    * Silero VAD (Voice Activity Detection)
---------------------------------------------------------------
""")

    import uvicorn
    uvicorn.run(
        "voice_agent.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
