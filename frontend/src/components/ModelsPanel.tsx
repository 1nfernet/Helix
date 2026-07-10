import { useEffect, useMemo, useState } from "react";
import { getAdapters } from "../api";
import type { AdaptersResult, AdapterInfo } from "../types";

const KIND: Record<string, { label: string; cls: string; real: boolean }> = {
  verified: { label: "validated model", cls: "k-real", real: true },
  database: { label: "live database", cls: "k-real", real: true },
  remote: { label: "remote API", cls: "k-real", real: true },
  external: { label: "external tool", cls: "k-external", real: true },
  heuristic: { label: "heuristic", cls: "k-approx", real: false },
  mock: { label: "placeholder", cls: "k-approx", real: false },
  builtin: { label: "built-in", cls: "k-builtin", real: false },
};

function copyText(text: string): boolean {
  // execCommand works in more contexts (incl. iframes) than the clipboard API, which
  // needs a secure context; try the legacy path first, then fall back.
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (ok) return true;
  } catch {
    /* fall through */
  }
  navigator.clipboard?.writeText(text).catch(() => {});
  return true;
}

function CopyKey({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="copy-key"
      title="Copy this simulate {} line"
      onClick={() => {
        if (copyText(text)) {
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        }
      }}
    >
      <code>{text}</code>
      <span className="copy-ic">{done ? "copied" : "copy"}</span>
    </button>
  );
}

export function ModelsPanel({
  provenance,
  designName,
}: {
  provenance?: Record<string, string>;
  designName?: string;
}) {
  const [data, setData] = useState<AdaptersResult | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    getAdapters().then(setData).catch(() => setErr("Could not load the backend registry."));
  }, []);

  // Which backend did the last design actually use, per role? (provenance value is "key@version")
  const activeKey = (provKey: string | null): string | null => {
    if (!provKey || !provenance) return null;
    const v = provenance[provKey];
    return v ? v.split("@")[0] : null;
  };

  // The trust summary is about the *predicted numbers*, so count only the prediction
  // roles a run used — not the sequence source or variant check.
  const trust = useMemo(() => {
    if (!data || !provenance) return null;
    const PREDICTION = new Set(["on_target", "off_target", "repair", "base_edit_model", "prime_edit_model"]);
    let real = 0;
    let approx = 0;
    for (const role of data.roles) {
      if (!role.prov_key || !PREDICTION.has(role.prov_key)) continue;
      const ak = activeKey(role.prov_key);
      const opt = ak ? role.options.find((o) => o.key === ak) : undefined;
      if (!opt) continue;
      if (KIND[opt.kind]?.real) real += 1;
      else approx += 1;
    }
    return { real, approx };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, provenance]);

  if (err) return <div className="empty"><div className="big">{err}</div></div>;
  if (!data) return <div className="empty"><span className="spinner" /></div>;

  return (
    <div className="models">
      <div className="models-intro">
        {provenance ? (
          <>
            <strong>{designName ?? "Your last design"}</strong> ran on{" "}
            <span className="tr-real">{trust?.real ?? 0} validated</span> and{" "}
            <span className="tr-approx">{trust?.approx ?? 0} heuristic</span> backend
            {(trust?.approx ?? 0) === 1 ? "" : "s"}.{" "}
            {(trust?.approx ?? 0) > 0
              ? "Heuristics are transparent stand-ins — set up a real tool below to upgrade any number."
              : "All active backends are validated tools."}
          </>
        ) : (
          <>Each role the compiler computes has a swappable backend. Compile a design to see which
            one it used, or copy a <code>simulate {"{}"}</code> line to switch.</>
        )}
      </div>

      {data.roles.map((role) => {
        const ak = activeKey(role.prov_key);
        return (
          <div key={role.label} className="model-role">
            <div className="mr-head">
              <span className="section-label">{role.label}</span>
              {role.sim_key && <code className="mr-key">simulate {"{"} {role.sim_key}: … {"}"}</code>}
            </div>
            <div className="model-list">
              {role.options.map((a: AdapterInfo) => {
                const active = ak === a.key;
                const needsSetup = a.configured === false;
                const k = KIND[a.kind] ?? KIND.builtin;
                return (
                  <div key={a.key} className={"model-item" + (active ? " active" : "") + (needsSetup ? " off" : "")}>
                    <div className="mi-head">
                      <code className="mi-key">{a.key}</code>
                      <span className={"kind " + k.cls}>{k.label}</span>
                      {active && <span className="mi-status act">● active in this run</span>}
                      {!active && needsSetup && <span className="mi-status warn">needs setup</span>}
                      {!active && a.configured === true && <span className="mi-status on">ready</span>}
                    </div>
                    {a.note && <div className="mi-note">{a.note}</div>}
                    {role.sim_key && <CopyKey text={`${role.sim_key}: ${a.key}`} />}
                    {needsSetup && a.setup && <div className="mi-setup">enable: <code>{a.setup}</code></div>}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      <div className="models-foot">
        These backends are also reachable by AI agents over MCP — <code>python3 -m helix.mcp</code> exposes
        the same compiler through <code>helix_compile</code> / <code>helix_list_models</code>.
      </div>
    </div>
  );
}
