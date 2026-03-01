"""
enact/ui.py — Local receipt browser for Enact audit receipts.

Starts a lightweight HTTP server (stdlib only, zero extra deps) that serves a
web UI for browsing, filtering, and inspecting receipt JSON files.

Usage:
    python -m enact.ui                        # serve receipts/ on port 8765
    python -m enact.ui --dir /path/receipts   # custom directory
    python -m enact.ui --port 9000            # custom port
    python -m enact.ui --secret MY_SECRET     # enable signature verification
    enact-ui                                  # after pip install enact-sdk

API endpoints served:
    GET /                              HTML UI
    GET /api/receipts                  JSON list of receipt summaries (newest first)
    GET /api/receipts/{run_id}         JSON full receipt + signature_valid field
"""
import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from enact.receipt import load_receipt, verify_signature

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

# ---------------------------------------------------------------------------
# Embedded HTML — single-file deployment, no template dependencies
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enact — Receipt Browser</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-2: #f1f5f9;
      --border: #e2e8f0;
      --text: #0f172a;
      --text-muted: #64748b;
      --pass: #16a34a;
      --pass-bg: rgba(22,163,74,.10);
      --block: #dc2626;
      --block-bg: rgba(220,38,38,.10);
      --partial: #d97706;
      --partial-bg: rgba(217,119,6,.10);
      --accent: #4f46e5;
      --radius: 6px;
    }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      font-size: 14px;
      line-height: 1.5;
    }
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      height: 56px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      font-size: 16px;
      color: var(--text);
    }
    .logo svg { color: var(--accent); flex-shrink: 0; }
    .header-sub { color: var(--text-muted); font-size: 13px; }
    main { padding: 24px; max-width: 1280px; margin: 0 auto; }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }
    .filter-btn {
      padding: 5px 12px;
      border-radius: var(--radius);
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text-muted);
      cursor: pointer;
      font-size: 13px;
      transition: border-color .15s, color .15s, background .15s;
    }
    .filter-btn:hover { border-color: var(--accent); color: var(--text); }
    .filter-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
    .search {
      margin-left: auto;
      padding: 5px 12px;
      border-radius: var(--radius);
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      font-size: 13px;
      width: 220px;
      outline: none;
    }
    .search:focus { border-color: var(--accent); }
    .search::placeholder { color: var(--text-muted); }
    .stats {
      display: flex;
      gap: 18px;
      margin-bottom: 14px;
      font-size: 13px;
      color: var(--text-muted);
      min-height: 20px;
    }
    .stat { display: flex; align-items: center; gap: 5px; }
    .stat-n { font-weight: 600; color: var(--text); }
    .table-wrap {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
    }
    table { width: 100%; border-collapse: collapse; }
    thead { background: var(--surface-2); border-bottom: 1px solid var(--border); }
    th {
      padding: 9px 16px;
      text-align: left;
      font-weight: 500;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: var(--text-muted);
    }
    tbody tr {
      border-bottom: 1px solid var(--border);
      cursor: pointer;
      transition: background .1s;
    }
    tbody tr:last-child { border-bottom: none; }
    tbody tr:hover { background: var(--surface-2); }
    tbody tr.selected { background: rgba(99,102,241,.12); }
    td { padding: 9px 16px; font-size: 13px; }
    .mono { font-family: monospace; font-size: 11px; color: var(--text-muted); }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .04em;
    }
    .badge-pass    { color: var(--pass);    background: var(--pass-bg); }
    .badge-block   { color: var(--block);   background: var(--block-bg); }
    .badge-partial { color: var(--partial); background: var(--partial-bg); }
    .empty { padding: 52px; text-align: center; color: var(--text-muted); }
    .empty svg { opacity: .35; margin-bottom: 14px; }
    .empty h3 { font-size: 15px; margin-bottom: 6px; color: var(--text); }
    .loading { padding: 32px; text-align: center; color: var(--text-muted); font-size: 13px; }
    /* Detail panel */
    #detail { display: none; margin-top: 22px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
    #detail.show { display: block; }
    .det-header {
      padding: 12px 20px;
      background: var(--surface-2);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .det-title { font-weight: 600; font-size: 13px; }
    .det-close {
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
      display: flex;
      align-items: center;
    }
    .det-close:hover { color: var(--text); background: var(--border); }
    .det-body {
      padding: 20px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }
    @media (max-width: 700px) { .det-body { grid-template-columns: 1fr; } }
    .det-section h4 {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: var(--text-muted);
      margin-bottom: 10px;
      font-weight: 500;
    }
    .det-section + .det-section { margin-top: 20px; }
    .meta-row { display: flex; gap: 10px; font-size: 13px; margin-bottom: 7px; }
    .meta-lbl { color: var(--text-muted); min-width: 90px; flex-shrink: 0; }
    .meta-val { color: var(--text); word-break: break-all; }
    pre.payload {
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 10px;
      font-size: 11px;
      overflow: auto;
      max-height: 180px;
      color: var(--text-muted);
      line-height: 1.6;
    }
    .item-list { display: flex; flex-direction: column; gap: 6px; }
    .item {
      padding: 8px 10px;
      border-radius: 4px;
      background: var(--surface-2);
      border: 1px solid var(--border);
      font-size: 12px;
    }
    .item-name { font-family: monospace; font-weight: 600; margin-bottom: 2px; }
    .item-sub  { color: var(--text-muted); font-size: 11px; word-break: break-word; }
    .item-pass   { border-left: 3px solid var(--pass); }
    .item-fail   { border-left: 3px solid var(--block); }
    .sig-ok  { color: var(--pass); }
    .sig-bad { color: var(--block); }
    .sig-unk { color: var(--text-muted); }
  </style>
</head>
<body>
<header>
  <div class="logo">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"/>
    </svg>
    Enact
  </div>
  <span class="header-sub">/ Receipt Browser</span>
</header>

<main>
  <div class="toolbar">
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="PASS">PASS</button>
    <button class="filter-btn" data-filter="BLOCK">BLOCK</button>
    <button class="filter-btn" data-filter="PARTIAL">PARTIAL</button>
    <input class="search" type="text" placeholder="Search workflow or actor..." id="q">
  </div>

  <div class="stats" id="stats"></div>

  <div class="table-wrap">
    <div class="loading" id="loading">Loading receipts...</div>
    <table id="tbl" style="display:none">
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Workflow</th>
          <th>Actor</th>
          <th>Decision</th>
          <th>Actions</th>
          <th>Policies</th>
          <th>Run ID</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="empty" id="empty" style="display:none">
      <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>
      </svg>
      <h3>No receipts found</h3>
      <p>Run an Enact workflow to generate audit receipts.</p>
    </div>
  </div>

  <div id="detail">
    <div class="det-header">
      <span class="det-title" id="det-title">Run details</span>
      <button class="det-close" id="det-close" title="Close">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>
    <div class="det-body" id="det-body"></div>
  </div>
</main>

<script>
  let all = [], filter = 'all', selected = null;

  // ---- data ----

  async function load() {
    try {
      const r = await fetch('/api/receipts');
      all = await r.json();
      render();
    } catch(e) {
      document.getElementById('loading').textContent = 'Failed to load receipts.';
    }
  }

  // ---- render table ----

  function render() {
    const q = document.getElementById('q').value.toLowerCase();
    const rows = all.filter(r => {
      if (filter !== 'all' && r.decision !== filter) return false;
      if (q && !r.workflow.toLowerCase().includes(q) && !r.user_email.toLowerCase().includes(q)) return false;
      return true;
    });

    document.getElementById('loading').style.display = 'none';
    const tbody = document.getElementById('tbody');
    tbody.innerHTML = '';

    if (rows.length === 0) {
      document.getElementById('tbl').style.display   = 'none';
      document.getElementById('empty').style.display = 'block';
    } else {
      document.getElementById('tbl').style.display   = 'table';
      document.getElementById('empty').style.display = 'none';
      for (const r of rows) {
        const tr = document.createElement('tr');
        if (r.run_id === selected) tr.classList.add('selected');
        const failPolicies = r.failed_policies > 0
          ? `<span style="color:var(--block)">${r.policy_count - r.failed_policies}/${r.policy_count}</span>`
          : `${r.policy_count}/${r.policy_count}`;
        tr.innerHTML = `
          <td style="white-space:nowrap">${fmtTs(r.timestamp)}</td>
          <td><span class="mono" style="font-size:12px;color:var(--text)">${esc(r.workflow)}</span></td>
          <td>${esc(r.user_email)}</td>
          <td>${badge(r.decision)}</td>
          <td>${r.action_count}</td>
          <td>${failPolicies}</td>
          <td><span class="mono">${r.run_id.slice(0,8)}&hellip;</span></td>
        `;
        tr.addEventListener('click', () => openDetail(r.run_id));
        tbody.appendChild(tr);
      }
    }

    // stats bar
    const pass    = all.filter(r => r.decision === 'PASS').length;
    const block   = all.filter(r => r.decision === 'BLOCK').length;
    const partial = all.filter(r => r.decision === 'PARTIAL').length;
    const shownNote = rows.length !== all.length ? `<span class="stat"><span class="stat-n">${rows.length}</span> shown</span>` : '';
    const partialNote = partial > 0 ? `<span class="stat" style="color:var(--partial)"><span class="stat-n">${partial}</span> PARTIAL</span>` : '';
    document.getElementById('stats').innerHTML = `
      <span class="stat"><span class="stat-n">${all.length}</span> total</span>
      <span class="stat" style="color:var(--pass)"><span class="stat-n">${pass}</span> PASS</span>
      <span class="stat" style="color:var(--block)"><span class="stat-n">${block}</span> BLOCK</span>
      ${partialNote}${shownNote}
    `;
  }

  // ---- detail panel ----

  async function openDetail(runId) {
    selected = runId;
    render();
    const panel = document.getElementById('detail');
    panel.classList.add('show');
    document.getElementById('det-body').innerHTML = '<div class="loading">Loading...</div>';

    try {
      const res = await fetch('/api/receipts/' + runId);
      if (!res.ok) { document.getElementById('det-body').innerHTML = '<div class="loading">Failed to load.</div>'; return; }
      const r = await res.json();
      renderDetail(r);
    } catch(e) {
      document.getElementById('det-body').innerHTML = '<div class="loading">Error loading receipt.</div>';
    }
  }

  function renderDetail(r) {
    document.getElementById('det-title').textContent = r.workflow + ' \u2014 ' + r.run_id;

    let sigHtml;
    if      (r.signature_valid === true)  sigHtml = '<span class="sig-ok">Valid \u2014 signature verified</span>';
    else if (r.signature_valid === false) sigHtml = '<span class="sig-bad">Invalid \u2014 receipt may be tampered</span>';
    else                                  sigHtml = '<span class="sig-unk">Not verified (start with --secret to check)</span>';

    const policies = r.policy_results.map(p => `
      <div class="item ${p.passed ? 'item-pass' : 'item-fail'}">
        <div class="item-name">${esc(p.policy)}</div>
        <div class="item-sub">${esc(p.reason)}</div>
      </div>`).join('') || '<div style="color:var(--text-muted);font-size:12px">None</div>';

    const actions = r.actions_taken.length === 0
      ? '<div style="color:var(--text-muted);font-size:12px">No actions taken</div>'
      : r.actions_taken.map(a => `
        <div class="item ${a.success ? 'item-pass' : 'item-fail'}">
          <div class="item-name">${esc(a.system)}.${esc(a.action)}</div>
          <div class="item-sub">${esc(JSON.stringify(a.output))}</div>
        </div>`).join('');

    document.getElementById('det-body').innerHTML = `
      <div>
        <div class="det-section">
          <h4>Run Info</h4>
          <div class="meta-row"><span class="meta-lbl">Run ID</span><span class="meta-val mono">${esc(r.run_id)}</span></div>
          <div class="meta-row"><span class="meta-lbl">Timestamp</span><span class="meta-val">${esc(r.timestamp)}</span></div>
          <div class="meta-row"><span class="meta-lbl">Workflow</span><span class="meta-val mono">${esc(r.workflow)}</span></div>
          <div class="meta-row"><span class="meta-lbl">Actor</span><span class="meta-val">${esc(r.user_email)}</span></div>
          <div class="meta-row"><span class="meta-lbl">Decision</span><span class="meta-val">${badge(r.decision)}</span></div>
          <div class="meta-row"><span class="meta-lbl">Signature</span><span class="meta-val">${sigHtml}</span></div>
        </div>
        <div class="det-section">
          <h4>Payload</h4>
          <pre class="payload">${esc(JSON.stringify(r.payload, null, 2))}</pre>
        </div>
      </div>
      <div>
        <div class="det-section">
          <h4>Policies (${r.policy_results.length})</h4>
          <div class="item-list">${policies}</div>
        </div>
        <div class="det-section">
          <h4>Actions Taken (${r.actions_taken.length})</h4>
          <div class="item-list">${actions}</div>
        </div>
      </div>
    `;
  }

  // ---- helpers ----

  function badge(d) {
    const cls = { PASS: 'badge-pass', BLOCK: 'badge-block', PARTIAL: 'badge-partial' };
    return `<span class="badge ${cls[d] || ''}">${esc(d)}</span>`;
  }

  function fmtTs(iso) {
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    } catch { return iso; }
  }

  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ---- events ----

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filter = btn.dataset.filter;
      render();
    });
  });

  document.getElementById('q').addEventListener('input', render);

  document.getElementById('det-close').addEventListener('click', () => {
    document.getElementById('detail').classList.remove('show');
    selected = null;
    render();
  });

  // Initial load + auto-refresh every 5 s
  load();
  setInterval(load, 5000);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Request handler (factory so directory/secret bind via closure)
# ---------------------------------------------------------------------------


def _make_handler(directory: str, secret):
    """
    Returns a BaseHTTPRequestHandler subclass with directory and secret
    bound via closure. Factory pattern avoids the need for global state or
    monkey-patching the handler's constructor signature.
    """

    class ReceiptBrowserHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path.rstrip("/") or "/"

            if path == "/":
                self._serve_index()
            elif path == "/api/receipts":
                self._serve_list()
            else:
                m = re.match(r"^/api/receipts/([^/]+)$", path)
                if m:
                    self._serve_detail(m.group(1))
                else:
                    self._error(404, "Not found")

        # ------------------------------------------------------------------
        # Route handlers
        # ------------------------------------------------------------------

        def _serve_index(self):
            body = _HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_list(self):
            receipts_path = Path(directory)
            summaries = []

            if receipts_path.exists():
                for json_file in receipts_path.glob("*.json"):
                    try:
                        with open(json_file) as f:
                            data = json.load(f)
                        summaries.append(
                            {
                                "run_id": data.get("run_id", ""),
                                "workflow": data.get("workflow", ""),
                                "user_email": data.get("user_email", ""),
                                "decision": data.get("decision", ""),
                                "timestamp": data.get("timestamp", ""),
                                "action_count": len(data.get("actions_taken", [])),
                                "policy_count": len(data.get("policy_results", [])),
                                "failed_policies": sum(
                                    1
                                    for p in data.get("policy_results", [])
                                    if not p.get("passed", True)
                                ),
                            }
                        )
                    except (json.JSONDecodeError, KeyError, OSError):
                        continue  # skip malformed or unreadable files

            summaries.sort(key=lambda r: r["timestamp"], reverse=True)
            self._json_ok(summaries)

        def _serve_detail(self, run_id: str):
            if not _UUID_PATTERN.match(run_id):
                self._error(400, f"Invalid run_id: {run_id!r}. Must be a UUID.")
                return

            try:
                receipt = load_receipt(run_id, directory=directory)
            except FileNotFoundError:
                self._error(404, f"No receipt found for run_id: {run_id}")
                return

            data = receipt.model_dump()
            data["signature_valid"] = (
                verify_signature(receipt, secret) if secret is not None else None
            )
            self._json_ok(data)

        # ------------------------------------------------------------------
        # Helpers
        # ------------------------------------------------------------------

        def _json_ok(self, payload):
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status: int, message: str):
            body = json.dumps({"error": message}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # suppress default stderr chatter
            pass

    return ReceiptBrowserHandler


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_server(
    directory: str = "receipts",
    port: int = 8765,
    secret=None,
) -> HTTPServer:
    """
    Create (but do not start) the receipt browser HTTPServer.

    Separated from serve() so tests can start and stop the server cleanly
    without having to run it in a separate process.

    Args:
        directory  path to the receipts/ directory to scan
        port       TCP port to listen on
        secret     HMAC secret for signature verification; None = skip verification
    """
    handler = _make_handler(directory, secret)
    return HTTPServer(("127.0.0.1", port), handler)


def serve(
    directory: str = "receipts",
    port: int = 8765,
    secret=None,
) -> None:
    """Start the receipt browser and block until Ctrl+C."""
    httpd = make_server(directory, port, secret)
    print(f"Enact receipt browser  http://127.0.0.1:{port}")
    print(f"Receipts directory:    {os.path.abspath(directory)}")
    if secret:
        print("Signature verification: enabled")
    else:
        print("Signature verification: disabled  (pass --secret to enable)")
    print("Press Ctrl+C to stop.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> None:
    """CLI entrypoint for the `enact-ui` command."""
    parser = argparse.ArgumentParser(
        description="Enact receipt browser — view and filter audit receipts in your browser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Environment variables: ENACT_RECEIPTS_DIR, ENACT_UI_PORT, ENACT_SECRET",
    )
    parser.add_argument(
        "--dir",
        default=os.environ.get("ENACT_RECEIPTS_DIR", "receipts"),
        metavar="PATH",
        help="Directory containing receipt JSON files (default: receipts/)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ENACT_UI_PORT", "8765")),
        help="Port to listen on (default: 8765)",
    )
    parser.add_argument(
        "--secret",
        default=os.environ.get("ENACT_SECRET"),
        metavar="SECRET",
        help="HMAC secret for signature verification (default: $ENACT_SECRET)",
    )
    args = parser.parse_args()
    serve(directory=args.dir, port=args.port, secret=args.secret)


if __name__ == "__main__":
    main()
