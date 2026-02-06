/**
 * OmniBar Component — Universal Natural Language Command Bar
 *
 * A floating command bar at the top of the app that accepts natural language
 * commands to add transactions, create goals, set budgets, query spending,
 * and chat with the AI financial assistant.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send,
  X,
  Sparkles,
  ChevronDown,
  Loader2,
  ArrowRight,
  Zap,
} from 'lucide-react';
import { omnibarApi, type OmniBarMessage, type OmniBarResponse } from '../api/omnibar';
import './OmniBar.css';

// Keyboard shortcut constant
const SHORTCUT_KEY = 'k';

// Quick action chips
const QUICK_ACTIONS = [
  { label: 'Add expense', prompt: 'Spent ₹ on ' },
  { label: 'Check spending', prompt: 'How much did I spend last month?' },
  { label: 'Goal progress', prompt: 'Show my goals progress' },
  { label: 'Budget status', prompt: 'Am I over budget?' },
  { label: 'Financial overview', prompt: "What's my savings rate?" },
];

function OmniBar() {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState<OmniBarMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestion, setSelectedSuggestion] = useState(-1);

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const suggestionsTimeoutRef = useRef<ReturnType<typeof setTimeout>>(null);
  const omnibarRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current && isExpanded) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isExpanded]);

  // Global keyboard shortcut: Ctrl/Cmd + K to open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === SHORTCUT_KEY) {
        e.preventDefault();
        setIsOpen(true);
        setTimeout(() => inputRef.current?.focus(), 100);
      }
      if (e.key === 'Escape') {
        if (showSuggestions) {
          setShowSuggestions(false);
        } else if (isExpanded) {
          setIsExpanded(false);
        } else if (isOpen) {
          setIsOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isExpanded, showSuggestions]);

  // Click outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (omnibarRef.current && !omnibarRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch suggestions with debounce
  const fetchSuggestions = useCallback(async (text: string) => {
    if (suggestionsTimeoutRef.current) {
      clearTimeout(suggestionsTimeoutRef.current);
    }

    if (text.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    suggestionsTimeoutRef.current = setTimeout(async () => {
      try {
        const results = await omnibarApi.suggest(text);
        setSuggestions(results);
        setShowSuggestions(results.length > 0);
        setSelectedSuggestion(-1);
      } catch {
        // Silently fail for suggestions
      }
    }, 300);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputValue(value);
    fetchSuggestions(value);
  };

  const selectSuggestion = (suggestion: string) => {
    setInputValue(suggestion);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const handleSubmit = async (overrideText?: string) => {
    const text = overrideText || inputValue.trim();
    if (!text || isLoading) return;

    // Add user message
    const userMessage: OmniBarMessage = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setShowSuggestions(false);
    setIsLoading(true);
    setIsExpanded(true);

    try {
      const response: OmniBarResponse = await omnibarApi.process(text, messages);

      const assistantMessage: OmniBarMessage = {
        role: 'assistant',
        content: response.message,
        intent: response.intent,
        data: response.data,
        suggestions: response.suggestions,
        timestamp: new Date().toISOString(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: any) {
      const errorMessage: OmniBarMessage = {
        role: 'assistant',
        content: error?.response?.data?.detail || 'Something went wrong. Please try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (showSuggestions && selectedSuggestion >= 0) {
        selectSuggestion(suggestions[selectedSuggestion]);
      } else {
        handleSubmit();
      }
    }
    if (e.key === 'ArrowDown' && showSuggestions) {
      e.preventDefault();
      setSelectedSuggestion(prev => 
        prev < suggestions.length - 1 ? prev + 1 : 0
      );
    }
    if (e.key === 'ArrowUp' && showSuggestions) {
      e.preventDefault();
      setSelectedSuggestion(prev => 
        prev > 0 ? prev - 1 : suggestions.length - 1
      );
    }
  };

  const clearConversation = () => {
    setMessages([]);
    setIsExpanded(false);
  };

  const handleQuickAction = (prompt: string) => {
    setInputValue(prompt);
    inputRef.current?.focus();
    // Position cursor at end or at placeholder
    setTimeout(() => {
      if (inputRef.current) {
        const pos = prompt.indexOf('₹');
        if (pos >= 0) {
          inputRef.current.setSelectionRange(pos + 2, pos + 2);
        }
      }
    }, 50);
  };

  // Intent badge color mapping
  const getIntentBadge = (intent?: string) => {
    if (!intent) return null;
    const badges: Record<string, { label: string; className: string }> = {
      add_transaction: { label: 'Transaction Added', className: 'badge-success' },
      add_goal: { label: 'Goal Created', className: 'badge-success' },
      add_budget: { label: 'Budget Set', className: 'badge-success' },
      update_goal_progress: { label: 'Goal Updated', className: 'badge-success' },
      query_spending: { label: 'Spending Query', className: 'badge-info' },
      query_goal: { label: 'Goal Query', className: 'badge-info' },
      query_budget: { label: 'Budget Query', className: 'badge-info' },
      query_general: { label: 'Overview', className: 'badge-info' },
      chat: { label: 'AI Chat', className: 'badge-ai' },
    };
    const badge = badges[intent];
    if (!badge) return null;
    return <span className={`omni-badge ${badge.className}`}>{badge.label}</span>;
  };

  // Render markdown-like formatting in messages
  const formatMessage = (text: string) => {
    // Split into lines and process
    const lines = text.split('\n');
    return lines.map((line, i) => {
      // Bold: **text**
      let processed = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      // Progress bars with blocks
      processed = processed.replace(/([█░]+)/g, '<span class="progress-bar-text">$1</span>');

      if (line.startsWith('• ') || line.startsWith('- ')) {
        return (
          <div key={i} className="omni-msg-bullet" dangerouslySetInnerHTML={{ __html: processed.slice(2) }} />
        );
      }
      if (line.trim() === '') {
        return <div key={i} className="omni-msg-spacer" />;
      }
      return <div key={i} dangerouslySetInnerHTML={{ __html: processed }} />;
    });
  };

  if (!isOpen) {
    return (
      <button
        className="omni-trigger"
        onClick={() => {
          setIsOpen(true);
          setTimeout(() => inputRef.current?.focus(), 100);
        }}
        title="Open OmniBar (Ctrl+K)"
      >
        <Sparkles size={18} />
        <span className="omni-trigger-text">Ask anything...</span>
        <kbd className="omni-shortcut">Ctrl K</kbd>
      </button>
    );
  }

  return (
    <div className={`omnibar-container ${isExpanded ? 'expanded' : ''}`} ref={omnibarRef}>
      {/* Backdrop for expanded mode */}
      {isExpanded && (
        <div className="omnibar-backdrop" onClick={() => setIsExpanded(false)} />
      )}

      <div className={`omnibar ${isExpanded ? 'omnibar-expanded' : ''}`}>
        {/* Header */}
        <div className="omnibar-header">
          <div className="omnibar-input-row">
            <Sparkles size={18} className="omnibar-icon" />
            <input
              ref={inputRef}
              type="text"
              className="omnibar-input"
              placeholder="Type a command or ask anything... (Esc to close)"
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (inputValue.length >= 2) setShowSuggestions(true);
              }}
              autoFocus
            />
            {isLoading ? (
              <Loader2 size={18} className="omnibar-loading spin" />
            ) : inputValue ? (
              <button className="omnibar-send" onClick={() => handleSubmit()} title="Send">
                <Send size={16} />
              </button>
            ) : null}
            <button
              className="omnibar-close"
              onClick={() => {
                setIsOpen(false);
                setIsExpanded(false);
                setShowSuggestions(false);
              }}
              title="Close (Esc)"
            >
              <X size={16} />
            </button>
          </div>

          {/* Suggestions dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="omnibar-suggestions">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className={`omnibar-suggestion ${i === selectedSuggestion ? 'selected' : ''}`}
                  onClick={() => selectSuggestion(s)}
                >
                  <ArrowRight size={14} />
                  <span>{s}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quick actions (shown when no messages) */}
        {!isExpanded && messages.length === 0 && (
          <div className="omnibar-quick-actions">
            {QUICK_ACTIONS.map((action, i) => (
              <button
                key={i}
                className="quick-action-chip"
                onClick={() => handleQuickAction(action.prompt)}
              >
                <Zap size={12} />
                {action.label}
              </button>
            ))}
          </div>
        )}

        {/* Messages area (expanded view) */}
        {isExpanded && (
          <div className="omnibar-messages">
            {messages.length === 0 && (
              <div className="omnibar-empty">
                <Sparkles size={24} />
                <p>Ask me anything about your finances!</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`omni-message omni-message-${msg.role}`}>
                {msg.role === 'assistant' && (
                  <div className="omni-message-header">
                    <Sparkles size={14} />
                    <span>AI Assistant</span>
                    {getIntentBadge(msg.intent)}
                  </div>
                )}
                <div className="omni-message-content">
                  {formatMessage(msg.content)}
                </div>
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="omni-suggestions-inline">
                    <span className="suggestion-label">Try:</span>
                    {msg.suggestions.map((s, j) => (
                      <button
                        key={j}
                        className="suggestion-chip"
                        onClick={() => handleSubmit(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="omni-message omni-message-assistant">
                <div className="omni-message-header">
                  <Sparkles size={14} />
                  <span>AI Assistant</span>
                </div>
                <div className="omni-message-content omni-typing">
                  <span></span><span></span><span></span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Footer with expand/collapse and clear */}
        {(messages.length > 0 || isExpanded) && (
          <div className="omnibar-footer">
            <button
              className="omnibar-toggle-expand"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              <ChevronDown size={14} className={isExpanded ? 'rotate-180' : ''} />
              {isExpanded ? 'Collapse' : `${messages.length} messages`}
            </button>
            {messages.length > 0 && (
              <button className="omnibar-clear" onClick={clearConversation}>
                Clear
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default OmniBar;
