import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { ScopeSelector } from './components/ScopeSelector';
import { IndexingPanel } from './components/IndexingPanel';
import { ChatView } from './components/ChatView';
import { ScopeMode, ChatMessage, HealthResponse, ScopeDetails } from './types';
import { checkHealth, sendChatMessage, getScopeDetails, deleteScope } from './api/client';

export const App: React.FC = () => {
  const [mode, setMode] = useState<ScopeMode>('page');
  const [scopeId, setScopeId] = useState<string | null>(null);
  const [scopeDetails, setScopeDetails] = useState<ScopeDetails | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Load backend health status
  const refreshHealth = useCallback(async () => {
    try {
      const data = await checkHealth();
      setHealth(data);
      setHealthError(null);
    } catch (err: any) {
      setHealth(null);
      setHealthError(err.message || 'Cannot reach backend service at 127.0.0.1:8000');
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    const interval = setInterval(refreshHealth, 15000);
    return () => clearInterval(interval);
  }, [refreshHealth]);

  // Load scope metadata when scopeId updates
  const loadScopeDetails = useCallback(async (id: string) => {
    try {
      const details = await getScopeDetails(id);
      setScopeDetails(details);
    } catch (err) {
      console.warn('Failed to load scope details:', err);
    }
  }, []);

  const handleScopeIndexed = (newScopeId: string) => {
    setScopeId(newScopeId);
    loadScopeDetails(newScopeId);
    const welcomeMsg: ChatMessage = {
      id: `sys_${Date.now()}`,
      role: 'assistant',
      content: `**Scope indexed:** \`${newScopeId}\`.\n\nYou can now ask specific questions or request a full summary.`,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, welcomeMsg]);
  };

  const handleClearIndex = async () => {
    if (!scopeId) return;
    const confirmClear = window.confirm(`Clear active index scope "${scopeId}"?`);
    if (!confirmClear) return;

    try {
      await deleteScope(scopeId);
      setScopeId(null);
      setScopeDetails(null);
      setMessages([]);
    } catch (err: any) {
      alert(`Error clearing index: ${err.message}`);
    }
  };

  const handleSendMessage = async (question: string) => {
    if (!scopeId) return;

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setChatLoading(true);

    try {
      const response = await sendChatMessage({
        scope_id: scopeId,
        question,
        top_k: 5,
      });

      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        role: 'assistant',
        content: `**Error:** Unable to query WebRAG backend: ${err.message}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-canvas text-content-primary overflow-hidden text-xs font-sans">
      {/* Sleek Top Header */}
      <Header
        health={health}
        healthError={healthError}
        onRefreshHealth={refreshHealth}
        onClearIndex={handleClearIndex}
        hasIndexedContent={Boolean(scopeId && (scopeDetails?.chunk_count || 0) > 0)}
        scopeId={scopeId}
      />

      {/* Main Content Workspace */}
      <div className="flex-1 flex flex-col p-2.5 space-y-2.5 min-h-0 overflow-hidden">
        {/* Scope Mode Segmented Control */}
        <ScopeSelector mode={mode} onChangeMode={setMode} disabled={chatLoading} />

        {/* Indexing Action Panel */}
        <IndexingPanel
          mode={mode}
          scopeId={scopeId}
          onScopeIndexed={handleScopeIndexed}
          scopeDetails={scopeDetails}
        />

        {/* RAG Inquiry and Chat View */}
        <ChatView
          messages={messages}
          onSendMessage={handleSendMessage}
          loading={chatLoading}
          scopeId={scopeId}
          hasIndexedContent={Boolean(scopeId)}
        />
      </div>
    </div>
  );
};
