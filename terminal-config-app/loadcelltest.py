import matplotlib.pyplot as plt
from labjack import ljm
#Name: Luis Bojorquez
#Date: 01/28/2025
# Open the LabJack device
handle = ljm.openS("T7", "USB", "ANY")

# Set up the analog input channel
voltage = ljm.eReadName(handle, "AIN0")

ljm.eWriteName(handle, "AIN0_NEGATIVE_CH", 1)
ljm.eWriteName(handle, "AIN0_EF_INDEX", 22)
ljm.eWriteName(handle, "AIN0_EF_CONFIG_A", 3)
ljm.eWriteName(handle, "AIN0_RANGE", 0.1)
ljm.eWriteName(handle, "AIN0_RESOLUTION_INDEX", 8)
# Initialize data storage for plotting
y = []  # List to hold temperature readings
x = []  # List to hold time (or count) values
count = 0  # Counter for the x-axis

#Create a plot
plt.ion()  # Turn on interactive mode
fig, ax = plt.subplots()
line, = ax.plot(x, y, 'r-')  # Line object for updating
ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage (V) Scaled by 10^5")
ax.set_ylim(-10, 5)  # Adjust according to expected temperature range
plt.title("Load Cell S Type Calibration")

# Continuously read voltage and update the plot
try:
    while True:
        # Read Voltage from the LabJack
        voltage = ljm.eReadName(handle, "AIN0")
        print("Voltage (V) Scaled by 10^5:", voltage*pow(10,5))

        # Append the new temperature and time value
        y.append(voltage*pow(10,5))
        count += 1
        weight = -0.5104 * (voltage*pow(10,5)) + 1.9834 - 0.009
        print("Approximate Weight (kg):", weight)
        x.append(count)

        # Update the plot
        line.set_xdata(x)
        line.set_ydata(y)
        ax.relim()  # Recalculate limits
        ax.autoscale_view()  # Autoscale view
        plt.pause(1)  # Pause for 1 second before next read

except KeyboardInterrupt:
    print("Stopped by user")

finally:
    # Close the LabJack handle and show the final plot
    ljm.close(handle)
    plt.ioff()  # Turn off interactive mode
    plt.show()  # Show the final plot
