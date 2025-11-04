from rest_framework import viewsets
from .models import McapLog
from .serializers import McapLogSerializer

class McapLogViewSet(viewsets.ModelViewSet):
    queryset = McapLog.objects.all()
    serializer_class = McapLogSerializer



