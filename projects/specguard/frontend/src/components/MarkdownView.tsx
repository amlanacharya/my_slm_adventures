// Tiny markdown renderer. Covers the subset the LLM produces:
//   # / ## / ###
//   paragraphs
//   - / * bullet lists
//   1. ordered lists
//   ```fenced code blocks```
//   `inline code`
// We don't pull in a library to keep the bundle small.

import { Fragment, type ReactNode } from 'react';

type Block =
  | { kind: 'h1' | 'h2' | 'h3'; text: string }
  | { kind: 'p'; text: string }
  | { kind: 'ul' | 'ol'; items: string[] }
  | { kind: 'code'; text: string };

function parse(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith('```')) {
      const start = i + 1;
      let end = start;
      while (end < lines.length && !lines[end].startsWith('```')) end++;
      blocks.push({ kind: 'code', text: lines.slice(start, end).join('\n') });
      i = end + 1;
      continue;
    }
    if (/^### /.test(line)) {
      blocks.push({ kind: 'h3', text: line.slice(4).trim() });
      i++;
      continue;
    }
    if (/^## /.test(line)) {
      blocks.push({ kind: 'h2', text: line.slice(3).trim() });
      i++;
      continue;
    }
    if (/^# /.test(line)) {
      blocks.push({ kind: 'h1', text: line.slice(2).trim() });
      i++;
      continue;
    }
    if (/^(\s*)[-*] /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^(\s*)[-*] /.test(lines[i])) {
        items.push(lines[i].replace(/^(\s*)[-*] /, '').trim());
        i++;
      }
      blocks.push({ kind: 'ul', items });
      continue;
    }
    if (/^\s*\d+\. /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\. /, '').trim());
        i++;
      }
      blocks.push({ kind: 'ol', items });
      continue;
    }
    if (line.trim() === '') {
      i++;
      continue;
    }
    const buf: string[] = [];
    while (i < lines.length && lines[i].trim() !== '' && !/^(#|```|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i])) {
      buf.push(lines[i]);
      i++;
    }
    blocks.push({ kind: 'p', text: buf.join(' ').trim() });
  }
  return blocks;
}

function renderInline(text: string): ReactNode {
  // Handle **bold**, *italic*, `code`. We escape everything else.
  const parts: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) parts.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith('`')) parts.push(<code key={key++}>{tok.slice(1, -1)}</code>);
    else parts.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.map((p, i) => <Fragment key={i}>{p}</Fragment>);
}

export function MarkdownView({ markdown }: { markdown: string }) {
  const blocks = parse(markdown);
  return (
    <div className="md">
      {blocks.map((b, i) => {
        if (b.kind === 'h1') return <h1 key={i} style={{ fontSize: 26, margin: '0 0 16px', fontWeight: 600 }}>{renderInline(b.text)}</h1>;
        if (b.kind === 'h2') return <h2 key={i}>{renderInline(b.text)}</h2>;
        if (b.kind === 'h3') return <h3 key={i}>{renderInline(b.text)}</h3>;
        if (b.kind === 'p') return <p key={i}>{renderInline(b.text)}</p>;
        if (b.kind === 'ul')
          return (
            <ul key={i}>
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it)}</li>
              ))}
            </ul>
          );
        if (b.kind === 'ol')
          return (
            <ol key={i} style={{ marginLeft: 20, marginBottom: 12 }}>
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it)}</li>
              ))}
            </ol>
          );
        // The only remaining kind is 'code'; assert for the type checker.
        const codeBlock = b as Extract<Block, { kind: 'code' }>;
        return (
          <pre
            key={i}
            style={{ background: 'var(--panel-2)', padding: 12, borderRadius: 6, overflowX: 'auto', fontSize: 12 }}
          >
            <code>{codeBlock.text}</code>
          </pre>
        );
      })}
    </div>
  );
}
