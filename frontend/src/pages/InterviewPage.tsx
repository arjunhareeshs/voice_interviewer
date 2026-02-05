
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { InterviewStatus, ResumeData } from '../types';
import Visualizer from '../components/Visualizer';
import StatusIndicator from '../components/StatusIndicator';
import { decode, decodeAudioData, encode } from '../services/audioUtils';

interface InterviewPageProps {
  resume: ResumeData | null;
  onEnd: () => void;
}

// Backend WebSocket URL - dynamically uses current host for network access (v2)
const getWsBaseUrl = () => {
  // Use env var if set, otherwise use dynamic hostname
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL as string;
  }
  // This allows access from any device on the same network
  return `ws://${window.location.hostname}:8000`;
};

const InterviewPage: React.FC<InterviewPageProps> = ({ resume, onEnd }) => {
  const [status, setStatus] = useState<InterviewStatus>(InterviewStatus.IDLE);
  const [isActive, setIsActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const inputContextRef = useRef<AudioContext | null>(null);
  const outputNodeRef = useRef<GainNode | null>(null);
  const nextStartTimeRef = useRef<number>(0);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  // Map backend status to frontend enum
  const mapStatus = (backendStatus: string): InterviewStatus => {
    switch (backendStatus.toLowerCase()) {
      case 'thinking':
      case 'processing':
        return InterviewStatus.THINKING;
      case 'speaking':
        return InterviewStatus.SPEAKING;
      case 'analyzing':
        return InterviewStatus.ANALYZING;
      default:
        return InterviewStatus.IDLE;
    }
  };

  const cleanup = useCallback(() => {
    setIsActive(false);
    setStatus(InterviewStatus.IDLE);

    // Stop audio sources
    sourcesRef.current.forEach(s => { try { s.stop(); } catch (e) { } });
    sourcesRef.current.clear();

    // Disconnect processor
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    // Stop media stream
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const startInterview = async () => {
    try {
      setIsActive(true);
      setStatus(InterviewStatus.ANALYZING);
      setError(null);

      // Request microphone permission
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          } 
        });
      } catch (err: any) {
        let errorMessage = 'Microphone access denied. ';
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          errorMessage += 'Please allow microphone access and try again.';
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          errorMessage += 'No microphone detected.';
        } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
          errorMessage += 'Microphone is being used by another application.';
        } else {
          errorMessage += err.message || 'Please check your microphone settings.';
        }
        
        setError(errorMessage);
        setIsActive(false);
        return;
      }

      // Initialize audio contexts
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const inputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;
      inputContextRef.current = inputCtx;
      mediaStreamRef.current = stream;

      const outNode = audioCtx.createGain();
      outNode.connect(audioCtx.destination);
      outputNodeRef.current = outNode;

      // Connect to backend WebSocket
      const ws = new WebSocket(`${getWsBaseUrl()}/ws/voice`);
      wsRef.current = ws;

      ws.onopen = () => {
        // Start new session
        ws.send(JSON.stringify({ type: 'new_session' }));

        // Setup audio processing
        const source = inputCtx.createMediaStreamSource(stream);
        const processor = inputCtx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;

          const inputData = e.inputBuffer.getChannelData(0);
          const int16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            int16[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
          }
          const base64 = encode(new Uint8Array(int16.buffer));
          ws.send(JSON.stringify({ type: 'audio', data: base64 }));
        };

        source.connect(processor);
        processor.connect(inputCtx.destination);
        setStatus(InterviewStatus.IDLE);
      };

      ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'status':
            setStatus(mapStatus(data.status));
            break;

          case 'audio_chunk':
            if (audioContextRef.current && outputNodeRef.current) {
              setStatus(InterviewStatus.SPEAKING);
              const ctx = audioContextRef.current;
              nextStartTimeRef.current = Math.max(nextStartTimeRef.current, ctx.currentTime);

              try {
                const audioBuffer = await decodeAudioData(
                  decode(data.data),
                  ctx,
                  data.sample_rate || 22050,
                  1
                );
                const source = ctx.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(outputNodeRef.current);

                source.addEventListener('ended', () => {
                  sourcesRef.current.delete(source);
                  if (sourcesRef.current.size === 0 && data.is_final) {
                    setStatus(InterviewStatus.IDLE);
                  }
                });

                source.start(nextStartTimeRef.current);
                nextStartTimeRef.current += audioBuffer.duration;
                sourcesRef.current.add(source);
              } catch (e) {
                console.error('Audio decode error:', e);
              }
            }
            break;

          case 'error':
            setError(data.message);
            break;
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Failed to connect to backend. Please ensure the server is running.');
        cleanup();
      };

      ws.onclose = () => {
        if (isActive) {
          setError('Connection to backend lost.');
          cleanup();
        }
      };

    } catch (err: any) {
      console.error('Interview setup error:', err);
      setError(err.message || 'Failed to start interview.');
      setIsActive(false);
      cleanup();
    }
  };

  const handleEnd = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_session' }));
    }
    cleanup();
    onEnd();
  };

  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-between p-12 bg-black text-white relative">
      <StatusIndicator status={status} />

      <header className="text-center">
        <h1 className="text-lg font-light tracking-[0.3em] uppercase text-gray-500 mb-2">Interview Session</h1>
        <p className="text-2xl font-medium">Candidate Session</p>
      </header>

      <main className="flex-1 flex items-center justify-center w-full">
        {error ? (
          <div className="text-center max-w-sm glass-morphism p-8 rounded-3xl border-red-500/20">
            <p className="text-red-400 mb-4">{error}</p>
            <button onClick={() => { setError(null); cleanup(); }} className="text-sm underline text-gray-400 hover:text-white">Try Again</button>
          </div>
        ) : (
          <div className="relative group">
            <div className={`absolute inset-0 bg-cyan-500/10 blur-[100px] rounded-full transition-opacity duration-1000 ${isActive ? 'opacity-100' : 'opacity-0'}`}></div>
            <Visualizer status={status} isActive={isActive} />
          </div>
        )}
      </main>

      <footer className="w-full flex flex-col items-center gap-4">
        {!isActive ? (
          <button
            onClick={startInterview}
            className="px-12 py-5 bg-white text-black rounded-full font-bold hover:scale-105 active:scale-95 transition-all shadow-[0_0_30px_rgba(255,255,255,0.1)]"
          >
            Start Interview
          </button>
        ) : (
          <button
            onClick={handleEnd}
            className="px-8 py-3 bg-red-500/10 border border-red-500/30 text-red-500 rounded-full font-medium hover:bg-red-500/20 transition-all"
          >
            End Interview
          </button>
        )}
      </footer>
    </div>
  );
};

export default InterviewPage;
