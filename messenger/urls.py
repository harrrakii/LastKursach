from rest_framework import routers
from django.urls import path, include

from .views import (
    GroupViewSet,
    TeacherViewSet,
    ParentViewSet,
    StudentViewSet,
    MethodPackageViewSet,
    ScheduleSlotViewSet,
    ChatRoomViewSet,
    MessageViewSet,
    EventViewSet,
    FeedPostViewSet,
    MethodAssignmentViewSet,
    HolidayViewSet,
    SubjectViewSet,
    LessonTopicViewSet,
    UserProfileViewSet,
    MediaUploadView,
    MeView,
    session_login,
    session_logout,
)

router = routers.DefaultRouter()
router.register(r'groups', GroupViewSet)
router.register(r'teachers', TeacherViewSet)
router.register(r'parents', ParentViewSet)
router.register(r'students', StudentViewSet)
router.register(r'method-packages', MethodPackageViewSet)
router.register(r'schedule', ScheduleSlotViewSet)
router.register(r'chats', ChatRoomViewSet)
router.register(r'messages', MessageViewSet)
router.register(r'events', EventViewSet)
router.register(r'feed-posts', FeedPostViewSet)
router.register(r'method-assignments', MethodAssignmentViewSet)
router.register(r'holidays', HolidayViewSet)
router.register(r'subjects', SubjectViewSet)
router.register(r'lesson-topics', LessonTopicViewSet)
router.register(r'profiles', UserProfileViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('upload/', MediaUploadView.as_view(), name='media_upload'),
    path('me/', MeView.as_view(), name='me'),
    path('session-login/', session_login, name='session_login'),
    path('session-logout/', session_logout, name='session_logout'),
]
