import DocsLayout from '../components/DocsLayout';

export default function Environment() {
  return (
    <DocsLayout
      title="Environment"
      description="Configuration guidance for runtime settings, API keys, and local development environment values."
    >
      <section>
        <h2>Environment File</h2>
        <p>Copy <code>.env.example</code> to <code>.env</code> and set the values needed for your local setup.</p>
        <pre>
          <code>copy .env.example .env</code>
        </pre>
        <p>Common values include:</p>
        <ul>
          <li><code>user_name</code>: local personalization token</li>
          <li><code>luna_api_key</code>: API key for remote browser access and networked devices</li>
          <li><code>llm_provider</code>: <code>ollama</code> or <code>openai-compatible</code></li>
          <li><code>ollama_base_url</code>: local Ollama server URL</li>
          <li><code>ollama_model</code>: your default chat model</li>
        </ul>
      </section>

      <section>
        <h2>Provider Configuration</h2>
        <p>If you use cloud or self-hosted models, set:</p>
        <pre>
          <code>llm_provider=openai-compatible
openai_base_url=https://your-openai-compatible-server
openai_api_key=YOUR_API_KEY
openai_model=gpt-4o-mini</code>
        </pre>
        <p>For embeddings use:</p>
        <pre>
          <code>embedding_provider=openai-compatible</code>
        </pre>
      </section>

      <section>
        <h2>Optional Keys</h2>
        <p>The repo supports optional external services if configured:</p>
        <ul>
          <li><code>the_news_api</code> — live news provider</li>
          <li><code>alpha_vantage</code> — markets and finance data</li>
          <li><code>open_weather</code> — weather provider fallback</li>
        </ul>
        <p>Weather works by default with Open-Meteo and does not require an API key.</p>
      </section>
    </DocsLayout>
  );
}
