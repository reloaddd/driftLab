
const $ = id => document.getElementById(id);

const pct = value =>
  Number.isFinite(Number(value))
    ? `${(Number(value) * 100).toFixed(2)}%`
    : "—";

async function request(url, options = {}) {
  const response = await fetch(url, options);
  let data;

  try {
    data = await response.json();
  } catch {
    throw Error(`HTTP ${response.status}: Invalid API response`);
  }

  if (!response.ok) {
    throw Error(
      data.detail
        ? JSON.stringify(data.detail)
        : `HTTP ${response.status}`
    );
  }

  return data;
}

function message(id, text, error = false) {
  const element = $(id);
  element.textContent = text;
  element.classList.toggle("error", error);
}

function textCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
}

function show(tab) {
  document.querySelectorAll(".panel").forEach(panel => {
    panel.hidden = panel.id !== tab;
  });

  document.querySelectorAll(".tab").forEach(button => {
    button.classList.toggle(
      "active",
      button.dataset.target === tab
    );
  });

  if (tab === "history") loadHistory();
  if (tab === "performance") loadPerformance();
  if (tab === "drift") loadDriftHistory();
}

document.querySelectorAll(".tab").forEach(button => {
  button.addEventListener("click", () => show(button.dataset.target));
});

// Decorative SVG motif

const rosette = $("rosette");

for (let i = 0; i < 18; i++) {
  const ellipse = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "ellipse"
  );

  const attributes = {
    cx: 110,
    cy: 110,
    rx: 33,
    ry: 86,
    fill: "none",
    stroke: "currentColor",
    "stroke-width": ".44",
    transform: `rotate(${i * 10} 110 110)`
  };

  for (const [key, value] of Object.entries(attributes)) {
    ellipse.setAttribute(key, value);
  }

  rosette.appendChild(ellipse);
}

// Service health

async function health() {
  try {
    const data = await request("/health");
    const ready = data.status === "ready";

    $("api-dot").className =
      "status-dot " + (ready ? "ok" : "fail");

    $("api-status").textContent = ready
      ? "MODEL SERVICE READY"
      : "MODEL NOT AVAILABLE";

    $("hero-version").textContent =
      "VERSION " + (data.model_version || "—");

    document.querySelectorAll(".model-version").forEach(el => {
      el.textContent = data.model_version || "—";
    });
  } catch {
    $("api-dot").className = "status-dot fail";
    $("api-status").textContent = "API CONNECTION UNAVAILABLE";
  }
}

// Machine prediction

$("predict-form").addEventListener("submit", async event => {
  event.preventDefault();

  const button = event.submitter;
  button.disabled = true;

  message("predict-message", "Running model inference…");

  const form = new FormData(event.target);

  const reading = {
    machine_type: form.get("machine_type")
  };

  for (const key of [
    "air_temperature",
    "process_temperature",
    "rotational_speed",
    "torque",
    "tool_wear"
  ]) {
    reading[key] = Number(form.get(key));
  }

  try {
    const result = await request("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reading)
    });

    $("result-empty").hidden = true;
    $("result-full").hidden = false;

    $("pred-percent").textContent =
      pct(result.failure_probability);

    $("pred-bar").style.width =
      `${Math.max(0, Math.min(100, result.failure_probability * 100))}%`;

    $("pred-class").textContent =
      result.predicted_failure
        ? "Failure flagged"
        : "No failure flagged";

    $("pred-risk").textContent =
      `${result.risk_level || "—"} RISK`;

    $("pred-threshold").textContent = pct(result.threshold);
    $("pred-version").textContent = result.model_version;
    $("pred-id").textContent = result.prediction_id || "—";

    message("predict-message", "Prediction recorded successfully.");
  } catch (error) {
    message("predict-message", error.message, true);
  } finally {
    button.disabled = false;
  }
});

// Prediction history

async function loadHistory() {
  message("history-message", "Loading…");

  try {
    const records = await request("/monitor/recent?limit=100");

    $("history-count").textContent = `${records.length} RECORDS`;
    $("history-body").replaceChildren();

    for (const record of records) {
      const row = document.createElement("tr");
      const reading = record.reading || {};

      const values = [
        record.recorded_at
          ? new Date(record.recorded_at).toLocaleString()
          : "—",
        reading.Type || "—",
        pct(record.probability),
        record.prediction === 1 ? "Failure" : "Normal",
        record.outcome == null
          ? "Pending"
          : record.outcome === 1
            ? "Failure"
            : "Normal",
        record.model_version || "—"
      ];

      values.forEach(value => textCell(row, value));
      $("history-body").appendChild(row);
    }

    if (!records.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");

      cell.colSpan = 6;
      cell.textContent = "No predictions stored yet.";
      row.appendChild(cell);

      $("history-body").appendChild(row);
    }

    message("history-message", "");
  } catch (error) {
    message("history-message", error.message, true);
  }
}

$("refresh-history").addEventListener("click", loadHistory);

// Performance reporting

async function loadPerformance() {
  message("performance-message", "Loading…");

  try {
    const data = await request("/monitor/performance");

    $("metric-labeled").textContent = data.labeled_count ?? "—";

    $("metric-precision").textContent =
      data.status === "ok" ? pct(data.precision) : "—";

    $("metric-recall").textContent =
      data.status === "ok" ? pct(data.recall) : "—";

    $("metric-f1").textContent =
      data.status === "ok" ? pct(data.f1) : "—";

    if (data.status === "insufficient_labels") {
      message(
        "performance-message",
        `Insufficient labels: ${data.labeled_count} / ${data.required} recorded outcomes.`
      );
    } else if (data.status === "ok") {
      const ap = data.average_precision == null
        ? "Unavailable"
        : pct(data.average_precision);

      message(
        "performance-message",
        `Average precision: ${ap}. Metrics summarize stored labelled records.`
      );
    } else {
      message("performance-message", JSON.stringify(data));
    }
  } catch (error) {
    message("performance-message", error.message, true);
  }
}

$("refresh-performance").addEventListener("click", loadPerformance);

// CSV ingestion

const mapping = {
  "Type": "machine_type",
  "Air temperature [K]": "air_temperature",
  "Process temperature [K]": "process_temperature",
  "Rotational speed [rpm]": "rotational_speed",
  "Torque [Nm]": "torque",
  "Tool wear [min]": "tool_wear"
};

function parseCSV(input) {
  const records = [];
  let row = [];
  let value = "";
  let quoted = false;

  for (let i = 0; i < input.length; i++) {
    const char = input[i];

    if (char === '"') {
      if (quoted && input[i + 1] === '"') {
        value += '"';
        i++;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      row.push(value);
      value = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && input[i + 1] === "\n") i++;

      row.push(value);
      value = "";

      if (row.some(item => item.trim())) {
        records.push(row);
      }

      row = [];
    } else {
      value += char;
    }
  }

  if (quoted) throw Error("Unclosed quoted field in CSV");

  if (value || row.length) {
    row.push(value);
    records.push(row);
  }

  if (records.length < 2) {
    throw Error("CSV has no data rows");
  }

  const headers = records.shift().map(
    header => header.trim().replace(/^\uFEFF/, "")
  );

  return records.map((cells, index) => {
    const object = {};

    headers.forEach((header, j) => {
      object[header] = cells[j] ?? "";
    });

    const reading = {};

    for (const [csvColumn, field] of Object.entries(mapping)) {
      const raw = object[csvColumn] ?? object[field];

      if (raw === undefined) {
        throw Error(`Missing CSV column: ${csvColumn}`);
      }

      reading[field] = field === "machine_type"
        ? raw.trim()
        : Number(raw);

      const valid = field === "machine_type"
        ? ["L", "M", "H"].includes(reading[field])
        : raw.trim() !== "" && Number.isFinite(reading[field]);

      if (!valid) {
        throw Error(`Invalid ${csvColumn} in row ${index + 2}`);
      }
    }

    return reading;
  });
}

// SVG chart helpers

const driftColumns = [
  ["air_temperature", "Air temperature [K]"],
  ["process_temperature", "Process temperature [K]"],
  ["rotational_speed", "Rotational speed [rpm]"],
  ["torque", "Torque [Nm]"],
  ["tool_wear", "Tool wear [min]"],
  ["machine_type", "Type"]
];

let driftState = null;

function chartNode(tag, attributes = {}, text = "") {
  const element = document.createElementNS(
    "http://www.w3.org/2000/svg",
    tag
  );

  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, String(value));
  }

  if (text) element.textContent = text;
  return element;
}

function prettyTick(value) {
  if (!Number.isFinite(value)) return "—";

  return Number(value.toPrecision(4)).toLocaleString("en-US", {
    maximumFractionDigits: 3
  });
}

function binsFor(data, min, max, n = 16) {
  const counts = Array(n).fill(0);
  const width = max - min || 1;

  for (const value of data) {
    const index = Math.max(
      0,
      Math.min(n - 1, Math.floor((value - min) / width * n))
    );

    counts[index]++;
  }

  return counts;
}

// Feature distribution chart

function renderDriftChart(key) {
  if (!driftState) return;

  const { reference, current, report } = driftState;
  const feature = driftColumns.find(item => item[0] === key);

  if (!feature) return;

  const svg = chartNode("svg", {
    viewBox: "0 0 780 325",
    role: "img",
    "aria-label": `Reference and current distributions for ${feature[1]}`
  });

  const group = chartNode("g");
  svg.appendChild(group);

  const left = 50;
  const top = 18;
  const plotWidth = 703;
  const plotHeight = 236;

  let valuesRef = [];
  let valuesCur = [];
  let labels = [];

  if (key === "machine_type") {
    labels = ["L", "M", "H"];

    valuesRef = labels.map(
      type => reference.filter(r => r.machine_type === type).length / reference.length
    );

    valuesCur = labels.map(
      type => current.filter(r => r.machine_type === type).length / current.length
    );
  } else {
    const a = reference.map(row => row[key]);
    const b = current.map(row => row[key]);

    const min = Math.min(...a, ...b);
    const max = Math.max(...a, ...b);
    const width = max - min || 1;

    valuesRef = binsFor(a, min, max).map(v => v / a.length);
    valuesCur = binsFor(b, min, max).map(v => v / b.length);

    labels = [
      prettyTick(min),
      prettyTick(min + width / 2),
      prettyTick(max)
    ];
  }

  const n = valuesRef.length;
  const topValue = Math.max(.01, ...valuesRef, ...valuesCur) * 1.13;

  for (let i = 0; i <= 4; i++) {
    const y = top + plotHeight * (1 - i / 4);

    group.appendChild(chartNode("line", {
      x1: left, y1: y,
      x2: left + plotWidth, y2: y,
      stroke: "#d9d5cb",
      "stroke-width": 1
    }));

    group.appendChild(chartNode("text", {
      x: left - 8, y: y + 4,
      "text-anchor": "end"
    }, `${(topValue * i / 4 * 100).toFixed(0)}%`));
  }

  const space = plotWidth / n;
  const barWidth = Math.min(29, space * .39);

  for (let i = 0; i < n; i++) {
    const x = left + i * space + space * .09;

    for (const [j, values, color] of [
      [0, valuesRef, "#6c7968"],
      [1, valuesCur, "#b3855e"]
    ]) {
      const value = values[i];
      const height = value / topValue * plotHeight;

      const rect = chartNode("rect", {
        x: x + j * (barWidth + 2),
        y: top + plotHeight - height,
        width: barWidth,
        height,
        fill: color,
        opacity: .88,
        rx: 1
      });

      rect.appendChild(chartNode(
        "title",
        {},
        `${j === 0 ? "Reference" : "Current"}: ${(value * 100).toFixed(2)}%`
      ));

      group.appendChild(rect);
    }
  }

  if (key === "machine_type") {
    labels.forEach((label, i) => {
      group.appendChild(chartNode("text", {
        x: left + (i + .5) * space,
        y: top + plotHeight + 27,
        "text-anchor": "middle"
      }, label));
    });
  } else {
    [0, .5, 1].forEach((fraction, i) => {
      group.appendChild(chartNode("text", {
        x: left + fraction * plotWidth,
        y: top + plotHeight + 27,
        "text-anchor": i === 0
          ? "start"
          : i === 2
            ? "end"
            : "middle"
      }, labels[i]));
    });
  }

  $("drift-chart").replaceChildren(svg);

  const metric = report.features?.[feature[1]];

  $("drift-chart-note").textContent =
    `${feature[1]} · ${metric?.metric === "psi" ? "PSI" : "Total variation"}: ` +
    `${typeof metric?.value === "number" ? metric.value.toFixed(4) : "unavailable"}. ` +
    "Chart bins are visual and do not necessarily match backend PSI bins.";

  document.querySelectorAll("#drift-features-body tr").forEach(row => {
    row.classList.toggle("selected", row.dataset.feature === key);
  });
}

// Current drift report

function renderDriftReport(data, reference, current, simulated) {
  const result = $("drift-result");

  result.className = "";
  result.replaceChildren();

  const label = document.createElement("p");
  label.className = "eyebrow";

  label.textContent =
    `${data.reference_size} REFERENCE / ${data.current_size} CURRENT` +
    (simulated ? " / SYNTHETIC +15 NM" : "");

  const summary = document.createElement("p");

  summary.textContent = data.flagged_features?.length
    ? `${data.flagged_features.length} of 6 features flagged for distribution shift.`
    : "No feature exceeded its configured drift threshold.";

  const note = document.createElement("p");
  note.className = "footnote";

  note.textContent =
    data.notice ||
    "A drift flag does not establish loss of predictive accuracy.";

  result.append(label, summary, note);

  $("drift-visuals").hidden = false;

  $("drift-flagged").textContent =
    `${data.flagged_features?.length ?? 0} / 6`;

  $("drift-ref-size").textContent =
    Number(data.reference_size).toLocaleString();

  $("drift-current-size").textContent =
    Number(data.current_size).toLocaleString();

  const selector = $("drift-feature");
  const body = $("drift-features-body");

  selector.replaceChildren();
  body.replaceChildren();

  for (const [key, backendName] of driftColumns) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = backendName;
    selector.appendChild(option);

    const metric = data.features?.[backendName];
    if (!metric) continue;

    const row = document.createElement("tr");
    row.dataset.feature = key;

    textCell(row, backendName);
    textCell(row, metric.metric === "psi" ? "PSI" : "Total variation");
    textCell(row, typeof metric.value === "number"
      ? metric.value.toFixed(4)
      : "N/A");

    const cell = document.createElement("td");
    const pill = document.createElement("span");

    pill.className =
      "drift-pill " +
      (metric.drift === true
        ? "flagged"
        : metric.drift === false
          ? "stable"
          : "unavailable");

    pill.textContent =
      metric.drift === true
        ? "FLAGGED"
        : metric.drift === false
          ? "WITHIN LIMIT"
          : "UNAVAILABLE";

    cell.appendChild(pill);
    row.appendChild(cell);
    body.appendChild(row);

    row.addEventListener("click", () => {
      selector.value = key;
      renderDriftChart(key);
    });
  }

  driftState = { report: data, reference, current };

  selector.value = "torque";
  renderDriftChart("torque");
}

$("drift-feature").addEventListener("change", event => {
  renderDriftChart(event.target.value);
});

// Drift API submission

$("run-drift").addEventListener("click", async () => {
  const referenceFile = $("reference-file").files[0];
  const currentFile = $("current-file").files[0];

  if (!referenceFile || !currentFile) {
    message("drift-message", "Choose both CSV files first.", true);
    return;
  }

  const button = $("run-drift");
  button.disabled = true;

  $("drift-visuals").hidden = true;
  driftState = null;

  message(
    "drift-message",
    "Validating CSV and contacting drift monitoring service…"
  );

  try {
    const reference = parseCSV(await referenceFile.text());
    const current = parseCSV(await currentFile.text());

    if (reference.length < 30 || current.length < 30) {
      throw Error("Each dataset must contain at least 30 readings.");
    }

    const simulated = $("simulate-shift").checked;

    if (simulated) {
      current.forEach(row => {
        row.torque += 15;
      });
    }

    const report = await request("/monitor/drift", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reference,
        current,
        simulated
      })
    });

    renderDriftReport(report, reference, current, simulated);
    await loadDriftHistory();

    message(
      "drift-message",
      "Completed. Drift is not proof of reduced model accuracy."
    );
  } catch (error) {
    message("drift-message", error.message, true);
  } finally {
    button.disabled = false;
  }
});

// Day 7: persisted drift-check history

async function loadDriftHistory() {
  const status = $("drift-history-message");
  const body = $("drift-history-body");
  const target = $("drift-timeline");

  status.classList.remove("error");
  status.textContent = "Loading saved checks…";

  try {
    const rows = await request("/monitor/drift/history?limit=100");

    body.replaceChildren();
    target.replaceChildren();

    $("drift-history-count").textContent =
      `${rows.length} SAVED CHECKS`;

    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");

      cell.colSpan = 5;
      cell.textContent = "No comparisons recorded yet.";

      row.appendChild(cell);
      body.appendChild(row);

      status.textContent = "Run a comparison to begin the timeline.";
      return;
    }

    // Table

    for (const record of rows) {
      const row = document.createElement("tr");

      const values = [
        new Date(record.recorded_at).toLocaleString(),
        record.model_version,
        record.simulated ? "SIMULATION" : "UNVERIFIED / UPLOADED",
        String(record.flagged_count),
        `${record.reference_size} / ${record.current_size}`
      ];

      values.forEach(value => textCell(row, value));
      body.appendChild(row);
    }

    // Timeline chart

    const ordered = [...rows].reverse();

    const width = 800;
    const height = 205;

    const left = 37;
    const right = 18;
    const top = 19;
    const bottom = 37;

    const baseline = height - bottom;
    const plotWidth = width - left - right;
    const plotHeight = baseline - top;

    const svg = chartNode("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-label": "Number of flagged features for each recorded drift check"
    });

    // Y-axis grid: number of flagged features

    for (let count = 0; count <= 6; count += 2) {
      const y = baseline - count / 6 * plotHeight;

      svg.appendChild(chartNode("line", {
        x1: left,
        y1: y,
        x2: width - right,
        y2: y,
        stroke: "#d9d5cb"
      }));

      svg.appendChild(chartNode("text", {
        x: left - 7,
        y: y + 4,
        "text-anchor": "end"
      }, String(count)));
    }

    const points = ordered.map((record, index) => {
      const x = left + (
        ordered.length === 1
          ? plotWidth / 2
          : index / (ordered.length - 1) * plotWidth
      );

      const flagged = Math.max(
        0,
        Math.min(6, record.flagged_count)
      );

      return {
        x,
        y: baseline - flagged / 6 * plotHeight,
        record
      };
    });

    // Connect check results chronologically

    if (points.length > 1) {
      svg.appendChild(chartNode("polyline", {
        points: points.map(p => `${p.x},${p.y}`).join(" "),
        fill: "none",
        stroke: "#6c7968",
        "stroke-width": 2
      }));
    }

    // Markers identify simulated checks

    for (const point of points) {
      const circle = chartNode("circle", {
        cx: point.x,
        cy: point.y,
        r: 5,
        fill: point.record.simulated
          ? "#b3855e"
          : "#6c7968"
      });

      circle.appendChild(chartNode(
        "title",
        {},
        `${point.record.recorded_at} • ${point.record.flagged_count} flags • ` +
        (point.record.simulated ? "simulation" : "uploaded data")
      ));

      svg.appendChild(circle);
    }

    svg.appendChild(chartNode("text", {
      x: left,
      y: height - 9
    }, "EARLIER"));

    svg.appendChild(chartNode("text", {
      x: width - right,
      y: height - 9,
      "text-anchor": "end"
    }, "LATEST"));

    target.appendChild(svg);

    status.textContent =
      "Amber points indicate declared simulations. " +
      "Other uploads are not independently verified as production data.";
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  }
}

$("refresh-drift-history").addEventListener(
  "click",
  loadDriftHistory
);

// Start the frontend

health();
