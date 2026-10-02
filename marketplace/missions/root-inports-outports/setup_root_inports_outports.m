% Setup for Mission 01: Root Inports and Outports
%
% Context: Respiratory signal from a chest impedance sensor on a patient
% monitor. The raw signal is corrupted by 60 Hz powerline interference
% and high-frequency EMG artifact from intercostal muscle activity.
% Goal: Filter out the noise and recover the clean breathing waveform.

%% Generate signal

% Time vector: 10 seconds at 1 kHz (typical medical device sample rate)
Fs = 1000;
t = (0:1/Fs:10)';

% Desired signal: quiet breathing at ~0.25 Hz (15 breaths/min)
% Second harmonic adds slight asymmetry (inhale vs exhale duration)
breathingRate = 0.25;
respiratory = 0.5*sin(2*pi*breathingRate*t) + 0.1*sin(2*pi*2*breathingRate*t);

% Noise 1: 60 Hz powerline interference (US clinical environment)
powerline = 0.3*sin(2*pi*60*t);

% Noise 2: EMG artifact from intercostal muscles (120 + 180 Hz components)
emg = 0.15*sin(2*pi*120*t + pi/4) + 0.1*sin(2*pi*180*t);

% Combined noisy signal
noisySignal = respiratory + powerline + emg;

%% Package for Simulink

% Timeseries object — ready to map directly to a root inport
respiratoryData = timeseries(noisySignal, t, "Name", "RespiratoryData");

%% Clean up internal variables

clear respiratory powerline emg breathingRate Fs t noisySignal

