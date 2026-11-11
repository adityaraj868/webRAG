import React, { useState, useEffect } from 'react';
import { Play, Loader2, CheckCircle2, AlertTriangle, Layers, Globe } from 'lucide-react';
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
    setStatusMessage('Extracting page content...');

    try {
      let extractedData: any = null;

      if (typeof chrome !== 'undefined' && chrome.tabs && activeTab?.id) {
        try {
          const response = await chrome.tabs.sendMessage(activeTab.id, { type: 'EXTRACT_PAGE_CONTENT' });
          if (response && response.success) {
            extractedData = response.data;
          }
        } catch {
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

      setStatusMessage('Ingesting to vector index...');
      const res = await ingestPage({
        url: pageUrl,
        title: pageTitle,
        text: pageText,
        html: pageHtml,
      });

      setStatusMessage(
        res.already_indexed
          ? 'Page unchanged; index up to date.'
          : `Indexed ${res.chunks_indexed} chunks successfully.`
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
    <div className="bg-canvas-subtle border border-edge rounded-panel p-3 space-y-2.5">
      {mode === 'page' ? (
        <div className="space-y-2">
          <div className="space-y-1">
            <span className="text-2xs font-mono uppercase tracking-wider text-content-muted block">
              Active Document
            </span>
            <div className="p-2 rounded-control bg-canvas border border-edge text-xs">
              <p className="font-medium text-content-primary truncate">
                {activeTab?.title || 'No active tab detected'}
              </p>
              <p className="text-2xs text-content-secondary truncate mt-0.5 font-mono">
                {activeTab?.url || '—'}
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={indexing || !activeTab?.url}
            onClick={handleIndexPage}
            className={`w-full py-1.5 px-3 rounded-control text-xs font-medium flex items-center justify-center space-x-1.5 transition-colors select-none ${
              indexing
                ? 'bg-teal/50 text-[#111315] cursor-wait'
                : 'bg-teal hover:bg-teal-hover text-[#111315] active:bg-teal-hover cursor-pointer'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {indexing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Indexing Page...</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 fill-current" />
                <span>Index Active Page</span>
              </>
            )}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-2xs font-mono uppercase tracking-wider text-content-muted block">
              Target Origin
            </label>
            <input
              type="url"
              value={siteUrl}
              onChange={(e) => setSiteUrl(e.target.value)}
              placeholder="https://example.com"
              disabled={indexing}
              className="w-full px-2.5 py-1.5 rounded-control bg-canvas border border-edge text-xs text-content-primary placeholder-content-muted focus:outline-none focus:border-teal transition-colors font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <label className="text-2xs text-content-secondary block">Max Pages (1-50)</label>
              <input
                type="number"
                min={1}
                max={50}
                value={maxPages}
                onChange={(e) => setMaxPages(parseInt(e.target.value) || 10)}
                disabled={indexing}
                className="w-full mt-0.5 px-2 py-1 rounded-control bg-canvas border border-edge text-content-primary text-xs font-mono focus:outline-none focus:border-teal transition-colors"
              />
            </div>
            <div>
              <label className="text-2xs text-content-secondary block">Max Depth (1-5)</label>
              <input
                type="number"
                min={1}
                max={5}
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value) || 2)}
                disabled={indexing}
                className="w-full mt-0.5 px-2 py-1 rounded-control bg-canvas border border-edge text-content-primary text-xs font-mono focus:outline-none focus:border-teal transition-colors"
              />
            </div>
          </div>

          <button
            type="button"
            disabled={indexing || !siteUrl}
            onClick={handleIndexSite}
            className={`w-full py-1.5 px-3 rounded-control text-xs font-medium flex items-center justify-center space-x-1.5 transition-colors select-none ${
              indexing
                ? 'bg-teal/50 text-[#111315] cursor-wait'
                : 'bg-teal hover:bg-teal-hover text-[#111315] active:bg-teal-hover cursor-pointer'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            {indexing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Crawling Website...</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 fill-current" />
                <span>Crawl & Index Website</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Crawl progress details */}
      {crawlStatus && crawlStatus.status === 'running' && (
        <div className="bg-canvas border border-edge rounded-control p-2 text-xs space-y-1.5">
          <div className="flex justify-between text-2xs text-content-secondary">
            <span>Crawl Progress</span>
            <span className="font-mono text-teal">
              {crawlStatus.pages_crawled} / {maxPages} pages
            </span>
          </div>
          <div className="w-full bg-canvas-subtle h-1 rounded-full overflow-hidden border border-edge">
            <div
              className="bg-teal h-full transition-all duration-300"
              style={{ width: `${Math.min(100, (crawlStatus.pages_crawled / maxPages) * 100)}%` }}
            />
          </div>
          {crawlStatus.current_url && (
            <p className="text-2xs text-content-muted truncate font-mono">
              {crawlStatus.current_url}
            </p>
          )}
        </div>
      )}

      {/* Status or error feedback */}
      {statusMessage && (
        <div className="flex items-center space-x-1.5 text-2xs text-teal bg-teal-subtle border border-teal-border rounded-control p-2">
          <CheckCircle2 className="w-3 h-3 text-teal flex-shrink-0" />
          <span className="truncate">{statusMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center space-x-1.5 text-2xs text-coral bg-coral-subtle border border-coral-border rounded-control p-2">
          <AlertTriangle className="w-3 h-3 text-coral flex-shrink-0" />
          <span className="truncate">{errorMessage}</span>
        </div>
      )}

      {/* Scope summary metadata */}
      {scopeDetails && (
        <div className="flex items-center justify-between text-2xs text-content-secondary bg-canvas border border-edge rounded-control px-2.5 py-1.5">
          <div className="flex items-center space-x-1.5 truncate">
            <Layers className="w-3 h-3 text-teal flex-shrink-0" />
            <span className="font-mono text-content-primary">
              {scopeDetails.page_count} {scopeDetails.page_count === 1 ? 'page' : 'pages'}
            </span>
            <span className="text-content-muted">•</span>
            <span className="font-mono text-content-primary">
              {scopeDetails.chunk_count} chunks
            </span>
          </div>
          <span className="text-2xs text-content-muted font-mono truncate max-w-[110px]" title={scopeDetails.scope_id}>
            {scopeDetails.scope_id}
          </span>
        </div>
      )}
    </div>
  );
};
