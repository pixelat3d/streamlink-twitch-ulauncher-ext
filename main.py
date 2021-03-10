import os 
import subprocess

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
        stream = event.get_argument()

        items.append(ExtensionResultItem(
                    icon='images/icon.png',
                    name="Watch %s"%stream,
                    description="Watch %s on Twitch"%stream,
                    on_enter=ExtensionCustomAction(stream)
                )
        )
    
        return RenderResultListAction(items)

class ItemEnterEventListener(EventListener):
    # When we slap enter on an item
    def on_event(self, event, extension):
        Notify.init("Streamlink Twitch")
        streamlink_path = extension.preferences.get("streamlink_path")
        quality = extension.preferences.get("stream_quality").lower()
        player = extension.preferences.get("video_player")
        skip_ads = extension.preferences.get("disable_ads").lower()
        no_notify = extension.preferences.get("disable_notifications").lower()
        icon_path = os.path.dirname(os.path.realpath(__file__))+"/images/icon.png"
        stream = event.get_data() or ""

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

        if skip_ads == "yes":
            cmd = [streamlink_path, "--twitch-disable-ads", "--player=%s"%player, url, quality]
        else:
            cmd = [streamlink_path, "--player=%s"%player, url, quality]

        buff = []
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, encoding='utf-8', )

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
            Notify.Notification.new(notification_title, notification_message, icon_path).show()

        Notify.uninit()

        return RenderResultListAction([])


if __name__ == '__main__':
    StreamlinkTwitchExtension().run()
