import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import type { Provider, ServerSettings } from '../types';

const PROVIDER_MODELS: Record<Provider, string[]> = {
  ollama: ['gemma4:latest', 'gemma3:4b', 'gemma3:12b', 'llama3.1:8b', 'qwen2.5:7b'],
  openai: ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini', 'o4-mini'],
  anthropic: ['claude-3-5-haiku-latest', 'claude-3-5-sonnet-latest', 'claude-sonnet-4-5'],
  minimax: ['MiniMax-M3'],
};

const CLOUD_PROVIDERS: Provider[] = ['openai', 'anthropic', 'minimax'];

function cloudEnvVar(
  provider: Provider,
): 'OPENAI_API_KEY' | 'ANTHROPIC_API_KEY' | 'MINIMAX_API_KEY' | null {
  if (provider === 'openai') return 'OPENAI_API_KEY';
  if (provider === 'anthropic') return 'ANTHROPIC_API_KEY';
  if (provider === 'minimax') return 'MINIMAX_API_KEY';
  return null;
}

export function SettingsPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['settings'], queryFn: () => api.getSettings() });
  const [form, setForm] = useState<ServerSettings | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (query.data && !form) setForm(query.data);
  }, [query.data, form]);

  const mutation = useMutation({
    mutationFn: (patch: Partial<ServerSettings>) => api.updateSettings(patch),
    onSuccess: (data) => {
      queryClient.setQueryData(['settings'], data);
      setForm(data);
      setToast('Settings saved');
      window.setTimeout(() => setToast(null), 2000);
    },
    onError: (err) => {
      setToast(`Save failed: ${(err as Error).message}`);
      window.setTimeout(() => setToast(null), 4000);
    },
  });

  if (query.isLoading || !form) {
    return (
      <div className="page-pad">
        <div className="settings-page">
          <h1>Settings</h1>
          <p className="subhead">Loading…</p>
        </div>
      </div>
    );
  }

  const set = <K extends keyof ServerSettings>(key: K, value: ServerSettings[K]) =>
    setForm((f) => (f ? { ...f, [key]: value } : f));

  const suggestions = PROVIDER_MODELS[form.provider];

  return (
    <div className="page-pad">
      <div className="settings-page">
        <h1>Settings</h1>
        <p className="subhead">Configure the local LLM provider, model, and output directory.</p>

        <div className="card">
          <h2>Provider</h2>
          <p className="hint">
            Where generation runs. <strong>Ollama</strong> is local and private. <strong>OpenAI</strong>{' '}
            <strong>Anthropic</strong>, and <strong>MiniMax</strong> require API keys in <code>.env</code>.
          </p>
          <div className="row">
            <label htmlFor="provider">Backend</label>
            <select
              id="provider"
              value={form.provider}
              onChange={(e) => {
                const newProvider = e.target.value as Provider;
                const defaultModel = PROVIDER_MODELS[newProvider][0];
                setForm((f) => (f ? { ...f, provider: newProvider, model: defaultModel } : f));
              }}
            >
              <option value="ollama">Ollama (local)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="minimax">MiniMax</option>
            </select>
          </div>
        </div>

        <div className="card">
          <h2>Model</h2>
          <p className="hint">
            The model to call for draft, review, and revision. Pick a suggestion, or type a custom name.
          </p>
          <div className="row">
            <label htmlFor="model">Model name</label>
            <input
              id="model"
              type="text"
              list="model-suggestions"
              value={form.model}
              onChange={(e) => set('model', e.target.value)}
            />
            <datalist id="model-suggestions">
              {suggestions.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </div>
        </div>

        {form.provider === 'ollama' && (
          <div className="card">
            <h2>Ollama endpoint</h2>
            <p className="hint">Base URL of the local Ollama server. Default works for most installs.</p>
            <div className="row">
              <label htmlFor="ollama-url">Base URL</label>
              <input
                id="ollama-url"
                type="text"
                value={form.ollama_base_url}
                onChange={(e) => set('ollama_base_url', e.target.value)}
              />
            </div>
          </div>
        )}

        {form.provider === 'minimax' && (
          <div className="card">
            <h2>MiniMax endpoint</h2>
            <p className="hint">
              OpenAI-compatible MiniMax API base URL. The default works for the global API.
            </p>
            <div className="row">
              <label htmlFor="minimax-url">Base URL</label>
              <input
                id="minimax-url"
                type="text"
                value={form.minimax_base_url}
                onChange={(e) => set('minimax_base_url', e.target.value)}
              />
            </div>
          </div>
        )}

        <div className="card">
          <h2>Output</h2>
          <p className="hint">Where finished documents are saved on this machine.</p>
          <div className="row">
            <label>Output dir</label>
            <span className="value">{form.output_dir}</span>
          </div>
        </div>

        {CLOUD_PROVIDERS.includes(form.provider) && (
          <ApiKeyCard
            provider={form.provider as 'openai' | 'anthropic' | 'minimax'}
            configured={
              form.provider === 'openai'
                ? form.has_openai_key
                : form.provider === 'anthropic'
                  ? form.has_anthropic_key
                  : form.has_minimax_key
            }
            onSaved={() => {
              queryClient.invalidateQueries({ queryKey: ['settings'] });
            }}
          />
        )}

        <button
          className="save-btn"
          disabled={mutation.isPending}
          onClick={() =>
            mutation.mutate({
              provider: form.provider,
              model: form.model,
              ollama_base_url: form.ollama_base_url,
              minimax_base_url: form.minimax_base_url,
            })
          }
        >
          {mutation.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function ApiKeyCard({
  provider,
  configured,
  onSaved,
}: {
  provider: 'openai' | 'anthropic' | 'minimax';
  configured: boolean;
  onSaved: () => void;
}) {
  const [key, setKey] = useState('');
  const [editing, setEditing] = useState(!configured);
  const [toast, setToast] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: () => api.setApiKey(provider, key, false),
    onSuccess: () => {
      setKey('');
      setEditing(false);
      onSaved();
      setToast('API key saved');
      window.setTimeout(() => setToast(null), 2000);
    },
    onError: (err) => {
      setToast(`Save failed: ${(err as Error).message}`);
      window.setTimeout(() => setToast(null), 4000);
    },
  });

  const clearMutation = useMutation({
    mutationFn: () => api.setApiKey(provider, '', true),
    onSuccess: () => {
      setEditing(true);
      onSaved();
      setToast('API key cleared');
      window.setTimeout(() => setToast(null), 2000);
    },
    onError: (err) => {
      setToast(`Clear failed: ${(err as Error).message}`);
      window.setTimeout(() => setToast(null), 4000);
    },
  });

  const envName = cloudEnvVar(provider);
  const label = provider === 'openai' ? 'OpenAI' : provider === 'anthropic' ? 'Anthropic' : 'MiniMax';

  return (
    <div className="card">
      <h2>{label} API key</h2>
      <p className="hint">
        The server reads <code>{envName}</code> from <code>.env</code> when calling the
        provider. Paste it here to save it without leaving the browser. The key is written
        to a local <code>.env</code> file — never transmitted anywhere else.
      </p>
      {configured && !editing ? (
        <div className="row">
          <label>Status</label>
          <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span
              className="chip"
              style={{ background: 'rgba(48,209,88,0.15)', color: 'var(--ok)', borderColor: 'rgba(48,209,88,0.3)' }}
            >
              <span className="dot" />
              configured
            </span>
            <button className="filter" onClick={() => setEditing(true)}>
              Replace
            </button>
            <button className="filter" onClick={() => clearMutation.mutate()}>
              Clear
            </button>
          </span>
        </div>
      ) : (
        <div className="row">
          <label htmlFor="api-key">Key</label>
          <input
            id="api-key"
            type="password"
            placeholder="paste your key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            autoComplete="off"
          />
          <button
            className="filter"
            disabled={saveMutation.isPending || !key.trim()}
            onClick={() => saveMutation.mutate()}
          >
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
          {configured && (
            <button className="filter" onClick={() => setEditing(false)}>
              Cancel
            </button>
          )}
        </div>
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
