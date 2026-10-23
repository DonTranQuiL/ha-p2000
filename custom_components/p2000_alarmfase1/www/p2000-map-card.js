/* P2000 Map Card - bundled with the p2000_alarmfase1 integration (auto-registered). */
const P2000_VERSION = "2.1.0";
const BASE = "/p2000_alarmfase1";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const SERVICES = {
  "Ambulance": { img: "ambulance.webp", color: "#f4c20d", label: "Ambulance" },
  "Fire Department": { img: "fire.webp", color: "#e53935", label: "Brandweer" },
  "Police": { img: "police.webp", color: "#1e63d6", label: "Politie" },
  "Trauma Heli": { img: "heli.webp", color: "#ff9800", label: "Traumaheli" },
  "KNRM / Water Rescue": { img: "heli.webp", color: "#00acc1", label: "KNRM" },
  "Other": { img: "ambulance.webp", color: "#9e9e9e", label: "Overig" },
};
let leafletPromise;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletPromise) {
    leafletPromise = new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = LEAFLET_JS; s.onload = () => res(window.L); s.onerror = rej;
      document.head.appendChild(s);
    });
  }
  return leafletPromise;
}
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

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
      <link rel="stylesheet" href="${LEAFLET_CSS}">
      <style>
        ha-card{overflow:hidden}
        .hdr{display:flex;align-items:center;gap:8px;padding:12px 16px 8px;font-weight:600;font-size:1.1em}
        .hdr img{width:28px;height:28px;border-radius:7px}
        .hdr .cnt{margin-left:auto;font-size:.8em;opacity:.7}
        #map{width:100%;z-index:0}
        .mk{position:relative;width:46px;height:46px}
        .mk .ph{position:absolute;inset:3px;border-radius:50%;background:#fff center/cover no-repeat;border:3px solid var(--c);box-shadow:0 3px 8px rgba(0,0,0,.45);z-index:2}
        .mk .ring{position:absolute;inset:0;border-radius:50%;border:3px solid var(--c);animation:pulse 1.8s ease-out infinite;z-index:1}
        .mk.new{animation:drop .7s cubic-bezier(.3,1.6,.5,1) both}
        .mk.new .ph{animation:flash 1s steps(2) infinite}
        .mk.old{opacity:.6;filter:saturate(.6)}
        .mk.old .ring{display:none}
        @keyframes pulse{0%{transform:scale(.9);opacity:.9}100%{transform:scale(2.1);opacity:0}}
        @keyframes drop{0%{transform:translateY(-60px) scale(.4);opacity:0}100%{transform:none;opacity:1}}
        @keyframes flash{0%{box-shadow:0 0 0 3px #1e63d6,0 0 14px #1e63d6}50%{box-shadow:0 0 0 3px #e53935,0 0 14px #e53935}}
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
  async _render() {
    const r = this.shadowRoot, cfg = this._config;
    r.querySelector(".ttl").textContent = cfg.title || "P2000 meldingen";
    r.querySelector(".cnt").textContent = `${this._calls.length} meldingen`;
    const el = r.getElementById("map");
    el.style.height = `${cfg.height}px`;
    const L = await loadLeaflet();
    if (!this._map) {
      const home = [this._hass.config.latitude || 52.1, this._hass.config.longitude || 5.3];
      this._map = L.map(el, { zoomControl: true, attributionControl: true }).setView(home, cfg.zoom);
      const dark = cfg.dark === true || (cfg.dark === "auto" && this._hass.themes?.darkMode);
      L.tileLayer(dark ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { maxZoom: 19, attribution: "&copy; OpenStreetMap" + (dark ? " &copy; CARTO" : "") }).addTo(this._map);
      this._layer = L.layerGroup().addTo(this._map);
      new ResizeObserver(() => this._map.invalidateSize()).observe(el);
    }
    this._layer.clearLayers();
    const pts = [], now = Date.now(), seen = this._seen || new Set(), next = new Set();
    this._markers = [];
    this._calls.forEach((c, i) => {
      const s = SERVICES[c.service_type] || SERVICES.Other;
      const key = c.absolute_time_str + c.message; next.add(key);
      if (c.latitude == null || c.longitude == null) { this._markers.push(null); return; }
      const age = c.absolute_time_str ? (now - new Date(c.absolute_time_str).getTime()) / 60000 : 999;
      const cls = (this._seen && !seen.has(key)) || i === 0 ? "new" : age > (cfg.fade_minutes || 60) ? "old" : "";
      const icon = L.divIcon({ className: "", iconSize: [46, 46], iconAnchor: [23, 23], popupAnchor: [0, -22],
        html: `<div class="mk ${cls}" style="--c:${s.color}"><div class="ring"></div><div class="ph" style="background-image:url(${BASE}/${s.img})"></div></div>` });
      const m = L.marker([c.latitude, c.longitude], { icon, zIndexOffset: 1000 - i }).addTo(this._layer);
      m.bindPopup(`<div class="pop"><img src="${BASE}/${s.img}"><div><b>${esc(c.title)}</b>
        <small>${esc(c.date)} ${esc(c.time)} · ${esc(c.priority || s.label)}</small><br><small>${esc(c.address)} ${esc(c.city)}</small>
        ${c.url ? `<br><a href="${esc(c.url)}" target="_blank" rel="noopener">alarmfase1.nl ↗</a>` : ""}</div></div>`);
      this._markers.push(m); pts.push([c.latitude, c.longitude]);
    });
    this._seen = next;
    if (pts.length && !this._fitted && cfg.auto_fit !== false) { this._map.fitBounds(pts, { padding: [30, 30], maxZoom: 14 }); this._fitted = true; }
    const ul = r.querySelector("ul");
    ul.innerHTML = "";
    if (!cfg.show_list) return;
    this._calls.slice(0, cfg.list_size).forEach((c, i) => {
      const s = SERVICES[c.service_type] || SERVICES.Other;
      const li = document.createElement("li");
      li.style.setProperty("--c", s.color); li.style.animationDelay = `${i * 60}ms`;
      li.innerHTML = `<img src="${BASE}/${s.img}"><div class="t"><div>${esc(c.title)}</div><small>${esc(c.time)} · ${esc(c.city)}</small></div><span class="tag">${esc(c.priority || s.label)}</span>`;
      li.onclick = () => { const m = this._markers[i]; if (m) { this._map.flyTo(m.getLatLng(), 15); m.openPopup(); } };
      ul.appendChild(li);
    });
  }
}
if (!customElements.get("p2000-map-card")) customElements.define("p2000-map-card", P2000MapCard);
window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === "p2000-map-card"))
  window.customCards.push({ type: "p2000-map-card", name: "P2000 Map Card", description: "Animated map of P2000 emergency calls (alarmfase1.nl)", preview: true });
console.info(`%c P2000-MAP-CARD %c v${P2000_VERSION} `, "background:#0b1d4a;color:#fff", "background:#e53935;color:#fff");
