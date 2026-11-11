import {
  HealthResponse,
  IngestPageResponse,
  IngestSiteResponse,
  CrawlJobStatus,
  ChatResponse,
  ScopeDetails,
} from '../types';

let BACKEND_URL = 'http://127.0.0.1:8000';

export function setBackendUrl(url: string) {
  BACKEND_URL = url.replace(/\/+$/, '');
}

export function getBackendUrl(): string {
  return BACKEND_URL;
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v1/health`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Health check failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function ingestPage(payload: {
  url: string;
  title?: string;
  text?: string;
  html?: string;
  scope_id?: string;
}): Promise<IngestPageResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v1/ingest/page`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Ingest page failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function ingestSite(payload: {
  url: string;
  max_pages?: number;
  max_depth?: number;
  concurrency?: number;
  scope_id?: string;
}): Promise<IngestSiteResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v1/ingest/site`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Ingest site failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function getCrawlStatus(jobId: string): Promise<CrawlJobStatus> {
  const res = await fetch(`${BACKEND_URL}/api/v1/ingest/status/${jobId}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Get status failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function sendChatMessage(payload: {
  scope_id: string;
  question: string;
  top_k?: number;
}): Promise<ChatResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Chat query failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function getScopeDetails(scopeId: string): Promise<ScopeDetails> {
  const res = await fetch(`${BACKEND_URL}/api/v1/scopes/${encodeURIComponent(scopeId)}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Get scope failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteScope(scopeId: string): Promise<{ deleted: boolean; scope_id: string }> {
  const res = await fetch(`${BACKEND_URL}/api/v1/scopes/${encodeURIComponent(scopeId)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Delete scope failed with HTTP ${res.status}`);
  }
  return res.json();
}
