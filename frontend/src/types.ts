
export enum InterviewStatus {
  IDLE = 'IDLE',
  THINKING = 'Thinking',
  SPEAKING = 'Speaking',
  ANALYZING = 'Analyzing'
}

export interface ResumeData {
  fileName: string;
  content?: string;
}

export type AppState = 'landing' | 'upload' | 'interview';
