import pandas as pd
import numpy as np
import os

from load_files import *

SAMPLE_RATE = 8

def findPeaks(data, offset, start_WT, end_WT, thres=0, sampleRate=SAMPLE_RATE):
	'''
		This function finds the peaks of an EDA signal and returns basic properties.
		Also, peak_end is assumed to be no later than the start of the next peak. (Is this okay??)

		********* INPUTS **********
		data:        DataFrame with EDA as one of the columns and indexed by a datetimeIndex
		offset:      the number of rising samples and falling samples after a peak needed to be counted as a peak
		start_WT:    maximum number of seconds before the apex of a peak that is the "start" of the peak
		end_WT:      maximum number of seconds after the apex of a peak that is the "rec.t/2" of the peak, 50% of amp
		thres:       the minimum uS change required to register as a peak, defaults as 0 (i.e. all peaks count)
		sampleRate:  number of samples per second, default=8

		********* OUTPUTS **********
		peaks:               list of binary, 1 if apex of SCR
		peak_start:          list of binary, 1 if start of SCR
		peak_start_times:    list of strings, if this index is the apex of an SCR, it contains datetime of start of peak
		peak_end:            list of binary, 1 if rec.t/2 of SCR
		peak_end_times:      list of strings, if this index is the apex of an SCR, it contains datetime of rec.t/2
		amplitude:           list of floats,  value of EDA at apex - value of EDA at start
		max_deriv:           list of floats, max derivative within 1 second of apex of SCR

	'''
	EDA_deriv = data['filtered_eda'][1:].as_matrix() - data['filtered_eda'][:-1].as_matrix()
	peaks = np.zeros(len(EDA_deriv))
	peak_sign = np.sign(EDA_deriv)
	for i in range(int(offset), int(len(EDA_deriv) - offset)):
		if peak_sign[i] == 1 and peak_sign[i + 1] < 1:
			peaks[i] = 1
			for j in range(1, int(offset)):
				if peak_sign[i - j] < 1 or peak_sign[i + j] > -1:
					#if peak_sign[i-j]==-1 or peak_sign[i+j]==1:
					peaks[i] = 0
					break

	# Finding start of peaks
	peak_start = np.zeros(len(EDA_deriv))
	peak_start_times = [''] * len(data)
	max_deriv = np.zeros(len(data))
	rise_time = np.zeros(len(data))

	for i in range(0, len(peaks)):
		if peaks[i] == 1:
			temp_start = max(0, i - sampleRate)
			max_deriv[i] = max(EDA_deriv[temp_start:i])
			start_deriv = .01 * max_deriv[i]

			found = False
			find_start = i
			# has to peak within start_WT seconds
			while found == False and find_start > (i - start_WT * sampleRate):
				if EDA_deriv[find_start] < start_deriv:
					found = True
					peak_start[find_start] = 1
					peak_start_times[i] = data.index[find_start]
					rise_time[i] = get_seconds_and_microseconds(data.index[i] - pd.to_datetime(peak_start_times[i]))

				find_start = find_start - 1

			# If we didn't find a start
			if found == False:
				peak_start[i - start_WT * sampleRate] = 1
				peak_start_times[i] = data.index[i - start_WT * sampleRate]
				rise_time[i] = start_WT

			# Check if amplitude is too small
			if thres > 0 and (data['EDA'].iloc[i] - data['EDA'][peak_start_times[i]]) < thres:
				peaks[i] = 0
				peak_start[i] = 0
				peak_start_times[i] = ''
				max_deriv[i] = 0
				rise_time[i] = 0

	# Finding the end of the peak, amplitude of peak
	peak_end = np.zeros(len(data))
	peak_end_times = [''] * len(data)
	amplitude = np.zeros(len(data))
	decay_time = np.zeros(len(data))
	half_rise = [''] * len(data)
	SCR_width = np.zeros(len(data))

	for i in range(0, len(peaks)):
		if peaks[i] == 1:
			peak_amp = data['EDA'].iloc[i]
			start_amp = data['EDA'][peak_start_times[i]]
			amplitude[i] = peak_amp - start_amp

			half_amp = amplitude[i] * .5 + start_amp

			found = False
			find_end = i
			# has to decay within end_WT seconds
			while found == False and find_end < (i + end_WT * sampleRate) and find_end < len(peaks):
				if data['EDA'].iloc[find_end] < half_amp:
					found = True
					peak_end[find_end] = 1
					peak_end_times[i] = data.index[find_end]
					decay_time[i] = get_seconds_and_microseconds(pd.to_datetime(peak_end_times[i]) - data.index[i])

					# Find width
					find_rise = i
					found_rise = False
					while found_rise == False:
						if data['EDA'].iloc[find_rise] < half_amp:
							found_rise = True
							half_rise[i] = data.index[find_rise]
							SCR_width[i] = get_seconds_and_microseconds(pd.to_datetime(peak_end_times[i]) - data.index[find_rise])
						find_rise = find_rise - 1

				elif peak_start[find_end] == 1:
					found = True
					peak_end[find_end] = 1
					peak_end_times[i] = data.index[find_end]
				find_end = find_end + 1

			# If we didn't find an end
			if found == False:
				min_index = np.argmin(data['EDA'].iloc[i:(i + end_WT * sampleRate)].tolist())
				peak_end[i + min_index] = 1
				peak_end_times[i] = data.index[i + min_index]

	peaks = np.concatenate((peaks, np.array([0])))
	peak_start = np.concatenate((peak_start, np.array([0])))
	max_deriv = max_deriv * sampleRate  # now in change in amplitude over change in time form (uS/second)

	return peaks, peak_start, peak_start_times, peak_end, peak_end_times, amplitude, max_deriv, rise_time, decay_time, SCR_width, half_rise

def get_seconds_and_microseconds(pandas_time):
	return pandas_time.seconds + pandas_time.microseconds * 1e-6

def calcPeakFeatures(data,outfile,offset,thresh,start_WT,end_WT):
	returnedPeakData = findPeaks(data, offset*SAMPLE_RATE, start_WT, end_WT, thresh, SAMPLE_RATE)
	data['peaks'] = returnedPeakData[0]
	data['peak_start'] = returnedPeakData[1]
	data['peak_end'] = returnedPeakData[3]

	data['peak_start_times'] = returnedPeakData[2]
	data['peak_end_times'] = returnedPeakData[4]
	data['half_rise'] = returnedPeakData[10]
	# Note: If an SCR doesn't decrease to 50% of amplitude, then the peak_end = min(the next peak's start, 15 seconds after peak)
	data['amp'] = returnedPeakData[5]
	data['max_deriv'] = returnedPeakData[6]
	data['rise_time'] = returnedPeakData[7]
	data['decay_time'] = returnedPeakData[8]
	data['SCR_width'] = returnedPeakData[9]

	featureData = data[data.peaks==1][['EDA','rise_time','max_deriv','amp','decay_time','SCR_width']]

	# Replace 0s with NaN, this is where the 50% of the peak was not found, too close to the next peak
	featureData[['SCR_width','decay_time']]=featureData[['SCR_width','decay_time']].replace(0, np.nan)
	featureData['AUC']=featureData['amp']*featureData['SCR_width']

	featureData.to_csv(outfile)

def chooseValueOrDefault(str_input, default):
	if str_input == "":
		return default
	else:
		return float(str_input)

if __name__ == "__main__":

	print "Please enter information about your EDA file... "
	dataType = raw_input("\tData Type (e4 or q or misc): ")
	if dataType=='q':
		filepath = raw_input("\tFile path: ")
		filepath_confirm = filepath
		data = loadData_Qsensor(filepath)
	elif dataType=='e4':
		filepath = raw_input("\tPath to E4 directory: ")
		filepath_confirm = os.path.join(filepath,"EDA.csv")
		data = loadData_E4(filepath)
	elif dataType=="misc":
		filepath = raw_input("\tFile path: ")
		filepath_confirm = filepath
		data = loadData_misc(filepath)
	else:
		print "Error: not a valid file choice"
	     
	print ""
	print "Where would you like to save the computed peak feature file?"
	outfile = raw_input('\tFile name: ')
	outputPath = raw_input('\tFile directory (./ for this directory): ')
	fullOutputPath = os.path.join(outputPath,outfile)
	if fullOutputPath[-4:] != '.csv':
		fullOutputPath = fullOutputPath+'.csv'

	print ""
	print "Please choose settings for the peak detection algorithm. For default values press return"
	thresh_str = raw_input('\tMinimum peak amplitude (default = .02):')
	thresh = chooseValueOrDefault(thresh_str,.02)
	offset_str = raw_input('\tOffset (default = 1): ')
	offset = chooseValueOrDefault(offset_str,1)
	start_WT_str = raw_input('\tMax rise time (s) (default = 4): ')
	start_WT = chooseValueOrDefault(start_WT_str,4)
	end_WT_str = raw_input('\tMax decay time (s) (default = 4): ')
	end_WT = chooseValueOrDefault(end_WT_str,4)

	print ""
	print "Okay, finding peaks in file", filepath_confirm, "using threshold =", thresh, "offset =", offset, "rise time =", start_WT, "decay time=", end_WT
	calcPeakFeatures(data,fullOutputPath,offset,thresh,start_WT,end_WT)
	print "Features computed and saved to "+ fullOutputPath

	# Plotting the data

	print '--------------------------------'
	print "Please also cite this project:"
	print "Taylor, S., Jaques, N., Chen, W., Fedor, S., Sano, A., & Picard, R. Automatic identification of artifacts in electrodermal activity data. In Engineering in Medicine and Biology Conference. 2015"
	print '--------------------------------'

