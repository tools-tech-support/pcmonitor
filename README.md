# GameTuneLogger

โปรแกรม system tray ตัวเบา สำหรับเก็บ log ประสิทธิภาพตอนเล่นเกม (fps, 1% low, 0.1% low, frametime spike, อุณหภูมิ/คล็อก/วัตต์ของ CPU+GPU, สถานะ throttle, RAM, WHEA error) เพื่อเอาไปวิเคราะห์จูน BIOS/เครื่อง

**เครื่องที่ออกแบบให้:** Windows 10/11 + การ์ดจอ NVIDIA (ตัวอื่นใช้ได้แต่ข้อมูล GPU จะหาย)

## มันทำงานยังไง (สั้น ๆ)

| ส่วน | เทคโนโลยี | หมายเหตุ |
|---|---|---|
| FPS / frametime | **Intel PresentMon** (ETW) | อ่าน event จาก Windows โดยตรง **ไม่ inject เข้าเกม** — วิธีเดียวกับ CapFrameX / OCAT จึงไม่มีปัญหากับ anti-cheat ตามปกติ |
| CPU temp/clock/power | **LibreHardwareMonitorLib** | ต้อง Run as administrator |
| GPU temp/clock/power/throttle | **NVIDIA NVML** | ผ่านไดรเวอร์ NVIDIA |

ใช้ resource ต่ำมาก: CPU ~ <1%, RAM ~100–150 MB — ไม่มี overlay ไม่กวนเกม

---

## ขั้นตอนที่ 1 — สร้าง repo และ build exe (ทำครั้งเดียว ~10 นาที)

1. เข้า https://github.com → sign in (หรือสมัครฟรี)
2. มุมขวาบนกด **+** → **New repository** → ตั้งชื่อ `gametune-logger` → เลือก **Private** → กด **Create repository**
3. ในหน้า repo ว่าง ๆ กดลิงก์ **uploading an existing file** → ลากไฟล์ 3 ไฟล์นี้เข้าไป: `gametune_logger.py`, `requirements.txt`, `README.md` → กด **Commit changes**
4. กด **Add file → Create new file** → ช่องชื่อไฟล์พิมพ์ `.github/workflows/build.yml` (พิมพ์เครื่องหมาย `/` แล้ว GitHub จะสร้างโฟลเดอร์ให้เอง) → เปิดไฟล์ `build.yml` ในเครื่องด้วย Notepad → copy เนื้อหาทั้งหมดมาวาง → **Commit changes**
5. ไปแท็บ **Actions** (ถ้ามีปุ่มให้ enable workflows ให้กดก่อน) → เลือก **Build GameTuneLogger (Windows)** → กด **Run workflow** → รอ 5–10 นาทีจนขึ้นติ๊กเขียว
6. กดเข้า run ที่เสร็จแล้ว → เลื่อนลงล่างสุดตรง **Artifacts** → ดาวน์โหลด **GameTuneLogger-win64** → ได้ไฟล์ zip → แตกไฟล์ไว้ที่ไหนก็ได้ เช่น `D:\GameTuneLogger`

> build ทำบนเครื่องของ GitHub ทั้งหมด ไม่ต้องลง Python ในเครื่องตัวเอง — ตัว workflow จะดึง PresentMon.exe และ LibreHardwareMonitorLib.dll เวอร์ชันล่าสุดมาแพ็ครวมให้อัตโนมัติ

## ขั้นตอนที่ 2 — วิธีใช้งาน

1. คลิกขวา `GameTuneLogger.exe` → **Run as administrator** (จำเป็น — อ่าน CPU temp และ ETW ไม่ได้ถ้าไม่ใช่แอดมิน)
   - ครั้งแรก Windows SmartScreen อาจเตือน (exe ไม่มี code signing): กด **More info → Run anyway**
   - ถ้า Defender กักไฟล์ ให้กด Allow (โค้ดทั้งหมดอยู่ใน repo ตรวจได้)
2. จะเห็นไอคอนวงกลม **สีเขียว** ใน system tray (มุมขวาล่าง อาจต้องกดลูกศร ^ )
3. **คลิกซ้าย 2 ครั้ง หรือคลิกขวา → Start logging** ก่อนเข้าแมตช์ → ไอคอนเปลี่ยนเป็น **สีแดง** = กำลังบันทึก
4. เล่นเกมตามปกติ พอจบแมตช์/พอใจแล้ว → คลิกขวาไอคอน → **Stop & save log**
5. โปรแกรมจะเปิดโฟลเดอร์ `logs` ให้อัตโนมัติ — ไฟล์ที่ต้องส่งไปวิเคราะห์คือ **`session_YYYYMMDD_HHMMSS.zip`** (ไฟล์เดียวจบ)

ในไฟล์ zip มี:

| ไฟล์ | ข้างในคือ |
|---|---|
| `summary.txt` | สรุปทั้ง session: avg fps, 1% low, 0.1% low, p99 frametime, spike count, temp/clock/power min-avg-max, วินาทีที่ GPU โดน limit, จำนวน WHEA error |
| `timeline.csv` | ข้อมูลวินาทีต่อวินาที (fps + เซนเซอร์ทุกตัว) — ใช้หาว่ากระตุก "ตอนไหน เพราะอะไร" |
| `sensors.csv` | เซนเซอร์ดิบ 1 Hz |
| `presentmon_raw.csv.gz` | frametime ดิบทุกเฟรม เผื่อเจาะลึก |

โปรแกรมเลือก "เกม" ให้อัตโนมัติ = โปรเซสที่วาดเฟรมมากที่สุดใน session (PUBG = `tslgame.exe`) ไม่ต้องตั้งค่าอะไร

## โปรโตคอลเทสสำหรับ PUBG

- **ขั้นต่ำ: 15–20 นาทีของเวลาในแมตช์จริง** ต่อ 1 session — น้อยกว่านี้ค่า 0.1% low จะมีเฟรมตัวอย่างไม่พอ สรุปผิดได้
- **แนะนำ: 2 แมตช์ต่อเนื่อง (~40–50 นาที)** ให้ครบเหตุการณ์ที่ fps เหวี่ยง: lobby → บนเครื่องบิน (คนครบ 100) → โดดร่มลงเมืองใหญ่ (Pochinki / Hacienda / โรงเรียน) → ไฟต์กลางเกม → วงท้าย
- กด Start **ตั้งแต่อยู่ lobby** แล้วหยุดหลังออกจากแมตช์ (ช่วง loading จะเห็นในไทม์ไลน์เอง แยกได้ตอนวิเคราะห์)
- **ห้ามเปลี่ยน graphics settings กลางทาง** และใช้เซตติ้งเดิมทุก session ที่จะเอามาเทียบกัน
- เทียบผลจูน BIOS: เก็บ **1 session ต่อ 1 Phase** (เช่น Phase 1 หนึ่งไฟล์, Phase 2 หนึ่งไฟล์) แล้วส่งมาคู่กัน
- ถ้าจำได้ จดคร่าว ๆ ว่านาทีไหนเกิดอะไร (เช่น "นาที 3 โดดร่ม Pochinki, นาที 12 ไฟต์ใหญ่") จะช่วยให้วิเคราะห์แม่นขึ้นมาก

## ดูผลด้วย Dashboard ในตัว

คลิกขวาไอคอน tray → **View Dashboard** — เปิดหน้าต่างกราฟ: เลือก session จากแถบซ้าย, KPI 6 ค่า (avg fps / 1% low / 0.1% low / max CPU°C / max GPU°C / WHEA), กราฟ fps + เซนเซอร์ทุกตัว (คลิก legend เพื่อเปิด-ปิดเส้น) และตารางสรุป**ทุก parameter** จาก summary — ค่าไหนหายจะขึ้น MISSING สีแดงพร้อม notes บอกสาเหตุ

## Troubleshooting

| อาการ | แก้ |
|---|---|
| ไม่มีค่า cpu_temp ใน log | 1) ไม่ได้ Run as administrator 2) DLL ของ LibreHardwareMonitor ต้องอยู่ข้าง exe **ครบทั้งชุด** (ไม่ใช่แค่ `LibreHardwareMonitorLib.dll` — build จาก Actions รุ่น v1.0.2 ขึ้นไปแพ็คให้ครบแล้ว) 3) **Windows 11 รุ่นใหม่บล็อก driver WinRing0** — ติดตั้ง [PawnIO](https://pawnio.eu) แล้วเปิดโปรแกรมใหม่ (ดู notes ใน summary.txt จะบอกสาเหตุที่เจอ) |
| fps เป็น 0 / ไม่มีข้อมูลเฟรม | `PresentMon.exe` ไม่อยู่ข้าง exe — ดาวน์โหลดจาก github.com/GameTechDev/PresentMon/releases (ไฟล์ `PresentMon-x.x.x-x64.exe`) เปลี่ยนชื่อเป็น `PresentMon.exe` วางข้าง ๆ |
| notes ขึ้น "live CSV tail failed ... parsed from file after stop" | **ปกติ ไม่ใช่ error** — PresentMon ล็อกไฟล์ CSV ระหว่างอัด โปรแกรมเลยอ่านทั้งไฟล์ตอนกด Stop แทน ข้อมูลครบเหมือนกัน |
| ไม่มีค่า GPU | ไดรเวอร์ NVIDIA ไม่อยู่ / ไม่ใช่การ์ด NVIDIA |
| เปิดแล้วไม่เห็นอะไร | ดูไอคอนใน tray (กดลูกศร ^ มุมขวาล่าง) และดูไฟล์ `gametune_debug.log` ข้าง exe |

## License ของของที่แพ็คมา

- PresentMon — MIT (Intel GameTechDev)
- LibreHardwareMonitorLib — MPL 2.0
