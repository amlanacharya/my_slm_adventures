import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, humanSize, relativeTime } from '../api';

type Filter = 'all' | 'prd' | 'brd' | 'tech_scope';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'prd', label: 'PRD' },
  { key: 'brd', label: 'BRD' },
  { key: 'tech_scope', label: 'Tech scope' },
];

export function HistoryPage() {
  const [filter, setFilter] = useState<Filter>('all');
  const query = useQuery({
    queryKey: ['history'],
    queryFn: () => api.history(),
    refetchInterval: 5_000,
  });

  const docs = useMemo(() => {
    if (!query.data) return [];
    if (filter === 'all') return query.data.documents;
    return query.data.documents.filter((d) => d.mode === filter);
  }, [query.data, filter]);

  return (
    <div className="page-pad">
      <div className="history-head">
        <div>
          <h1>Past documents</h1>
          <p className="subhead">
            {query.data
              ? `${query.data.documents.length} file${query.data.documents.length === 1 ? '' : 's'} in outputs/`
              : 'Loading…'}{' '}
            · all on this machine
          </p>
        </div>
        <div className="filters">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className="filter"
              aria-pressed={filter === f.key}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {query.isLoading && <p className="subhead">Loading…</p>}

      {!query.isLoading && docs.length === 0 && (
        <div className="empty-state">
          <h2>No documents yet</h2>
          <p>
            Head over to <Link to="/">Generate</Link> and run your first pipeline. Finished
            documents will appear here.
          </p>
        </div>
      )}

      {docs.length > 0 && (
        <table className="docs">
          <thead>
            <tr>
              <th>Document</th>
              <th>Type</th>
              <th>When</th>
              <th>Validation</th>
              <th style={{ textAlign: 'right' }}>Size</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.path}>
                <td>
                  <div className="title">{d.title}</div>
                  <div className="slug">{d.path}</div>
                </td>
                <td>
                  <span className={`mode-tag ${d.mode}`}>
                    {d.mode === 'tech_scope' ? 'Tech' : d.mode.toUpperCase()}
                  </span>
                </td>
                <td className="when">{relativeTime(d.created_at)}</td>
                <td>
                  {d.valid ? (
                    <span className="validity ok">✓ all sections</span>
                  ) : d.missing_sections.length === 0 ? (
                    <span className="validity warn">untested</span>
                  ) : (
                    <span className="validity bad">
                      missing {d.missing_sections.length}
                    </span>
                  )}
                </td>
                <td className="size">{humanSize(d.size_bytes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
