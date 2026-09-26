'use client';

import React from 'react';
import { BookOpen, Sparkles, Volume2 } from 'lucide-react';

interface HeaderProps {
  selectedGrade?: number;
  language?: 'en' | 'hi';
}

export const Header: React.FC<HeaderProps> = ({ selectedGrade = 4, language = 'en' }) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3.5 flex flex-wrap items-center justify-between gap-3">
        {/* Logo and Title */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-800 tracking-tight">
                Adaptive Reading Coach
              </h1>
              <span className="hidden sm:inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium border border-blue-200">
                <Sparkles className="w-3 h-3 text-blue-500" />
                NEP 2020 Aligned
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">
              {language === 'hi' 
                ? 'प्राथमिक स्तर वाचन साथी • चरण 1: वाचन मूल्यांकन' 
                : 'Upper Primary Reading Companion • Stage 1: Baseline Assessment'}
            </p>
          </div>
        </div>

        {/* Grade and Mode Status */}
        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-semibold flex items-center gap-1.5">
            <span>Grade {selectedGrade}</span>
            <span className="text-slate-300">•</span>
            <span>{language === 'hi' ? 'हिन्दी' : 'English'}</span>
          </div>
          <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200">
            <Volume2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>16kHz Mono Ready</span>
          </div>
        </div>
      </div>
    </header>
  );
};
