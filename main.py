import subprocess

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
        streamlink_path = extension.preferences.get("streamlink_path")
        quality = extension.preferences.get("stream_quality")
        player = extension.preferences.get("video_player")
        stream = event.get_data() or ""

        if "https://" not in stream:
            url = "https://twitch.tv/%s"%stream
        else:
            url = stream

        cmd = [streamlink_path, "--player=%s"%player, url, quality]
        subprocess.Popen(cmd)

        return RenderResultListAction([])

if __name__ == '__main__':
    StreamlinkTwitchExtension().run()
