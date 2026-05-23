# 📸 Hướng dẫn chụp ảnh cho slide thuyết trình

> Anh chụp **9 ảnh** sau theo thứ tự. Mỗi ảnh đặt tên đúng để em chèn vào slide.
> Đặt tất cả ảnh vào folder: `D:\...\web app\presentation\images\`

## ⚙️ Trước khi chụp

- Mở app, vào dự án **Phú Quốc** (TCTN.D0.25.066) — đã có dữ liệu sẵn để demo
- Phóng to trình duyệt full màn hình (F11)
- Dùng phím **`Win + Shift + S`** để chụp vùng → dán vào Paint → lưu

---

## 📋 Danh sách 9 ảnh cần chụp

### 1. `01_trang_chu.png` — Slide 4
**Chụp**: Trang chủ app (app.py) — hero banner Navy + Gold
- Vào: `http://<IP>:8501/`
- Chụp **toàn màn hình** (cả top nav)

### 2. `02_tong_quan.png` — Slide 5
**Chụp**: Trang Tổng quan dự án Phú Quốc với 4 KPI + biểu đồ
- Vào: 📊 Tổng quan
- Chụp **cả 4 KPI card + biểu đồ tròn + biểu đồ cột xưởng**

### 3. `03_import_master_upload.png` — Slide 8
**Chụp**: Trang Import Master sau khi upload file Phú Quốc, chưa bấm Import
- Vào: 📥 Import Master
- Upload file Phú Quốc
- Chụp **vùng có dòng "✅ Đã tự động phát hiện..."** + dropdown template

### 4. `04_import_master_ketqua.png` — Slide 9
**Chụp**: Kết quả sau import — phải có cả 2 banner xanh
- Sau khi bấm Import Phú Quốc
- Chụp 2 banner: **"Import thành công"** + **"📋 Phát hiện inspection có sẵn"**
- (Banner thứ 2 ghi 1,160 FUR + 1,089 DGRP)

### 5. `05_import_daily.png` — Slide 11
**Chụp**: Trang Import Daily — radio chọn Fit-up/Final + smart detect
- Vào: 📤 Import Daily
- Chụp **toàn bộ vùng upload + radio + dropdown sheet**

### 6. `06_cau_kien_bang.png` — Slide 12
**Chụp**: Bảng Cấu kiện 8 cột với dữ liệu Phú Quốc
- Vào: 🔧 Cấu kiện
- Chụp bảng có cột **Fit-up 🟢 + Final 🟢 + 2 ngày**
- Đảm bảo có vài dòng 🟢 Đạt và vài dòng ⚪ Chưa để thấy đối lập

### 7. `07_cau_kien_loc.png` — Slide 13
**Chụp**: Bảng Cấu kiện đã filter — bật "🎚 Lọc cột" + chọn workshop AH6
- Bật toggle "Lọc cột"
- Chọn Xưởng = AH6
- Chụp toàn bộ vùng filter + bảng kết quả

### 8. `08_bao_cao.png` — Slide 14
**Chụp**: Trang Báo cáo — biểu đồ + bảng tổng hợp
- Vào: 📊 Báo cáo (hoặc tên page báo cáo của anh)
- Chụp **biểu đồ chính**

### 9. `09_quan_tri.png` — Slide 15
**Chụp**: Trang Quản trị — backup database, audit log
- Vào: ⚙ Quản trị
- Chụp vùng có nút **Backup** + danh sách log

---

## ⚡ Mẹo chụp nhanh

- Chuột phải vào ảnh trong Paint → **Crop** bỏ phần thừa (taskbar, URL bar)
- Tên file phải **đúng chính xác** như list trên (kể cả số 01, 02, ...) — em đã hardcoded trong PPTX
- Nếu thiếu ảnh nào → slide đó sẽ có chữ "**[CHƯA CÓ ẢNH]**" để anh biết

---

## 🎯 Sau khi chụp xong

Báo em **"đã chụp xong"** → em sẽ:
1. Verify đủ 9 ảnh
2. Chèn vào PPTX (nếu chưa có em sẽ build lại)
3. Gửi anh file `.pptx` final

Hoặc anh có thể tự mở `BAI_THUYET_TRINH.pptx` → kéo thả ảnh vào các placeholder (em đặt sẵn box ở chỗ chèn ảnh).
