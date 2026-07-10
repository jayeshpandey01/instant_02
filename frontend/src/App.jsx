import React, { useState, useEffect } from 'react';
import {
  Activity,
  Terminal,
  Settings as SettingsIcon,
  BookOpen,
  Play,
  Square,
  RefreshCw,
  Copy,
  Check,
  Cpu,
  HardDrive,
  Layers,
  AlertTriangle,
  ExternalLink,
  Zap,
  Server,
  Flag,
  Wifi,
  ChevronDown,
  RotateCcw,
  Clock,
  DownloadCloud
} from 'lucide-react';

/* ── Tiny helper: format bytes → "X GiB" ───────────────────────────── */
function fmtBytes(str = '') {
  return str;
}

/* ── Compact progress double bar ────────────────────────────────────── */
function SegBar({ valueA = 0, valueB = 0, variant }) {
  return (
    <div className={`seg-bar ${variant ? 'variant-' + variant : ''}`}>
      {/* quota (blue, wider) */}
      <div className="seg-bar-fill-b" style={{ width: `${Math.min(valueB, 100)}%` }} />
      {/* provisioned / used (green, narrower) */}
      <div className="seg-bar-fill-a" style={{ width: `${Math.min(valueA, 100)}%` }} />
    </div>
  );
}

/* ── Single capacity card ────────────────────────────────────────────── */
function CapacityCard({ icon: Icon, label, value, unit, usedPct, quotaPct, meta, variant }) {
  const numVal = value?.replace('%', '') ?? '0';
  const isPercent = value?.includes('%');

  return (
    <div className={`capacity-card ${variant ? 'variant-' + variant : ''}`}>
      <div className="capacity-card-header">
        <div className="capacity-card-label">
          <Icon size={14} />
          {label}
        </div>
        <div className="capacity-card-value">
          {numVal}
          <sup>{isPercent ? '%' : unit}</sup>
        </div>
      </div>
      <SegBar valueA={usedPct} valueB={quotaPct} variant={variant} />
      <div className="capacity-card-meta">
        {meta.map((m, i) => (
          <span key={i}>{m}</span>
        ))}
      </div>
    </div>
  );
}

/* ── Sidebar nav item ────────────────────────────────────────────────── */
function NavItem({ icon: Icon, label, active, onClick }) {
  return (
    <button className={`nav-item${active ? ' active' : ''}`} onClick={onClick}>
      <Icon size={15} className="nav-icon" />
      {label}
    </button>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState('summary');          // 'summary' | 'metrics'
  const [activeTab, setActiveTab] = useState('utilization');         // sidebar tab
  const [systemStatus, setSystemStatus] = useState({
    docker_installed: true,
    status: 'offline',
    containers: [],
    tunnel_url: null
  });
  const [systemStats, setSystemStats] = useState({
    containers: [],
    totals: { cpu: '0%', memory: '0%' }
  });
  const [usageStats, setUsageStats] = useState({
    total_requests: 0,
    successful_requests: 0,
    failed_requests: 0,
    platforms: {}
  });
  const [logs, setLogs] = useState('Loading logs...');
  const [selectedLogService, setSelectedLogService] = useState('');
  const [copied, setCopied] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [now, setNow] = useState(new Date());
  // BUG-006 FIX: Real cookie status fetched from server
  const [cookieStatus, setCookieStatus] = useState({});
  // BUG-004 FIX: Expose manual refresh trigger
  const [refreshTick, setRefreshTick] = useState(0);

  const [cookieInputs, setCookieInputs] = useState({});
  const [expandedCookie, setExpandedCookie] = useState(null);

  // Clear action loading state when server comes online or goes offline
  useEffect(() => {
    setActionLoading(false);
  }, [systemStatus.status]);

  // Clock tick
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(t);
  }, []);

  // Poll status & stats — re-runs when refreshTick changes (BUG-004)
  useEffect(() => {
    const fetchStatus = () =>
      fetch('/api/control/status')
        .then(r => r.json())
        .then(d => {
          setSystemStatus(d);
          if (d.status === 'online') {
            setActionLoading(false);
          }
        })
        .catch(() => {});

    const fetchStats = () =>
      fetch('/api/control/stats')
        .then(r => r.json())
        .then(d => setSystemStats(d))
        .catch(() => {});

    const fetchUsageStats = () =>
      fetch('/api/control/usage-stats')
        .then(r => r.json())
        .then(d => setUsageStats(d))
        .catch(() => {});

    // BUG-006 FIX: Fetch real cookie status from server
    const fetchCookieStatus = () =>
      fetch('/api/control/cookie-status')
        .then(r => r.json())
        .then(d => setCookieStatus(d))
        .catch(() => {});

    fetchStatus(); fetchStats(); fetchUsageStats(); fetchCookieStatus();
    const iv = setInterval(() => { fetchStatus(); fetchStats(); fetchUsageStats(); }, 8000);
    return () => clearInterval(iv);
  }, [refreshTick]);

  // Poll logs
  useEffect(() => {
    if (activeTab !== 'logs' && !(activeTab === 'utilization' && actionLoading)) return;
    const fetchLogs = () => {
      const url = selectedLogService
        ? `/api/control/logs?service=${selectedLogService}`
        : '/api/control/logs';
      fetch(url)
        .then(r => {
          if (!r.ok) {
            return r.json()
              .then(errJson => {
                throw new Error(errJson.error || errJson.logs || r.statusText);
              })
              .catch(() => {
                throw new Error(r.statusText);
              });
          }
          return r.json();
        })
        .then(d => {
          if (d && typeof d.logs === 'string') {
            setLogs(d.logs);
          } else {
            throw new Error(d?.error || "Invalid response format: 'logs' property missing");
          }
        })
        .catch(e => setLogs(`Failed to fetch logs: ${e.message || e}`));
    };
    fetchLogs();
    const iv = setInterval(fetchLogs, 3000);
    return () => clearInterval(iv);
  }, [activeTab, selectedLogService, actionLoading]);

  // BUG-005 FIX: Check r.ok before treating response as success
  const handleAction = (action) => {
    setActionLoading(true);
    fetch('/api/control/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    })
      .then(r => {
        if (!r.ok) throw new Error(`Server error: ${r.status}`);
        return r.json();
      })
      .then(() => {
        if (action === 'stop' || action === 'restart') {
          setTimeout(() => setActionLoading(false), 5000);
        } else {
          setTimeout(() => setActionLoading(false), 15000); // 15 seconds fallback for start/rebuild
        }
      })
      .catch(err => { alert(`Action failed: ${err}`); setActionLoading(false); });
  };

  // BUG-011 FIX: Clipboard fallback for WebView context (navigator.clipboard may be restricted)
  const copyToClipboard = (text) => {
    const doFallback = () => {
      try {
        const el = document.createElement('textarea');
        el.value = text;
        el.style.position = 'fixed';
        el.style.opacity = '0';
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (_) { /* silent */ }
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); })
        .catch(doFallback);
    } else {
      doFallback();
    }
  };

  const cpuPercent  = parseFloat(systemStats.totals.cpu?.replace('%', '')) || 0;
  const memPercent  = parseFloat(systemStats.totals.memory?.replace('%', '')) || 0;
  const isOnline    = systemStatus.status === 'online';
  const timeStr     = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  // BUG-004 FIX: Manual refresh handler
  const handleManualRefresh = () => setRefreshTick(t => t + 1);
  // BUG-009 FIX: Docker warning only relevant on operational tabs
  const DOCKER_DEPENDENT_TABS = ['utilization', 'containers', 'logs', 'networking'];
  const showDockerWarning = !systemStatus.docker_installed && DOCKER_DEPENDENT_TABS.includes(activeTab);

  const handleSaveCookie = (service) => {
    fetch('/api/control/cookies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service, cookies: cookieInputs[`${service}_COOKIES`] || '' })
    }).then(r => r.json()).then(res => {
      if (res.status === 'success') {
        setExpandedCookie(null);
        setCookieInputs(prev => ({...prev, [`${service}_COOKIES`]: ''}));
        handleManualRefresh();
      } else {
        alert(res.error || 'Failed to save');
      }
    }).catch(err => alert(`Error: ${err}`));
  };

  const handleClearCookie = (service) => {
    if (!window.confirm(`Clear cookies for ${service}?`)) return;
    fetch(`/api/control/cookies/${service}`, { method: 'DELETE' })
      .then(response => {
        if (!response.ok) {
          alert(`Error: ${response.statusText}`);
          return;
        }
        handleManualRefresh();
      })
      .catch(err => alert(`Error: ${err}`));
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg-base)' }}>

      {/* ═══════════════ SIDEBAR ═══════════════ */}
      <aside className="sidebar">

        {/* System label (top brand area) */}
        <div className="sidebar-system-label">
          <div className="sys-tag">System</div>
          <div className="sys-name">
            <Layers size={16} />
            Reclip Control
          </div>
        </div>

        {/* Jump bar */}
        <div className="sidebar-jump">
          <Zap size={12} className="jump-icon" />
          <span style={{ fontSize: 11 }}>Jump to</span>
          <span className="jump-kbd">CMD+K</span>
        </div>

        {/* Docs shortcut */}
        <button
          className={`nav-item${activeTab === 'docs' ? ' active' : ''}`}
          style={{ marginTop: 6 }}
          onClick={() => setActiveTab('docs')}
        >
          <BookOpen size={15} className="nav-icon" />
          API Docs
        </button>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--border-subtle)', margin: '10px 0' }} />

        {/* System section */}
        <div className="nav-section-label">System</div>

        <NavItem icon={Activity}   label="Utilization"     active={activeTab === 'utilization'} onClick={() => setActiveTab('utilization')} />
        <NavItem icon={SettingsIcon} label="Settings"      active={activeTab === 'settings'}    onClick={() => setActiveTab('settings')} />
        <NavItem icon={Terminal}   label="Console Logs"    active={activeTab === 'logs'}        onClick={() => setActiveTab('logs')} />

        {/* Footer */}
        <div className="sidebar-footer">
          <span>Server Version</span>
          <span>v11.7.1</span>
        </div>
      </aside>

      {/* ═══════════════ MAIN ═══════════════ */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-surface)' }}>

        {/* Top bar */}
        <div className="topbar">
          <div className="topbar-title">
            <Activity size={18} />
            {activeTab === 'utilization' ? 'Utilization'
              : activeTab === 'logs'      ? 'Console Logs'
              : activeTab === 'docs'      ? 'API Docs'
              : 'Settings'
            }
          </div>

          {/* Right side actions */}
          <div className="topbar-actions">
            <button
              className="btn btn-start"
              disabled={actionLoading || !systemStatus.docker_installed}
              onClick={() => handleAction('start')}
            >
              <Play size={11} fill="currentColor" />
              Start
            </button>
            <button
              className="btn btn-stop"
              disabled={actionLoading || !systemStatus.docker_installed}
              onClick={() => handleAction('stop')}
            >
              <Square size={11} fill="currentColor" />
              Stop
            </button>
            <button
              className="btn btn-rebuild"
              disabled={actionLoading || !systemStatus.docker_installed}
              onClick={() => handleAction('rebuild')}
            >
              <RefreshCw size={11} className={actionLoading ? 'spin' : ''} />
              Rebuild
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px' }}>

          {!systemStatus.docker_installed ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', paddingBottom: '10vh' }}>
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 12, padding: '40px', maxWidth: 480, textAlign: 'center' }}>
                <AlertTriangle size={48} color="var(--danger)" style={{ margin: '0 auto 20px' }} />
                <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12, marginTop: 0 }}>Docker Desktop Required</h2>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.5 }}>
                  Reclip Control relies on Docker containers to run its backend services securely. Docker Desktop must be installed and running on this machine to continue.
                </p>
                <a
                  href="https://www.docker.com/products/docker-desktop/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-start"
                  style={{ padding: '10px 20px', fontSize: 13, display: 'inline-flex' }}
                >
                  <DownloadCloud size={14} />
                  Download Docker Desktop
                </a>
              </div>
            </div>
          ) : (
            <>

          {/* ── Tunnel URL banner — BUG-008 FIX: only shown on Utilization tab ── */}
          {activeTab === 'utilization' && systemStatus.tunnel_url && (
            <div className="tunnel-banner">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div className="tunnel-live-dot">
                  <span className="ping" />
                  <span />
                </div>
                <div>
                  <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 2 }}>
                    Live Cloudflare Tunnel
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {systemStatus.tunnel_url}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <a
                  href={systemStatus.tunnel_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: 'flex', padding: 6, borderRadius: 5, color: 'var(--accent)', transition: 'background 0.15s' }}
                  onMouseOver={e => e.currentTarget.style.background = 'var(--accent-subtle)'}
                  onMouseOut={e => e.currentTarget.style.background = 'transparent'}
                >
                  <ExternalLink size={14} />
                </a>
                <button
                  onClick={() => copyToClipboard(systemStatus.tunnel_url)}
                  className="btn btn-start"
                  style={{ padding: '5px 10px' }}
                >
                  {copied ? <Check size={11} /> : <Copy size={11} />}
                  {copied ? 'Copied!' : 'Copy URL'}
                </button>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════ */}
          {/*  UTILIZATION TAB                                  */}
          {/* ══════════════════════════════════════════════════ */}
          {activeTab === 'utilization' && (
            <div>
              {!isOnline ? (
                <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '40px', textAlign: 'center', marginTop: 20 }}>
                  <Server size={40} color="var(--text-muted)" style={{ margin: '0 auto 16px' }} />
                  <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, marginTop: 0 }}>Server is Offline</h2>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, maxWidth: 400, margin: '0 auto' }}>
                    Click below to boot the server containers. If this is your first time, it may take a few minutes to download the base images.
                  </p>
                  
                  {actionLoading ? (
                    <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 16, textAlign: 'left', height: 250, display: 'flex', flexDirection: 'column', marginTop: 24 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                        <RefreshCw size={14} className="spin" color="var(--accent)" />
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)' }}>Building & Starting (First boot may take 2-5 minutes...)</span>
                      </div>
                      <pre className="terminal-output" style={{ flex: 1, overflowY: 'auto' }}>
                        {logs.trim() === 'No logs available.' ? 'Downloading base images and building containers...\\nPlease wait, this process takes a few minutes.' : logs}
                      </pre>
                    </div>
                  ) : (
                    <button
                      className="btn btn-start"
                      onClick={() => handleAction('start')}
                      style={{ padding: '10px 24px', fontSize: 13 }}
                    >
                      <Play size={14} fill="currentColor" />
                      Set up & Start Server
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {/* Section heading: APPLICATION USAGE */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <span className="label-caps">Application Usage</span>
                <span style={{ fontSize: 9, color: 'var(--text-muted)', background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 3, padding: '1px 5px' }}>i</span>
              </div>

              {/* 3-column capacity cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
                <CapacityCard
                  icon={Activity}
                  label="Total Requests"
                  value={usageStats.total_requests.toString()}
                  usedPct={100}
                  quotaPct={100}
                  meta={['Total Hits', 'All Platforms']}
                />
                <CapacityCard
                  icon={Check}
                  label="Successful"
                  value={usageStats.successful_requests.toString()}
                  usedPct={usageStats.total_requests > 0 ? (usageStats.successful_requests / usageStats.total_requests) * 100 : 0}
                  quotaPct={100}
                  meta={['Resolved', 'Direct URLs']}
                />
                <CapacityCard
                  icon={AlertTriangle}
                  label="Failed"
                  variant="danger"
                  value={usageStats.failed_requests.toString()}
                  usedPct={usageStats.total_requests > 0 ? (usageStats.failed_requests / usageStats.total_requests) * 100 : 0}
                  quotaPct={100}
                  meta={['Errors', 'Timeouts']}
                />
              </div>

              {/* Summary | Metrics tab bar */}
              <div className="tab-bar">
                <button
                  className={`tab-btn${activeView === 'summary' ? ' active' : ''}`}
                  onClick={() => setActiveView('summary')}
                >
                  Summary
                </button>
                <button
                  className={`tab-btn${activeView === 'metrics' ? ' active' : ''}`}
                  onClick={() => setActiveView('metrics')}
                >
                  Metrics
                </button>
              </div>

              {/* Metrics control bar */}
              <div className="metrics-bar">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '5px 10px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 5, fontSize: 11, color: 'var(--text-secondary)', cursor: 'default'
                  }}>
                    All Containers <ChevronDown size={11} style={{ marginLeft: 2 }} />
                  </div>
                </div>
                <div className="updated" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Updated {timeStr}</span>
                  {/* BUG-004 FIX: Refresh button now actually triggers a re-fetch */}
                  <button
                    onClick={handleManualRefresh}
                    title="Refresh now"
                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 4, padding: '4px 6px', cursor: 'pointer', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}
                  >
                    <RotateCcw size={12} className={actionLoading ? 'spin' : ''} />
                  </button>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    padding: '4px 8px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 5, fontSize: 11, color: 'var(--text-secondary)', cursor: 'default'
                  }}>
                    <Clock size={11} />
                    Last 7 days <ChevronDown size={10} style={{ marginLeft: 2 }} />
                  </div>
                </div>
              </div>

              {/* BUG-007 FIX: Summary shows container table; Metrics shows stats breakdown */}
              {activeView === 'summary' && (
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, overflow: 'hidden' }}>
                {/* Table header row */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 1fr 2fr 1fr 1fr',
                  padding: '10px 16px',
                  background: 'var(--bg-header)',
                  borderBottom: '1px solid var(--border-subtle)'
                }}>
                  {['Container', 'Service', 'Status', 'CPU %', 'Memory'].map(h => (
                    <span key={h} className="label-caps">{h}</span>
                  ))}
                </div>

                {systemStatus.containers.length === 0 ? (
                  <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                    No containers are running.{' '}
                    <span
                      style={{ color: 'var(--accent)', cursor: 'pointer' }}
                      onClick={() => handleAction('start')}
                    >
                      Click Start to boot the server stack.
                    </span>
                  </div>
                ) : (
                  systemStatus.containers.map((container, idx) => {
                    const stat = systemStats.containers.find(s =>
                      s.name.includes(container.service) || container.name.includes(s.name)
                    );
                    // BUG-015 frontend side: check both 'running' (JSON) and 'up' (text)
                    const statusLow = container.status?.toLowerCase() || '';
                    const isUp = statusLow === 'running' || statusLow.startsWith('up');
                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '2fr 1fr 2fr 1fr 1fr',
                          padding: '12px 16px',
                          borderBottom: idx < systemStatus.containers.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                          alignItems: 'center',
                          transition: 'background 0.12s',
                        }}
                        onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                        onMouseOut={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                          {container.name}
                        </span>
                        <span style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                          {container.service}
                        </span>
                        <span>
                          <span className={isUp ? 'badge-up' : 'badge-down'}>
                            <span className={`status-dot${isUp ? ' online' : ''}`}>
                              {container.status}
                            </span>
                          </span>
                        </span>
                        <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)', fontWeight: 600 }}>
                          {stat ? stat.cpu : '0.0%'}
                        </span>
                        <span style={{ fontSize: 11.5, color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
                          {stat ? stat.memory_usage : '0B / 0B'}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
              )}

              {/* Metrics view — shows application request breakdown */}
              {activeView === 'metrics' && (
                <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '28px 24px' }}>
                  <div className="label-caps" style={{ marginBottom: 16 }}>Requests by Platform</div>
                  {Object.entries(usageStats.platforms || {}).map(([platform, count], i) => {
                    const total = usageStats.total_requests || 1;
                    const pct = (count / total) * 100;
                    return (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                        <span style={{ fontSize: 12, textTransform: 'capitalize', color: 'var(--text-secondary)', minWidth: 100 }}>{platform}</span>
                        <div style={{ flex: 1, height: 8, background: 'var(--bg-elevated)', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent)', borderRadius: 4, transition: 'width 0.6s ease' }} />
                        </div>
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: 'var(--text-primary)', minWidth: 48, textAlign: 'right' }}>{count}</span>
                      </div>
                    );
                  })}
                  {Object.keys(usageStats.platforms || {}).length === 0 && (
                    <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No requests recorded yet.</div>
                  )}
                </div>
              )}
                </>
              )}
            </div>
          )}

          {/* ══════════════════════════════════════════════════ */}
          {/*  LOGS TAB                                         */}
          {/* ══════════════════════════════════════════════════ */}
          {activeTab === 'logs' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div className="log-filter-bar">
                {['', 'reclip-api', 'cobalt-api', 'cloudflare-tunnel'].map(svc => (
                  <button
                    key={svc}
                    onClick={() => setSelectedLogService(svc)}
                    className={`log-filter-btn${selectedLogService === svc ? ' active' : ''}`}
                  >
                    {svc === '' ? 'All Logs' : svc}
                  </button>
                ))}
              </div>

              <div style={{
                flex: 1,
                background: 'var(--bg-base)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 8,
                padding: '16px',
                overflowY: 'auto',
                minHeight: 400,
                userSelect: 'text'
              }}>
                <pre className="terminal-output">{logs}</pre>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════ */}
          {/*  DOCS TAB                                         */}
          {/* ══════════════════════════════════════════════════ */}
          {activeTab === 'docs' && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '24px' }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 20, marginTop: 0 }}>
                API Documentation
              </h2>

              {[
                {
                  method: 'GET',
                  path: '/api/download',
                  desc: 'Direct download media resolver. Streams the media file back as a response.',
                  code: '?url=https://www.youtube.com/watch?v=...'
                },
                {
                  method: 'POST',
                  path: '/api/cobalt',
                  desc: 'Proxy to the Cobalt Node.js API with custom cookie fallbacks. Returns JSON with direct link URLs.',
                  code: '{ "url": "https://instagram.com/reel/..." }'
                },
                {
                  method: 'GET',
                  path: '/api/cookie-files',
                  desc: 'List all matching cookie .txt files currently loaded in the Flask root directories.',
                  code: null
                }
              ].map((ep, i, arr) => (
                <div key={ep.path} style={{ paddingBottom: 18, marginBottom: 18, borderBottom: i < arr.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span className={ep.method === 'GET' ? 'method-get' : 'method-post'}>{ep.method}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {ep.path}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: ep.code ? 8 : 0, marginTop: 0 }}>
                    {ep.desc}
                  </p>
                  {ep.code && <div className="api-code">{ep.code}</div>}
                </div>
              ))}
            </div>
          )}

          {/* ══════════════════════════════════════════════════ */}
          {/*  SETTINGS TAB                                     */}
          {/* ══════════════════════════════════════════════════ */}
          {activeTab === 'settings' && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '24px' }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 20, marginTop: 0 }}>
                Server Settings
              </h2>

              {/* Cookies section — BUG-006 FIX: real status from server */}
              <div style={{ marginBottom: 24 }}>
                <div className="label-caps" style={{ marginBottom: 6 }}>Service Cookies Setup</div>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12, marginTop: 0 }}>
                  To bypass download blocks (e.g. YouTube bot detection), copy your cookie values into your{' '}
                  <code style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--accent)', fontSize: 11 }}>.env</code>{' '}
                  file as single strings with escaped tabs and newlines.
                </p>

                <div style={{
                  background: 'var(--bg-base)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 6,
                  padding: '14px 16px'
                }}>
                  {[
                    'YOUTUBE_COOKIES',
                    'INSTAGRAM_COOKIES',
                    'TWITTER_COOKIES',
                    'TIKTOK_COOKIES'
                  ].map((key, i, arr) => {
                    const svcName = key.replace('_COOKIES', '');
                    const isConfigured = !!cookieStatus[key];
                    const isExpanded = expandedCookie === key;
                    return (
                      <div key={key} style={{
                        paddingBottom: i < arr.length - 1 ? 12 : 0,
                        marginBottom: i < arr.length - 1 ? 12 : 0,
                        borderBottom: i < arr.length - 1 ? '1px solid var(--border-subtle)' : 'none'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color: 'var(--text-primary)' }}>
                            {svcName}
                          </span>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            {isConfigured ? (
                              <>
                                <span style={{
                                  fontSize: 11,
                                  color: 'var(--accent)',
                                  background: 'var(--accent-subtle)',
                                  padding: '2px 8px', borderRadius: 4,
                                  border: '1px solid rgba(0,242,153,0.2)'
                                }}>
                                  ✓ Configured
                                </span>
                                <button
                                  onClick={() => handleClearCookie(svcName)}
                                  className="btn"
                                  style={{ padding: '2px 8px', fontSize: 11, background: 'var(--danger-subtle)', color: 'var(--danger)', border: '1px solid rgba(255, 60, 60, 0.2)' }}
                                >
                                  Clear
                                </button>
                              </>
                            ) : (
                              <>
                                <span style={{
                                  fontSize: 11,
                                  color: 'var(--text-muted)',
                                  background: 'var(--bg-elevated)',
                                  padding: '2px 8px', borderRadius: 4,
                                  border: '1px solid var(--border-subtle)'
                                }}>
                                  Not Set
                                </span>
                                <button
                                  onClick={() => setExpandedCookie(isExpanded ? null : key)}
                                  className="btn btn-start"
                                  style={{ padding: '2px 8px', fontSize: 11 }}
                                >
                                  {isExpanded ? 'Cancel' : 'Setup'}
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                        {isExpanded && !isConfigured && (
                          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                            <textarea
                              placeholder={`Paste raw HTTP Cookie header or Netscape cookies for ${svcName}...`}
                              style={{
                                width: '100%',
                                height: 80,
                                padding: '8px 12px',
                                background: 'var(--bg-card)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: 6,
                                color: 'var(--text-primary)',
                                fontFamily: "'JetBrains Mono', monospace",
                                fontSize: 11,
                                resize: 'vertical'
                              }}
                              value={cookieInputs[key] || ''}
                              onChange={e => setCookieInputs(prev => ({...prev, [key]: e.target.value}))}
                            />
                            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                              <button
                                onClick={() => handleSaveCookie(svcName)}
                                className="btn btn-start"
                                style={{ padding: '4px 16px', fontSize: 11 }}
                                disabled={!cookieInputs[key]}
                              >
                                Save
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Cloudflare section */}
              <div style={{ paddingTop: 20, borderTop: '1px solid var(--border-subtle)' }}>
                <div className="label-caps" style={{ marginBottom: 6 }}>Cloudflare Quick Tunnel Status</div>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>
                  Every time the tunnel is restarted, Cloudflare generates a random public hostname on{' '}
                  <code style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--accent)', fontSize: 11 }}>trycloudflare.com</code>.
                  This is 100% free and secure — no dynamic DNS or port forwarding required.
                </p>

                {/* Live status pill */}
                <div style={{ marginTop: 12, display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 12px', background: 'var(--bg-base)', border: '1px solid var(--border-subtle)', borderRadius: 6 }}>
                  <span className={`status-dot${isOnline ? ' online' : ''}`} style={{ fontSize: 12, color: isOnline ? 'var(--accent)' : 'var(--text-muted)' }}>
                    Tunnel {isOnline ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
          )}

            </>
          )}

        </div>{/* end scrollable */}
      </div>{/* end main */}
    </div>
  );
}
