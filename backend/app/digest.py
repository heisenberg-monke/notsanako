"""
Digest computation engine.
- Builds the structured JSON payload for a teacher's daily digest.
- Renders a responsive HTML email from that payload.
- Generates language-model-quality classroom intervention suggestions
  using hard-coded heuristics (no LLM cost for operational reports).
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app import crud, models


# ---------------------------------------------------------------------------
# Intervention suggestion heuristics
# ---------------------------------------------------------------------------

_INTERVENTIONS: Dict[str, str] = {
    "MATRA": (
        "Run a 5-minute 'Matra Matching' warm-up: write pairs like "
        "इ/ई and उ/ऊ on the board and ask students to clap when they hear "
        "the long vowel. Focus on words that appeared in today's sessions."
    ),
    "CONJUNCT": (
        "Conduct a 'Conjunct Letter Hunt': give students a short passage and "
        "ask them to circle all conjunct consonants (संयुक्ताक्षर). "
        "Pair readers to practise sounding out प्र, क्ष, त्र, ज्ञ aloud."
    ),
    "PHONETIC": (
        "Use a minimal-pair drill: read word pairs like त/ट and ख/क "
        "in quick succession. Ask students to repeat and identify the retroflex. "
        "Flashcards with Devanagari symbols work well."
    ),
    "OMISSION": (
        "Practise pointer reading: students use a finger or pencil to track "
        "each word. This reduces omissions caused by eye-skipping. "
        "Try choral reading with the passage displayed on the board."
    ),
    "REPETITION": (
        "Build reading confidence with easier passages first. "
        "Students who repeat words often hesitate at unfamiliar patterns — "
        "identify their stumble words and pre-teach them before the next session."
    ),
    "SUBSTITUTION": (
        "Encourage look-back reading: when a student substitutes a word, "
        "have them re-read the sentence from the beginning. "
        "Focus on context clues before phonics decoding."
    ),
}


def _suggest_interventions(top_error_types: List[str]) -> List[str]:
    seen = []
    for etype in top_error_types:
        hint = _INTERVENTIONS.get(etype)
        if hint and hint not in seen:
            seen.append(hint)
    return seen[:3]  # cap at 3 suggestions


# ---------------------------------------------------------------------------
# Core digest builder
# ---------------------------------------------------------------------------

def build_digest_payload(
    db: Session,
    teacher: models.Teacher,
    digest_date: str,
) -> Dict[str, Any]:
    """
    Build a fully structured digest payload for one teacher covering all their classrooms.
    digest_date: "YYYY-MM-DD" string (IST date of the digest).
    """
    classrooms = crud.get_classrooms(db, teacher.id)

    classroom_summaries = []
    all_error_types: List[str] = []

    for classroom in classrooms:
        # 1. Flag students
        crud.flag_students_needing_attention(db, classroom.id)

        students = crud.get_students(db, classroom.id)
        active_ids = crud.get_active_student_ids_today(db, classroom.id)

        total = len(students)
        active_today = len(active_ids)

        # 2. Build per-student cards (ranked: needs_attention first, then active today, then rest)
        attention_cards = []
        student_cards = []
        wcpm_vals = []
        acc_vals = []

        for student in students:
            metrics = crud.get_student_latest_metrics(db, student.id)
            if metrics["latest_wcpm"]:
                wcpm_vals.append(metrics["latest_wcpm"])
            if metrics["latest_accuracy"]:
                acc_vals.append(metrics["latest_accuracy"])

            card = {
                "student_id": student.id,
                "display_name": student.display_name,
                "roll_number": student.roll_number,
                "active_today": student.id in active_ids,
                "needs_attention": student.needs_attention,
                "attention_reason": student.attention_reason,
                "last_session_date": metrics["last_session_date"],
                "latest_wcpm": metrics["latest_wcpm"],
                "latest_accuracy": metrics["latest_accuracy"],
                "session_count": metrics["session_count"],
                "best_delta": metrics["best_delta"],
                "top_error_types": metrics["top_error_types"],
            }
            all_error_types.extend(metrics["top_error_types"])

            if student.needs_attention:
                attention_cards.append(card)

            student_cards.append(card)

        # Sort: attention → active → others
        student_cards.sort(
            key=lambda c: (not c["needs_attention"], not c["active_today"], c["display_name"])
        )

        # 3. Class-wide error patterns
        error_patterns = crud.get_class_error_patterns(db, classroom.id, days=7)
        for ep in error_patterns:
            ep["example_words"] = crud.get_top_error_words(
                db, classroom.id, ep["error_type"], limit=4
            )

        top_class_errors = [ep["error_type"] for ep in error_patterns[:3]]

        classroom_summaries.append({
            "classroom_id": classroom.id,
            "classroom_name": classroom.name,
            "grade_level": classroom.grade_level,
            "language": classroom.language,
            "total_students": total,
            "active_today": active_today,
            "needs_attention_count": len(attention_cards),
            "avg_wcpm": round(sum(wcpm_vals) / len(wcpm_vals), 1) if wcpm_vals else 0.0,
            "avg_accuracy": round(sum(acc_vals) / len(acc_vals), 1) if acc_vals else 0.0,
            "error_patterns": error_patterns,
            "attention_students": attention_cards,
            "student_cards": student_cards,
            "suggested_interventions": _suggest_interventions(top_class_errors),
        })

    # Global suggestions across all classrooms
    from collections import Counter
    top_global_errors = [t for t, _ in Counter(all_error_types).most_common(3)]

    payload = {
        "teacher_id": teacher.id,
        "teacher_name": teacher.name,
        "teacher_email": teacher.email,
        "digest_date": digest_date,
        "generated_at": datetime.utcnow().isoformat(),
        "total_classrooms": len(classrooms),
        "classroom_summaries": classroom_summaries,
        "global_top_errors": top_global_errors,
        "global_interventions": _suggest_interventions(top_global_errors),
    }

    return payload


# ---------------------------------------------------------------------------
# HTML email renderer
# ---------------------------------------------------------------------------

def render_digest_html(payload: Dict[str, Any]) -> str:
    """
    Render a responsive, WCAG-AA accessible HTML email from the digest payload.
    Uses inline styles for broad email client compatibility.
    """
    date_str = payload.get("digest_date", "Today")
    teacher_name = payload.get("teacher_name", "Teacher")
    classrooms = payload.get("classroom_summaries", [])

    # ── helpers ──
    def badge(text: str, color: str) -> str:
        return (
            f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
            f'background:{color};color:#fff;font-size:11px;font-weight:700;">{text}</span>'
        )

    def section_header(title: str, emoji: str = "") -> str:
        return (
            f'<tr><td style="padding:16px 24px 8px;">'
            f'<h2 style="margin:0;font-size:16px;color:#1e293b;font-weight:700;">'
            f'{emoji} {title}</h2></td></tr>'
        )

    classroom_html = ""
    for cls in classrooms:
        # --- Classroom header card ---
        attention_color = "#ef4444" if cls["needs_attention_count"] > 0 else "#10b981"
        classroom_html += f"""
        <tr><td style="padding:8px 24px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;">
            <tr>
              <td style="padding:16px 20px;">
                <h3 style="margin:0 0 4px;font-size:15px;color:#0f172a;">{cls['classroom_name']}</h3>
                <p style="margin:0;font-size:12px;color:#64748b;">Grade {cls['grade_level']} · {cls['language'].upper()}</p>
              </td>
              <td style="padding:16px 20px;text-align:right;vertical-align:top;">
                <table cellpadding="0" cellspacing="4">
                  <tr>
                    <td style="padding-right:12px;text-align:center;">
                      <div style="font-size:22px;font-weight:800;color:#1d4ed8;">{cls['active_today']}<span style="font-size:13px;color:#64748b;">/{cls['total_students']}</span></div>
                      <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">Active Today</div>
                    </td>
                    <td style="padding-right:12px;text-align:center;">
                      <div style="font-size:22px;font-weight:800;color:#0f172a;">{cls['avg_wcpm']}</div>
                      <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">Avg WCPM</div>
                    </td>
                    <td style="text-align:center;">
                      <div style="font-size:22px;font-weight:800;color:{attention_color};">{cls['needs_attention_count']}</div>
                      <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">Need Attention</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td></tr>
        """

        # --- Attention students ---
        if cls["attention_students"]:
            classroom_html += f"""
            <tr><td style="padding:4px 24px 0;">
              <p style="margin:0;font-size:12px;font-weight:700;color:#b45309;text-transform:uppercase;letter-spacing:.5px;">
                ⚠️ Students Requiring Attention
              </p>
            </td></tr>
            """
            for s in cls["attention_students"]:
                err_badges = " ".join(badge(e, "#7c3aed") for e in s.get("top_error_types", []))
                classroom_html += f"""
                <tr><td style="padding:4px 24px;">
                  <table width="100%" cellpadding="0" cellspacing="0"
                    style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;margin-bottom:4px;">
                    <tr>
                      <td style="padding:12px 16px;">
                        <strong style="font-size:13px;color:#0f172a;">{s['display_name']}</strong>
                        {'<span style="margin-left:8px;font-size:10px;color:#64748b;">' + (s['roll_number'] or '') + '</span>' if s.get('roll_number') else ''}
                        <br/>
                        <span style="font-size:11px;color:#92400e;">{s.get('attention_reason','')}</span>
                        <br/><span style="font-size:11px;color:#64748b;">
                          WCPM: <strong>{s['latest_wcpm'] or '—'}</strong> &nbsp;|&nbsp;
                          Accuracy: <strong>{f"{s['latest_accuracy']:.0f}%" if s.get('latest_accuracy') else '—'}</strong> &nbsp;|&nbsp;
                          Sessions: <strong>{s['session_count']}</strong>
                        </span>
                        <br/><span style="margin-top:4px;display:inline-block;">{err_badges}</span>
                      </td>
                    </tr>
                  </table>
                </td></tr>
                """

        # --- Error pattern bar ---
        if cls["error_patterns"]:
            classroom_html += f"""
            <tr><td style="padding:12px 24px 0;">
              <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:#1e293b;text-transform:uppercase;letter-spacing:.5px;">
                📊 7-Day Class Error Patterns
              </p>
            """
            bar_colors = {"MATRA": "#8b5cf6", "CONJUNCT": "#f59e0b", "PHONETIC": "#ef4444",
                          "OMISSION": "#3b82f6", "REPETITION": "#10b981", "SUBSTITUTION": "#f97316"}
            for ep in cls["error_patterns"]:
                color = bar_colors.get(ep["error_type"], "#64748b")
                words_str = ", ".join(ep.get("example_words", []))
                classroom_html += f"""
                <tr><td style="padding:2px 24px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="width:90px;font-size:11px;font-weight:600;color:#374151;">{ep['error_type']}</td>
                      <td>
                        <div style="background:#e2e8f0;border-radius:4px;overflow:hidden;height:8px;">
                          <div style="background:{color};width:{min(ep['percentage'],100)}%;height:8px;border-radius:4px;"></div>
                        </div>
                      </td>
                      <td style="width:40px;text-align:right;font-size:11px;color:#374151;padding-left:8px;">{ep['percentage']}%</td>
                    </tr>
                    {'<tr><td colspan="3" style="font-size:10px;color:#64748b;padding-bottom:2px;">e.g. ' + words_str + '</td></tr>' if words_str else ''}
                  </table>
                </td></tr>
                """

        # --- Interventions ---
        if cls["suggested_interventions"]:
            classroom_html += f"""
            <tr><td style="padding:12px 24px 0;">
              <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:#1e293b;text-transform:uppercase;letter-spacing:.5px;">
                💡 Suggested Classroom Interventions
              </p>
            </td></tr>
            """
            for i, hint in enumerate(cls["suggested_interventions"], 1):
                classroom_html += f"""
                <tr><td style="padding:2px 24px 4px;">
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="vertical-align:top;padding-right:8px;font-size:14px;">✦</td>
                      <td style="font-size:12px;color:#374151;line-height:1.5;">{hint}</td>
                    </tr>
                  </table>
                </td></tr>
                """

        classroom_html += '<tr><td style="padding:8px 24px;"><hr style="border:none;border-top:1px solid #e2e8f0;margin:0;"/></td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Reading Coach Digest — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1d4ed8,#4f46e5);padding:28px 24px 20px;">
            <h1 style="margin:0;font-size:20px;font-weight:800;color:#fff;">
              📚 Reading Coach — Daily Digest
            </h1>
            <p style="margin:6px 0 0;font-size:13px;color:#bfdbfe;">
              {date_str} &nbsp;·&nbsp; {teacher_name} &nbsp;·&nbsp; {payload.get('total_classrooms', 0)} classroom(s)
            </p>
          </td>
        </tr>

        <!-- Classroom sections -->
        {classroom_html}

        <!-- Footer -->
        <tr>
          <td style="padding:20px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;">
            <p style="margin:0;font-size:11px;color:#94a3b8;text-align:center;">
              This digest is auto-generated by Adaptive Reading Coach.<br/>
              No audio data is retained. Student data is processed under DPDP Act 2023 consent.<br/>
              View full dashboard → <a href="#" style="color:#4f46e5;">reading-coach.app/teacher</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return html
