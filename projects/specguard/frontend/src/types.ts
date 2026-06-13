// TypeScript types mirroring the FastAPI pydantic models in src/specguard/server.py.
// Keep these in sync when the API changes.

export type Provider = 'ollama' | 'openai' | 'anthropic' | 'minimax';

export interface ServerSettings {
  provider: Provider;
  model: string;
  ollama_base_url: string;
  minimax_base_url: string;
  output_dir: string;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
  has_minimax_key: boolean;
}

export interface SettingsUpdate {
  provider?: Provider;
  model?: string;
  ollama_base_url?: string;
  minimax_base_url?: string;
}

export interface ModeInfo {
  name: string;
  label: string;
  sections: string[];
}

export interface ValidationResult {
  ok: boolean;
  missing_sections: string[];
}

// Pipeline events streamed from POST /api/generate.
export type PipelineEvent =
  | { kind: 'draft'; timestamp: string; tokens?: number }
  | { kind: 'validate'; timestamp: string; validation: ValidationResult }
  | { kind: 'review'; timestamp: string; review_notes: string }
  | { kind: 'revise'; timestamp: string; tokens?: number }
  | {
      kind: 'save';
      timestamp: string;
      validation: ValidationResult;
      markdown?: string;
      output_path?: string;
      review_notes?: string;
      error?: string;
    }
  | { kind: 'error'; error: string };

export interface DocumentSummary {
  path: string;
  title: string;
  mode: string;
  created_at: string;
  size_bytes: number;
  valid: boolean;
  missing_sections: string[];
}

export interface HistoryResponse {
  documents: DocumentSummary[];
}

export interface HealthResponse {
  status: string;
  version: string;
  server_time: string;
}
