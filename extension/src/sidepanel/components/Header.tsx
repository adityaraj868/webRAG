import React from 'react';
import { Database, ShieldCheck, AlertCircle, RefreshCw } from 'lucide-react';
import { HealthResponse } from '../types';

interface HeaderProps {
  health: HealthResponse | null;
  healthError: string | null;
  onRefreshHealth: () => void;
  onClearIndex: () => void;
  hasIndexedContent: boolean;
  scopeId: string | null;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  healthError,
  onRefreshHealth,
  onClearIndex,
  hasIndexedContent,
  scopeId,
}) => {
  const isHealthy = health?.status === 'healthy';

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-20 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center space-x-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-md shadow-indigo-500/20">
          <Database className="w-4 h-4 text-white" />
        </div>
        <div>
          <div className="flex items-center space-x-1.5">
            <h1 className="font-semibold text-sm text-slate-100 tracking-tight">WebRAG</h1>
            <span className="text-[10px] font-medium uppercase px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              MVP
            </span>
          </div>
          <p className="text-[11px] text-slate-400 leading-tight">Grounded Knowledge Assistant</p>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        {/* Backend health status pill */}
        <div
          onClick={onRefreshHealth}
          className={`flex items-center space-x-1.5 px-2 py-1 rounded-full text-[11px] cursor-pointer transition-colors border ${
            isHealthy
              ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50 hover:bg-emerald-950/60'
              : 'bg-rose-950/40 text-rose-400 border-rose-800/50 hover:bg-rose-950/60'
          }`}
          title={healthError || (isHealthy ? `Backend ready (Groq: ${health?.groq_configured ? 'configured' : 'missing key'})` : 'Backend unreachable')}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
            }`}
          />
          <span className="font-medium">{isHealthy ? 'Backend Ready' : 'Offline'}</span>
        </div>

        {/* Clear index action */}
        {hasIndexedContent && (
          <button
            onClick={onClearIndex}
            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 rounded border border-transparent hover:border-rose-900/50 transition-colors"
            title={`Clear active scope (${scopeId})`}
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </header>
  );
};
