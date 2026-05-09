'use client'

import { useRef, useState, useEffect, useCallback } from 'react'
import { Bot, User, AlertCircle, X, History, Plus, Upload, FileSpreadsheet, CheckCircle, XCircle, FileUp, HelpCircle, Database, FileText, Calendar, Shield, DollarSign, Leaf, ChevronRight, X as XIcon } from 'lucide-react'
import { dispatchSseEvent, type SseEventType } from './sseUtils'
import ChatHistoryPanel, {
  type ChatSession,
  type StoredMessage,
  saveSession,
} from './ChatHistoryPanel'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  ragChunksUsed?: number
  isStreaming?: boolean
  error?: boolean
  attachment?: FileAttachment
}

interface FileAttachment {
  filename: string
  entityType?: string
  importResult?: ImportResult
}

interface ImportResult {
  import_id: string
  entity_type: string
  status: string
  total_rows: number
  successful_rows: number
  failed_rows: number
  created_count: number
  errors: { row_number: number; error_message: string; field_errors: Record<string, string> }[]
  warnings: string[]
  summary: string
  processing_time_seconds: number
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function getToken(): string {
  if (typeof window === 'undefined') return ''
  return (
    sessionStorage.getItem('access_token') ??
    localStorage.getItem('access_token') ??
    ''
  )
}

function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

type HealthStatus = 'checking' | 'online' | 'offline'

const healthConfig = {
  checking: { dot: 'bg-gray-400 animate-pulse', label: 'Checking…' },
  online:   { dot: 'bg-green-400', label: 'Ollama online' },
  offline:  { dot: 'bg-red-400', label: 'Ollama offline' },
}

const INITIAL_MESSAGE: ChatMessage = {
  role: 'assistant',
  content:
    "Hello! I'm HiTech AI, your intelligent assistant for waste management operations. I can help with compliance queries, ESG reporting, fleet management, client intelligence, and more. What would you like to know?",
}

const INITIAL_MESSAGE_DB: ChatMessage = {
  role: 'assistant',
  content:
    "Hi! I'm HiTech AI Database Assistant. I can help you create clients, jobs, vehicles, and manage data directly in the database. Try: 'Create a new client' or 'Show me all jobs for client X'.\n\n📎 **Bulk Import**: Drag & drop a CSV/Excel file or click the upload button to import multiple records at once!\n\n💡 **Tip**: Click the Help button (?) in the top right to see all available AI features!",
}

export default function AIAssistantChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [useRag, setUseRag] = useState(true)
  const [useDatabaseAgent, setUseDatabaseAgent] = useState(false)
  const [dbSessionId, setDbSessionId] = useState<string>('')
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('checking')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [helpTab, setHelpTab] = useState<'overview' | 'database' | 'scheduling' | 'compliance' | 'invoice' | 'esg'>('overview')
  const [sessionId, setSessionId] = useState<string>('')
  const [sessionStarted, setSessionStarted] = useState(false)
  
  // File upload state
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [filePreview, setFilePreview] = useState<{ columns: string[]; rowCount: number } | null>(null)
  
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/ai/rag-status`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (res.ok) {
        const data = await res.json()
        setHealthStatus(data.ollama?.connected ? 'online' : 'offline')
      } else {
        setHealthStatus('offline')
      }
    } catch {
      setHealthStatus('offline')
    }
  }, [])

  useEffect(() => {
    checkHealth()
    const id = setInterval(checkHealth, 60_000)
    return () => clearInterval(id)
  }, [checkHealth])

  // Save session to localStorage whenever messages change
  useEffect(() => {
    if (!sessionStarted || messages.length <= 1) return
    const userMessages = messages.filter((m) => m.role === 'user')
    if (userMessages.length === 0) return

    const storedMessages: StoredMessage[] = messages
      .filter((m) => !m.isStreaming)
      .map((m) => ({
        role: m.role,
        content: m.content,
        ragChunksUsed: m.ragChunksUsed,
        error: m.error,
      }))

    const session: ChatSession = {
      id: sessionId,
      title: userMessages[0].content.slice(0, 60) + (userMessages[0].content.length > 60 ? '…' : ''),
      createdAt: new Date(parseInt(sessionId.split('_')[1])).toISOString(),
      messageCount: storedMessages.length,
      messages: storedMessages,
    }
    saveSession(session)
  }, [messages, sessionId, sessionStarted])

  function startNewChat() {
    setMessages([useDatabaseAgent ? INITIAL_MESSAGE_DB : INITIAL_MESSAGE])
    setInput('')
    setSessionId(generateSessionId())
    setSessionStarted(false)
    setDbSessionId('')
    setSelectedFile(null)
    setFilePreview(null)
  }

  function toggleDatabaseAgent() {
    const newMode = !useDatabaseAgent
    setUseDatabaseAgent(newMode)
    setMessages([newMode ? INITIAL_MESSAGE_DB : INITIAL_MESSAGE])
    setDbSessionId('')
    setSessionId(generateSessionId())
    setSessionStarted(false)
  }

  function loadSession(session: ChatSession) {
    const restored: ChatMessage[] = session.messages.map((m) => ({
      role: m.role,
      content: m.content,
      ragChunksUsed: m.ragChunksUsed,
      error: m.error,
    }))
    setMessages(restored)
    setSessionId(session.id)
    setSessionStarted(true)
  }

  const sendMessage = useCallback(async () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return

    if (!sessionStarted) {
      const newId = generateSessionId()
      setSessionId(newId)
      setSessionStarted(true)
    }

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    const history = messages
      .filter((m) => !m.error && !m.isStreaming)
      .map((m) => ({ role: m.role, content: m.content }))

    setMessages((prev) => [
      ...prev,
      userMsg,
      { role: 'assistant', content: '', isStreaming: true },
    ])
    setInput('')
    setIsStreaming(true)

    abortRef.current = new AbortController()

    try {
      const endpoint = useDatabaseAgent ? `${API_BASE}/api/v1/ai/chat-db` : `${API_BASE}/api/v1/ai/chat`
      const body = useDatabaseAgent
        ? JSON.stringify({
            message: trimmed,
            conversation_history: history,
            session_id: dbSessionId || undefined,
            temperature: 0.7,
          })
        : JSON.stringify({
            message: trimmed,
            conversation_history: history,
            use_rag: useRag,
            max_context_chunks: 5,
            temperature: 0.7,
          })

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: body,
        signal: abortRef.current.signal,
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''
      let ragChunks = 0
      let currentEventType: SseEventType = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        if (useDatabaseAgent) {
          const data = await response.json()
          setDbSessionId(data.session_id || '')
          const operationsText = data.operations_performed?.length
            ? `\n\n📊 Database Operations: ${data.operations_performed.map((op: {action: string, entity_type: string, success: boolean}) => `${op.action} ${op.entity_type} ${op.success ? '✓' : '✗'}`).join(', ')}` 
            : ''
          const pendingText = data.pending_operation
            ? `\n\n⏳ Need more info: ${data.pending_operation.missing_fields?.join(', ')}` 
            : ''
          fullContent = data.response + operationsText + pendingText
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.isStreaming) updated[updated.length - 1] = {
              ...last, content: fullContent, isStreaming: false,
            }
            return updated
          })
          break
        }

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEventType = line.slice(6).trim() as SseEventType
            continue
          }
          if (line === '') { currentEventType = null; continue }
          if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim()
            if (!dataStr) continue
            try {
              const data = JSON.parse(dataStr) as Record<string, unknown>
              const result = dispatchSseEvent(currentEventType, data)
              currentEventType = null
              if (result.ragChunks !== undefined) ragChunks = result.ragChunks
              if (result.tokenDelta !== undefined && result.tokenDelta !== '') {
                fullContent += result.tokenDelta
                setMessages((prev) => {
                  const updated = [...prev]
                  const last = updated[updated.length - 1]
                  if (last?.isStreaming) updated[updated.length - 1] = { ...last, content: fullContent }
                  return updated
                })
              }
              if (result.isDone) {
                setMessages((prev) => {
                  const updated = [...prev]
                  const last = updated[updated.length - 1]
                  if (last?.isStreaming) updated[updated.length - 1] = {
                    ...last, content: fullContent, isStreaming: false, ragChunksUsed: ragChunks,
                  }
                  return updated
                })
              }
              if (result.errorText) {
                setMessages((prev) => {
                  const updated = [...prev]
                  updated[updated.length - 1] = {
                    role: 'assistant', content: result.errorText!, error: true, isStreaming: false,
                  }
                  return updated
                })
              }
            } catch { /* skip malformed */ }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      const errorContent = err instanceof Error && err.message.startsWith('HTTP')
        ? `The AI service returned an error (${err.message}). Please try again.`
        : 'Failed to connect to the AI service. Please ensure Ollama is running and try again.'
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant', content: errorContent, error: true, isStreaming: false,
        }
        return updated
      })
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [input, isStreaming, messages, useRag, sessionStarted])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  // File upload handlers
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      await processFile(file)
    }
  }, [useDatabaseAgent])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      await processFile(file)
    }
  }, [useDatabaseAgent])

  const detectEntityType = (filename: string): string => {
    const lower = filename.toLowerCase()
    if (lower.includes('client') || lower.includes('customer')) return 'client'
    if (lower.includes('job') || lower.includes('service')) return 'job'
    if (lower.includes('vehicle') || lower.includes('truck') || lower.includes('lorry')) return 'vehicle'
    if (lower.includes('user') || lower.includes('staff') || lower.includes('employee')) return 'user'
    if (lower.includes('container') || lower.includes('skip')) return 'container'
    if (lower.includes('waste') || lower.includes('batch')) return 'scheduled_waste_batch'
    return 'client' // Default
  }

  const processFile = async (file: File) => {
    if (!file.name.endsWith('.csv') && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '❌ Only CSV and Excel files (.csv, .xlsx, .xls) are supported for bulk import.',
        error: true
      }])
      return
    }

    setSelectedFile(file)
    
    // Detect entity type from filename
    const detectedEntity = detectEntityType(file.name)
    
    // Show file info in chat
    const fileMsg: ChatMessage = {
      role: 'user',
      content: `📎 Uploading: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`,
      attachment: { filename: file.name, entityType: detectedEntity }
    }
    setMessages((prev) => [...prev, fileMsg, { role: 'assistant', content: '', isStreaming: true }])
    setUploading(true)
    setSessionStarted(true)

    try {
      // Convert file to base64
      const base64Content = await fileToBase64(file)
      
      // First, get preview
      const previewRes = await fetch(`${API_BASE}/api/v1/ai/bulk-import-preview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          entity_type: detectedEntity,
          filename: file.name,
          file_content_base64: base64Content,
        }),
      })

      if (!previewRes.ok) {
        throw new Error(`Preview failed: ${previewRes.status}`)
      }

      const preview = await previewRes.json()
      setFilePreview({ columns: preview.detected_columns, rowCount: preview.total_rows })

      // Check if we can import
      if (!preview.can_import) {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: `⚠️ **Import Preview: ${file.name}**\n\nDetected ${preview.total_rows} rows\n\n❌ **Missing required columns:** ${preview.missing_required_fields.join(', ')}\n\nPlease add these columns to your file and try again.\n\n**Suggested column mappings:**\n${Object.entries(preview.suggested_mappings).map(([col, mapped]) => `- ${col} → ${mapped}`).join('\n')}`,
            isStreaming: false
          }
          return updated
        })
        setUploading(false)
        return
      }

      // Execute import with dry_run first
      const dryRunRes = await fetch(`${API_BASE}/api/v1/ai/bulk-import`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          entity_type: detectedEntity,
          filename: file.name,
          file_content_base64: base64Content,
          dry_run: true,
          skip_errors: true,
        }),
      })

      if (!dryRunRes.ok) {
        throw new Error(`Validation failed: ${dryRunRes.status}`)
      }

      const dryRunResult: ImportResult = await dryRunRes.json()

      if (dryRunResult.failed_rows > 0) {
        // Show validation errors
        const errorDetails = dryRunResult.errors.slice(0, 5).map(e => 
          `Row ${e.row_number}: ${e.error_message}`
        ).join('\n')
        
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: `⚠️ **Validation Results for ${file.name}**\n\n📊 **${preview.total_rows} rows detected**\n✅ ${dryRunResult.successful_rows} valid\n❌ ${dryRunResult.failed_rows} have errors\n\n**First few errors:**\n${errorDetails}\n\n${dryRunResult.failed_rows > 5 ? `... and ${dryRunResult.failed_rows - 5} more errors` : ''}\n\nFix these issues and try again, or say "import anyway" to skip invalid rows.`,
            isStreaming: false,
            attachment: { filename: file.name, entityType: detectedEntity, importResult: dryRunResult }
          }
          return updated
        })
      } else {
        // All valid, proceed with actual import
        await executeImport(file, base64Content, detectedEntity, preview.total_rows)
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `❌ Import failed: ${errorMsg}`,
          error: true,
          isStreaming: false
        }
        return updated
      })
    } finally {
      setUploading(false)
    }
  }

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.readAsDataURL(file)
      reader.onload = () => {
        const base64 = reader.result?.toString().split(',')[1]
        if (base64) resolve(base64)
        else reject(new Error('Failed to convert file'))
      }
      reader.onerror = reject
    })
  }

  const executeImport = async (file: File, base64Content: string, entityType: string, totalRows: number) => {
    setMessages((prev) => {
      const updated = [...prev]
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        content: `⏳ Importing ${totalRows} ${entityType} records from ${file.name}...`,
        isStreaming: true
      }
      return updated
    })

    const importRes = await fetch(`${API_BASE}/api/v1/ai/bulk-import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({
        entity_type: entityType,
        filename: file.name,
        file_content_base64: base64Content,
        dry_run: false,
        skip_errors: true,
      }),
    })

    if (!importRes.ok) {
      throw new Error(`Import failed: ${importRes.status}`)
    }

    const result: ImportResult = await importRes.json()

    // Build result message
    const statusIcon = result.status === 'completed' ? '✅' : result.status === 'partial' ? '⚠️' : '❌'
    const errorSection = result.errors.length > 0 
      ? `\n\n**Errors (${result.errors.length} shown):**\n${result.errors.map(e => `- Row ${e.row_number}: ${e.error_message}`).join('\n')}`
      : ''

    setMessages((prev) => {
      const updated = [...prev]
      updated[updated.length - 1] = {
        role: 'assistant',
        content: `${statusIcon} **Import Complete: ${file.name}**\n\n📊 **Summary:**\n- Total rows: ${result.total_rows}\n- ✅ Created: ${result.successful_rows}\n- ❌ Failed: ${result.failed_rows}\n- ⏱️ Time: ${result.processing_time_seconds.toFixed(2)}s\n\n${result.summary}${errorSection}`,
        isStreaming: false,
        attachment: { filename: file.name, entityType, importResult: result }
      }
      return updated
    })

    setSelectedFile(null)
    setFilePreview(null)
  }

  const stopStreaming = () => {
    abortRef.current?.abort()
    setIsStreaming(false)
    setMessages((prev) => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last?.isStreaming) updated[updated.length - 1] = { ...last, isStreaming: false }
      return updated
    })
  }

  return (
    <>
      <ChatHistoryPanel
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onLoadSession={loadSession}
        currentSessionId={sessionId}
      />

      <div className="flex flex-col h-full bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setHistoryOpen(true)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-200 transition-colors"
              title="Chat history"
            >
              <History className="w-4 h-4" />
            </button>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
              <Bot className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">HiTech AI</p>
              <p className="text-xs text-gray-500">Powered by Ollama</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setHelpOpen(true)}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-brand-600 hover:text-brand-700 hover:bg-brand-50 rounded-lg transition-colors"
              title="AI Features Help"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              Help
            </button>
            <button
              onClick={startNewChat}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-gray-500 hover:text-gray-900 hover:bg-gray-200 rounded-lg transition-colors"
              title="New chat"
            >
              <Plus className="w-3.5 h-3.5" />
              New
            </button>
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${healthConfig[healthStatus].dot}`} />
              <span className="text-xs text-gray-500 hidden sm:inline">{healthConfig[healthStatus].label}</span>
            </div>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <span className="text-xs text-gray-500">RAG</span>
              <div
                onClick={() => setUseRag((v) => !v)}
                className={`relative w-9 h-5 rounded-full transition-colors ${useRag ? 'bg-emerald-500' : 'bg-gray-300'}`}
              >
                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${useRag ? 'translate-x-4' : 'translate-x-0.5'}`} />
              </div>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer" title="Enable database read/write capabilities">
              <span className="text-xs text-gray-500">DB Agent</span>
              <div
                onClick={toggleDatabaseAgent}
                className={`relative w-9 h-5 rounded-full transition-colors ${useDatabaseAgent ? 'bg-brand-500' : 'bg-gray-300'}`}
              >
                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${useDatabaseAgent ? 'translate-x-4' : 'translate-x-0.5'}`} />
              </div>
            </label>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                msg.role === 'user'
                  ? 'bg-brand-500/20 border border-brand-500/30'
                  : 'bg-emerald-500/20 border border-emerald-500/30'
              }`}>
                {msg.role === 'user'
                  ? <User className="w-3.5 h-3.5 text-brand-400" />
                  : <Bot className="w-3.5 h-3.5 text-emerald-400" />
                }
              </div>
              <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-brand-50 border border-brand-200 text-gray-900'
                  : msg.error
                  ? 'bg-red-50 border border-red-200 text-red-600'
                  : 'bg-gray-50 border border-gray-200 text-gray-800'
              }`}>
                {msg.error && <AlertCircle className="w-3.5 h-3.5 inline mr-1.5 text-red-400" />}
                {msg.content || (msg.isStreaming ? '' : '…')}
                {msg.isStreaming && (
                  <span className="inline-block w-1.5 h-4 ml-0.5 bg-emerald-400 animate-pulse rounded-sm" />
                )}
                {msg.ragChunksUsed !== undefined && msg.ragChunksUsed > 0 && (
                  <p className="mt-1.5 text-xs text-gray-400">
                    {msg.ragChunksUsed} document chunk{msg.ragChunksUsed !== 1 ? 's' : ''} referenced
                  </p>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 py-3 border-t border-gray-200 bg-gray-50">
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about compliance, ESG, fleet, clients…"
              rows={1}
              disabled={isStreaming}
              className="flex-1 resize-none bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-brand-500/50 disabled:opacity-50 max-h-32 overflow-y-auto"
              style={{ minHeight: '38px' }}
            />
            {isStreaming ? (
              <button
                onClick={stopStreaming}
                className="flex-shrink-0 w-9 h-9 rounded-lg bg-red-50 border border-red-200 flex items-center justify-center hover:bg-red-100 transition-colors"
              >
                <X className="w-4 h-4 text-red-400" />
              </button>
            ) : (
              <button
                onClick={sendMessage}
                disabled={!input.trim()}
                className="flex-shrink-0 w-9 h-9 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center hover:bg-brand-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            )}
          </div>
          <p className="mt-1.5 text-xs text-gray-400">
            Enter to send · Shift+Enter for new line · RAG {useRag ? 'on' : 'off'} · DB Agent {useDatabaseAgent ? 'on' : 'off'}
            {useDatabaseAgent && ' · 📎 Drag & drop CSV/Excel files to import'}
          </p>
          
          {/* File Upload Zone - Only show when DB Agent is on */}
          {useDatabaseAgent && (
            <div 
              className={`mt-2 p-2 border-2 border-dashed rounded-lg transition-colors ${
                dragActive 
                  ? 'border-brand-500 bg-brand-50' 
                  : uploading 
                    ? 'border-gray-300 bg-gray-100' 
                    : 'border-gray-300 hover:border-gray-400'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={handleFileSelect}
                className="hidden"
                disabled={uploading}
              />
              <div className="flex items-center justify-center gap-2">
                {uploading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                    <span className="text-xs text-gray-600">Processing file...</span>
                  </>
                ) : selectedFile ? (
                  <>
                    <FileSpreadsheet className="w-4 h-4 text-green-500" />
                    <span className="text-xs text-gray-700">{selectedFile.name}</span>
                    <button 
                      onClick={() => { setSelectedFile(null); setFilePreview(null) }}
                      className="p-0.5 hover:bg-gray-200 rounded"
                    >
                      <XCircle className="w-3 h-3 text-gray-500" />
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-brand-600 hover:bg-brand-50 rounded-lg transition-colors"
                    disabled={uploading}
                  >
                    <FileUp className="w-4 h-4" />
                    <span>Upload CSV/Excel</span>
                  </button>
                )}
                <span className="text-xs text-gray-400">or drag & drop</span>
              </div>
              
              {filePreview && (
                <div className="mt-2 px-2 py-1 bg-white rounded border text-xs text-gray-600">
                  <span className="font-medium">{filePreview.rowCount} rows</span>
                  <span className="mx-1">·</span>
                  <span className="truncate">{filePreview.columns.slice(0, 4).join(', ')}{filePreview.columns.length > 4 ? '...' : ''}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Help Modal */}
      {helpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-4xl max-h-[90vh] bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col">
            {/* Help Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-brand-50 to-emerald-50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-emerald-500 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-900">AI Assistant Features</h2>
                  <p className="text-sm text-gray-500">6 AI Features • 30+ Functions • Natural Language Interface</p>
                </div>
              </div>
              <button
                onClick={() => setHelpOpen(false)}
                className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              >
                <XIcon className="w-5 h-5" />
              </button>
            </div>

            {/* Help Content */}
            <div className="flex flex-1 overflow-hidden">
              {/* Sidebar */}
              <div className="w-64 border-r border-gray-200 bg-gray-50 p-4 overflow-y-auto">
                <nav className="space-y-1">
                  <button
                    onClick={() => setHelpTab('overview')}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      helpTab === 'overview' ? 'bg-brand-100 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Bot className="w-4 h-4" />
                    Overview
                  </button>
                  <button
                    onClick={() => setHelpTab('database')}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      helpTab === 'database' ? 'bg-brand-100 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Database className="w-4 h-4" />
                    Database Agent
                  </button>
                  <button
                    onClick={() => setHelpTab('scheduling')}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      helpTab === 'scheduling' ? 'bg-brand-100 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Calendar className="w-4 h-4" />
                    Smart Scheduling
                  </button>
                  <button
                    onClick={() => setHelpTab('compliance')}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      helpTab === 'compliance' ? 'bg-brand-100 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Shield className="w-4 h-4" />
                    Compliance
                  </button>
                  <button
                    onClick={() => setHelpTab('invoice')}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      helpTab === 'invoice' ? 'bg-brand-100 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <DollarSign className="w-4 h-4" />
                    Invoice Intelligence
                  </button>
                  <button
                    onClick={() => setHelpTab('esg')}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      helpTab === 'esg' ? 'bg-brand-100 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <Leaf className="w-4 h-4" />
                    ESG Reporting
                  </button>
                </nav>

                <div className="mt-6 p-3 bg-brand-50 rounded-lg border border-brand-100">
                  <p className="text-xs text-brand-700 font-medium mb-1">💡 Quick Tip</p>
                  <p className="text-xs text-brand-600">
                    Toggle &quot;DB Agent&quot; in the chat header to enable database operations and bulk import features.
                  </p>
                </div>
              </div>

              {/* Content Area */}
              <div className="flex-1 overflow-y-auto p-6">
                {helpTab === 'overview' && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 mb-3">Welcome to HiTech AI</h3>
                      <p className="text-gray-600 leading-relaxed">
                        Your intelligent assistant for waste management operations. Use natural language to query data, 
                        schedule jobs, track compliance, manage invoices, and generate sustainability reports.
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { icon: Database, title: 'Database Agent', desc: 'Query & modify data with natural language', color: 'blue' },
                        { icon: FileText, title: 'Bulk Import', desc: 'CSV/Excel import with AI validation', color: 'purple' },
                        { icon: Calendar, title: 'Smart Scheduling', desc: 'Auto-assign jobs & optimize routes', color: 'green' },
                        { icon: Shield, title: 'Compliance', desc: 'Track permits & regulatory deadlines', color: 'orange' },
                        { icon: DollarSign, title: 'Invoice Intelligence', desc: 'AR aging & collection strategies', color: 'pink' },
                        { icon: Leaf, title: 'ESG Reporting', desc: 'Sustainability & carbon tracking', color: 'emerald' },
                      ].map((feature) => (
                        <button
                          key={feature.title}
                          onClick={() => setHelpTab(feature.title.toLowerCase().replace(' ', '') as typeof helpTab)}
                          className="flex items-start gap-3 p-4 rounded-xl border border-gray-200 hover:border-brand-300 hover:bg-brand-50 transition-all text-left group"
                        >
                          <div className={`w-10 h-10 rounded-lg bg-${feature.color}-100 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform`}>
                            <feature.icon className={`w-5 h-5 text-${feature.color}-600`} />
                          </div>
                          <div>
                            <h4 className="font-semibold text-gray-900">{feature.title}</h4>
                            <p className="text-sm text-gray-500 mt-1">{feature.desc}</p>
                          </div>
                          <ChevronRight className="w-4 h-4 text-gray-300 ml-auto flex-shrink-0 group-hover:text-brand-400" />
                        </button>
                      ))}
                    </div>

                    <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                      <h4 className="font-semibold text-gray-900 mb-2">🚀 Getting Started</h4>
                      <ol className="space-y-2 text-sm text-gray-600">
                        <li>1. <strong>General Chat:</strong> Ask about compliance, ESG, operations (RAG mode)</li>
                        <li>2. <strong>Database Mode:</strong> Toggle &quot;DB Agent&quot; to enable database read/write</li>
                        <li>3. <strong>Bulk Import:</strong> In DB mode, drag & drop CSV/Excel files</li>
                        <li>4. <strong>Other Features:</strong> Use the AI API endpoints directly for advanced features</li>
                      </ol>
                    </div>
                  </div>
                )}

                {helpTab === 'database' && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 mb-2 flex items-center gap-2">
                        <Database className="w-6 h-6 text-brand-600" />
                        Database Agent
                      </h3>
                      <p className="text-gray-600">Query and modify the database using natural language. No SQL required!</p>
                    </div>

                    <div className="space-y-4">
                      <div className="bg-brand-50 rounded-lg p-4 border border-brand-100">
                        <h4 className="font-semibold text-brand-900 mb-2">✨ What You Can Do</h4>
                        <ul className="space-y-1 text-sm text-brand-800">
                          <li>• Query any table with natural language</li>
                          <li>• Create new records (clients, jobs, vehicles)</li>
                          <li>• Update existing data</li>
                          <li>• Delete records safely</li>
                          <li>• Search with filters</li>
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">💬 Example Queries</h4>
                        <div className="space-y-2">
                          {[
                            'Show all clients in Kuala Lumpur',
                            'Create a new client ABC Manufacturing Sdn Bhd',
                            'Update client status to active for client XYZ',
                            'Delete the test job SW-2026-001',
                            'Find all jobs scheduled for tomorrow',
                            'What is the total outstanding for client ABC?',
                          ].map((q) => (
                            <div key={q} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-sm text-gray-700">
                              <span className="text-brand-500">→</span>
                              {q}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">📁 Supported Entities</h4>
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          {['Clients', 'Jobs', 'Vehicles', 'Invoices', 'Employees', 'BSF Batches', 'Destruction', 'Scheduled Waste', 'Recyclables'].map((e) => (
                            <div key={e} className="px-3 py-1.5 bg-gray-100 rounded-lg text-gray-700 text-center">{e}</div>
                          ))}
                        </div>
                      </div>

                      <div className="bg-purple-50 rounded-lg p-4 border border-purple-100">
                        <h4 className="font-semibold text-purple-900 mb-2 flex items-center gap-2">
                          <FileText className="w-4 h-4" />
                          Bulk Import (CSV/Excel)
                        </h4>
                        <p className="text-sm text-purple-800 mb-2">
                          When DB Agent is enabled, drag & drop CSV/Excel files to import multiple records:
                        </p>
                        <ul className="text-sm text-purple-700 space-y-1">
                          <li>• Auto-detects entity type from filename</li>
                          <li>• AI maps CSV columns to database fields</li>
                          <li>• Validates data before import</li>
                          <li>• Preview and error reporting</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {helpTab === 'scheduling' && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 mb-2 flex items-center gap-2">
                        <Calendar className="w-6 h-6 text-green-600" />
                        Smart Scheduling Agent
                      </h3>
                      <p className="text-gray-600">AI-powered job assignment, route optimization, and conflict detection.</p>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        {[
                          { title: 'Auto-Assignment', desc: 'Suggests best vehicle/driver for jobs' },
                          { title: 'Route Optimization', desc: 'Minimizes travel time and fuel costs' },
                          { title: 'Conflict Detection', desc: 'Identifies scheduling overlaps' },
                          { title: 'Priority Scoring', desc: 'Ranks jobs by urgency & capacity' },
                        ].map((f) => (
                          <div key={f.title} className="p-3 bg-green-50 rounded-lg border border-green-100">
                            <h4 className="font-semibold text-green-900">{f.title}</h4>
                            <p className="text-sm text-green-700">{f.desc}</p>
                          </div>
                        ))}
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">💬 Example Queries</h4>
                        <div className="space-y-2">
                          {[
                            'Suggest assignments for today\'s unassigned jobs',
                            'Optimize route for Vehicle PJ1234',
                            'Check for scheduling conflicts this week',
                            'What\'s the best driver for the KLCC job?',
                            'Batch schedule all pending recycling jobs',
                          ].map((q) => (
                            <div key={q} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-sm text-gray-700">
                              <span className="text-green-500">→</span>
                              {q}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                        <h4 className="font-semibold text-gray-900 mb-2">📊 Assignment Scoring Factors</h4>
                        <ul className="text-sm text-gray-600 space-y-1">
                          <li>• Vehicle proximity to job location</li>
                          <li>• Driver qualifications/certifications</li>
                          <li>• Vehicle capacity vs. waste volume</li>
                          <li>• Driver shift availability</li>
                          <li>• Historical performance</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {helpTab === 'compliance' && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 mb-2 flex items-center gap-2">
                        <Shield className="w-6 h-6 text-orange-600" />
                        Compliance Monitoring Agent
                      </h3>
                      <p className="text-gray-600">Track permits, licenses, regulatory deadlines, and generate alerts.</p>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">📋 Monitored Compliance Areas</h4>
                        <div className="space-y-2">
                          {[
                            { item: 'Scheduled Waste', rule: 'DOE 90/180 day storage rule' },
                            { item: 'Vehicle Road Tax', rule: 'JPJ Road Transport Act 1987' },
                            { item: 'Vehicle Insurance', rule: 'Motor Vehicles Act 1963' },
                            { item: 'PUSPAKOM Inspection', rule: 'CVLB Regulations' },
                            { item: 'Downstream Licenses', rule: 'DOE EQ Act 1974' },
                            { item: 'Destruction Certificates', rule: 'Contractual tracking' },
                            { item: 'Consignment Notes', rule: 'DOE waste tracking' },
                          ].map((c) => (
                            <div key={c.item} className="flex justify-between items-center p-2 bg-orange-50 rounded-lg text-sm">
                              <span className="font-medium text-orange-900">{c.item}</span>
                              <span className="text-orange-600">{c.rule}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-4 gap-3">
                        {[
                          { color: 'green', label: 'Compliant', desc: 'All good' },
                          { color: 'yellow', label: 'Warning', desc: 'Due within 30 days' },
                          { color: 'orange', label: 'Critical', desc: 'Due within 7 days' },
                          { color: 'red', label: 'Expired', desc: 'Past deadline' },
                        ].map((a) => (
                          <div key={a.label} className={`p-3 bg-${a.color}-50 rounded-lg border border-${a.color}-100 text-center`}>
                            <div className={`w-3 h-3 rounded-full bg-${a.color}-500 mx-auto mb-1`} />
                            <div className={`font-semibold text-${a.color}-900 text-sm`}>{a.label}</div>
                            <div className={`text-xs text-${a.color}-600`}>{a.desc}</div>
                          </div>
                        ))}
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">💬 Example Queries</h4>
                        <div className="space-y-2">
                          {[
                            'Show compliance dashboard',
                            'Check DOE compliance for client ABC Corp',
                            'Which vehicles have expired road tax?',
                            'Generate Q1 2026 compliance report',
                            'What are the critical alerts this week?',
                          ].map((q) => (
                            <div key={q} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-sm text-gray-700">
                              <span className="text-orange-500">→</span>
                              {q}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {helpTab === 'invoice' && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 mb-2 flex items-center gap-2">
                        <DollarSign className="w-6 h-6 text-pink-600" />
                        Invoice Intelligence Agent
                      </h3>
                      <p className="text-gray-600">AR aging reports, collection strategies, payment predictions, and risk scoring.</p>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        {[
                          { title: 'Aging Reports', desc: 'AR by buckets (current, 30, 60, 90, 120+)' },
                          { title: 'Risk Scoring', desc: 'AI-powered invoice risk assessment' },
                          { title: 'Collection Strategy', desc: 'Tailored action plans per client' },
                          { title: 'Payment Prediction', desc: 'ML-based payment probability' },
                        ].map((f) => (
                          <div key={f.title} className="p-3 bg-pink-50 rounded-lg border border-pink-100">
                            <h4 className="font-semibold text-pink-900">{f.title}</h4>
                            <p className="text-sm text-pink-700">{f.desc}</p>
                          </div>
                        ))}
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">📊 Aging Buckets</h4>
                        <div className="grid grid-cols-5 gap-2 text-center text-sm">
                          {[
                            { bucket: 'Current', days: '0-30', color: 'green' },
                            { bucket: '31-60', days: 'Early', color: 'yellow' },
                            { bucket: '61-90', days: 'Moderate', color: 'orange' },
                            { bucket: '91-120', days: 'High Risk', color: 'red' },
                            { bucket: '120+', days: 'Critical', color: 'red' },
                          ].map((b) => (
                            <div key={b.bucket} className={`p-2 bg-${b.color}-50 rounded-lg border border-${b.color}-100`}>
                              <div className={`font-semibold text-${b.color}-900`}>{b.bucket}</div>
                              <div className={`text-xs text-${b.color}-600`}>{b.days}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">💬 Example Queries</h4>
                        <div className="space-y-2">
                          {[
                            'Show aging report',
                            'Get collection strategy for client XYZ',
                            'Generate urgent collection message for ABC Corp',
                            'Will invoice INV-2026-015 be paid on time?',
                            'What\'s our DSO this month?',
                          ].map((q) => (
                            <div key={q} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-sm text-gray-700">
                              <span className="text-pink-500">→</span>
                              {q}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                        <h4 className="font-semibold text-gray-900 mb-2">🎭 Collection Tones</h4>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div className="p-2 bg-white rounded border">Professional - Standard business</div>
                          <div className="p-2 bg-white rounded border">Friendly - Warm but firm</div>
                          <div className="p-2 bg-white rounded border">Firm - Assertive, deadline-focused</div>
                          <div className="p-2 bg-white rounded border">Urgent - Immediate action</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {helpTab === 'esg' && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 mb-2 flex items-center gap-2">
                        <Leaf className="w-6 h-6 text-emerald-600" />
                        ESG Report Generation Agent
                      </h3>
                      <p className="text-gray-600">Automated Environmental, Social, and Governance (ESG) sustainability reporting.</p>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-3 gap-4">
                        {[
                          { title: 'Environmental', metrics: 'Carbon, waste diversion, recycling', color: 'emerald' },
                          { title: 'Social', metrics: 'Clients served, jobs completed', color: 'blue' },
                          { title: 'Governance', metrics: 'Compliance, audit findings', color: 'purple' },
                        ].map((c) => (
                          <div key={c.title} className={`p-3 bg-${c.color}-50 rounded-lg border border-${c.color}-100`}>
                            <h4 className={`font-semibold text-${c.color}-900`}>{c.title}</h4>
                            <p className={`text-sm text-${c.color}-700`}>{c.metrics}</p>
                          </div>
                        ))}
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">🌍 UN SDG Contributions</h4>
                        <div className="space-y-2">
                          {[
                            { sdg: '12', name: 'Responsible Consumption', contrib: 'Waste diversion from landfill' },
                            { sdg: '13', name: 'Climate Action', contrib: 'Carbon avoidance' },
                            { sdg: '11', name: 'Sustainable Cities', contrib: 'Urban waste management' },
                            { sdg: '8', name: 'Decent Work', contrib: 'Job creation' },
                          ].map((s) => (
                            <div key={s.sdg} className="flex items-center gap-3 p-2 bg-emerald-50 rounded-lg text-sm">
                              <div className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center font-bold text-xs">
                                {s.sdg}
                              </div>
                              <div>
                                <div className="font-semibold text-emerald-900">{s.name}</div>
                                <div className="text-emerald-600">{s.contrib}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3">💬 Example Queries</h4>
                        <div className="space-y-2">
                          {[
                            'Generate ESG report for April 2026',
                            'Show ESG dashboard',
                            'Generate sustainability report for client ABC',
                            'What\'s our carbon footprint this month?',
                            'Which SDGs are we contributing to?',
                            'How many trees equivalent have we saved?',
                          ].map((q) => (
                            <div key={q} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-sm text-gray-700">
                              <span className="text-emerald-500">→</span>
                              {q}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-100">
                        <h4 className="font-semibold text-emerald-900 mb-2">🌱 Carbon Tracking</h4>
                        <div className="grid grid-cols-2 gap-2 text-sm text-emerald-800">
                          <div>• Transport emissions</div>
                          <div>• Landfill avoidance credits</div>
                          <div>• Recycling credits</div>
                          <div>• WTE credits</div>
                          <div>• Net impact calculation</div>
                          <div>• Trees equivalent</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Help Footer */}
            <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
              <p className="text-xs text-gray-500">
                📚 Full documentation: <code className="bg-gray-200 px-1 rounded">AI_FEATURES_GUIDE.md</code>
              </p>
              <button
                onClick={() => setHelpOpen(false)}
                className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition-colors"
              >
                Got it!
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
