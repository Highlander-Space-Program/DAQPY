from labjack import ljm
import time

# Open connection to the LabJack T7
handle = ljm.openS("T7", "ANY", "ANY")

# Define differential channel pairs (Positive, Negative)
diff_pairs = [
    ("AIN48", "AIN56"),
    ("AIN49", "AIN57"),
    ("AIN50", "AIN58"),
    ("AIN51", "AIN59")
]

# Set configuration for each differential pair
for pos, neg in diff_pairs:
    ljm.eWriteName(handle, f"{pos}_RANGE", 0.01)  # Set range to ±0.01V
    ljm.eWriteName(handle, f"{pos}_NEGATIVE_CH", int(neg[3:]))  # Set negative channel

try:
    while True:  # Continuous reading loop
        # Read all differential voltages
        voltages = ljm.eReadNames(handle, len(diff_pairs), [pair[0] for pair in diff_pairs])

        # Apply scaling equation
        scaled_voltages = [(-(v * 51412) + 2.0204)/0.45359237  for v in voltages]

        # Compute total sum of scaled voltages
        total_scaled_voltage = sum(scaled_voltages)

        # Print results
        print("\nDifferential Voltage Readings (Scaled):")
        for (pos, neg), voltage, scaled in zip(diff_pairs, voltages, scaled_voltages):
            print(f"{pos} - {neg}: {voltage:.6f} V | Scaled: {scaled:.6f}")

        # Print the total sum of all scaled voltages
        print(f"\nTotal Scaled Voltage Sum: {total_scaled_voltage:.6f}\n")

        time.sleep(0.5)  # 500ms delay between readings

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    ljm.close(handle)  # Close connection
