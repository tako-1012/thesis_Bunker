"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  info: null,
  start: null,
  points: [],
  markers: [],
  base: null,
  image: null,
  routes: [],
  results: [],
  busy: false,
  playback: null,
  robot: null,
  simulation: null,
  simulatedRoute: null,
};
const map = L.map("map", {
  crs: L.CRS.Simple,
  minZoom: -3,
  maxZoom: 5,
  zoomSnap: 0.25,
  zoomControl: false,
});
L.control.zoom({ zoomInTitle: "拡大", zoomOutTitle: "縮小" }).addTo(map);
L.control.scale({ imperial: false, maxWidth: 100 }).addTo(map);
const names = { terrain: "地形を考慮", euclid: "直線距離" };
const colors = { terrain: "#216b62", euclid: "#496fb7" };
const latlng = (xy) => [xy[1], xy[0]];
const xy = (ll) => [Number(ll.lng.toFixed(3)), Number(ll.lat.toFixed(3))];
const number = (value, digits = 2) =>
  Number(value).toLocaleString("ja-JP", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });

function status(message, kind = "") {
  $("status-text").textContent = message;
  $("status").className = `status ${kind}`;
}

async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : `入力や通信を確認してください（${response.status}）`,
    );
  }
  return response.json();
}

function busy(value) {
  state.busy = value;
  for (const id of ["map-select", "load-points"]) $(id).disabled = value;
  for (const id of [
    "start-x",
    "start-y",
    "apply-start",
    "coordinates",
    "apply-points",
    "clear-points",
    "save-points",
    "method",
    "lookahead",
  ])
    $(id).disabled = value || !state.info;
  for (const marker of [...state.markers, state.base].filter(Boolean)) {
    if (value) marker.dragging.disable();
    else marker.dragging.enable();
  }
  updateButtons();
}

function updateButtons() {
  $("plan").disabled = $("compare").disabled =
    state.busy || !state.info || !state.points.length;
  $("play").disabled =
    state.busy || !state.results.some((r) => r.path.length > 1);
  $("simulate").disabled =
    state.busy || !state.results.some((r) => r.path.length > 1);
  $("point-count").textContent = `${state.points.length} / 12`;
  $("map-tip").hidden = state.points.length > 0 || state.busy;
}

function stopPlayback() {
  if (state.playback) cancelAnimationFrame(state.playback.frame);
  state.playback = null;
  if (state.robot) map.removeLayer(state.robot);
  state.robot = null;
  $("play").textContent = "▶ 再生";
}

function clearResults() {
  stopPlayback();
  clearSimulation();
  for (const route of state.routes) map.removeLayer(route);
  state.routes = [];
  state.results = [];
  $("result-content").hidden = true;
  $("empty-results").hidden = false;
}

function clearSimulation() {
  stopPlayback();
  if (state.simulatedRoute) map.removeLayer(state.simulatedRoute);
  state.simulatedRoute = null;
  state.simulation = null;
  $("simulation-result").hidden = true;
}

function waypointIcon(text) {
  // text is always an internally generated integer, never file/API HTML.
  return L.divIcon({
    className: "waypoint-shell",
    html: `<div class="waypoint-icon">${text}</div>`,
    iconSize: [44, 44],
    iconAnchor: [22, 22],
  });
}

function syncFields() {
  $("start-x").value = state.start[0];
  $("start-y").value = state.start[1];
  $("coordinates").value = state.points.map((p) => p.join(", ")).join("\n");
  updateButtons();
}

function drawMarkers() {
  for (const marker of state.markers) map.removeLayer(marker);
  state.markers = state.points.map((point, index) => {
    const marker = L.marker(latlng(point), {
      icon: waypointIcon(index + 1),
      draggable: !state.busy,
      keyboard: true,
      title: `地点 ${index + 1}`,
    }).addTo(map);
    const popup = document.createElement("div");
    popup.className = "popup-content";
    const label = document.createElement("div");
    label.textContent = `地点 ${index + 1}：${point.join(", ")} m`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "この地点を削除";
    remove.addEventListener("click", () => {
      if (state.busy) return;
      state.points.splice(index, 1);
      edited();
    });
    popup.append(label, remove);
    marker.bindPopup(popup);
    marker.on("dragend", () => {
      state.points[index] = xy(marker.getLatLng());
      edited();
    });
    return marker;
  });
  if (state.base) map.removeLayer(state.base);
  state.base = L.marker(latlng(state.start), {
    draggable: !state.busy,
    title: "基地（ドラッグで移動）",
    icon: L.divIcon({
      className: "base-shell",
      html: '<div class="base-icon"><span>基地</span></div>',
      iconSize: [44, 44],
      iconAnchor: [22, 22],
    }),
  })
    .addTo(map)
    .bindTooltip("基地");
  state.base.on("dragend", () => {
    state.start = xy(state.base.getLatLng());
    edited();
  });
}

function edited() {
  clearResults();
  drawMarkers();
  syncFields();
  status("地点を更新しました。「経路を計画」で計算してください。");
}

async function selectMap(id, imported = null) {
  busy(true);
  clearResults();
  status("地図を読み込んでいます…", "busy");
  state.info = null;
  try {
    const info = await api(`/api/maps/${id}`);
    map.fitBounds(info.bounds, { padding: [14, 14] });
    const image = L.imageOverlay(`/api/maps/${id}/image.png`, info.bounds, {
      interactive: false,
    });
    await new Promise((resolve, reject) => {
      image.once("load", resolve);
      image.once("error", () =>
        reject(new Error("地図の画像を読み込めませんでした")),
      );
      image.addTo(map);
    });
    if (state.image) map.removeLayer(state.image);
    state.image = image;
    state.info = info;
    $("map-size").textContent =
      `${info.shape[0] * info.resolution} × ${info.shape[1] * info.resolution} m`;
    $("file-attribution").textContent = info.attribution
      ? `選択中の地図の出典：${info.attribution}`
      : "";
    state.start = imported ? imported.start : info.start;
    state.points = imported ? imported.points : [];
    if (imported) $("method").value = imported.method || "terrain";
    $("map-select").value = id;
    $("map-name").textContent = $("map-select").selectedOptions[0].textContent;
    drawMarkers();
    syncFields();
    map.fitBounds(info.bounds, { padding: [14, 14] });
    status("地図をタップして地点を追加してください。最大12地点まで選べます。");
  } catch (error) {
    status(error.message, "error");
  } finally {
    busy(false);
  }
}

function validPair(value) {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    value.every((x) => typeof x === "number" && Number.isFinite(x))
  );
}

function readCoordinates() {
  const lines = $("coordinates")
    .value.trim()
    .split(/\n/)
    .filter((line) => line.trim());
  if (lines.length > 12) throw new Error("地点は12個までです。");
  return lines.map((line, i) => {
    const parts = line.trim().split(/[,，\s]+/);
    if (
      parts.length !== 2 ||
      parts.some((p) => p.trim() === "" || !Number.isFinite(Number(p)))
    )
      throw new Error(`${i + 1}行目を x, y の形式で入力してください。`);
    return parts.map(Number);
  });
}

function showResults(results) {
  clearResults();
  state.results = results;
  const orders = $("tour-orders");
  orders.replaceChildren();
  for (const result of results) {
    if (result.path.length)
      state.routes.push(
        L.polyline(result.path.map(latlng), {
          color: colors[result.method],
          weight: 4,
          opacity: 0.9,
          dashArray: result.method === "euclid" ? "9 7" : null,
        }).addTo(map),
      );
    const row = document.createElement("div");
    row.className = "tour-order";
    const tag = document.createElement("span");
    tag.className = `route-tag ${result.method}`;
    tag.textContent = names[result.method];
    const order = document.createElement("span");
    order.textContent =
      result.order.length > 1
        ? `基地 → ${result.order.slice(1).join(" → ")} → 基地`
        : "巡回できる地点がありません";
    row.append(tag, order);
    orders.append(row);
  }
  // In comparison mode markers display the terrain method's visit ranks.
  const primary = results.find((r) => r.method === "terrain") || results[0];
  state.markers.forEach((marker, index) => {
    const rank = primary.order.indexOf(index + 1);
    marker.setIcon(waypointIcon(rank > 0 ? rank : "×"));
    marker.bindTooltip(
      `入力 ${index + 1} ／ ${rank > 0 ? `巡回 ${rank}番目` : "受付外"}`,
    );
  });
  const fields = [
    ["全体の長さ", (r) => `${number(r.metrics.length_xy)} m`],
    ["登った高さ", (r) => `${number(r.metrics.climb)} m`],
    ["地形コストの平均", (r) => number(r.metrics.mean_cost, 4)],
    ["急斜面の長さ", (r) => `${number(r.metrics.steep_len)} m`],
    ["横傾き（95%値）", (r) => `${number(r.metrics.p95_roll)} °`],
    ["推定エネルギー", (r) => `${number(r.metrics.energy_kj)} kJ`],
    ["通行不可への接触", (r) => `${r.path_lethal_cells} マス`],
    ["行列の計算時間", (r) => `${number(r.timing.matrix_s, 3)} 秒`],
    ["順番の計算時間", (r) => `${number(r.timing.solve_s, 3)} 秒`],
    ["計画の総時間", (r) => `${number(r.timing.total_s, 3)} 秒`],
  ];
  const head = $("results-table").querySelector("thead");
  head.replaceChildren();
  const hr = document.createElement("tr");
  for (const text of ["指標", ...results.map((r) => names[r.method])]) {
    const th = document.createElement("th");
    th.textContent = text;
    th.scope = "col";
    hr.append(th);
  }
  head.append(hr);
  const body = $("results-table").querySelector("tbody");
  body.replaceChildren();
  for (const [name, format] of fields) {
    const row = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = name;
    row.append(th);
    for (const result of results) {
      const td = document.createElement("td");
      td.textContent = result.metrics ? format(result) : "—";
      row.append(td);
    }
    body.append(row);
  }
  const rejection = $("rejections");
  rejection.replaceChildren();
  for (const result of results) {
    if (!result.rejected.length) continue;
    const box = document.createElement("div");
    box.className = "rejected";
    const title = document.createElement("strong");
    title.textContent = `${names[result.method]}：受け付けなかった地点`;
    box.append(title);
    for (const item of result.rejected) {
      const p = document.createElement("p");
      p.textContent = `${item.index === 0 ? "基地" : `入力 ${item.index}`}：${item.reason}`;
      box.append(p);
    }
    rejection.append(box);
  }
  $("empty-results").hidden = true;
  $("result-content").hidden = false;
  updateButtons();
}

async function plan(compare) {
  if (state.busy || !state.info) return;
  stopPlayback();
  busy(true);
  const results = [];
  try {
    const methods = compare ? ["terrain", "euclid"] : [$("method").value];
    for (const method of methods) {
      status(
        `${names[method]}で計算中… 地点が多い場合は数十秒かかります。`,
        "busy",
      );
      results.push(
        await api("/api/plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            map_id: state.info.id,
            start: state.start,
            points: state.points,
            method,
          }),
        }),
      );
    }
    showResults(results);
    status(
      compare
        ? "2つの経路を表示しました。マーカーは地形を考慮した巡回順です。"
        : "計画が完了しました。マーカーの番号は巡回する順番です。",
    );
  } catch (error) {
    if (results.length) showResults(results);
    status(error.message, "error");
  } finally {
    busy(false);
  }
}

function play() {
  if (state.playback) {
    stopPlayback();
    return;
  }
  const result =
    state.results.find((r) => r.method === "terrain" && r.path.length > 1) ||
    state.results.find((r) => r.path.length > 1);
  if (!result) return;
  if (state.simulation) {
    playSimulation();
    return;
  }
  const path = result.path,
    cumulative = [0];
  for (let i = 1; i < path.length; i++)
    cumulative.push(
      cumulative[i - 1] +
        Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]),
    );
  if (!cumulative.at(-1)) return;
  state.robot = L.marker(latlng(path[0]), {
    interactive: false,
    zIndexOffset: 1000,
    icon: L.divIcon({
      className: "robot-shell",
      html: '<div class="robot-icon"></div>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    }),
  }).addTo(map);
  state.playback = { start: performance.now(), frame: null, segment: 0 };
  $("play").textContent = "■ 停止";
  function frame(now) {
    const run = state.playback;
    if (!run) return;
    const distance = ((now - run.start) / 1000) * 1.388;
    if (distance >= cumulative.at(-1)) {
      stopPlayback();
      status("再生が完了しました。基地に戻りました。");
      return;
    }
    while (
      run.segment < path.length - 2 &&
      cumulative[run.segment + 1] <= distance
    )
      run.segment++;
    const i = run.segment,
      span = cumulative[i + 1] - cumulative[i],
      f = span ? (distance - cumulative[i]) / span : 0;
    state.robot.setLatLng(
      latlng([
        path[i][0] + f * (path[i + 1][0] - path[i][0]),
        path[i][1] + f * (path[i + 1][1] - path[i][1]),
      ]),
    );
    run.frame = requestAnimationFrame(frame);
  }
  state.playback.frame = requestAnimationFrame(frame);
}

async function simulateDriving() {
  if (state.busy) return;
  const result =
    state.results.find((r) => r.method === "terrain" && r.path.length > 1) ||
    state.results.find((r) => r.path.length > 1);
  if (!result) return;
  clearSimulation();
  busy(true);
  status("Pure Pursuitで走行を計算しています…", "busy");
  try {
    const run = await api("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        map_id: state.info.id,
        path: result.path,
        lookahead_m: Number($("lookahead").value),
      }),
    });
    state.simulation = run;
    state.simulatedRoute = L.polyline(
      run.trajectory.map((p) => [p[2], p[1]]),
      { color: "#ce6b35", weight: 3, opacity: 0.95 },
    ).addTo(map);
    const box = $("simulation-result");
    box.replaceChildren();
    box.hidden = false;
    const title = document.createElement("h3");
    title.textContent = "走行シミュレーション（橙の軌跡）";
    box.append(title);
    const table = document.createElement("table");
    for (const [label, value] of [
      ["完走", run.completed ? "完走しました" : "時間内に完走しませんでした"],
      ["所要時間", `${number(run.elapsed_s)} 秒`],
      ["ずれの平均", `${number(run.deviation_mean_m, 3)} m`],
      ["ずれの最大", `${number(run.deviation_max_m, 3)} m`],
      ["通行不可への接触", `${run.path_lethal_cells} マス`],
      ["地図外の軌跡サンプル", `${run.out_of_bounds_samples} 個`],
    ]) {
      const row = document.createElement("tr"),
        th = document.createElement("th"),
        td = document.createElement("td");
      th.textContent = label;
      td.textContent = value;
      row.append(th, td);
      table.append(row);
    }
    box.append(table);
    status(
      run.path_lethal_cells || run.out_of_bounds_samples
        ? "走行で通行不可や地図外に接触しました。軌跡と結果を確認してください。"
        : "走行の計算が完了しました。「再生」で軌跡を時刻どおりに再生できます。",
      run.path_lethal_cells || run.out_of_bounds_samples ? "error" : "",
    );
  } catch (error) {
    status(error.message, "error");
  } finally {
    busy(false);
  }
}

function playSimulation() {
  const trace = state.simulation.trajectory;
  state.robot = L.marker([trace[0][2], trace[0][1]], {
    interactive: false,
    zIndexOffset: 1000,
    icon: L.divIcon({
      className: "robot-shell",
      html: '<div class="robot-icon"></div>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    }),
  }).addTo(map);
  state.playback = { start: performance.now(), segment: 0, frame: null };
  $("play").textContent = "■ 停止";
  function frame(now) {
    const run = state.playback;
    if (!run) return;
    const seconds = (now - run.start) / 1000;
    if (seconds >= trace[trace.length - 1][0]) {
      stopPlayback();
      status("走行軌跡の再生が完了しました。");
      return;
    }
    while (
      run.segment < trace.length - 2 &&
      trace[run.segment + 1][0] <= seconds
    )
      run.segment++;
    const a = trace[run.segment],
      b = trace[run.segment + 1],
      t = (seconds - a[0]) / (b[0] - a[0]);
    state.robot.setLatLng([a[2] + t * (b[2] - a[2]), a[1] + t * (b[1] - a[1])]);
    run.frame = requestAnimationFrame(frame);
  }
  state.playback.frame = requestAnimationFrame(frame);
}

$("simulate").addEventListener("click", simulateDriving);
$("lookahead").addEventListener("input", () => {
  clearSimulation();
  $("lookahead-value").textContent =
    `${Number($("lookahead").value).toFixed(1)} m`;
});

map.on("click", (event) => {
  if (state.busy || !state.info) return;
  if (state.points.length >= 12) {
    status("地点は12個までです。既存の地点を削除してください。", "error");
    return;
  }
  state.points.push(xy(event.latlng));
  edited();
});
map.on("mousemove", (event) => {
  $("cursor-position").textContent =
    `x ${number(event.latlng.lng, 1)} / y ${number(event.latlng.lat, 1)} m`;
});
$("map-select").addEventListener("change", () =>
  selectMap($("map-select").value),
);
$("fit-map").addEventListener("click", () => {
  if (state.info) map.fitBounds(state.info.bounds, { padding: [14, 14] });
});
$("apply-points").addEventListener("click", () => {
  try {
    state.points = readCoordinates();
    edited();
  } catch (error) {
    status(error.message, "error");
  }
});
$("apply-start").addEventListener("click", () => {
  if (!state.info) return;
  const raw = [$("start-x").value, $("start-y").value],
    point = raw.map(Number);
  if (raw.some((v) => !v.trim()) || !validPair(point)) {
    status("基地の x, y を数値で入力してください。", "error");
    return;
  }
  state.start = point;
  edited();
});
$("clear-points").addEventListener("click", () => {
  state.points = [];
  edited();
});
$("plan").addEventListener("click", () => plan(false));
$("compare").addEventListener("click", () => plan(true));
$("play").addEventListener("click", play);
$("save-points").addEventListener("click", () => {
  if (!state.info) return;
  const blob = new Blob(
    [
      JSON.stringify(
        {
          version: 1,
          map_id: state.info.id,
          start: state.start,
          points: state.points,
          method: $("method").value,
        },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "巡回地点.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
});
$("load-points").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file || state.busy) return;
  busy(true);
  try {
    if (file.size > 100000)
      throw new Error("地点のJSONは100KB以下にしてください。");
    const data = JSON.parse(await file.text());
    if (
      !data ||
      ![...$("map-select").options].some((o) => o.value === data.map_id) ||
      !validPair(data.start) ||
      !Array.isArray(data.points) ||
      data.points.length > 12 ||
      !data.points.every(validPair) ||
      ![undefined, "terrain", "euclid"].includes(data.method)
    )
      throw new Error("地図・基地・地点の形式を確認してください。");
    await selectMap(data.map_id, data);
  } catch (error) {
    status(`読み込み失敗：${error.message}`, "error");
  } finally {
    busy(false);
  }
});

async function init() {
  busy(true);
  try {
    const maps = await api("/api/maps");
    $("map-select").replaceChildren();
    for (const entry of maps) {
      const option = document.createElement("option");
      option.value = entry.id;
      option.textContent = entry.name;
      $("map-select").append(option);
    }
    await selectMap(maps[0].id);
  } catch (error) {
    status(error.message, "error");
  }
}
new ResizeObserver(() => map.invalidateSize()).observe($("map"));
init();
