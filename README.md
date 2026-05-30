# 🏭 *RIS-Working* Factory Dashboard — Real-Time Machine Monitoring System
### Live production monitoring dashboard for PCB drilling operations — deployed in factory

---

## Overview

A real-time web dashboard that connects directly to factory machine servers via TCP socket, parses raw machine data packets, and displays live production status across all drilling machines — including job progress, spindle status, run rate, and estimated job completion time.

Built to solve a real operational problem: **foremen had no way to see the status of all machines at a glance** without walking the floor or checking each machine individually. This dashboard gives a live overview from any browser on the factory network.

**Deployed and actively used in production at *RIS-Working* Manufacturing Co., Ltd.**

---

## Features

- **Live machine data** — refreshes every 5 seconds, pulls directly from factory system via TCP socket
- **Run Rate (MOR)** — calculated in real-time from online/stop seconds reported by each machine
- **Job Completion ETA** — estimates remaining time based on cycle time from PN config vs. current elapsed job time
- **Spindle Status** — visual indicator for each of 6 spindles per machine (active/inactive)
- **Part Number & Stack info** — loaded from factory PN config file, matched to running job
- **Dual view** — Card view for quick floor overview, Table view for sortable data
- **Sortable columns** — sort by machine name, run rate, remaining time, ETA
- **Color-coded status** — green (running), yellow (idle), red (alarm/stop)
- **Password-protected shutdown** — Tkinter GUI with password lock to prevent accidental shutdown
- **Production-grade server** — runs on Waitress (not Flask dev server), packaged for floor deployment

---

## System Architecture

```
Factory Machine Servers (TCP)
        │
        │  304-byte data packets @ 10ms interval
        ▼
[Data Collector Thread]  ←── socket connection to 10.61.16.1:6370
        │
        │  Parses: machine name, part no, user, status,
        │          spindle bits, sim_time, online/stop seconds
        ▼
[In-Memory machine_data dict]
        │
        ├──► REST API  /api/machines     → JSON live data
        │             /api/pn_config    → cycle time & stack config
        │
        └──► Web Dashboard  :8080/      → Browser UI (auto-refresh 5s)

[Tkinter GUI]  ←── background control panel + password-protected stop
```

---

## Data Decoded from Packet (304 bytes)

| Byte Range | Field | Description |
|---|---|---|
| 0–19 | Machine Name | ASCII string |
| 24–43 | User Name | Operator logged in |
| 44–99 | Part Number | Running job PN |
| 106 | Machine Status | Status code |
| 107 | Spindle Byte | Bitmask — 6 spindles |
| 110–111 | Sim Time | Current job elapsed time (seconds) |
| 296–299 | Online Seconds | Total online time |
| 300–303 | Stop Seconds | Total stop time |

**Run Rate formula:**
```
Run Rate = (1 - stop_sec / online_sec) × 100%
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Production Server | Waitress |
| Data Collection | TCP Socket (raw binary parsing) |
| Frontend | Vanilla JS, HTML/CSS (served via Flask) |
| GUI | Tkinter |
| Config | CSV-based PN config file |
| Deployment | Packaged as standalone .exe (PyInstaller) |

---

## Key Challenges Solved

**Binary packet parsing** — the factory system sends raw 304-byte binary packets with no documentation. Had to reverse-engineer the packet structure by observing machine states and matching byte positions to known values.

**Real-time ETA calculation** — job completion time is estimated by matching the running part number to a config file containing cycle times, then computing `cycle_time - sim_time`. Handles cases where cycle time is unknown or job has exceeded expected time.

**Multi-machine concurrency** — data collector runs in a separate thread, continuously pulling data from the server and updating a shared dict. Flask serves the API from the main thread with no data race issues for this use case.

**Production deployment** — packaged as a standalone .exe using PyInstaller so it can be deployed on any factory PC without Python installation.

---

## Configuration

Edit the top of `TL2DashboardV13_5.py`:

```python
SERVER_IP   = "10.61.16.1"   # Factory machine server IP
SERVER_PORT = 6370            # TCP port
WEB_PORT    = 8080            # Dashboard web port
PASSWORD_TO_CLOSE = "****"    # Shutdown password
```

PN config is loaded from `D:\CKA30_Database\MGR_PN_Observer.config` — a CSV file containing part number, stack count, and cycle time for each job type.

---

## Screenshots

> *Dashboard screenshots — see `/screenshots` folder*

---

## Status

✅ **Deployed and operational** — running in production at *RIS-Working* Manufacturing, used daily by foremen for production planning and floor monitoring.

---

## About

Built by **Peson Patimin** — Production Engineer at *RIS-Working* Manufacturing Co., Ltd.  
Designed, developed, and deployed independently to solve a real operational visibility problem on the factory floor.

🔗 [LinkedIn](https://linkedin.com/in/rispeson) | [GitHub](https://github.com/pesonpatimin-bit)
