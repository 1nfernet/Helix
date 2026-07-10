import { useRef } from "react";
import type { Format } from "../types";

// Structural keywords of the Helix grammar (block names + field keys). Enum values
// (SpCas9, crispr_ko, …) stay plain; keys are detected by a trailing ':' anyway.
const KEYWORDS = new Set([
  "helix", "organism", "cell_line", "target", "strategy", "constraints", "simulate",
  "deliver", "validate", "goal", "region", "sequence", "edit", "delete", "tss", "frame",
  "modality", "enzyme", "editor", "donor", "profile", "avoid", "on_target", "off_target",
  "repair_outcome", "sequence_provider", "base_edit_model", "prime_edit_model",
  "variant_source", "guides", "gc", "min", "max", "count", "min_efficiency", "max_cfd",
  "name", "genome_build", "cell_line",
]);

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

const span = (cls: string, text: string) => `<span class="t-${cls}">${esc(text)}</span>`;

// Tokenize a single line to highlighted HTML. Works for both the Helix grammar and
// YAML (keys are anything followed by ':'; comments/strings/numbers are shared).
function highlightLine(line: string): string {
  let out = "";
  let i = 0;
  const n = line.length;
  while (i < n) {
    const c = line[i];
    if (c === "#") {
      out += span("comment", line.slice(i));
      break;
    }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n && line[j] !== c) j++;
      j = Math.min(j + 1, n);
      out += span("string", line.slice(i, j));
      i = j;
      continue;
    }
    if (/[0-9]/.test(c) || (c === "." && /[0-9]/.test(line[i + 1] || ""))) {
      const m = /^[0-9]*\.?[0-9]+/.exec(line.slice(i));
      if (m) {
        out += span("number", m[0]);
        i += m[0].length;
        continue;
      }
    }
    if (/[A-Za-z_]/.test(c)) {
      // dotted identifier path, e.g. on_target.min_efficiency
      const m = /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*/.exec(line.slice(i));
      const word = m![0];
      const rest = line.slice(i + word.length);
      let cls = "ident";
      if (/^\s*\(/.test(rest)) cls = "func"; // gene(…), human(…), homopolymer(…)
      else if (/^\s*:/.test(rest) && !/^\s*::/.test(rest)) cls = "kw"; // a key
      else if (KEYWORDS.has(word)) cls = "kw";
      else if (word === "true" || word === "false") cls = "bool";
      out += span(cls, word);
      i += word.length;
      continue;
    }
    // punctuation / whitespace
    if (/\s/.test(c)) {
      out += esc(c);
    } else {
      out += span("punct", c);
    }
    i++;
  }
  return out || "​"; // keep empty lines at full height
}

export function CodeEditor({
  value,
  onChange,
  errorLine,
  placeholder,
}: {
  value: string;
  onChange: (s: string) => void;
  format: Format;
  errorLine?: number;
  placeholder?: string;
}) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const hlRef = useRef<HTMLPreElement>(null);
  const gutRef = useRef<HTMLDivElement>(null);

  const lines = value.length ? value.split("\n") : [""];
  const codeHtml = lines
    .map((ln, i) => `<div class="cl${errorLine === i + 1 ? " err" : ""}">${highlightLine(ln)}</div>`)
    .join("");
  const gutterHtml = lines
    .map((_, i) => `<div class="gl${errorLine === i + 1 ? " err" : ""}">${i + 1}</div>`)
    .join("");

  const sync = () => {
    const ta = taRef.current;
    if (!ta) return;
    if (hlRef.current) {
      hlRef.current.scrollTop = ta.scrollTop;
      hlRef.current.scrollLeft = ta.scrollLeft;
    }
    if (gutRef.current) gutRef.current.scrollTop = ta.scrollTop;
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = e.currentTarget;
      const s = ta.selectionStart;
      const end = ta.selectionEnd;
      const next = value.slice(0, s) + "  " + value.slice(end);
      onChange(next);
      requestAnimationFrame(() => ta.setSelectionRange(s + 2, s + 2));
    }
  };

  return (
    <div className="code-editor">
      <div className="code-gutter" ref={gutRef} dangerouslySetInnerHTML={{ __html: gutterHtml }} />
      <div className="code-view">
        <pre className="code-hl" ref={hlRef} aria-hidden="true">
          <code dangerouslySetInnerHTML={{ __html: codeHtml }} />
        </pre>
        <textarea
          ref={taRef}
          className="code-input"
          wrap="off"
          spellCheck={false}
          value={value}
          placeholder={placeholder}
          onScroll={sync}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
        />
      </div>
    </div>
  );
}
