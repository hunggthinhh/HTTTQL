# API Documentation - POS Standalone Bách Hóa Xanh

Tài liệu này mô tả các điểm cuối (Endpoints) được cung cấp bởi `BHXPosController` cho hệ thống Bách Hóa Xanh Standalone POS.

## Base URL
Tất cả các API được gọi dưới dạng Internal JSON-RPC hoặc HTTP RESTful tại path: `/bhx/pos/`

## 1. Giao diện (HTML Layout)
**Endpoint:** `GET /bhx/pos/web`
- **Mô tả:** Trả về bộ file tĩnh HTML đóng gói sẵn cùng CSS (Dark/Light mode) và JS thuần cho giao diện bán hàng (Standalone POS) Bách Hóa Xanh. Nó không require các module JS native của Odoo UI để khởi chạy.

## 2. API Lấy Dữ Liệu Sản Phẩm & Phân Loại
**Endpoint:** `POST /bhx/pos/get_data`
- **Mô tả:** Lấy danh sách danh mục (Categories) và sản phẩm (Products) kèm thông tin tồn kho thực từ kệ của cửa hàng hiện tại.
- **Request Body:**
  ```json
  {
      "shift_id": 12 
  }
  ```
- **Response:**
  ```json
  {
      "status": "success",
      "categories": [{"id": 1, "name": "Đồ tươi sống"}],
      "products": [{"id": 101, "name": "Thịt heo", "price": 50000, "qty_available": 50}]
  }
  ```

## 3. API Tìm Kiếm Khách Hàng (Tìm theo SĐT)
**Endpoint:** `POST /bhx/pos/search_customer`
- **Mô tả:** Trả về thông tin khách hàng hiện tại dựa theo số điện thoại đã nhập trên Numpad.
- **Request Body:**
  ```json
  {
      "phone": "0901234567"
  }
  ```
- **Response:**
  ```json
  {
      "status": "success",
      "customer": {
          "id": 5,
          "name": "Nguyen Van A",
          "phone": "0901234567"
      }
  }
  ```

## 4. API Xác Nhận Đơn Hàng (Thanh Toán & Trừ Kho)
**Endpoint:** `POST /bhx/pos/validate_order`
- **Mô tả:** Lưu hóa đơn bán hàng vào CSDL, đóng ca và ngay lập tức chạy phương thức trừ tồn kho thực tế ở kệ.
- **Request Body:**
  ```json
  {
      "shift_id": 12,
      "customer_id": 5,
      "lines": [
          {"product_id": 101, "qty": 2, "price": 50000}
      ],
      "amount_total": 100000,
      "payment_method": "cash",
      "amount_paid": 200000
  }
  ```
- **Response:**
  ```json
  {
      "status": "success",
      "order_id": 1005,
      "order_name": "BH/2026/03/00001"
  }
  ```
