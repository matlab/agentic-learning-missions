% Ready for Task 05: Scope connected to Inport, model has been run.
run('reset_t04.m');

add_block('simulink/Sinks/Scope', [mdl '/Scope']);
add_line(mdl, 'In1/1', 'Scope/1');
out = sim(mdl);
