// Thin fetch wrapper. The base path is "/api" because Vite proxies /api/* to FastAPI
// in dev, and in production the React build is served by FastAPI on the same origin.
import type {
  HealthResponse,
  HistoryResponse,
  ModeInfo,
  PipelineEvent,
  ServerSettings,
  SettingsUpdate,
} from './types';

const BASE = '/api';

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health(): Promise<HealthResponse> {
    return jsonFetch('/health');
  },
  getSettings(): Promise<ServerSettings> {
    return jsonFetch('/settings');
  },
  updateSettings(patch: SettingsUpdate): Promise<ServerSettings> {
    return jsonFetch('/settings', { method: 'POST', body: JSON.stringify(patch) });
  },
  setApiKey(
    provider: 'openai' | 'anthropic',
    key: string,
    clear = false,
  ): Promise<{ ok: boolean; provider: string; configured: boolean }> {
    return jsonFetch('/api-key', {
      method: 'POST',
      body: JSON.stringify({ provider, key, clear }),
    });
  },
  listModes(): Promise<{ modes: ModeInfo[] }> {
    return jsonFetch('/modes');
  },
  history(): Promise<HistoryResponse> {
    return jsonFetch('/history');
  },
  document(path: string): Promise<string> {
    return fetch(`${BASE}/document?path=${encodeURIComponent(path)}`).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      return r.text();
    });
  },
};

/**
 * Stream a generation request. The FastAPI server returns `text/event-stream`
 * where each event is `data: {json}\n\n` followed by `data: [DONE]\n\n`.
 *
 * @param onEvent  Called for each parsed PipelineEvent.
 * @param signal   Optional AbortSignal to cancel mid-stream.
 * @returns        The final `save` event.
 */
export async function streamGeneration(
  idea: string,
  mode: string,
  onEvent: (event: PipelineEvent) => void,
  signal?: AbortSignal,
): Promise<PipelineEvent> {
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idea, mode }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalEvent: PipelineEvent | null = null;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE events are separated by a blank line.
    let sep = buffer.indexOf('\n\n');
    while (sep !== -1) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const dataLine = chunk
        .split('\n')
        .find((l) => l.startsWith('data: '));
      if (dataLine) {
        const payload = dataLine.slice('data: '.length);
        if (payload === '[DONE]') {
          if (finalEvent) return finalEvent;
          throw new Error('stream ended without a save event');
        }
        try {
          const event = JSON.parse(payload) as PipelineEvent;
          onEvent(event);
          if (event.kind === 'save') finalEvent = event;
        } catch (err) {
          console.error('failed to parse SSE payload', payload, err);
        }
      }
      sep = buffer.indexOf('\n\n');
    }
  }
  if (finalEvent) return finalEvent;
  throw new Error('stream ended unexpectedly');
}

export function relativeTime(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diffSec = Math.max(0, Math.round((now - then) / 1000));
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
    return `${Math.round(diffSec / 86400)}d ago`;
  } catch {
    return iso;
  }
}

export function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
