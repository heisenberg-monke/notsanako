/**
 * Deterministic Audio Recording Engine.
 * 
 * 1. Checks context security (detects insecure http://IP:3000 vs https/localhost).
 * 2. Detects whether getUserMedia() is supported.
 * 3. Enumerates devices with 'default' as default selection without auto-locking.
 * 4. Passes deviceId into getUserMedia ONLY when explicitly chosen.
 * 5. Requests mono, ~16kHz audio constraints ({ channelCount: { ideal: 1 }, sampleRate: { ideal: 16000 } }).
 * 6. Inspects and logs actual track.getSettings() (sampleRate, channelCount, deviceId).
 * 7. Listens to track.onmute, track.onunmute, and track.onended for deterministic hardware state.
 * 8. Real time-domain RMS and dBFS signal power calculation.
 * 9. MediaRecorder audio blob is strictly the single source of truth.
 */

export interface AudioInputDevice {
  deviceId: string;
  label: string;
  groupId?: string;
}

export interface AudioTrackSettingsInfo {
  deviceId?: string;
  label: string;
  sampleRate?: number;
  channelCount?: number;
  echoCancellation?: boolean;
  noiseSuppression?: boolean;
  autoGainControl?: boolean;
  isMuted: boolean;
  readyState: MediaStreamTrackState;
}

export interface VolumeMeasurement {
  rms: number;          // Root Mean Square linear (0.0 to 1.0)
  dB: number;           // Decibels relative to Full Scale (-Infinity to 0 dBFS)
  normalized: number;   // 0 to 100 percentage scaled from noise floor (-50 dBFS) to peak (-4 dBFS)
  isSilent: boolean;    // True if signal power is below acoustic threshold (RMS < 0.002)
}

export interface ContextSecurityCheck {
  isSecure: boolean;
  errorMessage?: string;
}

/**
 * Validates context security and getUserMedia support.
 * Browsers block microphone access on insecure origins (e.g., http://192.168.x.x:3000).
 */
export function checkAudioContextSecurity(): ContextSecurityCheck {
  if (typeof window === 'undefined') {
    return { isSecure: true };
  }

  const hostname = window.location.hostname;
  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
  const isHttps = window.location.protocol === 'https:';

  if (!isLocalhost && !isHttps) {
    return {
      isSecure: false,
      errorMessage: `Insecure Context (${window.location.origin}): Web browsers permanently disable microphone access on non-HTTPS IP addresses. Please open the app via http://localhost:3000 or configure an HTTPS domain/tunnel.`
    };
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    return {
      isSecure: false,
      errorMessage: 'navigator.mediaDevices.getUserMedia() is not supported in this browser. Please use Chrome, Edge, Firefox, or Safari.'
    };
  }

  return { isSecure: true };
}

/**
 * Enumerates all connected audio input microphones.
 * Returns a list where 'default' represents system default without auto-locking.
 */
export async function getAudioInputDevices(): Promise<AudioInputDevice[]> {
  const security = checkAudioContextSecurity();
  if (!security.isSecure) {
    return [];
  }

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter((d) => d.kind === 'audioinput');

    const mapped: AudioInputDevice[] = audioInputs.map((d, index) => ({
      deviceId: d.deviceId,
      label: d.label || `Microphone ${index + 1} (${d.deviceId ? d.deviceId.slice(0, 8) + '...' : 'System Device'})`,
      groupId: d.groupId,
    }));

    // Prepend 'default' option if not explicitly present
    const hasDefault = mapped.some((d) => d.deviceId === 'default');
    if (!hasDefault) {
      mapped.unshift({
        deviceId: 'default',
        label: 'System Default Microphone (Auto)',
      } as AudioInputDevice);
    }

    return mapped;
  } catch (err) {
    console.error('Failed to enumerate audio devices:', err);
    return [{ deviceId: 'default', label: 'System Default Microphone (Auto)' } as AudioInputDevice];
  }
}

export class AudioRecordingService {
  private mediaStream: MediaStream | null = null;
  private audioTrack: MediaStreamTrack | null = null;
  private audioContext: AudioContext | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  private analyser: AnalyserNode | null = null;
  private animationFrameId?: number;
  private isCurrentlyRecording: boolean = false;

  // Event callbacks
  private onVolumeChange?: (measurement: VolumeMeasurement) => void;
  private onTrackMuteChange?: (isMuted: boolean) => void;
  private onTrackEnded?: () => void;

  /**
   * Initializes microphone stream.
   * Uses deviceId ONLY when explicitly chosen and different from 'default'.
   */
  async startRecording(
    options: {
      deviceId?: string;
      onVolumeChange?: (measurement: VolumeMeasurement) => void;
      onTrackMuteChange?: (isMuted: boolean) => void;
      onTrackEnded?: () => void;
    } = {}
  ): Promise<AudioTrackSettingsInfo> {
    const security = checkAudioContextSecurity();
    if (!security.isSecure) {
      throw new Error(security.errorMessage);
    }

    this.audioChunks = [];
    this.isCurrentlyRecording = true;
    this.onVolumeChange = options.onVolumeChange;
    this.onTrackMuteChange = options.onTrackMuteChange;
    this.onTrackEnded = options.onTrackEnded;

    // 1. Build audio constraints: request mono, ~16kHz where supported
    const audioConstraints: MediaTrackConstraints = {
      channelCount: { ideal: 1 },
      sampleRate: { ideal: 16000 },
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    };

    // Use deviceId ONLY when explicitly chosen (not 'default' and not empty)
    const explicitlyChosenId = options.deviceId && options.deviceId !== 'default' ? options.deviceId : null;
    if (explicitlyChosenId) {
      audioConstraints.deviceId = { exact: explicitlyChosenId };
    }

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: audioConstraints,
      });
    } catch (err: any) {
      // If exact deviceId or specific constraints failed, retry gracefully
      if (explicitlyChosenId) {
        console.warn(`Exact deviceId constraint failed (${err.name}), retrying with ideal deviceId...`);
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: { ideal: 1 },
            sampleRate: { ideal: 16000 },
            deviceId: { ideal: explicitlyChosenId },
          },
        });
      } else {
        console.warn(`Strict constraints failed (${err.name}), retrying with basic audio constraints...`);
        this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
    }

    // 2. Extract and inspect active audio track
    const tracks = this.mediaStream.getAudioTracks();
    if (tracks.length === 0) {
      throw new Error('No audio tracks returned from microphone stream.');
    }

    this.audioTrack = tracks[0];

    // 3. Register deterministic hardware event listeners
    this.audioTrack.onmute = () => {
      console.warn(`[Audio Engine Event] Hardware/OS MUTED track: ${this.audioTrack?.label} (${this.audioTrack?.id})`);
      this.onTrackMuteChange?.(true);
    };

    this.audioTrack.onunmute = () => {
      console.info(`[Audio Engine Event] Hardware/OS UNMUTED track: ${this.audioTrack?.label} (${this.audioTrack?.id})`);
      this.onTrackMuteChange?.(false);
    };

    this.audioTrack.onended = () => {
      console.warn(`[Audio Engine Event] Track ENDED / Disconnected: ${this.audioTrack?.label} (${this.audioTrack?.id})`);
      this.onTrackEnded?.();
    };

    // 4. Retrieve, inspect, and log the ACTUAL sample rate and channel count
    const settings = this.audioTrack.getSettings();
    const trackInfo: AudioTrackSettingsInfo = {
      deviceId: settings.deviceId,
      label: this.audioTrack.label || 'Default Microphone',
      sampleRate: settings.sampleRate,
      channelCount: settings.channelCount,
      echoCancellation: settings.echoCancellation,
      noiseSuppression: settings.noiseSuppression,
      autoGainControl: settings.autoGainControl,
      isMuted: this.audioTrack.muted,
      readyState: this.audioTrack.readyState,
    };

    console.info('[Audio Capture] Actual Hardware Settings:', {
      label: trackInfo.label,
      actualSampleRate: trackInfo.sampleRate ? `${trackInfo.sampleRate} Hz` : 'Browser default',
      actualChannels: trackInfo.channelCount || 1,
      isMuted: trackInfo.isMuted,
      readyState: trackInfo.readyState,
      echoCancellation: trackInfo.echoCancellation,
    });

    // 5. Setup Web Audio Analyser for True Time-Domain RMS Measurement
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioContextClass();

      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 1024;
      source.connect(this.analyser);

      if (this.onVolumeChange) {
        this.monitorTimeDomainRMS();
      }
    } catch (ctxErr) {
      console.warn('[Audio Engine] Web Audio Analyser setup warning:', ctxErr);
    }

    // 6. Setup MediaRecorder as the authoritative single source of truth
    let mimeType = '';
    const preferredMimes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
      ''
    ];

    for (const m of preferredMimes) {
      if (!m || MediaRecorder.isTypeSupported(m)) {
        mimeType = m;
        break;
      }
    }

    const mrOptions: MediaRecorderOptions = mimeType ? { mimeType } : {};
    this.mediaRecorder = new MediaRecorder(this.mediaStream, mrOptions);

    this.mediaRecorder.ondataavailable = (event: BlobEvent) => {
      if (event.data && event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    // Slice audio in 250ms chunks
    console.info(`[Audio Lifecycle] Recording started → mimeType="${this.mediaRecorder.mimeType || 'browser-default'}" | sliceInterval=250ms`);
    this.mediaRecorder.start(250);

    return trackInfo;
  }

  /**
   * Real Root Mean Square (RMS) & dBFS calculation using Float32 Time-Domain signal samples.
   * RMS = sqrt( (1/N) * sum(x_i^2) )
   * dBFS = 20 * log10(RMS)
   */
  private monitorTimeDomainRMS() {
    if (!this.analyser || !this.isCurrentlyRecording) return;

    const bufferLength = this.analyser.fftSize;
    const timeDomainData = new Float32Array(bufferLength);

    const update = () => {
      if (!this.analyser || !this.isCurrentlyRecording) return;

      this.analyser.getFloatTimeDomainData(timeDomainData);

      let sumOfSquares = 0;
      for (let i = 0; i < bufferLength; i++) {
        const val = timeDomainData[i];
        sumOfSquares += val * val;
      }
      const rms = Math.sqrt(sumOfSquares / bufferLength);

      // Decibels Full Scale (-Infinity to 0 dBFS)
      const dB = rms > 0.00001 ? 20 * Math.log10(rms) : -90;

      // Map range: -50 dBFS (ambient floor) to -4 dBFS (loud speech) -> 0 to 100%
      const minDb = -50;
      const maxDb = -4;
      let normalized = 0;
      if (dB > minDb) {
        normalized = Math.min(100, Math.max(0, Math.round(((dB - minDb) / (maxDb - minDb)) * 100)));
      }

      const measurement: VolumeMeasurement = {
        rms: Math.round(rms * 1000) / 1000,
        dB: Math.round(dB * 10) / 10,
        normalized,
        isSilent: rms < 0.002, // Below ~ -54 dBFS is considered silence/flatline
      };

      this.onVolumeChange?.(measurement);
      this.animationFrameId = requestAnimationFrame(update);
    };

    update();
  }

  /**
   * Stops recording and returns the raw audio Blob as the single source of truth.
   */
  async stopRecording(): Promise<{ audioBlob: Blob; mimeType: string }> {
    this.isCurrentlyRecording = false;

    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }

    return new Promise((resolve) => {
      const finalize = () => {
        const finalMime = this.mediaRecorder?.mimeType || 'audio/webm';
        const blob = new Blob(this.audioChunks, { type: finalMime });
        this.cleanup();
        resolve({ audioBlob: blob, mimeType: finalMime });
      };

      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        finalize();
        return;
      }

      this.mediaRecorder.onstop = finalize;
      this.mediaRecorder.stop();
    });
  }

  private cleanup() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => {
        track.stop();
      });
      this.mediaStream = null;
    }
    this.audioTrack = null;

    if (this.audioContext && this.audioContext.state !== 'closed') {
      try {
        this.audioContext.close();
      } catch (e) {
        // Ignore
      }
      this.audioContext = null;
    }

    this.mediaRecorder = null;
    this.analyser = null;
  }
}
