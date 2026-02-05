
import React, { useEffect, useRef } from 'react';
import { InterviewStatus } from '../types';

interface VisualizerProps {
  status: InterviewStatus;
  isActive: boolean;
}

const Visualizer: React.FC<VisualizerProps> = ({ status, isActive }) => {
  const barsRef = useRef<HTMLDivElement[]>([]);

  useEffect(() => {
    if (!isActive) return;

    let animationId: number;
    const animate = () => {
      barsRef.current.forEach((bar, i) => {
        if (!bar) return;
        
        let height = 16; // Increased base height
        if (status === InterviewStatus.SPEAKING) {
          // Significant pumping volume: Base 40px + up to 120px random variation
          height = 40 + Math.random() * 120;
        } else if (status === InterviewStatus.THINKING) {
          // Smooth wave: Base 30px + 20px sin wave
          height = 30 + Math.sin(Date.now() * 0.005 + i) * 20;
        } else if (status === InterviewStatus.ANALYZING) {
          // Jitter: Base 20px + 40px random
          height = 20 + Math.random() * 40;
        } else {
          height = 16;
        }
        
        bar.style.height = `${height}px`;
        // Use faster transitions for speaking to feel more responsive to audio
        bar.style.transition = status === InterviewStatus.SPEAKING ? 'height 0.05s ease-out' : 'height 0.4s ease-in-out';
      });
      animationId = requestAnimationFrame(animate);
    };

    animate();
    return () => cancelAnimationFrame(animationId);
  }, [status, isActive]);

  return (
    <div className="flex items-center justify-center gap-4 h-64 w-full">
      {[...Array(5)].map((_, i) => (
        <div
          key={i}
          ref={(el) => (barsRef.current[i] = el!)}
          className={`w-4 md:w-6 rounded-full transition-all duration-300 ${
            isActive 
              ? 'bg-cyan-400 shadow-[0_0_25px_rgba(34,211,238,0.6)]' 
              : 'bg-gray-800'
          }`}
          style={{ height: '16px' }}
        />
      ))}
    </div>
  );
};

export default Visualizer;
