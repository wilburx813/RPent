Cell: suite={suite}  task={task}  seed={seed}  MODE=PERCEPTION-ISOLATED.

The env server is already running with --hide_object_coords. Its output
directory is {output_dir}. states.json (with step 0 entry) +
images/image_00.png + images_cam/image_cam_00.png + depths/depth_00.npy +
camera_meta.json are ready. Run `mcp_list_dir` to confirm.

You do NOT have GT object world coordinates. You must localize objects
via images_cam + depth + camera_meta + back_project (see the MODE section
at the top of your system prompt).

Goal: make state.libero_terminated == True via a strict_perception hybrid run.

Save artifacts to: {output_dir}
- recipe filename: recipe_{recipe_tag}.jsonl
- audit  filename: {recipe_tag}.json

Suggested first steps:
1. read_text_file("logs/memory/MEMORY.md")
2. read_text_file("physical_agent/context/guides/STRICT_HYBRID_GUIDE.md")
3. read_text_file("physical_agent/context/guides/PRO_HYBRID_GUIDE.md")
4. view_camera_meta() — get the calibration matrices
5. view_driver_state(step=0) — see the initial scene (both images!)
6. Look at images_cam/image_cam_00.png; find the target object; back_project() its pixels
7. Plan; then call the primitive tools (move_to / pi0_pick / release /
   set_gripper / rotate_wrist / rotate_pitch / move_pose) repeatedly
   until libero_terminated=True
8. write_text_file the recipe + audit; finish(success)
