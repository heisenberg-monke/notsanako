'use client';

import React, { useEffect, useState } from 'react';
import confetti from 'canvas-confetti';
import { ReadingAnalysis, AdaptiveRemediationPreview, StructuredErrorRecord } from '@/types';
import {
  Trophy,
  Gauge,
  CheckCircle2,
  AlertTriangle,
  Volume2,
  Sparkles,
  ArrowRight,
  X,
  Clock,
  ShieldCheck,
  Pause,
  Layers,
  BookOpen,
  Loader2,
  HelpCircle
} from 'lucide-react';

interface EvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
  analysis: ReadingAnalysis | null;
  language: 'en' | 'hi';
  onGenerateAdaptivePassage?: (struggledWords: string[]) => Promise<AdaptiveRemediationPreview>;
}

export const EvaluationModal: React.FC<EvaluationModalProps> = ({
  isOpen,
  onClose,
  analysis,
  language,
  onGenerateAdaptivePassage,
}) => {
  const [remediationPreview, setRemediationPreview] = useState<AdaptiveRemediationPreview | null>(null);
  const [isGeneratingStory, setIsGeneratingStory] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'indic_breakdown' | 'records'>('overview');

  useEffect(() => {
    if (isOpen && analysis) {
      if (analysis.metrics.accuracy_percentage >= 75) {
        confetti({
          particleCount: 80,
          spread: 70,
          origin: { y: 0.6 },
        });
      }
    } else {
      setRemediationPreview(null);
      setActiveTab('overview');
    }
  }, [isOpen, analysis]);

  if (!isOpen || !analysis) return null;

  const { metrics, error_breakdown, structured_errors, stumble_clusters, long_pauses, feedback } = analysis;

  const speakWord = (word: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.lang = language === 'hi' ? 'hi-IN' : 'en-IN';
    utterance.rate = 0.8;
    window.speechSynthesis.speak(utterance);
  };

  const handleRequestAdaptiveStory = async () => {
    if (!onGenerateAdaptivePassage) return;
    setIsGeneratingStory(true);
    try {
      const wordsToRemediate = structured_errors && structured_errors.length > 0
        ? structured_errors.map(e => e.word)
        : ['प्रतियोगिता', 'परिश्रमी', 'बुद्धिमान'];
      const preview = await onGenerateAdaptivePassage(wordsToRemediate);
      setRemediationPreview(preview);
    } catch (err) {
      console.error('Failed to generate adaptive remediation story:', err);
    } finally {
      setIsGeneratingStory(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4">
      <div className="bg-white rounded-3xl max-w-3xl w-full p-5 sm:p-8 shadow-2xl border border-slate-100 relative animate-in fade-in zoom-in-95 duration-200 max-h-[92vh] flex flex-col">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="text-center mb-4 flex-shrink-0">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-amber-100 text-amber-600 mb-2 shadow-sm">
            <Trophy className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">
            {language === 'hi' ? 'वाचन एवं भाषाई विश्लेषण' : 'Oral Reading & Linguistic Analysis'}
          </h2>
          <p className="text-xs font-semibold text-blue-600 uppercase tracking-wider mt-0.5">
            {metrics.rating}
          </p>
          <p className="text-xs text-slate-600 max-w-lg mx-auto mt-1 leading-normal">
            {feedback}
          </p>
        </div>

        {/* Nav Tabs */}
        <div className="flex border-b border-slate-200 mb-4 flex-shrink-0 gap-2 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-2.5 px-3 border-b-2 transition-all ${
              activeTab === 'overview'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Fluency Overview
          </button>
          <button
            onClick={() => setActiveTab('indic_breakdown')}
            className={`pb-2.5 px-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'indic_breakdown'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <span>Indic Linguistic Insights</span>
            {(error_breakdown?.matra_errors || 0) + (error_breakdown?.conjunct_errors || 0) > 0 && (
              <span className="w-2 h-2 rounded-full bg-pink-500" />
            )}
          </button>
          <button
            onClick={() => setActiveTab('records')}
            className={`pb-2.5 px-3 border-b-2 transition-all ${
              activeTab === 'records'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Diagnostic Records ({structured_errors?.length || 0})
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="overflow-y-auto flex-1 pr-1 space-y-4">
          {activeTab === 'overview' && (
            <>
              {/* Primary Scorecard Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-2xl bg-blue-50/80 border border-blue-100 text-center">
                  <div className="text-2xl font-black text-blue-700">{metrics.accuracy_percentage}%</div>
                  <div className="text-[11px] font-semibold text-blue-600 uppercase tracking-wide mt-0.5">
                    Reading Accuracy
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-emerald-50/80 border border-emerald-100 text-center">
                  <div className="text-2xl font-black text-emerald-700">{metrics.wcpm}</div>
                  <div className="text-[11px] font-semibold text-emerald-600 uppercase tracking-wide mt-0.5">
                    WCPM (Speed)
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-amber-50/80 border border-amber-100 text-center">
                  <div className="text-2xl font-black text-amber-700">{metrics.target_wcpm}</div>
                  <div className="text-[11px] font-semibold text-amber-600 uppercase tracking-wide mt-0.5">
                    Benchmark Target
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-purple-50/80 border border-purple-100 text-center">
                  <div className="text-2xl font-black text-purple-700">{metrics.duration_seconds}s</div>
                  <div className="text-[11px] font-semibold text-purple-600 uppercase tracking-wide mt-0.5">
                    Duration
                  </div>
                </div>
              </div>

              {/* Special Indicators Summary (Pauses, Clusters, Dialect) */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-amber-50/60 border border-amber-200 flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-amber-100 text-amber-800">
                    <Pause className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-amber-900">
                      {error_breakdown?.long_pauses_count || 0} Pauses &gt; 1.5s
                    </div>
                    <div className="text-[10px] text-amber-700">Hesitation indicators</div>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-pink-50/60 border border-pink-200 flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-pink-100 text-pink-800">
                    <Layers className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-pink-900">
                      {error_breakdown?.stumble_clusters_count || 0} Stumble Clusters
                    </div>
                    <div className="text-[10px] text-pink-700">3+ consecutive stumbles</div>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-teal-50/60 border border-teal-200 flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-teal-100 text-teal-800">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-teal-900">
                      {error_breakdown?.dialect_variants_accepted || 0} Dialect Variants
                    </div>
                    <div className="text-[10px] text-teal-700">Fairly credited ✓</div>
                  </div>
                </div>
              </div>
            </>
          )}

          {activeTab === 'indic_breakdown' && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                Devanagari & Indic Phonological Diagnosis
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Matra Errors Card */}
                <div className="p-4 rounded-2xl bg-pink-50/60 border border-pink-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-pink-900 text-sm">
                      Matra / Vowel Length Mismatch
                    </span>
                    <span className="text-xs font-extrabold px-2 py-0.5 rounded-full bg-pink-200 text-pink-800">
                      {error_breakdown?.matra_errors || 0}
                    </span>
                  </div>
                  <p className="text-[11px] text-pink-800 leading-tight">
                    Confusion between short and long vowels (e.g. short 'ि' vs long 'ी', 'ु' vs 'ू').
                  </p>
                  <div className="mt-2 text-[10px] text-pink-700 font-medium">
                    Pedagogy: Emphasize vowel duration during choral warm-ups.
                  </div>
                </div>

                {/* Conjunct Consonants Card */}
                <div className="p-4 rounded-2xl bg-purple-50/60 border border-purple-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-purple-900 text-sm">
                      Conjunct / Sanyuktakshar Clusters
                    </span>
                    <span className="text-xs font-extrabold px-2 py-0.5 rounded-full bg-purple-200 text-purple-800">
                      {error_breakdown?.conjunct_errors || 0}
                    </span>
                  </div>
                  <p className="text-[11px] text-purple-800 leading-tight">
                    Clusters with virama/halant (प्र, क्ष, त्र, ज्ञ, स्त, R-kars) split or simplified.
                  </p>
                  <div className="mt-2 text-[10px] text-purple-700 font-medium">
                    Pedagogy: Practice half-letter sound blends without vowel insertion.
                  </div>
                </div>

                {/* Phonetic Shifts Card */}
                <div className="p-4 rounded-2xl bg-amber-50/60 border border-amber-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-amber-900 text-sm">
                      Phonetic Articulation (त/ट, क/ख)
                    </span>
                    <span className="text-xs font-extrabold px-2 py-0.5 rounded-full bg-amber-200 text-amber-800">
                      {error_breakdown?.phonetic_errors || 0}
                    </span>
                  </div>
                  <p className="text-[11px] text-amber-800 leading-tight">
                    Shifts between dental/retroflex sounds or aspirated/unaspirated consonants.
                  </p>
                  <div className="mt-2 text-[10px] text-amber-700 font-medium">
                    Pedagogy: Tongue placement and breath release demonstrations.
                  </div>
                </div>

                {/* Dialect Fair Card */}
                <div className="p-4 rounded-2xl bg-teal-50/60 border border-teal-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-teal-900 text-sm">
                      Dialect-Fair Equivalence
                    </span>
                    <span className="text-xs font-extrabold px-2 py-0.5 rounded-full bg-teal-200 text-teal-800">
                      {error_breakdown?.dialect_variants_accepted || 0}
                    </span>
                  </div>
                  <p className="text-[11px] text-teal-800 leading-tight">
                    Recognized regional variations (e.g. Eastern /v/ $\leftrightarrow$ /b/, /s/ $\leftrightarrow$ /sh/) accepted without penalty.
                  </p>
                  <div className="mt-2 text-[10px] text-teal-700 font-medium">
                    Pedagogy: Honors cultural and regional linguistic identity.
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'records' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Structured Error Diagnostic Telemetry</span>
                <span>Pedagogical & Non-Diagnostic</span>
              </div>

              {structured_errors && structured_errors.length > 0 ? (
                <div className="space-y-2">
                  {structured_errors.map((err, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs flex flex-col gap-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => speakWord(err.word)}
                            className="font-bold text-slate-900 hover:text-blue-600 flex items-center gap-1"
                          >
                            <Volume2 className="w-3.5 h-3.5 text-blue-500" />
                            <span>{err.word}</span>
                          </button>
                          {err.spoken_word && (
                            <span className="text-slate-400">
                              (Spoken: <span className="text-rose-600 font-semibold">{err.spoken_word}</span>)
                            </span>
                          )}
                        </div>

                        <span className="px-2 py-0.5 rounded-md font-bold text-[10px] uppercase tracking-wider bg-pink-100 text-pink-800">
                          {err.error_type}
                        </span>
                      </div>

                      <p className="text-slate-600 text-[11px]">
                        {err.linguistic_detail}
                      </p>

                      <div className="p-2 rounded-xl bg-blue-50/70 border border-blue-100 text-blue-900 text-[11px] font-medium">
                        🌱 <strong>Teaching Guidance:</strong> {err.pedagogical_remedy}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center text-emerald-700 text-xs font-semibold bg-emerald-50 rounded-2xl border border-emerald-200">
                  🎉 Fantastic! No phonological or reading errors recorded in this attempt!
                </div>
              )}
            </div>
          )}

          {/* Adaptive Story Generator (Gemini Powered) */}
          {remediationPreview ? (
            <div className="p-4 rounded-2xl bg-indigo-50/80 border border-indigo-200 animate-in fade-in">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-800 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                  Personalized Remediation Story Generated ({remediationPreview.source || 'AI'})
                </span>
              </div>
              <p className="text-sm text-slate-800 leading-relaxed font-medium bg-white p-3.5 rounded-xl border border-indigo-100">
                "{remediationPreview.remediation_story}"
              </p>
              <p className="text-[11px] text-indigo-700 mt-2">
                Remediating Target Words: <strong>{remediationPreview.target_words.join(', ')}</strong>
              </p>
            </div>
          ) : (
            <button
              onClick={handleRequestAdaptiveStory}
              disabled={isGeneratingStory}
              className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 text-white font-bold text-xs shadow-md shadow-indigo-500/20 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              {isGeneratingStory ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Synthesizing Adaptive Story via Gemini...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-300" />
                  <span>Synthesize Personalized Remediation Story (Based on these struggle patterns)</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          )}
        </div>

        {/* Modal Actions Footer */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 mt-3 flex-shrink-0">
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-semibold text-xs transition-colors"
          >
            Review Passage
          </button>
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-md shadow-blue-500/20 transition-all"
          >
            Practice Another Passage
          </button>
        </div>
      </div>
    </div>
  );
};
