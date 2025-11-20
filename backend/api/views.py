from rest_framework import viewsets
from rest_framework.decorators import action
from .models import McapLog, Car, Driver, EventType
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    McapLogSerializer, 
    ParseSummaryRequestSerializer,
    CarSerializer,
    DriverSerializer,
    EventTypeSerializer
)
from .parser import Parser
from .gpsparse import GpsParser
import os
import datetime
from django.utils import timezone
from django.contrib.gis.geos import LineString, Point, Polygon
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Q

class McapLogViewSet(viewsets.ModelViewSet):
    queryset = McapLog.objects.all()
    serializer_class = McapLogSerializer
    
    def get_queryset(self):
        """
        Override to support query parameter filtering.
        Supported query parameters:
        - start_date: Filter logs captured on or after this date (YYYY-MM-DD)
        - end_date: Filter logs captured on or before this date (YYYY-MM-DD)
        - car_id: Filter by car ID
        - event_type_id: Filter by event type ID
        - location: Filter by geographic bounding box (format: min_lon,min_lat,max_lon,max_lat)
        - driver_id: Filter by driver ID
        - parse_status: Filter by parse status
        - recovery_status: Filter by recovery status
        """
        queryset = McapLog.objects.all()
        
        # Date filtering - using captured_at field
        start_date = self.request.query_params.get('start_date', None)
        if start_date:
            try:
                from django.utils.dateparse import parse_date
                date_obj = parse_date(start_date)
                if date_obj:
                    # Start of day
                    start_datetime = timezone.make_aware(
                        datetime.datetime.combine(date_obj, datetime.time.min)
                    )
                    queryset = queryset.filter(captured_at__gte=start_datetime)
            except (ValueError, TypeError):
                pass  # Ignore invalid date formats
        
        end_date = self.request.query_params.get('end_date', None)
        if end_date:
            try:
                from django.utils.dateparse import parse_date
                date_obj = parse_date(end_date)
                if date_obj:
                    # End of day
                    end_datetime = timezone.make_aware(
                        datetime.datetime.combine(date_obj, datetime.time.max)
                    )
                    queryset = queryset.filter(captured_at__lte=end_datetime)
            except (ValueError, TypeError):
                pass  # Ignore invalid date formats
        
        # Filter by car
        car_id = self.request.query_params.get('car_id', None)
        if car_id:
            try:
                queryset = queryset.filter(car_id=int(car_id))
            except (ValueError, TypeError):
                pass
        
        # Filter by event type
        event_type_id = self.request.query_params.get('event_type_id', None)
        if event_type_id:
            try:
                queryset = queryset.filter(event_type_id=int(event_type_id))
            except (ValueError, TypeError):
                pass
        
        # Filter by driver
        driver_id = self.request.query_params.get('driver_id', None)
        if driver_id:
            try:
                queryset = queryset.filter(driver_id=int(driver_id))
            except (ValueError, TypeError):
                pass
        
        # Filter by parse status
        parse_status = self.request.query_params.get('parse_status', None)
        if parse_status:
            queryset = queryset.filter(parse_status=parse_status)
        
        # Filter by recovery status
        recovery_status = self.request.query_params.get('recovery_status', None)
        if recovery_status:
            queryset = queryset.filter(recovery_status=recovery_status)
        
        # Geographic location filtering (bounding box)
        # Format: min_lon,min_lat,max_lon,max_lat
        location = self.request.query_params.get('location', None)
        if location:
            try:
                coords = [float(x.strip()) for x in location.split(',')]
                if len(coords) == 4:
                    min_lon, min_lat, max_lon, max_lat = coords
                    # Create bounding box polygon
                    bbox = Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))
                    # Filter logs where lap_path intersects with bounding box
                    queryset = queryset.filter(lap_path__intersects=bbox)
            except (ValueError, TypeError, IndexError):
                pass  # Ignore invalid location formats
        
        return queryset.order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="List MCAP logs with optional filtering by date, location, car, event, and more.",
        manual_parameters=[
            openapi.Parameter(
                'start_date',
                openapi.IN_QUERY,
                description="Filter logs captured on or after this date (format: YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                'end_date',
                openapi.IN_QUERY,
                description="Filter logs captured on or before this date (format: YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                'car_id',
                openapi.IN_QUERY,
                description="Filter by car ID",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                'event_type_id',
                openapi.IN_QUERY,
                description="Filter by event type ID",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                'driver_id',
                openapi.IN_QUERY,
                description="Filter by driver ID",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                'location',
                openapi.IN_QUERY,
                description="Filter by geographic bounding box (format: min_lon,min_lat,max_lon,max_lat). Returns logs whose GPS path intersects with the bounding box.",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                'parse_status',
                openapi.IN_QUERY,
                description="Filter by parse status (e.g., 'completed', 'pending', 'error:...')",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                'recovery_status',
                openapi.IN_QUERY,
                description="Filter by recovery status",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        tags=['MCAP Logs']
    )
    def list(self, request, *args, **kwargs):
        """
        List MCAP logs with optional filtering.
        All query parameters are optional and can be combined.
        Examples:
        - /api/mcap-logs/?start_date=2025-01-01&end_date=2025-01-31
        - /api/mcap-logs/?car_id=1&event_type_id=2
        - /api/mcap-logs/?location=-122.5,37.7,-122.3,37.9
        """
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        """
        Create a new McapLog. If 'file' is uploaded, save it, parse it, and populate fields.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Handle file upload
        uploaded_file = request.FILES.get('file')
        saved_file_path = None
        
        if uploaded_file:
            # Create media directory if it doesn't exist
            media_dir = settings.MEDIA_ROOT / 'mcap_logs'
            media_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename to avoid conflicts
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f"{timestamp}_{uploaded_file.name}"
            file_path = media_dir / file_name
            
            # Save the uploaded file
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            saved_file_path = str(file_path)
            
            # Store the URI in original_uri
            serializer.validated_data['original_uri'] = f"{settings.MEDIA_URL}mcap_logs/{file_name}"
            # Set file_name from uploaded file if not already provided
            if 'file_name' not in serializer.validated_data or not serializer.validated_data.get('file_name'):
                serializer.validated_data['file_name'] = uploaded_file.name
            
            # Parse the uploaded file
            try:
                parsed_data = Parser.parse_stuff(saved_file_path)
                
                # Populate fields from parsed data
                serializer.validated_data['channels'] = parsed_data.get("channels", [])
                serializer.validated_data['channel_count'] = parsed_data.get("channel_count", 0)
                serializer.validated_data['start_time'] = parsed_data.get("start_time")
                serializer.validated_data['end_time'] = parsed_data.get("end_time")
                serializer.validated_data['duration_seconds'] = parsed_data.get("duration", 0)
                
                # Parse GPS coordinates from the file
                gps_data = GpsParser.parse_gps(saved_file_path)
                all_coordinates = gps_data.get("all_coordinates", [])
                
                # Create LineString from all GPS coordinates for map preview
                if all_coordinates:
                    # LineString takes a list of (x, y) tuples, which is [longitude, latitude] in our case
                    # all_coordinates is already in [longitude, latitude] format
                    serializer.validated_data['lap_path'] = LineString(all_coordinates, srid=4326)
                
                if parsed_data.get("start_time"):
                    # Convert timestamp to timezone-aware datetime
                    naive_dt = datetime.datetime.fromtimestamp(parsed_data.get("start_time"))
                    serializer.validated_data['captured_at'] = timezone.make_aware(naive_dt)
                
                serializer.validated_data['parse_status'] = "completed"
            except Exception as e:
                serializer.validated_data['parse_status'] = f"error: {str(e)}"
        else:
            # If no file uploaded, ensure file_name is set if provided in request
            if 'file_name' not in serializer.validated_data or not serializer.validated_data.get('file_name'):
                # Set a default file_name if not provided
                serializer.validated_data['file_name'] = 'unknown.mcap'
        
        # Remove 'file' from validated_data since it's not a model field
        serializer.validated_data.pop('file', None)
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @swagger_auto_schema(
        method='get',
        operation_description="Returns LineString as GeoJSON. Reads from DB if available, otherwise parses from MCAP file. Optionally uses PostGIS ST_SimplifyVW for simplification.",
        manual_parameters=[
            openapi.Parameter(
                'tolerance',
                openapi.IN_QUERY,
                description="Simplification tolerance in degrees (default: 0.00001, roughly 1.1 meters). Set to 0 or omit 'simplify' parameter to return full path. Higher values result in more aggressive simplification.",
                type=openapi.TYPE_NUMBER,
                required=False,
            ),
            openapi.Parameter(
                'simplify',
                openapi.IN_QUERY,
                description="Whether to apply simplification (default: false). Set to 'true' to enable simplification.",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="GeoJSON FeatureCollection with simplified LineString",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'type': openapi.Schema(type=openapi.TYPE_STRING, example='FeatureCollection'),
                        'features': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT)
                        ),
                    }
                )
            ),
            404: openapi.Response(description="No GPS path available for this log"),
            500: openapi.Response(description="Failed to parse MCAP file"),
        },
        tags=['MCAP Logs']
    )
    @action(detail=True, methods=['get'], url_path='geojson')
    def geojson(self, request, pk=None):
        """
        Returns LineString as GeoJSON.
        Reads from DB if available, otherwise parses from MCAP file.
        By default returns the full unsimplified path. Use ?simplify=true to enable simplification.
        """
        mcap_log = self.get_object()
        
        # Get or parse lap_path
        lap_path = mcap_log.lap_path
        
        # If lap_path doesn't exist in DB, try to parse from MCAP file
        if not lap_path and mcap_log.original_uri:
            try:
                # Extract file path from original_uri
                # original_uri format: /media/mcap_logs/filename.mcap
                if mcap_log.original_uri.startswith(settings.MEDIA_URL):
                    file_name = mcap_log.original_uri.replace(settings.MEDIA_URL, '')
                    file_path = settings.MEDIA_ROOT / file_name
                    
                    if file_path.exists():
                        # Parse GPS coordinates from MCAP file
                        gps_data = GpsParser.parse_gps(str(file_path))
                        all_coordinates = gps_data.get("all_coordinates", [])
                        
                        if all_coordinates:
                            lap_path = LineString(all_coordinates, srid=4326)
                            # Optionally save to DB for future use
                            mcap_log.lap_path = lap_path
                            mcap_log.save(update_fields=['lap_path'])
            except Exception as e:
                return Response(
                    {'error': f'Failed to parse MCAP file: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        if not lap_path:
            return Response(
                {'error': 'No GPS path available for this log'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if simplification is requested
        simplify = request.query_params.get('simplify', 'false').lower() == 'true'
        
        if simplify:
            # Simplify using PostGIS ST_SimplifyVW
            # Get tolerance parameter from query string (default: 0.00001 degrees, roughly 1.1 meters)
            tolerance = float(request.query_params.get('tolerance', 0.00001))
            
            try:
                # Use PostGIS ST_SimplifyVW function
                # Note: ST_SimplifyVW works with geometry, not geography, so we need to cast
                from django.contrib.gis.db.models import Func
                from django.contrib.gis.db.models.fields import GeometryField
                from django.db.models import F
                
                # Create a queryset with the simplified geometry
                # Cast geography to geometry using ::geometry, then simplify
                simplified_path = McapLog.objects.filter(pk=mcap_log.pk).annotate(
                    geometry_path=Func(
                        F('lap_path'),
                        template='%(expressions)s::geometry',
                        output_field=GeometryField(srid=4326)
                    ),
                    simplified_path=Func(
                        F('geometry_path'),
                        tolerance,
                        function='ST_SimplifyVW',
                        output_field=GeometryField(srid=4326)
                    )
                ).first().simplified_path
                
                # If simplification failed or returned None, use original
                if not simplified_path:
                    simplified_path = lap_path
            except Exception as e:
                # Fallback: use original path if PostGIS function fails
                print(f"Warning: ST_SimplifyVW failed, using original path: {e}")
                simplified_path = lap_path
        else:
            # Return full unsimplified path
            simplified_path = lap_path
        
        # Build GeoJSON FeatureCollection
        import json
        features = []
        
        # Add simplified path as LineString
        if simplified_path:
            # Convert LineString to GeoJSON format
            coordinates = list(simplified_path.coords)
            path_feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coordinates
                },
                'properties': {
                    'type': 'lap_path',
                    'id': mcap_log.id,
                    'simplified': simplify
                }
            }
            features.append(path_feature)
        
        # Return FeatureCollection
        geojson_response = {
            'type': 'FeatureCollection',
            'features': features
        }
        
        return Response(geojson_response, status=status.HTTP_200_OK)


class ParseSummaryView(APIView):
    @swagger_auto_schema(
        request_body=ParseSummaryRequestSerializer,
        operation_description="Parse MCAP file summary without creating a database record. Returns channel information, timestamps, and duration.",
        responses={
            200: openapi.Response(
                description="Parsed MCAP file summary",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'channels': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                        'channel_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'start_time': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'end_time': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'duration': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'formatted_date': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid request data"),
        },
        tags=['Parsing']
    )
    def post(self, request):
        """
        Parse MCAP file summary without creating a database record.
        Returns channel information, timestamps, and duration.
        """
        serializer = ParseSummaryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        path = serializer.validated_data["path"]

        # Call your existing parsing function here:
        result = Parser.parse_stuff(path)  # your Python parser returning a dict

        return Response(result, status=status.HTTP_200_OK)


class CarViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing Car instances.
    Provides list and detail views for dropdown population.
    """
    queryset = Car.objects.all().order_by('name')
    serializer_class = CarSerializer


class DriverViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing Driver instances.
    Provides list and detail views for dropdown population.
    """
    queryset = Driver.objects.all().order_by('name')
    serializer_class = DriverSerializer


class EventTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing EventType instances.
    Provides list and detail views for dropdown population.
    """
    queryset = EventType.objects.all().order_by('name')
    serializer_class = EventTypeSerializer
