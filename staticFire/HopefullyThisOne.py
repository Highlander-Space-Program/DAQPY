import PySimpleGUI as sg
import time as timer
import random
import string
import cmd

import csv
import time
from datetime import datetime
from labjack import ljm
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
CSV_FILE = "sensor_data.csv"

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



def Events(events, values):
	global window
	global pT_ETH_01Graph
	global pT_ETH_02Graph
	global pT_NO_01Graph
	global pT_NO_02Graph
	global pT_NO_03Graph
	global pT_CH_01Graph
	global tOT_WEIGHTGraph
	global tC_01Graph
	global tC_02Graph
	global tC_03Graph

	if values['TABLE'] == [0]:
		pT_ETH_01Graph = not pT_ETH_01Graph
		window['PT-ETH-01'].update(visible=pT_ETH_01Graph)

	elif values['TABLE'] == [1]:
		pT_ETH_02Graph = not pT_ETH_02Graph
		window['PT-ETH-02'].update(visible=pT_ETH_02Graph)

	elif values['TABLE'] == [2]:
		pT_NO_01Graph = not pT_NO_01Graph
		window['PT-NO-01'].update(visible=pT_NO_01Graph)

	elif values['TABLE'] == [3]:
		pT_NO_02Graph = not pT_NO_02Graph
		window['PT-NO-02'].update(visible=pT_NO_02Graph)

	elif values['TABLE'] == [4]:
		pT_NO_03Graph = not pT_NO_03Graph
		window['PT-NO-03'].update(visible=pT_NO_03Graph)

	elif values['TABLE'] == [5]:
		pT_CH_01Graph = not pT_CH_01Graph
		window['PT-CH-01'].update(visible=pT_CH_01Graph)

	elif values['TABLE'] == [6]:
		tOT_WEIGHTGraph = not tOT_WEIGHTGraph
		window['TOT-WEIGHT'].update(visible=tOT_WEIGHTGraph)

	elif values['TABLE'] == [7]:
		tC_01Graph = not tC_01Graph
		window['TC-01'].update(visible=tC_01Graph)

	elif values['TABLE'] == [8]:
		tC_02Graph = not tC_02Graph
		window['TC-02'].update(visible=tC_02Graph)

	elif values['TABLE'] == [9]:
		tC_03Graph = not tC_03Graph
		window['TC-03'].update(visible=tC_03Graph)

	window['col2'].contents_changed()

class Sensor:
	global x

	def __init__(self, window, name, Unit):
		self.graph = window
		self.visible = False
		self.tempData = 0
		self.data = 0
		self.title = name
		self.unit = Unit
	
	def Assign(self, value):
		self.tempData = self.data
		try:
			self.data = float(value)
		except:
			self.data = 0
						
		#self.value.update(self.title + ":\n" + str(self.data) + " " + self.unit)
	
	def Lines(self, start, height, startRange, endRange, stepSize, dist):
		self.graph.move(dist,0)
		self.graph.DrawLine((-500,-500), (-500,1000))
		self.graph.DrawLine((start,0), (500,0))

		tempTitle = self.title + " (" + self.unit + ")" 
		
		self.graph.DrawText(tempTitle, (0,height), color = 'gray', font = fontAndSize)

		stepSize

		for y in range(startRange, endRange, stepSize):    

			if y != 0:
				self.graph.DrawLine((-500,y), (-450,y))    
				self.graph.DrawText(y, (-400,y), color='gray', font=fontAndSize)  

	def Graph(self, color):
		if (abs(self.data-self.tempData)<1):
			self.graph.DrawCircle((x,self.data), 1, line_color = color)
		else:
			self.graph.DrawLine((x,self.tempData), (x,self.data), color, 2)

	def getData(self):
		return [self.title, str(round(self.data,2)) + " " + self.unit]
			
backgroundColor = "#121212"
buttonColor = "#8e3563"
disabledButton = "#000000"
buttonBackgroundColor = "#222222"
offColor = "#28bc64"
onColor = "#6f0000"
textColor = "#bcbcbc"
fontAndSize = "Comic 15"
font2 = "Comic 20"
padding = [10,10]
paddingSensor = [15,2]

pT_ETH_01Color = "#5C8374" 
pT_ETH_02Color = "#087CB4" 
pT_NO_01Color = "#F2613F" 
pT_NO_02Color = "#E95793" 
pT_NO_03Color = "#5C527F" 
pT_CH_01Color = "#A3C7B3" 
tOT_WEIGHTColor = "#FFD166" 
tC_01Color = "#6EC2EC" 
tC_02Color = "#8CA772" 
tC_03Color = "#C44D2F"

column_layout1 = [[ sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), key='PT-ETH-01', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), key='PT-ETH-02', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), key='PT-NO-01', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), key='PT-NO-02', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,1600), key='PT-NO-03', visible = False, background_color=buttonBackgroundColor)],
			[sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-2), graph_top_right=(500,1600), key='PT-CH-01', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-50), graph_top_right=(500,100), enable_events = True,  key='TOT-WEIGHT', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), key='TC-01', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), key='TC-02', visible = False, background_color=buttonBackgroundColor),
			sg.Graph(canvas_size=(500, 500),graph_bottom_left=(-500,-20), graph_top_right=(500,100), key='TC-03', visible = False, background_color=buttonBackgroundColor),]]

colors = [
	[0, pT_ETH_01Color, backgroundColor],
	[1, pT_ETH_02Color, backgroundColor],
	[2, pT_NO_01Color, backgroundColor],
	[3, pT_NO_02Color, backgroundColor],
	[4, pT_NO_03Color, backgroundColor],
	[5, pT_CH_01Color, backgroundColor],
	[6, tOT_WEIGHTColor, backgroundColor],
	[7, tC_01Color, backgroundColor],
	[8, tC_02Color, backgroundColor],
	[9, tC_03Color, backgroundColor],
]

layout = [[sg.Table(values=[[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],], headings=["Sensor", "Value"],
					cols_justification = ['l','r'],
					hide_vertical_scroll = True,
					row_height = 90,
					row_colors = colors,
					font = "Comic 70",
					header_background_color = backgroundColor,
					header_text_color = textColor,
					background_color=backgroundColor,
					key='TABLE',
					enable_events=True,
					expand_x=True,
					expand_y=True,), sg.Column(column_layout1, element_justification='left', background_color=backgroundColor,  vertical_alignment='l', k = 'col2', expand_x=True , expand_y=True, size = (500,2000), scrollable=True, sbar_arrow_color=buttonBackgroundColor, sbar_background_color=buttonBackgroundColor, sbar_frame_color=buttonBackgroundColor, sbar_trough_color=buttonBackgroundColor)]]

window = sg.Window('HSP UI', layout, grab_anywhere=True, finalize=True, background_color=backgroundColor, size = (1920,1080), resizable=True, scaling=1)  

pT_ETH_01 = Sensor(window['PT-ETH-01'], "PT-ETH-01", "psi")
pT_ETH_02 = Sensor(window['PT-ETH-02'], "PT-ETH-02", "psi")
pT_NO_01 = Sensor(window['PT-NO-01'], "PT-NO-01", "psi")
pT_NO_02 = Sensor(window['PT-NO-02'], "PT-NO-02", "psi")
pT_NO_03 = Sensor(window['PT-NO-03'], "PT-NO-03", "psi")
pT_CH_01 = Sensor(window['PT-CH-01'], "PT-CH-01", "psi")
tOT_WEIGHT = Sensor(window['TOT-WEIGHT'], "TOT-Weight", "lb")
tC_01 = Sensor(window['TC-01'], "TC-Ambient", "F")
tC_02 = Sensor(window['TC-02'], "TC-Supply", "F")
tC_03 = Sensor(window['TC-03'], "TC-NT", "F")

# Draw Graph    
x = -500
h = 0
pT_ETH_01Graph = False
pT_ETH_02Graph = False
pT_NO_01Graph = False
pT_NO_02Graph = False
pT_NO_03Graph = False
pT_CH_01Graph = False
tOT_WEIGHTGraph = False
tC_01Graph = False
tC_02Graph = False
tC_03Graph = False

pT_ETH_01.Lines(-500, 1520, 0, 1600, 250, 0)
pT_ETH_02.Lines(-500, 1520, 0, 1600, 250, 0)
pT_NO_01.Lines(-500, 1520, 0, 1600,  250,0)
pT_NO_02.Lines(-500, 1520, 0, 1600,  250,0)
pT_NO_03.Lines(-500, 1520, 0, 1600, 250, 0)
pT_CH_01.Lines(-500, 1520, 0, 1600, 250, 0)
tOT_WEIGHT.Lines(-500, 133, -140, 140, 20, 0)
tC_01.Lines(-500, 95, -20, 100, 10, 0)
tC_02.Lines(-500, 95, -20, 100, 10, 0)
tC_03.Lines(-500, 95, -20, 100, 10, 0)

startingSize = (1920,1080)


def main():
	global x
	line = ""
	tare = 0
	handle = ljm.openS("ANY", "ANY", "ANY")  # Open LabJack device
	print("Opened device:", ljm.getHandleInfo(handle))

	configure_differential_channels(handle, DIFF_PAIRS)
	configure_differential_channels(handle, TC_PAIRS)

	with open(CSV_FILE, mode="w", newline="") as file:
		writer = csv.writer(file)
		header = ["Timestamp"] + AIN_CHANNELS + ["Total_Scaled_Weight (lbs)"] + [f"TC_{i+1} (°F)" for i in range(len(TC_PAIRS))]
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
				if len(buffer) >= BUFFER_LIMIT:
					writer.writerows(buffer)
					file.flush()  # Ensure immediate write
					buffer.clear()
					print(f"Written {BUFFER_LIMIT} rows to {CSV_FILE}")

				#   time.sleep(0.01)  # Adjust sampling rate


				lineValues = line.split(',')
				time = lineValues[0].split(':')

				pT_ETH_01.Assign(lineValues[1])
				pT_ETH_02.Assign(lineValues[2])
				pT_NO_01.Assign(lineValues[3])
				pT_NO_02.Assign(lineValues[4])
				pT_NO_03.Assign(lineValues[5])
				pT_CH_01.Assign(lineValues[6])
				tOT_WEIGHT.Assign((float(lineValues[7]) - tare))
				tC_01.Assign(lineValues[8])
				tC_02.Assign(lineValues[9])
				tC_03.Assign(lineValues[10])

				man = [
					pT_ETH_01.getData(),
					pT_ETH_02.getData(),
					pT_NO_01.getData(),
					pT_NO_02.getData(),
					pT_NO_03.getData(),
					pT_CH_01.getData(),
					tOT_WEIGHT.getData(),
					tC_01.getData(),
					tC_02.getData(),
					tC_03.getData(),
					]
				
				window['TABLE'].update(values = man, row_colors = colors)

				pT_ETH_01.Graph(pT_ETH_01Color)
				pT_ETH_02.Graph(pT_ETH_02Color)
				pT_NO_01.Graph(pT_NO_01Color)
				pT_NO_02.Graph(pT_NO_02Color)
				pT_NO_03.Graph(pT_NO_03Color)
				pT_CH_01.Graph(pT_CH_01Color)
				tOT_WEIGHT.Graph(tOT_WEIGHTColor)
				tC_01.Graph(tC_01Color)
				tC_02.Graph(tC_02Color)
				tC_03.Graph(tC_03Color)

				x+=1

				if (x==500):

					x = -250
										
					pT_ETH_01.Lines(-250, 1520, 0, 1600, 250, -750)
					pT_ETH_02.Lines(-250, 1520, 0, 1600, 250, -750)
					pT_NO_01.Lines(-250, 1520, 0, 1600,  250,-750)
					pT_NO_02.Lines(-250, 1520, 0, 1600,  250,-750)
					pT_NO_03.Lines(-250, 1520, 0, 1600, 250, -750)
					pT_CH_01.Lines(-250, 1520, 0, 1600, 250, -750)
					tOT_WEIGHT.Lines(-250, 133, -140, 140, 20, -750)
					tC_01.Lines(-250, 95, -20, 100, 10, -750)
					tC_02.Lines(-250, 95, -20, 100, 10, -750)
					tC_03.Lines(-250, 95, -20, 100, 10, -750)
					
				event, values = window.read(timeout = 1)
				
				if event == 'TOT-WEIGHT':
					tare = float(lineValues[7])

				Events(event, values)

				if event == sg.WIN_CLOSED:
					break

			event, values = window.read(timeout = 1) 
					
			if event == 'TOT-WEIGHT':
				tare = float(lineValues[7])

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