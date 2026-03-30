# Push Notifications & Alert Status - Bách Hóa Xanh

Hệ thống Bách Hóa Xanh định nghĩa các Cảnh báo Tồn kho (Stock Alerts) và luồng đồng bộ công việc (Push Notification / Workflows).

## 1. Trạng thái Cảnh báo Kho (Stock Alerts Status)
Một `Cảnh Báo Tồn Kho` (Alert) sinh ra khi sản phẩm trên kệ / tủ vượt khỏi Định Mức tối thiểu. Các ranh giới trạng thái (Status) như sau:

| State Nội Bộ | Hiển Thị (Label) | Diễn Giải | Hành Động Kế Tiếp | Cờ Báo Tại Dashboard |
| --- | --- | --- | --- | --- |
| `draft` | Mới tạo | Cảnh báo vừa được tạo ngầm (CronJob) | Chờ nhân viên hoặc Quản lý ghi nhận | Dấu chấm Đỏ / Push |
| `in_progress`| Đang xử lý | Quản lý kho đã Confirm và đang tạo phiếu Xuất / Nhập | Đang chờ điều chuyển nội bộ | Đang chạy |
| `done` | Hoàn tất | Đã bổ sung đủ Kệ/Kho, Alert được đóng tự động | Lưu trữ lịch sử | Bỏ Cảnh Báo |
| `cancel` | Đã hủy | Bị từ chối do nhầm lẫn hoặc lỗi số liệu | Thông báo người tạo | Bỏ Cảnh Báo |

## 2. Luồng đẩy thông báo tự động (Automated Noti Flow)

1. **Từ Kho Lên POS**: Nếu một mặt hàng hết trong kho trưng bày (Display Location) thì POS tự động vô hiệu hóa thẻ sản phẩm bằng một Notification Overlay ngắn "HẾT HÀNG TẠI KỆ".
2. **Dashboard Badge**: Toàn bộ cảnh báo `draft` của `bhx_inventory_display` được aggregate lại và hiển thị lên Overview Dashboard dưới dạng con số Alert Badge báo màu Đỏ (Ví dụ: `15 Cần Xử Lý`).

## 3. Liên kết luồng Audit (Kiểm Kê / Hao Hụt)
Trong trường hợp nhân viên xử lý Alert phát hiện ra chênh lệch hàng thật và hàng phần mềm, trạng thái Cảnh Báo sẽ kích hoạt:
- Tự động nhảy pop-up `Tạo Phiếu Kiểm Kê Hiện Trường`.
- Tự động thay đổi Trạng thái Cảnh báo qua `Tạo Phiếu Hủy` chờ duyệt từ cấp trưởng phòng nếu là hàng hư hỏng.

## 4. Kiến trúc đồng bộ thông báo
- Notification Odoo Bus hoặc Cron Job quét định kỳ 5 phút/lần.
- Trạng thái chốt từ Cảnh báo -> Tự chuyển trạng thái Đơn hàng và Vòng tuần hoàn xử lý.
