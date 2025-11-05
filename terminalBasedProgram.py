import json

def AINNumber():
    while (s := input("Please enter acquired pin: ")):
        try:
            pin = int(s)
        except ValueError:
            print("Please enter a valid number")
            continue

        if pin < 0 or pin > 15:
            print("Pin is not in range (0–15)")
        else:
            return pin

def Sensortype():
    print("Voltage")
    print("Thermocouple")
    print("Pressure")

    while (s := input("Please choose from the available sensor types: ")):
        if s not in ("Voltage", "Thermocouple", "Pressure"):
            print("Please choose one of the available sensors")
        elif s == "Voltage":
            return "Voltage"
        elif s == "Thermocouple":
            return "Thermocouple"
        elif s == "Pressure":
            return "Pressure"

def isDifferential():
    while True:
        choice = input("Is this a differential input? (yes/no): ").strip().lower()
        if choice in ("y", "yes"):
            return True
        elif choice in ("n", "no"):
            return False
        else:
            print("Please choose whether this is a differential input (yes/no)")

def main():
    while True:
        pin = AINNumber()
        sensor = Sensortype()
        diff = isDifferential()

        print("\nSummary:")
        print(f"  AIN pin: {pin}")
        print(f"  Sensor type: {sensor}")
        print(f"  Differential: {diff}")

        cont = input("\nAdd another channel? (y/n): ").strip().lower()
        if cont not in ("y", "yes"):
            break

if __name__ == "__main__":
    main()
