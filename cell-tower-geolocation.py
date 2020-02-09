#!/usr/bin/env python3

import serial, time, json, requests, sys, os

api_key = "<api_key>"

print("")
print(" Cell Tower Geolocation ")
print(" via SIM800 Raspberry Pi GSM/GPRS HAT ")
print(" github.com/sion-evans/cell-tower-geolocation ")
print("")

if len(sys.argv) == 1 or "-h" in sys.argv:
    print(" Usage: " + sys.argv[0] + " <options>")
    print("")
    print(" Options:")
    print(" -s   Survey Available Cell Towers.")
    print(" -c   Locate Coordinates of Cell Towers. [Google Maps API Required]")
    print(" -m   Plot Coordinates to Google Maps HTML Template. [Google Maps API Required]")
    print("")

def query(input):

    port = serial.Serial('/dev/ttyS0', baudrate=115200, timeout=1)

    command = input + '\r'
    port.write(bytes(command, 'utf-8'))

    rcv = str(port.read(256), 'utf-8')

    while len(rcv) == 0 or rcv == command:
        time.sleep(1)
        rcv = str(port.read(256), 'utf-8')

    output = ""

    while len(rcv) > 0:
        output = output + rcv

        if output[:len(command)] == command:
            output = output[len(command):]

        if len(rcv) < 256:
            break
        else:
            rcv = str(port.read(256), 'utf-8')

    dataList = output.split('\r\n')
    while '' in dataList:
        dataList.remove('')

    return dataList

if __name__ == '__main__':

    if "-s" in sys.argv:

        print("[*]", "Performing AT test..")
        response = query('AT')

        if 'OK' in response:
            print("[+]", "AT test successful!")
        else:
            print("[!]", "AT test failed.")
            exit()

        print("[*]", "Querying survey format..")
        response = query('AT+CNETSCAN?')

        if 'OK' in response:
            if '+CNETSCAN: 1' in response:
                print("[+]", "Currently displaying LAC and BSIC information!")
            elif '+CNETSCAN: 0' in response:
                print("[-]", "Currently not displaying LAC and BSIC information.")
                print("[*]", "Attempting to change survey format..")
                response = query('AT+CNETSCAN=1')
                if 'OK' in response:
                    print("[+]", "Successfully changed survey format!")
                else:
                    print("[!]", "Failed to change survey format.")
                    exit()
            else:
                print("[!]", "Unexpected response.")
        else:
            print("[!]", "Query failed.")
            exit()

        print("[*]", "Performing survey..")
        cells = []
        response = query('AT+CNETSCAN')

        if 'OK' in response:
            print("[+]", "Survey successful!")

            for i in response:
                if i != "OK":

                    pairs = i.split(',')

                    dictionary = {}

                    for i in pairs:

                        if i.split(':')[0] == "Operator": # Long format alphanumeric of network operator.
                            dictionary["Operator"] = str(i.split(':')[1]).strip('\"')
                        elif i.split(':')[0] == "MCC": # Mobile country code.
                            dictionary["MCC"] = int(i.split(':')[1])
                        elif i.split(':')[0] == "MNC": # Mobile network code.
                            dictionary["MNC"] = int(i.split(':')[1])
                        elif i.split(':')[0] == "Rxlev": # Recieve level, in decimal format.
                            dictionary["Rxlev"] = int(i.split(':')[1])
                        elif i.split(':')[0] == "Cellid": # Cell identifier, in hexadecimal format.
                            dictionary["Cellid"] = int(i.split(':')[1], 16)
                        elif i.split(':')[0] == "Arfcn": # Absolute radio frequency channel number, in decimal format.
                            dictionary["Arfcn"] = int(i.split(':')[1])
                        elif i.split(':')[0] == "Lac": # Location area code, in hexadecimal format.
                            dictionary["Lac"] = int(i.split(':')[1], 16)
                        elif i.split(':')[0] == "Bsic": # Location area code, in hexadecimal format.
                            dictionary["Bsic"] = int(i.split(':')[1], 16) # Base station identity code, in hexadecimal format.

                    cells.append(dictionary)

            cells = sorted(cells, reverse = True, key = lambda i: (i["Operator"], i["Rxlev"]))

            filename = "survey/survey_" + str(int(time.time())) + ".json"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as outfile:
                json.dump(cells, outfile)
            print("[+]", "Survey saved to '" + filename + "'.")
            print("")
        else:
            print("[!]", "Survey failed.")

    if "-c" in sys.argv:

        url = "https://www.googleapis.com/geolocation/v1/geolocate?key=" + api_key
        headers = {'content-type': 'application/json'}

        for filename in os.listdir('survey/'):
            if not filename.endswith(".json"):
                continue

            print("[*]", "Processing '" + filename + "'.")

            with open('survey/' + filename) as json_file:
                json_data = json.load(json_file)

            dictionary = {}

            for i in json_data:
                if i["Operator"] not in dictionary:
                    dictionary[i["Operator"]] = []
                dictionary[i["Operator"]].append(i)

            for i in dictionary:
                output_filename = os.path.splitext(filename)[0] # e.g. survey_1581259393
                output_filename = output_filename.split("_")[1] # e.g. 1581259393
                output_filename = "coordinates/coordinates_" + output_filename + "_" + i + ".json"

                if os.path.isfile(output_filename):
                    print("[*]", "Skipping '" + i + "', file exists: '" + output_filename + "'.")
                    continue

                print("[*]", "Processing API request(s) for operator '" + i + "'.")

                result = []
                for x in dictionary[i]:
                    body = {
                            "cellTowers": [
                                {
                                    "cellId": int(x["Cellid"]),
                                    "locationAreaCode": int(x["Lac"]),
                                    "mobileCountryCode": int(x["MCC"]),
                                    "mobileNetworkCode": int(x["MNC"]),
                                    "signalStrength": int(-110 + int(x["Rxlev"]))
                                }
                            ]
                    }

                    print("[*]", "Submitting API request for CID: " + str(x["Cellid"]) + ".")
                    response = requests.post(url, data=json.dumps(body), headers=headers)
                    result.append(json.loads(response.text))

                os.makedirs(os.path.dirname(output_filename), exist_ok=True)
                with open(output_filename, 'w') as outfile:
                    outfile.write(str(result))
                print("[+]", "Coordinates saved to '" + output_filename + "'.")
                print("")

    if "-m" in sys.argv:

        with open("template.html", 'r') as outfile:
            html = outfile.read()

        html = html.replace("<api_key>", api_key)

        for filename in os.listdir('coordinates/'):
            if not filename.endswith(".json"):
                continue

            output_filename = 'coordinates/' + filename.replace(".json", ".html")
            if os.path.isfile(output_filename):
                print("[*]", "Skipping '" + filename + "', file exists: '" + output_filename + "'.")
                continue

            print("[*]", "Processing '" + filename + "'.")

            with open('coordinates/' + filename) as json_file:
                data = json_file.read()

            output = html.replace("var cells = []", "var cells = " + data)

            os.makedirs(os.path.dirname(output_filename), exist_ok=True)
            with open(output_filename, 'a') as outfile:
                outfile.write(output)
            print("[+]", "Coordinates plotted to '" + output_filename + "'.")
            print("")
