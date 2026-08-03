import { useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext';
import Message, { StreamingMessage, ImageGeneratingIndicator } from './Message';
import WelcomeScreen from './WelcomeScreen';
import ToolActivityIndicator from './ToolActivityIndicator';

export default function ChatArea() {
  const { state } = useApp();
  const { messages, streamContent, isGenerating, imageGenerating, toolActivity } = state;
  const bottomRef = useRef();
  const areaRef   = useRef();

  const hasContent = messages.length > 0 || isGenerating;

  // Auto-scroll to bottom
  useEffect(() => {
    const area = areaRef.current;
    if (!area) return;
    const isNearBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 150;
    if (isNearBottom || isGenerating) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, streamContent, isGenerating, imageGenerating, toolActivity]);

  return (
    <div className="messages-scroll" ref={areaRef}>
      {!hasContent ? (
        <WelcomeScreen />
      ) : (
        <div className="messages-inner">
          {messages.map(msg => (
            <Message key={msg.id} msg={msg} />
          ))}

          {/* Phase 3: Tool activity indicator */}
          {isGenerating && toolActivity && (
            <ToolActivityIndicator activity={toolActivity} />
          )}

          {/* Image is being generated — show spinner card */}
          {isGenerating && imageGenerating !== null && !streamContent && !toolActivity && (
            <ImageGeneratingIndicator prompt={imageGenerating} />
          )}

          {/* Normal text streaming */}
          {isGenerating && streamContent && (
            <StreamingMessage content={streamContent} />
          )}

          <div ref={bottomRef} style={{ height: 1 }} />
        </div>
      )}
    </div>
  );
}
