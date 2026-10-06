// LocalLens Frontend Engine

let currentTab = 'ask';
let allDocuments = [];
let activeDocId = null;
let activeDocData = null;
let activeDocPage = 1;
let highlightedQuote = null;
let latestEvalReport = null;
let currentEvalFilter = 'all';
let currentDemoStage = 1;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  if (window.lucide) lucide.createIcons();
  await loadDocuments();
  await loadLatestEvaluation();
  renderCollections();
  setDemoStage(1);
  await initUserDocuments();
});

// THEME (DAY / NIGHT MODE)
function initTheme() {
  const savedTheme = localStorage.getItem('locallens-theme') || 'dark';
  applyTheme(savedTheme);
}

function setSpecificTheme(theme) {
  localStorage.setItem('locallens-theme', theme);
  applyTheme(theme);
}

function toggleTheme() {
  const isLight = document.documentElement.classList.contains('light');
  setSpecificTheme(isLight ? 'dark' : 'light');
}

function applyTheme(theme) {
  const btnDay = document.getElementById('btn-theme-day');
  const btnNight = document.getElementById('btn-theme-night');
  
  if (theme === 'light') {
    document.documentElement.classList.add('light');
    document.documentElement.classList.remove('dark');
    if (btnDay) {
      btnDay.className = "px-2.5 py-1 rounded-md flex items-center space-x-1 transition text-amber-900 bg-amber-200 font-bold shadow-sm border border-amber-300";
    }
    if (btnNight) {
      btnNight.className = "px-2.5 py-1 rounded-md flex items-center space-x-1 transition text-slate-500 hover:text-slate-900 font-medium";
    }
  } else {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
    if (btnDay) {
      btnDay.className = "px-2.5 py-1 rounded-md flex items-center space-x-1 transition text-slate-400 hover:text-white font-medium";
    }
    if (btnNight) {
      btnNight.className = "px-2.5 py-1 rounded-md flex items-center space-x-1 transition text-indigo-300 bg-slate-800 font-bold shadow-sm border border-slate-700";
    }
  }
  if (window.lucide) lucide.createIcons();
}

// TAB SWITCHING
function switchTab(tabId) {
  currentTab = tabId;
  const tabs = ['ask', 'viewer', 'search', 'compare', 'eval', 'collections', 'ingest', 'demo', 'about'];
  
  tabs.forEach(t => {
    const view = document.getElementById(`view-${t}`);
    const navBtn = document.getElementById(`nav-${t}`);
    if (view) {
      if (t === tabId) {
        view.classList.remove('hidden');
      } else {
        view.classList.add('hidden');
      }
    }
    if (navBtn) {
      if (t === tabId) {
        navBtn.className = "tab-btn px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition text-white bg-slate-800 active-tab";
      } else {
        navBtn.className = "tab-btn px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition text-slate-400 hover:text-white hover:bg-slate-800/60";
      }
    }
  });

  if (window.lucide) lucide.createIcons();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ASK TAB LOGIC
function setQuery(text) {
  const input = document.getElementById('query-input');
  if (input) {
    input.value = text;
    handleQuerySubmit(new Event('submit'));
  }
}

async function handleQuerySubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  
  const input = document.getElementById('query-input');
  const question = input.value.trim();
  if (!question) return;

  const categoryFilter = document.getElementById('filter-category').value;
  const loading = document.getElementById('query-loading');
  const responseContainer = document.getElementById('query-response-container');
  const btnSubmit = document.getElementById('btn-submit');

  loading.classList.remove('hidden');
  responseContainer.classList.add('hidden');
  btnSubmit.disabled = true;

  try {
    const res = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: question,
        category_filter: categoryFilter || null,
        top_k: 5
      })
    });

    if (!res.ok) throw new Error('Query failed');
    const data = await res.json();
    renderQueryResponse(data);
  } catch (err) {
    alert('Error connecting to LocalLens backend: ' + err.message);
  } finally {
    loading.classList.add('hidden');
    responseContainer.classList.remove('hidden');
    btnSubmit.disabled = false;
    if (window.lucide) lucide.createIcons();
  }
}

function renderQueryResponse(data) {
  const contradictionBanner = document.getElementById('contradiction-banner');
  const abstentionBanner = document.getElementById('abstention-banner');
  const groundedCard = document.getElementById('grounded-answer-card');
  
  // 1. Contradictions Check
  if (data.contradictions && data.contradictions.length > 0) {
    const c = data.contradictions[0];
    contradictionBanner.classList.remove('hidden');
    document.getElementById('contradiction-desc').innerText = c.description;
    document.getElementById('conflict-source-a-title').innerText = c.source_a.document_title;
    document.getElementById('conflict-source-a-excerpt').innerText = `“${c.source_a.excerpt}” (${c.source_a.version})`;
    document.getElementById('conflict-source-b-title').innerText = c.source_b.document_title;
    document.getElementById('conflict-source-b-excerpt').innerText = `“${c.source_b.excerpt}” (${c.source_b.version})`;
    document.getElementById('conflict-guidance').innerText = c.guidance;
  } else {
    contradictionBanner.classList.add('hidden');
  }

  // 2. Abstention Check
  if (!data.answerable) {
    abstentionBanner.classList.remove('hidden');
    groundedCard.classList.add('hidden');
    document.getElementById('abstention-msg').innerText = data.answer;
    
    const foundList = document.getElementById('abstention-found-list');
    foundList.innerHTML = '';
    (data.what_i_found || ["General state schemes exist in Maharashtra, but not for this subject."]).forEach(item => {
      const li = document.createElement('li');
      li.innerText = item;
      foundList.appendChild(li);
    });

    const missingList = document.getElementById('abstention-missing-list');
    missingList.innerHTML = '';
    (data.missing_information || ["No matching Government Resolution in indexed archive."]).forEach(item => {
      const li = document.createElement('li');
      li.innerText = item;
      missingList.appendChild(li);
    });
    return;
  }

  // 3. Answerable Grounded Response
  abstentionBanner.classList.add('hidden');
  groundedCard.classList.remove('hidden');

  document.getElementById('answer-text').innerText = data.answer;
  document.getElementById('grounding-text').innerText = `Grounding: ${data.grounding_strength}`;
  document.getElementById('badge-status').innerText = data.document_status.includes('Current') ? '🟢 Current' : '🟡 ' + data.document_status;
  document.getElementById('badge-latency').innerText = `${data.latency_ms} ms`;
  document.getElementById('why-text').innerText = data.why_reasoning;

  // Key Points
  const keyList = document.getElementById('key-points-list');
  keyList.innerHTML = '';
  (data.key_points || []).forEach(pt => {
    const li = document.createElement('li');
    li.innerText = pt;
    keyList.appendChild(li);
  });

  // Evidence Cards
  const evidenceContainer = document.getElementById('evidence-cards-container');
  evidenceContainer.innerHTML = '';
  
  (data.evidence || []).forEach((ev, idx) => {
    const card = document.createElement('div');
    card.className = "bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2 hover:border-slate-700 transition";
    
    card.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 pb-2">
        <div class="flex items-center space-x-2">
          <span class="px-2 py-0.5 rounded bg-brand-500/10 text-brand-400 border border-brand-500/20 font-mono text-[11px] font-semibold">
            ${ev.section} — Page ${ev.page}
          </span>
          <span class="text-xs text-slate-400 font-medium">${ev.document_title}</span>
        </div>
        <div class="flex items-center space-x-2">
          <span class="text-[10px] px-2 py-0.5 rounded ${ev.status === 'current' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}">
            ${ev.status === 'current' ? '🟢 Current' : '🔴 Outdated'}
          </span>
          <button onclick="viewInDocument('${ev.document_id}', ${ev.page}, '${encodeURIComponent(ev.quote)}')" class="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded text-xs font-semibold flex items-center space-x-1 transition">
            <i data-lucide="external-link" class="w-3 h-3"></i>
            <span>View in Document</span>
          </button>
        </div>
      </div>
      <p class="text-xs text-slate-200 italic leading-relaxed pl-2 border-l-2 border-amber-500">
        “${ev.quote}”
      </p>
      <div class="text-[11px] text-slate-500 flex items-center justify-between pt-1">
        <span>Department: ${ev.department}</span>
        <span>Relevance: ${Math.round(ev.relevance_score * 1000) / 10}%</span>
      </div>
    `;
    evidenceContainer.appendChild(card);
  });

  // Telemetry drawer
  const telemetryDocs = document.getElementById('telemetry-docs');
  telemetryDocs.innerHTML = data.evidence.map(e => `• ${e.document_title} (Page ${e.page}, Score: ${e.relevance_score})`).join('<br>');

  // Related questions
  const relContainer = document.getElementById('related-questions-container');
  relContainer.innerHTML = '';
  (data.related_questions || []).forEach(q => {
    const btn = document.createElement('button');
    btn.className = "px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700/60 transition";
    btn.innerText = q;
    btn.onclick = () => setQuery(q);
    relContainer.appendChild(btn);
  });

  if (window.lucide) lucide.createIcons();
}

function toggleWhyDrawer() {
  const drawer = document.getElementById('why-drawer');
  const chevron = document.getElementById('why-chevron');
  if (drawer.classList.contains('hidden')) {
    drawer.classList.remove('hidden');
    if (chevron) chevron.style.transform = 'rotate(180deg)';
  } else {
    drawer.classList.add('hidden');
    if (chevron) chevron.style.transform = 'rotate(0deg)';
  }
}

// DOCUMENT VIEWER LOGIC
async function loadDocuments() {
  try {
    const res = await fetch('/api/documents');
    allDocuments = await res.json();
    renderDocSelector();
    if (allDocuments.length > 0 && !activeDocId) {
      loadDocumentDetails(allDocuments[0].id);
    }
  } catch (err) {
    console.error('Failed to load documents:', err);
  }
}

function renderDocSelector() {
  const sidebar = document.getElementById('doc-selector-sidebar');
  if (!sidebar) return;
  sidebar.innerHTML = '';

  allDocuments.forEach(doc => {
    const item = document.createElement('div');
    const isSelected = doc.id === activeDocId;
    item.className = `p-3.5 rounded-xl border cursor-pointer transition space-y-1.5 ${
      isSelected 
        ? 'bg-brand-950/40 border-brand-500/50 shadow-md' 
        : 'bg-slate-900 border-slate-800 hover:border-slate-700'
    }`;
    item.onclick = () => loadDocumentDetails(doc.id);

    item.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-semibold px-2 py-0.5 rounded ${doc.status === 'current' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}">
          ${doc.status === 'current' ? '🟢 Current' : '🔴 Outdated'}
        </span>
        <span class="text-[10px] font-mono text-slate-500">${doc.version}</span>
      </div>
      <h4 class="text-xs font-bold text-white leading-tight">${doc.title}</h4>
      <p class="text-[11px] text-slate-400">${doc.department}</p>
      <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1">
        <span>${doc.category}</span>
        <span>${doc.total_pages} Pages</span>
      </div>
    `;
    sidebar.appendChild(item);
  });
}

async function loadDocumentDetails(docId, targetPage = 1, quoteToHighlight = null) {
  activeDocId = docId;
  activeDocPage = targetPage;
  highlightedQuote = quoteToHighlight;
  renderDocSelector();

  try {
    const res = await fetch(`/api/documents/${docId}`);
    activeDocData = await res.json();
    renderActiveDocumentPage();
  } catch (err) {
    console.error('Error fetching document:', err);
  }
}

function renderActiveDocumentPage() {
  if (!activeDocData) return;
  const meta = activeDocData.metadata;

  document.getElementById('reader-title').innerText = meta.title;
  document.getElementById('reader-dept').innerText = meta.department;
  document.getElementById('reader-status-badge').innerText = meta.status === 'current' ? '🟢 Current' : '🔴 Outdated';
  document.getElementById('reader-version-badge').innerText = meta.version;
  document.getElementById('reader-gr-number').innerText = `GR: ${meta.gr_number || 'Official Notification'}`;
  document.getElementById('reader-published-date').innerText = `Published: ${meta.publication_date}`;
  document.getElementById('reader-source-link').href = meta.url || '#';

  const totalPages = activeDocData.pages.length || 1;
  document.getElementById('reader-current-page').innerText = `Page ${activeDocPage}`;
  document.getElementById('reader-total-pages').innerText = `Page ${totalPages}`;

  document.getElementById('btn-prev-page').disabled = (activeDocPage <= 1);
  document.getElementById('btn-next-page').disabled = (activeDocPage >= totalPages);

  // Render Page Markdown Content
  const currentPageData = activeDocData.pages.find(p => p.page_num === activeDocPage) || activeDocData.pages[0];
  const readerBody = document.getElementById('reader-body');
  
  let rawText = currentPageData ? currentPageData.text : "Page content not found.";

  // Highlight quote if present on this page
  if (highlightedQuote) {
    const cleanQuote = decodeURIComponent(highlightedQuote).trim();
    // Try exact or partial match
    const quoteWords = cleanQuote.split(/\s+/).slice(0, 8).join(" ");
    if (rawText.includes(cleanQuote)) {
      rawText = rawText.replace(cleanQuote, `\n\n<mark class="bg-amber-400/20 border-l-4 border-amber-400 p-3 my-2 text-amber-200 block rounded-r glow-amber">“${cleanQuote}”</mark>\n\n`);
    } else if (rawText.toLowerCase().includes(quoteWords.toLowerCase())) {
      const idx = rawText.toLowerCase().indexOf(quoteWords.toLowerCase());
      const snippet = rawText.substr(idx, Math.min(220, rawText.length - idx));
      rawText = rawText.replace(snippet, `\n\n<mark class="bg-amber-400/20 border-l-4 border-amber-400 p-3 my-2 text-amber-200 block rounded-r glow-amber">“${snippet}”</mark>\n\n`);
    }
  }

  // Simple clean markdown formatting
  let formattedHtml = rawText
    .replace(/^# (.*$)/gim, '<h1 class="text-lg font-bold text-white mb-2">$1</h1>')
    .replace(/^## (.*$)/gim, '<h2 class="text-base font-bold text-brand-300 mt-4 mb-2 border-b border-slate-800 pb-1">$1</h2>')
    .replace(/^### (.*$)/gim, '<h3 class="text-sm font-semibold text-slate-200 mt-3 mb-1">$1</h3>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em class="text-slate-300">$1</em>')
    .replace(/\n\n/gim, '</p><p class="mb-3">');

  // Table styling
  if (formattedHtml.includes('|')) {
    formattedHtml = formatMarkdownTables(formattedHtml);
  }

  readerBody.innerHTML = `<div class="prose prose-invert max-w-none text-xs sm:text-sm"><p>${formattedHtml}</p></div>`;

  // Auto scroll to mark if present
  const mark = readerBody.querySelector('mark');
  if (mark) {
    setTimeout(() => {
      mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 150);
  }
}

function formatMarkdownTables(text) {
  return text.replace(/(\|.+?\|\n\|[-:\s|]+\|\n(?:\|.+?\|\n?)+)/g, (match) => {
    const lines = match.trim().split('\n');
    if (lines.length < 3) return match;
    const headers = lines[0].split('|').slice(1, -1).map(c => `<th class="p-2 border border-slate-800 bg-slate-850 text-slate-200 font-semibold">${c.trim()}</th>`).join('');
    const rows = lines.slice(2).map(r => {
      const cells = r.split('|').slice(1, -1).map(c => `<td class="p-2 border border-slate-800">${c.trim()}</td>`).join('');
      return `<tr class="hover:bg-slate-850/50">${cells}</tr>`;
    }).join('');
    return `<div class="overflow-x-auto my-3"><table class="w-full text-xs text-left border-collapse border border-slate-800">${headers}${rows}</table></div>`;
  });
}

function prevDocPage() {
  if (activeDocPage > 1) {
    activeDocPage--;
    renderActiveDocumentPage();
  }
}

function nextDocPage() {
  if (activeDocData && activeDocPage < activeDocData.pages.length) {
    activeDocPage++;
    renderActiveDocumentPage();
  }
}

function viewInDocument(docId, pageNum, quote) {
  switchTab('viewer');
  loadDocumentDetails(docId, pageNum, quote);
}

// SEARCH TAB LOGIC
async function handleDirectSearch(e) {
  if (e && e.preventDefault) e.preventDefault();
  const query = document.getElementById('search-input').value.trim();
  if (!query) return;

  const container = document.getElementById('search-results-container');
  container.innerHTML = '<div class="text-center py-8 text-xs text-slate-400">Searching hybrid index...</div>';

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&top_k=8`);
    const results = await res.json();
    
    if (results.length === 0) {
      container.innerHTML = '<div class="text-center py-8 text-xs text-slate-400">No matching passages found.</div>';
      return;
    }

    container.innerHTML = '';
    results.forEach(item => {
      const card = document.createElement('div');
      card.className = "bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2 hover:border-slate-700 transition";
      card.innerHTML = `
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="font-bold text-xs text-white">${item.document_title}</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-brand-500/10 text-brand-400 font-mono">Page ${item.page}</span>
            <span class="text-[10px] text-slate-500 font-mono">Relevance: ${Math.round(item.relevance_score * 1000) / 10}%</span>
          </div>
          <button onclick="viewInDocument('${item.document_id}', ${item.page}, '${encodeURIComponent(item.snippet)}')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs transition flex items-center space-x-1">
            <i data-lucide="book-open" class="w-3 h-3"></i>
            <span>Inspect Page</span>
          </button>
        </div>
        <p class="text-xs text-slate-300 leading-relaxed">${item.snippet}</p>
        <div class="text-[11px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-800/60">
          <span>Section: ${item.section}</span>
          <span>Dept: ${item.department}</span>
        </div>
      `;
      container.appendChild(card);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="text-center py-8 text-xs text-rose-400">Search error: ${err.message}</div>`;
  }
}

// COMPARE TAB LOGIC
async function runComparisonTest(question) {
  switchTab('compare');
  
  document.getElementById('compare-generic-answer').innerText = 'Generating baseline general response...';
  document.getElementById('compare-locallens-answer').innerText = 'Retrieving official Maharashtra Government Resolution...';

  try {
    const res = await fetch('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    const data = await res.json();

    document.getElementById('compare-generic-answer').innerText = data.generic_llm.answer;
    document.getElementById('compare-generic-citation').innerText = data.generic_llm.source_citation;
    document.getElementById('compare-generic-risk').innerText = data.generic_llm.risk;

    document.getElementById('compare-locallens-answer').innerText = data.locallens.answer;
    document.getElementById('compare-locallens-citation').innerText = data.locallens.source_citation;
    document.getElementById('compare-locallens-why').innerText = data.why_local_grounding_wins;
  } catch (err) {
    console.error('Comparison error:', err);
  }
}

// EVALUATION TAB LOGIC
async function loadLatestEvaluation() {
  try {
    const res = await fetch('/api/evaluation/latest');
    if (!res.ok) return;
    latestEvalReport = await res.json();
    renderEvalMetrics(latestEvalReport);
    renderEvalTable(latestEvalReport.results);
  } catch (err) {
    console.error('Failed to load evaluation metrics:', err);
  }
}

async function runLiveBenchmark() {
  const btn = document.getElementById('btn-run-benchmark');
  btn.disabled = true;
  btn.innerHTML = `<div class="w-3.5 h-3.5 border-2 border-white border-t-transparent animate-spin mr-1"></div> Running 50 Tests...`;

  try {
    const res = await fetch('/api/evaluation/run', { method: 'POST' });
    latestEvalReport = await res.json();
    renderEvalMetrics(latestEvalReport);
    renderEvalTable(latestEvalReport.results);
    alert(`Benchmark completed successfully! Evaluated 50 questions across 4 categories.`);
  } catch (err) {
    alert('Failed to execute benchmark: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="play-circle" class="w-4 h-4 mr-1"></i> Run 50-Question Benchmark`;
    if (window.lucide) lucide.createIcons();
  }
}

function renderEvalMetrics(report) {
  if (!report) return;
  document.getElementById('metric-accuracy').innerText = `${report.answer_accuracy}%`;
  document.getElementById('metric-citation').innerText = `${report.citation_accuracy}%`;
  document.getElementById('metric-recall').innerText = `${report.evidence_recall_at_5}%`;
  document.getElementById('metric-groundedness').innerText = `${report.groundedness_score}%`;
  document.getElementById('metric-hallucination').innerText = `${report.hallucination_rate}%`;
  document.getElementById('metric-abstention').innerText = `${report.correct_abstention_rate}%`;
}

function filterEvalCategory(cat) {
  currentEvalFilter = cat;
  const buttons = ['all', 'answerable', 'unanswerable', 'ambiguous', 'multilingual'];
  buttons.forEach(b => {
    const el = document.getElementById(`btn-eval-${b}`);
    if (el) {
      if (b === cat) {
        el.className = "px-3 py-1 bg-slate-800 text-white rounded-md border border-slate-700";
      } else {
        el.className = "px-3 py-1 bg-slate-900 text-slate-400 rounded-md border border-slate-800 hover:text-white";
      }
    }
  });

  if (latestEvalReport) {
    renderEvalTable(latestEvalReport.results);
  }
}

function renderEvalTable(results) {
  const tbody = document.getElementById('eval-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const filtered = results.filter(r => {
    if (currentEvalFilter === 'all') return true;
    return r.category.toLowerCase() === currentEvalFilter.toLowerCase();
  });

  filtered.forEach(r => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-850/50 transition";
    
    let outcomeBadge = "";
    if (r.hallucination) {
      outcomeBadge = `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-semibold text-[11px]">Hallucination</span>`;
    } else if (r.correct_abstention) {
      outcomeBadge = `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-semibold text-[11px]">Correct Abstention</span>`;
    } else if (r.correct) {
      outcomeBadge = `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-semibold text-[11px]">Correct & Grounded</span>`;
    } else {
      outcomeBadge = `<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold text-[11px]">Partial / Review</span>`;
    }

    tr.innerHTML = `
      <td class="py-3 px-4 font-mono text-[11px] text-slate-400">${r.id}</td>
      <td class="py-3 px-4 font-medium text-slate-100 max-w-md truncate">${r.question}</td>
      <td class="py-3 px-4 capitalize text-slate-400 font-mono text-[11px]">${r.category}</td>
      <td class="py-3 px-4 font-mono text-[11px] ${r.actual_answerable ? 'text-emerald-400' : 'text-slate-400'}">
        ${r.actual_answerable ? 'Yes' : 'Refused'}
      </td>
      <td class="py-3 px-4">${outcomeBadge}</td>
      <td class="py-3 px-4 font-mono text-slate-500">${r.latency_ms} ms</td>
      <td class="py-3 px-4 text-right">
        <button onclick="openInspectorModal('${r.id}')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded text-[11px] transition">
          Inspect
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function openInspectorModal(qid) {
  if (!latestEvalReport) return;
  const item = latestEvalReport.results.find(r => r.id === qid);
  if (!item) return;

  document.getElementById('modal-qid').innerText = item.id;
  document.getElementById('modal-title').innerText = `Question Test Inspector`;
  document.getElementById('modal-question').innerText = item.question;
  document.getElementById('modal-category').innerText = item.category;
  document.getElementById('modal-outcome').innerText = item.correct ? 'PASS (100% Grounded)' : 'FAIL';
  document.getElementById('modal-answer').innerText = item.answer;

  const sourcesDiv = document.getElementById('modal-sources');
  sourcesDiv.innerHTML = item.retrieved_sources.map(s => `• ${s}`).join('<br>') || 'None (Abstention)';

  document.getElementById('inspector-modal').classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function closeInspectorModal() {
  document.getElementById('inspector-modal').classList.add('hidden');
}

function exportBenchmarkJSON() {
  if (!latestEvalReport) return;
  const blob = new Blob([JSON.stringify(latestEvalReport, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `locallens_benchmark_${Date.now()}.json`;
  a.click();
}

function exportBenchmarkCSV() {
  if (!latestEvalReport) return;
  const rows = [
    ["ID", "Category", "Question", "Answerable", "Correct", "Hallucination", "Latency_MS"]
  ];
  latestEvalReport.results.forEach(r => {
    rows.push([
      r.id,
      r.category,
      `"${r.question.replace(/"/g, '""')}"`,
      r.actual_answerable,
      r.correct,
      r.hallucination,
      r.latency_ms
    ]);
  });
  const csvContent = rows.map(e => e.join(",")).join("\n");
  const blob = new Blob([csvContent], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `locallens_benchmark_${Date.now()}.csv`;
  a.click();
}

// COLLECTIONS TAB & DEPARTMENT SUMMARIES
const collectionSummaries = {
  "Higher & Technical Education": {
    name: "Higher & Technical Education Department",
    name_mr: "उच्च व तंत्रशिक्षण विभाग, महाराष्ट्र शासन",
    icon: "graduation-cap",
    overview: "Oversees university, technical, and professional education across Maharashtra. Responsible for ensuring equitable access to higher studies for economically weaker sections (EWS/EBC), maintaining state scholarship frameworks, and subsidizing student living allowances through statutory government resolutions.",
    metrics: [
      { label: "Target Beneficiaries", value: "EBC & Rural Students" },
      { label: "Income Limit", value: "₹8,00,000 / Year" },
      { label: "Key Welfare Modes", value: "50% Fee Waiver & Hostels" }
    ],
    schemes: [
      {
        id: "scheme_001_ebc_scholarship",
        title: "Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulkh Shishyavrutti Yojna (EBC)",
        title_mr: "राजर्षी छत्रपती शाहू महाराज शिक्षण शुल्क शिष्यवृत्ती योजना (ईबीसी)",
        gr_number: "TEM-2018/CR-142/TE-4",
        status: "current",
        summary: "Provides 50% tuition and exam fee reimbursement to students admitted under CAP in professional and non-professional higher education courses whose annual family income is up to ₹8,00,000.",
        rules: "Mandatory CAP admission; excludes Management & Institutional quota admissions; strictly maximum 2 children per family; minimum 50% attendance.",
        query: "What is the annual income limit for the EBC scholarship in Maharashtra?"
      },
      {
        id: "scheme_004_punjabrao_deshmukh_hostel",
        title: "Dr. Punjabrao Deshmukh Vastigruh Nirvah Bhatta Yojna (Hostel Allowance)",
        title_mr: "डॉ. पंजाबराव देशमुख वसतिगृह निर्वाह भत्ता योजना",
        gr_number: "HED-2021/CR-45/HE-2",
        status: "current",
        summary: "Offers direct monthly boarding and lodging subsistence allowance for children of registered marginal farmers and registered agricultural laborers pursuing higher professional education away from home.",
        rules: "Tier 1 cities (Mumbai, Pune, Nagpur, Nashik) receive ₹30,000/year; Tier 2 cities receive ₹20,000/year; marginal farmer certificate or 7/12 extract mandatory.",
        query: "Can a student from Nashik apply for Dr. Punjabrao Deshmukh hostel allowance?"
      }
    ]
  },
  "Women & Child Development": {
    name: "Women & Child Development Department",
    name_mr: "महिला व बालविकास विभाग, महाराष्ट्र शासन",
    icon: "heart",
    overview: "Directs statewide welfare initiatives, economic independence schemes, nutritional security, and financial empowerment programs for women and children in Maharashtra. Notable for spearheading direct benefit transfer (DBT) safety nets.",
    metrics: [
      { label: "Target Beneficiaries", value: "Women aged 21 to 65" },
      { label: "Monthly Benefit", value: "₹1,500 Direct DBT" },
      { label: "Income Threshold", value: "₹2,50,000 / Year" }
    ],
    schemes: [
      {
        id: "scheme_002_ladki_bahin_v2",
        title: "Mukhyamantri Majhi Ladki Bahin Yojna (Revised Resolution v2.1)",
        title_mr: "मुख्यमंत्री माझी लाडकी बहीण योजना (सुधारित शासन निर्णय आवृत्ती २.१)",
        gr_number: "WCD-2024/CR-89/W-2",
        status: "current",
        summary: "Flagship women empowerment scheme transferring ₹1,500/month directly into Aadhaar-linked bank accounts of eligible resident women. Revised resolution extended age limits and relaxed domicile proof to include yellow/orange ration cards.",
        rules: "Eligible age: 21 to 65 years; annual household income under ₹2.5 lakh; applicants possessing 4-wheeler vehicle (except tractor) or family income tax payee disqualified.",
        query: "मुख्यमंत्री माझी लाडकी बहीण योजनेसाठी वयाची अट काय आहे?"
      },
      {
        id: "scheme_003_ladki_bahin_v1_deprecated",
        title: "Mukhyamantri Majhi Ladki Bahin Yojna (Initial Resolution v1.0 - Superseded)",
        title_mr: "मुख्यमंत्री माझी लाडकी बहीण योजना (मूळ शासन निर्णय - कालबाह्य)",
        gr_number: "WCD-2024/CR-71/W-2",
        status: "outdated",
        summary: "The initial June 2024 launch resolution with earlier age bracket (21-60 years) and original 15-day application window, subsequently superseded and expanded by Resolution v2.1.",
        rules: "Historical superseded draft preserved for contradiction testing and legal version provenance.",
        query: "What was the application deadline in the June 2024 order of Ladki Bahin Yojna vs current resolution?"
      }
    ]
  },
  "Public Health Department": {
    name: "Public Health Department",
    name_mr: "सार्वजनिक आरोग्य विभाग, महाराष्ट्र शासन",
    icon: "activity",
    overview: "Administers secondary and tertiary public healthcare services, state health assurance programs, hospital networks, and universal health coverage across Maharashtra, protecting families from catastrophic healthcare expenses.",
    metrics: [
      { label: "Health Cover", value: "₹5,00,000 / Family" },
      { label: "Procedures Covered", value: "1,356 Medical Surgeries" },
      { label: "Coverage Scope", value: "Universal (All Citizens)" }
    ],
    schemes: [
      {
        id: "scheme_006_mjpjay_health_scheme",
        title: "Mahatma Jyotirao Phule Jan Arogya Yojna (MJPJAY 2.0 Universal Health Scheme)",
        title_mr: "महात्मा ज्योतिराव फुले जन आरोग्य योजना (विस्तारित २.०)",
        gr_number: "PHD-2024/CR-198/Health-6",
        status: "current",
        summary: "Universal cashless health insurance coverage providing up to ₹5,00,000 per family per year across 1,356 identified secondary and tertiary surgeries in empaneled network hospitals.",
        rules: "Expanded in 2024 to cover all ration card holding citizens of Maharashtra; Ayushman Bharat ABHA card or ration card valid for admission.",
        query: "What is the annual health coverage limit under MJPJAY in Maharashtra?"
      }
    ]
  },
  "Energy & Mahavitaran": {
    name: "Energy Department & Mahavitaran (MSEDCL)",
    name_mr: "ऊर्जा विभाग आणि महावितरण, महाराष्ट्र शासन",
    icon: "zap",
    overview: "Responsible for power generation, transmission, and state rural electrification. Formulates statutory tariff subsidy regulations and agricultural pump electricity waivers to support rural farming productivity.",
    metrics: [
      { label: "Agricultural Subsidy", value: "100% Electricity Free" },
      { label: "Pump Capacity", value: "Up to 7.5 Horsepower" },
      { label: "Scheme Duration", value: "5 Years (2024-2029)" }
    ],
    schemes: [
      {
        id: "scheme_007_baliraja_vij_savalat",
        title: "Mukhyamantri Baliraja Vij Savalat Yojna (Agricultural Electricity Waiver)",
        title_mr: "मुख्यमंत्री बळीराजा मोफत वीज सवलत योजना",
        gr_number: "ENG-2024/CR-312/Power-2",
        status: "current",
        summary: "Provides complete 100% waiver of electricity bill payments for agricultural pump connections up to 7.5 HP capacity, with government depositing the full tariff directly to Mahavitaran.",
        rules: "Applies to registered agricultural power connections up to 7.5 HP; commercial agricultural setups and poultry/dairy industrial meters excluded.",
        query: "Which farmers are eligible for free electricity under Baliraja Vij Savalat Yojna?"
      }
    ]
  },
  "Social Justice & Special Assistance": {
    name: "Social Justice and Special Assistance Department",
    name_mr: "सामाजिक न्याय व विशेष सहाय्य विभाग, महाराष्ट्र शासन",
    icon: "users",
    overview: "Formulates social defense policies, affirmative action measures, destitute support grants, and higher education residential stipends for Scheduled Castes, Navabuddha, senior citizens, and differently-abled individuals.",
    metrics: [
      { label: "Target Groups", value: "SC, Destitute, Divyang" },
      { label: "Monthly Pension", value: "₹1,500 Assistance" },
      { label: "Student Stipend", value: "Up to ₹60,000 / Year" }
    ],
    schemes: [
      {
        id: "scheme_005_sanjay_gandhi_niradhar",
        title: "Sanjay Gandhi Niradhar Anudan Yojna (Financial Assistance for Destitute)",
        title_mr: "संजय गांधी निराधार अनुदान योजना",
        gr_number: "SJD-2023/CR-112/BCW-3",
        status: "current",
        summary: "Offers non-contributory monthly financial maintenance pension (₹1,500/month for single beneficiary, ₹2,400 for 2+ dependents) to destitute senior citizens, persons with severe disabilities, and widows.",
        rules: "Annual income limit ₹21,000; minimum 15 years domicile in Maharashtra; severe disability minimum 40% civil surgeon certificate.",
        query: "What is the monthly financial assistance under Sanjay Gandhi Niradhar Anudan Yojna?"
      },
      {
        id: "scheme_009_swadhar_yojna",
        title: "Dr. Babasaheb Ambedkar Swadhar Yojna for SC Students",
        title_mr: "भारतरत्न डॉ. बाबासाहेब आंबेडकर स्वाधार योजना",
        gr_number: "SJD-2022/CR-88/Edu-4",
        status: "current",
        summary: "Cash stipend covering hostel accommodation, mess, books, and living expenses for Scheduled Caste and Navabuddha students who did not secure admission into government hostels.",
        rules: "Income ceiling ₹2.5 lakh; student must be studying in recognized degree/diploma college; Tier 1 cities receive ₹60,000/year, other districts ₹51,000/year.",
        query: "What is the annual financial assistance for SC students under Swadhar Yojna?"
      }
    ]
  },
  "School Education & Sports": {
    name: "School Education and Sports Department",
    name_mr: "शालेय शिक्षण व क्रीडा विभाग, महाराष्ट्र शासन",
    icon: "book-open",
    overview: "Governs foundational, primary, and secondary education across the state. Oversees implementation of the Right to Free and Compulsory Education (RTE) Act and monitors mandatory private school admission quotas.",
    metrics: [
      { label: "RTE Quota", value: "25% Seats in Grade 1" },
      { label: "School Fees", value: "100% Free Tuition" },
      { label: "Income Limit", value: "₹1,00,000 / Year (EWS)" }
    ],
    schemes: [
      {
        id: "scheme_008_rte_maharashtra",
        title: "Right to Education (RTE) 25% Free Admission Scheme Maharashtra",
        title_mr: "बालकांचा मोफत व सक्तीच्या शिक्षणाचा अधिकार (आरटीई) २५% प्रवेश योजना",
        gr_number: "RTE-2024/CR-62/PE-1",
        status: "current",
        summary: "Mandates 25% quota of seats at pre-primary/Class 1 entry level in non-aided private schools reserved for children belonging to economically weaker sections and disadvantaged groups with zero school fees.",
        rules: "Annual income limit for EWS is ₹1,00,000 (no income limit for SC/ST); child must reside within 1 km (primary) to 3 km (secondary) radius of the school.",
        query: "What is the income criteria for RTE 25 percent admission in Maharashtra?"
      }
    ]
  },
  "General Administration & RTS": {
    name: "General Administration Department (RTS)",
    name_mr: "सामान्य प्रशासन विभाग (लोकसेवा हक्क आयोग), महाराष्ट्र शासन",
    icon: "shield-check",
    overview: "Drives transparency, e-governance, administrative reforms, and citizen delivery charters through the statutory Maharashtra Right to Public Services Act (RTS), operating via the Aaple Sarkar citizen portal.",
    metrics: [
      { label: "Citizen Services", value: "500+ Public Services" },
      { label: "Statutory Deadline", value: "Mandatory (7 to 21 Days)" },
      { label: "Legal Recourse", value: "Two-Tier Appellate System" }
    ],
    schemes: [
      {
        id: "scheme_010_rts_citizen_services",
        title: "Maharashtra Right to Public Services Act (RTS - Aaple Sarkar Delivery Standards)",
        title_mr: "महाराष्ट्र लोकसेवा हक्क अधिनियम (आपले सरकार सेवा हमी मानके)",
        gr_number: "RTS-2023/CR-29/GAD-1",
        status: "current",
        summary: "Legally guarantees transparent, efficient, and time-bound delivery of notified public certificates (Income Certificate in 15 days, Domicile in 15 days, Caste in 21 days) with financial penalties on defaulting officers.",
        rules: "Right to First Appeal within 30 days of default, and Second Appeal to the RTS Commissioner; tracking via 15-digit application token.",
        query: "What is the statutory deadline for an Income Certificate under Maharashtra RTS?"
      }
    ]
  }
};

function renderCollections() {
  const container = document.getElementById('collections-grid');
  if (!container) return;

  const categories = [
    { name: "Higher & Technical Education", icon: "graduation-cap", count: 2, schemes: "EBC Scholarship, Punjabrao Deshmukh Hostel Allowance" },
    { name: "Women & Child Development", icon: "heart", count: 2, schemes: "Majhi Ladki Bahin Yojna (v1.0 & v2.1 resolutions)" },
    { name: "Public Health Department", icon: "activity", count: 1, schemes: "Mahatma Jyotirao Phule Jan Arogya (MJPJAY 2.0)" },
    { name: "Energy & Mahavitaran", icon: "zap", count: 1, schemes: "Mukhyamantri Baliraja Vij Savalat Yojna" },
    { name: "Social Justice & Special Assistance", icon: "users", count: 2, schemes: "Sanjay Gandhi Niradhar, Swadhar Yojna" },
    { name: "School Education & Sports", icon: "book-open", count: 1, schemes: "Right to Education (RTE) 25% Free Admission" },
    { name: "General Administration & RTS", icon: "shield-check", count: 1, schemes: "Right to Public Services Act (Aaple Sarkar)" }
  ];

  container.innerHTML = '';
  categories.forEach(c => {
    const card = document.createElement('div');
    card.className = "bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 hover:border-brand-500/70 hover:bg-slate-850/80 transition-all cursor-pointer group shadow-lg transform hover:-translate-y-1 select-none";
    card.onclick = () => openCollectionModal(c.name);
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="w-10 h-10 rounded-xl bg-brand-500/10 text-brand-400 group-hover:bg-brand-500/20 group-hover:scale-105 transition flex items-center justify-center">
          <i data-lucide="${c.icon}" class="w-5 h-5"></i>
        </div>
        <span class="text-xs font-mono px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 group-hover:bg-brand-500/15 group-hover:text-brand-300 transition font-semibold">${c.count} Document${c.count === 1 ? '' : 's'}</span>
      </div>
      <div>
        <h4 class="text-sm font-bold text-white group-hover:text-brand-300 transition">${c.name}</h4>
        <p class="text-xs text-slate-400 mt-1 leading-relaxed">${c.schemes}</p>
      </div>
      <div class="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-800/80">
        <span class="text-emerald-400 flex items-center space-x-1.5 font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>Indexed & Grounded</span>
        </span>
        <span class="text-brand-400 group-hover:text-brand-300 font-semibold flex items-center space-x-1 transition">
          <span>View Summary</span>
          <i data-lucide="arrow-right" class="w-3.5 h-3.5 group-hover:translate-x-1 transition"></i>
        </span>
      </div>
    `;
    container.appendChild(card);
  });

  if (window.lucide) lucide.createIcons();
}

function openCollectionModal(catName) {
  const data = collectionSummaries[catName];
  if (!data) return;

  const titleEl = document.getElementById('col-modal-title');
  const titleMrEl = document.getElementById('col-modal-title-mr');
  const countBadge = document.getElementById('col-modal-count-badge');
  const iconContainer = document.getElementById('col-modal-icon-container');
  const overviewEl = document.getElementById('col-modal-overview');
  const metricsGrid = document.getElementById('col-modal-metrics-grid');
  const schemesList = document.getElementById('col-modal-schemes-list');

  if (titleEl) titleEl.innerText = data.name;
  if (titleMrEl) titleMrEl.innerText = data.name_mr;
  if (countBadge) countBadge.innerText = `${data.schemes.length} Official Document${data.schemes.length === 1 ? '' : 's'}`;
  if (iconContainer) iconContainer.innerHTML = `<i data-lucide="${data.icon}" class="w-6 h-6"></i>`;
  if (overviewEl) overviewEl.innerText = data.overview;

  if (metricsGrid) {
    metricsGrid.innerHTML = data.metrics.map(m => `
      <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-1">
        <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">${m.label}</span>
        <div class="text-xs sm:text-sm font-bold text-white">${m.value}</div>
      </div>
    `).join('');
  }

  if (schemesList) {
    schemesList.innerHTML = data.schemes.map(s => {
      const isOutdated = s.status === 'outdated';
      const badge = isOutdated 
        ? `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">⚠️ Superseded v1.0</span>`
        : `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">🟢 Active Resolution</span>`;

      return `
        <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3 hover:border-slate-700 transition">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 border-b border-slate-850 pb-2">
            <div>
              <h5 class="text-xs sm:text-sm font-bold text-white">${s.title}</h5>
              <div class="text-[11px] text-slate-400 mt-0.5 font-medium">${s.title_mr}</div>
            </div>
            <div class="flex items-center space-x-2 shrink-0">
              <span class="text-[10px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">${s.gr_number}</span>
              ${badge}
            </div>
          </div>

          <div class="text-xs text-slate-300 space-y-2">
            <p class="leading-relaxed"><strong class="text-slate-200">Scheme Objective:</strong> ${s.summary}</p>
            <div class="p-2.5 bg-slate-900/80 rounded-lg border border-slate-800/80 text-[11px] leading-relaxed">
              <strong class="text-amber-300">Rules & Eligibility:</strong> ${s.rules}
            </div>
          </div>

          <div class="flex items-center justify-end space-x-2 pt-1 text-xs">
            <button onclick="viewInDocument('${s.id}', 1, ''); closeCollectionModal();" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold transition flex items-center space-x-1.5 cursor-pointer">
              <i data-lucide="book-open" class="w-3.5 h-3.5 text-brand-400"></i>
              <span>Read Official GR</span>
            </button>
            <button onclick="switchTab('ask'); setQuery('${s.query.replace(/'/g, "\\'")}'); closeCollectionModal();" class="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold transition flex items-center space-x-1.5 shadow-sm cursor-pointer">
              <i data-lucide="message-square" class="w-3.5 h-3.5"></i>
              <span>Ask About Scheme</span>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  const modal = document.getElementById('collection-summary-modal');
  if (modal) modal.classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function closeCollectionModal() {
  const modal = document.getElementById('collection-summary-modal');
  if (modal) modal.classList.add('hidden');
}


// INGEST PIPELINE
async function handleIngestSubmit(e) {
  e.preventDefault();
  const title = document.getElementById('ingest-title').value;
  const dept = document.getElementById('ingest-dept').value;
  const cat = document.getElementById('ingest-cat').value;
  const date = document.getElementById('ingest-date').value;
  const ver = document.getElementById('ingest-ver').value;
  const text = document.getElementById('ingest-text').value;

  const btn = document.getElementById('btn-ingest');
  btn.disabled = true;
  btn.innerText = 'Executing 6-Stage Ingestion Pipeline...';

  const formData = new FormData();
  formData.append('title', title);
  formData.append('department', dept);
  formData.append('category', cat);
  formData.append('publication_date', date);
  formData.append('version', ver);
  formData.append('raw_text', text);

  try {
    const res = await fetch('/api/ingest', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    alert(`Success! Indexed document '${title}' with ${data.chunks_indexed} new chunks!`);
    await loadDocuments();
  } catch (err) {
    alert('Ingest error: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerText = 'Process & Index Document';
  }
}

// JUDGE DEMO MODE
const demoStages = [
  {
    step: 1,
    title: "1. The Local Knowledge Dilemma",
    narration: "A student asks: «Can a student admitted through Management Quota apply for the Maharashtra EBC Scholarship?» General AI guesses yes with an affidavit. LocalLens retrieves the exact Government Resolution.",
    actionQuery: "Can a student admitted through Management Quota apply for the EBC Scholarship in Maharashtra?",
    buttonText: "Ask LocalLens & Inspect Rule"
  },
  {
    step: 2,
    title: "2. Verifiable Evidence Passage (AI + Evidence)",
    narration: "Instead of 'Trust Me Bro', LocalLens renders an Evidence Card citing Page 2, Section 2.2: Management Quota admissions are explicitly disqualified. Centralized Admission Process (CAP) merit is strictly mandatory.",
    actionQuery: "What is the annual income limit for the EBC scholarship in Maharashtra?",
    buttonText: "Verify EBC ₹8,00,000 Income Limit"
  },
  {
    step: 3,
    title: "3. 1-Click Page Jump & Document Glow",
    narration: "Clicking 'View in Document' immediately opens the integrated reader, navigates to Page 2, and renders the verbatim quote with an amber glowing highlight.",
    actionQuery: null,
    buttonText: "Jump Directly to Document Reader"
  },
  {
    step: 4,
    title: "4. Disciplined Zero-Hallucination Abstention",
    narration: "Ask something absent from the knowledge base: «Does Maharashtra offer a free Tesla scheme for farmers?» Rather than inventing an answer, LocalLens says: «I couldn't find this information in the available documents.»",
    actionQuery: "Does Maharashtra offer a free Tesla electric vehicle scheme for agricultural pump owners?",
    buttonText: "Test Disciplined Abstention"
  },
  {
    step: 5,
    title: "5. Multilingual Local Language Intelligence (मराठी)",
    narration: "Ask in Marathi: «मुख्यमंत्री माझी लाडकी बहीण योजनेसाठी वयाची अट काय आहे?». The system retrieves the official GR and answers in Marathi with official citations.",
    actionQuery: "मुख्यमंत्री माझी लाडकी बहीण योजनेसाठी वयाची अट काय आहे?",
    buttonText: "Test Marathi Local Query"
  },
  {
    step: 6,
    title: "6. Real Contradiction Detection & Live Benchmarks",
    narration: "The June 2024 preliminary order stated age 60 and deadline 15 July. The August 2024 revision expanded age to 65. LocalLens flags conflicting GRs and advises relying on the latest resolution.",
    actionQuery: "What was the application deadline in the June 2024 order of Ladki Bahin Yojna vs current resolution?",
    buttonText: "Inspect Contradiction & Benchmark"
  }
];

function setDemoStage(stageNum) {
  currentDemoStage = stageNum;
  const stage = demoStages[stageNum - 1];

  for (let i = 1; i <= 6; i++) {
    const btn = document.getElementById(`demo-step-${i}`);
    if (btn) {
      if (i === stageNum) {
        btn.className = "demo-step-btn p-3 rounded-xl bg-amber-500 text-slate-950 font-bold border border-amber-400 text-left transition shadow-lg";
      } else {
        btn.className = "demo-step-btn p-3 rounded-xl bg-slate-900 text-slate-400 border border-slate-800 text-left transition hover:text-white";
      }
    }
  }

  document.getElementById('demo-stage-title').innerText = stage.title;
  document.getElementById('demo-stage-narration').innerHTML = stage.narration;

  const actionBox = document.getElementById('demo-stage-action-box');
  actionBox.innerHTML = `
    <div class="flex items-center justify-between">
      <div class="text-xs text-slate-300 font-mono">
        ${stage.actionQuery ? `Query: <strong>${stage.actionQuery}</strong>` : 'Action: Interactive Page Jump Demonstration'}
      </div>
      <button onclick="executeDemoAction(${stageNum})" class="px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-500 text-slate-950 font-bold text-xs rounded-lg shadow transition hover:opacity-95">
        ${stage.buttonText}
      </button>
    </div>
  `;
}

function prevDemoStage() {
  if (currentDemoStage > 1) setDemoStage(currentDemoStage - 1);
}

function nextDemoStage() {
  if (currentDemoStage < 6) setDemoStage(currentDemoStage + 1);
}

function executeDemoAction(stageNum) {
  const stage = demoStages[stageNum - 1];
  if (stageNum === 3) {
    viewInDocument('scheme_001_ebc_scholarship', 2, 'Candidates admitted under Management Quota, Institute Level Quota');
    return;
  }
  if (stageNum === 6) {
    switchTab('ask');
    setQuery(stage.actionQuery);
    return;
  }
  if (stage.actionQuery) {
    switchTab('ask');
    setQuery(stage.actionQuery);
  }
}

// =====================================================================
// AI DOCUMENT UPLOAD & QUESTION ANSWERING MODULE
// =====================================================================

let userSessionId = null;
let userDocuments = [];

function getUserSessionId() {
  if (!userSessionId) {
    userSessionId = localStorage.getItem('locallens-user-session');
    if (!userSessionId) {
      userSessionId = 'sess_' + Math.random().toString(36).substring(2, 10);
      localStorage.setItem('locallens-user-session', userSessionId);
    }
  }
  return userSessionId;
}

function resetUserSession() {
  userSessionId = 'sess_' + Math.random().toString(36).substring(2, 10);
  localStorage.setItem('locallens-user-session', userSessionId);
  const badge = document.getElementById('user-session-label');
  if (badge) badge.innerText = userSessionId;
  userDocuments = [];
  renderUserDocumentsTable();
  const resultBox = document.getElementById('user-qa-result-box');
  if (resultBox) resultBox.classList.add('hidden');
  const errorBox = document.getElementById('user-doc-error-box');
  if (errorBox) errorBox.classList.add('hidden');
  loadUserDocuments();
}

async function initUserDocuments() {
  const sess = getUserSessionId();
  const badge = document.getElementById('user-session-label');
  if (badge) badge.innerText = sess;
  await loadUserDocuments();
}

function handleUserDragOver(e) {
  e.preventDefault();
  e.stopPropagation();
  const dropzone = document.getElementById('user-upload-dropzone');
  if (dropzone) {
    dropzone.classList.add('border-brand-500', 'bg-brand-500/5');
  }
}

function handleUserDragLeave(e) {
  e.preventDefault();
  e.stopPropagation();
  const dropzone = document.getElementById('user-upload-dropzone');
  if (dropzone) {
    dropzone.classList.remove('border-brand-500', 'bg-brand-500/5');
  }
}

function handleUserDrop(e) {
  e.preventDefault();
  e.stopPropagation();
  const dropzone = document.getElementById('user-upload-dropzone');
  if (dropzone) {
    dropzone.classList.remove('border-brand-500', 'bg-brand-500/5');
  }
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    uploadUserPdfFiles(e.dataTransfer.files);
  }
}

function handleUserPdfUpload(e) {
  if (e.target && e.target.files && e.target.files.length > 0) {
    uploadUserPdfFiles(e.target.files);
  }
}

function setUploadStep(stepNum, label, percent) {
  const pBar = document.getElementById('user-progress-bar');
  const pPct = document.getElementById('user-progress-percentage');
  const pDesc = document.getElementById('user-progress-status-desc');
  
  if (pBar) pBar.style.width = percent + '%';
  if (pPct) pPct.innerText = percent + '%';
  if (pDesc) pDesc.innerText = label;

  for (let i = 1; i <= 6; i++) {
    const el = document.getElementById(`prog-step-${i}`);
    if (el) {
      if (i < stepNum) {
        el.className = "p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-center font-medium";
      } else if (i === stepNum) {
        el.className = "p-2 rounded-lg bg-brand-600 text-white border border-brand-400 text-center font-bold shadow-md animate-pulse";
      } else {
        el.className = "p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-500 text-center font-medium";
      }
    }
  }
}

async function uploadUserPdfFiles(fileList) {
  const errorBox = document.getElementById('user-doc-error-box');
  const errorMsg = document.getElementById('user-doc-error-message');
  if (errorBox) errorBox.classList.add('hidden');

  const pdfFiles = Array.from(fileList).filter(f => f.name.toLowerCase().endsWith('.pdf'));
  if (pdfFiles.length === 0) {
    if (errorBox && errorMsg) {
      errorMsg.innerText = "Please select valid PDF documents (.pdf). Other formats are not supported.";
      errorBox.classList.remove('hidden');
    }
    return;
  }

  // Check for empty 0-byte files
  for (const f of pdfFiles) {
    if (f.size === 0) {
      if (errorBox && errorMsg) {
        errorMsg.innerText = `File '${f.name}' is empty (0 bytes). Please upload a valid non-empty PDF.`;
        errorBox.classList.remove('hidden');
      }
      return;
    }
  }

  const progressContainer = document.getElementById('user-upload-progress');
  const fileNameLabel = document.getElementById('user-progress-file-name');
  if (progressContainer) progressContainer.classList.remove('hidden');
  if (fileNameLabel) {
    fileNameLabel.innerText = pdfFiles.length === 1 
      ? `Processing: ${pdfFiles[0].name}` 
      : `Processing ${pdfFiles.length} PDF Documents...`;
  }

  // 1. Stage 1: Uploading...
  setUploadStep(1, "Uploading PDF byte stream to server...", 15);
  await new Promise(r => setTimeout(r, 250));

  // 2. Stage 2: Reading PDF...
  setUploadStep(2, "Reading PDF catalog, stream structures, and logical pages...", 35);
  await new Promise(r => setTimeout(r, 250));

  // 3. Stage 3: Checking for scanned pages...
  setUploadStep(3, "Checking for digital font descriptors vs rasterized scanned pages...", 55);
  await new Promise(r => setTimeout(r, 250));

  // 4. Stage 4: Extracting text / Running OCR...
  setUploadStep(4, "Extracting text and running Windows Native OCR on image pages...", 75);

  const formData = new FormData();
  formData.append('session_id', getUserSessionId());
  for (const f of pdfFiles) {
    formData.append('files', f);
  }

  try {
    const res = await fetch('/api/user-docs/upload', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(errData.detail || 'Failed to process document upload.');
    }

    const data = await res.json();

    // Check if individual file had an error
    const errors = data.results.filter(r => r.status === 'error');
    if (errors.length > 0) {
      const errTexts = errors.map(e => `• ${e.filename}: ${e.error_message}`).join('<br>');
      if (errorBox && errorMsg) {
        errorMsg.innerHTML = `Some files could not be processed:<br>${errTexts}`;
        errorBox.classList.remove('hidden');
      }
    }

    // 5. Stage 5: Creating knowledge base...
    setUploadStep(5, "Building structure-aware chunks, headings, and BM25 hybrid indices...", 90);
    await new Promise(r => setTimeout(r, 350));

    // 6. Stage 6: Ready for questions ✓
    setUploadStep(6, "Knowledge base created successfully! Ready for grounded questions.", 100);

    // Refresh document library table
    await loadUserDocuments();

    // Reset file input
    const fileInput = document.getElementById('user-doc-file-input');
    if (fileInput) fileInput.value = '';

    // Hide progress bar after 2 seconds
    setTimeout(() => {
      if (progressContainer) progressContainer.classList.add('hidden');
    }, 2000);

  } catch (err) {
    if (errorBox && errorMsg) {
      errorMsg.innerText = err.message || "An unexpected error occurred during document upload.";
      errorBox.classList.remove('hidden');
    }
    if (progressContainer) progressContainer.classList.add('hidden');
  }
}

async function loadUserDocuments() {
  const sess = getUserSessionId();
  try {
    const res = await fetch(`/api/user-docs?session_id=${encodeURIComponent(sess)}`);
    if (res.ok) {
      userDocuments = await res.json();
      renderUserDocumentsTable();
      updateUserDocFilterDropdown();
    }
  } catch (e) {
    console.error('Failed to load user documents:', e);
  }
}

function renderUserDocumentsTable() {
  const countBadge = document.getElementById('user-docs-count-badge');
  const emptyState = document.getElementById('user-docs-empty-state');
  const tableWrapper = document.getElementById('user-docs-table-wrapper');
  const tbody = document.getElementById('user-docs-tbody');

  if (countBadge) {
    countBadge.innerText = `${userDocuments.length} Document${userDocuments.length === 1 ? '' : 's'}`;
  }

  if (!userDocuments || userDocuments.length === 0) {
    if (emptyState) emptyState.classList.remove('hidden');
    if (tableWrapper) tableWrapper.classList.add('hidden');
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');
  if (tableWrapper) tableWrapper.classList.remove('hidden');

  if (tbody) {
    tbody.innerHTML = '';
    userDocuments.forEach(doc => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-slate-950/30 transition";

      // Method Badge
      let methodBadge = '';
      if (doc.is_scanned) {
        const pagesStr = doc.ocr_pages && doc.ocr_pages.length > 0 ? ` (Pages ${doc.ocr_pages.join(', ')})` : '';
        methodBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">📷 Scanned • Native OCR${pagesStr}</span>`;
      } else {
        methodBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">🔍 Digital Text Extracted</span>`;
      }

      tr.innerHTML = `
        <td class="py-3 px-3">
          <div class="flex items-center space-x-2">
            <i data-lucide="file-text" class="w-4 h-4 text-brand-400 shrink-0"></i>
            <div>
              <div class="font-bold text-white text-xs">${doc.filename}</div>
              <div class="text-[10px] text-slate-500 font-mono">${(doc.file_size_bytes / 1024).toFixed(1)} KB • ${doc.uploaded_at}</div>
            </div>
          </div>
        </td>
        <td class="py-3 px-3">
          <span class="font-mono text-slate-300 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-[11px]">${doc.page_count} Page${doc.page_count === 1 ? '' : 's'}</span>
        </td>
        <td class="py-3 px-3">
          ${methodBadge}
        </td>
        <td class="py-3 px-3">
          <span class="inline-flex items-center space-x-1 text-emerald-400 text-[11px] font-medium">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Ready for Questions</span>
          </span>
        </td>
        <td class="py-3 px-3 text-right">
          <div class="flex items-center justify-end space-x-1.5">
            <button onclick="openUserSummaryModal('${doc.doc_id}')" class="px-2.5 py-1 bg-brand-600/20 hover:bg-brand-600/30 text-brand-300 border border-brand-500/30 rounded text-[11px] transition flex items-center space-x-1" title="View Document Summary">
              <i data-lucide="file-bar-chart-2" class="w-3 h-3"></i>
              <span>View Summary</span>
            </button>
            <button onclick="deleteUserDocument('${doc.doc_id}')" class="px-2 py-1 bg-rose-950/30 hover:bg-rose-900/40 text-rose-300 border border-rose-800/40 rounded text-[11px] transition" title="Delete Document">
              <i data-lucide="trash-2" class="w-3 h-3"></i>
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  if (window.lucide) lucide.createIcons();
}

function updateUserDocFilterDropdown() {
  const select = document.getElementById('user-qa-doc-filter');
  if (!select) return;

  const currentVal = select.value;
  select.innerHTML = '<option value="all">All Uploaded Documents</option>';

  userDocuments.forEach(doc => {
    const opt = document.createElement('option');
    opt.value = doc.doc_id;
    opt.innerText = `${doc.filename} (${doc.page_count} pages)`;
    select.appendChild(opt);
  });

  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) {
    select.value = currentVal;
  }
}

async function deleteUserDocument(docId) {
  if (!confirm('Are you sure you want to remove this document from your session knowledge base?')) {
    return;
  }
  const sess = getUserSessionId();
  try {
    const res = await fetch(`/api/user-docs/${encodeURIComponent(docId)}?session_id=${encodeURIComponent(sess)}`, {
      method: 'DELETE'
    });
    if (res.ok) {
      await loadUserDocuments();
      const resultBox = document.getElementById('user-qa-result-box');
      if (resultBox) resultBox.classList.add('hidden');
    }
  } catch (e) {
    alert('Failed to delete document: ' + e.message);
  }
}

async function openUserSummaryModal(docId) {
  const sess = getUserSessionId();
  try {
    const res = await fetch(`/api/user-docs/${encodeURIComponent(docId)}/summary?session_id=${encodeURIComponent(sess)}`);
    if (!res.ok) throw new Error('Summary not found.');
    const summary = await res.json();

    document.getElementById('sum-modal-filename').innerText = summary.filename;
    document.getElementById('sum-modal-short').innerText = summary.short_summary;

    const topicsDiv = document.getElementById('sum-modal-topics');
    topicsDiv.innerHTML = summary.main_topics.map(t => 
      `<span class="px-2.5 py-1 bg-brand-500/10 text-brand-300 border border-brand-500/20 rounded-md font-medium text-[11px]">${t}</span>`
    ).join('') || '<span class="text-slate-500">None detected</span>';

    const datesDiv = document.getElementById('sum-modal-dates');
    datesDiv.innerHTML = summary.important_dates.map(d => 
      `<div class="flex items-center space-x-1.5"><i data-lucide="calendar" class="w-3 h-3 text-amber-400"></i><span>${d}</span></div>`
    ).join('') || '<div class="text-slate-500">No explicit statutory dates found</div>';

    const rulesDiv = document.getElementById('sum-modal-rules');
    rulesDiv.innerHTML = summary.important_rules.map(r => 
      `<div class="p-2.5 bg-slate-950 border-l-4 border-amber-500 rounded-r-lg border-y border-r border-slate-800 text-xs leading-relaxed">${r}</div>`
    ).join('') || '<div class="text-slate-500">Standard regulations apply</div>';

    const keyDiv = document.getElementById('sum-modal-keypoints');
    keyDiv.innerHTML = summary.key_points.map(k => 
      `<div class="flex items-start space-x-2 text-xs"><span class="text-emerald-400 font-bold mt-0.5">•</span><span class="leading-relaxed">${k}</span></div>`
    ).join('') || '<div class="text-slate-500">Complete text indexed</div>';

    document.getElementById('user-summary-modal').classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    alert('Could not open summary: ' + err.message);
  }
}

function closeUserSummaryModal() {
  document.getElementById('user-summary-modal').classList.add('hidden');
}

function setUserQuery(questionText) {
  const input = document.getElementById('user-qa-input');
  if (input) {
    input.value = questionText;
    handleUserDocQuerySubmit(new Event('submit'));
  }
}

async function handleUserDocQuerySubmit(e) {
  if (e && e.preventDefault) e.preventDefault();

  const input = document.getElementById('user-qa-input');
  const question = input ? input.value.trim() : '';
  if (!question) return;

  const docFilter = document.getElementById('user-qa-doc-filter');
  const targetDocId = docFilter ? docFilter.value : 'all';

  const loading = document.getElementById('user-qa-loading');
  const resultBox = document.getElementById('user-qa-result-box');
  const submitBtn = document.getElementById('btn-user-qa-submit');

  if (loading) loading.classList.remove('hidden');
  if (resultBox) resultBox.classList.add('hidden');
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch('/api/user-docs/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: getUserSessionId(),
        question: question,
        doc_id: targetDocId
      })
    });

    const data = await res.json();

    // Populate Results
    const badge = document.getElementById('user-qa-status-badge');
    const answerEl = document.getElementById('user-qa-answer-text');
    const latencyEl = document.getElementById('user-qa-latency');
    const scopeEl = document.getElementById('user-qa-scope-label');
    const citationsSec = document.getElementById('user-qa-citations-section');
    const citationsList = document.getElementById('user-qa-citations-list');

    if (latencyEl) latencyEl.innerText = `${data.latency_ms} ms`;
    if (scopeEl) scopeEl.innerText = data.target_doc_name || 'All Docs';

    if (data.is_sufficient) {
      if (badge) {
        badge.className = "inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
        badge.innerHTML = `<i data-lucide="shield-check" class="w-3.5 h-3.5"></i><span>Grounded in Uploaded Documents (Zero Hallucination)</span>`;
      }
      if (answerEl) {
        // Simple markdown bold conversion
        answerEl.innerHTML = data.answer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      }

      // Render Citations
      if (citationsSec) citationsSec.classList.remove('hidden');
      if (citationsList) {
        citationsList.innerHTML = '';
        (data.citations || []).forEach(c => {
          const card = document.createElement('div');
          card.className = "bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-2 hover:border-slate-700 transition";
          
          const safeSnippet = (c.snippet || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
          const safeHeading = (c.heading || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');

          card.innerHTML = `
            <div class="flex items-center justify-between text-xs">
              <div class="flex items-center space-x-1.5 font-bold text-white">
                <i data-lucide="file-text" class="w-3.5 h-3.5 text-brand-400"></i>
                <span class="truncate max-w-[180px]">${c.doc_name}</span>
              </div>
              <span class="font-mono text-[11px] px-2 py-0.5 rounded bg-brand-500/10 text-brand-300 font-semibold">Page ${c.page_number}</span>
            </div>
            <div class="text-[11px] text-slate-400 font-medium truncate">
              Section: <em>${c.heading}</em>
            </div>
            <p class="text-xs text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 italic font-mono leading-relaxed line-clamp-3">
              "${c.snippet}"
            </p>
            <div class="pt-1 flex items-center justify-between text-[11px]">
              <span class="text-slate-500 font-mono">Score: ${c.relevance_score}</span>
              <button onclick="openUserSourceModal('${c.doc_id}', ${c.page_number}, '${safeSnippet}', '${safeHeading}')" class="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded text-[11px] font-semibold transition flex items-center space-x-1">
                <i data-lucide="external-link" class="w-3 h-3"></i>
                <span>View Source</span>
              </button>
            </div>
          `;
          citationsList.appendChild(card);
        });
      }
    } else {
      // Disciplined refusal
      if (badge) {
        badge.className = "inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20";
        badge.innerHTML = `<i data-lucide="shield-alert" class="w-3.5 h-3.5"></i><span>Strict Policy: Insufficient Evidence in Uploaded Documents</span>`;
      }
      if (answerEl) {
        answerEl.innerHTML = `<div class="text-rose-300 font-medium">${data.answer}</div>`;
      }
      if (citationsSec) citationsSec.classList.add('hidden');
    }

    if (resultBox) resultBox.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();

  } catch (err) {
    alert('Query failed: ' + err.message);
  } finally {
    if (loading) loading.classList.add('hidden');
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function openUserSourceModal(docId, pageNum, snippet, heading) {
  const sess = getUserSessionId();
  try {
    const res = await fetch(`/api/user-docs/${encodeURIComponent(docId)}/page/${pageNum}?session_id=${encodeURIComponent(sess)}`);
    if (!res.ok) throw new Error('Could not retrieve page text.');
    const data = await res.json();

    document.getElementById('src-modal-docname').innerText = data.doc_name;
    document.getElementById('src-modal-pagenum').innerText = pageNum;
    document.getElementById('src-modal-heading').innerText = heading || ('Section on Page ' + pageNum);
    document.getElementById('src-modal-snippet').innerText = snippet || 'Direct evidence cited from page.';

    const pageTextEl = document.getElementById('src-modal-pagetext');
    if (pageTextEl) {
      const fullText = data.text || '';
      if (snippet && snippet.length > 15) {
        const cleanSnippetWords = snippet.split(/\s+/).slice(0, 5).join(' ');
        const regex = new RegExp(`(${cleanSnippetWords.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^.\n]*)`, 'gi');
        pageTextEl.innerHTML = fullText.replace(regex, '<mark class="bg-amber-400/30 text-amber-200 border-l-2 border-amber-400 px-1 font-bold">$1</mark>');
      } else {
        pageTextEl.innerText = fullText;
      }
    }

    document.getElementById('user-source-modal').classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    alert('Could not open page source: ' + err.message);
  }
}

function closeUserSourceModal() {
  document.getElementById('user-source-modal').classList.add('hidden');
}

// =====================================================================
// FLOATING GEMMA 4 AI CHATBOT CONTROLLER
// =====================================================================

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

let chatbotHistory = [];
let isChatbotOpen = false;

function toggleChatbotWidget() {
  const widget = document.getElementById('locallens-chat-widget');
  if (!widget) return;

  isChatbotOpen = !isChatbotOpen;
  if (isChatbotOpen) {
    widget.classList.remove('chat-hidden');
    widget.classList.add('chat-visible');
    setTimeout(() => {
      const input = document.getElementById('chatbot-input');
      if (input) input.focus();
    }, 150);
  } else {
    widget.classList.remove('chat-visible');
    widget.classList.add('chat-hidden');
  }

  if (window.lucide) lucide.createIcons();
}

function sendQuickPrompt(promptText) {
  const input = document.getElementById('chatbot-input');
  if (input) {
    input.value = promptText;
    handleChatSubmit();
  }
}

async function handleChatSubmit(event) {
  if (event) event.preventDefault();

  const input = document.getElementById('chatbot-input');
  const sendBtn = document.getElementById('chatbot-send-btn');
  const messagesContainer = document.getElementById('chatbot-messages');
  const typingIndicator = document.getElementById('chatbot-typing');

  if (!input) return;
  const message = input.value.trim();
  if (!message) return;

  // Clear input field
  input.value = '';
  if (sendBtn) sendBtn.disabled = true;

  // Append user bubble to UI
  appendUserBubble(message);

  // Show typing indicator & scroll
  if (typingIndicator) typingIndicator.classList.remove('hidden');
  scrollChatToBottom();

  const userSession = (typeof getUserSessionId === 'function') ? getUserSessionId() : 'default-session';

  try {
    const response = await fetch('/api/chatbot/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        conversation_history: chatbotHistory,
        session_id: userSession
      })
    });

    if (!response.ok) {
      throw new Error(`Chat API error (${response.status})`);
    }

    const data = await response.json();

    // Store in history for multi-turn conversational context
    chatbotHistory.push({ role: 'user', content: message });
    chatbotHistory.push({ role: 'model', content: data.reply });

    // Append AI response bubble to UI
    appendAiBubble(data.reply, data.model_used, data.citations, data.latency_ms);

  } catch (err) {
    appendAiBubble(
      `Sorry, I encountered an issue: ${err.message}. Please check if the server is active.`,
      'System Error',
      [],
      0
    );
  } finally {
    if (typingIndicator) typingIndicator.classList.add('hidden');
    if (sendBtn) sendBtn.disabled = false;
    scrollChatToBottom();
    if (window.lucide) lucide.createIcons();
  }
}

function appendUserBubble(text) {
  const container = document.getElementById('chatbot-messages');
  if (!container) return;

  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = 'flex justify-end';
  bubbleDiv.innerHTML = `
    <div class="chat-bubble-user max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-tr-sm bg-gradient-to-r from-brand-600 to-indigo-600 text-white shadow-md text-xs leading-relaxed break-words">
      ${escapeHtml(text)}
    </div>
  `;
  container.appendChild(bubbleDiv);
  scrollChatToBottom();
}

function appendAiBubble(replyText, modelUsed, citations, latencyMs) {
  const container = document.getElementById('chatbot-messages');
  if (!container) return;

  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = 'flex items-start space-x-2 justify-start';

  // Format citations HTML if present
  let citationsHtml = '';
  if (citations && citations.length > 0) {
    citationsHtml = `
      <div class="mt-2.5 pt-2 border-t border-slate-700/50 space-y-1.5">
        <span class="text-[10px] uppercase font-bold tracking-wider text-slate-400 flex items-center space-x-1">
          <i data-lucide="bookmark" class="w-3 h-3 text-brand-400"></i>
          <span>Official Citations (${citations.length})</span>
        </span>
        <div class="flex flex-wrap gap-1">
          ${citations.slice(0, 3).map(c => `
            <span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] text-brand-300 font-mono" title="${escapeHtml(c.snippet || '')}">
              <i data-lucide="file-text" class="w-2.5 h-2.5"></i>
              <span>${escapeHtml(c.title || 'GR')} (P.${c.page || 1})</span>
            </span>
          `).join('')}
        </div>
      </div>
    `;
  }

  // Model & latency badge
  const metaHtml = `
    <div class="mt-2 flex items-center justify-between text-[10px] text-slate-400 font-mono">
      <span class="flex items-center space-x-1 text-emerald-400">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
        <span>${escapeHtml(modelUsed || 'Gemma 4')}</span>
      </span>
      <span>${latencyMs ? (latencyMs / 1000).toFixed(2) + 's' : ''}</span>
    </div>
  `;

  bubbleDiv.innerHTML = `
    <div class="w-6 h-6 rounded-lg bg-gradient-to-tr from-brand-600 to-indigo-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
      <i data-lucide="bot" class="w-3.5 h-3.5"></i>
    </div>
    <div class="chat-bubble-ai max-w-[85%] p-3.5 rounded-2xl rounded-tl-sm bg-slate-850 border border-slate-800 text-slate-100 shadow-md text-xs leading-relaxed break-words">
      <div class="prose prose-invert prose-xs max-w-none text-slate-200 space-y-1.5">
        ${formatChatMarkdown(replyText)}
      </div>
      ${citationsHtml}
      ${metaHtml}
    </div>
  `;

  container.appendChild(bubbleDiv);
  scrollChatToBottom();
}

function scrollChatToBottom() {
  const container = document.getElementById('chatbot-messages');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

function clearChatHistory() {
  chatbotHistory = [];
  const container = document.getElementById('chatbot-messages');
  if (!container) return;

  container.innerHTML = `
    <div class="space-y-3" id="chatbot-welcome-card">
      <div class="chat-bubble-ai p-3.5 rounded-xl bg-slate-850 border border-slate-800 text-slate-200 space-y-2">
        <div class="flex items-center space-x-1.5 text-brand-400 font-bold text-xs">
          <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
          <span>Conversation Reset</span>
        </div>
        <p class="text-[11px] text-slate-300 leading-relaxed">
          Chat history has been cleared. Ask any question regarding Maharashtra government schemes, resolutions, or citizen services!
        </p>
      </div>

      <div class="space-y-1.5">
        <span class="text-[10px] uppercase font-bold tracking-wider text-slate-500">Try common queries:</span>
        <div class="flex flex-wrap gap-1.5">
          <button onclick="sendQuickPrompt('What is the annual income cap for EBC scholarship in Maharashtra?')" class="pill-btn pill-default text-[11px] py-1">🎓 EBC Scholarship Cap</button>
          <button onclick="sendQuickPrompt('What is the eligibility and age limit for Majhi Ladki Bahin Yojna?')" class="pill-btn pill-default text-[11px] py-1">👩 Majhi Ladki Bahin Age</button>
          <button onclick="sendQuickPrompt('Are White Ration Card holders eligible for MJPJAY 2.0 free healthcare?')" class="pill-btn pill-default text-[11px] py-1">🏥 MJPJAY Healthcare</button>
          <button onclick="sendQuickPrompt('What is the electricity subsidy for 7.5 HP pumps under Baliraja Yojna?')" class="pill-btn pill-default text-[11px] py-1">⚡ Baliraja Free Electricity</button>
          <button onclick="sendQuickPrompt('स्वाधार योजनेसाठी महाविद्यालयापासून किमान किती अंतर आवश्यक आहे?')" class="pill-btn pill-marathi text-[11px] py-1">🇮🇳 स्वाधार योजना अंतर</button>
          <button onclick="sendQuickPrompt('What is the statutory deadline for Caste Certificate under RTS Act?')" class="pill-btn pill-default text-[11px] py-1">📜 RTS 21-Day Deadline</button>
        </div>
      </div>
    </div>
  `;

  fetch('/api/chatbot/clear', { method: 'POST' }).catch(() => {});
  if (window.lucide) lucide.createIcons();
}

function formatChatMarkdown(text) {
  if (!text) return '';
  let formatted = escapeHtml(text);

  // Bold **text**
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>');
  
  // Italic *text*
  formatted = formatted.replace(/\*(.*?)\*/g, '<em class="text-slate-300">$1</em>');

  // Bullet points * or -
  formatted = formatted.replace(/^\s*[\*\-]\s+(.*)$/gm, '<li class="ml-3 list-disc text-slate-200">$1</li>');

  // Paragraph breaks
  formatted = formatted.replace(/\n\n+/g, '</p><p class="mt-2 text-slate-200 leading-relaxed">');
  formatted = formatted.replace(/\n/g, '<br/>');

  return `<p class="leading-relaxed text-slate-200">${formatted}</p>`;
}


