import csv
import time
from datetime import datetime, timedelta
from labjack import ljm

# Configuration
SCAN_LIST = ["AIN0", "AIN1"]  # Channels to read
SCAN_RATE = 1000              # Scans per second
BUFFER_LIMIT = 5000           # Number of samples to buffer before writing to CSV
CSV_FILE = "streamed_data.csv"  # Output CSV file path
def apply_scaling(value):
    """
    Applies the scaling equation to a raw data value.
    Scaled Value = (value - 0.5) * (1000 / 4) + 14
    """
    return (value - 0.5) * (1000 / 4) + 14
def configure_stream(handle, scan_list, scan_rate):
    """
    Configures the stream with the given scan list and scan rate.
    """
    # Set resolution and range for each channel
    for channel in scan_list:
        ljm.eWriteName(handle, f"{channel}_RESOLUTION_INDEX", 0)  # Default resolution
        ljm.eWriteName(handle, f"{channel}_RANGE", 10.0)  # ±10V range

    # Add channels to the scan list by address
    addresses = [ljm.nameToAddress(name)[0] for name in scan_list]

    # Set the scan rate
    ljm.eWriteName(handle, "STREAM_SCANRATE_HZ", scan_rate)

    return addresses

def main():
    handle = ljm.openS("ANY", "ANY", "ANY")  # Open the first available LabJack
    print("Opened device:", ljm.getHandleInfo(handle))

    # Configure stream
    scan_addresses = configure_stream(handle, SCAN_LIST, SCAN_RATE)
    num_channels = len(scan_addresses)

    print(f"Stream configured for {num_channels} channels at {SCAN_RATE} scans/second.")

    # Start the stream (read 500 scans per read)
    scans_per_read = 500  # Adjust based on buffer size and requirements
    scan_rate_actual = ljm.eStreamStart(handle, scans_per_read, num_channels, scan_addresses, SCAN_RATE)
    print(f"Stream started with actual scan rate: {scan_rate_actual:.2f} Hz")

    # CSV Setup
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        # Write header
        header = ["Timestamp"] + SCAN_LIST
        writer.writerow(header)

        try:
            buffer = []
            while True:
                # Read stream data
                ret_data = ljm.eStreamRead(handle)
                data = ret_data[0]  # Flattened data array

                # Starting timestamp of the batch
                batch_start_time = datetime.now()

                # Calculate time interval between samples
                sample_interval = 1.0 / scan_rate_actual  # Time per sample

                # Process data in chunks (data is interleaved by channel)
                for i in range(0, len(data), num_channels):
                    # Calculate the timestamp for each sample
                    sample_time = batch_start_time + timedelta(seconds=i // num_channels * sample_interval)
                    timestamp = sample_time.strftime("%H:%M:%S:%f")[:-3]  # Format timestamp
                    scaled_data = [apply_scaling(data[i + j]) for j in range(num_channels)]
                    print(f"{timestamp} | Scaled Voltages: {', '.join(f'{val:.2f}' for val in scaled_data)}")


                    # Create a row with the timestamp and scaled data
                    row = [timestamp] + scaled_data
                    buffer.append(row)
                    # Write to CSV if buffer limit is reached
                    if len(buffer) >= BUFFER_LIMIT:
                        writer.writerows(buffer)
                        buffer.clear()  # Clear buffer
                        print(f"Written {BUFFER_LIMIT} rows to {CSV_FILE}")

        except KeyboardInterrupt:
            print("\nStream interrupted by user.")
        finally:
            # Stop the stream and close the handle
            ljm.eStreamStop(handle)
            ljm.close(handle)
            print("Stream stopped and device closed.")

if __name__ == "__main__":
    main()

