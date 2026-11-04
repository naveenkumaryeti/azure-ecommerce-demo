// Shop (index.html), product management (products.html) and order history (admin.html)
const page = document.body.dataset.page;
let PRODUCTS = [];

async function loadProducts() { PRODUCTS = await api("/products"); }

/* ---------- SHOP ---------- */
function renderShop() {
  const q = ($("#q").value || "").toLowerCase();
  const list = PRODUCTS.filter(p => (p.name + p.category + p.description).toLowerCase().includes(q));
  $("#grid").innerHTML = list.length ? list.map(p => `<div class="col-6 col-md-4 col-lg-3"><div class="card pcard">
    <img src="${imgUrl(p)}" alt="${esc(p.name)}" loading="lazy"><div class="card-body d-flex flex-column">
    <span class="badge bg-info text-dark align-self-start mb-1">${esc(p.category)}</span>
    <h6 class="card-title">${esc(p.name)}</h6><p class="small text-muted flex-grow-1">${esc(p.description)}</p>
    <div class="d-flex justify-content-between align-items-center"><span class="price">${money(p.price)}</span>
    <small class="${p.quantity ? "text-success" : "text-danger"}">${p.quantity ? p.quantity + " in stock" : "Out of stock"}</small></div>
    <button class="btn btn-primary btn-sm mt-2" ${p.quantity ? "" : "disabled"} onclick='Cart.add(PRODUCTS.find(x=>x.id==="${p.id}"))'><i class="bi bi-cart-plus"></i> Add to cart</button>
    </div></div></div>`).join("") : `<p class="text-center text-muted py-5">No products yet - add some under <a href="products.html">Manage Products</a>.</p>`;
}

function renderCart() {
  const lines = Object.values(Cart.get());
  const total = lines.reduce((a, l) => a + l.price * l.qty, 0);
  $("#cartBody").innerHTML = lines.length ? lines.map(l => `<div class="d-flex justify-content-between align-items-center border-bottom py-2">
    <div><b>${esc(l.name)}</b><br><small>${money(l.price)} each</small></div>
    <div class="input-group input-group-sm" style="width:110px"><button class="btn btn-outline-secondary" onclick="chg('${l.id}',-1)">-</button>
    <span class="form-control text-center">${l.qty}</span><button class="btn btn-outline-secondary" onclick="chg('${l.id}',1)">+</button></div></div>`).join("")
    + `<h5 class="mt-3">Total: ${money(total)}</h5>` : "<p class='text-muted'>Your cart is empty.</p>";
  $("#checkoutForm").classList.toggle("d-none", !lines.length);
}
function chg(id, d) { const c = Cart.get(); const l = c[id]; l.qty = Math.max(0, Math.min(l.max, l.qty + d)); if (!l.qty) delete c[id]; Cart.set(c); renderCart(); }

async function checkout(e) {
  e.preventDefault();
  const f = e.target, items = Object.values(Cart.get()).map(l => ({id: l.id, quantity: l.qty}));
  try {
    const o = await api("/orders", jsonOpts("POST", {items, customer: {name: f.cname.value, email: f.email.value, address: f.address.value}}));
    Cart.set({}); renderCart(); f.reset(); toast(`Order ${o.id} placed! Stored as orders/${o.id}.json`);
    await loadProducts(); renderShop();
  } catch (err) { fail(err); }
}

/* ---------- MANAGE ---------- */
function renderManage() {
  $("#ptable").innerHTML = PRODUCTS.map(p => `<tr><td><img class="thumb" src="${imgUrl(p)}"></td>
    <td class="mono">${p.id}</td><td>${esc(p.name)}</td><td>${esc(p.category)}</td><td>${money(p.price)}</td><td>${p.quantity}</td>
    <td class="text-end"><button class="btn btn-sm btn-outline-primary" onclick="openForm('${p.id}')"><i class="bi bi-pencil"></i> Edit</button>
    <button class="btn btn-sm btn-outline-danger" onclick="delProduct('${p.id}')"><i class="bi bi-trash"></i> Delete</button></td></tr>`).join("")
    || `<tr><td colspan="7" class="text-center text-muted py-4">No products. Click “Add Product”.</td></tr>`;
}
let modal;
function openForm(id) {
  const f = $("#pform"); f.reset(); const p = PRODUCTS.find(x => x.id === id);
  $("#mtitle").textContent = p ? "Edit product" : "Add product";
  f.pid.value = p ? p.id : ""; f.etag.value = p ? p.etag : "";
  if (p) { f.name.value = p.name; f.category.value = p.category; f.price.value = p.price; f.quantity.value = p.quantity; f.description.value = p.description; }
  $("#preview").src = p ? imgUrl(p) : NOIMG;
  (modal = modal || new bootstrap.Modal($("#pmodal"))).show();
}
async function saveProduct(e) {
  e.preventDefault(); const f = e.target, btn = $("#saveBtn"); btn.disabled = true;
  const body = {name: f.name.value, category: f.category.value, price: f.price.value, quantity: f.quantity.value, description: f.description.value};
  try {
    const p = f.pid.value ? await api(`/products/${f.pid.value}`, jsonOpts("PUT", body, {"If-Match": f.etag.value})) : await api("/products", jsonOpts("POST", body));
    if (f.image.files[0]) { const fd = new FormData(); fd.append("image", f.image.files[0]); await api(`/products/${p.id}/image`, {method: "POST", body: fd}); }
    modal.hide(); toast(`Saved to Blob Storage: products/${p.id}.json`);
    await loadProducts(); renderManage();
  } catch (err) { fail(err); } finally { btn.disabled = false; }
}
async function delProduct(id) {
  if (!confirm(`Delete ${id}? Its JSON blob and image blob will be removed.`)) return;
  try { await api(`/products/${id}`, {method: "DELETE", headers: {"If-Match": PRODUCTS.find(p => p.id === id).etag}}); toast(`Deleted products/${id}.json`); await loadProducts(); renderManage(); }
  catch (err) { fail(err); }
}

/* ---------- ORDERS ---------- */
async function renderOrders() {
  const orders = await api("/orders");
  $("#otable").innerHTML = orders.map(o => `<tr><td class="mono">${o.id}</td><td>${new Date(o.created_at).toLocaleString()}</td>
    <td>${esc(o.customer.name)}<br><small class="text-muted">${esc(o.customer.email)}</small></td>
    <td>${o.items.map(i => `${esc(i.name)} × ${i.quantity}`).join("<br>")}</td><td><b>${money(o.total)}</b></td>
    <td><span class="badge bg-success">${o.status}</span></td></tr>`).join("") || `<tr><td colspan="6" class="text-center text-muted py-4">No orders yet.</td></tr>`;
}

/* ---------- init ---------- */
document.addEventListener("DOMContentLoaded", async () => {
  try {
    if (page === "shop") {
      renderNav("index.html"); await loadProducts(); renderShop(); renderCart();
      $("#q").addEventListener("input", renderShop); $("#checkoutForm").addEventListener("submit", checkout);
      if (location.search.includes("cart=1")) new bootstrap.Offcanvas($("#cart")).show();
      $("#cart").addEventListener("show.bs.offcanvas", renderCart);
    } else if (page === "manage") {
      renderNav("products.html"); await loadProducts(); renderManage();
      $("#pform").addEventListener("submit", saveProduct);
      $("#pform").image.addEventListener("change", ev => { const f = ev.target.files[0]; if (f) $("#preview").src = URL.createObjectURL(f); });
    } else if (page === "orders") { renderNav("admin.html"); await renderOrders(); }
  } catch (err) { renderNav(); fail(err); }
});
