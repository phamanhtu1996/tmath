from django.urls import include
from django.conf.urls import url
from .views import *

app_name = 'typeracer'

urlpatterns = [
  url(r'^rooms/$', TypoRoomList.as_view(), name='list_room'),
  url(r'^asdawdadsa/$', updateProgress, name='update_progress'),
  url(r'^new_user/$', Racer.as_view(), name="new_user"),
  url(r'^room/(?P<pk>\d+)', include([
    url(r'^/$', RoomDetail.as_view(), name='room_detail'),
    url(r'^/join$', JoinRoom.as_view(), name='join_room'),
    url(r'^/getquote$', getQuote, name="get_quote"),
    # url(r'^leave/$'),
  ]))
]
