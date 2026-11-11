export type ScopeMode = 'page' | 'site';

export interface Citation {
  source_url: string;
  page_title: string;
  chunk_index: number;
  content_excerpt: string;
  relevance_score?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: Citation[];
  timestamp: string;
}

export interface PageMetadata {
  url: string;
  title: string;
  chunk_count: number;
  content_hash: string;
  indexed_at: string;
}

export interface ScopeDetails {
  scope_id: string;
  type: ScopeMode;
  base_url: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
  pages: PageMetadata[];
}

export interface IngestPageResponse {
  scope_id: string;
  page_title: string;
  source_url: string;
  chunks_indexed: number;
  already_indexed: boolean;
  status: string;
  message?: string;
}

export interface IngestSiteResponse {
  job_id: string;
  scope_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message?: string;
}

export interface CrawlJobStatus {
  job_id: string;
  scope_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  pages_crawled: number;
  pages_indexed: number;
  total_chunks: number;
  current_url?: string;
  error?: string | null;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  scope_id: string;
  context_found: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  vector_store: string;
  embeddings: string;
  groq_configured: boolean;
  model: string;
}
