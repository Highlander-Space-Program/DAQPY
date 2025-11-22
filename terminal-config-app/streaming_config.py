import json
import time
from labjack import ljm  # Requires LabJack LJM driver and Python bindings installed


def load_channels(filename="labjack_channels.json"):
    with open(filename, "r") as f:
        data = json.load(f)
    if isinstance(data, dict) and "Channels" in data:
        data = data["Channels"]

    if not isinstance(data, list):
        raise ValueError("Expected a list of channels in JSON file.")

    ain_channels = []
    for ch in data:
        if not isinstance(ch, dict):
            continue
        if ch.get("Type", "AIN") == "AIN" and "AIN" in ch:
            ain_channels.append(ch)

    if not ain_channels:
        raise ValueError("No AIN channels found in configuration.")

    return ain_channels



def open_t7(connection_type="USB"):
    print(f"Opening T7 over {connection_type}...")
    handle = ljm.openS("T7", connection_type, "ANY")
    info = ljm.getHandleInfo(handle)
    print(f"Opened T7: Device type: {info[0]}, Connection type: {info[1]}, "
          f"Serial: {info[2]}, IP: {info[3]}")
    return handle



def build_scan_list(ain_channels):
    channel_names = [ch["AIN"] for ch in ain_channels] 

    num_addrs, a_addresses, a_types = ljm.namesToAddresses(len(channel_names), channel_names)

    print("\nScan list:")
    for name, addr in zip(channel_names, a_addresses):
        print(f"  {name} -> address {addr}")

    return a_addresses, len(channel_names), channel_names



def configure_stream_params():
    scan_rate_hz = 1000.0
    scans_per_read = 1000 
    return scan_rate_hz, scans_per_read



def format_influx_line(measurement, tags, fields, timestamp_ns):
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



def run_stream(handle, scan_list, num_channels, channel_names, ain_channels):
    scan_rate_hz, scans_per_read = configure_stream_params()
    sensor_by_name = {ch["AIN"]: ch.get("SensorType") for ch in ain_channels}
    diff_by_name = {ch["AIN"]: ch.get("Differential", False) for ch in ain_channels}

    print(f"\nStarting stream:")
    print(f"  Scan rate:      {scan_rate_hz} Hz")
    print(f"  Channels:       {channel_names}")
    print(f"  Scans per read: {scans_per_read}")

    actual_scan_rate = ljm.eStreamStart(handle,
                                        scans_per_read,
                                        num_channels,
                                        scan_list,
                                        scan_rate_hz)

    print(f"Actual stream scan rate: {actual_scan_rate} Hz")
    print("\nStreaming... press Ctrl+C to stop.\n")

    try:
        while True:
            scans, data, device_backlog, ljm_backlog = ljm.eStreamRead(handle)
            # For each scan:
            for scan_idx in range(scans):
                base = scan_idx * num_channels
                ts_ns = int(time.time() * 1e9)
                for ch_idx, name in enumerate(channel_names):
                    value = data[base + ch_idx]

                    tags = {
                        "device": "T7",
                        "channel": name,
                        "sensor": sensor_by_name.get(name),
                        "differential": str(bool(diff_by_name.get(name, False))).lower()
                    }

                    fields = {
                        "voltage": value
                    }

                    line = format_influx_line("labjack", tags, fields, ts_ns)
                    if line is not None:
                        print(line)
            if scans > 0:
                print(f"# scans: {scans}, deviceBacklog: {device_backlog}, LJMBacklog: {ljm_backlog}")

    except KeyboardInterrupt:
        print("\nStopping stream (Ctrl+C detected)...")

    finally:
        ljm.eStreamStop(handle)
        ljm.close(handle)
        print("Stream stopped and device closed.")


def main():
    ain_channels = load_channels("labjack_channels.json")

    handle = open_t7("USB")  # You can change to "ANY", "ETHERNET", etc.

    scan_list, num_channels, channel_names = build_scan_list(ain_channels)

    run_stream(handle, scan_list, num_channels, channel_names, ain_channels)


if __name__ == "__main__":
    main()

#labjack gives a format when reading data and we have to match it to the Influx db line protocol format