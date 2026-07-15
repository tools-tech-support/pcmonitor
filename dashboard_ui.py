import os
import json
import webview
import csv

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GameTuneLogger Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0f172a;
            --bg-panel: rgba(30, 41, 59, 0.7);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.4);
            --danger: #ef4444;
        }
        body {
            margin: 0;
            padding: 0;
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        /* Sidebar */
        .sidebar {
            width: 260px;
            background: var(--bg-panel);
            backdrop-filter: blur(12px);
            border-right: 1px solid rgba(255,255,255,0.1);
            display: flex;
            flex-direction: column;
        }
        .sidebar-header {
            padding: 20px;
            font-size: 1.2rem;
            font-weight: 800;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .session-list {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .session-item {
            padding: 12px 15px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.9rem;
        }
        .session-item:hover {
            background: rgba(255,255,255,0.1);
        }
        .session-item.active {
            background: var(--accent);
            color: #000;
            font-weight: 600;
            box-shadow: 0 0 15px var(--accent-glow);
        }

        /* Main Content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
            overflow-y: auto;
            gap: 20px;
        }

        /* KPI Cards */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }
        .kpi-card {
            background: var(--bg-panel);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(255,255,255,0.2);
        }
        .kpi-value {
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 5px;
        }
        .kpi-label {
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* Chart Container */
        .chart-container {
            background: var(--bg-panel);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            flex: 1;
            min-height: 400px;
            position: relative;
        }
        .chart-hint {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin: 0 0 8px 0;
        }
        .chart-wrap {
            position: relative;
            height: 380px;
        }

        /* Full summary details */
        .details-panel {
            background: var(--bg-panel);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
        }
        .details-panel h3 {
            margin: 0 0 12px 0;
            font-size: 0.95rem;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .details-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 6px 24px;
            font-size: 0.85rem;
        }
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 5px 8px;
            border-radius: 6px;
            background: rgba(255,255,255,0.03);
        }
        .detail-key { color: var(--text-muted); }
        .detail-val { font-weight: 600; }
        .detail-val.missing { color: var(--danger); font-weight: 800; }
        .notes-box {
            margin-top: 12px;
            font-size: 0.82rem;
            color: #fbbf24;
            line-height: 1.5;
        }
        .presenters-box {
            margin-top: 12px;
            font-size: 0.82rem;
            color: var(--text-muted);
        }
        .presenters-box b { color: var(--text-main); }

        /* Loading Overlay */
        #loading {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--accent);
            border-radius: 12px;
            z-index: 10;
            display: none;
        }

        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255,255,255,0.3);
        }
    </style>
</head>
<body>

    <div class="sidebar">
        <div class="sidebar-header">
            GameTune Dashboard
        </div>
        <div class="session-list" id="session-list">
            <!-- Sessions will be populated here -->
        </div>
    </div>

    <div class="main-content">
        <div class="kpi-grid" id="kpi-grid">
            <div class="kpi-card"><div class="kpi-value" id="kpi-fps">-</div><div class="kpi-label">Avg FPS</div></div>
            <div class="kpi-card"><div class="kpi-value" id="kpi-1low">-</div><div class="kpi-label">1% Low</div></div>
            <div class="kpi-card"><div class="kpi-value" id="kpi-01low">-</div><div class="kpi-label">0.1% Low</div></div>
            <div class="kpi-card"><div class="kpi-value" id="kpi-cputemp">-</div><div class="kpi-label">Max CPU °C</div></div>
            <div class="kpi-card"><div class="kpi-value" id="kpi-gputemp">-</div><div class="kpi-label">Max GPU °C</div></div>
            <div class="kpi-card"><div class="kpi-value" id="kpi-whea">-</div><div class="kpi-label">WHEA Errors</div></div>
        </div>

        <div class="chart-container">
            <div id="loading">Processing Data...</div>
            <p class="chart-hint">คลิกชื่อ series ใน legend เพื่อเปิด/ปิดเส้นกราฟ (clock/VRAM ใช้แกนขวาตัวที่สอง)</p>
            <div class="chart-wrap"><canvas id="mainChart"></canvas></div>
        </div>

        <div class="details-panel">
            <h3>Session summary (ทุก parameter)</h3>
            <div class="details-grid" id="details-grid"></div>
            <div class="presenters-box" id="presenters-box"></div>
            <div class="notes-box" id="notes-box"></div>
        </div>
    </div>

    <script>
        let chartInstance = null;

        // Every numeric column in timeline.csv is chartable. hidden:true series
        // start toggled off but stay one legend-click away.
        const SERIES = [
            {key:'fps',           label:'FPS',                color:'#38bdf8', axis:'y',  hidden:false, fill:true, fillColor:'rgba(56, 189, 248, 0.1)'},
            {key:'ft_max_ms',     label:'Frametime max (ms)', color:'#f97316', axis:'y1', hidden:true},
            {key:'ft_avg_ms',     label:'Frametime avg (ms)', color:'#fdba74', axis:'y1', hidden:true},
            {key:'cpu_temp_c',    label:'CPU Temp (°C)',      color:'#ef4444', axis:'y1', hidden:false},
            {key:'gpu_temp_c',    label:'GPU Temp (°C)',      color:'#eab308', axis:'y1', hidden:false},
            {key:'cpu_load_pct',  label:'CPU Load (%)',       color:'#a78bfa', axis:'y1', hidden:true},
            {key:'gpu_load_pct',  label:'GPU Load (%)',       color:'#10b981', axis:'y1', hidden:false},
            {key:'cpu_power_w',   label:'CPU Power (W)',      color:'#f43f5e', axis:'y1', hidden:true},
            {key:'gpu_power_w',   label:'GPU Power (W)',      color:'#22d3ee', axis:'y1', hidden:true},
            {key:'cpu_clock_mhz', label:'CPU Clock (MHz)',    color:'#c084fc', axis:'y2', hidden:true},
            {key:'gpu_clock_mhz', label:'GPU Clock (MHz)',    color:'#4ade80', axis:'y2', hidden:true},
            {key:'gpu_vram_mb',   label:'VRAM (MB)',          color:'#94a3b8', axis:'y2', hidden:true},
            {key:'ram_used_gb',   label:'RAM (GB)',           color:'#fb7185', axis:'y1', hidden:true}
        ];

        // Fetch sessions on load
        window.addEventListener('pywebviewready', function() {
            pywebview.api.get_sessions().then(sessions => {
                const list = document.getElementById('session-list');
                list.innerHTML = '';
                if (!sessions.length) {
                    list.innerHTML = '<div class="session-item">ยังไม่มี session ในโฟลเดอร์ logs</div>';
                    return;
                }
                sessions.forEach(s => {
                    const el = document.createElement('div');
                    el.className = 'session-item';
                    el.textContent = s.replace('session_', '');
                    el.onclick = () => loadSession(s, el);
                    list.appendChild(el);
                });
            });
        });

        function fmt(v) {
            if (v === null || v === undefined || v === '') return null;
            return v;
        }

        function loadSession(sessionId, element) {
            // Update active styling
            document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
            element.classList.add('active');

            // Show loading
            document.getElementById('loading').style.display = 'flex';

            pywebview.api.get_session_data(sessionId).then(data => {
                if(data.error) {
                    alert("Error: " + data.error);
                    document.getElementById('loading').style.display = 'none';
                    return;
                }

                // Update KPIs
                const summary = data.summary;
                document.getElementById('kpi-fps').textContent = fmt(summary.avg_fps) ?? '-';
                document.getElementById('kpi-1low').textContent = fmt(summary.fps_1pct_low) ?? '-';
                document.getElementById('kpi-01low').textContent = fmt(summary.fps_01pct_low) ?? '-';
                document.getElementById('kpi-cputemp').textContent = fmt(summary.cpu_temp_max_c) ?? '-';
                document.getElementById('kpi-gputemp').textContent = fmt(summary.gpu_temp_max_c) ?? '-';

                const wheaEl = document.getElementById('kpi-whea');
                wheaEl.textContent = summary.whea_events !== null && summary.whea_events !== undefined ? summary.whea_events : '-';
                if(summary.whea_events > 0) wheaEl.style.color = 'var(--danger)';
                else wheaEl.style.color = '';

                renderDetails(summary);
                renderChart(data.timeline);

                document.getElementById('loading').style.display = 'none';
            });
        }

        function renderDetails(summary) {
            const grid = document.getElementById('details-grid');
            grid.innerHTML = '';
            Object.keys(summary).forEach(k => {
                if (k === 'notes' || k === 'top_presenters') return;
                const v = summary[k];
                const row = document.createElement('div');
                row.className = 'detail-row';
                const missing = (v === null || v === undefined || v === '');
                row.innerHTML = '<span class="detail-key">' + k + '</span>' +
                                '<span class="detail-val' + (missing ? ' missing' : '') + '">' +
                                (missing ? 'MISSING' : v) + '</span>';
                grid.appendChild(row);
            });

            const pres = document.getElementById('presenters-box');
            if (summary.top_presenters && summary.top_presenters.length) {
                pres.innerHTML = '<b>Top presenters:</b> ' + summary.top_presenters
                    .map(p => p.app + ' (pid ' + p.pid + ', ' + p.frames + ' frames)')
                    .join(' · ');
            } else {
                pres.innerHTML = '';
            }

            const notes = document.getElementById('notes-box');
            if (summary.notes && summary.notes.length) {
                notes.innerHTML = '<b>Notes:</b> ' + summary.notes.join('<br>');
            } else {
                notes.innerHTML = '';
            }
        }

        function renderChart(timeline) {
            if (typeof Chart === 'undefined') {
                document.querySelector('.chart-hint').textContent =
                    'โหลด Chart.js ไม่ได้ (ต้องต่ออินเทอร์เน็ตครั้งแรก) — ดูข้อมูลดิบจาก timeline.csv แทน';
                return;
            }
            const ctx = document.getElementById('mainChart').getContext('2d');

            if (chartInstance) {
                chartInstance.destroy();
            }

            const labels = timeline.map(row => row.sec);
            const datasets = SERIES
                .filter(s => timeline.some(row => typeof row[s.key] === 'number'))
                .map(s => ({
                    label: s.label,
                    data: timeline.map(row => (typeof row[s.key] === 'number' ? row[s.key] : null)),
                    borderColor: s.color,
                    backgroundColor: s.fillColor,
                    borderWidth: s.key === 'fps' ? 2 : 1.5,
                    yAxisID: s.axis,
                    fill: !!s.fill,
                    hidden: s.hidden,
                    tension: 0.1,
                    pointRadius: 0,
                    spanGaps: true
                }));

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#f8fafc', boxWidth: 18, font: { size: 11 } }
                        }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: 'seconds (game time)', color: '#94a3b8' },
                            ticks: { color: '#94a3b8', maxTicksLimit: 20 },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: { display: true, text: 'FPS', color: '#94a3b8' },
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        },
                        y1: {
                            type: 'linear',
                            display: 'auto',
                            position: 'right',
                            title: { display: true, text: '°C / % / W / ms / GB', color: '#94a3b8' },
                            ticks: { color: '#94a3b8' },
                            grid: { drawOnChartArea: false }
                        },
                        y2: {
                            type: 'linear',
                            display: 'auto',
                            position: 'right',
                            title: { display: true, text: 'MHz / MB', color: '#94a3b8' },
                            ticks: { color: '#94a3b8' },
                            grid: { drawOnChartArea: false }
                        }
                    }
                }
            });
        }
    </script>
</body>
</html>
"""

class DashboardApi:
    def __init__(self, log_dir):
        self.log_dir = log_dir

    def get_sessions(self):
        if not os.path.exists(self.log_dir):
            return []

        sessions = []
        for item in os.listdir(self.log_dir):
            if item.startswith("session_") and os.path.isdir(os.path.join(self.log_dir, item)):
                sessions.append(item)
            elif item.startswith("session_") and item.endswith(".zip"):
                name = item[:-4]
                if name not in sessions:
                    sessions.append(name)

        return sorted(sessions, reverse=True)

    def get_session_data(self, session_id):
        # Prefer directory over zip for direct reading
        target_dir = os.path.join(self.log_dir, session_id)
        zip_path = os.path.join(self.log_dir, f"{session_id}.zip")

        # If folder doesn't exist but ZIP does, extract it next to the zip
        if not os.path.exists(target_dir) and os.path.exists(zip_path):
            import zipfile
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)

        if not os.path.exists(target_dir):
            return {"error": "Session data not found."}

        summary_path = os.path.join(target_dir, "summary.txt")
        timeline_path = os.path.join(target_dir, "timeline.csv")

        # Parse Summary JSON
        summary_data = {}
        if os.path.exists(summary_path):
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "=== JSON ===" in content:
                        json_str = content.split("=== JSON ===")[1].strip()
                        summary_data = json.loads(json_str)
            except Exception as e:
                print(f"Error parsing summary: {e}")

        # Parse Timeline CSV
        timeline_data = []
        if os.path.exists(timeline_path):
            try:
                with open(timeline_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        processed_row = {}
                        for k, v in row.items():
                            v = (v or "").strip()
                            if v == "":
                                processed_row[k] = None
                                continue
                            try:
                                processed_row[k] = float(v) if "." in v else int(v)
                            except ValueError:
                                processed_row[k] = v
                        timeline_data.append(processed_row)
            except Exception as e:
                print(f"Error parsing timeline: {e}")

        return {
            "summary": summary_data,
            "timeline": timeline_data
        }

def run_dashboard(log_dir):
    api = DashboardApi(log_dir)
    webview.create_window('GameTuneLogger Dashboard', html=HTML_CONTENT, js_api=api, width=1100, height=700)
    webview.start()
