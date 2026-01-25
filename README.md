# NostalgiaGhosts
A minecraft datapack to view the last positions of all the players on your old world save. An image of once was...

## Install
- Install python 3, ideally 3.12+. You can make a venv if you like, or just run from global, your choice.
- run `pip install nbtlib` in your terminal
- Place dat_to_ghosts in the world save folder
- In a terminal, run `python dat_to_ghosts.py`. This will take a moment and generate a `nostalgia_ghosts` folder.
- Shove the `nostalgia_ghosts` folder in `datapacks` and you're good to go!

- NOTE: You will need to run this script for every world you want to use.


## How to use

- Load into world, make sure you have cheats enabled. (If you don't, just do ESC > Open To Lan > Allow Cheats: On > Start LAN World)
- Right clicking on the carrot on a stick will teleport you to the next player.
- See other commands using /function ghosts:xyz. You only really need `despawm_all`, `spawn_all` and `teleport_next`/`teleport_prev`. Everything else is used as part of those functions.