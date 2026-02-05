
import React from 'react';
import { InterviewStatus } from '../types';

interface StatusIndicatorProps {
  status: InterviewStatus;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status }) => {
  const getStatusColor = () => {
    switch (status) {
      case InterviewStatus.SPEAKING: return 'bg-green-500/20 text-green-400 border-green-500/30';
      case InterviewStatus.THINKING: return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case InterviewStatus.ANALYZING: return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  if (status === InterviewStatus.IDLE) return null;

  return (
    <div className={`fixed top-8 right-8 px-4 py-2 rounded-full border glass-morphism flex items-center gap-2 animate-fade-in ${getStatusColor()}`}>
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-current"></span>
      </span>
      <span className="text-sm font-medium tracking-wide uppercase">{status}</span>
    </div>
  );
};

export default StatusIndicator;
