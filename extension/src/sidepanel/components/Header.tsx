import React from 'react';
import { Trash2, RefreshCw } from 'lucide-react';
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
  const groqReady = health?.groq_configured;

  const statusTooltip = healthError
    ? `Backend unreachable: ${healthError}`
    : isHealthy
    ? groqReady
      ? 'Backend connected • Groq LLM ready'
      : 'Backend connected • Warning: GROQ_API_KEY missing'
    : 'Connecting to backend...';

  return (
    <header className="border-b border-edge bg-canvas px-3.5 py-2.5 flex items-center justify-between select-none">
      {/* Brand & Wordmark */}
      <div className="flex items-center space-x-2">
        <div className="w-5 h-5 rounded-control bg-canvas-elevated border border-edge-strong flex items-center justify-center">
          <span className="font-mono font-bold text-[11px] text-teal leading-none">W</span>
        </div>
        <div className="flex items-baseline space-x-1.5">
          <span className="font-semibold text-xs tracking-tight text-content-primary">WebRAG</span>
          <span className="font-mono text-2xs text-content-muted tracking-wide uppercase">research</span>
        </div>
      </div>

      {/* Controls & Connection Status */}
      <div className="flex items-center space-x-1.5">
        {/* Connection status pill */}
        <button
          type="button"
          onClick={onRefreshHealth}
          title={`${statusTooltip} (Click to refresh)`}
          className="flex items-center space-x-1.5 px-2 py-1 rounded-control bg-canvas-subtle border border-edge hover:border-edge-strong text-content-secondary transition-colors text-2xs"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              isHealthy
                ? groqReady
                  ? 'bg-teal'
                  : 'bg-amber'
                : 'bg-coral'
            }`}
          />
          <span className="font-mono">
            {isHealthy ? (groqReady ? 'online' : 'no llm key') : 'offline'}
          </span>
        </button>

        {/* Clear index action */}
        {hasIndexedContent && (
          <button
            type="button"
            onClick={onClearIndex}
            className="p-1 rounded-control text-content-secondary hover:text-coral hover:bg-coral-subtle border border-transparent hover:border-coral-border transition-colors"
            title={`Clear active scope (${scopeId})`}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </header>
  );
};
