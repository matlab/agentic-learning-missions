% Ready for Task 04: inport mapped to respiratoryData at 1 kHz.
run('reset_t03.m');

set_param(mdl, 'LoadExternalInput', 'on');
set_param(mdl, 'ExternalInput', 'respiratoryData');
set_param([mdl '/In1'], 'SampleTime', '0.001');
