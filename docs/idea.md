# Ý tưởng Dự án (Project Idea) - Bách Hóa Xanh Odoo ERP & POS

## 1. Bối cảnh
Hệ thống chuỗi bán lẻ/Siêu thị mini như Bách Hóa Xanh đòi hỏi tốc độ xử lý tại quầy thu ngân (POS) cực kỳ nhanh, khả năng hiển thị tồn kho chính xác theo thời gian thực và quản lý nhân sự/hàng hóa mượt mà. Đặc biệt, luồng xử lý hàng hóa từ lúc nhập hàng (hàng khô, hàng fresh, rau củ) cho đến khi đưa lên kệ, kiểm soát Date và bán qua POS cần phải trơn tru, tạo thành một vòng tuần hoàn khép kín. Việc bóc tách Odoo thành các phân hệ (addons) chuyên biệt giúp tối ưu hóa nghiệp vụ, giảm bớt sự rườm rà của luồng ERP gốc.

## 2. Giải pháp Đồng bộ theo Flow Chuỗi Cung Ứng (Supply Chain Flow)

Hệ sinh thái được thiết kế để hàng hóa chảy qua 4 bước cốt lõi tạo thành 1 chu trình tự động hóa khép kín:

```mermaid
flowchart TD
    %% Node Definitions
    B1("Bước 1 — Nhập hàng (Purchase + Inventory)"):::step
    B2("Bước 2 — Quản lý tồn kho & trưng bày (Inventory)"):::step
    B3("Bước 3 — Kiểm kê & kiểm soát hàng hóa (Inventory)"):::step
    B4("Bước 4 — Bán hàng (Point of Sale)"):::step
    B5("Tồn kho cập nhật tự động sau mỗi giao dịch POS"):::triggerBox

    %% Step 1 Sub-nodes
    N1["Kiểm hàng FMCG<br/>(Nhập kho khô / đóng gói)"]:::subNode
    N2["Nhập rau củ trái cây<br/>(Cân khối lượng thực tế)"]:::subNode
    N3["Nhập hàng Fresh<br/>(Lot + date hết hạn)"]:::subNode

    %% Step 2 Sub-nodes
    K1["Tạo đợt châm hàng<br/>(Internal transfer kho -> kệ)"]:::subNode
    K2["Xử lý kệ trống<br/>(Alert -> bổ sung từ kho)"]:::subNode

    %% Step 3 Sub-nodes
    C1["Kiểm kê hàng Fresh<br/>(Physical inventory count)"]:::subNode
    C2["Kiểm date / cận date<br/>(FEFO + removal strategy)"]:::subNode

    %% Step 4 Sub-nodes
    P1["Thanh toán thu ngân<br/>(POS session -> payment -> receipt)"]:::subNode

    %% Connections
    B1 --- N1 & N2 & N3
    N1 & N2 & N3 -->|hàng vào kho| B2
    
    B2 --- K1 & K2
    K1 <.->|trigger| K2
    K1 & K2 -->|hàng trên kệ| B3

    B3 --- C1 & C2
    C1 -.-|điều chỉnh tồn kho| Mid(( ))
    C2 -.-|đưa ra bán / huỷ| Mid
    Mid -->|hàng sạch, đúng date| B4

    B4 --- P1
    P1 -->|tự động trừ tồn| B5

    B5 -.->|Nếu tồn thấp → trigger châm hàng (quay lại Bước 2)| B2

    %% Styles
    classDef step fill:#e6edff,stroke:#93a5cf,stroke-width:2px,color:#333,font-weight:bold
    classDef subNode fill:#e8f4f8,stroke:#a2c4c9,stroke-width:1px,color:#333
    classDef triggerBox fill:#f5f5f5,stroke:#ccc,stroke-width:1px,color:#333,font-style:italic
```

## 3. Liên kết Logic với Code Module (Architecture Mapping)

Toàn bộ sơ đồ phía trên được "hiện thực hóa" qua các phân hệ (Addons) tương ứng mà chúng ta đã phát triển:

**▶ Bước 1: Nhập hàng (`bhx_import_goods`)**
- Module này trực tiếp xử lý quy trình **FMCG**, **Hàng Rau củ** và **Hàng Fresh**. 
- Nó quản lý việc nhập kho với các thuộc tính cụ thể (ví dụ: Cân nặng đối với rau củ, Lot/Date đối với hàng Fresh) để đưa chính xác vào Kho Cửa Hàng hoặc Kho Trung Tâm.

**▶ Bước 2: Quản lý tồn kho & trưng bày (`bhx_inventory_display`)**
- Module này quản lý "Hàng đã vào kho" lên kệ. 
- Nó xử lý việc **Internal transfer (châm hàng)** từ rổ vị trí kho lưu trữ lên các ngăn kệ trưng bày hiện trường (Display Location).
- Cơ chế **Alert (Xử lý kệ trống)** cũng nằm trong module này: Việc quét định kỳ phát hiện kệ bị khuất hàng/hết hàng để trigger nhân viên bổ sung ngay.

**▶ Bước 3: Kiểm kê & kiểm soát hàng hóa (`bhx_audit_control`)**
- Để có được "Hàng sạch, đúng date" ra POS, module này chạy các quy trình kiểm tra rủi ro.
- Chịu trách nhiệm cho **Kiểm kê hàng Fresh (Physical Count)** và xử lý các sản phẩm cận date. Hàng không đạt sẽ kích hoạt quy trình đẩy ra **Hủy (Disposal)**, hàng đạt mốc an toàn sẽ được cho vào luồng lưu thông báo đến khách.

**▶ Bước 4: Bán hàng (`bhx_sales`)**
- Ứng dụng Standalone POS tiếp nhận "hàng trên kệ", thực hiện quy trình **Thanh toán thu ngân**.
- Logic module được cấu hình để gửi API `/bhx/pos/validate_order` xuống Backend. Lúc này API không đi rườm rà qua Stock Move gốc của Odoo mà sẽ **trừ tồn kho trực tiếp (`tự động trừ tồn`)** vào vị trí hiển thị kệ hàng.

**▶ Vòng Lặp Tự Động (Automation Trigger)**
- Quá trình trừ kho ở Module `bhx_sales` ngay lập tức làm thay đổi số lượng kho ở module `bhx_inventory_display`.
- Nếu phát hiện logic `tồn kho thấp dưới Alert Rule`, hệ thống lại búng cảnh báo cho nhân viên, tự động đóng vòng phản hồi một cách hoàn hảo và khép kín.
