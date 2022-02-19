from django.urls import path
from django.conf.urls import url, include

from emath.views.exam import ExamDetail, ExamJoin, ExamLeave, ExamRanking
from .views import ExamProblemView, ProblemDetail, ProblemList, ExamList, AllSubmissions
from emath.views.submission import AllUserSubmissions, UserExamSubmissions, ExamSubmissions
from dmoj.urls import paged_list_view

app_name = 'emath'

urlpatterns = [
    url(r'^$', ExamList.as_view(), name='exam_list'),
    url(r'^exam/(?P<exam>\w+)', include([
        url(r'^$', ExamDetail.as_view(), name='exam_detail'),
        url(r'^/ranking$', ExamRanking.as_view(), name='exam_ranking'),
        url(r'^/submit$', ExamProblemView.as_view(), name='exam_task'),
        url(r'^/leave$', ExamLeave.as_view(), name='exam_leave'),
        url(r'^/join$', ExamJoin.as_view(), name='exam_join'),
        url(r'^/submissions/', paged_list_view(ExamSubmissions, 'chronological_submissions')),
        url(r'^/submissions/(?P<user>[\w-]+)/', paged_list_view(UserExamSubmissions, 'user_submissions')),
    ])),
    url(r'^submissions$', AllSubmissions.as_view(), name='all_submissions'),
    url(r'^submissions/user/(?P<user>[\w-]+)/', paged_list_view(AllUserSubmissions, 'all_user_submissions')),
    url(r'^problems$', ProblemList.as_view(), name='emath_problem_list'),
    url(r'^problem/(?P<problem>[^/]+)$', ProblemDetail.as_view(), name='problem_detail')
]