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
  Settings2,
  RefreshCw,
  Sliders,
  ShieldAlert
} from 'lucide-react';
import {
  AudioRecordingService,
  AudioInputDevice,
  AudioTrackSettingsInfo,
  VolumeMeasurement,
  getAudioInputDevices,
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
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('default');
  const [activeTrackSettings, setActiveTrackSettings] = useState<AudioTrackSettingsInfo | null>(null);
  const [isHardwareMuted, setIsHardwareMuted] = useState(false);

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
  const [silenceWarning, setSilenceWarning] = useState(false);

  const recordingServiceRef = useRef<AudioRecordingService | null>(null);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Enumerate microphones on mount and listen to device changes
  const refreshDevices = async () => {
    try {
      const list = await getAudioInputDevices();
      setDevices(list);
      if (list.length > 0 && selectedDeviceId === 'default') {
        setSelectedDeviceId(list[0].deviceId);
      }
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
    setSilenceWarning(false);
    timerIntervalRef.current = setInterval(() => {
      setElapsedSeconds((prev) => {
        const next = prev + 1;
        // If 4 seconds have passed with 0 RMS audio, warn about hardware mute
        if (next >= 4 && volumeMeasurement.isSilent) {
          setSilenceWarning(true);
        }
        return next;
      });
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
    setSilenceWarning(false);
    setIsHardwareMuted(false);

    try {
      if (!recordingServiceRef.current) {
        recordingServiceRef.current = new AudioRecordingService();
      }

      // Start recording with explicit deviceId & real RMS listener
      const trackSettings = await recordingServiceRef.current.startRecording({
        deviceId: selectedDeviceId !== 'default' ? selectedDeviceId : undefined,
        onVolumeChange: (measurement) => {
          setVolumeMeasurement(measurement);
          if (!measurement.isSilent) {
            setSilenceWarning(false);
          }
        },
        onTrackMuteChange: (muted) => {
          setIsHardwareMuted(muted);
        },
        onTrackEnded: () => {
          setMicError('Microphone was unplugged or disconnected.');
          handleStopRecording();
        },
      });

      setActiveTrackSettings(trackSettings);
      setIsHardwareMuted(trackSettings.isMuted);

      setIsRecording(true);
      if (onRecordingStateChange) onRecordingStateChange(true);
      startTimer();

      // Refresh devices now that permission is granted (to get actual device labels)
      refreshDevices();
    } catch (err: any) {
      console.error('Failed to access microphone:', err);
      let message = 'Could not access your microphone.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        message = 'Microphone permission denied. Click the lock icon in your browser URL bar to Allow microphone access.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        message = 'No microphone device detected. Please connect an input device.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        message = 'Microphone is busy or locked by another application (PulseAudio/ALSA/another browser tab).';
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
    setSilenceWarning(false);
    setIsHardwareMuted(false);
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
      {/* Hardware Mute Alert */}
      {isHardwareMuted && (
        <div className="p-3.5 rounded-2xl bg-amber-500 text-white text-xs font-bold flex items-center gap-2 animate-bounce">
          <ShieldAlert className="w-5 h-5 flex-shrink-0" />
          <span>
            ⚠️ HARDWARE/OS MUTE DETECTED: The operating system reports this microphone track is MUTED. Please unmute your mic switch or system slider.
          </span>
        </div>
      )}

      {/* Error Alert */}
      {micError && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-start gap-2.5 animate-in fade-in">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-bold">Microphone Hardware Error</div>
            <div className="mt-0.5">{micError}</div>
          </div>
        </div>
      )}

      {/* Silence Warning */}
      {silenceWarning && isRecording && (
        <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium flex items-center gap-2 animate-in fade-in">
          <HelpCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>
            Zero signal power detected (RMS &lt; 0.002). Verify your input volume in Linux sound settings (<code>pavucontrol</code>) or select a different microphone below.
          </span>
        </div>
      )}

      {/* Deterministic Microphone Selection & Hardware Inspector */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs">
        <div className="flex items-center gap-2 flex-1 min-w-[240px]">
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
              <option value="default">Default System Microphone</option>
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
          <div className="flex items-center gap-2 text-[11px] font-mono px-3 py-1 rounded-xl bg-slate-200/70 text-slate-800">
            <span>SR: <strong>{activeTrackSettings.sampleRate || 'auto'} Hz</strong></span>
            <span>•</span>
            <span>CH: <strong>{activeTrackSettings.channelCount || 1}</strong></span>
            <span>•</span>
            <span className={activeTrackSettings.isMuted ? 'text-rose-600 font-bold' : 'text-emerald-700 font-bold'}>
              {activeTrackSettings.isMuted ? 'MUTED' : 'ACTIVE'}
            </span>
          </div>
        )}
      </div>

      {/* Main Record Control Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-5 pt-1">
        {/* Status and True RMS Level Meter */}
        <div className="flex items-center gap-4 w-full sm:w-auto">
          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-all ${
              isRecording
                ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/30 animate-pulse'
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
                  ? 'Recording Audio (Source of Truth)...'
                  : isAnalyzing
                  ? 'Analyzing Audio on Server...'
                  : 'Ready to Read Aloud'}
              </h3>
              {isRecording && (
                <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 font-bold">
                  {formatTime(elapsedSeconds)}
                </span>
              )}
            </div>

            {/* True RMS & dBFS Progress Bar */}
            {isRecording ? (
              <div className="space-y-1 mt-1.5">
                <div className="flex items-center gap-2">
                  <div className="w-44 h-2.5 rounded-full bg-slate-100 overflow-hidden p-0.5 border border-slate-200">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-yellow-500 to-rose-500 transition-all duration-75"
                      style={{ width: `${Math.max(4, volumeMeasurement.normalized)}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 whitespace-nowrap">
                    {volumeMeasurement.dB > -80 ? `${volumeMeasurement.dB} dBFS` : '-∞ dBFS'}
                  </span>
                </div>
                <div className="text-[10px] font-mono text-slate-400">
                  RMS: <strong>{volumeMeasurement.rms}</strong> • {volumeMeasurement.isSilent ? 'Silent' : 'Signal Present'}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 mt-0.5">
                Microphone audio will be processed by the speech engine upon pressing Stop.
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
    </div>
  );
};
