# Mini PID X2

Board điều khiển 2 động cơ DC chổi than có encoder, chạy vòng PID trên STM32F103C8T6. Thiết kế bằng **KiCad 10**, kích thước **55 × 40 mm**.

## Tính năng

- Điều khiển **2 động cơ DC** bằng 2 × **DRV8871** (H-bridge tích hợp, giới hạn dòng bằng R_ILIM 22 kΩ).
- **2 kênh encoder A/B** với điện trở kéo lên 10 kΩ và bộ lọc RC (1 kΩ + 1 nF).
- MCU **STM32F103C8T6**, thạch anh 16 MHz, USB Full-Speed qua cổng **USB-C**.
- Nguồn vào **VIN** (pin 2S–4S, tối đa khoảng 18 V):
  - Chống cắm ngược cực bằng P-MOSFET **AONR21357**, gate được kẹp bằng Zener 10 V.
  - TVS **SMAJ18A** và tụ hóa 100 µF.
  - Cầu chia đo điện áp VIN đưa về ADC.
- **Buck 5 V MP2359** (1,2 A đỉnh, khuyến nghị tải ≤ 1 A), ghép OR bằng diode với VBUS của USB-C.
- **LDO 3,3 V ME6211** cho MCU và encoder.
- 3 ngõ vào điều khiển ngoài (J8), mỗi ngõ có LED báo trạng thái.
- Cổng UART, I2C và SWD riêng; nút RESET, BOOT0 và USER.

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
|---|---|
| `MiniPID_Manual.kicad_pro` / `.kicad_sch` / `.kicad_pcb` | Project KiCad: schematic và PCB |
| `MiniPID_Manual.kicad_sym` | Thư viện symbol riêng của project (MP2359DJ) |
| `MiniPID_Manual.pretty/` | Thư viện footprint riêng |
| `BOM_MuaHang.csv` | Danh sách mua linh kiện đã gộp mã (32 mã, 89 linh kiện mỗi board), có mã LCSC |
| `bom/ibom.html` | Interactive BOM, mở bằng trình duyệt để hỗ trợ hàn |
| `gerber_to_order/` | Gerber nén zip để đặt mạch (JLCPCB, PCBWay, Elecrow, FusionPCB) |
| `tools/` | CLI `minipid` bọc `kicad-cli` và `pcbnew` (xem `tools/README.md`) |
| `legacy/` | Dữ liệu gốc từ EasyEDA Pro (file `.epro`, symbol và footprint đã import) |

## Connector

| Ref | Loại | Chân |
|---|---|---|
| J1 | Nguồn vào | 1 GND, 2 VIN |
| J2 / J3 | JST PH 6P, động cơ 1 / 2 | 1 OUT1, 2 GND, 3 ENC_A, 4 ENC_B, 5 +3V3, 6 OUT2 |
| J4 | USB-C | USB 2.0 FS, CC 5,1 kΩ (thiết bị) |
| J5 | PicoBlade 4P, UART | 1 +3V3, 2 TX, 3 RX, 4 GND |
| J6 | PicoBlade 4P, I2C | 1 GND, 2 +3V3, 3 SDA, 4 SCL |
| J7 | Header 2.54 mm 4P, SWD | 1 +3V3, 2 SWDIO, 3 SWCLK, 4 GND |
| J8 | JST PH 5P, điều khiển | 1 +5V, 2 CTL1, 3 CTL2, 4 CTL3, 5 GND |

> Encoder được cấp **3,3 V** từ J2/J3. Encoder Hall loại 5 V cần kiểm tra lại mức điện áp trước khi dùng.

## Mở và xuất file

```bash
kicad MiniPID_Manual.kicad_pro
```

```bash
kicad-cli sch erc MiniPID_Manual.kicad_sch
```

```bash
kicad-cli pcb drc --schematic-parity MiniPID_Manual.kicad_pcb
```

## Ghi chú thiết kế

- Buck đặt R4 = 49,9 kΩ, R5 = 10 kΩ, cho Vout ≈ 4,85 V. Sau diode OR, rail +5V còn khoảng 4,5 V.
- Đầu ra buck dùng tụ 10 µF 50 V × 2; datasheet MP2359 khuyên khoảng 22 µF.
- MP2359 đang ở trạng thái *Not recommended for new designs* (MPS khuyên chuyển sang MP2331H). Linh kiện vẫn có trên JLCPCB/LCSC: C14259, hoặc bản tương thích MSKSEMI C30197555.
- Gerber trong `gerber_to_order/` được xuất ngày 2026-11-08. Nên xuất lại từ PCB hiện tại trước khi đặt mạch.

## Việc còn tồn

- [ ] Lỗ bắt vít H1–H4 chưa gán net trong schematic (8 lỗi ERC).
- [ ] Đường GND trên F.Cu chạm pad H4 (DRC báo chập mạch và vi phạm khe hở).
- [ ] J1: mã LCSC là XT30PW nhưng footprint đang là terminal Phoenix 5.08 mm.
