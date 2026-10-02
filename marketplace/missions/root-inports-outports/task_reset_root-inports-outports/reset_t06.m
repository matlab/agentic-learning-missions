% Ready for Task 06: Inport -> low-pass filter -> Outport.
run('reset_t05.m');

% First-order low-pass Transfer Fcn with a 0.3-second time constant.
tau = 0.3;
add_block("simulink/Continuous/Transfer Fcn", mdl + "/LowPass");
set_param(mdl + "/LowPass", "Numerator", "1");
set_param(mdl + "/LowPass", "Denominator", mat2str([tau 1]));

add_block("simulink/Sinks/Out1", mdl + "/Out1");
add_line(mdl, "In1/1", "LowPass/1");
add_line(mdl, "LowPass/1", "Out1/1");
clear tau
