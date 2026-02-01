import os
import subprocess
import asyncio
import threading
import shutil

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction

def notify_show(title, message):
	notify_send = shutil.which("notify-send")
	if not notify_send:
		return

	icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "images", "icon.png")
	cmd = [notify_send, "-a", "Streamlink Twitch", "-i", icon_path, "-t", "5000", title, message]

	try:
		subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	except Exception:
		pass


class StreamlinkTwitchExtension(Extension):
	def __init__(self):
		super(StreamlinkTwitchExtension, self).__init__()
		self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
		self.subscribe(ItemEnterEvent, ItemEnterEventListener())


class KeywordQueryEventListener(EventListener):
	def on_event(self, event, extension):
		items = []
		autocomplete = extension.preferences.get("autocomplete").lower().split(',')
		stream = (event.get_argument() or "").lower()

		if len(stream) > 2:
			for streamer in autocomplete:
				if stream in streamer:
					items.append(ExtensionResultItem(
						icon='images/icon.png',
						name="Watch %s" % streamer,
						description="Watch %s on Twitch" % streamer.strip(" "),
						on_enter=ExtensionCustomAction(streamer.strip(" "))
					))

		if stream == "--":
			items.append(ExtensionResultItem(
				icon='images/icon.png',
				name="Watch Everything",
				description="Loads all favorites at once",
				on_enter=ExtensionCustomAction(stream)
			))

		items.append(ExtensionResultItem(
			icon='images/icon.png',
			name="Watch %s" % stream,
			description="Watch %s on Twitch" % stream,
			on_enter=ExtensionCustomAction(stream)
		))

		return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):
	async def probe_stream(self, stream, extension):
		streamlink_path = extension.preferences.get("streamlink_path") or "streamlink"
		auth_token = extension.preferences.get("auth_token") or ""
		url = stream if "://" in stream else "https://twitch.tv/%s" % stream

		result = {
			"status": None,
			"message": None,
			"url": url,
			"stream_url": None
		}

		cmd = [streamlink_path]
		if auth_token:
			cmd.append("--twitch-api-header=Authorization=OAuth=%s" % auth_token)

		cmd_str = " ".join(cmd + ["--stream-url", "%s best" % url])

		try:
			proc = await asyncio.create_subprocess_shell(cmd_str, stdout=asyncio.subprocess.PIPE)

			try:
				stdout_bytes = await asyncio.wait_for(proc.communicate(), timeout=4)
			except asyncio.TimeoutError:
				proc.kill()
				await proc.wait()
				result["status"] = "timeout"
				result["message"] = "%s: probe timed out" % stream
				return result

			stdout = (stdout_bytes[0] or b"").decode("utf-8", errors="replace").strip()
			stdout_lower = stdout.lower()

			if "no playable streams found" in stdout_lower:
				result["status"] = "offline"
				result["message"] = "%s is currently Offline" % stream
				return result

			if "unable to validate key" in stdout_lower:
				result["status"] = "notfound"
				result["message"] = "%s does not exist" % stream
				return result

			if proc.returncode == 0 and stdout.startswith("http"):
				result["status"] = "online"
				result["message"] = "%s is online" % stream
				result["stream_url"] = stdout
				return result

			result["status"] = "error"
			result["message"] = "Probe error for %s" % stream if stdout else "Unknown error while probing %s" % stream
			return result

		except Exception as e:
			result["status"] = "error"
			result["message"] = "Probe exception: %s" % str(e)
			return result

	async def load_stream(self, stream, extension, special):
		streamlink_path = extension.preferences.get("streamlink_path") or "streamlink"
		quality = extension.preferences.get("stream_quality").lower()
		player = extension.preferences.get("video_player").lower()
		taskset = extension.preferences.get("restrict_cores").lower()
		is_flatpak = extension.preferences.get("player_is_flatpak").lower()
		auth_token = extension.preferences.get("auth_token") or ""
		no_notify = extension.preferences.get("disable_notifications").lower()

		url = stream if "://" in stream else "https://twitch.tv/%s" % stream
		if quality == "audio only":
			quality = "audio_only"

		probe = await self.probe_stream(stream, extension)
		if probe["status"] in ("offline", "notfound", "timeout", "error"):
			if no_notify != "yes" and not special:
				notify_show("Whoops!", probe["message"])
			return

		if no_notify != "yes":
			notify_show("Grab Some Popcorn!", "%s's Stream is loading. Hang tight while we wait for the preroll ads to finish." % stream)

		cmd = []
		cmd_tail = []
		player_args = []
		arg_string = ""

		if taskset == "yes":
			cmd += ["taskset -c 0", streamlink_path]
		else:
			cmd.append(streamlink_path)

		if is_flatpak == "yes":
			selected_player = player
			player = "flatpak"

			match selected_player:
				case "vlc":
					player_args.append("run org.videolan.VLC")
				case "mpv":
					player_args.append("run io.mpv.Mpv")
				case "celluloid":
					player_args += ["run io.github.celluloid_player.Celluloid", "--no-existing-session"]
					cmd_tail.append("--player-continuous-http")
				case "gnome video (showtime)":
					player_args += ["run org.gnome.Showtime", "--new-window"]
					cmd_tail.append("--player-passthrough=hls,http")
				case "clapper":
					player_args.append("run com.github.rafostar.Clapper")
				case "smplayer":
					player_args.append("run info.smplayer.SMPlayer")
		else:
			if "celluloid" in player:
				player = "%s --no-existing-session" % player
				player_args.append("-n")
			else:
				cmd.append('--title "{author} is Playing \'{game}\' | {title} | %s"' % url)

		if auth_token:
			cmd.append("--twitch-api-header=Authorization=OAuth=%s" % auth_token)

		cmd.append("--player=%s" % player)

		if player_args:
			arg_string = '--player-args="' + " ".join(player_args) + '"'

		cmd.append("%s %s" % (url, quality))

		cmd_str = " ".join(cmd)
		if arg_string:
			cmd_str += " %s " % arg_string
		if cmd_tail:
			cmd_str += " " + " ".join(cmd_tail)

		print(cmd_str)

		try:
			await asyncio.create_subprocess_shell(cmd_str, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
		except Exception as e:
			print("Launch failed:", e)
			if no_notify != "yes" and not special:
				notify_show("Whoops!", "Launch failed for %s" % stream)



	def on_event(self, event, extension):
		threading.Thread(target=self._run_async, args=(event.get_data() or "", extension), daemon=True).start()
		return RenderResultListAction([])


	def _run_async(self, stream, extension):
		try:
			asyncio.run(self._handle_enter(stream, extension))
		except Exception as e:
			print("Async handler error:", e)


	async def _handle_enter(self, stream, extension):
		if stream == "--":
			autocomplete = [s.strip(" ") for s in extension.preferences.get("autocomplete").lower().split(",") if s.strip(" ")]

			notify_show("Grab some Popcorn!", "Loading all of your favorites. Streams will pop up if they are online. This may take a while...")

			sem = asyncio.Semaphore(5)

			async def _load_one(fav):
				async with sem:
					await self.load_stream(fav, extension, True)

			await asyncio.gather(*(_load_one(fav) for fav in autocomplete))
			return

		await self.load_stream(stream, extension, False)


if __name__ == '__main__':
	StreamlinkTwitchExtension().run()
