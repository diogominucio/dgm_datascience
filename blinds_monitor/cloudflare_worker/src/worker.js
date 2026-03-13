/**
 * Blinds.com Price Monitor — Cloudflare Worker
 *
 * Runs daily via Cron Trigger to scrape blinds.com prices,
 * store historical data in KV, and send email reports.
 *
 * Setup:
 *   1. Create KV namespace: wrangler kv:namespace create PRICE_DATA
 *   2. Set secrets: wrangler secret put SMTP_USERNAME
 *                    wrangler secret put SMTP_PASSWORD
 *                    wrangler secret put RECIPIENT_EMAIL
 *   3. Deploy: wrangler deploy
 */

const CATEGORIES = {
  cellular_shades: {
    name: "Cellular Shades",
    url: "https://www.blinds.com/c/cellular-shades/t/all",
  },
  faux_wood_blinds: {
    name: "Faux Wood Blinds",
    url: "https://www.blinds.com/c/faux-wood-blinds/t/all",
  },
  wood_blinds: {
    name: "Wood Blinds",
    url: "https://www.blinds.com/c/wood-blinds/t/all",
  },
  roman_shades: {
    name: "Roman Shades",
    url: "https://www.blinds.com/c/roman-shades/t/all",
  },
  roller_shades: {
    name: "Roller Shades",
    url: "https://www.blinds.com/c/roller-shades/t/all",
  },
};

const PRICE_TIERS = [
  [70, "Tier 1: $0-$70"],
  [100, "Tier 2: $70-$100"],
  [150, "Tier 3: $100-$150"],
  [200, "Tier 4: $150-$200"],
  [300, "Tier 5: $200-$300"],
  [Infinity, "Tier 6: $300+"],
];

function classifyPriceTier(price) {
  if (price == null) return "Unknown";
  for (const [threshold, label] of PRICE_TIERS) {
    if (price <= threshold) return label;
  }
  return "Tier 6: $300+";
}

async function scrapeCategory(categoryKey, categoryInfo) {
  try {
    const response = await fetch(categoryInfo.url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      },
    });

    if (!response.ok) {
      console.error(`Failed to fetch ${categoryInfo.url}: ${response.status}`);
      return [];
    }

    const html = await response.text();
    const products = parseProducts(html, categoryKey, categoryInfo.name);
    return products;
  } catch (error) {
    console.error(`Error scraping ${categoryInfo.name}:`, error);
    return [];
  }
}

function parseProducts(html, categoryKey, categoryName) {
  const products = [];
  const today = new Date().toISOString().split("T")[0];

  // Extract JSON-LD structured data
  const jsonLdRegex = /<script type="application\/ld\+json">([\s\S]*?)<\/script>/g;
  let match;

  while ((match = jsonLdRegex.exec(html)) !== null) {
    try {
      const data = JSON.parse(match[1]);
      const items = Array.isArray(data) ? data : [data];

      for (const item of items) {
        if (item["@type"] === "Product" || item["@type"] === "IndividualProduct") {
          const offers = Array.isArray(item.offers) ? item.offers[0] : item.offers || {};
          const price = parseFloat(offers.price || offers.lowPrice) || null;
          const msrp = parseFloat(item.msrp) || null;

          products.push({
            name: item.name || "Unknown",
            url: item.url || "",
            price,
            msrp,
            price_tier: classifyPriceTier(price),
            msrp_tier: classifyPriceTier(msrp),
            discount_pct: price && msrp && msrp > 0 ? Math.round((1 - price / msrp) * 1000) / 10 : null,
            category: categoryName,
            category_key: categoryKey,
            brand: (item.brand || {}).name || "",
            scrape_date: today,
          });
        }
      }
    } catch (e) {
      // Skip invalid JSON
    }
  }

  // Extract from inline product data patterns
  const dataPatterns = [
    /"name"\s*:\s*"([^"]+)"[\s\S]*?"price"\s*:\s*"?([\d.]+)"?/g,
    /"productName"\s*:\s*"([^"]+)"[\s\S]*?"salePrice"\s*:\s*"?([\d.]+)"?/g,
  ];

  for (const pattern of dataPatterns) {
    let dataMatch;
    while ((dataMatch = pattern.exec(html)) !== null) {
      const name = dataMatch[1];
      const price = parseFloat(dataMatch[2]);

      // Avoid duplicates
      if (!products.some((p) => p.name === name)) {
        products.push({
          name,
          price: isNaN(price) ? null : price,
          msrp: null,
          price_tier: classifyPriceTier(isNaN(price) ? null : price),
          msrp_tier: "Unknown",
          discount_pct: null,
          category: categoryName,
          category_key: categoryKey,
          scrape_date: today,
        });
      }
    }
  }

  return products;
}

async function scrapeAllCategories() {
  const results = {};
  for (const [key, info] of Object.entries(CATEGORIES)) {
    results[key] = await scrapeCategory(key, info);
    // Small delay between requests
    await new Promise((r) => setTimeout(r, 1000));
  }
  return results;
}

async function storeSnapshot(env, results) {
  const today = new Date().toISOString().split("T")[0];

  // Store today's snapshot
  await env.PRICE_DATA.put(`snapshot:${today}`, JSON.stringify(results), {
    expirationTtl: 60 * 60 * 24 * 365, // Keep for 1 year
  });

  // Update the list of snapshot dates
  const datesStr = (await env.PRICE_DATA.get("snapshot_dates")) || "[]";
  const dates = JSON.parse(datesStr);
  if (!dates.includes(today)) {
    dates.push(today);
    // Keep last 365 days
    while (dates.length > 365) dates.shift();
    await env.PRICE_DATA.put("snapshot_dates", JSON.stringify(dates));
  }

  return today;
}

async function loadPreviousSnapshot(env) {
  const datesStr = (await env.PRICE_DATA.get("snapshot_dates")) || "[]";
  const dates = JSON.parse(datesStr);

  if (dates.length < 2) return null;

  // Get the second-to-last date (previous snapshot)
  const prevDate = dates[dates.length - 2];
  const snapshotStr = await env.PRICE_DATA.get(`snapshot:${prevDate}`);

  return snapshotStr ? { date: prevDate, data: JSON.parse(snapshotStr) } : null;
}

function detectPriceChanges(current, previous) {
  if (!previous) return [];

  const changes = [];
  for (const [catKey, products] of Object.entries(current)) {
    const prevProducts = previous.data[catKey] || [];
    const prevMap = new Map(prevProducts.map((p) => [p.name, p]));

    for (const product of products) {
      const prev = prevMap.get(product.name);
      if (prev && prev.price != null && product.price != null && prev.price !== product.price) {
        const changePct = Math.round(((product.price - prev.price) / prev.price) * 1000) / 10;
        changes.push({
          product: product.name,
          category: product.category,
          previous_price: prev.price,
          current_price: product.price,
          change_pct: changePct,
          direction: changePct > 0 ? "increase" : "decrease",
        });
      }
    }
  }

  changes.sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
  return changes;
}

function generateEmailHtml(results, priceChanges) {
  const today = new Date().toLocaleDateString("pt-BR");
  const totalProducts = Object.values(results).reduce((s, p) => s + p.length, 0);
  const increases = priceChanges.filter((c) => c.direction === "increase");
  const decreases = priceChanges.filter((c) => c.direction === "decrease");

  let categorySummary = "";
  for (const [key, products] of Object.entries(results)) {
    if (products.length === 0) continue;
    const prices = products.map((p) => p.price).filter((p) => p != null);
    const avg = prices.length ? (prices.reduce((a, b) => a + b, 0) / prices.length).toFixed(2) : "N/A";
    const min = prices.length ? Math.min(...prices).toFixed(2) : "N/A";
    const max = prices.length ? Math.max(...prices).toFixed(2) : "N/A";
    const discounts = products.map((p) => p.discount_pct).filter((d) => d != null);
    const avgDiscount = discounts.length
      ? (discounts.reduce((a, b) => a + b, 0) / discounts.length).toFixed(1)
      : "N/A";

    categorySummary += `<tr>
      <td><strong>${products[0]?.category || key}</strong></td>
      <td>${products.length}</td>
      <td>$${avg}</td><td>$${min}</td><td>$${max}</td>
      <td>${avgDiscount}%</td></tr>`;
  }

  let changesHtml = "";
  if (priceChanges.length > 0) {
    changesHtml = `<h2 style="color:#16213e;border-left:4px solid #e94560;padding-left:10px;">💰 Alterações de Preço</h2><table style="width:100%;border-collapse:collapse;font-size:13px;">
    <tr style="background:#16213e;color:white;"><th style="padding:10px;">Produto</th><th>Categoria</th><th>Anterior</th><th>Atual</th><th>Variação</th></tr>`;
    for (const c of priceChanges.slice(0, 20)) {
      const cls = c.direction === "increase" ? "color:#e94560;font-weight:bold;" : "color:#27ae60;font-weight:bold;";
      changesHtml += `<tr><td style="padding:8px;">${c.product}</td><td>${c.category}</td>
        <td>$${c.previous_price.toFixed(2)}</td><td>$${c.current_price.toFixed(2)}</td>
        <td style="${cls}">${c.change_pct > 0 ? "+" : ""}${c.change_pct}%</td></tr>`;
    }
    changesHtml += "</table>";
  }

  return `<!DOCTYPE html><html><head><meta charset="utf-8"></head>
  <body style="font-family:'Segoe UI',Arial,sans-serif;color:#333;max-width:900px;margin:0 auto;padding:20px;background:#f5f5f5;">
  <div style="background:#fff;border-radius:8px;padding:30px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
  <h1 style="color:#1a1a2e;border-bottom:3px solid #e94560;padding-bottom:10px;">🔍 Blinds.com — Relatório de Inteligência Competitiva</h1>
  <p style="color:#666;">Data: ${today} | Cloudflare Worker Monitor</p>
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:20px;border-radius:8px;margin:20px 0;">
    <h2 style="color:#fff;">📊 Resumo Executivo</h2>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-top:15px;">
      <div style="background:rgba(255,255,255,0.1);padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#e94560;">${totalProducts}</div>
        <div style="font-size:12px;color:#ccc;">PRODUTOS</div></div>
      <div style="background:rgba(255,255,255,0.1);padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#e94560;">${Object.keys(results).length}</div>
        <div style="font-size:12px;color:#ccc;">CATEGORIAS</div></div>
      <div style="background:rgba(255,255,255,0.1);padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#e94560;">${increases.length}</div>
        <div style="font-size:12px;color:#ccc;">AUMENTOS</div></div>
      <div style="background:rgba(255,255,255,0.1);padding:15px;border-radius:6px;text-align:center;">
        <div style="font-size:28px;font-weight:bold;color:#27ae60;">${decreases.length}</div>
        <div style="font-size:12px;color:#ccc;">REDUÇÕES</div></div>
    </div>
  </div>
  ${changesHtml}
  <h2 style="color:#16213e;border-left:4px solid #e94560;padding-left:10px;">📋 Visão por Categoria</h2>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <tr style="background:#16213e;color:white;"><th style="padding:10px;">Categoria</th><th>Produtos</th><th>Preço Médio</th><th>Menor</th><th>Maior</th><th>Desc. Médio</th></tr>
    ${categorySummary}
  </table>
  <div style="text-align:center;color:#999;font-size:11px;margin-top:30px;padding-top:20px;border-top:1px solid #eee;">
    <p>Relatório automático — Blinds.com Price Monitor | DGM Data Science</p>
  </div></div></body></html>`;
}

async function sendEmailViaWorker(env, html) {
  // Use MailChannels API (free for Cloudflare Workers) or configured SMTP
  // MailChannels integration (recommended for Workers):
  const recipient = env.RECIPIENT_EMAIL || "Diogominucio@gmail.com";

  try {
    const response = await fetch("https://api.mailchannels.net/tx/v1/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        personalizations: [{ to: [{ email: recipient }] }],
        from: {
          email: "monitor@blinds-price-monitor.workers.dev",
          name: "Blinds Price Monitor",
        },
        subject: `📊 Blinds.com Competitor Report - ${new Date().toLocaleDateString("pt-BR")}`,
        content: [{ type: "text/html", value: html }],
      }),
    });

    if (response.ok) {
      console.log("Email sent successfully via MailChannels");
    } else {
      console.error("Email send failed:", await response.text());
    }
  } catch (error) {
    console.error("Email error:", error);
  }
}

export default {
  // Cron trigger handler — runs daily
  async scheduled(event, env, ctx) {
    console.log("Cron trigger fired:", new Date().toISOString());

    // Scrape all categories
    const results = await scrapeAllCategories();
    const totalProducts = Object.values(results).reduce((s, p) => s + p.length, 0);
    console.log(`Scraped ${totalProducts} products`);

    // Load previous snapshot for comparison
    const previous = await loadPreviousSnapshot(env);

    // Detect price changes
    const priceChanges = detectPriceChanges(results, previous);
    console.log(`Detected ${priceChanges.length} price changes`);

    // Store today's snapshot
    await storeSnapshot(env, results);

    // Generate and send email
    const emailHtml = generateEmailHtml(results, priceChanges);
    await sendEmailViaWorker(env, emailHtml);

    console.log("Pipeline complete");
  },

  // HTTP handler — for manual triggers and health checks
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/run") {
      // Manually trigger the pipeline
      ctx.waitUntil(this.scheduled({}, env, ctx));
      return new Response("Pipeline triggered. Check logs for progress.", {
        status: 200,
      });
    }

    if (url.pathname === "/status") {
      const datesStr = (await env.PRICE_DATA.get("snapshot_dates")) || "[]";
      const dates = JSON.parse(datesStr);
      return new Response(
        JSON.stringify({
          status: "ok",
          total_snapshots: dates.length,
          last_snapshot: dates[dates.length - 1] || "none",
        }),
        { headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response(
      "Blinds.com Price Monitor\n\nEndpoints:\n  /run    - Trigger manual scrape\n  /status - Check monitor status",
      { status: 200 }
    );
  },
};
