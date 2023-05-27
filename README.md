# strava_kikourou_importer
Synchronize activities from Strava to Kikourou

## Requirement
This project use Python3 https://www.python.org/downloads/

## Installation
To install python packages used by this project, run pip command:

`pip3 install -r requirements.txt`

## Configuration
The script need to connect to your Strava and Kikourou accounts.

The accounts configuration have to be on `config.json` file. The file must also contains strava to kikourou activities type translation.

An example of this file with activities type translation exists: `config.example.json`. The easiest way is to copy this file as `config.json` and fill your Strava and Kikourou accounts informations.

### Strava configuration
You don't have to enter your account name or your password. Strava use  OAuth2 authentification protocol that use token.

You have to go to API Strava page (https://www.strava.com/settings/api) to get you client ID and client secret.

You also have to fill the callback address of your application on the bottom of the page with `localhost:5000`

### Kikourou configuration
You just have to enter your kikourou acocunt information (name and password).

## Strava access
On the first strava connection, you have to authorize the script to access to your strava account.

For this, run the script `strava.py`:

`python3 strava.py`

If the application don't have the access to your strava account, it will open a page in your navigator that will ask for the authorisation.

You have to access the read access to your account.

## Synchronization

The following command will synchronized your latest 50 activities from Strava to Kikourou:

`python3 sync_activities.py`

