# NostalgiaGhosts
A minecraft datapack generator to view the last positions of all the players on your old world save. An image of once was...

## Install
- Install python 3, ideally 3.12+. You can make a venv if you like, or just run from global, your choice.
- run `pip install nbtlib` in your terminal
- Place dat_to_ghosts.py in the world save folder
- In a terminal (with venv active), run `python dat_to_ghosts.py`. This will take a moment and generate a `nostalgia_ghosts` folder inside the world datapacks.
- You're good to go! Feel free to open up the world save.

- NOTE: You will need to run this script for every world you want to use.
- NOTE: Only tested on vanilla worlds, I will be testing on modded worlds soon.


## How to use

- Load into world, make sure you have cheats enabled. (If you don't, just do ESC > Open To Lan > Allow Cheats: On > Start LAN World)
- If you didn't have cheats enabled when the world was opened, you will need to run `/function ghosts:spawn_all`
- Right clicking on the carrot on a stick will teleport you to the next player.
- See other commands using /function ghosts:xyz. You only really need `despawm_all`, `spawn_all` and `teleport_next`/`teleport_prev`. Everything else is used as part of those functions.