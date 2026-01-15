import json
import os

# mapping bases for X3/X4/X5 (CB37 AIN0..13 -> actual AIN)
BANK_BASE = {
    "X3": 48,
    "X4": 72,
    "X5": 96
}

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
                # store used pins as strings "AIN#", "FIO#", "DAC#"
                if "AIN" in ch:
                    used_pins.add(ch["AIN"])
                if "NegativeAIN" in ch:
                    used_pins.add(ch["NegativeAIN"])
                if "FIO" in ch:
                    used_pins.add(ch["FIO"])
                if "DAC" in ch:
                    used_pins.add(ch["DAC"])

            print("\nLoaded existing configuration from 'labjack_channels.json'")
            print_configured_channels(channels)
            return channels, used_pins

        except (json.JSONDecodeError, TypeError):
            print("Warning: Could not parse JSON file. Starting with an empty configuration.")
            return [], set()


def print_configured_channels(channels):
    if not channels:
        print("\nNo channels currently configured.\n")
        return

    print("\n=== Configured Channels ===")
    for ch in channels:
        t = ch.get("Type", "AIN")
        if t == "AIN":
            ain = ch["AIN"]
            neg = ch.get("NegativeAIN", "—")
            print(f"  {ain} - {neg} | {ch['SensorType']} | Differential: {ch['Differential']}")
        elif t == "FIO":
            print(f"  {ch['FIO']} | FIO | Direction: {ch.get('Direction','—')}")
        elif t == "DAC":
            print(f"  {ch['DAC']} | DAC | Voltage: {ch.get('Voltage','—')}")
    print("============================")


def remove_channel(channels, used_pins):
    if not channels:
        print("\nNo channels to remove.")
        return

    print_configured_channels(channels)
    try:
        label = input("\nEnter the channel label to remove (e.g. AIN94, FIO3, DAC0): ").strip()
    except ValueError:
        print("Invalid input.")
        return

    for ch in channels:
        # compare by label membership
        if (ch.get("AIN") == label) or (ch.get("FIO") == label) or (ch.get("DAC") == label):
            channels.remove(ch)
            # remove used pins tracked
            if "AIN" in ch:
                used_pins.discard(ch["AIN"])
            if "NegativeAIN" in ch:
                used_pins.discard(ch["NegativeAIN"])
            if "FIO" in ch:
                used_pins.discard(ch["FIO"])
            if "DAC" in ch:
                used_pins.discard(ch["DAC"])
            print(f"\nRemoved {label} successfully.")
            return

    print(f"\n{label} not found in configuration.")


def Sensortype():
    print("\nAvailable sensor types:")
    print("  - Voltage")
    print("  - Thermocouple")
    print("  - Pressure")
    print("  - LoadCell")

    while True:
        s = input("Please choose from the available sensor types: ").strip().capitalize()
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


def ask_bank():
    while True:
        b = input("Which Mux80 bank? (X2, X3, X4, X5): ").strip().upper()
        if b in ("X2", "X3", "X4", "X5"):
            return b
        print("Please choose one of X2, X3, X4, X5.")


def ask_cb37_pin(bank):
    """
    Ask user to select CB37 pin type and index.
    Returns a tuple (type, index) where type in {"AIN","FIO","DAC"}.
    """
    while True:
        print("\nCB37 pin types:")
        print("  1) AIN0 - AIN13")
        print("  2) FIO0 - FIO7")
        print("  3) DAC0 or DAC1")
        choice = input("Select pin type (1-3): ").strip()
        if choice == "1":
            try:
                idx = int(input("Enter AIN index on CB37 (0-13): ").strip())
            except ValueError:
                print("Enter a valid integer 0-13.")
                continue
            if idx < 0 or idx > 13:
                print("AIN index out of range (0-13).")
                continue
            if bank == "X2" and idx > 3:
                print("On X2 we allow only AIN0-AIN3 for AIN configuration. Please choose another pin or bank.")
                return None
            return ("AIN", idx)

        elif choice == "2":
            try:
                idx = int(input("Enter FIO index (0-7): ").strip())
            except ValueError:
                print("Enter a valid integer 0-7.")
                continue
            if idx < 0 or idx > 7:
                print("FIO index out of range (0-7).")
                continue
            return ("FIO", idx)

        elif choice == "3":
            dac = input("Enter DAC channel (0 or 1): ").strip()
            if dac not in ("0", "1"):
                print("Only DAC0 or DAC1 are available.")
                continue
            return ("DAC", int(dac))

        else:
            print("Please choose 1-3.")


def map_cb37_to_actual_ain(bank, cb37_idx):
    """
    Map CB37 AIN index (0..13) to actual T7 AIN number based on bank.
    For X2 we only allow 0..3 and map directly to AIN0..AIN3.
    For X3/X4/X5 use BANK_BASE.
    """
    if bank == "X2":
        #only AIN0..AIN3 are allowed on X2
        if 0 <= cb37_idx <= 3:
            return cb37_idx
        return None
    else:
        base = BANK_BASE[bank]
        return base + cb37_idx  # CB37 AIN0 -> base + 0, AIN13 -> base + 13


def add_channel_flow(channels, used_pins):
    # Ask whether this channel is on a mux80
    on_mux = input("Is this channel on a Mux80? (yes/no): ").strip().lower()
    on_mux_flag = on_mux in ("y", "yes")

    bank = None
    if on_mux_flag:
        bank = ask_bank()

    # ask CB37 pin if mux80 used, else allow direct AIN/FIO/DAC entry
    if on_mux_flag:
        res = ask_cb37_pin(bank)
        if res is None:
            # invalid selection (e.g., tried AIN4..13 on X2)
            return  # return to main menu
        pin_type, idx = res

        if pin_type == "AIN":
            mapped_ain = map_cb37_to_actual_ain(bank, idx)
            if mapped_ain is None:
                print(f"CB37 AIN{idx} is not available on {bank}.")
                return

            # ask differential or single-ended
            diff = isDifferential()
            # validate differential rules
            if bank == "X2":
                # differential only allowed for AIN0 -> AIN1 and AIN2 -> AIN3
                if diff and idx not in (0, 2):
                    print(f"AIN{idx} cannot be differential on bank {bank}.")
                    return  # return to main menu (user requested this behavior)
                if diff:
                    pos_label = f"AIN{mapped_ain}"
                    neg_label = f"AIN{mapped_ain + 1}"  # 0->1, 2->3
                    if pos_label in used_pins or neg_label in used_pins:
                        print("One of the pins is already configured.")
                        return
                    used_pins.add(pos_label)
                    used_pins.add(neg_label)
                    sensor = Sensortype()
                    channel_info = {
                        "Type": "AIN",
                        "AIN": pos_label,
                        "NegativeAIN": neg_label,
                        "SensorType": sensor,
                        "Differential": True,
                        "Bank": bank,
                        "CB37_Index": idx
                    }
                else:
                    pos_label = f"AIN{mapped_ain}"
                    if pos_label in used_pins:
                        print("That AIN is already configured.")
                        return
                    used_pins.add(pos_label)
                    sensor = Sensortype()
                    channel_info = {
                        "Type": "AIN",
                        "AIN": pos_label,
                        "SensorType": sensor,
                        "Differential": False,
                        "Bank": bank,
                        "CB37_Index": idx
                    }

            else:
                # X3/X4/X5
                # differential allowed only for CB37 AIN0..AIN7 (idx 0..7)
                if diff and idx > 7:
                    print(f"AIN{idx} cannot be differential on bank {bank}.")
                    return  # return to main menu
                if diff:
                    pos_label = f"AIN{mapped_ain}"
                    neg_label = f"AIN{mapped_ain + 8}"  # positive + 8
                    if pos_label in used_pins or neg_label in used_pins:
                        print("One of the pins is already configured.")
                        return
                    used_pins.add(pos_label)
                    used_pins.add(neg_label)
                    sensor = Sensortype()
                    channel_info = {
                        "Type": "AIN",
                        "AIN": pos_label,
                        "NegativeAIN": neg_label,
                        "SensorType": sensor,
                        "Differential": True,
                        "Bank": bank,
                        "CB37_Index": idx
                    }
                else:
                    pos_label = f"AIN{mapped_ain}"
                    if pos_label in used_pins:
                        print("That AIN is already configured.")
                        return
                    used_pins.add(pos_label)
                    sensor = Sensortype()
                    channel_info = {
                        "Type": "AIN",
                        "AIN": pos_label,
                        "SensorType": sensor,
                        "Differential": False,
                        "Bank": bank,
                        "CB37_Index": idx
                    }

        elif pin_type == "FIO":
            fio_label = f"FIO{idx}"
            if fio_label in used_pins:
                print("That FIO is already used.")
                return
            direction = input("Direction (input/output): ").strip().lower()
            if direction not in ("input", "output"):
                direction = "input"
            used_pins.add(fio_label)
            channel_info = {
                "Type": "FIO",
                "FIO": fio_label,
                "Direction": direction,
                "Bank": bank,
                "CB37_Index": idx
            }

        else:  # DAC
            dac_label = f"DAC{idx}"
            if dac_label in used_pins:
                print("That DAC is already used.")
                return
            try:
                value = float(input("Enter output voltage (0–5 V): ").strip())
            except ValueError:
                print("Invalid voltage entered.")
                return
            if value < 0: value = 0
            if value > 5: value = 5
            used_pins.add(dac_label)
            channel_info = {
                "Type": "DAC",
                "DAC": dac_label,
                "Voltage": value,
                "Bank": bank,
                "CB37_Index": idx
            }

    else:
        # Not on Mux80: allow direct AIN(0-15), FIO0-7, DAC0/1
        print("\nNot using Mux80 for this channel. Choose pin type:")
        res = ask_cb37_pin_no_mux()
        if res is None:
            return
        pin_type, idx = res
        if pin_type == "AIN":
            # direct AIN0..15
            if idx < 0 or idx > 15:
                print("AIN must be 0-15 for a non-Mux device.")
                return
            pos_label = f"AIN{idx}"
            diff = isDifferential()
            if diff:
                # For non-mux, assume standard pairing even->odd only for 0/1 and 2/3? 
                # We'll restrict to the simplest: only allow differential if paired exists within 0..15 and not used.
                # Require user to enter the negative by choosing an AIN that is its correct pair (we won't invent pair rules).
                try:
                    neg_idx = int(input("Enter negative AIN index (0-15): ").strip())
                except ValueError:
                    print("Invalid negative AIN.")
                    return
                neg_label = f"AIN{neg_idx}"
                if pos_label in used_pins or neg_label in used_pins:
                    print("One of the pins is already configured.")
                    return
                used_pins.add(pos_label)
                used_pins.add(neg_label)
                sensor = Sensortype()
                channel_info = {
                    "Type": "AIN",
                    "AIN": pos_label,
                    "NegativeAIN": neg_label,
                    "SensorType": sensor,
                    "Differential": True,
                    "Bank": None,
                    "CB37_Index": None
                }
            else:
                if pos_label in used_pins:
                    print("That AIN is already configured.")
                    return
                used_pins.add(pos_label)
                sensor = Sensortype()
                channel_info = {
                    "Type": "AIN",
                    "AIN": pos_label,
                    "SensorType": sensor,
                    "Differential": False,
                    "Bank": None,
                    "CB37_Index": None
                }

        elif pin_type == "FIO":
            fio_label = f"FIO{idx}"
            if fio_label in used_pins:
                print("That FIO is already used.")
                return
            direction = input("Direction (input/output): ").strip().lower()
            if direction not in ("input", "output"):
                direction = "input"
            used_pins.add(fio_label)
            channel_info = {
                "Type": "FIO",
                "FIO": fio_label,
                "Direction": direction
            }
        else:  # DAC
            dac_label = f"DAC{idx}"
            if dac_label in used_pins:
                print("That DAC is already used.")
                return
            try:
                value = float(input("Enter output voltage (0–5 V): ").strip())
            except ValueError:
                print("Invalid voltage entered.")
                return
            if value < 0: value = 0
            if value > 5: value = 5
            used_pins.add(dac_label)
            channel_info = {
                "Type": "DAC",
                "DAC": dac_label,
                "Voltage": value
            }

    # if we get here, channel_info should be defined
    channels.append(channel_info)
    print("\nAdded new channel:")
    print(json.dumps(channel_info, indent=2))
    print_configured_channels(channels)


def ask_cb37_pin_no_mux():
    # same as ask_cb37_pin but without bank-specific X2 restriction and mapping
    while True:
        print("\nPin types (no Mux80):")
        print("  1) AIN0 - AIN15")
        print("  2) FIO0 - FIO7")
        print("  3) DAC0 or DAC1")
        choice = input("Select pin type (1-3): ").strip()
        if choice == "1":
            try:
                idx = int(input("Enter AIN index (0-15): ").strip())
            except ValueError:
                print("Enter a valid integer 0-15.")
                continue
            if idx < 0 or idx > 15:
                print("AIN index out of range (0-15).")
                continue
            return ("AIN", idx)
        elif choice == "2":
            try:
                idx = int(input("Enter FIO index (0-7): ").strip())
            except ValueError:
                print("Enter a valid integer 0-7.")
                continue
            if idx < 0 or idx > 7:
                print("FIO index out of range (0-7).")
                continue
            return ("FIO", idx)
        elif choice == "3":
            dac = input("Enter DAC channel (0 or 1): ").strip()
            if dac not in ("0", "1"):
                print("Only DAC0 or DAC1 are available.")
                continue
            return ("DAC", int(dac))
        else:
            print("Please choose 1-3.")


def main():
    channels, used_pins = load_channels()

    if channels:
        overwrite = input("\nDo you want to completely overwrite the existing configuration? (y/n): ").strip().lower()
        if overwrite in ("y", "yes"):
            channels = []
            used_pins = set()
            print("\nConfiguration cleared.\n")

    print("\n=== LabJack T7 Channel Configuration ===")
    while True:
        print("\nOptions:")
        print("  1. Add a channel")
        print("  2. Remove a channel")
        print("  3. View all configured channels")
        print("  4. Save and exit")

        choice = input("Select an option (1-4): ").strip()

        if choice == "1":
            add_channel_flow(channels, used_pins)

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
