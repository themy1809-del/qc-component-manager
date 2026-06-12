# Cloudflare Tunnel — Cho AE QC dùng ngoài mạng LAN

## Khi nào dùng?

AE QC ở **khác mạng** với máy server (ở nhà, ở công trường, máy wifi cá nhân, VPN khác...) → vẫn dùng được app.

## Cách dùng (lần đầu)

### Bước 1 — Bật server Streamlit
Double-click **`START_SERVER.bat`** → chờ thấy dòng:
```
You can now view your Streamlit app in your browser.
```

### Bước 2 — Bật tunnel
Double-click **`START_TUNNEL.bat`** trong cùng thư mục.

- Lần đầu sẽ **tự tải `cloudflared.exe`** (~18MB) — chờ khoảng 30 giây
- Sau đó tunnel khởi tạo và in ra URL kiểu:

```
+--------------------------------------------------------------------------------------------+
|  https://random-words-1234.trycloudflare.com                                               |
+--------------------------------------------------------------------------------------------+
```

### Bước 3 — Gửi URL cho AE QC
Copy URL `https://xxx.trycloudflare.com` đó, gửi vào Zalo/Mess nhóm QC.

AE QC mở Chrome/Edge → dán URL → vào được app ngay (kể cả từ wifi nhà / 4G).

## Lưu ý quan trọng

- **URL đổi mỗi lần chạy lại** — phải gửi URL mới cho AE QC.
- **Tunnel public** — ai biết URL đều vào được. Không gửi URL ra ngoài QC.
- **Phải bật cả 2** — `START_SERVER.bat` + `START_TUNNEL.bat`.
- **Cả 2 cửa sổ đen phải giữ mở** — đóng = tắt.
- **Cần internet** — máy server không có mạng = tunnel không hoạt động.

## Khi đóng app

- Đóng cửa sổ `START_TUNNEL.bat` trước → tunnel tắt
- Đóng cửa sổ `START_SERVER.bat` sau → server tắt

## Nâng cấp sau (tùy chọn)

Nếu muốn URL **cố định không đổi** (vd `qc-daidung.trycloudflare.com`):
- Đăng ký tài khoản Cloudflare miễn phí
- Mua domain (~$10/năm) hoặc dùng subdomain Cloudflare tặng
- Setup "Named Tunnel" — báo anh oke

Nếu chỉ thỉnh thoảng dùng → URL random hiện tại là đủ.
