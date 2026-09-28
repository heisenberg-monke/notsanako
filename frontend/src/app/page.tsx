'use client';

import React, { useState, useEffect } from 'react';
import { Header } from '@/components/Header';
import { PassageSelector } from '@/components/PassageSelector';
import { ReadingViewer } from '@/components/ReadingViewer';
import { AudioControls } from '@/components/AudioControls';
import { EvaluationModal } from '@/components/EvaluationModal';
import { ThemeSelectorModal } from '@/components/ThemeSelectorModal';
import { RemediationReadingCard } from '@/components/RemediationReadingCard';
import { DeltaImprovementModal } from '@/components/DeltaImprovementModal';
import {
  Passage,
  ReadingAnalysis,
  WordAlignment,
  PriorityTargetWord,
  RemediationPassage,
  DeltaSummary,
  ReadingMetrics,
  RetestEvaluationResult
} from '@/types';
import { Sparkles, RefreshCw, AlertCircle, ArrowRight, CheckCircle2, Trophy, RotateCcw } from 'lucide-react';

const DEFAULT_PASSAGES: Passage[] = [
  {
    id: 'hi-rabbit-gr3',
    title: 'चालाक खरगोश और शेर',
    grade_level: 3,
    language: 'hi',
    target_wcpm: 60,
    description: 'पंचतंत्र की प्रसिद्ध कहानी जो चतुराई और बुद्धि का महत्व बताती है।',
    text: 'एक घने जंगल में भासुरक नाम का एक घमंडी शेर रहता था। वह प्रतिदिन कई निर्दोष जानवरों का शिकार करता था। एक दिन एक बुद्धिमान छोटे खरगोश की बारी आई। खरगोश ने एक गहरी योजना बनाई और शेर को एक गहरे कुएँ के पास ले गया। कुएँ के पानी में अपनी परछाई देखकर शेर ने गर्जना की और कुएँ में कूद पड़ा। इस तरह छोटे खरगोश ने अपनी सूझबूझ से जंगल के सभी जीवों की जान बचाई।',
    difficulty: 'Easy',
    key_vocabulary: ['घमंडी', 'बुद्धिमान', 'परछाई', 'गर्जना', 'सूझबूझ'],
  },
  {
    id: 'hi-farmer-gr4',
    title: 'मेहनती किसान और सुनहरा खेत',
    grade_level: 4,
    language: 'hi',
    target_wcpm: 75,
    description: 'परिश्रम और ईमानदारी की प्रेरणादायक कहानी।',
    text: 'रामू काका गाँव के सबसे परिश्रमी किसान थे। वह सूरज उगने से पहले ही अपने दो बैलों के साथ खेत में पहुँच जाते थे। कड़ाके की धूप हो या मूसलाधार बारिश, उन्होंने कभी काम से जी नहीं चुराया। जब सुनहरी फसल लहलहाई, तो पूरे गाँव ने उनके धैर्य और लगन की प्रशंसा की। रामू काका ने सिखाया कि सच्ची मेहनत कभी व्यर्थ नहीं जाती।',
    difficulty: 'Medium',
    key_vocabulary: ['परिश्रमी', 'मूसलाधार', 'धैर्य', 'प्रशंसा', 'व्यर्थ'],
  },
  {
    id: 'en-kalam-gr4',
    title: 'Wings of Curiosity',
    grade_level: 4,
    language: 'en',
    target_wcpm: 80,
    description: 'An inspiring tale based on Dr. APJ Abdul Kalam\'s childhood in Rameswaram.',
    text: 'Young Abdul loved watching sea birds glide gently across the blue ocean. Early every dawn, he walked along the sandy shore to deliver newspapers to the townspeople. His science teacher once took the class to the seashore to show how birds flap their wings to stay balanced in strong wind. That simple lesson sparked a lifelong dream in Abdul to build rockets that soar into space.',
    difficulty: 'Medium',
    key_vocabulary: ['curiosity', 'glide', 'dawn', 'balanced', 'sparked', 'soar'],
  },
  {
    id: 'en-potter-gr3',
    title: 'The Brave Little Potter',
    grade_level: 3,
    language: 'en',
    target_wcpm: 65,
    description: 'A cheerful village story about quick thinking and friendship.',
    text: 'Raghu was a cheerful potter in a small village near Mysore. Every morning, he shaped cool clay into round pots and lamps. One rainy afternoon, a tired little monkey took shelter in his workshop. Raghu smiled and offered the monkey a ripe yellow banana. From that day on, the monkey helped Raghu carry dry leaves to the kiln.',
    difficulty: 'Easy',
    key_vocabulary: ['cheerful', 'workshop', 'shelter', 'potter', 'kiln'],
  },
];

type SessionStage = 'BASELINE' | 'THEME_SELECT' | 'REMEDIATION_RETEST' | 'COMPLETED';

export default function Home() {
  const [passages, setPassages] = useState<Passage[]>(DEFAULT_PASSAGES);
  const [selectedPassage, setSelectedPassage] = useState<Passage>(DEFAULT_PASSAGES[0]);
  const [selectedLanguage, setSelectedLanguage] = useState<'en' | 'hi'>('hi');
  const [selectedGrade, setSelectedGrade] = useState<number>(3);

  // Stage Tracking
  const [sessionStage, setSessionStage] = useState<SessionStage>('BASELINE');

  // Baseline Recording & Analysis
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [baselineAnalysis, setBaselineAnalysis] = useState<ReadingAnalysis | null>(null);
  const [isBaselineModalOpen, setIsBaselineModalOpen] = useState(false);

  // Theme & Target Words
  const [isThemeModalOpen, setIsThemeModalOpen] = useState(false);
  const [priorityTargetWords, setPriorityTargetWords] = useState<PriorityTargetWord[]>([]);
  const [isGeneratingStory, setIsGeneratingStory] = useState(false);

  // Remediation Story & Retest
  const [remediationPassage, setRemediationPassage] = useState<RemediationPassage | null>(null);
  const [isRetestAnalyzing, setIsRetestAnalyzing] = useState(false);

  // Final Delta Results
  const [deltaSummary, setDeltaSummary] = useState<DeltaSummary | null>(null);
  const [retestMetrics, setRetestMetrics] = useState<ReadingMetrics | null>(null);
  const [isDeltaModalOpen, setIsDeltaModalOpen] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load passages from backend API if available
  useEffect(() => {
    async function loadPassages() {
      try {
        const res = await fetch('/api/passages');
        if (res.ok) {
          const data = await res.json();
          if (data.passages && data.passages.length > 0) {
            setPassages(data.passages);
            const match = data.passages.find(
              (p: Passage) => p.language === selectedLanguage && p.grade_level === selectedGrade
            ) || data.passages[0];
            setSelectedPassage(match);
          }
        }
      } catch (err) {
        console.info('Backend not connected yet, using bundled passages.');
      }
    }
    loadPassages();
  }, [selectedLanguage, selectedGrade]);

  const handleLanguageChange = (lang: 'en' | 'hi') => {
    setSelectedLanguage(lang);
    const match = passages.find((p) => p.language === lang && p.grade_level === selectedGrade)
      || passages.find((p) => p.language === lang)
      || passages[0];
    setSelectedPassage(match);
    handleResetAll();
  };

  const handleGradeChange = (grade: number) => {
    setSelectedGrade(grade);
    const match = passages.find((p) => p.grade_level === grade && p.language === selectedLanguage)
      || passages.find((p) => p.grade_level === grade)
      || passages[0];
    setSelectedPassage(match);
    handleResetAll();
  };

  const handlePassageSelect = (passage: Passage) => {
    setSelectedPassage(passage);
    setSelectedLanguage(passage.language);
    setSelectedGrade(passage.grade_level);
    handleResetAll();
  };

  const handleResetAll = () => {
    setSessionStage('BASELINE');
    setBaselineAnalysis(null);
    setLiveTranscript('');
    setIsBaselineModalOpen(false);
    setIsThemeModalOpen(false);
    setRemediationPassage(null);
    setDeltaSummary(null);
    setRetestMetrics(null);
    setIsDeltaModalOpen(false);
    setErrorMessage(null);
  };

  const handleBaselineAudioComplete = async (
    audioBlob: Blob,
    clientTranscript: string,
    durationSeconds: number
  ) => {
    setIsAnalyzing(true);
    setErrorMessage(null);

    console.info(`[Audio Lifecycle] STT started → uploading ${(audioBlob.size / 1024).toFixed(1)} KB baseline audio to /api/analyze-reading`);

    try {
      const formData = new FormData();
      formData.append('passage_id', selectedPassage.id);
      formData.append('duration_seconds', durationSeconds.toString());
      if (clientTranscript) {
        formData.append('client_transcript', clientTranscript);
      }
      if (audioBlob && audioBlob.size > 0) {
        formData.append('audio', audioBlob, 'baseline.webm');
      }

      const res = await fetch('/api/analyze-reading', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Server returned error code: ${res.status}`);
      }

      const analysisData: ReadingAnalysis = await res.json();
      console.info(`[Audio Lifecycle] STT completed → Analysis received: accuracy=${analysisData.metrics?.accuracy_percentage?.toFixed(1)}% | WCPM=${analysisData.metrics?.wcpm?.toFixed(0)}`);

      setBaselineAnalysis(analysisData);

      if (analysisData.priority_target_words && analysisData.priority_target_words.length > 0) {
        setPriorityTargetWords(analysisData.priority_target_words);
      } else {
        const defaults = selectedPassage.key_vocabulary.slice(0, 4).map((w) => ({
          word: w,
          error_type: 'PRACTICE',
          frequency: 1,
          total_score: 3.0,
        }));
        setPriorityTargetWords(defaults);
      }

      console.info('[Audio Lifecycle] Result displayed → opening baseline evaluation modal.');
      setIsBaselineModalOpen(true);
    } catch (err: any) {
      console.error('[Audio Lifecycle] Baseline analysis failed:', err);
      setErrorMessage(
        err.message || 'Audio analysis failed. Verify backend is running and STT API key is configured in backend/.env.'
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Step 2 -> 3: Student proceeds from Evaluation to Theme Selection & Generation
  const handleProceedToTheme = () => {
    setIsBaselineModalOpen(false);
    setIsThemeModalOpen(true);
  };

  // Step 3: Call Gemini / Backend to Generate Custom Remediation Story
  const handleGenerateStory = async (theme: string, studentName: string) => {
        console.log('[PAGE] handleGenerateStory CALLED', {
        theme,
        studentName,
    });

    setIsGeneratingStory(true);
    try {
      const targetWords = priorityTargetWords.map((tw) => tw.word);

      const res = await fetch('/api/rank-and-generate-remediation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          grade_level: selectedGrade,
          language: selectedLanguage,
          student_name: studentName,
          theme: theme,
          override_target_words: targetWords,
          structured_errors: baselineAnalysis?.structured_errors || [],
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setRemediationPassage(data.remediation_passage);
        setIsThemeModalOpen(false);
        setSessionStage('REMEDIATION_RETEST');
        return;
      }
    } catch (err) {
      console.warn('Backend story generation failed, using local deterministic story:', err);
    } finally {
      setIsGeneratingStory(false);
    }

    // Local fallback 60-80 word structured story
    const targetWords = priorityTargetWords.map((tw) => tw.word);
    const w1 = targetWords[0] || 'साहस';
    const w2 = targetWords[1] || 'परिश्रम';
    const w3 = targetWords[2] || 'बुद्धिमान';
    const w4 = targetWords[3] || 'प्रशंसा';

    const fallbackStoryText = selectedLanguage === 'hi'
      ? `एक सुनहरी सुबह ${studentName} ने अपनी नई उड़ान शुरू की। उन्होंने जाना कि जीवन में ${w1} और ${w2} सबसे सच्चे साथी हैं। जब भी कोई नई चुनौती आई, उन्होंने एक ${w3} बालक की तरह हर बात को ध्यान से समझा। गुरुजी ने उनके लगन की ${w4} की और कहा कि ${w1} से हर लक्ष्य प्राप्त होता है। सभी ने तालियाँ बजाकर उनका हौसला बढ़ाया।`
      : `Early one sunny morning, young ${studentName} embarked on an inspiring journey across the valley. Having pure ${w1} and a steady mind proved essential for every challenge. Along the breezy path, walking with a ${w2} spirit helped overcome every steep hill. A kind guide smiled warmly and noted how this effort ${w3} immense joy in everyone. Soon, the companions celebrated their triumph with great ${w4}.`;

    const fallbackRemediation: RemediationPassage = {
      title: `${studentName} का नया सफर`,
      text: fallbackStoryText,
      sentences: [fallbackStoryText],
      target_word_occurrences: targetWords.map((w) => ({
        word: w,
        occurrences_count: 1,
        sentence_indices: [0],
      })),
      word_count: fallbackStoryText.split(/\s+/).length,
      theme: theme,
      grade_level: selectedGrade,
      language: selectedLanguage,
      generator_source: 'Local Fallback',
    };

    setRemediationPassage(fallbackRemediation);
    setIsThemeModalOpen(false);
    setSessionStage('REMEDIATION_RETEST');
  };

  // Step 4: Retest Audio Completed -> Evaluate Delta Improvement
  const handleRetestAudioComplete = async (
    audioBlob: Blob,
    clientTranscript: string,
    durationSeconds: number
  ) => {
    if (!remediationPassage) return;
    setIsRetestAnalyzing(true);
    setErrorMessage(null);

    console.info(`[Audio Lifecycle] STT started → uploading ${(audioBlob.size / 1024).toFixed(1)} KB retest audio to /api/evaluate-retest`);

    const targetWords = priorityTargetWords.map((tw) => tw.word);

    try {
      const formData = new FormData();
      formData.append('remediation_passage_text', remediationPassage.text);
      formData.append('target_words_json', JSON.stringify(targetWords));
      formData.append('duration_seconds', durationSeconds.toString());
      formData.append('language', selectedLanguage);
      if (baselineAnalysis?.alignments) {
        formData.append('baseline_alignments_json', JSON.stringify(baselineAnalysis.alignments));
      }
      if (clientTranscript) {
        formData.append('client_transcript', clientTranscript);
      }
      if (audioBlob && audioBlob.size > 0) {
        formData.append('audio', audioBlob, 'retest.webm');
      }

      const res = await fetch('/api/evaluate-retest', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Server returned error code: ${res.status}`);
      }

      const retestData: RetestEvaluationResult = await res.json();
      console.info(`[Audio Lifecycle] STT completed → Retest delta: ${retestData.delta_summary?.delta?.toFixed(2)} | mastered=${retestData.delta_summary?.mastered_words_count}`);

      setDeltaSummary(retestData.delta_summary);
      setRetestMetrics(retestData.retest_metrics);
      setSessionStage('COMPLETED');

      console.info('[Audio Lifecycle] Result displayed → opening delta improvement modal.');
      setIsDeltaModalOpen(true);
    } catch (err: any) {
      console.error('[Audio Lifecycle] Retest evaluation failed:', err);
      setErrorMessage(
        err.message || 'Retest evaluation failed. Verify backend is running and STT API key is configured in backend/.env.'
      );
    } finally {
      setIsRetestAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 font-sans">
      <Header selectedGrade={selectedGrade} language={selectedLanguage} />

      {/* Progress Stage Tracker Bar */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3">
          <div className="flex items-center justify-between text-xs font-semibold gap-2 overflow-x-auto pb-1 sm:pb-0">
            <div
              className={`flex items-center gap-2 flex-shrink-0 ${
                sessionStage === 'BASELINE' ? 'text-blue-600 font-bold' : 'text-slate-500'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  sessionStage === 'BASELINE'
                    ? 'bg-blue-600 text-white'
                    : 'bg-emerald-100 text-emerald-700'
                }`}
              >
                1
              </span>
              <span>1. Baseline Reading</span>
            </div>

            <span className="text-slate-300">→</span>

            <div
              className={`flex items-center gap-2 flex-shrink-0 ${
                sessionStage === 'THEME_SELECT' ? 'text-indigo-600 font-bold' : 'text-slate-500'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  sessionStage === 'THEME_SELECT'
                    ? 'bg-indigo-600 text-white'
                    : sessionStage === 'REMEDIATION_RETEST' || sessionStage === 'COMPLETED'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-200 text-slate-600'
                }`}
              >
                2
              </span>
              <span>2. Diagnose & Theme</span>
            </div>

            <span className="text-slate-300">→</span>

            <div
              className={`flex items-center gap-2 flex-shrink-0 ${
                sessionStage === 'REMEDIATION_RETEST' ? 'text-indigo-600 font-bold' : 'text-slate-500'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  sessionStage === 'REMEDIATION_RETEST'
                    ? 'bg-indigo-600 text-white'
                    : sessionStage === 'COMPLETED'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-200 text-slate-600'
                }`}
              >
                3
              </span>
              <span>3. Personalized Retest</span>
            </div>

            <span className="text-slate-300">→</span>

            <div
              className={`flex items-center gap-2 flex-shrink-0 ${
                sessionStage === 'COMPLETED' ? 'text-emerald-600 font-bold' : 'text-slate-400'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  sessionStage === 'COMPLETED'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-200 text-slate-600'
                }`}
              >
                4
              </span>
              <span>4. Mastery Delta (Δ)</span>
            </div>
          </div>
        </div>
      </div>

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
        {errorMessage && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* STAGE 1: Baseline Reading */}
        {sessionStage === 'BASELINE' && (
          <>
            <PassageSelector
              passages={passages}
              selectedPassage={selectedPassage}
              onSelectPassage={handlePassageSelect}
              selectedLanguage={selectedLanguage}
              onLanguageChange={handleLanguageChange}
              selectedGrade={selectedGrade}
              onGradeChange={handleGradeChange}
              disabled={isRecording || isAnalyzing}
            />

            <ReadingViewer
              passage={selectedPassage}
              alignments={baselineAnalysis?.alignments}
              isRecording={isRecording}
            />

            <AudioControls
              language={selectedLanguage}
              onAnalysisStart={() => setIsAnalyzing(true)}
              onAnalysisComplete={handleBaselineAudioComplete}
              onReset={handleResetAll}
              onRecordingStateChange={(rec) => setIsRecording(rec)}
              isAnalyzing={isAnalyzing}
            />
          </>
        )}

        {/* STAGE 2 / 3: Personalized Story Remediation & Retest */}
        {sessionStage === 'REMEDIATION_RETEST' && remediationPassage && (
          <RemediationReadingCard
            passage={remediationPassage}
            targetWords={priorityTargetWords.map((tw) => tw.word)}
            language={selectedLanguage}
            onAnalysisStart={() => setIsRetestAnalyzing(true)}
            onAnalysisComplete={handleRetestAudioComplete}
            onReset={() => setSessionStage('BASELINE')}
            isAnalyzing={isRetestAnalyzing}
          />
        )}

        {/* STAGE 4: Completed Closed-Loop Banner */}
        {sessionStage === 'COMPLETED' && deltaSummary && (
          <div className="p-8 rounded-3xl bg-white border border-slate-200 shadow-sm text-center space-y-4">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-700 shadow-sm">
              <Trophy className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-black text-slate-900">
              {selectedLanguage === 'hi' ? 'अभ्यास सत्र सफलतापूर्वक पूर्ण!' : 'Remediation Loop Complete!'}
            </h2>
            <p className="text-sm font-semibold text-emerald-600 max-w-lg mx-auto">
              {deltaSummary.positive_reinforcement}
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={() => setIsDeltaModalOpen(true)}
                className="px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md transition-all flex items-center gap-2"
              >
                <span>View Full Delta Report (Δ)</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                onClick={handleResetAll}
                className="px-6 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold text-xs transition-colors flex items-center gap-2"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Practice Another Story</span>
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Step 2: Baseline Diagnostic Modal */}
      <EvaluationModal
        isOpen={isBaselineModalOpen}
        onClose={() => setIsBaselineModalOpen(false)}
        analysis={baselineAnalysis}
        language={selectedLanguage}
        onGenerateAdaptivePassage={async () => {
          handleProceedToTheme();
          return {
            target_words: priorityTargetWords.map((tw) => tw.word),
            grade_level: selectedGrade,
            remediation_story: 'Loading customized story...',
            prompt_context: 'Story generation',
          };
        }}
      />

      {/* Step 3: Theme Selector & Gemini Generator Modal */}
      <ThemeSelectorModal
        isOpen={isThemeModalOpen}
        onClose={() => setIsThemeModalOpen(false)}
        targetWords={priorityTargetWords}
        gradeLevel={selectedGrade}
        language={selectedLanguage}
        onGenerateStory={handleGenerateStory}
        isGenerating={isGeneratingStory}
      />

      {/* Step 4: Final Delta Improvement Modal */}
      <DeltaImprovementModal
        isOpen={isDeltaModalOpen}
        onClose={() => setIsDeltaModalOpen(false)}
        deltaSummary={deltaSummary}
        retestMetrics={retestMetrics}
        baselineMetrics={baselineAnalysis?.metrics || null}
        language={selectedLanguage}
        onRestart={handleResetAll}
      />
    </div>
  );
}
