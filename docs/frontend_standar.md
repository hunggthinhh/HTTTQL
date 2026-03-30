# Frontend Standards - Bách Hóa Xanh POS

Tài liệu này xác định các quy chuẩn lập trình Frontend, bao gồm HTML/CSS/JS cho Standalone POS và giao diện Backoffice của hệ thống Bách Hóa Xanh.

## 1. Kiến trúc Vanilla JS (Standalone POS)
Để tăng tốc độ load tối đa, toàn bộ Giao diện POS không dùng SCSS / QWeb native framework của Odoo.
- **Logic State Control:** State Management quản lý thủ công qua đối tượng Global `S`.
- JS thuần túy không yêu cầu JQuery hay React/VueJS, tương thích trình duyệt Safari cũ trên iPad hoặc màn POS.
- File JS chính: `static/src/js/pos_logic.js`

## 2. Thiết kế CSS / Giao diện người dùng
### a) Design System / Variables
- Thiết kế hệ thống Gradient, Glassmorphism dựa trên biến CSS (CSS Variables) để quản lý màu sắc.
- Cho phép toggle cực tiểu qua mode: Sáng / Tối (Light / Dark Mode).
- Sử dụng font chữ: `Inter`, `Roboto` (Chỉ định rõ trong file CSS).

### b) Responsive Touch-Friendly
- **Target Platform:** Màn hình POS (Ngang), iPad Tablet.
- **Button Sizing:** Diện tích chạm tay tối thiểu 44x44px đối với tất cả nút Numpad, Thanh toán, Chọn hàng.
- Nút "Quick Cash" (Tiền Nhanh) trên Numpad nằm rõ ràng để thu ngân thao tác 1 tay góc dưới phải.
- Form tìm khách hàng hiển thị Pop-up che lấp một phần, tránh cuộn trang.

## 3. Quy chuẩn cho giao diện Backoffice (Odoo Standard + Custom)
- Đối với các màn hình quản lý (Stock Dashboards, Import Data Kanban):
  - Áp dụng `Smart Buttons` ở các form liên kết (VD: Từ màn hình Xử lý tồn kho -> Bấm vào để ra Giao dịch Cảnh báo kho hoặc Yêu cầu duyệt hàng hủy).
  - Sử dụng Notification Badge màu Đỏ cho các Cảnh báo Tồn kho (Pending Alerts).
  - Tích hợp biểu đồ đơn giản bằng các Chart widgets mặc định của Odoo 16/17 (Tùy phiên bản hiện hành).

## 4. Xử lý hoạt ảnh (Micro-animations)
Hệ thống cho phép các micro-animations tinh tế (CSS Transitions ~0.2s) ở:
- Hover nút bấm.
- Click sản phẩm (Nháy lên để báo hiệu cho vào giỏ).
- Cảnh báo hoặc Alert báo Lỗi (Rung nhẹ Numpad).
