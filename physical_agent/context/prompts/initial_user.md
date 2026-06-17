Cell: suite={suite}  task={task}  seed={seed}.

The env server is already running. Its output directory is {output_dir}
(this is also the default for mcp_list_dir / view_driver_state and every
primitive tool — move_to, pi0_pick, release, ...). states.json (with
step 0 entry) + images/image_00.png are ready. Run `mcp_list_dir` to
confirm.

Goal: make state.libero_terminated == True via a strict-regime hybrid run
(Pi0 only for the pick via track_obj cut; LLM scripts every move + release).

Save artifacts to: {output_dir}
- recipe filename: recipe_{recipe_tag}.jsonl
- audit  filename: {recipe_tag}.json

Suggested first steps:
1. read_text_file("logs/memory/MEMORY.md")
   — the index of operating wisdom. Scan ALL lines, then read the
   ~3-5 individual feedback_*.md files (in the same dir) that look
   most relevant to your suite (e.g. for libero_spatial bowl tasks,
   definitely read feedback_bowl_eef_y_offset.md).
2. read_text_file("physical_agent/context/guides/STRICT_HYBRID_GUIDE.md")
3. read_text_file("physical_agent/context/guides/PRO_HYBRID_GUIDE.md")
4. (optional) list_dir on the appropriate workspace_pro/results_*_pert/
   then read a past recipe_<sim>.jsonl as a starting point — BUT
   re-derive coords from states.json[0] and apply memory offsets, don't
   blindly copy.
5. view_driver_state(step=0)  — see initial scene
6. plan; then call the primitive tools (move_to / pi0_pick / release /
   set_gripper / rotate_wrist / rotate_pitch / move_pose) repeatedly
   until libero_terminated=True
7. write_text_file the recipe + audit; finish(success)
