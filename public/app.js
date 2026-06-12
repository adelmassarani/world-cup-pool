const REFRESH_INTERVAL_MS = 60 * 1000;

async function loadStandings() {
  try {
    const res = await fetch("/api/leaderboard");
    const data = await res.json();
    renderLeaderboard(data.players);
    renderSquads(data.players);
    renderLastUpdated(data.lastUpdated, data.error);
  } catch (err) {
    document.getElementById("lastUpdated").textContent =
      "Couldn't load data: " + err.message;
  }
}

function renderLastUpdated(timestamp, error) {
  const el = document.getElementById("lastUpdated");
  const date = new Date(timestamp * 1000);
  let text = "Last updated: " + date.toLocaleTimeString();
  if (error) {
    text += " (using cached data — FIFA API error: " + error + ")";
  }
  el.textContent = text;
}

function formatPoints(points) {
  return points % 1 === 0 ? points.toFixed(0) : points.toFixed(1);
}

function renderLeaderboard(players) {
  const tbody = document.querySelector("#leaderboard-table tbody");
  tbody.innerHTML = "";
  players.forEach((p, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${p.name}</td>
      <td>${formatPoints(p.points)}</td>
      <td>${p.w}</td>
      <td>${p.t}</td>
      <td>${p.l}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderSquads(players) {
  const container = document.getElementById("squad-cards");
  container.innerHTML = "";
  players.forEach((p) => {
    const card = document.createElement("div");
    card.className = "squad-card";

    const teamItems = p.squad
      .map(
        (team) => `
        <li class="${team.eliminated ? "eliminated" : ""}">
          <span class="team-name"><span class="flag">${team.flag}</span> ${team.name}${team.eliminated ? ' <span class="out-badge">OUT</span>' : ""}</span>
          <span class="record"><span class="w">${team.w}W</span> <span class="t">${team.t}T</span> <span class="l">${team.l}L</span></span>
        </li>`
      )
      .join("");

    card.innerHTML = `
      <h3>${p.name} <span class="points">${formatPoints(p.points)} pts</span></h3>
      <ul>${teamItems}</ul>
    `;
    container.appendChild(card);
  });
}

loadStandings();
setInterval(loadStandings, REFRESH_INTERVAL_MS);
