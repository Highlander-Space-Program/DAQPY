import PySimpleGUI as sg
import time as timer
import random
import string
import cmd

import csv
import time
from datetime import datetime
#from labjack import ljm
import numpy as np

# --- NIST Type J Table ---
temp_table = np.array([
    -200, -190, -180, -170, -160, -150, -140, -130, -120, -110,
    -100,  -90,  -80,  -70,  -60,  -50,  -40,  -30,  -20,  -10,
       0,   10,   20,   30,   40,   50,   60,   70,   80,   90,
     100,  110,  120,  130,  140,  150,  160,  170,  180,  190,
     200
])

mv_table = np.array([
    -8.095, -7.890, -7.659, -7.403, -7.123, -6.821, -6.500, -6.159, -5.801, -5.426,
    -5.037, -4.633, -4.215, -3.786, -3.344, -2.893, -2.431, -1.961, -1.482, -0.995,
    -0.501,  0.000,  0.507,  1.019,  1.537,  2.059,  2.585,  3.116,  3.650,  4.187,
     4.726,  5.269,  5.814,  6.360,  6.909,  7.459,  8.010,  8.562,  9.115,  9.669,
    10.224
])

def type_j_temp_from_mv(voltage_mv):
    """Convert a measured thermocouple voltage (mV) to temperature (°C)."""
    return np.interp(voltage_mv, mv_table, temp_table)
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
# --- Configuration ---
# ETH1 ETH2 NO1 NO2 NO3 CHO1
#AIN_CHANNELS = ["AIN0", "AIN1", "AIN2", "AIN3", "AIN120", "AIN122"]  # Single-ended inputs
AIN_CHANNELS = ["AIN122", "AIN1", "AIN120", "AIN3", "AIN0", "AIN2"]  # Single-ended inputs
DIFF_PAIRS = [("AIN48", "AIN56"), ("AIN49", "AIN57"), ("AIN50", "AIN58"), ("AIN51", "AIN59")]  # Load Cell Pairs
TC_PAIRS = [("AIN80", "AIN88"), ("AIN81", "AIN89"), ("AIN82", "AIN90")]  # Thermocouple Pairs
BUFFER_LIMIT = 5000

def apply_scaling(value, channel):
    """Applies the appropriate scaling equation based on the channel."""
    if channel == "AIN0":
        return (421.98) * (value - 0.04) - 166.26 + 4
    elif channel == "AIN1":
        return (421.98) * (value - 0.04) - 166.26 + 10
    elif channel in ["AIN2", "AIN3", "AIN120"]:
        return (421.98) * (value - 0.04) - 166.26 + 10
    elif channel == "AIN122":
        return (306.25) * (value - 0.04) - 132.81
    else:
        return 0

def apply_differential_scaling(voltage):
    """Applies scaling to differential load cell readings."""
    return (-(voltage * 51412) + 2.0204) / 0.45359237  # Converts voltage to weight (lbs)

def configure_differential_channels(handle, diff_pairs):
    """Configures differential channels."""
    for pos, neg in diff_pairs:
        ljm.eWriteName(handle, f"{pos}_RANGE", 0.01)  # Set range to ±0.01V
        ljm.eWriteName(handle, f"{pos}_NEGATIVE_CH", int(neg[3:]))  # Assign negative channel

def Events(events, values, sensorList):
	global window

	if values['TABLE'] == [0]:
		sensorList[0].visible = not sensorList[0].visible
		window['PT-ETH-01'].update(visible=sensorList[0].visible)

	elif values['TABLE'] == [1]:
		sensorList[1].visible = not sensorList[1].visible
		window['PT-ETH-02'].update(visible=sensorList[1].visible)

	elif values['TABLE'] == [2]:
		sensorList[2].visible = not sensorList[2].visible
		window['PT-NO-01'].update(visible=sensorList[2].visible)

	elif values['TABLE'] == [3]:
		sensorList[3].visible = not sensorList[3].visible
		window['PT-NO-02'].update(visible=sensorList[3].visible)

	elif values['TABLE'] == [4]:
		sensorList[4].visible = not sensorList[4].visible
		window['PT-NO-03'].update(visible=sensorList[4].visible)

	elif values['TABLE'] == [5]:
		sensorList[5].visible = not sensorList[5].visible
		window['PT-CH-01'].update(visible=sensorList[5].visible)

	elif values['TABLE'] == [6]:
		sensorList[6].visible = not sensorList[6].visible
		window['TOT-WEIGHT'].update(visible=sensorList[6].visible)

	elif values['TABLE'] == [7]:
		sensorList[7].visible = not sensorList[7].visible
		window['TC-01'].update(visible=sensorList[7].visible)

	elif values['TABLE'] == [8]:
		sensorList[8].visible = not sensorList[8].visible
		window['TC-02'].update(visible=sensorList[8].visible)

	elif values['TABLE'] == [9]:
		sensorList[9].visible = not sensorList[9].visible
		window['TC-03'].update(visible=sensorList[9].visible)

	window['col2'].contents_changed()

def Tare(event, sensorList, data):

	if event == 'PT-ETH-01':
		sensorList[0].Tare(data[0])

	elif event == 'PT-ETH-02':
		sensorList[1].Tare(data[1])

	elif event == 'PT-NO-01':
		sensorList[2].Tare(data[2])

	elif event == 'PT-NO-02':
		sensorList[3].Tare(data[3])

	elif event == 'PT-NO-03':
		sensorList[4].Tare(data[4])

	elif event == 'PT-CH-01':
		sensorList[5].Tare(data[5])

	elif event == 'TOT-WEIGHT':
		sensorList[6].Tare(data[6])

class Sensor:
	global x

	def __init__(self, window, name, Unit, color):
		self.graph = window
		self.visible = False
		self.tempData = 0
		self.data = 0
		self.tare = 0
		self.title = name
		self.unit = Unit
		self.color = color
	
	def Assign(self, value):
		self.tempData = self.data
		try:
			self.data = float(value) - self.tare
		except:
			self.data = 0

	def Tare(self, tare):
		self.tare = tare
	
	def Lines(self, start, height, startRange, endRange, stepSize, dist):
		self.graph.move(dist,0)
		self.graph.DrawLine((-500,-500), (-500,1000))
		self.graph.DrawLine((start,0), (500,0))

		tempTitle = self.title + " (" + self.unit + ")" 
		
		self.graph.DrawText(tempTitle, (0,height), color = 'gray', font = FONTANDSIZE)

		for y in range(startRange, endRange, stepSize):    

			if y != 0:
				self.graph.DrawLine((-500,y), (-450,y))    
				self.graph.DrawText(y, (-400,y), color='gray', font=FONTANDSIZE)  

	def Graph(self):
		if (abs(self.data-self.tempData)<1):
			self.graph.DrawCircle((x,self.data), 1, line_color = self.color)
		else:
			self.graph.DrawLine((x,self.tempData), (x,self.data), self.color, 2)

	def getData(self):
		return [self.title, str(round(self.data,2)) + " " + self.unit]
			
BACKGROUNDCOLOR = "#121212"
GRAPHBACKGROUNDCOLOR = "#222222"
TEXTCOLOR = "#bcbcbc"
FONTANDSIZE = "Courier 15"

PT_ETH_01COLOR = "#FFFFFF" 
PT_ETH_02COLOR = "#FFD700"
PT_NO_01COLOR = "#FF4500" 
PT_NO_02COLOR = "#00FF00"  
PT_NO_03COLOR = "#00BFFF" 
PT_CH_01COLOR = "#FF1493"  
TOT_WEIGHTCOLOR = "#FFFF00" 
TC_01COLOR = "#FF69B4" 
TC_02COLOR = "#87CEFA" 
TC_03COLOR = "#F5A623"

file_name_layout = [
	[sg.Text("Enter File Name:")],
	[sg.Input(key="FILE_NAME")],
	[sg.Button("Submit")]
]

file_name_window = sg.Window('HSP UI', file_name_layout, grab_anywhere=True, finalize=True, background_color=BACKGROUNDCOLOR, size = (1280,720), resizable=True, scaling=1)  

while True:
	event, values = file_name_window.read()
	if event == sg.WIN_CLOSED or event == "Submit":
		break

file_name_window.close()

CSV_FILE = values["FILE_NAME"] + ".csv"

column_layout1 = [[ sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-ETH-01', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-ETH-02', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-NO-01', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-NO-02', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-NO-03', visible = False, background_color=GRAPHBACKGROUNDCOLOR)],
			[sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-2), graph_top_right=(500,1600), enable_events = True, key='PT-CH-01', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-50), graph_top_right=(500,100), enable_events = True,  key='TOT-WEIGHT', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), enable_events = True, key='TC-01', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), enable_events = True, key='TC-02', visible = False, background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), enable_events = True, key='TC-03', visible = False, background_color=GRAPHBACKGROUNDCOLOR),]]

COLORS = [
	[0, PT_ETH_01COLOR, BACKGROUNDCOLOR],
	[1, PT_ETH_02COLOR, BACKGROUNDCOLOR],
	[2, PT_NO_01COLOR, BACKGROUNDCOLOR],
	[3, PT_NO_02COLOR, BACKGROUNDCOLOR],
	[4, PT_NO_03COLOR, BACKGROUNDCOLOR],
	[5, PT_CH_01COLOR, BACKGROUNDCOLOR],
	[6, TOT_WEIGHTCOLOR, BACKGROUNDCOLOR],
	[7, TC_01COLOR, BACKGROUNDCOLOR],
	[8, TC_02COLOR, BACKGROUNDCOLOR],
	[9, TC_03COLOR, BACKGROUNDCOLOR],
	]

button1 = [[sg.Button("Start Writing", key="START_WRITING", size=(20,2))]]
button2 = [[sg.Button("Stop Writing", key="STOP_WRITING", size=(20,2))]]

layout = [
	[[sg.Column(button1), sg.Column(button2)]],
	[sg.Table(values=[[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],], headings=["Sensor", "Value"],
					cols_justification = ['l','r'],
					hide_vertical_scroll = True,
					row_height = 90,
					row_colors = COLORS,
					font = "Comic 70",
					header_background_color = BACKGROUNDCOLOR,
					header_text_color = TEXTCOLOR,
					background_color=BACKGROUNDCOLOR,
					key='TABLE',
					enable_events=True,
					expand_x=True,
					expand_y=True,), sg.Column(column_layout1, element_justification='left', background_color=BACKGROUNDCOLOR,  vertical_alignment='l', k = 'col2', expand_x=True , expand_y=True, size = (500,2000), scrollable=True, sbar_arrow_color=GRAPHBACKGROUNDCOLOR, sbar_background_color=GRAPHBACKGROUNDCOLOR, sbar_frame_color=GRAPHBACKGROUNDCOLOR, sbar_trough_color=GRAPHBACKGROUNDCOLOR)]]

window = sg.Window('HSP UI', layout, grab_anywhere=True, finalize=True, background_color=BACKGROUNDCOLOR, size = (1920,1080), resizable=True, scaling=1)  

sensorList = [
		 Sensor(window['PT-ETH-01'], "PT-ETH-01", "psi", PT_ETH_01COLOR)
		,Sensor(window['PT-ETH-02'], "PT-ETH-02", "psi", PT_ETH_02COLOR)
		,Sensor(window['PT-NO-01'], "PT-NO-01", "psi", PT_NO_01COLOR)
		,Sensor(window['PT-NO-02'], "PT-NO-02", "psi", PT_NO_02COLOR)
		,Sensor(window['PT-NO-03'], "PT-NO-03", "psi", PT_NO_03COLOR)
		,Sensor(window['PT-CH-01'], "PT-CH-01", "psi", PT_CH_01COLOR)
		,Sensor(window['TOT-WEIGHT'], "TOT-Weight", "lb", TOT_WEIGHTCOLOR)
		,Sensor(window['TC-01'], "TC-01", "F", TC_01COLOR)
		,Sensor(window['TC-02'], "TC-02", "F", TC_02COLOR)
		,Sensor(window['TC-03'], "TC-03", "F", TC_03COLOR)
		]
# Draw Graph    
x = -500

sensorList[0].Lines(-500, 1520, 0, 1600, 250, 0)
sensorList[1].Lines(-500, 1520, 0, 1600, 250, 0)
sensorList[2].Lines(-500, 1520, 0, 1600,  250,0)
sensorList[3].Lines(-500, 1520, 0, 1600,  250,0)
sensorList[4].Lines(-500, 1520, 0, 1600, 250, 0)
sensorList[5].Lines(-500, 1520, 0, 1600, 250, 0)
sensorList[6].Lines(-500, 1330, -1400, 1400, 200, 0)
sensorList[7].Lines(-500, 95, -20, 100, 10, 0)
sensorList[8].Lines(-500, 95, -20, 100, 10, 0)
sensorList[9].Lines(-500, 95, -20, 100, 10, 0)

startingSize = (1920,1080)

def main():
	global x
	line = ""
	tare = 0
	#handle = ljm.openS("ANY", "ANY", "ANY")  # Open LabJack device
	#print("Opened device:", ljm.getHandleInfo(handle))

	#configure_differential_channels(handle, DIFF_PAIRS)
	#configure_differential_channels(handle, TC_PAIRS)

	write_to_csv = False

	with open(CSV_FILE, mode="w", newline="") as file:
		writer = csv.writer(file)
		header = ["Timestamp"] + AIN_CHANNELS + ["Total_Scaled_Weight (lbs)"] + [f"TC_{i+1} (°F)" for i in range(len(TC_PAIRS))]
		writer.writerow(header)

		try:
			buffer = []
			while True:
				timestamp = datetime.now().strftime("%H:%M:%S:%f")[:-3]
				'''
				# Read AIN Values
				ain_values = [ljm.eReadName(handle, ch) for ch in AIN_CHANNELS]
				scaled_ain_values = [apply_scaling(ain_values[i], AIN_CHANNELS[i]) for i in range(len(AIN_CHANNELS))]

				# Read Load Cell (Weight) Differential Values
				diff_voltages = [ljm.eReadName(handle, pair[0]) for pair in DIFF_PAIRS]
				scaled_diffs = [apply_differential_scaling(v) for v in diff_voltages]
				total_scaled_weight = sum(scaled_diffs)
	
				# Read Thermocouple Differential Voltages
				cj_temp_k = ljm.eReadName(handle, "TEMPERATURE_DEVICE_K")
				cj_temp_c = cj_temp_k -273.15
				tc_voltages = [ljm.eReadName(handle, pair[0]) for pair in TC_PAIRS]
				print(tc_voltages[0]*1)
				tc_temps = [ (thermocouple_voltage_to_temperature(v, cj_temp_c)) for v in tc_voltages]  # Convert V to mV and to °F

				# Print Data
				print(f"{timestamp}, {', '.join(f'{v:.2f}' for v in scaled_ain_values)} "
				f", {total_scaled_weight:.2f}, {', '.join(f'{t:.2f}°F' for t in tc_temps)}")
				
				line = f"{timestamp}, {', '.join(f'{v:.2f}' for v in scaled_ain_values)}" f", {total_scaled_weight:.2f}, {', '.join(f'{t:.2f}' for t in tc_temps)}"

				# Append Data to Buffer
				buffer.append([timestamp] + scaled_ain_values + [total_scaled_weight] + tc_temps)

				# Write Buffer to CSV if limit is reached
				if write_to_csv and len(buffer) >= BUFFER_LIMIT:
					writer.writerows(buffer)
					file.flush()  # Ensure immediate write
					buffer.clear()
					print(f"Written {BUFFER_LIMIT} rows to {CSV_FILE}")

				#   time.sleep(0.01)  # Adjust sampling rate
				'''
				
				line = '10,101,10,01,01,151,101,101,101,101,10,101,101,101,01,101,101,3'
				lineValues = line.split(',')
				for i in range(len(sensorList)):
					sensorList[i].Assign(lineValues[i])

				man = list(item.getData() for item in sensorList)
				
				window['TABLE'].update(values = man, row_colors = COLORS)

				for item in sensorList:
					item.Graph()

				x+=1

				if (x==500):

					x = -250
										
					sensorList[0].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[1].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[2].Lines(-250, 1520, 0, 1600,  250,-750)
					sensorList[3].Lines(-250, 1520, 0, 1600,  250,-750)
					sensorList[4].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[5].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[6].Lines(-250, 1330, -1400, 1400, 200, -750)
					sensorList[7].Lines(-250, 95, -20, 100, 10, -750)
					sensorList[8].Lines(-250, 95, -20, 100, 10, -750)
					sensorList[9].Lines(-250, 95, -20, 100, 10, -750)
					
				event, values = window.read(timeout = 0)
				
				if event == 'START_WRITING':
					write_to_csv = True

				if event == 'STOP_WRITING':
					write_to_csv = False

				Events(event, values, sensorList)

				Tare(event, sensorList, lineValues)

				if event == sg.WIN_CLOSED:
					break
			
		except KeyboardInterrupt:
			print("\nStream interrupted by user.")
		finally:
			if buffer:
				writer.writerows(buffer)
				print(f"Written remaining {len(buffer)} rows to {CSV_FILE}")

			#ljm.close(handle)
			print("Stream stopped and device closed.")

if __name__ == "__main__":
    main()