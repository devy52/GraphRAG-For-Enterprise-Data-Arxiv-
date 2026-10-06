/**
 * Enterprise GraphRAG — Material 3 Client Application
 * Zero-Node.js vanilla ES6 architecture connecting to FastAPI backend
 */

// ==============================================================================
// State & Configuration
// ==============================================================================
const state = {
  activeView: 'chat-view',
  sessionId: sessionStorage.getItem('graphrag_session_id') || ('session_' + Math.random().toString(36).substring(2, 9)),
  serverBootId: null,
  chatHistory: JSON.parse(sessionStorage.getItem('graphrag_chat_history') || '[]'),
  isDarkTheme: true,
  graphData: { nodes: [], edges: [] },
  networkInstance: null,
  activeFilter: 'all',
};

// Ontology Colors (Material 3 Palette)
const ONTOLOGY_COLORS = {
  Paper: '#42A5F5',
  Method: '#AB47BC',
  Dataset: '#FFA726',
  Author: '#66BB6A',
  Topic: '#FF7043',
  Institution: '#26C6DA',
  Default: '#D0BCFF',
};

// ==============================================================================
// DOM Element Selectors
// ==============================================================================
const elements = {
  navRail: document.getElementById('nav-rail'),
  destinations: document.querySelectorAll('.rail-destination'),
  viewportSections: document.querySelectorAll('.viewport-section'),
  themeToggleBtn: document.getElementById('theme-toggle-btn'),
  themeIcon: document.getElementById('theme-icon'),
  
  // Health & Stats
  postgresStatus: document.getElementById('postgres-status'),
  neo4jStatus: document.getElementById('neo4j-status'),
  cacheStatText: document.getElementById('cache-stat-text'),
  
  // Chat
  chatMessages: document.getElementById('chat-messages'),
  queryInput: document.getElementById('query-input'),
  sendBtn: document.getElementById('send-btn'),
  cacheToggle: document.getElementById('cache-toggle'),
  clearChatBtn: document.getElementById('clear-chat-btn'),
  exportChatBtn: document.getElementById('export-chat-btn'),
  sessionIdLabel: document.getElementById('session-id-label'),
  welcomeCard: document.getElementById('welcome-card'),
  
  // Graph Canvas
  visCanvas: document.getElementById('vis-network-canvas'),
  graphSearchInput: document.getElementById('graph-search-input'),
  filterChips: document.querySelectorAll('.m3-filter-chip'),
  topologyCounter: document.getElementById('topology-counter'),
  refreshGraphBtn: document.getElementById('refresh-graph-btn'),
  fitGraphBtn: document.getElementById('fit-graph-btn'),
  nodeInspector: document.getElementById('node-inspector'),
  closeInspectorBtn: document.getElementById('close-inspector-btn'),
  inspectorName: document.getElementById('inspector-name'),
  inspectorType: document.getElementById('inspector-type'),
  inspectorAliases: document.getElementById('inspector-aliases'),
  inspectorEdges: document.getElementById('inspector-edges'),
  queryEntityBtn: document.getElementById('query-entity-btn'),
  
  // Citation Dialog
  citationDialog: document.getElementById('citation-dialog'),
  closeDialogBtn: document.getElementById('close-dialog-btn'),
  dialogDoneBtn: document.getElementById('dialog-done-btn'),
  dialogChunkId: document.getElementById('dialog-chunk-id'),
  dialogPaperTitle: document.getElementById('dialog-paper-title'),
  dialogSectionPath: document.getElementById('dialog-section-path'),
  dialogDocId: document.getElementById('dialog-doc-id'),
  dialogPassageText: document.getElementById('dialog-passage-text'),
  dialogEntitiesChips: document.getElementById('dialog-entities-chips'),
  
  // Telemetry Dashboard
  tPostgresBadge: document.getElementById('t-postgres-badge'),
  tNeo4jBadge: document.getElementById('t-neo4j-badge'),
  tHitRate: document.getElementById('t-hit-rate'),
  tTotalQueries: document.getElementById('t-total-queries'),
  tHitsMisses: document.getElementById('t-hits-misses'),
  tCachedCount: document.getElementById('t-cached-count'),
  tAttribution: document.getElementById('t-attribution'),
  tPostgresTarget: document.getElementById('t-postgres-target'),
  tNeo4jTarget: document.getElementById('t-neo4j-target'),
  tEmbeddingDim: document.getElementById('t-embedding-dim'),
  tGatewayTitle: document.getElementById('t-gateway-title'),
  tModelExtraction: document.getElementById('t-model-extraction'),
  tModelRouter: document.getElementById('t-model-router'),
  tModelSynthesis: document.getElementById('t-model-synthesis'),
  tModelEmbedding: document.getElementById('t-model-embedding'),

  // Ingestion Modal
  openIngestDialogBtn: document.getElementById('open-ingest-dialog-btn'),
  ingestModalScrim: document.getElementById('ingest-modal-scrim'),
  closeIngestDialogBtn: document.getElementById('close-ingest-dialog-btn'),
  cancelIngestBtn: document.getElementById('cancel-ingest-btn'),
  startIngestBtn: document.getElementById('start-ingest-btn'),
  modeExisting: document.getElementById('mode-existing'),
  modeHarvest: document.getElementById('mode-harvest'),
  harvestParamsGroup: document.getElementById('harvest-params-group'),
  ingestQueryInput: document.getElementById('ingest-query-input'),
  ingestPaperLimit: document.getElementById('ingest-paper-limit'),
  ingestChunkLimit: document.getElementById('ingest-chunk-limit'),
  ingestPopNeo4j: document.getElementById('ingest-pop-neo4j'),
  ingestPopVector: document.getElementById('ingest-pop-vector'),
  ingestTelemetryPanel: document.getElementById('ingest-telemetry-panel'),
  ingestStageBadge: document.getElementById('ingest-stage-badge'),
  ingestStatusMessage: document.getElementById('ingest-status-message'),
  ingestStatusPct: document.getElementById('ingest-status-pct'),
  ingestProgressBar: document.getElementById('ingest-progress-bar'),
  ingestLogTerminal: document.getElementById('ingest-log-terminal'),
};

// ==============================================================================
// Initialization
// ==============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNavigation();
  initChat();
  initGraphExplorer();
  initCitationDialog();
  initIngestDialog();
  pollTelemetry();
  setInterval(pollTelemetry, 8000); // Live poll every 8 seconds
});

// ==============================================================================
// 1. Theme Management (Material 3 Dark/Light)
// ==============================================================================
function initTheme() {
  const saved = localStorage.getItem('graphrag_theme');
  state.isDarkTheme = saved !== 'light';
  applyTheme();

  elements.themeToggleBtn.addEventListener('click', () => {
    state.isDarkTheme = !state.isDarkTheme;
    localStorage.setItem('graphrag_theme', state.isDarkTheme ? 'dark' : 'light');
    applyTheme();
    if (state.networkInstance) {
      updateGraphColors();
    }
  });
}

function applyTheme() {
  if (state.isDarkTheme) {
    document.body.classList.remove('m3-light-theme');
    document.body.classList.add('m3-dark-theme');
    elements.themeIcon.textContent = 'light_mode';
  } else {
    document.body.classList.remove('m3-dark-theme');
    document.body.classList.add('m3-light-theme');
    elements.themeIcon.textContent = 'dark_mode';
  }
}

// ==============================================================================
// 2. Navigation Rail
// ==============================================================================
function initNavigation() {
  elements.destinations.forEach(dest => {
    dest.addEventListener('click', () => {
      const targetView = dest.getAttribute('data-view');
      switchView(targetView);
    });
  });
}

function switchView(viewId) {
  state.activeView = viewId;
  
  elements.destinations.forEach(d => {
    if (d.getAttribute('data-view') === viewId) {
      d.classList.add('active');
    } else {
      d.classList.remove('active');
    }
  });

  elements.viewportSections.forEach(s => {
    if (s.id === viewId) {
      s.classList.add('active');
    } else {
      s.classList.remove('active');
    }
  });

  // If entering Graph View for the first time or resize, redraw canvas
  if (viewId === 'graph-view') {
    if (!state.networkInstance) {
      fetchAndRenderGraph();
    } else {
      setTimeout(() => state.networkInstance.fit(), 100);
    }
  }
}

// ==============================================================================
// 4. Grounded Chat Workspace
// ==============================================================================
function initChat() {
  if (!sessionStorage.getItem('graphrag_session_id')) {
    sessionStorage.setItem('graphrag_session_id', state.sessionId);
  }
  elements.sessionIdLabel.textContent = state.sessionId;

  // Restore messages from current session storage
  if (state.chatHistory && state.chatHistory.length > 0) {
    if (elements.welcomeCard) {
      elements.welcomeCard.style.display = 'none';
    }
    state.chatHistory.forEach(item => {
      if (item.role === 'user') {
        appendUserMessage(item.text, false);
      } else if (item.role === 'assistant') {
        const row = document.createElement('div');
        row.className = 'chat-message-row assistant-row';
        elements.chatMessages.appendChild(row);
        replaceAssistantResponse(row, item.data, false);
      } else if (item.role === 'error') {
        const row = document.createElement('div');
        row.className = 'chat-message-row assistant-row';
        elements.chatMessages.appendChild(row);
        replaceAssistantError(row, item.errorMsg, false);
      }
    });
  }

  // Textarea auto-resize
  elements.queryInput.addEventListener('input', () => {
    elements.queryInput.style.height = 'auto';
    elements.queryInput.style.height = Math.min(elements.queryInput.scrollHeight, 160) + 'px';
  });

  // Enter to send (Shift+Enter for newline)
  elements.queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendQuery();
    }
  });

  elements.sendBtn.addEventListener('click', handleSendQuery);

  elements.clearChatBtn.addEventListener('click', () => {
    state.chatHistory = [];
    sessionStorage.removeItem('graphrag_chat_history');
    state.sessionId = 'session_' + Math.random().toString(36).substring(2, 9);
    sessionStorage.setItem('graphrag_session_id', state.sessionId);
    elements.sessionIdLabel.textContent = state.sessionId;
    elements.chatMessages.innerHTML = '';
    if (elements.welcomeCard) {
      elements.welcomeCard.style.display = '';
      elements.chatMessages.appendChild(elements.welcomeCard);
    }
  });

  if (elements.exportChatBtn) {
    elements.exportChatBtn.addEventListener('click', handleExportChat);
  }

  // Suggested prompt chips
  document.querySelectorAll('.prompt-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const prompt = btn.getAttribute('data-prompt');
      elements.queryInput.value = prompt;
      handleSendQuery();
    });
  });
}

function handleExportChat() {
  if (!state.chatHistory || state.chatHistory.length === 0) {
    alert('No chat messages in current session to export.');
    return;
  }

  let md = `# Enterprise GraphRAG — Chat Session Export\n\n`;
  md += `- **Session ID:** \`${state.sessionId}\`\n`;
  md += `- **Export Date:** ${new Date().toLocaleString()}\n`;
  md += `- **Total Dialogue Turns:** ${state.chatHistory.length}\n\n`;
  md += `---\n\n`;

  state.chatHistory.forEach((msg, idx) => {
    const timeStr = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : 'N/A';
    if (msg.role === 'user') {
      md += `### 👤 User (${timeStr})\n\n`;
      md += `${msg.text}\n\n`;
    } else if (msg.role === 'assistant') {
      const d = msg.data || {};
      const route = (d.route_taken || 'both').toUpperCase();
      const lat = d.latency_breakdown_ms || {};
      md += `### 🤖 Assistant (${timeStr})\n\n`;
      md += `> **Route:** ${route} | **Grounded:** ${d.is_grounded ? 'Yes' : 'No'} | **Cached:** ${d.from_cache ? 'Yes' : 'No'}\n`;
      md += `> **Latency:** Total ${lat.total_request_ms || 0}ms (Route: ${lat.routing_ms || 0}ms, Graph: ${lat.graph_ms || 0}ms, Vector: ${lat.vector_ms || 0}ms)\n\n`;
      md += `${d.answer || ''}\n\n`;

      if (d.graph_facts && d.graph_facts.length > 0) {
        md += `**Traversed Graph Facts:**\n`;
        d.graph_facts.forEach(f => {
          md += `- ${f}\n`;
        });
        md += `\n`;
      }

      if (d.cited_chunks && d.cited_chunks.length > 0) {
        md += `**Cited Chunks:**\n`;
        d.cited_chunks.forEach(c => {
          md += `- \`[${c}]\`\n`;
        });
        md += `\n`;
      }
    } else if (msg.role === 'error') {
      md += `### ⚠️ Error (${timeStr})\n\n`;
      md += `${msg.errorMsg}\n\n`;
    }
    md += `---\n\n`;
  });

  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `GraphRAG_Session_${state.sessionId}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function handleSendQuery() {
  const query = elements.queryInput.value.trim();
  if (!query) return;

  // Clear input
  elements.queryInput.value = '';
  elements.queryInput.style.height = 'auto';

  // Hide welcome hero on first user query
  if (elements.welcomeCard) {
    elements.welcomeCard.style.display = 'none';
  }

  // 1. Render User Message
  appendUserMessage(query);

  // 2. Render Loading Assistant Placeholder
  const loadingRow = appendAssistantLoading();

  try {
    const startTs = performance.now();
    const response = await fetch('/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        session_id: state.sessionId,
        top_k: 5,
        use_cache: elements.cacheToggle.checked,
      }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Network error' }));
      replaceAssistantError(loadingRow, errData.detail || 'Query failed');
      return;
    }

    const data = await response.json();
    replaceAssistantResponse(loadingRow, data);
  } catch (err) {
    replaceAssistantError(loadingRow, err.message || 'Connection to server failed');
  }
}

function appendUserMessage(text, save = true) {
  const row = document.createElement('div');
  row.className = 'chat-message-row user-row';
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  elements.chatMessages.appendChild(row);
  scrollToBottom();

  if (save) {
    state.chatHistory.push({
      role: 'user',
      text: text,
      timestamp: new Date().toISOString()
    });
    sessionStorage.setItem('graphrag_chat_history', JSON.stringify(state.chatHistory));
    sessionStorage.setItem('graphrag_session_id', state.sessionId);
  }
}

function appendAssistantLoading() {
  const row = document.createElement('div');
  row.className = 'chat-message-row assistant-row';
  row.innerHTML = `
    <div class="assistant-card">
      <div class="assistant-meta-bar">
        <div class="meta-badges-left">
          <span class="route-badge route-both">Routing...</span>
        </div>
      </div>
      <div class="assistant-text-content" style="color: var(--md-sys-color-outline);">
        Analyzing question across knowledge graph and dense vector space...
      </div>
    </div>
  `;
  elements.chatMessages.appendChild(row);
  scrollToBottom();
  return row;
}

function replaceAssistantError(row, errorMsg, save = true) {
  row.innerHTML = `
    <div class="assistant-card" style="border-color: var(--md-sys-color-error);">
      <div class="assistant-meta-bar">
        <span class="route-badge" style="background-color: var(--md-sys-color-error-container); color: var(--md-sys-color-on-error-container);">Error</span>
      </div>
      <div class="assistant-text-content" style="color: var(--md-sys-color-error);">
        ${escapeHtml(errorMsg)}
      </div>
    </div>
  `;
  scrollToBottom();

  if (save) {
    state.chatHistory.push({
      role: 'error',
      errorMsg: errorMsg,
      timestamp: new Date().toISOString()
    });
    sessionStorage.setItem('graphrag_chat_history', JSON.stringify(state.chatHistory));
    sessionStorage.setItem('graphrag_session_id', state.sessionId);
  }
}

function replaceAssistantResponse(row, data, save = true) {
  const route = (data.route_taken || 'both').toLowerCase();
  const routeClass = `route-${route}`;
  const canvasUid = 'canvas_' + Math.random().toString(36).substring(2, 9);
  
  // Format citations into interactive chips
  const formattedAnswer = renderMarkdownWithCitations(data.answer);

  // Latency breakdown badges
  const lat = data.latency_breakdown_ms || {};
  const latStr = `Route: ${lat.routing_ms || 0}ms | Graph: ${lat.graph_ms || 0}ms | Vector: ${lat.vector_ms || 0}ms | Total: ${lat.total_request_ms || 0}ms`;

  const hasSubgraph = data.subgraph && data.subgraph.nodes && data.subgraph.nodes.length > 0;

  row.innerHTML = `
    <div class="assistant-card">
      <div class="assistant-meta-bar">
        <div class="meta-badges-left">
          <span class="route-badge ${routeClass}">${route.toUpperCase()}</span>
          ${data.is_grounded ? `
            <span class="grounded-badge">
              <span class="material-symbols-outlined" style="font-size: 14px;">verified</span>
              Grounded
            </span>
          ` : ''}
          ${data.from_cache ? `
            <span class="m3-badge m3-badge-tonal">
              <span class="material-symbols-outlined" style="font-size: 12px; vertical-align: middle;">bolt</span>
              Cached
            </span>
          ` : ''}
        </div>
        <div class="meta-latencies-right">
          <span>${latStr}</span>
        </div>
      </div>

      <div class="assistant-text-content">
        ${formattedAnswer}
      </div>

      ${data.graph_facts && data.graph_facts.length > 0 ? `
        <div style="margin-top: 14px; padding-top: 10px; border-top: 1px dashed var(--md-sys-color-outline-variant);">
          <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--md-sys-color-outline); margin-bottom: 6px;">Traversed Graph Facts:</div>
          <ul style="font-size: 13px; color: var(--md-sys-color-on-surface-variant); margin-left: 18px;">
            ${data.graph_facts.map(f => `<li>${escapeHtml(f)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      ${hasSubgraph ? `
        <div class="inline-subgraph-wrapper">
          <button class="inline-subgraph-toggle-btn" type="button" id="btn-${canvasUid}">
            <span class="material-symbols-outlined" style="font-size: 16px;">hub</span>
            <span>Traversed Subgraph (${data.subgraph.nodes.length} nodes, ${data.subgraph.edges.length} edges)</span>
            <span class="material-symbols-outlined inline-toggle-icon" id="icon-${canvasUid}" style="font-size: 16px;">expand_more</span>
          </button>
          <div class="inline-subgraph-canvas-container" id="container-${canvasUid}" style="display: none;">
            <div class="inline-subgraph-canvas" id="canvas-${canvasUid}"></div>
            <div class="inline-subgraph-caption">
              <span class="material-symbols-outlined" style="font-size: 14px;">info</span>
              <span>2-hop neighborhood traversed across knowledge graph entities for this query</span>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;

  // Attach citation chip click listeners
  row.querySelectorAll('.citation-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const chunkId = chip.getAttribute('data-chunk');
      openCitationDialog(chunkId);
    });
  });

  // Attach inline subgraph toggle listener
  if (hasSubgraph) {
    let inlineNetwork = null;
    const toggleBtn = row.querySelector(`#btn-${canvasUid}`);
    const containerEl = row.querySelector(`#container-${canvasUid}`);
    const canvasEl = row.querySelector(`#canvas-${canvasUid}`);
    const iconEl = row.querySelector(`#icon-${canvasUid}`);

    if (toggleBtn && containerEl && canvasEl) {
      toggleBtn.addEventListener('click', () => {
        const isHidden = containerEl.style.display === 'none';
        if (isHidden) {
          containerEl.style.display = 'block';
          if (iconEl) iconEl.textContent = 'expand_less';
          if (!inlineNetwork) {
            inlineNetwork = renderInlineVisNetwork(canvasEl, data.subgraph);
          } else {
            setTimeout(() => inlineNetwork.fit(), 50);
          }
        } else {
          containerEl.style.display = 'none';
          if (iconEl) iconEl.textContent = 'expand_more';
        }
      });
    }
  }

  scrollToBottom();

  if (save) {
    state.chatHistory.push({
      role: 'assistant',
      data: data,
      timestamp: new Date().toISOString()
    });
    sessionStorage.setItem('graphrag_chat_history', JSON.stringify(state.chatHistory));
    sessionStorage.setItem('graphrag_session_id', state.sessionId);
  }
}

function renderMarkdownWithCitations(text) {
  if (!text) return '';
  
  // 1. Replace [chunk_id] with clickable interactive chip
  let html = text.replace(/\[([a-zA-Z0-9_\-\.]+)\]/g, (match, chunkId) => {
    return `<button class="citation-chip" data-chunk="${escapeHtml(chunkId)}" title="Click to inspect source chunk"><span class="material-symbols-outlined" style="font-size: 12px;">receipt_long</span>${escapeHtml(chunkId)}</button>`;
  });

  // 2. Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // 3. Convert paragraphs
  const paragraphs = html.split(/\n\n+/);
  return paragraphs.map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
}

function scrollToBottom() {
  setTimeout(() => {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  }, 50);
}

// ==============================================================================
// 5. Interactive Neo4j Topology Visualizer (Vis-Network)
// ==============================================================================
function initGraphExplorer() {
  elements.refreshGraphBtn.addEventListener('click', fetchAndRenderGraph);
  elements.fitGraphBtn.addEventListener('click', () => {
    if (state.networkInstance) state.networkInstance.fit();
  });

  elements.closeInspectorBtn.addEventListener('click', () => {
    elements.nodeInspector.style.display = 'none';
  });

  // Filter chips
  elements.filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      elements.filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      state.activeFilter = chip.getAttribute('data-filter');
      applyGraphFilter();
    });
  });

  // Search input
  elements.graphSearchInput.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    if (!term || !state.networkInstance) return;

    const matchedNode = state.graphData.nodes.find(n => n.label.toLowerCase().includes(term));
    if (matchedNode) {
      state.networkInstance.focus(matchedNode.id, {
        scale: 1.2,
        animation: { duration: 600, easingFunction: 'easeInOutQuad' },
      });
      state.networkInstance.selectNodes([matchedNode.id]);
      showNodeInspection(matchedNode);
    }
  });

  elements.queryEntityBtn.addEventListener('click', () => {
    const entity = elements.inspectorName.textContent;
    switchView('chat-view');
    elements.queryInput.value = `Tell me about ${entity} and its relationships in the literature.`;
    handleSendQuery();
  });
}

async function fetchAndRenderGraph() {
  try {
    elements.topologyCounter.textContent = 'Loading graph...';
    const res = await fetch('/graph/subgraph?limit=150');
    if (!res.ok) throw new Error('Failed to fetch subgraph');

    const data = await res.json();
    state.graphData = data;
    elements.topologyCounter.textContent = `Nodes: ${data.total_nodes} | Edges: ${data.total_edges}`;
    renderVisNetwork(data);
  } catch (err) {
    elements.topologyCounter.textContent = 'Graph offline or empty';
  }
}

function renderVisNetwork(data) {
  const visNodes = data.nodes.map(n => {
    const color = ONTOLOGY_COLORS[n.type] || ONTOLOGY_COLORS.Default;
    return {
      id: n.id,
      label: n.label,
      title: `${n.type}: ${n.label}`,
      color: {
        background: color,
        border: color,
        highlight: { background: '#FFFFFF', border: color },
      },
      font: { color: '#FFFFFF', face: 'Roboto', size: 13 },
      shape: n.type === 'Paper' ? 'box' : 'dot',
      size: n.type === 'Paper' ? undefined : 16,
      margin: n.type === 'Paper' ? 8 : undefined,
      ontologyType: n.type,
      aliases: n.aliases || [],
    };
  });

  const visEdges = data.edges.map(e => ({
    from: e.source,
    to: e.target,
    label: e.type,
    arrows: 'to',
    font: { size: 10, color: '#938F99', align: 'middle' },
    color: { color: 'rgba(147, 143, 153, 0.4)', highlight: '#D0BCFF' },
    smooth: { type: 'curvedCW', roundness: 0.15 },
    relType: e.type,
    confidence: e.confidence,
    sourceChunkId: e.source_chunk_id,
  }));

  const container = elements.visCanvas;
  const graphPayload = {
    nodes: new vis.DataSet(visNodes),
    edges: new vis.DataSet(visEdges),
  };

  const options = {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -40,
        centralGravity: 0.008,
        springLength: 120,
        springConstant: 0.08,
        damping: 0.85,
      },
      stabilization: { iterations: 120 },
    },
    interaction: {
      hover: true,
      tooltipDelay: 100,
      zoomView: true,
      dragView: true,
    },
  };

  state.networkInstance = new vis.Network(container, graphPayload, options);

  // Node Click Inspector
  state.networkInstance.on('click', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0];
      const nodeObj = visNodes.find(n => n.id === nodeId);
      if (nodeObj) {
        showNodeInspection(nodeObj);
      }
    } else {
      elements.nodeInspector.style.display = 'none';
    }
  });
}

function renderInlineVisNetwork(container, data) {
  const visNodes = data.nodes.map(n => {
    const color = ONTOLOGY_COLORS[n.type] || ONTOLOGY_COLORS.Default;
    return {
      id: n.id,
      label: n.label,
      title: `${n.type}: ${n.label}`,
      color: {
        background: color,
        border: color,
        highlight: { background: '#FFFFFF', border: color },
      },
      font: { color: '#FFFFFF', face: 'Roboto', size: 12 },
      shape: n.type === 'Paper' ? 'box' : 'dot',
      size: n.type === 'Paper' ? undefined : 14,
      margin: n.type === 'Paper' ? 6 : undefined,
      ontologyType: n.type,
    };
  });

  const visEdges = data.edges.map(e => ({
    from: e.source,
    to: e.target,
    label: e.type,
    arrows: 'to',
    font: { size: 9, color: '#938F99', align: 'middle' },
    color: { color: 'rgba(147, 143, 153, 0.45)', highlight: '#D0BCFF' },
    smooth: { type: 'curvedCW', roundness: 0.15 },
  }));

  const graphPayload = {
    nodes: new vis.DataSet(visNodes),
    edges: new vis.DataSet(visEdges),
  };

  const options = {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -35,
        centralGravity: 0.01,
        springLength: 100,
        springConstant: 0.08,
        damping: 0.85,
      },
      stabilization: { iterations: 100 },
    },
    interaction: {
      hover: true,
      zoomView: true,
      dragView: true,
    },
  };

  return new vis.Network(container, graphPayload, options);
}

function showNodeInspection(node) {
  elements.nodeInspector.style.display = 'block';
  elements.inspectorName.textContent = node.label;
  elements.inspectorType.textContent = node.ontologyType;
  elements.inspectorType.style.backgroundColor = ONTOLOGY_COLORS[node.ontologyType] || ONTOLOGY_COLORS.Default;

  const aliases = node.aliases && node.aliases.length > 0 ? node.aliases.join(', ') : 'None';
  elements.inspectorAliases.textContent = aliases;

  // Find connected edges
  const connected = state.graphData.edges.filter(e => e.source === node.id || e.target === node.id);
  if (connected.length === 0) {
    elements.inspectorEdges.innerHTML = '<em>No direct relationships recorded yet</em>';
  } else {
    elements.inspectorEdges.innerHTML = connected.slice(0, 8).map(e => `
      <div style="margin-bottom: 4px;">
        <strong>${escapeHtml(e.type)}</strong> &rarr; ${escapeHtml(e.source === node.id ? e.target : e.source)}
      </div>
    `).join('');
  }
}

function applyGraphFilter() {
  if (!state.networkInstance || !state.graphData) return;
  fetchAndRenderGraph();
}

function updateGraphColors() {
  // Update node font colors based on theme if needed
}

// ==============================================================================
// 6. Citation Chunk Inspection Dialog
// ==============================================================================
function initCitationDialog() {
  elements.closeDialogBtn.addEventListener('click', closeCitationDialog);
  elements.dialogDoneBtn.addEventListener('click', closeCitationDialog);
  elements.citationDialog.addEventListener('click', (e) => {
    if (e.target === elements.citationDialog) {
      closeCitationDialog();
    }
  });
}

async function openCitationDialog(chunkId) {
  elements.dialogChunkId.textContent = chunkId;
  elements.dialogPaperTitle.textContent = 'Loading...';
  elements.dialogSectionPath.textContent = '--';
  elements.dialogDocId.textContent = '--';
  elements.dialogPassageText.textContent = 'Fetching chunk passage from pgvector store...';
  elements.dialogEntitiesChips.innerHTML = '';
  elements.citationDialog.style.display = 'flex';

  try {
    const res = await fetch(`/chunks/${encodeURIComponent(chunkId)}`);
    if (!res.ok) {
      throw new Error(`Chunk ${chunkId} could not be retrieved`);
    }
    const chunk = await res.json();
    elements.dialogPaperTitle.textContent = chunk.paper_title || 'Unknown Paper';
    elements.dialogSectionPath.textContent = chunk.section_path || 'Abstract';
    elements.dialogDocId.textContent = chunk.document_id || '--';
    elements.dialogPassageText.textContent = chunk.text || 'No text content';

    if (chunk.entity_ids && chunk.entity_ids.length > 0) {
      elements.dialogEntitiesChips.innerHTML = chunk.entity_ids.map(ent => `
        <span class="m3-chip" style="padding: 4px 8px; font-size: 11px;">
          ${escapeHtml(ent)}
        </span>
      `).join('');
    } else {
      elements.dialogEntitiesChips.innerHTML = '<span style="color: var(--md-sys-color-outline); font-size: 12px;">No entities linked</span>';
    }
  } catch (err) {
    elements.dialogPassageText.textContent = `Error: ${err.message}`;
  }
}

function closeCitationDialog() {
  elements.citationDialog.style.display = 'none';
}

// ==============================================================================
// 6. Ingestion Management & Live Telemetry
// ==============================================================================
let ingestPollInterval = null;

function initIngestDialog() {
  if (elements.openIngestDialogBtn) {
    elements.openIngestDialogBtn.addEventListener('click', openIngestModal);
  }
  if (elements.closeIngestDialogBtn) {
    elements.closeIngestDialogBtn.addEventListener('click', closeIngestModal);
  }
  if (elements.cancelIngestBtn) {
    elements.cancelIngestBtn.addEventListener('click', closeIngestModal);
  }
  if (elements.modeExisting && elements.modeHarvest) {
    elements.modeExisting.addEventListener('change', toggleIngestMode);
    elements.modeHarvest.addEventListener('change', toggleIngestMode);
  }
  if (elements.startIngestBtn) {
    elements.startIngestBtn.addEventListener('click', startIngestionProcess);
  }
}

function openIngestModal() {
  elements.ingestModalScrim.style.display = 'flex';
  checkCurrentIngestStatus();
}

function closeIngestModal() {
  elements.ingestModalScrim.style.display = 'none';
}

function toggleIngestMode() {
  if (elements.modeHarvest.checked) {
    elements.harvestParamsGroup.style.display = 'block';
  } else {
    elements.harvestParamsGroup.style.display = 'none';
  }
}

async function checkCurrentIngestStatus() {
  try {
    const res = await fetch('/ingest/status');
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === 'running') {
      elements.ingestTelemetryPanel.style.display = 'block';
      elements.startIngestBtn.disabled = true;
      updateIngestUI(data);
      if (!ingestPollInterval) {
        ingestPollInterval = setInterval(pollIngestStatus, 1200);
      }
    }
  } catch (err) {
    console.error('Failed to check ingestion status:', err);
  }
}

async function startIngestionProcess() {
  const mode = elements.modeHarvest.checked ? 'harvest_arxiv' : 'existing_corpus';
  const query = elements.ingestQueryInput.value.trim() || 'retrieval-augmented generation';
  const paperLimit = parseInt(elements.ingestPaperLimit.value, 10) || 50;
  const chunkLimitRaw = elements.ingestChunkLimit.value.trim();
  const chunkLimit = chunkLimitRaw ? parseInt(chunkLimitRaw, 10) : null;
  const popNeo4j = elements.ingestPopNeo4j.checked;
  const popVector = elements.ingestPopVector.checked;

  const payload = {
    mode,
    query,
    paper_limit: paperLimit,
    chunk_limit: chunkLimit,
    populate_neo4j: popNeo4j,
    populate_pgvector: popVector,
  };

  elements.ingestTelemetryPanel.style.display = 'block';
  elements.startIngestBtn.disabled = true;
  elements.ingestStageBadge.textContent = 'starting';
  elements.ingestStatusMessage.textContent = 'Submitting job...';
  elements.ingestStatusPct.textContent = '0%';
  elements.ingestProgressBar.style.width = '0%';
  elements.ingestLogTerminal.innerHTML = '<div class="log-entry">Submitting ingestion request to server...</div>';

  try {
    const res = await fetch('/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.status === 409) {
      alert('An ingestion task is already actively running.');
    } else if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    updateIngestUI(data);

    if (ingestPollInterval) clearInterval(ingestPollInterval);
    ingestPollInterval = setInterval(pollIngestStatus, 1200);
  } catch (err) {
    elements.startIngestBtn.disabled = false;
    elements.ingestStatusMessage.textContent = `Error: ${err.message}`;
    elements.ingestLogTerminal.innerHTML += `<div class="log-entry log-err">Error: ${escapeHtml(err.message)}</div>`;
  }
}

async function pollIngestStatus() {
  try {
    const res = await fetch('/ingest/status');
    if (!res.ok) return;
    const data = await res.json();
    updateIngestUI(data);

    if (data.status === 'completed' || data.status === 'failed') {
      clearInterval(ingestPollInterval);
      ingestPollInterval = null;
      elements.startIngestBtn.disabled = false;

      if (data.status === 'completed') {
        // Refresh graph topology and health telemetry
        if (typeof fetchAndRenderGraph === 'function') fetchAndRenderGraph();
        pollTelemetry();
      }
    }
  } catch (err) {
    console.error('Error polling ingest status:', err);
  }
}

function updateIngestUI(data) {
  elements.ingestStageBadge.textContent = data.stage || data.status;
  elements.ingestStatusMessage.textContent = data.message || '';
  elements.ingestStatusPct.textContent = `${Math.round(data.progress_pct)}%`;
  elements.ingestProgressBar.style.width = `${data.progress_pct}%`;

  if (data.logs && data.logs.length > 0) {
    elements.ingestLogTerminal.innerHTML = data.logs.map(line => `
      <div class="log-entry ${line.startsWith('ERROR') ? 'log-err' : ''}">
        ${escapeHtml(line)}
      </div>
    `).join('');
    elements.ingestLogTerminal.scrollTop = elements.ingestLogTerminal.scrollHeight;
  }
}

// ==============================================================================
// 7. System Telemetry & Dynamic Diagnostics
// ==============================================================================
function purgeSessionStorage() {
  sessionStorage.removeItem('graphrag_chat_history');
  sessionStorage.removeItem('graphrag_session_id');
  state.chatHistory = [];
  state.sessionId = 'session_' + Math.random().toString(36).substring(2, 9);
  sessionStorage.setItem('graphrag_session_id', state.sessionId);
  if (elements.sessionIdLabel) {
    elements.sessionIdLabel.textContent = state.sessionId;
  }
  if (elements.chatMessages) {
    elements.chatMessages.innerHTML = '';
    if (elements.welcomeCard) {
      elements.welcomeCard.style.display = '';
      elements.chatMessages.appendChild(elements.welcomeCard);
    }
  }
}

function handleServerDisconnect() {
  updateHealthPills({ postgres_connected: false, neo4j_connected: false });
  if (sessionStorage.getItem('graphrag_chat_history')) {
    console.warn('Localhost connection lost. Auto-clearing session storage.');
    purgeSessionStorage();
  }
}

async function pollTelemetry() {
  try {
    // 1. Check health & detect server restarts
    const healthRes = await fetch('/health');
    if (!healthRes.ok) {
      handleServerDisconnect();
      return;
    }
    const hData = await healthRes.json();

    // Check server reboot lifecycle via boot_id
    if (hData.boot_id) {
      if (state.serverBootId && state.serverBootId !== hData.boot_id) {
        console.warn('Server process reboot detected. Auto-clearing previous session storage.');
        purgeSessionStorage();
      }
      state.serverBootId = hData.boot_id;
    }

    updateHealthPills(hData);

    // 2. Fetch runtime stats & dynamic config
    const statsRes = await fetch('/stats');
    if (statsRes.ok) {
      const sData = await statsRes.json();
      updateStatsPanel(sData);
    }
  } catch (err) {
    handleServerDisconnect();
  }
}

function updateHealthPills(data) {
  // Top app bar pills
  if (elements.postgresStatus) {
    const dot = elements.postgresStatus.querySelector('.status-dot');
    if (dot) {
      dot.className = `status-dot ${data.postgres_connected ? 'dot-active' : 'dot-error'}`;
    }
  }
  if (elements.neo4jStatus) {
    const dot = elements.neo4jStatus.querySelector('.status-dot');
    if (dot) {
      dot.className = `status-dot ${data.neo4j_connected ? 'dot-active' : 'dot-error'}`;
    }
  }

  // Telemetry page badges
  if (elements.tPostgresBadge) {
    elements.tPostgresBadge.textContent = data.postgres_connected ? 'Active' : 'Offline';
    elements.tPostgresBadge.className = `m3-badge ${data.postgres_connected ? 'm3-badge-success' : 'm3-badge-error'}`;
  }
  if (elements.tNeo4jBadge) {
    elements.tNeo4jBadge.textContent = data.neo4j_connected ? 'Active' : 'Offline';
    elements.tNeo4jBadge.className = `m3-badge ${data.neo4j_connected ? 'm3-badge-success' : 'm3-badge-error'}`;
  }
}

function updateStatsPanel(data) {
  if (elements.cacheStatText) {
    elements.cacheStatText.textContent = `Cache: ${(data.cache_hit_rate * 100).toFixed(1)}% (${data.cached_entries})`;
  }
  if (elements.tHitRate) {
    elements.tHitRate.textContent = `${(data.cache_hit_rate * 100).toFixed(1)}%`;
  }
  if (elements.tTotalQueries) {
    elements.tTotalQueries.textContent = data.total_requests;
  }
  if (elements.tHitsMisses) {
    elements.tHitsMisses.textContent = `${data.cache_hits} / ${data.cache_misses}`;
  }
  if (elements.tCachedCount) {
    elements.tCachedCount.textContent = data.cached_entries;
  }
  if (elements.tAttribution && data.acknowledgments) {
    elements.tAttribution.textContent = `"${data.acknowledgments}"`;
  }

  // Dynamic Infrastructure Targets from .env
  if (data.infrastructure) {
    if (elements.tPostgresTarget && data.infrastructure.postgres_target) {
      elements.tPostgresTarget.textContent = data.infrastructure.postgres_target;
    }
    if (elements.tNeo4jTarget && data.infrastructure.neo4j_uri) {
      elements.tNeo4jTarget.textContent = data.infrastructure.neo4j_uri;
    }
  }

  // Dynamic Model Gateway Targets from .env
  if (data.models) {
    if (elements.tGatewayTitle && data.models.llm_base_url) {
      const isNim = data.models.llm_base_url.includes('nvidia') || data.models.llm_base_url.includes('10.0');
      elements.tGatewayTitle.textContent = `Model Gateway (${isNim ? 'NVIDIA NIM' : 'OpenAI Gateway'})`;
    }
    if (elements.tModelExtraction && data.models.extraction_model) {
      elements.tModelExtraction.textContent = data.models.extraction_model;
    }
    if (elements.tModelRouter && data.models.router_model) {
      elements.tModelRouter.textContent = data.models.router_model;
    }
    if (elements.tModelSynthesis && data.models.synthesis_model) {
      elements.tModelSynthesis.textContent = data.models.synthesis_model;
    }
    if (elements.tModelEmbedding && data.models.embedding_model) {
      elements.tModelEmbedding.textContent = data.models.embedding_model;
    }
    if (elements.tEmbeddingDim && data.models.embedding_dim) {
      elements.tEmbeddingDim.textContent = `${data.models.embedding_dim} dims`;
    }
  }
}

// ==============================================================================
// Utilities
// ==============================================================================
function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

