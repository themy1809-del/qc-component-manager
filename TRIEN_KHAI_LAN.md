# 🚀 Triển khai LAN — Hướng dẫn cho anh oke

> Mục tiêu: Chạy app trên 1 máy (máy anh), AE QC truy cập qua trình duyệt.

---

## Tổng quan kiến trúc

```
┌──────────────────────┐
│  MÁY ANH (server)    │   ← cài app, chạy 24/7 trong giờ làm
│  Windows + Python    │
│  Database: qc.db     │
│  Port: 8501          │
└──────────┬───────────┘
           │
   ━━━━━━━━┷━━━━━━━━━━━━━━━━ LAN công ty
   │       │       │       │
  QC1     QC2     QC3    QC...
 (Chrome) (Chrome) (Chrome)
```

**Yêu cầu**:
- Máy server **luôn bật** trong giờ làm
- Cùng mạng LAN với các máy QC khác
- Đã cài Python 3.11 + venv (đã làm xong)

---

## ✅ Checklist 5 bước

### **Bước 1 — Xem IP máy server**

Double-click **`GET_MY_IP.bat`** → ghi nhớ IP (vd: `192.168.1.50`)

> ⚠️ Bỏ qua IP `127.0.0.1` (localhost) và `169.254.x.x` (lỗi mạng).
> Lấy IP dạng `192.168.x.x` hoặc `10.x.x.x`.

---

### **Bước 2 — Mở firewall Windows (1 lần duy nhất)**

Mở **PowerShell với quyền Admin**, copy lệnh sau dán vào:

```powershell
New-NetFirewallRule -DisplayName "Streamlit QC App" `
    -Direction Inbound -Protocol TCP -LocalPort 8501 `
    -Action Allow -Profile Any
```

Nếu thành công sẽ in ra bảng có dòng `Enabled: True`.

> 💡 Nếu chưa biết PowerShell Admin: gõ "PowerShell" ở thanh Start →
> chuột phải → **"Run as administrator"** → Yes.

---

### **Bước 3 — Khởi động server**

Double-click **`START_SERVER.bat`**

Cửa sổ đen mở ra hiển thị:
```
Địa chỉ IP LAN:    192.168.1.50
Port:              8501
http://192.168.1.50:8501
```

**⚠️ Đừng đóng cửa sổ này** — đóng = tắt server.

> Nếu muốn ẩn cửa sổ: thu nhỏ (Minimize) thôi, **không bấm X**.

---

### **Bước 4 — Test trên máy anh trước**

Mở Chrome trên **máy của anh**, vào địa chỉ trên → app phải mở được.

Nếu OK → sang Bước 5.

---

### **Bước 5 — Test trên máy QC khác**

Sang 1 máy QC bất kỳ, mở Chrome → gõ địa chỉ → app phải mở được.

✅ Nếu OK → gửi địa chỉ + file **`HUONG_DAN_QC.md`** cho cả nhóm.

❌ Nếu báo "Không kết nối được":
- Kiểm tra 2 máy có cùng mạng không (Wifi cty hay dây cty?)
- Kiểm tra firewall đã mở (Bước 2)
- Tắt VPN trên máy QC (nếu có)

---

## 🔁 Hằng ngày — phải làm gì?

- **Sáng vào**: double-click `START_SERVER.bat` (nếu hôm trước đã tắt máy)
- **Trong ngày**: cửa sổ server **giữ mở** (cho phép minimize)
- **Tối**: có thể tắt server (đóng cửa sổ) nếu muốn

> 💡 **Mẹo**: Đặt shortcut `START_SERVER.bat` vào folder **Startup** của Windows để tự chạy khi anh login.
> Đường dẫn folder Startup: `Win + R` → gõ `shell:startup` → Enter.

---

## 🛟 Backup database (QUAN TRỌNG)

Database lưu ở:
```
D:\Workshop AH6-AH9\Cải tiến hồ sơ\Phần mềm hồ sơ\Streamlit_Web_App\web app\qc.db
```

**Mỗi tuần copy file `qc.db` ra ổ khác hoặc USB**.
Nếu máy hỏng → vẫn còn data.

Hoặc dùng trang **⚙️ Quản trị** trong app → nút **"Backup"**.

---

## 🆘 Khi có sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| AE QC không vào được app | Check máy server có bật không, `START_SERVER.bat` có đang chạy không |
| App chậm / treo | Đóng cửa sổ server → mở lại bằng `START_SERVER.bat` |
| Đổi mạng / đổi máy | Chạy `GET_MY_IP.bat` lại để lấy IP mới, gửi cho AE QC |
| File `qc.db` lỗi | Khôi phục từ bản backup gần nhất (xem mục trên) |

---

## 📁 Các file đã tạo

| File | Mục đích |
|---|---|
| `START_SERVER.bat` | Khởi động server LAN (anh dùng) |
| `GET_MY_IP.bat` | Xem IP máy (anh dùng) |
| `HUONG_DAN_QC.md` | Gửi cho AE QC |
| `TRIEN_KHAI_LAN.md` | File này — anh đọc |

