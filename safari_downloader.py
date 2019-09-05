# A resumable Safari Books Online Video downloader
# Main reference: https://mvdwoord.github.io/tools/2017/02/02/safari-downloader.html

from bs4 import BeautifulSoup
import requests
import os
from subprocess import call, run, PIPE
import unicodedata
import string
import sys
import json

class SafariDownloader:
    def __init__(self, url):
        req = requests.get(url)
        soup = BeautifulSoup(req.text, 'html.parser')

        self.output_folder = soup.find_all('h1')[0].text
        self.output_folder = "".join([c for c in self.output_folder if c.isalpha() or c.isdigit() or c==' ']).rstrip()

        self.topics = soup.find_all('li', class_='toc-level-1') # top-level topic titles

    def validify(self, filename):
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        valid_chars = frozenset(valid_chars)
        # The unicodedata.normalize call replaces accented characters with the unaccented equivalent,
        # which is better than simply stripping them out. After that all disallowed characters are removed.
        cleaned_filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
        return ''.join(c for c in cleaned_filename if c in valid_chars)

    def getCookies(self):
        with open("cookies.txt", 'r') as f:
            lines = f.readlines()

        allCookies = "; ".join(["=".join(line.strip().split('\t')[5:]) for line in lines if not line.startswith('#') and line.strip() != ""])
        return allCookies

    def download(self):
        for topic in self.topics:
            topic_name = topic.a.text
            # Creating folder to put the videos in
            topic_name = "".join([c for c in topic_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            save_folder = '{}/{}'.format(self.output_folder, topic_name)
            os.makedirs(save_folder, exist_ok=True)
            # You can choose to skip these topic_name, comment these three lines if you do not want to skip any
            if topic_name in ('Sponsored'):
                print("Skipping {}...".format(topic_name))
                continue
            for index, video in enumerate(topic.ol.find_all('a')):
                video_name = '{:03d} - {}'.format(index + 1, video.text)
                video_name = self.validify(video_name)
                video_url = video.get('href')

                video_out = '{}/{}.mp4'.format(save_folder, video_name)
                
                # Check if file already exists
                if os.path.isfile(video_out):
                    print("File {} already exists! Skipping...".format(video_out))
                    continue

                print("Downloading {} ...".format(video_name))
                
                result = run(["youtube-dl", "--cookies", "cookies.txt", "-J", "--output", video_out, video_url], stdout=PIPE, stderr=PIPE, universal_newlines=True)

                video_url = json.loads(result.stdout)['url']

                if video_url.startswith("http://cdnapi.kaltura.com/"):
                    oneMinuteVideoResponse = requests.head(video_url, headers={'cookie': self.getCookies()})
                    video_url = oneMinuteVideoResponse.headers['Location']

                if "/clipTo/60000/name/a.mp4" in video_url:
                    video_url = video_url.replace("/clipTo/60000/name/a.mp4", "")
                    call(["wget", video_url, "-O", video_out])
                elif "index.m3u8" in video_url:
                    video_url = video_url.replace("/name/a.mp4/clipTo/60000", "")
                    call(["ffmpeg", "-i", video_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", video_out])

if __name__ == '__main__':
    downloader = SafariDownloader(url=sys.argv[1])
    downloader.download()