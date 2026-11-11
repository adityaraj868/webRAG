import React, { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronUp, Bookmark } from 'lucide-react';
import { Citation } from '../types';

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export const CitationCard: React.FC<CitationCardProps> = ({ citation, index }) => {
  const [expanded, setExpanded] = useState(false);

  const handleOpenSource = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (citation.source_url) {
      if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
        chrome.tabs.create({ url: citation.source_url });
      } else {
        window.open(citation.source_url, '_blank', 'noopener,noreferrer');
      }
    }
  };

  const domain = (() => {
    try {
      return new URL(citation.source_url).hostname;
    } catch {
      return citation.source_url;
    }
  })();

  return (
    <div className="text-xs bg-slate-900/90 border border-slate-800 rounded-lg overflow-hidden transition-all hover:border-slate-700">
      <div
        onClick={() => setExpanded(!expanded)}
        className="p-2.5 flex items-start justify-between cursor-pointer hover:bg-slate-800/40"
      >
        <div className="flex items-start space-x-2 flex-1 min-w-0 pr-2">
          <span className="flex-shrink-0 w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 font-mono text-[10px] flex items-center justify-center font-bold">
            {index + 1}
          </span>
          <div className="min-w-0 flex-1">
            <h4 className="font-medium text-slate-200 truncate leading-snug">
              {citation.page_title || 'Untitled Document'}
            </h4>
            <div className="flex items-center space-x-1.5 text-[11px] text-slate-400 mt-0.5">
              <span className="truncate max-w-[160px] text-slate-500">{domain}</span>
              <span>•</span>
              <span className="text-slate-500 font-mono">Chunk {citation.chunk_index}</span>
              {typeof citation.relevance_score === 'number' && (
                <>
                  <span>•</span>
                  <span className="text-emerald-400/90 font-mono">
                    {(citation.relevance_score * 100).toFixed(0)}%
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-1 flex-shrink-0">
          <button
            onClick={handleOpenSource}
            title="Open in new tab"
            className="p-1 rounded text-slate-400 hover:text-indigo-400 hover:bg-indigo-950/40 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            className="p-1 rounded text-slate-400 hover:text-slate-200 transition-colors"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-800/60 bg-slate-950/60 text-slate-300">
          <p className="text-[11px] leading-relaxed italic border-l-2 border-indigo-500/50 pl-2 text-slate-300 font-sans whitespace-pre-wrap">
            "{citation.content_excerpt}"
          </p>
          <div className="mt-2 flex justify-end">
            <button
              onClick={handleOpenSource}
              className="text-[11px] text-indigo-400 hover:text-indigo-300 underline inline-flex items-center space-x-1"
            >
              <span>View full source</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
