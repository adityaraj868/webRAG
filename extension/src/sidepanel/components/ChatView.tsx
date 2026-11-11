import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Loader2, Compass, CornerDownLeft } from 'lucide-react';
import { ChatMessage } from '../types';
import { MessageItem } from './MessageItem';

interface ChatViewProps {
  messages: ChatMessage[];
  onSendMessage: (question: string) => Promise<void>;
  loading: boolean;
  scopeId: string | null;
  hasIndexedContent: boolean;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  onSendMessage,
  loading,
  scopeId,
  hasIndexedContent,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;
    setInput('');
    await onSendMessage(query);
  };

  const samplePrompts = [
    'Summarize this page in 3 concise points',
    'What are the core conclusions and arguments?',
    'What key facts, data, or dates are mentioned?',
  ];

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-canvas-subtle rounded-panel border border-edge overflow-hidden">
      {/* Scrollable Messages Area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 space-y-3 select-none">
            <div className="w-8 h-8 rounded-control bg-canvas-elevated border border-edge flex items-center justify-center text-teal">
              <Compass className="w-4 h-4" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-content-primary">
                {hasIndexedContent ? 'Content Indexed & Ready' : 'No Active Index'}
              </h3>
              <p className="text-2xs text-content-secondary max-w-[240px] leading-relaxed">
                {hasIndexedContent
                  ? 'Ask questions grounded strictly in the active index. Every answer includes citations.'
                  : 'Index the active page or crawl a website domain above to begin inquiry.'}
              </p>
            </div>

            {hasIndexedContent && (
              <div className="pt-2 w-full space-y-1 text-left">
                <span className="text-2xs font-mono uppercase tracking-wider text-content-muted block px-1">
                  Suggested Queries
                </span>
                {samplePrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInput(prompt);
                    }}
                    className="w-full text-left p-2 rounded-control bg-canvas border border-edge hover:border-edge-strong text-2xs text-content-secondary hover:text-content-primary transition-colors flex items-center justify-between group"
                  >
                    <span className="truncate pr-2">{prompt}</span>
                    <CornerDownLeft className="w-2.5 h-2.5 text-content-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg) => <MessageItem key={msg.id} message={msg} />)
        )}

        {loading && (
          <div className="flex items-center space-x-2 text-2xs text-teal bg-teal-subtle border border-teal-border rounded-control p-2 w-fit">
            <Loader2 className="w-3 h-3 animate-spin text-teal" />
            <span className="font-mono">Retrieving grounded context & synthesizing answer...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Pinned Input Composer */}
      <form onSubmit={handleSubmit} className="p-2 bg-canvas border-t border-edge flex items-center space-x-1.5">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={hasIndexedContent ? 'Ask a question about the active document...' : 'Index document or site above first...'}
          disabled={!hasIndexedContent || loading}
          className="flex-1 bg-canvas-subtle border border-edge rounded-control px-2.5 py-1.5 text-xs text-content-primary placeholder-content-muted focus:outline-none focus:border-teal transition-colors disabled:opacity-40 disabled:cursor-not-allowed font-sans"
        />
        <button
          type="submit"
          disabled={!input.trim() || !hasIndexedContent || loading}
          className="p-1.5 rounded-control bg-teal hover:bg-teal-hover text-[#111315] disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex-shrink-0 cursor-pointer"
          title="Send query"
        >
          <ArrowUp className="w-3.5 h-3.5 stroke-[2.5]" />
        </button>
      </form>
    </div>
  );
};
