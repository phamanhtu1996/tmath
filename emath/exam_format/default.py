from datetime import timedelta
from django.utils.translation import gettext_lazy
from django.db.models import Max
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.template.defaultfilters import floatformat

from .base import BaseExamFormat
from .registry import registry_exam_format

from judge.utils.timedelta import nice_repr

@registry_exam_format('default')
class DefaultExamFormat(BaseExamFormat):
    name = gettext_lazy('Default')

    def __init__(self, exam):
        super(DefaultExamFormat, self).__init__(exam)
    
    def update_participation(self, participation):
        cumtime = 0
        points = 0
        format_data = {}

        sub = participation.submissions.aggregate(point=Max('points'))

        submission = participation.submissions.filter(points=sub['point']).order_by('-submission__date').first()

        # print(sub)


        dt = (submission.submission.date - participation.start).total_seconds()
        cumtime += dt
        
        for sub_problem in submission.submission.problems.all():
            # print(sub_problem.problem.id)
            format_data[str(sub_problem.problem.id)] = {'status': sub_problem.result}
            points += sub_problem.points
        
        participation.cumtime = max(cumtime, 0)
        participation.score = round(points, self.exam.points_precision)
        participation.tiebreaker = 0
        participation.format_data = format_data

        # print(format_data)
        
        participation.save()
    
    def display_user_problem(self, participation, exam_problem):
        # print('display_user_problem')
        format_data = (participation.format_data or {}).get(str(exam_problem.problem.id))

        # print('display_user_problem: %s', str(exam_problem.problem.id))

        if format_data:
            return format_html(
                u'<td class="{state}"><span class="material-icons">{result}</span></td>',
                state='accept' if format_data['status'] else 'wrong',
                result='check_circle' if format_data['status'] else 'clear'
            )
        else:
            return mark_safe('<td></td>')
    
    def display_participation_result(self, participation):
        # print("display_result ",participation.virtual, participation.score)
        return format_html(
            u'<td class="user-points"><strong>{points}<div class="solving-time">{cumtime}</div></strong></td>',
            points=floatformat(participation.score, -self.exam.points_precision),
            cumtime=nice_repr(timedelta(seconds=participation.cumtime), 'noday'),
        )

    def get_problem_breakdown(self, participation, exam_problems):
        return [(participation.format_data or {}).get(str(exam_problem.id)) for exam_problem in exam_problems]

    def get_label_for_problem(self, index):
        return str(index + 1)