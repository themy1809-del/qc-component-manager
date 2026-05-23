# Admin Guide — QC Component Manager Web v2.0

> Dành cho IT vận hành. Deploy + monitor + backup.

## 1. Yêu cầu hệ thống

### Server (Windows 11 hoặc Ubuntu 22.04+)

- **CPU**: 2+ cores
- **RAM**: 4 GB tối thiểu (8 GB khuyến nghị cho 8K+ cấu kiện)
- **Đĩa**: 5 GB trống (DB + backup)
- **Python**: 3.11 hoặc 3.12
- **Mạng**: LAN nội bộ phòng QC

### Client (mọi PC trong LAN)

- Trình duyệt Chrome / Edge mới (5 năm gần đây)
- Tablet/phone cũng dùng được nhưng UX tốt nhất trên PC

## 2. Cài đặt lần đầu

### 2.1 Cài Python + dependencies

```bat
# Tải Python 3.11 từ python.org → cài đặt với tick "Add to PATH"
python --version  # phải hiện Python 3.11.x

# Vào thư mục dự án
cd "D:\Workshop AH6-AH9\Cải tiến hồ sơ\Phần mềm hồ sơ\Streamlit_Web_App\web app"

# Tạo venv (recommended)
python -m venv .venv
.venv\Scripts\activate

# Cài thư viện
pip install -r streamlit_qc\requirements.txt
```

### 2.2 Test chạy thủ công

```bat
cd streamlit_qc
streamlit run app.py
```

Mở [http://localhost:8501](http://localhost:8501) — kiểm tra app load OK.

### 2.3 Mở firewall cho port 8501

PowerShell as Admin:

```powershell
New-NetFirewallRule -DisplayName "Streamlit QC" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

Hoặc qua GUI: **Windows Defender Firewall → Advanced → Inbound Rules → New Rule** → TCP 8501 → Allow.

### 2.4 Tìm IP server để báo QC

```bat
ipconfig | findstr IPv4
```

QC vào `http://<IP-server>:8501` từ máy của họ.

## 3. Chạy như Windows Service (production)

Dùng [NSSM](https://nssm.cc/) để Streamlit auto-start khi máy boot + auto-restart khi crash.

### 3.1 Tải NSSM

Download `nssm.exe` → copy vào `C:\Windows\System32\`.

### 3.2 Tạo service

PowerShell as Admin:

```powershell
nssm install StreamlitQC
```

Trong GUI mở ra:

- **Application**:
  - Path: `D:\Workshop AH6-AH9\Cải tiến hồ sơ\Phần mềm hồ sơ\Streamlit_Web_App\web app\.venv\Scripts\python.exe`
  - Startup directory: `D:\Workshop AH6-AH9\Cải tiến hồ sơ\Phần mềm hồ sơ\Streamlit_Web_App\web app\streamlit_qc`
  - Arguments: `-m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true`

- **I/O**:
  - Output: `D:\logs\streamlit_qc.log`
  - Error: `D:\logs\streamlit_qc.err.log`

- **Exit actions**: Restart application (mặc định)

Bấm **Install service**.

### 3.3 Start/Stop service

```bat
nssm start StreamlitQC
nssm stop StreamlitQC
nssm restart StreamlitQC
```

Hoặc qua **Services.msc** → "Streamlit QC".

## 4. Backup định kỳ

### 4.1 Cách 1: dùng UI

QC/Admin vào page **⚙ Quản trị → 💾 Backup** → bấm "Tạo backup ngay" → tải .zip.

### 4.2 Cách 2: script tự động (.bat)

Tạo file `D:\backups\backup_qc.bat`:

```bat
@echo off
setlocal
set DB="D:\Workshop AH6-AH9\Cải tiến hồ sơ\Phần mềm hồ sơ\Streamlit_Web_App\web app\streamlit_qc\data\qc_components.db"
set DEST=D:\backups\qc
set TS=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
set TS=%TS: =0%

if not exist %DEST% mkdir %DEST%

REM Force WAL checkpoint trước khi copy
echo PRAGMA wal_checkpoint(FULL); | sqlite3 %DB%

copy %DB% "%DEST%\qc_%TS%.db"
echo Backup created: %DEST%\qc_%TS%.db

REM Xoá backup cũ hơn 30 ngày
forfiles /p %DEST% /s /m *.db /d -30 /c "cmd /c del @path" 2>nul
```

### 4.3 Schedule task chạy hằng đêm 23:00

```bat
schtasks /create /tn "QC Backup" /tr "D:\backups\backup_qc.bat" /sc daily /st 23:00 /ru SYSTEM
```

### 4.4 Khuyến nghị

- Backup hằng đêm vào ổ khác (D: thì backup sang E:)
- Mỗi tuần copy backup sang NAS / Google Drive
- Mỗi tháng test restore 1 lần để đảm bảo backup work

## 5. Restore khi mất dữ liệu

### Cách 1: dùng UI (recommended)

1. Stop service: `nssm stop StreamlitQC`
2. Backup file hiện tại sang chỗ khác (đề phòng)
3. Start service lại
4. Vào page **⚙ Quản trị → 💾 Restore**
5. Upload file backup `.db` hoặc `.zip`
6. App sẽ tự đóng connection cũ
7. **Restart service** lần nữa: `nssm restart StreamlitQC`

### Cách 2: thủ công

1. Stop service
2. Copy file backup vào: `streamlit_qc\data\qc_components.db` (ghi đè)
3. Start service

## 6. Monitor

### Xem log

```bat
type D:\logs\streamlit_qc.log
```

Hoặc dùng PowerShell:

```powershell
Get-Content D:\logs\streamlit_qc.log -Tail 50 -Wait
```

### Audit log nghiệp vụ

Vào page **⚙ Quản trị → 📋 Audit Log** — filter theo user/action/ngày.

### Database size

```bat
dir streamlit_qc\data\qc_components.db
```

Khi > 500 MB nên cân nhắc:
- Archive dự án cũ (xoá projects đã hoàn thành sau khi backup)
- Migrate sang PostgreSQL (xem mục 8 dưới)

## 7. Tinh chỉnh hiệu năng

### Config Streamlit

File `streamlit_qc/.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 200          # MB — tăng nếu file PKL > 100 MB
maxMessageSize = 200

[browser]
gatherUsageStats = false     # tắt telemetry

[runner]
fastReruns = true            # nhanh hơn khi user click nhiều
```

### Tăng RAM cho Python (Windows)

Không cần — Python tự manage. Chỉ chú ý nếu RAM máy < 4GB.

## 8. Khi nào migrate sang PostgreSQL?

Hiện tại dùng SQLite (WAL mode) — đủ dùng cho **10-50 user đồng thời** với DB < 1 GB.

Cân nhắc migrate PostgreSQL khi:
- > 50 user truy cập cùng lúc (lock SQLite gây chậm)
- > 1 GB DB
- Cần backup không downtime
- Cần replication / standby

Migration plan (Milestone 7+):
- Thêm SQLAlchemy ORM
- Dùng Alembic migration
- Tạo PostgreSQL container Docker
- Export sqlite → postgres dùng `pgloader`

## 9. Cập nhật app

```bat
# Stop service
nssm stop StreamlitQC

# Pull code mới (nếu dùng git) hoặc copy code
git pull

# Cập nhật deps
.venv\Scripts\activate
pip install -r streamlit_qc\requirements.txt --upgrade

# Start lại
nssm start StreamlitQC
```

## 10. Troubleshooting

| Triệu chứng | Giải pháp |
|---|---|
| App không mở từ máy khác | Check firewall port 8501 + IP server đúng |
| Service không start | Xem log lỗi `D:\logs\streamlit_qc.err.log`, có thể Python path sai |
| DB locked | Restart service. Chỉ xảy ra khi nhiều process cùng ghi. |
| Browser hiện "trang trắng" | Hard refresh `Ctrl+Shift+R` |
| Upload file lỗi | Tăng `maxUploadSize` trong config.toml |

## 11. Liên hệ
- Phát triển: oke (QC Đại Dũng) + Claude AI
- Version: v2.0.0 — May 2026
