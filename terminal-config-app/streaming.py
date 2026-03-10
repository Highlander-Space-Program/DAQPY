import json
import time
import csv
from datetime import datetime
from labjack import ljm
from threading import Lock, Thread

live_data = {}
live_data_lock = Lock()

from sensors import load_sensors_from_json, Sensor

# counter = 0

# def count():
#     before = counter
#     while True:
#         delta = counter - before
#         print(f"{delta=} hz")
#         before = counter
#         time.sleep(1)

# my_thread = Thread(target=count)
# my_thread.start()

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
    scan_rate_hz = 100
    scans_per_read = 100
    return scan_rate_hz, scans_per_read


def run_stream(handle, scan_list, sensors: list[Sensor], channel_names: list[str]):
    # global counter
    scan_rate_hz, scans_per_read = configure_stream_params()
    num_channels = len(channel_names)

    sensor_type_by_name = {s.ain: s.sensor_type for s in sensors}

    print("\nStarting stream:")
    print(f"  Scan rate:      {scan_rate_hz} Hz")
    print(f"  Channels:       {channel_names}")
    print(f"  Scans per read: {scans_per_read}")

    # actual_scan_rate = ljm.eStreamStart(
    #     handle,
    #     scans_per_read,
    #     num_channels,
    #     scan_list,
    #     scan_rate_hz,
    # )

    
    actual_scan_rate = ljm.eStreamStart(
        handle,
        1,
        num_channels,
        scan_list,
        50,
    )

    print(f"Actual stream scan rate: {actual_scan_rate} Hz")
    print("\nStreaming... press Ctrl+C to stop.\n")

    print("\n")
    print("Enter CSV File: ")
    fileToOpen = input()
    csvfile = open(f"{fileToOpen}.csv", "w", newline="")
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
            # counter += 1
            scans = len(data) // num_channels

            for scan_idx in range(scans):
                base = scan_idx * num_channels
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                for ch_idx, ain_name in enumerate(channel_names):
                    value = data[base + ch_idx]

                    row = {
                        "device": "T7",
                        "ain": ain_name,
                        "sensor": sensor_type_by_name.get(ain_name),
                        "voltage": value,
                        "measurement": "sensor_data",
                        "timestamp": timestamp
                    }

                    # Write to CSV (already doing this)
                    writer.writerow(row)

                    # Update live data for dashboard
                    with live_data_lock:
                        live_data[ain_name] = row


            if scans > 0:
                # print(
                #     f"# scans: {scans}, deviceBacklog: {device_backlog}, "
                #     f"LJMBacklog: {ljm_backlog}"
                # )
                pass

    except KeyboardInterrupt:
        print("\nStopping stream (Ctrl+C detected)...")

    finally:
        csvfile.close()
        ljm.eStreamStop(handle)
        ljm.close(handle)
        print("Stream stopped and device closed.")

def thermocouple_voltage_to_temperature(thermo_voltage, cj_temp_c):
    """
    Convert thermocouple voltage (in volts) to temperature in °F.
    
    This uses a simple linear approximation:
      - K-type thermocouple sensitivity is approximately 41 µV/°C.
      - dT (°C) = thermo_voltage (V) / 0.000041
      - Thermocouple temperature (°C) = Cold Junction Temperature (°C) + dT
      - Then convert °C to °F.
    
    Note: This linear approximation is valid only over a narrow temperature range.
    """
    # Calculate the temperature difference from the thermocouple voltage
    dT_c = thermo_voltage / 0.000041  # in °C
    tc_temp_c = cj_temp_c + dT_c        # thermocouple temperature in °C
    tc_temp_f = (tc_temp_c * 9/5) + 32    # convert °C to °F
    return tc_temp_f
    
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
