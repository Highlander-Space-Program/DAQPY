import random
from itertools import count
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


#count func counts up once and gets the next vals

#We're going to be taking a CSV file ( think txt) that const gets updated 


#This plt style use just specifies what chart

plt.style.use('fivethirtyeight')

x_vals = [] 
y_vals = []

index = count() 


def animate(i):
    data = pd.read_csv('data.csv')
    x = data['x_value']
    y1 = data['total_1']
    y2 = data['total_2']

    #cla just clears axis and makes it look cleaner 
    plt.cla() 

    plt.plot(x, y1, label='PsiVTime')
    plt.plot(x, y2, label='SomeOtherGraph')
    plt.legend()
    plt.tight_layout() 

ani = FuncAnimation(plt.gcf(), animate, interval =1000) 

plt.tight_layout()
plt.show() 
