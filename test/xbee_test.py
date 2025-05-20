from serial.tools import list_ports
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice
from digi.xbee.models.address import XBee64BitAddress
from digi.xbee.exception import TimeoutException
import sys, re

BAUD = 9600            # same as BD on your radios
TIMEOUT_S = 0.4        # short → snappy but still long enough for an AT reply
PAYLOAD = "Hello, broadcast!"    # ≤ 80‑100 bytes ideal for broadcasts


# ---------------------------------------------------------------------------
# Helper: keep only “USB‑style” device paths
# ---------------------------------------------------------------------------
def usb_serial_ports():
    """
    Yield candidate port paths that *look* like USB serial adapters:
        • macOS:  /dev/tty.usbserial‑*, /dev/tty.usbmodem‑*
        • Linux:  /dev/ttyUSB*, /dev/ttyACM*
        • Win:    COM1 … COM256
    """
    for p in list_ports.comports():
        dev = p.device

        if sys.platform.startswith("darwin"):              # macOS
            yield "/dev/tty.usbserial-D30DTM37"            
#if re.match(r"/dev/tty\.usb(serial)", dev):
               # yield dev

        elif sys.platform.startswith("linux"):             # Linux/RPi
            if re.match(r"/dev/tty(USB|ACM|usb)\d+", dev):
                yield dev

        elif sys.platform.startswith("win"):               # Windows
            if re.match(r"COM\d{1,3}$", dev):              # COM1–COM255
                yield dev


# ---------------------------------------------------------------------------
# Auto‑detect the first live XBee on a *USB* serial port
# ---------------------------------------------------------------------------
def autodetect_xbee_usb(baud=BAUD, timeout_s=TIMEOUT_S):
    """Return the serial‑port path of the first XBee that answers AT commands."""
    for dev in usb_serial_ports():
        try:
            xb = XBeeDevice(dev, baud)
            xb.set_sync_ops_timeout(timeout_s)
            xb.open()

            # Issue any local AT command (e.g. firmware version)
            _ = xb.get_firmware_version()
            xb.close()
            return dev                                # Success!

        except TimeoutException:
            if xb.is_open():
                xb.close()                            # Not an XBee or asleep
        except Exception:                             # busy/permissions/etc.
            pass

    raise RuntimeError("No XBee radio found on USB/COM ports")


# --- DEMO ---------------------------------------------------------------
if __name__ == "__main__":
    port = autodetect_xbee_usb()
    print("Found XBee on", port)
    device = XBeeDevice(port, BAUD)
    device.open()

    # Broadcast address (00‑00‑00‑00‑00‑00‑FF‑FF) is exposed as a constant:
    broadcast = RemoteXBeeDevice(device, XBee64BitAddress.BROADCAST_ADDRESS)

    # Send once; returns after the local radio has aired the frame
    device.send_data(broadcast, PAYLOAD)
    print("Broadcast sent.")

    device.close()
