import argparse
import os
import csv
import datetime

def detect_headers(header_row):
    """
    Automatically map column names based on keywords in the header row.
    """
    header_mapping = {}
    for column in header_row:
        lower_column = column.lower()
        if "sensor" in lower_column:
            header_mapping["Sensor"] = column
        elif "time" in lower_column:
            header_mapping["Time of Measurement"] = column
        elif "value" in lower_column:
            header_mapping["Value of Measurement"] = column
        elif "field" in lower_column or "measurement" in lower_column:
            header_mapping["Unit"] = column

    # Check if all required mappings were found
    required_keys = ["Sensor", "Time of Measurement", "Value of Measurement", "Unit"]
    for key in required_keys:
        if key not in header_mapping:
            raise ValueError(f"Could not automatically detect the column for '{key}'. Please ensure the CSV has appropriate headers.")

    return header_mapping

def split_measurements(file_path):
    # Create an output folder with a timestamp
    output_folder = f"output_measurements_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(output_folder, exist_ok=True)

    # Read the CSV file
    with open(file_path, mode='r') as csv_file:
        # Skip metadata rows (lines starting with #)
        csv_reader = csv.reader(csv_file)
        rows = [row for row in csv_reader if not row[0].startswith("#")]

        # Extract the actual headers and data rows
        header_row = rows[0]
        data_rows = rows[1:]
        csv_reader = csv.DictReader(data_rows, fieldnames=header_row)

        # Automatically detect headers
        header_mapping = detect_headers(header_row)

        # Dictionary to store grouped data
        sensor_data = {}
        all_times = []

        for row in csv_reader:
            # Map the CSV column headers to the required fields
            sensor = row[header_mapping['Sensor']]
            time_of_measurement = row[header_mapping['Time of Measurement']]
            value_of_measurement = row[header_mapping['Value of Measurement']]
            unit = row[header_mapping['Unit']]

            # Collect all times to calculate start and stop times
            all_times.append(time_of_measurement)

            # Create a record for the current row
            record = {
                "Sensor": sensor,
                "Time of Measurement": time_of_measurement,
                "Value of Measurement": value_of_measurement,
                "Unit": unit
            }

            # Add the record to the corresponding sensor group
            if sensor not in sensor_data:
                sensor_data[sensor] = []
            sensor_data[sensor].append(record)

    # Determine the start and stop times
    start_time = min(all_times) if all_times else "Unknown"
    end_time = max(all_times) if all_times else "Unknown"

    # Write data to separate files for each sensor type
    for sensor, records in sensor_data.items():
        file_name = f"{output_folder}/{sensor.lower()}Data.csv"
        with open(file_name, mode='w', newline='') as sensor_file:
            # Write the start and stop times
            sensor_file.write(f"Start Time: {start_time}  End Time: {end_time}\n\n")
            sensor_file.write("Sensor, Time of Measurement, Value of Measurement, Unit\n")

            # Write each record
            for record in records:
                sensor_file.write(f"{record['Sensor']}, {record['Time of Measurement']}, {record['Value of Measurement']}, {record['Unit']}\n")

    print(f"Files saved in the folder: {output_folder}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a CSV file of measurements.")
    parser.add_argument("file_path", help="Path to the CSV file to process")
    args = parser.parse_args()

    if args.file is None:
        file_path = input("Please enter the path to the CSV file: ")
    else:
        file_path = args.fileo

    # Run the script with the specified file
    split_measurements(args.file_path)
