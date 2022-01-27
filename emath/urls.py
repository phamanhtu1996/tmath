from django.urls import path
from django.conf.urls import url, include
from .views import ExamProblemView, judge, ExamList, AllSubmissions

app_name = 'emath'

urlpatterns = [
    url(r'^exam$', ExamList.as_view(), name='exam_list'),
    url(r'^exam/(?P<pk>\d+)$', ExamProblemView.as_view(), name='exam_detail'),
    url(r'^judge$', judge, name="judge_exam"),
    url(r'^submissions', AllSubmissions.as_view(), name='all_submissions'),
]