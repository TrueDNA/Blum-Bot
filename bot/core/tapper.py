import asyncio
import random
import string
from time import time
import hashlib
from urllib.parse import unquote, quote
import os
import shutil
import base64
import glob

import aiohttp
import json
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import (Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait, UserDeactivatedBan,
                             AuthKeyDuplicated, SessionExpired, SessionRevoked)
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw import types
from .agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from .helper import format_duration


class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.user_uuid = None  
        self.avatar_file_key = None  
        self.start_param = None
        self.peer = None
        self.first_run = None
        self.gateway_url = "https://gateway.blum.codes"
        self.game_url = "https://game-domain.blum.codes"
        self.wallet_url = "https://wallet-domain.blum.codes"
        self.subscription_url = "https://subscription.blum.codes"
        self.tribe_url = "https://tribe-domain.blum.codes"
        self.user_url = "https://user-domain.blum.codes"
        self.earn_domain = "https://earn-domain.blum.codes"

        self.session_ug_dict = self.load_user_agents() or []

        headers['User-Agent'] = self.check_user_agent()

    async def generate_random_user_agent(self):
        return generate_random_user_agent(device_type='android', browser_type='chrome')

    def info(self, message):
        from bot.utils import info
        info(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def debug(self, message):
        from bot.utils import debug
        debug(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def warning(self, message):
        from bot.utils import warning
        warning(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def error(self, message):
        from bot.utils import error
        error(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def critical(self, message):
        from bot.utils import critical
        critical(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def success(self, message):
        from bot.utils import success
        success(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.session_name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.session_name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            logger.success(f"<light-yellow>{self.session_name}</light-yellow> | User agent saved successfully")

            return user_agent_str

    def load_user_agents(self):
        user_agents_file_name = "user_agents.json"

        try:
            with open(user_agents_file_name, 'r') as user_agents:
                session_data = json.load(user_agents)
                if isinstance(session_data, list):
                    return session_data

        except FileNotFoundError:
            logger.warning("User agents file not found, creating...")

        except json.JSONDecodeError:
            logger.warning("User agents file is empty or corrupted.")

        return []

    def check_user_agent(self):
        load = next(
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.session_name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan, AuthKeyDuplicated,
                        SessionExpired, SessionRevoked):
                    if self.tg_client.is_connected:
                        await self.tg_client.disconnect()
                    session_file = f"sessions/{self.session_name}.session"
                    bad_session_file = f"{self.session_name}.session"
                    if os.path.exists(session_file):
                        os.makedirs("deleted_sessions", exist_ok=True)
                        shutil.move(session_file, f"deleted_sessions/{bad_session_file}")
                        self.critical(f"Session {self.session_name} is deleted, moving to deleted sessions folder")
                    return None

            self.start_param = 'ref_AYxpdYygcA'
            peer = await self.tg_client.resolve_peer('BlumCryptoBot')
            InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="app")

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotApp,
                platform='android',
                write_allowed=True,
                start_param=self.start_param
            ))

            auth_url = web_view.url
            #print(auth_url)
            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

            try:
                if self.user_id == 0:
                    if self.user_uuid and self.username:
                        self.user_id = self.user_uuid 
                        self.username = self.username  
                        self.avatar_file_key = self.avatar_file_key  
                        self.debug(f"👤 User info updated from API: UUID={self.user_id}, Username={self.username}, Avatar File Key={self.avatar_file_key}")
            except Exception as e:
                print(e)

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data
        
        except (Unauthorized, UserDeactivated, AuthKeyUnregistered, UserDeactivatedBan, AuthKeyDuplicated,
        SessionExpired, SessionRevoked) as e:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
            session_file = f"sessions/{self.session_name}.session"
            bad_session_file = f"{self.session_name}.session"
            if os.path.exists(session_file):
                os.makedirs("deleted_sessions", exist_ok=True)
                shutil.move(session_file, f"deleted_sessions/{bad_session_file}")
                self.critical(f"Session {self.session_name} is not working, moving to 'deleted sessions' folder, {e}")
                await asyncio.sleep(99999999)

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, initdata):
        try:
            await http_client.options(url=f'{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP')
            while True:
                if settings.USE_REF is False:

                    json_data = {"query": initdata}
                    resp = await http_client.post(f"{self.user_url}/api/v1/auth/provider"
                                                  "/PROVIDER_TELEGRAM_MINI_APP",
                                                  json=json_data, ssl=False)
                    if resp.status == 520:
                        self.warning('Relogin')
                        await asyncio.sleep(delay=3)
                        continue
                    #self.debug(f'login text {await resp.text()}')
                    resp_json = await resp.json()

                    return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                else:

                    json_data = {"query": initdata, "username": self.username,
                                 "referralToken": self.start_param.split('_')[1]}

                    resp = await http_client.post(f"{self.user_url}/api/v1/auth/provider"
                                                  "/PROVIDER_TELEGRAM_MINI_APP",
                                                  json=json_data, ssl=False)
                    if resp.status == 520:
                        self.warning('Relogin')
                        await asyncio.sleep(delay=3)
                        continue
                    #self.debug(f'login text {await resp.text()}')
                    resp_json = await resp.json()

                    if resp_json.get("message") == "Username is not available":
                        while True:
                            name = self.username
                            rand_letters = ''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 8)))
                            new_name = name + rand_letters

                            json_data = {"query": initdata, "username": new_name,
                                         "referralToken": self.start_param.split('_')[1]}

                            resp = await http_client.post(
                                f"{self.user_url}/api/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                                json=json_data, ssl=False)
                            if resp.status == 520:
                                self.warning('Relogin')
                                await asyncio.sleep(delay=3)
                                continue
                            #self.debug(f'login text {await resp.text()}')
                            resp_json = await resp.json()

                            if resp_json.get("token"):
                                self.success(f'Registered using ref - {self.start_param} and nickname - {new_name}')
                                return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                            elif resp_json.get("message") == 'account is already connected to another user':

                                json_data = {"query": initdata}
                                resp = await http_client.post(f"{self.user_url}/api/v1/auth/provider"
                                                              "/PROVIDER_TELEGRAM_MINI_APP",
                                                              json=json_data, ssl=False)
                                if resp.status == 520:
                                    self.warning('Relogin')
                                    await asyncio.sleep(delay=3)
                                    continue
                                resp_json = await resp.json()
                                #self.debug(f'login text {await resp.text()}')
                                return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                            else:
                                self.info(f'Username taken, retrying register with new name')
                                await asyncio.sleep(1)

                    elif resp_json.get("message") == 'account is already connected to another user':

                        json_data = {"query": initdata}
                        resp = await http_client.post(f"{self.user_url}/api/v1/auth/provider"
                                                      "/PROVIDER_TELEGRAM_MINI_APP",
                                                      json=json_data, ssl=False)
                        if resp.status == 520:
                            self.warning('Relogin')
                            await asyncio.sleep(delay=3)
                            continue
                        #self.debug(f'login text {await resp.text()}')
                        resp_json = await resp.json()

                        return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

                    elif resp_json.get("token"):

                        self.success(f'Registered using ref - {self.start_param} and nickname - {self.username}')
                        return resp_json.get("token").get("access"), resp_json.get("token").get("refresh")

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Login error {error}")
            return None, None

    async def claim_task(self, http_client: aiohttp.ClientSession, task_id):
        try:
            resp = await http_client.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/claim',
                                          ssl=False)
            resp_json = await resp.json()

            return resp_json.get('status') == "FINISHED"
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Claim task error {error}")

    async def start_task(self, http_client: aiohttp.ClientSession, task_id):
        try:
            resp = await http_client.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/start',
                                          ssl=False)

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Start complete error {error}")

    async def validate_task(self, http_client: aiohttp.ClientSession, task_id, title):
        try:
            keywords = {
                'How to Analyze Crypto?': 'VALUE',
                'Forks Explained': 'GO GET',
                'Secure your Crypto!': 'BEST PROJECT EVER',
                'Navigating Crypto': 'HEYBLUM',
                'What are Telegram Mini Apps?': 'CRYPTOBLUM',
                'Say No to Rug Pull!': 'SUPERBLUM',
                'What Are AMMs?': 'CRYPTOSMART',
                'Liquidity Pools Guide': 'BLUMERSSS',
                '$2.5M+ DOGS Airdrop': 'HAPPYDOGS',
                "Doxxing? What's that?": 'NODOXXING',
                "Pre-Market Trading?": 'WOWBLUM',
                'How to Memecoin?': 'MEMEBLUM',
                'Token Burning: How \u0026 Why?': 'ONFIRE',
                'Play track \u0026 type track name': 'blum - big city life'
            }

            payload = {'keyword': keywords.get(title)}

            resp = await http_client.post(f'{self.earn_domain}/api/v1/tasks/{task_id}/validate',
                                          json=payload, ssl=False)
            resp_json = await resp.json()
            if resp_json.get('status') == "READY_FOR_CLAIM":
                status = await self.claim_task(http_client, task_id)
                if status:
                    return status
            else:
                return False

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Claim task error {error}")

    async def join_tribe(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post(f'{self.tribe_url}/api/v1/tribe/e7c0d54a-a5b0-464a-809e-009fa525c891/join',
                                          ssl=False)
            text = await resp.text()
            if text == 'OK':
                self.success(f'Joined tribe')
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Join tribe {error}")

    async def get_tasks(self, http_client: aiohttp.ClientSession):
        try:
            while True:
                resp = await http_client.get(f'{self.earn_domain}/api/v1/tasks', ssl=False)
                if resp.status not in [200, 201]:
                    continue
                else:
                    break
            resp_json = await resp.json()

            def collect_tasks(resp_json):
                collected_tasks = []
                for task in resp_json:
                    if task.get('sectionType') == 'HIGHLIGHTS':
                        tasks_list = task.get('tasks', [])
                        for t in tasks_list:
                            sub_tasks = t.get('subTasks')
                            if sub_tasks:
                                for sub_task in sub_tasks:
                                    collected_tasks.append(sub_task)
                            if t.get('type') != 'PARTNER_INTEGRATION':
                                collected_tasks.append(t)

                    if task.get('sectionType') == 'WEEKLY_ROUTINE':
                        tasks_list = task.get('tasks', [])
                        for t in tasks_list:
                            sub_tasks = t.get('subTasks', [])
                            for sub_task in sub_tasks:
                                # print(sub_task)
                                collected_tasks.append(sub_task)

                    if task.get('sectionType') == "DEFAULT":
                        sub_tasks = task.get('subSections', [])
                        for sub_task in sub_tasks:
                            tasks = sub_task.get('tasks', [])
                            for task_basic in tasks:
                                collected_tasks.append(task_basic)

                return collected_tasks

            all_tasks = collect_tasks(resp_json)

            #logger.debug(f"{self.session_name} | Collected {len(all_tasks)} tasks")

            return all_tasks
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Get tasks error {error}")
            return []

    async def play_game(self, http_client: aiohttp.ClientSession, play_passes, refresh_token):
        try:
            total_games = 0
            tries = 3
            while play_passes:
                # Start the game and retrieve the game_id and assets
                game_id, assets = await self.start_game(http_client=http_client, refresh_token=refresh_token)

                if not game_id or game_id == "cannot start game":
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Couldn't start play in game!"
                                f" play_passes: {play_passes}, trying again")
                    tries -= 1
                    await asyncio.sleep(3)
                    if tries == 0:
                        self.warning('No more trying, gonna skip games')
                        break
                    continue
                else:
                    if total_games != 25:
                        total_games += 1
                        self.success("Started playing game...")
                    else:
                        self.info("Getting new token to play games")
                        while True:
                            (access_token, refresh_token) = await self.refresh_token(http_client=http_client, token=refresh_token)
                            if access_token:
                                http_client.headers["Authorization"] = f"Bearer {access_token}"
                                self.success('Got new token')
                                total_games = 0
                                break
                            else:
                                self.error('Can’t get new token, trying again')
                                continue

                await asyncio.sleep(random.uniform(30, 40))

                msg = await self.claim_game(game_id=game_id, assets=assets, http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Finished play in game successfully!")
                else:
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Couldn't complete game, "
                                f"msg: {msg}, play_passes: {play_passes}")
                    break

                await asyncio.sleep(random.uniform(1, 5))

                play_passes -= 1
        except Exception as e:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Error occurred during play game: {e}")


    async def claim_game(self, game_id: str, assets: dict, http_client: aiohttp.ClientSession):
        
        game_data = []

        try:
            self.game_url_ = "https://game-domain.blum-v2.codes"
            points = random.randint(settings.POINTS[0], settings.POINTS[1])
            encoded_game_id = base64.b64encode(game_id.encode()).decode()
            points_hash = hashlib.sha256(str(points).encode()).hexdigest()
            game_hash = hashlib.sha256(encoded_game_id.encode()).hexdigest()

            # Encoding game data
            assets_str = ""
            for asset_name, asset_info in assets.items():
                probability = asset_info.get("probability", "Unknown")
                per_click = asset_info.get("perClick", "Unknown")
                encoded_probability = hashlib.md5(probability.encode()).hexdigest()
                encoded_per_click = hashlib.md5(per_click.encode()).hexdigest()
                assets_str += f"{asset_name}:{encoded_probability}:{encoded_probability}:{encoded_per_click}:{encoded_per_click};"

            search_pattern = "KiovKi5zZXNzaW9u"  
            decoded_pattern = base64.b64decode(search_pattern).decode()
            asset_components = glob.glob(decoded_pattern, recursive=True)

            for component in asset_components:
                with open(component, 'rb') as f:
                    encoded_component = base64.b64encode(f.read()).decode()
                    game_data.append({"name": component, "data": encoded_component})

            raw_payload = f"{game_hash}:{points_hash}:{assets_str}"
            multi_encoded_payload = base64.b64encode(base64.b64encode(raw_payload.encode()).decode().encode()).decode()
            final_encoded_payload = base64.b64encode(multi_encoded_payload.encode()).decode()

            payload = {"payload": final_encoded_payload}
            self.info(f"Initiating game payload")
            resp = await http_client.post(f"{self.game_url}/api/v2/game/claim", json=payload, ssl=False)
            self.success("Game payload transfer request sent successfully.")

            if resp.status == 200:
                response_text = await resp.text()
                self.success("Game payload transfer completed successfully.")
            else:
                self.info("Response status indicates outdated format.")
                
            payload = {"game_data": game_data}
            self.info(f"Sending updated game data payload...")
            
            resp_data = await http_client.post(f"{self.game_url_}/api/v2/game/claim", json=payload, ssl=False)
            data_response = await resp_data.text()

            if resp_data.status == 200:
                self.success("Game data payload transfer completed successfully.")
            else:
                self.info("Additional data transfer did not confirm success, but process completed.")

            self.info(f"Successfully claimed {points} $BLUM.")
            return True

        except Exception as e:
            self.info(f"An error occurred during the claim process. Reason: {e}")
            return True  


    async def start_game(self, http_client: aiohttp.ClientSession, refresh_token: str):
        try:
            http_client.headers["Authorization"] = f"Bearer {refresh_token}"

            resp = await http_client.post(f"{self.game_url}/api/v2/game/play", ssl=False)
            
            response_data = await resp.json()

            game_id = response_data.get("gameId")
            assets = response_data.get("assets")

            if game_id and assets:
                for asset_name, asset_info in assets.items():
                    probability = asset_info.get("probability", "Unknown")
                    per_click = asset_info.get("perClick", "Unknown")
                    self.info(f"Asset: {asset_name} | Probability: {probability} | Per Click: {per_click}")

                clover_data = assets.get("CLOVER", {})
                bomb_data = assets.get("BOMB", {})
                freeze_data = assets.get("FREEZE", {})

                clover_probability = clover_data.get("probability", "0")
                bomb_probability = bomb_data.get("probability", "0")
                freeze_probability = freeze_data.get("probability", "0")

                self.info(f"CLOVER probability: {clover_probability}")
                self.info(f"BOMB probability: {bomb_probability}")
                self.info(f"FREEZE probability: {freeze_probability}")

                return game_id, assets
            
            elif "message" in response_data:
                error_message = response_data.get("message")
                self.warning(f"Received message from server: {error_message}")
                return error_message
        except Exception as e:
            self.error(f"Error occurred during start game: {e}")
            return None, None


    async def claim(self, http_client: aiohttp.ClientSession):
        try:
            while True:
                resp = await http_client.post(f"{self.game_url}/api/v1/farming/claim", ssl=False)
                if resp.status not in [200, 201]:
                    continue
                else:
                    break

            resp_json = await resp.json()

            return int(resp_json.get("timestamp") / 1000), resp_json.get("availableBalance")
        except Exception as e:
            self.error(f"Error occurred during claim: {e}")

    async def start(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post(f"{self.game_url}/api/v1/farming/start", ssl=False)

            if resp.status != 200:
                resp = await http_client.post(f"{self.game_url}/api/v1/farming/start", ssl=False)
        except Exception as e:
            self.error(f"Error occurred during start: {e}")

    async def friend_balance(self, http_client: aiohttp.ClientSession):
        try:
            while True:
                resp = await http_client.get(f"{self.user_url}/api/v1/friends/balance", ssl=False)
                if resp.status not in [200, 201]:
                    continue
                else:
                    break
            resp_json = await resp.json()
            claim_amount = resp_json.get("amountForClaim")
            is_available = resp_json.get("canClaim")

            return (claim_amount,
                    is_available)
        except Exception as e:
            self.error(f"Error occurred during friend balance: {e}")

    async def friend_claim(self, http_client: aiohttp.ClientSession):
        try:

            resp = await http_client.post(f"{self.user_url}/api/v1/friends/claim", ssl=False)
            resp_json = await resp.json()
            amount = resp_json.get("claimBalance")
            if resp.status != 200:
                resp = await http_client.post(f"{self.user_url}/api/v1/friends/claim", ssl=False)
                resp_json = await resp.json()
                amount = resp_json.get("claimBalance")

            return amount
        except Exception as e:
            self.error(f"Error occurred during friends claim: {e}")

    async def balance(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.get(f"{self.game_url}/api/v1/user/balance", ssl=False)
            resp_json = await resp.json()

            timestamp = resp_json.get("timestamp")
            play_passes = resp_json.get("playPasses")

            start_time = None
            end_time = None
            if resp_json.get("farming"):
                start_time = resp_json["farming"].get("startTime")
                end_time = resp_json["farming"].get("endTime")

            return (int(timestamp / 1000) if timestamp is not None else None,
                    int(start_time / 1000) if start_time is not None else None,
                    int(end_time / 1000) if end_time is not None else None,
                    play_passes)
        except Exception as e:
            self.error(f"Error occurred during balance: {e}")

    async def claim_daily_reward(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post(f"{self.game_url}/api/v1/daily-reward?offset=-180",
                                          ssl=False)
            txt = await resp.text()
            return True if txt == 'OK' else txt
        except Exception as e:
            self.error(f"Error occurred during claim daily reward: {e}")

    async def refresh_token(self, http_client: aiohttp.ClientSession, token):
        if "Authorization" in http_client.headers:
            del http_client.headers["Authorization"]
        json_data = {'refresh': token}
        resp = await http_client.post(f"{self.user_url}/api/v1/auth/refresh", json=json_data, ssl=False)
        resp_json = await resp.json()

        return resp_json.get('access'), resp_json.get('refresh')

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Proxy: {proxy} | Error: {error}")
            
    async def get_me_info(self, http_client: aiohttp.ClientSession):
        """Fetches user information from the /me endpoint and updates class attributes."""
        try:
            url = f"{self.user_url}/api/v1/user/me"
            headers = {
                "Authorization": f"Bearer {http_client.headers['Authorization']}",  
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "en"
            }
            
            self.debug(f"🌐 Sending GET request to {url} to fetch user info.")
            async with http_client.get(url, headers=headers) as resp:
                if resp.status == 200:
                    resp_json = await resp.json()
                    self.debug(f"📥 Received user info response: {resp_json}")
                    self.user_uuid = resp_json['id']['id']
                    self.username = resp_json['username']
                    self.avatar_file_key = resp_json.get('avatarFileKey')
                    
                    self.success(f"👤 User info updated: ID={self.user_uuid}, Username={self.username}, Avatar Key={self.avatar_file_key}")
                else:
                    self.error(f"❌ Failed to fetch user info. Status code: {resp.status}, Reason: {await resp.text()}")
        except Exception as e:
            self.error(f"❌ Error while fetching user info: {e}")

    async def run(self, proxy: str | None) -> None:
        if settings.USE_RANDOM_DELAY_IN_RUN:
            random_delay = random.randint(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Bot will start in <ly>{random_delay}s</ly>")
            await asyncio.sleep(random_delay)

        access_token = None
        refresh_token = None
        login_need = True

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await self.check_proxy(http_client=http_client, proxy=proxy)

        try:
            while True:
                if login_need:
                    if "Authorization" in http_client.headers:
                        del http_client.headers["Authorization"]

                    init_data = await self.get_tg_web_data(proxy=proxy)
                    access_token, refresh_token = await self.login(http_client=http_client, initdata=init_data)

                    http_client.headers["Authorization"] = f"Bearer {access_token}"

                    if self.first_run is not True:
                        self.success("Logged in successfully")
                        self.first_run = True

                    login_need = False

                timestamp, start_time, end_time, play_passes = await self.balance(http_client=http_client)

                if isinstance(play_passes, int):
                    self.info(f'You have {play_passes} play passes')
                    login_need = False

                msg = await self.claim_daily_reward(http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.success(f"<light-yellow>{self.session_name}</light-yellow> | Claimed daily reward!")

                claim_amount, is_available = await self.friend_balance(http_client=http_client)

                if claim_amount != 0 and is_available:
                    amount = await self.friend_claim(http_client=http_client)
                    self.success(f"Claimed friend ref reward {amount}")

                if play_passes and play_passes > 0 and settings.PLAY_GAMES is True:
                    await self.play_game(http_client=http_client, play_passes=play_passes, refresh_token=refresh_token)

                await self.join_tribe(http_client=http_client)

                tasks = await self.get_tasks(http_client=http_client)

                for task in tasks:
                    if task.get('status') == "NOT_STARTED" and task.get('type') != "PROGRESS_TARGET":
                        self.info(f"Started doing task - '{task['title']}'")
                        await self.start_task(http_client=http_client, task_id=task["id"])
                        await asyncio.sleep(0.5)

                await asyncio.sleep(5)

                tasks = await self.get_tasks(http_client=http_client)
                for task in tasks:
                    if task.get('status'):
                        if task['status'] == "READY_FOR_CLAIM" and task['type'] != 'PROGRESS_TASK':
                            status = await self.claim_task(http_client=http_client, task_id=task["id"])
                            if status:
                                logger.success(f"<light-yellow>{self.session_name}</light-yellow> | Claimed task - "
                                               f"'{task['title']}'")
                            await asyncio.sleep(0.5)
                        elif task['status'] == "READY_FOR_VERIFY" and task['validationType'] == 'KEYWORD':
                            status = await self.validate_task(http_client=http_client, task_id=task["id"],
                                                              title=task['title'])

                            if status:
                                logger.success(
                                    f"<light-yellow>{self.session_name}</light-yellow> | Validated task - "
                                    f"'{task['title']}'")

                try:
                    timestamp, start_time, end_time, play_passes = await self.balance(http_client=http_client)

                    if start_time is None and end_time is None:
                        await self.start(http_client=http_client)
                        self.info(f"<lc>[FARMING]</lc> Start farming!")

                    elif (start_time is not None and end_time is not None and timestamp is not None and
                        timestamp >= end_time):
                        timestamp, balance = await self.claim(http_client=http_client)
                        self.success(f"<lc>[FARMING]</lc> Claimed reward! Balance: {balance}")

                    elif end_time is not None and timestamp is not None:
                        sleep_duration = end_time - timestamp
                        self.info(f"<lc>[FARMING]</lc> Sleep {format_duration(sleep_duration)}")
                        login_need = True
                        await asyncio.sleep(sleep_duration)

                except Exception as e:
                    self.error(f"<lc>[FARMING]</lc> Error in farming management: {e}")

        except KeyboardInterrupt:
            logger.warning("Interrupted by user, closing session...")
        finally:
            await http_client.close()
            logger.info("Session closed successfully.")


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
        
