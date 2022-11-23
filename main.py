import network
import time
import ntptime
import urequests as requests
from machine import Pin, ADC, PWM, SDCard
from time import sleep
from os import mount
import uasyncio as asyncio
from nanoweb import Nanoweb

# my fork of my work

def connect_to_wifi():
  print("Connecting to WiFi", end="")
  sta_if = network.WLAN(network.STA_IF)
  sta_if.active(True)
  sta_if.connect('Wokwi-GUEST', '')
  while not sta_if.isconnected():
    print(".", end="")
    time.sleep(0.1)
  print(" Connected!")


def calc_lux(adc_val):
  GAMMA = 0.7;
  RL10 = 50;

  voltage = adc_val / 65535 * 5
  resistance = 2000 * voltage / (1 - voltage / 5)
  return round(pow(RL10 * 1e3 * pow(10, GAMMA) / resistance, (1 / GAMMA)), 2)


def write_to_db(line):
  with open("/sd/db.csv", "a") as file:
      file.write(line)
      file.write('\n')


def read_db():
  try:
    with open("/sd/db.csv", "r") as file:
        data = file.read()
        return data
  except:
    return ""


def get_current_time():
  global secs_add_to_utc_time
  return time.localtime(time.mktime(time.localtime())+secs_add_to_utc_time)


def setup_time():
  ntptime.host = "pool.ntp.org"

  try:
    ntptime.settime()
  except Exception as e:
    print("Error syncing time:", e)


async def light_control():
  global sunrise_time

  #запускаем фитолампу с восходом солнца, полярный день учтен
  if time.mktime(time.localtime())+secs_add_to_utc_time < sunrise_time:
    print(sunrise_time-time.mktime(time.localtime())+secs_add_to_utc_time)
    await asyncio.sleep(sunrise_time-time.mktime(time.localtime())+secs_add_to_utc_time)

  adc = ADC(Pin(32))
  adc.atten(ADC.ATTN_11DB)
  adc.width(ADC.WIDTH_12BIT)

  pwm = PWM(Pin(21))
  pwm.freq(19500)
  while True:
    if light_state:
      pwm.duty_u16(adc.read_u16())
    else:
      pwm.duty_u16(0)

    write_to_db(str(calc_lux(adc.read_u16())) + ':' +
    str(get_current_time()))
    await asyncio.sleep(5)
  

connect_to_wifi()
setup_time()
mount(SDCard(slot=3), "/sd")
light_time = 5
light_state = True
city = 'Москва' 
resp = requests.get('http://api.openweathermap.org/geo/1.0/direct?q=+'+city+'&limit=1&appid=5618870074845b5a54df87caf5684d6a').json()
lat, lon = str(resp[0]['lat']), str(resp[0]['lon'])
resp = requests.get('https://api.openweathermap.org/data/2.5/weather?lat='+lat+'&lon='+lon+'&appid=5618870074845b5a54df87caf5684d6a').json()
secs_add_to_utc_time = resp['timezone']
sunrise_time = resp['sys']['sunrise']-946684800+secs_add_to_utc_time

naw = Nanoweb()


@naw.route("/get_city")
def get_city(request):
    global city
    await request.writeResult(city, 200, 'OK', 'Content-Type: text/html')


@naw.route("/get_time")
def get_time(request):
    global light_time
    await request.writeResult(str(light_time), 200, 'OK', 'Content-Type: text/html')


@naw.route("/db")
def db(request):
    await request.writeResult(read_db(), 200, 'OK', 'Content-Type: text/html')


@naw.route("/set_city")
def set_city(request):
    global city
    global sunrise_time
    global secs_add_to_utc_time
    value = await request.readJSON()
    city = value['city']
    resp = requests.get('http://api.openweathermap.org/geo/1.0/direct?q=+'+city+'&limit=1&appid=5618870074845b5a54df87caf5684d6a').json()
    lat, lon = str(resp[0]['lat']), str(resp[0]['lon'])
    resp = requests.get('https://api.openweathermap.org/data/2.5/weather?lat='+lat+'&lon='+lon+'&appid=5618870074845b5a54df87caf5684d6a').json()
    secs_add_to_utc_time = resp['timezone']
    sunrise_time = resp['sys']['sunrise']-946684800+secs_add_to_utc_time
    await request.writeResult('ok', 200, 'OK', 'Content-Type: text/html')



@naw.route("/set_light_time")
def set_light_time(request):
    global light_time
    value = await request.readJSON()
    light_time = value['time']
    await request.writeResult('ok', 200, 'OK', 'Content-Type: text/html')


@naw.route("/off")
def off(request):
    global light_state
    light_state = False
    await request.writeResult('ok', 200, 'OK', 'Content-Type: text/html')


@naw.route("/on")
def on(request):
    global light_state
    light_state = True
    await request.writeResult('ok', 200, 'OK', 'Content-Type: text/html')


@naw.route("/")
def index(request):
    with open('index.txt', 'r') as f:
      html = f.read()
    await request.writeResult(html, 200, 'OK', 'Content-Type: text/html')


loop = asyncio.get_event_loop()
loop.create_task(naw.run())
loop.create_task(light_control())
loop.run_forever()
