import json
import os

def AINNumber(prompt, used_pins) -> int:
    while True:
        s = input(prompt)
        try:
            pin = int(s)
        except ValueError:
            print("Please enter a valid number")
            continue

        if pin < 0 or pin > 84:
            print("Pin is not in range (0-84)")
        elif pin in used_pins:
            print(f"AIN{pin} is already configured. Please choose another.")
        else:
            return pin


def Sensortype():
    print("\nAvailable sensor types:")
    print("  - Voltage")
    print("  - Thermocouple")
    print("  - Pressure")
    print("  - LoadCell")

    while True:
        s = input("Please choose from the available sensor types: ").capitalize()
        if s not in ("Voltage", "Thermocouple", "Pressure", "Loadcell"):
            print("Please choose one of the available sensors")
        else:
            return "LoadCell" if s == "Loadcell" else s


def isDifferential():
    while True:
        choice = input("Is this a differential input? (yes/no): ").strip().lower()
        if choice in ("y", "yes"):
            return True
        elif choice in ("n", "no"):
            return False
        else:
            print("Please choose yes or no.")


def print_configured_channels(channels):
    if not channels:
        print("\nNo channels currently configured.")
        return

    print("\n=== Configured Channels ===")
    for ch in channels:
        ain = ch["AIN"]
        neg = ch.get("NegativeAIN", "—")
        print(f"  {ain} - {neg} | {ch['SensorType']} | Differential: {ch['Differential']}")
    print("============================")


def remove_channel(channels, used_pins):
    if not channels:
        print("\nNo channels to remove.")
        return

    print_configured_channels(channels)
    try:
        pin_to_remove = int(input("\nEnter the AIN number to remove: "))
    except ValueError:
        print("Invalid input. Must be a number.")
        return

    ain_label = f"AIN{pin_to_remove}"
    for ch in channels:
        if ch["AIN"] == ain_label:
            channels.remove(ch)
            used_pins.remove(pin_to_remove)
            neg_pin = ch.get("NegativeAIN")
            if neg_pin:
                used_pins.discard(int(neg_pin.replace("AIN", "")))
            print(f"\nRemoved {ain_label} successfully.")
            return

    print(f"\n{ain_label} not found in configuration.")


def load_channels():
    if not os.path.exists("labjack_channels.json"):
        return [], set()

    with open("labjack_channels.json", "r") as f:
        try:
            data = json.load(f)
            if isinstance(data, dict) and "Channels" in data:
                channels = data["Channels"]
            elif isinstance(data, list):
                channels = data
            else:
                print("Unrecognized JSON structure. Starting fresh.")
                return [], set()

            used_pins = set()
            for ch in channels:
                if "AIN" in ch:
                    used_pins.add(int(ch["AIN"].replace("AIN", "")))
                if "NegativeAIN" in ch:
                    used_pins.add(int(ch["NegativeAIN"].replace("AIN", "")))

            print("\nLoaded existing configuration from 'labjack_channels.json'")
            print_configured_channels(channels)
            return channels, used_pins

        except (json.JSONDecodeError, TypeError):
            print("Warning: Could not parse JSON file. Starting with an empty configuration.")
            return [], set()


def main():
    channels, used_pins = load_channels()

    if channels:
        overwrite = input("\nDo you want to completely overwrite the existing configuration? (y/n): ").strip().lower()
        if overwrite in ("y", "yes"):
            channels = []
            used_pins = set()
            print("\nConfiguration cleared.")

    print("\n=== LabJack T7 Channel Configuration ===")
    while True:
        print("\nOptions:")
        print("  1. Add a channel")
        print("  2. Remove a channel")
        print("  3. View all configured channels")
        print("  4. Save and exit")

        choice = input("Select an option (1-4): ").strip()

        if choice == "1":
            diff = isDifferential()

            if diff:
                ain_pos = AINNumber("Enter positive AIN (0-84): ", used_pins)
                used_pins.add(ain_pos)
                ain_neg = AINNumber("Enter negative AIN (0-84): ", used_pins)
                used_pins.add(ain_neg)
                sensor = Sensortype()

                channel_info = {
                    "AIN": f"AIN{ain_pos}",
                    "NegativeAIN": f"AIN{ain_neg}",
                    "SensorType": sensor,
                    "Differential": True
                }

            else:
                ain = AINNumber("Enter AIN (0-84): ", used_pins)
                used_pins.add(ain)
                sensor = Sensortype()

                channel_info = {
                    "AIN": f"AIN{ain}",
                    "SensorType": sensor,
                    "Differential": False
                }

            channels.append(channel_info)
            print("\nAdded new channel:")
            print(json.dumps(channel_info, indent=2))
            print_configured_channels(channels)

        elif choice == "2":
            remove_channel(channels, used_pins)

        elif choice == "3":
            print_configured_channels(channels)

        elif choice == "4":
            break

        else:
            print("Invalid option. Please select 1-4.")

    with open("labjack_channels.json", "w") as f:
        json.dump(channels, f, indent=4)

    print("\nConfiguration saved to 'labjack_channels.json'")
    print_configured_channels(channels)


if __name__ == "__main__":
    main()
