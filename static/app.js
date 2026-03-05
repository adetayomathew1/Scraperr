/**
 * static/app.js
 * ─────────────────────────────────────────────────────────────
 * SCRAPERRR — War Intelligence Dashboard
 * Handles: API fetch, localStorage persistence, filters,
 *          bookmarks, ticker, 24h auto-refresh, search.
 */

'use strict';

/* ── Constants ────────────────────────────────────────────── */
const API_ARTICLES = '/api/articles';
const API_REFRESH = '/api/refresh';
const LS_SAVED_KEY = 'scraperrr_saved';
const LS_DATA_KEY = 'scraperrr_articles_cache';
const REFRESH_MS = 24 * 60 * 60 * 1000; // 24 hours

/* ── State ────────────────────────────────────────────────── */
let allArticles = [];
let activeSource = 'All';
let activeTab = 'all';
let searchQuery = '';

/* ── localStorage helpers ─────────────────────────────────── */
function getSaved() {
    try { return JSON.parse(localStorage.getItem(LS_SAVED_KEY)) || { saved_ids: [], saved_at: {} }; }
    catch { return { saved_ids: [], saved_at: {} }; }
}

function setSaved(data) {
    localStorage.setItem(LS_SAVED_KEY, JSON.stringify(data));
}

function isArticleSaved(id) {
    return getSaved().saved_ids.includes(id);
}

function toggleSave(id) {
    const s = getSaved();
    if (s.saved_ids.includes(id)) {
        s.saved_ids = s.saved_ids.filter(x => x !== id);
        delete s.saved_at[id];
        showToast('Article removed from saved', 'info');
    } else {
        s.saved_ids.push(id);
        s.saved_at[id] = new Date().toISOString();
        showToast('🔖 Article saved!', 'success');
    }
    setSaved(s);
    rerenderSaveButtons(id);
    updateSavedBadge();
    if (activeTab === 'saved') applyFilters();
}

/* ── Saved badge ──────────────────────────────────────────── */
function updateSavedBadge() {
    const count = getSaved().saved_ids.length;
    document.getElementById('savedBadge').textContent = count;
    document.getElementById('statSaved').textContent = count;
}

/* Rerender only save buttons for a given article id */
function rerenderSaveButtons(id) {
    document.querySelectorAll(`[data-save-id="${id}"]`).forEach(btn => {
        const saved = isArticleSaved(id);
        btn.textContent = saved ? '🔖' : '🤍';
        btn.classList.toggle('saved', saved);
        btn.title = saved ? 'Unsave article' : 'Save article';
    });
    // Mark card border
    document.querySelectorAll(`[data-card-id="${id}"]`).forEach(card => {
        card.classList.toggle('saved', isArticleSaved(id));
    });
}

/* ── Date helpers ─────────────────────────────────────────── */
function formatDate(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
            ' · ' +
            d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
}

function timeAgo(iso) {
    if (!iso) return '';
    try {
        const secs = (Date.now() - new Date(iso).getTime()) / 1000;
        if (secs < 60) return `${Math.floor(secs)}s ago`;
        if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
        if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
        return `${Math.floor(secs / 86400)}d ago`;
    } catch { return ''; }
}

/* ── Ticker ──────────────────────────────────────────────── */
function buildTicker(articles) {
    const track = document.getElementById('tickerTrack');
    if (!articles || articles.length === 0) return;

    const top20 = articles.slice(0, 20);
    const items = top20.map(a =>
        `<span class="ticker-item"><b>${a.source}</b> — ${a.title}</span>`
    );
    // Duplicate for seamless loop
    const all = [...items, ...items].join('');
    track.innerHTML = `<div class="ticker-inner">${all}</div>`;
}

/* ── Source filter pills ─────────────────────────────────── */
function buildSourceFilters(articles) {
    const sources = ['All', ...new Set(articles.map(a => a.source))];
    const wrap = document.getElementById('sourceFilters');
    wrap.innerHTML = sources.map(s => `
    <button
      class="filter-pill ${s === 'All' ? 'active' : ''}"
      data-source="${s}"
      onclick="filterBySource('${s}')"
    >${s}</button>
  `).join('');
}

function filterBySource(source) {
    activeSource = source;
    document.querySelectorAll('.filter-pill').forEach(p => {
        p.classList.toggle('active', p.dataset.source === source);
    });
    applyFilters();
}

/* ── Filtering logic ─────────────────────────────────────── */
function getVisibleArticles() {
    let list = [...allArticles];

    // Tab filter
    if (activeTab === 'saved') {
        const saved_ids = getSaved().saved_ids;
        list = list.filter(a => saved_ids.includes(a.id));
    }

    // Source filter
    if (activeSource !== 'All') {
        list = list.filter(a => a.source === activeSource);
    }

    // Search filter
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        list = list.filter(a =>
            (a.title || '').toLowerCase().includes(q) ||
            (a.summary || '').toLowerCase().includes(q) ||
            (a.source || '').toLowerCase().includes(q) ||
            (a.tags || []).some(t => t.includes(q))
        );
    }

    return list;
}

function applyFilters() {
    renderGrid(getVisibleArticles());
}

/* ── Tab switching ───────────────────────────────────────── */
function switchTab(tab) {
    activeTab = tab;

    // Update tab UI
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    if (tab === 'all') document.getElementById('tabAll').classList.add('active');
    else if (tab === 'saved') document.getElementById('tabSaved').classList.add('active');

    applyFilters();
}

/* ── Search ──────────────────────────────────────────────── */
function applyFiltersFromSearch() { applyFilters(); }

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('searchInput');
    const clear = document.getElementById('searchClear');
    input.addEventListener('input', () => {
        searchQuery = input.value.trim();
        clear.classList.toggle('visible', searchQuery.length > 0);
        applyFilters();
    });
});

function clearSearch() {
    const input = document.getElementById('searchInput');
    const clear = document.getElementById('searchClear');
    input.value = '';
    searchQuery = '';
    clear.classList.remove('visible');
    applyFilters();
}

/* ── Card rendering ──────────────────────────────────────── */
function badgeClass(source) {
    return 'badge-' + (source || '').replace(/\s+/g, '-');
}

function renderCard(article) {
    const saved = isArticleSaved(article.id);
    /**
     * Image strategy:
     *  1. Use article's own image if it has one.
     *  2. On load error → fall back to CSS source banner (no external image).
     *  3. No image_url → show CSS source banner immediately.
     *  CSS banners are 100% reliable — no external URLs, no hotlink blocks.
     */
    const sourceSlug = (article.source || '').replace(/\s+/g, '-').toLowerCase();
    const sourceBanner = `<div class="card-source-banner source-${sourceSlug}"><span class="source-banner-name">${escHtml(article.source)}</span></div>`;

    let imgHtml = '';
    if (article.image_url) {
        imgHtml = `<img class="card-img" src="${article.image_url}" alt="${escHtml(article.title)}" loading="lazy" onerror="if(this.dataset.done)return;this.dataset.done='1';this.outerHTML='${sourceBanner.replace(/'/g, "\\'")}'">`;
    } else {
        imgHtml = sourceBanner;
    }


    const tagsHtml = (article.tags || []).map(t =>
        `<span class="tag tag-${t}">${t}</span>`
    ).join('');

    const card = document.createElement('article');
    card.className = `card ${saved ? 'saved' : ''}`;
    card.dataset.cardId = article.id;
    card.setAttribute('role', 'article');

    card.innerHTML = `
    <div class="card-img-wrap">
      ${imgHtml}
      <span class="card-source-badge ${badgeClass(article.source)}">${article.source}</span>
      <button
        class="card-save-btn ${saved ? 'saved' : ''}"
        data-save-id="${article.id}"
        title="${saved ? 'Unsave article' : 'Save article'}"
        onclick="event.stopPropagation(); toggleSave('${article.id}')"
        aria-label="${saved ? 'Unsave' : 'Save'} article"
      >${saved ? '🔖' : '🤍'}</button>
    </div>
    <div class="card-body">
      <div class="card-meta">
        <time class="card-date" datetime="${article.published}">${timeAgo(article.published)}</time>
      </div>
      <h2 class="card-title">${escHtml(article.title)}</h2>
      <p class="card-summary">${escHtml(article.summary)}</p>
      <div class="card-tags">${tagsHtml}</div>
    </div>
    <div class="card-footer">
      <a class="card-read-link" href="${article.url}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">
        Read full story →
      </a>
    </div>
  `;

    // Clicking card opens article (unless clicking save btn or link)
    card.addEventListener('click', (e) => {
        if (!e.target.closest('.card-save-btn') && !e.target.closest('.card-read-link')) {
            window.open(article.url, '_blank', 'noopener,noreferrer');
        }
    });

    return card;
}

function escHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderGrid(articles) {
    const grid = document.getElementById('articleGrid');
    const empty = document.getElementById('emptyState');

    grid.innerHTML = '';

    if (!articles || articles.length === 0) {
        grid.style.display = 'none';
        empty.style.display = 'flex';
        return;
    }

    empty.style.display = 'none';
    grid.style.display = 'grid';

    articles.forEach((a, i) => {
        const card = renderCard(a);
        card.style.animationDelay = `${Math.min(i * 40, 400)}ms`;
        grid.appendChild(card);
    });
}

/* ── Stats update ────────────────────────────────────────── */
function updateStats(payload) {
    document.getElementById('statTotal').textContent = payload.total_count || allArticles.length;
    document.getElementById('statSources').textContent = (payload.sources_hit || []).length || '—';
    updateSavedBadge();

    const lastFetched = payload.last_fetched;
    document.getElementById('lastUpdated').textContent = lastFetched
        ? `Updated ${timeAgo(lastFetched)}`
        : 'Never fetched';

    // Casualties
    const casWrap = document.getElementById('casualtyWrap');
    if (payload.casualties && Object.keys(payload.casualties).length > 0) {
        casWrap.style.display = 'flex';
        const list = document.getElementById('casList');
        const flags = {
            'USA': 'us', 'US': 'us', 'United States': 'us',
            'Iran': 'ir', 'Israel': 'il',
            'UAE': 'ae', 'Qatar': 'qa', 'Kuwait': 'kw',
            'Iraq': 'iq', 'Bahrain': 'bh', 'Oman': 'om',
            'Syria': 'sy', 'Yemen': 'ye', 'Lebanon': 'lb',
            'Gaza': 'ps', 'Palestine': 'ps', 'Jordan': 'jo',
            'Egypt': 'eg', 'Saudi Arabia': 'sa', 'UK': 'gb', 'France': 'fr'
        };

        list.innerHTML = Object.entries(payload.casualties).map(([region, count]) => {
            const code = flags[region];
            const flagHtml = code ? `<img src="https://flagcdn.com/w20/${code}.png" alt="${region} flag" class="cas-flag-img">` : '<span class="cas-flag">🌍</span>';
            return `<div class="cas-item" title="${region}">${region} ${flagHtml} <strong>${count.dead}</strong></div>`;
        }).join('');
    } else {
        casWrap.style.display = 'none';
    }
}

/* ── Main data load ──────────────────────────────────────── */
async function loadArticles() {
    showSkeleton(true);

    try {
        const res = await fetch(API_ARTICLES);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        allArticles = data.articles || [];

        buildTicker(allArticles);
        buildSourceFilters(allArticles);
        updateStats(data);
        applyFilters();
        showSkeleton(false);

        // Cache payload time for 24h check
        if (data.last_fetched) {
            localStorage.setItem(LS_DATA_KEY, data.last_fetched);
        }

    } catch (err) {
        console.error('Failed to load articles:', err);
        showSkeleton(false);
        showEmptyWithMessage('Could not connect to the server. Make sure tools/server.py is running.');
    }
}

function showSkeleton(show) {
    document.getElementById('skeletonGrid').style.display = show ? 'grid' : 'none';
    document.getElementById('articleGrid').style.display = show ? 'none' : 'grid';
    if (show) document.getElementById('emptyState').style.display = 'none';
}

function showEmptyWithMessage(msg) {
    const empty = document.getElementById('emptyState');
    empty.style.display = 'flex';
    const p = empty.querySelector('p');
    if (p) p.textContent = msg;
}

/* ── Force refresh ───────────────────────────────────────── */
async function forceRefresh() {
    const btn = document.getElementById('btnRefresh');
    btn.classList.add('loading');
    showToast('🔄 Scraping latest war news…', 'info');

    try {
        const res = await fetch(API_REFRESH, { method: 'POST' });
        const data = await res.json();

        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Refresh failed');
        }

        showToast(`✅ Loaded ${data.total_count} articles from ${(data.sources_hit || []).join(', ')}`, 'success');
        await loadArticles();

    } catch (err) {
        console.error('Refresh error:', err);
        showToast(`❌ ${err.message}`, 'error');
    } finally {
        btn.classList.remove('loading');
    }
}

/* ── 24h auto-refresh check ──────────────────────────────── */
/**
 * Boot strategy:
 *  1. ALWAYS load from /api/articles first (shows cached data instantly).
 *  2. After load, check the server's last_fetched timestamp.
 *  3. If >24h old (or no data at all), trigger a background forceRefresh().
 *  This prevents the "skeleton stuck" bug on first browser visit.
 */
async function check24hRefresh() {
    // Step 1 — always show whatever the server has cached right now
    await loadArticles();

    // Step 2 — check if a background refresh is warranted
    const serverLastFetched = localStorage.getItem(LS_DATA_KEY);

    if (!serverLastFetched) {
        // Server has no data at all — trigger a scrape in background
        console.log('[SCRAPERRR] No server data — triggering background scrape…');
        silentRefresh();
        return;
    }

    const elapsed = Date.now() - new Date(serverLastFetched).getTime();
    if (elapsed > REFRESH_MS) {
        console.log('[SCRAPERRR] 24h elapsed — background refresh…');
        silentRefresh();
    } else {
        const hoursLeft = Math.round((REFRESH_MS - elapsed) / 3600000);
        console.log(`[SCRAPERRR] Cache fresh — next refresh in ~${hoursLeft}h`);
    }
}

/** Background refresh — runs scraper silently, then reloads grid */
async function silentRefresh() {
    try {
        const res = await fetch(API_REFRESH, { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
            console.log(`[SCRAPERRR] Background scrape done — ${data.total_count} articles`);
            await loadArticles(); // reload with fresh data
        }
    } catch (err) {
        console.warn('[SCRAPERRR] Background refresh failed:', err.message);
    }
}

/* ── Toast ───────────────────────────────────────────────── */
let toastTimer;
function showToast(msg, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.className = `toast show ${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.classList.remove('show');
    }, 3500);
}


/* ── Boot ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    updateSavedBadge();
    check24hRefresh();

    // ── Newsletter Modal ─────────────────────────────────────
    const nlOverlay = document.getElementById('nlOverlay');
    const nlDismiss = document.getElementById('nlDismiss');
    const nlBackdrop = document.getElementById('nlBackdrop');
    const nlForm = document.getElementById('newsletterForm');
    const nlEmail = document.getElementById('newsletterEmail');
    const nlBtn = document.getElementById('newsletterBtn');
    const nlError = document.getElementById('newsletterError');
    const nlSuccess = document.getElementById('newsletterSuccess');

    function dismissModal() {
        nlOverlay.classList.add('hidden');
        sessionStorage.setItem('nl_dismissed', '1');
    }

    // Show modal after 3 seconds if not already dismissed this session
    if (nlOverlay && !sessionStorage.getItem('nl_dismissed')) {
        nlOverlay.classList.add('hidden'); // start hidden
        setTimeout(() => nlOverlay.classList.remove('hidden'), 3000);
    } else if (nlOverlay) {
        nlOverlay.classList.add('hidden');
    }

    if (nlDismiss) nlDismiss.addEventListener('click', dismissModal);
    if (nlBackdrop) nlBackdrop.addEventListener('click', dismissModal);

    if (nlForm) {
        nlForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            nlError.style.display = 'none';

            const email = nlEmail.value.trim();
            if (!email) {
                nlError.textContent = 'Email is required';
                nlError.style.display = 'block';
                return;
            }
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                nlError.textContent = 'Please enter a valid email address';
                nlError.style.display = 'block';
                return;
            }

            nlBtn.disabled = true;
            nlBtn.querySelector('span').textContent = 'Subscribing…';

            // Simulate API call (replace with real endpoint later)
            await new Promise(r => setTimeout(r, 800));

            // Show success
            nlForm.style.display = 'none';
            nlSuccess.style.display = 'block';

            // Confetti blast 🎉
            if (typeof confetti === 'function') {
                confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
            }

            showToast('Successfully subscribed! 🎉', 'success');

            // Auto-close modal after 2.5 seconds
            setTimeout(dismissModal, 2500);
        });
    }
});
