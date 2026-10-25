/* P2000 Map Card - bundled with the p2000_alarmfase1 integration (auto-registered). */
(() => {
const P2000_VERSION = "2.1.8";
const BASE = "/p2000_alarmfase1";
const SERVICES = {
  "Ambulance": { img: "ambulance.webp", color: "#f4c20d", label: "Ambulance" },
  "Fire Department": { img: "fire.webp", color: "#e53935", label: "Brandweer" },
  "Police": { img: "police.webp", color: "#1e63d6", label: "Politie" },
  "Trauma Heli": { img: "heli.webp", color: "#ff9800", label: "Traumaheli" },
  "KNRM / Water Rescue": { img: "heli.webp", color: "#00acc1", label: "KNRM" },
  "Other": { img: "ambulance.webp", color: "#9e9e9e", label: "Overig" },
};
const MARKER_CSS = `
        .p2000-mk{cursor:pointer}
        .mk.approx .ph{border-style:dashed}
        .mk.approx .ring{border-style:dashed}
        .mk .apx{position:absolute;right:-2px;top:-2px;z-index:3;width:16px;height:16px;border-radius:50%;background:#fff;color:#000;font:700 12px/16px sans-serif;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.5)}
        .mk{position:relative;width:46px;height:46px}
        .mk .ph{position:absolute;inset:3px;border-radius:50%;background:#fff center/cover no-repeat;border:3px solid var(--c);box-shadow:0 3px 8px rgba(0,0,0,.45);z-index:2}
        .mk .ring{position:absolute;inset:0;border-radius:50%;border:3px solid var(--c);animation:pulse 1.8s ease-out infinite;z-index:1}
        .mk.new{animation:drop .7s cubic-bezier(.3,1.6,.5,1) both}
        .mk.new .ph{animation:flash 1s steps(2) infinite}
        .mk.old{opacity:.6;filter:saturate(.6)}
        .mk.old .ring{animation-duration:3.2s;opacity:.5}
        @keyframes pulse{0%{transform:scale(.9);opacity:.9}100%{transform:scale(2.1);opacity:0}}
        @keyframes drop{0%{transform:translateY(-60px) scale(.4);opacity:0}100%{transform:none;opacity:1}}
        @keyframes flash{0%{box-shadow:0 0 0 3px #1e63d6,0 0 14px #1e63d6}50%{box-shadow:0 0 0 3px #e53935,0 0 14px #e53935}}
        .pop{display:flex;gap:10px;min-width:220px}
        .pop img{width:64px;height:64px;border-radius:10px;object-fit:cover}
        .pop b{display:block;margin-bottom:4px}
        .pop small{opacity:.75}
`;
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const safeUrl = (u) => { const t = typeof u === "string" ? u.trim() : ""; return /^https?:\/\//i.test(t) ? t : ""; };
class P2000MapCard extends HTMLElement {
  static getStubConfig(hass) {
    const e = Object.keys(hass.states).find((k) => k.startsWith("sensor.") && hass.states[k].attributes.calls);
    return { entity: e || "sensor.p2000", height: 400, show_list: true };
  }
  setConfig(config) {
    if (!config.entity && !config.entities) throw new Error("Set 'entity' (or 'entities') to a P2000 sensor");
    this._config = { height: 400, zoom: 11, show_list: true, list_size: 6, max_markers: 50, dark: "auto", ...config };
    this._entities = config.entities || [config.entity];
    this._sig = null;
    if (!this.shadowRoot) this._build();
  }
  getCardSize() { return Math.ceil(this._config.height / 50) + (this._config.show_list ? 3 : 0); }
  _build() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        ha-card{overflow:hidden}
        .hdr{display:flex;align-items:center;gap:8px;padding:12px 16px 8px;font-weight:600;font-size:1.1em}
        .hdr img{width:28px;height:28px;border-radius:7px}
        .hdr .cnt{margin-left:auto;font-size:.8em;opacity:.7}
        #map{width:100%;z-index:0;position:relative}
        #map ha-map{display:block;height:100%}
        .nomap{padding:16px;opacity:.7}
        .popwrap{position:absolute;left:10px;right:10px;bottom:10px;z-index:1000;background:var(--card-background-color,#fff);color:var(--primary-text-color,#000);border-radius:12px;padding:10px 30px 10px 10px;box-shadow:0 4px 14px rgba(0,0,0,.35);border-left:4px solid var(--c);animation:fade .3s both}
        .popwrap .x{position:absolute;top:4px;right:6px;border:0;background:none;font-size:20px;cursor:pointer;color:inherit}
        .popwrap a{color:var(--primary-color,#03a9f4)}
        .pop{display:flex;gap:10px;min-width:220px}
        .pop img{width:64px;height:64px;border-radius:10px;object-fit:cover}
        .pop b{display:block;margin-bottom:4px}
        .pop small{opacity:.75}
        ul{list-style:none;margin:0;padding:4px 0 8px}
        li{display:flex;gap:10px;align-items:center;padding:6px 16px;cursor:pointer;animation:fade .4s both}
        li:hover{background:rgba(127,127,127,.12)}
        li img{width:36px;height:36px;border-radius:50%;border:2px solid var(--c);object-fit:cover}
        li .t{flex:1;min-width:0}
        li .t div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        li .t small{opacity:.7}
        .tag{font-size:.75em;padding:2px 6px;border-radius:6px;background:var(--c);color:#000;font-weight:600}
        @keyframes fade{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}
      </style>
      <ha-card><div class="hdr"><img src="${BASE}/icon.png" onerror="this.remove()"><span class="ttl"></span><span class="cnt"></span></div>
      <div id="map"></div><ul></ul></ha-card>`;
  }
  set hass(hass) {
    this._hass = hass;
    const calls = [];
    for (const id of this._entities) {
      const st = hass.states[id];
      if (st && Array.isArray(st.attributes.calls)) calls.push(...st.attributes.calls);
    }
    calls.sort((a, b) => String(b.absolute_time_str).localeCompare(String(a.absolute_time_str)));
    const sig = JSON.stringify(calls.map((c) => c.absolute_time_str + c.message));
    if (sig === this._sig) return;
    this._sig = sig;
    this._calls = calls.slice(0, this._config.max_markers);
    this._render();
  }
  // Home Assistant's own map element (same tiles as the native Map card). HA's tile layers are left untouched.
  async _ensureHaMap() {
    if (customElements.get("ha-map")) return true;
    try {
      const h = await window.loadCardHelpers?.();
      if (h) { const c = await h.createCardElement({ type: "map", entities: [] }); c.hass = this._hass; }
      await Promise.race([customElements.whenDefined("ha-map"), new Promise((r) => setTimeout(r, 8000))]);
    } catch (e) { /* ignore */ }
    return !!customElements.get("ha-map");
  }
  // HA 2026.10+ ha-map runs a pluggable engine (MapLibre vector, Leaflet fallback) exposed as
  // map._engine with addMarker(element, [lat, lng], opts) / fitBounds / setView. Older HA exposes
  // map.leafletMap + map.Leaflet. Both are wrapped in one small adapter; HA's tiles are untouched.
  _adapter(map) {
    const eng = map._engine;
    if (eng && typeof eng.addMarker === "function") return {
      key: eng,
      add: (el, ll, i) => eng.addMarker(el, ll, { size: [46, 46], anchor: [23, 23], interactive: true, nativeTitle: false, raised: i === 0 }),
      fit: (pts) => eng.fitBounds(pts, { maxZoom: 14, pad: 0.15, padding: { top: 40, right: 40, bottom: 40, left: 40 } }),
      fly: (ll) => eng.setView(ll, 15),
    };
    const lm = map.leafletMap, Lf = map.Leaflet;
    if (lm && Lf) {
      if (!this._legacyLayer || this._legacyKey !== lm) { this._legacyLayer = Lf.layerGroup().addTo(lm); this._legacyKey = lm; }
      const grp = this._legacyLayer;
      return {
        key: lm,
        add: (el, ll, i) => { const m = Lf.marker(ll, { icon: Lf.divIcon({ className: "", iconSize: [46, 46], iconAnchor: [23, 23], html: el }), zIndexOffset: 1000 - i }).addTo(grp);
          return { remove: () => grp.removeLayer(m) }; },
        fit: (pts) => lm.fitBounds(pts, { padding: [30, 30], maxZoom: 14 }),
        fly: (ll) => lm.flyTo(ll, 15),
      };
    }
    return null;
  }
  _injectCss(map) {
    const host = map.shadowRoot || map.renderRoot;
    if (host && !host.querySelector("style[data-p2000]")) { const st = document.createElement("style"); st.dataset.p2000 = "1"; st.textContent = MARKER_CSS; host.appendChild(st); }
  }
  _initHaMap(el) {
    if (!this._mapInit) this._mapInit = (async () => {
      if (!(await this._ensureHaMap())) { el.innerHTML = '<div class="nomap">Home Assistant map not available</div>'; return null; }
      const cfg = this._config, map = document.createElement("ha-map");
      map.hass = this._hass; map.zoom = cfg.zoom; map.autoFit = false; map.fitZones = false; map.entities = [];
      if (cfg.dark === true) map.themeMode = "dark"; else if (cfg.dark === false) map.themeMode = "light";
      el.appendChild(map); this._haMap = map;
      // Wait for HA's engine (up to ~20s); never give up permanently - keep watching for a (re)built engine.
      for (let t = 0; t < 200 && !this._adapter(map); t++) await new Promise((r) => setTimeout(r, 100));
      clearInterval(this._watch);
      this._watch = setInterval(() => { const a = this._adapter(map); if (a && a.key !== this._engKey) this._drawMarkers(); }, 1000);
      return map;
    })();
    return this._mapInit;
  }
  _closePopup() { const p = this.shadowRoot.querySelector(".popwrap"); if (p) p.remove(); }
  _openPopup(i) {
    const c = this._calls[i]; if (!c) return;
    const s = SERVICES[c.service_type] || SERVICES.Other;
    this._closePopup();
    const w = document.createElement("div"); w.className = "popwrap"; w.style.setProperty("--c", s.color);
    w.innerHTML = `<button class="x" aria-label="close">×</button><div class="pop"><img src="${BASE}/${s.img}"><div><b>${esc(c.title)}</b>
        <small>${esc(c.date)} ${esc(c.time)} · ${esc(c.priority || s.label)}</small><br><small>${c.approx ? "~ " : ""}${esc(c.address)} ${esc(c.city)}${c.latitude == null ? " · geen locatie" : c.approx ? (c.location_source === "postcode" ? " · locatie via postcode" : " · locatie via adres") : ""}</small>
        ${safeUrl(c.url) ? `<br><a href="${esc(safeUrl(c.url))}" target="_blank" rel="noopener">alarmfase1.nl ↗</a>` : ""}</div></div>`;
    w.querySelector(".x").onclick = (e) => { e.stopPropagation(); this._closePopup(); };
    this.shadowRoot.getElementById("map").appendChild(w);
  }
  _drawMarkers() {
    const map = this._haMap; if (!map) return;
    const ad = this._adapter(map);
    if (!ad) return;
    this._injectCss(map);
    if (ad.key !== this._engKey) { this._engKey = ad.key; this._handles = []; this._fitted = false; }
    (this._handles || []).forEach((h) => { try { h && h.remove(); } catch (e) { /* engine gone */ } });
    this._handles = [];
    const cfg = this._config, pts = [], now = Date.now(), seen = this._seen || new Set(), next = new Set();
    this._lls = [];
    this._calls.forEach((c, i) => {
      const s = SERVICES[c.service_type] || SERVICES.Other;
      const key = c.absolute_time_str + c.message; next.add(key);
      if (c.latitude == null || c.longitude == null) { this._lls.push(null); return; }
      const age = c.absolute_time_str ? (now - new Date(c.absolute_time_str).getTime()) / 60000 : 999;
      const cls = (this._seen && !seen.has(key)) || i === 0 ? "new" : age > (cfg.fade_minutes || 60) ? "old" : "";
      // The engine positions `el` with its own transform/position; all visuals + animations live on the inner .mk
      const el = document.createElement("div");
      el.className = "p2000-mk"; el.title = c.title || "";
      el.innerHTML = `<div class="mk ${cls}${c.approx ? " approx" : ""}" style="--c:${s.color}"><div class="ring"></div><div class="ph" style="background-image:url(${BASE}/${s.img})"></div>${c.approx ? '<span class="apx" title="Locatie geschat">~</span>' : ""}</div>`;
      el.addEventListener("click", (e) => { e.stopPropagation(); this._openPopup(i); });
      const ll = [Number(c.latitude), Number(c.longitude)];
      try { this._handles.push(ad.add(el, ll, i)); } catch (e) { console.warn("P2000-MAP-CARD marker", e); }
      this._lls.push(ll); pts.push(ll);
    });
    this._seen = next;
    this._pts = pts;
    if (pts.length && !this._fitted && cfg.auto_fit !== false) this._fit(0);
  }
  _fit(n) {
    const map = this._haMap, ad = map && this._adapter(map), eng = map && map._engine;
    if (!ad || !this._pts || !this._pts.length) return;
    const ready = !eng || typeof eng.hasUsableSize !== "function" || eng.hasUsableSize();
    if (!ready) { if (n < 50) setTimeout(() => this._fit(n + 1), 200); return; }
    try { eng && eng.invalidateSize && eng.invalidateSize(); ad.fit(this._pts); this._fitted = true; }
    catch (e) { if (n < 50) setTimeout(() => this._fit(n + 1), 200); }
  }
  disconnectedCallback() { clearInterval(this._watch); this._watch = null; }
  connectedCallback() { if (this._haMap && !this._watch) this._watch = setInterval(() => { const a = this._adapter(this._haMap); if (a && a.key !== this._engKey) this._drawMarkers(); }, 1000); }
  async _render() {
    const r = this.shadowRoot, cfg = this._config;
    r.querySelector(".ttl").textContent = cfg.title || "P2000 meldingen";
    r.querySelector(".cnt").textContent = `${this._calls.length} meldingen`;
    const el = r.getElementById("map");
    el.style.height = `${cfg.height}px`;
    if (this._haMap) this._haMap.hass = this._hass;
    await this._initHaMap(el);
    this._drawMarkers();
    const ul = r.querySelector("ul");
    ul.innerHTML = "";
    if (!cfg.show_list) return;
    this._calls.slice(0, cfg.list_size).forEach((c, i) => {
      const s = SERVICES[c.service_type] || SERVICES.Other;
      const li = document.createElement("li");
      li.style.setProperty("--c", s.color); li.style.animationDelay = `${i * 60}ms`;
      li.innerHTML = `<img src="${BASE}/${s.img}"><div class="t"><div>${esc(c.title)}</div><small>${esc(c.time)} · ${esc(c.city)}${c.latitude == null ? " · geen locatie" : c.approx ? " · ~" : ""}</small></div><span class="tag">${esc(c.priority || s.label)}</span>`;
      li.onclick = () => { const ll = this._lls && this._lls[i], ad = this._haMap && this._adapter(this._haMap); if (ll && ad) { try { ad.fly(ll); } catch (e) { /* ignore */ } } this._openPopup(i); };
      ul.appendChild(li);
    });
  }
}
const _existing = customElements.get("p2000-map-card");
if (!_existing) customElements.define("p2000-map-card", P2000MapCard);
else if (_existing !== P2000MapCard) {
  // An older card version was loaded first (cached JS / duplicate resource): upgrade it in place.
  for (const k of Object.getOwnPropertyNames(P2000MapCard.prototype)) if (k !== "constructor") Object.defineProperty(_existing.prototype, k, Object.getOwnPropertyDescriptor(P2000MapCard.prototype, k));
  _existing.getStubConfig = P2000MapCard.getStubConfig;
  console.warn("P2000-MAP-CARD: older version was already registered; upgraded to v" + P2000_VERSION + ". Remove duplicate resources / clear cache.");
}
window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === "p2000-map-card"))
  window.customCards.push({ type: "p2000-map-card", name: "P2000 Map Card", description: "Animated map of P2000 emergency calls (alarmfase1.nl)", preview: true });
console.info(`%c P2000-MAP-CARD %c v${P2000_VERSION} `, "background:#0b1d4a;color:#fff", "background:#e53935;color:#fff");
})();
