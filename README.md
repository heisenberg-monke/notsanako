# Adaptive Reading Coach — MVP

An AI-powered oral reading coach and fluency assessment system for upper-primary students (Grades 3–5) in India, aligned with **NEP 2020** and **NIPUN Bharat** foundational literacy benchmarks.

---

## 🌟 What Has Been Built (Stage 1: Baseline Reading Loop)

This MVP implements the first half of the adaptive oral reading loop:

1. **Grade-Appropriate Passage Selection**: Curated Indian cultural and educational stories across Grades 3, 4, and 5 in both **English** (e.g. Dr. APJ Abdul Kalam, Panchatantra) and **Hindi** (e.g. Devanagari tales).
2. **Kid-Friendly Reading Viewer**: Clear, large typography with word-level click-to-pronounce Text-To-Speech (TTS) to aid young learners.
3. **16kHz Mono Microphone Audio Capture**: Built-in browser audio pipeline utilizing `navigator.mediaDevices.getUserMedia` with strict 16kHz mono audio constraints for speech-to-text engines.
4. **Live Speech-to-Text Feedback**: Integrated browser Web Speech recognition ticker to provide real-time encouragement while the child reads aloud.
5. **Word-Level Sequence Alignment Engine**: Custom dynamic programming sequence alignment (`Needleman-Wunsch` variant) supporting English and Indic Devanagari scripts with NFC normalization.
6. **Detailed Error Classification**:
   - **Correct**: Accurately read words (green highlights).
   - **Substitution**: Mispronounced or replaced words (rose highlights with tooltips showing what was heard vs expected).
   - **Omission**: Skipped words (amber dashed highlights).
   - **Insertion / Repetition**: Extraneous words uttered (violet inline badges).
7. **Oral Reading Fluency Metrics**:
   - **Accuracy (%)**: `(Correct Words / Total Words) * 100`
   - **WCPM (Words Correct Per Minute)**: Industry-standard foundational literacy metric.
   - **Gross WPM & Elapsed Duration**.
8. **Stop / Finish Action & Evaluation Modal**:
   - Celebratory confetti on solid reading attempts.
   - Breakdown of correct vs misread words.
   - Interactive struggled word chips that speak the proper pronunciation upon tap.
   - **Bridge to Stage 2**: Direct action to preview personalized remediation story generation.

---

## 📁 Project Structure

```text
/home/noel/Documents/notsanako/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI endpoints (/api/passages, /api/analyze-reading, etc.)
│   │   ├── passages.py        # Curated English & Hindi reading passages
│   │   ├── alignment.py       # Sequence alignment & oral reading metrics engine
│   │   └── stt_service.py     # Modular Speech-to-Text provider (Groq, OpenAI, Web Speech)
│   ├── requirements.txt
│   ├── .env.example
│   └── run.sh                 # One-click backend startup script
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx     # PWA layout & Google Fonts
│   │   │   ├── page.tsx       # Interactive student reading session
│   │   │   └── globals.css    # Tailwind CSS & animations
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── PassageSelector.tsx
│   │   │   ├── ReadingViewer.tsx
│   │   │   ├── AudioControls.tsx
│   │   │   └── EvaluationModal.tsx
│   │   ├── utils/
│   │   │   └── audio.ts       # 16kHz mono audio recorder & Web Speech service
│   │   └── types/
│   │       └── index.ts       # TypeScript interfaces
│   ├── public/
│   │   └── manifest.json      # PWA Web Manifest
│   ├── package.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   └── run.sh                 # One-click frontend startup script
└── README.md
```

---

## 🚀 How to Run

### Step 1: Start the Backend (FastAPI)

In a terminal window:
```bash
cd /home/noel/Documents/notsanako/backend
chmod +x run.sh
./run.sh
```
*The backend API will be live at `http://localhost:8000` (interactive Swagger docs at `http://localhost:8000/docs`).*

### Step 2: Start the Frontend (Next.js PWA)

In a second terminal window:
```bash
cd /home/noel/Documents/notsanako/frontend
chmod +x run.sh
./run.sh
```
*The web app will open at `http://localhost:3000`.*

---

## ⚙️ Configuration (Optional Cloud Speech-to-Text)

The app works seamlessly out-of-the-box using the browser's native Web Speech API and in-browser audio processing.

If you wish to use ultra-fast cloud Whisper transcription (e.g. for noisy Indian classroom environments), copy `.env.example` in the backend:
```bash
cd /home/noel/Documents/notsanako/backend
cp .env.example .env
```
And add your free [Groq Cloud API key](https://console.groq.com):
```env
GROQ_API_KEY=gsk_your_groq_key_here
```

---

## 🔮 Next Steps (Second Half of the Adaptive Loop)

Now that the baseline evaluation engine is operational:
1. **Linguistic Diagnosis**: Classify Devanagari errors into Matra errors vs. Conjunct (*sanyuktakshar*) errors vs. Dialect shifts.
2. **Remediation Story Generator**: Connect Gemini 1.5 to dynamically write 60-80 word stories focused on the child's identified struggled words.
3. **Retest & Delta Calculation**: Allow the child to read the custom remediation passage and calculate the before/after improvement delta.
4. **End-of-Day Teacher Digest**: Configure daily 4:00 PM email summaries showing students who need help.
