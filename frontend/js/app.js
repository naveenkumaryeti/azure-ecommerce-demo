// Shared helpers: API wrapper, toasts, nav, cart. The browser only ever talks to /api (same origin via nginx).
const API = "/api";
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const money = n => "₹" + Number(n).toLocaleString("en-IN");
const NOIMG = "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="100%" height="100%" fill="#e9ecef"/><text x="50%" y="50%" fill="#6c757d" font-family="sans-serif" text-anchor="middle">No image</text></svg>');
const imgUrl = p => p.image_url ? `${API}/images/${encodeURIComponent(p.image_url.split("/").pop())}` : NOIMG;

async function api(path, opts = {}) {
  const r = await fetch(API + path, opts);
  let d = null; try { d = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error((d && (d.message || d.error)) || `HTTP ${r.status}`);
  return d;
}
const jsonOpts = (method, body, headers = {}) => ({method, headers: {"Content-Type": "application/json", ...headers}, body: JSON.stringify(body)});

function toast(msg, type = "success") {
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${type} border-0`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${esc(msg)}</div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  $("#toasts").append(el);
  new bootstrap.Toast(el, {delay: 5000}).show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}
const fail = e => toast(e.message || String(e), "danger");

const Cart = {
  get() { try { return JSON.parse(localStorage.getItem("cart") || "{}"); } catch (e) { return {}; } },
  set(c) { localStorage.setItem("cart", JSON.stringify(c)); Cart.badge(); },
  add(p) { const c = Cart.get(); const l = c[p.id] || {id: p.id, name: p.name, price: p.price, qty: 0, max: p.quantity}; l.qty = Math.min(l.qty + 1, p.quantity); l.max = p.quantity; c[p.id] = l; Cart.set(c); toast(`${p.name} added to cart`); },
  badge() { const n = Object.values(Cart.get()).reduce((a, l) => a + l.qty, 0); const b = $("#cartBadge"); if (b) b.textContent = n; }
};

function renderNav(active) {
  const links = [["index.html", "Shop"], ["products.html", "Manage Products"], ["admin.html", "Orders"], ["storage-dashboard.html", "Azure Storage"]];
  $("#nav").innerHTML = `<nav class="navbar navbar-expand-lg navbar-dark" style="background:var(--az-dark)"><div class="container">
    <a class="navbar-brand fw-bold" href="index.html"><i class="bi bi-cloud-check-fill"></i> AzureKart</a>
    <button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#nv"><span class="navbar-toggler-icon"></span></button>
    <div id="nv" class="collapse navbar-collapse"><ul class="navbar-nav me-auto">
    ${links.map(([h, t]) => `<li class="nav-item"><a class="nav-link ${h === active ? "active" : ""}" href="${h}">${t}</a></li>`).join("")}</ul>
    <a class="btn btn-outline-light" href="index.html?cart=1"><i class="bi bi-cart3"></i> Cart <span id="cartBadge" class="badge bg-warning text-dark">0</span></a></div></div></nav>`;
  Cart.badge();
}
