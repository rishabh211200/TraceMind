import React, { useEffect, useRef, useState } from 'react';
import {
  deleteConversation,
  getAnalystStats,
  getConversationById,
  listConversations,
  sendChatMessage,
} from '../api/analyst';
import {
  AnalystStats,
  Citation,
  ConversationItem,
  ToolCall,
  ToolResult,
} from '../types/analyst';
import { CitationBadge } from '../components/analyst/CitationBadge';
import { ToolExecutionCard } from '../components/analyst/ToolExecutionCard';
import {
  AlertTriangle,
  Bot,
  MessageSquare,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  Zap,
} from 'lucide-react';

interface LocalMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  toolCalls?: ToolCall[];
  toolResults?: ToolResult[];
  citations?: Citation[];
  groundingScore?: number;
}

const STARTER_PROMPTS = [
  {
    title: 'Diagnose Root Cause',
    query: 'What caused the failure in order_fulfillment execution exec_4a9b?',
    icon: '🔍',
  },
  {
    title: 'Explain ML Risk & SHAP',
    query: 'Explain the in-flight failure probability and TreeSHAP attributions for execution exec_4a9b.',
    icon: '📊',
  },
  {
    title: 'Optimize Workflow Path',
    query: 'What optimal routing detour does the optimizer recommend around inventory-db?',
    icon: '⚡',
  },
  {
    title: 'Inspect System Topology',
    query: 'Show me the managed microservice dependency topology and operational health.',
    icon: '🌐',
  },
];

export const AnalystView: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [stats, setStats] = useState<AnalystStats | null>(null);
  const [provider, setProvider] = useState<'mock' | 'openai'>('mock');
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const loadConversations = async () => {
    try {
      const items = await listConversations({ limit: 30 });
      setConversations(items);
      const st = await getAnalystStats();
      setStats(st);
    } catch (err: any) {
      console.error('Failed to load conversations:', err);
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  const handleSelectConversation = async (convId: string) => {
    setActiveConvId(convId);
    setError(null);
    try {
      const detail = await getConversationById(convId);
      const mapped: LocalMessage[] = detail.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        toolCalls: m.tool_calls as any,
        toolResults: m.tool_results as any,
        citations: m.citations as any,
        groundingScore: m.grounding_score,
      }));
      setMessages(mapped);
    } catch (err: any) {
      setError('Failed to load conversation messages.');
    }
  };

  const handleNewChat = () => {
    setActiveConvId(null);
    setMessages([]);
    setError(null);
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    try {
      await deleteConversation(convId);
      if (activeConvId === convId) {
        handleNewChat();
      }
      await loadConversations();
    } catch (err: any) {
      setError('Failed to delete conversation.');
    }
  };

  const handleSendMessage = async (queryText: string) => {
    const text = queryText.trim();
    if (!text || loading) return;

    setInputQuery('');
    setError(null);

    const userTempId = `user_${Date.now()}`;
    const newMsgList: LocalMessage[] = [
      ...messages,
      { id: userTempId, role: 'user', content: text },
    ];
    setMessages(newMsgList);
    setLoading(true);

    try {
      const response = await sendChatMessage({
        query: text,
        conversation_id: activeConvId || undefined,
        provider,
        persist: true,
      });

      if (!activeConvId) {
        setActiveConvId(response.conversation_id);
        await loadConversations();
      }

      setMessages([
        ...newMsgList,
        {
          id: response.message_id,
          role: 'assistant',
          content: response.content,
          toolCalls: response.tool_calls,
          toolResults: response.tool_results,
          citations: response.grounding_report.citations,
          groundingScore: response.grounding_report.grounding_score,
        },
      ]);
    } catch (err: any) {
      setError(err.message || 'Error generating grounded response.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-4 animate-fadeIn">
      {/* Sidebar: Conversation Sessions */}
      <div className="w-80 bg-slate-900/70 border border-slate-800 rounded-2xl flex flex-col overflow-hidden shadow-xl">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-indigo-400" />
            <span className="font-bold text-slate-100 text-sm">Diagnostic Sessions</span>
          </div>
          <button
            onClick={handleNewChat}
            className="p-1.5 rounded-lg bg-indigo-950/80 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 transition shadow-inner"
            title="New Diagnostic Chat"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {conversations.length === 0 ? (
            <div className="text-center p-6 text-slate-400 text-xs">
              No previous sessions. Start a new diagnostic query!
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConvId;
              return (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConversation(conv.id)}
                  className={`group px-3 py-2.5 rounded-xl cursor-pointer transition flex items-center justify-between text-xs ${
                    isActive
                      ? 'bg-indigo-950/70 border border-indigo-700/70 text-indigo-100'
                      : 'hover:bg-slate-800/60 text-slate-300 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate flex-1 mr-2">
                    <MessageSquare className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="truncate font-medium">{conv.title}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-400 rounded transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Bottom Stats Footer */}
        {stats && (
          <div className="p-3 bg-slate-950/60 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Grounding Score:</span>
            <span className="font-mono font-bold text-emerald-400">
              {(stats.average_grounding_score * 100).toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {/* Main Chat Assistant Area */}
      <div className="flex-1 bg-slate-900/60 border border-slate-800 rounded-2xl flex flex-col overflow-hidden shadow-xl">
        {/* Chat Header Bar */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-950/80 border border-indigo-700/60 rounded-xl text-indigo-400 shadow-inner">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-100 flex items-center gap-2">
                Conversational AI Analyst
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800">
                  Milestone 10
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Deterministic ReAct tool-grounding across M0–M9 telemetry, TreeSHAP, RCA & Optimizer.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <select
              value={provider}
              onChange={(e: any) => setProvider(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="mock">Local Deterministic Engine</option>
              <option value="openai">OpenAI (gpt-4o)</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="mx-4 mt-3 p-3 bg-rose-950/60 border border-rose-800 rounded-xl text-rose-200 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto text-center space-y-6">
              <div className="p-4 bg-indigo-950/50 border border-indigo-800/60 rounded-2xl text-indigo-400 shadow-2xl">
                <Bot className="w-12 h-12 mx-auto" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-100">
                  How can I assist your workflow investigation?
                </h2>
                <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                  Ask any question about root causes, failure risk factors, anomaly detections, or multi-objective path routing.
                </p>
              </div>

              {/* Starter Prompt Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
                {STARTER_PROMPTS.map((starter, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(starter.query)}
                    className="p-3.5 bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 hover:border-indigo-700/60 rounded-xl transition text-xs group shadow-md"
                  >
                    <div className="flex items-center gap-2 font-semibold text-slate-200 group-hover:text-indigo-300">
                      <span>{starter.icon}</span>
                      <span>{starter.title}</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">
                      {starter.query}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3.5 ${
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {msg.role !== 'user' && (
                  <div className="w-8 h-8 rounded-xl bg-indigo-950 border border-indigo-700/60 flex items-center justify-center text-indigo-400 shrink-0 shadow-sm">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-3xl rounded-2xl p-4 shadow-lg text-xs leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-none'
                      : 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-bl-none'
                  }`}
                >
                  {/* Tool Call Cards Accordion */}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="mb-3 space-y-1.5">
                      <div className="flex items-center gap-1 text-[11px] font-semibold text-slate-400">
                        <Zap className="w-3 h-3 text-indigo-400" />
                        <span>Platform Tools Invoked ({msg.toolCalls.length})</span>
                      </div>
                      {msg.toolCalls.map((tc, idx) => {
                        const result = msg.toolResults?.[idx];
                        return (
                          <ToolExecutionCard
                            key={tc.id || idx}
                            toolCall={tc}
                            toolResult={result}
                          />
                        );
                      })}
                    </div>
                  )}

                  {/* Message Markdown Content */}
                  <div className="whitespace-pre-wrap font-sans text-slate-200">
                    {msg.content}
                  </div>

                  {/* Inline Citations & Grounding Score Footer */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex flex-wrap items-center gap-2 text-[11px]">
                      <div className="flex items-center gap-1 font-semibold text-slate-400">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Verified Citations:</span>
                      </div>
                      {msg.citations.map((c) => (
                        <CitationBadge key={c.citation_id} citation={c} />
                      ))}
                      {msg.groundingScore !== undefined && (
                        <span className="ml-auto font-mono text-[10px] text-emerald-400 font-bold bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded-full">
                          Grounding: {(msg.groundingScore * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 shadow-sm">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))
          )}

          {loading && (
            <div className="flex gap-3.5 justify-start">
              <div className="w-8 h-8 rounded-xl bg-indigo-950 border border-indigo-700/60 flex items-center justify-center text-indigo-400 shrink-0 shadow-sm">
                <Bot className="w-4 h-4 animate-spin" />
              </div>
              <div className="bg-slate-900/90 border border-slate-800 rounded-2xl rounded-bl-none p-4 text-xs text-slate-400 flex items-center gap-2 shadow-lg">
                <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
                <span>Invoking platform tools and verifying evidence grounding...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/80">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage(inputQuery);
            }}
            className="flex items-center gap-2.5"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask a question (e.g. 'What caused the failure in exec_4a9b?')..."
              disabled={loading}
              className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition shadow-inner"
            />
            <button
              type="submit"
              disabled={!inputQuery.trim() || loading}
              className="px-5 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-semibold rounded-xl transition flex items-center gap-2 shadow-lg cursor-pointer"
            >
              <span>Send</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
