'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Mic, Square, Loader2, RotateCcw, Volume2, AlertCircle, HelpCircle } from 'lucide-react';
import { AudioRecordingService } from '@/utils/audio';

interface AudioControlsProps {
  language: 'en' | 'hi';
  onAnalysisStart: () => void;
  onAnalysisComplete: (audioBlob: Blob, clientTranscript: string, durationSeconds: number) => void;
  onReset: () => void;
  onRecordingStateChange?: (isRecording: boolean) => void;
  onLiveTranscriptChange?: (text: string) => void;
  isAnalyzing: boolean;
  disabled?: boolean;
}

export const AudioControls: React.FC<AudioControlsProps> = ({
  language,
  onAnalysisStart,
  onAnalysisComplete,
  onReset,
  onRecordingStateChange,
  onLiveTranscriptChange,
  isAnalyzing,
  disabled = false,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [micError, setMicError] = useState<string | null>(null);
  const [silenceWarning, setSilenceWarning] = useState(false);

  const recordingServiceRef = useRef<AudioRecordingService | null>(null);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    recordingServiceRef.current = new AudioRecordingService();
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, []);

  const startTimer = () => {
    setElapsedSeconds(0);
    setSilenceWarning(false);
    timerIntervalRef.current = setInterval(() => {
      setElapsedSeconds((prev) => {
        const next = prev + 1;
        // If 4 seconds passed and audio level is consistently 0, gently warn
        if (next >= 4 && audioLevel < 5) {
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
    setLiveTranscript('');
    setSilenceWarning(false);

    try {
      if (!recordingServiceRef.current) {
        recordingServiceRef.current = new AudioRecordingService();
      }

      await recordingServiceRef.current.startRecording(
        language,
        (transcript) => {
          setLiveTranscript(transcript);
          if (onLiveTranscriptChange) onLiveTranscriptChange(transcript);
        },
        (level) => {
          setAudioLevel(level);
          if (level > 10) setSilenceWarning(false);
        }
      );

      setIsRecording(true);
      if (onRecordingStateChange) onRecordingStateChange(true);
      startTimer();
    } catch (err: any) {
      console.error('Failed to access microphone:', err);
      let message = 'Could not access your microphone.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        message = 'Microphone permission denied. Click the lock/camera icon next to the URL bar in your browser to Allow microphone access, then try again.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        message = 'No microphone device detected. Please connect a headset or microphone.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        message = 'Microphone is currently in use by another application. Please close other recording apps and try again.';
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
      const { audioBlob, clientTranscript } = await recordingServiceRef.current.stopRecording();
      onAnalysisComplete(audioBlob, clientTranscript || liveTranscript, duration);
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
    setLiveTranscript('');
    setMicError(null);
    setSilenceWarning(false);
    onReset();
  };

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm">
      {micError && (
        <div className="mb-4 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-start gap-2.5 animate-in fade-in">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-bold">Microphone Access Error</div>
            <div className="mt-0.5">{micError}</div>
          </div>
        </div>
      )}

      {silenceWarning && isRecording && (
        <div className="mb-4 p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium flex items-center gap-2 animate-in fade-in">
          <HelpCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>
            No voice input detected. If using Linux, check system volume settings (e.g. <code>pavucontrol</code>) or ensure mic is unmuted.
          </span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row items-center justify-between gap-5">
        {/* Status and Audio Level Meter */}
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
                  ? 'Recording in Progress...'
                  : isAnalyzing
                  ? 'Analyzing Reading Audio...'
                  : 'Ready to Read Aloud'}
              </h3>
              {isRecording && (
                <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 font-bold">
                  {formatTime(elapsedSeconds)}
                </span>
              )}
            </div>

            {/* Audio Wave level bar */}
            {isRecording ? (
              <div className="flex items-center gap-2 mt-1.5">
                <div className="w-36 h-2.5 rounded-full bg-slate-100 overflow-hidden p-0.5 border border-slate-200">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-yellow-500 to-rose-500 transition-all duration-75"
                    style={{ width: `${Math.max(8, audioLevel)}%` }}
                  />
                </div>
                <span className="text-[11px] text-slate-500 font-bold">
                  {audioLevel > 15 ? '🟢 Speaking' : 'Listening...'}
                </span>
              </div>
            ) : (
              <p className="text-xs text-slate-500 mt-0.5">
                Press start, read clearly into your mic, then tap finish.
              </p>
            )}
          </div>
        </div>

        {/* Action Buttons */}
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
