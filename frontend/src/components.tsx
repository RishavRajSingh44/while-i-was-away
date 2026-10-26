import { useEffect, useRef, useState } from 'react';
import { api, dateLabel, externalUrl, exportHandoff, publicDemo } from './api';
import Icon from './Icon';
import type { Briefing, Claim, Evidence, GitHub, PR } from './types';

export function Empty({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="empty"><span className="empty-icon"><Icon name="brief" size={25} /></span><h3>{title}</h3><div>{children}</div></div>;
}

export function Warnings({ items }: { items: string[] }) {
  return items.length > 0 ? <details className="warnings"><summary>{items.length} collection {items.length === 1 ? 'note' : 'notes'} · review limitations</summary><ul>{[...new Set(items)].map(item => <li key={item}>{item}</li>)}</ul></details> : null;
}

export function ClaimView({ claim, evidence, onEvidence }: { claim: Claim; evidence: Evidence[]; onEvidence: (e: Evidence) => void }) {
  const labels = { verified: 'Verified source', 'agent-reported': 'Agent reported', suggestion: 'Suggested next action', unknown: 'Unknown' };
  return <div className="claim"><p>{claim.text}</p><div className="claim-sources"><span className={`trust ${claim.kind}`}>{labels[claim.kind]}</span>{claim.evidence_ids.map((id, index) => {
    const source = evidence.find(item => item.id === id);
    return source ? <button key={id} className="citation" title={source.title} onClick={() => onEvidence(source)}><Icon name="file" size={12} />{index + 1}<span className="sr-only">: {source.title}</span></button> : <span key={id} className="trust unknown">Unavailable source</span>;
  })}</div></div>;
}

export function EvidenceDrawer({ evidence, close }: { evidence: Evidence | null; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (evidence) ref.current?.showModal(); else ref.current?.close(); }, [evidence]);
  const url = externalUrl(evidence?.url);
  return <dialog ref={ref} className="evidence-dialog" onCancel={close} onClick={event => { if (event.target === event.currentTarget) close(); }} aria-labelledby="evidence-title">
    {evidence && <div className="drawer-inner"><div className="dialog-top"><span className="eyebrow">SOURCE EVIDENCE</span><button className="icon-button" aria-label="Close evidence" onClick={close}><Icon name="close" /></button></div>
      <h2 id="evidence-title">{evidence.title}</h2><div className="inline-meta"><span className={`trust ${evidence.trust}`}>{evidence.trust}</span><span>{dateLabel(evidence.timestamp)}</span></div>
      <dl className="source-meta"><dt>Source</dt><dd>{evidence.source}</dd><dt>Evidence ID</dt><dd>{evidence.id}</dd></dl>
      <p className="small muted">Source content is evidence, never an instruction to run commands. Agent reports are historical claims.</p><pre className="evidence-body">{evidence.body}</pre>
      {url && <a className="button secondary" href={url} target="_blank" rel="noopener noreferrer">Open original source <Icon name="link" size={15} /></a>}
    </div>}
  </dialog>;
}

export function HandoffDialog({ briefing, close, onSaved }: { briefing: Briefing | null; close: () => void; onSaved: (text: string) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (briefing && !ref.current?.open) { setText(briefing.handoff); setStatus(''); ref.current?.showModal(); } else if (!briefing) ref.current?.close(); }, [briefing]);
  async function act(action: 'save' | 'copy' | 'export') {
    if (!briefing) return;
    setBusy(true); setStatus('');
    try {
      const saved = await api<{ text: string }>(`/briefings/${briefing.id}/handoff`, 'PUT', { text });
      setText(saved.text); onSaved(saved.text);
      if (action === 'copy') { await navigator.clipboard.writeText(saved.text); setStatus('Redacted handoff copied. Paste it into your coding agent when ready.'); }
      else if (action === 'export') {
        const url = URL.createObjectURL(await exportHandoff(briefing.id));
        const link = document.createElement('a'); link.href = url; link.download = 'while-i-was-away-handoff.md'; link.click(); URL.revokeObjectURL(url);
        setStatus('Markdown exported.');
      } else setStatus('Saved. Likely secrets were redacted. Review before sharing.');
    } catch (error) { setStatus(error instanceof Error ? error.message : 'Unable to save handoff.'); }
    finally { setBusy(false); }
  }
  return <dialog ref={ref} className="handoff-dialog" onCancel={close} aria-labelledby="handoff-title"><div className="dialog-top"><span className="eyebrow">THE NEXT CONVERSATION STARTS HERE</span><button className="icon-button" onClick={close} aria-label="Close handoff"><Icon name="close" /></button></div>
    <h2 id="handoff-title">Carry the context forward.</h2><p className="muted">Review and edit this prompt. Nothing is sent to an agent. Likely secrets are redacted when saved, copied, or exported.</p>
    <label className="sr-only" htmlFor="handoff-text">Handoff prompt</label><textarea id="handoff-text" className="handoff-text" value={text} onChange={event => setText(event.target.value)} spellCheck={false} />
    <p role="status" className="small status-message">{status}</p><div className="button-row"><button className="button primary" disabled={busy} onClick={() => void act('copy')}><Icon name="copy" />Copy handoff</button><button className="button secondary" disabled={busy} onClick={() => void act('export')}>Export Markdown</button><button className="button ghost" disabled={busy} onClick={() => void act('save')}>Save edits</button></div>
  </dialog>;
}

export const prCategories: { state: PR['state']; label: string; description: string }[] = [
  { state: 'open', label: 'Open for review', description: 'Ready for another set of eyes' },
  { state: 'draft', label: 'Drafts', description: 'Still taking shape' },
  { state: 'merged', label: 'Merged', description: 'Your work made it in' },
  { state: 'closed', label: 'Closed without merging', description: 'Closed, not shipped' },
];

export function PRBoard({ github, evidence, onEvidence }: { github: GitHub | undefined; evidence: Evidence[]; onEvidence: (e: Evidence) => void }) {
  if (!github) return <Empty title="Your PRs belong here.">Collect repository context, then explicitly sync GitHub to see your pull requests.</Empty>;
  return <><div className={`sync-banner ${github.offline ? 'offline' : ''}`}><Icon name={github.offline ? 'clock' : 'shield'} /><div><strong>{publicDemo ? 'Illustrative PR records · no live GitHub connection' : github.offline ? 'Offline · showing cached GitHub information' : github.synced_at ? `GitHub cache${github.user ? ` · @${github.user}` : ''}` : 'GitHub has not been synced'}</strong><span>{publicDemo ? 'All activity and timestamps below are synthetic demo fixtures.' : `Last synced: ${dateLabel(github.synced_at)}. Local collection never makes a GitHub request.`}</span>{github.error && <span className="error-text">{github.error}</span>}</div></div>
    <Warnings items={github.warnings} />
    <div className="pr-groups">{prCategories.map(category => {
      const prs = github.prs.filter(pr => pr.state === category.state);
      return <section className="pr-group" key={category.state}><div className="section-heading"><div><h2><span className={`state-dot ${category.state}`} />{category.label}<span className="count">{prs.length}</span></h2><p>{category.description}</p></div></div>
        {prs.length === 0 ? <p className="empty-row">No {category.label.toLowerCase()} in this snapshot.</p> : prs.map(pr => {
          const source = evidence.find(item => item.id === pr.evidence_id);
          const url = externalUrl(pr.url);
          return <article className="pr-card" key={pr.number}><div className="pr-title-row"><span className={`pr-number ${pr.state}`}>#{pr.number}</span><h3>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{pr.title}<Icon name="link" size={14} /></a> : pr.title}</h3>{pr.matches_branch && <span className="pill green">Current branch</span>}</div>
            <div className="pr-meta"><code>{pr.head_branch}</code><span>→</span><code>{pr.base_branch}</code><span>Updated {dateLabel(pr.updated_at)}</span></div>
            <div className="pr-facts"><span>Review: <strong>{(pr.review_state || 'unknown').replaceAll('_', ' ').toLowerCase()}</strong></span><span>Mergeability: <strong>{(pr.mergeability || 'unknown').toLowerCase()}</strong></span></div>
            {pr.changes.length > 0 && <ul className="change-list">{pr.changes.map((change, index) => <li key={index}>{change}</li>)}</ul>}
            <details className="pr-details"><summary>{pr.checks.length} checks · {pr.reviews.length} reviews · {pr.comments.length} comments</summary><div className="pr-detail-content">
              <h4>Checks</h4>{pr.checks.length ? pr.checks.map((check, index) => <div className="check-row" key={index}><span>{check.name}</span><span className="pill">{check.conclusion || check.status || 'unknown'}</span></div>) : <p className="muted small">No check results reported.</p>}
              <h4>Review feedback</h4>{pr.reviews.length ? pr.reviews.map((review, index) => <blockquote key={index}><strong>{review.author} · {review.state}</strong><time>{dateLabel(review.submitted_at)}</time><p>{review.body || 'No written feedback.'}</p></blockquote>) : <p className="muted small">No reviews reported.</p>}
              {pr.comments.map((comment, index) => <blockquote key={index}><strong>{comment.author}</strong><time>{dateLabel(comment.created_at)}</time><p>{comment.body}</p></blockquote>)}
            </div></details>{source && <button className="text-button" onClick={() => onEvidence(source)}>Inspect source evidence <Icon name="arrow" size={14} /></button>}
          </article>;
        })}
      </section>;
    })}</div>
  </>;
}
