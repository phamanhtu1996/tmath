from reversion import revisions

from .organization import Organization
from .problem import Problem
from .exam import Exam, ExamProblem, ExamParticipation, ExamSubmission
from .submission import Submission

revisions.register(Problem)
revisions.register(Exam, follow=['exam_problems'])
revisions.register(ExamProblem)

del revisions