import json
import time
import csv
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

    a_addresses, a_types = ljm.namesToAddresses(len(channel_names), channel_names)

    print("\nScan list:")
    for name, addr in zip(channel_names, a_addresses):
        print(f"  {name} -> address {addr}")

    num_addrs = len(a_addresses)
    return a_addresses, num_addrs, channel_names



def configure_stream_params():
    scan_rate_hz = 1000
    scans_per_read = 1000
    return scan_rate_hz, scans_per_read


def format_influx_line(measurement: str, tags: dict, fields: dict, timestamp_ns: int):
    line = measurement

    if tags:
        tag_parts = []
        for k, v in tags.items():
            if v is None:
                continue
            tag_parts.append(f"{k}={v}")
        if tag_parts:
            line += "," + ",".join(tag_parts)

    field_parts = []
    for k, v in fields.items():
        if isinstance(v, bool):
            v_str = "true" if v else "false"
        elif isinstance(v, (int, float)):
            v_str = f"{v}"
        else:
            v_str = f"\"{v}\""
        field_parts.append(f"{k}={v_str}")

    if not field_parts:
        return None

    line += " " + ",".join(field_parts)

    line += f" {timestamp_ns}"

    return line


def run_stream(handle, scan_list, sensors: list[Sensor], channel_names: list[str], csv_writer):
    scan_rate_hz, scans_per_read = configure_stream_params()
    num_channels = len(channel_names)

    sensor_type_by_name = {s.ain: s.sensor_type for s in sensors}
    diff_by_name = {s.ain: s.differential for s in sensors}

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

    try:
        while True:
            # eStreamRead returns (data, device_backlog, ljm_backlog) in Python
            data, device_backlog, ljm_backlog = ljm.eStreamRead(handle)

            # How many scans did we just get?
            scans = len(data) // num_channels

            for scan_idx in range(scans):
                base = scan_idx * num_channels
                ts_ns = int(time.time() * 1e9)

                for ch_idx, name in enumerate(channel_names):
                    value = data[base + ch_idx]

                    tags = {
                        "device": "T7",
                        "channel": name,
                        "sensor": sensor_type_by_name.get(name),
                        "differential": str(bool(diff_by_name.get(name, False))).lower(),
                    }

                    fields = {
                        "voltage": value,
                    }

                    line = format_influx_line("labjack", tags, fields, ts_ns)
                    if line is not None:
                        print(line)

                    csv_writer.writerow([
                    ts_ns,
                    tags["device"],
                    name,
                    tags["sensor"],
                    tags["differential"],
                    value,
                    ])

            if scans > 0:
                print(
                    f"# scans: {scans}, deviceBacklog: {device_backlog}, "
                    f"LJMBacklog: {ljm_backlog}"
                )

    except KeyboardInterrupt:
        print("\nStopping stream (Ctrl+C detected)...")

    finally:
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

    csv_filename = "labjack_stream.csv"
    print(f"Logging data to {csv_filename}")

    with open(csv_filename, mode="w", newline="", encoding="utf-8") as f:
        csv_writer = csv.writer(f)

        csv_writer.writerow([
            "timestamp_ns",
            "device",
            "channel",
            "sensor_type",
            "differential",
            "voltage",
        ])

        run_stream(handle, scan_list, sensors, channel_names, csv_writer)


if __name__ == "__main__":
    main()
