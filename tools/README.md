# minipid — CLI cho project KiCad MiniPID

Bọc `kicad-cli` và Python `pcbnew` (KiCad 10). Chạy từ bất kỳ thư mục nào:

```
~/Documents/KiCad/MiniPID/tools/minipid <lệnh>
```

| Lệnh | Việc làm | Sửa file? |
|---|---|---|
| `info` | Kích thước board, số linh kiện / net / dây / via / vùng đồng | không |
| `rules` | In luật board và các nhóm net (độ rộng, khe hở, via) | không |
| `check [--json]` | ERC + DRC + so khớp schematic/PCB. Mã thoát 1 nếu DRC có lỗi hoặc còn net chưa nối | không |
| `refill` | Tính lại kết nối và đổ lại toàn bộ vùng đồng | `.kicad_pcb` |
| `sync` | Chép Value và các trường (LCSC, Manufacturer Part…) từ schematic sang footprint | `.kicad_pcb` |
| `fab [-o DIR]` | Gerber + drill (zip), BOM và CPL theo định dạng JLCPCB, gốc toạ độ ở góc dưới trái board | thư mục `fab/` |
| `render [--side top\|bottom\|…] [-o FILE]` | Ảnh 3D PNG | file PNG |

`refill` và `sync` từ chối chạy khi PCB/Schematic Editor đang mở project (có file `~*.lck`) — lưu và đóng editor trước.

Ví dụ quy trình trước khi đặt mạch:

```
minipid sync && minipid refill && minipid check && minipid fab
```
