# คู่มือภาษาไทย

โปรเจกต์นี้มีสองโปรแกรมอิสระบน Python 3.12 + NiceGUI ไม่ต้องใช้ PySide6 และไม่มี installer หรือ EXE

- `Program1_Interface_Tunnel/`: ตรวจ interface และ Shutdown / No Shutdown พร้อมอ่านสถานะกลับ ใช้ port 8080
- `Program2_Dot1x_Recovery/`: recovery จำลอง, import workbook, snapshot, diff และ restore ใช้ port 8081 สำหรับ Internal IT เท่านั้น

**สถานะปัจจุบัน: โปรแกรมจำลองที่ใช้งานได้และมี Cisco SSH adapter สำหรับตรวจใน lab ยังไม่ใช่ implementation ครบทุกข้อของสเปก** ดูรายการที่ยังขาดใน SECURITY_AND_LIMITATIONS.md ห้ามเรียกผลทดสอบจำลองว่าเป็นผลบน hardware

## ติดตั้งครั้งเดียวโดย IT อนุมัติ

ติดตั้ง Python 3.12 จากแหล่งที่องค์กรอนุมัติ เปิด terminal ในโฟลเดอร์โปรแกรมแต่ละตัวแล้วรัน:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

ทำแยกกันทั้งสองโฟลเดอร์ จากนั้นดับเบิลคลิก `run_interface_manager.bat` หรือ `run_dot1x_recovery.bat` แต่ละ launcher เปลี่ยน directory ไปโฟลเดอร์ตัวเอง ตรวจ dependency และเปิด browser อัตโนมัติ ไม่ติดตั้ง package หรือยกระดับสิทธิ์เอง ปิดหน้าต่าง terminal หรือ Ctrl+C เพื่อหยุด server และ session; ปิด browser tab ไม่ได้หยุดงาน

การติดตั้ง offline ให้ IT เตรียม wheels สำหรับ Windows/Python รุ่นเป้าหมายในเครื่องที่อนุญาต:

```bat
python -m pip download --dest wheelhouse -r requirements.txt
.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements.txt
```

ต้องตรวจแหล่งที่มาและ dependency ทั้งหมดตามกระบวนการขององค์กร ไม่จำเป็นต้องต่อ Internet ระหว่างใช้งาน UI

## การใช้งาน

เพิ่ม inventory ด้วย hostname, management_ip, wan_ip, vendor (`cisco` หรือ `huawei` ในโหมดจำลอง) และเลือก checkbox ของอุปกรณ์ก่อนเริ่มงาน CSV/XLSX ใช้ชื่อ column เหมือนแบบฟอร์ม Export ได้ทั้งสองรูปแบบ ไม่มีข้อมูลจริงแถมมา

Program 1 เริ่มด้วย SIMULATED mode, interface ตัวอย่าง `Tunnel90` และ `GigabitEthernet0/0/0` เลือก interface กลางหรือใส่ exceptions แบบ `SW1=Tunnel90;GigabitEthernet0/0/0` แต่ละบรรทัดเป็นคนละเครื่อง Write ต้องยืนยันรายชื่อก่อน ทำงานนอก UI event loop และอ่านสถานะกลับ ไม่มีการ retry write อัตโนมัติเมื่อผลไม่แน่นอน

LIVE LAB ใช้ได้เฉพาะ Cisco Direct SSH ต้องเลือกเองและยืนยันทุกงาน ระบุไฟล์ known_hosts ที่ IT ตรวจ fingerprint/enroll แล้ว โปรแกรมไม่ยอมรับ host key อัตโนมัติ Runtime password ไม่ถูกบันทึกลง SQLite Console และ SSH Jump ที่เลือกได้ตอนนี้เป็นเพียง simulation ไม่ใช่การทดสอบ gateway CLI

Program 2 เลือก switch/port เช่น `Gi1/0/1,Gi1/0/2` แล้ว import workbook หรือกรอก exception `SW1,Gi1/0/1,30` แยกบรรทัดตาม interface ไม่มี override ทั้ง switch กด Preview recovery diff ตรวจ source VLAN และ diff แล้วยืนยัน Snapshot ถูกบันทึกพร้อม checksum ก่อนเปลี่ยนค่า เลือก snapshot เพื่อ Restore ระบบปฏิเสธถ้าค่าปัจจุบันไม่ตรง recovery snapshot

VLAN จำลองที่มีอยู่: 10,20,27,30,40,50 การคืนค่ารักษา authentication, data/voice VLAN และ attributes เดิมทั้งหมด โดยไม่สมมติว่า dynamic VLAN จาก RADIUS คือ static VLAN เดิม

## Workbook ที่รองรับ

ไม่ commit `Vlan_User.xlsx` จริง ใช้ไฟล์ local เท่านั้น:

- `Sum_Vlan` หรือ `Sum Vlan`: column `SW Name`, `VLAN` สำหรับ exact match หรือ `Pattern`, `Floor`, `Side`, `VLAN` สำหรับ pattern แบบ token เช่น `ASW_9_*` wildcard ต้องกินทั้ง token ที่คั่นด้วย `_` ไม่มีการเดารูปแบบ workbook ที่ไม่รู้จัก
- `Sum_switch`: `SW Name`, `IP`, `Vendor`, `Floor`, `Side`, `Site`; Floor/Side ใช้กรอง pattern เมื่อตั้งใน reference แถวนั้น Inventory ถูกนำเข้า GUI ด้วย
- `Special user` หรือ `Specail user`: `SW Name`, `Interface` กำหนด VLAN 27

ลำดับ manual per-interface > special-user > reference; reference ที่ซ้อนกันหรือไม่พบถูกปฏิเสธ ไม่จับ ASW_9_1 เป็น ASW_9_10 โดย prefix และไม่เดา mapping เมื่อมีความกำกวม

## ข้อมูลและการทดสอบ

แต่ละโฟลเดอร์มี `data/state.sqlite3` แยกกัน (gitignore) เก็บ inventory/tasks/snapshots แต่ไม่เก็บ credential โปรแกรมจำลองเก็บ device state ใน memory; restart process แล้วไม่สามารถรับรอง current device state เดิมได้ จึงปฏิเสธ restore แทนการเดา ต้องสำรอง SQLite ตามนโยบายองค์กร

ทดสอบแต่ละโปรแกรมจากโฟลเดอร์ของตัวเอง:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

Browser smoke test ที่ root: ติดตั้ง `playwright==1.64.1`, `python -m playwright install chromium`, แล้ว `python scripts/browser_smoke.py` ใช้ข้อมูล temporary และ port 18080/18081 โดยไม่ต่ออุปกรณ์จริง

CI กำหนด unit tests บน Linux/Windows และ browser test บน Linux; การเพิ่ม workflow ไม่ได้แปลว่า Windows CI ได้รันแล้ว

## แก้ปัญหา

Python ไม่พบ: ให้ IT ตรวจ PATH หรือสร้าง `.venv` ด้วย approved runtime; ห้าม bypass endpoint controls Dependencies ไม่ครบ: ติดตั้งตามขั้นตอน IT-approved ด้านบน Port ซ้ำ: ปิด instance เดิม หรือกำหนด `NETWORK_TOOLS_PORT` ต่างกัน Browser refresh: เลือก task ID เดิมเพื่อดูประวัติ ไม่ส่งงานใหม่อัตโนมัติ Console driver/baud: ยังต้องตรวจใน lab; ไม่มี live console workflow ในรุ่นนี้ Host key ไม่ตรง: หยุดแล้วตรวจ fingerprint กับ IT ห้ามลบ known_hosts เพื่อเลี่ยง Session loss หลัง write: ถือว่าผลไม่แน่นอน ตรวจอุปกรณ์ก่อน retry

ส่งให้ vendor เฉพาะ `Program1_Interface_Tunnel` (ไม่รวม data จริง) ห้ามส่ง Program 2 หรือ workbook ภายในไปด้วย
