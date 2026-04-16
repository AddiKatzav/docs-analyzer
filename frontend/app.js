const { useEffect, useRef, useState } = React;

const API_BASE = "/api";

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await res.json() : {};
  if (!res.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function ConfigPage() {
  const [provider, setProvider] = useState("OPENAI");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadStatus() {
    try {
      const data = await api("/config/status");
      setStatus(data);
      if (data.provider) {
        setProvider(data.provider);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function onVerify() {
    setError("");
    setMessage("");
    try {
      await api("/config/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      setMessage("API key verified successfully.");
    } catch (err) {
      setError(err.message);
    }
  }

  async function onSave() {
    setError("");
    setMessage("");
    try {
      await api("/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      setApiKey("");
      setMessage("Configuration saved. Previous key was replaced.");
      await loadStatus();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <h2>LLM Configuration</h2>
      <label>Provider</label>
      <select value={provider} onChange={(e) => setProvider(e.target.value)}>
        <option value="OPENAI">OpenAI</option>
        <option value="CLAUDE">Claude (Anthropic)</option>
      </select>

      <label>API Key</label>
      <input
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="Paste provider API key"
      />

      <div style={{ display: "flex", gap: "8px" }}>
        <button onClick={onVerify}>Verify</button>
        <button className="primary" onClick={onSave}>
          Save
        </button>
      </div>

      {status && (
        <p>
          Current status: <b>{status.configured ? "Configured" : "Not configured"}</b>
          {status.provider ? ` (${status.provider})` : ""}
        </p>
      )}
      {message ? <div className="message success">{message}</div> : null}
      {error ? <div className="message error">{error}</div> : null}
    </div>
  );
}

function RulesPage() {
  const [rules, setRules] = useState([]);
  const [newRule, setNewRule] = useState("");
  const [version, setVersion] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadRules() {
    try {
      const data = await api("/rules");
      setRules(data.rules || []);
      setVersion(data.version || 0);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadRules();
  }, []);

  async function onAddRule() {
    setError("");
    setMessage("");
    if (!newRule.trim()) {
      setError("Rule text is required.");
      return;
    }
    try {
      const data = await api("/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: newRule }),
      });
      setRules(data.rules || []);
      setVersion(data.version);
      setNewRule("");
      setMessage(`Rule added. Global rules version ${data.version} is active.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function onRemoveRule(ruleId) {
    setError("");
    setMessage("");
    try {
      const data = await api(`/rules/${ruleId}`, {
        method: "DELETE",
      });
      setRules(data.rules || []);
      setVersion(data.version);
      setMessage(`Rule removed. Global rules version ${data.version} is active.`);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <h2>Global Rules</h2>
      <p>
        This ruleset is shared by the entire system and applied to every uploaded document.
      </p>
      <label>Add Rule</label>
      <textarea
        value={newRule}
        onChange={(e) => setNewRule(e.target.value)}
        placeholder="Example: Flag any mention of credit card numbers, national IDs, private keys..."
      />
      <button className="primary" onClick={onAddRule}>
        Add Rule
      </button>
      <p>Current version: {version}</p>
      <h3>Active Rules</h3>
      {rules.length === 0 ? <p>No rules defined yet.</p> : null}
      {rules.map((rule) => (
        <div className="rule-row" key={rule.id}>
          <p className="rule-text">{rule.text}</p>
          <button onClick={() => onRemoveRule(rule.id)}>Remove</button>
        </div>
      ))}
      {message ? <div className="message success">{message}</div> : null}
      {error ? <div className="message error">{error}</div> : null}
    </div>
  );
}

function formatSeverity(severity) {
  if (!severity) {
    return "Unknown";
  }
  const value = String(severity).toLowerCase();
  if (value === "high") {
    return "High";
  }
  if (value === "medium") {
    return "Medium";
  }
  if (value === "low") {
    return "Low";
  }
  return String(severity);
}

function AnalyzeResultView({ result }) {
  const analysis = result.analysis || {};
  const compliant = analysis.compliant === true;
  const violations = Array.isArray(analysis.violations) ? analysis.violations : [];
  const summaryText = analysis.summary || (compliant ? "No violations were detected." : "Violations were detected.");
  const highestSeverity = violations.some((v) => String(v?.severity || "").toLowerCase() === "high")
    ? "High"
    : violations.some((v) => String(v?.severity || "").toLowerCase() === "medium")
      ? "Medium"
      : violations.some((v) => String(v?.severity || "").toLowerCase() === "low")
        ? "Low"
        : "None";

  return (
    <section className="analysis-result" aria-label="Compliance assessment report">
      <h3>Compliance Assessment Report</h3>

      <div className={`message ${compliant ? "success" : "error"} report-status`}>
        <b>Overall Decision:</b> {compliant ? "Compliant" : "Non-compliant"}
      </div>

      <p className="report-summary">{summaryText}</p>

      <div className="analysis-meta report-meta">
        <span>
          Findings: <b>{violations.length}</b>
        </span>
        <span>
          Highest Severity: <b>{highestSeverity}</b>
        </span>
      </div>

      <div className="analysis-meta technical-meta">
        <span>
          Run ID: <b>{result.run_id}</b>
        </span>
        <span>
          Provider: <b>{result.provider}</b>
        </span>
        <span>
          Rules Version: <b>{result.rules_version}</b>
        </span>
      </div>

      {!compliant && violations.length > 0 ? (
        <>
          <h4>Findings</h4>
          <div className="violations-list">
            {violations.map((violation, index) => (
              <div className="violation-card" key={`${result.run_id}-${index}`}>
                <div className="violation-top-row">
                  <b>Rule: {violation.rule || "Rule violation"}</b>
                  <span className={`severity-badge severity-${String(violation.severity || "").toLowerCase()}`}>
                    {formatSeverity(violation.severity)}
                  </span>
                </div>
                {violation.explanation ? (
                  <p className="violation-explanation">
                    <b>Why this is an issue:</b> {violation.explanation}
                  </p>
                ) : null}
                {violation.evidence ? (
                  <p className="violation-evidence">
                    <b>Evidence from document:</b> <em>{violation.evidence}</em>
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </>
      ) : null}

      {!compliant && violations.length === 0 ? (
        <p className="muted">
          Violations were flagged, but no detailed violation entries were returned.
        </p>
      ) : null}
    </section>
  );
}

function AnalyzePage() {
  const [files, setFiles] = useState([]);
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [progressText, setProgressText] = useState("");
  const fileInputRef = useRef(null);

  function normalizeDocxFiles(inputFiles) {
    const validFiles = Array.from(inputFiles || []).filter((candidate) =>
      String(candidate?.name || "").toLowerCase().endsWith(".docx")
    );
    const dedupedByName = new Map(validFiles.map((candidate) => [candidate.name, candidate]));
    return Array.from(dedupedByName.values());
  }

  function onFileInputChange(event) {
    const selectedFiles = normalizeDocxFiles(event.target.files);
    setFiles(selectedFiles);
    setResults([]);
    setError(
      selectedFiles.length > 0 ? "" : "Please select at least one .docx file."
    );
  }

  function onChooseFilesClick() {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  }

  function onDrop(event) {
    event.preventDefault();
    setDragActive(false);
    const droppedFiles = normalizeDocxFiles(event.dataTransfer?.files);
    setFiles(droppedFiles);
    setResults([]);
    setError(droppedFiles.length > 0 ? "" : "Only .docx files are supported.");
  }

  function onDragOver(event) {
    event.preventDefault();
    if (!dragActive) {
      setDragActive(true);
    }
  }

  function onDragLeave(event) {
    event.preventDefault();
    setDragActive(false);
  }

  async function onAnalyze() {
    if (files.length === 0) {
      setError("Choose one or more .docx files first.");
      return;
    }
    setError("");
    setResults([]);
    setLoading(true);
    try {
      setProgressText(`Uploading ${files.length} file${files.length === 1 ? "" : "s"}...`);
      const formData = new FormData();
      for (const selectedFile of files) {
        formData.append("files", selectedFile);
      }
      const response = await api("/analyze/bulk", { method: "POST", body: formData });
      const completedResults = (response.items || []).map((item) => ({
        fileName: item.file_name,
        ok: item.ok === true,
        data: item.result || null,
        error: item.error || "Analysis failed",
      }));
      setResults(completedResults);
      if (completedResults.every((item) => !item.ok)) {
        setError("All files failed analysis. Check per-file errors below.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setProgressText("");
    }
  }

  return (
    <div className="card">
      <h2>Upload & Analyze</h2>
      <label>DOCX Files</label>
      <input
        ref={fileInputRef}
        type="file"
        accept=".docx"
        multiple
        onChange={onFileInputChange}
        style={{ display: "none" }}
      />
      <div
        className={`drop-zone ${dragActive ? "drag-active" : ""}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        <p>Drag and drop .docx files here, or</p>
        <button type="button" onClick={onChooseFilesClick}>
          Browse Files
        </button>
      </div>
      {files.length > 0 ? (
        <div className="selected-files">
          <p>
            Selected files: <b>{files.length}</b>
          </p>
          {files.map((selectedFile) => (
            <p key={selectedFile.name} className="muted selected-file-name">
              {selectedFile.name}
            </p>
          ))}
        </div>
      ) : null}
      <button className="primary" onClick={onAnalyze} disabled={loading}>
        {loading ? "Analyzing..." : `Analyze ${files.length || 0} Document${files.length === 1 ? "" : "s"}`}
      </button>
      {loading && progressText ? <p className="muted">{progressText}</p> : null}

      {error ? <div className="message error">{error}</div> : null}
      {results.length > 0 ? (
        <div className="bulk-results">
          <p>
            Completed: <b>{results.filter((item) => item.ok).length}</b> / {results.length}
          </p>
          {results.map((item) =>
            item.ok ? (
              <div key={item.data?.run_id || item.fileName} className="card">
                <p className="muted">File: {item.fileName}</p>
                <AnalyzeResultView result={item.data} />
              </div>
            ) : (
              <div key={item.fileName} className="message error">
                <b>{item.fileName}</b>: {item.error}
              </div>
            )
          )}
        </div>
      ) : null}
    </div>
  );
}

function HistoryPage() {
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState("");

  async function loadRuns() {
    setError("");
    try {
      const data = await api("/runs");
      setRuns(data);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadRuns();
  }, []);

  return (
    <div className="card">
      <h2>Analysis History</h2>
      <button onClick={loadRuns}>Refresh</button>
      {error ? <div className="message error">{error}</div> : null}
      {runs.length === 0 ? <p>No analysis runs yet.</p> : null}
      {runs.map((run) => (
        <div key={run.run_id} className="card">
          <b>{run.file_name}</b>
          <p>
            Run: {run.run_id} | Provider: {run.provider} | Rules Version: {run.rules_version}
          </p>
          <small>{new Date(run.created_at).toLocaleString()}</small>
        </div>
      ))}
    </div>
  );
}

function App() {
  const [tab, setTab] = useState("config");

  return (
    <div className="container">
      <h1>Global Rules DOCX Analyzer</h1>
      <div className="tabs">
        <button className={tab === "config" ? "active" : ""} onClick={() => setTab("config")}>
          Config
        </button>
        <button className={tab === "rules" ? "active" : ""} onClick={() => setTab("rules")}>
          Rules
        </button>
        <button className={tab === "analyze" ? "active" : ""} onClick={() => setTab("analyze")}>
          Analyze
        </button>
        <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>
          History
        </button>
      </div>

      {tab === "config" ? <ConfigPage /> : null}
      {tab === "rules" ? <RulesPage /> : null}
      {tab === "analyze" ? <AnalyzePage /> : null}
      {tab === "history" ? <HistoryPage /> : null}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
