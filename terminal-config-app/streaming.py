import json
import time
import csv
from datetime import datetime
from labjack import ljm

from sensors import load_sensors_from_json, Sensor


def open_t7(connection_type: str = "USB"):
    print(f"Opening T7 over {connection_type}...")
    handle = ljm.openS("T7", connection_type, "ANY")
    info = ljm.getHandleInfo(handle)
    print(
        f"Opened T7: Device type: {info[0]}, "
        f"Connection type: {info[1]}, Serial: {info[2]}, IP: {info[3]}"
    )
    return handle


def build_scan_list(sensors: list[Sensor]):
    channel_names = [s.ain for s in sensors]
    a_addresses, _ = ljm.namesToAddresses(len(channel_names), channel_names)

    print("\nScan list:")
    for name, addr in zip(channel_names, a_addresses):
        print(f"  {name} -> address {addr}")

    return a_addresses, len(a_addresses), channel_names


def configure_stream_params():
    scan_rate_hz = 1000
    scans_per_read = 1000
    return scan_rate_hz, scans_per_read


def run_stream(handle, scan_list, sensors: list[Sensor], channel_names: list[str]):
    scan_rate_hz, scans_per_read = configure_stream_params()
    num_channels = len(channel_names)

    sensor_type_by_name = {s.ain: s.sensor_type for s in sensors}

    print("\nStarting stream:")
    print(f"  Scan rate:      {scan_rate_hz} Hz")
    print(f"  Channels:       {channel_names}")
    print(f"  Scans per read: {scans_per_read}")

    actual_scan_rate = ljm.eStreamStart(
        handle,
        scans_per_read,
        num_channels,
        scan_list,
        scan_rate_hz,
    )

    print(f"Actual stream scan rate: {actual_scan_rate} Hz")
    print("\nStreaming... press Ctrl+C to stop.\n")

    csvfile = open("data.csv", "w", newline="")
    writer = csv.DictWriter(csvfile, fieldnames=[
        "device",
        "ain",
        "sensor",
        "voltage",
        "measurement",
        "timestamp"
    ])
    writer.writeheader()

    try:
        while True:
            data, device_backlog, ljm_backlog = ljm.eStreamRead(handle)
            scans = len(data) // num_channels

            for scan_idx in range(scans):
                base = scan_idx * num_channels
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                for ch_idx, ain_name in enumerate(channel_names):
                    value = data[base + ch_idx]

                    writer.writerow({
                        "device": "T7",
                        "ain": ain_name,
                        "sensor": sensor_type_by_name.get(ain_name),
                        "voltage": value,
                        "measurement": "sensor_data",
                        "timestamp": timestamp
                    })

            if scans > 0:
                print(
                    f"# scans: {scans}, deviceBacklog: {device_backlog}, "
                    f"LJMBacklog: {ljm_backlog}"
                )

    except KeyboardInterrupt:
        print("\nStopping stream (Ctrl+C detected)...")

    finally:
        csvfile.close()
        ljm.eStreamStop(handle)
        ljm.close(handle)
        print("Stream stopped and device closed.")


def main():
    sensors = load_sensors_from_json("labjack_channels.json")
    if not sensors:
        print("No sensors found in JSON config. Exiting.")
        return

    handle = open_t7("USB")

    for s in sensors:
        s.configure_labjack(ljm, handle)

    scan_list, num_channels, channel_names = build_scan_list(sensors)

    run_stream(handle, scan_list, sensors, channel_names)


if __name__ == "__main__":
    main()
