import React from 'react';
import Header from './Header';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

const Layout = ({ children, mid, onMidChange, connectionStatus, lastUpdate }) => {
  return (
    <div className="bg-grid relative flex h-screen w-full flex-col overflow-hidden bg-background text-foreground selection:bg-primary selection:text-black">
      <div className="z-10 flex h-full flex-col">
        <Header mid={mid} onMidChange={onMidChange} connectionStatus={connectionStatus} lastUpdate={lastUpdate} />
        <main className="relative flex-1 overflow-hidden border-t border-white/20">
          {children}
        </main>
      </div>
      
      {/* Decorative corner accents */}
      <div className="pointer-events-none absolute bottom-0 left-0 h-16 w-16 border-b-2 border-l-2 border-primary" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-16 w-16 border-b-2 border-r-2 border-primary" />
      <div className="pointer-events-none absolute right-0 top-0 h-16 w-16 border-r-2 border-t-2 border-primary" />
    </div>
  );
};

export default Layout;
