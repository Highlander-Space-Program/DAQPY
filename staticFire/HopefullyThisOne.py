import PySimpleGUI as sg
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

import time as timer
import random
import string
import cmd

import csv
import time	
from datetime import datetime
from labjack import ljm
import numpy as np


# 1. Load your historical dataset.
# Assume your CSV has columns: time, supply_pressure, supply_temperature, run_pressure, run_temperature, current_mass, and full_fill_time.
# full_fill_time is the time (in seconds) from the measurement to when the run tank reaches the target mass.
data = pd.read_csv('trainingData.csv')

# 2. Define features and target.
# Here, our features are the current sensor readings.
features = data[['supply_pressure', 'supply_temperature', 'run_pressure', 'run_temperature', 'current_mass']]
target = data['full_fill_time']

columns = ['supply_pressure', 'supply_temperature', 'run_pressure', 'run_temperature', 'current_mass']

# 3. Split data into training and testing sets.
X_train, X_test, y_train, y_test = train_test_split(features, target, test_size=0.2, random_state=42)

# 4. Create and train the regression model.
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

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
# N03 is 1000 psi PT
#AIN_CHANNELS = ["AIN0", "AIN1", "AIN2", "AIN3", "AIN120", "AIN122"]  # Single-ended inputs
AIN_CHANNELS = ["AIN63", "AIN64", "AIN65", "AIN66", "AIN67", "AIN68"]  # Single-ended inputs
DIFF_PAIRS = [("AIN48", "AIN56"), ("AIN49", "AIN57"), ("AIN51", "AIN58"), ("AIN52", "AIN59")]  # Load Cell Pairs
TC_PAIRS = [("AIN52", "AIN60"), ("AIN53", "AIN61"), ("AIN54", "AIN")]  # Thermocouple Pairs
BUFFER_LIMIT = 5000

def apply_scaling(value, channel):
	"""Applies the appropriate scaling equation based on the channel."""
	if channel == "AIN67":
		return (value - 0.5)/4 * (1000)
	else:
		return (397.14*(value)-189.29)

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

def Place_Button(key, xPos, yPos):
	global window
	click = window[key].widget
	master = click.master
	master.place(x=xPos, y=yPos, bordermode=sg.tk.INSIDE)

def updatePID(key, val, unit):
	global window
	try:
		window[key].update(str(round(float(val),2)) + unit)
	except:
		window[key].update((val))
	
BACKGROUNDCOLOR = "#121212"
GRAPHBACKGROUNDCOLOR = "#222222"
TEXTCOLOR = "#FFFFFF"
FONTANDSIZE = "Courier 15"

PT_ETH_01COLOR = "#FF5733"
PT_ETH_02COLOR = "#33C3FF"
PT_NO_01COLOR = "#FFC300"
PT_NO_02COLOR = "#8D33FF"
PT_NO_03COLOR = "#3333FF"
PT_CH_01COLOR = "#FF33A1"
TOT_WEIGHTCOLOR = "#17A2B8"
TC_01COLOR = "#C70039"
TC_02COLOR = "#00994D"
TC_03COLOR = "#EE00FF"

file_name_layout = [
	[sg.Text("Enter File Name:", background_color= GRAPHBACKGROUNDCOLOR)],
	[sg.Input(key="FILE_NAME")],
	[sg.Button("Submit", button_color= GRAPHBACKGROUNDCOLOR)]
]

file_name_window = sg.Window('HSP UI', file_name_layout, grab_anywhere=True, finalize=True, background_color=BACKGROUNDCOLOR, size = (1280,720), resizable=True, scaling=1)  

while True:
	event, values = file_name_window.read()
	if event == sg.WIN_CLOSED or event == "Submit":
		break

file_name_window.close()

CSV_FILE = values["FILE_NAME"] + ".csv"

column_layout1 = [[ sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-ETH-01', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-ETH-02', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-NO-01', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-NO-02', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), enable_events = True, key='PT-NO-03', background_color=GRAPHBACKGROUNDCOLOR)],
			[sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-2), graph_top_right=(500,1600), enable_events = True, key='PT-CH-01', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-100), graph_top_right=(500,100), enable_events = True,  key='TOT-WEIGHT', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), enable_events = True, key='TC-01', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), enable_events = True, key='TC-02', background_color=GRAPHBACKGROUNDCOLOR),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), enable_events = True, key='TC-03', background_color=GRAPHBACKGROUNDCOLOR),]]

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

TEXT = "Courier 20"

image_layout = [
	[sg.Image(filename="C:\\Users\\chris\\Downloads\\output-onlinepngtools.png", background_color=BACKGROUNDCOLOR, key='IMAGE', size = (1001,957))],
	[sg.Text(k='PID_PTN01', colors=(PT_NO_01COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification='right', size=(11,1))],
	[sg.Text(k='PID_PTN02', colors=(PT_NO_02COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))],
	[sg.Text(k='PID_PTN03', colors=(PT_NO_03COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))],
	[sg.Text(k='PID_PTE01', colors=(PT_ETH_01COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))],
	[sg.Text(k='PID_PTE02', colors=(PT_ETH_02COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))],
	[sg.Text(k='PID_PTCH01', colors=(PT_CH_01COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))],
	[sg.Text(k='PID_TC01', colors=(TC_01COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))],
	[sg.Text(k='PID_TC02', colors=(TC_02COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))],
	[sg.Text(k='PID_TC03', colors=(TC_03COLOR, BACKGROUNDCOLOR), p = 0, font = TEXT, justification="right", size=(11,1))]
]
etaLayout = [
			[sg.Text("TIME LEFT (s): ")],
			[sg.Text(":(", k = "Method1", s = (6,1))],
			[sg.Text(":(", k = "Method2", s = (6,1))],
			[sg.Text(":(", k = "Method3", s = (6,1))],
			[sg.Text(":(", k = "Method4", s = (6,1))],
			
]

tabGraph = [[sg.Column(column_layout1, element_justification='left', background_color=BACKGROUNDCOLOR, visible = True, vertical_alignment='l', k = 'col2', expand_x=True , expand_y=True, size = (500,2000), scrollable=True, sbar_arrow_color=GRAPHBACKGROUNDCOLOR, sbar_background_color=GRAPHBACKGROUNDCOLOR, sbar_frame_color=GRAPHBACKGROUNDCOLOR, sbar_trough_color=GRAPHBACKGROUNDCOLOR)]]

tabPID = [[sg.Column(image_layout, background_color=BACKGROUNDCOLOR, size=(1100,1000))]]

tabLayout = [[sg.TabGroup(selected_background_color=GRAPHBACKGROUNDCOLOR, selected_title_color = "#FFFFFF", layout = [[sg.Tab('Tab 1', tabGraph, tooltip='tip', background_color=GRAPHBACKGROUNDCOLOR), sg.Tab('Tab 2', tabPID, background_color=GRAPHBACKGROUNDCOLOR)]], tooltip='TIP2', background_color=GRAPHBACKGROUNDCOLOR, title_color=GRAPHBACKGROUNDCOLOR)]] 

layout = [
	[[sg.Column(button1), sg.Column(button2)]],
	[sg.Table(values=[[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],], headings=["Sensor", "Value"],
					cols_justification = ['l','r'],
					hide_vertical_scroll = True,
					row_height = 85,
					row_colors = COLORS,
					font = "Courier 50",
					header_background_color = BACKGROUNDCOLOR,
					header_text_color = TEXTCOLOR,
					background_color=BACKGROUNDCOLOR,
					key='TABLE',
					size = (800,1000),
					expand_x = True,
					expand_y = True,
					enable_events=True), 
					sg.Column(etaLayout),
					sg.Column(tabLayout)]]

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
sensorList[6].Lines(-500, 1330, -100, 100, 10, 0)
sensorList[7].Lines(-500, 95, -20, 100, 10, 0)
sensorList[8].Lines(-500, 95, -20, 100, 10, 0)
sensorList[9].Lines(-500, 95, -20, 100, 10, 0)

startingSize = (1920,1080)

offsetX = 15
offsetY = 14

FILE_PATH = 'trimmedblowup.csv'

mass = []
massTime1 = []
timestart = True
lastDataPoint = 0
firstTare = True
massTime1 = []
smallX = 0
coefficientstwo = np.array([1.72501276, -24.80675432, 95.42369204])
methodtwo = list(range(0, 200, 1))
methodtwoList = (np.polyval(coefficientstwo, np.array(list(range(0, 200, 1))))).tolist()

def main():
	global x
	line = ""
	handle = ljm.openS("ANY", "ANY", "ANY")  # Open LabJack device
	print("Opened device:", ljm.getHandleInfo(handle))

	configure_differential_channels(handle, DIFF_PAIRS)
	configure_differential_channels(handle, TC_PAIRS)

	write_to_csv = False

	with open(CSV_FILE, mode="w", newline="") as file:
		writer = csv.writer(file)
		header = ["Timestamp"] + AIN_CHANNELS + ["Total_Scaled_Weight (lbs)"] + [f"TC_{i+1} (F)" for i in range(len(TC_PAIRS))]
		writer.writerow(header)

		try:
			buffer = []
			while True:
				timestamp = datetime.now().strftime("%H:%M:%S:%f")[:-3]

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


				lineValues = line.split(',')
				runTime = lineValues[0].split(':')

				for i in range(len(sensorList)):
					sensorList[i].Assign(lineValues[i+1])

				man = list(item.getData() for item in sensorList)
				
				window['TABLE'].update(values = man, row_colors = COLORS)

				for item in sensorList:
					item.Graph()

				x+=1

				if float(lineValues[4]) > 400.00:
					if firstTare:
						loadTare = abs(float(lineValues[7]))
						firstTare = False	
					

					live_data = {
						'supply_pressure': [lineValues[3]],
						'supply_temperature': [lineValues[8]],
						'run_pressure': [lineValues[4]],
						'run_temperature': [lineValues[9]],
						'current_mass': [abs(float(lineValues[7])) - loadTare]
					}

					live_features = pd.DataFrame(live_data, columns=columns)
					predicted_remaining_time = model.predict(live_features)
					print("Predicted remaining time (seconds):", predicted_remaining_time[0])
					window['Method2'].update(round(predicted_remaining_time[0], 2))

					if (abs(float(lineValues[7])) - loadTare) >= 5:
					
						if timestart:
							hourTare = int(runTime[0])
							minTare = int(runTime[1])
							secTare = int(runTime[2])
							nanSecTare = int(runTime[3])
							timestart = False
						
						timeNow = (hourTare - int(runTime[0])) * 3600 + (minTare - int(runTime[1])) * 60 + (secTare - int(runTime[2])) + (nanSecTare - int(runTime[3])) * 0.001

						mass.append(abs(float(lineValues[7])) - loadTare)
						methodtwo.append(mass[-1])
						massTime1.append(abs(timeNow))
						methodtwoList.append(massTime1[-1])
						
						massSamples = np.array(mass, dtype='float32')
						massTime = np.array(massTime1, dtype='float32')
						methodtwoArray = np.array(methodtwo, dtype='float32')
						methodtwoListArray = np.array(methodtwoList, dtype='float32')
						
						# Remove NaN and infinite values
						valid_indices = ~(np.isnan(methodtwoArray) | np.isnan(methodtwoListArray) | np.isinf(methodtwoArray) | np.isinf(methodtwoListArray))
						methodtwoArray = methodtwoArray[valid_indices]
						methodtwoListArray = methodtwoListArray[valid_indices]

						# Remove NaN and infinite values
						valid_indices = ~(np.isnan(massSamples) | np.isnan(massTime) | np.isinf(massSamples) | np.isinf(massTime))
						massSamples = massSamples[valid_indices]
						massTime = massTime[valid_indices]

						if len(massSamples) >= 3 and len(np.unique(massTime)) > 1:
							coefficients = np.polyfit(massSamples, massTime, 2)
							newCoefficients = np.polyfit(methodtwoArray, methodtwoListArray, 2)
							window['Method1'].update(str(round(np.polyval(coefficients, 17) - massTime1[-1])))
							window['Method3'].update(str(round(np.polyval(newCoefficients, 17) - massTime[-1])))
							window['Method4'].update(str(round(np.polyval(coefficientstwo, 17) - massTime[-1])))
						
				Place_Button('PID_PTN01', 715 + offsetX, 596 + offsetY) # (7,7)
				Place_Button('PID_PTN02', 411 + offsetX, 387 + offsetY) # (7,7)
				Place_Button('PID_PTN03', 411 + offsetX, 693 + offsetY) # (7,7)
				Place_Button('PID_PTE01', 411 + offsetX, 28 + offsetY) # (7,7) (411,29) (24 14)
				Place_Button('PID_PTE02', 1 + offsetX, 693 + offsetY ) # (7,7)
				Place_Button('PID_PTCH01', 411 + offsetX, 790 + offsetY) # (7,7)
				Place_Button('PID_TC01', 715 + offsetX, 790 + offsetY) # (7,7)
				Place_Button('PID_TC02', 411 + offsetX, 294 + offsetY) # (7,7)
				Place_Button('PID_TC03', 715 + offsetX, 107 + offsetY) # (7,7)

				updatePID('PID_PTE01', lineValues[1], ' psi')
				updatePID('PID_PTE02', lineValues[2], ' psi')
				updatePID('PID_PTN01', lineValues[3], ' psi')
				updatePID('PID_PTN02', lineValues[4], ' psi')
				updatePID('PID_PTN03', lineValues[5], ' psi')
				updatePID('PID_PTCH01', lineValues[6], ' psi')
				updatePID('PID_TC01', lineValues[8], ' F')
				updatePID('PID_TC02', lineValues[9], ' F')
				updatePID('PID_TC03', lineValues[10], ' F')

				if (x==500):

					x = -250
										
					sensorList[0].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[1].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[2].Lines(-250, 1520, 0, 1600,  250,-750)
					sensorList[3].Lines(-250, 1520, 0, 1600,  250,-750)
					sensorList[4].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[5].Lines(-250, 1520, 0, 1600, 250, -750)
					sensorList[6].Lines(-250, 1330, -100, 100, 10, -750)
					sensorList[7].Lines(-250, 95, -20, 100, 10, -750)
					sensorList[8].Lines(-250, 95, -20, 100, 10, -750)
					sensorList[9].Lines(-250, 95, -20, 100, 10, -750)
				
				event, values = window.read(timeout = 0)
				Events(event, values, sensorList)
				
				if event == 'TOT-WEIGHT':
					tare = float(lineValues[7])

				if event == 'START_WRITING':
					write_to_csv = True

				if event == 'STOP_WRITING':
					write_to_csv = False

				if event == sg.WIN_CLOSED:
					break

			event, values = window.read(timeout = 1) 
					
			if event == 'TOT-WEIGHT':
				tare = float(lineValues[7])

			if event == 'START_WRITING':
				write_to_csv = True

			if event == 'STOP_WRITING':
				write_to_csv = False

			Events(event, values)
			
		except KeyboardInterrupt:
			print("\nStream interrupted by user.")
		finally:
			if buffer:
				writer.writerows(buffer)
				print(f"Written remaining {len(buffer)} rows to {CSV_FILE}")

			ljm.close(handle)
			print("Stream stopped and device closed.")

if __name__ == "__main__":
    main()