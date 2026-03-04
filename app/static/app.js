// ----- Gestion impersonate via URL -----
const urlParams = new URLSearchParams(window.location.search);
const impersonateToken = urlParams.get("impersonate");

if (impersonateToken) {
    localStorage.setItem("token", impersonateToken);

    // Nettoie l'URL
    window.history.replaceState({}, document.title, "/static/index.html");

    // Recharge complètement sans cache
    window.location.href = "/static/index.html?reload=" + Date.now();
}

// app/static/app.js
// HaitiWallet — app.js (clean + complet) ✅
// Fix: doublons (renderBalances), IDs register/login, API undefined, admin tab pour admin+superadmin,
// Superadmin UI cohérente, wiring centralisé, register via /auth/register.
let token = localStorage.getItem("token") || "";

if (!token && !window.location.pathname.includes("index.html")) {
  window.location.href = "/static/index.html";
}
let superadminToken = localStorage.getItem("superadmin_token") || "";
let me = null;
let fx = { sell_usd: 134.0, buy_usd: 126.0 };

const $ = (id) => document.getElementById(id);

/**
 * Coordonnées “où envoyer l’argent” (à adapter)
 */
const PAY_COORDS = {
  moncash: {
    label: "MonCash",
    to: "+509 48 07 1798 (MonCash Haiti Wallet)",
    how: "Envoie via MonCash à ce numéro. Garde le reçu / code de transaction et mets-le dans la Référence.",
  },
  natcash: {
    label: "NatCash",
    to: "+509 35 95 8772 (NatCash Haiti Wallet)",
    how: "Envoie via NatCash à ce numéro. Garde le reçu / code et mets-le dans la Référence.",
  },
  interac: {
    label: "Interac",
    to: "438 454 8899",
    how: "Envoie un virement Interac à ce numéro. Mets la référence (numéro/ID) dans la Référence.",
  },
};

/* ---------------------------
   Export CSV
--------------------------- */
let lastWalletTx = [];
let lastMyTopups = [];
let lastAdminPendingTopups = [];

function csvEscape(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function toCsv(rows, headers) {
  const head = headers.map((h) => csvEscape(h.label)).join(",");
  const body = rows
    .map((r) => headers.map((h) => csvEscape(r[h.key])).join(","))
    .join("\n");
  return head + "\n" + body + "\n";
}

function downloadTextFile(filename, text, mime = "text/csv;charset=utf-8") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 800);
}

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(
    d.getHours()
  )}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function exportWalletTxCsv() {
  const msgEl = $("histExportMsg");
  hideMsg(msgEl);

  if (!lastWalletTx || lastWalletTx.length === 0) {
    showMsg(msgEl, false, "Rien à exporter (aucune transaction chargée).");
    return;
  }

  const rows = lastWalletTx.map((t) => ({
    id: t.id ?? "",
    created_at: t.created_at ? safeDate(t.created_at) : "",
    type: t.type ?? "",
    currency: t.currency ?? "",
    amount: t.amount ?? "",
    note: t.note ?? "",
  }));

  const csv = toCsv(rows, [
    { key: "id", label: "ID" },
    { key: "created_at", label: "Date" },
    { key: "type", label: "Type" },
    { key: "currency", label: "Devise" },
    { key: "amount", label: "Montant" },
    { key: "note", label: "Détails" },
  ]);

  downloadTextFile(`wallet_transactions_${nowStamp()}.csv`, csv);
  showMsg(msgEl, true, `Export OK (${rows.length} lignes).`);
  setTimeout(() => hideMsg(msgEl), 1500);
}

function exportMyTopupsCsv() {
  const msgEl = $("topupsExportMsg");
  hideMsg(msgEl);

  if (!lastMyTopups || lastMyTopups.length === 0) {
    showMsg(msgEl, false, "Rien à exporter (aucune demande chargée).");
    return;
  }

  const rows = lastMyTopups.map((t) => ({
    id: t.id ?? "",
    status: (t.status ?? "").toUpperCase(),
    amount: t.amount ?? "",
    currency: t.currency ?? "",
    method: t.method ?? "",
    reference: t.reference ?? "",
    proof_url: t.proof_url ?? "",
    note: t.note ?? "",
    admin_note: t.admin_note ?? "",
    created_at: t.created_at ? safeDate(t.created_at) : "",
    decided_at: t.decided_at ? safeDate(t.decided_at) : "",
  }));

  const csv = toCsv(rows, [
    { key: "id", label: "ID" },
    { key: "status", label: "Statut" },
    { key: "amount", label: "Montant" },
    { key: "currency", label: "Devise" },
    { key: "method", label: "Méthode" },
    { key: "reference", label: "Référence" },
    { key: "proof_url", label: "Preuve URL" },
    { key: "note", label: "Note user" },
    { key: "admin_note", label: "Note admin" },
    { key: "created_at", label: "Créé" },
    { key: "decided_at", label: "Décidé" },
  ]);

  downloadTextFile(`topup_requests_mine_${nowStamp()}.csv`, csv);
  showMsg(msgEl, true, `Export OK (${rows.length} lignes).`);
  setTimeout(() => hideMsg(msgEl), 1500);
}

function exportAdminPendingCsv() {
  const msgEl = $("adminExportMsg");
  hideMsg(msgEl);

  if (!lastAdminPendingTopups || lastAdminPendingTopups.length === 0) {
    showMsg(msgEl, false, "Rien à exporter (aucune demande en attente chargée).");
    return;
  }

  const rows = lastAdminPendingTopups.map((t) => ({
    id: t.id ?? "",
    user_email: t.user_email ?? "",
    status: (t.status ?? "").toUpperCase(),
    amount: t.amount ?? "",
    currency: t.currency ?? "",
    method: t.method ?? "",
    reference: t.reference ?? "",
    proof_url: t.proof_url ?? "",
    note: t.note ?? "",
    created_at: t.created_at ? safeDate(t.created_at) : "",
  }));

  const csv = toCsv(rows, [
    { key: "id", label: "ID" },
    { key: "user_email", label: "User" },
    { key: "status", label: "Statut" },
    { key: "amount", label: "Montant" },
    { key: "currency", label: "Devise" },
    { key: "method", label: "Méthode" },
    { key: "reference", label: "Référence" },
    { key: "proof_url", label: "Preuve URL" },
    { key: "note", label: "Note user" },
    { key: "created_at", label: "Créé" },
  ]);

  downloadTextFile(`topup_pending_admin_${nowStamp()}.csv`, csv);
  showMsg(msgEl, true, `Export OK (${rows.length} lignes).`);
  setTimeout(() => hideMsg(msgEl), 1500);
}

/* ---------------------------
   UI helpers
--------------------------- */
function showMsg(el, ok, text) {
  if (!el) return;
  el.className = ok ? "ok" : "err";
  el.textContent = text;
  el.classList.remove("hide");
}

function hideMsg(el) {
  if (!el) return;
  el.classList.add("hide");
  el.textContent = "";
}

async function api(path, opts = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(opts.headers || {})
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return fetch(path, {
    ...opts,
    headers
  });
}

/* ---------------------------
   TABS
--------------------------- */
const TABS = ["dashboard", "topup", "transfer", "history", "partners", "info", "admin"];

function setActiveTabButton(name) {
  for (const t of TABS) {
    const b = $(`tabBtn-${t}`);
    if (!b) continue;
    b.classList.toggle("active", t === name);
  }
}

function showTab(name) {

    if (!TABS.includes(name)) {
        name = "dashboard";
    }

    let foundVisible = false;

    for (const t of TABS) {
        const el = document.getElementById(`tab-${t}`);
        if (!el) continue;

        const shouldHide = t !== name;
        el.classList.toggle("hide", shouldHide);

        if (!shouldHide) {
            foundVisible = true;
        }
    }

    // sécurité ultime : si rien n'est visible, force dashboard
    if (!foundVisible) {
        const dash = document.getElementById("tab-dashboard");
        if (dash) dash.classList.remove("hide");
    }

    setActiveTabButton(name);
    location.hash = `#${name}`;
}


function tabFromHash() {
  const h = (location.hash || "").replace("#", "").trim();
  return TABS.includes(h) ? h : "dashboard";
}

/* ---------------------------
   AUTH
--------------------------- */
async function login(email, password) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j.detail || "Login failed");
  }
  const j = await res.json();
  token = j.access_token;

  localStorage.setItem("token", token);
  await refreshAll();
document.getElementById("loginBox").classList.add("hide");
document.getElementById("appBox").classList.remove("hide");

if (j.user?.role === "superadmin") {
    localStorage.setItem("superadmin_token", token);
    superadminToken = token;
  }

  updateProfileVisibility();

}

async function registerUser(first_name, last_name, email, password, ref) {

  const res = await fetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      first_name: first_name,
      last_name: last_name,
      email: email,
      password: password,
      ref: (ref || "").trim()
    })
  });

  const data = await res.json().catch(()=>({}));

  if (!res.ok) {
    throw new Error(data.detail || "Erreur inscription");
  }

  return data;
}

async function loadMe() {
  const res = await api("/auth/me");
  if (!res.ok) throw new Error("Non authentifié");
  me = await res.json();
}

async function loadFxPublicHint() {
  try {
    const res = await api("/admin/fx");
    if (res.ok) fx = await res.json();
  } catch {}
}

/* ---------------------------
   RENDER / HELPERS
--------------------------- */
function safeDate(v) {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d) ? "—" : d.toLocaleString();
}

function pill(status) {
  const s = (status || "").toUpperCase();
  if (s === "APPROVED") return `<span class="pill pillApproved">APPROVED</span>`;
  if (s === "REJECTED") return `<span class="pill pillRejected">REJECTED</span>`;
  return `<span class="pill pillPending">PENDING</span>`;
}

function renderBalances() {
  const htg = Number(me?.wallet?.htg || 0);
  const usdReal = Number(me?.wallet?.usd || 0);

  $("balHtg") && ($("balHtg").textContent = htg.toFixed(2));
  $("balUsdReal") && ($("balUsdReal").textContent = usdReal.toFixed(2));

  const usdEq = fx.sell_usd > 0 ? htg / fx.sell_usd : 0;
  $("balUsdEq") && ($("balUsdEq").textContent = `≈ ${usdEq.toFixed(2)}`);

  $("rateHint") &&
    ($("rateHint").textContent = `1 USD ≈ ${fx.sell_usd.toFixed(2)} HTG (vente) | ${fx.buy_usd.toFixed(
      2
    )} HTG (achat)`);

  $("who") && ($("who").textContent = `${me.email} (${me.role})`);
  $("badge")?.classList.remove("hide");

  const isAdminOrSuper = me?.role === "admin" || me?.role === "superadmin";
  $("tabBtn-admin")?.classList.toggle("hide", !isAdminOrSuper);
  $("partnersAdminBox")?.classList.toggle("hide", !isAdminOrSuper);

  const isSuper = me?.role === "superadmin";
  $("superadminCard")?.classList.toggle("hide", !isSuper);
  if (isSuper) loadUsersSuperadmin();

  // code parrainage
  if ($("myRefCode")) $("myRefCode").textContent = me.ref_code || "—";
}

/* ---------------------------
   Payment instructions UI
--------------------------- */
function renderPaymentInstructions(method) {
  const m = (method || "interac").toLowerCase();
  const cfg = PAY_COORDS[m] || PAY_COORDS.interac;

  $("payMethodLabel") && ($("payMethodLabel").textContent = cfg.label);
  $("payTo") && ($("payTo").textContent = cfg.to);
  $("payHow") && ($("payHow").textContent = cfg.how);
}

async function copyPayToClipboard() {
  const text = $("payTo")?.textContent || "";
  try {
    await navigator.clipboard.writeText(text);
    const msgEl = $("topMsg");
    showMsg(msgEl, true, "Copié.");
    setTimeout(() => hideMsg(msgEl), 1200);
  } catch {
    const msgEl = $("topMsg");
    showMsg(msgEl, false, "Copie impossible (navigateur).");
  }
}

/* ---------------------------
   WALLET: HISTORY
--------------------------- */
async function loadHistory() {
  const res = await api("/wallet/transactions");
  const body = $("histBody");
  if (!body) return;

  body.innerHTML = "";

  if (!res.ok) {
    body.innerHTML = `<tr><td colspan="5">Erreur chargement</td></tr>`;
    $("histHint") && ($("histHint").textContent = "");
    lastWalletTx = [];
    return;
  }

  const j = await res.json();
  const items = Array.isArray(j) ? j : j.items || [];
  lastWalletTx = items;

  $("histHint") && ($("histHint").textContent = `${items.length} transaction(s) chargée(s)`);

  if (items.length === 0) {
    body.innerHTML = `<tr><td colspan="5" class="muted">Aucune transaction</td></tr>`;
    return;
  }

  for (const t of items.slice(0, 50)) {
    body.innerHTML += `
      <tr>
        <td>${safeDate(t.created_at)}</td>
        <td>${t.type}</td>
        <td>${t.currency}</td>
        <td>${Number(t.amount).toFixed(2)}</td>
        <td>${t.note || ""}</td>
      </tr>
    `;
  }
}

/* ---------------------------
   WALLET: TRANSFER
--------------------------- */
async function sendTransfer() {
  const msgEl = $("txMsg");
  hideMsg(msgEl);

  const res = await api("/wallet/transfer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      to_email: $("toEmail")?.value.trim(),
      currency: $("txCurrency")?.value,
      amount: Number($("txAmount")?.value || 0),
      note: $("txNote")?.value || "",
    }),
  });

  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    showMsg(msgEl, false, j.detail || "Erreur transfert");
    return;
  }

  showMsg(msgEl, true, "Transfert effectué.");
  await refreshAll();
  showTab("history");
}

/* ---------------------------
   WALLET: CONVERT
--------------------------- */
async function convert() {
  const amount = Number($("convAmount")?.value || 0);
  const direction = $("convDirection")?.value;
  const msgEl = $("convMsg");
  hideMsg(msgEl);

  if (amount <= 0) {
    showMsg(msgEl, false, "Montant invalide");
    return;
  }

  const res = await api("/wallet/convert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ direction, amount }),
  });

  const j = await res.json().catch(() => ({}));
  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Conversion échouée");
    return;
  }

  const label = direction === "usd_to_htg" ? "USD → HTG" : "HTG → USD";
  showMsg(
    msgEl,
    true,
    `${label} : ${Number(j.amount_in).toFixed(2)} → ${Number(j.amount_out).toFixed(2)} (taux ${j.rate})`
  );

  $("convAmount") && ($("convAmount").value = "");
  await refreshAll();
}

/* ---------------------------
   TOPUPS: USER REQUEST
--------------------------- */
async function createTopupRequest() {
  const msgEl = $("topMsg");
  hideMsg(msgEl);

  const payload = {
    amount: Number($("topAmount")?.value || 0),
    currency: $("topCurrency")?.value,
    method: $("topMethod")?.value,
    reference: $("topReference")?.value.trim(),
    proof_url: ($("topProof")?.value || "").trim() || null,
    note: ($("topNote")?.value || "").trim() || null,
  };

  if (!payload.amount || payload.amount <= 0) {
    showMsg(msgEl, false, "Montant invalide");
    return;
  }
  if (!payload.reference || payload.reference.length < 3) {
    showMsg(msgEl, false, "Référence obligatoire (min 3 caractères)");
    return;
  }

  const res = await api("/topups/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const j = await res.json().catch(() => ({}));
  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Demande échouée");
    return;
  }

  showMsg(msgEl, true, `Demande envoyée (#${j.id}) — statut ${j.status}`);

  $("topAmount") && ($("topAmount").value = "");
  $("topReference") && ($("topReference").value = "");
  $("topProof") && ($("topProof").value = "");
  $("topNote") && ($("topNote").value = "");

  await loadMyTopups();
}

/* ---------------------------
   TOPUPS: MY REQUESTS
--------------------------- */
async function loadMyTopups() {
  const pendingBody = $("myTopupsPendingBody");
  const historyBody = $("myTopupsHistoryBody");
  const msgEl = $("myTopupsMsg");
  if (!pendingBody || !historyBody) return;

  hideMsg(msgEl);
  pendingBody.innerHTML = "";
  historyBody.innerHTML = "";

  const res = await api("/topups/mine");
  const j = await res.json().catch(() => ({}));

  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Impossible de charger tes demandes");
    pendingBody.innerHTML = `<tr><td colspan="7" class="muted">Erreur chargement</td></tr>`;
    historyBody.innerHTML = `<tr><td colspan="9" class="muted">Erreur chargement</td></tr>`;
    lastMyTopups = [];
    return;
  }

  const items = Array.isArray(j) ? j : j.items || [];
  lastMyTopups = items;

  const pending = items.filter((x) => (x.status || "").toUpperCase() === "PENDING");
  const decided = items.filter((x) => (x.status || "").toUpperCase() !== "PENDING");

  if (pending.length === 0) {
    pendingBody.innerHTML = `<tr><td colspan="7" class="muted">Aucune demande en attente</td></tr>`;
  } else {
    for (const t of pending.slice(0, 50)) {
      pendingBody.innerHTML += `
        <tr>
          <td>${t.id}</td>
          <td>${Number(t.amount).toFixed(2)}</td>
          <td>${t.currency}</td>
          <td>${t.method}</td>
          <td>${t.reference}</td>
          <td>${safeDate(t.created_at)}</td>
          <td>${pill(t.status)}</td>
        </tr>
      `;
    }
  }

  if (decided.length === 0) {
    historyBody.innerHTML = `<tr><td colspan="9" class="muted">Aucun historique</td></tr>`;
  } else {
    decided.sort((a, b) => {
      const da = new Date(a.decided_at || a.created_at || 0).getTime();
      const db = new Date(b.decided_at || b.created_at || 0).getTime();
      return db - da;
    });

    for (const t of decided.slice(0, 50)) {
      historyBody.innerHTML += `
        <tr>
          <td>${t.id}</td>
          <td>${Number(t.amount).toFixed(2)}</td>
          <td>${t.currency}</td>
          <td>${t.method}</td>
          <td>${t.reference}</td>
          <td>${safeDate(t.created_at)}</td>
          <td>${safeDate(t.decided_at)}</td>
          <td>${pill(t.status)}</td>
          <td>${t.admin_note || ""}</td>
        </tr>
      `;
    }
  }
}

/* ---------------------------
   TOPUPS: ADMIN PENDING
--------------------------- */
async function loadPendingTopups() {
  const body = $("adminTopupsBody");
  const msgEl = $("adminTopupsMsg");
  if (!body) return;

  hideMsg(msgEl);
  body.innerHTML = "";

  const res = await api("/topups/pending");
  const j = await res.json().catch(() => ({}));

  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Impossible de charger les demandes");
    body.innerHTML = `<tr><td colspan="9" class="muted">Erreur chargement</td></tr>`;
    lastAdminPendingTopups = [];
    return;
  }

  const items = Array.isArray(j) ? j : j.items || [];
  lastAdminPendingTopups = items;

  if (items.length === 0) {
    body.innerHTML = `<tr><td colspan="9" class="muted">Aucune demande en attente</td></tr>`;
    updateStatsBoxFromLoaded();
    return;
  }

  for (const t of items) {
    const fee =
      t.fee_amount !== undefined && t.fee_amount !== null
        ? Number(t.fee_amount)
        : computeFee(Number(t.amount || 0));

    const net = Math.max(0, Number(t.amount || 0) - fee);

    body.innerHTML += `
      <tr>
        <td>${t.id}</td>
        <td>${t.user_email}</td>
        <td>
          ${Number(t.amount).toFixed(2)}
          <div class="muted">Frais: <b>${fee.toFixed(2)}</b> | Net: <b>${net.toFixed(2)}</b></div>
        </td>
        <td>${t.currency}</td>
        <td>${t.method}</td>
        <td>${t.reference}</td>
        <td>${safeDate(t.created_at)}</td>
        <td>${pill(t.status)}</td>
        <td>
          <div class="inline" style="gap:8px">
            <button class="btnSmall btnOk" data-act="approve" data-id="${t.id}">Approuver</button>
            <button class="btnSmall btnNo" data-act="reject" data-id="${t.id}">Refuser</button>
          </div>
        </td>
      </tr>
    `;
  }

  body.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.onclick = async () => {
      const id = Number(btn.getAttribute("data-id"));
      const act = btn.getAttribute("data-act");
      const status = act === "approve" ? "APPROVED" : "REJECTED";
      const note = ($("adminNote")?.value || "").trim() || null;
      await decideTopup(id, status, note);
    };
  });

  updateStatsBoxFromLoaded();
}

async function decideTopup(reqId, status, adminNote) {
  const msgEl = $("adminTopupsMsg");
  hideMsg(msgEl);

  const res = await api(`/topups/${reqId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, admin_note: adminNote }),
  });

  const j = await res.json().catch(() => ({}));
  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Action échouée");
    return;
  }

  showMsg(msgEl, true, `Demande #${reqId} → ${status}`);
  await loadPendingTopups();
  await loadMyTopups();
  await refreshAll();
}

/* ---------------------------
   PARTNERS (public + admin)
--------------------------- */
async function loadPartners() {
  const body = $("partnersBody");
  const msgEl = $("partnersMsg");
  hideMsg(msgEl);
  if (!body) return;

  body.innerHTML = `<tr><td colspan="4" class="muted">Chargement...</td></tr>`;

  const res = await api("/partners");
  const j = await res.json().catch(() => ({}));

  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Erreur chargement partenaires");
    body.innerHTML = `<tr><td colspan="4" class="muted">Erreur</td></tr>`;
    return;
  }

  const items = Array.isArray(j) ? j : j.items || [];
  if (items.length === 0) {
    body.innerHTML = `<tr><td colspan="4" class="muted">Aucun partenaire</td></tr>`;
    return;
  }

  body.innerHTML = "";
  for (const p of items) {
    if (p.active !== undefined && !p.active) continue;
    body.innerHTML += `
      <tr>
        <td><b>${p.name || "Partenaire"}</b></td>
        <td>${p.category || "autre"}</td>
        <td>${p.description || ""}</td>
        <td>${p.url ? `<a href="${p.url}" target="_blank" rel="noopener noreferrer">${p.url}</a>` : "—"}</td>
      </tr>
    `;
  }

  if (body.innerHTML.trim() === "") {
    body.innerHTML = `<tr><td colspan="4" class="muted">Aucun partenaire actif</td></tr>`;
  }
}

async function loadPartnersAdmin() {
  const body = $("partnersAdminBody");
  if (!body) return;

  body.innerHTML = `<tr><td colspan="6" class="muted">Chargement...</td></tr>`;

  const res = await api("/partners/admin");
  const j = await res.json().catch(() => ({}));

  if (!res.ok) {
    body.innerHTML = `<tr><td colspan="6" class="muted">Admin seulement ou erreur</td></tr>`;
    return;
  }

  const items = Array.isArray(j) ? j : j.items || [];
  if (items.length === 0) {
    body.innerHTML = `<tr><td colspan="6" class="muted">Aucun</td></tr>`;
    return;
  }

  body.innerHTML = "";
  for (const p of items) {
    body.innerHTML += `
      <tr>
        <td>${p.id}</td>
        <td>${p.name}</td>
        <td>${p.category || "autre"}</td>
        <td>${p.active ? "✅" : "❌"}</td>
        <td>${p.url ? `<a href="${p.url}" target="_blank" rel="noopener noreferrer">ouvrir</a>` : "—"}</td>
        <td>
          <button class="btnSmall ${p.active ? "btnNo" : "btnOk"}" data-pid="${p.id}" data-act="${p.active ? "off" : "on"}">
            ${p.active ? "Désactiver" : "Activer"}
          </button>
        </td>
      </tr>
    `;
  }

  body.querySelectorAll("button[data-pid]").forEach((btn) => {
    btn.onclick = async () => {
      const id = Number(btn.getAttribute("data-pid"));
      const act = btn.getAttribute("data-act");
      await setPartnerActive(id, act === "on");
    };
  });
}

async function setPartnerActive(id, active) {
  const msgEl = $("partnerAddMsg");
  hideMsg(msgEl);

  const res = await api(`/partners/${id}/active?active=${active}`, { method: "POST" });
  const j = await res.json().catch(() => ({}));

  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Action échouée");
    return;
  }

  showMsg(msgEl, true, `Partenaire #${id} → ${active ? "actif" : "inactif"}`);
  await loadPartners();
  await loadPartnersAdmin();
}

async function addPartner() {
  const msgEl = $("partnerAddMsg");
  hideMsg(msgEl);

  const payload = {
    name: $("pName")?.value.trim(),
    category: ($("pCategory")?.value || "autre").trim(),
    url: $("pUrl")?.value.trim(),
    logo_url: ($("pLogo")?.value || "").trim() || null,
    description: ($("pDesc")?.value || "").trim() || null,
    active: true,
  };

  if (!payload.name || payload.name.length < 2) return showMsg(msgEl, false, "Nom invalide");
  if (!payload.url || !payload.url.startsWith("http")) return showMsg(msgEl, false, "URL invalide (http/https)");

  const res = await api("/partners", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const j = await res.json().catch(() => ({}));
  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Ajout échoué");
    return;
  }

  showMsg(msgEl, true, `Ajouté: ${j.name} (#${j.id})`);

  $("pName") && ($("pName").value = "");
  $("pCategory") && ($("pCategory").value = "");
  $("pUrl") && ($("pUrl").value = "");
  $("pLogo") && ($("pLogo").value = "");
  $("pDesc") && ($("pDesc").value = "");

  await loadPartners();
  if (me?.role === "admin" || me?.role === "superadmin") await loadPartnersAdmin();
}

/* ---------------------------
   REFRESH ALL
--------------------------- */
async function refreshAll() {
  await loadMe();
  await loadFxPublicHint();
  renderBalances();

  await loadHistory();
  await loadMyTopups();

  await loadPartners();
  if (me?.role === "admin" || me?.role === "superadmin") {
    await loadPartnersAdmin();
    await loadPendingTopups();
  }

  ensureInjectedUI();
  wireMenusSafe();
}

/* =========================================================
   AJOUTS — Frais + (Dépenser sans payer) + Stats + Admin Debit/Credit + Superadmin
========================================================= */

// barème fixe
function computeFee(amount) {
  const a = Number(amount || 0);
  if (a <= 0) return 0;
  if (a <= 20) return 1.5;
  if (a <= 50) return 3.0;
  if (a <= 70) return 5.0;
  return 7.5;
}

function feeLabel(currency, amount) {
  const fee = computeFee(amount);
  const cur = (currency || "").toLowerCase() === "usd" ? "USD" : "HTG";
  return `${fee.toFixed(2)} ${cur}`;
}

function injectFeesBox() {
  const tabTopup = $("tab-topup");
  if (!tabTopup) return;
  if ($("feesBox")) return;

  const box = document.createElement("div");
  box.id = "feesBox";
  box.className = "card section";
  box.innerHTML = `
    <h3 style="margin:0 0 10px">Frais Haiti Wallet</h3>
    <div class="muted" style="margin-bottom:10px">
      Zéro surprise: tu vois les frais avant d’envoyer. Frais à l’entrée, jamais à la sortie.
    </div>
    <div class="info">
      <div style="font-weight:900;margin-bottom:6px">Barème (USD et HTG)</div>
      <div class="muted">
        0–20 → <b>1.50</b><br/>
        21–50 → <b>3.00</b><br/>
        51–70 → <b>5.00</b><br/>
        71–100+ → <b>7.50</b>
      </div>
      <div style="height:10px"></div>
      <div class="muted">Estimation sur ton montant:</div>
      <div id="feeLive" style="font-weight:900">—</div>
      <div class="muted" style="margin-top:6px">Exemple: 100 → frais 7.50 → net 92.50</div>
    </div>
  `;

  const firstCard = tabTopup.querySelector(".card.section");
  if (firstCard) firstCard.insertAdjacentElement("afterend", box);
  else tabTopup.insertBefore(box, tabTopup.firstChild);

  const amountEl = $("topAmount");
  const curEl = $("topCurrency");
  const feeLive = $("feeLive");

  function updateLiveFee() {
    if (!feeLive) return;
    const amt = Number(amountEl?.value || 0);
    const cur = curEl?.value || "htg";
    feeLive.textContent = !amt || amt <= 0 ? "—" : feeLabel(cur, amt);
  }

  amountEl?.addEventListener("input", updateLiveFee);
  curEl?.addEventListener("change", updateLiveFee);
}

function injectSpendBox() {
  const tabPartners = $("tab-partners");
  if (!tabPartners) return;
  if ($("spendBox")) return;

  const spend = document.createElement("div");
  spend.id = "spendBox";
  spend.className = "card section";
  spend.innerHTML = `
    <h3 style="margin:0 0 10px">Où dépenser tes crédits</h3>
    <div class="muted" style="margin-bottom:10px">
      Clique sur un lien pour explorer le site. Le paiement se fait directement chez le partenaire.
    </div>
  `;

  tabPartners.insertBefore(spend, tabPartners.firstChild);
}

function injectStatsBox() {
  const tabAdmin = $("tab-admin");
  if (!tabAdmin) return;
  if ($("statsCard")) return;

  const card = document.createElement("div");
  card.id = "statsCard";
  card.className = "card section";
  card.innerHTML = `
    <div class="inline" style="justify-content:space-between;align-items:center">
      <h3 style="margin:0">Stats — Revenus (frais)</h3>
      <button id="btnStatsRefresh" class="secondary" style="max-width:180px">Rafraîchir</button>
    </div>
    <div style="height:10px"></div>
    <div id="statsBox" class="muted">—</div>
  `;

  tabAdmin.appendChild(card);
  $("btnStatsRefresh")?.addEventListener("click", updateStatsBoxFromLoaded);
}

function updateStatsBoxFromLoaded() {
  const box = $("statsBox");
  if (!box) return;

  const pending = Array.isArray(lastAdminPendingTopups) ? lastAdminPendingTopups : [];
  const totalFees = pending.reduce((acc, t) => acc + computeFee(Number(t.amount || 0)), 0);

  box.innerHTML = `
    Demandes pending: <b>${pending.length}</b><br/>
    Frais estimés (pending): <b>${totalFees.toFixed(2)}</b><br/>
    <span class="muted">Quand le backend stocke les frais, on affichera le revenu réel.</span>
  `;
}

/* ---------------------------
   ADMIN — Débiter / Créditer un compte (frontend)
   => nécessite backend: POST /admin/wallet/adjust
--------------------------- */
function injectAdminAdjustBox() {
  const tabAdmin = $("tab-admin");
  if (!tabAdmin) return;
  if ($("adminAdjustCard")) return;

  const card = document.createElement("div");
  card.id = "adminAdjustCard";
  card.className = "card section";
  card.innerHTML = `
    <h3 style="margin:0 0 10px">Admin — Débiter / Créditer un compte</h3>
    <div class="muted" style="margin-bottom:10px">
      Montant <b>positif</b> = créditer. Montant <b>négatif</b> = débiter (ex: -100.00).
    </div>
    <div class="inline">
      <input id="adjEmail" placeholder="Email du compte" />
      <select id="adjCurrency" style="max-width:140px">
        <option value="htg">htg</option>
        <option value="usd">usd</option>
      </select>
      <input id="adjAmount" type="number" step="0.01" placeholder="Montant (+/-)" />
    </div>
    <div style="height:10px"></div>
    <input id="adjNote" placeholder="Note (optionnel: payout boutique, correction...)" />
    <div style="height:10px"></div>
    <button id="btnAdminAdjust" class="dark" style="max-width:240px">Appliquer</button>
    <div style="height:10px"></div>
    <div id="adminAdjustMsg" class="hide"></div>
  `;

  tabAdmin.appendChild(card);
  $("btnAdminAdjust")?.addEventListener("click", adminAdjustBalance);
}

async function adminAdjustBalance() {
  const msgEl = $("adminAdjustMsg");
  hideMsg(msgEl);

  const email = ($("adjEmail")?.value || "").trim();
  const currency = $("adjCurrency")?.value || "htg";
  const amount = Number($("adjAmount")?.value || 0);
  const note = ($("adjNote")?.value || "").trim() || null;

  if (!email || email.length < 5) return showMsg(msgEl, false, "Email invalide");
  if (!amount || amount === 0) return showMsg(msgEl, false, "Montant invalide (≠ 0)");

  const res = await api("/admin/wallet/adjust", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, currency, amount, note }),
  });

  const j = await res.json().catch(() => ({}));
  if (!res.ok) {
    showMsg(msgEl, false, j.detail || "Ajustement échoué (backend?)");
    return;
  }

  showMsg(
    msgEl,
    true,
    `OK — Nouveau solde: HTG ${Number(j.new_balance_htg).toFixed(2)} | USD ${Number(
      j.new_balance_usd
    ).toFixed(2)}`
  );

  $("adjAmount") && ($("adjAmount").value = "");
  $("adjNote") && ($("adjNote").value = "");
  await refreshAll();
}

/* ---------------------------
   SUPERADMIN — Gestion des admins
   => nécessite backend:
     GET  /superadmin/users
     POST /superadmin/users/{id}/role   body {role}
--------------------------- */
function injectSuperadminBox() {

  if (me?.role !== "superadmin") return;

  const tabAdmin = $("tab-admin");
  if (!tabAdmin) return;
  if ($("superadminCard")) return;

  const card = document.createElement("div");
  card.id = "superadminCard";
  card.className = "card section hide"; // caché par défaut
  card.innerHTML = `
  <div class="inline" style="justify-content:space-between;align-items:center">
    <h3 style="margin:0">Superadmin — Gestion des utilisateurs</h3>
    <button id="btnSaRefresh" class="secondary" style="max-width:180px">Rafraîchir</button>
  </div>

  <div style="height:10px"></div>

  <!-- 🔎 Recherche -->
  <div class="inline">
    <input id="saSearch" placeholder="🔎 Rechercher par email..." />
  </div>

  <div style="height:10px"></div>
  <div id="saMsg" class="hide"></div>

  <div style="overflow:auto">
    <table class="table" style="min-width:720px">
      <thead>
        <tr>
          <th>ID</th>
          <th>Email</th>
          <th>Rôle</th>
          <th>Statut</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="saUsersBody"></tbody>
    </table>
  </div>

  <div style="height:10px"></div>
  <button id="btnSaMore" class="secondary" style="max-width:180px">Voir plus</button>
`;

  tabAdmin.insertBefore(card, tabAdmin.firstChild);
  $("btnSaRefresh")?.addEventListener("click", loadUsersSuperadmin);
}

/* =========================================================
   SUPERADMIN — VERSION STABLE PROPRE
========================================================= */

const SUPERADMIN_PAGE_SIZE = 5;
let superadminUsers = [];
let superadminPage = 1;
let superadminVisibleCount = 5;

/* ---------- UI Injection ---------- */

function injectSuperadminBox() {
  const tabAdmin = $("tab-admin");
  if (!tabAdmin) return;
  if ($("superadminCard")) return;

  const card = document.createElement("div");
  card.id = "superadminCard";
  card.className = "card section hide";

  card.innerHTML = `
    <div class="inline" style="justify-content:space-between;align-items:center">
      <h3 style="margin:0">Superadmin — Gestion des utilisateurs</h3>
      <button id="btnSaRefresh" class="secondary">Rafraîchir</button>
    </div>

    <div style="height:10px"></div>

    <input id="saSearch" placeholder="🔎 Rechercher par email..." />

    <div style="height:10px"></div>

    <table class="table" style="min-width:720px">
      <thead>
        <tr>
          <th>ID</th>
          <th>Email</th>
          <th>Rôle</th>
          <th>Statut</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="saUsersBody"></tbody>
    </table>

    <div style="height:10px"></div>
    <button id="btnSaMore" class="secondary">Voir plus</button>
  `;

  tabAdmin.insertBefore(card, tabAdmin.firstChild);

  $("btnSaRefresh").onclick = loadUsersSuperadmin;
  $("btnSaMore") && ($("btnSaMore").onclick = () => {
  superadminVisibleCount += SUPERADMIN_PAGE_SIZE;
  renderSuperadminUsers();
});

loadUsersSuperadmin();

  $("saSearch").addEventListener("input", () => {
    superadminPage = 1;
    renderSuperadminUsers();
  });
}

/* ---------- Load Users ---------- */

async function loadUsersSuperadmin() {
  const tbody = $("saUsersBody");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="5">Chargement...</td></tr>`;

  const res = await api("/superadmin/users");

  if (!res.ok) {
    tbody.innerHTML = `<tr><td colspan="5">Erreur</td></tr>`;
    return;
  }

  superadminUsers = await res.json();
  superadminPage = 1;
  superadminVisibleCount = SUPERADMIN_PAGE_SIZE;
  renderSuperadminUsers();
}

/* ---------- Render ---------- */

function renderSuperadminUsers() {
  const tbody = $("saUsersBody");
  if (!tbody) return;

  tbody.innerHTML = "";

const search = $("saSearch")?.value.toLowerCase() || "";

const filtered = superadminUsers.filter(u =>
  u.email.toLowerCase().includes(search)
);

const visible = filtered.slice(0, superadminVisibleCount);

visible.forEach((u, index) => {
  const isSuper = u.role === "superadmin";
    const isAdmin = u.role === "admin";
    const pauseLabel = u.status === "suspended" ? "Ouvrir" : "Pause";

    tbody.innerHTML += `
      <tr>
        <td>${index + 1}</td>
        <td>${u.email}</td>
        <td>${u.role}</td>
        <td>${u.status}</td>
        <td style="position:relative;">
          ${
            isSuper
              ? `<span class="muted">Protégé</span>`
              : `
                <button class="menuBtn" data-menu="${u.id}">⋮</button>
                <div class="userMenu hide" id="menu-${u.id}">
                  <button data-role="${u.id}">
                    ${isAdmin ? "Retirer admin" : "Admin"}
                  </button>
                  <button data-pause="${u.id}">
                    ${pauseLabel}
                  </button>
                  <button data-ban="${u.id}">
                    Ban
                  </button>
                  <button data-delete="${u.id}">
                    Supprimer
                  </button>
                  <button data-impersonate="${u.id}">
                    Login
                  </button>
                </div>
              `
          }
        </td>
      </tr>
    `;
    const btnMore = $("btnSaMore");

if (btnMore) {
  if (superadminVisibleCount >= filtered.length) { 
    btnMore.style.display = "none";
  } else {
    btnMore.style.display = "block";
  }
}
  });

  wireUserMenus();
  wireSuperadminButtons();
}

function wireUserMenus() {
  document.querySelectorAll("[data-menu]").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();

      // Ferme tous les autres menus
      document.querySelectorAll(".userMenu").forEach(m => m.classList.add("hide"));

      const id = btn.getAttribute("data-menu");
      const menu = document.getElementById("menu-" + id);

      menu.classList.toggle("hide");
    };
  });

  // Ferme si on clique ailleurs
  document.addEventListener("click", () => {
    document.querySelectorAll(".userMenu").forEach(m => m.classList.add("hide"));
  });
}

/* ---------- Buttons ---------- */

function wireSuperadminButtons() {

  document.querySelectorAll("[data-role]").forEach(btn => {
    btn.onclick = async () => {
      const uid = btn.getAttribute("data-role");

      const user = superadminUsers.find(u => String(u.id) === uid);
      const newRole = user.role === "admin" ? "user" : "admin";

      await api(`/superadmin/users/${uid}/role`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole })
      });

      await loadUsersSuperadmin();
    };
  });

  document.querySelectorAll("[data-pause]").forEach(btn => {
    btn.onclick = async () => {
      const uid = btn.getAttribute("data-pause");

      const user = superadminUsers.find(u => String(u.id) === uid);
      const newStatus = user.status === "suspended" ? "active" : "suspended";

      await api(`/superadmin/users/${uid}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus })
      });

      await loadUsersSuperadmin();
    };
  });

  document.querySelectorAll("[data-ban]").forEach(btn => {
    btn.onclick = async () => {
      const uid = btn.getAttribute("data-ban");
      if (!confirm("Bannir définitivement ?")) return;

      await api(`/superadmin/users/${uid}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "banned" })
      });

      await loadUsersSuperadmin();
    };
  });

  document.querySelectorAll("[data-delete]").forEach(btn => {
    btn.onclick = async () => {
      const uid = btn.getAttribute("data-delete");
      if (!confirm("Supprimer définitivement ?")) return;

      await api(`/superadmin/users/${uid}`, {
        method: "DELETE"
      });

      await loadUsersSuperadmin();
    };
  });

  document.querySelectorAll("[data-impersonate]").forEach(btn => {
  btn.onclick = async () => {
    const uid = btn.getAttribute("data-impersonate");

    const res = await api(`/superadmin/users/${uid}/impersonate`, {
      method: "POST"
    });

    if (!res.ok) return alert("Erreur impersonate");

    const j = await res.json();

    // OUVRE NOUVEL ONGLET AVEC TOKEN DANS URL
    window.open(`/static/index.html?impersonate=${j.access_token}`, "_blank");
  };
});

  // VIEW POPUP
  document.querySelectorAll("[data-view]").forEach(btn => {
    btn.onclick = async () => {
      const uid = btn.getAttribute("data-view");

      const user = superadminUsersCache.find(u => String(u.id) === uid);

      alert(
`ID: ${user.id}
Email: ${user.email}
Rôle: ${user.role}
Statut: ${user.status}
Téléphone: ${user.phone || "-"}
Créé le: ${user.created_at || "-"}`
      );
    };
  });
}


/* ---------------------------
   Referral copy
--------------------------- */
async function copyRefCode() {
  const code = (me?.ref_code || "").trim();
  const msgEl = $("refMsg");
  hideMsg(msgEl);

  if (!code) return showMsg(msgEl, false, "Code indisponible.");
  try {
    await navigator.clipboard.writeText(code);
    showMsg(msgEl, true, "Code copié ✅");
    setTimeout(() => hideMsg(msgEl), 1200);
  } catch {
    showMsg(msgEl, false, "Copie impossible (navigateur).");
  }
}

/* ---------------------------
   Wiring menus + UI injection
--------------------------- */
function wireMenusSafe() {
  $("tabBtn-dashboard") && ($("tabBtn-dashboard").onclick = () => showTab("dashboard"));
  $("tabBtn-topup") && ($("tabBtn-topup").onclick = () => showTab("topup"));
  $("tabBtn-transfer") && ($("tabBtn-transfer").onclick = () => showTab("transfer"));
  $("tabBtn-history") && ($("tabBtn-history").onclick = () => showTab("history"));
  $("tabBtn-partners") &&
    ($("tabBtn-partners").onclick = async () => {
      showTab("partners");
      await loadPartners();
    });
  $("tabBtn-info") && ($("tabBtn-info").onclick = () => showTab("info"));
  $("tabBtn-admin") && ($("tabBtn-admin").onclick = () => showTab("admin"));
}

function ensureInjectedUI() {
  try {
    injectFeesBox();
    injectSpendBox();
    injectStatsBox();
    injectAdminAdjustBox();
    injectSuperadminBox();
  } catch (e) {
    console.error("UI inject error:", e);
  }
}

function restoreSuperadmin() {
  const saved = localStorage.getItem("superadmin_token");
  if (!saved) return alert("Token superadmin introuvable");

  token = saved;
  localStorage.setItem("token", token);
  refreshAll();
}

document.addEventListener("DOMContentLoaded", async () => {
  const savedToken = localStorage.getItem("token");

  if (!savedToken) {
    $("loginBox")?.classList.remove("hide");
    $("appBox")?.classList.add("hide");
    return;
  }

  try {
    token = savedToken;
    await refreshAll();

    $("loginBox")?.classList.add("hide");
    $("appBox")?.classList.remove("hide");
  } catch (e) {
    localStorage.removeItem("token");
    $("loginBox")?.classList.remove("hide");
    $("appBox")?.classList.add("hide");
  }
});

/* ---------------------------
   EVENTS
--------------------------- */
// Login
$("btnLogin") &&
  ($("btnLogin").onclick = async () => {
    try {
      await login($("email")?.value || "", $("password")?.value || "");

      await refreshAll();


      $("loginBox")?.classList.add("hide");
      $("appBox")?.classList.remove("hide");

      renderPaymentInstructions($("topMethod")?.value);
      showTab(tabFromHash());

      ensureInjectedUI();
      wireMenusSafe();
    } catch (e) {
      showMsg($("loginMsg"), false, e.message);
    }
  });

// Logout
// Logout propre
$("btnLogout") && ($("btnLogout").onclick = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("superadmin_token");
  token = "";
  updateProfileVisibility();
  window.location.href = "/static/index.html";
});

$("logoutAccount") && ($("logoutAccount").onclick = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("superadmin_token");
  token = "";
  updateProfileVisibility();
  window.location.href = "/static/index.html";
});

// Buttons
$("btnCopyRef") && ($("btnCopyRef").onclick = copyRefCode);
$("btnSend") && ($("btnSend").onclick = sendTransfer);
$("btnConvert") && ($("btnConvert").onclick = convert);
$("btnRefresh") && ($("btnRefresh").onclick = refreshAll);

$("btnTopupRequest") && ($("btnTopupRequest").onclick = createTopupRequest);
$("btnMyTopups") && ($("btnMyTopups").onclick = loadMyTopups);
$("btnMyTopups2") && ($("btnMyTopups2").onclick = loadMyTopups);
$("btnAdminRefresh") && ($("btnAdminRefresh").onclick = loadPendingTopups);

$("btnCopyPay") && ($("btnCopyPay").onclick = copyPayToClipboard);

$("btnSaMore") && ($("btnSaMore").onclick = () => {
  superadminVisibleCount += SUPERADMIN_PAGE_SIZE;
  renderSuperadminUsers();
});


// export
$("btnExportTxCsv") && ($("btnExportTxCsv").onclick = exportWalletTxCsv);
$("btnExportMyTopupsCsv") && ($("btnExportMyTopupsCsv").onclick = exportMyTopupsCsv);
$("btnExportAdminTopupsCsv") && ($("btnExportAdminTopupsCsv").onclick = exportAdminPendingCsv);

// partners
$("btnPartnersRefresh") && ($("btnPartnersRefresh").onclick = loadPartners);
$("btnPartnersAdminRefresh") && ($("btnPartnersAdminRefresh").onclick = loadPartnersAdmin);
$("btnPartnerAdd") && ($("btnPartnerAdd").onclick = addPartner);

// Topup method change
$("topMethod") &&
  $("topMethod").addEventListener("change", () => {
    renderPaymentInstructions($("topMethod")?.value);
  });

// Hash change
window.addEventListener("hashchange", () => {
  if (!token) return;
  showTab(tabFromHash());
});

$("btnForgot") && ($("btnForgot").onclick = () => {
  $("forgotBox")?.classList.toggle("hide");
});

$("btnSendResetCode") && ($("btnSendResetCode").onclick = async () => {
  const msgEl = $("forgotMsg");
  hideMsg(msgEl);

  const email = ($("fpEmail")?.value || "").trim();
  if (!email) return showMsg(msgEl, false, "Email requis.");

  const res = await fetch("/auth/password/forgot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  const j = await res.json().catch(() => ({}));
  if (!res.ok) return showMsg(msgEl, false, j.detail || "Erreur");

  showMsg(msgEl, true, j.message || "Code envoyé (si email existe).");
});

$("btnResetPass") && ($("btnResetPass").onclick = async () => {
  const msgEl = $("forgotMsg");
  hideMsg(msgEl);

  const email = ($("fpEmail")?.value || "").trim();
  const token = ($("fpToken")?.value || "").trim();
  const new_password = ($("fpNewPass")?.value || "").trim();

  if (!email || !token || !new_password) return showMsg(msgEl, false, "Champs requis.");
  if (new_password.length < 6) return showMsg(msgEl, false, "Mot de passe min 6.");

  const res = await fetch("/auth/password/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, token, new_password }),
  });

  const j = await res.json().catch(() => ({}));
  if (!res.ok) return showMsg(msgEl, false, j.detail || "Erreur reset");

  showMsg(msgEl, true, j.message || "Mot de passe mis à jour.");
});

/* ---------------------------
   REGISTER UI (simple)
   IDs attendus:
   - btnRegister (ouvrir box)
   - btnLogin (déjà utilisé pour se connecter) -> ici on masque register box au click (sans casser login)
   - register-box
   - do-register
   - reg-email, reg-pass, reg-ref
--------------------------- */
const regBox = $("register-box");
$("btnRegister") &&
  ($("btnRegister").onclick = () => {
    if (regBox) regBox.style.display = "block";
  });

// option: si tu as un bouton "fermer register" ajoute id="btnCloseRegister"
$("btnCloseRegister") &&
  ($("btnCloseRegister").onclick = () => {
    if (regBox) regBox.style.display = "none";
  });

/* ---------------------------
   Initial view
--------------------------- */
$("loginBox")?.classList.remove("hide");
$("appBox")?.classList.add("hide");

$("do-register") && ($("do-register").onclick = async () => {

  const msgEl = $("registerMsg");
  hideMsg(msgEl);

  const email = $("reg-email").value.trim();
  const password = $("registerPassword").value.trim();
  const ref = $("reg-ref").value.trim();
  const first_name = $("reg-first").value.trim();
  const last_name = $("reg-last").value.trim();

  if (!email || !password) {
    return showMsg(msgEl,false,"Email et mot de passe requis");
  }

  try {

    await registerUser(first_name,last_name,email,password,ref);

    showMsg(msgEl,true,"Compte créé. Tu peux te connecter.");

  } catch(e) {

    showMsg(msgEl,false,e.detail || e.message);

  }

});
/* =========================================================
   ⚠️ TON CODE ORIGINAL (non supprimé) — fin
========================================================= */

ensureInjectedUI();
wireMenusSafe();

console.log("HaitiWallet app.js loaded — clean_full_v1");

// Initial tab activation
showTab(tabFromHash());

// Toggle mot de passe mobile + desktop
const toggle = document.getElementById("togglePassword");
const passwordInput = document.getElementById("password");

if (toggle && passwordInput) {
  toggle.addEventListener("click", () => {
    const isHidden = passwordInput.type === "password";

    passwordInput.type = isHidden ? "text" : "password";

    toggle.classList.toggle("hidden", !isHidden);
  });
}

// Toggle password REGISTER
const toggleRegister = document.getElementById("toggleRegisterPassword");
const registerPasswordInput = document.getElementById("registerPassword");

if (toggleRegister && registerPasswordInput) {
  toggleRegister.addEventListener("click", () => {
    const isHidden = registerPasswordInput.type === "password";

    registerPasswordInput.type = isHidden ? "text" : "password";

    toggleRegister.classList.toggle("hidden", isHidden);
  });
}


const goProfile = document.getElementById("goProfile");
const profileSection = document.getElementById("profileSection");
const appBox = document.getElementById("appBox");
const backToApp = document.getElementById("backToApp");
const goSecurity = document.getElementById("goSecurity");
const securitySection = document.getElementById("securitySection");

if (goProfile && profileSection && appBox && securitySection) {
    goProfile.addEventListener("click", async () => {
        appBox.classList.add("hide");
        securitySection.classList.add("hide");
        profileSection.classList.remove("hide");
        await loadProfile();
    });
}

if (goSecurity && securitySection && appBox && profileSection) {
    goSecurity.addEventListener("click", () => {
        appBox.classList.add("hide");
        profileSection.classList.add("hide");
        securitySection.classList.remove("hide");
    });
}

async function loadProfile() {
  const res = await api("/auth/me");
  if (!res.ok) {
    console.error("Erreur profil");
    return;
  }

  const user = await res.json();

  document.getElementById("profileFirstName").value = user.first_name || "";
  document.getElementById("profileLastName").value = user.last_name || "";
  document.getElementById("profileEmail").value = user.email || "";
  document.getElementById("profilePhone").value = user.phone || "";
}

const saveProfile = document.getElementById("saveProfile");

if (saveProfile) {
  saveProfile.addEventListener("click", async () => {

    const res = await api("/auth/me", {
      method: "PUT",
      body: JSON.stringify({
        first_name: document.getElementById("profileFirstName").value,
        last_name: document.getElementById("profileLastName").value,
        phone: document.getElementById("profilePhone").value,
      })
    });

    if (!res.ok) {
      alert("Erreur sauvegarde");
      return;
    }

    await loadProfile(); // 🔥 recharge depuis backend
    alert("Profil mis à jour");
  });
}

// === NAVIGATION SIMPLE ET PROPRE ===

    function showSection(id) {
        document.querySelectorAll('[id^="tab-"]').forEach(sec => {
            sec.classList.add("hide");
        });

        const target = document.getElementById("tab-" + id);
        if (target) {
            target.classList.remove("hide");
        }
    }

    document.addEventListener("DOMContentLoaded", () => {

    // Dashboard par défaut
    showSection("dashboard");

    // Boutons menu
    const sections = ["dashboard", "topup", "transfer", "history", "partners", "info", "admin"];

    sections.forEach(name => {
        const btn = document.getElementById("tabBtn-" + name);
        if (btn) {
            btn.addEventListener("click", () => {
                showSection(name);
                sideMenu.classList.add("hide");
            });
        }
    });

});

// Bouton supprimer mon compte
const deleteBtn = document.getElementById("deleteAccount");

if (deleteBtn) {
    deleteBtn.addEventListener("click", () => {
        showDeleteAccount();
    });
}

function updateProfileVisibility() {
    const profileToggle = document.getElementById("profileToggle");
    const menuToggle = document.getElementById("menuToggle");

    if (!profileToggle || !menuToggle) return;

    if (token) {
        profileToggle.style.display = "block";
        menuToggle.style.display = "block";   // 👈 ON AFFICHE ☰
    } else {
        profileToggle.style.display = "none";
        menuToggle.style.display = "none";    // 👈 ON CACHE ☰
    }
}

document.addEventListener("DOMContentLoaded", updateProfileVisibility);

const saveSecurity = document.getElementById("saveSecurity");

if (saveSecurity) {
  saveSecurity.addEventListener("click", async () => {

    const msgEl = document.getElementById("securityMsg");
    msgEl.classList.add("hide");

    const current = document.getElementById("currentPassword").value;
    const newPass = document.getElementById("newPassword").value;
    const confirm = document.getElementById("confirmPassword").value;

    if (!current || !newPass || !confirm) {
      msgEl.textContent = "Tous les champs sont requis.";
      msgEl.className = "err";
      msgEl.classList.remove("hide");
      return;
    }

    if (newPass.length < 6) {
      msgEl.textContent = "Nouveau mot de passe trop court.";
      msgEl.className = "err";
      msgEl.classList.remove("hide");
      return;
    }

    if (newPass !== confirm) {
      msgEl.textContent = "Les mots de passe ne correspondent pas.";
      msgEl.className = "err";
      msgEl.classList.remove("hide");
      return;
    }

    const res = await api("/auth/password/change", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        old_password: current,
        new_password: newPass
      })
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      msgEl.textContent = data.detail || "Erreur.";
      msgEl.className = "err";
      msgEl.classList.remove("hide");
      return;
    }

    msgEl.textContent = "Mot de passe mis à jour avec succès.";
    msgEl.className = "ok";
    msgEl.classList.remove("hide");

    document.getElementById("currentPassword").value = "";
    document.getElementById("newPassword").value = "";
    document.getElementById("confirmPassword").value = "";
  });
}

async function sendDeleteRequest() {

    const data = {
        first_name: document.getElementById("deleteFirstName").value,
        last_name: document.getElementById("deleteLastName").value,
        email: document.getElementById("deleteEmail").value,
        reason: document.getElementById("deleteReason").value
    };

    const res = await fetch("/auth/request-delete-account", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    });

    const result = await res.json();

    document.getElementById("deleteMessage").innerText = result.message;
}

function showDeleteAccount() {
    window.location.href = "/static/index.html";
}

// === MENU FIX FINAL ===

const menuToggle = document.getElementById("menuToggle");
const sideMenu = document.getElementById("sideMenu");
const profileToggle = document.getElementById("profileToggle");
const profileDropdown = document.getElementById("profileDropdown");

function closeAllMenus() {
  sideMenu?.classList.add("hide");
  profileDropdown?.classList.add("hide");
}

menuToggle?.addEventListener("click", (e) => {
  e.stopPropagation();

  // 🔥 ferme sections ouvertes
  document.getElementById("profileSection")?.classList.add("hide");
  document.getElementById("securitySection")?.classList.add("hide");
  document.getElementById("appBox")?.classList.remove("hide");

  const isOpen = !sideMenu.classList.contains("hide");

  closeAllMenus();

  if (!isOpen) {
    sideMenu.classList.remove("hide");
  }
});

profileToggle?.addEventListener("click", (e) => {
  e.stopPropagation();

  if (!profileDropdown) return;

  const isOpen = !profileDropdown.classList.contains("hide");

  closeAllMenus();

  if (!isOpen) {
    profileDropdown.classList.remove("hide");
  }
});

document.addEventListener("click", closeAllMenus);

// === BOUTONS RETOUR ===

document.getElementById("backToApp")?.addEventListener("click", () => {
  document.getElementById("profileSection")?.classList.add("hide");
  document.getElementById("appBox")?.classList.remove("hide");
});

document.getElementById("backFromSecurity")?.addEventListener("click", () => {
  document.getElementById("securitySection")?.classList.add("hide");
  document.getElementById("appBox")?.classList.remove("hide");
});

async function loadRevenueStats() {
  const btn = document.getElementById("btnRefreshRevenue");
  if (btn) btn.textContent = "Chargement...";

  const res = await api("/admin/stats");
  if (!res.ok) return;

  const data = await res.json();

  document.getElementById("revToday").textContent =
    data.today.toFixed(2);

  document.getElementById("revMonth").textContent =
    data.month.toFixed(2);

  document.getElementById("revTotal").textContent =
    data.total.toFixed(2);

  drawRevenueChart(data.monthly);

  if (btn) btn.textContent = "Rafraîchir";
}
document.addEventListener("click", (e) => {
  if (e.target && e.target.id === "btnRefreshRevenue") {
    loadRevenueStats();
  }
});

function drawRevenueChart(monthlyData) {
  const ctx = document.getElementById("revenueChart");

  const labels = monthlyData.map(m =>
    `${m.year}-${String(m.month).padStart(2, "0")}`
  );

  const values = monthlyData.map(m => m.total);

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Revenus mensuels",
        data: values,
      }]
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadRevenueStats();
});