# workingtitle

A chat app written in Python 3.

## Setup

- Create a venv: `python -m venv venv`
- Activate the venv: `source venv/bin/activate`
- Install requirements `pip install -r ./requirements.txt`
- Copy the config template: `cp config.py.example config.py`
- Edit the config:`$EDITOR config.py`
- Initialize the database: `QUART_APP=main:app quart init_db`
- Run the server: `python main.py`
