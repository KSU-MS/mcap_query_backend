from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from api.views import McapLogViewSet, ParseSummaryView

router = DefaultRouter()
router.register(r'mcap-logs', McapLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path("parse/summary/", ParseSummaryView.as_view(), name="parse-summary"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
