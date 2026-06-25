import React, { useState, useEffect } from 'react'
import {
  Play, Activity, Cpu, BookOpen,
  Terminal, RefreshCw,
  Layout, Layers, BarChart2
} from 'lucide-react'

// Backend Host Configuration
const API_URL = 'https://forgeos-backend.onrender.com/api'

interface Task {
  id: string
  title: string
  description: string
  status: string
  assigned_agent: string
  priority: string
  difficulty: string
  eta_seconds: number
  model: string
  confidence: number
  created_at: string
  pending_approval?: boolean
  skills?: string[]
}

interface HealthStatus {
  status: string
  last_checked: string
  message: string
}

interface Analytics {
  estimated_tokens: number
  actual_tokens: number
  estimated_cost: number
  actual_cost: number
  estimated_time_seconds: number
  actual_time_seconds: number
  coverage: number
  security_score: number
  quality_score: number
  confidence_avg: number
  loaded_skills_count: number
}

interface Decision {
  id: string
  task_id: string
  timestamp: string
  difficulty: string
  selected_model: string
  reason: string
  loaded_skills: string[]
  estimated_cost: number
  actual_cost: number
  estimated_time: number
  actual_time: number
  outcome: string
}



interface SlackMessage {
  timestamp: string
  message: string
  sender: string
}

interface PipelineEvent {
  timestamp: string
  source: string
  event_type: string
  payload: string
  task_id?: string
}

export default function App() {
  const [goal, setGoal] = useState('Build a FastAPI CRUD API')
  const [tasks, setTasks] = useState<Record<string, Task[]>>({})
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [decisions, setDecisions] = useState<Decision[]>([])

  const [health, setHealth] = useState<Record<string, HealthStatus>>({})
  const [activeChannel, setActiveChannel] = useState('#sprint-main')
  const [slackLogs, setSlackLogs] = useState<SlackMessage[]>([])
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [slashCommand, setSlashCommand] = useState('')

  // Fetch all dashboard data
  const fetchData = async () => {
    try {
      // Fetch Tasks
      const tasksRes = await fetch(`${API_URL}/tasks`)
      if (tasksRes.ok) {
        const tasksData = await tasksRes.json()
        setTasks(tasksData)
      }

      // Fetch Analytics
      const analyticsRes = await fetch(`${API_URL}/analytics`)
      if (analyticsRes.ok) {
        const analyticsData = await analyticsRes.json()
        setAnalytics(analyticsData)
      }

      // Fetch Decisions
      const decisionsRes = await fetch(`${API_URL}/decisions`)
      if (decisionsRes.ok) {
        const decisionsData = await decisionsRes.json()
        setDecisions(decisionsData)
      }



      // Fetch Health
      const healthRes = await fetch(`${API_URL}/health`)
      if (healthRes.ok) {
        const healthData = await healthRes.json()
        setHealth(healthData)
      }
    } catch (err) {
      console.error('Failed to connect to backend api:', err)
      // We do not set error state here to allow fallback demonstration
    }
  }

  // Fetch Slack Logs for active channel
  const fetchSlackLogs = async (channelName: string) => {
    try {
      const res = await fetch(`${API_URL}/slack?channel=${encodeURIComponent(channelName)}`)
      if (res.ok) {
        const logs = await res.json()
        setSlackLogs(logs)
      }
    } catch (err) {
      console.error('Failed to fetch Slack logs:', err)
    }
  }

  // Periodic polling for real-time feel
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    fetchSlackLogs(activeChannel)
    const interval = setInterval(() => fetchSlackLogs(activeChannel), 2000)
    return () => clearInterval(interval)
  }, [activeChannel])

  // Fetch live event log
  const fetchEvents = async () => {
    try {
      const res = await fetch(`${API_URL}/events?limit=60`)
      if (res.ok) setEvents(await res.json())
    } catch (err) {
      console.error('Failed to fetch events:', err)
    }
  }
  useEffect(() => {
    fetchEvents()
    const interval = setInterval(fetchEvents, 2000)
    return () => clearInterval(interval)
  }, [])

  // Trigger Hermes sprint planning
  const handleLaunchSprint = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!goal.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/sprint/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal })
      })
      if (!res.ok) {
        throw new Error('Failed to initiate planning')
      }
      // Wait briefly for backends initialization
      setTimeout(() => {
        fetchData()
        setLoading(false)
      }, 1000)
    } catch (err: any) {
      setError(err.message)
      setLoading(false)
    }
  }

  // Run multi-agent pipeline (Developer -> QA -> Security -> Doc)
  const handleExecutePipeline = async (taskId: string) => {
    try {
      await fetch(`${API_URL}/sprint/execute/${taskId}`, { method: 'POST' })
      fetchData()
    } catch (err) {
      console.error('Failed to trigger task autopilot:', err)
    }
  }

  // Approve a paused sprint to merge and deploy
  const handleApproveSprint = async (taskId: string) => {
    try {
      setLoading(true)
      const res = await fetch(`${API_URL}/sprint/approve/${taskId}`, {
        method: 'POST'
      })
      if (res.ok) {
        await fetchData()
      } else {
        const err = await res.json()
        setError(err.detail || 'Failed to approve sprint')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Handle slash command submission
  const handleSlashCommandSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!slashCommand.trim()) return

    const trimmed = slashCommand.trim()
    const parts = trimmed.split(' ')
    const command = parts[0]
    const text = parts.slice(1).join(' ')

    try {
      setLoading(true)
      const res = await fetch(`${API_URL}/slack/commands`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command, text })
      })
      if (res.ok) {
        setSlashCommand('')
        await fetchData()
      } else {
        const err = await res.json()
        setError(err.detail || 'Failed to execute command')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Reset database for a clean start demo
  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset all tasks and logs?')) return
    try {
      await fetch(`${API_URL}/tasks/reset`, { method: 'POST' })
      fetchData()
    } catch (err) {
      console.error('Failed to reset store:', err)
    }
  }

  return (
    <div className="min-h-screen bg-background text-slate-100 flex flex-col">
      {/* Upper Navigation Header */}
      <header className="border-b border-border bg-surface px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center space-x-3">
          <Layers className="h-8 w-8 text-primary animate-pulse" />
          <div>
            <h1 className="text-xl font-bold tracking-tight flex items-center space-x-2">
              <span>ForgeOS</span>
              <span className="text-xs bg-accent/20 text-accent border border-accent/40 rounded px-1.5 py-0.5 ml-2 font-mono">
                Simulation Ready
              </span>
            </h1>
            <p className="text-xs text-slate-400">AI multi-agent software engineering framework</p>
          </div>
        </div>

        {/* Global Statistics Indicators */}
        <div className="flex items-center space-x-6 text-sm">
          <div className="bg-card border border-border px-3 py-1.5 rounded-lg">
            <span className="text-xs text-slate-400 block">Est / Actual Tokens</span>
            <span className="font-mono font-medium text-emerald-400">
              {analytics?.estimated_tokens ? `${analytics.estimated_tokens.toLocaleString()} / ${analytics.actual_tokens.toLocaleString()}` : '—'}
            </span>
          </div>
          <div className="bg-card border border-border px-3 py-1.5 rounded-lg">
            <span className="text-xs text-slate-400 block">Sprint Cost</span>
            <span className="font-mono font-medium text-primary">
              {analytics?.actual_cost !== undefined ? `$${analytics.actual_cost.toFixed(4)}` : '—'}
            </span>
          </div>
          <div className="bg-card border border-border px-3 py-1.5 rounded-lg">
            <span className="text-xs text-slate-400 block">QA Coverage</span>
            <span className="font-mono font-medium text-accent">
              {analytics?.coverage !== undefined ? `${analytics.coverage}%` : '—'}
            </span>
          </div>
          <div className="bg-card border border-border px-3 py-1.5 rounded-lg">
            <span className="text-xs text-slate-400 block">Security Score</span>
            <span className="font-mono font-medium text-emerald-400">
              {analytics?.security_score !== undefined ? `${analytics.security_score}/100` : '—'}
            </span>
          </div>
          <button
            onClick={handleReset}
            className="p-2 bg-red-950/40 hover:bg-red-900/60 border border-red-900/50 rounded-lg text-red-400 text-xs transition duration-200"
            title="Reset Board Database"
          >
            Reset Board
          </button>
        </div>
      </header>

      {/* Main Grid Content */}
      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-4 gap-6 overflow-hidden">

        {/* LEFT COLUMN: Controls, Health Monitor, Skill Engine */}
        <div className="space-y-6 flex flex-col">
          {/* Goal Input Console */}
          <div className="bg-surface border border-border p-4 rounded-xl shadow-lg">
            <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center space-x-2">
              <Cpu className="h-4 w-4 text-primary" />
              <span>Orchestrator Command Panel</span>
            </h2>
            <form onSubmit={handleLaunchSprint} className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Define Engineering Goal</label>
                <textarea
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="w-full bg-card border border-border rounded-lg p-2.5 text-sm text-slate-100 focus:outline-none focus:border-primary transition duration-150 h-20 resize-none"
                  placeholder="e.g. Build a FastAPI CRUD API"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 bg-primary hover:bg-primary/95 text-white font-medium rounded-lg text-sm flex items-center justify-center space-x-2 transition duration-200"
              >
                {loading ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    <span>Orchestrate Sprint</span>
                  </>
                )}
              </button>
            </form>
            {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
          </div>

          {/* Health Monitor */}
          <div className="bg-surface border border-border p-4 rounded-xl shadow-lg flex-1 overflow-y-auto">
            <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center space-x-2">
              <Activity className="h-4 w-4 text-emerald-400" />
              <span>System Health Checks</span>
            </h2>
            <div className="space-y-2.5">
              {Object.entries(health).length > 0 ? (
                Object.entries(health).map(([service, state]) => (
                  <div key={service} className="bg-card border border-border/60 p-2 rounded-lg flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${state.status === 'Healthy' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' :
                        state.status === 'Warning' ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]' :
                          'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
                        }`} />
                      <span className="font-semibold text-slate-200">{service}</span>
                    </div>
                    <span className="text-[10px] text-slate-400 truncate max-w-[140px]" title={state.message}>
                      {state.message}
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400">Loading health monitor...</div>
              )}
            </div>
          </div>

          {/* Skill Engine Status */}
          <div className="bg-surface border border-border p-4 rounded-xl shadow-lg">
            <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center space-x-2">
              <BookOpen className="h-4 w-4 text-accent" />
              <span>Active Claude-style Skills</span>
            </h2>
            <div className="flex flex-wrap gap-1.5">
              {(() => {
                const activeSkills = decisions[0]?.loaded_skills || [];
                const allSkills = [
                  'backend', 'frontend', 'react', 'fastapi', 'python',
                  'database', 'testing', 'security', 'documentation',
                  'deployment', 'github', 'review', 'debugging', 'architecture'
                ];
                return allSkills.map(skill => {
                  const isActive = activeSkills.includes(skill);
                  return (
                    <span
                      key={skill}
                      className={`text-xs px-2 py-1 rounded cursor-pointer transition duration-150 border ${isActive
                        ? 'bg-accent/25 border-accent text-accent font-semibold shadow-sm shadow-accent/10'
                        : 'bg-card border-border text-slate-400 hover:border-accent/30'
                        }`}
                      title={isActive ? 'Skill Active for current Sprint' : 'Skill Inactive'}
                    >
                      skills/{skill}/
                    </span>
                  );
                });
              })()}
            </div>
          </div>
        </div>

        {/* MIDDLE COLUMNS: Kanban Board & Slack Channels (2/4 width) */}
        <div className="lg:col-span-2 space-y-6 flex flex-col">
          {/* Kanban Board Container */}
          <div className="bg-surface border border-border p-4 rounded-xl shadow-lg flex-1 flex flex-col min-h-0">
            <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center space-x-2">
              <Layout className="h-4 w-4 text-primary" />
              <span>Sprint Kanban Board</span>
            </h2>

            <div className="flex-1 grid grid-cols-4 gap-3 overflow-x-auto pb-2 min-h-0">
              {/* Backlog / Planning column */}
              <div className="bg-card/40 border border-border/50 rounded-lg p-2 flex flex-col">
                <div className="text-xs font-semibold text-slate-400 mb-2 border-b border-border/40 pb-1 flex justify-between items-center">
                  <span>BACKLOG & PLANS</span>
                  <span className="bg-border px-1.5 py-0.5 rounded text-[10px]">
                    {((tasks['Backlog'] || []).length + (tasks['Planning'] || []).length)}
                  </span>
                </div>
                <div className="space-y-2 flex-1 overflow-y-auto pr-1">
                  {[...(tasks['Backlog'] || []), ...(tasks['Planning'] || [])].map((t) => (
                    <div key={t.id} className="bg-card border border-border p-2.5 rounded-lg text-xs space-y-2 hover:border-primary/50 transition">
                      <div className="flex justify-between items-start">
                        <span className="font-semibold text-slate-200 line-clamp-1">{t.title}</span>
                        <span className={`text-[9px] px-1 rounded font-bold ${t.priority === 'High' ? 'text-red-400 bg-red-950/20' : 'text-slate-400 bg-slate-900'
                          }`}>{t.priority}</span>
                      </div>
                      <p className="text-slate-400 text-[11px] line-clamp-2">{t.description}</p>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 border-t border-border/30 pt-1.5">
                        <span className="font-mono bg-border/40 px-1 rounded">{t.model}</span>
                        <span>Diff: {t.difficulty}</span>
                      </div>
                      {t.status === 'Planning' && (
                        <button
                          onClick={() => handleExecutePipeline(t.id)}
                          className="w-full py-1 bg-primary/20 hover:bg-primary/30 border border-primary/50 rounded text-primary text-[10px] font-medium transition"
                        >
                          Execute Autopilot
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* In Progress / Review column */}
              <div className="bg-card/40 border border-border/50 rounded-lg p-2 flex flex-col">
                <div className="text-xs font-semibold text-slate-400 mb-2 border-b border-border/40 pb-1 flex justify-between items-center">
                  <span>DEV & REVIEW</span>
                  <span className="bg-border px-1.5 py-0.5 rounded text-[10px]">
                    {((tasks['In Progress'] || []).length + (tasks['Review'] || []).length)}
                  </span>
                </div>
                <div className="space-y-2 flex-1 overflow-y-auto pr-1">
                  {[...(tasks['In Progress'] || []), ...(tasks['Review'] || [])].map((t) => (
                    <div key={t.id} className="bg-card border border-border p-2.5 rounded-lg text-xs space-y-2 border-l-2 border-l-primary hover:border-primary/50 transition">
                      <div className="flex justify-between items-start">
                        <span className="font-semibold text-slate-200">{t.title}</span>
                        <span className="bg-blue-950/40 text-blue-400 border border-blue-900/40 px-1 rounded text-[9px] font-bold">
                          {t.status}
                        </span>
                      </div>
                      <p className="text-slate-400 text-[11px]">{t.description}</p>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 border-t border-border/30 pt-1.5">
                        <span className="font-mono bg-border/40 px-1 rounded">{t.model}</span>
                        <span>Agent: Dev</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Testing / Security column */}
              <div className="bg-card/40 border border-border/50 rounded-lg p-2 flex flex-col">
                <div className="text-xs font-semibold text-slate-400 mb-2 border-b border-border/40 pb-1 flex justify-between items-center">
                  <span>TEST & AUDIT</span>
                  <span className="bg-border px-1.5 py-0.5 rounded text-[10px]">
                    {((tasks['Testing'] || []).length + (tasks['Security'] || []).length)}
                  </span>
                </div>
                <div className="space-y-2 flex-1 overflow-y-auto pr-1">
                  {[...(tasks['Testing'] || []), ...(tasks['Security'] || [])].map((t) => (
                    <div key={t.id} className="bg-card border border-border p-2.5 rounded-lg text-xs space-y-2 border-l-2 border-l-amber-500 hover:border-amber-500/50 transition">
                      <div className="flex justify-between items-start">
                        <span className="font-semibold text-slate-200">{t.title}</span>
                        <span className="bg-amber-950/40 text-amber-400 border border-amber-900/40 px-1 rounded text-[9px] font-bold">
                          {t.status}
                        </span>
                      </div>
                      <p className="text-slate-400 text-[11px]">{t.description}</p>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 border-t border-border/30 pt-1.5">
                        <span className="font-mono bg-border/40 px-1 rounded">{t.model}</span>
                        <span>Agent: QA/Sec</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Done column */}
              <div className="bg-card/40 border border-border/50 rounded-lg p-2 flex flex-col">
                <div className="text-xs font-semibold text-slate-400 mb-2 border-b border-border/40 pb-1 flex justify-between items-center">
                  <span>DONE</span>
                  <span className="bg-border px-1.5 py-0.5 rounded text-[10px]">
                    {((tasks['Documentation'] || []).length + (tasks['Done'] || []).length)}
                  </span>
                </div>
                <div className="space-y-2 flex-1 overflow-y-auto pr-1">
                  {[...(tasks['Documentation'] || []), ...(tasks['Done'] || [])].map((t) => (
                    <div key={t.id} className="bg-card border border-border p-2.5 rounded-lg text-xs space-y-2 border-l-2 border-l-emerald-500 hover:border-emerald-500/50 transition">
                      <div className="flex justify-between items-start">
                        <span className="font-semibold text-slate-200 line-clamp-1">{t.title}</span>
                        <span className="bg-emerald-950/40 text-emerald-400 border border-emerald-900/40 px-1 rounded text-[9px] font-bold">
                          {t.status}
                        </span>
                      </div>
                      <p className="text-slate-400 text-[11px] line-clamp-2">{t.description}</p>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 border-t border-border/30 pt-1.5">
                        <span className="font-mono bg-border/40 px-1 rounded">{t.model}</span>
                        <span>Confidence: {(t.confidence * 100).toFixed(0)}%</span>
                      </div>
                      {t.pending_approval && (
                        <button
                          onClick={() => handleApproveSprint(t.id)}
                          className="w-full mt-2 py-1.5 bg-emerald-600 hover:bg-emerald-700 border border-emerald-500 rounded text-white text-[10px] font-semibold transition shadow-md shadow-emerald-950/20"
                        >
                          Approve & Deploy Sprint
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Slack Feed */}
          <div className="bg-surface border border-border rounded-xl shadow-lg flex-1 flex flex-col min-h-0 overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
              <div className="flex items-center space-x-2">
                <Terminal className="h-4 w-4 text-accent" />
                <span className="text-sm font-semibold text-slate-300">Slack — {activeChannel}</span>
                {slackLogs.length > 0 && (
                  <span className="text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded px-1.5 py-0.5">
                    LIVE · {slackLogs.length} messages
                  </span>
                )}
              </div>
              <span className="text-[10px] font-mono text-slate-500">auto-refresh 2s</span>
            </div>

            {/* Channel tabs */}
            <div className="flex border-b border-border overflow-x-auto shrink-0 bg-black/20">
              {[
                '#sprint-main', '#agent-developer', '#agent-security',
                '#agent-qa', '#agent-docs', '#ci-cd', '#analytics',
                '#human-review', '#system-health', '#agent-log'
              ].map(chan => (
                <button
                  key={chan}
                  onClick={() => setActiveChannel(chan)}
                  className={`text-[11px] px-3 py-2 whitespace-nowrap transition border-b-2 ${activeChannel === chan
                    ? 'text-white font-semibold border-b-accent bg-accent/10'
                    : 'text-slate-500 border-b-transparent hover:text-slate-300 hover:bg-white/5'
                    }`}
                >
                  {chan}
                </button>
              ))}
            </div>

            {/* Messages — newest at bottom, auto-scroll */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3"
              ref={(el) => { if (el) el.scrollTop = el.scrollHeight }}
            >
              {slackLogs.length > 0 ? (
                slackLogs.map((log, idx) => {
                  const initials = log.sender.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()
                  const avatarColors = ['bg-violet-600', 'bg-blue-600', 'bg-emerald-600', 'bg-orange-600', 'bg-pink-600', 'bg-cyan-600']
                  const avatarColor = avatarColors[log.sender.length % avatarColors.length]
                  return (
                    <div key={idx} className="flex items-start space-x-3 group">
                      {/* Avatar */}
                      <div className={`${avatarColor} rounded shrink-0 w-8 h-8 flex items-center justify-center text-white text-[10px] font-bold`}>
                        {initials}
                      </div>
                      {/* Body */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline space-x-2 mb-0.5">
                          <span className="text-sm font-semibold text-slate-200">{log.sender}</span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-[13px] text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
                          {log.message}
                        </p>
                      </div>
                    </div>
                  )
                })
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center py-12 space-y-2">
                  <Terminal className="h-8 w-8 text-slate-700" />
                  <p className="text-slate-500 text-sm">No messages in {activeChannel} yet.</p>
                  <p className="text-slate-600 text-xs">Use the terminal below to send a command — messages will appear here in real time.</p>
                </div>
              )}
            </div>

            {/* Command input */}
            <div className="border-t border-border px-4 py-3 shrink-0">
              <form onSubmit={handleSlashCommandSubmit} className="flex items-center space-x-2">
                <span className="text-sm font-mono text-slate-500 shrink-0">/forge</span>
                <input
                  type="text"
                  value={slashCommand}
                  onChange={(e) => setSlashCommand(e.target.value)}
                  placeholder="sprint &quot;Build a FastAPI CRUD API&quot; · status · health · logs · approve &lt;id&gt;"
                  className="flex-1 bg-card border border-border/80 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-accent transition"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-accent hover:bg-accent/90 rounded-lg text-white text-sm font-medium transition disabled:opacity-50"
                >
                  {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : 'Send'}
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Live Event Console + Decision Log */}
        <div className="space-y-6 flex flex-col overflow-hidden">

          {/* Live Event Console */}
          <div className="bg-surface border border-border rounded-xl shadow-lg flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-border flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-300 flex items-center space-x-2">
                <Activity className="h-4 w-4 text-emerald-400" />
                <span>Live Event Console</span>
              </h2>
              <span className="text-[10px] font-mono text-slate-500">
                {events.length} events · auto-refresh 2s
              </span>
            </div>
            <div className="flex-1 overflow-y-auto font-mono text-[11px] p-3 space-y-0 bg-black/40">
              {events.length > 0 ? (
                events.map((ev, idx) => {
                  const sourceColors: Record<string, string> = {
                    'Slack': 'text-violet-400',
                    'Hermes': 'text-blue-400',
                    'Skills': 'text-cyan-400',
                    'Router': 'text-yellow-400',
                    'Developer': 'text-emerald-400',
                    'Git': 'text-orange-400',
                    'CI': 'text-pink-400',
                    'QA': 'text-teal-400',
                    'Security': 'text-red-400',
                    'Documentation': 'text-indigo-400',
                    'System': 'text-slate-400',
                    'Dashboard': 'text-purple-400',
                    'Slack Gateway': 'text-violet-300',
                  }
                  const col = sourceColors[ev.source] || 'text-slate-300'
                  const isLast = idx === 0
                  return (
                    <div key={idx} className={`flex items-start space-x-2 py-1 border-b border-border/10 last:border-0 ${isLast ? 'opacity-100' : 'opacity-80'}`}>
                      <span className="text-slate-600 shrink-0 w-16">{ev.timestamp.slice(11, 19)}</span>
                      <span className={`${col} font-semibold shrink-0 w-24`}>{ev.source}</span>
                      <span className="text-slate-400 shrink-0 w-28">{ev.event_type}</span>
                      <span className="text-slate-300 truncate">{ev.payload}</span>
                    </div>
                  )
                })
              ) : (
                <div className="text-slate-600 italic pt-4 text-center">
                  Waiting for events…<br />
                  <span className="text-[10px]">Send <code className="text-accent">/forge sprint "your goal"</code> to start</span>
                </div>
              )}
            </div>
          </div>

          {/* Decision Engine Logs (compact) */}
          <div className="bg-surface border border-border p-4 rounded-xl shadow-lg h-56 flex flex-col">
            <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center space-x-2">
              <BarChart2 className="h-4 w-4 text-primary" />
              <span>Routing Decisions</span>
            </h2>
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {decisions.length > 0 ? (
                decisions.map((dec) => (
                  <div key={dec.id} className="bg-card border border-border p-2.5 rounded-lg text-xs space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-slate-200 font-mono text-[10px]">{dec.id}</span>
                      <span className="text-[10px] text-slate-400">{new Date(dec.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div className="flex flex-wrap gap-2 font-mono text-[10px] text-slate-300">
                      <span>Model: <span className="text-primary font-semibold">{dec.selected_model}</span></span>
                      <span>Cost: <span className="text-emerald-400">${dec.actual_cost?.toFixed(4)}</span></span>
                      <span>Skills: <span className="text-slate-400">{dec.loaded_skills?.join(', ') || '-'}</span></span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400">No decisions logged yet.</div>
              )}
            </div>
          </div>
        </div>

      </main>
    </div>
  )
}
