import React from 'react';
import { FileText, Globe } from 'lucide-react';
import { ScopeMode } from '../types';

interface ScopeSelectorProps {
  mode: ScopeMode;
  onChangeMode: (mode: ScopeMode) => void;
  disabled?: boolean;
}

export const ScopeSelector: React.FC<ScopeSelectorProps> = ({ mode, onChangeMode, disabled }) => {
  return (
    <div className="bg-slate-950/60 p-1 rounded-lg border border-slate-800/80 grid grid-cols-2 gap-1">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChangeMode('page')}
        className={`flex items-center justify-center space-x-2 py-1.5 px-3 rounded-md text-xs font-medium transition-all ${
          mode === 'page'
            ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <FileText className="w-3.5 h-3.5" />
        <span>Current Page</span>
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onChangeMode('site')}
        className={`flex items-center justify-center space-x-2 py-1.5 px-3 rounded-md text-xs font-medium transition-all ${
          mode === 'site'
            ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <Globe className="w-3.5 h-3.5" />
        <span>Entire Website</span>
      </button>
    </div>
  );
};
