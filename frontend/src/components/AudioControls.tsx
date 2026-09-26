'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  Square,
  Loader2,
  RotateCcw,
  Volume2,
  AlertCircle,
  HelpCircle,
  Sliders,
  RefreshCw,
  ShieldAlert,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info
} from 'lucide-react';
import {
  AudioRecordingService,
  AudioInputDevice,
  AudioTrackSettingsInfo,
  VolumeMeasurement,
  getAudioInputDevices,
  checkAudioContextSecurity
} from '@/utils/audio';

interface AudioControlsProps {
  language: 'en' | 'hi';
  onAnalysisStart: () => void;
  onAnalysisComplete: (audioBlob: Blob, clientTranscript: string, durationSeconds: number) => void;
  onReset: () => void;
  onRecordingStateChange?: (isRecording: boolean) => void;
  isAnalyzing: boolean;
  disabled?: boolean;
}

export const AudioControls: React.FC<AudioControlsProps> = ({
  language,
  onAnalysisStart,
  onAnalysisComplete,
  onReset,
  onRecordingStateChange,
  isAnalyzing,
  disabled = false,
}) => {
  // Device Selection & Hardware Track Metadata
  const [devices, setDevices] = useState<AudioInputDevice[]>([]);
  // Start with 'default' so we DO NOT automatically lock onto the first enumerated device
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('default');
  const [activeTrackSettings, setActiveTrackSettings] = useState<AudioTrackSettingsInfo | null>(null);

  // Hardware State Tracking
  const [isHardwareMuted, setIsHardwareMuted] = useState(false);
  const [hasTrackEnded, setHasTrackEnded] = useState(false);

  // Recording State & Volume Metrics
  const [isRecording, setIsRecording] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [volumeMeasurement, setVolumeMeasurement] = useState<VolumeMeasurement>({
    rms: 0,
    dB: -90,
    normalized: 0,
    isSilent: true,
  });

  const [micError, setMicError] = useState<string | null>(null);
  const [showDebugGuide, setShowDebugGuide] = useState(false);

  const recordingServiceRef = useRef<AudioRecordingService | null>(null);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Initial Security & Device Check on Mount
  const refreshDevices = async () => {
    const security = checkAudioContextSecurity();
    if (!security.isSecure) {
      setMicError(security.errorMessage || 'Insecure origin detected.');
      return;
    }

    try {
      const list = await getAudioInputDevices();
      setDevices(list);
    } catch (e) {
      console.warn('Could not enumerate audio devices:', e);
    }
  };

  useEffect(() => {
    recordingServiceRef.current = new AudioRecordingService();
    refreshDevices();

    if (typeof navigator !== 'undefined' && navigator.mediaDevices) {
      navigator.mediaDevices.addEventListener('devicechange', refreshDevices);
      return () => {
        navigator.mediaDevices.removeEventListener('devicechange', refreshDevices);
        if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      };
    }
  }, []);

  const startTimer = () => {
    setElapsedSeconds(0);
    timerIntervalRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
  };

  const stopTimer = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
  };

  const handleStartRecording = async () => {
    setMicError(null);
    setIsHardwareMuted(false);
    setHasTrackEnded(false);

    // Context check
    const security = checkAudioContextSecurity();
    if (!security.isSecure) {
      setMicError(security.errorMessage || 'Insecure origin detected.');
      return;
    }

    try {
      if (!recordingServiceRef.current) {
        recordingServiceRef.current = new AudioRecordingService();
      }

      // Start recording: passes deviceId ONLY when explicitly chosen
      const trackSettings = await recordingServiceRef.current.startRecording({
        deviceId: selectedDeviceId !== 'default' ? selectedDeviceId : undefined,
        onVolumeChange: (measurement) => {
          setVolumeMeasurement(measurement);
        },
        onTrackMuteChange: (muted) => {
          setIsHardwareMuted(muted);
        },
        onTrackEnded: () => {
          setHasTrackEnded(true);
          setMicError('Microphone track was disconnected or ended by the system.');
          handleStopRecording();
        },
      });

      setActiveTrackSettings(trackSettings);
      setIsHardwareMuted(trackSettings.isMuted);

      setIsRecording(true);
      if (onRecordingStateChange) onRecordingStateChange(true);
      startTimer();

      // Refresh labels now that permission has been approved
      refreshDevices();
    } catch (err: any) {
      console.error('Failed to access microphone:', err);
      let message = 'Could not access your microphone.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        message = 'Microphone permission denied. Click the lock/tune icon in your browser URL bar to Allow microphone access, then try again.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        message = 'No microphone device detected. Please connect an input device or headset.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        message = 'Microphone is currently in use or locked by another application/tab. Please close other recording apps.';
      } else if (err.message) {
        message = err.message;
      }
      setMicError(message);
    }
  };

  const handleStopRecording = async () => {
    if (!recordingServiceRef.current || !isRecording) return;

    stopTimer();
    setIsRecording(false);
    if (onRecordingStateChange) onRecordingStateChange(false);
    onAnalysisStart();

    const duration = Math.max(elapsedSeconds, 1);
    try {
      // MediaRecorder is strictly the single source of truth for audio
      const { audioBlob } = await recordingServiceRef.current.stopRecording();
      onAnalysisComplete(audioBlob, '', duration);
    } catch (err: any) {
      console.error('Failed to finalize audio capture:', err);
      onReset();
    }
  };

  const handleReset = () => {
    stopTimer();
    setIsRecording(false);
    if (onRecordingStateChange) onRecordingStateChange(false);
    setElapsedSeconds(0);
    setMicError(null);
    setIsHardwareMuted(false);
    setHasTrackEnded(false);
    setActiveTrackSettings(null);
    setVolumeMeasurement({ rms: 0, dB: -90, normalized: 0, isSilent: true });
    onReset();
  };

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm space-y-4">
      {/* Hardware / OS Mute Warning Banner */}
      {isHardwareMuted && (
        <div className="p-3.5 rounded-2xl bg-amber-500 text-white text-xs font-bold flex items-center gap-2 animate-bounce shadow-md">
          <ShieldAlert className="w-5 h-5 flex-shrink-0" />
          <span>
            ⚠️ HARDWARE/OS MUTE DETECTED: Operating system reports this microphone track is MUTED. Please check your physical mic switch or Linux volume slider (e.g. <code>pavucontrol</code>).
          </span>
        </div>
      )}

      {/* Disconnect Alert */}
      {hasTrackEnded && (
        <div className="p-3.5 rounded-2xl bg-rose-600 text-white text-xs font-bold flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>Microphone was unplugged or stopped by the system.</span>
        </div>
      )}

      {/* Mic Error Banner */}
      {micError && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-start gap-2.5 animate-in fade-in">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-bold text-sm">Microphone Access Error</div>
            <div className="mt-1 leading-normal">{micError}</div>
          </div>
        </div>
      )}

      {/* Explicit "No Audio Detected" Banner if recording and silent */}
      {isRecording && volumeMeasurement.isSilent && elapsedSeconds >= 3 && !isHardwareMuted && (
        <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-300 text-amber-900 text-xs font-semibold flex items-center gap-2 animate-in fade-in">
          <HelpCircle className="w-4 h-4 text-amber-700 flex-shrink-0" />
          <span>
            ⚠️ No audio detected (RMS: 0.000 • -∞ dBFS). The stream is connected, but zero signal is arriving. Check if your microphone volume slider is raised or select a different device below.
          </span>
        </div>
      )}

      {/* Microphone Selection & Hardware Inspector */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs">
        <div className="flex items-center gap-2 flex-1 min-w-[250px]">
          <Sliders className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <span className="font-bold text-slate-700 whitespace-nowrap">Input Device:</span>
          <select
            value={selectedDeviceId}
            onChange={(e) => setSelectedDeviceId(e.target.value)}
            disabled={isRecording || isAnalyzing}
            className="flex-1 px-3 py-1.5 rounded-xl border border-slate-300 bg-white text-slate-800 font-medium text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
          >
            {devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label}
              </option>
            ))}
            {devices.length === 0 && (
              <option value="default">System Default Microphone (Auto)</option>
            )}
          </select>

          <button
            onClick={refreshDevices}
            disabled={isRecording || isAnalyzing}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-200 text-slate-600 transition-colors"
            title="Refresh microphone list"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Real Hardware Track Settings Badge */}
        {activeTrackSettings && (
          <div className="flex items-center gap-2 text-[11px] font-mono px-3 py-1 rounded-xl bg-slate-200/80 text-slate-800">
            <span>SR: <strong>{activeTrackSettings.sampleRate ? `${activeTrackSettings.sampleRate} Hz` : '~16kHz ideal'}</strong></span>
            <span>•</span>
            <span>CH: <strong>{activeTrackSettings.channelCount || 1}</strong></span>
            <span>•</span>
            <span className={activeTrackSettings.isMuted ? 'text-rose-600 font-bold' : 'text-emerald-700 font-bold'}>
              {activeTrackSettings.isMuted ? 'MUTED' : 'ACTIVE'}
            </span>
          </div>
        )}
      </div>

      {/* Main Recording Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-5 pt-1">
        {/* Status Icon & Live Physical RMS Meter */}
        <div className="flex items-center gap-4 w-full sm:w-auto">
          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-all ${
              isRecording
                ? volumeMeasurement.isSilent
                  ? 'bg-amber-500 text-white animate-pulse'
                  : 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/30'
                : isAnalyzing
                ? 'bg-amber-500 text-white animate-spin'
                : 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
            }`}
          >
            {isAnalyzing ? (
              <Loader2 className="w-7 h-7" />
            ) : isRecording ? (
              <Volume2 className="w-7 h-7" />
            ) : (
              <Mic className="w-7 h-7" />
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-slate-800 text-base">
                {isRecording
                  ? volumeMeasurement.isSilent
                    ? 'No Audio Detected'
                    : 'Recording Audio (Source of Truth)...'
                  : isAnalyzing
                  ? 'Analyzing Audio on Backend...'
                  : 'Ready to Read Aloud'}
              </h3>
              {isRecording && (
                <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 font-bold">
                  {formatTime(elapsedSeconds)}
                </span>
              )}
            </div>

            {/* True RMS Signal Power Meter */}
            {isRecording ? (
              <div className="space-y-1 mt-1.5">
                <div className="flex items-center gap-2">
                  <div className="w-44 h-2.5 rounded-full bg-slate-100 overflow-hidden p-0.5 border border-slate-200">
                    <div
                      className={`h-full rounded-full transition-all duration-75 ${
                        volumeMeasurement.isSilent
                          ? 'bg-slate-300'
                          : 'bg-gradient-to-r from-emerald-500 via-yellow-500 to-rose-500'
                      }`}
                      style={{ width: `${Math.max(4, volumeMeasurement.normalized)}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 whitespace-nowrap">
                    {volumeMeasurement.dB > -80 ? `${volumeMeasurement.dB} dBFS` : '-∞ dBFS'}
                  </span>
                </div>
                <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1.5">
                  <span>RMS: <strong>{volumeMeasurement.rms}</strong></span>
                  <span>•</span>
                  {volumeMeasurement.isSilent ? (
                    <span className="text-amber-600 font-bold">⚠️ No Audio (Check Mic)</span>
                  ) : (
                    <span className="text-emerald-600 font-bold">🟢 Audio Signal Active</span>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 mt-0.5">
                Microphone audio will be uploaded and transcribed by backend STT upon pressing Stop.
              </p>
            )}
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          <button
            onClick={handleReset}
            disabled={isAnalyzing || isRecording || disabled}
            className="p-3 rounded-2xl border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 disabled:opacity-40 transition-colors"
            title="Reset attempt"
          >
            <RotateCcw className="w-5 h-5" />
          </button>

          {!isRecording ? (
            <button
              onClick={handleStartRecording}
              disabled={isAnalyzing || disabled}
              className="flex-1 sm:flex-none px-6 py-3.5 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-bold text-sm shadow-md shadow-blue-500/20 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
            >
              <Mic className="w-4 h-4" />
              <span>{language === 'hi' ? 'पढ़ना शुरू करें' : 'Start Reading Aloud'}</span>
            </button>
          ) : (
            <button
              onClick={handleStopRecording}
              className="flex-1 sm:flex-none px-6 py-3.5 rounded-2xl bg-rose-600 hover:bg-rose-700 active:scale-95 text-white font-bold text-sm shadow-md shadow-rose-500/30 transition-all flex items-center justify-center gap-2"
            >
              <Square className="w-4 h-4 fill-white" />
              <span>{language === 'hi' ? 'वाचन समाप्त करें (Stop)' : 'Finish Reading (Stop)'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Recommended Debugging Guide Accordion */}
      <div className="pt-2 border-t border-slate-100">
        <button
          onClick={() => setShowDebugGuide(!showDebugGuide)}
          className="text-[11px] font-semibold text-slate-500 hover:text-blue-600 flex items-center gap-1.5 transition-colors"
        >
          <Info className="w-3.5 h-3.5" />
          <span>Recommended Debugging Order & Audio Setup Guide</span>
          {showDebugGuide ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {showDebugGuide && (
          <div className="mt-2 p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-2 animate-in fade-in">
            <div className="font-bold text-slate-800">5-Step Audio Troubleshooting Order:</div>
            <ol className="list-decimal list-inside space-y-1 text-[11px] text-slate-600">
              <li>
                <strong>Verify Context:</strong> Ensure you are on <code>http://localhost:3000</code> or an HTTPS origin. Insecure IP origins block microphone access.
              </li>
              <li>
                <strong>Browser Permissions:</strong> Click the lock/tune icon next to your URL bar and confirm Microphone is set to <strong>Allow</strong>.
              </li>
              <li>
                <strong>Watch the RMS Meter:</strong> Speak into the mic. The meter must report <code>🟢 Audio Signal Active</code> with RMS &gt; 0.005. If it stays at 0.000, check Linux volume settings (e.g. <code>pavucontrol</code>).
              </li>
              <li>
                <strong>Inspect Track Settings:</strong> Verify the badge above displays <code>ACTIVE</code> (not <code>MUTED</code>) and shows your desired sample rate/channel count.
              </li>
              <li>
                <strong>Verify Backend STT API Key:</strong> Once audio is verified, ensure <code>GROQ_API_KEY</code> or <code>OPENAI_API_KEY</code> is set in <code>backend/.env</code> for Whisper speech-to-text.
              </li>
            </ol>
          </div>
        )}
      </div>
    </div>
  );
};
