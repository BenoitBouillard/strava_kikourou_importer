import http.server
import socketserver
import argparse
from urllib import parse
from threading import Thread
import webbrowser
import json
import requests
from functools import partial


class RouteHttpServer(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        self.code_callback = kwargs['code_callback']
        kwargs.pop('code_callback')
        super().__init__(*args, **kwargs)

    def do_GET(self):
        print(self.path)
        parsed_path = parse.urlparse(self.path)
        qs = parse.parse_qs(parsed_path.query, keep_blank_values=True)
        print(qs)
        if 'code' in qs:
            self.code_callback(qs['code'][0])
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("URL={}".format(self.path).encode('utf-8'))
        print("shutdown")


AUTH_URI  = "https://www.strava.com/oauth/authorize?client_id={}&response_type=code&redirect_uri=http://localhost:{}&approval_prompt=force&scope=activity:read_all"
TOKEN_URI = "https://www.strava.com/oauth/token"

class Strava(object):
    def __init__(self, config_file="config.json"):
        with open(config_file, 'r') as hc:
            self.config = json.load(hc)
        self.client_id = self.config['strava']['client_id']
        self.callback_port = self.config['strava']['callback_port']
        self.client_secret = self.config['strava']['client_secret']
        self.refresh_token = self.config['strava']['refresh_token']
        self.code = None

        try:
            with open('strava_tokens.json', 'r') as hr:
                self.tokens = json.load(hr)
                print(self.tokens)
        except:
            self.tokens = None

    def set_code(self, value):
        print("==== set_code from callback", value)
        self.code = value

    def strava_authorize_server(self, port):
        self.code = None
        handler_class = partial(RouteHttpServer, code_callback=self.set_code)
        with socketserver.TCPServer(("", port), handler_class) as httpd:
            print("serving at port", port)
            while self.code is None:
                httpd.handle_request()
        if self.code is None:
            raise Exception("No auth code")

    def __refresh_auth_code(self):
        auth_uri = AUTH_URI.format(self.client_id, self.callback_port)
        t1 = Thread(target=self.strava_authorize_server, kwargs={'port': self.callback_port})
        t1.setDaemon(True)
        t1.start()
        webbrowser.open(auth_uri)
        t1.join()
        print("Strava auth code", self.code)

    def __get_token(self):
        print("authorization_code")
        response = requests.post(
            url=TOKEN_URI,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': self.code,
                'grant_type': 'authorization_code'
            }
        )
        self.tokens = response.json()
        print(self.tokens)
        if response.status_code == 400:
            return False
        with open('strava_tokens.json', 'w') as hw:
            json.dump(self.tokens, hw)
        return True

    def __refresh_token(self):
        print("Refresh token")
        response = requests.post(
            url=TOKEN_URI,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token
            }
        )
        # Save json response as a variable
        self.tokens = response.json()
        print(self.tokens)
        if response.status_code == 400:
            return False
        return True

    def connect(self):
        if self.tokens is None:
            self.__refresh_auth_code()
            self.__get_token()

    def headers(self):
        return {"accept": "application/json",
                'authorization': "{} {}".format(self.tokens['token_type'], self.tokens['access_token'])}

    def get_athlete(self):
        response = requests.get("https://www.strava.com/api/v3/athlete", headers=self.headers())
        print(response.json())

    def get_activities(self):
        # curl -X GET "https://www.strava.com/api/v3/athlete/activities?per_page=30" -H "accept: application/json" -H "authorization: Bearer aca99ba556ae884102a34231d4419f8ab0283630"
        params = {'page':1,
                  'per_page':30,
                  }
        response = requests.get("https://www.strava.com/api/v3/athlete/activities", params=params, headers=self.headers())
        return response.json()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Strava api connection')
    args = parser.parse_args()
    strava = Strava()
    strava.connect()

