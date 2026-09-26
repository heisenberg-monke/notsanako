'use client';

import React from 'react';
import { Passage } from '@/types';
import { BookMarked, Clock, Gauge, Globe2, Sparkles } from 'lucide-react';

interface PassageSelectorProps {
  passages: Passage[];
  selectedPassage: Passage | null;
  onSelectPassage: (passage: Passage) => void;
  selectedLanguage: 'en' | 'hi';
  onLanguageChange: (lang: 'en' | 'hi') => void;
  selectedGrade: number;
  onGradeChange: (grade: number) => void;
  disabled?: boolean;
}

export const PassageSelector: React.FC<PassageSelectorProps> = ({
  passages,
  selectedPassage,
  onSelectPassage,
  selectedLanguage,
  onLanguageChange,
  selectedGrade,
  onGradeChange,
  disabled = false,
}) => {
  // Filter passages based on selection
  const filteredPassages = passages.filter((p) => {
    const matchLang = p.language === selectedLanguage;
    const matchGrade = selectedGrade === 0 || p.grade_level === selectedGrade;
    return matchLang && matchGrade;
  });

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5 pb-4 border-b border-slate-100">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <BookMarked className="w-5 h-5 text-blue-600" />
            Step 1: Choose Your Reading Passage
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Select a story to practice reading aloud. We will listen and coach you!
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Language Switch */}
          <div className="inline-flex rounded-xl p-1 bg-slate-100 border border-slate-200">
            <button
              onClick={() => onLanguageChange('en')}
              disabled={disabled}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedLanguage === 'en'
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              English
            </button>
            <button
              onClick={() => onLanguageChange('hi')}
              disabled={disabled}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedLanguage === 'hi'
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              हिन्दी (Hindi)
            </button>
          </div>

          {/* Grade Selector */}
          <div className="inline-flex rounded-xl p-1 bg-slate-100 border border-slate-200">
            {[3, 4, 5].map((g) => (
              <button
                key={g}
                onClick={() => onGradeChange(g)}
                disabled={disabled}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  selectedGrade === g
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Grade {g}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Passage Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {filteredPassages.map((passage) => {
          const isSelected = selectedPassage?.id === passage.id;
          const wordCount = passage.text.split(/\s+/).length;

          return (
            <div
              key={passage.id}
              onClick={() => !disabled && onSelectPassage(passage)}
              className={`group relative rounded-xl p-4 border transition-all cursor-pointer text-left ${
                isSelected
                  ? 'border-blue-600 bg-blue-50/40 ring-2 ring-blue-500/20 shadow-sm'
                  : 'border-slate-200 bg-white hover:border-blue-300 hover:shadow-md'
              } ${disabled ? 'opacity-60 pointer-events-none' : ''}`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <span
                  className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                    passage.difficulty === 'Easy'
                      ? 'bg-emerald-100 text-emerald-800'
                      : passage.difficulty === 'Medium'
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-purple-100 text-purple-800'
                  }`}
                >
                  {passage.difficulty}
                </span>

                <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                  <Gauge className="w-3.5 h-3.5 text-blue-500" />
                  Target: {passage.target_wcpm} WCPM
                </span>
              </div>

              <h3 className="font-bold text-slate-800 text-base group-hover:text-blue-600 transition-colors line-clamp-1 mb-1">
                {passage.title}
              </h3>

              <p className="text-xs text-slate-600 line-clamp-2 mb-3">
                {passage.description}
              </p>

              <div className="flex items-center justify-between text-[11px] font-medium text-slate-400 pt-2 border-t border-slate-100">
                <span className="flex items-center gap-1">
                  <BookMarked className="w-3 h-3 text-slate-400" />
                  {wordCount} words
                </span>
                <span className="text-blue-600 font-semibold group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5">
                  {isSelected ? 'Selected ✓' : 'Select Story →'}
                </span>
              </div>
            </div>
          );
        })}

        {filteredPassages.length === 0 && (
          <div className="col-span-full py-8 text-center text-slate-400 text-sm">
            No passages found for the selected grade and language.
          </div>
        )}
      </div>
    </div>
  );
};
