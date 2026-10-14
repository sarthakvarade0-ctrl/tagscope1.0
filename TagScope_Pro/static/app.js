const form = document.getElementById('search-form');
const queryInput = document.getElementById('query');
const searchButton = document.getElementById('search-button');
const statusPanel = document.getElementById('status-panel');
const resultsSection = document.getElementById('results-section');
const articlesContainer = document.getElementById('articles');
const filterIds = ['category-filter', 'date-filter', 'publisher-filter', 'source-filter', 'sort-filter'];
let currentRequest = 0;
let currentData = null;
let activeQuery = '';

function showStatus(title, message, isError = false) {
  statusPanel.classList.remove('hidden');
  statusPanel.classList.toggle('error', isError);
  statusPanel.innerHTML = '';
  const icon = document.createElement('div'); icon.className = 'empty-symbol'; icon.textContent = isError ? '!' : '⌕';
  const heading = document.createElement('h2'); heading.textContent = title;
  const paragraph = document.createElement('p'); paragraph.textContent = message;
  statusPanel.append(icon, heading, paragraph);
}
function textElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text || '';
  return element;
}
function safeDate(article) {
  if (article.publishedAt) {
    const d = new Date(article.publishedAt);
    if (!Number.isNaN(d.getTime())) return d;
  }
  if (article.published) {
    const d = new Date(article.published);
    if (!Number.isNaN(d.getTime())) return d;
  }
  return null;
}
function formatDate(article) {
  const date = safeDate(article);
  if (!date) return 'Date unavailable';
  return new Intl.DateTimeFormat(undefined, {month:'short', day:'numeric', year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined}).format(date);
}
function normalizeWords(text) {
  const stop = new Set('the and for with from that this have has was were are but not you your into over after before says said latest news report reports about amid more than how why what when where who will can could should would may might its their they them then than today update updates'.split(' '));
  return (text.toLowerCase().match(/[a-z][a-z0-9'-]{2,}/g) || []).filter(w => !stop.has(w));
}
function relevanceScore(article) {
  const queryWords = normalizeWords(activeQuery);
  const title = normalizeWords(article.title).join(' ');
  const body = normalizeWords((article.title || '') + ' ' + (article.description || '')).join(' ');
  return queryWords.reduce((score, word) => score + (title.split(' ').includes(word) ? 4 : 0) + (body.split(' ').includes(word) ? 1 : 0), 0);
}
function getFilteredArticles() {
  if (!currentData) return [];
  const category = document.getElementById('category-filter').value;
  const dateRange = document.getElementById('date-filter').value;
  const publisher = document.getElementById('publisher-filter').value;
  const source = document.getElementById('source-filter').value;
  const sort = document.getElementById('sort-filter').value;
  const now = Date.now();
  const cutoff = dateRange === 'day' ? now - 86400000 : dateRange === 'week' ? now - 7 * 86400000 : dateRange === 'month' ? now - 30 * 86400000 : null;
  let articles = currentData.articles.filter(article => {
    if (category !== 'all' && article.category !== category) return false;
    if (publisher !== 'all' && article.publisher !== publisher) return false;
    if (source !== 'all' && !(article.providers || []).includes(source)) return false;
    if (cutoff) { const date = safeDate(article); if (!date || date.getTime() < cutoff) return false; }
    return true;
  });
  if (sort === 'newest') articles.sort((a,b) => (safeDate(b)?.getTime() || 0) - (safeDate(a)?.getTime() || 0));
  else if (sort === 'oldest') articles.sort((a,b) => (safeDate(a)?.getTime() || Infinity) - (safeDate(b)?.getTime() || Infinity));
  else articles.sort((a,b) => relevanceScore(b) - relevanceScore(a));
  return articles;
}
function populatePublishers(articles) {
  const select = document.getElementById('publisher-filter');
  const previous = select.value;
  select.innerHTML = '<option value="all">All publishers</option>';
  [...new Set(articles.map(a => a.publisher).filter(Boolean))].sort((a,b) => a.localeCompare(b)).forEach(publisher => {
    const option = document.createElement('option'); option.value = publisher; option.textContent = publisher; select.append(option);
  });
  select.value = [...select.options].some(o => o.value === previous) ? previous : 'all';
}
function renderArticles(items) {
  articlesContainer.innerHTML = '';
  for (const article of items) {
    const card = document.createElement('article'); card.className = 'article-card';
    const meta = document.createElement('div'); meta.className = 'article-meta';
    const publisher = textElement('span', 'publisher', article.publisher || 'News publisher');
    const date = textElement('span', 'article-date', formatDate(article)); meta.append(publisher, date);
    const tags = document.createElement('div'); tags.className = 'article-tags';
    tags.append(textElement('span', 'category-tag', article.category || 'Other disasters'));
    (article.providers || []).forEach(provider => tags.append(textElement('span', 'feed-tag', provider)));
    const heading = document.createElement('h4'); const titleLink = document.createElement('a');
    titleLink.href = article.url; titleLink.target = '_blank'; titleLink.rel = 'noopener noreferrer'; titleLink.textContent = article.title; heading.append(titleLink);
    const description = textElement('p', 'article-description', article.description || 'Open the original article to read the full report.');
    const readLink = document.createElement('a'); readLink.className = 'read-link'; readLink.href = article.url; readLink.target = '_blank'; readLink.rel = 'noopener noreferrer'; readLink.textContent = 'Read full story ↗';
    card.append(meta, tags, heading, description, readLink); articlesContainer.append(card);
  }
}
function renderKeyPoints(points) {
  const list = document.getElementById('key-points'); list.innerHTML = '';
  (points || []).slice(0,4).forEach(point => list.append(textElement('li', '', point)));
  if (!list.children.length) list.append(textElement('li', '', 'Open the linked incident reports to review the available details.'));
}
function renderTimeline(articles) {
  const container = document.getElementById('timeline-chart'); container.innerHTML = '';
  const counts = new Map();
  articles.forEach(article => { const date = safeDate(article); if (date) { const key = date.toLocaleDateString(undefined,{month:'short',day:'numeric'}); counts.set(key,(counts.get(key)||0)+1); } });
  const entries = [...counts.entries()].slice(0,7).reverse();
  if (!entries.length) { container.append(textElement('p','chart-empty','Publication dates are not available for these results.')); return; }
  const max = Math.max(...entries.map(e=>e[1]),1);
  entries.forEach(([date,count]) => {
    const row = document.createElement('div'); row.className = 'timeline-row';
    row.append(textElement('span','timeline-date',date));
    const track = document.createElement('div'); track.className = 'timeline-track'; const bar = document.createElement('div'); bar.className = 'timeline-bar'; bar.style.width = `${Math.max(8,count/max*100)}%`; track.append(bar);
    row.append(track,textElement('span','timeline-count',String(count))); container.append(row);
  });
}
function renderKeywords(articles) {
  const cloud = document.getElementById('keyword-cloud'); cloud.innerHTML = '';
  const counts = new Map();
  articles.forEach(article => {
    const unique = new Set(normalizeWords(`${article.title} ${article.description || ''}`));
    unique.forEach(word => counts.set(word,(counts.get(word)||0)+1));
  });
  const words = [...counts.entries()].filter(([word,count])=>count>1 && word.length>3).sort((a,b)=>b[1]-a[1]).slice(0,12);
  if (!words.length) { cloud.append(textElement('p','chart-empty','More articles are needed to surface recurring terms.')); return; }
  const max = words[0][1];
  words.forEach(([word,count],index) => {
    const chip = document.createElement('span'); chip.className = `keyword-chip ${index<3?'keyword-strong':''}`; chip.textContent = word; chip.title = `Appears in ${count} articles`;
    const countSpan = textElement('small','',String(count)); chip.append(countSpan); chip.style.opacity = String(0.68 + 0.32*count/max); cloud.append(chip);
  });
}
function headlineTokens(article) { return new Set(normalizeWords(article.title).filter(w=>w.length>3)); }
function similarity(a,b) {
  const aa = headlineTokens(a), bb = headlineTokens(b);
  if (!aa.size || !bb.size) return 0;
  let overlap = 0; aa.forEach(word=>{if(bb.has(word)) overlap++;});
  return overlap / (aa.size + bb.size - overlap);
}
function renderComparisons(articles) {
  const container = document.getElementById('comparison-list'); container.innerHTML = '';
  const clusters = [];
  for (const article of articles) {
    let best = null, bestScore = 0;
    for (const cluster of clusters) {
      const score = Math.max(...cluster.items.map(item=>similarity(item,article)));
      if (score > bestScore) { bestScore = score; best = cluster; }
    }
    if (best && bestScore >= 0.28 && best.items.length < 4) best.items.push(article);
    else clusters.push({items:[article]});
  }
  const useful = clusters.filter(cluster => cluster.items.length >= 2 && new Set(cluster.items.map(a=>a.publisher)).size >= 2).slice(0,4);
  if (!useful.length) {
    const empty = document.createElement('div'); empty.className = 'comparison-empty';
    empty.append(textElement('strong','','No clear cross-publisher incident groups yet.'),textElement('span','','Try a broader hazard or location query, such as “India floods” or “cyclone landfall”.')); container.append(empty); return;
  }
  useful.forEach((cluster,index) => {
    const card = document.createElement('article'); card.className = 'comparison-card';
    const top = document.createElement('div'); top.className = 'comparison-card-head'; top.append(textElement('span','comparison-index',`0${index+1}`),textElement('span','comparison-count',`${cluster.items.length} related headlines`));
    const title = textElement('h4','',cluster.items[0].title); card.append(top,title);
    cluster.items.forEach(item => {
      const row = document.createElement('div'); row.className = 'comparison-source';
      const left = document.createElement('div'); left.className = 'comparison-source-copy'; left.append(textElement('span','comparison-publisher',item.publisher),textElement('p','',item.title));
      const link = document.createElement('a'); link.href = item.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = '↗'; link.setAttribute('aria-label','Open original article'); row.append(left,link); card.append(row);
    });
    container.append(card);
  });
}
function renderFilteredView() {
  const filtered = getFilteredArticles();
  document.getElementById('result-count').textContent = filtered.length;
  document.getElementById('filtered-count').textContent = filtered.length;
  document.getElementById('filter-summary-copy').textContent = `Showing ${filtered.length} of ${(currentData?.articles || []).length} retrieved articles.`;
  document.getElementById('stat-articles').textContent = filtered.length;
  document.getElementById('stat-publishers').textContent = new Set(filtered.map(a => a.publisher).filter(Boolean)).size;
  document.getElementById('stat-feeds').textContent = new Set(filtered.flatMap(a => a.providers || [])).size;
  const latest = filtered.map(safeDate).filter(Boolean).sort((a,b) => b - a)[0];
  document.getElementById('stat-latest').textContent = latest ? new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric'}).format(latest) : '—';
  renderArticles(filtered);
  renderTimeline(filtered);
  renderKeywords(filtered);
  renderComparisons(filtered);
  document.getElementById('no-filter-results').classList.toggle('hidden', filtered.length > 0);
  articlesContainer.classList.toggle('hidden', filtered.length === 0);
  document.getElementById('analytics-panel').classList.toggle('muted-panel', filtered.length === 0);
}
async function search(query) {
  const trimmed = query.trim();
  if (trimmed.length < 2) { showStatus('Enter a hazard or incident','Use at least two characters, such as flood, cyclone, earthquake, wildfire, or evacuation.'); return; }
  const requestId = ++currentRequest; activeQuery = trimmed;
  searchButton.disabled = true; searchButton.innerHTML = '<span>Exploring…</span><span aria-hidden="true">◌</span>';
  resultsSection.classList.add('hidden');
  showStatus('Gathering incident reports…','Checking available news feeds and preparing your disaster situation workspace.');
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(trimmed)}`);
    const data = await response.json();
    if (requestId !== currentRequest) return;
    if (!response.ok) throw new Error(data.error || 'Incident report search could not be completed.');
    currentData = data;
    statusPanel.classList.add('hidden'); resultsSection.classList.remove('hidden');
    activateFeature('explore');
    document.getElementById('results-title').textContent = `Incident reports: “${data.query}”`;
    document.getElementById('results-subtitle').textContent = `${data.articles.length} distinct disaster-related reports collected from available news feeds.`;
    document.getElementById('summary-text').textContent = data.summary;
    renderKeyPoints(data.keyPoints);
    document.getElementById('provider-label').textContent = (data.providers || []).join(' + ') || 'News coverage';
    document.getElementById('cache-note').textContent = `${data.cached ? 'Loaded from recent local cache. ' : ''}${data.notice || ''}${data.sourceErrors?.length ? ' Some sources could not be reached: ' + data.sourceErrors.join(', ') + '.' : ''}`;
    filterIds.forEach(id=>{const el=document.getElementById(id); if(id==='category-filter'||id==='date-filter'||id==='publisher-filter'||id==='source-filter')el.value='all'; if(id==='sort-filter')el.value='relevance';});
    populatePublishers(data.articles);
    renderFilteredView();
  } catch (error) {
    if (requestId !== currentRequest) return;
    showStatus('Incident reports are temporarily unavailable',error.message + ' Check your connection, wait a moment, and try again.',true);
  } finally {
    if (requestId === currentRequest) { searchButton.disabled = false; searchButton.innerHTML = '<span>Track incident</span><span aria-hidden="true">→</span>'; }
  }
}
form.addEventListener('submit', event=>{event.preventDefault();search(queryInput.value);});
document.querySelectorAll('[data-query]').forEach(button=>button.addEventListener('click',()=>{queryInput.value=button.dataset.query;search(button.dataset.query);}));
filterIds.forEach(id=>document.getElementById(id).addEventListener('change',renderFilteredView));
document.getElementById('reset-filters').addEventListener('click',()=>{document.getElementById('category-filter').value='all';document.getElementById('date-filter').value='all';document.getElementById('publisher-filter').value='all';document.getElementById('source-filter').value='all';document.getElementById('sort-filter').value='relevance';renderFilteredView();});


// Each requested feature has its own workspace tab.
function activateFeature(name) {
  document.querySelectorAll('[data-feature-panel]').forEach(panel => {
    panel.classList.toggle('hidden', panel.dataset.featurePanel !== name);
  });
  document.querySelectorAll('[data-feature-tab]').forEach(tab => {
    const active = tab.dataset.featureTab === name;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  const results = document.getElementById('results-section');
  if (results) results.dataset.activeFeature = name;
}
document.querySelectorAll('[data-feature-tab]').forEach(tab => {
  tab.addEventListener('click', () => activateFeature(tab.dataset.featureTab));
});
document.querySelectorAll('[data-open-feature]').forEach(button => {
  button.addEventListener('click', () => activateFeature(button.dataset.openFeature));
});
