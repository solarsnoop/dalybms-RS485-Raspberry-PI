import time
import sys
import paho.mqtt.client as mqtt
from dalybms import DalyBMS

# --- CONFIGURATION ---
# Path to your Daly RS485 to USB Adapter (e.g. /dev/ttyUSB0 or /dev/serial/by-path/...)
DALY_PATH = 'YOUR_SERIAL_PATH_HERE' 
# IP address of your MQTT broker (e.g. "192.168.178.2")
MQTT_SERVER = "YOUR_MQTT_BROKER_IP"
# MQTT broker port (default is 1883)
MQTT_PORT = 1883
# Unique Client ID for the MQTT broker
CLIENT_ID = "Daly_BMS_Logger"
# Base topic for MQTT messages
MQTT_BASE = "solpiplog/daly"
# Battery capacity in AH for calculation of remaining power please modify to your value
MAX_AH = 280.0
# Update interval in seconds can be modify
INTERVAL = 3 

# Initialize MQTT Client
client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)

try:
    # Attempt to connect to the broker
    client.connect(MQTT_SERVER, MQTT_PORT, 60)
except Exception as e:
    sys.stderr.write(f"Initial Connection Error: {e}\n")
    # Exit with error so systemd can handle the restart
    sys.exit(1)

# Start MQTT network loop in a background thread
client.loop_start()

# IMPORTANT: Wait 2 seconds to ensure the background connection is established
# before the first check in the main loop.
time.sleep(2)

bms = DalyBMS()
print(f"Daly-Logger active. Sending data every {INTERVAL}s...")

while True:
    try:
        # SELF-HEALING: Verify if MQTT connection is still active
        if not client.is_connected():
            raise Exception("MQTT Connection lost")

        # Establish connection to BMS and fetch telemetry
        bms.connect(DALY_PATH)
        soc_data = bms.get_soc()
        
        if soc_data:
            cell_voltages = bms.get_cell_voltages()
            temps = bms.get_temperatures()
            status_bms = bms.get_status()
            
            # Calculate remaining AH based on SOC percentage
            calc_rem = round((MAX_AH * soc_data['soc_percent']) / 100.0, 2)
            
            # Publish core battery data
            client.publish(f"{MQTT_BASE}/volt", str(soc_data['total_voltage']))
            client.publish(f"{MQTT_BASE}/ampere", str(soc_data['current']))
            client.publish(f"{MQTT_BASE}/soc", str(soc_data['soc_percent']))
            client.publish(f"{MQTT_BASE}/remainah", str(calc_rem))
            client.publish(f"{MQTT_BASE}/temp1", str(temps.get(1, 0)))
            client.publish(f"{MQTT_BASE}/temp2", str(temps.get(2, 0)))
            
            if status_bms:
                client.publish(f"{MQTT_BASE}/cycles", str(status_bms.get('cycles', 0)))

            # Cell Voltage Analysis and individual cell publishing
            if cell_voltages:
                # Filter None values and calculate min/max/drift
                # Adjust range(1, 17) for 16 cells if necessary
                v_list = [cell_voltages.get(i) for i in range(1, 17) if cell_voltages.get(i) is not None]
                if v_list:
                    v_max, v_min = max(v_list), min(v_list)
                    client.publish(f"{MQTT_BASE}/maxvoltage", str(v_max))
                    client.publish(f"{MQTT_BASE}/minvoltage", str(v_min))
                    client.publish(f"{MQTT_BASE}/drift", str(round(v_max - v_min, 3)))
                
                # Publish individual cell voltages (e.g. cell01, cell02...)
                for i in range(1, 17):
                    if i in cell_voltages:
                        client.publish(f"{MQTT_BASE}/cell{i:02d}", str(cell_voltages[i]))

        # Main loop delay
        time.sleep(INTERVAL)

    except Exception as e:
        sys.stderr.write(f"Critical Error: {e}\n")
        # Exit with error code 1 to trigger systemd auto-restart
        sys.exit(1)
