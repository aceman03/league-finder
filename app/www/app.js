"use strict";

// League Finder: loads the standardized dataset (league-data repo,
// schema/leagues.schema.json) from a private GitHub repo and lets you search
// and filter it. Data and settings are cached on the device.

const PAGE_SIZE = 50;
const DAY_NAMES = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };
const LABELS = {
  traditional: "Traditional", short_season: "Short season", national_league: "National league",
  school_special_needs: "School / special needs", tournament: "Tournament",
  mixed: "Mixed", youth: "Youth", adult_child: "Adult + child", women: "Women", men: "Men", senior: "Senior",
  weekly: "Weekly", biweekly: "Every other week", every_4_weeks: "Every 4 weeks", monthly: "Monthly",
};

const $ = (id) => document.getElementById(id);
const store = {
  get(key, fallback = null) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* quota or disabled */ }
  },
};

const state = {
  data: null,          // { centers, leagues, generated_at }
  centers: new Map(),  // id -> center
  origin: null,        // { lat, lon, label }
  days: new Set(),
  shown: PAGE_SIZE,
};

// ---------- data loading ----------

// Settings entered in the app win; otherwise use what the build baked in.
function settings() {
  const built = window.LEAGUE_FINDER_CONFIG || {};
  const defaults = { token: "", repo: "aceman03/league-data", path: "data/leagues.json" };
  const saved = store.get("settings");
  if (saved && saved.token) return { ...saved, builtIn: false };
  const s = { ...defaults, ...Object.fromEntries(Object.entries(built).filter(([, v]) => v)) };
  return { ...s, token: String(s.token).trim(), builtIn: !!s.token };
}

async function fetchDataset(s, etag) {
  const url = `https://api.github.com/repos/${s.repo}/contents/${s.path}`;
  const headers = { Accept: "application/vnd.github.raw+json", Authorization: `Bearer ${s.token}` };
  if (etag) headers["If-None-Match"] = etag;
  const resp = await fetch(url, { headers, cache: "no-store" });
  if (resp.status === 304) return { notModified: true };
  if (resp.status === 401) throw new Error("GitHub rejected the token (401). Check that it hasn't expired.");
  if (resp.status === 403) throw new Error("The token can't read that repo (403). Give it read-only Contents access.");
  if (resp.status === 404) throw new Error("Repo or file not found (404). Check the names, and that the token can see the repo.");
  if (!resp.ok) throw new Error(`GitHub returned ${resp.status}.`);
  const data = await resp.json();
  if (!data || !Array.isArray(data.leagues) || !Array.isArray(data.centers)) throw new Error("That file isn't a league dataset.");
  return { data, etag: resp.headers.get("ETag") };
}

function useDataset(data) {
  state.data = data;
  state.centers = new Map(data.centers.map((c) => [c.id, c]));
  fillOptions("format", data.leagues.map((l) => l.format));
  fillOptions("audience", data.leagues.map((l) => l.audience));
  restoreFilters();
  $("setup").hidden = true;
  $("main").hidden = false;
  $("data-info").textContent =
    `${data.leagues.length.toLocaleString()} listings at ${data.centers.length} centers · data updated ${fmtDateTime(data.generated_at)}`;
  render();
}

async function refresh({ quiet }) {
  const s = settings();
  if (!s.token) { showSetup(); return; }
  try {
    const result = await fetchDataset(s, state.data ? store.get("etag") : null);
    if (result.notModified) return;
    store.set("dataset", result.data);
    store.set("etag", result.etag);
    useDataset(result.data);
  } catch (err) {
    if (quiet && state.data) return; // keep showing cached data when offline
    showSetup(s.builtIn ? `The token built into this app didn't work: ${err.message}` : err.message);
  }
}

function showSetup(message = "") {
  const s = settings();
  $("token").value = s.token;
  $("repo").value = s.repo;
  $("path").value = s.path;
  $("setup-error").textContent = message;
  $("close-settings").hidden = !state.data;
  $("setup").hidden = false;
  $("main").hidden = true;
}

// ---------- filtering ----------

const FILTER_IDS = ["q", "radius", "kind", "format", "audience", "skill", "team-size", "starts", "time"];

function saveFilters() {
  const f = Object.fromEntries(FILTER_IDS.map((id) => [id, $(id).value]));
  f.days = [...state.days];
  store.set("filters", f);
}

function restoreFilters() {
  const f = store.get("filters");
  if (!f) return;
  for (const id of FILTER_IDS) {
    if (f[id] !== undefined && [...($(id).options || [{ value: f[id] }])].some((o) => o.value === f[id])) $(id).value = f[id];
  }
  state.days = new Set(f.days || []);
  document.querySelectorAll("[data-day]").forEach((b) => b.setAttribute("aria-pressed", state.days.has(b.dataset.day)));
}

function fillOptions(id, values) {
  const select = $(id);
  const keep = select.options[0];
  select.replaceChildren(keep);
  for (const v of [...new Set(values.filter(Boolean))].sort()) {
    select.append(new Option(label(v), v));
  }
}

function label(v) {
  return LABELS[v] || v.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function milesBetween(a, b) {
  const R = 3958.8, rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDays(iso, n) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// A 5-digit query matching a center's zip searches around that center
// instead of matching text.
function zipOrigin(q) {
  if (!/^\d{5}$/.test(q)) return null;
  for (const c of state.centers.values()) {
    if (c.postal_code === q && c.latitude != null) return { lat: c.latitude, lon: c.longitude, label: q };
  }
  return null;
}

const REGION_NAMES = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado",
  CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky",
  LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota",
  MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire",
  NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota",
  OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island",
  SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont",
  VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming", PR: "Puerto Rico",
  AB: "Alberta", BC: "British Columbia", MB: "Manitoba", NB: "New Brunswick", NL: "Newfoundland and Labrador",
  NS: "Nova Scotia", ON: "Ontario", PE: "Prince Edward Island", QC: "Quebec", SK: "Saskatchewan",
};

function haystack(l, c) {
  return [l.name, c?.name, c?.brand, c?.city, c?.state, REGION_NAMES[c?.state], c?.postal_code].filter(Boolean).join(" ").toLowerCase();
}

function filtered() {
  const q = $("q").value.trim();
  const origin = zipOrigin(q) || state.origin;
  const terms = origin && origin.label === q ? [] : q.toLowerCase().split(/\s+/).filter(Boolean);
  const radius = Number($("radius").value);
  const kind = $("kind").value, format = $("format").value, audience = $("audience").value;
  const skill = $("skill").value, teamSize = $("team-size").value, starts = $("starts").value, time = $("time").value;
  const now = today();

  const out = [];
  for (const l of state.data.leagues) {
    const c = state.centers.get(l.center_id);
    if (kind && l.kind !== kind) continue;
    if (format && l.format !== format) continue;
    if (audience && l.audience !== audience) continue;
    if (skill && !l.skill_levels.includes(skill)) continue;
    if (teamSize && !(teamSize === "5" ? l.team_size >= 5 : l.team_size === Number(teamSize))) continue;
    if (state.days.size && !l.days.some((d) => state.days.has(d))) continue;
    if (starts === "upcoming" && !(l.season_start && l.season_start >= now)) continue;
    if (starts === "30" && !(l.season_start && l.season_start >= now && l.season_start <= addDays(now, 30))) continue;
    if (time) {
      const h = Number((l.start_time || "").slice(0, 2));
      if (!l.start_time || (time === "morning" && h >= 12) || (time === "afternoon" && (h < 12 || h >= 17)) || (time === "evening" && h < 17)) continue;
    }
    if (terms.length) {
      const hay = haystack(l, c);
      if (!terms.every((t) => hay.includes(t))) continue;
    }
    let miles = null;
    if (origin && c?.latitude != null) {
      miles = milesBetween(origin, { lat: c.latitude, lon: c.longitude });
      if (radius && miles > radius) continue;
    } else if (origin && radius) {
      continue;
    }
    out.push({ l, c, miles });
  }
  out.sort((a, b) =>
    (a.miles ?? Infinity) - (b.miles ?? Infinity) ||
    (a.l.season_start || "9999").localeCompare(b.l.season_start || "9999") ||
    a.l.name.localeCompare(b.l.name));
  return { items: out, origin };
}

// ---------- rendering ----------

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function fmtTime(t) {
  if (!t) return "";
  let [h, m] = t.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${h}:${String(m).padStart(2, "0")} ${ampm}`;
}

function fmtDate(iso) {
  if (!iso) return "";
  return new Date(iso.slice(0, 10) + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function fmtDateTime(iso) {
  return iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "unknown";
}

function when(l) {
  const days = l.days.map((d) => DAY_NAMES[d]).join(", ");
  return [days, fmtTime(l.start_time)].filter(Boolean).join(" · ");
}

function chips(l) {
  const out = [label(l.format || l.kind), l.audience && label(l.audience)];
  if (l.skill_levels.length) out.push(l.skill_levels.length > 1
    ? `${label(l.skill_levels[0])}–${label(l.skill_levels[l.skill_levels.length - 1])}`
    : label(l.skill_levels[0]));
  if (l.team_size) out.push(l.team_size === 1 ? "Singles" : `${l.team_size}/team`);
  if (l.weeks) out.push(`${l.weeks} wk`);
  return out.filter(Boolean);
}

function render() {
  saveFilters();
  const { items, origin } = filtered();
  const where = origin ? ` within ${$("radius").value === "0" ? "any distance" : $("radius").value + " mi"} of ${origin.label}` : "";
  $("status").textContent = `${items.length.toLocaleString()} result${items.length === 1 ? "" : "s"}${where}`;
  $("near-me").setAttribute("aria-pressed", String(!!state.origin));

  const list = $("results");
  list.replaceChildren();
  for (const [i, { l, c, miles }] of items.slice(0, state.shown).entries()) {
    const li = document.createElement("li");
    li.innerHTML = `
      <button class="card" data-index="${i}">
        <h3>${esc(l.name)}</h3>
        <div class="where">${esc(c?.name || "")}${c ? ` · ${esc(c.city)}, ${esc(c.state)}` : ""}${miles != null ? ` · ${miles.toFixed(miles < 10 ? 1 : 0)} mi` : ""}</div>
        <div class="when">${esc(when(l))}${l.season_start ? ` <span class="where">starts ${esc(fmtDate(l.season_start))}</span>` : ""}</div>
        <div class="chips">${chips(l).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
      </button>`;
    li.querySelector("button").addEventListener("click", () => showDetail(l, c, miles));
    list.append(li);
  }
  $("more").hidden = items.length <= state.shown;
}

function showDetail(l, c, miles) {
  const rows = [
    ["When", when(l)],
    ["Season", [fmtDate(l.season_start), fmtDate(l.season_end)].filter(Boolean).join(" – ")],
    ["Length", l.weeks ? `${l.weeks} weeks` : ""],
    ["How often", l.frequency_text || label(l.frequency || "")],
    ["Format", label(l.format || l.kind)],
    ["Who", l.audience ? label(l.audience) : ""],
    ["Skill", l.skill_levels.map(label).join(", ")],
    ["Teams", [l.team_size && `${l.team_size} per team`, l.teams && `${l.teams} teams`].filter(Boolean).join(", ")],
    ["Meeting", l.meeting_at ? `${fmtDate(l.meeting_at)} ${fmtTime(l.meeting_at.slice(11, 16))}` : ""],
    ["Center", c ? `${c.name}\n${c.street}, ${c.city}, ${c.state} ${c.postal_code}` : ""],
    ["Distance", miles != null ? `${miles.toFixed(1)} mi` : ""],
  ].filter(([, v]) => v);
  const map = c?.latitude != null ? `https://www.google.com/maps/search/?api=1&query=${c.latitude},${c.longitude}` : null;
  $("detail-body").innerHTML = `
    <h2>${esc(l.name)}</h2>
    <div class="chips">${chips(l).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd class="desc">${esc(v)}</dd>`).join("")}</dl>
    ${l.description ? `<p class="desc">${esc(l.description)}</p>` : ""}
    <div class="actions">
      <a class="primary" href="${esc(l.signup_url)}">Sign up</a>
      ${c?.phone ? `<a href="tel:${esc(c.phone.replace(/[^\d+]/g, ""))}">Call center</a>` : ""}
      ${map ? `<a href="${esc(map)}">Directions</a>` : ""}
      ${c?.url ? `<a href="${esc(c.url)}">Center page</a>` : ""}
    </div>`;
  $("detail").showModal();
}

// ---------- updates ----------
//
// New versions are published as releases (tagged vX.Y.Z, with
// League-Finder.apk attached) in the same private repo as the data, because
// the APK carries the data token. The token reads them; installing stays
// manual since Android always asks before installing an APK.

const APP_VERSION = window.LEAGUE_FINDER_VERSION || "0.0.0";
const CHECK_EVERY_MS = 6 * 60 * 60 * 1000;   // on launch, at most this often
const WATCH_EVERY_MS = 30 * 60 * 1000;       // while the app stays open

// "v0.10.2" -> [0, 10, 2]; compares numerically, so 0.10 > 0.9.
const versionParts = (v) => String(v).replace(/^v/i, "").split(".").map((n) => parseInt(n, 10) || 0);
function isNewer(a, b) {
  const x = versionParts(a), y = versionParts(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  }
  return false;
}

// -> { available, version, notes, downloadUrl, pageUrl }; throws on network/API errors.
async function checkForUpdate() {
  const s = settings();
  if (!s.token) throw new Error("no GitHub token set");
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), 10000);
  let resp;
  try {
    resp = await fetch(`https://api.github.com/repos/${s.repo}/releases/latest`, {
      headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${s.token}` },
      cache: "no-store", signal: abort.signal,
    });
  } finally {
    clearTimeout(timer);
  }
  store.set("update-checked", Date.now());
  if (resp.status === 404) return { available: false, version: null }; // no releases yet
  if (!resp.ok) throw new Error(`GitHub answered ${resp.status}`);
  const release = await resp.json();
  const version = String(release.tag_name || "").replace(/^v/i, "");
  const apk = (release.assets || []).find((a) => /\.apk$/i.test(a.name));
  return {
    available: isNewer(version, APP_VERSION),
    version,
    notes: release.body || "",
    downloadUrl: apk?.browser_download_url || release.html_url,
    pageUrl: release.html_url,
  };
}

// External links leave the app: Capacitor hands non-app URLs to the browser.
function openExternal(url) {
  window.location.href = url;
}

function showUpdateBanner(update) {
  const banner = $("update-banner");
  banner.innerHTML = `
    <span><b>League Finder ${esc(update.version)}</b> is available. You have ${esc(APP_VERSION)}.</span>
    <button class="primary" data-update="download">Download</button>
    <button data-update="notes">What's new</button>
    <button class="icon" data-update="later" aria-label="Not now" title="Not now">×</button>`;
  banner.hidden = false;
  banner.onclick = (e) => {
    const action = e.target.closest("[data-update]")?.dataset.update;
    if (action === "download") openExternal(update.downloadUrl);
    if (action === "notes") openExternal(update.pageUrl);
    if (action === "later") {
      store.set("update-dismissed", update.version);
      banner.hidden = true;
    }
  };
}

async function autoCheck({ force = false } = {}) {
  if (!force && Date.now() - (store.get("update-checked") || 0) < CHECK_EVERY_MS) return;
  try {
    const update = await checkForUpdate();
    if (update.available && update.version !== store.get("update-dismissed")) showUpdateBanner(update);
  } catch {
    // Offline, no token yet, or rate-limited: try again later.
  }
}

// ---------- wiring ----------

function rerender() { state.shown = PAGE_SIZE; render(); }

$("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  store.set("settings", { token: $("token").value.trim(), repo: $("repo").value.trim(), path: $("path").value.trim() });
  store.set("etag", null);
  $("setup-error").textContent = "Loading…";
  await refresh({ quiet: false });
});
$("open-settings").addEventListener("click", () => showSetup());
$("app-version").textContent = APP_VERSION;
$("check-update").addEventListener("click", async () => {
  const status = $("update-status");
  status.textContent = "Checking…";
  try {
    const update = await checkForUpdate();
    if (update.available) {
      status.textContent = `Version ${update.version} is available.`;
      showUpdateBanner(update);
    } else {
      status.textContent = update.version
        ? `You're up to date (latest is ${update.version}).`
        : "No releases published yet.";
    }
  } catch (err) {
    status.textContent = `Couldn't check: ${err.message}. Are you online?`;
  }
});
$("close-settings").addEventListener("click", () => { $("setup").hidden = true; $("main").hidden = false; });

for (const id of FILTER_IDS) $(id).addEventListener(id === "q" ? "input" : "change", rerender);
document.querySelectorAll("[data-day]").forEach((b) => b.addEventListener("click", () => {
  const d = b.dataset.day;
  state.days.has(d) ? state.days.delete(d) : state.days.add(d);
  b.setAttribute("aria-pressed", state.days.has(d));
  rerender();
}));
$("more").addEventListener("click", () => { state.shown += PAGE_SIZE; render(); });
$("reset").addEventListener("click", () => {
  for (const id of FILTER_IDS) if (id !== "q" && id !== "radius" && id !== "kind") $(id).value = "";
  state.days.clear();
  document.querySelectorAll("[data-day]").forEach((b) => b.setAttribute("aria-pressed", "false"));
  rerender();
});
$("near-me").addEventListener("click", () => {
  if (state.origin) { state.origin = null; rerender(); return; }
  if (!navigator.geolocation) { $("status").textContent = "Location isn't available on this device."; return; }
  $("status").textContent = "Finding your location…";
  navigator.geolocation.getCurrentPosition(
    (pos) => { state.origin = { lat: pos.coords.latitude, lon: pos.coords.longitude, label: "you" }; rerender(); },
    (err) => { $("status").textContent = `Couldn't get your location: ${err.message}`; },
    { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 },
  );
});

(function start() {
  const cached = store.get("dataset");
  if (cached) useDataset(cached);
  refresh({ quiet: true });
  autoCheck();
  setInterval(() => autoCheck({ force: true }), WATCH_EVERY_MS);
})();
