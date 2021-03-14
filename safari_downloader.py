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
    def __init__(self, course_url):
        self.course_url = course_url
        self.course_id = course_url.split('/')[-1]

        req = requests.get(course_url)
        soup = BeautifulSoup(req.text, 'html.parser')
        # print(soup)
        # sys.exit(0)

        self.output_folder = soup.find_all('h1')[0].text
        self.output_folder = "".join([c for c in self.output_folder if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        print(self.output_folder)

        if '/videos/' in self.course_url:
            self.topics = soup.find_all('li', class_='toc-level-1') # top-level topic titles
        else:
            self.topics = soup.find_all('button', attrs={"title": "Click to hide the chapters in this part"})
            self.topics = [topic.parent for topic in self.topics]
        # self.topics = soup.find_all('div', class_="content-ContentSummary")
        print(len(self.topics))
        # sys.exit(0)

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
        topic_index = 0
        for topic in self.topics:
            topic_index = topic_index + 1

            if '/videos/' in self.course_url:
                topic_name = topic.a.text
            else:
                topic_name = topic.span.text

            # Creating folder to put the videos in
            topic_name = "".join([c for c in topic_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            save_folder = '{}/{:02d} - {}'.format(self.output_folder, topic_index, topic_name)
            os.makedirs(save_folder, exist_ok=True)
            # You can choose to skip these topic_name, comment these three lines if you do not want to skip any
            if topic_name in ('Sponsored'):
                print("Skipping {}...".format(topic_name))
                continue
            
            print(topic)

            if topic.ol:
                videos_in_topic = topic.ol.find_all('a')
            else:
                videos_in_topic = topic.find_all('a')
            
            print("VIDEOS IN TOPIC = " + str(len(videos_in_topic)))

            for index, video in enumerate(videos_in_topic):
                if '/videos/' in self.course_url:
                    print(video)
                    onlyVideoName = video.text
                else:
                    onlyVideoName = video.span.text

                print("onlyVideoName = " + str(onlyVideoName))
                video_name = '{:03d} - {}'.format(index + 1, onlyVideoName)
                video_name = self.validify(video_name)
                video_url = video.get('href')

                video_out = '{}/{}.mp4'.format(save_folder, video_name)
                
                # Check if file already exists
                if os.path.isfile(video_out):
                    print("File {} already exists! Skipping...".format(video_out))
                    continue

                print("Downloading {video_name} from {video_url} ...".format(video_name=video_name, video_url=video_url))

                video_url_last_part_without_html = video_url.split('/')[-1].replace(".html", "")
                if '/videos/' in self.course_url:
                    subtitles_url = "https://learning.oreilly.com/api/v1/videoclips/{course_id}-{video_url_last_part_without_html}".format(course_id=self.course_id, video_url_last_part_without_html=video_url_last_part_without_html)
                else:
                    subtitles_url = "https://learning.oreilly.com/api/v1/videoclips/{video_url_last_part_without_html}".format(video_url_last_part_without_html=video_url_last_part_without_html)
                # subtitles_name = os.path.splitext(video_name)[0] + '.json'
                subtitles_out = '{}/{}.json'.format(save_folder, video_name)
                call(["wget", subtitles_url, "-O", subtitles_out])

                with open(subtitles_out) as json_file:
                    subtitles_content = json.load(json_file)

                subtitles_lines = [line['text'] for line in subtitles_content['transcriptions'][0]['transcription']['lines']]
                lines = [""]
                for line in subtitles_lines:
                    if len(line) == 0:
                        continue
                    if line[0].isupper():
                        lines.append(line)
                    else:
                        lines[-1] = lines[-1] + " " + line

                lines = lines[1:]
                subtitles_txt_out = '{}/{}.txt'.format(save_folder, video_name)
                with open(subtitles_txt_out, "w") as f:
                    f.write(os.linesep.join(lines))

                # continue
                
                if '/videos/' not in self.course_url:
                    video_url = "https://learning.oreilly.com" + video_url
                    # video_url = "https://learning.oreilly.com/learning-paths/learning-path-managing/9781492042020/9781492031628-video318181"
                print("DOWNLOAD FROM URL = " + video_url)
                result = run(["youtube-dl", "--cookies", "cookies.txt", "-J", "--output", video_out, video_url], stdout=PIPE, stderr=PIPE, universal_newlines=True)

                print(result.stdout)
                video_url = json.loads(result.stdout)['url']
                print("FIRST URL = " + video_url)
                # sys.exit(0)

                if video_url.startswith("http://cdnapi.kaltura.com/"):
                    print("GETTING ONE MINUTE VIDEO RESPONSE")
                    oneMinuteVideoResponse = requests.head(video_url, headers={'cookie': self.getCookies()})
                    print(oneMinuteVideoResponse)
                    video_url = oneMinuteVideoResponse.headers['Location']

                if "/clipTo/60000/name/a.mp4" in video_url:
                    video_url = video_url.replace("/clipTo/60000/name/a.mp4", "")
                    print("Downloading {video_name} from {video_url} ...".format(video_name=video_name, video_url=video_url))
                    call(["wget", video_url, "-O", video_out])
                elif "index.m3u8" in video_url:
                    video_url = video_url.replace("/name/a.mp4/clipTo/60000", "")
                    print("Downloading {video_name} from {video_url} ...".format(video_name=video_name, video_url=video_url))
                    call(["ffmpeg", "-i", video_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", video_out])
                else:
                    print("Failed to get the url.")
                    sys.exit(1)

if __name__ == '__main__':
    downloader = SafariDownloader(course_url=sys.argv[1])
    downloader.download()


# https://learning.oreilly.com/videos/tcp-ip/9781771370790/9781771370790-video166922
# https://learning.oreilly.com/library/view/tcpip/9781771370790/video166922.html

# https://learning.oreilly.com/api/v1/videoclips/9781771370790-video166922/
