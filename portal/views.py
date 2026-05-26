from django.shortcuts import render

# Create your views here.

# results/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from django.http import HttpResponse

from .models import Student, Result, TermSummary
# from .utils import logged_in_student   # adjust import path to match your project


# ── Grade / remark helpers ────────────────────────────────────────────────────

def get_grade(score):
    if score >= 70: return 'A'
    if score >= 60: return 'B'
    if score >= 50: return 'C'
    if score >= 45: return 'D'
    if score >= 40: return 'E'
    return 'F'

def get_remark(grade):
    return {
        'A': 'Excellent',
        'B': 'Very Good',
        'C': 'Good',
        'D': 'Fair',
        'E': 'Poor',
        'F': 'Fail',
    }.get(grade, '')

def get_remark_class(grade):
    return {
        'A': 'remark-excellent',
        'B': 'remark-good',
        'C': 'remark-average',
        'D': 'remark-below',
        'E': 'remark-poor',
        'F': 'remark-fail',
    }.get(grade, '')

def get_bar_color(total):
    if total >= 70:
        return 'linear-gradient(180deg,#1e7a44,rgba(30,122,68,0.5))'
    if total >= 60:
        return 'linear-gradient(180deg,#1e4fa3,rgba(30,79,163,0.5))'
    if total >= 50:
        return 'linear-gradient(180deg,#b8860b,rgba(184,134,11,0.5))'
    if total >= 45:
        return 'linear-gradient(180deg,#e65100,rgba(230,81,0,0.5))'
    if total >= 40:
        return 'linear-gradient(180deg,#9b59b6,rgba(155,89,182,0.5))'
    return 'linear-gradient(180deg,#c0392b,rgba(192,57,43,0.5))'


def logged_in_student(request):
    sid = request.session.get('student_id')
    if not sid:
        return None
    try:
        return Student.objects.get(pk=sid)
    except Student.DoesNotExist:
        return None

def get_logged_in_student(request):
    student_id = request.session.get('student_id')
    if not student_id:
        return None
    try:
        return Student.objects.get(student_id=student_id)
    except Student.DoesNotExist:
        return None


# ── Row builder ───────────────────────────────────────────────────────────────

def resolve_subject(subject_field):
    """
    Safely extract (name, icon, category) from a subject field that may be
    either a Subject model instance or a plain string (when the FK resolved
    to its __str__ representation, or when subject is stored as a CharField).
    """
    if isinstance(subject_field, str):
        # Subject came through as a string — use it as the name directly.
        return subject_field, '📚', 'other'
    # Normal FK object path
    name     = getattr(subject_field, 'name',     str(subject_field))
    icon     = getattr(subject_field, 'icon',     '📚')
    category = getattr(subject_field, 'category', 'other') or 'other'
    return name, icon, category


def build_rows(results):
    """
    Convert a queryset of Result objects into dicts the template needs.
    Result fields used: .subject (FK or str), .ca1, .ca2, .exam_score, .total
    """
    rows = []
    for r in results:
        subject_name, subject_icon, category = resolve_subject(r.subject)
        ca_combined = r.ca1 + r.ca2
        total       = r.total
        grade       = get_grade(total)
        rows.append({
            # Flat subject fields — no attribute access needed in template or Python
            'subject_name': subject_name,
            'subject_icon': subject_icon,
            'category':     category,
            'ca':           ca_combined,
            'ca1':          r.ca1,
            'ca2':          r.ca2,
            'exam_score':   r.exam_score,
            'total':        total,
            'grade':        grade,
            'remark':       get_remark(grade),
            'remark_class': get_remark_class(grade),
            'bar_color':    get_bar_color(total),
        })
    return rows


# ── Attendance dot builder ────────────────────────────────────────────────────

# def build_attendance_dots(summary):
#     """
#     Build the list of attendance dot types for the calendar strip.

#     TermSummary stores days_present, days_absent, days_late, total_days.
#     We reconstruct an ordered sequence: all present dots first, then absent,
#     then late — interspersed with a 'holiday' dot every 5th position so the
#     visual rhythm matches the original design.

#     If those granular fields don't exist yet, we fall back to a simple
#     percentage-based approximation so the calendar always renders.
#     """
#     if summary is None:
#         return []

#     total_days  = getattr(summary, 'total_days',   None)
#     days_present= getattr(summary, 'days_present', None)
#     days_absent = getattr(summary, 'days_absent',  None)
#     days_late   = getattr(summary, 'days_late',    None)

#     # ── Fallback: derive from attendance percentage ───────────────────────────
#     if total_days is None:
#         # Approximate: treat attendance % as out of 62 school days (a common
#         # Nigerian first-term length).  Adjust the constant for your school.
#         SCHOOL_DAYS = 62
#         pct          = summary.attendance if summary.attendance else 0
#         days_present = round(pct / 100 * SCHOOL_DAYS)
#         days_absent  = max(0, SCHOOL_DAYS - days_present)
#         days_late    = 0
#         total_days   = SCHOOL_DAYS

#     # ── Build raw sequence (no holidays yet) ─────────────────────────────────
#     raw = (
#         ['present'] * int(days_present) +
#         ['absent']  * int(days_absent)  +
#         ['late']    * int(days_late)
#     )

#     # ── Intersperse a 'holiday' every Saturday (every 5th working day) ───────
#     dots = []
#     working_day = 0
#     for status in raw:
#         working_day += 1
#         dots.append(status)
#         if working_day % 5 == 0:          # end of each school week
#             dots.append('holiday')

#     return dots

# ── views ─────────────────────────────────────────────────────────────────────

def build_attendance_dots(days_present, days_absent):
    """
    Builds the dot list directly from days_present and days_absent integers.
    Inserts a 'holiday' dot after every 5 working days (end of school week).
    """
    if not days_present and not days_absent:
        return []
    raw  = ['present'] * days_present + ['absent'] * days_absent
    dots = []
    for i, status in enumerate(raw, start=1):
        dots.append(status)
        if i % 5 == 0:
            dots.append('holiday')
    return dots


def login_view(request):
    # if logged_in_student(request):
    #     return redirect('dashboard')

    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip().upper()
        pin        = request.POST.get('pin', '').strip()
        try:
            student = Student.objects.get(student_id=student_id, pin=pin)
            request.session['student_id'] = student.pk
            return redirect('dashboard')
        except Student.DoesNotExist:
            return render(request, 'portal/login3.html',
                          {'error': 'Invalid Student ID or PIN.'})

    return render(request, 'portal/login3.html')


def logout_view(request):
    request.session.flush()
    return redirect('login')



# def dashboard_view(request):
    # student = logged_in_student(request)
    # if not student:
    #     return redirect('login')

    # terms      = ['first', 'second', 'third']
    # term_cards = []

    # for term in terms:
    #     results = Result.objects.filter(
    #         student=student, term=term
    #     ).select_related('subject').order_by('subject__name')

    #     if not results.exists():
    #         continue

    #     rows   = build_rows(results)
    #     totals = [r['total'] for r in rows]
    #     avg    = round(sum(totals) / len(totals), 1) if totals else 0

    #     # ── Highest-scoring subject ───────────────────────────────────────────
    #     best_row = max(rows, key=lambda r: r['total']) if rows else None
    #     highest_subject = {
    #         'name':  best_row['subject_name'],
    #         'total': best_row['total'],
    #     } if best_row else None

    #     # ── TermSummary extras ────────────────────────────────────────────────
    #     summary = TermSummary.objects.filter(
    #         student=student, term=term
    #     ).first()

    #     # Position and attendance: use None sentinel so template can do
    #     # {% if tc.position %} without string comparisons.
    #     position       = summary.class_position if summary else None
    #     total_students = summary.total_students if summary else None
    #     attendance     = summary.attendance     if summary else None

    #     # Comments — may be empty strings
    #     teacher_comment   = (summary.teacher_comment   or '').strip() if summary else ''
    #     principal_comment = (summary.principal_comment or '').strip() if summary else ''

    #     # Attendance calendar dots
    #     attendance_dots = build_attendance_dots(summary)

    #     # Count dot types for the legend
    #     dot_counts = {
    #         'present': attendance_dots.count('present'),
    #         'absent':  attendance_dots.count('absent'),
    #         'late':    attendance_dots.count('late'),
    #     }

    #     term_cards.append({
    #         # ── identity ──────────────────────────────────────────────────────
    #         'term':       term,
    #         'term_label': results.first().get_term_display(),
    #         'session':    results.first().session,

    #         # ── scores ────────────────────────────────────────────────────────
    #         'rows':           rows,
    #         'total_score':    sum(totals),
    #         'max_score':      len(rows) * 100,
    #         'subject_count':  len(rows),
    #         'average':        avg,
    #         'overall_grade':  get_grade(avg),
    #         'highest_subject': highest_subject,

    #         # ── TermSummary ───────────────────────────────────────────────────
    #         'position':          position,        # int or None
    #         'total_students':    total_students,  # int or None
    #         'attendance':        attendance,       # int (%) or None
    #         'teacher_comment':   teacher_comment,
    #         'principal_comment': principal_comment,
    #         'next_term_begins':  summary.next_term_begins if summary else None,

    #         # ── attendance calendar ───────────────────────────────────────────
    #         'attendance_dots': attendance_dots,   # list of strings
    #         'dot_counts':      dot_counts,
    #     })

    # return render(request, 'portal/result3.html', {
    #     'student':    student,
    #     'term_cards': term_cards,
    # })

def dashboard_view(request):
    student = logged_in_student(request)
    if not student:
        return redirect('login')

    term_cards = []

    for term, term_label in [('first','First Term'),('second','Second Term'),('third','Third Term')]:

        results = (
            Result.objects
            .filter(student=student, term=term)
            .select_related('subject')
            .order_by('subject__name')
        )
        if not results.exists():
            continue

        rows   = build_rows(results)
        totals = [r['total'] for r in rows]
        avg    = round(sum(totals) / len(totals), 1) if totals else 0
        best   = max(rows, key=lambda r: r['total']) if rows else None

        summary = TermSummary.objects.filter(
            student=student, term=term
        ).order_by('-id').first()

        # Read days directly — attendance % computed by model property
        days_present      = summary.days_present      if summary else 0
        days_absent       = summary.days_absent       if summary else 0
        attendance_pct    = summary.attendance        if summary else None  # model property
        class_position    = summary.class_position    if summary else None
        total_students    = summary.total_students    if summary else None
        teacher_comment   = (summary.teacher_comment   or '').strip() if summary else ''
        principal_comment = (summary.principal_comment or '').strip() if summary else ''
        next_term_begins  = summary.next_term_begins  if summary else None
        session           = summary.session           if summary else results.first().session

        term_cards.append({
            'term':            term,
            'term_label':      term_label,
            'session':         session,

            # scores
            'rows':            rows,
            'total_score':     sum(totals),
            'max_score':       len(rows) * 100,
            'subject_count':   len(rows),
            'average':         avg,
            'overall_grade':   get_grade(avg),
            'highest_subject': {'name': best['subject_name'], 'total': best['total']} if best else None,

            # TermSummary
            'position':          class_position,
            'total_students':    total_students,
            'attendance':        attendance_pct,   # percentage (auto-calculated)
            'days_present':      days_present,
            'days_absent':       days_absent,
            'teacher_comment':   teacher_comment,
            'principal_comment': principal_comment,
            'next_term_begins':  next_term_begins,

            # attendance calendar
            'attendance_dots': build_attendance_dots(days_present, days_absent),
        })

    return render(request, 'portal/result4.html', {
        'student':    student,
        'term_cards': term_cards,
    })



def term_result_view(request, term):
    student = logged_in_student(request)
    if not student:
        return redirect('login')

    results = Result.objects.filter(student=student, term=term).select_related('subject')
    if not results.exists():
        raise Http404('No results for this term.')

    rows    = build_rows(results)
    totals  = [r['total'] for r in rows]
    avg     = round(sum(totals) / len(totals), 1)
    summary = TermSummary.objects.filter(student=student, term=term).first()

    return render(request, 'portal/detail.html', {
        'student':     student,
        'term':        term,
        'term_label':  results.first().get_term_display(),
        'rows':        rows,
        'total_score': sum(totals),
        'max_score':   len(rows) * 100,
        'average':     avg,
        'overall_grade': get_grade(avg),
        'summary':     summary,
    })


def download_pdf_view(request, term):
    student = logged_in_student(request)
    if not student:
        return HttpResponse('Login required', status=403)

    results = Result.objects.filter(student=student, term=term).select_related('subject')
    if not results.exists():
        raise Http404('No results for this term.')

    rows    = build_rows(results)
    totals  = [r['total'] for r in rows]
    avg     = round(sum(totals) / len(totals), 1)
    summary = TermSummary.objects.filter(student=student, term=term).first()
    term_label = results.first().get_term_display()

    buffer = io.BytesIO()
    _build_pdf(buffer, student, term_label, rows, avg, sum(totals), len(rows)*100, summary)
    buffer.seek(0)

    filename = f"Result_{student.student_id}_{term_label.replace(' ','_')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── PDF builder ───────────────────────────────────────────────────────────────

def _build_pdf(buffer, student, term_label, rows, avg, total_score, max_score, summary):
    INK   = colors.HexColor('#0d0f14')
    GOLD  = colors.HexColor('#c8a84b')
    CREAM = colors.HexColor('#ede9e0')
    GREEN = colors.HexColor('#1e7a44')
    BLUE  = colors.HexColor('#1e4fa3')
    RED   = colors.HexColor('#c0392b')
    SOFT  = colors.HexColor('#f5f2ec')
    WHITE = colors.white

    GRADE_COLOR = {'A': GREEN, 'B': BLUE, 'C': colors.HexColor('#b8860b'),
                   'D': RED,   'F': RED}

    M   = 18 * mm
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=M, bottomMargin=M)
    W   = A4[0] - 2 * M
    ss  = getSampleStyleSheet()

    def p(text, **kw):
        return Paragraph(text, ParagraphStyle('x', parent=ss['Normal'], **kw))

    story = []

    # Header
    hdr = Table([[
        p('<b>Evergreen Academy</b>',
          fontSize=14, textColor=WHITE),
        p(f'<b>Academic Result Sheet</b><br/>'
          f'<font size="9" color="#c8a84b">{term_label}</font>',
          fontSize=11, textColor=WHITE, alignment=TA_RIGHT),
    ]], colWidths=[W*0.6, W*0.4])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), INK),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width=W, thickness=2, color=GOLD, spaceAfter=4))

    # Student info
    def cell(label, val):
        return p(f'<font size="7" color="#888888">{label}</font><br/><b>{val}</b>',
                 fontSize=10)

    info = Table([[
        cell('STUDENT NAME',   student.full_name),
        cell('STUDENT ID',     student.student_id),
        cell('CLASS',          student.class_name),
        cell('CLASS POSITION', summary.class_position if summary else '—'),
        cell('ATTENDANCE',     f"{summary.attendance}%" if summary else '—'),
        p(f'<font size="30" color="#c8a84b"><b>{get_grade(avg)}</b></font>'
          f'<br/><font size="9" color="#888888">{avg}% avg</font>',
          alignment=TA_CENTER),
    ]], colWidths=[W*0.22, W*0.16, W*0.16, W*0.14, W*0.14, W*0.18])
    info.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,-1), SOFT),
        ('TOPPADDING', (0,0),(-1,-1), 6), ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('LEFTPADDING',(0,0),(-1,-1), 5), ('RIGHTPADDING', (0,0),(-1,-1), 5),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('LINEAFTER',  (0,0),(4,-1),  0.5, CREAM),
    ]))
    story.append(info)
    story.append(Spacer(1, 5*mm))

    # Results table
    def th(t): return p(f'<b>{t}</b>', fontSize=7.5, textColor=colors.HexColor('#555'),
                         alignment=TA_CENTER)
    def td(t, align=TA_CENTER): return p(str(t), fontSize=9, alignment=align)
    def td_grade(g):
        return p(f'<b>{g}</b>', fontSize=9, textColor=GRADE_COLOR.get(g, INK),
                  alignment=TA_CENTER)

    table_data = [[th('SUBJECT'), th('CA1\n/20'), th('CA2\n/20'),
                   th('EXAM\n/60'), th('TOTAL\n/100'), th('GRADE'), th('REMARK')]]
    for r in rows:
        table_data.append([
            td(r['subject'], TA_LEFT),
            td(r['ca1']), td(r['ca2']), td(r['exam']),
            p(f"<b>{r['total']}</b>", fontSize=9, alignment=TA_CENTER),
            td_grade(r['grade']),
            p(r['remark'], fontSize=8,
              textColor=GRADE_COLOR.get(r['grade'], INK), alignment=TA_CENTER),
        ])

    tbl = Table(table_data,
                colWidths=[W*0.28, W*0.09, W*0.09, W*0.1, W*0.11, W*0.1, W*0.13],
                repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',     (0,0),(-1,0),  CREAM),
        ('ROWBACKGROUNDS', (0,1),(-1,-1), [WHITE, SOFT]),
        ('GRID',           (0,0),(-1,-1), 0.3, colors.HexColor('#e0ddd6')),
        ('TOPPADDING',     (0,0),(-1,-1), 4),
        ('BOTTOMPADDING',  (0,0),(-1,-1), 4),
        ('LEFTPADDING',    (0,0),(-1,-1), 4),
        ('RIGHTPADDING',   (0,0),(-1,-1), 4),
        ('VALIGN',         (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 3*mm))
    story.append(p('<b>Key:</b>  A=75-100 Excellent  B=65-74 Good  '
                   'C=55-64 Average  D=45-54 Below Average  F=0-44 Fail',
                   fontSize=7.5, textColor=colors.HexColor('#555')))
    story.append(Spacer(1, 5*mm))

    # Comments
    if summary and (summary.teacher_comment or summary.principal_comment):
        comments = Table([[
            p(f'<b>Form Tutor:</b><br/><i>{summary.teacher_comment or "—"}</i>',
              fontSize=8.5, leading=13),
            p(f'<b>Principal:</b><br/><i>{summary.principal_comment or "—"}</i>',
              fontSize=8.5, leading=13),
        ]], colWidths=[W*0.49, W*0.49])
        comments.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), SOFT),
            ('TOPPADDING',   (0,0),(-1,-1), 8), ('BOTTOMPADDING',(0,0),(-1,-1), 8),
            ('LEFTPADDING',  (0,0),(-1,-1), 8), ('RIGHTPADDING', (0,0),(-1,-1), 8),
            ('LINEAFTER',    (0,0),(0,-1),  0.5, CREAM),
            ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ]))
        story.append(comments)
        story.append(Spacer(1, 4*mm))

    # Footer
    next_term = summary.next_term_begins.strftime('%d %b %Y') if (summary and summary.next_term_begins) else '—'
    foot = Table([[
        p('<b>✓  Result Verified &amp; Approved</b><br/>'
          '<font size="7" color="#888888">Evergreen Academy · Academic Board</font>',
          fontSize=9, textColor=WHITE),
        p(f'Next Term Begins: <b>{next_term}</b>',
          fontSize=8, textColor=colors.HexColor('#aaaaaa'), alignment=TA_RIGHT),
    ]], colWidths=[W*0.6, W*0.4])
    foot.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), INK),
        ('TOPPADDING',    (0,0),(-1,-1), 8), ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('LEFTPADDING',   (0,0),(-1,-1), 10), ('RIGHTPADDING',(0,0),(-1,-1), 10),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(foot)
    doc.build(story)


from .docx import print_result_view as _build_and_send

def print_result(request):
    student = logged_in_student(request)
    if not student:
        return redirect('login')

    # Reuse the same term_cards builder — no duplication
    term_cards = _build_term_cards(student)
    return _build_and_send(request, student, term_cards)


def _build_term_cards(student):
    """Extracted so both result_view and print_result can share it."""
    term_cards = []
    for term, term_label in [('first','First Term'),('second','Second Term'),('third','Third Term')]:
        results = (
            Result.objects
            .filter(student=student, term=term)
            .select_related('subject')
            .order_by('subject__name')
        )
        if not results.exists():
            continue

        rows   = build_rows(results)
        totals = [r['total'] for r in rows]
        avg    = round(sum(totals) / len(totals), 1) if totals else 0
        best   = max(rows, key=lambda r: r['total']) if rows else None

        summary = TermSummary.objects.filter(
            student=student, term=term
        ).order_by('-id').first()

        days_present      = summary.days_present      if summary else 0
        days_absent       = summary.days_absent       if summary else 0
        attendance_pct    = summary.attendance        if summary else None
        class_position    = summary.class_position    if summary else None
        total_students    = summary.total_students    if summary else None
        teacher_comment   = (summary.teacher_comment   or '').strip() if summary else ''
        principal_comment = (summary.principal_comment or '').strip() if summary else ''
        next_term_begins  = summary.next_term_begins  if summary else None
        session           = summary.session           if summary else results.first().session

        term_cards.append({
            'term':            term,
            'term_label':      term_label,
            'session':         session,
            'rows':            rows,
            'total_score':     sum(totals),
            'max_score':       len(rows) * 100,
            'subject_count':   len(rows),
            'average':         avg,
            'overall_grade':   get_grade(avg),
            'highest_subject': {'name': best['subject_name'], 'total': best['total']} if best else None,
            'position':          class_position,
            'total_students':    total_students,
            'attendance':        attendance_pct,
            'days_present':      days_present,
            'days_absent':       days_absent,
            'teacher_comment':   teacher_comment,
            'principal_comment': principal_comment,
            'next_term_begins':  next_term_begins,
            'attendance_dots':   build_attendance_dots(days_present, days_absent),
        })
    return term_cards

def health_check(request):
    return HttpResponse("OK")