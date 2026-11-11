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
    <div className="bg-canvas-subtle p-0.5 rounded-control border border-edge grid grid-cols-2 gap-0.5 select-none">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChangeMode('page')}
        className={`flex items-center justify-center space-x-1.5 py-1.5 px-2.5 rounded-control text-2xs font-medium transition-all ${
          mode === 'page'
            ? 'bg-canvas-elevated text-content-primary border border-edge-strong shadow-sm'
            : 'text-content-secondary hover:text-content-primary hover:bg-canvas-hover border border-transparent'
        } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
      >
        <FileText className={`w-3.5 h-3.5 ${mode === 'page' ? 'text-teal' : 'text-content-muted'}`} />
        <span>Current Page</span>
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onChangeMode('site')}
        className={`flex items-center justify-center space-x-1.5 py-1.5 px-2.5 rounded-control text-2xs font-medium transition-all ${
          mode === 'site'
            ? 'bg-canvas-elevated text-content-primary border border-edge-strong shadow-sm'
            : 'text-content-secondary hover:text-content-primary hover:bg-canvas-hover border border-transparent'
        } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
      >
        <Globe className={`w-3.5 h-3.5 ${mode === 'site' ? 'text-teal' : 'text-content-muted'}`} />
        <span>Entire Website</span>
      </button>
    </div>
  );
};
