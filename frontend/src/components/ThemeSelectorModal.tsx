'use client';

import React, { useEffect, useRef, useState } from 'react';
import { PriorityTargetWord } from '@/types';
import { Sparkles, Rocket, Compass, Trophy, PartyPopper, Loader2, Volume2, X } from 'lucide-react';

interface ThemeSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetWords: PriorityTargetWord[];
  gradeLevel: number;
  language: 'en' | 'hi';
  onGenerateStory: (theme: string, studentName: string) => Promise<void>;
  isGenerating: boolean;
}

const THEMES = [
  {
    id: 'space',
    icon: Rocket,
    title_en: 'Space & Rockets',
    title_hi: 'अंतरिक्ष यात्रा',
    desc_en: 'Voyage to distant stars, satellites, and planets.',
    desc_hi: 'तारों, उपग्रहों और नए ग्रहों का रोमांचक सफर।',
    accent: 'from-blue-600 to-indigo-600',
    border: 'border-blue-200 hover:border-blue-400',
    bg: 'bg-blue-50/50'
  },
  {
    id: 'jungle',
    icon: Compass,
    title_en: 'Jungle & Animals',
    title_hi: 'जंगल और जानवर',
    desc_en: 'Explore lush forests, brave tigers, and singing rivers.',
    desc_hi: 'घने जंगल, बुद्धिमान शेर और चहकते पक्षी।',
    accent: 'from-emerald-600 to-teal-600',
    border: 'border-emerald-200 hover:border-emerald-400',
    bg: 'bg-emerald-50/50'
  },
  {
    id: 'sports',
    icon: Trophy,
    title_en: 'Sports & Games',
    title_hi: 'खेलकूद और साहस',
    desc_en: 'Exciting matches, team spirit, and triumphant cheers.',
    desc_hi: 'मैदान का उत्साह, दोस्तों की टोली और जीत की खुशी।',
    accent: 'from-amber-500 to-orange-600',
    border: 'border-amber-200 hover:border-amber-400',
    bg: 'bg-amber-50/50'
  },
  {
    id: 'festivals',
    icon: PartyPopper,
    title_en: 'Festivals & Fairs',
    title_hi: 'त्योहार और मेला',
    desc_en: 'Colorful stalls, bright lamps, sweets, and joy.',
    desc_hi: 'रंग-बिरंगा मेला, स्वादिष्ट मिठाइयाँ और रोशनी।',
    accent: 'from-purple-600 to-pink-600',
    border: 'border-purple-200 hover:border-purple-400',
    bg: 'bg-purple-50/50'
  }
];

const defaultStudentName = (language: 'en' | 'hi') => language === 'hi' ? 'आरव' : 'Aarav';

export const ThemeSelectorModal: React.FC<ThemeSelectorModalProps> = ({
  isOpen,
  onClose,
  targetWords,
  gradeLevel,
  language,
  onGenerateStory,
  isGenerating,
}) => {
  const [selectedTheme, setSelectedTheme] = useState('space');
  const [studentName, setStudentName] = useState(defaultStudentName(language));
  const previousLanguage = useRef(language);

  useEffect(() => {
    const previousDefault = defaultStudentName(previousLanguage.current);
    setStudentName((currentName) =>
      currentName === previousDefault ? defaultStudentName(language) : currentName
    );
    previousLanguage.current = language;
  }, [language]);

  if (!isOpen) return null;

  const speakWord = (word: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.lang = language === 'hi' ? 'hi-IN' : 'en-IN';
    utterance.rate = 0.8;
    window.speechSynthesis.speak(utterance);
  };

  const handleSubmit = async () => {
    const name =
        studentName.trim() ||
        (language === 'hi' ? 'विद्यार्थी' : 'Learner');

    console.log('[ThemeSelectorModal] BUTTON CLICKED');
    console.log('[ThemeSelectorModal] theme:', selectedTheme);
    console.log('[ThemeSelectorModal] studentName:', name);

    try {
        await onGenerateStory(selectedTheme, name);
        console.log('[ThemeSelectorModal] onGenerateStory completed');
    } catch (error) {
        console.error('[ThemeSelectorModal] onGenerateStory FAILED:', error);
        throw error;
    }
    };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-100 relative animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={onClose}
          disabled={isGenerating}
          className="absolute top-5 right-5 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="text-center mb-5">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-100 text-indigo-600 mb-2">
            <Sparkles className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">
            {language === 'hi' ? 'आपकी व्यक्तिगत अभ्यास कहानी' : 'Create Your Personalized Practice Story'}
          </h2>
          <p className="text-xs text-slate-600 mt-1 max-w-md mx-auto">
            {language === 'hi'
              ? 'हम आपके चुने हुए विषय में एक मजेदार कहानी तैयार करेंगे, जिसमें ये अभ्यास शब्द शामिल होंगे!'
              : 'We will weave your practice words into an exciting 60–80 word custom mini-story!'}
          </p>
        </div>

        {/* Target Words Pill Strip */}
        <div className="mb-6 p-4 rounded-2xl bg-indigo-50/60 border border-indigo-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-800">
              Priority Practice Words ({targetWords.length}):
            </span>
            <span className="text-[10px] text-indigo-600">Tap to hear pronunciation</span>
          </div>

          <div className="flex flex-wrap gap-2">
            {targetWords.map((tw, idx) => (
              <button
                key={idx}
                onClick={() => speakWord(tw.word)}
                className="px-3 py-1.5 rounded-xl bg-white border border-indigo-200 hover:border-indigo-400 text-indigo-950 font-bold text-xs shadow-sm flex items-center gap-1.5 transition-all active:scale-95"
              >
                <Volume2 className="w-3.5 h-3.5 text-indigo-500" />
                <span>{tw.word}</span>
                <span className="text-[9px] px-1.5 py-0.2 rounded-md bg-indigo-100 text-indigo-700 font-semibold uppercase">
                  {tw.error_type}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Student Name Input */}
        <div className="mb-5">
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
            {language === 'hi' ? 'कहानी के नायक / आपका नाम:' : 'Hero Name / Student Name:'}
          </label>
          <input
            type="text"
            value={studentName}
            onChange={(e) => setStudentName(e.target.value)}
            disabled={isGenerating}
            placeholder={language === 'hi' ? 'आरव' : 'Aarav'}
            className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm font-medium focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        {/* Theme Grid */}
        <div className="mb-6">
          <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
            {language === 'hi' ? 'पसंदीदा विषय चुनें:' : 'Pick Your Story Theme:'}
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {THEMES.map((thm) => {
              const Icon = thm.icon;
              const isSelected = selectedTheme === thm.id;
              return (
                <div
                  key={thm.id}
                  onClick={() => !isGenerating && setSelectedTheme(thm.id)}
                  className={`p-3.5 rounded-2xl border cursor-pointer transition-all flex items-start gap-3 ${thm.bg} ${
                    isSelected
                      ? 'border-indigo-600 ring-2 ring-indigo-500/20 shadow-md'
                      : `${thm.border} hover:shadow-sm opacity-85`
                  } ${isGenerating ? 'pointer-events-none opacity-60' : ''}`}
                >
                  <div
                    className={`w-9 h-9 rounded-xl bg-gradient-to-tr ${thm.accent} text-white flex items-center justify-center flex-shrink-0 shadow-sm`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 text-xs sm:text-sm">
                      {language === 'hi' ? thm.title_hi : thm.title_en}
                    </h4>
                    <p className="text-[11px] text-slate-600 line-clamp-1 mt-0.5">
                      {language === 'hi' ? thm.desc_hi : thm.desc_en}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Action Button */}
        <button
          onClick={handleSubmit}
          disabled={isGenerating}
          className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 text-white font-bold text-sm shadow-lg shadow-indigo-500/25 flex items-center justify-center gap-2 transition-all active:scale-98 disabled:opacity-60"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Generating your personalized 60–80 word story...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5 text-amber-300" />
              <span>
                {language === 'hi'
                  ? 'व्यक्तिगत कहानी तैयार करें और पुनः पढ़ें →'
                  : 'Generate My Custom Story & Begin Retest →'}
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
