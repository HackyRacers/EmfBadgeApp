import app
import time
import requests
import json
import os
from app_components import clear_background
from events.input import Buttons, BUTTON_TYPES

BASE_URL = "https://live.hackyracers.co.uk"
CONVERT_URL = "https://chris-stubbs.co.uk/extras/hacky/badgeapp/convert.php?file="


class HackyRacersMoxieApp(app.App):
    def __init__(self):
        super().__init__()

        print("[DEBUG] App init")

        self.button_states = Buttons(self)

        self.state = "SELECT_EVENT"

        self.events = [
            {"id": 2, "name": "EMF 2026"},
            {"id": 3, "name": "Test"},
        ]
        self.selected_event_idx = 0
        self.event_id = None

        self.vehicles = []
        self.selected_vehicle_idx = 0

        self.last_vote_time = 0
        self.cooldown_period = 30 * 60
        self.message = ""
        self.client_hash = "tildagon-" + str(int(time.time()))

        self.img_folder = os.path.dirname(__file__) + "/img"
        try:
            os.mkdir(self.img_folder)
            print("[DEBUG] Created img folder")
        except Exception:
            print("[DEBUG] img folder already exists")

    def draw_centered(self, ctx, text, y, base_size=22):
        length = len(text)

        if length <= 12:
            font_size = base_size
        else:
            font_size = max(10, base_size - (length - 12))

        ctx.font_size = font_size

        w = ctx.text_width(text)
        x = -w / 2

        ctx.move_to(x, y).text(text)

    def make_timestamp(self):
        gm = time.gmtime(time.time())
        print("[DEBUG] gmtime returned:", gm)
        y, m, d, hh, mm, ss = gm[:6]
        return f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}.000Z"

    # ---------------------------------------------------------
    # DOWNLOAD PNG AND SAVE TO DISK (avatar-style)
    # ---------------------------------------------------------
    def download_vehicle_image(self, vehicle_id, image_url):
        print(f"[DEBUG] download_vehicle_image() id={vehicle_id} url={image_url}")

        filename = f"vehicle_{vehicle_id}.png"
        local_path = f"{self.img_folder}/{filename}"

        print(f"[DEBUG] Local PNG path: {local_path}")

        try:
            os.stat(local_path)
            print("[DEBUG] PNG already exists, skipping download")
            return local_path
        except Exception:
            pass

        print("[DEBUG] Downloading PNG...")
        try:
            res = requests.get(image_url)
        except Exception as e:
            print(f"[DEBUG] HTTP error: {e}")
            return None

        print(f"[DEBUG] HTTP status: {res.status_code}")

        if res.status_code != 200:
            print("[DEBUG] Download failed")
            return None

        png_bytes = res.content
        print(f"[DEBUG] PNG bytes received: {len(png_bytes)}")

        try:
            with open(local_path, "wb") as f:
                f.write(png_bytes)
            print("[DEBUG] PNG write OK")
        except Exception as e:
            print(f"[DEBUG] PNG write FAILED: {e}")
            return None

        return local_path

    # ---------------------------------------------------------
    # UPDATE LOGIC
    # ---------------------------------------------------------
    def update(self, delta):
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self.state = "SELECT_EVENT"
            self.minimise()
            return

        # EVENT SELECTION
        if self.state == "SELECT_EVENT":
            if self.button_states.get(BUTTON_TYPES["UP"]):
                self.button_states.clear()
                self.selected_event_idx = (self.selected_event_idx - 1) % len(self.events)
            elif self.button_states.get(BUTTON_TYPES["DOWN"]):
                self.button_states.clear()
                self.selected_selected_event_idx = (self.selected_event_idx + 1) % len(self.events)
            elif self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.event_id = self.events[self.selected_event_idx]["id"]
                print(f"[DEBUG] Selected event ID: {self.event_id}")
                self.state = "INSTRUCTIONS"

        # NEW INSTRUCTION SCREEN
        elif self.state == "INSTRUCTIONS":
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.state = "FETCHING_VEHICLES"

        # FETCH VEHICLES
        elif self.state == "FETCHING_VEHICLES":
            try:
                url = f"{BASE_URL}/api/moxie/events/{self.event_id}/vehicles"
                print(f"[DEBUG] Fetching vehicles: {url}")

                res = requests.get(url)
                print(f"[DEBUG] Vehicle HTTP status: {res.status_code}")

                if res.status_code == 200:
                    self.vehicles = res.json()
                    print(f"[DEBUG] Vehicles received: {len(self.vehicles)}")

                    for v in self.vehicles:
                        if v["image"]:
                            img_filename = v["image"].split("/")[-1]
                            convert_url = CONVERT_URL + img_filename
                            print(f"[DEBUG] Converting via: {convert_url}")
                            v["local_png"] = self.download_vehicle_image(v["id"], convert_url)
                        else:
                            v["local_png"] = None

                    self.selected_vehicle_idx = 0
                    self.state = "LIST_VEHICLES"
                else:
                    self.message = f"HTTP {res.status_code}"
                    self.state = "ERROR"

            except Exception as e:
                print(f"[DEBUG] Exception fetching vehicles: {e}")
                self.message = "No WiFi"
                self.state = "ERROR"

        # LIST VEHICLES
        elif self.state == "LIST_VEHICLES":
            if self.button_states.get(BUTTON_TYPES["UP"]):
                self.button_states.clear()
                self.selected_vehicle_idx = (self.selected_vehicle_idx - 1) % len(self.vehicles)
            elif self.button_states.get(BUTTON_TYPES["DOWN"]):
                self.button_states.clear()
                self.selected_vehicle_idx = (self.selected_vehicle_idx + 1) % len(self.vehicles)
            elif self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                now = time.time()
                if now - self.last_vote_time < self.cooldown_period:
                    remaining = int((self.cooldown_period - (now - self.last_vote_time)) / 60)
                    self.message = f"Wait {remaining}m"
                    self.state = "COOLDOWN"
                else:
                    self.state = "VOTING"

        # VOTING
        elif self.state == "VOTING":
            try:
                url = f"{BASE_URL}/api/moxie/events/{self.event_id}/vote"

                v_id = self.vehicles[self.selected_vehicle_idx]["id"]

                payload = {
                    "client_hash": self.client_hash,
                    "vehicle_id": int(v_id),
                    "event_id": int(self.event_id),
                    "timestamp": self.make_timestamp(),
                    "ranking": 1,
                    "source": "Online",
                }

                headers = {"Content-Type": "application/json"}

                res = requests.post(url, data=json.dumps(payload), headers=headers)

                print(f"[DEBUG] Vote HTTP status: {res.status_code}")

                if res.status_code in [200, 201]:
                    self.last_vote_time = time.time()
                    self.state = "FINAL_SCREEN"
                else:
                    self.message = f"Fail {res.status_code}"
                    self.state = "ERROR"

            except Exception as e:
                print(f"[DEBUG] Vote exception: {e}")
                self.message = "Net Err"
                self.state = "ERROR"

        # FINAL SCREEN
        elif self.state == "FINAL_SCREEN":
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.state = "SELECT_EVENT"
                self.minimise()

        # COOLDOWN / ERROR
        elif self.state in ["COOLDOWN", "ERROR"]:
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.state = "LIST_VEHICLES" if self.vehicles else "SELECT_EVENT"

    # ---------------------------------------------------------
    # DRAW LOGIC
    # ---------------------------------------------------------
    def draw(self, ctx):
        clear_background(ctx)
        ctx.rgb(0.1, 0.1, 0.1).rectangle(-120, -120, 240, 240).fill()

        # INSTRUCTION SCREEN
        if self.state == "INSTRUCTIONS":
            ctx.font_size = 24
            ctx.rgb(0.8, 0.8, 0.8).move_to(-97, -30).text("Use A/D to scroll")
            ctx.rgb(0.8, 0.8, 0.8).move_to(-100, 0).text("Pick your favourite")
            ctx.rgb(0.8, 0.8, 0.8).move_to(-83, 30).text("Press C to vote")
            ctx.font_size = 20
            ctx.rgb(0.5, 1, 0.5).move_to(-60, 63).text("[C - continue]")
            return

        # SELECT EVENT
        if self.state == "SELECT_EVENT":
            ctx.font_size = 26
            ctx.rgb(1, 1, 1).move_to(-80, -50).text("Select Event")
            ctx.font_size = 20
            ctx.rgb(0.5, 1, 0.5).move_to(-62, 70).text("[A/D - Scroll]")
            ctx.rgb(0.5, 1, 0.5).move_to(-53, 90).text("[C - Select]")
            ctx.font_size = 20
            for i, ev in enumerate(self.events):
                y = -20 + (i * 25)
                name = ev["name"]
                if i == self.selected_event_idx:
                    ctx.rgb(0, 1, 0).move_to(-90, y).text("> " + name)
                else:
                    ctx.rgb(0.6, 0.6, 0.6).move_to(-90, y).text(name)
            return

        # FETCHING
        if self.state == "FETCHING_VEHICLES":
            ctx.rgb(1, 1, 0).move_to(-80, 0).text("Loading…")
            return

        # LIST VEHICLES
        if self.state == "LIST_VEHICLES":
            v = self.vehicles[self.selected_vehicle_idx]
            png_path = v.get("local_png")

            if png_path:
                ctx.save()
                ctx.image(png_path, -120, -120, 240, 240)
                ctx.restore()
            else:
                ctx.rgb(1, 0, 0).move_to(-80, 0).text("[no img]")

            ctx.rgb(1, 1, 1)
            self.draw_centered(ctx, v["name"], 80, 24)
            return

        # VOTING
        if self.state == "VOTING":
            ctx.rgb(1, 1, 0).move_to(-80, 0).text("Sending…")
            return

        # FINAL SCREEN
        if self.state == "FINAL_SCREEN":
            ctx.font_size = 26
            ctx.rgb(0.8, 1, 0.8).move_to(-110, -20).text("Thanks for voting!")
            ctx.font_size = 20
            ctx.rgb(0.8, 0.8, 0.8).move_to(-102, 20).text("Come back next race")
            ctx.rgb(0.8, 0.8, 0.8).move_to(-60, 45).text("to vote again")
            ctx.font_size = 20
            ctx.rgb(0.5, 1, 0.5).move_to(-40, 80).text("[C - Exit]")
            return

        # COOLDOWN / ERROR
        if self.state in ["COOLDOWN", "ERROR"]:
            ctx.rgb(1, 0, 0).move_to(-80, 0).text(self.message)
            ctx.rgb(0.6, 0.6, 0.6).move_to(-80, 40).text("[Back]")
            return


__app_export__ = HackyRacersMoxieApp
