from django.urls import include, path
from .views import *

app_name = 'typeracer'

urlpatterns = [
  path('rooms/', TypoRoomList.as_view(), name='list_room'),
  path('asdawdadsa/', updateProgress, name='update_progress'),
  path('new_user/', Racer.as_view(), name="new_user"),
  path('finish/', finishTypoContest, name='finish_contest'),
  path('room/<int:pk>', include([
    path('/', RoomDetail.as_view(), name='room_detail'),
    path('/join', JoinRoom.as_view(), name='join_room'),
    path('/getquote', getQuote, name="get_quote"),
    # url(r'^/ranking$', ),
  ])),
  path('contest/<int:pk>', include([
    path('/rank', Ranking.as_view(), name="typo_ranking"),
  ]))
]
