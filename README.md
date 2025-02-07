# Setup
Download git from git https://git-scm.com/downloads
If you don't have it already, download anaconda here: https://www.anaconda.com/download/success

Run the following commands

```bash
# This installs mamba, which is the exact same as conda but much faster because written in C
conda install mamba

# This downloads the packages for the HSP environment, i.e. downloading all the libraries and stuff
conda env create -n HSP -f environment.yml

# This activates the environment so that you can actually use the stuff you just downloaded
conda activate HSP

# This installs some packages that don't exist in 
python -m pip install -r requirements.txt
```

## Test
To test if everything worked properly, run
```bash
# test dearpy
python test_dearpy.py

# show full daq ui
python daq_ui.py
```

# Saving
These are the steps to save any new packages you may have installed

```bash
# Save new conda env
conda env export --from-history > environment.yml

# Save new pip env
python -m pip freeze > requirements.txt
```

# Troubleshooting
Ensure you activated your environment with 
```bash
conda activate HSP
```

Check to see if the environment is correct. You can see the packages with
```bash
conda env list
```
If the envs are different, sync up the correct environment files, and then redownload.

Ensure you're using `python -m pip...` to do things, not just the pip command. 
Running with python -m makes sure it uses the environment pip, not the local system pip.
