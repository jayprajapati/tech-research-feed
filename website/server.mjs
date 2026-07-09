import { createServer } from 'node:http';
const port = process.env.PORT || 8080;
let blob;

createServer((req, res) => {
  (async () => {
    try {
      const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
      if (url.pathname === '/health') { res.writeHead(200); res.end('ok'); return; }
      if (!blob) blob = await import('./blob.mjs');
      if (url.pathname === '/') return await serveHome(req, res);
      if (url.pathname === '/archive') return await serveArchive(req, res);
      const m = url.pathname.match(/^\/(\d{4}-\d{2}-\d{2})\/(.+)$/);
      if (m) return await serveReport(req, res, m[1], m[2]);
      res.writeHead(404, { 'content-type': 'text/html' }); res.end('<h1>404</h1>');
    } catch (e) {
      res.writeHead(500, { 'content-type': 'text/html' }); res.end(`<h1>Error</h1><pre>${e.message}</pre>`);
    }
  })().catch(e => { console.error(e); res.writeHead(500); res.end('error'); });
}).listen(port, () => console.log(`listening on ${port}`));

async function serveHome(req, res) {
  const reports = await blob.getReportManifest();
  res.writeHead(200, { 'content-type': 'text/html' });
  res.end(layout(`<div class="max-w-4xl mx-auto px-4 py-8"><h1 class="text-3xl font-bold mb-8">Research Feed</h1>${reports.map(r => `<article class="mb-6 p-6 bg-white rounded-lg shadow"><time class="text-sm text-gray-500">${esc(r.date)}</time><h2 class="text-xl font-semibold mt-1"><a href="/${r.date}/${r.slug}" class="text-blue-600 hover:underline">${esc(r.title)}</a></h2><p class="mt-2 text-gray-600">${esc(r.summary)}</p><div class="mt-2 flex gap-2">${r.tags.map(t => `<span class="text-xs bg-gray-100 px-2 py-1 rounded">${esc(t)}</span>`).join('')}</div></article>`).join('')}</div>`));
}

async function serveArchive(req, res) {
  const reports = await blob.getReportManifest();
  const byDate = {};
  for (const r of reports) (byDate[r.date.slice(0, 7)] ||= []).push(r);
  res.writeHead(200, { 'content-type': 'text/html' });
  res.end(layout(`<div class="max-w-4xl mx-auto px-4 py-8"><h1 class="text-3xl font-bold mb-8">Archive</h1>${Object.entries(byDate).sort(([a],[b])=>b.localeCompare(a)).map(([m,rs]) => `<section class="mb-8"><h2 class="text-xl font-semibold mb-4 text-gray-700">${esc(m)}</h2>${rs.map(r => `<div class="mb-2"><a href="/${r.date}/${r.slug}" class="text-blue-600 hover:underline">${esc(r.title)}</a> <span class="text-sm text-gray-400">${esc(r.type)}</span></div>`).join('')}</section>`).join('')}</div>`));
}

async function serveReport(req, res, date, slug) {
  const report = await blob.getReport(date, slug);
  if (!report) { res.writeHead(404); res.end('not found'); return; }
  res.writeHead(200, { 'content-type': 'text/html' });
  res.end(layout(`<div class="max-w-4xl mx-auto px-4 py-8"><time class="text-sm text-gray-500">${esc(report.date)}</time><h1 class="text-3xl font-bold mt-1">${esc(report.title)}</h1><p class="mt-2 text-gray-600">${esc(report.summary)}</p><div class="mt-2 flex gap-2">${report.tags.map(t => `<span class="text-xs bg-gray-100 px-2 py-1 rounded">${esc(t)}</span>`).join('')}</div><div class="mt-8 prose max-w-none">${report.sections.map(s => renderSection(s)).join('')}</div><footer class="mt-12 text-xs text-gray-400">Generated: ${esc(report.generatedAt)} | Model: ${esc(report.model)}</footer></div>`));
}

function renderSection(s) {
  if (s.type === 'text') return `<section class="mb-8"><h2 class="text-2xl font-semibold mb-4">${esc(s.heading)}</h2><div class="whitespace-pre-wrap">${esc(s.content)}</div></section>`;
  if (s.type === 'table') {
    const t = s.content;
    return `<section class="mb-8"><h2 class="text-2xl font-semibold mb-4">${esc(s.heading)}</h2><div class="overflow-x-auto"><table class="w-full border-collapse"><thead><tr>${t.headers.map(h => `<th class="border p-2 bg-gray-50 text-left font-semibold text-sm">${esc(h)}</th>`).join('')}</tr></thead><tbody>${t.rows.map(row => `<tr>${row.map(c => `<td class="border p-2 text-sm">${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>${t.caption ? `<p class="text-sm text-gray-500 mt-1">${esc(t.caption)}</p>` : ''}</div></section>`;
  }
  if (s.type === 'cards' || s.type === 'ranking') {
    const cards = s.content;
    return `<section class="mb-8"><h2 class="text-2xl font-semibold mb-4">${esc(s.heading)}</h2><div class="grid gap-4 md:grid-cols-2">${cards.map(c => `<div class="border rounded-lg p-4 ${c.tier === 'top' ? 'border-yellow-300 bg-yellow-50' : ''}"><h3 class="font-semibold">${esc(c.name)}${c.tier ? `<span class="ml-2 text-xs uppercase text-gray-400">${esc(c.tier)}</span>` : ''}</h3><p class="mt-1 text-sm text-gray-600">${esc(c.reasoning)}</p>${c.metrics ? `<dl class="mt-2 grid grid-cols-2 gap-1 text-xs">${Object.entries(c.metrics).map(([k,v]) => `<dt class="text-gray-400">${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` : ''}</div>`).join('')}</div></section>`;
  }
  return '';
}

function layout(c) { return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Feed</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-gray-50 text-gray-900 antialiased">${c}</body></html>`; }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
