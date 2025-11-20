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
    EventTypeSerializer,
    DownloadRequestSerializer
)
from .parser import Parser
from .gpsparse import GpsParser
from .tasks import parse_mcap_file
from celery.result import AsyncResult
import os
import datetime
import zipfile
import tempfile
from pathlib import Path
from django.http import FileResponse, HttpResponse
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
            
            # Calculate and store file size
            file_size = file_path.stat().st_size
            serializer.validated_data['file_size'] = file_size
            
            # Store the URI in original_uri
            serializer.validated_data['original_uri'] = f"{settings.MEDIA_URL}mcap_logs/{file_name}"
            # Set file_name from uploaded file if not already provided
            if 'file_name' not in serializer.validated_data or not serializer.validated_data.get('file_name'):
                serializer.validated_data['file_name'] = uploaded_file.name
            
            # Set parse_status to pending - will be processed in background
            serializer.validated_data['parse_status'] = "pending"
        else:
            # If no file uploaded, ensure file_name is set if provided in request
            if 'file_name' not in serializer.validated_data or not serializer.validated_data.get('file_name'):
                # Set a default file_name if not provided
                serializer.validated_data['file_name'] = 'unknown.mcap'
        
        # Remove 'file' from validated_data since it's not a model field
        serializer.validated_data.pop('file', None)
        
        # Create the record first
        self.perform_create(serializer)
        mcap_log_instance = serializer.instance
        
        # If a file was uploaded, trigger background parsing
        if saved_file_path:
            task = parse_mcap_file.delay(mcap_log_instance.id, saved_file_path)
            # Store the task ID for status tracking
            mcap_log_instance.parse_task_id = task.id
            mcap_log_instance.save(update_fields=['parse_task_id'])
        
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
    
    @swagger_auto_schema(
        method='post',
        request_body=DownloadRequestSerializer,
        operation_description="Download selected MCAP log files as a ZIP archive. Accepts a list of MCAP log IDs.",
        responses={
            200: openapi.Response(
                description="ZIP file containing the selected MCAP log files",
                schema=openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_BINARY
                )
            ),
            400: openapi.Response(description="Invalid request data or no files found"),
            404: openapi.Response(description="One or more log IDs not found"),
        },
        tags=['MCAP Logs']
    )
    @action(detail=False, methods=['post'], url_path='download')
    def download(self, request):
        """
        Download selected MCAP log files as a ZIP archive.
        Accepts a POST request with a list of log IDs in the request body.
        Example: {"ids": [1, 2, 3]}
        """
        serializer = DownloadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        log_ids = serializer.validated_data['ids']
        
        # Get the McapLog objects
        mcap_logs = McapLog.objects.filter(id__in=log_ids)
        
        if not mcap_logs.exists():
            return Response(
                {'error': 'No logs found with the provided IDs'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if all requested IDs were found
        found_ids = set(mcap_logs.values_list('id', flat=True))
        requested_ids = set(log_ids)
        missing_ids = requested_ids - found_ids
        
        if missing_ids:
            return Response(
                {'error': f'Log IDs not found: {list(missing_ids)}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create a temporary file for the ZIP
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_file_path = temp_file.name
        temp_file.close()
        
        files_added = 0
        files_missing = []
        
        try:
            # Create ZIP file
            with zipfile.ZipFile(temp_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for mcap_log in mcap_logs:
                    try:
                        if not mcap_log.original_uri:
                            files_missing.append(f"{mcap_log.file_name} (ID: {mcap_log.id}) - no file URI")
                            continue
                        
                        # Extract file path from original_uri
                        # original_uri format: /media/mcap_logs/filename.mcap
                        if mcap_log.original_uri.startswith(settings.MEDIA_URL):
                            file_name = mcap_log.original_uri.replace(settings.MEDIA_URL, '', 1)  # Only replace first occurrence
                            file_path = Path(settings.MEDIA_ROOT) / file_name
                        elif mcap_log.original_uri.startswith('/'):
                            # Handle absolute paths starting with /
                            file_path = Path(mcap_log.original_uri)
                        else:
                            # Handle relative paths or other formats
                            file_path = Path(settings.MEDIA_ROOT) / mcap_log.original_uri
                        
                        # Resolve the path to handle any symlinks or relative paths
                        file_path = file_path.resolve()
                        
                        # Check if file exists
                        if not file_path.exists():
                            files_missing.append(f"{mcap_log.file_name} (ID: {mcap_log.id}) - file not found at {file_path}")
                            continue
                        
                        # Check if it's actually a file (not a directory)
                        if not file_path.is_file():
                            files_missing.append(f"{mcap_log.file_name} (ID: {mcap_log.id}) - path is not a file")
                            continue
                        
                        # Add file to ZIP with original filename
                        zip_file.write(str(file_path), arcname=mcap_log.file_name)
                        files_added += 1
                    except Exception as file_error:
                        # Handle individual file errors gracefully
                        files_missing.append(f"{mcap_log.file_name} (ID: {mcap_log.id}) - error: {str(file_error)}")
                        continue
            
            # If no files were added, return error
            if files_added == 0:
                os.unlink(temp_file_path)
                return Response(
                    {
                        'error': 'No files could be added to the ZIP archive',
                        'missing_files': files_missing
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate download filename
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f'mcap_logs_{timestamp}.zip'
            
            # Read the ZIP file into memory for response
            # This ensures proper cleanup of the temp file
            with open(temp_file_path, 'rb') as zip_file:
                zip_content = zip_file.read()
            
            # Delete temp file now that we have the content
            os.unlink(temp_file_path)
            
            # Create response with the ZIP content
            response = HttpResponse(zip_content, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
            response['Content-Length'] = len(zip_content)
            
            # Add info about missing files in response headers if any
            if files_missing:
                response['X-Missing-Files'] = ', '.join(files_missing)
            
            return response
            
        except Exception as e:
            # Clean up temp file on error
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
            # Log the full error for debugging
            import traceback
            error_details = traceback.format_exc()
            print(f"Download error: {str(e)}\n{error_details}")
            
            return Response(
                {'error': f'Failed to create ZIP archive: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get the parsing job status for a specific MCAP log.",
        responses={
            200: openapi.Response(
                description="Job status information",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'log_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'parse_status': openapi.Schema(type=openapi.TYPE_STRING, description="pending, processing, completed, or error"),
                        'parse_task_id': openapi.Schema(type=openapi.TYPE_STRING, description="Celery task ID"),
                        'task_state': openapi.Schema(type=openapi.TYPE_STRING, description="Celery task state: PENDING, STARTED, SUCCESS, FAILURE, RETRY"),
                        'task_info': openapi.Schema(type=openapi.TYPE_OBJECT, description="Additional task information"),
                    }
                )
            ),
            404: openapi.Response(description="Log not found"),
        },
        tags=['MCAP Logs']
    )
    @action(detail=True, methods=['get'], url_path='job-status')
    def job_status(self, request, pk=None):
        """
        Get the parsing job status for a specific MCAP log.
        Returns both the database parse_status and Celery task status.
        """
        mcap_log = self.get_object()
        
        response_data = {
            'log_id': mcap_log.id,
            'file_name': mcap_log.file_name,
            'parse_status': mcap_log.parse_status,
            'parse_task_id': mcap_log.parse_task_id,
        }
        
        # If there's a task ID, get detailed Celery task status
        if mcap_log.parse_task_id:
            try:
                task_result = AsyncResult(mcap_log.parse_task_id)
                response_data['task_state'] = task_result.state
                response_data['task_info'] = {
                    'ready': task_result.ready(),
                    'successful': task_result.successful() if task_result.ready() else None,
                    'failed': task_result.failed() if task_result.ready() else None,
                }
                
                # Add result or error if available
                if task_result.ready():
                    if task_result.successful():
                        response_data['task_info']['result'] = task_result.result
                    elif task_result.failed():
                        response_data['task_info']['error'] = str(task_result.info)
            except Exception as e:
                response_data['task_info'] = {'error': f'Could not fetch task status: {str(e)}'}
        else:
            response_data['task_state'] = None
            response_data['task_info'] = {'message': 'No task ID available'}
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        method='post',
        operation_description="Upload multiple MCAP files at once. Each file will be processed in the background.",
        manual_parameters=[
            openapi.Parameter(
                'files',
                openapi.IN_FORM,
                description="Multiple MCAP files to upload",
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_FILE),
                required=True,
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of created MCAP log records with their job statuses",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT)
                        ),
                    }
                )
            ),
            400: openapi.Response(description="No files provided"),
        },
        tags=['MCAP Logs']
    )
    @action(detail=False, methods=['post'], url_path='batch-upload')
    def batch_upload(self, request):
        """
        Upload multiple MCAP files at once.
        Each file will create a database record and trigger a background parsing job.
        Returns a list of created records with their job statuses.
        """
        # Get all uploaded files
        uploaded_files = request.FILES.getlist('files')
        
        if not uploaded_files:
            return Response(
                {'error': 'No files provided. Use multipart/form-data with "files" field containing one or more files.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = []
        media_dir = settings.MEDIA_ROOT / 'mcap_logs'
        media_dir.mkdir(parents=True, exist_ok=True)
        
        for uploaded_file in uploaded_files:
            try:
                # Generate unique filename
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                file_name = f"{timestamp}_{uploaded_file.name}"
                file_path = media_dir / file_name
                
                # Save the uploaded file
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                saved_file_path = str(file_path)
                
                # Calculate file size
                file_size = file_path.stat().st_size
                
                # Create database record
                mcap_log = McapLog.objects.create(
                    file_name=uploaded_file.name,
                    original_uri=f"{settings.MEDIA_URL}mcap_logs/{file_name}",
                    file_size=file_size,
                    parse_status="pending",
                    recovery_status="pending",
                )
                
                # Trigger background parsing job
                task = parse_mcap_file.delay(mcap_log.id, saved_file_path)
                mcap_log.parse_task_id = task.id
                mcap_log.save(update_fields=['parse_task_id'])
                
                # Serialize the result
                serializer = self.get_serializer(mcap_log)
                results.append(serializer.data)
                
            except Exception as e:
                # If one file fails, continue with others
                results.append({
                    'file_name': uploaded_file.name if uploaded_file else 'unknown',
                    'error': str(e),
                    'parse_status': 'error'
                })
        
        return Response({
            'count': len(results),
            'results': results
        }, status=status.HTTP_201_CREATED)
    
    @swagger_auto_schema(
        method='get',
        operation_description="Get parsing job statuses for all MCAP logs. Optionally filter by status.",
        manual_parameters=[
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Filter by parse status (pending, processing, completed, or error:*)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of job statuses",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT)
                        ),
                    }
                )
            ),
        },
        tags=['MCAP Logs']
    )
    @action(detail=False, methods=['get'], url_path='job-statuses')
    def job_statuses(self, request):
        """
        Get parsing job statuses for all MCAP logs.
        Optionally filter by parse_status query parameter.
        """
        queryset = McapLog.objects.all()
        
        # Filter by status if provided
        status_filter = request.query_params.get('status', None)
        if status_filter:
            if status_filter.startswith('error'):
                # Match any error status
                queryset = queryset.filter(parse_status__startswith='error')
            else:
                queryset = queryset.filter(parse_status=status_filter)
        
        # Order by created_at descending (newest first)
        queryset = queryset.order_by('-created_at')
        
        # Build response with job statuses
        results = []
        for mcap_log in queryset:
            try:
                job_data = {
                    'log_id': mcap_log.id,
                    'file_name': mcap_log.file_name,
                    'parse_status': mcap_log.parse_status,
                    'parse_task_id': mcap_log.parse_task_id,
                    'created_at': mcap_log.created_at.isoformat() if mcap_log.created_at else None,
                }
                
                # Get Celery task status if task ID exists
                if mcap_log.parse_task_id:
                    try:
                        task_result = AsyncResult(mcap_log.parse_task_id)
                        job_data['task_state'] = task_result.state
                        job_data['task_ready'] = task_result.ready()
                    except Exception as e:
                        # If we can't get task status, still include the record
                        job_data['task_state'] = 'UNKNOWN'
                        job_data['task_error'] = str(e)
                else:
                    job_data['task_state'] = None
                
                results.append(job_data)
            except Exception as e:
                # If there's an error processing a single record, log it but continue
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing log {mcap_log.id}: {str(e)}")
                # Still add a basic record
                results.append({
                    'log_id': mcap_log.id,
                    'file_name': getattr(mcap_log, 'file_name', 'unknown'),
                    'parse_status': getattr(mcap_log, 'parse_status', 'unknown'),
                    'error': str(e)
                })
        
        return Response({
            'count': len(results),
            'results': results
        }, status=status.HTTP_200_OK)


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
