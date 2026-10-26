import { useCallback, useEffect, useState } from 'react';
import { api, dateLabel, publicDemo } from './api';
import { ClaimView, Empty, EvidenceDrawer, HandoffDialog, PRBoard, Warnings, prCategories } from './components';
import { Connections, Sessions, SettingsPanel } from './Panels';
import Icon from './Icon';
import type { Briefing, Evidence, Health, Job, Overview, Repository, Settings, WindowChoice } from './types';

const pages = [
  { id: 'overview', label: 'Overview', icon: 'home' },
  { id: 'briefing', label: 'Your briefing', icon: 'brief' },
  { id: 'prs', label: 'Pull requests', icon: 'branch' },
  { id: 'sessions', label: 'Agent sessions', icon: 'session' },
  { id: 'history', label: 'Briefing history', icon: 'history' },
] as const;
type Page = typeof pages[number]['id'] | 'connections' | 'settings';
const titles: Record<Page, { eyebrow: string; title: string; description: string }> = {
  overview: { eyebrow: 'WELCOME BACK', title: 'Pick up the thread.', description: 'One repository. The context you need. A clear place to continue.' },
  briefing: { eyebrow: 'YOUR CONTEXT, RESTORED', title: 'Here’s where you left off.', description: 'A grounded account of your work, with the sources a click away.' },
  prs: { eyebrow: 'WHILE YOU WERE AWAY', title: 'Follow your work forward.', description: 'The authoritative state of your pull requests, from GitHub’s last sync.' },
  sessions: { eyebrow: 'THE CONVERSATION SO FAR', title: 'Keep the useful parts.', description: 'Bring forward the decisions, constraints, and unfinished questions.' },
  history: { eyebrow: 'A RECORD OF YOUR RETURNS', title: 'Context worth keeping.', description: 'Each briefing is a snapshot. Only you decide when to acknowledge it.' },
  connections: { eyebrow: 'MAKE YOURSELF AT HOME', title: 'A little setup. A lot of context.', description: 'Connect the tools already on your computer, or explore a synthetic demo.' },
  settings: { eyebrow: 'LOCAL, BY DESIGN', title: 'Your workspace. Your choices.', description: 'Control the model, collected context, and the data you keep.' },
};

export default function App() {
  const [page, setPage] = useState<Page>('overview');
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [repoId, setRepoId] = useState('');
  const [overview, setOverview] = useState<Overview | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [settings, setSettings] = useState<Settings>({ model: '', exclusions: [] });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [windowChoice, setWindowChoice] = useState<WindowChoice>('24h');
  const [since, setSince] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [historical, setHistorical] = useState<Briefing | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const repository = repositories.find(repo => repo.id === repoId) || null;
  const briefing = historical || overview?.briefing || null;
  const snapshot = overview?.snapshot;
  const github = snapshot?.github;
  const activeJob = job?.status === 'queued' || job?.status === 'running';

  const loadOverview = useCallback(async () => {
    if (!repoId) return;
    const result = await api<Overview>(`/repos/${repoId}/overview`);
    setOverview(result);
    setRepositories(current => current.map(repo => repo.id === repoId ? result.repository : repo));
    const pending = result.jobs.find(item => item.status === 'running' || item.status === 'queued');
    if (pending) setJob(pending);
  }, [repoId]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api<Repository[]>('/repos', 'GET', undefined, controller.signal), api<Settings>('/settings', 'GET', undefined, controller.signal), api<Health>('/health', 'GET', undefined, controller.signal)])
      .then(([repos, preferences, connections]) => {
        setRepositories(repos); setSettings(preferences); setHealth(connections);
        const remembered = localStorage.getItem('away-repository');
        setRepoId(repos.find(repo => repo.id === remembered)?.id || repos[0]?.id || '');
        if (!repos.length) setPage('connections');
      }).catch(reason => { if (!controller.signal.aborted) { setError(reason instanceof Error ? reason.message : 'The local server is unavailable.'); setPage('connections'); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    setOverview(null); setHistorical(null); setJob(null); setEvidence(null); setHandoffOpen(false);
    if (!repoId) return;
    localStorage.setItem('away-repository', repoId);
    setLoading(true);
    const controller = new AbortController();
    api<Overview>(`/repos/${repoId}/overview`, 'GET', undefined, controller.signal).then(result => {
      setOverview(result); setWindowChoice(result.repository.acknowledged_snapshot_id ? 'acknowledged' : '24h');
      setJob(result.jobs.find(item => item.status === 'running' || item.status === 'queued') || null);
    }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Unable to read repository.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [repoId]);

  useEffect(() => {
    if (!activeJob || !job) return;
    let cancelled = false;
    const timeout = window.setTimeout(async () => {
      try {
        const next = await api<Job>(`/jobs/${job.id}`);
        if (cancelled) return;
        setJob(next);
        if (next.status === 'completed') { await loadOverview(); setHistorical(null); setPage('briefing'); setNotice('Your briefing is ready. Your acknowledged checkpoint has not changed.'); }
        if (next.status === 'failed') setError(next.error || 'Inference failed. Your previous briefing is still available.');
      } catch (reason) { if (!cancelled) { setError(reason instanceof Error ? reason.message : 'Unable to check progress.'); setJob(null); } }
    }, 1200);
    return () => { cancelled = true; window.clearTimeout(timeout); };
  }, [activeJob, job, loadOverview]);

  async function run(label: string, task: () => Promise<void>) {
    setBusy(label); setError(''); setNotice('');
    try { await task(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Something went wrong. Please try again.'); }
    finally { setBusy(''); }
  }
  function timeWindow() {
    if (windowChoice === 'custom') {
      if (!since || Number.isNaN(new Date(since).valueOf())) throw new Error('Choose a valid custom start date.');
      if (new Date(since).valueOf() > Date.now()) throw new Error('The start date must be in the past.');
      return { window: windowChoice, since: new Date(since).toISOString() };
    }
    return { window: windowChoice };
  }
  function generate() { void run('Collecting context…', async () => { const next = await api<Job>(`/repos/${repoId}/briefings`, 'POST', { ...timeWindow(), ...(settings.model ? { model: settings.model } : {}) }); setJob(next); setHistorical(null); setPage('briefing'); }); }
  function navigate(next: Page) { setPage(next); if (next !== 'briefing') setHistorical(null); }
  async function selectRepository(repo: Repository) { setRepositories(current => [...current.filter(item => item.id !== repo.id), repo]); setRepoId(repo.id); setPage('overview'); setNotice(repo.demo ? 'Synthetic demo loaded. No live integration or model was used.' : 'Repository connected. Collect a snapshot, import relevant sessions, then generate your first briefing.'); }
  const allEvidence = [...(briefing?.evidence || []), ...(snapshot?.evidence || []), ...(github?.evidence || []), ...(snapshot?.git.evidence || [])];
  const nextStep = briefing?.sections.find(section => section.key === 'next_step');
  const remainingSections = briefing?.sections.filter(section => section.key !== 'next_step') || [];

  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to content</a><aside className="sidebar"><a className="brand" href="#" onClick={event => { event.preventDefault(); navigate(repoId ? 'overview' : 'connections'); }} aria-label="While I Was Away home"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span>while i<br /><strong>was away.</strong></span></a><p className="brand-note">GOOD WORK CAN WAIT.</p>
      <div className="repo-switch"><label htmlFor="repository-select">YOUR WORKSPACE</label><select id="repository-select" value={repoId} onChange={event => { setRepoId(event.target.value); setPage('overview'); }} disabled={!!busy}><option value="" disabled>Select a repository</option>{repositories.map(repo => <option key={repo.id} value={repo.id}>{repo.demo ? '◇ ' : ''}{repo.name}{repo.demo ? ' · demo' : ''}</option>)}</select><button className="add-repo" onClick={() => navigate('connections')}><Icon name="plus" size={13} />Add a repository</button></div>
      <nav aria-label="Main navigation">{pages.map(item => <button key={item.id} className={`nav-link ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined} disabled={!repoId} onClick={() => navigate(item.id)}><Icon name={item.icon} /><span>{item.label}</span>{item.id === 'sessions' && !!overview?.sessions.length && <span className="nav-count">{overview.sessions.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><button className={`nav-link ${page === 'connections' ? 'active' : ''}`} onClick={() => navigate('connections')}><Icon name="shield" />Connections<span className={`tiny-dot ${health?.git.ok && health.ollama.ok ? 'ok' : ''}`} /></button><button className={`nav-link ${page === 'settings' ? 'active' : ''}`} disabled={publicDemo} title={publicDemo ? 'Available in the local app' : undefined} onClick={() => navigate('settings')}><Icon name="settings" />Settings</button><div className="local-footer"><span className="local-light" /><div>{publicDemo ? 'Public synthetic preview' : 'Local to this computer'}<span>{publicDemo ? 'Precomputed. No live inference.' : 'No telemetry. Your pace.'}</span></div></div></div>
    </aside><div className="workspace"><header className="topbar"><div className="breadcrumb"><span>Workspace</span><span>/</span><strong>{repository?.name || 'Getting started'}</strong>{repository?.demo && <span className="pill demo-pill">SYNTHETIC DEMO</span>}</div><div className="topbar-right"><span className="local-tag"><Icon name="shield" size={14} />{publicDemo ? 'Public preview' : 'Local first'}</span>{snapshot && <span className="snapshot-label">Snapshot {dateLabel(snapshot.created_at)}</span>}</div></header>
      <main id="main-content" tabIndex={-1}><div className="page-heading"><div><div className="eyebrow">{titles[page].eyebrow}</div><h1>{titles[page].title}</h1><p>{titles[page].description}</p></div>{(page === 'overview' || page === 'briefing') && repository && <button className="button primary" disabled={!!busy || activeJob || (!repository.demo && !settings.model)} onClick={generate}><Icon name="refresh" size={16} />{publicDemo ? 'Replay demo briefing' : briefing ? 'Refresh briefing' : 'Generate briefing'}</button>}</div>
        {error && <div className="alert error" role="alert"><div><strong>We couldn’t finish that.</strong><p>{error}</p></div><button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><Icon name="close" /></button></div>}
        {notice && <div className="alert notice" role="status"><Icon name="check" /><p>{notice}</p><button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><Icon name="close" /></button></div>}
        {busy && <p className="busy-line" role="status"><span className="spinner" />{busy}</p>}
        {repository?.demo && <div className="demo-ribbon"><span className="demo-symbol">◇</span><p><strong>{publicDemo ? 'Public demo • precomputed synthetic results • no live inference.' : 'A synthetic workspace, with real interactions.'}</strong> {publicDemo ? 'Explore in your browser. Install the local app to connect real repositories and models.' : 'These illustrative records are not live GitHub activity or model output.'}</p></div>}
        {(page === 'overview' || page === 'briefing') && repository && <div className="context-toolbar"><div className="window-picker"><Icon name="clock" size={16} /><label htmlFor="window">Look back</label><select id="window" value={windowChoice} onChange={event => setWindowChoice(event.target.value as WindowChoice)}><option value="24h">24 hours</option><option value="7d">7 days</option><option value="custom">Custom date</option><option value="acknowledged" disabled={!repository.acknowledged_snapshot_id}>Since acknowledged briefing</option></select>{windowChoice === 'custom' && <input aria-label="Custom start date" type="datetime-local" value={since} onChange={event => setSince(event.target.value)} />}</div><div className="model-label"><span className={`health-dot ${repository.demo || health?.ollama.ok ? 'ok' : 'unavailable'}`} />{repository.demo ? 'Demo synthesis' : settings.model || 'Choose a model in Settings'}</div></div>}
        {activeJob && job && <div className="job-progress" role="status"><div><span className="spinner" /><strong>{job.stage || 'Preparing your briefing'}</strong><span className="small">{job.status} · attempt {job.attempts}</span><button className="text-button" onClick={() => void run('Cancelling…', async () => { setJob(await api<Job>(`/jobs/${job.id}/cancel`, 'POST', {})); setNotice('Briefing cancelled. Your checkpoint and previous briefing are unchanged.'); })}>Cancel</button></div><progress max="100" value={job.progress <= 1 ? job.progress * 100 : job.progress} aria-label="Briefing progress" /></div>}
        {job?.status === 'cancelled' && <div className="inline-notice">Generation was cancelled. You can start again when you’re ready.</div>}
        {loading ? <div className="loading-state" role="status"><span className="spinner" /><p>Finding your place…</p></div> : <>
          {page === 'connections' && <Connections health={health} repositories={repositories} busy={!!busy} addRepository={path => void run('Connecting repository…', async () => { await selectRepository(await api<Repository>('/repos', 'POST', { path })); })} openDemo={() => void run('Opening synthetic demo…', async () => { await selectRepository(await api<Repository>('/demo', 'POST', {})); })} refreshHealth={() => void run('Checking local connections…', async () => setHealth(await api<Health>('/health')))} />}
          {page === 'settings' && <SettingsPanel key={`${settings.model}-${settings.exclusions.join()}-${repoId}`} settings={settings} health={health} repository={repository} busy={!!busy} save={value => void run('Saving settings…', async () => { setSettings(await api<Settings>('/settings', 'PUT', value)); setNotice('Settings saved. Future briefings use this model and these exclusions.'); })} removeRepository={() => void run('Removing local repository data…', async () => { await api(`/repos/${repoId}`, 'DELETE', {}); const remaining = repositories.filter(repo => repo.id !== repoId); setRepositories(remaining); setRepoId(remaining[0]?.id || ''); setPage('connections'); })} deleteAll={() => void run('Deleting local app data…', async () => { await api('/data', 'DELETE', { confirm: 'DELETE' }); setRepositories([]); setRepoId(''); setOverview(null); setSettings(await api<Settings>('/settings')); localStorage.removeItem('away-repository'); setPage('connections'); setNotice('All app data deleted. Original repositories and transcript files were not changed.'); })} />}
          {(page === 'overview' || page === 'briefing') && repository && <>
            {historical && <div className="inline-notice">Viewing a historical briefing from {dateLabel(historical.created_at)}. <button className="text-button" onClick={() => setHistorical(null)}>Return to latest</button></div>}
            <div className="briefing-layout"><div className="briefing-main">{briefing ? <>
              <section className="next-step-card"><div className="next-heading"><span className="eyebrow">YOUR NEXT STEP</span><span className="next-symbol" aria-hidden="true">↗</span></div><h2>A good place to begin.</h2>{nextStep?.claims.length ? nextStep.claims.map((claim, index) => <ClaimView key={index} claim={claim} evidence={briefing.evidence} onEvidence={setEvidence} />) : <p>No supported next step was generated. Review the evidence below.</p>}<div className="next-footer"><button className="button light" onClick={() => setHandoffOpen(true)}>Continue with your agent <Icon name="arrow" size={16} /></button><span>Review the handoff first</span></div></section>
              <section className="card briefing-card"><div className="section-heading"><h2>{page === 'overview' ? 'The short version' : 'Your briefing'}</h2><span className="small muted">{dateLabel(briefing.created_at)}</span></div>{remainingSections.map((section, index) => <section className="briefing-section" key={section.key}><div className="section-number">{String(index + 1).padStart(2, '0')}</div><div><h3>{section.title}</h3>{section.claims.map((claim, claimIndex) => <ClaimView key={claimIndex} claim={claim} evidence={briefing.evidence} onEvidence={setEvidence} />)}</div></section>)}<Warnings items={briefing.warnings} /><div className="briefing-footer"><span><Icon name="shield" size={14} />{briefing.demo ? 'Synthetic demonstration' : `Synthesized locally · ${briefing.model}`}</span><span>{briefing.evidence.length} source records</span></div></section>
              <section className="checkpoint-card"><Icon name="check" size={24} /><div><h3>{repository.acknowledged_snapshot_id === briefing.snapshot_id ? 'You’ve acknowledged this snapshot.' : 'Caught up? Mark your place.'}</h3><p>Generating a briefing never moves your checkpoint. Acknowledge it when you’re ready to use this moment as your next starting point.</p></div><button className="button secondary" disabled={!!busy || repository.acknowledged_snapshot_id === briefing.snapshot_id} onClick={() => void run('Saving your checkpoint…', async () => { const updated = await api<Repository>(`/briefings/${briefing.id}/acknowledge`, 'POST', {}); setRepositories(current => current.map(repo => repo.id === updated.id ? updated : repo)); setWindowChoice('acknowledged'); setNotice('Checkpoint saved. Future briefings can look back from this snapshot.'); })}>{repository.acknowledged_snapshot_id === briefing.snapshot_id ? 'Acknowledged' : 'Acknowledge briefing'}</button></section>
            </> : <section className="card"><Empty title="Your first return starts here."><p>Collect a local snapshot, sync GitHub if you’re online, and bring in a relevant agent session. Then generate your first briefing.</p><button className="button primary" disabled={!!busy || activeJob || !settings.model} onClick={generate}>Generate briefing <Icon name="arrow" /></button>{!settings.model && <p className="small">Choose an installed model in Settings first.</p>}</Empty></section>}
            </div><aside className="context-rail"><section className="card repo-context"><div className="section-heading"><span className="eyebrow">{publicDemo ? 'SYNTHETIC WORKING TREE' : 'ON YOUR MACHINE'}</span><Icon name="branch" size={17} /></div><h3>{snapshot?.git.branch || (snapshot?.git.head ? 'Detached HEAD' : 'No branch collected')}</h3><p className="source-path">{repository.path}</p>{snapshot && <><div className="head-line"><code>{snapshot.git.head?.slice(0, 10) || 'No commits yet'}</code><span>{snapshot.git.upstream || 'No upstream'}</span></div><div className="file-stats"><div><strong>{snapshot.git.staged.length}</strong><span>staged</span></div><div><strong>{snapshot.git.unstaged.length}</strong><span>unstaged</span></div><div><strong>{snapshot.git.untracked.length}</strong><span>untracked</span></div></div><details className="files-detail"><summary>Inspect working context</summary>{(['staged', 'unstaged', 'untracked'] as const).map(kind => <div key={kind}><h4>{kind}</h4>{snapshot.git[kind].length ? <ul>{snapshot.git[kind].map(file => <li key={file}><code>{file}</code></li>)}</ul> : <p className="small muted">None</p>}</div>)}<h4>Worktrees</h4>{snapshot.git.worktrees.map(tree => <p className="source-path" key={tree.path}>{tree.path} · {tree.branch || 'detached'}</p>)}{snapshot.git.base_branch && <p className="small">Base: {snapshot.git.base_branch} · {snapshot.git.base_changes.length} changed files since snapshot</p>}</details></>}
              <button className="text-button" disabled={!!busy || activeJob || publicDemo} onClick={() => void run('Reading local Git context…', async () => { await api(`/repos/${repoId}/collect`, 'POST', timeWindow()); await loadOverview(); setNotice('Local snapshot collected. GitHub cache and acknowledged checkpoint are unchanged.'); })}>Collect local snapshot <Icon name="refresh" size={13} /></button></section>
              <section className="card pr-summary"><div className="section-heading"><span className="eyebrow">YOUR PULL REQUESTS</span><Icon name="branch" size={17} /></div>{prCategories.map(category => <button key={category.state} onClick={() => navigate('prs')}><span><i className={`state-dot ${category.state}`} />{category.label}</span><strong>{github?.prs.filter(pr => pr.state === category.state).length ?? '—'}</strong></button>)}<p className="small muted">{publicDemo ? 'Illustrative PR states · no live sync' : github?.offline ? 'Offline · cached information' : github?.synced_at ? `Synced ${dateLabel(github.synced_at)}` : 'Not synced with GitHub'}</p><button className="text-button" disabled={!!busy || publicDemo} onClick={() => void run('Syncing with GitHub…', async () => { await api(`/repos/${repoId}/sync`, 'POST', {}); await loadOverview(); })}>Sync GitHub now <Icon name="refresh" size={13} /></button></section>
              <section className="card"><span className="eyebrow">CONVERSATION CONTEXT</span><h3>{overview?.sessions.length || 0} imported {overview?.sessions.length === 1 ? 'session' : 'sessions'}</h3><p className="small muted">Only the conversations you selected. Historical test results remain historical.</p><button className="text-button" onClick={() => navigate('sessions')}>Manage agent sessions <Icon name="arrow" size={14} /></button></section>
              {snapshot && <Warnings items={[...snapshot.warnings, ...snapshot.git.warnings]} />}
            </aside></div>
            {page === 'briefing' && briefing && <section className="evidence-index"><div className="section-heading"><div><span className="eyebrow">NOT JUST A SUMMARY</span><h2>Follow the evidence.</h2></div><span className="small muted">{briefing.evidence.length} records in this briefing</span></div><div className="evidence-grid">{briefing.evidence.map(item => <button className="evidence-tile" key={item.id} onClick={() => setEvidence(item)}><Icon name={item.kind.includes('session') ? 'session' : 'file'} /><span><strong>{item.title}</strong><small>{item.trust} · {item.kind}</small></span><Icon name="arrow" size={16} /></button>)}</div></section>}
          </>}
          {page === 'prs' && repository && <><div className="page-actions"><button className="button secondary" disabled={!!busy || publicDemo} onClick={() => void run('Syncing with GitHub…', async () => { await api(`/repos/${repoId}/sync`, 'POST', {}); await loadOverview(); })}><Icon name="refresh" size={15} />Sync GitHub now</button><button className="button ghost" disabled={!!busy || repository.demo || publicDemo} onClick={() => void run('Fetching remote Git refs…', async () => { const result = await api<{ message: string }>(`/repos/${repoId}/fetch`, 'POST', {}); setNotice(result.message); })}>Fetch remote Git refs</button><span className="small muted">{publicDemo ? 'Live integrations are available in the local app.' : 'These actions contact remotes explicitly.'}</span></div><PRBoard github={github} evidence={allEvidence} onEvidence={setEvidence} /></>}
          {page === 'sessions' && repository && <Sessions key={repoId} repository={repository} sessions={overview?.sessions || []} onChanged={loadOverview} onEvidence={setEvidence} />}
          {page === 'history' && <>{overview?.history.length ? <div className="history-list">{overview.history.map(item => <button className="history-row" key={item.id} onClick={() => { setHistorical(item); setPage('briefing'); }}><span className="history-icon"><Icon name="brief" /></span><span><strong>{dateLabel(item.created_at)}</strong><small>{item.demo ? 'Synthetic demo' : item.model} · {item.evidence.length} evidence records</small></span>{repository?.acknowledged_snapshot_id === item.snapshot_id && <span className="pill green">Acknowledged checkpoint</span>}<Icon name="arrow" /></button>)}</div> : <Empty title="Your next return is the first chapter.">Generated briefings will appear here, with their evidence and original timestamps.</Empty>}</>}
        </>}
        <footer className="page-footer"><span>Close your laptop. Lose the context. Get it back in one briefing.</span><span>While I Was Away <span className="footer-dot">·</span> {health?.version || 'local'}</span></footer>
      </main>
    </div><EvidenceDrawer evidence={evidence} close={() => setEvidence(null)} /><HandoffDialog briefing={handoffOpen ? briefing : null} close={() => setHandoffOpen(false)} onSaved={text => { if (historical) setHistorical({ ...historical, handoff: text }); else if (overview?.briefing) setOverview({ ...overview, briefing: { ...overview.briefing, handoff: text } }); }} /></div>;
}
