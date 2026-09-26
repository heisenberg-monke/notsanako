'use client';

import React, { useEffect } from 'react';
import confetti from 'canvas-confetti';
import { DeltaSummary, ReadingMetrics } from '@/types';
import {
  Trophy,
  Sparkles,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Volume2,
  Gauge,
  ArrowRight,
  RotateCcw,
  X
} from 'lucide-react';

interface DeltaImprovementModalProps {
  isOpen: boolean;
  onClose: () => void;
  deltaSummary: DeltaSummary | null;
  retestMetrics: ReadingMetrics | null;
  baselineMetrics: ReadingMetrics | null;
  language: 'en' | 'hi';
  onRestart: () => void;
}

export const DeltaImprovementModal: React.FC<DeltaImprovementModalProps> = ({
  isOpen,
  onClose,
  deltaSummary,
  retestMetrics,
  baselineMetrics,
  language,
  onRestart,
}) => {
  useEffect(() => {
    if (isOpen && deltaSummary) {
      confetti({
        particleCount: 100,
        spread: 80,
        origin: { y: 0.5 },
      });
    }
  }, [isOpen, deltaSummary]);

  if (!isOpen || !deltaSummary) return null;

  const speakWord = (word: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.lang = language === 'hi' ? 'hi-IN' : 'en-IN';
    utterance.rate = 0.8;
    window.speechSynthesis.speak(utterance);
  };

  const isPositiveDelta = deltaSummary.delta >= 0;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-100 relative animate-in fade-in zoom-in-95 duration-200 max-h-[92vh] flex flex-col">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header with Trophy */}
        <div className="text-center mb-5 flex-shrink-0">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-400 to-yellow-500 text-white mb-2 shadow-lg shadow-amber-500/30">
            <Trophy className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-black text-slate-900">
            {language === 'hi' ? 'वाचन सुधार मूल्यांकन' : 'Adaptive Remediation Delta Report'}
          </h2>
          <p className="text-sm font-bold text-emerald-600 mt-1">
            {deltaSummary.positive_reinforcement}
          </p>
        </div>

        {/* Main Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5 flex-shrink-0">
          {/* Delta Card */}
          <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white text-center shadow-md">
            <div className="text-3xl font-black">
              {isPositiveDelta ? `+${deltaSummary.delta}%` : `${deltaSummary.delta}%`}
            </div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-100 mt-1 flex items-center justify-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" />
              Target Word Delta (Δ)
            </div>
          </div>

          {/* Mastered Count Card */}
          <div className="p-4 rounded-2xl bg-indigo-50 border border-indigo-200 text-center">
            <div className="text-3xl font-black text-indigo-700">
              {deltaSummary.mastered_words_count} / {deltaSummary.total_target_words}
            </div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-indigo-600 mt-1">
              Tricky Words Mastered
            </div>
          </div>

          {/* Speed Card */}
          <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-center">
            <div className="text-3xl font-black text-amber-700">
              {retestMetrics?.wcpm || 0}
            </div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-amber-600 mt-1 flex items-center justify-center gap-1">
              <Gauge className="w-3.5 h-3.5" />
              Retest Speed (WCPM)
            </div>
          </div>
        </div>

        {/* Word-by-Word Before vs After Breakdown */}
        <div className="overflow-y-auto flex-1 pr-1 space-y-3 mb-5">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            Target Word Mastery Breakdown (Before vs. After):
          </h3>

          <div className="space-y-2">
            {deltaSummary.word_mastery_breakdown.map((item, idx) => (
              <div
                key={idx}
                className="p-3 rounded-2xl border bg-slate-50 border-slate-200 flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => speakWord(item.word)}
                    className="font-bold text-slate-900 hover:text-blue-600 flex items-center gap-1"
                  >
                    <Volume2 className="w-3.5 h-3.5 text-blue-500" />
                    <span className="text-sm font-semibold">{item.word}</span>
                  </button>
                </div>

                <div className="flex items-center gap-4">
                  {/* Baseline State */}
                  <div className="flex items-center gap-1 text-[11px] text-slate-500">
                    <span>Baseline:</span>
                    {item.baseline_correct ? (
                      <span className="text-emerald-600 font-semibold flex items-center gap-0.5">
                        <CheckCircle2 className="w-3 h-3" /> OK
                      </span>
                    ) : (
                      <span className="text-rose-600 font-semibold flex items-center gap-0.5">
                        <XCircle className="w-3 h-3" /> Stumbled
                      </span>
                    )}
                  </div>

                  <span className="text-slate-300">→</span>

                  {/* Retest State */}
                  <div className="flex items-center gap-1 text-[11px]">
                    <span className="text-slate-500">Retest:</span>
                    {item.retest_correct ? (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Mastered!
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold flex items-center gap-1">
                        Developing
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Modal Actions Footer */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 flex-shrink-0">
          <button
            onClick={onRestart}
            className="px-5 py-2.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-semibold text-xs flex items-center gap-1.5 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Practice Another Story</span>
          </button>
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-md shadow-blue-500/20 transition-all flex items-center gap-1.5"
          >
            <span>Finish Session ✓</span>
          </button>
        </div>
      </div>
    </div>
  );
};
