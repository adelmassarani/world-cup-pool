const REFRESH_INTERVAL_MS = 60 * 1000;

const expandedTeams = new Set();

async function loadStandings() {
  try {
    const res = await fetch("/api/leaderboard");
    const data = await res.json();
    renderLeaderboard(data.players);
    renderSquads(data.players);
    renderBanner(data.liveMatches, data.nextMatch);
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

function formatMatchDate(iso) {
  if (!iso) return "TBD";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderMatchup(match) {
  return `<span class="banner-team"><span class="flag">${match.home.flag}</span> ${match.home.name}</span>
    <span class="banner-score">${
      match.home.score !== null && match.home.score !== undefined
        ? `${match.home.score} - ${match.away.score}`
        : "vs"
    }</span>
    <span class="banner-team"><span class="flag">${match.away.flag}</span> ${match.away.name}</span>`;
}

function renderBanner(liveMatches, nextMatch) {
  const el = document.getElementById("matchBanner");
  if (liveMatches && liveMatches.length > 0) {
    el.innerHTML = liveMatches
      .map(
        (match) => `
        <div class="banner-row banner-live">
          <span class="live-indicator"><span class="live-dot"></span> LIVE</span>
          ${renderMatchup(match)}
          <span class="banner-stage">${match.stage}</span>
        </div>`
      )
      .join("");
    return;
  }

  if (nextMatch) {
    el.innerHTML = `
      <div class="banner-row banner-upcoming">
        <span class="banner-label">Up Next</span>
        ${renderMatchup(nextMatch)}
        <span class="banner-stage">${nextMatch.stage} · ${formatMatchDate(nextMatch.date)}</span>
      </div>`;
    return;
  }

  el.innerHTML = "";
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

function renderSchedule(team) {
  if (!team.schedule || team.schedule.length === 0) {
    return `<div class="schedule"><p class="schedule-empty">No matches found.</p></div>`;
  }

  const rows = team.schedule
    .map((match) => {
      let right;
      if (match.finished) {
        right = `<span class="record"><span class="${match.result}">${match.score}</span></span>`;
      } else {
        right = `<span class="schedule-date">${formatMatchDate(match.date)}</span>`;
      }
      return `
        <li>
          <span class="team-name"><span class="flag">${match.opponentFlag}</span> vs ${match.opponentName}</span>
          ${right}
        </li>
        <li class="schedule-meta">${match.stage}${match.finished ? " · " + formatMatchDate(match.date) : ""}</li>`;
    })
    .join("");

  return `<div class="schedule"><ul>${rows}</ul></div>`;
}

function renderSquads(players) {
  const container = document.getElementById("squad-cards");
  container.innerHTML = "";
  players.forEach((p) => {
    const card = document.createElement("div");
    card.className = "squad-card";

    const teamItems = p.squad
      .map((team) => {
        const expanded = expandedTeams.has(team.code);
        return `
        <li class="team-row ${team.eliminated ? "eliminated" : ""} ${expanded ? "expanded" : ""}" data-code="${team.code}">
          <span class="team-name"><span class="flag">${team.flag}</span> ${team.name}${team.eliminated ? ' <span class="out-badge">OUT</span>' : ""}</span>
          <span class="record"><span class="w">${team.w}W</span> <span class="t">${team.t}T</span> <span class="l">${team.l}L</span></span>
        </li>
        <li class="schedule-container ${expanded ? "expanded" : ""}">${renderSchedule(team)}</li>`;
      })
      .join("");

    card.innerHTML = `
      <h3>${p.name} <span class="points">${formatPoints(p.points)} pts</span></h3>
      <ul>${teamItems}</ul>
    `;
    container.appendChild(card);
  });
}

document.getElementById("squad-cards").addEventListener("click", (e) => {
  const row = e.target.closest(".team-row");
  if (!row) return;
  const code = row.dataset.code;
  if (expandedTeams.has(code)) {
    expandedTeams.delete(code);
  } else {
    expandedTeams.add(code);
  }
  row.classList.toggle("expanded");
  row.nextElementSibling.classList.toggle("expanded");
});

loadStandings();
setInterval(loadStandings, REFRESH_INTERVAL_MS);
