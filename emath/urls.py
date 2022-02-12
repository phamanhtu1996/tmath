from django.urls import path
from django.conf.urls import url, include
from .views import ExamProblemView, ProblemDetail, ProblemList, judge, ExamList, AllSubmissions

app_name = 'emath'

urlpatterns = [
    url(r'^$', ExamList.as_view(), name='exam_list'),
    url(r'^exam/(?P<pk>\d+)$', ExamProblemView.as_view(), name='exam_detail'),
    url(r'^judge$', judge, name="judge_exam"),
    url(r'^submissions$', AllSubmissions.as_view(), name='all_submissions'),
    url(r'^problems$', ProblemList.as_view(), name='emath_problem_list'),
    url(r'^problem/(?P<problem>[^/]+)$', ProblemDetail.as_view(), name='problem_detail')
]