/**
 * Ultramen Universal Proxy
 * 
 * Port 4141 — OpenAI-compatible (untuk opencode)
 * Port 4142 — Anthropic-compatible (untuk Claude Code)
 * 
 * Fitur:
 * - Replace system prompt agar tidak kena content filter China
 * - Translate Anthropic Messages API → OpenAI Chat Completions API
 * - Translate response balik ke format Anthropic
 * 
 * Usage: node ultramen-proxy.mjs
 */

import http from 'node:http';
import https from 'node:https';
import crypto from 'node:crypto';

const ULTRAMEN_HOST = 'ultramen.my.id';
const OPENAI_PORT = 4141;
const ANTHROPIC_PORT = 4142;

// System prompt bersih yang tidak akan kena content filter
const CLEAN_SYSTEM_PROMPT = `You are an expert software engineer and coding assistant. Help users with programming tasks including writing code, debugging, explaining concepts, and building projects. Be concise and provide working solutions.`;

// Model mapping: Claude Code model names → Ultramen model names
const MODEL_MAP = {
  'claude-opus-4-7': 'claude-opus-4.6',
  'claude-opus-4.7': 'claude-opus-4.6',
  'claude-sonnet-4-7': 'claude-opus-4.6',
  'claude-sonnet-4.7': 'claude-opus-4.6',
  'claude-opus-4': 'claude-opus-4.6',
  'claude-sonnet-4': 'claude-opus-4.6',
  'claude-3-5-sonnet': 'claude-opus-4.6',
  'claude-3-opus': 'claude-opus-4.6',
  'claude-3.5-sonnet': 'claude-opus-4.6',
};

function mapModel(model) {
  // Direct match
  if (MODEL_MAP[model]) {
    console.log(`  [model] Mapped: ${model} → ${MODEL_MAP[model]}`);
    return MODEL_MAP[model];
  }
  // Partial match - any claude model → claude-opus-4.6
  if (model.startsWith('claude-')) {
    console.log(`  [model] Mapped (fallback): ${model} → claude-opus-4.6`);
    return 'claude-opus-4.6';
  }
  return model;
}

// ============================================================
// Utility Functions
// ============================================================

function makeId() {
  return 'msg_' + crypto.randomBytes(16).toString('hex').slice(0, 24);
}

function httpsPost(path, headers, body, timeoutMs = 120000) {
  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: ULTRAMEN_HOST,
      port: 443,
      path,
      method: 'POST',
      headers,
      timeout: timeoutMs,
    }, resolve);
    req.on('timeout', () => req.destroy(new Error(`Upstream POST timed out after ${timeoutMs}ms`)));
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function httpsGet(path, headers, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: ULTRAMEN_HOST,
      port: 443,
      path,
      method: 'GET',
      headers,
      timeout: timeoutMs,
    }, resolve);
    req.on('timeout', () => req.destroy(new Error(`Upstream GET timed out after ${timeoutMs}ms`)));
    req.on('error', reject);
    req.end();
  });
}

function readBody(req, maxBytes = 50 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let body = '';
    let bytes = 0;
    req.on('data', chunk => {
      bytes += chunk.length;
      if (bytes > maxBytes) {
        req.destroy(new Error('Request body too large'));
        reject(new Error('Request body too large'));
        return;
      }
      body += chunk;
    });
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

// ============================================================
// OpenAI Proxy (Port 4141) — untuk opencode
// ============================================================

function replaceSystemPrompt(messages) {
  if (!Array.isArray(messages)) return messages;
  return messages.map(msg => {
    if (msg.role === 'system') {
      console.log(`  [openai] System prompt replaced (was ${typeof msg.content === 'string' ? msg.content.length : '?'} chars)`);
      return { ...msg, content: CLEAN_SYSTEM_PROMPT };
    }
    return msg;
  });
}

const openaiProxy = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(200, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': '*', 'Access-Control-Allow-Headers': '*' });
    return res.end();
  }

  const body = await readBody(req);
  let modifiedBody = body;

  if (req.url.includes('/chat/completions') && body) {
    try {
      const parsed = JSON.parse(body);
      if (parsed.messages) {
        parsed.messages = replaceSystemPrompt(parsed.messages);
      }
      modifiedBody = JSON.stringify(parsed);
    } catch (e) {
      console.error('  [openai] Parse error:', e.message);
    }
  }

  console.log(`[openai] ${req.method} ${req.url}`);

  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) {
    if (k === 'host' || k === 'connection') continue;
    headers[k] = v;
  }
  headers['content-length'] = Buffer.byteLength(modifiedBody);

  try {
    const proxyRes = await httpsPost(`${req.url}`, headers, modifiedBody);
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  } catch (err) {
    console.error('  [openai] Error:', err.message);
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { message: err.message } }));
  }
});

// ============================================================
// Anthropic → OpenAI Translation (Port 4142) — untuk Claude Code
// ============================================================

function anthropicToOpenAIMessages(system, messages) {
  const result = [];

  result.push({ role: 'system', content: CLEAN_SYSTEM_PROMPT });
  if (system && typeof system === 'string') {
    console.log(`  [anthropic] System prompt replaced (was ${system.length} chars)`);
  } else if (Array.isArray(system)) {
    const totalLen = system.reduce((a, b) => a + (b.text?.length || 0), 0);
    console.log(`  [anthropic] System prompt replaced (was ${totalLen} chars, ${system.length} blocks)`);
  }

  for (const msg of messages) {
    if (msg.role === 'user') {
      if (typeof msg.content === 'string') {
        result.push({ role: 'user', content: msg.content });
        continue;
      }
      if (!Array.isArray(msg.content)) continue;

      const toolResults = msg.content.filter(b => b.type === 'tool_result');
      const textBlocks = msg.content.filter(b => b.type === 'text');
      const imageBlocks = msg.content.filter(b => b.type === 'image');

      for (const tr of toolResults) {
        let content;
        if (typeof tr.content === 'string') {
          content = tr.content;
        } else if (Array.isArray(tr.content)) {
          content = tr.content
            .map(b => b.type === 'text' ? b.text : (b.type === 'image' ? '[image]' : JSON.stringify(b)))
            .join('\n');
        } else {
          content = JSON.stringify(tr.content ?? '');
        }
        if (tr.is_error) content = `[ERROR] ${content}`;

        result.push({
          role: 'tool',
          tool_call_id: tr.tool_use_id,
          content,
        });
      }

      if (imageBlocks.length > 0) {
        const parts = [];
        for (const tb of textBlocks) {
          if (tb.text) parts.push({ type: 'text', text: tb.text });
        }
        for (const ib of imageBlocks) {
          if (ib.source?.type === 'base64') {
            parts.push({
              type: 'image_url',
              image_url: { url: `data:${ib.source.media_type};base64,${ib.source.data}` },
            });
          }
        }
        if (parts.length > 0) {
          result.push({ role: 'user', content: parts });
        }
      } else {
        const textStr = textBlocks.map(b => b.text).filter(Boolean).join('\n');
        if (textStr) {
          result.push({ role: 'user', content: textStr });
        }
      }

    } else if (msg.role === 'assistant') {
      if (typeof msg.content === 'string') {
        result.push({ role: 'assistant', content: msg.content });
        continue;
      }
      if (!Array.isArray(msg.content)) continue;

      const textParts = msg.content.filter(b => b.type === 'text').map(b => b.text);
      const toolCalls = msg.content.filter(b => b.type === 'tool_use');

      const assistantMsg = { role: 'assistant', content: textParts.join('\n') || null };

      if (toolCalls.length > 0) {
        assistantMsg.tool_calls = toolCalls.map(tc => ({
          id: tc.id,
          type: 'function',
          function: {
            name: tc.name,
            arguments: JSON.stringify(tc.input || {}),
          },
        }));
      }
      result.push(assistantMsg);
    }
  }
  return result;
}

function anthropicToOpenAITools(tools) {
  if (!tools || !Array.isArray(tools)) return undefined;
  return tools.map(tool => ({
    type: 'function',
    function: {
      name: tool.name,
      description: tool.description || '',
      parameters: tool.input_schema || { type: 'object', properties: {} }
    }
  }));
}

function safeWrite(res, data) {
  if (!res.writableEnded && !res.destroyed) {
    try { return res.write(data); } catch { return false; }
  }
  return false;
}

function safeEnd(res) {
  if (!res.writableEnded && !res.destroyed) {
    try { res.end(); } catch { /* ignore */ }
  }
}

function createAnthropicStreamTransformer(res, model, requestId) {
  let buffer = '';
  let contentIndex = 0;
  let approxOutputTokens = 0;
  let sentStart = false;
  let sentContentStart = false;
  let hasToolUse = false;
  let pingInterval = null;

  function startPing() {
    pingInterval = setInterval(() => {
      safeWrite(res, `event: ping\ndata: ${JSON.stringify({ type: "ping" })}\n\n`);
    }, 15000);
  }

  function cleanup() {
    if (pingInterval) { clearInterval(pingInterval); pingInterval = null; }
  }

  function finalize(stopReason, tokenCount) {
    cleanup();
    if (sentContentStart) {
      safeWrite(res, `event: content_block_stop\ndata: ${JSON.stringify({ type: "content_block_stop", index: contentIndex })}\n\n`);
    }
    safeWrite(res, `event: message_delta\ndata: ${JSON.stringify({
      type: "message_delta",
      delta: { stop_reason: stopReason, stop_sequence: null },
      usage: { output_tokens: tokenCount }
    })}\n\n`);
    safeWrite(res, `event: message_stop\ndata: ${JSON.stringify({ type: "message_stop" })}\n\n`);
    safeEnd(res);
  }

  startPing();

  return {
    cleanup,
    onData(chunk) {
      buffer += chunk.toString();
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') {
          finalize(hasToolUse ? 'tool_use' : 'end_turn', approxOutputTokens);
          return;
        }

        try {
          const parsed = JSON.parse(data);
          const choice = parsed.choices?.[0];
          if (!choice) continue;

          if (!sentStart) {
            sentStart = true;
            safeWrite(res, `event: message_start\ndata: ${JSON.stringify({
              type: "message_start",
              message: {
                id: requestId,
                type: "message",
                role: "assistant",
                content: [],
                model,
                stop_reason: null,
                stop_sequence: null,
                usage: { input_tokens: parsed.usage?.prompt_tokens || 0, output_tokens: 0, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 }
              }
            })}\n\n`);
          }

          const delta = choice.delta;
          if (!delta) continue;

          if (delta.tool_calls && delta.tool_calls.length > 0) {
            for (const tc of delta.tool_calls) {
              if (tc.function?.name) {
                hasToolUse = true;
                if (sentContentStart) {
                  safeWrite(res, `event: content_block_stop\ndata: ${JSON.stringify({ type: "content_block_stop", index: contentIndex })}\n\n`);
                  contentIndex++;
                }
                safeWrite(res, `event: content_block_start\ndata: ${JSON.stringify({
                  type: "content_block_start",
                  index: contentIndex,
                  content_block: { type: "tool_use", id: tc.id || makeId(), name: tc.function.name, input: {} }
                })}\n\n`);
                sentContentStart = true;
              }
              if (tc.function?.arguments) {
                approxOutputTokens += Math.max(1, Math.ceil(tc.function.arguments.length / 4));
                safeWrite(res, `event: content_block_delta\ndata: ${JSON.stringify({
                  type: "content_block_delta",
                  index: contentIndex,
                  delta: { type: "input_json_delta", partial_json: tc.function.arguments }
                })}\n\n`);
              }
            }
            continue;
          }

          const text = delta.content || '';
          if (text) {
            if (!sentContentStart) {
              sentContentStart = true;
              safeWrite(res, `event: content_block_start\ndata: ${JSON.stringify({
                type: "content_block_start",
                index: contentIndex,
                content_block: { type: "text", text: "" }
              })}\n\n`);
            }
            approxOutputTokens += Math.max(1, Math.ceil(text.length / 4));
            safeWrite(res, `event: content_block_delta\ndata: ${JSON.stringify({
              type: "content_block_delta",
              index: contentIndex,
              delta: { type: "text_delta", text }
            })}\n\n`);
          }

          if (choice.finish_reason === 'stop' || choice.finish_reason === 'tool_calls') {
            const stopReason = choice.finish_reason === 'tool_calls' ? 'tool_use' : 'end_turn';
            finalize(stopReason, parsed.usage?.completion_tokens || approxOutputTokens);
            return;
          }
        } catch {
          // Skip unparseable chunks
        }
      }
    },
    onEnd() {
      if (!res.writableEnded && !res.destroyed) {
        finalize(hasToolUse ? 'tool_use' : 'end_turn', approxOutputTokens);
      } else {
        cleanup();
      }
    },
    onError(err) {
      console.error('  [anthropic] Stream error:', err.message);
      cleanup();
      safeWrite(res, `event: error\ndata: ${JSON.stringify({
        type: "error",
        error: { type: "api_error", message: `Upstream stream error: ${err.message}` }
      })}\n\n`);
      safeEnd(res);
    }
  };
}

// Convert OpenAI non-streaming response to Anthropic format
function openAIToAnthropicResponse(openaiRes, model, requestId) {
  const choice = openaiRes.choices?.[0];
  const message = choice?.message || {};

  const content = [];

  if (message.content) {
    content.push({ type: 'text', text: message.content });
  }

  if (message.tool_calls) {
    for (const tc of message.tool_calls) {
      content.push({
        type: 'tool_use',
        id: tc.id,
        name: tc.function.name,
        input: JSON.parse(tc.function.arguments || '{}')
      });
    }
  }

  return {
    id: requestId,
    type: 'message',
    role: 'assistant',
    content,
    model,
    stop_reason: choice?.finish_reason === 'tool_calls' ? 'tool_use' : 'end_turn',
    stop_sequence: null,
    usage: {
      input_tokens: openaiRes.usage?.prompt_tokens || 0,
      output_tokens: openaiRes.usage?.completion_tokens || 0
    }
  };
}

const anthropicProxy = http.createServer(async (req, res) => {
  // Handle GET /v1/models (for model listing)
  if (req.method === 'GET' && req.url?.startsWith('/v1/models')) {
    console.log(`[anthropic] GET ${req.url}`);
    try {
      const headers = {};
      if (req.headers['x-api-key']) headers['Authorization'] = `Bearer ${req.headers['x-api-key']}`;
      if (req.headers['authorization']) headers['Authorization'] = req.headers['authorization'];
      const proxyRes = await httpsGet(req.url, headers);
      let body = '';
      proxyRes.on('data', c => body += c);
      proxyRes.on('end', () => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(body);
      });
    } catch (err) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: { message: err.message } }));
    }
    return;
  }

  // Only handle POST /v1/messages
  if (req.method !== 'POST' || !req.url?.startsWith('/v1/messages')) {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { type: 'not_found_error', message: `Route ${req.method} ${req.url} not found` } }));
    return;
  }

  const body = await readBody(req);
  let anthropicReq;
  try {
    anthropicReq = JSON.parse(body);
  } catch (e) {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: { type: 'invalid_request_error', message: 'Invalid JSON' } }));
    return;
  }

  const rawModel = anthropicReq.model || 'claude-opus-4.6';
  const model = mapModel(rawModel);
  const isStream = anthropicReq.stream === true;
  const requestId = makeId();

  console.log(`[anthropic] POST /v1/messages model=${model} stream=${isStream}`);

  // Translate to OpenAI format
  const openaiMessages = anthropicToOpenAIMessages(anthropicReq.system, anthropicReq.messages || []);
  const openaiTools = anthropicToOpenAITools(anthropicReq.tools);

  const openaiBody = {
    model,
    messages: openaiMessages,
    stream: isStream,
  };

  if (anthropicReq.max_tokens) openaiBody.max_tokens = anthropicReq.max_tokens;
  if (anthropicReq.temperature !== undefined) openaiBody.temperature = anthropicReq.temperature;
  if (anthropicReq.top_p !== undefined) openaiBody.top_p = anthropicReq.top_p;
  if (openaiTools) openaiBody.tools = openaiTools;
  if (isStream) openaiBody.stream_options = { include_usage: true };

  const openaiBodyStr = JSON.stringify(openaiBody);

  // Get API key from anthropic headers
  const apiKey = req.headers['x-api-key'] || req.headers['authorization']?.replace('Bearer ', '') || '';

  const reqHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${apiKey}`,
    'Content-Length': Buffer.byteLength(openaiBodyStr),
  };

  try {
    const proxyRes = await httpsPost('/v1/chat/completions', reqHeaders, openaiBodyStr);

    if (proxyRes.statusCode !== 200) {
      let errBody = '';
      proxyRes.on('data', c => errBody += c);
      proxyRes.on('end', () => {
        console.error(`  [anthropic] Upstream error ${proxyRes.statusCode}: ${errBody.slice(0, 200)}`);
        res.writeHead(proxyRes.statusCode, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          type: 'error',
          error: { type: 'api_error', message: errBody || 'Upstream error' }
        }));
      });
      return;
    }

    if (isStream) {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'x-request-id': requestId,
        'request-id': requestId,
      });

      const transformer = createAnthropicStreamTransformer(res, model, requestId);

      res.on('close', () => {
        transformer.cleanup();
        proxyRes.destroy();
      });

      proxyRes.on('data', (chunk) => transformer.onData(chunk));
      proxyRes.on('end', () => transformer.onEnd());
      proxyRes.on('error', (err) => transformer.onError(err));
    } else {
      let responseBody = '';
      proxyRes.on('data', c => responseBody += c);
      proxyRes.on('end', () => {
        try {
          const openaiRes = JSON.parse(responseBody);
          const anthropicRes = openAIToAnthropicResponse(openaiRes, model, requestId);
          res.writeHead(200, {
            'Content-Type': 'application/json',
            'x-request-id': requestId,
            'request-id': requestId,
          });
          res.end(JSON.stringify(anthropicRes));
        } catch (e) {
          console.error('  [anthropic] Response parse error:', e.message);
          res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ type: 'error', error: { type: 'api_error', message: 'Failed to parse upstream response' } }));
        }
      });
    }
  } catch (err) {
    console.error('  [anthropic] Error:', err.message);
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ type: 'error', error: { type: 'api_error', message: err.message } }));
  }
});

// ============================================================
// Start both proxies
// ============================================================

openaiProxy.listen(OPENAI_PORT, () => {
  console.log(`\n🔵 OpenAI Proxy    → http://localhost:${OPENAI_PORT}/v1  (untuk opencode)`);
});

anthropicProxy.listen(ANTHROPIC_PORT, () => {
  console.log(`🟣 Anthropic Proxy → http://localhost:${ANTHROPIC_PORT}    (untuk Claude Code)`);
  console.log(`\n📝 System prompt otomatis diganti agar tidak kena content filter`);
  console.log(`\n--- Claude Code Setup ---`);
  console.log(`Tambahkan di settings.json atau environment:`);
  console.log(`  ANTHROPIC_BASE_URL=http://localhost:${ANTHROPIC_PORT}`);
  console.log(`  ANTHROPIC_AUTH_TOKEN=ulm-YOUR_API_KEY`);
  console.log(`-------------------------\n`);
});

let shuttingDown = false;
function gracefulShutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`\n[proxy] ${signal} received, shutting down...`);
  openaiProxy.close(() => console.log('[proxy] OpenAI proxy closed'));
  anthropicProxy.close(() => console.log('[proxy] Anthropic proxy closed'));
  setTimeout(() => { console.log('[proxy] Force exit'); process.exit(0); }, 5000).unref();
}
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
