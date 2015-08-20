from pyquery import PyQuery as pq
from gmusicapi import Mobileclient
from difflib import SequenceMatcher
import datetime
import urllib
import time
import getpass

username = raw_input("Please enter your Google username: ")
password = getpass.getpass("Please enter password for user %s: " % username)
gmusic = Mobileclient()
logged_in = gmusic.login(username, password, Mobileclient.FROM_MAC_ADDRESS)
if not logged_in:
    raise Exception("Failed to authenticate google music account")
    sys.exit(2)

# crawl birp.fm to get a list of tracks from this month's playlist
current_date = datetime.datetime.now()
year = current_date.year
month = current_date.strftime("%B")
birpURL = "http://www.birp.fm/playlist/%s/%s-%s?order=rating" % (year, month, year)

# init pyQuery
d = pq(birpURL)

# extract song information from the html
birp_track_list = []
for el in d(".fap-single-track")[1:]:
    birp_track_list.append(el.get("title"))

# matches with confidence score above this threshold don't need additional
# checking
absolute_confidence_threshold = 150

# matches with scores below this threshold are rejected
confidence_threshold = 60

# classifications of matches
confident = []
unconfident = []
missing = []

# list of google IDs of accepted matches
track_ids = []

# look up each track from birp using google music search
for track in birp_track_list:
    search_results =  gmusic.search_all_access(track, 1)["song_hits"]
    if len(search_results) == 0:
        missing.append(track)
        # no results for this query, so skip it
        continue

    search_result = search_results[0]
    result_confidence = search_result["score"]

    is_confident = False
    if result_confidence >= absolute_confidence_threshold:
        # Google's confidence score is high enough to accept match
        is_confident = True
    elif result_confidence >= confidence_threshold:
        # Need to double check artist and track similarity manually
        tokens = track.split(" - ")
        birp_artist = tokens[0].lower()
        gmusic_artist = search_result["track"]["albumArtist"].lower()
        birp_title = tokens[1].lower()
        gmusic_title = search_result["track"]["title"].lower()
        artist_confidence = SequenceMatcher(None, birp_artist, gmusic_artist).ratio()
        title_confidence = SequenceMatcher(None, birp_title, gmusic_title).ratio()

        #TODO: document this
        stripped_confidence = 0
        feat_index_birp = birp_title.find("feat")
        feat_index_gmusic = gmusic_title.find("feat")
        if feat_index_birp >= 0 or feat_index_gmusic >= 0:
            print("found feat in %s" % birp_title)
            stripped_birp_title = birp_title if feat_index_birp == -1 else birp_title[:feat_index_birp]
            stripped_gmusic_title = gmusic_title if feat_index_gmusic == -1 else gmusic_title[:feat_index_gmusic]
            print("comparing %s and %s" % (stripped_gmusic_title, stripped_birp_title))
            stripped_confidence = SequenceMatcher(None, stripped_gmusic_title, stripped_birp_title).ratio()
            print("stripped confidence is %f" % stripped_confidence)
        is_confident = artist_confidence > 0.8 and (title_confidence > 0.5 or stripped_confidence > 0.5)

    if is_confident:
        track_id = search_result["track"]["nid"]
        track_ids.append(track_id)
        confident.append({"query" : track, "artist" : search_result["track"]["albumArtist"], "title" : search_result["track"]["title"], "confidence" : result_confidence})
    else:
        unconfident.append({"query" : track, "artist" : search_result["track"]["albumArtist"], "title" : search_result["track"]["title"], "confidence" : result_confidence})

# create birp playlist on google music
playlist_name = "BIRP! %s %s Playlist" % (month.capitalize(), year)
playlist_description = "%s %s playlist compiled by Josh Blalock at http://birp.fm" % (month.capitalize(), year)
playlist_id = gmusic.create_playlist(playlist_name, playlist_description)

# populate playlist with available birp tracks
gmusic.add_songs_to_playlist(playlist_id, track_ids)

# print stats about song selection
print("---------------------------")
print("CONFIDENT: %d songs\n" % len(confident))
for song in confident:
    print("\noriginal query: %s") % song["query"]
    print("artist: %s") % song["artist"]
    print("title: %s") % song["title"]
    print("confidence: %s") % song["confidence"]

print("---------------------------")
print("UNCONFIDENT %d songs\n" % len(unconfident))
for song in unconfident:
    print("\noriginal query: %s") % song["query"]
    print("artist: %s") % song["artist"]
    print("title: %s") % song["title"]
    print("confidence: %s") % song["confidence"]

print("---------------------------")
print("MISSING %d songs\n" % len(missing))
for song in missing:
    print("original query: %s") % song
