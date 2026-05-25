# results/models.py

from django.db import models
from django.contrib.auth.models import User

class Student(models.Model):
    student_id = models.CharField(max_length=30, unique=True)
    full_name  = models.CharField(max_length=150)
    class_name = models.CharField(max_length=50)
    pin        = models.CharField(max_length=10)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students'
    )

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default='📚')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subjects'
    )

    def __str__(self):
        return self.name


class Result(models.Model):
    TERM_CHOICES = [
        ('first',  'First Term'),
        ('second', 'Second Term'),
        ('third',  'Third Term'),
    ]
    student    = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject    = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term       = models.CharField(max_length=10, choices=TERM_CHOICES)
    session    = models.CharField(max_length=20, default='2024/2025')
    ca1        = models.PositiveSmallIntegerField(default=0)
    ca2        = models.PositiveSmallIntegerField(default=0)
    exam_score = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='results'
    )

    @property
    def total(self):
        return self.ca1 + self.ca2 + self.exam_score

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.term}"


class TermSummary(models.Model):
    TERM_CHOICES = [
        ('first',  'First Term'),
        ('second', 'Second Term'),
        ('third',  'Third Term'),
    ]

    student           = models.ForeignKey(Student, on_delete=models.CASCADE)
    term              = models.CharField(max_length=10, choices=TERM_CHOICES)
    session           = models.CharField(max_length=20, default='2024/2025')
    class_position    = models.PositiveSmallIntegerField(default=1)
    total_students    = models.PositiveSmallIntegerField(default=1)
    days_present      = models.PositiveSmallIntegerField(default=0,
                            help_text='Number of days the student was present')
    days_absent       = models.PositiveSmallIntegerField(default=0,
                            help_text='Number of days the student was absent')
    teacher_comment   = models.TextField(blank=True)
    principal_comment = models.TextField(blank=True)
    next_term_begins  = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='term_summaries'
    )

    @property
    def attendance(self):
        """Percentage calculated automatically — no need to enter it manually."""
        total = self.days_present + self.days_absent
        if total == 0:
            return 0
        return round((self.days_present / total) * 100)

    class Meta:
        unique_together = ('student', 'term', 'session')

    def __str__(self):
        return f"{self.student} - {self.term} - {self.session}"
