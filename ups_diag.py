#!/usr/bin/env python3
import smbus, time, csv, datetime, os

I2C_ADDR = 0x42
LOG_PATH = "/home/gabe0000/ups_diag_fixed.csv"

# from your measurements: 54 ≈ battery, 57 ≈ external present
CHARGE_V_THRESH = 56  # >= 56 → call it external/charging

TEST_STEPS = [
    (
        "PI_USB_ONLY",
        "1) POWER Pi from USB (12V->5V)\n"
        "2) UPS SWITCH = ON\n"
        "3) UPS CHARGER = UNPLUGGED\n"
        "Press ENTER when ready..."
    ),
    (
        "PI_USB_ONLY_UPS_SWITCH_OFF",
        "1) KEEP Pi on USB power\n"
        "2) TURN THE UPS SWITCH **OFF** (HAT off)\n"
        "3) UPS CHARGER = UNPLUGGED\n"
        "Press ENTER when ready..."
    ),
    (
        "PI_USB + UPS_CHARGER",
        "1) KEEP Pi USB ON\n"
        "2) TURN UPS back ON (if you turned it off)\n"
        "3) PLUG IN the UPS's own charger\n"
        "Press ENTER when ready..."
    ),
    (
        "UPS_ONLY",
        "1) UNPLUG Pi USB (Pi must stay on from UPS)\n"
        "2) UPS SWITCH = ON\n"
        "3) UPS CHARGER = UNPLUGGED\n"
        "Press ENTER when ready..."
    ),
    (
        "UPS_ONLY + UPS_CHARGER",
        "1) KEEP Pi USB UNPLUGGED\n"
        "2) UPS SWITCH = ON\n"
        "3) PLUG IN the UPS's own charger\n"
        "Press ENTER when ready..."
    ),
]

def read_regs(bus):
    regs = []
    for r in range(8):
        try:
            regs.append(bus.read_byte_data(I2C_ADDR, r))
        except OSError:
            regs.append(None)
    return regs

def infer_state(raw_v, flags):
    # flags on your board lie, so trust voltage first
    if raw_v is None:
        return "UNKNOWN"
    if raw_v >= CHARGE_V_THRESH:
        return "EXT_PWR / CHARGING"
    return "BATTERY / DISCHARGING"

def main():
    bus = smbus.SMBus(1)

    new_file = not os.path.exists(LOG_PATH)
    f = open(LOG_PATH, "a", newline="")
    w = csv.writer(f)
    if new_file:
        w.writerow([
            "timestamp",
            "step",
            "battery_pct",
            "raw_v",
            "inferred",
            "flags",
            "all_regs",
        ])

    print("UPS diag (with UPS-OFF test)\nLogging to:", LOG_PATH, "\n")

    for name, instructions in TEST_STEPS:
        print("\n----------------------------------------------------")
        print("STEP:", name)
        print(instructions)
        input()

        for _ in range(3):
            regs = read_regs(bus)
            pct   = regs[0]
            raw_v = regs[2]
            flags = regs[6]
            inferred = infer_state(raw_v, flags)
            ts = datetime.datetime.now().isoformat(timespec="seconds")

            print(f"[{ts}] {name}: pct={pct}% raw_v={raw_v} → {inferred} "
                  f"(flags=0x{(flags or 0):02X}) regs={regs}")

            w.writerow([
                ts,
                name,
                pct,
                raw_v,
                inferred,
                f"0x{(flags or 0):02X}",
                repr(regs),
            ])
            f.flush()
            time.sleep(2)

    f.close()
    print("\n✅ Done. Open", LOG_PATH, "to review.")

if __name__ == "__main__":
    main()
