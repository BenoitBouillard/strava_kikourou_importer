import argparse
import datetime
import json

import requests
from bs4 import BeautifulSoup


class Kikourou(object):
    def __init__(self, config_file="config.json"):
        with open(config_file, 'r') as hc:
            self.config = json.load(hc)
        self.user_id = self.config['kikourou']['user_id']
        self.name = self.config['kikourou']['name']
        self.password = self.config['kikourou']['password']
        self.session = requests.Session()

    @staticmethod
    def headers():
        return {
            'Host': "www.kikourou.net",
            'User-Agent': "Mozilla/5.0",
            "Accept": "text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8",
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
            'Upgrade-Insecure-Requests': "1",
            'Connection': "keep-alive",
            'Content-Type': "application/x-www-form-urlencoded",
        }

    def connect(self):
        r = self.session.post("http://www.kikourou.net/forum/ucp.php?mode=login", headers=self.headers())
        soup = BeautifulSoup(r.text, "html.parser")
        sid = soup.find("input", {"name": "sid"})["value"]

        url = "http://www.kikourou.net/forum/ucp.php?mode=login"
        params = {"mode": "login",
                  "username": self.name,
                  "password": self.password,
                  "sid": sid,
                  "redirect": "./ucp.php?mode=login",
                  "login": "Connection"}
        r = self.session.post(url, data=params, headers=self.headers())
        if not r.text.find("Vous vous êtes connecté avec succès"):
            raise Exception("Not connection to kikourou")

        # r = self.session.get("http://www.kikourou.net")
        print("Connected to kikourou")

    @staticmethod
    def parse_date(date):
        d = date.split("/")
        return datetime.datetime(int(d[2]), int(d[1]), int(d[0]))

    @staticmethod
    def parse_duration(duration):
        seconds = int(duration[-4:-2], 10)
        minutes = int(duration[-7:-5], 10)
        if len(duration) > 8:
            hours = int(duration[0:2], 10)
        else:
            hours = 0
        return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

    @staticmethod
    def parse_elevation(elevation):
        ele = elevation.split(" ")[0]
        if ele == "-":
            return 0
        return int(ele)

    def get_activities(self, limit=50):
        activities = {}

        params = {"nav1an": 1,
                  "kikoureur": self.user_id}
        r = self.session.get("http://www.kikourou.net/profil/")
        soup = BeautifulSoup(r.text, "html.parser")
        cal = soup.find("div", {"id": "ongletentr"})
        for tr in cal.find_all("tr"):
            if tr.find('th') is not None:
                continue
            td = tr.select("td")
            url = td[1].a["href"]
            print("http://www.kikourou.net" + url)
            r_s = self.session.get("http://www.kikourou.net" + url)
            soup_s = BeautifulSoup(r_s.text, "html.parser")

            trs_table = soup_s.find_all('table')[1].find_all('tr')

            activities[url] = {
                'date': self.parse_date(trs_table[1].find_all('td')[1].string),
                'url': url,
                'title': td[1].a.get_text(),
                'kind': trs_table[3].find_all('td')[1].get_text(),
                'duration': self.parse_duration(trs_table[3].find_all('td')[5].get_text()),
                'distance': float(trs_table[1].find_all('td')[-1].get_text().split(" ")[0]),
                'elevation': self.parse_elevation(trs_table[2].find_all('td')[5].get_text()),
                'comment_public': trs_table[-3].get_text().strip(),
                'comment_private': trs_table[-1].td.get_text().strip(),
            }
            # print("Kikourou activity:", td[1].a.get_text())

            if len(activities) >= limit:
                break
        print("Kikourou: find {} activities".format(len(activities)))
        return activities

    @staticmethod
    def sport_from_strava_type(activity):
        if activity['type'] == "Run":
            return 24  # trail
        elif activity['type'] == "Ride":
            return 3  # Vélo
        elif activity['type'] == "Walk":
            return 28  # Marche
        # todo select VTT/Vélo suivant vitesse
        print(">>>>>> Activity type not managed", activity['type'])
        return 21  # autre

    @staticmethod
    def intensite_from_strava(activity):
        if activity['suffer_score'] < 10:
            return 1  # trop facile
        if activity['suffer_score'] < 20:
            return 2  # tres facile
        if activity['suffer_score'] < 40:
            return 3  # facile
        if activity['suffer_score'] < 70:
            return 4  # moyenne
        if activity['suffer_score'] < 110:
            return 5  # assez difficile
        if activity['suffer_score'] < 160:
            return 6  # difficile
        if activity['suffer_score'] < 220:
            return 7  # très difficile
        return 8  # extreme

    def add_activity(self, activity):
        params = {
            'jour': activity['date'].day,
            'mois': activity['date'].month,
            'annee': activity['date'].year,
            'type': 1,  # Continu
            'nom': activity['name'].encode('iso-8859-1', 'replace'),
            'difficulte': 4,  # moyenne
            'lieu': activity['location_country'].encode('iso-8859-1', 'replace'),
            'intensite': self.intensite_from_strava(activity),
            'sport': self.sport_from_strava_type(activity),
            'phase': 0,
            'distance': "{:.3f}".format(activity['distance']),
            'denivele': int(activity['elevation']),
            'heure': int(activity['duration'].total_seconds() / 3600),
            'min': int(activity['duration'].total_seconds() / 60) % 60,
            'sec': int(activity['duration'].total_seconds() % 60),
            'fcmoy': "{:.1f}".format(activity['average_heartrate']) if 'average_heartrate' in activity else "",
            'fcmax': int(activity['max_heartrate']) if 'max_heartrate' in activity else "",
            'descriptionpublique': ("Importé de Strava le " + datetime.datetime.now().isoformat(
                ' ') + " par strava_kikourou_importer").encode('iso-8859-1'),
            'description': "https://www.strava.com/activities/{}".format(activity['id']),
            'details': 0,
            'submit': "Enregistrer",
            "dureesommeil": "0",
            "etape": "3",
            "etatarrivee": "1",
            "etirements": "0",
            "FCmaxj": "180",
            "FCR": "45",
            "forme": "1",
            "meteo": "1",
            "pct1": "100",
            "sommeil": "1",
            "typeterrain1": "1",
            "typeterrain2": "1",
            "typeterrain3": "1",
            "zone1": "122",
            "zone2": "150",
            "zone3": "157",
            "zone4": "166",
            "zone5": "173",
            "zone5sup": "178",
        }
        # print(params)
        r = self.session.post("http://www.kikourou.net/entrainement/ajout.php", params=params, headers=self.headers())
        soup = BeautifulSoup(r.text, "html.parser")
        main_text = soup.find('div', {'id': "contenuprincipal"}).text
        if "Nouvel entrainement enregistré" not in main_text:
            raise Exception("Error saving a new activity")
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Strava api connection')
    args = parser.parse_args()
    kikourou = Kikourou()
    kikourou.connect()
    kikourou.get_activities()
