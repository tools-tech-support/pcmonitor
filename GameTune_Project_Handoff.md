# GameTune Project — Handoff & Context

> เอกสารสรุปบทสนทนา + สเปคงานทั้งหมด (14 ก.ค. 2026) สำหรับใช้ต่อยอดใน Claude Code
> ครอบคลุม: ข้อมูลเครื่อง → ปัญหา/การวินิจฉัย → BIOS checklist ฉบับเต็ม → สเปคแอป GameTuneLogger → โปรโตคอลเทส → สถานะปัจจุบัน

---

## 1. ข้อมูลเครื่อง (จาก CPU-Z + คู่มือบอร์ด)

| ส่วน | รายละเอียด |
|---|---|
| CPU | Intel Core i9-11900K (Rocket Lake, LGA1200, 8C/16T, TVB สูงสุด 5.3 GHz, Tj Max 105°C) — VID boost เบา ๆ ที่เห็น ~1.484V เป็นค่าปกติของรุ่นนี้ |
| Mainboard | ASRock **H570M-ITX/ac**, BIOS **L1.72** (01/2024) — ชิปเซ็ต H570 **ล็อค CPU ratio OC** (ทำได้แค่ power limit / undervolt / memory) แต่รองรับ Re-Size BAR (Clever Access Memory) |
| GPU | NVIDIA **RTX 5070 Ti 16GB GDDR7** (GB203, TDP 300W) — บนบอร์ดนี้วิ่ง PCIe 4.0 x16 (การ์ดรองรับ 5.0 แต่บอร์ดได้แค่ Gen4) |
| RAM | 32GB = 2x16GB PNY DDR4-3200 XMP 2.0 CL16-18-18-38 1.35V, **dual-rank ทั้งคู่, IC คนละเจ้า: Slot1 = Nanya, Slot2 = Samsung** (จุดเสี่ยงเรื่อง Gear 1) |
| Cooling | **ชุดน้ำ** (water cooling) — ผู้ใช้จะไม่ซื้ออุปกรณ์เพิ่ม |
| การใช้งาน | เล่นเกมเป็นหลัก โดยเฉพาะ **PUBG** (process: `tslgame.exe`) |

**เป้าหมาย (เรียงความสำคัญ):** 1) ไม่ร้อน 2) ไม่ lag 3) performance ภาพรวมดีขึ้น — **กินไฟได้ไม่จำกัด**

---

## 2. ไทม์ไลน์เหตุการณ์ในแชทนี้

1. **จูนรอบแรก** — แนะนำ: XMP + DRAM Gear Mode = Gear 1 (เพราะพบว่าแรมวิ่ง Gear 2 อยู่: Mem Controller 798 MHz = ครึ่งของ DRAM 1596 MHz ทั้งที่ 11900K รองรับ 3200 Gear 1), undervolt offset -0.05V, Above 4G + Re-Size BAR, PL1 200W/PL2 250W, AVX-512 Disabled, fan curve
2. **ผลลัพธ์แย่** — ผู้ใช้รายงาน: เย็นลงเล็กน้อย แต่เกมกระตุกหนักมาก **1% / 0.1% low เหลือ ~15 fps**
3. **วินิจฉัย — ผู้ต้องสงสัย 3 ตัว:**
   - Undervolt ลึกไป หรือเผลอตั้งเป็นโหมด **Fixed** → clock stretching = เฟรมไทม์พังทั้งที่ไม่เด้ง (อันดับหนึ่ง)
   - **Gear 1 บนไฟเลี้ยง VCCSA/VCCIO = Auto** ไม่พอกับแรม dual-rank IC ผสม → memory error / WHEA → กระตุก
   - **ปั๊มน้ำโดน fan curve** → รอบตก → น้ำสะสมความร้อน → thermal throttle เป็นช่วง ๆ (ตรงกับ "เย็นลงแค่นิดเดียว")
4. **ออก BIOS checklist แบบ Phase** (ไฟล์ `BIOS_Tuning_Checklist_H570M-ITXac_11900K.pdf`) — สรุปฉบับเต็มอยู่ข้อ 3 ด้านล่าง
5. **BitLocker recovery โผล่หลังแก้ BIOS** — ปกติ (TPM measurement เปลี่ยน) แก้โดยหา key 48 หลักที่ https://account.microsoft.com/devices/recoverykey (เทียบ Key ID 8 ตัวแรก) และสอนกันเกิดซ้ำ: ก่อนแก้ BIOS ทุกครั้งรัน PowerShell (admin): `manage-bde -protectors -disable C: -RebootCount 2`
6. **ผู้ใช้เลือกพัดลม/ปั๊ม Full Speed ทั้งหมด** แทน curve (รับเสียงได้ เอาเย็นสุด) — อัปเดต checklist แล้ว
7. **สร้างเครื่องมือ GameTuneLogger** (repo zip: `gametune-logger-repo.zip`) เพื่อเก็บ log ตอนเล่น PUBG แล้วส่งกลับมาวิเคราะห์ — สเปคเต็มข้อ 4

---

## 3. BIOS Checklist ฉบับเต็ม (สถานะล่าสุด: พัดลม Full Speed)

### STEP 0 — ล้างค่าก่อน (ห้ามข้าม)
- เข้า BIOS (F2/Del) → F6 เข้า Advanced Mode
- Exit → **Load UEFI Defaults** (F9) → Save Changes and Exit (F10) → เข้า BIOS ใหม่

### PHASE 1 — Stable Base (ต้องหายกระตุกก่อน)

| เมนู | ตัวเลือก | ค่า |
|---|---|---|
| OC Tweaker → DRAM Configuration | Load XMP Setting | XMP 2.0 Profile 1 (DDR4-3200) |
| | DRAM Frequency | Auto (ต้องขึ้น 3200) |
| | **DRAM Gear Mode** | **Auto** (ยอม Gear 2 ชั่วคราวเพื่อพิสูจน์หายกระตุก) |
| | DRAM Voltage | 1.350V |
| OC Tweaker → CPU Configuration | Long Duration Power Limit | 250 W |
| | Long Duration Maintained | 128 (หรือค่าสูงสุด) |
| | Short Duration Power Limit | 250 W |
| | Unlimited Current Limit | Enabled |
| | SpeedStep / Turbo Boost / Speed Shift / TB Max 3.0 | Enabled ทั้งหมด |
| | TVB Voltage Optimizations | Enabled |
| | CPU Tj Max | 105 |
| OC Tweaker → Voltage Configuration | **CPU Core/Cache Voltage** | **Auto — ยกเลิก undervolt ทั้งหมด** (Fixed ค่าต่ำ = clock stretching) |
| | Load-Line Calibration | Auto |
| | VCCSA / VCCIO / อื่น ๆ | Auto |
| Advanced → CPU Configuration | Hyper Threading | Enabled |
| | CPU C States / C1E / C6 / C7 | Enabled / Auto |
| | Package C State Support | Disabled (default) |
| | CPU Thermal Throttling | Enabled |
| | Intel AVX/AVX2 | Enabled |
| | Intel AVX-512 | Disabled |
| Advanced → Chipset Configuration | Primary Graphics Adapter | External (สายจอเสียบการ์ดจอ) |
| | Above 4G Decoding | Enabled |
| | Re-Size BAR Support | Enabled |
| | PCIE1 Link Speed | Auto |
| | ASPM ทั้ง 4 ตัว (PCIE/PCH PCIE/DMI/PCH DMI) | Disabled |
| | IGPU Multi-Monitor | Disabled |
| H/W Monitor | ปั๊มน้ำ | เสียบ CHA_FAN1/WP → W_PUMP Switch = **Water Pump** / เสียบ CPU_FAN1 → CPU Fan 1 = **Full Speed** |
| | CPU Fan 1 / Chassis Fan 1 / Chassis Fan 2 | **Full Speed ทั้งหมด** (ไม่ต้อง Fan Tuning / ไม่ต้อง curve — เอาเย็นสุด แลกเสียงดัง) |
| Boot | CSM | Disabled (จำเป็นต่อ ReBAR) |
| | Fast Boot | Disabled ช่วงจูน |

### TEST 1 (ต้องผ่านครบก่อนไป Phase 2)
- เล่นเกมเดิม 15–20 นาที + HWiNFO64: 1%/0.1% low ปกติ, **WHEA = 0**, CPU Package < 85°C, ไม่มี clock ดิ่งวูบ
- GPU-Z: Resizable BAR = Enabled, Bus = PCIe x16 4.0
- ถ้ายังกระตุก: ปิด ReBAR เทส 1 รอบ (ตัดตัวแปร) → เช็คไดรเวอร์ NVIDIA clean install → ถ้ายังไม่หาย = ไม่ใช่ BIOS

### PHASE 2 — Gear 1 + ไฟเลี้ยงที่ถูกต้อง
- DRAM Gear Mode = **Gear 1**
- **VCCSA = 1.250V, VCCIO = 1.150V** (จุดที่ Auto ให้ไม่พอจนพังรอบแรก)
- TEST 2: TestMem5 (anta777) ≥1 ชม. error = 0 + เกม 20 นาที WHEA = 0 — ไม่ผ่าน → ถอยกลับ Gear Auto/ไฟ Auto จบที่ Gear 2

### PHASE 3 — Undervolt (ทางเลือก ทำท้ายสุด)
- **ข้ามได้เลยถ้าอุณหภูมิเกม < 80°C** (ผู้ใช้บอกกินไฟได้หมด)
- ถ้าทำ: โหมด **Offset (-) เท่านั้น ห้าม Fixed**, เริ่ม -0.030V, ขยับทีละ 0.015V สูงสุด -0.075V, LLC Level 2
- สัญญาณ clock stretching: "ไม่เด้งแต่เฟรม/คะแนนแย่ลง" → ถอย 1 ขั้น

### จบงาน / กู้ชีพ
- OC Tweaker → **Save User Default** เก็บ profile
- ไม่ POST: Clear CMOS jumper **CLRMOS1** (คู่มือหน้า 7 หมายเลข 17) — ถอดปลั๊ก 15 วิ → short 5 วิ → ถอด cap → เปิดเครื่อง
- **ก่อนแก้ BIOS ทุกครั้ง:** `manage-bde -protectors -disable C: -RebootCount 2` (กัน BitLocker ถาม key)

---

## 4. GameTuneLogger — สเปคแอปฉบับเต็ม (สำหรับต่อยอดใน Claude Code)

### 4.1 เป้าหมาย
Background/system-tray logger บน Windows กิน resource ต่ำสุด (CPU <1%, RAM ~100–150MB, ไม่มี overlay) เปิด-ปิดได้จาก tray, ทุกรอบเปิด-ปิด = 1 session → เซฟ log อัตโนมัติ ครบทุกค่าที่ใช้จูน: fps, 1% low, 0.1% low, frametime spike, CPU/GPU temp/clock/power, GPU throttle reason, VRAM, RAM, WHEA errors

### 4.2 สถาปัตยกรรม (เหตุผลการเลือก)
| ชั้น | เทคโนโลยี | เหตุผล |
|---|---|---|
| FPS/frametime | **Intel PresentMon** (console exe, ETW consumer) | passive อ่าน DXGI present events จาก OS — **ไม่ inject เกม** จึงปลอดภัยกับ BattlEye (วิธีเดียวกับ CapFrameX/OCAT) และแม่นระดับ benchmark |
| CPU temp/clock/power | **LibreHardwareMonitorLib.dll** (.NET Framework net472) ผ่าน pythonnet | ทางเดียวที่อ่าน CPU Package temp ได้จาก Python บน Windows; ต้อง Run as Administrator (Ring0 driver) |
| GPU | **NVML** (nvidia-ml-py / pynvml) | อ่านผ่านไดรเวอร์ NVIDIA ตรง ๆ รวม throttle reasons bitmask |
| Tray UI | pystray + Pillow | เบา ไม่มี window |
| Packaging | PyInstaller onedir --noconsole, build บน GitHub Actions | ผู้ใช้ไม่ต้องลง Python; exe + DLL + PresentMon.exe อยู่โฟลเดอร์เดียว |

### 4.3 โครง repo (อยู่ใน `gametune-logger-repo.zip`)
```
gametune-logger/
├── gametune_logger.py          # แอปทั้งหมด ไฟล์เดียว (~700 บรรทัด)
├── requirements.txt            # pystray==0.19.5, Pillow, psutil, nvidia-ml-py, pythonnet>=3.0.3
├── README.md                   # คู่มือไทย: สร้าง repo, build, ใช้งาน, โปรโตคอล PUBG, troubleshoot
└── .github/workflows/build.yml # CI build Windows exe
```

### 4.4 โครงสร้างโค้ด `gametune_logger.py`
- **ค่าคงที่:** `POLL_SEC=1.0`, `MAX_STORED_FRAMES=3_000_000`, `FT_COLS=("msbetweenpresents","frametime")`, `BLACKLIST` (dwm/explorer/steam/discord/browser/obs/overlay ฯลฯ)
- **`GpuReader`** — NVML: temp, graphics clock, load, power(W), VRAM used, P-state, throttle reasons (decode bitmask → IDLE/APP_CLK/SW_PWR/HW_SLOW/SYNC/SW_THERM/HW_THERM/PWR_BRAKE/DISP_CLK) ทุกฟิลด์มี try/except คืน None
- **`CpuReader`** — `pythonnet.load("netfx")` → `clr.AddReference("LibreHardwareMonitorLib")` → `Hardware.Computer(IsCpuEnabled=True)`; อ่าน sensors: Temperature "CPU Package" (fallback "Core Max"), Load "CPU Total", Power "CPU Package", Clock = max ของ core clocks
- **`PresentMonRunner`** — spawn `PresentMon.exe --output_file <raw.csv> --stop_existing_session` ด้วย CREATE_NO_WINDOW|CREATE_NEW_PROCESS_GROUP; stop: CTRL_BREAK_EVENT → terminate → kill (fallback chain เพราะ GUI process ส่ง console signal อาจ fail — เสีย tail <1 วิ ยอมรับได้)
- **`FrameParser`** (thread) — tail CSV แบบ streaming, กันบรรทัดครึ่ง (pending buffer):
  - **ไม่พึ่งคอลัมน์เวลาใด ๆ** — สร้าง timeline จาก **cumulative sum ของ frametime ต่อ (app,pid)** → ทนทั้ง schema v1 (`MsBetweenPresents`) และ v2 (`FrameTime`) auto-detect จาก header
  - เก็บต่อ (app,pid): list frametimes (cap 3M), cum time, buckets รายวินาที `[count, sum_ft, max_ft]`
  - จับ `first_row_wall` เพื่อ align กับ sensors (offset = first_row_wall - session_start, คลาด ±1–2 วิ ยอมรับ)
- **`SensorLogger`** (thread, 1 Hz) — รวม CpuReader+GpuReader+psutil (RAM, fallback cpu load/freq); เขียน `sensors.csv` แบบ flush ทุกแถว (crash-safe) + เก็บ dict `samples[elapsed_sec]`
- **`App`** — tray icon เขียว(idle)/แดง(recording), เมนู: Start logging / Stop & save (default = double-click), Open logs folder, Exit; single-instance ผ่าน `CreateMutexW("Global\\GameTuneLoggerMutex")`; ไม่ใช่ admin → MessageBox + relaunch ด้วย ShellExecuteW "runas"
- **การเลือก "เกม" อัตโนมัติ:** process ที่มีเฟรมมากสุดใน session โดยตัด BLACKLIST ก่อน (ต่ำกว่า 300 เฟรม fallback เป็น presenter ใหญ่สุด + WARNING ใน notes) → ไม่ต้อง config ชื่อเกม
- **WHEA:** `wevtutil qe System /q:*[System[Provider[@Name='Microsoft-Windows-WHEA-Logger'] and TimeCreated[timediff(@SystemTime) <= <ms>]]] /f:xml /c:500` → นับ `</Event>`

### 4.5 นิยามสถิติ (สำคัญต่อการวิเคราะห์)
- **avg_fps** = frames / cum_duration
- **1% low** = เอา frametime แย่สุด 1% ของทั้ง session มาเฉลี่ย → แปลง 1000/avg (แบบ CapFrameX "1% low average"); **0.1% low** เช่นเดียวกันที่ 0.1%
- **ft_p99 / ft_p999 / ft_max** (ms), **spikes_gt50ms / gt100ms** (+ ต่อ นาที), **worst_1s_fps**, **worst_10s_avg_fps** (sliding window)
- Sensor aggregates: avg/max ของ cpu/gpu temp+power, cpu_clock_max, gpu_clock_min_under_load (เฉพาะวินาทีที่ gpu_load ≥90%), **gpu_limited_secs** (วินาทีที่ throttle มี THERM/SW_PWR/HW/PWR_BRAKE), ram_used_max, **whea_events**

### 4.6 Output ต่อ session (`logs/session_YYYYMMDD_HHMMSS.zip`)
| ไฟล์ | เนื้อหา |
|---|---|
| `summary.txt` | สรุป human-readable + บล็อก `=== JSON ===` (machine-readable ครบทุกฟิลด์ข้อ 4.5 + top_presenters 5 อันดับ + notes) |
| `timeline.csv` | รายวินาที: `sec,fps,ft_avg_ms,ft_max_ms,cpu_temp_c,cpu_clock_mhz,cpu_load_pct,cpu_power_w,gpu_temp_c,gpu_clock_mhz,gpu_load_pct,gpu_power_w,gpu_vram_mb,gpu_pstate,gpu_throttle,ram_used_gb` |
| `sensors.csv` | เซนเซอร์ดิบ 1 Hz (มี ts, elapsed_s) |
| `presentmon_raw.csv.gz` | frametime ดิบทุกเฟรมทุก process (gzip) |

### 4.7 Build pipeline (`.github/workflows/build.yml`)
- trigger: workflow_dispatch + push main/master; runs-on: windows-latest
- ขั้นตอน: checkout → setup-python 3.11 → `pip install -r requirements.txt pyinstaller` → `gh release download` **PresentMon** (repo GameTechDev/PresentMon, pattern `PresentMon-*-x64.exe`; ตอนตรวจล่าสุด = v2.5.1) → **LHM** (repo LibreHardwareMonitor/LibreHardwareMonitor, pattern `LibreHardwareMonitor.zip` **เท่านั้น — ห้ามใช้ LibreHardwareMonitor.NET.10.zip** เพราะเราต้อง net472 build ให้เข้ากับ pythonnet netfx; ตอนตรวจ = v0.9.6, แตกเอา `LibreHardwareMonitorLib.dll` + `HidSharp.dll`)
- PyInstaller: `--onedir --noconsole --name GameTuneLogger --collect-all pythonnet --collect-all clr_loader --hidden-import pystray._win32`
- copy PresentMon.exe + DLL เข้า `dist/GameTuneLogger/` → upload artifact `GameTuneLogger-win64`

### 4.8 ข้อจำกัด / ความเสี่ยงที่รู้ (ยังไม่ได้เทสบน Windows จริง)
- CTRL_BREAK จาก GUI process อาจส่งไม่ถึง PresentMon → มี terminate fallback (เสียข้อมูล tail เล็กน้อย)
- ชื่อ sensor ของ LHM อาจต่างตามเวอร์ชัน/CPU (โค้ดจับ "CPU Package"/"Core Max"/"CPU Total") — ถ้า temp เป็น None ให้ดู `gametune_debug.log`
- PresentMon เปลี่ยน header ในอนาคต → parser auto-detect แล้ว แต่ควรเช็คถ้า fps = 0
- pystray `notify` บางเครื่องไม่เด้ง toast — ไม่กระทบการเก็บ log
- exe ไม่มี code signing → SmartScreen เตือน (README มีวิธีข้าม)

### 4.9 ไอเดียต่อยอดใน Claude Code (backlog)
1. Global hotkey start/stop (เช่น Scroll Lock) — ไม่ต้อง alt-tab
2. Auto-start/stop เมื่อเจอ/ปิด `tslgame.exe` (poll process list)
3. ปุ่ม "Mark event" ใส่ marker ลง timeline (โดดร่ม/ไฟต์ใหญ่)
4. สร้าง HTML report มีกราฟ (fps vs temp vs clock overlay) ต่อ session อัตโนมัติ
5. เทียบ 2 session (A/B ระหว่าง BIOS phase) ออกตารางส่วนต่าง
6. per-core CPU clock/temp, แยก effective clock
7. รองรับ AMD GPU (ADLX/atiadlxx) และ iGPU
8. config file (blacklist เพิ่ม, poll rate, โฟลเดอร์ log)
9. ลด footprint: rewrite เป็น C#/.NET (ใช้ LHM ตรง ๆ ไม่ต้อง pythonnet)
10. Installer (MSI) + code signing

---

## 5. โปรโตคอลเทส PUBG (ตกลงกันแล้ว)
- **ขั้นต่ำ 15–20 นาทีของเวลาในแมตช์จริง** ต่อ 1 session (สั้นกว่านี้ 0.1% low ตัวอย่างไม่พอ)
- **แนะนำ 2 แมตช์ (~40–50 นาที)** ครบเหตุการณ์: lobby → เครื่องบินคนครบ 100 → โดดร่มลงเมืองใหญ่ (Pochinki/โรงเรียน) → ไฟต์กลางเกม → วงท้าย
- เริ่มบันทึกตั้งแต่ lobby, จบแมตช์ค่อย Stop
- กราฟิกเซตเดิมทุก session ที่จะเทียบกัน / **1 session ต่อ 1 BIOS Phase**
- จดนาทีเหตุการณ์คร่าว ๆ ถ้าจำได้ (ช่วยวิเคราะห์)

## 6. สถานะปัจจุบัน + งานค้าง
- [ ] ผู้ใช้ทำ BIOS checklist Phase 1 (จำ suspend BitLocker ก่อน)
- [ ] สร้าง repo GitHub + build GameTuneLogger ตาม README
- [ ] เก็บ log PUBG ตามโปรโตคอล → ส่ง `session_xxx.zip` กลับมาวิเคราะห์
- เกณฑ์อ่านผลที่จะใช้: **whea_events = 0** (แรมเสถียร), **gpu_limited_secs** (GPU โดน power/thermal limit ไหม), cpu/gpu temp max, worst_1s / worst_10s / 0.1% low เทียบ avg, ช่วงวินาทีที่ fps ดิ่ง → cross-check กับ temp/clock/throttle ใน `timeline.csv`
- ถ้า Phase 1 แล้วยังกระตุก = ปัญหาไม่ใช่ BIOS → ไล่ฝั่ง Windows/driver ต่อ

## ภาคผนวก — คำสั่ง/ลิงก์ที่ใช้บ่อย
- Suspend BitLocker ก่อนแก้ BIOS: `manage-bde -protectors -disable C: -RebootCount 2`
- BitLocker recovery key: https://account.microsoft.com/devices/recoverykey
- PresentMon: https://github.com/GameTechDev/PresentMon (MIT)
- LibreHardwareMonitor: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor (MPL 2.0)
- ตรวจ ReBAR: GPU-Z → Resizable BAR = Enabled / ตรวจ WHEA สด: HWiNFO64 → Windows Hardware Errors
- Clear CMOS: jumper CLRMOS1 (คู่มือ H570M-ITX/ac หน้า 7 หมายเลข 17)
