% Ready for Task 07: output logging enabled, model run, filtered data in workspace.
run('reset_t06.m');

set_param(mdl, 'SaveOutput', 'on');
set_param(mdl, 'OutputSaveName', 'yout');
out = sim(mdl);
