import sys
import hid
from struct import Struct
from enum import IntEnum, IntFlag

#
def _open_hid(vid, pid):
    import hid
    # Newer API
    if hasattr(hid, "Device"):
        return hid.Device(vid=vid, pid=pid)
    # Debian python3-hid API
    d = hid.device()
    d.open(vid, pid)
    return d

def _open_hid(vid, pid):
    import hid
    if hasattr(hid, "Device"):           # hidapi style
        return hid.Device(vid=vid, pid=pid)
    d = hid.device()                      # python3-hid (Debian) style
    d.open(vid, pid)
    return d

def _as_bytes(x):
    # Some HID libs return list[int]; convert to bytes
    return bytes(x) if isinstance(x, list) else x

def _hid_str(dev, which):
    # Works for both APIs
    if hasattr(dev, which):              # hidapi: dev.manufacturer / dev.product / dev.serial
        return getattr(dev, which)
    # python3-hid:
    m = {
        "manufacturer": "get_manufacturer_string",
        "product": "get_product_string",
        "serial": "get_serial_number_string",
    }.get(which)
    return getattr(dev, m)() if m and hasattr(dev, m) else None
#

class Register(IntEnum):
    MAGIC = 0x00
    USBID = 0x08
    AIOC_IOMUX0 = 0x24
    AIOC_IOMUX1 = 0x25
    CM108_IOMUX0 = 0x44
    CM108_IOMUX1 = 0x45
    CM108_IOMUX2 = 0x46
    CM108_IOMUX3 = 0x47
    SERIAL_CTRL = 0x60
    SERIAL_IOMUX0 = 0x64
    SERIAL_IOMUX1 = 0x65
    SERIAL_IOMUX2 = 0x66
    SERIAL_IOMUX3 = 0x67
    VPTT_LVLCTRL = 0x82
    VPTT_TIMCTRL = 0x84
    VCOS_LVLCTRL = 0x92
    VCOS_TIMCTRL = 0x94

class Command(IntFlag):
    NONE = 0x00
    WRITESTROBE = 0x01
    DEFAULTS = 0x10
    RECALL = 0x40
    STORE = 0x80

class PTTSource(IntFlag):
    NONE = 0x00000000
    CM108GPIO1 = 0x00000001
    CM108GPIO2 = 0x00000002
    CM108GPIO3 = 0x00000004
    CM108GPIO4 = 0x00000008
    SERIALDTR = 0x00000100
    SERIALRTS = 0x00000200
    SERIALDTRNRTS = 0x00000400
    SERIALNDTRRTS = 0x00000800
    VPTT = 0x00001000

class CM108ButtonSource(IntFlag):
    NONE = 0x00000000
    IN1 =  0x00010000
    IN2 =  0x00020000
    VCOS = 0x01000000
"""

def read(device, address):
    # Set address and read
    request = Struct('<BBBL').pack(0, Command.NONE, address, 0x00000000)
    device.send_feature_report(request)
    data = device.get_feature_report(0, 7)
    _, _, _, value = Struct('<BBBL').unpack(data)
    return value

def write(device, address, value):
    data = Struct('<BBBL').pack(0, Command.WRITESTROBE, address, value)
    device.send_feature_report(data)

def cmd(device, cmd):
    data = Struct('<BBBL').pack(0, cmd, 0x00, 0x00000000)
    device.send_feature_report(data)

def dump(device):
    for r in Register:
        print(f'Reg. {r.value:02x}: {read(device, r.value):08x}')
"""
def read(device, address):
    # Set address and read
    request = Struct('<BBBL').pack(0, Command.NONE, address, 0x00000000)
    device.send_feature_report(_as_bytes(request))
    data = device.get_feature_report(0, 7)   # some libs return list[int]
    data = _as_bytes(data)
    _, _, _, value = Struct('<BBBL').unpack(data)
    return value

def write(device, address, value):
    payload = Struct('<BBBL').pack(0, Command.WRITESTROBE, address, value)
    device.send_feature_report(_as_bytes(payload))

def cmd(device, cmd_code):
    payload = Struct('<BBBL').pack(0, cmd_code, 0x00, 0x00000000)
    device.send_feature_report(_as_bytes(payload))

def dump(device):
    for r in Register:
        print(f'Reg. {r.value:02x}: {read(device, r.value):08x}')

#aioc = hid.Device(vid=0x1209, pid=0x7388)
aioc = _open_hid(0x1209, 0x7388)

magic = Struct("<L").pack(read(aioc, Register.MAGIC))

if (magic != b'AIOC'):
    print(f'Unexpected magic: {magic}')
    sys.exit(-1)

"""
print(f'Manufacturer: {aioc.manufacturer}')
print(f'Product: {aioc.product}')
print(f'Serial No: {aioc.serial}')
print(f'Magic: {magic}')
"""
print(f"Manufacturer: {_hid_str(aioc, 'manufacturer')}")
print(f"Product:      {_hid_str(aioc, 'product')}")
print(f"Serial:       {_hid_str(aioc, 'serial')}")

if False:
    # Load the hardware defaults
    print(f'Loading Defaults...')
    cmd(aioc, Command.DEFAULTS)

if False:
    # Dump all known registers
    dump(aioc)

ptt1_source = PTTSource(read(aioc, Register.AIOC_IOMUX0))
ptt2_source = PTTSource(read(aioc, Register.AIOC_IOMUX1))

print(f'Current PTT1 Source: {str(ptt1_source)}')
print(f'Current PTT2 Source: {str(ptt2_source)}')

btn1_source = CM108ButtonSource(read(aioc, Register.CM108_IOMUX0))
btn2_source = CM108ButtonSource(read(aioc, Register.CM108_IOMUX1))
btn3_source = CM108ButtonSource(read(aioc, Register.CM108_IOMUX2))
btn4_source = CM108ButtonSource(read(aioc, Register.CM108_IOMUX3))

print(f'Current CM108 Button 1 (VolUP) Source: {str(btn1_source)}')
print(f'Current CM108 Button 2 (VolDN) Source: {str(btn2_source)}')
print(f'Current CM108 Button 3 (PlbMute) Source: {str(btn3_source)}')
print(f'Current CM108 Button 4 (RecMute) Source: {str(btn4_source)}')

if False:
    # Swap PTT1/PTT2
    ptt1_source, ptt2_source = ptt2_source, ptt1_source
    print(f'Setting PTT1 Source to {str(ptt1_source)}')
    write(aioc, Register.AIOC_IOMUX0, ptt1_source)
    print(f'Setting PTT2 Source to {str(ptt2_source)}')
    write(aioc, Register.AIOC_IOMUX1, ptt2_source)

    print(f'Now PTT1 Source: {str(PTTSource(read(aioc, Register.AIOC_IOMUX0)))}')
    print(f'Now PTT2 Source: {str(PTTSource(read(aioc, Register.AIOC_IOMUX1)))}')

if False:
    # Set to AutoPTT on PTT1
    print(f'Setting PTT1 Source to {str(PTTSource.VPTT)}')
    write(aioc, Register.AIOC_IOMUX0, PTTSource.VPTT)
    print(f'Now PTT1 Source: {str(PTTSource(read(aioc, Register.AIOC_IOMUX0)))}')
    print(f'Now PTT2 Source: {str(PTTSource(read(aioc, Register.AIOC_IOMUX1)))}')

if True:
    # Set USB VID and PID (use with caution. Will need changes above to be able to re-configure the AIOC)
    write(aioc, Register.USBID, (0x0d8c << 0) | (0x000c << 16))
    print(f'Now USBID: {read(aioc, Register.USBID):08x}')

if False:
   # Set Volume Button Down to IN2 for HWCOS instead of VCOS and set Volume Up to NONE
   print(f'Setting VolUP button source to {str(CM108ButtonSource.NONE)}')
   print(f'Setting VolDN button source to {str(CM108ButtonSource.IN2)}')
   write(aioc, Register.CM108_IOMUX0, CM108ButtonSource.NONE)
   write(aioc, Register.CM108_IOMUX1, CM108ButtonSource.IN2)
   print(f'Now VolUP button source: {str(CM108ButtonSource(read(aioc, Register.CM108_IOMUX0)))}')
   print(f'Now VolDN button source: {str(CM108ButtonSource(read(aioc, Register.CM108_IOMUX1)))}')

if True:
    # Store settings into flash
    print(f'Storing...')
    cmd(aioc, Command.STORE)
