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

  // Load backend health
  const refreshHealth = useCallback(async () => {
    try {
      const data = await checkHealth();
      setHealth(data);
      setHealthError(null);
    } catch (err: any) {
      setHealth(null);
      setHealthError(err.message || 'Cannot connect to backend at 127.0.0.1:8000');
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    const interval = setInterval(refreshHealth, 15000);
    return () => clearInterval(interval);
  }, [refreshHealth]);

  // Load scope details when scopeId changes
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
    // Add welcoming message
    const welcomeMsg: ChatMessage = {
      id: `sys_${Date.now()}`,
      role: 'assistant',
      content: `✅ **Content indexed successfully!** Scope: \`${newScopeId}\`.\n\nYou can now ask questions about the indexed content.`,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, welcomeMsg]);
  };

  const handleClearIndex = async () => {
    if (!scopeId) return;
    const confirmClear = window.confirm(`Clear indexed content for scope "${scopeId}"?`);
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
        content: `❌ **Error querying WebRAG:** ${err.message}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 overflow-hidden text-xs">
      {/* Top Header */}
      <Header
        health={health}
        healthError={healthError}
        onRefreshHealth={refreshHealth}
        onClearIndex={handleClearIndex}
        hasIndexedContent={Boolean(scopeId && (scopeDetails?.chunk_count || 0) > 0)}
        scopeId={scopeId}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col p-3 space-y-3 min-h-0 overflow-hidden">
        {/* Scope Mode Selector */}
        <ScopeSelector mode={mode} onChangeMode={setMode} disabled={chatLoading} />

        {/* Indexing Action Panel */}
        <IndexingPanel
          mode={mode}
          scopeId={scopeId}
          onScopeIndexed={handleScopeIndexed}
          scopeDetails={scopeDetails}
        />

        {/* RAG Chat View */}
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
