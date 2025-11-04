from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import McapLogViewSet

router = DefaultRouter()
router.register(r'mcap-logs', McapLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
