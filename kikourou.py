import argparse
import datetime
import json
import re
import time

import requests
from bs4 import BeautifulSoup


class Kikourou(object):
    """
    Kikourou connector
    """
    def __init__(self, config: dict) -> object:
        """

        :param config: dictionary for kikourou connection with name and password values, and strava_to_kikourou for actovity type conversion
        """
        self.user_id = None
        self.name = config['name']
        self.password = config['password']
        self.config = config
        self.session = requests.Session()

    @staticmethod
    def __headers() -> dict:
        """
        Construct header for kikourou request

        :return: header for request
        """
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

    def connect(self) -> None:
        """
        Open session with kikourou server and login
        """
        r = self.session.post("http://www.kikourou.net/forum/ucp.php?mode=login", headers=self.__headers())
        soup = BeautifulSoup(r.text, "html.parser")
        sid = soup.find("input", {"name": "sid"})["value"]
        print("sid", self.sid)

        url = "http://www.kikourou.net/forum/ucp.php?mode=login"
        params = {"mode": "login",
                  "username": self.name,
                  "password": self.password,
                  "sid": sid,
                  "redirect": "./ucp.php?mode=login",
                  "login": "Connection"}
        r = self.session.post(url, data=params, headers=self.__headers())
        if not r.text.find("Vous vous êtes connecté avec succès"):
            raise Exception("Not connection to kikourou")

        r = self.session.get("http://www.kikourou.net", headers=self.__headers())
        re_id = re.findall('idsportif=([0-9]+)"', r.text)
        if re_id:
            self.user_id = re_id[0]
            print("idsportif is", self.user_id)
        else:
            raise Exception("Kikourou idsportif not found")
        print("Connected to kikourou")

    @staticmethod
    def __parse_date(date: str) -> datetime.datetime:
        """
        Convert kikourou date to datetime
        """
        d = date.split("/")
        return datetime.datetime(int(d[2]), int(d[1]), int(d[0]))

    @staticmethod
    def __parse_duration(duration: str) -> datetime.timedelta:
        """
        Convert a kikourou duration into timedelta
        """
        seconds = int(duration[-4:-2], 10)
        if len(duration) > 4:
            minutes = int(duration[-7:-5], 10)
        else:
            minutes = 0
        if len(duration) > 8:
            hours = int(duration[0:2], 10)
        else:
            hours = 0
        return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

    @staticmethod
    def __parse_elevation(elevation: str) -> int:
        """
        Convert a kikourou elevation to int
        """
        ele = elevation.split(" ")[0]
        if ele == "-":
            return 0
        return int(ele)

    def get_activities(self, limit: int = 50) -> list:
        """
        Get kikourou activities

        :param limit: number of activities to get (50 by default)
        :return: list of activities
        """
        activities = []

        params = {"nav1an": 1,
                  "kikoureur": self.user_id}
        r = self.session.get("http://www.kikourou.net/entrainement/navigation.php", params=params)
        soup = BeautifulSoup(r.text, "html.parser")
        cal = soup.find("table", class_="calendrier")
        for tr in cal.find_all("tr"):
            if tr.find('th') is not None:
                continue
            td = tr.select("td")
            url = td[1].a["href"]
            r_s = self.session.get("http://www.kikourou.net/entrainement/"+url)
            soup_s = BeautifulSoup(r_s.text, "html.parser")

            trs_table = soup_s.find(id="contenuprincipal").find('table').find_all('tr')

            activities.append({
                'date': self.__parse_date(trs_table[1].find_all('td')[1].string),
                'url': url,
                'title': td[1].a.get_text(),
                'kind': trs_table[3].find_all('td')[1].get_text(),
                'duration': self.__parse_duration(trs_table[3].find_all('td')[5].get_text()),
                'distance': float(trs_table[1].find_all('td')[-1].get_text().split(" ")[0]),
                'elevation': self.__parse_elevation(trs_table[2].find_all('td')[5].get_text()),
                'comment_public': trs_table[-3].get_text().strip(),
                'comment_private': trs_table[-1].td.get_text().strip(),
            })

            if len(activities) >= limit:
                break
        print("Kikourou: find {} activities".format(len(activities)))
        return activities

    @staticmethod
    def __intensite_from_strava(activity: dict) -> int:
        """
        Define the intensite of the activity from strava activity data

        :param activity: strava actovity
        :return: intensite
        """
        suffer_score = activity.get('suffer_score', 0)
        if suffer_score < 10:
            return 1  # trop facile
        if suffer_score < 20:
            return 2  # tres facile
        if suffer_score < 40:
            return 3  # facile
        if suffer_score < 70:
            return 4  # moyenne
        if suffer_score < 110:
            return 5  # assez difficile
        if suffer_score < 160:
            return 6  # difficile
        if suffer_score < 220:
            return 7  # très difficile
        return 8  # extreme

    def add_activity(self, activity: dict) -> bool:
        """
        Add the strava activity to kikourou training log
        :param activity: strava activity
        :return: true if no error !
        """
        if activity['type'] not in self.config["strava_to_kikourou"]['sport']:
            print("!!! Activity type {} is not managed. Use 'autre' !!!", format(activity['type']))
        sport = self.config["strava_to_kikourou"]['sport'].get(activity['type'], 21)

        params = {
            'jour': activity['date'].day,
            'mois': activity['date'].month,
            'annee': activity['date'].year,
            'type': 1,  # Continu
            'nom': activity['name'].encode('iso-8859-1', 'replace'),
            'difficulte': 4,  # moyenne
            'lieu': activity['location_country'].encode('iso-8859-1', 'replace'),
            'intensite': self.__intensite_from_strava(activity),
            'sport': sport,
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
            'description': activity['url'],
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
        r = self.session.post("http://www.kikourou.net/entrainement/ajout.php", params=params, headers=self.__headers())
        soup = BeautifulSoup(r.text, "html.parser")
        main_text = soup.find('div', {'id': "contenuprincipal"}).text
        if "Nouvel entrainement enregistré" not in main_text:
            raise Exception("Error saving a new activity")
        return True

    def search_userid(self, user_name):
        params = {"username": user_name,
                  "kikoureur": self.user_id}
        r = self.session.get("http://www.kikourou.net/forum/memberlist.php?form=postform&field=username_list&select_single=&mode=searchuser", params=params)
        re_id = re.findall('mode=viewprofile&amp;u=([0-9]+)"', r.text)
        if re_id:
            user_id = re_id[0]
            print(f"user_id of {user_name} is {user_id}")
            return user_id
        print("Not found for {user_name}")
        return None

    def send_message(self, to, subject, message):
        r = self.session.get("http://www.kikourou.net/forum/ucp.php?i=pm&mode=compose")
        soup = BeautifulSoup(r.text, "html.parser")
        form = soup.find("form", {"id":"postform"} )
        form_action = form.attrs['action']
        hidden = {}
        for input in form.find_all("input", {'type': "hidden"}):
            hidden[input.attrs['name']] = input.attrs['value']

        params = {
            f"address_list[u][{to}]": "to",
            "subject": subject,
            "message": message,
            "username_list": "",
            "icon": 8,
            "addbbcode20": 100,
            "post": "Envoyer",
            "attach_sig": "on",
            "filecomment": "",
        }
        params.update(hidden)

        req = requests.Request("POST", f"http://www.kikourou.net/forum/{form_action}", data=params, files=dict())
        preq = self.session.prepare_request(req)
        r = self.session.send(preq)
        if r.text.find("Le message a été envoyé avec succès.")>=0:
            return True
        return False



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Strava api connection')
    args = parser.parse_args()
    with open("config.json", 'r') as hc:
        config = json.load(hc)
    kikourou = Kikourou(config["kikourou"])
    kikourou.connect()
    id = kikourou.search_userid("BouBou27")
    kikourou.send_message(id, "test 2", "msg 2")
    # kikourou.get_activities()


