'use client';

import React, { useState } from 'react';
import { RemediationPassage } from '@/types';
import { AudioControls } from '@/components/AudioControls';
import { Sparkles, BookOpen, Volume2, Target, CheckCircle2 } from 'lucide-react';

interface RemediationReadingCardProps {
  passage: RemediationPassage;
  targetWords: string[];
  language: 'en' | 'hi';
  onAnalysisStart: () => void;
  onAnalysisComplete: (audioBlob: Blob, clientTranscript: string, durationSeconds: number) => void;
  onReset: () => void;
  isAnalyzing: boolean;
}

export const RemediationReadingCard: React.FC<RemediationReadingCardProps> = ({
  passage,
  targetWords,
  language,
  onAnalysisStart,
  onAnalysisComplete,
  onReset,
  isAnalyzing,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');

  const speakWord = (word: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.lang = language === 'hi' ? 'hi-IN' : 'en-IN';
    utterance.rate = 0.85;
    window.speechSynthesis.speak(utterance);
  };

  const cleanTargets = targetWords.map((w) => w.toLowerCase().replace(/[^\w\u0900-\u097F]/g, ''));
  const words = passage.text.split(/\s+/);

  return (
    <div className="space-y-6">
      {/* Story Card */}
      <div className="bg-white rounded-3xl border-2 border-indigo-200 p-6 sm:p-8 shadow-md">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-md border border-indigo-200 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                Step 3: Personalized Remediation Story
              </span>
              <span className="text-xs font-semibold text-slate-500">
                {passage.word_count} words • Grade {passage.grade_level}
              </span>
            </div>
            <h2 className="text-2xl font-black text-slate-900 mt-2">
              {passage.title}
            </h2>
          </div>

          <div className="flex items-center gap-2 text-xs font-semibold text-indigo-700 bg-indigo-50 px-3 py-1.5 rounded-xl border border-indigo-100">
            <Target className="w-4 h-4 text-indigo-600" />
            <span>Target Words Embedded: {targetWords.length}</span>
          </div>
        </div>

        {/* Embedded Target Words Strip */}
        <div className="mb-6 p-3.5 rounded-2xl bg-amber-50/70 border border-amber-200 flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-amber-900 flex items-center gap-1 mr-1">
            <CheckCircle2 className="w-4 h-4 text-amber-600" />
            Spot these tricky words:
          </span>
          {targetWords.map((tw, idx) => (
            <button
              key={idx}
              onClick={() => speakWord(tw)}
              className="px-2.5 py-1 rounded-lg bg-white border border-amber-300 text-amber-900 text-xs font-bold shadow-sm hover:border-amber-500 flex items-center gap-1 active:scale-95 transition-all"
            >
              <Volume2 className="w-3 h-3 text-amber-600" />
              <span>{tw}</span>
            </button>
          ))}
        </div>

        {/* Reading Passage Text Container */}
        <div className="p-6 sm:p-8 rounded-2xl bg-slate-50 border border-slate-200 min-h-[160px] flex items-center justify-center">
          <div className="leading-loose text-slate-800 text-xl sm:text-2xl font-medium select-text">
            {words.map((word, idx) => {
              const cleanW = word.toLowerCase().replace(/[^\w\u0900-\u097F]/g, '');
              const isTarget = cleanTargets.includes(cleanW);

              return (
                <span
                  key={idx}
                  onClick={() => speakWord(word)}
                  className={`inline-block mr-2 my-1 px-1.5 py-0.5 rounded-lg transition-all cursor-pointer ${
                    isTarget
                      ? 'bg-amber-100 text-amber-950 font-bold border border-amber-300 ring-2 ring-amber-400/30'
                      : 'hover:bg-slate-200/70'
                  }`}
                  title={isTarget ? 'Target practice word' : 'Tap to hear audio'}
                >
                  {word}
                </span>
              );
            })}
          </div>
        </div>

        {isRecording && (
          <div className="mt-4 flex items-center justify-center gap-2 text-rose-600 font-semibold text-xs animate-pulse">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
            <span>Listening to retest oral reading...</span>
          </div>
        )}

        {isRecording && liveTranscript && (
          <div className="mt-3 p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900 text-center">
            <span className="font-bold text-blue-700 mr-1.5">Live Hearing:</span>
            <span className="italic">"{liveTranscript}"</span>
          </div>
        )}

        <p className="text-xs text-slate-400 mt-4 text-center">
          Highlighted words are your target practice words. Read slowly and clearly!
        </p>
      </div>

      {/* Retest Audio Recorder Controls */}
      <AudioControls
        language={language}
        onAnalysisStart={onAnalysisStart}
        onAnalysisComplete={onAnalysisComplete}
        onReset={onReset}
        onRecordingStateChange={(rec) => setIsRecording(rec)}
        isAnalyzing={isAnalyzing}
      />
    </div>
  );
};
