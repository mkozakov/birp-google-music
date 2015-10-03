from pyquery import PyQuery as pq
from gmusicapi import Mobileclient
from difflib import SequenceMatcher
import datetime
import urllib
import time
import getpass

# matches with confidence score above this threshold don't need additional checking
ABSOLUTE_CONFIDENCE_THRESHOLD = 150

# matches with scores below this threshold are rejected
CONFIDENCE_THRESHOLD = 60

def init_gmusic():
    """Request credentials, authenticate and connect to Google Music. Return
    authenticated MobileClient instance.
    """

    username = raw_input("Please enter your Google username: ")
    password = getpass.getpass("Please enter password for user %s: " % username)
    gmusic = Mobileclient()
    logged_in = gmusic.login(username, password, Mobileclient.FROM_MAC_ADDRESS)
    if not logged_in:
        raise Exception("Failed to authenticate google music account")
        sys.exit(2)
    return gmusic

# crawl birp.fm to get a list of tracks from this month's playlist
def crawl_birp():
    #"""Download HTML code of the most recent Birp page, and
    birpURL = "http://www.birp.fm/playlist/%s/%s-%s?order=rating" % (get_year(), get_month(), get_year())

    # init pyQuery
    pyQuery = pq(birpURL)

    # extract song information from the html
    birp_track_list = []
    for el in pyQuery(".fap-single-track")[1:]:
        birp_track_list.append(el.get("title"))
    return birp_track_list

def get_month():
    return datetime.datetime.now().strftime("%B")

def get_year():
    return datetime.datetime.now().year
# look up each track from birp using google music search
def match_songs(song_list, is_silent=False):

    # classifications of matches
    confident = []
    unconfident = []
    missing = []

    # list of google IDs of accepted matches
    track_ids = []

    for track in song_list:
        search_results =  gmusic.search_all_access(track, 1)["song_hits"]
        if len(search_results) == 0:
            missing.append(track)
            # no results for this query, so skip it
            continue

        search_result = search_results[0]
        result_confidence = search_result["score"]

        is_confident = False
        if result_confidence >= ABSOLUTE_CONFIDENCE_THRESHOLD:
            # Google's confidence score is high enough to accept match
            is_confident = True
        elif result_confidence >= CONFIDENCE_THRESHOLD:
            # Need to double check artist and track similarity manually
            tokens = track.split(" - ")
            birp_artist = tokens[0].lower()
            gmusic_artist = search_result["track"]["albumArtist"].lower()
            birp_title = tokens[1].lower()
            gmusic_title = search_result["track"]["title"].lower()
            artist_confidence = SequenceMatcher(None, birp_artist, gmusic_artist).ratio()
            title_confidence = SequenceMatcher(None, birp_title, gmusic_title).ratio()

            # Confidence level when song title takes works like "feat" into consideration
            stripped_confidence = 0
            feat_index_birp = birp_title.find("feat")
            feat_index_gmusic = gmusic_title.find("feat")
            if feat_index_birp >= 0 or feat_index_gmusic >= 0:
                # found the word "feat" in the song title
                stripped_birp_title = birp_title if feat_index_birp == -1 else birp_title[:feat_index_birp]
                stripped_gmusic_title = gmusic_title if feat_index_gmusic == -1 else gmusic_title[:feat_index_gmusic]
                # compare distance of between titles up until the word "feat"
                stripped_confidence = SequenceMatcher(None, stripped_gmusic_title, stripped_birp_title).ratio()
            is_confident = artist_confidence > 0.8 and (title_confidence > 0.5 or stripped_confidence > 0.5)

        if is_confident:
            track_id = search_result["track"]["nid"]
            track_ids.append(track_id)
            confident.append({"query" : track, "artist" : search_result["track"]["albumArtist"], "title" : search_result["track"]["title"], "confidence" : result_confidence})
        else:
            unconfident.append({"query" : track, "artist" : search_result["track"]["albumArtist"], "title" : search_result["track"]["title"], "confidence" : result_confidence})
    if not is_silent:
        print_results(confident, unconfident, missing)

    return track_ids

# create birp playlist on google music
def create_birp_playlist(track_ids):
    playlist_name = "BIRP! %s %s Playlist" % (get_month().capitalize(), get_year())
    playlist_description = "%s %s playlist compiled by Josh Blalock at http://birp.fm" % (get_month().capitalize(), get_year())
    playlist_id = gmusic.create_playlist(playlist_name, playlist_description, True)

    # populate playlist with available birp tracks
    gmusic.add_songs_to_playlist(playlist_id, track_ids)

# print stats about song selection
def print_results(confident, unconfident, missing):
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

gmusic = init_gmusic()
track_list = crawl_birp()
#track_list = get_tracks_from_file()
song_ids = match_songs(track_list)
create_birp_playlist(song_ids)
