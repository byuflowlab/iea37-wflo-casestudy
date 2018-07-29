import numpy as np
import sys
import yaml                                 # For reading .yaml files
from math import radians as DegToRad        # For converting from degrees to radians
# Written by PJ Stanley, Jared Thomas, and Nicholas F. Baker
# BYU FLOW lab
# Completed 10 June 2018
# Updated 11 Jul 2018 to include read-in of .yaml turb locs and wind freq dist.
# Completed 26 Jul 2018 for commenting and release

def WindFrame(turbineX, turbineY, windDirDeg):
    """ Calculates the locations of each turbine in the frame of reference of the specified wind direction """

    # Convert from meteorological polar system (CW, 0 deg.=N) to standard polar system (CCW, 0 deg.=W)
    windDirDeg = 270. - windDirDeg          # Shift so wind comes "along" x-axis, from left to right.
    if windDirDeg < 0.:                     # If it's left of North (up)
        windDirDeg += 360.                  # Then adjust so we count CW from up.
    windDirRad = DegToRad(windDirDeg)       # Convert inflow wind direction from degrees to radians

    # Convert to downwind(x) & crosswind(y) coordinates
    turbineXw = turbineX*np.cos(-windDirRad)-turbineY*np.sin(-windDirRad)
    turbineYw = turbineX*np.sin(-windDirRad)+turbineY*np.cos(-windDirRad)

    return turbineXw, turbineYw


def GaussianWake(turbineXw, turbineYw):
    """ Returns each turbines total loss from wakes """
    # Equations and values explained in <iea37-wakemodel.pdf>
    nTurbines = len(turbineXw)

    CT = 4.0*1./3.*(1.0-1./3.)  # Constant thrust coefficient
    k = 0.0324555               # Constant turbulence

    D = 130.                    # IEA37 3.35MW onshore reference turbine rotor diameter

    loss = np.zeros(nTurbines)              # Array holding the wake deficit seen at each turbine

    for i in range(nTurbines):              # Looking at the turbines one at a time (Primary)
        loss_array = np.zeros(nTurbines)    # Calculate the loss contribution from all other turbines
        for j in range(nTurbines):          # Looking at all the others (Target)
            x = turbineXw[i]-turbineXw[j]   # Calculate the x-distance
            y = turbineYw[i]-turbineYw[j]   # And the y-offset
            if x > 0.:                      # If the Target turb is downwind of the Primary
                sigma = k*(x)+D/np.sqrt(8.) # Calculate the wake loss using the Simplified Bastankhah Gaussian wake model
                loss_array[j] = (1.-np.sqrt(1.-CT/(8.*sigma**2/D**2)))*np.exp(-0.5*(y/sigma)**2)
            else:                           # If it's upstream
                loss_array[j] = 0.          # No wake effect in this model, count loss as zero
        loss[i] = np.sqrt(np.sum(loss_array**2))  # Total wake losses from all upstream turbines, using sqrt of sum of sqrs

    return loss

def DirPower(turbineX, turbineY, windDirDeg, windSpeed, turbCI, turbCO, turbRtdWS, turbRtdPwr):
    """ Returns the power produced by each turbine for a given wind speed and direction """
    nTurbines = len(turbineX)

    turbineXw, turbineYw = WindFrame(turbineX,turbineY,windDirDeg)  # Shift coordinate frame of reference so wind comes from West
    loss = GaussianWake(turbineXw, turbineYw)                       # Use the Simplified Bastankhah Gaussian wake model to calculate wake deficits

    windSpeedEff = windSpeed*(1.-loss)                              # Effective windspeed is freestream multiplied by the calculated deficits

    pwrTurb = np.zeros(nTurbines)

    #  Calculate the power from each turb based on experienced wind speed & power curve
    for i in range(nTurbines):                                      # Looking at each turbine
        if windSpeedEff[i] <= turbCI:                       # If we're below the cut-in speed
            pwrTurb[i] = 0.                                         # It won't produce power
        elif turbCI < windSpeedEff[i] < turbRtdWS:          # If we're on the curve
            pwrTurb[i] = turbRtdPwr*((windSpeedEff[i]-turbCI)/(turbRtdWS-turbCI))**3    # Calculate the curve speed
        elif turbRtdWS < windSpeedEff[i] < turbCO:          # If we're between rated ws and cut-out
            pwrTurb[i] = turbRtdPwr                                 # Produce rated power
        else:                                               # If we're above the curve (though this scenario doesn't go past cut-out speed)
            pwrTurb[i] = 0                                          # It generates no power

    pwrDir = np.sum(pwrTurb)  # Sum of power from all turbines for this direction

    return pwrDir


def calcAEP(turbineX, turbineY, windFreq, windSpeed, windDir, turbCutInWS, turbCutOutWS, turbRtdWS, turbRtdPwr):
    """ Calculate the wind farm AEP """
    nDirections = len(windFreq)  # Windrose number of bins

    #  Power produced by the wind farm from each wind direction
    PwrProduced = np.zeros(nDirections)
    for i in range(nDirections):                                                    # For each wind bin
        PwrProduced[i] = DirPower(turbineX, turbineY, windDir[i], windSpeed,
                                  turbCutInWS, turbCutOutWS, turbRtdWS, turbRtdPwr) # Find the farm's power for the given direction

    #  Convert power to AEP
    hrsPerYr = 365.*24.
    AEP = hrsPerYr * np.sum(windFreq*PwrProduced)
    AEP /= 1.E6 # Convert to MWh

    return AEP

def getTurbLocYAML(sFileName):
    turbineX = np.array([])
    turbineY = np.array([])

    # Read in the .yaml file
    with open(sFileName, 'r') as f:
        doc = yaml.load(f)

    # rip the x- and y-coordinates
    turbineX = np.asarray(doc['definitions']['position']['items']['xc']) # Convert from <list> to <ndarray>
    turbineY = np.asarray(doc['definitions']['position']['items']['yc'])
    # rip the expected AEP, used for comparison
    # AEP = doc['definitions']['plant_energy']['properties']['annual_energy_production']['default']

    return turbineX, turbineY#, AEP
def getWindRoseYAML(sFileName):
    windFreq = np.array([])

    # Read in the .yaml file
    with open(sFileName, 'r') as f:
        doc = yaml.load(f)

    # rip wind directional bins, their frequency, and the farm windspeed 
    windDir = np.asarray(doc['definitions']['wind_inflow']['properties']['direction']['bins'])         # Convert from <list> to <ndarray>
    windFreq = np.asarray(doc['definitions']['wind_inflow']['properties']['probability']['default'])   # Convert from <list> to <ndarray>
    windSpeed = float(doc['definitions']['wind_inflow']['properties']['speed']['default'])             # Convert from <list> to <float>

    return windDir, windFreq, windSpeed

def getTurbAtrbt(sFileName):
    # Read in the .yaml file
    with open(sFileName, 'r') as f:
        doc = yaml.load(f)

    # rip the turbine attributes
    CutInWS = float(doc['definitions']['operating_mode']['properties']['cut_in_wind_speed']['default']) # Convert from <list> to <ndarray>
    CutOutWS = float(doc['definitions']['operating_mode']['properties']['cut_out_wind_speed']['default']) # Convert from <list> to <float>
    RtdWS = float(doc['definitions']['operating_mode']['properties']['rated_wind_speed']['default']) # Convert from <list> to <float>
    RtdPwr = float(doc['definitions']['wind_turbine_lookup']['properties']['power']['maximum']) # Convert from <list> to <float>

    return CutInWS, CutOutWS, RtdWS, RtdPwr

if __name__ == "__main__":
    """ Used for demonstration """
    turbineX = np.array([])
    turbineY = np.array([])

    # For Python .yaml capability, in the terminal type "pip install pyyaml".
    # An example command line syntax to run this file is "python iea37-aepcalc.py iea37-ex16.yaml iea37-windrose.yaml iea37-335mw.yaml"

    # Read necessary values from .yaml files
    turbineX, turbineY = getTurbLocYAML(sys.argv[1])                # Get turbine locations from .yaml file
    windDir, windFreq, windSpeed = getWindRoseYAML(sys.argv[2])     # Get the array wind sampling bins, frequency at each bin, and wind speed
    turbCutInWS, turbCutOutWS, turbRtdWS, turbRtdPwr = getTurbAtrbt(sys.argv[3])  # Pull from the turbine file

    # Calculate the AEP from ripped values
    AEP = calcAEP(turbineX, turbineY, windFreq, windSpeed, windDir,
                  turbCutInWS, turbCutOutWS, turbRtdWS, turbRtdPwr)
    print AEP                                                       # Print calculated AEP
