# PCO → DiGiCo Snapshot Builder (GUI)

A lightweight Python GUI that pulls **Planning Center Online (PCO)** plans and builds **DiGiCo** snapshots over **OSC**.  
Dark-mode UI, preview-before-send, and 0-based snapshot indexing with optional offset for existing shows.  
No grandMA3 integration—this app only targets DiGiCo.

---

## ✨ Features

- **PCO auth & fetch**: enter App ID/Secret, test connection, fetch service types & upcoming plans  
- **Plan times with names + local time**: e.g., `2:00 PM Service — 9:00 AM` (UTC→America/Chicago)  
- **Preview first**: see all snapshot names & DiGiCo indices before anything is sent  
- **Safe indexing**: DiGiCo uses **0** as the first snapshot index; add an offset if your show already has snapshots  
- **Send when ready**: “Send to DiGiCo” button turns green only when there’s something to send  
- **Config persistence**: saves credentials and settings to `config.json` (plain text, local)

---

## 🧰 Requirements

- **Python**: 3.9+ (tested with 3.10–3.13)
- **Python IDE application**
- **Dependencies**:
  ```bash
  pip install requests python-osc ttkbootstrap
  ```
- **PCO**: App ID & Secret (from your Planning Center account)
- **Network**: Your computer must reach the DiGiCo console IP on the configured OSC port

> macOS note: If Tk/ttk looks missing or broken, install Python from python.org (includes Tk), or `brew install python-tk@3.x` for your version.

---

## 🚀 Quick Start

1. **Clone & install**
   ```bash
   git clone <your-repo-url>
   cd <repo-folder>
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt  # or install the three deps listed above
   ```

2. **Run the app**
   ```bash
   python GUI.py
   ```

3. **Connect to PCO**
   - Enter **PCO App ID** and **PCO Secret**
   - Click **Test PCO** (should show “Connected successfully”)

4. **Select Service & Plan**
   - Click **Fetch Service Types**, choose a service type
   - Optionally adjust “Show next (plans)” count, then **Fetch Plans**
   - Select a plan and click **Load Plan Times**

5. **Choose Times & Preview**
   - In **Times & Snapshot Settings**, select one or more time slots (labels include original name + local time)
   - If your show **already has snapshots**, toggle **“Show already has snapshots”** and enter how many (this becomes the index offset)
   - Click **Preview Snapshots** to see the names and **0-based** DiGiCo indices

6. **Setup the External Control on the DiGiCo**
   - Go to External Control options under the Setup tab on the console
   - Select Add Device and add the DiGiCo Pad options (making sure to load the iPad commands allowed at the bottom of the window).
   - Input the IP Address of the computer running the script and assign it a receive and send port. You will use the receive port with this script.
   - Make sure to enable the control by having a green check mark.

8. **Send to DiGiCo**
   - Enter **DiGiCo IP/Host** and **OSC Port**
   - Click **Send to DiGiCo** (you’ll be asked to confirm)

---

## 🖥️ GUI Overview

- **Connections**
  - PCO App ID / Secret
  - DiGiCo IP/Host and OSC Port
  - **Save Config** writes to `config.json` (plain text, local)
- **Service Types & Plans**
  - Fetch service types → choose one → fetch upcoming plans
  - Select plan → **Load Plan Times**
- **Times & Snapshot Settings**
  - Multi-select plan times  
  - Toggle “Show already has snapshots” and set **Existing snapshot count** to apply an index offset
- **Preview**
  - Shows a table with: sequence number, snapshot name (from PCO item title), and **DiGiCo index (0-based)**
  - **Send to DiGiCo** enabled only when preview rows exist
- **Log**
  - Shows progress, errors, and OSC send results

---

## ⚙️ Configuration

A `config.json` is created/updated alongside the script:
```json
{
  "pco_app_id": "...",
  "pco_secret": "...",
  "digico_ip": "10.11.60.2",
  "digico_port": 9000,
  "service_type": { "id": "12345", "name": "Sunday Morning Service" }
}
```

> **Security note:** Credentials are saved in **plain text** because this is a local app by design. If you need more security, consider OS-level keychains or environment variables.

---

## 🧩 How indexing works

- DiGiCo snapshots are **0-based** (`0, 1, 2, …`).  
- If your show already contains **N** snapshots, set **Existing snapshot count = N**.  
  - The first new snapshot is created at index **N**, the second at **N+1**, etc.  
- If your show is empty, leave the toggle off (offset = 0).

---

## 🌎 Time zones

- Plan times are shown as:  
  **`<PCO plan-time name> — <local time in America/Chicago>`**  
- To change the local time zone, edit the top of `GUI.py`:
  ```python
  from zoneinfo import ZoneInfo
  LOCAL_TZ = ZoneInfo("America/Chicago")  # change to your tz, e.g., "America/Denver"
  ```

---

## 🛠️ Troubleshooting

- **`ModuleNotFoundError: No module named 'ttkbootstrap'`**  
  Install it: `pip install ttkbootstrap`

- **`AttributeError: module 'ttkbootstrap' has no attribute 'toast'`**  
  We already guard against this: the app falls back to a standard dialog if toasts aren’t available. No action needed.

- **Empty space at top / content at bottom**  
  Fixed in current code (scroll frame is correctly placed at `row=0`).

- **No snapshots sent**  
  - Ensure **Preview Snapshots** shows items  
  - Verify DiGiCo IP and OSC Port  
  - Check your network/firewall routes to the console

- **PCO authentication fails**  
  - Recheck App ID/Secret  
  - Try **Test PCO** and see the log for details

---

## 📦 Project structure

```
.
├── GUI.py           # Main application
├── requirements.txt # Optional: pin versions of requests, python-osc, ttkbootstrap
└── config.json      # Created after you save settings (ignored by .gitignore recommended)
```

Example `requirements.txt`:
```txt
requests>=2.28
python-osc>=1.8
ttkbootstrap>=1.10
```

> Consider adding `config.json` to `.gitignore` so you don’t commit credentials.

---

## 🔑 Getting Your Planning Center App ID and Secret

To use this app, you need a Planning Center Personal Access Token (PAT) which provides the App ID and Secret.

Log in to Planning Center Online
Go to https://api.planningcenteronline.com/
 with your Planning Center account.

Create a Personal Access Token

Click “Create Personal Access Token”.

Give it a name (e.g., DiGiCo Snapshot Builder).

(Optional) Add a description for clarity.

Save.

Copy your App ID and Secret

After creating the PAT, Planning Center will show you an App ID and a Secret.

Copy both values.

Store them somewhere safe. (You can re-generate if lost, but the Secret won’t be shown again after you leave the page.)

Enter in the App

In the GUI, paste App ID and Secret into the corresponding fields.

Click Test PCO to confirm connection.

⚠️ Important: The Secret is like a password. Keep it private. The app saves credentials locally in config.json (plain text) for convenience. If sharing your repo, be sure .gitignore excludes config.json.

## 🤝 Contributing

- PRs welcome: styling tweaks, more themes, additional time-zone options, improved error messages.
- Please keep the app **DiGiCo-only** (no MA3 code).

---

## 📝 License

MIT
