
const byId = id => document.getElementById(id);

const esc = value => String(value ?? "—");

async function registryRequest(
  endpoint,
  options = {}
) {
  const response = await fetch(endpoint, options);
  const json = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof json.detail === "string"
        ? json.detail
        : "Registry request failed"
    );
  }

  return json;
}

async function refreshRegistry() {
  const target = byId("registry-entries");

  byId("registry-message").textContent =
    "Loading model versions…";

  try {
    const status = await registryRequest(
      "/registry/status"
    );

    byId("registry-active").textContent =
      status.active_version;

    target.replaceChildren();

    for (const candidate of status.versions) {
      const block = document.createElement("article");
      block.className = "registry-entry";

      const heading = document.createElement("h3");

      heading.textContent =
        candidate.version +
        (candidate.active ? " · ACTIVE" : "");

      const details = document.createElement("p");
      const evaluation = candidate.evaluation;

      details.textContent = evaluation
        ? (
          `AP: champion ${
            (
              evaluation.champion.average_precision * 100
            ).toFixed(1)
          }%, challenger ${
            (
              evaluation.challenger.average_precision * 100
            ).toFixed(1)
          }%; review eligible: ${
            evaluation.approved_for_review
              ? "yes"
              : "no"
          }`
        )
        : (
          `Kind: ${esc(candidate.kind)}. ` +
          "No recorded challenger evaluation."
        );

      block.append(heading, details);
      target.appendChild(block);
    }

    byId("registry-message").textContent =
      "Registry loaded. Promotion requires an explicit confirmation phrase.";

  } catch (error) {
    byId("registry-message").textContent =
      error.message;
  }
}

async function changeModel(operation) {
  const version = byId(
    "registry-version"
  ).value.trim();

  const confirmation = byId(
    "registry-confirm"
  ).value.trim();

  const text = byId("registry-message");

  if (!version) {
    text.textContent = "Enter a version.";
    return;
  }

  if (confirmation !== `ACTIVATE ${version}`) {
    text.textContent =
      `Confirmation must be: ACTIVATE ${version}`;
    return;
  }

  if (!window.confirm(
    `Confirm ${operation} to ${version}? ` +
    "This changes live inference."
  )) {
    return;
  }

  text.textContent = "Validating model artifacts…";

  try {
    
    const adminKey = window.prompt(
    "Enter the DriftLab administrator key:"
    );

    if (!adminKey) {
    text.textContent = "Operation cancelled.";
    return;
    }

    const result = await registryRequest(
    `/registry/${operation}`,
    {
        method: "POST",
        headers: {
        "Content-Type": "application/json",
        "X-DriftLab-Admin-Key": adminKey
        },
        body: JSON.stringify({
        version,
        confirmation
        })
    }
    );


    text.textContent =
      `Active version: ${result.active_version}. ` +
      "Reload the page to refresh all model labels.";

    await refreshRegistry();

  } catch (error) {
    text.textContent = error.message;
  }
}

byId("registry-refresh").addEventListener(
  "click",
  refreshRegistry
);

byId("registry-promote").addEventListener(
  "click",
  () => changeModel("promote")
);

byId("registry-rollback").addEventListener(
  "click",
  () => changeModel("rollback")
);

refreshRegistry();
