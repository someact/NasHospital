from django import forms
from .models import Paper, PaperRound, ReviewFeedback, CoordinatorLetter, AccessRequest, ReviewDecision, CoordinatorDecision


class PaperSubmissionForm(forms.ModelForm):
    pdf_file = forms.FileField(
        required=True,
        label="Manuscript PDF (Full Text)",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )
    summary_notes = forms.CharField(
        required=False,
        label="Submission Notes",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Initial clinical context or submission remarks'})
    )

    class Meta:
        model = Paper
        fields = ['title', 'category', 'department', 'co_authors', 'abstract']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Clinical Efficacy of Novel SGLT2 Inhibitors'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Cardiology / Clinical Trial'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Cardiology'}),
            'co_authors': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dr. Jane Smith, MD; Dr. John Watson, PhD'}),
            'abstract': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Structured clinical abstract (Background, Methods, Results, Conclusion)'}),
        }


class RevisionSubmissionForm(forms.Form):
    pdf_file = forms.FileField(
        required=True,
        label="Revised Manuscript PDF",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )
    summary_notes = forms.CharField(
        required=True,
        label="Response to Coordinator Revision Directives",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Explain how reviewer critiques and coordinator synthesis were addressed.'})
    )


class ReviewCritiqueForm(forms.ModelForm):
    class Meta:
        model = ReviewFeedback
        fields = ['structure_comment', 'intro_comment', 'expansion_comment', 'decision', 'annotated_pdf']
        widgets = {
            'structure_comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Assess clinical study design, methodology, sample size power, and statistical rigor...'
            }),
            'intro_comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Assess background relevance, clinical literature depth, hypotheses, and clinical problem statement...'
            }),
            'expansion_comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Critique clinical trial endpoints, safety outcomes, adverse effects, and discussion limits...'
            }),
            'decision': forms.Select(attrs={'class': 'form-select'}),
            'annotated_pdf': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
        }
        labels = {
            'structure_comment': '1. Structure & Methodology (เค้าโครง)',
            'intro_comment': '2. Introduction & Literature (บทนำ)',
            'expansion_comment': '3. Results & Discussion (บทขยาย)',
            'decision': 'Evaluation Recommendation',
            'annotated_pdf': 'Optional Annotated PDF Attachment',
        }


class CoordinatorLetterForm(forms.ModelForm):
    class Meta:
        model = CoordinatorLetter
        fields = ['consolidated_comment', 'decision']
        widgets = {
            'consolidated_comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Synthesize reviewer observations into clear directives for the author (Double-blind: no reviewer names)...'
            }),
            'decision': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'consolidated_comment': 'Consolidated Coordinator Directives (Sent to Author)',
            'decision': 'Coordinator Final Disposition',
        }


class AccessRequestForm(forms.ModelForm):
    class Meta:
        model = AccessRequest
        fields = ['duration_days', 'reason']
        widgets = {
            'duration_days': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'State clinical or research necessity (e.g. Protocol formulation for Departmental Grand Rounds)...'
            }),
        }
        labels = {
            'duration_days': 'Requested Pass Duration',
            'reason': 'Clinical Justification',
        }
