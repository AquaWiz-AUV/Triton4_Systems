import React, { useState, useRef, useEffect } from 'react';
import { Activity, Settings, Trash2 } from 'lucide-react';
import { cn } from './Layout';

const Header = ({ mid, onMidChange, connectionStatus, lastUpdate }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const settingsRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (settingsRef.current && !settingsRef.current.contains(event.target)) {
        setIsSettingsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <header className="z-50 flex h-16 w-full items-center justify-between border-b border-white/20 bg-background px-6">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center bg-primary text-black shadow-[4px_4px_0px_0px_rgba(255,255,255,0.2)]">
            <Activity size={20} strokeWidth={3} />
          </div>
          <span className="text-2xl font-black uppercase tracking-tighter text-white">
            TR4<span className="text-primary">:OVERWATCH</span>
          </span>
        </div>
        
        <div className="h-8 w-px bg-white/20" />
        
        <div className="flex items-center gap-3 border border-white/20 bg-black px-3 py-1">
          <span className={cn(
            "h-2 w-2",
            connectionStatus ? "bg-primary shadow-[0_0_10px_var(--primary)]" : "bg-destructive shadow-[0_0_10px_var(--destructive)]"
          )} />
          <span className="font-mono text-xs font-bold uppercase text-white">
            {connectionStatus ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>

        {lastUpdate && (
          <div className="hidden items-center gap-2 border-l border-white/10 pl-6 md:flex">
            <span className="font-mono text-[10px] font-bold uppercase text-white/40 tracking-widest">LATEST_UPDATE:</span>
            <span className="font-mono text-sm font-bold text-primary">
              {new Date(lastUpdate).toLocaleTimeString([], { hour12: false })}
              <span className="text-[10px] text-white/40 ml-1">
                .{new Date(lastUpdate).getMilliseconds().toString().padStart(3, '0')}
              </span>
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="group flex items-center gap-3 border border-white/20 bg-black px-4 py-2 hover:border-primary hover:bg-primary/10">
          <span className="font-mono text-[10px] font-bold uppercase text-white/60">TARGET:</span>
          <select 
            className="bg-transparent font-mono text-sm font-bold text-white focus:outline-none"
            value={mid} 
            onChange={(e) => onMidChange(e.target.value)}
          >
            <option value="TR4-SIM-001">TR4-SIM-001</option>
            <option value="TR4-TEST-001">TR4-TEST-001</option>
          </select>
          <span className="flex h-4 items-center bg-primary px-1 font-mono text-[10px] font-bold text-black">
            LIVE
          </span>
        </div>

        <div className="relative" ref={settingsRef}>
          <button 
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            className={cn(
              "flex h-10 w-10 items-center justify-center border border-white/20 bg-black text-white transition-all hover:bg-white hover:text-black",
              isSettingsOpen && "bg-white text-black"
            )}
          >
            <Settings size={20} />
          </button>

          {isSettingsOpen && (
            <div className="absolute right-0 top-full mt-2 w-56 border border-white/20 bg-black shadow-[4px_4px_0px_0px_rgba(255,255,255,0.2)]">
              <div className="border-b border-white/10 px-3 py-2">
                <span className="font-mono text-[10px] font-bold uppercase text-white/40">SYSTEM_CONTROLS</span>
              </div>
              <button 
                onClick={async () => {
                  if (window.confirm('WARNING: This will delete ALL data from the database. This action cannot be undone.\n\nAre you sure you want to proceed?')) {
                    try {
                      const { resetDatabase } = await import('../api');
                      await resetDatabase();
                      window.location.reload();
                    } catch (error) {
                      console.error('Failed to reset database:', error);
                      alert('Failed to reset database. Check console for details.');
                    }
                  }
                  setIsSettingsOpen(false);
                }}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-destructive/20"
              >
                <Trash2 size={16} className="text-destructive" />
                <span className="font-mono text-xs font-bold uppercase text-destructive">RESET DATA</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
