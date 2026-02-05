
import React, { useState } from 'react';
import { ResumeData } from '../types';

interface UploadPageProps {
  onUpload: (data: ResumeData) => void;
  onBack: () => void;
}

// Backend URL - dynamically uses current host for network access (v2)
const getApiBaseUrl = () => {
  // Use env var if set, otherwise use dynamic hostname
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL as string;
  }
  // This allows access from any device on the same network
  return `http://${window.location.hostname}:8000`;
};

const UploadPage: React.FC<UploadPageProps> = ({ onUpload, onBack }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      // Upload to backend
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${getApiBaseUrl()}/api/upload-resume`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const result = await response.json();
      onUpload({ fileName: file.name, content: result.message || "Resume processed" });
    } catch (err: any) {
      setError(err.message || 'Failed to upload. Please try again.');
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-[#0a0a0a] text-white">
      <div className="max-w-md w-full">
        <button
          onClick={onBack}
          className="mb-8 text-gray-500 hover:text-white flex items-center gap-2 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Go Back
        </button>

        <h2 className="text-3xl font-bold mb-2">Upload Resume</h2>
        <p className="text-gray-500 mb-8">We'll use your resume to tailor the interview questions.</p>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
            {error}
          </div>
        )}

        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
              setFile(e.dataTransfer.files[0]);
            }
          }}
          className={`relative border-2 border-dashed rounded-3xl p-12 transition-all flex flex-col items-center justify-center cursor-pointer
            ${isDragging ? 'border-cyan-500 bg-cyan-500/5' : 'border-white/10 hover:border-white/20 hover:bg-white/5'}
            ${file ? 'border-cyan-500/50 bg-cyan-500/5' : ''}`}
        >
          <input
            type="file"
            className="absolute inset-0 opacity-0 cursor-pointer"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.txt"
          />

          <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
            <svg className={`w-8 h-8 ${file ? 'text-cyan-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>

          <p className="text-center font-medium">
            {file ? file.name : 'Click to upload or drag & drop'}
          </p>
          <p className="text-xs text-gray-500 mt-2">PDF, DOCX up to 10MB</p>
        </div>

        <button
          disabled={!file || isUploading}
          onClick={handleSubmit}
          className={`w-full mt-8 py-4 rounded-full font-semibold transition-all
            ${file && !isUploading
              ? 'bg-cyan-500 text-white hover:bg-cyan-400 shadow-lg shadow-cyan-500/20'
              : 'bg-white/5 text-gray-500 cursor-not-allowed'}`}
        >
          {isUploading ? 'Uploading...' : 'Continue to Interview'}
        </button>
      </div>
    </div>
  );
};

export default UploadPage;
