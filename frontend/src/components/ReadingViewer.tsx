'use client';

import React, { useState } from 'react';
import { Passage, WordAlignment } from '@/types';
import { Volume2, HelpCircle, Sparkles, Pause, ShieldCheck, AlertCircle } from 'lucide-react';

interface ReadingViewerProps {
  passage: Passage;
  alignments?: WordAlignment[];
  isRecording: boolean;
  liveTranscript?: string;
  onWordClick?: (word: string) => void;
}

export const ReadingViewer: React.FC<ReadingViewerProps> = ({
  passage,
  alignments,
  isRecording,
  liveTranscript,
  onWordClick,
}) => {
  const [activeTooltip, setActiveTooltip] = useState<number | null>(null);

  const speakWord = (word: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.lang = passage.language === 'hi' ? 'hi-IN' : 'en-IN';
    utterance.rate = 0.85;
    window.speechSynthesis.speak(utterance);
    if (onWordClick) onWordClick(word);
  };

  const renderCleanPassage = () => {
    const words = passage.text.split(/\s+/);
    return (
      <div className="leading-relaxed tracking-normal text-slate-800 text-xl sm:text-2xl font-medium">
        {words.map((word, idx) => (
          <span
            key={idx}
            className="inline-block mr-2 my-1 px-1.5 py-0.5 rounded-lg hover:bg-blue-50 transition-colors cursor-pointer select-text"
            onClick={() => speakWord(word)}
            title="Click to hear pronunciation"
          >
            {word}
          </span>
        ))}
      </div>
    );
  };

  const renderAlignedPassage = () => {
    if (!alignments || alignments.length === 0) return renderCleanPassage();

    return (
      <div className="leading-loose text-slate-800 text-xl sm:text-2xl font-medium select-text">
        {alignments.map((item, idx) => {
          const isCorrect = item.status === 'correct';
          const isDialect = item.error_type === 'DIALECT_EQUIVALENT';
          const isMatra = item.error_type === 'MATRA';
          const isConjunct = item.error_type === 'CONJUNCT';
          const isPhonetic = item.error_type === 'PHONETIC';
          const isRepetition = item.error_type === 'REPETITION';
          const isOmit = item.status === 'omission';
          const isInsert = item.status === 'insertion';
          const hasLongPause = (item.pause_before || 0) >= 1.5;
          const inStumble = item.in_stumble_cluster;

          if (isInsert) {
            return (
              <span
                key={`insert-${idx}`}
                className="inline-flex items-center gap-1 mr-2 my-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-violet-100 text-violet-800 border border-violet-200"
                title={`Extra spoken word: ${item.spoken_word}`}
              >
                +{item.spoken_word}
              </span>
            );
          }

          const displayWord = item.expected_word || '';

          // Visual badge styling based on Indic diagnostic category
          let badgeStyle = 'text-slate-800 border-transparent hover:bg-slate-100';
          let categoryLabel = '';

          if (isDialect) {
            badgeStyle = 'bg-teal-50 text-teal-800 border-teal-300 font-semibold';
            categoryLabel = 'Dialect variant accepted';
          } else if (isCorrect) {
            badgeStyle = 'bg-emerald-50 text-emerald-900 border-emerald-300 font-semibold';
          } else if (isMatra) {
            badgeStyle = 'bg-pink-50 text-pink-900 border-pink-400 font-bold decoration-pink-500 underline decoration-2';
            categoryLabel = 'Matra (Vowel)';
          } else if (isConjunct) {
            badgeStyle = 'bg-purple-50 text-purple-900 border-purple-400 font-bold decoration-purple-500 underline decoration-2';
            categoryLabel = 'Conjunct (Sanyuktakshar)';
          } else if (isPhonetic) {
            badgeStyle = 'bg-amber-50 text-amber-900 border-amber-400 font-bold';
            categoryLabel = 'Phonetic Shift';
          } else if (isRepetition) {
            badgeStyle = 'bg-blue-50 text-blue-900 border-blue-400 font-medium italic';
            categoryLabel = 'Repetition';
          } else if (isOmit) {
            badgeStyle = 'bg-slate-100 text-slate-400 border-dashed border-slate-300 line-through';
            categoryLabel = 'Skipped';
          } else {
            badgeStyle = 'bg-rose-50 text-rose-800 border-rose-300 underline font-semibold';
          }

          return (
            <span
              key={`word-${idx}`}
              className={`relative inline-block mr-2 my-1.5 transition-all ${
                inStumble ? 'ring-2 ring-amber-300/60 rounded-xl px-1 py-0.5 bg-amber-50/20' : ''
              }`}
              onMouseEnter={() => (!isCorrect || isDialect || hasLongPause) && setActiveTooltip(idx)}
              onMouseLeave={() => setActiveTooltip(null)}
              onClick={() => speakWord(displayWord)}
            >
              {/* Optional Pause Badge if child hesitated > 1.5s */}
              {hasLongPause && (
                <span
                  className="inline-flex items-center gap-0.5 mr-1 text-[11px] font-bold px-1.5 py-0.2 rounded-md bg-amber-100 text-amber-800 border border-amber-300 align-middle"
                  title={`Hesitation pause of ${item.pause_before}s before this word`}
                >
                  <Pause className="w-2.5 h-2.5" />
                  {item.pause_before}s
                </span>
              )}

              <span className={`px-2 py-0.5 rounded-lg cursor-pointer transition-all border ${badgeStyle}`}>
                {displayWord}
              </span>

              {/* Indic Pedagogical Tooltip */}
              {(!isCorrect || isDialect || hasLongPause) && activeTooltip === idx && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 w-64 p-3 rounded-2xl bg-slate-900 text-white text-xs shadow-2xl animate-fade-in pointer-events-none">
                  <div className="flex items-center justify-between gap-1 mb-1 border-b border-slate-700 pb-1">
                    <span className="font-bold text-amber-300 uppercase tracking-wider text-[10px]">
                      {categoryLabel || 'Word Observation'}
                    </span>
                    {isDialect && (
                      <span className="text-[10px] text-teal-300 flex items-center gap-0.5">
                        <ShieldCheck className="w-3 h-3" /> Dialect-Fair
                      </span>
                    )}
                  </div>

                  {item.spoken_word && (
                    <div className="text-slate-200 mb-1">
                      Heard: <span className="text-rose-300 font-bold">"{item.spoken_word}"</span>
                    </div>
                  )}

                  {item.linguistic_detail && (
                    <p className="text-slate-300 text-[11px] leading-tight mb-1.5">
                      {item.linguistic_detail}
                    </p>
                  )}

                  {item.pedagogical_remedy && (
                    <div className="p-1.5 rounded-lg bg-slate-800 text-amber-200 text-[10px] font-medium border border-slate-700">
                      💡 {item.pedagogical_remedy}
                    </div>
                  )}

                  <div className="text-[9px] text-slate-400 mt-1.5 flex items-center gap-1">
                    <Volume2 className="w-3 h-3" /> Tap word to hear model audio
                  </div>
                </div>
              )}
            </span>
          );
        })}
      </div>
    );
  };

  return (
    <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-sm">
      {/* Passage Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 pb-4 border-b border-slate-100">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md">
            Oral Reading Practice
          </span>
          <h2 className="text-2xl font-bold text-slate-900 mt-2">
            {passage.title}
          </h2>
        </div>

        {/* Diagnostic Legend */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="flex items-center gap-1 text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-md font-medium border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            Accurate
          </span>
          <span className="flex items-center gap-1 text-pink-800 bg-pink-50 px-2 py-0.5 rounded-md font-medium border border-pink-200">
            <span className="w-2 h-2 rounded-full bg-pink-500" />
            Matra (इ/ई, उ/ऊ)
          </span>
          <span className="flex items-center gap-1 text-purple-800 bg-purple-50 px-2 py-0.5 rounded-md font-medium border border-purple-200">
            <span className="w-2 h-2 rounded-full bg-purple-500" />
            Conjunct (प्र, स्त)
          </span>
          <span className="flex items-center gap-1 text-teal-800 bg-teal-50 px-2 py-0.5 rounded-md font-medium border border-teal-200">
            <span className="w-2 h-2 rounded-full bg-teal-500" />
            Dialect-Fair ✓
          </span>
        </div>
      </div>

      {/* Reading Text Container */}
      <div className="p-6 sm:p-8 rounded-2xl bg-slate-50/70 border border-slate-200 min-h-[170px] flex items-center justify-center">
        {alignments && alignments.length > 0
          ? renderAlignedPassage()
          : renderCleanPassage()}
      </div>

      {/* Footer Helper */}
      <div className="mt-4 flex flex-wrap items-center justify-between text-xs text-slate-500 gap-2">
        <div className="flex items-center gap-1.5">
          <HelpCircle className="w-4 h-4 text-blue-500" />
          <span>Click any word to hear model pronunciation. Hover over highlighted words to see phonics tips.</span>
        </div>

        {isRecording && (
          <div className="flex items-center gap-2 text-rose-600 font-semibold animate-pulse">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
            Listening to oral reading...
          </div>
        )}
      </div>

      {isRecording && liveTranscript && (
        <div className="mt-4 p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900">
          <span className="font-bold text-blue-700 mr-1.5">Live Speech Transcript:</span>
          <span className="italic">"{liveTranscript}"</span>
        </div>
      )}
    </div>
  );
};
