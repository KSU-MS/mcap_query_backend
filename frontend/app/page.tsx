'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import 'leaflet/dist/leaflet.css';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, Download } from 'lucide-react';

// Map Preview Component - small preview for table rows
const MapPreview = dynamic(
  () => {
    return Promise.resolve().then(() => {
      const React = require('react');
      const L = require('leaflet');
      const { MapContainer, TileLayer, GeoJSON, useMap } = require('react-leaflet');

      // Fix for default marker icons in Next.js
      if (typeof window !== 'undefined') {
        delete (L.Icon.Default.prototype as any)._getIconUrl;
        L.Icon.Default.mergeOptions({
          iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
          iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
          shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
        });
      }

      const FitBounds = ({ geoJsonData }: { geoJsonData: any }) => {
        const map = useMap();
        React.useEffect(() => {
          if (geoJsonData && map) {
            try {
              const geoJsonLayer = L.geoJSON(geoJsonData as any);
              const bounds = geoJsonLayer.getBounds();
              if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [5, 5] });
              }
            } catch (err) {
              // Silently fail for preview
            }
          }
        }, [geoJsonData, map]);
        return null;
      };

      return ({ logId, apiBaseUrl, onMapClick }: { logId: number; apiBaseUrl: string; onMapClick?: (logId: number) => void }) => {
      const [geoJsonData, setGeoJsonData] = React.useState<any>(null);
      const [loading, setLoading] = React.useState(true);
      const [mounted, setMounted] = React.useState(false);
      const [containerReady, setContainerReady] = React.useState(false);

      React.useEffect(() => {
        // Use a small delay to ensure DOM is ready
        const timer = setTimeout(() => {
          setMounted(true);
        }, 100);
        return () => clearTimeout(timer);
      }, []);

      // Check if container is ready after mount
      React.useEffect(() => {
        if (mounted) {
          // Additional small delay to ensure container is in DOM
          const timer = setTimeout(() => {
            setContainerReady(true);
          }, 50);
          return () => clearTimeout(timer);
        }
      }, [mounted]);

      React.useEffect(() => {
        if (!mounted) return;
        
        let cancelled = false;
        const fetchGeoJson = async () => {
          try {
            const response = await fetch(`${apiBaseUrl}/mcap-logs/${logId}/geojson`);
            if (!response.ok) {
              throw new Error('Failed to fetch');
            }
            const data = await response.json();
            if (!cancelled) {
              setGeoJsonData(data);
            }
          } catch (err) {
            // Silently fail for preview
          } finally {
            if (!cancelled) {
              setLoading(false);
            }
          }
        };

        fetchGeoJson();
        return () => {
          cancelled = true;
        };
      }, [logId, apiBaseUrl, mounted]);

      const geoJsonStyle = {
        color: '#3388ff',
        weight: 2,
        opacity: 0.8,
        fillOpacity: 0.2,
      };

      const pointToLayer = (feature: any, latlng: L.LatLng) => {
        return L.circleMarker(latlng, {
          radius: 3,
          fillColor: '#3388ff',
          color: '#fff',
          weight: 1,
          opacity: 1,
          fillOpacity: 0.8,
        });
      };

      // Calculate center from GeoJSON if available
      let center: [number, number] = [0, 0];
      if (geoJsonData?.features?.[0]?.geometry?.coordinates) {
        const coords = geoJsonData.features[0].geometry.coordinates;
        if (geoJsonData.features[0].geometry.type === 'Point') {
          center = [coords[1], coords[0]];
        } else if (geoJsonData.features[0].geometry.type === 'LineString' && coords.length > 0) {
          center = [coords[0][1], coords[0][0]];
        }
      }

      if (!mounted) {
        return (
          <div className="w-full h-24 bg-gray-100 rounded flex items-center justify-center">
            <span className="text-xs text-gray-500">Loading...</span>
          </div>
        );
      }

      if (loading) {
        return (
          <div className="w-full h-24 bg-gray-100 rounded flex items-center justify-center">
            <span className="text-xs text-gray-500">Loading...</span>
          </div>
        );
      }

      if (!geoJsonData) {
        return (
          <div className="w-full h-24 bg-gray-100 rounded flex items-center justify-center">
            <span className="text-xs text-gray-500">No map data</span>
          </div>
        );
      }

      return (
        <div 
          className="w-full h-24 rounded overflow-hidden border border-gray-200 cursor-pointer hover:border-purple-500 transition-colors"
          onClick={() => onMapClick?.(logId)}
          title="Click to view full map"
        >
          {mounted && containerReady ? (
          <MapContainer
            center={center}
            zoom={13}
            style={{ height: '100%', width: '100%', zIndex: 0 }}
            scrollWheelZoom={false}
            zoomControl={false}
            dragging={false}
            doubleClickZoom={false}
            boxZoom={false}
            touchZoom={false}
              key={`map-${logId}-${mounted}`}
          >
            <TileLayer
              attribution=""
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <GeoJSON
              data={geoJsonData}
              style={geoJsonStyle}
              pointToLayer={pointToLayer}
            />
            <FitBounds geoJsonData={geoJsonData} />
          </MapContainer>
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <span className="text-xs text-gray-500">Loading map...</span>
            </div>
          )}
        </div>
      );
      };
    });
  },
  { ssr: false }
);

// Map Component - dynamically imported to avoid SSR issues
const MapComponent = dynamic(
  () => {
    return Promise.resolve().then(() => {
      const React = require('react');
      const L = require('leaflet');
      const { MapContainer, TileLayer, GeoJSON, useMap } = require('react-leaflet');

      // Fix for default marker icons in Next.js
      if (typeof window !== 'undefined') {
        delete (L.Icon.Default.prototype as any)._getIconUrl;
        L.Icon.Default.mergeOptions({
          iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
          iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
          shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
        });
      }

      const FitBounds = ({ geoJsonData }: { geoJsonData: any }) => {
        const map = useMap();
        React.useEffect(() => {
          if (geoJsonData && map) {
            try {
              const geoJsonLayer = L.geoJSON(geoJsonData as any);
              const bounds = geoJsonLayer.getBounds();
              if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [20, 20] });
              }
            } catch (err) {
              console.error('Error fitting bounds:', err);
            }
          }
        }, [geoJsonData, map]);
        return null;
      };

      return ({ geoJsonData }: { geoJsonData: any }) => {
        const [mounted, setMounted] = React.useState(false);

        React.useEffect(() => {
          setMounted(true);
        }, []);

        const geoJsonStyle = {
          color: '#3388ff',
          weight: 3,
          opacity: 0.8,
          fillOpacity: 0.2,
        };

        const pointToLayer = (feature: any, latlng: L.LatLng) => {
          return L.circleMarker(latlng, {
            radius: 6,
            fillColor: '#3388ff',
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8,
          });
        };

        const onEachFeature = (feature: any, layer: L.Layer) => {
          if (feature.properties) {
            const popupContent = Object.keys(feature.properties)
              .map((key) => `<strong>${key}:</strong> ${feature.properties[key]}`)
              .join('<br>');
            layer.bindPopup(popupContent);
          }
        };

        // Calculate center from GeoJSON if available
        let center: [number, number] = [0, 0];
        if (geoJsonData?.features?.[0]?.geometry?.coordinates) {
          const coords = geoJsonData.features[0].geometry.coordinates;
          if (geoJsonData.features[0].geometry.type === 'Point') {
            center = [coords[1], coords[0]];
          } else if (geoJsonData.features[0].geometry.type === 'LineString' && coords.length > 0) {
            center = [coords[0][1], coords[0][0]];
          }
        }

        if (!mounted) {
          return (
            <div className="w-full h-full flex items-center justify-center">
              <span className="text-zinc-500">Loading map...</span>
            </div>
          );
        }

        return (
          <div className="w-full h-full">
            <MapContainer
              center={center}
              zoom={13}
              style={{ height: '100%', width: '100%', zIndex: 0 }}
              scrollWheelZoom={true}
              key={`fullmap-${mounted}`}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {geoJsonData && (
                <GeoJSON
                  data={geoJsonData}
                  style={geoJsonStyle}
                  pointToLayer={pointToLayer}
                  onEachFeature={onEachFeature}
                />
              )}
              <FitBounds geoJsonData={geoJsonData} />
            </MapContainer>
          </div>
        );
      };
    });
  },
  { ssr: false }
);

interface McapLog {
  id: number;
  recovery_status?: string;
  parse_status?: string;
  captured_at?: string;
  duration_seconds?: number;
  channel_count?: number;
  channels?: string[];
  channels_summary?: string[];
  rough_point?: string;
  car?: string | { id: number; name: string };
  driver?: string | { id: number; name: string };
  event_type?: string | { id: number; name: string };
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

const API_BASE_URL = 'http://127.0.0.1:8000';

export default function Home() {
  const [logs, setLogs] = useState<McapLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedLog, setSelectedLog] = useState<McapLog | null>(null);
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [logToDelete, setLogToDelete] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    car: '',
    driver: '',
    event_type: '',
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [loadingLog, setLoadingLog] = useState(false);
  const [isMapModalOpen, setIsMapModalOpen] = useState(false);
  const [geoJsonData, setGeoJsonData] = useState<any>(null);
  const [loadingGeoJson, setLoadingGeoJson] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [downloading, setDownloading] = useState<number | null>(null);
  const [selectedLogIds, setSelectedLogIds] = useState<number[]>([]);
  const [isDownloadDialogOpen, setIsDownloadDialogOpen] = useState(false);
  const [downloadFormat, setDownloadFormat] = useState<'mcap' | 'csv_omni' | 'csv_tvn' | 'ld'>('mcap');
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [bulkDownloadError, setBulkDownloadError] = useState<string | null>(null);
  const [cars, setCars] = useState<{ id: number; name: string }[]>([]);
  const [drivers, setDrivers] = useState<{ id: number; name: string }[]>([]);
  const [eventTypes, setEventTypes] = useState<{ id: number; name: string }[]>([]);
  const [loadingLookups, setLoadingLookups] = useState(false);

  // Fetch cars, drivers, and event types for dropdowns
  const fetchLookups = async () => {
    setLoadingLookups(true);
    try {
      // Fetch cars
      try {
        const carsResponse = await fetch(`${API_BASE_URL}/cars/`);
        if (carsResponse.ok) {
          const carsData = await carsResponse.json();
          // Handle paginated response (DRF returns {results: [...]}) or direct array
          const carsArray = Array.isArray(carsData) ? carsData : (carsData.results || []);
          setCars(carsArray);
        }
      } catch (err) {
        console.warn('Failed to fetch cars:', err);
      }

      // Fetch drivers
      try {
        const driversResponse = await fetch(`${API_BASE_URL}/drivers/`);
        if (driversResponse.ok) {
          const driversData = await driversResponse.json();
          // Handle paginated response (DRF returns {results: [...]}) or direct array
          const driversArray = Array.isArray(driversData) ? driversData : (driversData.results || []);
          setDrivers(driversArray);
        }
      } catch (err) {
        console.warn('Failed to fetch drivers:', err);
      }

      // Fetch event types
      try {
        const eventTypesResponse = await fetch(`${API_BASE_URL}/event-types/`);
        if (eventTypesResponse.ok) {
          const eventTypesData = await eventTypesResponse.json();
          // Handle paginated response (DRF returns {results: [...]}) or direct array
          const eventTypesArray = Array.isArray(eventTypesData) ? eventTypesData : (eventTypesData.results || []);
          setEventTypes(eventTypesArray);
        }
      } catch (err) {
        console.warn('Failed to fetch event types:', err);
      }
    } catch (err) {
      console.error('Error fetching lookups:', err);
    } finally {
      setLoadingLookups(false);
    }
  };

  // Fetch logs from the API
  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const allLogs: McapLog[] = [];
      let url: string | null = `${API_BASE_URL}/mcap-logs/`;

      while (url) {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch logs: ${response.statusText}`);
        }
        const data = await response.json();

        if (Array.isArray(data)) {
          allLogs.push(...data);
          url = null;
        } else if (data?.results) {
          allLogs.push(...data.results);
          url = data.next;
        } else {
          // Unknown shape; stop
          url = null;
        }
      }

      setLogs(allLogs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs');
      console.error('Error fetching logs:', err);
    } finally {
      setLoading(false);
    }
  };

  // Upload file
  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file first');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch(`${API_BASE_URL}/mcap-logs/`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || errorData.message || `Upload failed: ${response.statusText}`
        );
      }

      // Clear selected file and refresh logs
      setSelectedFile(null);
      await fetchLogs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload file');
      console.error('Error uploading file:', err);
    } finally {
      setUploading(false);
    }
  };

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.name.endsWith('.mcap')) {
        setSelectedFile(file);
        setError(null);
      } else {
        setError('Please select a .mcap file');
        setSelectedFile(null);
      }
    }
  };

  // Fetch a specific log by ID
  const fetchLog = async (id: number) => {
    setLoadingLog(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/mcap-logs/${id}/`);
      if (!response.ok) {
        throw new Error(`Failed to fetch log: ${response.statusText}`);
      }
      const data = await response.json();
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch log');
      console.error('Error fetching log:', err);
      throw err;
    } finally {
      setLoadingLog(false);
    }
  };

  // View log details
  const handleViewLog = async (id: number) => {
    try {
      const log = await fetchLog(id);
      setSelectedLog(log);
      setIsViewModalOpen(true);
    } catch (err) {
      // Error already handled in fetchLog
    }
  };

  // Helper to extract name from car/driver/event_type (handles both object and string)
  const getName = (value: string | { id: number; name: string } | undefined): string => {
    if (!value) return 'N/A';
    if (typeof value === 'string') return value;
    if (typeof value === 'object' && 'name' in value) return value.name;
    return 'N/A';
  };

  // Helper to extract ID from car/driver/event_type (handles both object and string)
  const extractId = (value: any): string => {
    if (!value) return '';
    if (typeof value === 'object' && value.id) return value.id.toString();
    if (typeof value === 'string') {
      // If it's a string, try to find matching ID from lookups
      const carMatch = cars.find(c => c.name === value);
      if (carMatch) return carMatch.id.toString();
      const driverMatch = drivers.find(d => d.name === value);
      if (driverMatch) return driverMatch.id.toString();
      const eventMatch = eventTypes.find(e => e.name === value);
      if (eventMatch) return eventMatch.id.toString();
    }
    return '';
  };

  // Open edit modal
  const handleEditLog = async (id: number) => {
    try {
      const log = await fetchLog(id);
      setSelectedLog(log);
      
      // Extract IDs - wait a bit if lookups aren't ready yet
      let carId = extractId(log.car);
      let driverId = extractId(log.driver);
      let eventId = extractId(log.event_type);
      
      // If extraction failed and lookups aren't loaded, wait and try again
      if ((!carId || !driverId || !eventId) && loadingLookups) {
        // Wait for lookups to load
        await new Promise(resolve => setTimeout(resolve, 500));
        carId = extractId(log.car);
        driverId = extractId(log.driver);
        eventId = extractId(log.event_type);
      }
      
      setEditForm({
        car: carId,
        driver: driverId,
        event_type: eventId,
        notes: log.notes || '',
      });
      setIsEditModalOpen(true);
    } catch (err) {
      // Error already handled in fetchLog
    }
  };

  // Update log (PATCH or PUT)
  const handleUpdateLog = async (id: number, usePut = false) => {
    setSaving(true);
    setError(null);

    try {
      const method = usePut ? 'PUT' : 'PATCH';
      
      // Build request body - convert IDs to numbers for car, driver, event_type
      const body: any = {
        notes: editForm.notes || '',
      };

      // Convert string IDs to numbers
      // The API expects car_id, driver_id, event_type_id (with _id suffix) for updates
      // For PATCH: only include fields that have values (don't send null)
      // For PUT: include all fields, even if null
      if (usePut) {
        // PUT requires all fields - send null if empty
        body.car_id = editForm.car && editForm.car.trim() !== '' ? Number(editForm.car) : null;
        body.driver_id = editForm.driver && editForm.driver.trim() !== '' ? Number(editForm.driver) : null;
        body.event_type_id = editForm.event_type && editForm.event_type.trim() !== '' ? Number(editForm.event_type) : null;
      } else {
        // PATCH: only include fields that have values
        if (editForm.car && editForm.car.trim() !== '') {
          const carId = Number(editForm.car);
          if (!isNaN(carId) && carId > 0) {
            body.car_id = carId;
          }
        }
        if (editForm.driver && editForm.driver.trim() !== '') {
          const driverId = Number(editForm.driver);
          if (!isNaN(driverId) && driverId > 0) {
            body.driver_id = driverId;
          }
        }
        if (editForm.event_type && editForm.event_type.trim() !== '') {
          const eventId = Number(editForm.event_type);
          if (!isNaN(eventId) && eventId > 0) {
            body.event_type_id = eventId;
          }
        }
      }

      console.log('=== UPDATE DEBUG ===');
      console.log('Log ID:', id);
      console.log('Method:', method);
      console.log('Edit form state:', editForm);
      console.log('Request body being sent:', body);
      console.log('Body JSON:', JSON.stringify(body));

      const response = await fetch(`${API_BASE_URL}/mcap-logs/${id}/`, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        let errorMessage = `Update failed: ${response.statusText}`;
        try {
          const errorData = await response.json();
          console.error('Update error response:', errorData); // Debug log
          // Handle different error response formats
          if (errorData.detail) {
            errorMessage = errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else if (typeof errorData === 'object') {
            // Handle field-specific errors
            const fieldErrors = Object.entries(errorData)
              .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
              .join('; ');
            if (fieldErrors) {
              errorMessage = fieldErrors;
            }
          }
        } catch (parseError) {
          // If JSON parsing fails, use the status text
          console.error('Error parsing error response:', parseError);
        }
        throw new Error(errorMessage);
      }

      // Get the updated log data
      const updatedData = await response.json();
      console.log('Update successful, response:', updatedData); // Debug log
      console.log('Response car:', updatedData.car);
      console.log('Response driver:', updatedData.driver);
      console.log('Response event_type:', updatedData.event_type);
      
      // Check if the update actually worked
      if (updatedData.car === null && body.car !== undefined) {
        console.warn('⚠️ WARNING: Backend returned null for car despite sending:', body.car);
        console.warn('This suggests the backend serializer may not be processing the car field in PATCH requests.');
      }
      if (updatedData.driver === null && body.driver !== undefined) {
        console.warn('⚠️ WARNING: Backend returned null for driver despite sending:', body.driver);
      }
      if (updatedData.event_type === null && body.event_type !== undefined) {
        console.warn('⚠️ WARNING: Backend returned null for event_type despite sending:', body.event_type);
      }

      // Optimistically update the logs state with the response data
      // This ensures the UI updates immediately even if fetchLogs is slow
      setLogs((prevLogs) =>
        prevLogs.map((log) =>
          log.id === id
            ? {
                ...log,
                car: updatedData.car,
                driver: updatedData.driver,
                event_type: updatedData.event_type,
                notes: updatedData.notes || log.notes,
              }
            : log
        )
      );

      setIsEditModalOpen(false);
      setSelectedLog(null);
      // Still refetch to ensure we have the latest data
      await fetchLogs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update log');
      console.error('Error updating log:', err);
    } finally {
      setSaving(false);
    }
  };

  // Delete log
  const handleDeleteLog = async (id: number) => {
    setDeleting(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/mcap-logs/${id}/`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || errorData.message || `Delete failed: ${response.statusText}`
        );
      }

      setIsDeleteModalOpen(false);
      setLogToDelete(null);
      await fetchLogs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete log');
      console.error('Error deleting log:', err);
    } finally {
      setDeleting(false);
    }
  };

  // Open delete confirmation
  const openDeleteConfirm = (id: number) => {
    setLogToDelete(id);
    setIsDeleteModalOpen(true);
  };

  // Fetch GeoJSON for a log
  const fetchGeoJson = async (id: number) => {
    setLoadingGeoJson(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/mcap-logs/${id}/geojson`);
      if (!response.ok) {
        throw new Error(`Failed to fetch GeoJSON: ${response.statusText}`);
      }
      const data = await response.json();
      setGeoJsonData(data);
      setIsMapModalOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch GeoJSON');
      console.error('Error fetching GeoJSON:', err);
    } finally {
      setLoadingGeoJson(false);
    }
  };

  // Download MCAP file
  const handleDownload = async (id: number) => {
    setDownloading(id);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/mcap-logs/${id}/download`);
      if (!response.ok) {
        throw new Error(`Failed to download file: ${response.statusText}`);
      }
      
      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `mcap-log-${id}.mcap`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download file');
      console.error('Error downloading file:', err);
    } finally {
      setDownloading(null);
    }
  };

  // Filter logs based on search query
  const filteredLogs = logs.filter((log) => {
    if (!searchQuery.trim()) return true;
    
    const query = searchQuery.toLowerCase();
    return (
      log.id.toString().includes(query) ||
      getName(log.car).toLowerCase().includes(query) ||
      getName(log.driver).toLowerCase().includes(query) ||
      getName(log.event_type).toLowerCase().includes(query) ||
      (log.notes && log.notes.toLowerCase().includes(query)) ||
      (log.recovery_status && log.recovery_status.toLowerCase().includes(query)) ||
      (log.parse_status && log.parse_status.toLowerCase().includes(query)) ||
      (log.captured_at && new Date(log.captured_at).toLocaleString().toLowerCase().includes(query))
    );
  });

  // Selection helpers
  const toggleSelectLog = (id: number) => {
    setSelectedLogIds((prev) =>
      prev.includes(id) ? prev.filter((logId) => logId !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    const allIds = filteredLogs.map((log) => log.id);
    const allSelected = allIds.every((id) => selectedLogIds.includes(id)) && allIds.length > 0;
    if (allSelected) {
      setSelectedLogIds((prev) => prev.filter((id) => !allIds.includes(id)));
    } else {
      setSelectedLogIds((prev) => Array.from(new Set([...prev, ...allIds])));
    }
  };

  const openDownloadDialog = () => {
    if (selectedLogIds.length === 0) {
      setError('Select at least one log to download');
      return;
    }
    setBulkDownloadError(null);
    setIsDownloadDialogOpen(true);
  };

  const handleBulkDownload = async () => {
    if (selectedLogIds.length === 0) {
      setBulkDownloadError('Select at least one log to download');
      return;
    }
    setBulkDownloading(true);
    setBulkDownloadError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/mcap-logs/download/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedLogIds, format: downloadFormat }),
      });

      if (!response.ok) {
        let message = `Failed to download files: ${response.statusText}`;
        try {
          const data = await response.json();
          message = data.error || message;
        } catch (_) {
          // ignore json errors
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const filename = `mcap_logs_${downloadFormat}.zip`;
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setIsDownloadDialogOpen(false);
    } catch (err) {
      setBulkDownloadError(err instanceof Error ? err.message : 'Failed to download files');
      console.error('Error downloading files:', err);
    } finally {
      setBulkDownloading(false);
    }
  };

  // Fetch logs and lookups on component mount
  useEffect(() => {
    fetchLookups();
    fetchLogs();
  }, []);

  return (
    <div className="min-h-screen bg-white py-8 px-4 sm:px-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-gray-900 mb-8">
          MCAP Log Manager
        </h1>

        {/* Upload Section */}
        <Card className="mb-8 bg-white border border-gray-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-gray-900">Upload MCAP File</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
              <label className="cursor-pointer">
              <input
                type="file"
                accept=".mcap"
                onChange={handleFileChange}
                className="hidden"
                disabled={uploading}
              />
                <Button variant="outline" className="cursor-pointer border-gray-300 text-gray-700 hover:bg-gray-50" asChild>
              <span>Select MCAP File</span>
                </Button>
            </label>

            {selectedFile && (
              <div className="flex-1">
                <p className="text-sm text-gray-600">
                  Selected: <span className="font-medium text-gray-900">{selectedFile.name}</span>
                </p>
                <p className="text-xs text-gray-500">
                  Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            )}

              <Button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
                className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              {uploading ? 'Uploading...' : 'Upload'}
              </Button>
          </div>

          {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600">{error}</p>
            </div>
          )}
          </CardContent>
        </Card>

        {/* Logs Display Section */}
        <Card className="bg-white border border-gray-200 shadow-sm">
          <CardHeader>
              <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-3">
                <CardTitle className="text-gray-900">MCAP Logs</CardTitle>
                {selectedLogIds.length > 0 && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800 border border-purple-200">
                    {selectedLogIds.length} {selectedLogIds.length === 1 ? 'file' : 'files'} selected
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={openDownloadDialog}
                  disabled={selectedLogIds.length === 0}
                  className="bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Download Selected
                  {selectedLogIds.length > 0 && (
                    <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-purple-500 text-xs font-semibold">
                      {selectedLogIds.length}
                    </span>
                  )}
                </Button>
                <Button
                onClick={fetchLogs}
                disabled={loading}
                  variant="outline"
                  className="border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                {loading ? 'Refreshing...' : 'Refresh'}
                </Button>
              </div>
          </div>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search logs by ID, car, driver, event type, notes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white border-gray-300"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>

          {loading && logs.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-600">Loading logs...</p>
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-600">
                {searchQuery ? `No logs found matching "${searchQuery}"` : 'No logs found. Upload a file to get started.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-clean">
                <thead>
                  <tr>
                    <th className="py-3 px-2 w-10">
                      <input
                        type="checkbox"
                        aria-label="Select all"
                        checked={
                          filteredLogs.length > 0 &&
                          filteredLogs.every((log) => selectedLogIds.includes(log.id))
                        }
                        onChange={toggleSelectAll}
                      />
                    </th>
                    <th>ID</th>
                    <th>Map Preview</th>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Duration</th>
                    <th>Channels</th>
                    <th>Status</th>
                    <th>Car</th>
                    <th>Driver</th>
                    <th>Event</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLogs.map((log) => (
                    <tr
                      key={log.id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="py-3 px-2">
                        <input
                          type="checkbox"
                          aria-label={`Select log ${log.id}`}
                          checked={selectedLogIds.includes(log.id)}
                          onChange={() => toggleSelectLog(log.id)}
                          className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                        />
                      </td>
                      <td className="text-sm text-gray-900 font-medium">{log.id}</td>
                      <td>
                        <MapPreview 
                          logId={log.id} 
                          apiBaseUrl={API_BASE_URL} 
                          onMapClick={fetchGeoJson}
                        />
                      </td>
                      <td className="text-sm text-gray-700">
                        {log.captured_at
                          ? new Date(log.captured_at).toLocaleDateString()
                          : 'N/A'}
                      </td>
                      <td className="text-sm text-gray-700">
                        {log.captured_at
                          ? new Date(log.captured_at).toLocaleTimeString()
                          : 'N/A'}
                      </td>
                      <td className="text-sm text-gray-700">
                        {log.duration_seconds
                          ? `${log.duration_seconds.toFixed(1)}s`
                          : 'N/A'}
                      </td>
                      <td className="text-sm text-gray-700">
                        {log.channel_count ?? 'N/A'}
                      </td>
                      <td>
                        <div className="flex flex-col gap-1">
                          {log.recovery_status && (
                            <span
                              className={`inline-block px-2 py-1 rounded text-xs ${
                                log.recovery_status === 'completed' || log.recovery_status === 'success'
                                  ? 'bg-green-100 text-green-800'
                                  : log.recovery_status === 'pending'
                                  ? 'bg-yellow-100 text-yellow-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              Recovery: {log.recovery_status}
                            </span>
                          )}
                          {log.parse_status && (
                            <span
                              className={`inline-block px-2 py-1 rounded text-xs ${
                                log.parse_status === 'completed' || log.parse_status === 'success'
                                  ? 'bg-green-100 text-green-800'
                                  : log.parse_status === 'pending'
                                  ? 'bg-yellow-100 text-yellow-800'
                                  : log.parse_status?.startsWith('error')
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-blue-100 text-blue-800'
                              }`}
                            >
                              Parse: {log.parse_status}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="text-sm text-gray-700">
                        {getName(log.car)}
                      </td>
                      <td className="text-sm text-gray-700">
                        {getName(log.driver)}
                      </td>
                      <td className="text-sm text-gray-700">
                        {getName(log.event_type)}
                      </td>
                      <td>
                        <div className="flex gap-2 flex-wrap">
                          <Button
                            onClick={() => handleViewLog(log.id)}
                            size="sm"
                            className="text-xs bg-purple-600 hover:bg-purple-700 text-white"
                          >
                            View
                          </Button>
                          <Button
                            onClick={() => fetchGeoJson(log.id)}
                            disabled={loadingGeoJson}
                            size="sm"
                            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300"
                          >
                            Map
                          </Button>
                          <Button
                            onClick={() => handleDownload(log.id)}
                            disabled={downloading === log.id}
                            size="sm"
                            className="text-xs border border-gray-300 text-gray-700 hover:bg-gray-50"
                            title="Download MCAP file"
                          >
                            <Download className="h-3 w-3 mr-1" />
                            {downloading === log.id ? 'Downloading...' : 'Download'}
                          </Button>
                          <Button
                            onClick={() => handleEditLog(log.id)}
                            size="sm"
                            className="text-xs bg-green-600 hover:bg-green-700 text-white"
                          >
                            Edit
                          </Button>
                          <Button
                            onClick={() => openDeleteConfirm(log.id)}
                            size="sm"
                            className="text-xs bg-red-600 hover:bg-red-700 text-white"
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          </CardContent>
        </Card>

        {/* Bulk Download Format Dialog */}
        <Dialog
          open={isDownloadDialogOpen}
          onOpenChange={(open) => {
            setIsDownloadDialogOpen(open);
            if (!open) setBulkDownloadError(null);
          }}
        >
          <DialogContent className="bg-white border border-gray-200">
            <DialogHeader>
              <DialogTitle className="text-gray-900">Select download format</DialogTitle>
              <DialogDescription className="text-gray-600">
                {selectedLogIds.length} log{selectedLogIds.length === 1 ? '' : 's'} selected
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3">
              <Label className="text-gray-700">Format</Label>
              <Select
                value={downloadFormat}
                onValueChange={(val) => setDownloadFormat(val as 'mcap' | 'csv_omni' | 'csv_tvn' | 'ld')}
              >
                <SelectTrigger className="w-full bg-white border-gray-300">
                  <SelectValue placeholder="Select format" />
                </SelectTrigger>
                <SelectContent className="bg-white border border-gray-200">
                  <SelectItem value="mcap">MCAP (original)</SelectItem>
                  <SelectItem value="csv_omni">CSV (omni)</SelectItem>
                  <SelectItem value="csv_tvn">CSV (tvn)</SelectItem>
                  <SelectItem value="ld">LD (i2)</SelectItem>
                </SelectContent>
              </Select>

              {bulkDownloadError && (
                <p className="text-sm text-red-600">{bulkDownloadError}</p>
              )}
            </div>

            <DialogFooter className="gap-2">
              <Button 
                variant="outline" 
                onClick={() => setIsDownloadDialogOpen(false)}
                className="border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </Button>
              <Button 
                onClick={handleBulkDownload} 
                disabled={bulkDownloading}
                className="bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-50"
              >
                {bulkDownloading ? 'Preparing...' : 'Download'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* View Modal */}
        <Dialog open={isViewModalOpen} onOpenChange={(open) => {
          setIsViewModalOpen(open);
          if (!open) setSelectedLog(null);
        }}>
          {selectedLog && (
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-white border border-gray-200">
              <DialogHeader>
                <DialogTitle className="text-gray-900">Log Details - ID: {selectedLog.id}</DialogTitle>
              </DialogHeader>
                {loadingLog ? (
                  <div className="text-center py-8">
                    <p className="text-gray-600">Loading log details...</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-sm font-medium text-gray-600">Recovery Status</label>
                        <p className="text-gray-900">{selectedLog.recovery_status || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Parse Status</label>
                        <p className="text-gray-900">{selectedLog.parse_status || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Captured At</label>
                        <p className="text-gray-900">
                          {selectedLog.captured_at ? new Date(selectedLog.captured_at).toLocaleString() : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Duration</label>
                        <p className="text-gray-900">
                          {selectedLog.duration_seconds ? `${selectedLog.duration_seconds.toFixed(1)}s` : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Channel Count</label>
                        <p className="text-gray-900">{selectedLog.channel_count ?? 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Rough Point</label>
                        <p className="text-gray-900">{selectedLog.rough_point || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Car</label>
                        <p className="text-gray-900">{getName(selectedLog.car)}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Driver</label>
                        <p className="text-gray-900">{getName(selectedLog.driver)}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Event Type</label>
                        <p className="text-gray-900">{getName(selectedLog.event_type)}</p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Created At</label>
                        <p className="text-gray-900">
                          {selectedLog.created_at ? new Date(selectedLog.created_at).toLocaleString() : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-gray-600">Updated At</label>
                        <p className="text-gray-900">
                          {selectedLog.updated_at ? new Date(selectedLog.updated_at).toLocaleString() : 'N/A'}
                        </p>
                      </div>
                    </div>
                    {selectedLog.channels && selectedLog.channels.length > 0 && (
                      <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                        <div className="flex justify-between items-center mb-3">
                          <label className="text-base font-semibold text-gray-900">
                            Channels
                          </label>
                          <span className="text-sm text-gray-600">
                            Count: {selectedLog.channel_count ?? selectedLog.channels.length}
                          </span>
                        </div>
                        <div className="max-h-64 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                          <table className="w-full border-collapse">
                            <thead className="sticky top-0 bg-gray-100">
                              <tr>
                                <th className="text-left py-2 px-4 text-sm font-semibold text-gray-700 border-b border-gray-200">
                                  #
                                </th>
                                <th className="text-left py-2 px-4 text-sm font-semibold text-gray-700 border-b border-gray-200">
                                  Channel Name
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedLog.channels.map((channel, idx) => (
                                <tr
                              key={idx}
                                  className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                            >
                                  <td className="py-2 px-4 text-sm text-gray-600">
                                    {idx + 1}
                                  </td>
                                  <td className="py-2 px-4 text-sm text-gray-900 font-mono">
                              {channel}
                                  </td>
                                </tr>
                          ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    {selectedLog.notes && (
                      <div>
                        <label className="text-sm font-medium text-gray-600">Notes</label>
                        <p className="text-gray-900 mt-1">{selectedLog.notes}</p>
                      </div>
                    )}
                    <div className="pt-4">
                      <Button
                        onClick={() => fetchGeoJson(selectedLog.id)}
                        disabled={loadingGeoJson}
                        className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300"
                      >
                        {loadingGeoJson ? 'Loading Map...' : 'View on Map'}
                      </Button>
                    </div>
                  </div>
                )}
            </DialogContent>
        )}
        </Dialog>

        {/* Map Modal */}
        <Dialog open={isMapModalOpen} onOpenChange={(open) => {
          setIsMapModalOpen(open);
          if (!open) setGeoJsonData(null);
        }}>
          {geoJsonData && (
            <DialogContent className="max-w-6xl w-full h-[90vh] flex flex-col p-0 bg-white border border-gray-200">
              <div className="p-4 border-b border-gray-200 flex justify-between items-center">
                <DialogTitle>Map View - Log ID: {selectedLog?.id}</DialogTitle>
              </div>
              <div className="flex-1 relative">
                <MapComponent geoJsonData={geoJsonData} />
              </div>
            </DialogContent>
        )}
        </Dialog>

        {/* Edit Modal */}
        <Dialog open={isEditModalOpen} onOpenChange={(open) => {
          setIsEditModalOpen(open);
          if (!open) setSelectedLog(null);
        }}>
          {selectedLog && (
            <DialogContent className="max-w-2xl bg-white border border-gray-200">
              <DialogHeader>
                <DialogTitle className="text-gray-900">Edit Log - ID: {selectedLog.id}</DialogTitle>
              </DialogHeader>
                <div className="space-y-4">
                  <div>
                  <div className="flex items-center justify-between mb-1">
                    <Label htmlFor="car" className="text-gray-700">Car</Label>
                    {editForm.car && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-gray-600 hover:text-gray-900"
                        onClick={() => setEditForm({ ...editForm, car: '' })}
                      >
                        Clear
                      </Button>
                    )}
                  </div>
                  {loadingLookups ? (
                    <Input
                      id="car"
                      type="text"
                      value="Loading..."
                      disabled
                      className="bg-gray-100 border-gray-300"
                    />
                  ) : (
                    <Select
                      value={editForm.car || undefined}
                      onValueChange={(value) => {
                        console.log('Car selected:', value);
                        setEditForm({ ...editForm, car: value });
                      }}
                    >
                      <SelectTrigger id="car" className="bg-white border-gray-300">
                        <SelectValue placeholder="Select a car" />
                      </SelectTrigger>
                      <SelectContent className="bg-white border border-gray-200 z-[100]">
                        {cars.length === 0 ? (
                          <div className="px-2 py-1.5 text-sm text-gray-500">No cars available</div>
                        ) : (
                          cars.map((car) => (
                            <SelectItem key={car.id} value={car.id.toString()}>
                              {car.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  )}
                  </div>
                  <div>
                  <div className="flex items-center justify-between mb-1">
                    <Label htmlFor="driver" className="text-gray-700">Driver</Label>
                    {editForm.driver && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-gray-600 hover:text-gray-900"
                        onClick={() => setEditForm({ ...editForm, driver: '' })}
                      >
                        Clear
                      </Button>
                    )}
                  </div>
                  {loadingLookups ? (
                    <Input
                      id="driver"
                      type="text"
                      value="Loading..."
                      disabled
                      className="bg-gray-100 border-gray-300"
                    />
                  ) : (
                    <Select
                      value={editForm.driver || undefined}
                      onValueChange={(value) => {
                        console.log('Driver selected:', value);
                        setEditForm({ ...editForm, driver: value });
                      }}
                    >
                      <SelectTrigger id="driver" className="bg-white border-gray-300">
                        <SelectValue placeholder="Select a driver" />
                      </SelectTrigger>
                      <SelectContent className="bg-white border border-gray-200 z-[100]">
                        {drivers.length === 0 ? (
                          <div className="px-2 py-1.5 text-sm text-gray-500">No drivers available</div>
                        ) : (
                          drivers.map((driver) => (
                            <SelectItem key={driver.id} value={driver.id.toString()}>
                              {driver.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  )}
                  </div>
                  <div>
                  <div className="flex items-center justify-between mb-1">
                    <Label htmlFor="event_type" className="text-gray-700">Event Type</Label>
                    {editForm.event_type && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-gray-600 hover:text-gray-900"
                        onClick={() => setEditForm({ ...editForm, event_type: '' })}
                      >
                        Clear
                      </Button>
                    )}
                  </div>
                  {loadingLookups ? (
                    <Input
                      id="event_type"
                      type="text"
                      value="Loading..."
                      disabled
                      className="bg-gray-100 border-gray-300"
                    />
                  ) : (
                    <Select
                      value={editForm.event_type || undefined}
                      onValueChange={(value) => {
                        console.log('Event type selected:', value);
                        setEditForm({ ...editForm, event_type: value });
                      }}
                    >
                      <SelectTrigger id="event_type" className="bg-white border-gray-300">
                        <SelectValue placeholder="Select an event type" />
                      </SelectTrigger>
                      <SelectContent className="bg-white border border-gray-200 z-[100]">
                        {eventTypes.length === 0 ? (
                          <div className="px-2 py-1.5 text-sm text-gray-500">No event types available</div>
                        ) : (
                          eventTypes.map((eventType) => (
                            <SelectItem key={eventType.id} value={eventType.id.toString()}>
                              {eventType.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  )}
                  </div>
                  <div>
                  <Label htmlFor="notes" className="text-gray-700">Notes</Label>
                  <Textarea
                    id="notes"
                      value={editForm.notes}
                      onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                      rows={4}
                      className="bg-white border-gray-300"
                    />
                  </div>
                <DialogFooter>
                  <Button
                    onClick={() => handleUpdateLog(selectedLog.id, false)}
                    disabled={saving}
                    className="bg-purple-600 hover:bg-purple-700 text-white"
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </Button>
                  <Button
                    onClick={() => {
                      setIsEditModalOpen(false);
                      setSelectedLog(null);
                    }}
                    className="bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300"
                  >
                    Cancel
                  </Button>
                </DialogFooter>
                  </div>
            </DialogContent>
        )}
        </Dialog>

        {/* Delete Confirmation Modal */}
        <Dialog open={isDeleteModalOpen} onOpenChange={(open) => {
          setIsDeleteModalOpen(open);
          if (!open) setLogToDelete(null);
        }}>
          {logToDelete !== null && (
            <DialogContent className="max-w-md bg-white border border-gray-200">
              <DialogHeader>
                <DialogTitle className="text-gray-900">Confirm Delete</DialogTitle>
                <DialogDescription className="text-gray-600">
                  Are you sure you want to delete log ID {logToDelete}? This action cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                    onClick={() => handleDeleteLog(logToDelete)}
                    disabled={deleting}
                    className="bg-red-600 hover:bg-red-700 text-white"
                  >
                    {deleting ? 'Deleting...' : 'Delete'}
                </Button>
                <Button
                    onClick={() => {
                      setIsDeleteModalOpen(false);
                      setLogToDelete(null);
                    }}
                    className="bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300"
                  >
                    Cancel
                </Button>
              </DialogFooter>
            </DialogContent>
          )}
        </Dialog>
        </div>
    </div>
  );
}
