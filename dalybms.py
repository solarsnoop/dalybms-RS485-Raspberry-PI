import time
from dalybms import DalyBMS
import paho.mqtt.publish as publish

# --- KONFIGURATION ---
# here your Daly RS485 to USB Adapter find under dev/serial/by-path/
DALY_PATH = '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3:1.0-port0'
# your IP from yur MQTT broker
MQTT_SERVER = "192.x.x.x"
# Your MQTT broker port
MQTT_PORT = 1886
# your topic (here same like solpiplog, but free to edit)
MQTT_BASE = "solpiplog/daly"
# set your AH from yur battery for calculate rest power ...
MAX_AH = 100
# set up your update interval in seconds
INTERVALL = 3 

bms = DalyBMS()

print(f"Daly-Logger aktiv. send all {INTERVALL}s...")

while True:
    try:
        bms.connect(DALY_PATH)
        
        soc_data = bms.get_soc()
        cell_voltages = bms.get_cell_voltages()
        temps = bms.get_temperatures()
        status = bms.get_status()

        if soc_data:
            # AH Berechnung
            calc_remain_ah = round((MAX_AH * soc_data['soc_percent']) / 100.0, 2)

            msgs = [
                {'topic': f"{MQTT_BASE}/volt", 'payload': str(soc_data['total_voltage'])},
                {'topic': f"{MQTT_BASE}/ampere", 'payload': str(soc_data['current'])},
                {'topic': f"{MQTT_BASE}/soc", 'payload': str(soc_data['soc_percent'])},
                {'topic': f"{MQTT_BASE}/remainah", 'payload': str(calc_remain_ah)},
                {'topic': f"{MQTT_BASE}/temp1", 'payload': str(temps.get(1, 0))},
                {'topic': f"{MQTT_BASE}/temp2", 'payload': str(temps.get(2, 0))},
                {'topic': f"{MQTT_BASE}/cycles", 'payload': str(status.get('cycles', 0) if status else 0)}
            ]

            if cell_voltages:
                # please modify if you use more than 7 cells eg.: 16 cell change 8 to 17 !
                v_list = [cell_voltages.get(i) for i in range(1, 8) if cell_voltages.get(i) is not None]
                if v_list:
                    v_max = max(v_list)
                    v_min = min(v_list)
                    v_drift = round(v_max - v_min, 3)
                    
                    msgs.append({'topic': f"{MQTT_BASE}/maxvoltage", 'payload': str(v_max)})
                    msgs.append({'topic': f"{MQTT_BASE}/minvoltage", 'payload': str(v_min)})
                    msgs.append({'topic': f"{MQTT_BASE}/drift", 'payload': str(v_drift)}) 
                
                for i in range(1, 8):
                    msgs.append({'topic': f"{MQTT_BASE}/cell{i:02d}", 'payload': str(cell_voltages.get(i))})

            publish.multiple(msgs, hostname=MQTT_SERVER, port=MQTT_PORT)

    except Exception as e:
        print(f"conection error: {e}")
        time.sleep(2)

    time.sleep(INTERVALL)
