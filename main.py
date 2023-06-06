import os 
import subprocess
import gi
import time
gi.require_version('Notify', '0.7')
from gi.repository import Notify

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction

class StreamlinkTwitchExtension(Extension):
    # Required
    def __init__(self):
        super(StreamlinkTwitchExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())

class KeywordQueryEventListener(EventListener):
    # Event handler for input query changes
    def on_event(self, event, extension):
        items = []
        autocomplete = []
        autocomplete = extension.preferences.get("autocomplete").lower()
        autocomplete = autocomplete.split(',')
        stream = event.get_argument()

        if stream:
            stream = stream.lower()
        else:
            stream = ""

        if len(stream) > 2:
            for streamer in autocomplete:
                if stream in streamer:
                    items.append(ExtensionResultItem(
                                icon='images/icon.png',
                                name="Watch %s"%streamer,
                                description="Watch %s on Twitch"%streamer.strip(" "),
                                on_enter=ExtensionCustomAction(streamer.strip(" "))
                            )
                    )

        if stream == "!!":
            items.append(ExtensionResultItem(
                        icon='images/icon.png',
                        name="Watch Everything",
                        description="Loads all favorites at once",
                        on_enter=ExtensionCustomAction(stream)
                    )
            )


        items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name="Watch %s"%stream,
                    description="Watch %s on Twitch"%stream,
                    on_enter=ExtensionCustomAction(stream)
                )
        )

        return RenderResultListAction(items)

class ItemEnterEventListener(EventListener):
    # Load stream accoridng to preferences
    def load_stream(self, stream, extension, special):
        Notify.init("Streamlink Twitch")
        streamlink_path = extension.preferences.get("streamlink_path")
        quality = extension.preferences.get("stream_quality").lower()
        player = extension.preferences.get("video_player")
        skip_ads = extension.preferences.get("disable_ads").lower()
        no_notify = extension.preferences.get("disable_notifications").lower()
        icon_path = os.path.dirname(os.path.realpath(__file__))+"/images/icon.png"
        notification_title = "Whoops!"
        notification_message = "Something probably went wrong"        
        cid = "ue6666qo983tsx6so1t0vnawi233wa"

        # If left blank, let's hope it's somewhere in their $PATH
        if not streamlink_path:
            streamlink_path = 'streamlink'

        # Clean up the UI and substitute here
        if quality == "audio only":
            quality = "audio_only"

        # If they didn't type a full URL (which why would you?)...
        if "://" not in stream:
            url = "https://twitch.tv/%s"%stream
        else:
            url = stream

        player_unique_args = []
        if "celluloid" in player:
            player = '%s --no-existing-session'%player
            player_unique_args.append("-n")

        if skip_ads == "yes":
            cmd = [streamlink_path, "--twitch-disable-ads", "--twitch-disable-reruns", "--twitch-api-header Client-ID=%s"%cid, "--player=%s"%player]
        else:
            cmd = [streamlink_path, "--twitch-api-header Client-ID=%s"%cid, "--player=%s"%player]

        if player_unique_args:
            for arg in player_unique_args:
                cmd.append(arg)

        cmd.append("%s %s"%(url,quality))

        # Popen doesn't like cmd list eleemnts with spaces, so we break it down intos a string and
        # add shell=True to the call to let it use that instead of the list
        cmdStr = ' '.join(cmd)

        buff = []
        proc = subprocess.Popen(cmdStr, stdout=subprocess.PIPE, encoding='utf-8', shell=True)

        for line in iter(proc.stdout.readline,''):
            line = line.lower()
            buff.append(line)

            # Stream Offline
            if "no playable streams found on this url" in line:
                notification_title = "Whoops!"
                notification_message = "%s is currently Offline"%stream
                break

            # Stream does not exist or API error
            if "unable to validate key" in line:
                notification_title = "Whoops!"
                notification_message = "%s does not exist"%stream
                break

            if "opening stream:" in line:
                if skip_ads == 'yes':
                    notification_title = "Grab Some Popcorn!"
                    notification_message = "%s's Stream is loading. Hang tight while we wait for the preroll ads to finish."%stream
                else:
                    notification_title = 'Grab Some Popcorn!'
                    notification_message = "%s's Stream is loading."%stream
                break

            if len(buff) > 10:
                notification_title = 'Yikes!'
                notification_message = "Infinite loop proection kicked in."
                break

        if not no_notify == 'yes':
            if not special:
                Notify.Notification.new(notification_title, notification_message, icon_path).show()
            else:
                if "is loading" in notification_message:
                    Notify.Notification.new(notification_title, notification_message, icon_path).show()

        Notify.uninit()


    # When we slap enter on an item
    def on_event(self, event, extension):
        stream = event.get_data() or ""

        if stream == '!!':
            autocomplete = extension.preferences.get("autocomplete").lower()
            autocomplete = autocomplete.split(',')

            Notify.init("Streamlink Twitch")
            icon_path = os.path.dirname(os.path.realpath(__file__))+"/images/icon.png"
            notification_title = "Grab some Popcorn!"
            notification_message =  "Loading all of your favorites. Streams will pop up if they are online. This may take a while..."
            Notify.Notification.new(notification_title, notification_message, icon_path).show()
            Notify.uninit()
            for fav in autocomplete:
                self.load_stream(fav, extension, True)
                time.sleep(1)
        else:
            self.load_stream(stream, extension, False)

        return RenderResultListAction([])

if __name__ == '__main__':
    StreamlinkTwitchExtension().run()
