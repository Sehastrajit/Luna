import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'auth',       label: 'Authentication' },
  { id: 'chat',       label: 'Chat' },
  { id: 'memory',     label: 'Memory' },
  { id: 'voice',      label: 'Voice' },
  { id: 'vision',     label: 'Vision' },
  { id: 'agent',      label: 'Agent' },
  { id: 'system',     label: 'System' },
  { id: 'luna',       label: 'Luna dashboard' },
  { id: 'calendar',   label: 'Calendar' },
  { id: 'spotify',    label: 'Spotify' },
  { id: 'errors',     label: 'Error format' },
];

export default function APIReference() {
  return (
    <DocsLayout
      title="API Reference"
      description="Full HTTP endpoint documentation for every Luna router — request shapes, response shapes, and SSE event protocol."
      toc={toc}
    >
      <section>
        <h2 id="auth">Authentication</h2>
        <p>
          All routes are unauthenticated by default. If you set <code>luna_api_key</code> in your
          <code>.env</code>, every request must include the header:
        </p>
        <CodeFile label="header">
          <pre><code>{`X-Luna-Key: <your-api-key>`}</code></pre>
        </CodeFile>
        <p>
          Requests missing the header return <code>401 Unauthorized</code>. The key is only checked
          when <code>luna_api_key</code> is non-empty in config — omit it for local development.
        </p>

        <Callout type="info" title="Base URL">
          <p>All routes are relative to <code>http://localhost:8899</code>. In Electron builds this
          is accessed via the <code>electronAPI.apiBase</code> bridge value.</p>
        </Callout>
      </section>

      <section>
        <h2 id="chat">Chat</h2>

        <h3>Stream a message — <code>GET /api/chat/stream</code></h3>
        <p>Primary chat endpoint. Returns a Server-Sent Events stream.</p>

        <table>
          <thead><tr><th>Parameter</th><th>Type</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>message</code></td><td>string (query)</td><td>The user's message text.</td></tr>
            <tr><td><code>conversation_id</code></td><td>UUID (query, optional)</td><td>Resumes an existing conversation. Omit to start a new one.</td></tr>
            <tr><td><code>mode</code></td><td>string (query)</td><td><code>chat</code> (default) or <code>voice</code>.</td></tr>
          </tbody>
        </table>

        <h4>SSE event types</h4>
        <table>
          <thead><tr><th>Event</th><th>Data shape</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>metadata</code></td><td><code>{'{"conversation_id":"…","model":"…"}'}</code></td><td>Sent first. Carries the conversation ID and model name.</td></tr>
            <tr><td><code>token</code></td><td><code>{'{"text":"…"}'}</code></td><td>One streamed token from the LLM.</td></tr>
            <tr><td><code>command</code></td><td><code>{'{"tool":"…","input":{…}}'}</code></td><td>Luna is about to call a tool. Shown in the UI as a bracket tag.</td></tr>
            <tr><td><code>confirmation</code></td><td><code>{'{"request_id":"…","tool":"…","input":{…}}'}</code></td><td>Tool is in <code>confirm</code> mode — stream pauses. Send approval to <code>POST /api/chat/confirm</code>.</td></tr>
            <tr><td><code>done</code></td><td><code>{'{"conversation_id":"…"}'}</code></td><td>Stream complete. Safe to close the connection.</td></tr>
            <tr><td><code>error</code></td><td><code>{'{"message":"…"}'}</code></td><td>A non-recoverable error occurred.</td></tr>
          </tbody>
        </table>

        <CodeFile label="example">
          <pre><code>{`# Basic chat message
curl "http://localhost:8899/api/chat/stream?message=Hello+Luna" \\
  -H "Accept: text/event-stream"

# Resume a conversation
curl "http://localhost:8899/api/chat/stream?message=Tell+me+more&conversation_id=<uuid>" \\
  -H "Accept: text/event-stream"`}</code></pre>
        </CodeFile>

        <h3>Confirm a tool call — <code>POST /api/chat/confirm</code></h3>
        <p>Approves or rejects a tool call that emitted a <code>confirmation</code> event.</p>
        <CodeFile label="request body">
          <pre><code>{`{
  "request_id": "<uuid from confirmation event>",
  "approved": true
}`}</code></pre>
        </CodeFile>

        <h3>List conversations — <code>GET /api/chat/conversations</code></h3>
        <p>Returns all conversations ordered by last activity, newest first.</p>
        <CodeFile label="response">
          <pre><code>{`[
  {
    "id": "uuid",
    "title": "Conversation title (auto-generated)",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T11:00:00Z",
    "message_count": 14
  }
]`}</code></pre>
        </CodeFile>

        <h3>Get conversation messages — <code>GET /api/chat/conversations/{id}/messages</code></h3>
        <p>Returns all messages in a conversation, ordered oldest first.</p>
        <CodeFile label="response">
          <pre><code>{`[
  {
    "id": "uuid",
    "role": "user" | "assistant",
    "content": "message text",
    "created_at": "2024-01-15T10:30:00Z"
  }
]`}</code></pre>
        </CodeFile>

        <h3>Delete a conversation — <code>DELETE /api/chat/conversations/{id}</code></h3>
        <p>Permanently deletes the conversation and all its messages. Returns <code>204 No Content</code>.</p>

        <h3>Get proactive message — <code>GET /api/chat/proactive</code></h3>
        <p>Returns a pending unsolicited message from Luna (if any), and clears it from the queue.</p>
        <CodeFile label="response">
          <pre><code>{`{ "message": "Hey, your standup is in 10 minutes." }
// or
{ "message": null }`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="memory">Memory</h2>

        <h3>List facts — <code>GET /api/memory/facts</code></h3>
        <p>Returns all stored facts ordered by <code>last_accessed</code> descending.</p>
        <CodeFile label="response">
          <pre><code>{`[
  {
    "id": "uuid",
    "content": "user prefers dark mode interfaces",
    "confidence": 0.92,
    "created_at": "2024-01-10T09:00:00Z",
    "last_accessed": "2024-01-15T10:45:00Z"
  }
]`}</code></pre>
        </CodeFile>

        <h3>Add a fact — <code>POST /api/memory/facts</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{
  "content": "user is vegetarian",
  "confidence": 0.95
}`}</code></pre>
        </CodeFile>

        <h3>Delete a fact — <code>DELETE /api/memory/facts/{id}</code></h3>
        <p>Returns <code>204 No Content</code>.</p>

        <h3>Semantic search — <code>POST /api/memory/search</code></h3>
        <p>Runs a cosine similarity search against the ChromaDB embedding index.</p>
        <CodeFile label="request body">
          <pre><code>{`{
  "query": "food preferences",
  "limit": 5
}`}</code></pre>
        </CodeFile>
        <CodeFile label="response">
          <pre><code>{`[
  { "id": "uuid", "content": "user is vegetarian", "score": 0.91 },
  { "id": "uuid", "content": "user doesn't like spicy food", "score": 0.87 }
]`}</code></pre>
        </CodeFile>

        <h3>Get personality state — <code>GET /api/memory/personality</code></h3>
        <CodeFile label="response">
          <pre><code>{`{
  "mood": 0.4,
  "energy": 0.7,
  "formality": 0.3,
  "humor": 0.6,
  "emotional_support": 0.5
}`}</code></pre>
        </CodeFile>

        <h3>Update personality — <code>PUT /api/memory/personality</code></h3>
        <p>Partial updates are supported — send only the dimensions you want to change.</p>
        <CodeFile label="request body">
          <pre><code>{`{ "humor": 0.8, "formality": 0.2 }`}</code></pre>
        </CodeFile>

        <h3>Trigger compaction — <code>POST /api/memory/compact</code></h3>
        <p>Manually triggers conversation compaction. Normally runs automatically via the
        <code>memory_maintenance</code> background process.</p>
      </section>

      <section>
        <h2 id="voice">Voice</h2>

        <h3>Transcribe audio — <code>POST /api/voice/transcribe</code></h3>
        <p>Accepts a WAV audio blob and returns a transcription.</p>
        <CodeFile label="request">
          <pre><code>{`Content-Type: multipart/form-data
Body: file=<wav blob>`}</code></pre>
        </CodeFile>
        <CodeFile label="response">
          <pre><code>{`{ "text": "What's the weather like today?" }`}</code></pre>
        </CodeFile>

        <h3>Synthesise speech — <code>POST /api/voice/speak</code></h3>
        <p>Converts text to speech and plays it through the system audio output. Returns when playback is complete.</p>
        <CodeFile label="request body">
          <pre><code>{`{ "text": "The weather today is sunny and 22 degrees." }`}</code></pre>
        </CodeFile>

        <h3>Get voice status — <code>GET /api/voice/status</code></h3>
        <CodeFile label="response">
          <pre><code>{`{
  "wake_word_enabled": true,
  "listening": false,
  "tts_speaking": false,
  "stt_model": "base",
  "tts_rate": 150
}`}</code></pre>
        </CodeFile>

        <h3>Detect emotion — <code>POST /api/voice/emotion</code></h3>
        <p>Analyses an audio blob for emotional tone. Returns a label and confidence score.</p>
        <CodeFile label="response">
          <pre><code>{`{
  "emotion": "neutral",
  "confidence": 0.78,
  "scores": { "neutral": 0.78, "happy": 0.14, "sad": 0.05, "angry": 0.03 }
}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="vision">Vision</h2>

        <h3>Capture screen — <code>POST /api/vision/screen</code></h3>
        <p>Takes a screenshot, sends it to the vision model, and returns a natural language description.</p>
        <CodeFile label="response">
          <pre><code>{`{ "description": "The screen shows a code editor with a Python file open…" }`}</code></pre>
        </CodeFile>

        <h3>Capture camera — <code>POST /api/vision/camera</code></h3>
        <p>Captures a frame from the default camera and returns a description.</p>

        <Callout type="warn" title="Permission required">
          <p>Both vision routes require the <code>vision</code> tool permission to be set to
          <code>allow</code> or <code>confirm</code>. They default to <code>confirm</code>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="agent">Agent</h2>

        <h3>List skills — <code>GET /api/agent/skills</code></h3>
        <CodeFile label="response">
          <pre><code>{`[
  {
    "name": "web-search",
    "version": "1.0.0",
    "description": "Search the web using DuckDuckGo.",
    "commands": ["web_search"]
  }
]`}</code></pre>
        </CodeFile>

        <h3>Get permissions — <code>GET /api/agent/permissions</code></h3>
        <p>Returns the current permission mode for every registered tool.</p>
        <CodeFile label="response">
          <pre><code>{`{
  "web_search": "allow",
  "write_file": "confirm",
  "launch_app": "confirm",
  "browser_open": "block"
}`}</code></pre>
        </CodeFile>

        <h3>Update permission — <code>POST /api/agent/permissions/{tool_name}</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{ "mode": "allow" | "confirm" | "block" }`}</code></pre>
        </CodeFile>

        <h3>List workspace files — <code>GET /api/agent/workspace</code></h3>
        <CodeFile label="response">
          <pre><code>{`[
  { "path": "notes/ideas.md", "size": 1240, "modified": "2024-01-15T10:00:00Z" },
  { "path": "research/competitors.txt", "size": 4820, "modified": "2024-01-14T09:30:00Z" }
]`}</code></pre>
        </CodeFile>

        <h3>Read workspace file — <code>GET /api/agent/workspace/read</code></h3>
        <table>
          <thead><tr><th>Parameter</th><th>Type</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>path</code></td><td>string (query)</td><td>Relative path within <code>data/workspace/</code>.</td></tr>
          </tbody>
        </table>

        <h3>Write workspace file — <code>POST /api/agent/workspace/write</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{ "path": "notes/ideas.md", "content": "# Ideas\n…" }`}</code></pre>
        </CodeFile>

        <h3>List tasks — <code>GET /api/agent/tasks</code></h3>
        <CodeFile label="response">
          <pre><code>{`[
  {
    "id": "uuid",
    "title": "Research competitors",
    "status": "in_progress",
    "steps": 5,
    "completed_steps": 2,
    "created_at": "2024-01-15T09:00:00Z"
  }
]`}</code></pre>
        </CodeFile>

        <h3>Create task — <code>POST /api/agent/tasks</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{
  "title": "Research competitors",
  "description": "Find the top 5 competitors to Notion and summarise their pricing."
}`}</code></pre>
        </CodeFile>

        <h3>Browser status — <code>GET /api/agent/browser/status</code></h3>
        <CodeFile label="response">
          <pre><code>{`{ "playwright_available": true, "active_page": null }`}</code></pre>
        </CodeFile>

        <h3>Audit log — <code>GET /api/agent/audit</code></h3>
        <p>Returns the last 100 audit log entries. Each entry is a JSON object.</p>
        <CodeFile label="response item">
          <pre><code>{`{
  "ts": "2024-01-15T10:45:22Z",
  "tool": "web_search",
  "input": { "query": "Luna AI competitor analysis" },
  "mode": "allow",
  "result": "ok",
  "summary": "Returned 5 results"
}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="system">System</h2>

        <h3>Health check — <code>GET /health</code></h3>
        <CodeFile label="response">
          <pre><code>{`{ "status": "ok", "version": "1.0.0", "uptime_seconds": 3620 }`}</code></pre>
        </CodeFile>

        <h3>Background processes — <code>GET /api/system/processes</code></h3>
        <p>Returns all registered background processes and their current status.</p>
        <CodeFile label="response">
          <pre><code>{`[
  { "name": "memory_maintenance", "status": "running", "last_run": "2024-01-15T10:40:00Z" },
  { "name": "proactive_followups", "status": "running", "last_run": "2024-01-15T10:35:00Z" },
  { "name": "calendar_reminders", "status": "running", "last_run": "2024-01-15T10:30:00Z" },
  { "name": "voice_runtime", "status": "stopped", "last_run": null }
]`}</code></pre>
        </CodeFile>

        <h3>Launch application — <code>POST /api/system/launch</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{ "app": "notepad" }`}</code></pre>
        </CodeFile>

        <h3>Generate 3D scene — <code>POST /api/system/scene</code></h3>
        <p>Asks the LLM to generate a Three.js scene description for the dynamic overlay.</p>
        <CodeFile label="request body">
          <pre><code>{`{ "prompt": "A calm ocean at night with stars" }`}</code></pre>
        </CodeFile>

        <h3>Get app state — <code>GET /api/state</code></h3>
        <p>Returns the persisted UI state (sidebar view, active conversation, etc.).</p>

        <h3>Set app state — <code>PUT /api/state</code></h3>
        <p>Persists UI state across sessions.</p>
      </section>

      <section>
        <h2 id="luna">Luna dashboard</h2>

        <h3>Dashboard summary — <code>GET /api/luna/dashboard</code></h3>
        <p>Returns aggregated weather, market, and news data in a single call.</p>
        <CodeFile label="response">
          <pre><code>{`{
  "weather": {
    "temperature": 22.4,
    "condition": "partly cloudy",
    "humidity": 58,
    "wind_kph": 14
  },
  "markets": [
    { "symbol": "SPY", "price": 521.40, "change_pct": 0.32 }
  ],
  "news": [
    { "title": "…", "source": "BBC", "url": "…", "published_at": "2024-01-15T08:00:00Z" }
  ]
}`}</code></pre>
        </CodeFile>

        <h3>Weather — <code>GET /api/luna/weather</code></h3>
        <p>Returns current conditions from Open-Meteo. No API key required.</p>

        <h3>Markets — <code>GET /api/luna/markets</code></h3>
        <p>Returns configured stock and crypto quotes. Requires <code>alpha_vantage_key</code> in
        <code>.env</code> for equities.</p>

        <h3>News — <code>GET /api/luna/news</code></h3>
        <p>Returns recent headlines. Requires <code>news_api_key</code> for TheNewsAPI.</p>
      </section>

      <section>
        <h2 id="calendar">Calendar</h2>

        <h3>List tasks — <code>GET /api/calendar/tasks</code></h3>
        <h3>Create task — <code>POST /api/calendar/tasks</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{
  "title": "Finish PR review",
  "due_date": "2024-01-16T17:00:00Z",
  "priority": "high"
}`}</code></pre>
        </CodeFile>
        <h3>Update task — <code>PUT /api/calendar/tasks/{id}</code></h3>
        <h3>Delete task — <code>DELETE /api/calendar/tasks/{id}</code></h3>

        <h3>List events — <code>GET /api/calendar/events</code></h3>
        <h3>Create event — <code>POST /api/calendar/events</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{
  "title": "Design team standup",
  "start": "2024-01-16T10:00:00Z",
  "end":   "2024-01-16T10:30:00Z",
  "recurrence": "weekly"
}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="spotify">Spotify</h2>

        <Callout type="note" title="OAuth required">
          <p>Spotify routes require completing the OAuth flow at
          <code>GET /api/spotify/login</code> first. See the <a href="/environment#spotify" style={{color:'#7c3aed'}}>Environment</a> page
          for setup instructions.</p>
        </Callout>

        <h3>Login — <code>GET /api/spotify/login</code></h3>
        <p>Redirects to Spotify's OAuth authorisation page.</p>

        <h3>Playback state — <code>GET /api/spotify/status</code></h3>
        <CodeFile label="response">
          <pre><code>{`{
  "is_playing": true,
  "track": "Midnight City",
  "artist": "M83",
  "album": "Hurry Up, We're Dreaming",
  "progress_ms": 84000,
  "duration_ms": 243733
}`}</code></pre>
        </CodeFile>

        <h3>Play / pause — <code>POST /api/spotify/play</code> / <code>POST /api/spotify/pause</code></h3>
        <h3>Skip track — <code>POST /api/spotify/next</code></h3>
        <h3>Previous track — <code>POST /api/spotify/previous</code></h3>
        <h3>Set volume — <code>POST /api/spotify/volume</code></h3>
        <CodeFile label="request body">
          <pre><code>{`{ "volume_percent": 60 }`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="errors">Error format</h2>
        <p>All error responses use a consistent JSON envelope:</p>
        <CodeFile label="error response">
          <pre><code>{`{
  "detail": "Human-readable error description."
}`}</code></pre>
        </CodeFile>

        <table>
          <thead><tr><th>Status</th><th>Meaning</th></tr></thead>
          <tbody>
            <tr><td><code>400</code></td><td>Bad request — missing or invalid parameter.</td></tr>
            <tr><td><code>401</code></td><td>Unauthorized — missing or incorrect <code>X-Luna-Key</code> header.</td></tr>
            <tr><td><code>403</code></td><td>Forbidden — tool is blocked by permission policy.</td></tr>
            <tr><td><code>404</code></td><td>Not found — resource does not exist.</td></tr>
            <tr><td><code>500</code></td><td>Internal server error — check the FastAPI logs.</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/architecture',      label: 'Deep dive', title: 'Architecture',      desc: 'How the SSE stream, tool permission system, and memory layers connect.' },
        { href: '/agent',             label: 'Feature',   title: 'Agent & Skills',    desc: 'Extend the API with custom tools and skills.' },
        { href: '/troubleshooting',   label: 'Support',   title: 'Troubleshooting',   desc: 'Fix common API, port, and backend issues.' },
      ]} />
    </DocsLayout>
  );
}
