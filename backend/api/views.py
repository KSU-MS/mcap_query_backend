from rest_framework import viewsets
from .models import McapLog
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import McapLogSerializer , ParseSummaryRequestSerializer
from .parser import Parser

class McapLogViewSet(viewsets.ModelViewSet):
    queryset = McapLog.objects.all()
    serializer_class = McapLogSerializer


class ParseSummaryView(APIView):
    def post(self, request):
        serializer = ParseSummaryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        path = serializer.validated_data["path"]

        # Call your existing parsing function here:
        result = Parser.parse_stuff(path)  # your Python parser returning a dict

        return Response(result, status=status.HTTP_200_OK)
