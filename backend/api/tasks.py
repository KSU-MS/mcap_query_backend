"""
Background tasks for MCAP log processing.
"""
from celery import shared_task
from django.contrib.gis.geos import LineString
from django.utils import timezone
from django.conf import settings
from pathlib import Path
import datetime
from .models import McapLog
from .parser import Parser
from .gpsparse import GpsParser
from .mcap_converter import McapToCsvConverter


@shared_task(bind=True, max_retries=3)
def parse_mcap_file(self, mcap_log_id, file_path):
    """
    Background task to parse an MCAP file and update the database record.
    
    Args:
        mcap_log_id: The ID of the McapLog record to update
        file_path: Path to the MCAP file to parse
    """
    try:
        mcap_log = McapLog.objects.get(id=mcap_log_id)
        
        # Update parse status to processing
        mcap_log.parse_status = "processing"
        mcap_log.save(update_fields=['parse_status'])
        
        # Parse the MCAP file
        parsed_data = Parser.parse_stuff(file_path)
        
        # Update fields from parsed data
        mcap_log.channels = parsed_data.get("channels", [])
        mcap_log.channel_count = parsed_data.get("channel_count", 0)
        mcap_log.start_time = parsed_data.get("start_time")
        mcap_log.end_time = parsed_data.get("end_time")
        mcap_log.duration_seconds = parsed_data.get("duration", 0)
        
        # Parse GPS coordinates from the file
        gps_data = GpsParser.parse_gps(file_path)
        all_coordinates = gps_data.get("all_coordinates", [])
        
        # Create LineString from all GPS coordinates for map preview
        if all_coordinates:
            mcap_log.lap_path = LineString(all_coordinates, srid=4326)
        
        # Set captured_at from start_time
        if parsed_data.get("start_time"):
            naive_dt = datetime.datetime.fromtimestamp(parsed_data.get("start_time"))
            mcap_log.captured_at = timezone.make_aware(naive_dt)
        
        # Mark as completed
        mcap_log.parse_status = "completed"
        mcap_log.save()
        
        return f"Successfully parsed MCAP file for log {mcap_log_id}"
        
    except McapLog.DoesNotExist:
        return f"McapLog with id {mcap_log_id} does not exist"
    except Exception as e:
        # Update parse status with error
        try:
            mcap_log = McapLog.objects.get(id=mcap_log_id)
            mcap_log.parse_status = f"error: {str(e)}"
            mcap_log.save(update_fields=['parse_status'])
        except:
            pass
        
        # Retry the task if it's a retryable error
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return f"Error parsing MCAP file: {str(e)}"


@shared_task(bind=True, max_retries=3)
def convert_mcap_to_csv(self, mcap_log_id, format='omni'):
    """
    Background task to convert an MCAP file to CSV format.
    
    Args:
        mcap_log_id: The ID of the McapLog record to convert
        format: CSV format profile ('omni' or 'tvn')
        
    Returns:
        Path to the converted CSV file
    """
    try:
        mcap_log = McapLog.objects.get(id=mcap_log_id)
        
        # Determine source file path
        file_path = None
        
        # Try recovered_uri first if available and not pending
        if mcap_log.recovered_uri and mcap_log.recovered_uri != "pending":
            if mcap_log.recovered_uri.startswith(settings.MEDIA_URL):
                file_name = mcap_log.recovered_uri.replace(settings.MEDIA_URL, '', 1)
                file_path = Path(settings.MEDIA_ROOT) / file_name
            elif mcap_log.recovered_uri.startswith('/'):
                file_path = Path(mcap_log.recovered_uri)
            else:
                file_path = Path(settings.MEDIA_ROOT) / mcap_log.recovered_uri
        
        # Fall back to original_uri if recovered_uri not available
        if not file_path or not file_path.exists():
            if mcap_log.original_uri:
                if mcap_log.original_uri.startswith(settings.MEDIA_URL):
                    file_name = mcap_log.original_uri.replace(settings.MEDIA_URL, '', 1)
                    file_path = Path(settings.MEDIA_ROOT) / file_name
                elif mcap_log.original_uri.startswith('/'):
                    file_path = Path(mcap_log.original_uri)
                else:
                    file_path = Path(settings.MEDIA_ROOT) / mcap_log.original_uri
        
        if not file_path or not file_path.exists():
            raise FileNotFoundError(f"MCAP file not found for log {mcap_log_id}")
        
        file_path = file_path.resolve()
        
        # Create output directory for converted files
        converted_dir = Path(settings.MEDIA_ROOT) / 'converted'
        converted_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        format_suffix = format.replace('csv_', '') if format.startswith('csv_') else format
        output_filename = f"{mcap_log_id}_{format_suffix}_{timestamp}.csv"
        output_path = converted_dir / output_filename
        
        # Convert MCAP to CSV
        converter = McapToCsvConverter()
        converter.convert_to_csv(str(file_path), str(output_path), format=format_suffix)
        
        # Return the path relative to MEDIA_ROOT for easy access
        relative_path = output_path.relative_to(settings.MEDIA_ROOT)
        return str(relative_path)
        
    except McapLog.DoesNotExist:
        return f"McapLog with id {mcap_log_id} does not exist"
    except Exception as e:
        # Retry the task if it's a retryable error
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return f"Error converting MCAP file to CSV: {str(e)}"

