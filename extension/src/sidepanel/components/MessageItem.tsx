import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Bot, User, Bookmark } from 'lucide-react';
import { ChatMessage } from '../types';
import { CitationCard } from './CitationCard';

interface MessageItemProps {
  message: ChatMessage;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex flex-col space-y-2 ${isUser ? 'items-end' : 'items-start'}`}>
      <div className={`flex items-start space-x-2 max-w-[92%] ${isUser ? 'flex-row-reverse space-x-reverse' : 'flex-row'}`}>
        <div
          className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 text-xs ${
            isUser ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-indigo-400 border border-slate-700'
          }`}
        >
          {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
        </div>

        <div
          className={`rounded-xl px-3.5 py-2.5 text-xs leading-relaxed shadow-sm ${
            isUser
              ? 'bg-indigo-600 text-white rounded-tr-none'
              : 'bg-slate-800/80 border border-slate-700/70 text-slate-200 rounded-tl-none'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-xs max-w-none space-y-2">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>

      {/* Citations section if present */}
      {!isUser && message.citations && message.citations.length > 0 && (
        <div className="w-full pl-8 space-y-1.5 mt-1">
          <div className="flex items-center space-x-1.5 text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
            <Bookmark className="w-3 h-3 text-indigo-400" />
            <span>Retrieved Sources ({message.citations.length})</span>
          </div>
          <div className="space-y-1.5">
            {message.citations.map((citation, idx) => (
              <CitationCard key={idx} citation={citation} index={idx} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
