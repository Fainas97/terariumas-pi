import Adafruit_DHT
import threading
import time
import requests
import RPi.GPIO as GPIO
from datetime import datetime
from flask import Flask, request
import math

app = Flask(__name__)

ledHeater = 13    # Heater
ledLight = 17   # Light
heaterStatus = 0
lightStatus = 0
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(ledHeater, GPIO.OUT)
GPIO.setup(ledLight, GPIO.OUT)

DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 4

def average(list, isRound=False):
    averageNumber = sum(list) / len(list)
    if isRound:
        if averageNumber - math.floor(averageNumber) < 0.5:
            return math.floor(averageNumber)
        return math.ceil(averageNumber)
    return averageNumber

def light():
    global lightStatus
    if (time_light_start <= datetime.now().strftime("%H:%M:%S") <= time_light_end):
        GPIO.output(ledLight, GPIO.HIGH)
        lightStatus = GPIO.HIGH
    else:
        GPIO.output(ledLight, GPIO.LOW)
        lightStatus = GPIO.LOW

def controlHeat(temperature, humidity):
    global heaterStatus
    report = ''
    if (int(temperature) <= temp_limit - temp_hysteresis):
        report = 'Temperature is to low - {0:0.1f}°C limit {1:0.1f}°C - {2:0.1f}°C hysteresis'.format(temperature, temp_limit, temp_hysteresis)
        print(report)
        GPIO.output(ledHeater, GPIO.HIGH)
        heaterStatus = GPIO.HIGH
        sendMessage(report, active=0)
    if (int(temperature) >= temp_limit + temp_hysteresis):
        report = 'Temperature is to high - {0:0.1f}°C limit {1:0.1f}°C + {2:0.1f}°C hysteresis'.format(temperature, temp_limit, temp_hysteresis)
        print(report)
        GPIO.output(ledHeater, GPIO.LOW)
        heaterStatus = GPIO.LOW
        sendMessage(report, active=0)
    if (int(humidity) <= humi_limit - humi_hysteresis):
        report = 'Humidity is to low - {0:0.1f}% limit {1:0.1f}% - {2:0.1f}% hysteresis'.format(humidity, humi_limit, humi_hysteresis)
        print(report)
        sendMessage(report, active=0)
    if (int(humidity) > humi_limit + humi_hysteresis):
        report = 'Humidity is to high - {0:0.1f}% limit {1:0.1f}% + {2:0.1f}% hysteresis'.format(humidity, humi_limit, humi_hysteresis)
        print(report)
        sendMessage(report, active=0)

def sendData(temperature, humidity, heater, lightStatus):
    post_data = {'humidity': humidity, 'temperature': temperature, 'light': lightStatus, 'heater': heaterStatus, 'auth': auth}
    post_response = requests.post(url='http://192.168.0.100:8000/terrarium/data', data=post_data)
    print(post_response.text)
    print(post_response.status_code)
    
def sendMessage(message, active):
    post_data = {'message' : message, 'auth' : auth, 'active' : active}
    post_response = requests.post(url='http://192.168.0.100:8000/message/data', data=post_data)
    print(post_response.text)
    print(post_response.status_code)

@app.route('/send/settings', methods = ['POST'])
def result():
    if (auth == request.form['auth']):
        global temp_hysteresis
        global temp_limit
        global humi_hysteresis
        global humi_limit
        global time_light_start
        global time_light_end
        temp_hysteresis = int(request.form['temp_hysteresis'])
        temp_limit = int(request.form['temp_limit'])
        humi_hysteresis = int(request.form['humi_hysteresis'])
        humi_limit = int(request.form['humi_limit'])
        time_light_start = request.form['time_light_start']
        time_light_end = request.form['time_light_end']
        return "Received"
    return "False"
    
def server():
    app.run(host='0.0.0.0', port = 8090, debug=True, use_reloader=False)

def dht():
    temp_list = []
    humi_list = []
    heater_list = []
    
    temp_mes = []
    heater_mes = []
    while True:
        humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)

        if humidity is not None and temperature is not None and 0 <= humidity <= 100:
            light()
            print("Temp={0:0.1f}°C  Humidity={1:0.1f}%".format(temperature, humidity))
            heater_list.append(heaterStatus)
            temp_list.append(temperature)
            humi_list.append(humidity)
            
            temp_mes.append(temperature)
            heater_mes.append(heaterStatus)
            if (len(temp_list) >= 10):
                temp_t = average(temp_list)
                humi_t = average(humi_list)
                
                controlHeat(temp_t, humi_t)
                sendData(temp_t, humi_t, average(heater_list, isRound=True), lightStatus)
                
                humi_list = []
                temp_list = []
                heater_list = []
            if (len(temp_mes) >= 30):
                temp_t = average(temp_mes)
                heater_t = average(heater_mes)
                if (heater_t >= 0.9 and temp_t < temp_limit - temp_hysteresis and temperature < temp_limit - temp_hysteresis):
                    report = 'Temperature is not rising, past 100 measurements temp average {0:0.1f}°C limit {1:0.1f}°C, heater status {2:d}%'.format(temp_t, temp_limit + temp_hysteresis, int(heater_t * 100))
                    sendMessage(report, active=1)
                    print(report)
                elif (heater_t <= 0.1 and temp_t > temp_limit + temp_hysteresis and temperature > temp_limit + temp_hysteresis):
                    report = 'Temperature is not decreasing, past 100 measurements temp average {0:0.1f}°C limit {1:0.1f}°C, heater status {2:d}%'.format(temp_t, temp_limit + temp_hysteresis, int(heater_t * 100))
                    sendMessage(report, active=1)
                temp_mes = []
                heater_mes = []
        else:
            print("Failed to retrieve data from humidity sensor")
        time.sleep(3)

temp_hysteresis = 2
temp_limit = 27
humi_hysteresis = 10
humi_limit = 30
time_light_start = '18:09:20'
time_light_end = '18:12:05'

auth = 'd428f7216c7d4bd27942b5d4a7709cf1e7ad16a86afbe3126040102bbaea2fee'

first = threading.Thread(target=server)
second = threading.Thread(target=dht)
first.start()
second.start()