import requests
from strava import Strava
import json


strava = Strava()
strava.connect()
strava.get_athlete()

for ac in strava.get_activities():
    print(ac)
