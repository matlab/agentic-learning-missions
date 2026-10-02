% Ready for Task 03: model open with a root Inport block.
run('reset_t02.m');

mdl = 'mission01';
new_system(mdl);
open_system(mdl);
add_block('simulink/Sources/In1', [mdl '/In1']);
