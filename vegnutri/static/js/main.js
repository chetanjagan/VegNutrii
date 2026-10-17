/* VegNutri v4 client. No inline handlers: everything is delegated from here (strict CSP). */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const csrf = () => ($('meta[name="csrf-token"]') || {}).content || "";

  async function postJSON(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(data || {}),
      credentials: "same-origin",
    });
    let body = {};
    try { body = await res.json(); } catch (e) { /* non-JSON error page */ }
    return { ok: res.ok, status: res.status, body };
  }

  // ── Theme ────────────────────────────────────────────────
  function setTheme(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
    try { t ? localStorage.setItem("vn-theme", t) : localStorage.removeItem("vn-theme"); } catch (e) {}
  }
  function currentTheme() {
    const set = document.documentElement.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  // ── Click delegation ─────────────────────────────────────
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-action], [data-swap-url], [data-water], [data-checkout], [data-starter], [role='tab'], [data-period], [data-copy]");
    if (!el) {
      const rail = $(".rail.open");
      if (rail && !e.target.closest(".rail")) rail.classList.remove("open");
      return;
    }
    const action = el.dataset.action;
    if (action === "theme") { setTheme(currentTheme() === "dark" ? "light" : "dark"); }
    else if (action === "menu") { e.stopPropagation(); $(".rail")?.classList.toggle("open"); }
    else if (action === "dismiss") { el.closest(".flash")?.remove(); }
    else if (action === "print") { window.print(); }
    else if (el.dataset.swapUrl) { e.preventDefault(); swapMeal(el); }
    else if (el.dataset.water) { e.preventDefault(); addWater(parseInt(el.dataset.water, 10)); }
    else if (el.dataset.checkout) { e.preventDefault(); checkout(el); }
    else if (el.dataset.starter) { e.preventDefault(); const t = $("#chat-input"); if (t) { t.value = el.dataset.starter; $("#chat-form").requestSubmit(); } }
    else if (el.getAttribute("role") === "tab") { selectTab(el); }
    else if (el.dataset.period) { setPeriod(el.dataset.period); }
    else if (el.dataset.copy) { copyText(el); }
  });

  async function copyText(btn) {
    const src = $(btn.dataset.copy);
    if (!src) return;
    try { await navigator.clipboard.writeText(src.value || src.textContent); toast("Link copied"); }
    catch (e) { src.select && src.select(); toast("Press Ctrl+C or Cmd+C to copy"); }
  }

  // Confirm before destructive submits
  document.addEventListener("submit", (e) => {
    const msg = e.target.dataset.confirm;
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // ── Tabs (meal plan days) ────────────────────────────────
  function selectTab(tab) {
    const list = tab.closest("[role='tablist']");
    $$("[role='tab']", list).forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(t.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    });
  }
  document.addEventListener("keydown", (e) => {
    const tab = e.target.closest("[role='tab']");
    if (!tab || !["ArrowRight", "ArrowLeft"].includes(e.key)) return;
    const tabs = $$("[role='tab']", tab.closest("[role='tablist']"));
    const next = tabs[(tabs.indexOf(tab) + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    next.focus(); selectTab(next);
  });

  // ── Meal swap ────────────────────────────────────────────
  async function swapMeal(btn) {
    const row = btn.closest("[data-meal]");
    row?.classList.add("swapping");
    btn.disabled = true;
    const { ok, body } = await postJSON(btn.dataset.swapUrl);
    btn.disabled = false;
    row?.classList.remove("swapping");
    if (!ok || !body.meal) { toast(body.message || "Couldn't swap that meal. Try again."); return; }
    const m = body.meal;
    const link = $(".name a", row);
    if (link) { link.textContent = m.name; link.href = link.href.replace(/[^/]+$/, m.key); }
    const macros = $(".macros", row);
    if (macros) macros.textContent = `${Math.round(m.kcal)} kcal, ${Math.round(m.protein)} g protein, ${m.mins} min`;
    const panel = row.closest(".day-panel");
    if (panel) {
      const t = body.totals;
      const set = (sel, v) => { const el = $(sel, panel); if (el) el.textContent = v; };
      set("[data-total='kcal']", Math.round(t.kcal));
      set("[data-total='protein']", Math.round(t.protein));
      set("[data-total='cost']", Math.round(t.cost));
    }
  }

  // ── Water ────────────────────────────────────────────────
  async function addWater(ml) {
    const { ok, body } = await postJSON("/water", { amount: ml });
    if (!ok) { toast("Couldn't save that. Check your connection."); return; }
    $$("[data-water-total]").forEach((el) => (el.textContent = body.total.toLocaleString("en-IN")));
    $$("[data-water-bar]").forEach((el) => (el.style.width = Math.min(100, (body.total / body.goal) * 100) + "%"));
    toast(`Added ${ml} ml`);
  }

  // ── Toast ────────────────────────────────────────────────
  function toast(text) {
    let box = $("#toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "toast";
      box.setAttribute("role", "status");
      box.style.cssText = "position:fixed;left:50%;transform:translateX(-50%);bottom:calc(5.5rem + env(safe-area-inset-bottom,0px));" +
        "background:var(--ink);color:var(--bg);padding:.6rem 1rem;border-radius:10px;z-index:50;font-size:.95rem;max-width:90vw";
      document.body.appendChild(box);
    }
    box.textContent = text;
    box.hidden = false;
    clearTimeout(box._t);
    box._t = setTimeout(() => (box.hidden = true), 2600);
  }
  window.vnToast = toast;

  // ── Food search (log page) ──────────────────────────────
  const search = $("#food-search");
  if (search) {
    const results = $("#food-results");
    let timer;
    search.addEventListener("input", () => {
      clearTimeout(timer);
      const q = search.value.trim();
      if (q.length < 2) { results.hidden = true; return; }
      timer = setTimeout(async () => {
        const res = await fetch("/api/foods?q=" + encodeURIComponent(q), { credentials: "same-origin" });
        const items = res.ok ? await res.json() : [];
        results.innerHTML = "";
        if (!items.length) {
          const p = document.createElement("p");
          p.className = "muted"; p.style.padding = ".75rem";
          p.textContent = "No match. Use \"Enter it yourself\" below, or add it to My foods.";
          results.appendChild(p);
        }
        items.forEach((it) => {
          const b = document.createElement("button");
          b.type = "button";
          const left = document.createElement("span");
          left.innerHTML = "<strong></strong><br><small class='muted'></small>";
          left.querySelector("strong").textContent = it.name;
          left.querySelector("small").textContent = it.serving + (it.source === "custom" ? ", your food" : "");
          const right = document.createElement("small");
          right.className = "muted";
          right.textContent = `${Math.round(it.kcal)} kcal, ${it.protein} g`;
          b.append(left, right);
          b.addEventListener("click", () => pickFood(it));
          results.appendChild(b);
        });
        results.hidden = false;
      }, 180);
    });
    search.addEventListener("keydown", (e) => { if (e.key === "Escape") results.hidden = true; });
  }
  function pickFood(it) {
    $("#source").value = it.source;
    $("#food_key").value = it.source === "food" ? it.key : "";
    $("#custom_id").value = it.source === "custom" ? it.key : "";
    const picked = $("#picked");
    picked.hidden = false;
    $("#picked-name").textContent = it.name;
    $("#picked-meta").textContent = `${it.serving}: ${Math.round(it.kcal)} kcal, ${it.protein} g protein per serving`;
    $("#food-results").hidden = true;
    $("#food-search").value = "";
    $("#servings")?.focus();
  }

  // ── Coach chat ───────────────────────────────────────────
  const chatForm = $("#chat-form");
  if (chatForm) {
    const log = $("#chat-log");
    const input = $("#chat-input");
    const left = $("#quota-left");
    const scroll = () => (log.scrollTop = log.scrollHeight);
    const bubble = (role, text) => {
      const d = document.createElement("div");
      d.className = "bubble " + role;
      d.textContent = text;
      log.appendChild(d); scroll();
      return d;
    };
    scroll();
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); chatForm.requestSubmit(); }
    });
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      $("#chat-empty")?.remove();
      bubble("user", text);
      input.value = "";
      const wait = bubble("assistant pending", "Thinking…");
      const send = $("button[type='submit']", chatForm);
      send.disabled = true;
      const { ok, body } = await postJSON("/api/coach", { message: text });
      send.disabled = false;
      wait.classList.remove("pending");
      if (ok) {
        wait.textContent = body.reply;
        if (left && typeof body.left === "number") left.textContent = body.left;
      } else {
        wait.textContent = body.message || "The coach couldn't reply. Try again.";
        if (body.upgrade) {
          const a = document.createElement("a");
          a.href = "/pricing"; a.textContent = " See Pro plans";
          wait.appendChild(a);
        }
      }
      scroll();
      input.focus();
    });
    if (input.value) input.focus();
  }

  // ── Pricing / checkout ──────────────────────────────────
  let appliedCoupon = "";
  const inr = (paise) => "₹" + Math.round(paise / 100).toLocaleString("en-IN");
  const couponForm = $("#coupon-form");
  if (couponForm) {
    couponForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const code = $("#coupon").value.trim().toUpperCase();
      const status = $("#coupon-status");
      const { ok, body } = await postJSON("/api/billing/quote", { coupon: code });
      if (!ok) { status.textContent = "Couldn't check that code. Try again."; return; }
      appliedCoupon = body.applied ? body.applied.code : "";
      status.textContent = body.applied ? `${body.applied.code} applied: ${body.applied.percent_off}% off.`
        : (code ? body.error || "That code isn't valid." : "");
      $$(".price[data-plan]").forEach((el) => {
        ["month", "year"].forEach((period) => {
          const q = body.prices[`${el.dataset.plan}-${period}`];
          if (!q) return;
          const suffix = period === "month" ? "Month" : "Year";
          el.dataset["price" + suffix] = inr(q.amount);
          if (q.discount) el.dataset["was" + suffix] = inr(q.price);
          else delete el.dataset["was" + suffix];
        });
      });
      const current = ($("[data-period][aria-pressed='true']") || {}).dataset;
      setPeriod((current && current.period) || "year");
    });
  }

  function setPeriod(period) {
    $$("[data-period]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.period === period ? "true" : "false"));
    $$("[data-price-month], [data-price-year]").forEach((el) => {
      const val = el.dataset["price" + (period === "month" ? "Month" : "Year")];
      const card = el.closest(".price-card");
      const btn = card && $("[data-checkout]", card);
      if (val) {
        el.innerHTML = "";
        el.append(val);
        const s = document.createElement("small");
        s.textContent = period === "month" ? " / month" : " / year";
        el.appendChild(s);
        const was = el.dataset["was" + (period === "month" ? "Month" : "Year")];
        if (was) {
          const w = document.createElement("s");
          w.className = "was";
          w.textContent = was;
          w.setAttribute("aria-label", "was " + was);
          el.appendChild(w);
        }
        card.hidden = false;
        if (btn) btn.dataset.period = period;
      } else if (card && btn) {
        card.hidden = period === "month"; // family is yearly only
      }
    });
  }

  async function checkout(btn) {
    if (btn.dataset.login) { window.location.href = btn.dataset.login; return; }
    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = "Opening payment…";
    const { ok, body } = await postJSON("/api/billing/order", { plan: btn.dataset.checkout, period: btn.dataset.period, coupon: appliedCoupon });
    const reset = () => { btn.disabled = false; btn.textContent = label; };
    if (!ok) { reset(); toast(body.message || "Couldn't start the payment."); return; }
    const verify = async (resp) => {
      const v = await postJSON("/api/billing/verify", resp);
      if (v.ok) window.location.href = "/billing/success";
      else { reset(); toast(v.body.message || "Payment couldn't be verified."); }
    };
    if (body.demo) { verify({ razorpay_order_id: body.order_id }); return; }
    if (typeof window.Razorpay !== "function") { reset(); toast("Payment window didn't load. Check your connection."); return; }
    const rzp = new window.Razorpay({
      key: body.key, amount: body.amount, currency: body.currency, order_id: body.order_id,
      name: body.name, description: body.description, prefill: body.prefill,
      theme: { color: getComputedStyle(document.documentElement).getPropertyValue("--leaf").trim() || "#1e4d3b" },
      handler: verify,
      modal: { ondismiss: reset },
    });
    rzp.on("payment.failed", (r) => { reset(); toast((r.error && r.error.description) || "Payment failed. No money was taken."); });
    rzp.open();
  }

  // ── Quick log: snap, say or type ────────────────────────
  const ql = $("#quicklog");
  if (ql) {
    const status = $("#ql-status");
    const say = (t) => { status.textContent = t; };
    let busy = false;

    async function upload(url, form) {
      const res = await fetch(url, { method: "POST", body: form, credentials: "same-origin", headers: { "X-CSRFToken": csrf() } });
      let body = {};
      try { body = await res.json(); } catch (e) { body = { message: res.status === 413 ? "That file is too big." : "Something went wrong. Try again." }; }
      return { ok: res.ok, body };
    }

    function updateLeft(body) {
      if (typeof body.photo_left === "number") $$("[data-left='photo']").forEach((el) => (el.textContent = body.photo_left));
      if (typeof body.smart_left === "number") $$("[data-left='smart']").forEach((el) => (el.textContent = body.smart_left));
    }

    async function recognise(promise, sourceLabel) {
      if (busy) return;
      busy = true;
      say("Recognising your food…");
      $("#ql-review").hidden = true;
      try {
        const { ok, body } = await promise();
        if (!ok) {
          say(body.message || "Couldn't recognise that. Try again.");
          if (body.upgrade) {
            const a = document.createElement("a");
            a.href = body.upgrade; a.textContent = " See Pro for more.";
            status.appendChild(a);
          }
          return;
        }
        updateLeft(body);
        if (!body.items || !body.items.length) { say("I couldn't spot any food. Try again, or type it instead."); return; }
        say("");
        showReview(body, sourceLabel);
      } catch (e) {
        say("No connection. Check your internet and try again.");
      } finally {
        busy = false;
      }
    }

    // Photo: shrink in the browser, then upload
    async function shrink(file) {
      const MAX = 1024;
      let bitmap;
      try { bitmap = await createImageBitmap(file); }
      catch (e) {
        const url = URL.createObjectURL(file);
        bitmap = await new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = reject;
          img.src = url;
        });
      }
      const scale = Math.min(1, MAX / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(bitmap.width * scale);
      canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.82));
    }

    $("#ql-photo").addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      e.target.value = "";
      if (!file) return;
      let blob;
      try { blob = await shrink(file); }
      catch (err) { say("Couldn't read that photo. Try a JPEG, or take a new photo."); return; }
      if (!blob) { say("Couldn't read that photo. Try a JPEG, or take a new photo."); return; }
      const form = new FormData();
      form.append("image", blob, "meal.jpg");
      recognise(() => upload("/api/quick-log/photo", form), "From your photo");
    });

    // Voice: record up to 60 seconds
    const recBtn = $("#ql-record");
    const timer = $("#ql-timer");
    let recorder = null, chunks = [], started = 0, tick = null, autoStop = null;
    const canRecord = !!(navigator.mediaDevices && window.MediaRecorder);
    if (!canRecord) { recBtn.disabled = true; recBtn.textContent = "Recording not supported here"; }

    function pickMime() {
      for (const t of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"]) {
        if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t)) return t;
      }
      return "";
    }

    function stopRecording() {
      if (recorder && recorder.state === "recording") recorder.stop();
    }

    recBtn.addEventListener("click", async () => {
      if (recorder && recorder.state === "recording") { stopRecording(); return; }
      if (busy) return;
      let stream;
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch (e) { say("Microphone access was blocked. Allow it in your browser settings, or type instead."); return; }
      const mime = pickMime();
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunks = [];
      recorder.ondataavailable = (ev) => { if (ev.data && ev.data.size) chunks.push(ev.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        clearInterval(tick); clearTimeout(autoStop);
        timer.textContent = "";
        recBtn.textContent = "Start recording";
        recBtn.setAttribute("aria-pressed", "false");
        recBtn.classList.remove("btn-danger");
        const type = (recorder.mimeType || mime || "audio/webm");
        const blob = new Blob(chunks, { type });
        if (blob.size < 1000) { say("That was too short. Hold on a moment and say what you ate."); return; }
        const ext = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        const form = new FormData();
        form.append("audio", blob, "meal." + ext);
        recognise(() => upload("/api/quick-log/voice", form), "From your voice note");
      };
      recorder.start();
      started = Date.now();
      recBtn.textContent = "Stop and recognise";
      recBtn.setAttribute("aria-pressed", "true");
      recBtn.classList.add("btn-danger");
      say("Listening… say what you ate.");
      tick = setInterval(() => { timer.textContent = Math.round((Date.now() - started) / 1000) + "s · "; }, 500);
      autoStop = setTimeout(stopRecording, 60000);
    });

    // Text
    $("#ql-text-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const text = $("#ql-text").value.trim();
      if (!text) { say("Type what you ate first."); return; }
      recognise(() => postJSON("/api/quick-log/text", { text }), "From what you typed");
    });

    // Review list
    let current = [];
    function fmt(n) { return Math.round(n).toLocaleString("en-IN"); }

    function totals() {
      let kcal = 0, pro = 0;
      $$(".ql-item", ql).forEach((row, i) => {
        if (!$("input[type=checkbox]", row).checked) return;
        const s = parseFloat($("input[type=number]", row).value) || 0;
        kcal += current[i].per.kcal * s;
        pro += current[i].per.protein * s;
        $(".ql-kcal", row).textContent = `${fmt(current[i].per.kcal * s)} kcal, ${(current[i].per.protein * s).toFixed(1)} g protein`;
      });
      $("#ql-total-kcal").textContent = fmt(kcal);
      $("#ql-total-pro").textContent = pro.toFixed(1);
    }

    function showReview(body, sourceLabel) {
      current = body.items;
      const list = $("#ql-items");
      list.innerHTML = "";
      body.items.forEach((item, i) => {
        const row = document.createElement("div");
        row.className = "ql-item";
        row.innerHTML =
          '<label class="check"><input type="checkbox" checked><span><strong class="ql-name"></strong><br>' +
          '<small class="muted ql-serving"></small></span></label>' +
          '<div class="ql-qty"><label class="sr-only">Servings</label><input type="number" min="0.25" max="10" step="0.25"></div>' +
          '<small class="muted ql-kcal"></small><p class="ql-warn" hidden></p>';
        $(".ql-name", row).textContent = item.name;
        $(".ql-serving", row).textContent = item.estimate ? "AI estimate, as eaten" : "Servings of " + item.serving;
        const qty = $("input[type=number]", row);
        qty.value = item.servings;
        qty.id = "ql-qty-" + i;
        $(".ql-qty label", row).setAttribute("for", qty.id);
        if (item.warning) {
          const w = $(".ql-warn", row);
          w.textContent = item.warning;
          w.hidden = false;
          if (item.estimate) w.classList.add("is-estimate");
        }
        if (item.estimate) { const t = document.createElement("span"); t.className = "tag turmeric"; t.textContent = "Estimate"; $(".ql-name", row).after(" ", t); }
        list.appendChild(row);
      });
      $("#ql-source").textContent = sourceLabel;
      const note = $("#ql-note");
      const heard = body.transcript ? `I heard: "${body.transcript}"` : "";
      note.textContent = [heard, body.note].filter(Boolean).join(" · ");
      note.hidden = !note.textContent;
      $("#ql-review").hidden = false;
      totals();
      $("#ql-review").scrollIntoView({ behavior: "smooth", block: "start" });
    }

    $("#ql-items").addEventListener("input", totals);
    $("#ql-items").addEventListener("change", totals);

    $("#ql-save").addEventListener("click", async () => {
      const items = [];
      $$(".ql-item", ql).forEach((row, i) => {
        if (!$("input[type=checkbox]", row).checked) return;
        const it = current[i];
        items.push({ key: it.key, name: it.name, per: it.per, servings: parseFloat($("input[type=number]", row).value) || 1 });
      });
      if (!items.length) { say("Tick at least one item to log."); return; }
      const btn = $("#ql-save");
      btn.disabled = true;
      const { ok, body } = await postJSON("/api/quick-log/save", { items, meal_type: $("#ql-meal").value, log_date: $("#ql-date").value });
      btn.disabled = false;
      if (!ok) { say(body.message || "Couldn't save. Try again."); return; }
      window.location.href = body.redirect;
    });
  }

  // ── Thali rings ──────────────────────────────────────────
  function drawRings() {
    $$(".thali .fill[data-pct]").forEach((c) => {
      const r = parseFloat(c.getAttribute("r"));
      const len = 2 * Math.PI * r;
      const pct = Math.max(0, Math.min(100, parseFloat(c.dataset.pct) || 0));
      c.style.strokeDasharray = `${len}`;
      c.style.strokeDashoffset = `${len}`;
      requestAnimationFrame(() => requestAnimationFrame(() => (c.style.strokeDashoffset = `${len * (1 - pct / 100)}`)));
    });
  }

  // ── Charts ───────────────────────────────────────────────
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function drawCharts() {
    if (typeof window.Chart !== "function") return;
    $$("canvas[data-chart]").forEach((canvas) => {
      let cfg;
      try { cfg = JSON.parse(canvas.dataset.chart); } catch (e) { return; }
      const ink2 = cssVar("--ink-2"), line = cssVar("--line");
      const palette = { leaf: cssVar("--leaf"), turmeric: cssVar("--turmeric-bright"), water: cssVar("--water"), chilli: cssVar("--chilli") };
      const datasets = cfg.series.map((s) => ({
        label: s.label, data: s.data, type: s.type || cfg.type,
        backgroundColor: palette[s.color] || palette.leaf, borderColor: palette[s.color] || palette.leaf,
        borderWidth: s.type === "line" || cfg.type === "line" ? 2 : 0, borderRadius: 6, pointRadius: 0,
        borderDash: s.dashed ? [6, 5] : [], fill: false, tension: 0.3, spanGaps: true,
      }));
      new window.Chart(canvas, {
        type: cfg.type, data: { labels: cfg.labels, datasets },
        options: {
          responsive: true, maintainAspectRatio: false, animation: { duration: 400 },
          plugins: { legend: { display: datasets.length > 1, labels: { color: ink2, boxWidth: 12 } } },
          scales: {
            x: { grid: { display: false }, ticks: { color: ink2, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
            y: { beginAtZero: cfg.beginAtZero !== false, grid: { color: line }, ticks: { color: ink2, precision: cfg.integer ? 0 : undefined } },
          },
        },
      });
    });
  }

  // ── Init ─────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    drawRings();
    drawCharts();
    if ($("[data-period]")) setPeriod(($("[data-period][aria-pressed='true']") || {}).dataset?.period || "year");
    $$(".flash").forEach((f) => setTimeout(() => f.remove(), 7000));
  });

  if ("serviceWorker" in navigator && location.protocol === "https:") {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }
})();
