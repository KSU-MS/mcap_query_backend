# MCAP Query Backend API Documentation

A Django REST Framework API for managing and querying Formula SAE telemetry logs recorded in the `.mcap` format.

## Base URL

- **Development**: `http://localhost:8000`
- **API Prefix**: `/api/`

## Authentication

Currently, the API does not require authentication. (Add authentication as needed for production.)

---

## Table of Contents

- [MCAP Logs Endpoints](#mcap-logs-endpoints)
- [Reference Data Endpoints](#reference-data-endpoints)
- [Parsing Endpoints](#parsing-endpoints)
- [Query Parameters & Filtering](#query-parameters--filtering)
- [Pagination](#pagination)
- [Response Formats](#response-formats)

---

## MCAP Logs Endpoints

### List MCAP Logs

**GET** `/api/mcap-logs/`

Returns a paginated list of MCAP logs with optional filtering.

**Query Parameters:** See [Query Parameters & Filtering](#query-parameters--filtering) section.

**Example Request:**
```bash
GET /api/mcap-logs/?search=race&car_id=1&page=1
```

**Example Response:**
```json
{
  "count": 45,
  "next": "http://localhost:8000/api/mcap-logs/?search=race&car_id=1&page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "file_name": "race_log.mcap",
      "created_at": "2025-01-15T10:30:00Z",
      "parse_status": "completed",
      "recovery_status": "completed",
      "captured_at": "2025-01-15T08:00:00Z",
      "duration_seconds": 3600.5,
      "channel_count": 25,
      "channels": ["topic1", "topic2", ...],
      "car": {"id": 1, "name": "Car A"},
      "driver": {"id": 2, "name": "John Doe"},
      "event_type": {"id": 1, "name": "Race"},
      "notes": "Test session notes",
      ...
    }
  ]
}
```

---

### Get Single MCAP Log

**GET** `/api/mcap-logs/{id}/`

Returns detailed information about a specific MCAP log.

**Example Request:**
```bash
GET /api/mcap-logs/1/
```

**Example Response:**
```json
{
  "id": 1,
  "file_name": "race_log.mcap",
  "created_at": "2025-01-15T10:30:00Z",
  "original_uri": "/media/mcap_logs/20250115_103000_race_log.mcap",
  "recovered_uri": "/media/mcap_logs/recovered_race_log.mcap",
  "recovery_status": "completed",
  "parse_status": "completed",
  "parse_task_id": "abc123-def456-...",
  "captured_at": "2025-01-15T08:00:00Z",
  "start_time": 1705312800.0,
  "end_time": 1705316400.5,
  "duration_seconds": 3600.5,
  "channel_count": 25,
  "channels": ["evelogger_vectornav_position_data", "topic2", ...],
  "file_size": 104857600,
  "car": {"id": 1, "name": "Car A"},
  "driver": {"id": 2, "name": "John Doe"},
  "event_type": {"id": 1, "name": "Race"},
  "notes": "Test session notes"
}
```

---

### Create/Upload MCAP Log

**POST** `/api/mcap-logs/`

Upload a new MCAP file. The file will be automatically parsed in the background.

**Request Body (multipart/form-data):**
- `file` (file, optional): MCAP file to upload
- `file_name` (string, optional): Custom file name
- `car_id` (integer, optional): Car ID
- `driver_id` (integer, optional): Driver ID
- `event_type_id` (integer, optional): Event type ID
- `notes` (string, optional): Notes about the log

**Example Request:**
```bash
POST /api/mcap-logs/
Content-Type: multipart/form-data

file: [binary MCAP file]
car_id: 1
driver_id: 2
event_type_id: 1
notes: "Race session from January 15"
```

**Example Response:**
```json
{
  "id": 1,
  "file_name": "race_log.mcap",
  "parse_status": "pending",
  "parse_task_id": "abc123-def456-...",
  ...
}
```

---

### Update MCAP Log

**PATCH** `/api/mcap-logs/{id}/`

Update metadata for an existing MCAP log (tags, notes, etc.). Cannot update file or parsed data.

**Request Body (JSON):**
```json
{
  "car_id": 1,
  "driver_id": 2,
  "event_type_id": 1,
  "notes": "Updated notes"
}
```

**Example Request:**
```bash
PATCH /api/mcap-logs/1/
Content-Type: application/json

{
  "notes": "Updated session notes"
}
```

---

### Delete MCAP Log

**DELETE** `/api/mcap-logs/{id}/`

Delete a MCAP log record and associated file.

**Example Request:**
```bash
DELETE /api/mcap-logs/1/
```

**Response:** `204 No Content`

---

### Get GPS Path as GeoJSON

**GET** `/api/mcap-logs/{id}/geojson/`

Returns the GPS lap path as GeoJSON LineString. Optionally simplifies the path using PostGIS.

**Query Parameters:**
- `simplify` (boolean, optional): Enable path simplification (default: `false`)
- `tolerance` (float, optional): Simplification tolerance in degrees (default: `0.00001`, ~1.1 meters)

**Example Request:**
```bash
GET /api/mcap-logs/1/geojson/?simplify=true&tolerance=0.0001
```

**Example Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-122.5, 37.7],
          [-122.4, 37.8],
          ...
        ]
      },
      "properties": {
        "type": "lap_path",
        "id": 1,
        "simplified": true
      }
    }
  ]
}
```

---

### Get Parsing Job Status

**GET** `/api/mcap-logs/{id}/job-status/`

Get the status of the background parsing job for a specific log.

**Example Request:**
```bash
GET /api/mcap-logs/1/job-status/
```

**Example Response:**
```json
{
  "log_id": 1,
  "file_name": "race_log.mcap",
  "parse_status": "completed",
  "parse_task_id": "abc123-def456-...",
  "task_state": "SUCCESS",
  "task_info": {
    "ready": true,
    "successful": true,
    "failed": false,
    "result": "Successfully parsed MCAP file for log 1"
  }
}
```

**Task States:**
- `PENDING`: Task is queued
- `STARTED`: Task is running
- `SUCCESS`: Task completed successfully
- `FAILURE`: Task failed
- `RETRY`: Task is being retried

---

### Download Multiple Logs as ZIP

**POST** `/api/mcap-logs/download/`

Download multiple MCAP log files as a ZIP archive.

**Request Body (JSON):**
```json
{
  "ids": [1, 2, 3]
}
```

**Example Request:**
```bash
POST /api/mcap-logs/download/
Content-Type: application/json

{
  "ids": [1, 2, 3]
}
```

**Response:** Binary ZIP file with `Content-Type: application/zip`

**Response Headers:**
- `Content-Disposition: attachment; filename="mcap_logs_20250115_103000.zip"`
- `X-Missing-Files`: Comma-separated list of files that couldn't be added (if any)

---

### Batch Upload Multiple Files

**POST** `/api/mcap-logs/batch-upload/`

Upload multiple MCAP files at once. Each file will be processed in the background.

**Request Body (multipart/form-data):**
- `files` (file[], required): Array of MCAP files

**Example Request:**
```bash
POST /api/mcap-logs/batch-upload/
Content-Type: multipart/form-data

files: [file1.mcap, file2.mcap, file3.mcap]
```

**Example Response:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "file_name": "file1.mcap",
      "parse_status": "pending",
      ...
    },
    ...
  ]
}
```

---

### Get All Job Statuses

**GET** `/api/mcap-logs/job-statuses/`

Get parsing job statuses for all MCAP logs, optionally filtered by status.

**Query Parameters:**
- `status` (string, optional): Filter by parse status (e.g., `pending`, `completed`, `error:*`)

**Example Request:**
```bash
GET /api/mcap-logs/job-statuses/?status=completed
```

**Example Response:**
```json
{
  "count": 10,
  "results": [
    {
      "log_id": 1,
      "file_name": "race_log.mcap",
      "parse_status": "completed",
      "parse_task_id": "abc123-...",
      "created_at": "2025-01-15T10:30:00Z",
      "task_state": "SUCCESS",
      "task_ready": true
    },
    ...
  ]
}
```

---

## Reference Data Endpoints

### Cars

**GET** `/api/cars/`

List all cars (read-only).

**Example Response:**
```json
[
  {"id": 1, "name": "Car A"},
  {"id": 2, "name": "Car B"}
]
```

**GET** `/api/cars/{id}/`

Get a specific car.

---

### Drivers

**GET** `/api/drivers/`

List all drivers (read-only).

**Example Response:**
```json
[
  {"id": 1, "name": "John Doe"},
  {"id": 2, "name": "Jane Smith"}
]
```

**GET** `/api/drivers/{id}/`

Get a specific driver.

---

### Event Types

**GET** `/api/event-types/`

List all event types (read-only).

**Example Response:**
```json
[
  {"id": 1, "name": "Race"},
  {"id": 2, "name": "Practice"},
  {"id": 3, "name": "Qualifying"}
]
```

**GET** `/api/event-types/{id}/`

Get a specific event type.

---

## Parsing Endpoints

### Parse MCAP Summary (No DB Record)

**POST** `/api/parse/summary/`

Parse an MCAP file summary without creating a database record. Useful for previewing file contents before upload.

**Request Body (JSON):**
```json
{
  "path": "/path/to/file.mcap"
}
```

**Example Request:**
```bash
POST /api/parse/summary/
Content-Type: application/json

{
  "path": "/Users/pettruskonnoth/Documents/mcap_logs/race.mcap"
}
```

**Example Response:**
```json
{
  "channels": ["topic1", "topic2", ...],
  "channel_count": 25,
  "start_time": 1705312800.0,
  "end_time": 1705316400.5,
  "duration": 3600.5,
  "formatted_date": "2025-01-15 08:00:00",
  "latitude": 37.7749,
  "longitude": -122.4194
}
```

---

## Query Parameters & Filtering

All query parameters are **optional** and can be **combined**. Use them with the `GET /api/mcap-logs/` endpoint.

### Text Search

**`search`** (string)

Search in `file_name` and `notes` fields (case-insensitive partial match).

**Example:**
```
GET /api/mcap-logs/?search=race
```

Finds logs with "race" in filename or notes.

---

### Date Range Filtering

**`start_date`** (string, format: `YYYY-MM-DD`)

Filter logs captured on or after this date (inclusive, start of day).

**`end_date`** (string, format: `YYYY-MM-DD`)

Filter logs captured on or before this date (inclusive, end of day).

**Example:**
```
GET /api/mcap-logs/?start_date=2025-01-01&end_date=2025-01-31
```

---

### Foreign Key Filtering

**`car_id`** (integer)

Filter by car ID.

**`driver_id`** (integer)

Filter by driver ID.

**`event_type_id`** (integer)

Filter by event type ID.

**Example:**
```
GET /api/mcap-logs/?car_id=1&driver_id=2&event_type_id=1
```

---

### Status Filtering

**`parse_status`** (string)

Filter by parse status. Common values:
- `pending`: Not yet parsed
- `processing`: Currently being parsed
- `completed`: Successfully parsed
- `error:*`: Parsing failed (error message included)

**`recovery_status`** (string)

Filter by recovery status. Common values:
- `pending`: Not yet recovered
- `completed`: Successfully recovered
- `failed`: Recovery failed

**Example:**
```
GET /api/mcap-logs/?parse_status=completed&recovery_status=completed
```

---

### Geographic Location Filtering

**`location`** (string, format: `min_lon,min_lat,max_lon,max_lat`)

Filter logs by geographic bounding box. Returns logs whose GPS path (`lap_path`) intersects with the bounding box.

**Example:**
```
GET /api/mcap-logs/?location=-122.5,37.7,-122.3,37.9
```

This filters logs that have GPS coordinates within the San Francisco Bay Area bounding box.

**Note:** Requires PostGIS and logs with parsed GPS data (`lap_path` field).

---

### Combined Filtering Example

You can combine multiple filters:

```
GET /api/mcap-logs/?search=race&start_date=2025-01-01&car_id=1&parse_status=completed&page=1
```

This will:
1. Search for "race" in filename/notes
2. Filter by date range (January 2025)
3. Filter by car ID = 1
4. Only show completed logs
5. Return page 1 of results

---

## Pagination

All list endpoints support pagination. The default page size is **10 items per page**.

### Query Parameters

**`page`** (integer, default: `1`)

Page number to retrieve.

**Example:**
```
GET /api/mcap-logs/?page=2
```

### Response Format

Paginated responses include:

- `count`: Total number of items (across all pages)
- `next`: URL to next page (or `null` if last page)
- `previous`: URL to previous page (or `null` if first page)
- `results`: Array of items for current page

**Example:**
```json
{
  "count": 45,
  "next": "http://localhost:8000/api/mcap-logs/?page=2",
  "previous": null,
  "results": [...]
}
```

**Note:** Filter parameters are automatically preserved in `next` and `previous` URLs.

---

## Response Formats

### Success Responses

- **200 OK**: Successful GET request
- **201 Created**: Successful POST request (resource created)
- **204 No Content**: Successful DELETE request

### Error Responses

- **400 Bad Request**: Invalid request data or parameters
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error

**Error Response Format:**
```json
{
  "error": "Error message description"
}
```

---

## API Documentation (Swagger/ReDoc)

Interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/swagger/`
- **ReDoc**: `http://localhost:8000/redoc/`
- **OpenAPI Schema (JSON)**: `http://localhost:8000/swagger.json`
- **OpenAPI Schema (YAML)**: `http://localhost:8000/swagger.yaml`

---

## Notes

- All timestamps are in UTC
- File uploads are saved to `MEDIA_ROOT/mcap_logs/`
- Parsing happens asynchronously via Celery (check job status endpoints)
- GPS coordinates are stored as `(longitude, latitude)` in GeoJSON format
- Invalid query parameters are silently ignored (no error thrown)

---

*Last updated: January 2025*

