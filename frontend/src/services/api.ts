/**
 * API Service - Handles all backend communication
 */

// Backend URL - dynamically uses the current host for network access
const getApiBaseUrl = (): string => {
    // If environment variable is set, use it
    if (import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL as string;
    }
    // Otherwise, use the current host (works on both localhost and network IP)
    const host = window.location.hostname;
    const port = window.location.port || '8000';
    // If we're on the same port as the backend, use that port
    return `http://${host}:8000`;
};

const getWsBaseUrl = (): string => {
    // If environment variable is set, use it
    if (import.meta.env.VITE_WS_URL) {
        return import.meta.env.VITE_WS_URL as string;
    }
    // Otherwise, use the current host (works on both localhost and network IP)
    const host = window.location.hostname;
    return `ws://${host}:8000`;
};

// Use getter functions directly instead of cached values

/**
 * Upload resume to backend for extraction and vector store creation
 */
export async function uploadResume(file: File): Promise<{ success: boolean; message: string; filename: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${getApiBaseUrl()}/api/upload-resume`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
}

/**
 * Check backend health status
 */
export async function checkHealth(): Promise<{ status: string; services: Record<string, boolean> }> {
    const response = await fetch(`${getApiBaseUrl()}/health`);
    return response.json();
}

/**
 * Get conversation history
 */
export async function getConversation(sessionId?: string): Promise<any> {
    const url = sessionId
        ? `${getApiBaseUrl()}/api/conversation/full?session_id=${sessionId}`
        : `${getApiBaseUrl()}/api/conversation/full`;
    const response = await fetch(url);
    return response.json();
}

/**
 * WebSocket connection manager for voice interview
 */
export class VoiceWebSocket {
    private ws: WebSocket | null = null;
    private sessionId: string | null = null;

    // Callbacks
    public onStatus: ((status: string) => void) | null = null;
    public onTranscript: ((role: string, text: string) => void) | null = null;
    public onAudioChunk: ((data: string, sampleRate: number, isFinal: boolean) => void) | null = null;
    public onError: ((error: string) => void) | null = null;
    public onConnected: ((sessionId: string) => void) | null = null;
    public onDisconnected: (() => void) | null = null;

    /**
     * Connect to the voice WebSocket
     */
    connect(): Promise<void> {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(`${getWsBaseUrl()}/ws/voice`);

                this.ws.onopen = () => {
                    console.log('✅ WebSocket connected');
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.onError?.('Connection error');
                    reject(error);
                };

                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.onDisconnected?.();
                };
            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Handle incoming WebSocket messages
     */
    private handleMessage(data: any): void {
        switch (data.type) {
            case 'status':
                this.onStatus?.(data.status);
                if (data.session_id) {
                    this.sessionId = data.session_id;
                    this.onConnected?.(data.session_id);
                }
                break;

            case 'transcript':
                this.onTranscript?.(data.role, data.text);
                break;

            case 'audio_chunk':
                this.onAudioChunk?.(data.data, data.sample_rate || 22050, data.is_final || false);
                break;

            case 'error':
                this.onError?.(data.message);
                break;

            case 'session_started':
                this.sessionId = data.session_id;
                this.onConnected?.(data.session_id);
                break;
        }
    }

    /**
     * Send audio data to backend
     */
    sendAudio(base64Data: string): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'audio',
                data: base64Data
            }));
        }
    }

    /**
     * Request a new session
     */
    startNewSession(): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'new_session' }));
        }
    }

    /**
     * End the current session
     */
    endSession(): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'end_session' }));
        }
    }

    /**
     * Disconnect WebSocket
     */
    disconnect(): void {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    /**
     * Check if connected
     */
    get isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    /**
     * Get current session ID
     */
    getSessionId(): string | null {
        return this.sessionId;
    }
}

// Export singleton instance
export const voiceWebSocket = new VoiceWebSocket();
