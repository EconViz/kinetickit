"""The small, dependency-free browser runtime embedded in every interactive document."""

from __future__ import annotations

RUNTIME_CSS = r"""
.kk-figure{margin:0;font:14px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#1f2933}
.kk-stage{position:relative;max-width:100%;overflow:hidden;touch-action:none}
.kk-stage svg.kk-svg{display:block;max-width:100%;height:auto;cursor:grab}
.kk-stage svg.kk-svg.kk-dragging{cursor:grabbing}
.kk-stage .kk-overlay-layer{position:absolute;inset:0;pointer-events:none}
.kk-controls{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;padding:.5rem 0}
.kk-controls button,.kk-controls select{font:inherit;min-width:2.25rem;min-height:2.25rem;padding:.2rem .6rem;border:1px solid #9aa5b1;border-radius:6px;background:#fff;color:inherit;cursor:pointer}
.kk-controls button:hover,.kk-controls select:hover{background:#f0f4f8}
.kk-controls button:focus-visible,.kk-controls select:focus-visible,.kk-controls input:focus-visible,.kk-figure:focus-visible{outline:3px solid #0b6bcb;outline-offset:2px}
.kk-controls input[type=range]{flex:1 1 12rem;min-width:8rem}
.kk-controls output{font-variant-numeric:tabular-nums;min-width:8ch}
.kk-markers{display:flex;flex-wrap:wrap;gap:.4rem}
.kk-sr{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.kk-fallback{max-width:60ch}
@media (prefers-reduced-motion:reduce){.kk-figure *{scroll-behavior:auto!important}}
"""

RUNTIME_JS = r"""
(function () {
  "use strict";
  var dataEl = document.getElementById("kk-data");
  var data = JSON.parse(dataEl.textContent);
  var root = document.getElementById("kk-root");
  var D = data.duration || 0;
  var reduce = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var state = { time: 0, playing: false, speed: data.speed || 1, loop: !!data.loop };
  var handlers = {};
  var q = function (sel) { return root.querySelector(sel); };
  var ui = {
    play: q("[data-kk=play]"), prev: q("[data-kk=prev]"), next: q("[data-kk=next]"),
    first: q("[data-kk=first]"), last: q("[data-kk=last]"), seek: q("[data-kk=seek]"),
    time: q("[data-kk=time]"), speed: q("[data-kk=speed]"), loop: q("[data-kk=loop]"),
    reset: q("[data-kk=reset]"), live: q("[data-kk=live]")
  };

  function emit(type, detail) {
    detail = detail || {};
    detail.type = type;
    detail.time = state.time;
    var list = (handlers[type] || []).concat(handlers["*"] || []);
    for (var i = 0; i < list.length; i++) { try { list[i](detail); } catch (e) { console.error(e); } }
    root.dispatchEvent(new CustomEvent("kinetickit:" + type, { detail: detail, bubbles: true }));
  }

  /* ---- 2D: the exported native SVG, driven through its SMIL timeline ---- */
  function svgAdapter() {
    var svg = root.querySelector("svg.kk-svg");
    var view = { x: 0, y: 0, k: 1 };
    var world = svg.getElementById ? svg.getElementById("world") : svg.querySelector("#world");
    var holder = null;
    if (world) {
      holder = document.createElementNS("http://www.w3.org/2000/svg", "g");
      holder.setAttribute("id", "kk-view");
      world.parentNode.insertBefore(holder, world);
      holder.appendChild(world);
    }
    function applyView() {
      if (holder) holder.setAttribute("transform", "translate(" + view.x + " " + view.y + ") scale(" + view.k + ")");
    }
    function pt(evt) {
      var p = svg.createSVGPoint(); p.x = evt.clientX; p.y = evt.clientY;
      return p.matrixTransform(svg.getScreenCTM().inverse());
    }
    var drag = null;
    svg.addEventListener("wheel", function (e) {
      if (!holder) return;
      e.preventDefault();
      var p = pt(e), f = Math.exp(-e.deltaY * 0.0015), k = Math.min(50, Math.max(0.1, view.k * f));
      view.x = p.x - (p.x - view.x) * (k / view.k); view.y = p.y - (p.y - view.y) * (k / view.k); view.k = k;
      applyView(); emit("camera", { zoom: view.k, pan: [view.x, view.y] });
    }, { passive: false });
    svg.addEventListener("pointerdown", function (e) {
      if (!holder || e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
      svg.setPointerCapture(e.pointerId);
    });
    svg.addEventListener("pointermove", function (e) {
      if (!drag) return;
      var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
      drag.moved = true; svg.classList.add("kk-dragging");
      var m = svg.getScreenCTM(), s = m ? m.a : 1;
      view.x = drag.vx + dx / s; view.y = drag.vy + dy / s; applyView();
    });
    function endDrag(e) {
      if (!drag) return;
      if (drag.moved) emit("camera", { zoom: view.k, pan: [view.x, view.y] });
      drag = null; svg.classList.remove("kk-dragging");
    }
    svg.addEventListener("pointerup", endDrag); svg.addEventListener("pointercancel", endDrag);
    function owner(el) {
      while (el && el !== svg) { if (el.getAttribute && el.getAttribute("data-kk-id")) return el; el = el.parentNode; }
      return null;
    }
    svg.addEventListener("pointerover", function (e) { var o = owner(e.target); if (o) emit("hover", { id: o.getAttribute("data-kk-id"), state: "enter" }); });
    svg.addEventListener("pointerout", function (e) { var o = owner(e.target); if (o) emit("hover", { id: o.getAttribute("data-kk-id"), state: "leave" }); });
    svg.addEventListener("click", function (e) { if (drag && drag.moved) return; var o = owner(e.target); if (o) emit("click", { id: o.getAttribute("data-kk-id") }); });
    svg.addEventListener("dblclick", function (e) { var o = owner(e.target); if (o) emit("dblclick", { id: o.getAttribute("data-kk-id") }); });
    svg.addEventListener("focusin", function (e) { var o = owner(e.target); if (o) emit("focus", { id: o.getAttribute("data-kk-id") }); });
    if (svg.pauseAnimations) svg.pauseAnimations();
    return {
      show: function (t) { if (svg.setCurrentTime) svg.setCurrentTime(t); },
      resetView: function () { view = { x: 0, y: 0, k: 1 }; applyView(); emit("camera", { zoom: 1, pan: [0, 0] }); }
    };
  }

  /* ---- 3D: pre-sampled frames shown through the embedded plotting runtime ---- */
  function plotAdapter() {
    var div = document.getElementById("kk-plot");
    var frames = data.frames || [];
    var n = frames.length;
    var lastIdx = -1, busy = false, wanted = null;
    var opts = { responsive: true, displaylogo: false, showLink: false, showSendToCloud: false,
                 showEditInChartStudio: false, scrollZoom: true, plotlyServerURL: "",
                 modeBarButtonsToRemove: ["sendDataToCloud", "editInChartStudio"] };
    var ready = Plotly.newPlot(div, data.traces, data.layout, opts);
    function idxFor(t) { return n <= 1 || D <= 0 ? 0 : Math.max(0, Math.min(n - 1, Math.round(t / D * (n - 1)))); }
    function apply() {
      if (busy || wanted === null) return;
      var i = wanted; wanted = null;
      if (i === lastIdx) return;
      lastIdx = i; busy = true;
      var f = frames[i];
      Plotly.animate(div, { data: f.data, traces: f.traces, layout: f.layout || {} },
        { frame: { duration: 0, redraw: true }, transition: { duration: 0 }, mode: "immediate" })
        .then(function () { busy = false; apply(); }, function () { busy = false; apply(); });
    }
    ready.then(function () {
      var by = function (e) { var p = e.points && e.points[0]; var m = p && p.data && p.data.meta; return m && m.id; };
      div.on("plotly_hover", function (e) { var id = by(e); if (id) emit("hover", { id: id, state: "enter" }); });
      div.on("plotly_unhover", function (e) { var id = by(e); if (id) emit("hover", { id: id, state: "leave" }); });
      div.on("plotly_click", function (e) { var id = by(e); if (id) emit("click", { id: id }); });
      div.on("plotly_relayout", function (e) { if (e["scene.camera"] || e["scene.camera.eye"]) emit("camera", { camera: e["scene.camera"] || null }); });
      apply();
    });
    return {
      show: function (t) { wanted = idxFor(t); ready.then(apply); },
      resetView: function () { Plotly.relayout(div, { "scene.camera": (frames[lastIdx < 0 ? 0 : lastIdx].layout || {}).scene ? frames[lastIdx < 0 ? 0 : lastIdx].layout.scene.camera : data.layout.scene.camera }); },
      snap: function (t) { return n <= 1 || D <= 0 ? 0 : idxFor(t) / (n - 1) * D; }
    };
  }

  var adapter = data.dimension === 3 ? plotAdapter() : svgAdapter();
  var fps = data.fps || 30;

  function fmt(t) { return t.toFixed(2) + " / " + D.toFixed(2) + " s"; }
  function refresh() {
    if (ui.play) { ui.play.textContent = state.playing ? "⏸" : "▶"; ui.play.setAttribute("aria-label", state.playing ? "Pause" : "Play"); ui.play.setAttribute("aria-pressed", state.playing ? "true" : "false"); }
    if (ui.seek) { ui.seek.value = String(state.time); ui.seek.setAttribute("aria-valuetext", fmt(state.time)); }
    if (ui.time) ui.time.textContent = fmt(state.time);
  }
  function show(t) {
    state.time = Math.max(0, Math.min(D, t));
    adapter.show(state.time);
    refresh();
  }

  var raf = null, last = 0;
  function tick(now) {
    if (!state.playing) return;
    var t = state.time + (now - last) / 1000 * state.speed;
    last = now;
    if (t >= D) {
      if (state.loop && D > 0) { t = t % D; emit("loop"); }
      else { show(D); pause(); emit("end"); return; }
    }
    show(t);
    raf = requestAnimationFrame(tick);
  }
  function play() {
    if (D <= 0) return;
    if (state.time >= D) show(0);
    state.playing = true; last = performance.now(); raf = requestAnimationFrame(tick);
    refresh(); emit("play");
  }
  function pause() {
    var was = state.playing;
    state.playing = false; if (raf) cancelAnimationFrame(raf);
    refresh(); if (was) emit("pause");
  }
  function seek(t) { show(t); emit("seek"); }
  function step(k) { pause(); var d = 1 / fps; show(Math.round(state.time / d + k) * d); emit("seek"); }
  function setSpeed(s) { state.speed = s; emit("speed", { speed: s }); }
  function setLoop(v) { state.loop = !!v; emit("loop-changed", { loop: state.loop }); }

  if (ui.seek) { ui.seek.max = String(D); ui.seek.step = String(1 / fps); ui.seek.addEventListener("input", function () { pause(); seek(parseFloat(ui.seek.value)); }); }
  if (ui.play) ui.play.addEventListener("click", function () { state.playing ? pause() : play(); });
  if (ui.prev) ui.prev.addEventListener("click", function () { step(-1); });
  if (ui.next) ui.next.addEventListener("click", function () { step(1); });
  if (ui.first) ui.first.addEventListener("click", function () { pause(); seek(0); });
  if (ui.last) ui.last.addEventListener("click", function () { pause(); seek(D); });
  if (ui.speed) { ui.speed.value = String(state.speed); ui.speed.addEventListener("change", function () { setSpeed(parseFloat(ui.speed.value)); }); }
  if (ui.loop) { ui.loop.checked = state.loop; ui.loop.addEventListener("change", function () { setLoop(ui.loop.checked); }); }
  if (ui.reset) ui.reset.addEventListener("click", function () { adapter.resetView(); });
  var marks = root.querySelectorAll("[data-kk-marker]");
  for (var m = 0; m < marks.length; m++) {
    (function (b) { b.addEventListener("click", function () { pause(); seek(data.markers[b.getAttribute("data-kk-marker")]); }); })(marks[m]);
  }

  root.addEventListener("keydown", function (e) {
    var tag = e.target && e.target.tagName;
    var typing = tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA";
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === " " && tag !== "BUTTON" && !typing) { e.preventDefault(); state.playing ? pause() : play(); }
    else if (e.key === "ArrowLeft" && !typing) { e.preventDefault(); step(-1); }
    else if (e.key === "ArrowRight" && !typing) { e.preventDefault(); step(1); }
    else if (e.key === "Home" && !typing) { e.preventDefault(); pause(); seek(0); }
    else if (e.key === "End" && !typing) { e.preventDefault(); pause(); seek(D); }
  });

  window.kinetickit = {
    version: data.version, duration: D, data: data,
    play: play, pause: pause, seek: seek, step: step, setSpeed: setSpeed, setLoop: setLoop,
    get time() { return state.time; }, get playing() { return state.playing; },
    on: function (type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
    off: function (type, fn) { handlers[type] = (handlers[type] || []).filter(function (f) { return f !== fn; }); }
  };

  if (reduce) { show(D); }
  else { show(0); if (data.autoplay) play(); }
  root.setAttribute("data-kk-ready", "true");
  emit("ready", { reducedMotion: reduce });
})();
"""
