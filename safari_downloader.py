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
import re

class SafariDownloader:
    def __init__(self, url):
        req = requests.get(url)
        soup = BeautifulSoup(req.text, 'html.parser')
        # print(soup.prettify())
        # sys.exit(0)

        self.output_folder = soup.find_all('h1')[0].text
        self.output_folder = "".join([c for c in self.output_folder if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        os.makedirs(self.output_folder, exist_ok=True)

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
        topic_count = len(self.topics)

        topic_index = 0
        for topic in self.topics:
            topic_index = topic_index + 1
            topic_name = topic.a.text
            # Creating folder to put the videos in
            topic_name = "".join([c for c in topic_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            if topic_count < 10:
                save_folder = '{}/{:01d} - {}'.format(self.output_folder, topic_index, topic_name)
            elif topic_count < 100:
                save_folder = '{}/{:02d} - {}'.format(self.output_folder, topic_index, topic_name)
            else:
                save_folder = '{}/{:03d} - {}'.format(self.output_folder, topic_index, topic_name)
            os.makedirs(save_folder, exist_ok=True)
            # You can choose to skip these topic_name, comment these three lines if you do not want to skip any
            if topic_name in ('Sponsored'):
                print("Skipping {}...".format(topic_name))
                continue

            if topic.ol:
                video_list = topic.ol.find_all('a')
            else:
                video_list = topic.find_all('a')

            video_list_count = sum(1 for _ in video_list)
            for index, video in enumerate(video_list):
                self.downloadVideo(index, video, save_folder, video_list_count)

    def downloadVideo(self, index, video, save_folder, video_list_count):
        if video_list_count < 10:
            video_name = '{:01d} - {}'.format(index + 1, video.text)
        elif video_list_count < 100:
            video_name = '{:02d} - {}'.format(index + 1, video.text)
        else:
            video_name = '{:03d} - {}'.format(index + 1, video.text)
        video_name = self.validify(video_name)
        video_url = video.get('href')

        print(f"INITIAL VIDEO URL = {video_url}")

        # https://learning.oreilly.com/library/view/design-patterns-in/9781491935828/video226613.html
        # https://learning.oreilly.com/api/v1/videoclips/9781491935828-video226613
        videoUrlParts = video_url.split("/")
        courseId = videoUrlParts[-2]
        videoId = videoUrlParts[-1].replace(".html", "")
        subtitleUrl = f"https://learning.oreilly.com/api/v1/videoclips/{courseId}-{videoId}"
        subtitle_out = '{}/{}.json'.format(save_folder, video_name)
        result = call(["wget", "--load-cookies=cookies.txt", "-O", subtitle_out, subtitleUrl])
        # downloadSubtitle(subtitleUrl)

        video_out = '{}/{}.mp4'.format(save_folder, video_name)
        
        # Check if file already exists
        if os.path.isfile(video_out):
            print("File {} already exists! Skipping...".format(video_out))
            return

        print("Downloading {} ...".format(video_name))
        
        result = run(["youtube-dl", "--cookies", "cookies.txt", "-J", "--output", video_out, video_url], stdout=PIPE, stderr=PIPE, universal_newlines=True)

        video_url = json.loads(result.stdout)['url']
        print(f"INTERMEDIATE VIDEO URL = {video_url}")

        if video_url.startswith("http://cdnapi.kaltura.com/"):
            oneMinuteVideoResponse = requests.head(video_url, headers={'cookie': self.getCookies()})
            video_url = oneMinuteVideoResponse.headers['Location']

        print(f"FINAL VIDEO URL = {video_url}")
        if "/clipTo/" in video_url and "/name/a.mp4" in video_url:
            video_url = re.sub(r'/clipTo/[0-9]+/name/a.mp4', '', video_url)
            # video_url = video_url.replace("/clipTo/60000/name/a.mp4", "")
            call(["wget", video_url, "-O", video_out])
        elif "index.m3u8" in video_url:
            video_url = re.sub(r'/name/a.mp4/clipTo/[0-9]+', '', video_url)
            # video_url = video_url.replace("/name/a.mp4/clipTo/60000", "")
            call(["ffmpeg", "-i", video_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", video_out])

if __name__ == '__main__':
    for url in sys.argv[1:]:
        downloader = SafariDownloader(url=url)
        downloader.download()
