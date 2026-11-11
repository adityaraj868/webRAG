import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Sparkles, MessageSquare } from 'lucide-react';
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
    'What is the main topic of this page?',
    'Summarize the key points in 3 bullets.',
    'What tools or technologies are mentioned?',
  ];

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-slate-950/40 rounded-xl border border-slate-800/80 overflow-hidden">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 space-y-3">
            <div className="w-10 h-10 rounded-full bg-indigo-950/50 border border-indigo-800/40 flex items-center justify-center text-indigo-400">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-slate-200">
                {hasIndexedContent ? 'Ask Anything About This Content' : 'No Content Indexed Yet'}
              </h3>
              <p className="text-[11px] text-slate-400 max-w-[240px]">
                {hasIndexedContent
                  ? 'Ask natural-language questions grounded strictly in the indexed content with source citations.'
                  : 'Index the current page or crawl a website above to start asking questions.'}
              </p>
            </div>

            {hasIndexedContent && (
              <div className="pt-2 w-full space-y-1.5">
                <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider block">
                  Suggested Questions
                </span>
                {samplePrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInput(prompt);
                    }}
                    className="w-full text-left p-2 rounded-lg bg-slate-900 border border-slate-800/80 hover:border-indigo-600/50 hover:bg-slate-850 text-xs text-slate-300 transition-colors flex items-center space-x-1.5"
                  >
                    <Sparkles className="w-3 h-3 text-indigo-400 flex-shrink-0" />
                    <span className="truncate">{prompt}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg) => <MessageItem key={msg.id} message={msg} />)
        )}

        {loading && (
          <div className="flex items-center space-x-2 text-xs text-indigo-300 bg-indigo-950/20 border border-indigo-900/30 rounded-lg p-2.5 w-fit">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
            <span>Retrieving context and generating grounded answer...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input box */}
      <form onSubmit={handleSubmit} className="p-2.5 bg-slate-900 border-t border-slate-800 flex items-center space-x-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={hasIndexedContent ? 'Ask a question about the indexed content...' : 'Index content above first...'}
          disabled={!hasIndexedContent || loading}
          className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={!input.trim() || !hasIndexedContent || loading}
          className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 disabled:cursor-not-allowed shadow-sm transition-colors"
          title="Send question"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
};
