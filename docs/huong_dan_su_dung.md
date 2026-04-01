# Hướng Dẫn Sử Dụng — Hệ Thống BHX Odoo ERP

> Tài liệu này mô tả **thao tác từng bước** cho từng module trong hệ thống.  
> Người dùng cần đăng nhập tại: `http://localhost:8069/web` (hoặc URL Cloudflare được cấp).

---

## MODULE 1: BHX Nhập Hàng (`bhx_import_goods`)

> **Dành cho:** Nhân viên nhận hàng, Quản lý nhập hàng  
> **Mục tiêu:** Ghi nhận hàng hóa từ Nhà cung cấp / Tổng kho vào Kho cửa hàng

### Luồng 1A — Nhập hàng FMCG (Hàng đóng gói, bao bì)

1. Vào **BHX Nhập Hàng → Nhập hàng FMCG → Tạo mới**
2. Điền các thông tin header:
   - **Ngày nhập kho**: Chọn ngày hiện tại
   - **Nhà cung cấp**: Chọn NCC (mặc định: Kho trung tâm)
   - **Kho nhập**: Chọn cửa hàng cần nhập
   - **Số phiếu giao hàng / Biển số xe**: Nhập theo chứng từ giấy đi kèm xe hàng
3. Bấm **"Bắt đầu kiểm hàng"** → Trạng thái chuyển sang `Đang kiểm hàng`
4. Thêm dòng hàng hóa trong bảng chi tiết:
   - **Sản phẩm**: Tìm tên hoặc mã sản phẩm
   - **SL đặt hàng**: Số lượng theo PO / phiếu giao hàng
   - **SL thực nhận**: Đếm thực tế và nhập vào
   - **SL hàng lỗi**: Ghi nhận hàng dập vỡ (nếu có)
   - **Đơn giá**: Kiểm tra và điền nếu chưa có
5. Kiểm tra tổng số lượng và tổng giá trị ở cuối form
6. Bấm **"Hoàn thành nhập kho"**
   - Hệ thống tự tạo phiếu nhập kho Odoo (`stock.picking`)
   - Tự động tăng tồn kho dự trữ tại cửa hàng
   - Tự động đóng các cảnh báo hết hàng của sản phẩm đó

---

### Luồng 1B — Nhập hàng Fresh (Thịt, cá, sữa tươi)

1. Vào **BHX Nhập Hàng → Nhập hàng Fresh → Tạo mới**
2. Điền các thông tin (tương tự FMCG) + thêm:
   - **Hạn sử dụng lô hàng**: Bắt buộc phải điền
3. Trong bảng chi tiết có thêm cột:
   - **Trọng lượng thực nhận (kg)**
   - **Trọng lượng hao hụt (kg)**
4. Các bước còn lại giống Luồng 1A

---

### Luồng 1C — Nhập hàng Rau củ quả

1. Vào **BHX Nhập Hàng → Nhập hàng Rau củ → Tạo mới**
2. Điền thông tin tương tự Fresh
3. Bấm **"Hoàn thành"** để cập nhật kho

---

## MODULE 2: BHX Tồn Kho & Trưng Bày (`bhx_inventory_display`)

> **Dành cho:** Nhân viên kệ, Quản lý cửa hàng  
> **Mục tiêu:** Theo dõi tồn kho tại từng vị trí kệ và xử lý cảnh báo châm hàng

### Luồng 2A — Xem Dashboard Tổng Quan

1. Vào **Bảng điều khiển BHX** → Tab **"Tổng quan"**
2. Xem các thẻ thống kê:
   - **Cảnh báo mới**: Số kệ đang vơi hàng (đỏ = khẩn cấp)
   - **Đang châm hàng**: Số lệnh đang trong tiến trình
   - **Tồn kho thấp**: Số sản phẩm dưới mức Min

---

### Luồng 2B — Xem và Xử lý Cảnh báo Tồn kho

1. Vào **BHX Tồn Kho & Trưng Bày → Cảnh báo tồn kho**
2. Lọc theo **Trạng thái**: `Mới` → ưu tiên xử lý cảnh báo `Khẩn cấp` trước
3. Chọn một cảnh báo → Chọn hành động phù hợp:

| Tình huống | Nút bấm | Kết quả |
|---|---|---|
| Còn hàng trong kho dự trữ | **"Châm hàng"** | Tạo lệnh lấy hàng từ kho ra kệ |
| Hết cả kho dự trữ | **"Tạo đơn nhập hàng"** | Tạo phiếu nhập FMCG/Fresh tự động |
| Hàng cận date, cần kiểm | **"Tạo phiếu kiểm kê"** | Chuyển sang module Kiểm Kê |
| Hàng đã hỏng/hết date | **"Tạo phiếu hủy"** | Chuyển sang module Kiểm Soát |

---

### Luồng 2C — Châm hàng nội bộ (kho dự trữ → kệ)

1. Từ Cảnh báo → Bấm **"Châm hàng"** → Hệ thống tạo **Đợt châm hàng** mới
2. Vào **BHX Tồn Kho → Đợt châm hàng** → Mở đợt đang ở `Nháp`
3. Kiểm tra danh sách sản phẩm và số lượng cần châm
4. Bấm **"Xác nhận"** → Nhân viên ra kho lấy hàng
5. Sau khi đặt hàng lên kệ → Bấm **"Hoàn thành"**
6. Hệ thống cập nhật tồn kệ và đóng cảnh báo

---

### Luồng 2D — Thiết lập Layout Kệ (Lần đầu)

1. Vào **BHX Tồn Kho → Vị trí trưng bày → Tạo mới**
2. Điền tên vị trí (VD: `Kệ A1 - Tầng 2`) và chọn kho
3. Thêm sản phẩm vào bảng: Tồn hiện tại / Mức Min / Mức Max
4. **Lưu** → Hệ thống theo dõi tự động từ đây

---

## MODULE 3: BHX Kiểm Kê & Kiểm Soát (`bhx_audit_control`)

> **Dành cho:** Nhân viên chất lượng, Quản lý cửa hàng  
> **Mục tiêu:** Kiểm đếm tồn kho thực tế và xử lý hàng hỏng/hết hạn

### Luồng 3A — Kiểm đếm tồn kho (Inventory Count)

1. Vào **BHX Kiểm Kê → Phiếu kiểm kê → Tạo mới**
2. Chọn **Loại kiểm kê**: `Đột xuất` hoặc `Định kỳ`
3. Thêm sản phẩm cần kiểm: nhân viên đếm thực tế → nhập **Tồn thực tế**
4. Hệ thống tự tính chênh lệch so với tồn hệ thống
5. Bấm **"Xác nhận"** để ghi nhận kết quả

---

### Luồng 3B — Kiểm soát hàng hóa (Goods Control)

1. Vào **BHX Kiểm Kê → Phiếu kiểm soát → Tạo mới**
2. Chọn loại kiểm: `Ngẫu nhiên` hoặc `Theo cảnh báo`
3. Thêm sản phẩm → Ghi nhận: SL trên kệ / Tình trạng (OK / Cận date / Hỏng)
4. Bấm **"Hoàn thành kiểm soát"**

---

### Luồng 3C — Bảo hủy hàng (Disposal) — Cần Manager duyệt

1. **Nhân viên** tạo **Phiếu hủy hàng** (hoặc từ Cảnh báo hết hạn)
2. Chọn lý do hủy: `Hết hạn` / `Hàng hỏng` / `Khác`
3. Thêm sản phẩm cần hủy với số lượng thực tế
4. Bấm **"Gửi duyệt"** → Phiếu chuyển sang `Chờ duyệt`
5. **Quản lý** xem xét → Bấm **"Phê duyệt"**
6. Hệ thống tự động **trừ tồn kho** và ghi nhận chi phí hao hụt

---

## MODULE 4: BHX Bán Hàng POS (`bhx_sales`)

> **Dành cho:** Thu ngân, Quản lý ca  
> **Mục tiêu:** Xử lý giao dịch bán lẻ nhanh, đồng bộ tồn kho tức thì

### Luồng 4A — Mở ca bán hàng

1. Vào **BHX Bán Hàng → Ca bán hàng → Tạo mới**
2. Điền tên ca, chọn cửa hàng, giờ bắt đầu
3. Bấm **"Mở ca"**

---

### Luồng 4B — Tạo đơn hàng bán lẻ

1. Từ Ca bán hàng → Bấm **"Tạo đơn hàng mới"**
2. Nhập SĐT khách hàng thành viên (nếu có)
3. Thêm sản phẩm: tìm tên → nhập số lượng → hệ thống tự điền đơn giá
4. Chọn chương trình KM và phương thức thanh toán:
   - `Tiền mặt` / `Thẻ` / `Chuyển khoản` / `Ví điện tử` / `Voucher`
5. Bấm **"Thanh toán"**:
   - Ghi nhận đơn hàng
   - **Tự động trừ tồn kho tại kệ trưng bày**
   - In hóa đơn

---

### Luồng 4C — Hoàn hàng

1. Vào **BHX Bán Hàng → Đơn hàng** → Tìm đơn cần hoàn
2. Bấm **"Hoàn hàng"** → Ghi lý do → Xác nhận

---

### Luồng 4D — Đóng ca

1. Vào Ca bán hàng đang mở → Xem báo cáo tổng kết
2. Bấm **"Đóng ca"**

---

## MODULE 5: BHX Vòng Quay May Mắn (`bhx_lucky_spin`)

> **Dành cho:** Thu ngân, Khách hàng

### Luồng 5A — Cấu hình chương trình (Admin)

1. Vào **BHX Lucky Spin → Chương trình khuyến mãi → Tạo mới**
2. Điền tên, điều kiện (hóa đơn tối thiểu), thời gian áp dụng
3. Cấu hình ô giải thưởng: tên / xác suất / loại thưởng
4. **Lưu và Kích hoạt**

---

### Luồng 5B — Thực hiện quay thưởng tại quầy

1. Sau khi thanh toán đơn đủ điều kiện → Hệ thống hiện thông báo
2. Thu ngân mời khách bấm **"Quay"** trên màn hình
3. Kết quả được lưu tự động vào hồ sơ khách (theo SĐT)
4. Thu ngân xác nhận và trao thưởng

---

## Bảng xử lý sự cố nhanh

| Tình huống | Cách xử lý |
|---|---|
| Không thấy module trong menu | Admin cấp quyền tại **Cài đặt → Người dùng** |
| Lỗi "Không đủ quyền truy cập" | Chọn đúng nhóm quyền BHX tương ứng cho user |
| Tồn kho không khớp thực tế | Tạo **Phiếu kiểm đếm đột xuất** để điều chỉnh |
| Cảnh báo không tự động tắt | Kiểm tra CronJob hoặc tắt thủ công sau khi hoàn thành |
