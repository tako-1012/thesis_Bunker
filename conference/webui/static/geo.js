"use strict";

// Geographic tools are optional; planning and robot transport keep map metres.
(() => {
  let mapId = null, signature = "", renderVersion = 0, cursorVersion = 0, cursorTimer;
  const controls = ["geo-coordinates", "apply-geo", "load-geo", "save-geo-json", "save-geo-txt"];
  async function convert(direction, points, id = state.info.id) {
    return api(`/api/geo/${direction}`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({map_id: id, points}),
    });
  }
  const lines = (points) => points.map((p) => `${p.lat.toFixed(9)},${p.lng.toFixed(9)}`).join("\n");

  async function update() {
    const available = Boolean(state.info?.geo);
    $("geo-tools").hidden = !available;
    $("cursor-latlon").hidden = !available;
    for (const id of controls) $(id).disabled = state.busy || !available;
    for (const id of ["save-geo-json", "save-geo-txt"])
      $(id).disabled ||= !state.points.length;
    if (mapId !== state.info?.id) {
      mapId = state.info?.id;
      signature = "";
      renderVersion++;
      cursorVersion++;
      clearTimeout(cursorTimer);
      $("cursor-latlon").textContent = "緯度・経度：地図を指すと表示";
    }
    const next = JSON.stringify([state.info?.id, state.points]);
    if (!available || next === signature) return;
    signature = next;
    const version = ++renderVersion;
    if (!state.points.length) { $("geo-coordinates").value = ""; return; }
    try {
      const response = await convert("to-latlon", state.points);
      if (version === renderVersion && next === JSON.stringify([state.info?.id, state.points]))
        $("geo-coordinates").value = lines(response.points);
    } catch (error) {
      if (version === renderVersion) status(error.message, "error");
    }
  }

  function pointer(event) {
    if (!state.info?.geo) return;
    const id = state.info.id, point = xy(event.latlng), version = ++cursorVersion;
    clearTimeout(cursorTimer);
    cursorTimer = setTimeout(async () => {
      try {
        const result = await convert("to-latlon", [point], id);
        if (version !== cursorVersion || state.info?.id !== id) return;
        const p = result.points[0];
        $("cursor-latlon").textContent = `緯度 ${p.lat.toFixed(8)} / 経度 ${p.lng.toFixed(8)}°`;
      } catch (_) {
        if (version === cursorVersion) $("cursor-latlon").textContent = "緯度・経度を取得できません";
      }
    }, 90);
  }

  function latLng(value) {
    const pair = Array.isArray(value) ? value : [value?.lat, value?.lng ?? value?.lon];
    if (pair.length !== 2 || pair.some((v) => v == null || (typeof v === "string" && !v.trim())))
      throw new Error("1地点ずつ緯度,経度を指定してください。");
    const [lat, lng] = pair.map(Number);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) throw new Error("緯度・経度は有限の数値で指定してください。");
    return {lat, lng};
  }

  function parse(text) {
    text = text.trim();
    if (!text) throw new Error("緯度・経度を入力してください。");
    let data;
    if (/^[\[{]/.test(text)) {
      data = JSON.parse(text);
      if (Array.isArray(data)) data = {points: data};
      if (!Array.isArray(data.points) && Array.isArray(data.lat) && Array.isArray(data.lng)) {
        if (data.lat.length !== data.lng.length) throw new Error("latとlngの要素数を揃えてください。");
        data.points = data.lat.map((lat, i) => ({lat, lng: data.lng[i]}));
      }
    } else {
      const rows = text.split(/\r?\n/).map((r) => r.trim()).filter(Boolean);
      if (/^lat\s*,\s*(lng|lon)$/i.test(rows[0])) rows.shift();
      data = {points: rows.map((r) => r.replaceAll("，", ",").split(/[,\s]+/))};
    }
    if (!Array.isArray(data.points) || !data.points.length || data.points.length > 12)
      throw new Error("地点は1〜12個で指定してください。");
    return {...data, points: data.points.map(latLng), start: data.start ? latLng(data.start) : null};
  }

  async function importGeo(text) {
    if (state.busy || !state.info?.geo) return;
    busy(true);
    try {
      const data = parse(text), targetId = data.map_id || state.info.id;
      if (data.method && !["terrain", "euclid"].includes(data.method)) throw new Error("巡回方法が不正です。");
      const info = targetId === state.info.id ? state.info : await api(`/api/maps/${targetId}`);
      if (!info.geo) throw new Error("この地図には位置情報がありません。");
      const input = data.start ? [data.start, ...data.points] : data.points;
      const result = await convert("to-map", input, targetId);
      const metres = result.points.map((p) => p.map((v) => Number(v.toFixed(3))));
      const points = data.start ? metres.slice(1) : metres;
      const start = data.start ? metres[0] : (targetId === state.info.id ? state.start : info.start);
      if (targetId !== state.info.id) await selectMap(targetId, {start, points, method: data.method || "terrain"});
      else { state.start = start; state.points = points; if (data.method) $("method").value = data.method; edited(); }
      status("緯度・経度から地点を読み込みました。");
    } catch (error) { status(error.message, "error"); }
    finally { busy(false); }
  }

  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], {type}));
    const link = document.createElement("a"); link.href = url; link.download = name;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function save(format) {
    if (state.busy || !state.info?.geo || !state.points.length) return;
    busy(true);
    try {
      const result = await convert("to-latlon", [state.start, ...state.points]);
      const points = result.points.slice(1);
      if (format === "json") download("waypoints_latlng.json", JSON.stringify({format: "latlng", map_id: state.info.id,
        start: result.points[0], points, method: $("method").value}, null, 2)+"\n", "application/json");
      else download("waypoints_latlng.txt", lines(points)+"\n", "text/plain");
      status(`緯度・経度を${format === "json" ? "JSON" : "lat,lngのテキスト"}で書き出しました。`);
    } catch (error) { status(error.message, "error"); }
    finally { busy(false); }
  }
  $("apply-geo").addEventListener("click", () => importGeo($("geo-coordinates").value));
  $("load-geo").addEventListener("click", () => $("geo-file-input").click());
  $("geo-file-input").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (file) { try { await importGeo(await file.text()); } catch (error) { status(error.message, "error"); } }
    event.target.value = "";
  });
  $("save-geo-json").addEventListener("click", () => save("json"));
  $("save-geo-txt").addEventListener("click", () => save("txt"));
  map.on("mousemove", pointer); map.on("click", pointer);
  document.addEventListener("bunker:update", update);
  update();
})();
