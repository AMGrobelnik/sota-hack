// Waitlist store for the SOTA hack site: a count, sign-ups, and an admin route.
// Storage: one D1 database (binding DB). Secrets: ADMIN_TOKEN, IP_SALT.

const ALLOWED_ORIGIN = "https://amgrobelnik.github.io";
const MAX_BODY = 4096;
const RATE_LIMIT = 5; // sign-up attempts per IP hash per hour
const HOUR_MS = 3600_000;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function cors(request) {
  if (request.headers.get("Origin") !== ALLOWED_ORIGIN) return {};
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(request, status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...cors(request), ...extra },
  });
}

async function count(env) {
  const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM signups").first();
  return row ? row.n : 0;
}

async function sha256Hex(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function timingSafeEqual(a, b) {
  const x = new TextEncoder().encode(a);
  const y = new TextEncoder().encode(b);
  if (x.length !== y.length) return false;
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

export function normaliseEmail(raw) {
  return String(raw).replace(/\s+/g, "").toLowerCase();
}

export function validate(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return "body must be a JSON object";
  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (name.length < 1 || name.length > 100) return "name must be 1 to 100 characters";
  if (typeof body.email !== "string") return "email is required";
  const email = normaliseEmail(body.email);
  if (email.length > 200 || !EMAIL_RE.test(email)) return "email is not valid";
  for (const key of ["organisation", "build", "variant"]) {
    const v = body[key];
    if (v === undefined || v === null) continue;
    if (typeof v !== "string" || v.length > 300) return `${key} must be text up to 300 characters`;
  }
  return null;
}

async function signUp(request, env) {
  if (!(request.headers.get("Content-Type") || "").toLowerCase().startsWith("application/json")) {
    return json(request, 415, { ok: false, error: "JSON only" });
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).length >= MAX_BODY) {
    return json(request, 413, { ok: false, error: "body too large" });
  }
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return json(request, 400, { ok: false, error: "invalid JSON" });
  }
  const error = validate(body);
  if (error) return json(request, 400, { ok: false, error });

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const ipHash = await sha256Hex(`${env.IP_SALT}:${ip}`);
  const now = Date.now();
  await env.DB.prepare("DELETE FROM attempts WHERE at < ?").bind(now - HOUR_MS).run();
  const recent = await env.DB.prepare("SELECT COUNT(*) AS n FROM attempts WHERE ip_hash = ?")
    .bind(ipHash)
    .first();
  if (recent && recent.n >= RATE_LIMIT) {
    return json(request, 429, { ok: false, error: "too many sign-ups, try later" });
  }

  const opt = (v) => (typeof v === "string" ? v.trim() : null);
  await env.DB.batch([
    env.DB.prepare("INSERT INTO attempts (ip_hash, at) VALUES (?, ?)").bind(ipHash, now),
    env.DB.prepare(
      "INSERT INTO signups (email, name, organisation, build, variant, created_at) " +
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(email) DO NOTHING",
    ).bind(
      normaliseEmail(body.email),
      body.name.trim(),
      opt(body.organisation),
      opt(body.build),
      opt(body.variant),
      new Date(now).toISOString(),
    ),
  ]);
  return json(request, 200, { ok: true, count: await count(env) });
}

function csvCell(v) {
  const s = v === null || v === undefined ? "" : String(v);
  // Neutralise spreadsheet formulas, then quote.
  const safe = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return `"${safe.replace(/"/g, '""')}"`;
}

async function admin(request, env, url) {
  const auth = request.headers.get("Authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  if (!env.ADMIN_TOKEN || !token || !timingSafeEqual(token, env.ADMIN_TOKEN)) {
    return new Response("not found", { status: 404 });
  }
  if (url.pathname === "/admin/export" && request.method === "GET") {
    const { results } = await env.DB.prepare(
      "SELECT created_at, name, email, organisation, build, variant FROM signups ORDER BY created_at",
    ).all();
    const cols = ["created_at", "name", "email", "organisation", "build", "variant"];
    const lines = [cols.join(",")].concat(results.map((r) => cols.map((c) => csvCell(r[c])).join(",")));
    return new Response(lines.join("\r\n") + "\r\n", {
      headers: { "Content-Type": "text/csv; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  if (url.pathname === "/admin/signup" && request.method === "DELETE") {
    const email = normaliseEmail(url.searchParams.get("email") || "");
    const res = await env.DB.prepare("DELETE FROM signups WHERE email = ?").bind(email).run();
    return Response.json({ ok: true, deleted: res.meta.changes, count: await count(env) });
  }
  return new Response("not found", { status: 404 });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/admin/")) return admin(request, env, url);
    if (url.pathname !== "/") return new Response("not found", { status: 404 });
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(request) });
    if (request.method === "GET") {
      return json(request, 200, { count: await count(env) }, { "Cache-Control": "public, max-age=5" });
    }
    if (request.method === "POST") return signUp(request, env);
    return json(request, 405, { ok: false, error: "method not allowed" }, { Allow: "GET, POST, OPTIONS" });
  },
};
