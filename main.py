import requests
from strava import Strava
import json
from kikourou import Kikourou
import datetime
from math import fabs


strava = Strava()
strava.connect()
strava_activities = strava.get_activities()

kikourou = Kikourou()
kikourou.connect()
kik_activities = kikourou.get_activities()

for sa in strava_activities.values():
    #print(sa)

    for ka in kik_activities.values():
        if ka['date'].date() == sa['date'].date() and fabs(ka['distance']-sa['distance'])<1  and ka['duration'] == sa['duration']:
            # print("Find", sa['name'], sa['type'])
            if 'strava_id' in ka:
                raise Exception("Error: a kikourou activity has 2 strava activities")
            ka['strava_id'] = sa['id']
            sa['kikourou_id'] = ka['url']
            break
    else:
        print(">> Find a new activity", sa['name'], sa['date'].date(), sa['distance'], sa['duration'], sa['type'])
        kikourou.add_activity(sa)

