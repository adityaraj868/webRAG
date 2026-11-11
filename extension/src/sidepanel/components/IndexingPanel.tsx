import React, { useState, useEffect } from 'react';
import { Play, Loader2, CheckCircle2, AlertTriangle, Layers, ExternalLink } from 'lucide-react';
import { ScopeMode, CrawlJobStatus, ScopeDetails } from '../types';
import { ingestPage, ingestSite, getCrawlStatus } from '../api/client';

interface IndexingPanelProps {
  mode: ScopeMode;
  scopeId: string | null;
  onScopeIndexed: (scopeId: string, details?: any) => void;
  scopeDetails: ScopeDetails | null;
}

export const IndexingPanel: React.FC<IndexingPanelProps> = ({
  mode,
  scopeId,
  onScopeIndexed,
  scopeDetails,
}) => {
  const [activeTab, setActiveTab] = useState<{ id?: number; title?: string; url?: string } | null>(null);
  const [siteUrl, setSiteUrl] = useState('');
  const [maxPages, setMaxPages] = useState(10);
  const [maxDepth, setMaxDepth] = useState(2);

  const [indexing, setIndexing] = useState(false);
  const [crawlStatus, setCrawlStatus] = useState<CrawlJobStatus | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Read active browser tab and update on tab changes
  useEffect(() => {
    const updateActiveTab = () => {
      if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.query) {
        chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
          if (tab) {
            setActiveTab({ id: tab.id, title: tab.title, url: tab.url });
            if (tab.url) {
              try {
                const parsed = new URL(tab.url);
                if (parsed.protocol.startsWith('http')) {
                  setSiteUrl(parsed.origin);
                }
              } catch {
                // Ignore invalid url
              }
            }
          }
        }).catch((err) => console.warn('Could not query active tab:', err));
      }
    };

    updateActiveTab();

    if (typeof chrome !== 'undefined' && chrome.tabs) {
      if (chrome.tabs.onActivated) {
        chrome.tabs.onActivated.addListener(updateActiveTab);
      }
      if (chrome.tabs.onUpdated) {
        chrome.tabs.onUpdated.addListener(updateActiveTab);
      }
    }

    return () => {
      if (typeof chrome !== 'undefined' && chrome.tabs) {
        if (chrome.tabs.onActivated) {
          chrome.tabs.onActivated.removeListener(updateActiveTab);
        }
        if (chrome.tabs.onUpdated) {
          chrome.tabs.onUpdated.removeListener(updateActiveTab);
        }
      }
    };
  }, []);

  // Poll crawl job status if active
  useEffect(() => {
    if (!crawlStatus || crawlStatus.status === 'completed' || crawlStatus.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await getCrawlStatus(crawlStatus.job_id);
        setCrawlStatus(updated);
        if (updated.status === 'completed') {
          setIndexing(false);
          setStatusMessage(`Crawled ${updated.pages_crawled} pages (${updated.total_chunks} chunks indexed)`);
          onScopeIndexed(updated.scope_id);
        } else if (updated.status === 'failed') {
          setIndexing(false);
          setErrorMessage(updated.error || 'Crawling failed');
        }
      } catch (err) {
        console.error('Error polling crawl status:', err);
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [crawlStatus, onScopeIndexed]);

  // Index active webpage
  const handleIndexPage = async () => {
    setIndexing(true);
    setErrorMessage(null);
    setStatusMessage('Extracting active page content...');

    try {
      let extractedData: any = null;

      if (typeof chrome !== 'undefined' && chrome.tabs && activeTab?.id) {
        try {
          // Attempt direct message to content script
          const response = await chrome.tabs.sendMessage(activeTab.id, { type: 'EXTRACT_PAGE_CONTENT' });
          if (response && response.success) {
            extractedData = response.data;
          }
        } catch {
          // If content script was not yet injected into tab, inject it on demand
          try {
            await chrome.scripting.executeScript({
              target: { tabId: activeTab.id },
              files: ['content-script.js'],
            });
            const response = await chrome.tabs.sendMessage(activeTab.id, { type: 'EXTRACT_PAGE_CONTENT' });
            if (response && response.success) {
              extractedData = response.data;
            }
          } catch (scriptErr) {
            console.warn('Could not inject content script:', scriptErr);
          }
        }
      }

      const pageUrl = extractedData?.url || activeTab?.url || 'https://example.com';
      const pageTitle = extractedData?.title || activeTab?.title || 'Active Page';
      const pageText = extractedData?.text || undefined;
      const pageHtml = extractedData?.html || undefined;

      setStatusMessage('Sending to WebRAG backend...');
      const res = await ingestPage({
        url: pageUrl,
        title: pageTitle,
        text: pageText,
        html: pageHtml,
      });

      setStatusMessage(
        res.already_indexed
          ? 'Page already indexed and unchanged.'
          : `Indexed ${res.chunks_indexed} chunks successfully!`
      );
      onScopeIndexed(res.scope_id);
    } catch (err: any) {
      console.error('Page indexing error:', err);
      setErrorMessage(err.message || 'Failed to index webpage');
    } finally {
      setIndexing(false);
    }
  };

  // Crawl and index website
  const handleIndexSite = async () => {
    if (!siteUrl) {
      setErrorMessage('Please enter a website URL');
      return;
    }

    setIndexing(true);
    setErrorMessage(null);
    setStatusMessage('Starting website crawler...');

    try {
      const res = await ingestSite({
        url: siteUrl,
        max_pages: maxPages,
        max_depth: maxDepth,
      });

      setCrawlStatus({
        job_id: res.job_id,
        scope_id: res.scope_id,
        status: 'running',
        pages_crawled: 0,
        pages_indexed: 0,
        total_chunks: 0,
      });
      setStatusMessage('Crawling website pages...');
      onScopeIndexed(res.scope_id);
    } catch (err: any) {
      console.error('Site indexing error:', err);
      setErrorMessage(err.message || 'Failed to start website crawling');
      setIndexing(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-3 shadow-sm">
      {mode === 'page' ? (
        <div className="space-y-2.5">
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
              Target Webpage
            </span>
            <div className="p-2 rounded-lg bg-slate-950/80 border border-slate-800/80 text-xs">
              <p className="font-medium text-slate-200 truncate">
                {activeTab?.title || 'No active tab detected'}
              </p>
              <p className="text-[11px] text-slate-500 truncate mt-0.5 font-mono">
                {activeTab?.url || '—'}
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={indexing || !activeTab?.url}
            onClick={handleIndexPage}
            className={`w-full py-2 px-3 rounded-lg text-xs font-medium flex items-center justify-center space-x-2 transition-all ${
              indexing
                ? 'bg-indigo-600/50 text-indigo-200 cursor-wait'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 active:scale-[0.99]'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {indexing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Indexing Page...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Index Active Page</span>
              </>
            )}
          </button>
        </div>
      ) : (
        <div className="space-y-2.5">
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
              Website URL
            </label>
            <input
              type="url"
              value={siteUrl}
              onChange={(e) => setSiteUrl(e.target.value)}
              placeholder="https://example.com"
              disabled={indexing}
              className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <label className="text-[10px] text-slate-400">Max Pages (1-50)</label>
              <input
                type="number"
                min={1}
                max={50}
                value={maxPages}
                onChange={(e) => setMaxPages(parseInt(e.target.value) || 10)}
                disabled={indexing}
                className="w-full mt-0.5 px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-400">Max Depth (1-5)</label>
              <input
                type="number"
                min={1}
                max={5}
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value) || 2)}
                disabled={indexing}
                className="w-full mt-0.5 px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          <button
            type="button"
            disabled={indexing || !siteUrl}
            onClick={handleIndexSite}
            className={`w-full py-2 px-3 rounded-lg text-xs font-medium flex items-center justify-center space-x-2 transition-all ${
              indexing
                ? 'bg-indigo-600/50 text-indigo-200 cursor-wait'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 active:scale-[0.99]'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {indexing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Crawling Website...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Crawl & Index Website</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Crawl progress details */}
      {crawlStatus && crawlStatus.status === 'running' && (
        <div className="bg-slate-950/90 border border-indigo-900/40 rounded-lg p-2.5 text-xs space-y-1.5 animate-pulse">
          <div className="flex justify-between text-[11px] text-slate-400">
            <span>Crawling Progress</span>
            <span className="font-mono text-indigo-400">
              {crawlStatus.pages_crawled}/{maxPages} pages
            </span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-indigo-500 h-full transition-all duration-300"
              style={{ width: `${Math.min(100, (crawlStatus.pages_crawled / maxPages) * 100)}%` }}
            />
          </div>
          {crawlStatus.current_url && (
            <p className="text-[10px] text-slate-500 truncate font-mono">
              Crawling: {crawlStatus.current_url}
            </p>
          )}
        </div>
      )}

      {/* Status or error badges */}
      {statusMessage && (
        <div className="flex items-center space-x-1.5 text-xs text-indigo-300 bg-indigo-950/30 border border-indigo-800/40 rounded-md p-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
          <span className="truncate">{statusMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center space-x-1.5 text-xs text-rose-300 bg-rose-950/40 border border-rose-800/50 rounded-md p-2">
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
          <span className="truncate">{errorMessage}</span>
        </div>
      )}

      {/* Scope summary badge */}
      {scopeDetails && (
        <div className="flex items-center justify-between text-[11px] text-slate-400 bg-slate-950/50 border border-slate-800/60 rounded-md px-2.5 py-1.5">
          <div className="flex items-center space-x-1.5 truncate">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span className="font-mono text-slate-300">{scopeDetails.page_count} page{scopeDetails.page_count === 1 ? '' : 's'}</span>
            <span>•</span>
            <span className="font-mono text-slate-300">{scopeDetails.chunk_count} chunks</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono truncate max-w-[100px]">
            {scopeDetails.scope_id}
          </span>
        </div>
      )}
    </div>
  );
};
