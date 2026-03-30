# Bách Hóa Xanh (BHX) - Odoo ERP & POS System 🛒

Repository chứa hệ thống các phân hệ (Odoo Modules / Addons) được phát triển riêng biệt phục vụ cho quy trình quản lý chuỗi siêu thị/bán lẻ **Bách Hóa Xanh**. Hệ thống bao phủ toàn diện từ khâu nhập hàng, quản lý tồn kho, kiểm soát hao hụt cho đến hệ thống bán hàng POS chuyên dụng.

## 📦 Cấu trúc Hệ thống (Modules / Addons)

Hệ thống bao gồm các phân hệ chính nằm trong thư mục `addons/`:

### 1. `bhx_import_goods` (Quản lý Nhập Hàng)
- Quản lý dòng chảy hàng hóa nhập vào từ nhà cung cấp (FMCG).
- Theo dõi đơn mua hàng, quy trình duyệt nhập, và phân bổ hàng hóa vào Kho cửa hàng / Kho trung tâm.
- Tự động hóa quá trình nhận hàng dựa vào cảnh báo thiếu hụt dự trữ.

### 2. `bhx_inventory_display` (Quản lý Kho & Trưng Bày)
- Cốt lõi của hệ thống tồn kho thời gian thực.
- Theo dõi layout kệ hàng, vị trí trưng bày của từng sản phẩm.
- Tự động sinh **Cảnh Báo Tồn Kho (Stock Alerts)** khi hàng hóa dưới định mức, giúp nhân viên bổ sung kệ hàng kịp thời.

### 3. `bhx_audit_control` (Kiểm Soát Kiểm Kê & Hao Hụt)
- Quản lý quy trình kiểm đếm thực tế (Inventory Count) và kiểm soát hàng hóa hiện trường (Goods Control).
- Quản lý quy trình hàng bảo hủy (Disposal).
- **Tích hợp chặt chẽ:** Tự động tạo các phiếu kiểm kê hoặc yêu cầu xử lý từ dữ liệu cảnh báo của `bhx_inventory_display`. Cho phép truy vết (Traceability) ngược về nguồn gốc cảnh báo.

### 4. `bhx_sales` (Hệ Thống Bán Hàng - POS)
- **Kiến trúc Standalone POS**: Giao diện bán lẻ chạy độc lập nhằm tối ưu hiệu năng tối đa, không phụ thuộc CSS/JS gốc của Odoo.
- **Touch-Friendly UI/UX**: Thiết kế phù hợp với màn hình cảm ứng, hỗ trợ Dark Mode.
- Quy trình thanh toán nhanh: Quản lý ca bán hàng, giỏ hàng, tính toán tiền thừa, thanh toán nhanh Quick Cash.
- **Đồng bộ thời gian thực**: Trừ trực tiếp số lượng tồn kho định vị trên kệ hàng ngay khi hoàn tất hóa đơn.

### 5. `bhx_lucky_spin` (Vòng Quay May Mắn)
- Module Gamification phục vụ các chương trình khuyến mãi, quay số trúng thưởng ngay tại điểm bán hoặc trên nền tảng tích hợp.

---

## 🌟 Điểm Nhấn Kiến Trúc & Tự Động Hóa

- **Dashboard Báo Cáo Thông Minh**: Giao diện tổng quan (Overview) cung cấp thông tin "Real-time" về số lượng cảnh báo tồn cần xử lý, đơn nhập, hóa đơn, tỷ lệ hoa hụt/kiểm kê.
- **Luồng Xử Lý Khép Kín (End-to-End Operation)**: 
  *Nhập Hàng* ➔ *Sắp Xếp Lên Kệ* ➔ *Cảnh Báo & Kiểm Đếm Tự Động* ➔ *Bán Hàng & Trừ Kho* ➔ *Bảo Hủy (Nếu Có)*.
- **Giao Diện Thân Thiện**: Các Form View, Tree View và Kanban được thiết kế tinh gọn lại nhằm phù hợp với nhân viên cửa hàng không quen với phần mềm ERP phức tạp.

## 🔧 Hướng Dẫn Cài Đặt (Deployment)

1. **Khởi tạo môi trường Odoo qua Docker**:
   ```bash
   docker-compose up -d
   ```
2. **Kích hoạt Developer Mode** trên giao diện Odoo.
3. **Cập nhật danh sách ứng dụng (Update Apps List)**.
4. **Cài đặt các ứng dụng** theo thứ tự từ core đến nghiệp vụ:
   - `bhx_inventory_display`
   - `bhx_import_goods`
   - `bhx_audit_control`
   - `bhx_sales`
   - `bhx_lucky_spin`
5. **Cấu hình ban đầu**: Tạo dữ liệu Master Data (Sản phẩm, Kho, Kệ Hàng) trước khi vận hành.

---
_Dự án được phát triển và tối ưu để đáp ứng tốc độ cao tại quầy và sự chính xác tuyệt đối trong quy trình quản lý chuỗi cung ứng nội bộ._
