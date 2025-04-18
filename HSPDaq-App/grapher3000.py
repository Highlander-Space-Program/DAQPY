import dearpygui.dearpygui as dpg
import pandas as pd
import os 

file_name = input("Enter the file name: ")
file_path = "data/"+file_name 
df = pd.read_csv(file_path)

# Time axis 
if "Timestamp" in df.columns:
    #
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%H:%M:%S:%f')
    # 
    df['TimeSeconds'] = (df['Timestamp'] - df['Timestamp'].iloc[0]).dt.total_seconds()
else:
    # 
    df['TimeSeconds'] = df.index.tolist()

# Column label mapping
column_labels = {
    "AIN65": "PT-ETH-02",
    "AIN2": "PT-CH-01",
    "AIN63": "PT-NO-02",
    "AIN67": "PT-NO-01",
    "AIN68": "PT-ETH-01"
}

columns_to_plot = [col for col in df.columns if col not in ['Timestamp', 'TimeSeconds']]

dpg.create_context()
dpg.create_viewport(title='All Channels vs Time', width=820, height=800)
dpg.setup_dearpygui()

with dpg.window(label="All Data Plots", width=1920, height=1080):
    for col in columns_to_plot:
        label = column_labels.get(col, col)  
        with dpg.plot(label=f"{label} vs Time", height=250, width=-1):
            # X-axis for TimeSeconds
            dpg.add_plot_axis(dpg.mvXAxis, label="Time (seconds)")
            # Y-axis for the current column
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label=label)
            dpg.add_line_series(
                df["TimeSeconds"].tolist(),
                df[col].tolist(),
                label=label,
                parent=y_axis
            )

dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
