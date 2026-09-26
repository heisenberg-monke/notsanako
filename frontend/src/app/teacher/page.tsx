'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, BookOpen, TrendingUp, AlertTriangle, CheckCircle2,
  RefreshCw, Plus, ChevronDown, ChevronRight, Mail, Clock,
  BarChart3, Lightbulb, UserCheck, Activity, ArrowUpRight,
  Zap, Eye, X, School
} from 'lucide-react';
import type {
  Teacher, Classroom, StudentWithStats, ClassDashboard,
  ErrorPatternSummary, StudentAttentionCard, PracticeSession
} from '@/types/teacher';

// ─── helpers ────────────────────────────────────────────────────────────────
const API = '/api'; // proxied by Next.js to :8000

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

const ERROR_COLORS: Record<string, string> = {
  MATRA: 'bg-purple-100 text-purple-800 border-purple-200',
  CONJUNCT: 'bg-amber-100 text-amber-800 border-amber-200',
  PHONETIC: 'bg-rose-100 text-rose-800 border-rose-200',
  OMISSION: 'bg-blue-100 text-blue-800 border-blue-200',
  REPETITION: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  SUBSTITUTION: 'bg-orange-100 text-orange-800 border-orange-200',
};

const ERROR_BAR_COLORS: Record<string, string> = {
  MATRA: '#8b5cf6', CONJUNCT: '#f59e0b', PHONETIC: '#ef4444',
  OMISSION: '#3b82f6', REPETITION: '#10b981', SUBSTITUTION: '#f97316',
};

function ErrorBadge({ type }: { type: string }) {
  const cls = ERROR_COLORS[type] || 'bg-slate-100 text-slate-700 border-slate-200';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold border ${cls}`}>
      {type}
    </span>
  );
}

function MetricCard({
  label, value, sub, icon: Icon, color = 'text-blue-600',
}: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; color?: string;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex items-center gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-slate-50 ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-xl font-black text-slate-900">{value}</div>
        <div className="text-xs font-semibold text-slate-500">{label}</div>
        {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
      </div>
    </div>
  );
}

// ─── Student Card ────────────────────────────────────────────────────────────
function StudentCard({
  student, onViewSessions,
}: {
  student: StudentWithStats;
  onViewSessions: (s: StudentWithStats) => void;
}) {
  return (
    <div
      className={`rounded-2xl border p-4 transition-shadow hover:shadow-md ${
        student.needs_attention
          ? 'border-amber-300 bg-amber-50'
          : 'border-slate-200 bg-white'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-slate-900 text-sm">{student.display_name}</span>
            {student.roll_number && (
              <span className="text-[10px] text-slate-400 font-mono">#{student.roll_number}</span>
            )}
            {student.needs_attention && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-200 text-amber-800">
                <AlertTriangle className="w-3 h-3" /> Needs Attention
              </span>
            )}
          </div>
          {student.attention_reason && (
            <p className="text-[11px] text-amber-700 mt-1 leading-snug">{student.attention_reason}</p>
          )}
        </div>
        <button
          onClick={() => onViewSessions(student)}
          className="flex-shrink-0 p-1.5 rounded-xl hover:bg-slate-100 text-slate-500 transition-colors"
          title="View sessions"
        >
          <Eye className="w-4 h-4" />
        </button>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-base font-black text-slate-800">
            {student.latest_wcpm?.toFixed(0) ?? '—'}
          </div>
          <div className="text-[10px] text-slate-500">WCPM</div>
        </div>
        <div>
          <div className="text-base font-black text-slate-800">
            {student.latest_accuracy != null ? `${student.latest_accuracy.toFixed(0)}%` : '—'}
          </div>
          <div className="text-[10px] text-slate-500">Accuracy</div>
        </div>
        <div>
          <div className={`text-base font-black ${
            (student.best_delta ?? 0) > 0 ? 'text-emerald-600' : 'text-slate-400'
          }`}>
            {student.best_delta != null ? `+${student.best_delta.toFixed(0)}%` : '—'}
          </div>
          <div className="text-[10px] text-slate-500">Best Δ</div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-1">
        {student.top_error_types.map((t) => <ErrorBadge key={t} type={t} />)}
      </div>

      <div className="mt-2 text-[10px] text-slate-400">
        {student.session_count} session{student.session_count !== 1 ? 's' : ''}
        {student.last_session_date && ` · Last: ${student.last_session_date}`}
      </div>
    </div>
  );
}

// ─── Error Pattern Bar ───────────────────────────────────────────────────────
function ErrorPatternBar({ patterns }: { patterns: ErrorPatternSummary[] }) {
  return (
    <div className="space-y-2.5">
      {patterns.map((p) => (
        <div key={p.error_type}>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="font-semibold text-slate-700">{p.error_type}</span>
            <span className="text-slate-500">{p.percentage}% ({p.count})</span>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(p.percentage, 100)}%`,
                background: ERROR_BAR_COLORS[p.error_type] || '#64748b',
              }}
            />
          </div>
          {p.example_words.length > 0 && (
            <div className="text-[10px] text-slate-400 mt-0.5">
              e.g. {p.example_words.join(', ')}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Session Drawer ──────────────────────────────────────────────────────────
function SessionDrawer({
  student, teacherId, onClose,
}: {
  student: StudentWithStats; teacherId: string; onClose: () => void;
}) {
  const [sessions, setSessions] = useState<PracticeSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<PracticeSession[]>(`/teacher/${teacherId}/students/${student.id}/sessions`)
      .then(setSessions)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [student.id, teacherId]);

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white w-full sm:max-w-lg rounded-t-3xl sm:rounded-3xl shadow-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div>
            <h2 className="font-black text-slate-900">{student.display_name}</h2>
            <p className="text-xs text-slate-500">{sessions.length} session(s) on record</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100"><X className="w-4 h-4" /></button>
        </div>
        <div className="overflow-y-auto flex-1 p-5 space-y-3">
          {loading && <div className="text-center text-sm text-slate-400 py-8">Loading sessions…</div>}
          {!loading && sessions.length === 0 && (
            <div className="text-center text-sm text-slate-400 py-8">No sessions recorded yet.</div>
          )}
          {sessions.map((s) => (
            <div key={s.id} className="p-3.5 rounded-2xl border border-slate-200 bg-slate-50">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-800">
                  {new Date(s.started_at).toLocaleDateString('en-IN', {
                    day: 'numeric', month: 'short', year: 'numeric',
                  })}
                </span>
                {s.completed_retest && (
                  <span className="flex items-center gap-1 text-emerald-600 font-semibold">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Full Loop
                  </span>
                )}
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="font-black text-slate-900">{s.avg_wcpm.toFixed(0)}</div>
                  <div className="text-[10px] text-slate-500">WCPM</div>
                </div>
                <div>
                  <div className="font-black text-slate-900">{s.total_words_read}</div>
                  <div className="text-[10px] text-slate-500">Words</div>
                </div>
                <div>
                  <div className={`font-black ${
                    (s.delta_summary as any)?.delta > 0 ? 'text-emerald-600' : 'text-slate-400'
                  }`}>
                    {(s.delta_summary as any)?.delta != null
                      ? `+${Number((s.delta_summary as any).delta).toFixed(0)}%`
                      : '—'}
                  </div>
                  <div className="text-[10px] text-slate-500">Delta Δ</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Classroom Panel ──────────────────────────────────────────────────────────
function ClassroomPanel({
  classroom, teacherId,
}: {
  classroom: Classroom; teacherId: string;
}) {
  const [dashboard, setDashboard] = useState<ClassDashboard | null>(null);
  const [students, setStudents] = useState<StudentWithStats[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<StudentWithStats | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, studs] = await Promise.all([
        apiFetch<ClassDashboard>(
          `/teacher/${teacherId}/classrooms/${classroom.id}/dashboard`
        ),
        apiFetch<StudentWithStats[]>(
          `/teacher/${teacherId}/classrooms/${classroom.id}/students`
        ),
      ]);
      setDashboard(dash);
      setStudents(studs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [classroom.id, teacherId]);

  const toggle = () => {
    if (!expanded && !dashboard) load();
    setExpanded((v) => !v);
  };

  return (
    <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Classroom header */}
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between p-5 hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-black text-slate-900">{classroom.name}</h3>
            <p className="text-xs text-slate-500">
              Grade {classroom.grade_level} · {classroom.language.toUpperCase()} · {classroom.student_count} students
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {dashboard && (
            <span className={`text-xs font-bold px-2 py-1 rounded-full ${
              dashboard.needs_attention_count > 0
                ? 'bg-amber-100 text-amber-700'
                : 'bg-emerald-100 text-emerald-700'
            }`}>
              {dashboard.needs_attention_count > 0
                ? `⚠️ ${dashboard.needs_attention_count} need attention`
                : '✅ All on track'}
            </span>
          )}
          {expanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 p-5 space-y-6">
          {loading && (
            <div className="text-center py-8 text-sm text-slate-400">Loading dashboard…</div>
          )}

          {dashboard && !loading && (
            <>
              {/* Metrics row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricCard label="Active Today" value={`${dashboard.active_today}/${dashboard.total_students}`} icon={Activity} color="text-blue-600" />
                <MetricCard label="Avg WCPM" value={dashboard.avg_wcpm} icon={TrendingUp} color="text-indigo-600" />
                <MetricCard label="Avg Accuracy" value={`${dashboard.avg_accuracy}%`} icon={BarChart3} color="text-violet-600" />
                <MetricCard label="Need Attention" value={dashboard.needs_attention_count} icon={AlertTriangle} color={dashboard.needs_attention_count > 0 ? 'text-amber-600' : 'text-emerald-600'} />
              </div>

              {/* Attention students */}
              {dashboard.attention_students.length > 0 && (
                <div>
                  <h4 className="text-xs font-black uppercase tracking-wider text-amber-700 mb-3 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" /> Students Requiring Attention
                  </h4>
                  <div className="space-y-2">
                    {dashboard.attention_students.map((s) => (
                      <div key={s.student_id} className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <span className="font-bold text-slate-900 text-sm">{s.display_name}</span>
                            <p className="text-[11px] text-amber-700 mt-0.5 leading-snug">{s.reason}</p>
                          </div>
                          <div className="text-right flex-shrink-0">
                            <div className="text-sm font-black text-slate-800">{s.latest_wcpm?.toFixed(0) ?? '—'}</div>
                            <div className="text-[10px] text-slate-500">WCPM</div>
                          </div>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {s.top_errors.map((t) => <ErrorBadge key={t} type={t} />)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error patterns */}
              {dashboard.error_patterns.length > 0 && (
                <div>
                  <h4 className="text-xs font-black uppercase tracking-wider text-slate-600 mb-3 flex items-center gap-1.5">
                    <BarChart3 className="w-3.5 h-3.5" /> 7-Day Error Patterns
                  </h4>
                  <ErrorPatternBar patterns={dashboard.error_patterns} />
                </div>
              )}

              {/* Interventions */}
              {dashboard.suggested_interventions.length > 0 && (
                <div>
                  <h4 className="text-xs font-black uppercase tracking-wider text-slate-600 mb-3 flex items-center gap-1.5">
                    <Lightbulb className="w-3.5 h-3.5" /> Suggested Interventions
                  </h4>
                  <div className="space-y-2">
                    {dashboard.suggested_interventions.map((hint, i) => (
                      <div key={i} className="flex gap-2.5 p-3 rounded-xl bg-blue-50 border border-blue-100">
                        <Zap className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                        <p className="text-xs text-slate-700 leading-relaxed">{hint}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Student roster */}
          {students.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-black uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5" /> Student Roster
                </h4>
                <button
                  onClick={load}
                  className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400"
                  title="Refresh"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {students.map((s) => (
                  <StudentCard key={s.id} student={s} onViewSessions={setSelectedStudent} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {selectedStudent && (
        <SessionDrawer
          student={selectedStudent}
          teacherId={teacherId}
          onClose={() => setSelectedStudent(null)}
        />
      )}
    </div>
  );
}

// ─── Add Classroom Modal ──────────────────────────────────────────────────────
function AddClassroomModal({
  teacherId, onCreated, onClose,
}: {
  teacherId: string;
  onCreated: (c: Classroom) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState({ name: '', grade_level: 4, language: 'hi' });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErr('');
    try {
      const cls = await apiFetch<Classroom>(`/teacher/${teacherId}/classrooms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      onCreated(cls);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-black text-slate-900">New Classroom</h2>
          <button onClick={onClose} className="p-1.5 rounded-xl hover:bg-slate-100"><X className="w-4 h-4" /></button>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1">Classroom Name</label>
            <input
              className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="e.g. Grade 4-A"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-600 block mb-1">Grade</label>
              <select
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                value={form.grade_level}
                onChange={(e) => setForm({ ...form, grade_level: Number(e.target.value) })}
              >
                {[1,2,3,4,5,6,7,8].map(g => <option key={g} value={g}>Grade {g}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600 block mb-1">Language</label>
              <select
                className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              >
                <option value="hi">Hindi</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>
          {err && <p className="text-xs text-rose-600">{err}</p>}
          <button
            type="submit"
            disabled={saving}
            className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm disabled:opacity-50 transition-colors"
          >
            {saving ? 'Creating…' : 'Create Classroom'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── Teacher Registration ────────────────────────────────────────────────────
function TeacherRegistration({
  onRegistered,
}: {
  onRegistered: (t: Teacher) => void;
}) {
  const [form, setForm] = useState({ email: '', name: '', school_name: '', digest_time: '16:00' });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr('');
    try {
      const teacher = await apiFetch<Teacher>('/teacher/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      localStorage.setItem('teacher_id', teacher.id);
      onRegistered(teacher);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <School className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-black text-slate-900">Teacher Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Adaptive Reading Coach — Teacher Portal</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1">Full Name</label>
            <input className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="Ms. Sunita Sharma" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1">School Email</label>
            <input type="email" className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="teacher@school.edu.in" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1">School Name (optional)</label>
            <input className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="Kendriya Vidyalaya, Pune" value={form.school_name}
              onChange={(e) => setForm({ ...form, school_name: e.target.value })} />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1">Daily Digest Time</label>
            <input type="time" className="w-full px-4 py-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.digest_time}
              onChange={(e) => setForm({ ...form, digest_time: e.target.value })} />
            <p className="text-[10px] text-slate-400 mt-1">You'll receive an email digest at this time every day (IST).</p>
          </div>
          {err && <p className="text-xs text-rose-600 bg-rose-50 p-3 rounded-xl">{err}</p>}
          <button type="submit" disabled={loading}
            className="w-full py-3.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-black text-sm disabled:opacity-50 transition-colors">
            {loading ? 'Setting up…' : 'Enter Dashboard →'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── Main Teacher Dashboard Page ─────────────────────────────────────────────
export default function TeacherDashboard() {
  const [teacher, setTeacher] = useState<Teacher | null>(null);
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [loadingClassrooms, setLoadingClassrooms] = useState(false);
  const [showAddClassroom, setShowAddClassroom] = useState(false);
  const [triggeringDigest, setTriggeringDigest] = useState(false);
  const [digestMsg, setDigestMsg] = useState('');
  const [globalError, setGlobalError] = useState('');

  // Restore teacher from localStorage on mount
  useEffect(() => {
    const savedId = localStorage.getItem('teacher_id');
    if (savedId) {
      apiFetch<Teacher>(`/teacher/${savedId}`)
        .then(setTeacher)
        .catch(() => localStorage.removeItem('teacher_id'));
    }
  }, []);

  const loadClassrooms = useCallback(async (t: Teacher) => {
    setLoadingClassrooms(true);
    try {
      const cls = await apiFetch<Classroom[]>(`/teacher/${t.id}/classrooms`);
      setClassrooms(cls);
    } catch (e: any) {
      setGlobalError(e.message);
    } finally {
      setLoadingClassrooms(false);
    }
  }, []);

  useEffect(() => {
    if (teacher) loadClassrooms(teacher);
  }, [teacher, loadClassrooms]);

  const handleTriggerDigest = async () => {
    if (!teacher) return;
    setTriggeringDigest(true);
    setDigestMsg('');
    try {
      const res = await apiFetch<{ status: string; digest_date: string; email_sent: boolean }>(
        `/teacher/${teacher.id}/digest/trigger`,
        { method: 'POST' }
      );
      setDigestMsg(
        res.email_sent
          ? `✅ Digest for ${res.digest_date} sent to ${teacher.email}.`
          : `📋 Digest for ${res.digest_date} generated. Email skipped (RESEND_API_KEY not set in backend/.env).`
      );
    } catch (e: any) {
      setDigestMsg(`❌ ${e.message}`);
    } finally {
      setTriggeringDigest(false);
    }
  };

  if (!teacher) {
    return <TeacherRegistration onRegistered={(t) => setTeacher(t)} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Top Bar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-xl flex items-center justify-center">
              <School className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="font-black text-slate-900 text-sm">Teacher Dashboard</h1>
              <p className="text-[10px] text-slate-500">{teacher.name} · {teacher.school_name || teacher.email}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden sm:flex items-center gap-1 text-[10px] text-slate-500">
              <Clock className="w-3 h-3" />
              <span>Digest: {teacher.digest_time} IST</span>
            </div>
            <button
              onClick={handleTriggerDigest}
              disabled={triggeringDigest}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs transition-colors disabled:opacity-50"
            >
              <Mail className="w-3.5 h-3.5" />
              {triggeringDigest ? 'Sending…' : 'Send Digest Now'}
            </button>
            <a
              href="/"
              className="text-xs font-bold text-blue-600 hover:text-blue-700 px-2.5 py-1.5 rounded-xl border border-blue-200 bg-blue-50/50"
            >
              ← Student Reading Coach
            </a>
            <button
              onClick={() => { localStorage.removeItem('teacher_id'); setTeacher(null); }}
              className="text-[10px] text-slate-400 hover:text-slate-600 px-2 py-1 rounded-lg"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Digest message */}
        {digestMsg && (
          <div className={`p-4 rounded-2xl text-sm font-semibold flex items-start gap-2 ${
            digestMsg.startsWith('✅') ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
            : digestMsg.startsWith('📋') ? 'bg-blue-50 border border-blue-200 text-blue-800'
            : 'bg-rose-50 border border-rose-200 text-rose-800'
          }`}>
            <span className="flex-1">{digestMsg}</span>
            <button onClick={() => setDigestMsg('')}><X className="w-4 h-4" /></button>
          </div>
        )}

        {/* Global error */}
        {globalError && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm">
            {globalError}
          </div>
        )}

        {/* Classrooms header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-black text-slate-900 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-600" />
            My Classrooms
            {!loadingClassrooms && (
              <span className="text-xs font-semibold text-slate-400">({classrooms.length})</span>
            )}
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => teacher && loadClassrooms(teacher)}
              className="p-2 rounded-xl hover:bg-slate-100 text-slate-500"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowAddClassroom(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Classroom
            </button>
          </div>
        </div>

        {/* Classrooms list */}
        {loadingClassrooms && (
          <div className="text-center py-12 text-slate-400 text-sm">Loading classrooms…</div>
        )}

        {!loadingClassrooms && classrooms.length === 0 && (
          <div className="text-center py-12 bg-white rounded-3xl border border-slate-200">
            <BookOpen className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="font-semibold text-slate-500">No classrooms yet.</p>
            <p className="text-xs text-slate-400 mt-1">Click "Add Classroom" to create your first class.</p>
          </div>
        )}

        <div className="space-y-4">
          {classrooms.map((cls) => (
            <ClassroomPanel key={cls.id} classroom={cls} teacherId={teacher.id} />
          ))}
        </div>
      </main>

      {/* Add Classroom Modal */}
      {showAddClassroom && (
        <AddClassroomModal
          teacherId={teacher.id}
          onCreated={(cls) => {
            setClassrooms((prev) => [cls, ...prev]);
            setShowAddClassroom(false);
          }}
          onClose={() => setShowAddClassroom(false)}
        />
      )}
    </div>
  );
}
