import React, { useState, useEffect } from 'react';
import MapComponent from './components/MapComponent';
import MachineInfoPanel from './components/MachineInfoPanel';
import Layout from './components/Layout';
import { fetchTrajectory, fetchLatestTelemetry } from './api';
import './App.css';

const DEFAULT_MID = import.meta.env.VITE_TRITON_MID || 'TR4-SIM-001';

function App() {
  const [mid, setMid] = useState(DEFAULT_MID);
  const [trajectory, setTrajectory] = useState(null);
  const [latestTelemetry, setLatestTelemetry] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState(false);
  const [isTracking, setIsTracking] = useState(true);

  const loadData = async () => {
    try {
      console.log('Fetching data for:', mid);
      const [trajData, latestData] = await Promise.all([
        fetchTrajectory(mid),
        fetchLatestTelemetry(mid)
      ]);
      
      console.log('Trajectory:', trajData);
      console.log('Latest:', latestData);

      setTrajectory(trajData);
      setLatestTelemetry(latestData);
      setConnectionStatus(true);
      
      // If tracking is active, always show latest data
      if (isTracking && latestData) {
        setSelectedPoint({
            properties: {
                ...latestData,
                timestamp: latestData.ts_utc
            }
        });
      }
    } catch (error) {
      console.error('Failed to load data:', error);
      setConnectionStatus(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [isTracking, mid]); // Add mid dependency

  const handlePointClick = (point) => {
    setSelectedPoint(point);
    setIsTracking(false); // Stop tracking when user selects a specific point
  };

  const handleMapDrag = () => {
    setIsTracking(false);
  };

  const handleResumeTracking = () => {
    setIsTracking(true);
    // Immediately update to latest data if available
    if (latestTelemetry) {
      setSelectedPoint({
          properties: {
              ...latestTelemetry,
              timestamp: latestTelemetry.ts_utc
          }
      });
    }
  };

  return (
    <Layout mid={mid} onMidChange={setMid} connectionStatus={connectionStatus} lastUpdate={latestTelemetry?.ts_utc}>
      <div className="relative w-full h-full">
        <MapComponent 
          trajectory={trajectory} 
          onPointClick={handlePointClick}
          selectedPoint={selectedPoint}
          isTracking={isTracking}
          onMapDrag={handleMapDrag}
          onResumeTracking={handleResumeTracking}
        />
        
        <div className="absolute top-4 right-4 z-10 w-80 pointer-events-none">
          <div className="pointer-events-auto">
            <MachineInfoPanel 
              data={selectedPoint} 
              mid={mid} 
            />
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default App;
