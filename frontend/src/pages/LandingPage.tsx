
import React from 'react';

interface LandingPageProps {
  onStart: () => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ onStart }) => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden bg-[#0a0a0a]">
      {/* Background Orbs */}
      <div className="absolute top-1/4 -left-20 w-96 h-96 bg-cyan-900/20 rounded-full blur-[120px] animate-pulse-slow"></div>
      <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-blue-900/20 rounded-full blur-[120px] animate-pulse-slow" style={{ animationDelay: '2s' }}></div>

      <div className="z-10 text-center max-w-3xl">
        <div className="mb-8 inline-block">
          <div className="w-20 h-20 mx-auto rounded-3xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-2xl shadow-cyan-500/20">
             <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
             </svg>
          </div>
        </div>
        
        <h1 className="text-5xl md:text-7xl font-bold mb-6 tracking-tight bg-clip-text text-transparent bg-gradient-to-b from-white to-gray-400">
          Aura Voice
        </h1>
        <p className="text-xl md:text-2xl text-gray-400 mb-12 font-light leading-relaxed">
          The next generation of <span className="text-cyan-400 font-medium">resume-based interview</span> experiences. 
          Conduct your most <span className="text-white font-medium">critical interview session</span> with our advanced voice agent.
        </p>

        <button 
          onClick={onStart}
          className="group relative px-8 py-4 bg-white text-black font-semibold rounded-full overflow-hidden transition-all hover:scale-105 active:scale-95"
        >
          <div className="absolute inset-0 w-3 bg-cyan-400 transition-all duration-[250ms] ease-out group-hover:w-full"></div>
          <span className="relative group-hover:text-white transition-colors duration-[250ms]">Start Journey</span>
        </button>

        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
          <div className="p-6 rounded-2xl border border-white/5 bg-white/5">
            <h3 className="text-white font-medium mb-2">Voice Optimized</h3>
            <p className="text-sm text-gray-500 leading-relaxed">Real-time low latency conversation powered by cutting-edge neural models.</p>
          </div>
          <div className="p-6 rounded-2xl border border-white/5 bg-white/5">
            <h3 className="text-white font-medium mb-2">Context Aware</h3>
            <p className="text-sm text-gray-500 leading-relaxed">Deep analysis of your resume to provide tailored questions and feedback.</p>
          </div>
          <div className="p-6 rounded-2xl border border-white/5 bg-white/5">
            <h3 className="text-white font-medium mb-2">Dark Immersive</h3>
            <p className="text-sm text-gray-500 leading-relaxed">Focused, distraction-free environment designed for peak performance.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
