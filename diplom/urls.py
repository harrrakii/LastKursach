from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from messenger.views import login_page, admin_console, admin_create_page, student_page, parent_page, teacher_page, methodist_page, manager_page, manager_console_page, manager_create_page

try:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
    HAS_SPECTACULAR = True
except Exception:
    HAS_SPECTACULAR = False

urlpatterns = [
    path('', lambda r: redirect('/login/')),
    path('login/', login_page, name='login'),
    path('console/', admin_console, name='admin_console'),
    path('console/create/<str:model>/', admin_create_page, name='admin_create_page'),
    path('student/', student_page, name='student_page'),
    path('parent/', parent_page, name='parent_page'),
    path('teacher/', teacher_page, name='teacher_page'),
    path('methodist/', methodist_page, name='methodist_page'),
    path('manager/', manager_page, name='manager_page'),
    path('manager/console/', manager_console_page, name='manager_console_page'),
    path('manager/create/<str:model>/', manager_create_page, name='manager_create_page'),
    path('admin/', admin.site.urls),
    path('api/', include('messenger.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if HAS_SPECTACULAR:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
