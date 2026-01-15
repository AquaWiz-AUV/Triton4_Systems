import React, { useCallback, useMemo, useState, useRef } from 'react';
import { GoogleMap, useJsApiLoader, Polyline, Marker, InfoWindow } from '@react-google-maps/api';
import { Navigation } from 'lucide-react';

const containerStyle = {
  width: '100%',
  height: '100%',
};

const defaultCenter = {
  lat: 35.6895,
  lng: 139.6917,
};

const mapStyles = [
  {
    "elementType": "geometry",
    "stylers": [{ "color": "#050505" }]
  },
  {
    "elementType": "labels.icon",
    "stylers": [{ "visibility": "off" }]
  },
  {
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#757575" }]
  },
  {
    "elementType": "labels.text.stroke",
    "stylers": [{ "color": "#050505" }]
  },
  {
    "featureType": "administrative",
    "elementType": "geometry",
    "stylers": [{ "color": "#333333" }]
  },
  {
    "featureType": "administrative.country",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#9e9e9e" }]
  },
  {
    "featureType": "administrative.land_parcel",
    "stylers": [{ "visibility": "off" }]
  },
  {
    "featureType": "administrative.locality",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#bdbdbd" }]
  },
  {
    "featureType": "poi",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#757575" }]
  },
  {
    "featureType": "poi.park",
    "elementType": "geometry",
    "stylers": [{ "color": "#0a0a0a" }]
  },
  {
    "featureType": "poi.park",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#616161" }]
  },
  {
    "featureType": "poi.park",
    "elementType": "labels.text.stroke",
    "stylers": [{ "color": "#1b1b1b" }]
  },
  {
    "featureType": "road",
    "elementType": "geometry.fill",
    "stylers": [{ "color": "#1a1a1a" }]
  },
  {
    "featureType": "road",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#8a8a8a" }]
  },
  {
    "featureType": "road.arterial",
    "elementType": "geometry",
    "stylers": [{ "color": "#222222" }]
  },
  {
    "featureType": "road.highway",
    "elementType": "geometry",
    "stylers": [{ "color": "#2c2c2c" }]
  },
  {
    "featureType": "road.highway.controlled_access",
    "elementType": "geometry",
    "stylers": [{ "color": "#333333" }]
  },
  {
    "featureType": "road.local",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#616161" }]
  },
  {
    "featureType": "transit",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#757575" }]
  },
  {
    "featureType": "water",
    "elementType": "geometry",
    "stylers": [{ "color": "#000000" }]
  },
  {
    "featureType": "water",
    "elementType": "labels.text.fill",
    "stylers": [{ "color": "#3d3d3d" }]
  }
];

const options = {
  disableDefaultUI: true,
  zoomControl: false,
  mapTypeControl: false,
  streetViewControl: false,
  fullscreenControl: false,
  keyboardShortcuts: false,
  styles: mapStyles,
};

const MapComponent = ({ trajectory, onPointClick, selectedPoint, isTracking, onMapDrag, onResumeTracking }) => {
  const { isLoaded } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '',
  });

  const [map, setMap] = useState(null);
  const mapRef = useRef(null);
  const [selectedDive, setSelectedDive] = useState(null);

  const onLoad = useCallback(function callback(map) {
    setMap(map);
    mapRef.current = map;
  }, []);

  const onUnmount = useCallback(function callback(map) {
    setMap(null);
    mapRef.current = null;
  }, []);

  // Attach listeners manually to ensure they are registered correctly
  React.useEffect(() => {
    if (!map) return;

    const dragListener = map.addListener('dragstart', () => {
      console.log('User dragging - disabling auto-center');
      if (onMapDrag) onMapDrag();
    });

    return () => {
      if (window.google && window.google.maps) {
        window.google.maps.event.removeListener(dragListener);
      }
    };
  }, [map, onMapDrag]);

  const trajectoryPaths = useMemo(() => {
    if (!trajectory?.features) return [];
    // Find all trajectory segments
    return trajectory.features
      .filter((f) => 
        f.geometry.type === 'LineString' && 
        (f.properties.type === 'trajectory' || !f.properties.type)
      )
      .map(f => f.geometry.coordinates.map(coord => ({
        lat: coord[1],
        lng: coord[0],
      })));
  }, [trajectory]);

  const diveSegments = useMemo(() => {
    if (!trajectory?.features) return [];
    return trajectory.features
      .filter((f) => f.geometry.type === 'LineString' && f.properties.type === 'dive')
      .map((f) => ({
        path: f.geometry.coordinates.map((coord) => ({
          lat: coord[1],
          lng: coord[0],
        })),
        properties: f.properties,
      }));
  }, [trajectory]);

  const points = useMemo(() => {
    if (!trajectory?.features) return [];
    return trajectory.features.filter((f) => 
      f.geometry.type === 'Point' && 
      f.properties.type !== 'deployment' && 
      f.properties.type !== 'current' &&
      f.properties.type !== 'dive_marker' // Exclude dive markers from standard points
    );
  }, [trajectory]);

  const diveMarkers = useMemo(() => {
    if (!trajectory?.features) return [];
    return trajectory.features.filter((f) => f.properties.type === 'dive_marker');
  }, [trajectory]);

  const currentPos = useMemo(() => {
    if (!trajectory?.features) return null;
    const feature = trajectory.features.find((f) => f.properties.type === 'current');
    if (!feature) return null;
    return {
      lat: feature.geometry.coordinates[1],
      lng: feature.geometry.coordinates[0],
    };
  }, [trajectory]);

  React.useEffect(() => {
    if (map && currentPos && isTracking) {
      map.panTo(currentPos);
    }
  }, [map, currentPos, isTracking]);

  if (!isLoaded) {
    return <div className="flex h-full w-full items-center justify-center bg-black font-mono text-xs text-white/50">INITIALIZING_MAP_SYSTEMS...</div>;
  }

  return (
    <div className="relative h-full w-full bg-black">
      <GoogleMap
        mapContainerStyle={containerStyle}
        center={defaultCenter}
        zoom={14}
        onLoad={onLoad}
        onUnmount={onUnmount}
        options={options}
      >
        {/* Standard Trajectory (Multiple Segments) */}
        {trajectoryPaths.map((path, index) => (
          <Polyline
            key={`traj-${index}`}
            path={path}
            options={{
              strokeColor: '#ffffff',
              strokeOpacity: 0.5,
              strokeWeight: 2,
            }}
          />
        ))}

        {/* Dive Segments (Dashed) */}
        {diveSegments.map((segment, index) => (
          <Polyline
            key={`dive-${index}`}
            path={segment.path}
            options={{
              strokeColor: '#22c55e', // Acid Green
              strokeOpacity: 0, // Hide the main line
              strokeWeight: 2,
              icons: [{
                icon: {
                  path: 'M 0,-1 0,1',
                  strokeOpacity: 1,
                  scale: 3,
                  strokeColor: '#22c55e'
                },
                offset: '0',
                repeat: '15px'
              }],
              clickable: true,
              zIndex: 10, // Ensure clickability
            }}
            onClick={(e) => {
              setSelectedDive({
                properties: segment.properties,
                position: e.latLng,
              });
            }}
          />
        ))}

        {/* Standard Points */}
        {points.map((point, index) => (
          <Marker
            key={`pt-${index}`}
            position={{
              lat: point.geometry.coordinates[1],
              lng: point.geometry.coordinates[0],
            }}
            onClick={() => onPointClick(point)}
            icon={{
              path: window.google.maps.SymbolPath.CIRCLE,
              scale: 3,
              fillColor: '#000000',
              fillOpacity: 1,
              strokeColor: '#ffffff',
              strokeWeight: 1,
            }}
          />
        ))}

        {/* Dive Markers (Start/End) */}
        {diveMarkers.map((marker, index) => (
          <Marker
            key={`dm-${index}`}
            position={{
              lat: marker.geometry.coordinates[1],
              lng: marker.geometry.coordinates[0],
            }}
            icon={{
              path: window.google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
              scale: 4,
              fillColor: '#22c55e', // Acid Green
              fillOpacity: 1,
              strokeColor: '#000000',
              strokeWeight: 1,
            }}
            title={marker.properties.marker_type === 'start' ? 'Dive Start' : 'Dive End'}
            onClick={() => {
              // Find the dive segment corresponding to this marker
              const diveProp = diveSegments.find(d => d.properties.dive_id === marker.properties.dive_id)?.properties;
              if (diveProp) {
                setSelectedDive({
                  properties: diveProp,
                  position: { lat: marker.geometry.coordinates[1], lng: marker.geometry.coordinates[0] },
                });
              }
            }}
          />
        ))}

        {currentPos && (
          <Marker
            position={currentPos}
            icon={{
              path: window.google.maps.SymbolPath.CIRCLE,
              scale: 8,
              fillColor: '#22c55e',
              fillOpacity: 1,
              strokeColor: '#ffffff',
              strokeWeight: 2,
            }}
          />
        )}

        {/* Selected Point Highlight */}
        {selectedPoint && selectedPoint.geometry && (
          <Marker
            position={{
              lat: selectedPoint.geometry.coordinates[1],
              lng: selectedPoint.geometry.coordinates[0],
            }}
            zIndex={100} // Ensure it's on top
            icon={{
              path: window.google.maps.SymbolPath.CIRCLE,
              scale: 6,
              fillColor: '#ffffff', // White fill
              fillOpacity: 1,
              strokeColor: '#22c55e', // Acid Green stroke
              strokeWeight: 2,
            }}
          />
        )}

        {/* Dive Info Window */}
        {selectedDive && (
          <InfoWindow
            position={selectedDive.position}
            onCloseClick={() => setSelectedDive(null)}
          >
            <div className="min-w-[220px] bg-black font-mono text-xs text-white">
              {/* Header Bar */}
              <div className="flex items-center border-b border-white/20 bg-white/5 px-3 py-2 pr-8">
                <div className="h-2 w-2 bg-primary mr-2 animate-pulse"></div>
                <span className="font-bold tracking-widest text-white/70">DIVE DATA</span>
              </div>
              
              {/* Content */}
              <div className="p-3">
                <h3 className="mb-3 border-b border-white/10 pb-2 text-sm font-black uppercase text-primary">
                  DIVE_SEQ_#{selectedDive.properties.dive_id}
                </h3>
                <div className="grid gap-2">
                  <div className="flex justify-between border-b border-dotted border-white/10 pb-1">
                    <span className="text-[10px] text-white/50">MAX_DEPTH</span>
                    <span className="font-bold">{selectedDive.properties.max_depth_m?.toFixed(1)}m</span>
                  </div>
                  <div className="flex justify-between border-b border-dotted border-white/10 pb-1">
                    <span className="text-[10px] text-white/50">DURATION</span>
                    <span className="font-bold">{selectedDive.properties.duration_s}s</span>
                  </div>
                  <div className="flex justify-between pt-1">
                    <span className="text-[10px] text-white/50">T_START</span>
                    <span className="font-bold">
                      {new Date(selectedDive.properties.started_at).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </InfoWindow>
        )}
      </GoogleMap>

      {!isTracking && (
        <button 
          onClick={onResumeTracking}
          className="absolute bottom-8 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 border border-primary bg-black px-6 py-3 font-mono text-sm font-bold uppercase text-primary shadow-[4px_4px_0px_0px_var(--primary)] transition-all hover:bg-primary/10 focus:outline-none"
        >
          <Navigation size={18} className="animate-pulse" />
          RESUME_TRACKING
        </button>
      )}
    </div>
  );
};

export default React.memo(MapComponent);
