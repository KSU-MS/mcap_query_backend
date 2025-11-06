from rest_framework import serializers
from .models import McapLog, Car, Driver, EventType

class McapLogSerializer(serializers.ModelSerializer):
    car = serializers.PrimaryKeyRelatedField(
        queryset=Car.objects.all(), allow_null=True, required=False
    )
    driver = serializers.PrimaryKeyRelatedField(
        queryset=Driver.objects.all(), allow_null=True, required=False
    )
    event_type = serializers.PrimaryKeyRelatedField(
        queryset=EventType.objects.all(), allow_null=True, required=False
    )
    class Meta:
        model = McapLog
        fields = ['id',
                  'file_name',
                  'created_at',
                  'original_uri',
                  'recovered_uri',
                  'recovery_status',
                  'parse_status',
                  'captured_at',
                  'duration_seconds',
                  'channel_count',
                  'car',
                  'driver',
                  'event_type',
                  'notes'
                  ]
        
class ParseSummaryRequestSerializer(serializers.Serializer):
    path = serializers.CharField()
    

