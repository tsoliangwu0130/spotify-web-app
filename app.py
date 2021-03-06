import json
import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, redirect, render_template, request, url_for
from urllib.parse import quote_plus, urlencode

app = Flask(__name__)

CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']
REDIRECT_URI = os.environ['REDIRECT_URI']
PORT = 5000
SCOPE = 'user-read-currently-playing user-read-playback-state'
ACCESS_TOKEN = ''
REFRESH_TOKEN = ''

SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_BASE_URL = 'https://api.spotify.com/v1'
SPOTIFY_API_USER_PROFILE_ENDPOINT = SPOTIFY_API_BASE_URL + '/me'
SPOTIFY_API_CURRENT_PLAYBACK_ENDPOINT = SPOTIFY_API_USER_PROFILE_ENDPOINT + '/player'

GOOGLE_SEARCH_URL = 'https://www.google.com/search'

IMAGE_NOT_FOUND_URL = 'https://cdn.browshot.com/static/images/not-found.png'


def request_token(token_payload):
    token_result = requests.post(
        SPOTIFY_TOKEN_URL,
        data=token_payload,
        auth=(CLIENT_ID, CLIENT_SECRET)
    )
    token_data = json.loads(token_result.text)
    return token_data


def fetch_news(artists):
    fetched_news = []
    for artist in artists:
        search_payload = {
            'q': artist['name'],
            'tbm': 'nws'
        }
        res_html = requests.get(url=GOOGLE_SEARCH_URL, params=search_payload)
        soup = BeautifulSoup(res_html.text, 'html.parser')
        news = soup.find('div', {'id': 'ires'}).find_all('div', {'class': 'g'})

        for item in news:
            title = item.find('h3').text
            url = re.findall(r'(http.+?)&', item.find('a')['href'])[0]
            img_src = item.find('img', {'class': 'th'})
            preview_content = item.find('div', {'class': 'st'}).text
            fetched_news.append({
                'title': title,
                'url': url,
                'img_src': img_src['src'] if img_src else IMAGE_NOT_FOUND_URL,
                'preview_content': preview_content
            })
    return fetched_news


@app.route('/')
def index():
    global ACCESS_TOKEN

    # Request access token and refresh token while first login
    if not ACCESS_TOKEN and not REFRESH_TOKEN:
        return redirect(url_for('login'))

    headers = {'Authorization': '{} {}'.format('Bearer', ACCESS_TOKEN)}
    status_code = requests.get(SPOTIFY_API_BASE_URL, headers=headers).status_code

    # Refresh token while current access token is expired
    if status_code == 401 and REFRESH_TOKEN:
        token_payload = {
            'grant_type': 'refresh_token',
            'refresh_token': REFRESH_TOKEN
        }
        print('* Access token is expired. Requesting a new token...')
        token_data = request_token(token_payload)
        ACCESS_TOKEN = token_data['access_token']
        headers = {'Authorization': '{} {}'.format('Bearer', ACCESS_TOKEN)}

    profile_res = requests.get(SPOTIFY_API_USER_PROFILE_ENDPOINT, headers=headers)
    cur_playback_res = requests.get(SPOTIFY_API_CURRENT_PLAYBACK_ENDPOINT, headers=headers)

    profile_data = json.loads(profile_res.text)
    cur_playback_data = json.loads(cur_playback_res.text)

    artists = cur_playback_data['item']['artists']
    fetched_news = fetch_news(artists)
    return render_template(
        'index.html',
        profile=profile_data,
        cur_playback=cur_playback_data,
        fetched_news=fetched_news
    )


@app.route('/login')
def login():
    auth_payload = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE
    }
    encoded_auth_url = '{}/?{}'.format(
        SPOTIFY_AUTH_URL,
        urlencode(auth_payload, quote_via=quote_plus)
    )
    return redirect(encoded_auth_url)


@app.route('/callback')
def callback():
    global ACCESS_TOKEN, REFRESH_TOKEN

    token_payload = {
        'grant_type': 'authorization_code',
        'code': request.args['code'],
        'redirect_uri': REDIRECT_URI
    }
    token_data = request_token(token_payload)
    REFRESH_TOKEN = token_data['refresh_token']
    ACCESS_TOKEN = token_data['access_token']

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
