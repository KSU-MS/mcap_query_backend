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

