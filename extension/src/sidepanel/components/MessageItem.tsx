import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Bookmark } from 'lucide-react';
import { ChatMessage } from '../types';
import { CitationCard } from './CitationCard';

interface MessageItemProps {
  message: ChatMessage;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end select-text">
        <div className="max-w-[88%] rounded-panel bg-canvas-elevated border border-edge px-3 py-2 text-xs text-content-primary shadow-sm leading-relaxed">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-2 select-text w-full">
      {/* Assistant Response Body */}
      <div className="w-full text-xs text-content-primary leading-relaxed">
        <div className="markdown-body">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      </div>

      {/* Sources and Citations */}
      {message.citations && message.citations.length > 0 && (
        <div className="w-full pt-1.5 space-y-1.5">
          <div className="flex items-center space-x-1.5 text-2xs font-mono uppercase tracking-wider text-content-muted select-none">
            <Bookmark className="w-3 h-3 text-teal flex-shrink-0" />
            <span>Citations ({message.citations.length})</span>
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
