import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from labjack import ljm
import json
from datetime import datetime as dt

#We're going to be taking a CSV/JSON file ( think txt) that const gets updated 

#Open first availbe labjack in Demo mode
#handle = ljm.openS(“ANY”, “ANY”, “-2”) 

#This is how we would call our t7
#handle = ljm.openS("T7", "Ethernet", "Auto")

def setupPlot():
    plt.legend()
    plt.tight_layout() 
    plt.xlabel("t+ (s)")
    plt.ylabel("temp. (F)")

#This plt style use just specifies what chart
plt.style.use('fivethirtyeight')

with open("data.json") as f:
    x,y = zip(*json.load(f)['data'])
start_ts = dt.fromisoformat(x[0])
x = [(dt.fromisoformat(ts) - start_ts).total_seconds() for ts in x[1:]]

def animate(frame):

    #cla just clears axis and makes it look cleaner 
    plt.cla() 

    plt.plot(x[:frame], y[:frame], label='TempVTime')
    setupPlot()

ani = FuncAnimation(plt.gcf(), animate, interval =1000) 

setupPlot()
plt.show()
