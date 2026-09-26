/**
 * Deterministic Audio Recording Engine.
 * 
 * Architectural Highlights:
 * 1. Explicit device enumeration via navigator.mediaDevices.enumerateDevices().
 * 2. Hardware deviceId passing into getUserMedia().
 * 3. Inspects and exposes track.getSettings() (actual sampleRate, channelCount, deviceId).
 * 4. Listens to track.onmute, track.onunmute, and track.onended for deterministic hardware state.
 * 5. Time-domain Root Mean Square (RMS) & dBFS measurement (no heuristic frequency bin averaging).
 * 6. MediaRecorder audio blob is strictly the single source of truth.
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
  normalized: number;   // 0 to 100 percentage scaled from noise floor (-50 dBFS) to peak (-3 dBFS)
  isSilent: boolean;    // True if signal power is below acoustic threshold
}

/**
 * Enumerates all connected audio input microphones.
 */
export async function getAudioInputDevices(): Promise<AudioInputDevice[]> {
  if (typeof window === 'undefined' || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
    return [];
  }

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const audioInputs = devices.filter((d) => d.kind === 'audioinput');

    return audioInputs.map((d, index) => ({
      deviceId: d.deviceId,
      label: d.label || `Microphone ${index + 1} (${d.deviceId ? d.deviceId.slice(0, 8) + '...' : 'Default'})`,
      groupId: d.groupId,
    }));
  } catch (err) {
    console.error('Failed to enumerate audio devices:', err);
    return [];
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
   * Initializes microphone stream with specified deviceId.
   */
  async startRecording(
    options: {
      deviceId?: string;
      onVolumeChange?: (measurement: VolumeMeasurement) => void;
      onTrackMuteChange?: (isMuted: boolean) => void;
      onTrackEnded?: () => void;
    } = {}
  ): Promise<AudioTrackSettingsInfo> {
    this.audioChunks = [];
    this.isCurrentlyRecording = true;
    this.onVolumeChange = options.onVolumeChange;
    this.onTrackMuteChange = options.onTrackMuteChange;
    this.onTrackEnded = options.onTrackEnded;

    // 1. Build deterministic audio constraints
    const audioConstraints: MediaTrackConstraints = {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    };

    if (options.deviceId && options.deviceId !== 'default') {
      audioConstraints.deviceId = { exact: options.deviceId };
    }

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: audioConstraints,
      });
    } catch (err: any) {
      // If exact deviceId or advanced constraint fails, retry with soft constraint
      if (options.deviceId && options.deviceId !== 'default') {
        console.warn(`Exact deviceId constraint failed (${err.name}), retrying with ideal deviceId...`);
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: { deviceId: { ideal: options.deviceId } },
        });
      } else {
        throw err;
      }
    }

    // 2. Extract and inspect the active audio track
    const tracks = this.mediaStream.getAudioTracks();
    if (tracks.length === 0) {
      throw new Error('No audio tracks returned from microphone stream.');
    }

    this.audioTrack = tracks[0];

    // 3. Register deterministic hardware event listeners
    this.audioTrack.onmute = () => {
      console.warn(`[Audio Engine] Hardware/OS MUTED track: ${this.audioTrack?.label} (${this.audioTrack?.id})`);
      this.onTrackMuteChange?.(true);
    };

    this.audioTrack.onunmute = () => {
      console.info(`[Audio Engine] Hardware/OS UNMUTED track: ${this.audioTrack?.label} (${this.audioTrack?.id})`);
      this.onTrackMuteChange?.(false);
    };

    this.audioTrack.onended = () => {
      console.warn(`[Audio Engine] Track ENDED / Disconnected: ${this.audioTrack?.label} (${this.audioTrack?.id})`);
      this.onTrackEnded?.();
    };

    // 4. Retrieve and log track settings
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

    console.info('[Audio Engine] Active Track Settings:', trackInfo);

    // 5. Setup Web Audio Analyser for True RMS Measurement
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioContextClass();

      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 1024; // High time-domain resolution for RMS
      source.connect(this.analyser);

      if (this.onVolumeChange) {
        this.monitorTimeDomainRMS();
      }
    } catch (ctxErr) {
      console.warn('[Audio Engine] Web Audio Analyser initialization warning:', ctxErr);
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

    // Capture in 250ms chunks
    this.mediaRecorder.start(250);

    return trackInfo;
  }

  /**
   * Real Root Mean Square (RMS) & dBFS calculation using Float32 Time-Domain signal samples.
   */
  private monitorTimeDomainRMS() {
    if (!this.analyser || !this.isCurrentlyRecording) return;

    const bufferLength = this.analyser.fftSize;
    const timeDomainData = new Float32Array(bufferLength);

    const update = () => {
      if (!this.analyser || !this.isCurrentlyRecording) return;

      // Extract time-domain waveform in range [-1.0, 1.0]
      this.analyser.getFloatTimeDomainData(timeDomainData);

      // Compute RMS = sqrt( (1/N) * sum(x_i^2) )
      let sumOfSquares = 0;
      for (let i = 0; i < bufferLength; i++) {
        const val = timeDomainData[i];
        sumOfSquares += val * val;
      }
      const rms = Math.sqrt(sumOfSquares / bufferLength);

      // Compute dBFS (decibels relative to full scale)
      // Clamped to floor of -90 dBFS
      const dB = rms > 0.00001 ? 20 * Math.log10(rms) : -90;

      // Map range: -50 dBFS (quiet room noise) to -4 dBFS (loud speech) -> 0 to 100%
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
        isSilent: rms < 0.002, // Below ~ -54 dBFS
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
