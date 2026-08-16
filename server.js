/* Static server for Railway (and any plain Node host).
 *
 * Vercel serves this site straight from vercel.json, so nothing here runs
 * there. Railway has no equivalent, which means the headers vercel.json
 * declares - cache policy and the CSP - have to be reproduced in code or the
 * site would silently deploy without them.
 *
 * Node built-ins only: no dependencies to install, nothing to keep patched.
 */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const url = require("url");

const ROOT = __dirname;
const PORT = process.env.PORT || 3000;

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".geojson": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".txt": "text/plain; charset=utf-8",
};

// Kept in step with vercel.json so the site behaves the same on both hosts.
// connect-src allows GitHub raw because the page reads live results from
// there rather than from whatever this deployment happens to contain.
const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data:",
  "connect-src 'self' https://vitals.vercel-insights.com https://raw.githubusercontent.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

// Paths that must never be served, matched before anything touches the disk.
const PRIVATE = /^\/(work|scripts|node_modules)(\/|$)|(^|\/)\.[^/]/;

function cacheFor(pathname, ext) {
  // data/ is the live count: allow a CDN to hold it briefly, never a browser.
  if (pathname.startsWith("/data/")) {
    return "public, max-age=0, s-maxage=30, stale-while-revalidate=120";
  }
  // Fingerprinted by ?v= in index.html, so a short TTL is safe.
  if (ext === ".css" || ext === ".js") return "public, max-age=300";
  // Emblems are immutable once published.
  if (pathname.startsWith("/assets/")) return "public, max-age=86400";
  if (ext === ".html") return "no-cache";
  return "public, max-age=3600";
}

function send(res, status, body, headers) {
  res.writeHead(status, Object.assign({
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
  }, headers || {}));
  res.end(body);
}

const server = http.createServer(function (req, res) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    return send(res, 405, "Method not allowed", { "Content-Type": "text/plain" });
  }

  let pathname;
  try {
    pathname = decodeURIComponent(url.parse(req.url).pathname || "/");
  } catch (e) {
    return send(res, 400, "Bad request", { "Content-Type": "text/plain" });
  }

  // Railway health checks hit this; it must not depend on any file.
  if (pathname === "/healthz") {
    return send(res, 200, "ok", { "Content-Type": "text/plain" });
  }

  // Never serve operator state, however the working tree happens to look.
  // work/ holds the sheet images, raw reader output and the review queue,
  // which is deliberately unpublished; scripts/ and .git are nobody's
  // business either. These are gitignored so a clean deploy lacks them, but
  // the server must not depend on that being true.
  if (PRIVATE.test(pathname)) {
    return send(res, 404, "Not found", { "Content-Type": "text/plain" });
  }

  if (pathname === "/") pathname = "/index.html";
  // cleanUrls parity with Vercel: /method serves method.html if it exists.
  let rel = pathname.replace(/^\/+/, "");
  let file = path.join(ROOT, rel);

  // Contain every request inside ROOT: a crafted path must not escape it.
  if (path.relative(ROOT, file).startsWith("..")) {
    return send(res, 403, "Forbidden", { "Content-Type": "text/plain" });
  }

  fs.stat(file, function (err, st) {
    if (!err && st.isDirectory()) {
      file = path.join(file, "index.html");
    } else if (err && !path.extname(file)) {
      file = file + ".html";
    }
    fs.readFile(file, function (err2, buf) {
      if (err2) {
        return send(res, 404, "Not found", { "Content-Type": "text/plain" });
      }
      const ext = path.extname(file).toLowerCase();
      send(res, 200, req.method === "HEAD" ? "" : buf, {
        "Content-Type": TYPES[ext] || "application/octet-stream",
        "Content-Length": buf.length,
        "Cache-Control": cacheFor(pathname, ext),
      });
    });
  });
});

server.listen(PORT, function () {
  console.log("osun-results listening on " + PORT);
});
