import subprocess

subprocess.run(["python", "step0_reproject.py"])
subprocess.run(["python", "step1_draw_Centerlines.py"])
subprocess.run(["python", "step2_construct_graph.py"])