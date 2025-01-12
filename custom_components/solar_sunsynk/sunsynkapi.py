import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from homeassistant.core import HomeAssistant
from datetime import datetime, timedelta
from .enums import SunsynkApiNames
import requests
import json
from functools import partial
import logging
_LOGGER = logging.getLogger(__name__)
class sunsynk_api:
    def __init__(self, region, username, password,scan_interval, hass: HomeAssistant):
        self.region = region
        self.hass = hass
        self.username = username
        self.password = password
        self.scan_interval = scan_interval
        self.token = None
        self.token_expires = datetime.now()

    async def request(self, method, path, body, autoAuth):
        if autoAuth:
            if not self.token or self.token_expires <= datetime.now():
                responseAuth = await self.authenticate(self.username, self.password)
                self.token = responseAuth["data"]["access_token"]
                expires_in_seconds = responseAuth["data"]["expires_in"]
                self.token_expires = datetime.now() + timedelta(seconds=expires_in_seconds)
            headers = {
                'Content-Type': 'application/json',
                "Authorization": f"Bearer {self.token}"
            }
        else:
            headers = {
                'Content-Type': 'application/json',
            }

       # _LOGGER.error(self.region)
        if self.region == SunsynkApiNames.PowerView or self.region == 'Region 1':
            host = 'https://pv.inteless.com/'
        elif self.region == SunsynkApiNames.Sunsynk or self.region == 'Region 2': 
            host = 'https://api.sunsynk.net/'
        url = host + path
        response = await self.hass.async_add_executor_job(
            partial(self._send_request, method, url, headers, body)
        )
        return response

    def _send_request(self, method, url, headers, body):
        try:
            with requests.Session() as s:
                s.headers = headers
                if body:
                    # Added verify=False to disable SSL verification
                    response = s.request(method, url, data=json.dumps(body), verify=False)
                else:
                    # Added verify=False to disable SSL verification
                    response = s.request(method, url, verify=False)
            response.raise_for_status()  # Raise an exception if the HTTP request returned an error status
        except requests.exceptions.HTTPError as errh:
            _LOGGER.error(f"HTTP Error: {errh}")
            return None
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.error(f"Error Connecting: {errc}")
            return None
        except requests.exceptions.Timeout as errt:
            _LOGGER.error(f"Timeout Error: {errt}")
            return None
        except requests.exceptions.RequestException as err:
            _LOGGER.error(f"Something Else: {err}")
            return None
        return response.json()


            
    async def get_inverters_data(self,id):
        return await self.request('GET', f'api/v1/plant/{id}/inverters?page=1&limit=10&status=-1&sn=&id={id}&type=-2', None,True)        
    async def get_inverter_data(self,id):
        return await self.request('GET', f'api/v1/inverter/{id}', None,True)        
    async def get_inverter_load_data(self,id):
        return await self.request('GET', f'api/v1/inverter/load/{id}/realtime?sn={id}&lan=en', None,True)        
    async def get_inverter_grid_data(self,id):
        return await self.request('GET', f'api/v1/inverter/grid/{id}/realtime?sn={id}&lan=en', None,True)        
    async def get_inverter_battery_data(self,id):
        return await self.request('GET', f'api/v1/inverter/battery/{id}/realtime?sn={id}&lan=en', None,True)        
    async def get_inverter_input_data(self,id):
        return await self.request('GET', f'api/v1/inverter/{id}/realtime/input', None,True)        
    async def get_inverter_output_data(self,id):
        return await self.request('GET', f'api/v1/inverter/{id}/realtime/output', None,True)        
    # async def get_inverter_load_data(self,id):
    #     now = datetime.today().strftime('%Y-%m-%d')
    #     return await self.request('GET', f'api/v1/inverter/grid/{id}/day?lan=en&date={now}&column=pac', None,True)        
    async def get_plant_data(self):
        return await self.request('GET', f'api/v1/plants?page=1&limit=10', None,True)        
    async def get_energy_flow_data(self,id):
        return await self.request('GET', f'api/v1/plant/energy/{id}/flow', None,True)        
    async def get_realtime_data(self,id):
        return await self.request('GET', f'api/v1/plant/{id}/realtime?id={id}', None,True) 
    async def safe_fetch(self, coroutine, *args, error_message="Error"):
        """Safely fetch data using the provided coroutine function and arguments."""
        try:
            data = await coroutine(*args)
            return data
        except Exception as e:
            _LOGGER.error(f"Calling {coroutine.__name__} with args: {args}")
            _LOGGER.error(f"{error_message}: {e}")
            return None

    async def get_all_data(self):
        all_data = {}

        # Attempt to fetch plant data
        plant_data = await self.safe_fetch(self.get_plant_data, error_message="Error while getting plant data")
        if plant_data is None or "data" not in plant_data or "infos" not in plant_data["data"]:
            return None

        for plant in plant_data["data"]["infos"]:
            plant_id = plant["id"]
            inverterdata = await self.safe_fetch(self.get_inverters_data, plant_id, error_message="Error while getting inverter data")
            if inverterdata is None or "data" not in inverterdata or "infos" not in inverterdata["data"]:
                continue

            for inverter in inverterdata["data"]["infos"]:
                inverterId = inverter["sn"]
                inverter_data = await self.safe_fetch(self.get_inverter_data, inverterId, error_message="Error while getting inverter data")
                inverter_load_data = await self.safe_fetch(self.get_inverter_load_data, inverterId, error_message="Error while getting inverter load data")
                inverter_grid_data = await self.safe_fetch(self.get_inverter_grid_data, inverterId, error_message="Error while getting inverter grid data")
                inverter_battery_data = await self.safe_fetch(self.get_inverter_battery_data, inverterId, error_message="Error while getting inverter battery data")
                inverter_input_data = await self.safe_fetch(self.get_inverter_input_data, inverterId, error_message="Error while getting inverter input data")
                inverter_output_data = await self.safe_fetch(self.get_inverter_output_data, inverterId, error_message="Error while getting inverter output data")
                inverter_settings = await self.safe_fetch(self.get_settings, inverterId, error_message="Error while getting inverter settings")

                plant_sn_id = f"sunsynk_{plant_id}_{inverterId}"  
                # Add data to all_data
                all_data[plant_sn_id] = {
                    "inverter_data": inverter_data["data"] if inverter_data else None,
                    "inverter_load_data": inverter_load_data["data"] if inverter_load_data else None,
                    "inverter_grid_data": inverter_grid_data["data"] if inverter_grid_data else None,
                    "inverter_battery_data": inverter_battery_data["data"] if inverter_battery_data else None,
                    "inverter_input_data": inverter_input_data["data"] if inverter_input_data else None,
                    "inverter_output_data": inverter_output_data["data"] if inverter_output_data else None,
                    "inverter_settings_data": inverter_settings["data"] if inverter_settings else None,
                }

        return all_data
    
    
    async def get_settings(self,sn):
        return await self.request('GET', f'api/v1/common/setting/{sn}/read', None,True)
    async def set_settings(self, sn,setting_data):
        return await self.request('POST', f'api/v1/common/setting/{sn}/set', setting_data,True)
    
    def authenticate(self, username, password):
        pool_data = {
            "username": username,
            "password": password,
            'grant_type': 'password',
            'client_id': 'csp-web'
        }
        try:
            return self.request('POST', 'oauth/token', pool_data, False)
        except Exception as e:
            _LOGGER.error(f"Error during authentication: {e}")
        return None

