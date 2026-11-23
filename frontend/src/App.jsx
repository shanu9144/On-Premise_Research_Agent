import { useEffect, useState } from 'react'
import {
  ArrowUpRight, Check, ChevronDown, CircleHelp, Clock3, Command, FileText, Globe2,
  LoaderCircle, Menu, MoreHorizontal, PanelLeft, Search, Send, SlidersHorizontal,
  Sparkles, Trash2,
} from 'lucide-react'
import './App.css'

const apiBase = () => (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

// Anonymous per-browser ID so each visitor only sees their own history.
function clientId() {
  let id = localStorage.getItem('fieldnotes-client-id')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('fieldnotes-client-id', id)
  }
  return id
}

async function apiRequest(path, options = {}) {
  let response
  try {
    response = await fetch(`${apiBase()}${path}`, { ...options, headers: { ...options.headers, 'X-Client-Id': clientId() } })
  } catch {
    throw new Error('Could not reach the research server. It may be waking up - try again in a minute.')
  }
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Request failed')
  return result
}

const routeFromHash = () => (window.location.hash === '#/history' ? 'history' : 'research')

function Digest({ entry }) {
  const { query, digest, sources } = entry
  return (
    <section className="results-grid" aria-live="polite">
      <article className="digest-panel">
        <div className="panel-heading">
          <div><span className="section-label">Research digest</span><h2>The short version</h2>{query && <p className="answered-query">“{query}”</p>}</div>
          <button className="small-action" type="button" title="Copy digest" aria-label="Copy digest" onClick={() => navigator.clipboard?.writeText(digest)}><FileText size={15} />Copy</button>
        </div>
        <div className="digest-body">{digest.split('\n').map((line, index) => line.startsWith('## ') ? <h3 key={index}>{line.replace('## ', '')}</h3> : line.trim() ? <p className={/^\d+\. /.test(line) ? 'digest-list' : undefined} key={index}>{line}</p> : <div className="digest-space" key={index} />)}</div>
        <div className="confidence"><Check size={14} /><span><b>Grounded answer</b><small>Based on {sources.length} selected sources · verify details before relying on them</small></span></div>
      </article>
      <aside className="sources-panel" id="sources">
        <div className="panel-heading"><div><span className="section-label">Source trail</span><h2>{sources.length} sources</h2></div></div>
        <div className="source-list">{sources.map((source, index) => <a className="source-item" href={source.url} target="_blank" rel="noreferrer" key={`${source.url}-${index}`}><div className="source-number">0{index + 1}</div><div className="source-content"><div className="source-title">{source.title}<ArrowUpRight size={14} /></div><div className="source-domain">{source.domain}</div><p>{source.snippet}</p><span className="source-tag">{source.tag}</span></div></a>)}</div>
      </aside>
    </section>
  )
}

function ResearchPage({ result, onResult }) {
  const [query, setQuery] = useState('')
  const [provider, setProvider] = useState('Auto-select')
  const [depth, setDepth] = useState('Balanced')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  async function runResearch(event) {
    event.preventDefault()
    const question = query.trim()
    if (!question || running) return
    setRunning(true)
    setError('')
    try {
      const answer = await apiRequest('/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: question, provider, depth }) })
      onResult({ id: answer.id, query: question, digest: answer.digest || answer.summary || '', sources: answer.sources || [] })
      setQuery('')
    } catch (requestError) {
      setError(requestError.message || 'Could not reach the research server.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="page-wrap">
      <section className="intro"><div className="eyebrow"><span className="eyebrow-line"></span>Personal research desk</div><h1>Find the signal.<br /><em>Keep the sources.</em></h1><p>Ask a question, choose how deep to go, and get a grounded digest you can actually trace.</p></section>
      <form className="query-card" onSubmit={runResearch}>
        <label htmlFor="research-query">What are you researching?</label>
        <textarea id="research-query" autoFocus value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); event.currentTarget.form.requestSubmit() } }} rows="3" placeholder="Ask a question..." />
        <div className="query-footer"><span className="hint"><span className="keycap">⌘</span><span className="keycap">↵</span> or Ctrl+Enter to search</span><button className="search-button" type="submit" disabled={running || !query.trim()}>{running ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}{running ? 'Researching' : 'Start research'}</button></div>
      </form>
      <div className="controls-row">
        <div className="control-group"><label htmlFor="provider">Provider</label><div className="select-wrap"><Globe2 size={15} /><select id="provider" value={provider} onChange={(event) => setProvider(event.target.value)}><option>Auto-select</option><option>Exa</option><option>Tavily</option><option>Firecrawl</option></select><ChevronDown size={14} /></div></div>
        <div className="control-group"><label htmlFor="depth">Depth</label><div className="select-wrap"><Search size={15} /><select id="depth" value={depth} onChange={(event) => setDepth(event.target.value)}><option>Quick</option><option>Balanced</option><option>Deep research</option></select><ChevronDown size={14} /></div></div>
        <div className="run-meta"><span className="status-dot"></span>{running ? 'Searching across the web...' : 'Ready for a new question'}</div>
      </div>
      {error && <div className="api-error" role="alert">{error}</div>}
      {result && <Digest entry={result} />}
    </div>
  )
}

function HistoryPage({ history, onDelete }) {
  const [selected, setSelected] = useState(null)
  const [loadingId, setLoadingId] = useState(null)
  const [error, setError] = useState('')

  async function openEntry(id) {
    if (loadingId) return
    setLoadingId(id)
    setError('')
    try {
      setSelected(await apiRequest(`/history/${id}`))
    } catch (requestError) {
      setError(requestError.message || 'Could not load this history entry.')
    } finally {
      setLoadingId(null)
    }
  }

  async function deleteEntry(id) {
    try {
      await apiRequest(`/history/${id}`, { method: 'DELETE' })
      onDelete(id)
      if (selected?.id === id) setSelected(null)
    } catch (requestError) {
      setError(requestError.message || 'Could not delete this history entry.')
    }
  }

  return (
    <div className="page-wrap history-page">
      <section className="intro"><div className="eyebrow"><span className="eyebrow-line"></span>Saved in your database</div><h1>Your <em>history.</em></h1></section>
      {error && <div className="api-error" role="alert">{error}</div>}
      <div className="history-layout">
        <aside className="history-panel" aria-label="Research history">
          <div className="panel-heading"><div><span className="section-label">All questions</span><h2>{history.length} saved</h2></div></div>
          {history.length === 0 ? <p className="history-empty">Answered questions are saved here.</p> : <ul className="history-list">{history.map((item) => <li key={item.id} className={item.id === selected?.id ? 'history-item active' : 'history-item'}><button type="button" className="history-open" onClick={() => openEntry(item.id)} disabled={loadingId !== null}><span className="history-query">{item.query}</span><span className="history-meta">{loadingId === item.id ? 'Loading…' : `${new Date(item.created_at).toLocaleString()} · ${item.source_count} sources`}</span></button><button type="button" className="history-delete" title="Delete from history" aria-label="Delete from history" onClick={() => deleteEntry(item.id)}><Trash2 size={14} /></button></li>)}</ul>}
        </aside>
        <div className="history-detail">{selected ? <Digest entry={selected} /> : <div className="empty-state">Select a question to load its full digest and sources.</div>}</div>
      </div>
    </div>
  )
}

function App() {
  const [route, setRoute] = useState(routeFromHash)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => {
    fetch(`${apiBase()}/health`).catch(() => {})
    const onHashChange = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  // Reload the list whenever the History page opens so it also shows newly saved answers.
  useEffect(() => {
    if (route !== 'history') return undefined
    let cancelled = false
    apiRequest('/history').then((data) => { if (!cancelled) setHistory(data.items) }).catch(() => {})
    return () => { cancelled = true }
  }, [route, result])

  const navItems = [
    { key: 'research', href: '#/', label: 'Research desk', icon: <PanelLeft size={17} /> },
    { key: 'history', href: '#/history', label: 'History', icon: <Clock3 size={17} /> },
  ]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><Sparkles size={16} /></span><span>fieldnotes</span></div>
        <nav className="main-nav" aria-label="Main navigation">{navItems.map((item) => <a key={item.key} className={route === item.key ? 'nav-item active' : 'nav-item'} href={item.href} aria-current={route === item.key ? 'page' : undefined}>{item.icon}{item.label}</a>)}</nav>
        <div className="sidebar-bottom"><button className="nav-item ghost-button" type="button"><SlidersHorizontal size={17} />Preferences</button><button className="nav-item ghost-button" type="button"><CircleHelp size={17} />Help & feedback</button></div>
      </aside>

      <main className="main-content" id="workspace">
        <header className="topbar"><div className="mobile-brand"><Menu size={18} /><span>fieldnotes</span></div><nav className="mobile-nav" aria-label="Main navigation">{navItems.map((item) => <a key={item.key} className={route === item.key ? 'active' : undefined} href={item.href}>{item.label}</a>)}</nav><div className="topbar-actions"><button className="icon-button" title="Open command menu" aria-label="Open command menu"><Command size={17} /></button><button className="icon-button" title="More options" aria-label="More options"><MoreHorizontal size={18} /></button></div></header>
        {route === 'history'
          ? <HistoryPage history={history} onDelete={(id) => setHistory((items) => items.filter((item) => item.id !== id))} />
          : <ResearchPage result={result} onResult={setResult} />}
        <footer className="footer-note page-footer"><span><span className="status-dot"></span>Sources stay visible by default</span><span>Powered by Groq <Sparkles size={13} /></span></footer>
      </main>
    </div>
  )
}

export default App
