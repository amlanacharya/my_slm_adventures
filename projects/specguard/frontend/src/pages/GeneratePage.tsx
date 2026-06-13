import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, streamGeneration } from '../api';
import type { PipelineEvent } from '../types';
import { MarkdownView } from '../components/MarkdownView';

type TraceRow = {
  ts: string;
  step: string;
  stepKind: 'ok' | 'warn' | 'bad' | 'plain';
  msg: string;
  msgMuted?: boolean;
};

const STEP_LABELS: Record<string, string> = {
  draft: 'draft',
  validate: 'validate',
  review: 'review',
  revise: 'revise',
  save: 'save',
};

function summarizeEvent(ev: PipelineEvent): TraceRow | null {
  if (ev.kind === 'error') {
    return { ts: '', step: 'error', stepKind: 'bad', msg: ev.error };
  }
  const step = STEP_LABELS[ev.kind] ?? ev.kind;
  let msg = '';
  let msgMuted = false;
  let stepKind: TraceRow['stepKind'] = 'plain';
  if (ev.kind === 'draft' || ev.kind === 'revise') {
    msg = `${ev.tokens ?? 0} tokens`;
    stepKind = 'plain';
  } else if (ev.kind === 'validate') {
    if (ev.validation.ok) {
      msg = 'all required sections present';
      stepKind = 'ok';
    } else {
      msg = `missing: ${ev.validation.missing_sections.join(', ')}`;
      stepKind = 'warn';
    }
  } else if (ev.kind === 'review') {
    const truncated =
      ev.review_notes.length > 200 ? ev.review_notes.slice(0, 197) + '…' : ev.review_notes;
    msg = truncated;
    msgMuted = true;
    stepKind = 'warn';
  } else if (ev.kind === 'save') {
    if (ev.error) {
      msg = `failed: ${ev.error}`;
      stepKind = 'bad';
    } else {
      msg = ev.output_path ?? '';
      msgMuted = true;
      stepKind = 'ok';
    }
  }
  return { ts: ev.timestamp ?? '', step, stepKind, msg, msgMuted };
}

// Hard cap on how many trace rows the UI keeps in memory. A 6-event pipeline
// produces 6 rows; this cap only matters if the SSE stream somehow emits
// thousands of events (which would itself be a server bug, but we'd rather
// degrade gracefully than crash the page).
const MAX_TRACE_ROWS = 200;

export function GeneratePage() {
  const modesQuery = useQuery({ queryKey: ['modes'], queryFn: () => api.listModes() });
  const [mode, setMode] = useState<string>('prd');
  const [idea, setIdea] = useState<string>(
    'Build an app for interior designers to manage quotation, billing, GST invoice, labour payments, and procurement.',
  );
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trace, setTrace] = useState<TraceRow[]>([]);
  const [finalMarkdown, setFinalMarkdown] = useState<string | null>(null);
  const [finalPath, setFinalPath] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const onRun = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setError(null);
    setSaveError(null);
    setFinalMarkdown(null);
    setFinalPath(null);
    setTrace([]);
    setStartedAt(Date.now());

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const final = await streamGeneration(
        idea,
        mode,
        (ev) => {
          const row = summarizeEvent(ev);
          if (row) {
            setTrace((t) => {
              const next = t.length >= MAX_TRACE_ROWS ? t.slice(1) : t;
              return [...next, row];
            });
          }
          if (ev.kind === 'save') {
            if (ev.markdown) setFinalMarkdown(ev.markdown);
            if (ev.output_path) setFinalPath(ev.output_path);
            if (ev.error) setSaveError(ev.error);
          }
        },
        controller.signal,
      );
      if (final.kind === 'save' && final.validation && !final.validation.ok) {
        setSaveError(final.error ?? 'validation failed');
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message);
      }
    } finally {
      setIsRunning(false);
      abortRef.current = null;
    }
  };

  const onCancel = () => {
    abortRef.current?.abort();
  };

  const onCopy = async () => {
    if (finalMarkdown) {
      await navigator.clipboard.writeText(finalMarkdown);
    }
  };

  const onOpenFile = () => {
    if (finalPath) alert(`Saved at: ${finalPath}`);
  };

  const elapsedMs = startedAt ? Date.now() - startedAt : 0;
  const stepCountLabel = trace.length
    ? `${trace.length} step${trace.length === 1 ? '' : 's'} · ${(elapsedMs / 1000).toFixed(1)}s`
    : '';

  return (
    <div className="shell">
      <aside className="left">
        <div className="scroll">
          <div className="group">
            <h3>Document</h3>
            <div className="seg" role="tablist">
              {modesQuery.data?.modes.map((m) => (
                <button
                  key={m.name}
                  aria-pressed={mode === m.name}
                  onClick={() => setMode(m.name)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <div className="group">
            <h3>Idea</h3>
            <textarea
              className="idea"
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="What do you want to build?"
            />
          </div>
        </div>
        <div className="footer">
          {isRunning ? (
            <button className="run cancel" onClick={onCancel}>
              Cancel
            </button>
          ) : (
            <button className="run" onClick={onRun} disabled={idea.trim().length < 3}>
              Run pipeline
            </button>
          )}
        </div>
      </aside>

      <section className="right">
        <div className="trace">
          <div className="trace-head">
            <span className={`dot ${isRunning ? 'running' : ''}`} />
            <span>Pipeline trace</span>
            {stepCountLabel && <span className="count">{stepCountLabel}</span>}
          </div>
          {error && <div className="error-banner">{error}</div>}
          {trace.length === 0 && !error && (
            <div className="trace-empty">
              {isRunning
                ? 'Starting…'
                : 'Press "Run pipeline" to start. Each step will appear here as the model produces it.'}
            </div>
          )}
          {trace.map((row, i) => (
            <div className="trace-line" key={`${row.ts}-${row.step}-${i}`}>
              <span className="trace-ts">{row.ts}</span>
              <span className={`trace-step ${row.stepKind === 'plain' ? '' : row.stepKind}`}>
                {row.step}
              </span>
              <span className={`trace-msg ${row.msgMuted ? 'muted' : ''}`}>{row.msg}</span>
            </div>
          ))}
        </div>

        <article className="output">
          {finalMarkdown ? (
            <>
              <div className="output-meta">
                <span>Document</span>
                <span>·</span>
                <span className="lower">{(elapsedMs / 1000).toFixed(1)}s</span>
                <span>·</span>
                {saveError ? (
                  <span className="badge bad">failed</span>
                ) : (
                  <span className="badge">saved</span>
                )}
                <span className="spacer" />
                <button className="chip-btn" onClick={onCopy}>
                  Copy markdown
                </button>
                <button className="chip-btn" onClick={onOpenFile}>
                  Open file
                </button>
              </div>
              {saveError && (
                <div className="error-banner">
                  Generation failed: {saveError}. Try a more specific idea, or pick a stronger model.
                </div>
              )}
              <MarkdownView markdown={finalMarkdown} />
            </>
          ) : (
            <div className="output-empty">
              <h2>Nothing generated yet</h2>
              <p>Type your idea on the left and press Run pipeline.</p>
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
