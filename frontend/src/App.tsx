
import React, { useState } from 'react';
import LandingPage from './pages/LandingPage';
import UploadPage from './pages/UploadPage';
import InterviewPage from './pages/InterviewPage';
import { AppState, ResumeData } from './types';

const App: React.FC = () => {
  const [currentStep, setCurrentStep] = useState<AppState>('landing');
  const [resumeData, setResumeData] = useState<ResumeData | null>(null);

  const handleStart = () => setCurrentStep('upload');
  const handleUpload = (data: ResumeData) => {
    setResumeData(data);
    setCurrentStep('interview');
  };
  const handleBack = () => setCurrentStep('landing');
  const handleEnd = () => {
    setResumeData(null);
    setCurrentStep('landing');
  };

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      {currentStep === 'landing' && (
        <LandingPage onStart={handleStart} />
      )}
      
      {currentStep === 'upload' && (
        <UploadPage onUpload={handleUpload} onBack={handleBack} />
      )}

      {currentStep === 'interview' && (
        <InterviewPage resume={resumeData} onEnd={handleEnd} />
      )}
    </div>
  );
};

export default App;
