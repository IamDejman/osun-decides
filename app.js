/* Osun 2026 polling unit results - static client.
   Reads /data/results.json (rebuilt whenever new sheets are read) and
   /data/osun-lgas.geojson for the map. Party figures from a readable
   column are published even when the rest of the sheet does not add up. */
(function () {
  "use strict";

  window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };

  var D = null, GEO = null, view = "overview";
  var sortKey = "code", sortAsc = true, openLga = null;
  var main = document.getElementById("main");

  /* Fixed hue per party so a colour means the same thing on every screen.
     Muted on purpose: the rest of the page is INEC green and grey, so these
     are the only other colours and they have to sit alongside it quietly. */
  var PCOL = {
    A: "#2C5C9E", APC: "#1E7A55", ADC: "#A85A2B", PDP: "#6E3E96", ADP: "#9C7C22",
    AA: "#4A6F7C", AAC: "#7C5296", APGA: "#2A7C76", APM: "#8C5638", APP: "#55618F",
    BP: "#6F7A38", NNPP: "#A8433A", PRP: "#66677A", SDP: "#957A34", YPP: "#3A7060",
    ZLP: "#7C6096"
  };
  /* Colours sampled from each party's official INEC emblem, so the map, the
     share bars and the logo beside them all say the same thing. PCOL above is
     the fallback for anything the sampler could not read. */
  var PHEX = {};
  function pcol(p) { return PHEX[p] || PCOL[p] || "var(--muted)"; }

  /* The ballot prints Accord as a bare "A", which reads as a typo off the
     sheet, so it is spelled out everywhere the code would otherwise show. */
  var PNAME = { A: "Accord" };
  function pname(p) { return PNAME[p] || p; }

  function el(t, c, x) { var n = document.createElement(t); if (c) n.className = c; if (x != null) n.textContent = x; return n; }
  function svg(t, a) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", t);
    for (var k in a) if (a[k] != null) n.setAttribute(k, a[k]);
    return n;
  }
  function fmt(n) { return (n || 0).toLocaleString("en-NG"); }
  function pct(a, b) { return b ? (a / b * 100) : 0; }
  function pc1(a, b) { return pct(a, b).toFixed(1) + "%"; }
  function ranked(v) {
    return Object.keys(v).map(function (k) { return [k, v[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
  }
  function counted(v) { return ranked(v).filter(function (x) { return x[1] > 0; }); }
  function dot(p) { var i = el("i", "dot"); i.style.background = pcol(p); return i; }

  /* Official party emblems from INEC's own register. The coloured dot stays
     the fallback whenever a logo is missing, because the map, the share bars
     and the ward summaries all key off PCOL - if a party appeared as a logo
     here and a colour there, the two would stop agreeing. */
  var LOGOS = {};
  function emblem(p, size) {
    if (!LOGOS[p]) return dot(p);
    var i = document.createElement("img");
    i.className = "plogo";
    i.src = LOGOS[p];
    i.alt = "";               // decorative: the party name is always beside it
    i.loading = "lazy";
    i.width = size || 20;
    i.height = size || 20;
    i.style.setProperty("--lsz", (size || 20) + "px");
    i.onerror = function () {
      var d = dot(p);
      if (i.parentNode) i.parentNode.replaceChild(d, i);
    };
    return i;
  }
  function sechead(title, note) {
    var s = el("section", "sec");
    s.appendChild(el("h2", null, title));
    if (note) s.appendChild(el("p", "note", note));
    return s;
  }

  /* ---------------- how much has been counted ---------------- */
  /* A unit INEC cancelled will never produce a vote, so leaving it in the
     outstanding pile would show a count that can never reach 100%. It is
     settled, but it is not counted, so it is neither added to the counted
     figure nor left pending. */
  function settled(t) {
    return (t.pu_transcribed || 0) + (t.pu_cancelled || 0);
  }

  function countedRule(t) {
    var box = el("section", "counted");
    var fig = el("div", "cfig");
    var left = el("div", "cpct");
    left.appendChild(document.createTextNode(pct(t.pu_transcribed, t.pu_total).toFixed(1) + "% "));
    left.appendChild(el("span", null, "counted"));
    fig.appendChild(left);
    fig.appendChild(el("div", "cmeta",
      fmt(t.pu_transcribed) + " of " + fmt(t.pu_total) + " polling units"));
    box.appendChild(fig);
    var m = el("div", "meter");
    var a = el("i", "done"); a.style.width = pct(t.pu_transcribed, t.pu_total) + "%";
    m.appendChild(a);
    box.appendChild(m);
    if (t.pu_cancelled) {
      box.appendChild(el("div", "cmeta",
        fmt(t.pu_cancelled) + " further units were cancelled by INEC, so they carry no votes"));
    }
    return box;
  }

  /* ---------------- lede: leader, runner-up, the rest ---------------- */
  function lede(t) {
    var rows = ranked(t.votes);
    var withVotes = counted(t.votes);
    var tot = withVotes.reduce(function (s, r) { return s + r[1]; }, 0);
    var box = el("section", "lede");
    if (!withVotes.length) {
      box.appendChild(el("div", "empty", "No votes counted yet"));
      return box;
    }
    var margin = withVotes.length > 1 ? withVotes[0][1] - withVotes[1][1] : withVotes[0][1];

    /* A bare "51.9%" and a bare "+60,142" carry no weight and read as
       footnotes. Each party gets its share drawn to scale, and every number
       is labelled with what it counts, because the count is the thing people
       actually read. */
    function share(p, votes, big) {
      var w = el("div", "pshare");
      var bar = el("div", "pbar");
      var fill = el("i");
      fill.style.width = pct(votes, tot).toFixed(1) + "%";
      fill.style.background = pcol(p);
      bar.appendChild(fill);
      w.appendChild(bar);
      var f = el("div", "pfig");
      var pcv = el("span", "ppc" + (big ? " big" : ""), pc1(votes, tot));
      f.appendChild(pcv);
      f.appendChild(el("span", "plabel", "of votes counted"));
      w.appendChild(f);
      return w;
    }

    var a = el("div", "lcol");
    var l1 = el("div", "pline");
    l1.appendChild(emblem(withVotes[0][0], 30));
    l1.appendChild(document.createTextNode(pname(withVotes[0][0])));
    l1.appendChild(el("span", "flagtag", "Leading"));
    a.appendChild(l1);
    a.appendChild(el("div", "big", fmt(withVotes[0][1])));
    a.appendChild(el("div", "vlabel", "votes"));
    a.appendChild(share(withVotes[0][0], withVotes[0][1], true));
    if (withVotes.length > 1) {
      var lead = el("div", "leadbox");
      lead.appendChild(el("div", "leadnum", "+" + fmt(margin)));
      lead.appendChild(el("div", "leadlbl",
        "votes ahead of " + pname(withVotes[1][0])));
      a.appendChild(lead);

      var second = el("div", "runner");
      var l2 = el("div", "pline");
      l2.appendChild(emblem(withVotes[1][0], 24));
      l2.appendChild(document.createTextNode(pname(withVotes[1][0])));
      second.appendChild(l2);
      second.appendChild(el("div", "mid", fmt(withVotes[1][1])));
      second.appendChild(el("div", "vlabel", "votes"));
      second.appendChild(share(withVotes[1][0], withVotes[1][1], false));
      a.appendChild(second);
    }
    box.appendChild(a);

    var c = el("div", "lcol");
    c.appendChild(el("div", "rlbl", "Other parties"));
    var list = el("ul", "rest");
    var others = rows.slice(2);
    list.style.setProperty("--rows", Math.ceil(others.length / 2));
    others.forEach(function (r) {
      var row = el("li", "rrow" + (r[1] ? "" : " zero"));
      row.appendChild(emblem(r[0], 16));
      row.appendChild(el("span", null, pname(r[0])));
      row.appendChild(el("span", "rnum", fmt(r[1])));
      row.appendChild(el("span", "rpc", r[1] ? pc1(r[1], tot) : "-"));
      list.appendChild(row);
    });
    c.appendChild(list);
    box.appendChild(c);
    return box;
  }

  function stats(t) {
    var s = el("div", "stats");
    [[fmt(t.registered), "Registered"],
     [fmt(t.accredited), "Accredited"],
     [fmt(t.valid), "Valid votes"],
     [fmt(t.rejected), "Rejected"],
     [t.registered ? pc1(t.accredited, t.registered) : "-", "Turnout"]]
      .forEach(function (k) {
        var d = el("div", "stat");
        d.appendChild(el("div", "v", k[0]));
        d.appendChild(el("div", "k", k[1]));
        s.appendChild(d);
      });
    return s;
  }

  /* ---------------- map ---------------- */
  function buildMap(interactive) {
    var f = document.createDocumentFragment();
    f.appendChild(sechead("Leading party by local government",
      "Full colour once every unit in the LGA is counted"));
    if (!GEO) { f.appendChild(el("div", "empty", "Map unavailable")); return f; }

    var byName = {};
    D.lgas.forEach(function (L) { byName[L.name.toUpperCase()] = L; });

    // bbox over all rings
    var minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
    function scan(c, dep) {
      if (dep === 0) {
        if (c[0] < minx) minx = c[0]; if (c[0] > maxx) maxx = c[0];
        if (c[1] < miny) miny = c[1]; if (c[1] > maxy) maxy = c[1];
      } else for (var i = 0; i < c.length; i++) scan(c[i], dep - 1);
    }
    GEO.features.forEach(function (ft) {
      scan(ft.geometry.coordinates, ft.geometry.type === "Polygon" ? 2 : 3);
    });
    var W = 760, H = 560, pad = 14;
    var latmid = (miny + maxy) / 2;
    var kx = Math.cos(latmid * Math.PI / 180);
    var gw = (maxx - minx) * kx, gh = maxy - miny;
    var s = Math.min((W - pad * 2) / gw, (H - pad * 2) / gh);
    var ox = (W - gw * s) / 2, oy = (H - gh * s) / 2;
    function px(c) {
      return [(ox + (c[0] - minx) * kx * s).toFixed(1),
              (oy + (maxy - c[1]) * s).toFixed(1)];
    }
    function ring(r) {
      var d = "";
      for (var i = 0; i < r.length; i++) {
        var p = px(r[i]);
        d += (i ? "L" : "M") + p[0] + " " + p[1];
      }
      return d + "Z";
    }
    function pathFor(g) {
      var polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
      return polys.map(function (poly) { return poly.map(ring).join(""); }).join("");
    }

    var s1 = svg("svg", { viewBox: "0 0 " + W + " " + H, class: "map",
      role: "img", "aria-label": "Osun local governments shaded by leading party" });
    var tip = el("div", "maptip"); tip.hidden = true;
    var marks = [];

    GEO.features.forEach(function (ft) {
      var L = byName[(ft.properties.name || "").toUpperCase()];
      var t = L && L.totals;
      var rows = t ? counted(t.votes) : [];
      var fill = "var(--line-2)", op = 1, lead = null, marg = 0;
      if (rows.length) {
        lead = rows[0][0];
        var tot = rows.reduce(function (x, y) { return x + y[1]; }, 0);
        marg = rows.length > 1 ? pct(rows[0][1] - rows[1][1], tot) : 100;
        fill = pcol(lead);
        // Depth of colour answers "is this local government finished?", not
        // "how big is the lead". Encoding the margin instead made a fully
        // counted LGA with a modest lead look paler than a barely started one
        // with a wide early lead - exactly backwards for reading the map.
        op = (t && t.pu_total && settled(t) === t.pu_total) ? 1 : 0.34;
      }
      var complete = !!(t && t.pu_total && settled(t) === t.pu_total);
      // A plain-text summary for screen readers and as the accessible name.
      // Deliberately NOT an SVG <title>: the browser draws its own tooltip
      // from that, on top of the styled one, and you get two boxes at once.
      var label = ft.properties.name;
      if (L) {
        label += lead
          ? ", " + pname(lead) + " leading with " + fmt(rows[0][1]) + " votes, " +
            t.pu_transcribed + " of " + t.pu_total + " units counted"
          : ", not yet counted";
      }
      var p = svg("path", { d: pathFor(ft.geometry), fill: fill, "fill-opacity": op,
        stroke: "#fff", "stroke-width": 1, class: "lgapath", tabindex: "0",
        role: "img", "aria-label": label, "data-name": ft.properties.name });

      // Counts, not percentage points: a margin in points says nothing about
      // how many people it represents, and the map gets screenshotted.
      function fillTip() {
        tip.textContent = "";
        var head = el("div", "tiphead");
        head.appendChild(el("span", "tipname", ft.properties.name));
        if (complete) {
          var tick = el("span", "tipdone");
          tick.appendChild(el("i", "tick", "✓"));
          tick.appendChild(document.createTextNode(t.pu_cancelled
            ? "all " + t.pu_total + " units in, " + t.pu_cancelled + " cancelled"
            : "all " + t.pu_total + " units counted"));
          head.appendChild(tick);
        } else if (t) {
          head.appendChild(el("span", "tipunits",
            fmt(t.pu_transcribed) + " of " + fmt(t.pu_total) + " units"));
        }
        tip.appendChild(head);
        if (!rows.length) {
          tip.appendChild(el("div", "tiprow", "not yet counted"));
          return;
        }
        rows.slice(0, 3).forEach(function (r, i) {
          var row = el("div", "tiprow" + (i === 0 && complete ? " won" : ""));
          var sw = el("i", "tipdot"); sw.style.background = pcol(r[0]);
          row.appendChild(sw);
          row.appendChild(el("span", "tipparty", pname(r[0])));
          row.appendChild(el("span", "tipnum", fmt(r[1])));
          tip.appendChild(row);
        });
      }

      function show(e) {
        tip.hidden = false;
        fillTip();
        var r = s1.getBoundingClientRect();
        var x = (e.clientX || r.left + r.width / 2) - r.left;
        var y = (e.clientY || r.top) - r.top;
        // Measure after filling: the box is now several rows tall, so a fixed
        // offset would either sit under the cursor or run off the top edge.
        var w = tip.offsetWidth, h = tip.offsetHeight;
        tip.style.left = Math.max(4, Math.min(r.width - w - 4, x - w / 2)) + "px";
        tip.style.top = (y - h - 12 < 0 ? y + 18 : y - h - 12) + "px";
      }
      p.addEventListener("mousemove", show);
      p.addEventListener("focus", show);
      p.addEventListener("mouseleave", function () { tip.hidden = true; });
      p.addEventListener("blur", function () { tip.hidden = true; });
      if (interactive && L) {
        p.addEventListener("click", function () {
          view = "lgas"; openLga = L.code; syncTabs(); render();
        });
        p.style.cursor = "pointer";
      }
      s1.appendChild(p);
      // The leading party's emblem at the LGA centre. Only where something has
      // been counted, and only once the shape is drawn, so it sits on top.
      if (lead && ft.properties.c && LOGOS[lead]) {
        var cxy = px(ft.properties.c);
        var r0 = complete ? 13 : 10;
        var halo = svg("circle", { cx: cxy[0], cy: cxy[1], r: r0 + 2,
          fill: "#fff", stroke: "rgba(0,0,0,.25)", "stroke-width": 1,
          class: "lgamarkbg", "pointer-events": "none" });
        var im = svg("image", { x: cxy[0] - r0, y: cxy[1] - r0,
          width: r0 * 2, height: r0 * 2, href: LOGOS[lead],
          preserveAspectRatio: "xMidYMid meet",
          class: "lgamark", "pointer-events": "none" });
        im.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", LOGOS[lead]);
        marks.push(halo); marks.push(im);
      }
    });
    // Drawn after every shape so no neighbouring polygon covers them.
    marks.forEach(function (m) { s1.appendChild(m); });

    var holder = el("div", "mapwrap");
    holder.appendChild(s1); holder.appendChild(tip);
    f.appendChild(holder);

    var leg = el("div", "maplegend");
    var seen = {};
    D.lgas.forEach(function (L) {
      var r = counted(L.totals.votes);
      if (r.length) seen[r[0][0]] = (seen[r[0][0]] || 0) + 1;
    });
    Object.keys(seen).sort(function (a, b) { return seen[b] - seen[a]; }).forEach(function (p) {
      var k = el("span", "kitem");
      var sw = el("i", "sw"); sw.style.background = pcol(p);
      k.appendChild(sw);
      k.appendChild(document.createTextNode(pname(p) + " " + seen[p]));
      leg.appendChild(k);
    });
    // Say what the two depths mean, or the map reads as arbitrary shading.
    var kf = el("span", "kitem");
    var swf = el("i", "sw"); swf.style.background = "var(--muted)";
    kf.appendChild(swf);
    kf.appendChild(document.createTextNode("all units counted"));
    leg.appendChild(kf);
    var kp = el("span", "kitem");
    var swp = el("i", "sw"); swp.style.background = "var(--muted)"; swp.style.opacity = ".34";
    kp.appendChild(swp);
    kp.appendChild(document.createTextNode("still counting"));
    leg.appendChild(kp);
    var none = D.lgas.length - Object.keys(seen).reduce(function (a, k) { return a + seen[k]; }, 0);
    if (none > 0) {
      var k2 = el("span", "kitem");
      k2.appendChild(el("i", "sw none"));
      k2.appendChild(document.createTextNode(none + " not yet counted"));
      leg.appendChild(k2);
    }
    f.appendChild(leg);
    return f;
  }

  /* ---------------- lga table + drill ---------------- */
  function shareBar(votes) {
    var r = counted(votes);
    var tot = r.reduce(function (s, x) { return s + x[1]; }, 0);
    var bar = el("div", "bar");
    if (!tot) return bar;
    r.slice(0, 6).forEach(function (x) {
      var seg = el("i");
      seg.style.width = pct(x[1], tot) + "%";
      seg.style.background = pcol(x[0]);
      seg.title = pname(x[0]) + " " + fmt(x[1]);
      bar.appendChild(seg);
    });
    return bar;
  }
  function leaderCell(votes) {
    var r = counted(votes);
    if (!r.length) return el("span", "code", "-");
    var p = el("span", "lead-pill");
    p.appendChild(dot(r[0][0]));
    p.appendChild(document.createTextNode(pname(r[0][0]) + " " + fmt(r[0][1])));
    return p;
  }

  function puBlock(u, trail) {
    var d = el("div", "pu");
    var top = el("div", "putop");
    top.appendChild(el("span", "pucode", u.code));
    top.appendChild(el("span", "puname", u.name || "-"));
    if (u.status === "cancelled") {
      top.appendChild(el("span", "chip warn", "Cancelled: " +
        String(u.not_held || "").toLowerCase()));
    } else if (!u.votes) top.appendChild(el("span", "chip await", "Not counted"));
    else if (u.flag) top.appendChild(el("span", "chip warn", u.flag));
    if (u.img && /^https:\/\//i.test(u.img)) {
      var a = el("a", "chip sheet", "Sheet");
      a.href = u.img;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.setAttribute("aria-label", "Open the EC8A sheet for polling unit " + u.code);
      top.appendChild(a);
    }
    d.appendChild(top);
    if (u.votes) {
      var sc = el("div", "scores");
      counted(u.votes).forEach(function (x) {
        var s = el("span", "score");
        s.appendChild(document.createTextNode(pname(x[0]) + " "));
        s.appendChild(el("b", null, fmt(x[1])));
        sc.appendChild(s);
      });
      d.appendChild(sc);
      d.appendChild(el("div", "pustat",
        fmt(u.accredited) + " of " + fmt(u.registered) + " accredited · " +
        fmt(u.valid) + " valid · " + fmt(u.rejected || 0) + " rejected"));
    }
    if (trail) d.appendChild(el("div", "pustat", trail));
    return d;
  }

  function wardCard(w) {
    var d = el("details", "ward");
    var s = el("summary");
    var top = el("div", "wtop");
    top.appendChild(el("div", "wname", w.code + " · " + w.name));
    top.appendChild(el("div", "wmeta", w.totals.pu_transcribed + "/" + w.totals.pu_total));
    s.appendChild(top);
    s.appendChild(shareBar(w.totals.votes));
    var lead = counted(w.totals.votes)[0];
    s.appendChild(el("div", "wmeta", lead
      ? pname(lead[0]) + " " + fmt(lead[1]) + " of " + fmt(w.totals.valid)
      : "not yet counted"));
    d.appendChild(s);
    var built = false;
    d.addEventListener("toggle", function () {
      if (d.open && !built) {
        built = true;
        var box = el("div", "puwrap");
        w.pus.forEach(function (u) { box.appendChild(puBlock(u)); });
        d.appendChild(box);
      }
    });
    return d;
  }

  function lgaTable() {
    var f = document.createDocumentFragment();
    f.appendChild(sechead("Local governments", "Open a row for wards and units"));
    var scroll = el("div", "tscroll");
    var table = el("table");
    var thead = el("thead"), hr = el("tr");
    [["", "", ""], ["code", "Code", "s"], ["name", "Local government", "s"],
     ["lead", "Leading", ""], ["valid", "Valid", "s num"],
     ["read", "Counted", "s num"], ["share", "Split", "hide-s"]].forEach(function (c) {
      var th = el("th", c[2], c[1]);
      if (c[0]) th.dataset.k = c[0];
      hr.appendChild(th);
    });
    thead.appendChild(hr); table.appendChild(thead);
    var tb = el("tbody"); table.appendChild(tb);

    function draw() {
      tb.textContent = "";
      var rows = D.lgas.slice();
      rows.sort(function (a, b) {
        var x, y;
        if (sortKey === "code") { x = a.code; y = b.code; }
        else if (sortKey === "name") { x = a.name; y = b.name; }
        else if (sortKey === "valid") { x = a.totals.valid; y = b.totals.valid; }
        else { x = a.totals.pu_transcribed; y = b.totals.pu_transcribed; }
        var r = typeof x === "string" ? x.localeCompare(y) : x - y;
        return sortAsc ? r : -r;
      });
      rows.forEach(function (L) {
        var tr = el("tr", "click" + (openLga === L.code ? " open" : ""));
        tr.tabIndex = 0;
        var c0 = el("td"); c0.appendChild(el("span", "chev", "▶")); tr.appendChild(c0);
        tr.appendChild(el("td", "code", L.code));
        tr.appendChild(el("td", "nm", L.name));
        var ld = el("td"); ld.appendChild(leaderCell(L.totals.votes)); tr.appendChild(ld);
        tr.appendChild(el("td", "num", fmt(L.totals.valid)));
        tr.appendChild(el("td", "num", L.totals.pu_transcribed + "/" + L.totals.pu_total));
        var sh = el("td", "hide-s"); sh.appendChild(shareBar(L.totals.votes)); tr.appendChild(sh);
        function toggle() { openLga = openLga === L.code ? null : L.code; draw(); }
        tr.addEventListener("click", toggle);
        tr.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
        });
        tb.appendChild(tr);
        if (openLga === L.code) {
          var dr = el("tr", "drill");
          var td = el("td"); td.colSpan = 7;
          var g = el("div", "wardgrid");
          L.wards.forEach(function (w) { g.appendChild(wardCard(w)); });
          td.appendChild(g); dr.appendChild(td); tb.appendChild(dr);
        }
      });
    }
    thead.querySelectorAll("th.s, th.s.num").forEach(function (th) {
      th.addEventListener("click", function () {
        var k = th.dataset.k;
        if (!k) return;
        if (sortKey === k) sortAsc = !sortAsc;
        else { sortKey = k; sortAsc = (k === "code" || k === "name"); }
        draw();
      });
    });
    draw();
    scroll.appendChild(table); f.appendChild(scroll);
    return f;
  }

  /* ---------------- search ---------------- */
  var INDEX = null;
  function viewSearch() {
    if (!INDEX) {
      INDEX = [];
      D.lgas.forEach(function (L) {
        L.wards.forEach(function (w) {
          w.pus.forEach(function (u) {
            INDEX.push({ u: u, trail: L.name + " › " + w.name,
              hay: (u.code + " " + (u.name || "") + " " + L.name + " " + w.name).toLowerCase() });
          });
        });
      });
    }
    var f = document.createDocumentFragment();
    f.appendChild(sechead("Find a polling unit"));
    var bar = el("div", "searchbar");
    var inp = document.createElement("input");
    inp.type = "search";
    inp.placeholder = "Name, ward, local government, or code";
    inp.setAttribute("aria-label", "Search polling units");
    bar.appendChild(inp); f.appendChild(bar);
    var out = el("div"); f.appendChild(out);
    out.appendChild(el("div", "count", fmt(D.meta.totals.pu_total) + " units"));
    var t;
    inp.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () {
        var q = inp.value.trim().toLowerCase();
        out.textContent = "";
        if (!q) { out.appendChild(el("div", "count", fmt(D.meta.totals.pu_total) + " units")); return; }
        var res = INDEX.filter(function (r) { return r.hay.indexOf(q) > -1; });
        out.appendChild(el("div", "count", fmt(res.length) + " match" + (res.length === 1 ? "" : "es")));
        var box = el("div", "puwrap");
        res.slice(0, 200).forEach(function (r) { box.appendChild(puBlock(r.u, r.trail)); });
        out.appendChild(box);
      }, 130);
    });
    setTimeout(function () { inp.focus(); }, 30);
    return f;
  }

  /* ---------------- shell ---------------- */
  function viewOverview() {
    var t = D.meta.totals;
    var f = document.createDocumentFragment();
    f.appendChild(countedRule(t));
    f.appendChild(lede(t));
    f.appendChild(sechead("In counted units"));
    f.appendChild(stats(t));
    f.appendChild(buildMap(true));
    return f;
  }
  function viewMap() {
    var f = document.createDocumentFragment();
    f.appendChild(countedRule(D.meta.totals));
    f.appendChild(buildMap(true));
    return f;
  }
  function viewLgas() {
    var f = document.createDocumentFragment();
    f.appendChild(countedRule(D.meta.totals));
    f.appendChild(lgaTable());
    return f;
  }

  function syncTabs() {
    document.querySelectorAll("#tabs button").forEach(function (x) {
      if (x.dataset.v === view) x.setAttribute("aria-current", "page");
      else x.removeAttribute("aria-current");
    });
  }
  /* keepScroll is used by refreshes, which must not yank the reader back up */
  function render(keepScroll) {
    var y = window.scrollY;
    main.textContent = "";
    main.appendChild(
      view === "overview" ? viewOverview()
      : view === "map" ? viewMap()
      : view === "lgas" ? viewLgas()
      : view === "search" ? viewSearch()
      : viewOverview());
    window.scrollTo(0, keepScroll ? y : 0);
  }
  document.getElementById("tabs").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    view = b.dataset.v; syncTabs(); render();
  });

  function stamp() {
    var node = document.getElementById("footstamp");
    var d = D.meta.polled_at ? new Date(D.meta.polled_at) : null;
    if (!d || isNaN(d.getTime())) {
      node.textContent = "Updated -";
      return;
    }
    var parts = {};
    new Intl.DateTimeFormat("en-GB", {
      timeZone: "Africa/Lagos",
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true
    }).formatToParts(d).forEach(function (p) { parts[p.type] = p.value; });
    node.textContent = "Updated " + parts.weekday + ", " + parts.day + " " +
      parts.month + " " + parts.year + " " + parts.hour + ":" + parts.minute +
      " " + (parts.dayPeriod || "").toUpperCase();
  }

  /* Live totals come from GitHub, not from the last Vercel deploy. A data
     commit must not burn a free-plan deploy slot. Localhost still reads
     the file this folder just rebuilt.

     GitHub serves raw files with a five-minute CDN cache, so no-store alone
     can still hand back the previous build. The automatic poll lives with
     that: busting the cache every minute for every reader would trade a
     little freshness for GitHub's anonymous rate limit. A reader who asks
     for a refresh by hand is answering "is it current?", so that one gets a
     unique URL and a genuine round trip. */
  function resultsUrl(fresh) {
    var host = location.hostname;
    if (host === "localhost" || host === "127.0.0.1") return "/data/results.json";
    var u = "https://raw.githubusercontent.com/IamDejman/osun-decides/main/data/results.json";
    return fresh ? u + "?t=" + Date.now() : u;
  }

  var btn = document.getElementById("refresh");
  function pull(manual) {
    return fetch(resultsUrl(manual), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (n) {
        if (!n || !n.meta) return;
        if (!manual && n.meta.built_at === D.meta.built_at) return;
        D = n; INDEX = null; stamp(); render(true);
      }).catch(function () {});
  }
  btn.addEventListener("click", function () {
    btn.disabled = true;
    btn.textContent = "Refreshing";
    pull(true).then(function () {
      btn.disabled = false;
      btn.textContent = "Refresh";
    });
  });

  Promise.all([
    // no-store on the first load too: a cached results.json would show a
    // coverage figure and vote totals from an earlier build, and on a page
    // whose whole point is "how much is counted right now" that is worse
    // than a slower load.
    fetch(resultsUrl(), { cache: "no-store" }).then(function (r) { return r.json(); }),
    fetch("/data/osun-lgas.geojson").then(function (r) { return r.json(); }).catch(function () { return null; }),
    fetch("/data/party-logos.json").then(function (r) { return r.json(); }).catch(function () { return {}; }),
    fetch("/data/party-colours.json").then(function (r) { return r.json(); }).catch(function () { return {}; })
  ]).then(function (res) {
    D = res[0]; GEO = res[1]; LOGOS = res[2] || {};
    var ph = res[3] || {};
    for (var k in ph) if (ph[k]) PHEX[k] = ph[k];
    stamp(); render();
    // Pick up new figures without a reload while the count is running.
    setInterval(pull, 60000);
  }).catch(function () {
    main.textContent = "";
    main.appendChild(el("div", "empty", "Results could not be loaded."));
  });
})();
