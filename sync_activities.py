from strava import Strava
from kikourou import Kikourou
from math import fabs
import json

with open("config.json", 'r') as hc:
    config = json.load(hc)

kikourou = Kikourou(config["kikourou"])
kikourou.connect()
kik_activities = kikourou.get_activities()

strava = Strava(config["strava"])
if not strava.connect(interract=False):
    raise ("Strava connection error. Need human to help. Run strava.py to authorize the app into strava")
strava_activities = strava.get_activities()

for sa in strava_activities.values():
    for ka in kik_activities.values():

        if ka['comment_private'] == sa['url'] or (ka['date'].date() == sa['date'].date() and
                                                  fabs(ka['distance'] - sa['distance']) < 1 and
                                                  ka['duration'] == sa['duration']):
            # print("Find", sa['name'], sa['type'])
            if 'strava_id' in ka:
                raise Exception("Error: a kikourou activity has 2 strava activities")
            ka['strava_id'] = sa['id']
            sa['kikourou_id'] = ka['url']
            break
    else:
        print(">> Find a new activity", sa['name'], sa['date'].date(), sa['distance'], sa['duration'], sa['type'])
        kikourou.add_activity(sa)
