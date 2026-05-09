const API = "http://127.0.0.1:5000"

const COLORS = {
  mouse:    "#4ade80",
  keyboard: "#fbbf24",
  phone:    "#38bdf8",
  charger:  "#a78bfa"
}

// ── Clock ──────────────────────────────────
setInterval(() => {
  const el = document.getElementById("clock")
  if (el) el.textContent = new Date().toLocaleTimeString()
}, 1000)

// ── Page Navigation ────────────────────────
function showPage(name) {
  document.querySelectorAll(".page").forEach(p => p.classList.add("hidden"))
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"))

  const page = document.getElementById("page-" + name)
  if (page) page.classList.remove("hidden")

  document.querySelectorAll(".nav-item").forEach(item => {
    if (item.getAttribute("onclick") === `showPage('${name}')`)
      item.classList.add("active")
  })

  const titles = {
    dashboard:  "Dashboard",
    livefeed:   "Live Feed",
    detections: "Detections",
    analytics:  "Analytics"
  }
  const el = document.getElementById("page-title")
  if (el && titles[name]) el.textContent = titles[name]

  
  if (name === "analytics")  initAnalyticsCharts()
  if (name === "screenshots") fetchScreenshots()  
}

// ── Toast ──────────────────────────────────
function showToast(msg) {
  const t = document.getElementById("toast")
  t.textContent = msg
  t.classList.remove("hidden")
  setTimeout(() => t.classList.add("hidden"), 3000)
}

// ── Screenshot ─────────────────────────────
async function takeScreenshot() {

  try {

    const res = await fetch(`${API}/capture`)
    const data = await res.json()

    if(data.file){

      showToast("📸 Screenshot Saved!")

      loadGallery()

    } else {

      showToast("❌ Capture failed")

    }

  } catch(e){

    showToast("❌ Flask not running")

  }
} 
// ── Camera Controls ───────────────────────

async function startCamera(){

  try{

    await fetch(`${API}/camera/start`)

    document.getElementById("webcam-img").src =
      `${API}/video_feed?t=` + new Date().getTime()

    showToast("▶ Camera Started")

  }catch(e){

    showToast("❌ Flask Offline")

  }
}


async function stopCamera(){

  try{

    await fetch(`${API}/camera/stop`)

    document.getElementById("webcam-img").src = ""

    showToast("⏹ Camera Stopped")

  }catch(e){

    showToast("❌ Flask Offline")

  }
}


async function pauseDetection(){

  try{

    const res = await fetch(`${API}/ai/pause`)
    const data = await res.json()

    if(data.paused){

      showToast("⏸ AI Detection Paused")

    }else{

      showToast("▶ AI Detection Resumed")

    }

  }catch(e){

    showToast("❌ Flask Offline")

  }
}
// ── Load Screenshot Gallery ─────────────────

async function loadGallery(){

  try{

    const res = await fetch(`${API}/screenshots`)
    const data = await res.json()

    const gallery = document.getElementById("gallery-list")

    if(data.length === 0){

      gallery.innerHTML =
        '<div class="gallery-empty">No screenshots yet</div>'

      return
    }

    gallery.innerHTML = data.map(img => `

      <div class="gallery-item">
        <img src="/screenshots/${img}"
             onclick="window.open('/screenshots/${img}','_blank')">
      </div>

    `).join("")

  } catch(e){}
}
// ── Charts Setup ───────────────────────────
const chartDefaults = {
  bar: {
    type: "bar",
    data: {
      labels:   ["Mouse","Keyboard","Phone","Charger"],
      datasets: [{
        data:            [0,0,0,0],
        backgroundColor: ["#4ade80","#fbbf24","#38bdf8","#a78bfa"],
        borderRadius:    8,
        borderSkipped:   false
      }]
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false } },
      scales:{
        y:{ beginAtZero:true, ticks:{ color:"#6060aa", stepSize:1 }, grid:{ color:"rgba(255,255,255,0.05)" } },
        x:{ ticks:{ color:"#8080cc" }, grid:{ display:false } }
      }
    }
  },
  pie: {
    type: "doughnut",
    data: {
      labels:   ["Mouse","Keyboard","Phone","Charger"],
      datasets: [{
        data:            [0,0,0,0],
        backgroundColor: ["#4ade80","#fbbf24","#38bdf8","#a78bfa"],
        borderColor:     "rgba(0,0,0,0.3)",
        borderWidth:     3
      }]
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{
          position:"bottom",
          labels:{ color:"#8080cc", padding:10, font:{ size:11 } }
        }
      },
      cutout:"60%"
    }
  }
}

// Dashboard charts
const barChart = new Chart(
  document.getElementById("barChart").getContext("2d"),
  JSON.parse(JSON.stringify(chartDefaults.bar))
)
const pieChart = new Chart(
  document.getElementById("pieChart").getContext("2d"),
  JSON.parse(JSON.stringify(chartDefaults.pie))
)

// Analytics charts (lazy init)
let barChart2, pieChart2
function initAnalyticsCharts() {
  if (barChart2) return
  barChart2 = new Chart(
    document.getElementById("barChart2").getContext("2d"),
    JSON.parse(JSON.stringify(chartDefaults.bar))
  )
  pieChart2 = new Chart(
    document.getElementById("pieChart2").getContext("2d"),
    JSON.parse(JSON.stringify(chartDefaults.pie))
  )
  fetchStats()
}

// ── Update all charts with new data ────────
function updateCharts(counts) {
  const data = [counts.mouse, counts.keyboard, counts.phone, counts.charger]

  barChart.data.datasets[0].data = data
  barChart.update()
  pieChart.data.datasets[0].data = data
  pieChart.update()

  if (barChart2) { barChart2.data.datasets[0].data = data; barChart2.update() }
  if (pieChart2) { pieChart2.data.datasets[0].data = data; pieChart2.update() }
}

// ── Fetch Live Feed ────────────────────────
async function fetchFeed() {
  try {
    const res  = await fetch(`${API}/detections/latest`)
    const data = await res.json()

    document.getElementById("flask-status").textContent = "● Online"
    document.getElementById("flask-status").className   = "sbadge green-badge"
    document.getElementById("flask-badge").textContent  = "Flask Online"

    const html = data.length === 0
      ? '<div class="empty-msg">Waiting for detections...</div>'
      : data.map(d => `
          <div class="feed-item">
            <div class="feed-dot d-${d.label}"></div>
            <div class="feed-name c-${d.label}">${d.label}</div>
            <div class="feed-conf c-${d.label}">${d.confidence.toFixed(1)}%</div>
            <div class="feed-time">${d.timestamp.split(" ")[1]}</div>
          </div>`).join("")

    document.getElementById("live-feed").innerHTML      = html
    document.getElementById("live-feed-full").innerHTML = html

  } catch(e) {
    document.getElementById("flask-status").textContent = "● Offline"
    document.getElementById("flask-status").className   = "sbadge gray-badge"
    document.getElementById("flask-badge").textContent  = "Flask Offline"
  }
}

// ── Fetch Stats ────────────────────────────
async function fetchStats() {
  try {
    const res  = await fetch(`${API}/stats`)
    const data = await res.json()

    const counts = { mouse:0, keyboard:0, phone:0, charger:0 }
    data.forEach(d => { counts[d.label] = d.count })

    const total = counts.mouse + counts.keyboard + counts.phone + counts.charger

    document.getElementById("total").textContent       = total
    document.getElementById("cnt-mouse").textContent    = counts.mouse
    document.getElementById("cnt-keyboard").textContent = counts.keyboard
    document.getElementById("cnt-phone").textContent    = counts.phone
    document.getElementById("cnt-charger").textContent  = counts.charger

    // Progress bars
    const max = Math.max(...Object.values(counts), 1)
    document.getElementById("bar-mouse").style.width    = (counts.mouse    / max * 100) + "%"
    document.getElementById("bar-keyboard").style.width = (counts.keyboard / max * 100) + "%"
    document.getElementById("bar-phone").style.width    = (counts.phone    / max * 100) + "%"
    document.getElementById("bar-charger").style.width  = (counts.charger  / max * 100) + "%"
    document.getElementById("total-bar").style.width    = "100%"

    // Most detected
    const sorted = Object.entries(counts).sort((a,b) => b[1]-a[1])
    if (sorted[0][1] > 0)
      document.getElementById("most-detected").textContent = sorted[0][0]

    updateCharts(counts)

  } catch(e) {}
}

// ── Fetch History Table ────────────────────
async function fetchHistory() {
  try {
    const res   = await fetch(`${API}/detections`)
    const data  = await res.json()
    const tbody = document.getElementById("history-body")

    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-msg">No detections yet</td></tr>'
      return
    }

    tbody.innerHTML = data.map(d => `
      <tr>
        <td style="color:#4040aa">${d.id}</td>
        <td>
          <span style="color:${COLORS[d.label]||'#fff'};font-weight:600;text-transform:uppercase;">
            ${d.label}
          </span>
        </td>
        <td>
          <div class="conf-bar-wrap">
            <div class="conf-bar-bg">
              <div class="conf-bar-fill"
                   style="width:${d.confidence.toFixed(0)}%;background:${COLORS[d.label]||'#38bdf8'}">
              </div>
            </div>
            <span class="conf-text">${d.confidence.toFixed(1)}%</span>
          </div>
        </td>
        <td style="color:#5050aa">${d.timestamp}</td>
      </tr>`).join("")

    document.getElementById("last-updated").textContent = new Date().toLocaleTimeString()

  } catch(e) {}
}

// ── Export CSV ─────────────────────────────
function downloadCSV() {
  fetch(`${API}/detections`)
    .then(r => r.json())
    .then(data => {
      if (data.length === 0) { showToast("⚠️ No data to export!"); return }
      let csv = "ID,Object,Confidence,Timestamp\n"
      data.forEach(d => { csv += `${d.id},${d.label},${d.confidence.toFixed(1)}%,${d.timestamp}\n` })
      const blob = new Blob([csv], { type:"text/csv" })
      const a    = document.createElement("a")
      a.href     = URL.createObjectURL(blob)
      a.download = "smartdesk_detections.csv"
      a.click()
      showToast("✅ CSV exported successfully!")
    })
    .catch(() => showToast("❌ Flask not running — start app.py first!"))
}

// ── Clear All ──────────────────────────────
function clearAll() {
  if (!confirm("Clear ALL detections from database? This cannot be undone.")) return

  fetch(`${API}/detections`, { method:"DELETE" })
    .then(r => r.json())
    .then(() => {
      showToast("🗑️ All detections cleared!")
      fetchFeed()
      fetchStats()
      fetchHistory()
    })
    .catch(() => showToast("❌ Flask not running — start app.py first!"))
}

// ── Auto Refresh ───────────────────────────
fetchFeed()
fetchStats()
fetchHistory()
loadGallery()
setInterval(fetchFeed,    3000)
setInterval(fetchStats,   3000)
setInterval(fetchHistory, 5000)
// Fetch and display screenshots
async function fetchScreenshots() {
  try {
    const res  = await fetch(`${API}/screenshots`)
    const data = await res.json()
    const grid = document.getElementById("screenshots-grid")

    if (data.length === 0) {
      grid.innerHTML = '<div class="empty-msg">No screenshots yet — click Capture on Live Feed page</div>'
      return
    }

    grid.innerHTML = data.map(s => `
      <div class="screenshot-item">
        <img src="${API}/screenshots/${s.filename}"
             alt="${s.filename}"
             onerror="this.src='';this.parentElement.style.display='none'"/>
        <div class="screenshot-info">
          <span class="screenshot-name">${s.filename}</span>
          <a class="screenshot-download"
             href="${API}/screenshots/${s.filename}"
             download="${s.filename}">
            ⬇ Save
          </a>
        </div>
      </div>
    `).join("")

  } catch(e) {
    showToast("❌ Flask not running!")
  }
}

// Override takeScreenshot to also refresh gallery
async function takeScreenshot() {
  try {
    const res  = await fetch(`${API}/capture`)
    const data = await res.json()
    showToast("📸 " + data.message + " — " + data.file)
    fetchScreenshots()
  } catch(e) {
    showToast("❌ Flask not running — start app.py!")
  }
}