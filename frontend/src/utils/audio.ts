/**
 * Resilient Audio Recording and Speech Processing Utilities.
 * Handles Linux / ALSA / PulseAudio / PipeWire hardware quirks gracefully:
 * - Uses soft 'ideal' constraints with fallback to { audio: true }
 * - Safely initializes AudioContext with explicit resume() on user gesture
 * - Boosts volume meter sensitivity so voice input is clearly visible
 * - Universal MediaRecorder MIME type detection
 */

export class AudioRecordingService {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  private analyser: AnalyserNode | null = null;
  private speechRecognition: any = null;
  private liveTranscript: string = '';
  private onTranscriptUpdate?: (text: string) => void;
  private onVolumeChange?: (level: number) => void;
  private animationFrameId?: number;
  private isCurrentlyRecording: boolean = false;

  /**
   * Initializes microphone stream with robust fallbacks.
   */
  async startRecording(
    language: 'en' | 'hi' = 'en',
    onTranscriptUpdate?: (text: string) => void,
    onVolumeChange?: (level: number) => void
  ): Promise<void> {
    this.audioChunks = [];
    this.liveTranscript = '';
    this.onTranscriptUpdate = onTranscriptUpdate;
    this.onVolumeChange = onVolumeChange;
    this.isCurrentlyRecording = true;

    // 1. Request microphone with fallback for Linux / browser device constraints
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: { ideal: 1 },
          sampleRate: { ideal: 16000 },
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (constraintErr) {
      console.warn('Constrained getUserMedia failed, falling back to basic audio:', constraintErr);
      // Fallback: request unconstrained audio (compatible with 100% of working input devices)
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }

    // Verify audio track is active and not muted
    const audioTracks = this.mediaStream.getAudioTracks();
    if (audioTracks.length === 0 || !audioTracks[0].enabled) {
      throw new Error('No active microphone audio track found.');
    }

    // 2. Setup Web Audio Analyser with explicit resume() for level visualization
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioContextClass();
      
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.5;
      source.connect(this.analyser);

      if (this.onVolumeChange) {
        this.monitorAudioLevel();
      }
    } catch (audioCtxErr) {
      console.warn('Web Audio level monitoring failed, recording will still continue:', audioCtxErr);
    }

    // 3. MediaRecorder setup with multi-codec detection
    let mimeType = '';
    const preferredTypes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
      ''
    ];

    for (const type of preferredTypes) {
      if (!type || MediaRecorder.isTypeSupported(type)) {
        mimeType = type;
        break;
      }
    }

    const options: MediaRecorderOptions = mimeType ? { mimeType } : {};
    this.mediaRecorder = new MediaRecorder(this.mediaStream, options);

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    // Request data every 250ms
    this.mediaRecorder.start(250);

    // 4. Start live speech recognition preview if supported
    this.startLiveSpeechRecognition(language);
  }

  private startLiveSpeechRecognition(language: 'en' | 'hi') {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    try {
      this.speechRecognition = new SpeechRecognition();
      this.speechRecognition.continuous = true;
      this.speechRecognition.interimResults = true;
      this.speechRecognition.lang = language === 'hi' ? 'hi-IN' : 'en-IN';

      this.speechRecognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript + ' ';
        }
        this.liveTranscript = transcript.trim();
        if (this.onTranscriptUpdate) {
          this.onTranscriptUpdate(this.liveTranscript);
        }
      };

      this.speechRecognition.onerror = (err: any) => {
        // Soft error handling - Linux Chromium often warns on network STT
        console.info('SpeechRecognition note:', err.error);
      };

      this.speechRecognition.start();
    } catch (e) {
      console.warn('SpeechRecognition failed to start:', e);
    }
  }

  private monitorAudioLevel() {
    if (!this.analyser || !this.onVolumeChange) return;

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    const update = () => {
      if (!this.analyser || !this.isCurrentlyRecording) return;
      this.analyser.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;

      // Sensitive scaling so speaking is clearly reflected (0 to 100)
      const scaled = Math.min(100, Math.round(average * 2.2));
      this.onVolumeChange!(scaled);

      this.animationFrameId = requestAnimationFrame(update);
    };
    update();
  }

  /**
   * Stops recording and returns the captured audio Blob + live transcript.
   */
  async stopRecording(): Promise<{ audioBlob: Blob; clientTranscript: string }> {
    this.isCurrentlyRecording = false;

    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }

    if (this.speechRecognition) {
      try {
        this.speechRecognition.stop();
      } catch (e) {
        // Ignore stop error
      }
    }

    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        const fallbackBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        this.cleanup();
        resolve({ audioBlob: fallbackBlob, clientTranscript: this.liveTranscript });
        return;
      }

      this.mediaRecorder.onstop = () => {
        const mimeType = this.mediaRecorder?.mimeType || 'audio/webm';
        const finalBlob = new Blob(this.audioChunks, { type: mimeType });
        this.cleanup();
        resolve({ audioBlob: finalBlob, clientTranscript: this.liveTranscript });
      };

      this.mediaRecorder.stop();
    });
  }

  private cleanup() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext && this.audioContext.state !== 'closed') {
      try {
        this.audioContext.close();
      } catch (e) {
        // Ignore close error
      }
      this.audioContext = null;
    }
    this.mediaRecorder = null;
    this.analyser = null;
  }
}
