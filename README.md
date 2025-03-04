

# Setup

## Prerequisites
- **Git:** Download and install Git from [Git Downloads](https://git-scm.com/downloads).
- **Miniconda:**  
  - Download Miniconda from the [official page](https://docs.conda.io/en/latest/miniconda.html).  
  - **Note:** There's no need to install Python separately.
  - **Important:** During Miniconda installation, ensure you check the option to "register as default python."

## Initial Terminal Setup
1. **Close** your current terminal.
2. Open the **Anaconda Powershell Prompt**.
3. Type and run:
   ```bash
   conda init bash
   ```
4. Next, open **Git Bash** and navigate to your repository.

## Environment Setup

Run the following commands in Git Bash:

```bash
# Create the conda environment (HSP) from environment.yml
conda env create -n HSP -f environment.yml

# Activate the environment
conda activate HSP

# Install pip requirements
python -m pip install -r requirements.txt
```

## LJM Software Installation
Install the LJM Software by downloading the installer from:
[LabJack Minimal LJM Installers](https://support.labjack.com/docs/minimal-ljm-installers)

## Troubleshooting GUI Issues
If you encounter errors with the simple GUI, try installing the following packages:

```bash
pip install --upgrade rsa
pip install PySimpleGUI -i https://pysimplegui.net/install
```

*You may use the free trial if applicable.*

---

# Test

To verify that everything is working correctly, run:

```bash
# Test dearpy
python test_dearpy.py

# Show full DAQ UI
python daq_ui.py
```

---

# Saving

After installing any new packages, update your environment files:

```bash
# Update the conda environment file (environment.yml)
conda env export --from-history > environment.yml

# Update the pip requirements file (requirements.txt)
python -m pip freeze > requirements.txt
```

---

# Troubleshooting

- **Ensure you activate the correct environment:**
  ```bash
  conda activate HSP
  ```
- **Check your environments:**
  ```bash
  conda env list
  ```
  If you see different environments, sync the correct environment files and then re-download.
- **Tip:** Always use `python -m pip ...` to ensure you are using the pip version tied to your active environment, not the system pip.

--- 
