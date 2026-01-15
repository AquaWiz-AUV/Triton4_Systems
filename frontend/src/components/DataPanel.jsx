import React from 'react';
import { X, Battery, Signal, Thermometer, Navigation } from 'lucide-react';
import { format } from 'date-fns';

const DataPanel = ({ data, onClose }) => {
  if (!data) return null;

  const { properties } = data;
  const { position, power, environment, network, state, timestamp } = properties;

  return (
    <div className="data-panel">
      <div className="panel-header">
        <h3>Data Point</h3>
        <button onClick={onClose} className="close-btn">
          <X size={20} />
        </button>
      </div>
      
      <div className="panel-content">
        <div className="data-row time">
          <span className="label">Time</span>
          <span className="value">{format(new Date(timestamp), 'HH:mm:ss')}</span>
        </div>
        
        <div className="data-row state">
          <span className="label">State</span>
          <span className={`status-badge ${state.toLowerCase()}`}>{state}</span>
        </div>

        <div className="section">
          <h4><Navigation size={16} /> Position</h4>
          <div className="grid">
            <div className="item">
              <span className="label">Lat</span>
              <span className="value">{position.lat.toFixed(6)}</span>
            </div>
            <div className="item">
              <span className="label">Lon</span>
              <span className="value">{position.lon.toFixed(6)}</span>
            </div>
            <div className="item">
              <span className="label">Depth</span>
              <span className="value">{environment?.depth_m?.toFixed(1) ?? '-'} m</span>
            </div>
          </div>
        </div>

        <div className="section">
          <h4><Battery size={16} /> Power</h4>
          <div className="grid">
            <div className="item">
              <span className="label">SoC</span>
              <span className="value">{power?.soc ?? '-'} %</span>
            </div>
            <div className="item">
              <span className="label">Voltage</span>
              <span className="value">{power?.voltage_v?.toFixed(1) ?? '-'} V</span>
            </div>
          </div>
        </div>

        <div className="section">
          <h4><Signal size={16} /> Network</h4>
          <div className="grid">
            <div className="item">
              <span className="label">RSRP</span>
              <span className="value">{network?.rsrp_dbm ?? '-'} dBm</span>
            </div>
            <div className="item">
              <span className="label">SNR</span>
              <span className="value">{network?.snr_db ?? '-'} dB</span>
            </div>
          </div>
        </div>

        <div className="section">
          <h4><Thermometer size={16} /> Environment</h4>
          <div className="grid">
            <div className="item">
              <span className="label">Water Temp</span>
              <span className="value">{environment?.water_temp_c?.toFixed(1) ?? '-'} °C</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataPanel;
