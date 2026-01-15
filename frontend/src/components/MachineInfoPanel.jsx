import React, { useState } from 'react';
import { 
  Battery, Signal, Thermometer, Navigation, 
  Anchor, Clock, Database, ChevronRight, ChevronDown 
} from 'lucide-react';
import { sendCommand } from '../api';
import { cn } from './Layout';

const TabButton = ({ active, label, onClick }) => (
  <button 
    className={cn(
      "flex-1 py-3 text-[10px] font-bold uppercase tracking-widest transition-all",
      active 
        ? "bg-primary text-black" 
        : "bg-transparent text-white/40 hover:bg-white/5 hover:text-white"
    )}
    onClick={onClick}
  >
    {label}
  </button>
);

const InfoRow = ({ label, value, unit, icon: Icon, status }) => (
  <div className="group flex items-end justify-between py-1.5">
    <div className="flex items-center gap-2 text-white/40">
      {Icon && <Icon size={12} />}
      <span className="font-mono text-[10px] font-bold uppercase tracking-wider">{label}</span>
    </div>
    <div className="flex flex-1 items-end mx-2 border-b border-dotted border-white/10 mb-1"></div>
    <div className={cn(
      "font-mono text-sm font-bold",
      status === 'idle' && "text-yellow-500",
      status === 'running' && "text-primary",
      status === 'error' && "text-destructive",
      !status && "text-white"
    )}>
      {value} {unit && <span className="text-[10px] text-white/30 ml-0.5">{unit}</span>}
    </div>
  </div>
);

const MachineInfoPanel = ({ data, mid }) => {
  const [activeTab, setActiveTab] = useState('details');
  const [isExpanded, setIsExpanded] = useState(true);
  const [cmdStatus, setCmdStatus] = useState(null);
  const [showRawData, setShowRawData] = useState(false);
  const [missionParams, setMissionParams] = useState({
    target_depth_m: 10,
    hold_at_depth_s: 30,
    cycles: 1
  });

  if (!data) return (
    <div className="w-full border border-white/10 bg-black p-1">
      <div className="flex items-center justify-between border-b border-white/10 p-4">
        <h3 className="font-mono text-xs font-bold uppercase tracking-widest text-white">Machine Details</h3>
      </div>
      <div className="p-4">
        <p className="font-mono text-[10px] text-white/30 animate-pulse">WAITING_FOR_TELEMETRY...</p>
      </div>
    </div>
  );

  const { properties } = data;
  const { position, power, environment, network, state, timestamp } = properties;

  const handleDive = async () => {
    setCmdStatus('sending');
    try {
      await sendCommand(mid, 'RUN_DIVE', missionParams);
      setCmdStatus('success');
    } catch (err) {
      setCmdStatus('error');
    } finally {
      setTimeout(() => setCmdStatus(null), 3000);
    }
  };

  return (
    <div className={cn(
      "w-full overflow-hidden border border-white/10 bg-black transition-all duration-300",
      !isExpanded && "w-auto"
    )}>
      <div 
        className="flex cursor-pointer items-center justify-between border-b border-white/10 bg-white/5 p-3 hover:bg-white/10"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 ${state === 'RUNNING' ? 'bg-primary animate-pulse' : 'bg-white/20'}`} />
          <h3 className="font-mono text-xs font-bold uppercase tracking-widest text-white">Machine Details</h3>
        </div>
        <button className="text-white/40 hover:text-white transition-colors">
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      {isExpanded && (
        <div className="animate-slide-up">
          <div className="flex border-b border-white/10">
            <TabButton 
              active={activeTab === 'details' && !showRawData} 
              label="Details" 
              onClick={() => { setActiveTab('details'); setShowRawData(false); }} 
            />
            <TabButton 
              active={activeTab === 'control' && !showRawData} 
              label="Control" 
              onClick={() => { setActiveTab('control'); setShowRawData(false); }} 
            />
          </div>

          <div className="p-4">
            {showRawData ? (
              <div className="relative animate-fade-in">
                <pre className="max-h-[300px] overflow-auto border border-white/10 bg-black p-3 font-mono text-[10px] text-primary/80 scrollbar-thin scrollbar-thumb-white/20">
                  {JSON.stringify(data, null, 2)}
                </pre>
              </div>
            ) : (
              <>
                {activeTab === 'details' && (
                  <div className="space-y-6 animate-fade-in">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 border-b border-white/10 pb-1">
                        <div className="h-1 w-1 bg-primary"></div>
                        <h4 className="font-mono text-[10px] font-bold uppercase text-white/50">System Status</h4>
                      </div>
                      <div className="space-y-px">
                        <InfoRow label="ID" value={mid} />
                        <InfoRow label="STATE" value={state} status={state.toLowerCase()} />
                        <InfoRow label="LAST_UPDATE" value={new Date(timestamp).toLocaleTimeString()} />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center gap-2 border-b border-white/10 pb-1">
                        <div className="h-1 w-1 bg-primary"></div>
                        <h4 className="font-mono text-[10px] font-bold uppercase text-white/50">Navigation Data</h4>
                      </div>
                      <div className="space-y-px">
                        <InfoRow label="LAT" value={position.lat.toFixed(6)} />
                        <InfoRow label="LON" value={position.lon.toFixed(6)} />
                        <InfoRow label="DEPTH" value={environment?.depth_m?.toFixed(1) ?? '-'} unit="m" />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center gap-2 border-b border-white/10 pb-1">
                        <div className="h-1 w-1 bg-primary"></div>
                        <h4 className="font-mono text-[10px] font-bold uppercase text-white/50">Telemetry</h4>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="border border-white/10 bg-white/5 p-2 text-center transition-colors hover:border-primary/50">
                          <div className="mb-1 text-[9px] font-bold text-white/40 uppercase tracking-wider">BATTERY</div>
                          <div className="font-mono text-lg font-bold text-primary">
                            {typeof power?.soc === 'number' ? power.soc.toFixed(1) : '-'}
                            <span className="ml-0.5 text-[10px] text-primary/50">%</span>
                          </div>
                        </div>
                        <div className="border border-white/10 bg-white/5 p-2 text-center transition-colors hover:border-white/30">
                          <div className="mb-1 text-[9px] font-bold text-white/40 uppercase tracking-wider">SIGNAL</div>
                          <div className="font-mono text-lg font-bold text-white">
                            {typeof network?.rsrp_dbm === 'number' ? network.rsrp_dbm.toFixed(0) : '-'}
                            <span className="ml-0.5 text-[10px] text-white/30">dBm</span>
                          </div>
                        </div>
                        <div className="border border-white/10 bg-white/5 p-2 text-center transition-colors hover:border-white/30">
                          <div className="mb-1 text-[9px] font-bold text-white/40 uppercase tracking-wider">TEMP</div>
                          <div className="font-mono text-lg font-bold text-white">
                            {typeof environment?.water_temp_c === 'number' ? environment.water_temp_c.toFixed(1) : '-'}
                            <span className="ml-0.5 text-[10px] text-white/30">°C</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'control' && (
                  <div className="space-y-4 animate-fade-in">
                    <div className="border border-white/10 bg-white/5 p-4">
                      <div className="mb-6 flex items-center gap-2 text-primary">
                        <Anchor size={16} />
                        <span className="font-mono text-xs font-bold uppercase tracking-widest">Dive Mission Profile</span>
                      </div>
                      
                      <div className="space-y-4">
                        <div className="space-y-1">
                          <label className="font-mono text-[10px] font-bold text-white/50 uppercase tracking-wider">TARGET_DEPTH (m)</label>
                          <input 
                            type="number" 
                            className="w-full border-b border-white/20 bg-transparent px-0 py-2 font-mono text-sm text-white focus:border-primary focus:outline-none transition-colors"
                            value={missionParams.target_depth_m}
                            onChange={(e) => setMissionParams({...missionParams, target_depth_m: parseFloat(e.target.value)})}
                          />
                        </div>

                        <div className="space-y-1">
                          <label className="font-mono text-[10px] font-bold text-white/50 uppercase tracking-wider">HOLD_DURATION (s)</label>
                          <input 
                            type="number" 
                            className="w-full border-b border-white/20 bg-transparent px-0 py-2 font-mono text-sm text-white focus:border-primary focus:outline-none transition-colors"
                            value={missionParams.hold_at_depth_s}
                            onChange={(e) => setMissionParams({...missionParams, hold_at_depth_s: parseFloat(e.target.value)})}
                          />
                        </div>

                        <div className="space-y-1">
                          <label className="font-mono text-[10px] font-bold text-white/50 uppercase tracking-wider">CYCLES</label>
                          <input 
                            type="number" 
                            className="w-full border-b border-white/20 bg-transparent px-0 py-2 font-mono text-sm text-white focus:border-primary focus:outline-none transition-colors"
                            value={missionParams.cycles}
                            onChange={(e) => setMissionParams({...missionParams, cycles: parseInt(e.target.value)})}
                          />
                        </div>

                        <button 
                          className={cn(
                            "mt-6 w-full border border-primary/50 bg-primary/10 px-4 py-3 font-mono text-xs font-bold uppercase tracking-widest text-primary transition-all hover:bg-primary hover:text-black",
                            cmdStatus === 'success' && "border-emerald-500 bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500 hover:text-black",
                            cmdStatus === 'error' && "border-destructive bg-destructive/10 text-destructive hover:bg-destructive hover:text-white"
                          )}
                          onClick={handleDive}
                          disabled={cmdStatus === 'sending'}
                        >
                          {cmdStatus === 'sending' ? 'TRANSMITTING...' : 
                           cmdStatus === 'success' ? 'COMMAND_SENT' : 
                           cmdStatus === 'error' ? 'TRANSMISSION_FAILED' : 'INITIATE_DIVE_SEQUENCE'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
          
          <div className="border-t border-white/10 bg-white/5 p-1">
            {activeTab === 'details' && (
              <button 
                className="flex w-full items-center justify-center gap-2 py-2 font-mono text-[10px] font-bold text-white/30 uppercase tracking-widest transition-colors hover:bg-white/5 hover:text-white"
                onClick={() => setShowRawData(!showRawData)}
              >
                <Database size={12} /> 
                {showRawData ? 'HIDE_RAW_DATA' : 'VIEW_RAW_DATA'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MachineInfoPanel;
