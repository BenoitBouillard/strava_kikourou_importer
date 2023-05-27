import argparse
import datetime
import http.server
import json
import os
import socketserver
import time
import webbrowser
from functools import partial
from threading import Thread
from urllib import parse

import requests


class StravaAuthServer(http.server.SimpleHTTPRequestHandler):
    """
    OAuth server for callback to get authentification code
    """

    def __init__(self, *args, **kwargs) -> None:
        """
        code_callback argument is added from SimpleHTTPRequestHandler
        """
        self.code_callback = kwargs.pop('code_callback')
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        """
        Manage GET request
        Call code_callback if code and scope are in the url
        """
        parsed_path = parse.urlparse(self.path)
        qs = parse.parse_qs(parsed_path.query, keep_blank_values=True)
        # default answer for debug (should never be the case)
        answer = "URL={}".format(self.path).encode('utf-8')
        if 'code' in qs and 'scope' in qs:
            answer = self.code_callback(qs['code'][0], qs['scope'][0])
        # construct the answer
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(answer)


AUTH_URI = "https://www.strava.com/oauth/authorize?client_id={}&response_type=code&redirect_uri=http://localhost:{}&approval_prompt=force&scope=activity:read_all"
TOKEN_URI = "https://www.strava.com/oauth/token"
TOKEN_FILE = 'strava_tokens.json'


class Strava(object):
    """
    Strava connector

    :param config: dictionary for strava configuration with client_id, callback_port and client_secret values
    """

    def __init__(self, config: dict) -> None:
        self.client_id = config['client_id']
        self.callback_port = config['callback_port']
        self.client_secret = config['client_secret']
        self.code = None
        self.session = requests.Session()

        try:
            with open(TOKEN_FILE, 'r') as hr:
                self.tokens = json.load(hr)
        except:
            self.tokens = None

    def __set_code(self, code: str, scope: str) -> str:
        scopes = scope.split(',')
        if 'activity:read' not in scopes and 'activity:read_all' not in scopes:
            self.code = False
            return "ERREUR: Vous n'avez pas donné accès à vos activités."
        print("==== set_code from callback", code)
        self.code = code
        return "L'accès a vos activités a bien été donné.<br />Vous pouvez fermer cette page."

    def __strava_authorize_server(self, port: int) -> None:
        self.code = None
        handler_class = partial(StravaAuthServer, code_callback=self.__set_code)
        with socketserver.TCPServer(("", port), handler_class) as httpd:
            print("serving at port", port)
            while self.code is None:
                httpd.handle_request()
        if self.code in [None, False]:
            raise Exception("No auth code")

    def __refresh_auth_code(self):
        auth_uri = AUTH_URI.format(self.client_id, self.callback_port)
        t1 = Thread(target=self.__strava_authorize_server, kwargs={'port': self.callback_port})
        t1.setDaemon(True)
        t1.start()
        webbrowser.open(auth_uri)
        t1.join()
        print("Strava auth code", self.code)

    def __get_token(self) -> bool:
        print("authorization_code")
        response = self.session.post(
            url=TOKEN_URI,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': self.code,
                'grant_type': 'authorization_code',
                'scope': "activity:read_all"
            }
        )
        self.tokens = response.json()
        if response.status_code == 400:
            return False
        with open(TOKEN_FILE, 'w') as hw:
            json.dump(self.tokens, hw)
        return True

    def __refresh_token(self) -> bool:
        print("Refresh token")
        response = self.session.post(
            url=TOKEN_URI,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': self.tokens['refresh_token'],
                'scope': "activity:read_all"
            }
        )
        # Save json response as a variable
        self.tokens = response.json()
        print("status_code", response.status_code)
        if response.status_code == 400:
            return False
        with open(TOKEN_FILE, 'w') as hw:
            json.dump(self.tokens, hw)
        return True

    def connect(self, interract: bool = True) -> bool:
        """
        Connect to Strava server

        :param interract: if true and if there is no token, launch the web page to ask for authorisation
        :return: True if connection is done
        """
        if self.tokens is None:
            if interract:
                self.__refresh_auth_code()
                self.__get_token()
            else:
                return False
        if int(time.time()) > self.tokens['expires_at']:
            if not self.__refresh_token():
                # Unable to refresh token: remove local token file
                os.remove(TOKEN_FILE)
                return False
        print("Connected to strava")
        return True

    def __headers(self):
        return {"accept": "application/json",
                'authorization': "{} {}".format(self.tokens['token_type'], self.tokens['access_token'])}

    def get_athlete(self) -> dict:
        """
        Get the athlete information from strava

        :rtype: dict of json according to strava answer: https://developers.strava.com/docs/reference/#api-Athletes-getLoggedInAthlete
        """
        response = self.session.get("https://www.strava.com/api/v3/athlete", headers=self.__headers())
        return response.json()

    def get_activities(self, after: int = None) -> list:
        """
        Return the list of athlete activities (see https://developers.strava.com/docs/reference/#api-Activities-getLoggedInAthleteActivities)
        Add fields:
        - date: datetime of start_date_local
        - duration: datetime of elapsed_time
        - distance: distance in kilometer
        - elevation: same as total_elevation_gain
        - url: strava url of the activity

        :param after: optional epoch timestamp to use for filtering activities that have taken place after a certain time.
        :return: list of activities
        """
        params = {'page': 1, 'per_page': 30}
        if after:
            params['after'] = after
        response = self.session.get("https://www.strava.com/api/v3/athlete/activities", params=params,
                                    headers=self.__headers())
        if response.status_code != 200:
            print(response.json())
            return None
        r = response.json()
        activities = []
        for ac in r:
            ac['date'] = datetime.datetime.fromisoformat(ac['start_date_local'][:-1])
            ac['duration'] = datetime.timedelta(seconds=ac['elapsed_time'])
            ac['distance'] = ac['distance'] / 1000
            ac['elevation'] = ac['total_elevation_gain']
            ac['url'] = "https://www.strava.com/activities/{}".format(ac['id'])
            activities.append(ac)
        print("Strava: find {} activities".format(len(activities)))
        return activities


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Strava api connection')
    parse_args = parser.parse_args()
    with open("config.json", 'r') as hc:
        config = json.load(hc)
    strava = Strava(config["strava"])
    if strava.connect():
        print(len(strava.get_activities()))
