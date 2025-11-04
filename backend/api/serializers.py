from rest_framework import serializers
from .models import McapLog

class McapLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = McapLog
        fields = ['id','file_name','created_at']
