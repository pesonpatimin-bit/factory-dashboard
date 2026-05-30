import socket
import threading
import time
import os
import sys
import logging
import tkinter as tk
from tkinter import simpledialog, messagebox
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from waitress import serve  # ใช้ Waitress สำหรับรัน Production

# ================= การตั้งค่า (Configuration) =================
SERVER_IP = "10.61.16.1"  
SERVER_PORT = 6370        
WEB_PORT = 8080           
PASSWORD_TO_CLOSE = "@A30.123" # รหัสผ่านสำหรับปิดโปรแกรม
# ==========================================================

# ระบบ Logging: บันทึก Error ลงไฟล์เมื่อไม่มีหน้าต่าง Console
logging.basicConfig(
    filename='dashboard_system.log', 
    level=logging.ERROR, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

machine_data = {}
app = Flask(__name__)

def decode_string(byte_array):
    end_idx = byte_array.find(b'\x00')
    if end_idx != -1: 
        byte_array = byte_array[:end_idx]
    return byte_array.decode('ascii', errors='ignore').strip()

# ================= แผนกหลังบ้าน: ดึงข้อมูล (Data Collector) =================
def data_collector():
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((SERVER_IP, SERVER_PORT))

            while True:
                sock.sendall(b'\xaa')
                data = sock.recv(4096)
                if not data: break
                
                if len(data) == 304:
                    m_name = decode_string(data[0:20])
                    u_name = decode_string(data[24:44]) 
                    p_name = decode_string(data[44:100])
                    
                    spindle_byte = data[107] 
                    spindles = [
                        bool(spindle_byte & 1), bool(spindle_byte & 2), bool(spindle_byte & 4),
                        bool(spindle_byte & 8), bool(spindle_byte & 16), bool(spindle_byte & 32)
                    ]
                    
                    m_status = data[106]
                    
                    sim_time = int.from_bytes(data[110:112], byteorder='little', signed=False)

                    online_sec = int.from_bytes(data[296:300], byteorder='little', signed=False)
                    stop_sec = int.from_bytes(data[300:304], byteorder='little', signed=False)
                    
                    calculated_rate = 0.0
                    if online_sec > 0:
                        calculated_rate = (1 - (stop_sec / online_sec)) * 100
                        calculated_rate = max(0.0, min(100.0, calculated_rate))

                    if m_name != "":
                        if m_name not in machine_data:
                            machine_data[m_name] = {}
                        
                        machine_data[m_name].update({
                            "part_no": p_name,
                            "user": u_name,
                            "status": m_status, 
                            "run_rate": f"{calculated_rate:.1f}",
                            "spindles": spindles,
                            "sim_time": sim_time,
                            "last_update": time.strftime("%H:%M:%S")
                        })
                time.sleep(0.01)

        except Exception as e:
            logging.error(f"Socket Data Error: {e}")
            time.sleep(3)
        finally:
            if 'sock' in locals(): sock.close()

# ================= API & WEB FRONTEND =================

@app.route('/api/machines')
def get_machine_data():
    return jsonify(machine_data)

@app.route('/')
def index():
    html_template = """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>COMPEQ Factory Dashboard</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700;900&display=swap');
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { font-family: 'Roboto', sans-serif; background: #080c12; color: #c9d1d9; overflow-x: hidden; }

            /* ===== HEADER ===== */
            .main-header {
                text-align: center; color: #58a6ff;
                text-transform: uppercase; font-weight: 900;
                letter-spacing: 2px; font-size: 26px;
                padding: 16px 0 14px 0;
            }

            /* ===== SECTION LABEL ===== */
            .sec-label {
                font-size: 12px; font-weight: 700; letter-spacing: 2px;
                text-transform: uppercase; color: #8b949e;
                display: flex; align-items: center; gap: 8px;
                margin: 0 0 10px 0;
            }
            .sec-label::after { content: ''; flex: 1; height: 1px; background: linear-gradient(to right,#30363d,transparent); }

            /* ===== SECTION WRAPPER ===== */
            .section { padding: 0 15px 28px 15px; }
            .section + .section { border-top: 1px solid #161b22; padding-top: 22px; }

            /* ===== LEGEND ===== */
            .legend-bar { display: flex; gap: 14px; justify-content: flex-end; align-items: center; margin-bottom: 10px; font-size: 11px; color: #8b949e; flex-wrap: wrap; }
            .legend-chip { display: flex; align-items: center; gap: 5px; }
            .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
            .dot-run { background: #1aff6e; } .dot-stop { background: #ffd23f; } .dot-alarm { background: #ff4d4d; }

            /* ===== SECTION 1: PART SUMMARY ===== */
            .summary-wrapper { overflow-x: auto; }
            .summary-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 420px; }
            .summary-table thead tr { background: #161b22; border-bottom: 2px solid #30363d; }
            .summary-table th { padding: 9px 14px; text-align: center; font-weight: 700; font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 1px; }
            .summary-table th:first-child { text-align: left; }
            .summary-table tbody tr { border-bottom: 1px solid #1c2128; }
            .summary-table tbody tr:hover { background: #1c2128; }
            .summary-table td { padding: 8px 14px; text-align: center; vertical-align: middle; }
            .summary-table td:first-child { text-align: left; font-weight: 700; color: #58a6ff; font-size: 13px; }
            .badge-cell { font-size: 15px; font-weight: 900; }
            .badge-run { color: #1aff6e; } .badge-stop { color: #ffd23f; } .badge-alarm { color: #ff4d4d; }
            .badge-total { color: #c9d1d9; font-size: 13px; }
            .summary-table tfoot tr { background: #161b22; border-top: 2px solid #30363d; }
            .summary-table tfoot td { padding: 8px 14px; font-weight: 700; color: #8b949e; font-size: 12px; text-align: center; }
            .summary-table tfoot td:first-child { text-align: left; }

            /* ===== SECTION 2: MAP ===== */
            .card {
                border-radius: 8px; padding: 8px;
                border-top: 5px solid #30363d;
                border-left: 1px solid rgba(255,255,255,0.06);
                border-right: 1px solid rgba(255,255,255,0.06);
                border-bottom: 1px solid rgba(255,255,255,0.06);
                display: flex; flex-direction: column; justify-content: space-between;
                box-shadow: 0 4px 10px rgba(0,0,0,0.5); overflow: hidden;
            }
            .card-offline { background: #0e1218 !important; border-top-color: #1c2128; opacity: 0.4; }
            .status-run   { border-top-color: #1aff6e !important; }
            .status-stop  { border-top-color: #ffd23f !important; }
            .status-error { border-top-color: #ff4d4d !important; }
            .top-row { display: flex; justify-content: space-between; align-items: baseline; }
            .machine-name { margin: 0; font-size: 18px; color: #fff; font-weight: 900; }
            .run-rate { font-size: 16px; font-weight: 900; }
            .part-no { font-size: 12px; color: #ffe082; font-weight: 700; margin: 4px 0; word-break: break-all; }
            .user-info { font-size: 9px; color: #cfd8dc; }
            .color-run { color: #69ff8a; font-weight: 900; } .color-stop { color: #ffe57f; font-weight: 900; }
            .color-error { color: #ff8080; font-weight: 900; } .color-offline { color: #ccc; }
            .spindle-container { display: flex; gap: 3px; justify-content: center; margin-top: 4px; background: rgba(0,0,0,0.2); padding: 3px; border-radius: 4px; }
            .spindle { width: 8px; height: 8px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.3); background: rgba(0,0,0,0.25); }
            .sp-on { background: #00b84a; border-color: #00b84a; }
            .card-dimmed { opacity: 0.15; filter: grayscale(60%); transition: opacity 0.3s, filter 0.3s; pointer-events: none; }
            .card { transition: opacity 0.3s, filter 0.3s; }

            /* ===== SECTION 3: LIST TABLE ===== */
            .list-controls { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
            .search-box {
                background: #161b22; border: 1px solid #30363d; border-radius: 6px;
                color: #c9d1d9; padding: 7px 12px; font-size: 13px;
                font-family: 'Roboto', sans-serif; outline: none; flex: 1; min-width: 160px;
            }
            .search-box:focus { border-color: #58a6ff; }
            .filter-btn {
                background: #161b22; border: 1px solid #30363d; border-radius: 6px;
                color: #8b949e; padding: 7px 14px; font-size: 12px; font-weight: 700;
                cursor: pointer; font-family: 'Roboto', sans-serif; transition: background 0.15s, color 0.15s;
            }
            .filter-btn:hover { background: #21262d; color: #c9d1d9; }
            .filter-btn.f-run.active   { border-color: #1aff6e; color: #1aff6e; background: #21262d; }
            .filter-btn.f-stop.active  { border-color: #ffd23f; color: #ffd23f; background: #21262d; }
            .filter-btn.f-alarm.active { border-color: #ff4d4d; color: #ff4d4d; background: #21262d; }
            .list-wrapper { overflow-x: auto; }
            .list-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 640px; }
            .list-table thead tr { background: #161b22; border-bottom: 2px solid #30363d; }
            .list-table th { padding: 10px 12px; text-align: left; font-weight: 700; font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 1px; cursor: pointer; user-select: none; white-space: nowrap; }
            .list-table th:hover { color: #c9d1d9; }
            .list-table th.sort-asc::after  { content: ' ▲'; font-size: 9px; }
            .list-table th.sort-desc::after { content: ' ▼'; font-size: 9px; }
            .list-table tbody tr { border-bottom: 1px solid #1c2128; transition: background 0.1s; }
            .list-table tbody tr:hover { background: #1c2128; }
            .list-table td { padding: 9px 12px; vertical-align: middle; }
            .pill { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; white-space: nowrap; }
            .pill-run   { background: rgba(26,255,110,0.15); color: #1aff6e; border: 1px solid #1aff6e; }
            .pill-stop  { background: rgba(255,210,63,0.15);  color: #ffd23f; border: 1px solid #ffd23f; }
            .pill-alarm { background: rgba(255,77,77,0.15);   color: #ff4d4d; border: 1px solid #ff4d4d; }
            .pill-off   { background: rgba(100,100,100,0.1);  color: #666;    border: 1px solid #333; }
            .sp-mini { display: inline-flex; gap: 2px; vertical-align: middle; }
            .sp-dot { width: 7px; height: 7px; border-radius: 50%; background: #222; border: 1px solid #444; display: inline-block; }
            .sp-dot.on { background: #00b84a; border-color: #00b84a; }
            .rate-bar-wrap { display: flex; align-items: center; gap: 6px; min-width: 90px; }
            .rate-bar { flex: 1; height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; }
            .rate-fill { height: 100%; border-radius: 3px; }
            .rate-text { font-size: 12px; font-weight: 700; min-width: 38px; text-align: right; }
            .color-swatch { display: inline-block; width: 12px; height: 12px; border-radius: 3px; vertical-align: middle; margin-right: 5px; }

            /* ===== RESPONSIVE ===== */
            @media (min-width: 900px) {
                .main-header { font-size: 32px; }
                .grid-container {
                    display: grid;
                    grid-template-columns: repeat(9, 1fr);
                    grid-template-rows: repeat(16, minmax(90px, auto));
                    gap: 8px; min-width: 1200px; margin: 0 auto;
                }
                .card { grid-column: var(--map-c); grid-row: var(--map-r); }
                .machine-name { font-size: 22px; } .run-rate { font-size: 20px; }
                .part-no { font-size: 13px; } .spindle { width: 10px; height: 10px; }
                .summary-table { font-size: 14px; } .summary-table th { font-size: 12px; }
                .list-table { font-size: 14px; } .list-table th { font-size: 12px; }
            }
            @media (max-width: 899px) {
                .grid-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; padding-bottom: 30px; }
                .card { width: 46%; min-width: 140px; }
                .card-offline { display: none !important; }
            }
        </style>
    </head>
    <body>
        <h1 class="main-header">&#127981; COMPEQ Dashboard</h1>

        <!-- ===== SECTION 1 ===== -->
        <div class="section">
            <div class="sec-label">&#128202; Section 1 — Part Number Summary</div>
            <div class="legend-bar">
                <div class="legend-chip"><div class="legend-dot dot-run"></div> Run</div>
                <div class="legend-chip"><div class="legend-dot dot-stop"></div> Stop</div>
                <div class="legend-chip"><div class="legend-dot dot-alarm"></div> Alarm</div>
            </div>
            <div class="summary-wrapper">
                <table class="summary-table">
                    <thead><tr>
                        <th>Part Number</th>
                        <th>&#128994; Run</th><th>&#128993; Stop</th><th>&#128308; Alarm</th><th>Total</th>
                    </tr></thead>
                    <tbody id="summary-body">
                        <tr><td colspan="5" style="text-align:center;color:#484f58;padding:20px;">กำลังโหลด...</td></tr>
                    </tbody>
                    <tfoot><tr>
                        <td>รวมทั้งหมด</td>
                        <td id="foot-run" class="badge-run">—</td>
                        <td id="foot-stop" class="badge-stop">—</td>
                        <td id="foot-alarm" class="badge-alarm">—</td>
                        <td id="foot-total" class="badge-total">—</td>
                    </tr></tfoot>
                </table>
            </div>
        </div>

        <!-- ===== SECTION 2 ===== -->
        <div class="section">
            <div class="sec-label">&#128205; Section 2 — ตำแหน่งเครื่อง Realtime</div>
            <div class="list-controls" style="margin-bottom:14px;flex-wrap:wrap;">
                <button class="filter-btn f-run"   id="map-fb-run"   onclick="toggleMapFilter('run')">&#9646; Run</button>
                <button class="filter-btn f-stop"  id="map-fb-stop"  onclick="toggleMapFilter('stop')">&#9646; Stop</button>
                <button class="filter-btn f-alarm" id="map-fb-alarm" onclick="toggleMapFilter('alarm')">&#9646; Alarm</button>
                <select class="search-box" id="map-part-select" onchange="applyMapFilter()" style="flex:0 1 220px;cursor:pointer;">
                    <option value="">&#128196; ทุก Part No.</option>
                </select>
                <button class="filter-btn" onclick="resetMapFilter()" style="color:#58a6ff;border-color:#58a6ff;">&#10006; Reset</button>
                <span style="display:flex;align-items:center;gap:10px;margin-left:8px;font-size:12px;color:#8b949e;font-weight:700;">
                    แสดงตัวเลข:
                    <label style="display:flex;align-items:center;gap:4px;cursor:pointer;">
                        <input type="radio" name="card-display" value="rate" checked onchange="setCardDisplay('rate')" style="accent-color:#58a6ff;">
                        <span style="color:#c9d1d9;">Run Rate</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:4px;cursor:pointer;">
                        <input type="radio" name="card-display" value="runtime" onchange="setCardDisplay('runtime')" style="accent-color:#58a6ff;">
                        <span style="color:#c9d1d9;">Run Time <span style='font-size:10px;color:#666;'>(hh:mm:ss)</span></span>
                    </label>
                </span>
            </div>
            <div class="grid-container" id="dashboard"></div>
        </div>

        <!-- ===== SECTION 3 ===== -->
        <div class="section">
            <div class="sec-label">&#128203; Section 3 — รายการเครื่องจักร</div>
            <div class="list-controls">
                <input class="search-box" type="text" id="list-search"
                    placeholder="&#128269; ค้นหา เครื่อง / Part No. / User..."
                    oninput="renderList()">
                <button class="filter-btn f-run"   id="fb-run"   onclick="toggleFilter('run')">&#9646; Run</button>
                <button class="filter-btn f-stop"  id="fb-stop"  onclick="toggleFilter('stop')">&#9646; Stop</button>
                <button class="filter-btn f-alarm" id="fb-alarm" onclick="toggleFilter('alarm')">&#9646; Alarm</button>
            </div>
            <div class="list-wrapper">
                <table class="list-table">
                    <thead><tr>
                        <th onclick="sortList('name')"   id="th-name">เครื่อง</th>
                        <th onclick="sortList('status')" id="th-status">สถานะ</th>
                        <th onclick="sortList('part')"   id="th-part">Part No.</th>
                        <th onclick="sortList('user')"   id="th-user">User</th>
                        <th onclick="sortList('rate')"   id="th-rate">Run Rate</th>
                        <th>Spindle</th>
                        <th onclick="sortList('sim_time')" id="th-sim">Run Time <span style='font-size:9px;color:#555;font-weight:400;'>(hh:mm:ss)</span></th>
                        <th onclick="sortList('update')" id="th-update">อัพเดท</th>
                    </tr></thead>
                    <tbody id="list-body">
                        <tr><td colspan="8" style="text-align:center;color:#484f58;padding:24px;">กำลังโหลด...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            /* ===== MAP LAYOUT ===== */
            var mapLayout = {
                'M1':{c:1,r:1},'D1':{c:2,r:1},'D2':{c:3,r:1},'T65':{c:4,r:1},'T66':{c:5,r:1},'T67':{c:6,r:1},'T68':{c:7,r:1},
                'T58':{c:1,r:2},'T59':{c:2,r:2},'T60':{c:3,r:2},'T61':{c:4,r:2},'T62':{c:5,r:2},'T63':{c:6,r:2},'T64':{c:7,r:2},
                'T51':{c:1,r:4},'T52':{c:2,r:4},'T53':{c:3,r:4},'T54':{c:4,r:4},'T55':{c:5,r:4},'T56':{c:6,r:4},'T57':{c:7,r:4},
                'T44':{c:1,r:5},'T45':{c:2,r:5},'T46':{c:3,r:5},'T47':{c:4,r:5},'T48':{c:5,r:5},'T49':{c:6,r:5},'T50':{c:7,r:5},
                'T37':{c:1,r:7},'T38':{c:2,r:7},'T39':{c:3,r:7},'T40':{c:4,r:7},'T41':{c:5,r:7},'T42':{c:6,r:7},'T43':{c:7,r:7},
                'T30':{c:1,r:8},'T31':{c:2,r:8},'T32':{c:3,r:8},'T33':{c:4,r:8},'T34':{c:5,r:8},'T35':{c:6,r:8},'T36':{c:7,r:8},
                'T23':{c:1,r:10},'T24':{c:2,r:10},'T25':{c:3,r:10},'T26':{c:4,r:10},'T27':{c:5,r:10},'T28':{c:6,r:10},'T29':{c:7,r:10},'T73':{c:9,r:10},
                'T16':{c:1,r:11},'T17':{c:2,r:11},'T18':{c:3,r:11},'T19':{c:4,r:11},'T20':{c:5,r:11},'T21':{c:6,r:11},'T22':{c:7,r:11},'T72':{c:9,r:11},
                'T09':{c:1,r:13},'T10':{c:2,r:13},'T11':{c:3,r:13},'T12':{c:4,r:13},'T13':{c:5,r:13},'T14':{c:6,r:13},'T15':{c:7,r:13},'T71':{c:9,r:13},
                'T05':{c:1,r:14},'T06':{c:2,r:14},'T07':{c:3,r:14},'T08':{c:4,r:14},'4':{c:5,r:14},'5':{c:6,r:14},'6':{c:7,r:14},'T70':{c:9,r:14},
                'T01':{c:1,r:16},'T02':{c:2,r:16},'T03':{c:3,r:16},'T04':{c:4,r:16},'1':{c:5,r:16},'2':{c:6,r:16},'3':{c:7,r:16},'T69':{c:9,r:16}
            };

            /* ===== COLOR (FNV-1a + golden ratio HSL) ===== */
            var partColorsMap = {};
            function getPartBgColor(partNo) {
                if (!partNo || partNo.trim()==='' || partNo==='---' || partNo==='NO PROGRAM')
                    return {bg:'#1e272e'};
                if (!partColorsMap[partNo]) {
                    var h1 = 2166136261;
                    for (var i = 0; i < partNo.length; i++)
                        h1 = ((h1 ^ partNo.charCodeAt(i)) * 16777619) & 0xFFFFFFFF;
                    var h2 = 2166136261;
                    for (var i = partNo.length - 1; i >= 0; i--)
                        h2 = ((h2 ^ partNo.charCodeAt(i)) * 16777619) & 0xFFFFFFFF;
                    var hue = Math.floor(((h1 * 0.6180339887) % 1.0) * 360);
                    var sat = 55 + (h2 % 20);
                    var lit = 30 + ((h2 / 256 | 0) % 16);
                    partColorsMap[partNo] = {bg: 'hsl('+hue+','+sat+'%,'+lit+'%)'};
                }
                return partColorsMap[partNo];
            }

            /* ===== STATUS ===== */
            function getStatusInfo(s) {
                s = parseInt(s);
                if (s===1||s===49) return {cardClass:'status-error',textClass:'color-error',type:'alarm',label:'ALARM'};
                if (s===2||s===50) return {cardClass:'status-stop', textClass:'color-stop', type:'stop', label:'STOP'};
                if (s===3||s===51) return {cardClass:'status-run',  textClass:'color-run',  type:'run',  label:'RUN'};
                return {cardClass:'',textClass:'color-offline',type:'offline',label:'OFFLINE'};
            }

            /* ===== LIST STATE ===== */
            var listData  = [];
            var sortCol   = 'name';
            var sortAsc   = true;
            var filterSet    = {};
            var mapFilterSet = {};

            function toggleMapFilter(type) {
                mapFilterSet[type] = !mapFilterSet[type];
                var btn = document.getElementById('map-fb-'+type);
                if (mapFilterSet[type]) btn.classList.add('active');
                else btn.classList.remove('active');
                applyMapFilter();
            }

            function applyMapFilter() {
                var af   = Object.keys(mapFilterSet).filter(function(k){ return mapFilterSet[k]; });
                var selEl = document.getElementById('map-part-select');
                var selPart = selEl ? selEl.value : '';
                var cards = document.querySelectorAll('#dashboard .card');
                cards.forEach(function(card) {
                    var t    = card.getAttribute('data-type');
                    var p    = card.getAttribute('data-part');
                    var passStatus = (af.length === 0) || (af.indexOf(t) >= 0);
                    var passPart   = (selPart === '') || (p === selPart);
                    if (passStatus && passPart) card.classList.remove('card-dimmed');
                    else card.classList.add('card-dimmed');
                });
            }

            function resetMapFilter() {
                mapFilterSet = {};
                ['run','stop','alarm'].forEach(function(t) {
                    var btn = document.getElementById('map-fb-'+t);
                    if (btn) btn.classList.remove('active');
                });
                var sel = document.getElementById('map-part-select');
                if (sel) sel.value = '';
                applyMapFilter();
            }

            function updatePartSelect(data) {
                var parts = {};
                Object.keys(data).forEach(function(k) {
                    var p = (data[k].part_no || '').trim();
                    if (p && p !== '---' && p !== 'NO PROGRAM') parts[p] = true;
                });
                var sel = document.getElementById('map-part-select');
                if (!sel) return;
                var cur = sel.value;
                var sorted = Object.keys(parts).sort();
                var html = '<option value="">&#128196; ทุก Part No.</option>';
                sorted.forEach(function(p) {
                    html += '<option value="'+p+'"'+(p===cur?' selected':'')+'>'+p+'</option>';
                });
                sel.innerHTML = html;
            }

            function toggleFilter(type) {
                filterSet[type] = !filterSet[type];
                var btn = document.getElementById('fb-'+type);
                if (filterSet[type]) btn.classList.add('active');
                else btn.classList.remove('active');
                renderList();
            }

            function sortList(col) {
                if (sortCol===col) sortAsc = !sortAsc;
                else { sortCol=col; sortAsc=true; }
                ['name','status','part','user','rate','sim','update'].forEach(function(c) {
                    var th = document.getElementById('th-'+c);
                    if (!th) return;
                    th.classList.remove('sort-asc','sort-desc');
                    var colMatch = (c==='sim') ? (col==='sim_time') : (c===col);
                    if (colMatch) th.classList.add(sortAsc?'sort-asc':'sort-desc');
                });
                renderList();
            }

            function renderList() {
                var q = (document.getElementById('list-search').value||'').toLowerCase();
                var af = Object.keys(filterSet).filter(function(k){ return filterSet[k]; });
                var rows = listData.filter(function(d) {
                    if (af.length>0 && af.indexOf(d.type)<0) return false;
                    if (q && (d.name+d.part+d.user).toLowerCase().indexOf(q)<0) return false;
                    return true;
                });
                rows.sort(function(a,b) {
                    var va,vb;
                    if (sortCol==='rate')     { return sortAsc?(parseFloat(a.rate)||0)-(parseFloat(b.rate)||0):(parseFloat(b.rate)||0)-(parseFloat(a.rate)||0); }
                    if (sortCol==='sim_time') { return sortAsc?(a.sim_time||0)-(b.sim_time||0):(b.sim_time||0)-(a.sim_time||0); }
                    if (sortCol==='name')   { va=a.name;   vb=b.name; }
                    else if (sortCol==='status') { va=a.type;   vb=b.type; }
                    else if (sortCol==='part')   { va=a.part;   vb=b.part; }
                    else if (sortCol==='user')   { va=a.user;   vb=b.user; }
                    else if (sortCol==='update') { va=a.update; vb=b.update; }
                    else { va=''; vb=''; }
                    if (va<vb) return sortAsc?-1:1;
                    if (va>vb) return sortAsc?1:-1;
                    return 0;
                });
                if (!rows.length) {
                    document.getElementById('list-body').innerHTML='<tr><td colspan="8" style="text-align:center;color:#484f58;padding:24px;">ไม่พบข้อมูล</td></tr>';
                    return;
                }
                var html='';
                rows.forEach(function(d) {
                    var pc = getPartBgColor(d.part);
                    var pillC = {run:'pill-run',stop:'pill-stop',alarm:'pill-alarm',offline:'pill-off'}[d.type]||'pill-off';
                    var rn = parseFloat(d.rate)||0;
                    var rc = rn>=80?'#1aff6e':rn>=50?'#ffd23f':'#ff4d4d';
                    var sp='<span class="sp-mini">';
                    d.spindles.forEach(function(on){ sp+='<span class="sp-dot'+(on?' on':'')+'"></span>'; });
                    sp+='</span>';
                    html+=
                        '<tr>'+
                        '<td style="font-weight:900;color:#fff;font-size:15px;">'+d.name+'</td>'+
                        '<td><span class="pill '+pillC+'">'+d.label+'</span></td>'+
                        '<td><span class="color-swatch" style="background:'+pc.bg+'"></span>'+(d.part||'—')+'</td>'+
                        '<td style="color:#8b949e;">'+(d.user||'—')+'</td>'+
                        '<td><div class="rate-bar-wrap">'+
                            '<div class="rate-bar"><div class="rate-fill" style="width:'+rn+'%;background:'+rc+'"></div></div>'+
                            '<span class="rate-text" style="color:'+rc+'">'+d.rate+'%</span>'+
                        '</div></td>'+
                        '<td>'+sp+'</td>'+
                        '<td style="color:#ffe082;font-weight:700;text-align:right;">'+
                            (d.sim_time>0?(function(s){var h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sc=s%60;return h+':'+String(m).padStart(2,'0')+':'+String(sc).padStart(2,'0');})(d.sim_time):'—')+
                        '</td>'+
                        '<td style="color:#484f58;font-size:11px;">'+(d.update||'—')+'</td>'+
                        '</tr>';
                });
                document.getElementById('list-body').innerHTML=html;
            }

            /* ===== CARD DISPLAY MODE ===== */
            var cardDisplayMode = 'rate';
            function setCardDisplay(mode) {
                cardDisplayMode = mode;
                // อัพเดท card ที่แสดงอยู่ทันที
                var cards = document.querySelectorAll('#dashboard .card[data-runtime]');
                cards.forEach(function(card) {
                    var rateEl = card.querySelector('.run-rate');
                    if (!rateEl) return;
                    if (mode === 'runtime') {
                        var s = parseInt(card.getAttribute('data-runtime')||'0');
                        rateEl.textContent = s>0?(function(s){var h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sc=s%60;return h+':'+String(m).padStart(2,'0')+':'+String(sc).padStart(2,'0');})(s):'—';
                    } else {
                        rateEl.textContent = card.getAttribute('data-runrate')+'%';
                    }
                });
            }

            /* ===== MAIN UPDATE ===== */
            function updateDashboard() {
                fetch('/api/machines')
                    .then(function(r){ return r.json(); })
                    .then(function(data) {

                        /* Section 1: Part Summary */
                        var ps={};
                        Object.keys(data).forEach(function(k) {
                            var info=data[k];
                            var part=(info.part_no&&info.part_no.trim()!=='')?info.part_no.trim():'(ไม่มี Part No.)';
                            if(!ps[part]) ps[part]={run:0,stop:0,alarm:0};
                            var si=getStatusInfo(info.status);
                            if(si.type==='run')   ps[part].run++;
                            if(si.type==='stop')  ps[part].stop++;
                            if(si.type==='alarm') ps[part].alarm++;
                        });
                        var sp=Object.keys(ps).sort(), tr=0,ts=0,ta=0,tb='';
                        sp.forEach(function(part) {
                            var s=ps[part]; tr+=s.run; ts+=s.stop; ta+=s.alarm;
                            var tot=s.run+s.stop+s.alarm;
                            tb+='<tr><td>'+part+'</td>'+
                                '<td class="badge-cell badge-run">'+(s.run>0?s.run:'<span style="color:#2d3540">0</span>')+'</td>'+
                                '<td class="badge-cell badge-stop">'+(s.stop>0?s.stop:'<span style="color:#2d3540">0</span>')+'</td>'+
                                '<td class="badge-cell badge-alarm">'+(s.alarm>0?s.alarm:'<span style="color:#2d3540">0</span>')+'</td>'+
                                '<td class="badge-total">'+tot+'</td></tr>';
                        });
                        if(!sp.length) tb='<tr><td colspan="5" style="text-align:center;color:#484f58;padding:20px;">ยังไม่มีข้อมูล</td></tr>';
                        document.getElementById('summary-body').innerHTML=tb;
                        document.getElementById('foot-run').textContent=tr;
                        document.getElementById('foot-stop').textContent=ts;
                        document.getElementById('foot-alarm').textContent=ta;
                        document.getElementById('foot-total').textContent=tr+ts+ta;

                        /* Section 2: Machine Map */
                        var allM=Object.keys(mapLayout);
                        Object.keys(data).forEach(function(k){ if(allM.indexOf(k)<0) allM.push(k); });
                        allM.sort();
                        var mb='';
                        allM.forEach(function(m) {
                            var info=data[m], gp=mapLayout[m];
                            var gs=gp?('--map-c:'+gp.c+';--map-r:'+gp.r+';'):'';
                            if(!info) {
                                mb+='<div class="card card-offline" style="'+gs+'">'+
                                    '<div class="top-row"><h2 class="machine-name" style="color:#555;">'+m+'</h2></div>'+
                                    '<div class="part-no" style="color:#555;">OFFLINE</div></div>';
                                return;
                            }
                            var si=getStatusInfo(info.status), pc=getPartBgColor(info.part_no);
                            var spH='';
                            info.spindles.forEach(function(on){ spH+='<div class="spindle '+(on?'sp-on':'')+'"></div>'; });
                            var safePart=(info.part_no||'').replace(/"/g,'&quot;');
                            var rtSec = info.sim_time||0;
                            var rtStr = rtSec>0?(function(s){var h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sc=s%60;return h+':'+String(m).padStart(2,'0')+':'+String(sc).padStart(2,'0');})(rtSec):'—';
                            var displayVal = cardDisplayMode==='runtime'?rtStr:(info.run_rate+'%');
                            mb+='<div class="card '+si.cardClass+'" data-type="'+si.type+'" data-part="'+safePart+'" data-runtime="'+rtSec+'" data-runrate="'+info.run_rate+'" style="background:'+pc.bg+';'+gs+'">'+
                                '<div class="top-row"><h2 class="machine-name">'+m+'</h2><div class="run-rate '+si.textClass+'">'+displayVal+'</div></div>'+
                                '<div class="part-no">'+(info.part_no||'---')+'</div>'+
                                '<div style="display:flex;justify-content:space-between;align-items:flex-end;">'+
                                '<div class="user-info">'+(info.user||'NONE')+'</div>'+
                                '<div class="spindle-container">'+spH+'</div></div></div>';
                        });
                        document.getElementById('dashboard').innerHTML=mb;
                        updatePartSelect(data);
                        applyMapFilter();

                        /* Section 3: List Table */
                        listData=[];
                        Object.keys(data).forEach(function(m) {
                            var info=data[m], si=getStatusInfo(info.status);
                            listData.push({
                                name:m, type:si.type, label:si.label,
                                part:info.part_no||'', user:info.user||'',
                                rate:info.run_rate||'0.0',
                                spindles:info.spindles||[],
                                sim_time:info.sim_time||0,
                                update:info.last_update||''
                            });
                        });
                        renderList();
                    })
                    .catch(function(){});
            }

            /* init sort indicator */
            document.getElementById('th-name').classList.add('sort-asc');
            setInterval(updateDashboard, 5000);
            updateDashboard();
        </script>
    </body>
    </html>
    """

    return render_template_string(html_template)


# ================= Web Server Control =================
def run_web_server():
    try:
        # ใช้ Waitress รับโหลด และป้องกันคอขวด
        serve(app, host='0.0.0.0', port=WEB_PORT, threads=6)
    except OSError as e:
        # ดักจับพอร์ตชน (Zombie Process)
        err_root = tk.Tk()
        err_root.withdraw()
        err_root.attributes("-topmost", True)
        messagebox.showerror(
            "CRITICAL SYSTEM ERROR", 
            f"ไม่สามารถเปิดพอร์ต {WEB_PORT} ได้!\n\nสาเหตุ: มีโปรแกรมค้างอยู่ในระบบ (Zombie Process)\nไปที่ Task Manager แล้ว End Task โปรแกรมนี้ทิ้งก่อนรันใหม่",
            parent=err_root
        )
        logging.error(f"Port {WEB_PORT} in use. Server failed to start.")
        os._exit(1)
    except Exception as e:
        logging.error(f"Web Server Crash: {e}")
        os._exit(1)

# ================= GUI Control Panel =================
if __name__ == "__main__":
    threading.Thread(target=data_collector, daemon=True).start()
    threading.Thread(target=run_web_server, daemon=True).start()

    root = tk.Tk()
    root.title("COMPEQ Background Server")
    root.geometry("320x160")
    root.resizable(False, False)
    root.configure(bg="#0d1117")

    def on_closing():
        pwd = simpledialog.askstring("Security Check", "กรุณาใส่รหัสผ่านเพื่อปิดระบบ:", show='*', parent=root)
        if pwd == PASSWORD_TO_CLOSE:
            root.destroy()
            os._exit(0) # บังคับปิดทุก Thread เด็ดขาด
        elif pwd is not None:
            messagebox.showerror("Access Denied", "รหัสผ่านไม่ถูกต้อง!", parent=root)

    root.protocol("WM_DELETE_WINDOW", on_closing)

    tk.Label(root, text="🏭 COMPEQ Dashboard", font=("Helvetica", 14, "bold"), bg="#0d1117", fg="#58a6ff").pack(pady=(15, 5))
    tk.Label(root, text=f"Service is running on Port: {WEB_PORT}", font=("Helvetica", 10), bg="#0d1117", fg="#8b949e").pack()
    tk.Label(root, text="(Running in Background)", font=("Helvetica", 9), bg="#0d1117", fg="#e3b341").pack()

    stop_btn = tk.Button(root, text="Stop Server", command=on_closing, bg="#f85149", fg="white", font=("Helvetica", 10, "bold"), relief="flat", padx=20)
    stop_btn.pack(pady=15)

    root.mainloop()