# Solution Architecture (Kiến trúc Giải pháp)

## 1. Tổng quan Kiến trúc
Hệ thống Odoo ERP cho chuỗi Bách Hóa Xanh được xây dựng theo mô hình **Modular Architecture** nhằm đảm bảo tính dễ dàng mở rộng, bảo trì và cô lập lỗi. Đồng thời, phân hệ POS sử dụng kiến trúc **Headless/Standalone UI** giao tiếp qua JSON-RPC Controller.

## 2. Sơ đồ các Layer (Layers Diagram)

```text
[ Client (Browser / POS Touch Screen) ]
       |
       |  (HTTP/RPC, Standalone HTML/JS)
       v
[ Odoo Controllers (Tầng Giao tiếp API) ]
   - POS Controller (/bhx/pos/...)
       |
       |  (ORM Methods)
       v
[ Odoo Models (Tầng Logic Nghiệp vụ & Database) ]
   - bhx.sales (Đơn hàng, Ca bán)
   - bhx.inventory.display (Kệ hàng, Tồn kho, Cảnh báo)
   - bhx.audit.control (Kiểm kê, Xử lý hủy)
   - bhx.import.goods (Nhập hàng)
       |
       v
[ PostgreSQL (Tầng Lưu trữ) ]
```

## 3. Thiết kế Standalone POS (Decoupled UI)
- Tránh dùng XML/QWeb mặc định của POS Odoo vì nó tải rất nhiều thư viện thừa.
- Thay vào đó, tạo một Web Controller `BHXPosController` trả về file HTML tĩnh cùng với CSS & JS thuần (Vanilla JS).
- Giao diện POS tự duy trì state qua biến nội bộ (`object S`), liên lạc với `BHXPosController` qua Fetch/AJAX.

## 4. Giao tiếp giữa các Module
- **Event-Driven / Automated Actions**: Thay vì nhân viên tạo thủ công, hệ thống sử dụng các Cron Jobs / Automated Triggers. 
  - *Ví dụ*: Tồn kho < 10 -> Cảnh báo tồn kho báo động -> Automated Action tạo Yêu cầu nhập hàng hoặc Yêu cầu kiểm kê.
- **Reference (Many2one / One2many)**: Mọi Transaction (Nhập, Bán, Hủy) đều liên kết chặt chẽ tới vị trí kệ chứa hàng (`bhx.display.location.line`) để truy xuất tồn kho thời gian thực.
